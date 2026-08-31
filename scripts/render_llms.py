#!/usr/bin/env python3
"""The ecosystem's llms.txt, derived from the registry.

    scripts/render_llms.py            # print it
    scripts/render_llms.py --write    # write site/llms.txt
    scripts/render_llms.py --check    # exit 1 if the committed file is stale

WHAT llms.txt IS, stated plainly because it is easy to oversell. It is a
PROPOSED convention (llmstxt.org): a markdown file at a site root giving a
model a short, link-dense map of what a site holds, so a crawler does not have
to infer the shape from HTML. No major provider has committed to consuming it.
It is cheap and it cannot hurt; it is not a substitute for the things that
demonstrably matter today, which are sitemaps, per-page descriptions and
internal links.

WHY IT LIVES HERE AND NOT AT THE DOMAIN ROOT. The convention says a SITE root,
and the natural root for this family would be `calvinchengx.github.io/llms.txt`
covering all eleven published sites at once. That is not available: the domain
root is served by a deployment last modified in April 2012, GitHub Pages is not
enabled on `calvinchengx.github.io`, and that repository's Docusaurus config
targets a different domain entirely. So the ecosystem index lives on the hub,
which is the repository that already owns the list of every member.

DERIVED, NEVER TYPED. Every entry comes from `members.json`, so a member added
to the registry appears here on the next run and a hand edit fails `--check`.
The alternative is a curated list that is wrong within a fortnight, which is
this repository's oldest lesson about itself.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "members.json"
OUT = ROOT / "site" / "llms.txt"
# The evidence table render_evidence.py writes. Read, not restated: the
# sentence about differential evidence below used to be a hand-written
# "nothing here is diffed against real Azure", and it stayed that way after
# entra started carrying `diff:` witnesses on its token endpoint. Two lines of
# this file's own output then contradicted the table two lines above it.
EVIDENCE = ROOT / "docs" / "05-why-these-emulators.md"
GITHUB = "https://github.com/calvinchengx"

# One line per tier, in the order a reader meets them. A tier absent from here
# is a tier absent from the file, which is why `--check` also asserts the set
# is complete: a new tier must be placed deliberately, not dropped silently.
SECTIONS = [
    ("emulator", "The emulators",
     "Each emulates one service, grades itself in a parity ledger, and binds "
     "every green claim to a named witness."),
    ("composition", "The certified set",
     "The bill of materials: pinned versions, the family compose, and a chain "
     "test that runs the whole set together."),
    ("core", "The data product, defined once",
     "Transforms, ODCS contracts and the expected numbers every cell must "
     "reproduce."),
    ("sources", "The source systems",
     "Four vendor systems every cell ingests from, so a difference between "
     "cells is never a difference in fixtures."),
    ("leaf", "The product, per cell",
     "One repository per (engine, orchestrator) pair, carrying only that "
     "platform's idiom."),
    ("platform", "The platform, per cell",
     "Compose, pins and provisioning for one cell. Paired one-to-one with a "
     "leaf."),
    ("application", "Built on the family",
     "Not part of the family: things built with it, each running locally "
     "against these emulators and unchanged against real Azure."),
    ("hub", "This directory",
     "The registry every list above is generated from, plus the ecosystem "
     "docs and the CI sweep."),
]


def load() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["members"]



def differential_sentence() -> str:
    """Say how much of the family is diffed against real Azure, from the table.

    Reads the `diff: vs real` column of the generated evidence block rather
    than asserting a number, so this cannot drift the way the sentence it
    replaces did.
    """
    text = EVIDENCE.read_text(encoding="utf-8")
    # Scoped to the generated block. The page holds several tables, and taking
    # the first one anywhere in the file read a different table's header and
    # reported the column missing.
    try:
        block = text.split("<!-- BEGIN evidence")[1].split("<!-- END evidence")[0]
    except IndexError:
        raise SystemExit(
            f"render_llms: no generated evidence block in {EVIDENCE.name}."
        ) from None
    rows = [
        [c.strip() for c in line.strip().strip("|").split("|")]
        for line in block.splitlines()
        if line.startswith("| ") and "---" not in line
    ]
    if not rows:
        raise SystemExit(
            f"render_llms: no evidence table in {EVIDENCE.name}. "
            "Run ./scripts/render_evidence.py first."
        )
    header, body = rows[0], rows[1:]
    try:
        col = header.index("diff: vs real")
    except ValueError:
        raise SystemExit(
            "render_llms: the evidence table has no 'diff: vs real' column. "
            "It is the source for the differential-evidence sentence; if the "
            "column was renamed, rename it here too rather than hardcoding a "
            "claim about real Azure."
        ) from None
    diffed = {r[0]: int(r[col]) for r in body if r[col].isdigit()}
    named = sorted(n for n, v in diffed.items() if v)
    if not named:
        return (
            "Nothing here is diffed against real Azure. Green means witnessed "
            "locally against real clients, which is a strong claim and a "
            "different one."
        )
    total = sum(diffed[n] for n in named)
    who = named[0] if len(named) == 1 else ", ".join(named[:-1]) + f" and {named[-1]}"
    claims = "claim" if total == 1 else "claims"
    rests = "rests" if total == 1 else "rest"
    only = " alone" if len(named) == 1 else ""
    return (
        f"Almost nothing here is diffed against real Azure: {total} green "
        f"{claims}, in {who}{only}, {rests} on a recorded comparison with a "
        f"live tenant. Everywhere else green means witnessed locally against "
        f"real clients, which is a strong claim and a different one."
    )


def render(members: list[dict]) -> str:
    by_tier: dict[str, list[dict]] = {}
    for m in members:
        by_tier.setdefault(m["tier"], []).append(m)

    known = {t for t, _, _ in SECTIONS}
    missing = sorted(set(by_tier) - known)
    if missing:
        raise SystemExit(
            f"render_llms: the registry has tier(s) {missing} that this file "
            f"does not place. Add a section for them rather than letting the "
            f"members go unlisted."
        )

    emulators = len(by_tier.get("emulator", []))
    cells = len(by_tier.get("leaf", []))
    engines = len({m["engine"] for m in by_tier.get("platform", [])})

    out = [
        "# Azure emulator family",
        "",
        "> Clean-room emulators of the control planes nobody else emulates "
        f"(Entra ID, ARM with RBAC, Key Vault, API Management) and of {engines} "
        "analytics engines (Fabric, Databricks, Snowflake), so an AI coding "
        "agent can build and PROVE Azure-shaped work on a laptop instead of in "
        "a tenant. The same code then points at the real service by changing "
        "environment variables.",
        "",
        f"{len(members)} repositories. {emulators} emulators, each with a graded "
        f"parity ledger whose green rows name the test that proves them. One "
        f"reference data product built {cells} ways across {engines} engines, "
        f"every cell reproducing the same figures.",
        "",
        differential_sentence(),
        "",
    ]

    for tier, heading, blurb in SECTIONS:
        group = by_tier.get(tier)
        if not group:
            continue
        out += [f"## {heading}", "", blurb, ""]
        for m in sorted(group, key=lambda x: x["name"]):
            target = m.get("docs") or f"{GITHUB}/{m['name']}"
            role = m.get("role")
            if not role:
                bits = [b for b in (m.get("engine"), m.get("orchestrator")) if b]
                role = " / ".join(bits) if bits else "no published site; see the repository"
            out.append(f"- [{m['name']}]({target}): {role}")
        out.append("")

    out += [
        "## Optional",
        "",
        f"- [Every repository on GitHub]({GITHUB}): source for all "
        f"{len(members)}, including the {sum(1 for m in members if not m.get('docs'))} "
        "with no published documentation site.",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--write", action="store_true")
    p.add_argument("--check", action="store_true")
    a = p.parse_args()

    want = render(load())
    if a.write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(want, encoding="utf-8")
        print(f"llms: wrote {OUT.relative_to(ROOT)}")
        return 0
    if a.check:
        if not OUT.is_file():
            print(f"llms: {OUT.relative_to(ROOT)} is missing. Run --write",
                  file=sys.stderr)
            return 1
        if OUT.read_text(encoding="utf-8") != want:
            print(f"llms: {OUT.relative_to(ROOT)} is stale. Run --write",
                  file=sys.stderr)
            return 1
        print(f"llms: {OUT.relative_to(ROOT)} matches the registry")
        return 0
    sys.stdout.write(want)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
