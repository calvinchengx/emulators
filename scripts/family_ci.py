#!/usr/bin/env python3
"""Family CI status across every repo in members.json.

Answers "is the ecosystem green?" without opening 25 Actions tabs.

Two independent questions, because either one alone lies:

  A. Is the tip of main green right now?  One batched GraphQL query, every
     repo aliased into it. All 25 cost 1 point of the 5000/hour budget.

  B. For each workflow, what did its most recent COMPLETED run on main
     conclude, and how long ago?  One REST call per repo.

A alone is a false all-clear. azure-emulators reports rollup=SUCCESS while its
Docs site workflow is absent from that rollup entirely: the head commit touched
only docker-compose.yml and a script, and the workflow is path-filtered. The
rollup was green partly because things did not run. B is what catches a
workflow that has been broken for weeks because nobody touched its paths.

Python rather than shell on purpose: the loop that would drive this in zsh
(`for r in $REPOS`) iterates once over the whole blob and reports success
having checked nothing.
"""
import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent.parent / "members.json"

# GitHub generates these itself (Dependabot, dependency graph). They are not
# the repo's own CI and their run names are dynamic, one per update, so they
# flood the table if left in.
GENERATED_PREFIX = "dynamic/"

# Conclusions that are neither pass nor fail. Folding these into either one
# would be a fabrication: entra's flutter-e2e is cancelled right now, and
# calling that green hides a gap while calling it red invents a failure.
NEUTRAL = {"cancelled", "skipped", "neutral", "stale", "action_required"}

OK, BAD, MEH, UNKNOWN, ERROR = "ok", "red", "neutral", "unknown", "ERROR"


class GhError(RuntimeError):
    """A gh failure, carrying GitHub's own message separately from the command.

    The split matters. A first cut at the self-test asserted on str(exception),
    which included the echoed query, so the bogus repo NAME appeared in the
    message no matter why gh failed. The test passed on a network error just as
    happily as on a missing repo: green for the wrong reason.
    """

    def __init__(self, command, detail):
        super().__init__(f"{command} failed: {detail[:400]}")
        self.detail = detail


