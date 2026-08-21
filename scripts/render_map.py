#!/usr/bin/env python3
"""Render docs/map.svg from members.json.

WHY THIS IS GENERATED. The tables beside it already are, and the diagram was
the one artefact still hand-drawn: seven leaves collapsed into one node, seven
platforms into another, and six edges carrying six different phrasings for
what turned out to be five relations. It showed the ecosystem's shape by
describing it rather than by having it.

WHAT IT DRAWS IS THE ONTOLOGY, nothing else. Entities are boxes coloured by
tier, cells are rows derived from (engine, orchestrator), and the only edges
are the five relations in docs/09-the-ontology.md. Health -- status, ci, the
sweep -- is deliberately absent: it changes hourly and would make the map
stale every time a workflow runs.

  ./scripts/render_map.py           write docs/map.svg and docs/map-dark.svg
  ./scripts/render_map.py --check   exit 1 if either is out of date
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "members.json"
LIGHT = ROOT / "docs" / "map.svg"
DARK = ROOT / "docs" / "map-dark.svg"

# 1040, not 900. At 900 the platform name and the leaf name in the
# notebook-pipelines row left an 8px gap between them -- measured, not eyed,
# after a first render put them nearly on top of each other.
W = 1040
PAD = 28
ROW_L, ROW_R = PAD + 226, W - PAD          # the cell row's span
COL_PLATFORM = ROW_L + 190
COL_LEAF = ROW_R - 14

# One palette per tier, and the tier IS the meaning. Two stops each: fill and
# the text that sits on it, picked so the pair clears WCAG AA at 14px in both
# themes rather than by eye.
THEMES = {
    "light": {
        "page": "none", "ink": "#1f2328", "muted": "#59636e", "line": "#8c959f",
        "emulator": ("#FAECE7", "#712B13", "#D85A30"),
        "platform": ("#E1F5EE", "#085041", "#1D9E75"),
        "product":  ("#EEEDFE", "#3C3489", "#7F77DD"),
        "neutral":  ("#F1EFE8", "#444441", "#888780"),
    },
    "dark": {
        "page": "none", "ink": "#e6edf3", "muted": "#9198a1", "line": "#6e7681",
        "emulator": ("#4A1B0C", "#F5C4B3", "#D85A30"),
        "platform": ("#04342C", "#9FE1CB", "#1D9E75"),
        "product":  ("#26215C", "#CECBF6", "#7F77DD"),
        "neutral":  ("#2C2C2A", "#D3D1C7", "#888780"),
    },
}

TIER_PALETTE = {
    "emulator": "emulator", "platform": "platform",
    "leaf": "product", "core": "product",
    "sources": "neutral", "composition": "neutral", "hub": "neutral",
}

ENGINE_LABEL = {"fabric": "Fabric", "databricks": "Databricks", "snowflake": "Snowflake"}
ORCH_LABEL = {
    "airflow3": "Airflow 3",
    "airflow-builtin": "Built-in Airflow",
    "notebook-pipelines": "Notebooks + Pipelines",
    "jobs": "Jobs",
    "tasks": "Tasks",
}
KIND_LABEL = {
    "identity": "identity", "control-plane": "control plane",
    "secrets": "secrets", "gateway": "gateway", "engine": "engine",
}
ENGINE_ORDER = ["fabric", "databricks", "snowflake"]
ORCH_ORDER = ["airflow-builtin", "airflow3", "notebook-pipelines", "jobs", "tasks"]


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def load():
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["members"]


def box(x, y, w, h, fill, stroke, rx=6):
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>')


def text(x, y, s, fill, size=13, weight=400, anchor="start"):
    return (f'<text x="{x}" y="{y}" fill="{fill}" font-size="{size}" '
            f'font-weight="{weight}" text-anchor="{anchor}" '
            f'font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif">'
            f'{esc(s)}</text>')


def render(members, theme_name):
    t = THEMES[theme_name]
    out = []

    by_tier = defaultdict(list)
    for m in members:
        by_tier[m["tier"]].append(m)

    cells = defaultdict(dict)
    for m in members:
        if m["tier"] in ("leaf", "platform"):
            cells[(m["engine"], m["orchestrator"])][m["tier"]] = m

    y = PAD

    # Shared inputs. Everything below depends on these two and nothing else.
    core = by_tier["core"][0]
    src = by_tier["sources"][0]
    pf, pt, ps = t["product"]
    nf, nt, ns = t["neutral"]
    half = (W - 2 * PAD - 20) // 2
    out.append(box(PAD, y, half, 54, pf, ps))
    out.append(text(PAD + 16, y + 23, core["name"], pt, 14, 500))
    out.append(text(PAD + 16, y + 41, "transforms, contracts, expected numbers", pt, 12))
    out.append(box(PAD + half + 20, y, half, 54, nf, ns))
    out.append(text(PAD + half + 36, y + 23, src["name"], nt, 14, 500))
    out.append(text(PAD + half + 36, y + 41, "four vendor systems, materialised not committed", nt, 12))
    y += 54 + 26

    out.append(text(PAD, y, "pins_by_tag ↓ every leaf", t["muted"], 12))
    out.append(text(PAD + half + 20, y, "materialises_from ↓ every platform", t["muted"], 12))
    y += 18

    # The cells. One row per (engine, orchestrator), grouped by engine, with
    # the engine emulator spanning its group -- which is `targets`, drawn as
    # containment rather than as three identical arrows.
    ef, et, es = t["emulator"]
    tf, tt, ts = t["platform"]

    # Column headers. Without them the two repository names in a row are just
    # two strings, and a reader has to infer which half of the cell each one
    # is -- exactly the guessing the ontology exists to remove.
    out.append(text(ROW_L + 14, y, "orchestrator", t["muted"], 12))
    out.append(text(COL_PLATFORM, y, "platform repository", t["muted"], 12))
    out.append(text(COL_LEAF, y, "leaf, under contoso-data-product-", t["muted"], 12, anchor="end"))
    y += 12
    row_h, row_gap, group_gap = 34, 6, 16
    engines = {m["engine"]: m for m in by_tier["emulator"] if m["kind"] == "engine"}

    for engine in ENGINE_ORDER:
        rows = [
            (orch, cells[(engine, orch)])
            for orch in ORCH_ORDER
            if (engine, orch) in cells
        ]
        gh = len(rows) * row_h + (len(rows) - 1) * row_gap + 20
        out.append(box(PAD, y, 210, gh, ef, es))
        emu = engines[engine]
        out.append(text(PAD + 16, y + 26, emu["name"], et, 14, 500))
        bom = "in the BOM" if emu["bom"] else "adjacent, not in the BOM"
        out.append(text(PAD + 16, y + 44, bom, et, 12))

        ry = y + 10
        for orch, halves in rows:
            out.append(box(ROW_L, ry, ROW_R - ROW_L, row_h, tf, ts, rx=5))
            out.append(text(ROW_L + 14, ry + 22, ORCH_LABEL[orch], tt, 13, 500))
            out.append(text(COL_PLATFORM, ry + 22, halves["platform"]["name"], tt, 12))
            leaf = halves["leaf"]["name"].replace("contoso-data-product-", "")
            out.append(text(COL_LEAF, ry + 22, leaf, tt, 12, anchor="end"))
            ry += row_h + row_gap
        y += gh + group_gap

    y += 10
    out.append(text(PAD, y, "pairs_with → derived from (engine, orchestrator); "
                            "targets → the emulator each group sits in", t["muted"], 12))
    y += 24

    # Cross-cutting emulators. One row, because an arrow from every platform
    # to every one of them is four times seven edges and no information.
    cross = [m for m in by_tier["emulator"] if m["kind"] != "engine"]
    cw = (W - 2 * PAD - 3 * 12) // 4
    out.append(text(PAD, y, "in every stack, whatever the engine", t["muted"], 12))
    y += 12
    for i, m in enumerate(cross):
        x = PAD + i * (cw + 12)
        out.append(box(x, y, cw, 52, ef, es))
        out.append(text(x + 14, y + 22, m["name"], et, 13, 500))
        out.append(text(x + 14, y + 40, KIND_LABEL[m["kind"]], et, 12))
    y += 52 + 26

    # The two members that are about the family rather than in it.
    comp = by_tier["composition"][0]
    hub = by_tier["hub"][0]
    out.append(box(PAD, y, half, 52, nf, ns))
    out.append(text(PAD + 14, y + 22, comp["name"], nt, 13, 500))
    out.append(text(PAD + 14, y + 40, "certifies six, pins them, runs the chain test", nt, 12))
    out.append(box(PAD + half + 20, y, half, 52, nf, ns))
    out.append(text(PAD + half + 34, y + 22, hub["name"], nt, 13, 500))
    out.append(text(PAD + half + 34, y + 40, "this directory, the docs site, the CI sweep", nt, 12))
    y += 52 + PAD

    body = "\n  ".join(out)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{y}" '
        f'viewBox="0 0 {W} {y}" role="img" aria-labelledby="title desc">\n'
        f'  <title id="title">The emulator family: {len(members)} repositories</title>\n'
        f'  <desc id="desc">One data product definition and one set of vendor systems feed '
        f'{len(cells)} cells. Each cell is a leaf paired with a platform, grouped under the '
        f'engine emulator it targets. Four cross-cutting emulators run in every stack.</desc>\n'
        f'  {body}\n</svg>\n'
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()

    members = load()
    wanted = {LIGHT: render(members, "light"), DARK: render(members, "dark")}

    if args.check:
        stale = [p.name for p, want in wanted.items()
                 if not p.exists() or p.read_text(encoding="utf-8") != want]
        if stale:
            print(f"out of date: {', '.join(stale)}. Run ./scripts/render_map.py")
            return 1
        print(f"map: {len(members)} members, both themes match the registry")
        return 0

    for p, want in wanted.items():
        p.write_text(want, encoding="utf-8")
    print(f"map: wrote {LIGHT.name} and {DARK.name} from {len(members)} members")
    return 0


if __name__ == "__main__":
    sys.exit(main())
