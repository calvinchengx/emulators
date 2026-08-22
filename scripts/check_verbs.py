#!/usr/bin/env python3
"""Enforce the family verb contract: the Makefile verbs every tier answers.

WHAT THIS IS FOR. "Run the medallion and tell me whether it worked" was
spelled four ways across seven platforms (`verify`, `witness`, `demo`,
`trigger`+`verify`), two emulators answered no `up` at all, and leaves ranged
from a full `up/down/run` to no Makefile. Someone who had learned one repo had
learned one repo. The contract is a FLOOR per tier, not a ceiling: a repo may
answer more, and the rest of its Makefile is its own business.

  emulator   up down logs doctor test
  platform   up down logs doctor test witness
  leaf       test
  sources    test

`witness` takes no arguments: it is the thing a launcher runs. A platform
that needs to be told which DAG derives it from the product it was pointed
at rather than asking.

READ FROM PUBLISHED MAIN, like every other gate here. A checkout can sit on a
branch; main is what a reader clones. `--local` reads sibling checkouts
instead, for pre-merge numbers, and says so in its output so the two cannot
be confused.

  ./scripts/check_verbs.py              every member, against published main
  ./scripts/check_verbs.py --local      sibling checkouts under ../
  ./scripts/check_verbs.py --self-test  prove the gate fails on a Makefile it should reject
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "members.json"
MAKEFILE_URL = "https://raw.githubusercontent.com/calvinchengx/{name}/main/Makefile"

FLOOR = {
    "emulator": ("up", "down", "logs", "doctor", "test"),
    "platform": ("up", "down", "logs", "doctor", "test", "witness"),
    "leaf": ("test",),
    "sources": ("test",),
}

# A target is a name at column 0 followed by a colon. Pattern rules (`%.o:`),
# variable assignments (`X := 1`) and recipe lines (tab-indented) do not
# match. `name: dep ## help` and `name: VAR ?= x` (a target-specific
# variable) both count, because both make `make name` answer.
TARGET = re.compile(r"^([a-z][a-z0-9_-]*):(?!=)", re.M)


def load():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["members"]


def verbs_of(makefile_text):
    return set(TARGET.findall(makefile_text))


def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as resp:
        return resp.read().decode("utf-8")


def makefile_for(member, local):
    """The member's Makefile text, or None when it has none.

    None is reported as its own failure by the caller, not folded into
    "missing every verb": a repo with no Makefile and a repo whose Makefile
    lost `up` are different defects with different fixes.
    """
    if local:
        path = ROOT.parent / member["name"] / "Makefile"
        return path.read_text(encoding="utf-8") if path.exists() else None
    try:
        return fetch(MAKEFILE_URL.format(name=member["name"]))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise


def check(members, local):
    """Returns complaints, one per member that falls below its floor."""
    bad = []
    for m in members:
        floor = FLOOR.get(m["tier"])
        if floor is None or m.get("status") == "reserved":
            continue
        text = makefile_for(m, local)
        if text is None:
            bad.append(f"{m['name']} ({m['tier']}): no Makefile, so it answers none of: {' '.join(floor)}")
            continue
        missing = [v for v in floor if v not in verbs_of(text)]
        if missing:
            bad.append(f"{m['name']} ({m['tier']}): missing {' '.join(missing)}")
    return bad


def self_test():
    """Prove the gate fails on a Makefile it should reject.

    Each case is a Makefile that LOOKS like it answers a verb and does not:
    the verb in a comment, in a variable, in a recipe line, or as a
    pattern. If any of these passes, the gate reads prose as a target.
    """
    cases = [
        ("the verb only in a comment", "# up: start things\ntest:\n\techo ok\n", {"up"}),
        ("the verb only as a variable", "up := yes\ntest:\n\techo ok\n", {"up"}),
        ("the verb only in a recipe line", "test:\n\tup:\n", {"up"}),
        ("an empty Makefile", "", {"test"}),
    ]
    ok = True
    for label, text, expect_missing in cases:
        found = verbs_of(text)
        if not (expect_missing - found) == expect_missing:
            print(f"SELF-TEST FAILED: {label} was read as answering {sorted(expect_missing & found)}")
            ok = False
    # And the positive direction, because a regex that matches nothing also
    # passes every negative case above.
    good = "up: ## start\n\tdocker up\nwitness: DAG ?= x\nwitness: verify\ntest:\n\tpytest\n"
    if not {"up", "witness", "test"} <= verbs_of(good):
        print(f"SELF-TEST FAILED: a well-formed Makefile was read as {sorted(verbs_of(good))}")
        ok = False
    print("self-test: the gate rejects each look-alike and reads real targets" if ok else "")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", action="store_true",
                    help="read sibling checkouts under ../ instead of published main")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    members = load()
    bad = check(members, args.local)
    where = "sibling checkouts (pre-merge)" if args.local else "published main"
    if bad:
        for line in bad:
            print(f"  {line}")
        print(f"\n{len(bad)} member(s) below the verb floor, read from {where}. "
              "See docs/09-the-ontology.md, 'The verb contract'.")
        return 1
    checked = [m for m in members if m["tier"] in FLOOR and m.get("status") != "reserved"]
    print(f"verbs: {len(checked)} members answer their tier's floor, read from {where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