def gh(*args):
    """Run gh, returning parsed JSON. Raises on failure rather than returning
    an empty result, so an API error can never read as 'nothing wrong here'."""
    p = subprocess.run(["gh", *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise GhError(f"gh {args[0]} {args[1] if len(args) > 1 else ''}",
                      p.stderr.strip())
    return json.loads(p.stdout)


def load_registry(path=REGISTRY):
    d = json.loads(path.read_text())
    return d["owner"], [m for m in d["members"]]


def rollups(owner, names):
    """Question A, for every repo in one request."""
    fields = "\n".join(
        f'  r{i}: repository(owner:"{owner}", name:"{n}") {{ ...S }}'
        for i, n in enumerate(names)
    )
    query = (
        "query {\n" + fields + "\n}\n"
        "fragment S on Repository { name defaultBranchRef { name target { "
        "... on Commit { oid committedDate statusCheckRollup { state } } } } }"
    )
    data = gh("api", "graphql", "-f", f"query={query}")
    out = {}
    if data.get("errors"):
        # A missing repo comes back as an error entry with the rest of the data
        # still present. Surface it rather than letting the row vanish.
        for e in data["errors"]:
            out.setdefault("_errors", []).append(e.get("message", str(e)))
    for v in (data.get("data") or {}).values():
        if not v:
            continue
        ref = v.get("defaultBranchRef")
        target = (ref or {}).get("target") or {}
        roll = target.get("statusCheckRollup") or {}
        out[v["name"]] = {
            "branch": (ref or {}).get("name"),
            "sha": target.get("oid", "")[:8],
            "at": target.get("committedDate"),
            "state": roll.get("state"),  # None when no checks ran on this commit
        }
    return out


def workflows(owner, name):
    """Question B: latest COMPLETED run per workflow on main.

    Asks PER WORKFLOW rather than filtering one shared page of runs. The shared
    page is what the first version did and it silently reported stale results:
    fabric-emulator has 2030 completed runs on main, so 100 of them span about
    34 hours, and any workflow quieter than that is represented in the window
    by an OLD run. It reported sempy.yml as failing off an August 12 run when
    the workflow had gone green on August 19.

    The subtler half is why a bigger page would not have fixed it. The API
    pages by created_at while the freshest result is the greatest updated_at,
    so a long run that started before the cutoff but finished after it is
    absent from the page no matter how the page is sized, and a staler run
    inside the window wins the comparison. One request per workflow, newest
    first, has no window to fall out of.

    Completed only. An earlier watcher took the newest run whatever its status,
    so an in-flight retry cleared a known failure and it announced the red was
    gone while main was still broken.
    """
    meta = gh("api", f"repos/{owner}/{name}/actions/workflows")
    best = {}
    for wf in meta.get("workflows", []):
        # GitHub generates these (Dependabot, dependency graph); they are not
        # the repo's own CI and their run names carry the update number.
        if wf["state"] != "active" or wf["path"].startswith(GENERATED_PREFIX):
            continue
        runs = gh("api", f"repos/{owner}/{name}/actions/workflows/{wf['id']}/runs"
                         f"?branch=main&status=completed&per_page=1")
        got = runs.get("workflow_runs") or []
        if got:
            best[wf["id"]] = got[0]
    return [
        {
            "file": r["path"].rsplit("/", 1)[-1],
            "name": r["name"],
            "conclusion": r["conclusion"],
            "at": r["updated_at"],
            "url": r["html_url"],
            # What fired it, and which commit it proved. A schedule-driven
            # workflow lags main by design, so "red" and "has not re-run since
            # the fix" look identical without these two.
            "event": r.get("event"),
            "sha": (r.get("head_sha") or "")[:7],
        }
        for r in sorted(best.values(), key=lambda r: r["path"])
    ]


def age_days(iso, now):
    if not iso:
        return None
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return (now - t).total_seconds() / 86400


def classify(member, roll, wfs, stale_days, now, others_red=False, tip_sha=None):
    """One verdict per member. Every branch is a state a reader can act on."""
    expect = member["ci"]
    # Workflows the registry declares conditional run only when a precondition
    # holds, so `skipped` is their healthy state rather than a gap. attribute.yml
    # is the worked example: it bisects a failed acceptance run, so it is inert
    # exactly when the repo is well. Counting that as "needs a look" made a
    # healthy repo read amber and trained the reader to ignore the colour.
    conditional = set(member.get("conditional") or [])
    wfs = [w for w in wfs
           if not (w["file"] in conditional and w["conclusion"] == "skipped")]
    reds = [w for w in wfs if w["conclusion"] == "failure" or w["conclusion"] == "timed_out"]
    neutrals = [w for w in wfs if w["conclusion"] in NEUTRAL]
    ages = [a for a in (age_days(w["at"], now) for w in wfs) if a is not None]
    oldest = max(ages) if ages else None

    if expect == "required" and not wfs:
        # Declared to have CI and has none. Never a blank row: this is the
        # shape of a workflow that was deleted or renamed into oblivion.
        return ERROR, "expects CI, no completed runs on main"
    if expect == "missing":
        return (ERROR if wfs else MEH), (
            "now has CI, registry says missing" if wfs
            else "substantive code, no CI at all")
    if expect == "none":
        return (ERROR if wfs else OK), (
            "reserved but has CI, registry stale" if wfs else "reserved, nothing to verify")
    if reds:
        def label(w):
            # A schedule-driven or dispatch-driven workflow does not run on
            # push, so its verdict can predate the commit that fixed it. Saying
            # so is the difference between "this is broken" and "nobody has
            # asked it since". The sweep still reports the failure, because the
            # newest ANSWER is the only honest one; it just stops the reader
            # concluding the tip is broken when the tip was never tested.
            stale = tip_sha and w.get("sha") and not tip_sha.startswith(w["sha"])
            via = f", last ran on {w['sha']} via {w['event']}" if stale else ""
            return f"{w['file']}={w['conclusion']}{via}"
        note = ", ".join(label(w) for w in reds)
        # THE REPORTER CANNOT REPORT ON ITSELF, and reading its own last run as
        # evidence made this sweep unable to recover.
        #
        # It fails by design when a member is red, so its own row repeated the
        # ecosystem's breakage as though the hub were broken too. The first fix
        # explained that away only while ANOTHER member was red, reasoning that
        # a reporter failing alone must be a real defect in the gate.
        #
        # That reasoning has a deadlock in it. Run N fails because member X is
        # red. X is fixed. Run N+1 now sees nothing else red, and the reporter's
        # last conclusion is still N's failure, so it reports a defect and fails.
        # Run N+2 sees N+1's failure. The sweep stays red forever, having been
        # red once, and a health check that cannot go green is one people stop
        # reading. Observed: three consecutive scheduled runs failing with every
        # other member green.
        #
        # So the reporter's own previous conclusion is dropped from its row. It
        # is not evidence about the present: THIS run supersedes it, and the
        # verdict is this run's exit code, which Actions already shows. Nothing
        # is lost, because a gate that is genuinely broken fails right here and
        # says so in its own status rather than in a row it wrote about itself.
        reporter = member.get("reporter")
        if reporter and [w["file"] for w in reds] == [reporter]:
            if others_red:
                return BAD, f"{note} (mirrors the rows below, not a defect here)"
            return OK, ""
        return BAD, note
    if neutrals:
        return MEH, ", ".join(f"{w['file']}={w['conclusion']}" for w in neutrals)
    if oldest is not None and oldest > stale_days:
        return MEH, f"green, oldest proof {oldest:.0f}d old"
    return OK, ""


def collect(owner, members, stale_days, require_rollup=True):
    """Gather both questions for every member.

    The rollup (question A) is a nice-to-have and is allowed to fail: GraphQL
    refuses unauthenticated callers, while the REST runs endpoint serves public
    repos to anyone. Question B is the one that finds real breakage, so losing A
    degrades the report rather than ending it. The degradation is printed, never
    silent, because a column that quietly turns into "unknown" for everyone is
    indistinguishable from a healthy fleet.
    """
    now = datetime.now(timezone.utc)
    names = [m["name"] for m in members]
    try:
        roll = rollups(owner, names)
    except GhError as e:
        if require_rollup:
            raise
        print(f"family_ci: rollup unavailable, reporting per-workflow only "
              f"({e.detail[:120]})", file=sys.stderr)
        roll = {}
    # Gather first, classify second: whether a reporter's failure is a mirror
    # or a real defect depends on the other members, so no row can be judged
    # until every row has been fetched.
    gathered = [(m, workflows(owner, m["name"])) for m in members]
    others_red = {
        m["name"]: any(
            any(w["conclusion"] in ("failure", "timed_out") for w in owfs)
            for om, owfs in gathered if om["name"] != m["name"])
        for m, _ in gathered}
    rows = []
    for m, wfs in gathered:
        r0 = roll.get(m["name"], {})
        verdict, note = classify(m, r0, wfs, stale_days, now,
                                 others_red=others_red[m["name"]],
                                 tip_sha=r0.get("sha"))
        r = roll.get(m["name"], {})
        rows.append({
            "name": m["name"], "tier": m["tier"], "ci": m["ci"],
            "verdict": verdict, "note": note,
            "tip": r.get("state") or "no checks on tip",
            "sha": r.get("sha"), "workflows": wfs,
            "oldest_days": max([a for a in (age_days(w["at"], now) for w in wfs)
                                if a is not None], default=None),
        })
    return rows


MARK = {OK: "🟢", BAD: "🔴", MEH: "🟡", UNKNOWN: "⚪", ERROR: "🟠"}


def render(rows, red_only=False):
    if red_only:
        rows = [r for r in rows if r["verdict"] in (BAD, ERROR, MEH)]
        if not rows:
            return "All members green. Nothing red, neutral or misdeclared.\n"
    out = ["## Family CI", "",
           "| | member | tier | tip of main | workflows | oldest proof | note |",
           "|---|---|---|---:|---:|---:|---|"]
    for r in rows:
        age = f"{r['oldest_days']:.0f}d" if r["oldest_days"] is not None else "-"
        out.append(
            f"| {MARK[r['verdict']]} | `{r['name']}` | {r['tier']} | {r['tip'].lower()} "
            f"| {len(r['workflows'])} | {age} | {r['note']} |")
    c = Counter(r["verdict"] for r in rows)
    out += ["",
            f"**{c[OK]} green · {c[BAD]} red · {c[MEH]} needs a look · "
            f"{c[ERROR]} misdeclared**, across {len(rows)} members.", "",
            "`tip of main` is the head commit's check rollup and goes blank when a",
            "path-filtered workflow did not run on that commit, so it is never read",
            "alone. `oldest proof` is the age of the stalest workflow's last completed",
            "run: a green that old is a claim about last week.", ""]
    return "\n".join(out)


def render_member(rows, name):
    r = next((x for x in rows if x["name"] == name), None)
    if r is None:
        return None
    out = [f"## `{r['name']}`", "",
           f"{MARK[r['verdict']]} **{r['verdict']}**"
           + (f" — {r['note']}" if r["note"] else ""),
           "", f"tier {r['tier']} · registry expects CI: {r['ci']} · "
           f"tip of main {r['tip'].lower()} @ {r['sha']}", "",
           "| workflow | last completed | when | run |", "|---|---|---|---|"]
    now = datetime.now(timezone.utc)
    for w in r["workflows"]:
        a = age_days(w["at"], now)
        out.append(f"| `{w['file']}` | {w['conclusion']} | {a:.0f}d ago | [run]({w['url']}) |")
    if not r["workflows"]:
        out.append("| _none_ | | | |")
    return "\n".join(out) + "\n"


def self_test(owner):
    """A repo name that cannot resolve must fail loudly, not skip the row.

    check_family_pins.py earned this the hard way: a silently unfetchable entry
    is a check that passes by not looking.
    """
    bogus = [{"name": "calvinchengx-no-such-repo-0000", "tier": "leaf", "ci": "required"}]
    try:
        collect(owner, bogus, 7, require_rollup=True)
    except GhError as e:
        # Assert on GitHub's own words, not on the echoed command: the repo name
        # is in the command either way, so matching it proves nothing.
        if "Could not resolve to a Repository" in e.detail:
            print("self-test: unresolvable member fails loudly, as intended")
            return 0
        print(f"self-test: gh failed, but not because the repo is missing: "
              f"{e.detail[:200]}", file=sys.stderr)
        return 1
    print("self-test: a bogus repo produced no error, the gate is blind",
          file=sys.stderr)
    return 1


def self_test_reporter(now=None):
    """The reporter must recover, and must not go blind doing it.

    Dropping the reporter's own last conclusion from its own row is what lets
    this sweep return to green after a member is fixed. Done carelessly it also
    stops the hub reporting ANY failure of its own, so the four cases that
    surround the one exception are asserted here, not just the exception.
    """
    import datetime

    now = now or datetime.datetime.now(datetime.timezone.utc)
    at = now.isoformat().replace("+00:00", "Z")

    def wf(file, conclusion):
        return {"file": file, "conclusion": conclusion, "sha": "abc",
                "event": "schedule", "at": at}

    hub = {"name": "emulators", "tier": "hub", "ci": "required",
           "reporter": "family-ci.yml"}
    leaf = {"name": "a-leaf", "tier": "leaf", "ci": "required"}
    cases = [
        ("reporter red alone recovers", hub, [wf("family-ci.yml", "failure")], False, OK),
        ("reporter red beside a red member still reports", hub,
         [wf("family-ci.yml", "failure")], True, BAD),
        ("an ordinary red member still fails the gate", leaf,
         [wf("ci.yml", "failure")], False, BAD),
        ("the hub's OWN other workflow still fails the gate", hub,
         [wf("docs.yml", "failure")], False, BAD),
        ("reporter plus another of the hub's own still fails", hub,
         [wf("family-ci.yml", "failure"), wf("docs.yml", "failure")], False, BAD),
    ]
    wrong = 0
    for name, member, wfs, others_red, want in cases:
        got, _ = classify(member, None, wfs, 7, now, others_red=others_red, tip_sha="abc")
        if got != want:
            print(f"self-test: {name}: got {got}, want {want}", file=sys.stderr)
            wrong += 1
    if wrong:
        return 1
    print(f"self-test: the reporter recovers, and still reports {len(cases) - 1} "
          f"other failures")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("member", nargs="?", help="one member, in detail")
    ap.add_argument("--red-only", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--stale-days", type=int, default=14)
    ap.add_argument("--fail-on-red", action="store_true",
                    help="exit 1 when any member is red or misdeclared")
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--no-rollup-required", action="store_true",
                    help="continue when GraphQL is unavailable (CI default)")
    a = ap.parse_args()

    owner, members = load_registry()
    if a.self_test:
        return self_test(owner) or self_test_reporter()

    if a.member:
        known = [m["name"] for m in members]
        if a.member not in known:
            print(f"unknown member: {a.member}\nknown: {', '.join(known)}",
                  file=sys.stderr)
            return 2
        members = [m for m in members if m["name"] == a.member]

    rows = collect(owner, members, a.stale_days,
                   require_rollup=not a.no_rollup_required)

    if a.json:
        print(json.dumps({
            "generated": datetime.now(timezone.utc).isoformat(),
            "members": rows}, indent=2))
    elif a.member:
        print(render_member(rows, a.member))
    else:
        print(render(rows, red_only=a.red_only))

    if a.fail_on_red and any(r["verdict"] in (BAD, ERROR) for r in rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
