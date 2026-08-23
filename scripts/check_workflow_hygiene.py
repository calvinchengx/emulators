#!/usr/bin/env python3
"""Every member's workflows must parse, and every job must say what its token may do.

    scripts/check_workflow_hygiene.py
    scripts/check_workflow_hygiene.py --self-test
    scripts/check_workflow_hygiene.py --member arm-emulator

TWO FAILURES, BOTH SEEN IN ONE EVENING, both silent.

**A duplicate key stops the workflow running at all.** Two sessions added a
docs-only `changes:` job to the same four files in `arm-emulator` an hour
apart; git merged both cleanly because they touched different lines, and the
result had two `changes:` jobs, two `needs:` and two `if:`. In
`azure-emulators` one insertion put a `needs:`/`if:` pair above a condition the
job already carried. GitHub answers "this run likely failed because of a
workflow file issue" with ZERO jobs, so `ci`, `codeql` and `make-targets` were
dark for six hours and the BOM's own certification gate for two, with no
failing check to point at.

**`yaml.safe_load` cannot see it.** It accepts duplicate keys and keeps the
last, so the obvious check passes on a file GitHub rejects. The loader here
raises instead, and that is the only reason this catches anything.

**A job with no `permissions:` inherits the repository default,** which is a
write token in many configurations. That is CodeQL's
`actions/missing-workflow-permissions`, and it was open on seven jobs across
six members. A workflow-level `permissions: contents: read` covers every job;
one that needs more escalates in its own block, which overrides.

Reads each repository's published `main` over HTTP, like the rest of this
repo's family checks: no checkouts, and it reports what is released rather
than what sits in a working tree.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

REGISTRY = Path(__file__).resolve().parent.parent / "members.json"
# Repos that are family infrastructure but not registry members.
EXTRA = ("homebrew-tap",)


class Strict(yaml.SafeLoader):
    """A loader that refuses a duplicate key, which is what GitHub does."""


def _no_dupes(loader, node, deep=False):
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in seen:
            raise yaml.YAMLError(
                f"duplicate key {key!r} at line {key_node.start_mark.line + 1}"
            )
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


Strict.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _no_dupes)


def gh(path: str) -> str | None:
    got = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    return got.stdout if got.returncode == 0 else None


def workflows(repo: str) -> list[tuple[str, str]]:
    listing = gh(f"repos/calvinchengx/{repo}/contents/.github/workflows")
    if listing is None:
        return []
    out = []
    for entry in json.loads(listing):
        if not entry["name"].endswith((".yml", ".yaml")):
            continue
        raw = gh(f"repos/calvinchengx/{repo}/contents/{entry['path']}")
        if raw is None:
            continue
        import base64

        out.append((entry["name"], base64.b64decode(json.loads(raw)["content"]).decode("utf-8", "replace")))
    return out


def audit(name: str, text: str) -> list[str]:
    """What is wrong with one workflow file."""
    try:
        doc = yaml.load(text, Strict)
    except yaml.YAMLError as exc:
        return [f"{name}: INVALID, GitHub will run nothing: {str(exc).splitlines()[0]}"]
    if not isinstance(doc, dict) or "jobs" not in doc:
        return []
    if "permissions" in doc:
        return []
    bare = [
        job
        for job, body in doc["jobs"].items()
        if isinstance(body, dict) and "permissions" not in body
    ]
    if bare:
        return [
            f"{name}: {', '.join(bare)} set no `permissions:`, so the job takes the "
            f"repository default token"
        ]
    return []


def self_test() -> int:
    cases = [
        ("a healthy workflow", "on: push\npermissions:\n  contents: read\njobs:\n  a:\n    steps: []\n", 0),
        ("per-job permissions instead", "on: push\njobs:\n  a:\n    permissions:\n      contents: read\n    steps: []\n", 0),
        ("a job with no permissions", "on: push\njobs:\n  a:\n    steps: []\n", 1),
        ("one bare job among covered ones",
         "on: push\njobs:\n  a:\n    permissions:\n      contents: read\n    steps: []\n  b:\n    steps: []\n", 1),
        ("a duplicate job key", "on: push\npermissions:\n  contents: read\njobs:\n  a:\n    steps: []\n  a:\n    steps: []\n", 1),
        ("a duplicate if key",
         "on: push\npermissions:\n  contents: read\njobs:\n  a:\n    if: x\n    name: n\n    if: y\n", 1),
        ("not a workflow at all", "just: a mapping\n", 0),
    ]
    failures = 0
    for label, text, want in cases:
        got = len(audit("w.yml", text))
        ok = (got > 0) == (want > 0)
        print(f"  {'ok  ' if ok else 'FAIL'} {label}: {got} complaint(s)")
        failures += 0 if ok else 1
    print("self-test FAILED" if failures else "self-test passed")
    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--member", help="check one repository")
    args = p.parse_args()
    if args.self_test:
        return self_test()

    members = [m["name"] for m in json.loads(REGISTRY.read_text())["members"]] + list(EXTRA)
    if args.member:
        if args.member not in members:
            print(f"unknown member {args.member!r}. Known: {', '.join(sorted(members))}", file=sys.stderr)
            return 2
        members = [args.member]

    bad, files = [], 0
    for repo in members:
        for name, text in workflows(repo):
            files += 1
            bad += [f"{repo}/{c}" for c in audit(name, text)]

    if not files:
        raise SystemExit(
            "check_workflow_hygiene: read no workflow files at all. That is a "
            "broken run, not a clean family."
        )
    if bad:
        print("check_workflow_hygiene FAILED", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"workflow hygiene: {files} files across {len(members)} repos, all parse, every job scoped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
