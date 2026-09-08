#!/usr/bin/env python3
"""A member whose CI proof is ageing must have something that refreshes it.

    scripts/check_ci_proof_ages.py
    scripts/check_ci_proof_ages.py --self-test
    scripts/check_ci_proof_ages.py --member arm-emulator
    scripts/check_ci_proof_ages.py --stale-days 7

WHAT THIS CATCHES, AND WHY IT IS NOT "every ci.yml needs a cron".

`ci.yml` on `push` and `pull_request` alone is fine while a repo is busy: every
commit re-proves it. It rots only when the repo goes quiet, because then
nothing re-runs it and the last green stops being a claim about today. Four
members drifted that way -- data-agent-formulator, contoso-sources,
contoso-data-product-snowflake-tasks, contoso-data-product-snowflake-airflow3 --
and each was found one at a time, by hand, after `family_ci.py` flagged it at
14 days.

THE PROXY WOULD HAVE BEEN WRONG. Requiring a `schedule` on every `ci.yml`
fails 23 of the 27 members that have one, and would impose a weekly run on
repos that commit daily and have never been stale -- including
`fabric-emulator`, whose `ci.yml` is a 47-job matrix. That is a policy change
priced in compute, dressed up as a hygiene rule.

So this gates on the DEFECT, not the proxy: a member fails only when its CI
proof is ALREADY ageing (default 7 days, half the 14 the hub flags at) AND it
has no `schedule` to refresh it. A busy repo never trips. A quiet repo trips a
week before the staleness flag, with the fix named in the message.

A member whose proof is old but DOES carry a schedule is reported, not failed:
its cron is due and will clear it, and if it does not, that is a broken cron
rather than a missing one.

Reads each repository's published `main` over HTTP, like the rest of this
repo's family checks: no checkouts, and it reports what is released rather
than what sits in a working tree.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import yaml

REGISTRY = Path(__file__).resolve().parent.parent / "members.json"
CI_PATH = ".github/workflows/ci.yml"


def gh(path: str) -> str | None:
    got = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    return got.stdout if got.returncode == 0 else None


def ci_triggers(repo: str) -> set[str] | None:
    """The `on:` keys of the member's ci.yml, or None when it has no ci.yml."""
    raw = gh(f"repos/calvinchengx/{repo}/contents/{CI_PATH}")
    if raw is None:
        return None
    text = base64.b64decode(json.loads(raw)["content"]).decode("utf-8", "replace")
    doc = yaml.safe_load(text)
    if not isinstance(doc, dict):
        return None
    # PyYAML resolves a bare `on:` to the boolean True, which is the single
    # most common way a check like this silently reads nothing.
    on = doc.get(True, doc.get("on"))
    if isinstance(on, dict):
        return set(on.keys())
    if isinstance(on, list):
        return set(on)
    return {str(on)}


def ci_age_days(repo: str, now: dt.datetime) -> float | None:
    """Age of the freshest COMPLETED ci.yml run on main. None when there is none.

    Completed, not latest: an in-flight run is not proof of anything, and
    counting it would let a queued retry mask a proof that never landed.

    A FULL PAGE, AND `updated_at`, NEITHER OF THEM OPTIONAL. The first version
    took `workflow_runs[0]["created_at"]` off a `per_page=1` request, and it
    read `azure-keyvault-emulator` as 23 days stale on CI while the same call
    from a laptop, and the hub's own sweep, both said 1 day. `family_ci.py`
    had already written down why: the API pages by `created_at` while the
    freshest result is the greatest `updated_at`, so a run that starts before
    the cutoff and finishes after it falls outside the window no matter how
    the window is sized. `per_page=1` is that window narrowed to one entry,
    and it also makes the answer depend on an ordering the API documents
    nowhere.

    So: take a page, and pick the maximum explicitly. Sorting our own page
    costs one request and depends on nothing.
    """
    raw = gh(
        f"repos/calvinchengx/{repo}/actions/workflows/ci.yml/runs"
        f"?branch=main&status=completed&per_page=100"
    )
    if raw is None:
        return None
    runs = json.loads(raw).get("workflow_runs") or []
    stamps = [r.get("updated_at") or r.get("created_at") for r in runs]
    stamps = [t for t in stamps if t]
    if not stamps:
        return None
    at = dt.datetime.fromisoformat(max(stamps).replace("Z", "+00:00"))
    return (now - at).total_seconds() / 86400.0


def verdict(repo: str, triggers: set[str] | None, age: float | None, stale_days: float):
    """(level, message) for one member. level is 'fail', 'note' or None."""
    if triggers is None:
        return None, None  # no ci.yml: check_workflow_hygiene owns that question
    if age is None:
        return ("fail", f"{repo}: ci.yml exists but has never completed a run on main")
    if age <= stale_days:
        return None, None
    if "schedule" in triggers:
        return ("note", f"{repo}: CI proof {age:.0f}d old, but a schedule is due to refresh it")
    return (
        "fail",
        f"{repo}: CI proof {age:.0f}d old and ci.yml has no `schedule` to refresh it "
        f"(triggers: {', '.join(sorted(triggers))}). Add a weekly cron, staggered off "
        f"this repo's other jobs.",
    )


def self_test() -> int:
    cases = [
        ("busy repo, no schedule", {"push", "pull_request"}, 2.0, None),
        ("quiet repo, no schedule", {"push", "pull_request"}, 9.0, "fail"),
        ("quiet repo, has schedule", {"push", "schedule"}, 9.0, "note"),
        ("exactly at the threshold", {"push"}, 7.0, None),
        ("just past the threshold", {"push"}, 7.1, "fail"),
        ("no ci.yml at all", None, None, None),
        ("ci.yml that never ran", {"push"}, None, "fail"),
    ]
    failures = 0
    for label, triggers, age, want in cases:
        got, _ = verdict("r", triggers, age, 7.0)
        ok = got == want
        print(f"  {'ok  ' if ok else 'FAIL'} {label}: {got!r} (want {want!r})")
        failures += 0 if ok else 1
    print("self-test FAILED" if failures else "self-test passed")
    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--member", help="check one repository")
    p.add_argument("--stale-days", type=float, default=7.0)
    args = p.parse_args()
    if args.self_test:
        return self_test()

    members = [m["name"] for m in json.loads(REGISTRY.read_text())["members"]]
    if args.member:
        if args.member not in members:
            print(
                f"unknown member {args.member!r}. Known: {', '.join(sorted(members))}",
                file=sys.stderr,
            )
            return 2
        members = [args.member]

    now = dt.datetime.now(dt.timezone.utc)
    bad, notes, looked = [], [], 0
    for repo in members:
        triggers = ci_triggers(repo)
        age = ci_age_days(repo, now) if triggers is not None else None
        if triggers is not None:
            looked += 1
        level, msg = verdict(repo, triggers, age, args.stale_days)
        if level == "fail":
            bad.append(msg)
        elif level == "note":
            notes.append(msg)

    if not looked:
        # Enumerate good, default deny: reading nothing is a broken run, and
        # must never render as a clean family.
        raise SystemExit(
            "check_ci_proof_ages: read no ci.yml at all. That is a broken run, "
            "not a clean family."
        )
    for note in notes:
        print(f"  note: {note}")
    if bad:
        print("check_ci_proof_ages FAILED", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(
        f"ci proof ages: {looked} members with a ci.yml, none ageing past "
        f"{args.stale_days:.0f}d without a schedule"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
