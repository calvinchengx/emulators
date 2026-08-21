#!/usr/bin/env python3
"""Enforce the ontology in docs/09-the-ontology.md against members.json.

WHAT THIS IS FOR. The registry already carried a vocabulary -- tier, engine,
orchestrator -- and nothing checked it. `tier` accepted any string, so a typo
made a new tier; a leaf could name an engine no platform served and the gap
read as silence. The schema closes the value sets; this closes the shapes and
the relations between members.

DERIVED, NOT LISTED, and that is the point. `pairs_with` is not a field: it is
equality of (engine, orchestrator) across a leaf and a platform. A field would
let a leaf name a platform that does not exist and nothing would notice. As a
derivation, the ABSENCE is the error.

  ./scripts/check_ontology.py          the structural invariants (1-5)
  ./scripts/check_ontology.py --bom    also check `bom` against azure-emulators

`--bom` reaches the network. It is separate because a structural check should
not fail when GitHub is unreachable, and because a gate that needs the network
to say anything is one people learn to ignore.
"""
import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "members.json"

# What the BOM actually stands up, read from where it is PUBLISHED rather than
# from a checkout that may be sitting on a branch.
#
# ONE SOURCE, AND IT IS THE COMPOSE. A first draft of this also read a
# `docs/family.json`, on the theory that two sources disagreeing is a finding.
# That file does not exist -- it 404s -- and the code caught the error and
# carried on, so the "second source" contributed nothing while making the
# check look twice as thorough as it was. An imaginary corroborator is worse
# than one honest source, because it is the reason nobody looks harder.
#
# The compose is the right single source anyway: it is what the chain test
# actually runs, which is the operative meaning of "certified".
BOM_COMPOSE = "https://raw.githubusercontent.com/calvinchengx/azure-emulators/main/docker-compose.yml"

# `image: ghcr.io/calvinchengx/<name>:` -- matched on the image reference, not
# on the name appearing anywhere in the file, so a mention in a comment or a
# volume name cannot be read as membership.
BOM_IMAGE = re.compile(r"image:\s*ghcr\.io/calvinchengx/([a-z0-9-]+):")

FIELDS_BY_TIER = {
    "emulator": {"kind", "bom"},
    "leaf": {"engine", "orchestrator"},
    "platform": {"engine", "orchestrator"},
}


def load():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["members"]


def structural(members):
    """Invariants 1-4. Returns a list of complaints, empty when well-formed."""
    bad = []

    # 2 and 3: a field belongs to its tier and to no other.
    for m in members:
        want = FIELDS_BY_TIER.get(m["tier"], set())
        for field in {"kind", "bom", "engine", "orchestrator"}:
            present = field in m
            allowed = field in want
            if present and not allowed:
                bad.append(f"{m['name']}: tier {m['tier']} must not carry `{field}`")
            if allowed and not present:
                bad.append(f"{m['name']}: tier {m['tier']} must carry `{field}`")

    # 4: one member per (engine, orchestrator, tier).
    seen = Counter(
        (m["engine"], m["orchestrator"], m["tier"])
        for m in members
        if m["tier"] in ("leaf", "platform")
    )
    for (engine, orch, tier), n in sorted(seen.items()):
        if n > 1:
            bad.append(f"{n} {tier}s claim the cell ({engine}, {orch}); a cell is one of each")

    # 1: pairs_with, derived. The absence is the error, and it is reported as
    # an UNPAIRED member rather than a missing edge -- a reader can act on the
    # first and not the second.
    cells = defaultdict(dict)
    for m in members:
        if m["tier"] in ("leaf", "platform"):
            cells[(m["engine"], m["orchestrator"])][m["tier"]] = m["name"]
    for cell, halves in sorted(cells.items()):
        if "leaf" not in halves:
            bad.append(f"cell {cell[0]} / {cell[1]}: platform {halves['platform']} has no leaf")
        if "platform" not in halves:
            bad.append(f"cell {cell[0]} / {cell[1]}: leaf {halves['leaf']} has no platform")

    return bad


def fetch(url):
    with urllib.request.urlopen(url, timeout=20) as resp:
        return resp.read().decode("utf-8")


def bom_members():
    """The emulator images the family compose stands up, from published main.

    REFUSES AN EMPTY ANSWER. A fetch that succeeds and matches nothing would
    report every declared member as "not in the compose", which reads as
    twenty violations rather than as a broken checker -- so an empty match is
    the checker's own failure and says so.
    """
    compose = fetch(BOM_COMPOSE)
    found = {m.group(1) for m in BOM_IMAGE.finditer(compose)}
    emulators = {n for n in found if n.endswith("-emulator")}
    if not emulators:
        raise SystemExit(
            "the family compose named no emulator images: the URL or the "
            "image convention has moved, and this check is not measuring "
            f"anything. Fetched {len(compose)} bytes from {BOM_COMPOSE}"
        )
    return emulators


def check_bom(members):
    declared = {m["name"] for m in members if m["tier"] == "emulator" and m.get("bom")}
    in_compose = bom_members()

    bad = []
    if in_compose != declared:
        bad.append(
            f"bom disagrees with the family compose: "
            f"declared-not-composed {sorted(declared - in_compose)}, "
            f"composed-not-declared {sorted(in_compose - declared)}"
        )
    return bad


def self_test():
    """Prove the gate fails on a registry it should reject.

    A checker nobody has watched fail is a checker nobody knows the direction
    of. Each case below is one invariant, broken deliberately.
    """
    cases = [
        ("a leaf with no platform",
         [{"name": "l", "tier": "leaf", "status": "built", "ci": "required",
           "engine": "fabric", "orchestrator": "jobs"}]),
        ("two leaves in one cell",
         [{"name": "a", "tier": "leaf", "status": "built", "ci": "required",
           "engine": "fabric", "orchestrator": "jobs"},
          {"name": "b", "tier": "leaf", "status": "built", "ci": "required",
           "engine": "fabric", "orchestrator": "jobs"},
          {"name": "p", "tier": "platform", "status": "built", "ci": "required",
           "engine": "fabric", "orchestrator": "jobs"}]),
        ("an emulator with no kind",
         [{"name": "e", "tier": "emulator", "status": "built", "ci": "required",
           "bom": True}]),
        ("a core carrying an engine",
         [{"name": "c", "tier": "core", "status": "built", "ci": "required",
           "engine": "fabric"}]),
    ]
    ok = True
    for label, members in cases:
        if not structural(members):
            print(f"SELF-TEST FAILED: {label} was accepted")
            ok = False
    if structural(load()):
        print("SELF-TEST FAILED: the real registry does not pass")
        ok = False
    print("self-test: the gate rejects each broken shape and accepts the registry" if ok else "")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bom", action="store_true",
                    help="also check `bom` against azure-emulators (needs the network)")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    members = load()
    bad = structural(members)
    if args.bom:
        bad += check_bom(members)

    if bad:
        for line in bad:
            print(f"  {line}")
        print(f"\n{len(bad)} ontology violation(s). See docs/09-the-ontology.md.")
        return 1

    cells = {(m["engine"], m["orchestrator"]) for m in members if m["tier"] == "leaf"}
    emulators = [m for m in members if m["tier"] == "emulator"]
    print(f"ontology: {len(members)} members, {len(cells)} cells paired, "
          f"{sum(1 for m in emulators if m['bom'])} of {len(emulators)} emulators in the BOM"
          + (" (checked against azure-emulators)" if args.bom else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
