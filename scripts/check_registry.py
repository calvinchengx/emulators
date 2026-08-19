#!/usr/bin/env python3
"""Prove members.json is a COMPLETE list of the ecosystem, not just a correct one.

This repo's whole claim is to be the master list. A registry that is merely
accurate is not enough: a new repo nobody added is invisible here, the front
door still renders perfectly, and nothing anywhere says a member is missing.
Correct-but-incomplete is the failure mode a directory cannot detect by
looking at itself, so this asks GitHub instead.

Both directions are errors:

  missing   an ecosystem-shaped repo on GitHub with no registry entry
  phantom   a registry entry with no repo behind it (renamed, deleted, typo)

The shape test is deliberately a NAMING convention rather than a topic or a
description, because names are what the family already standardises on:
`<engine>-platform-<orchestrator>`, `contoso-data-product-<engine>-<orch>`,
and `*-emulator`. When a genuinely unrelated repo matches, add it to IGNORE
with a reason. Widening the pattern to make the check pass would turn it into
a check that cannot fail.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent.parent / "members.json"

# A repo is ecosystem-shaped if its name contains one of these, or is an exact
# match below. Substrings, so `fabric-platform-airflow3` and `arm-emulator`
# both land without enumerating every cell.
PATTERNS = ("emulator", "contoso", "-platform-")
EXACT = {"azure-emulators", "emulators"}

# Repos that match the shape but are not members. Each needs a reason, so a
# future reader can tell a deliberate exclusion from a forgotten one.
IGNORE: dict[str, str] = {}


def gh_repos(owner):
    """Every non-archived repo the owner actually owns.

    `--source` drops forks: a fork of somebody's emulator is not a member, and
    including forks would make the check fail for reasons nobody can fix here.
    """
    p = subprocess.run(
        ["gh", "repo", "list", owner, "--limit", "1000", "--no-archived", "--source",
         "--json", "name,isFork,visibility"],
        capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"gh repo list failed: {p.stderr.strip()[:300]}")
    repos = json.loads(p.stdout)
    if not repos:
        # An empty listing would make every registry entry a phantom and every
        # missing repo invisible: the check would "pass" by seeing nothing.
        raise RuntimeError("gh repo list returned no repositories at all")
    return repos


def shaped(name):
    return name in EXACT or any(p in name for p in PATTERNS)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    d = json.loads(REGISTRY.read_text())
    owner = d["owner"]
    registry = {m["name"] for m in d["members"]}

    repos = gh_repos(owner)
    candidates = {r["name"] for r in repos if shaped(r["name"])}

    missing = sorted(candidates - registry - set(IGNORE))
    phantom = sorted(registry - {r["name"] for r in repos})

    if a.json:
        print(json.dumps({"owner": owner, "registry": len(registry),
                          "candidates": len(candidates),
                          "missing": missing, "phantom": phantom}, indent=2))
    else:
        print(f"registry: {len(registry)} members · "
              f"ecosystem-shaped repos under {owner}: {len(candidates)}")
        for n in missing:
            print(f"  MISSING  {n} is ecosystem-shaped and has no registry entry")
        for n in phantom:
            print(f"  PHANTOM  {n} is in the registry and does not exist")
        if not missing and not phantom:
            print("  the registry is complete")

    if missing or phantom:
        print("\nAdd the missing repos to members.json, or list one in IGNORE "
              "with a reason if it is genuinely not a member.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
