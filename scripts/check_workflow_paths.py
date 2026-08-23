#!/usr/bin/env python3
"""A workflow's path filter must cover every script that workflow runs.

    scripts/check_workflow_paths.py
    scripts/check_workflow_paths.py --self-test

WHY. Path filters are how a docs change avoids running a suite that cannot
observe it, and they are worth having. The failure they introduce is the
opposite one: a workflow that triggers on too little stops running for changes
it is the only check on.

Measured here, not imagined. `family-ci.yml` runs SEVEN scripts and triggered
on one of them, so an edit to `render_tables.py`, `render_map.py`,
`check_ontology.py`, `check_registry.py`, `check_verbs.py` or
`render_evidence.py` reached main with **no checks reported at all**. The
generator that writes the README was not covered by the gate that verifies the
README. That is the same shape as a green tick over a check that never ran,
which this ecosystem keeps finding in its own gates.

WHAT THIS DOES NOT DO. It does not ask a workflow to trigger on everything, and
it says nothing about `paths-ignore`, which is a different mechanism with a
different hazard (a workflow that never triggers leaves a required check
"Expected" forever; a job skipped by `if:` reports success). It asks one
question: of the scripts this workflow invokes, is any of them outside its own
trigger paths?
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = ROOT / ".github" / "workflows"

# `./scripts/x.py`, `scripts/x.py`, and the same behind `uv run ... `.
RUNS = re.compile(r"(?:\./)?(scripts/[A-Za-z0-9_./-]+\.(?:py|sh|mjs|js))")
# A `paths:` list under an event. Deliberately read as text rather than YAML:
# `on:` parses to the boolean True in YAML 1.1, which has surprised enough
# people that the block is safer read literally.
PATHS_BLOCK = re.compile(r"^\s*paths:\s*$((?:\n\s*-\s*'[^']*')+)", re.M)
PATTERN = re.compile(r"-\s*'([^']*)'")


def covered(path: str, patterns: list[str]) -> bool:
    """Whether a trigger list would fire for a change to `path`.

    Only the two shapes this repository actually uses: an exact path, and a
    `dir/**` prefix. An unrecognised pattern counts as NOT covering, which is
    the safe direction: it reports a gap that may not exist, rather than
    hiding one that does.
    """
    for p in patterns:
        if p == path:
            return True
        if p.endswith("/**") and path.startswith(p[:-2]):
            return True
        if p.endswith("*") and path.startswith(p[:-1]):
            return True
    return False


def audit(text: str) -> tuple[set[str], list[str]]:
    scripts = set(RUNS.findall(text))
    patterns: list[str] = []
    for block in PATHS_BLOCK.findall(text):
        patterns += PATTERN.findall(block)
    return scripts, patterns


def complaints(files: list[Path]) -> list[str]:
    bad = []
    for wf in sorted(files):
        text = wf.read_text(encoding="utf-8")
        scripts, patterns = audit(text)
        if not patterns:
            # No filter at all means it runs on everything, which is never the
            # failure this checks for.
            continue
        for script in sorted(scripts):
            if not covered(script, patterns):
                bad.append(
                    f"{wf.name} runs {script} and does not trigger on it, so an "
                    f"edit to that script lands with this workflow silent"
                )
    return bad


def self_test() -> int:
    """Prove the check can fail, on text rather than on the real workflows."""
    cases = [
        ("a covered script", """
on:
  push:
    paths:
      - 'scripts/a.py'
jobs:
  j:
    steps:
      - run: ./scripts/a.py --check
""", 0),
        ("an uncovered script", """
on:
  push:
    paths:
      - 'members.json'
jobs:
  j:
    steps:
      - run: ./scripts/a.py --check
""", 1),
        ("covered by a directory glob", """
on:
  push:
    paths:
      - 'scripts/**'
jobs:
  j:
    steps:
      - run: ./scripts/a.py
""", 0),
        ("no filter at all is not a finding", """
on:
  push:
jobs:
  j:
    steps:
      - run: ./scripts/a.py
""", 0),
        ("uv-wrapped invocation is still an invocation", """
on:
  push:
    paths:
      - 'members.json'
jobs:
  j:
    steps:
      - run: uv run --no-project --with jsonschema ./scripts/a.py --bom
""", 1),
    ]
    failures = 0
    import tempfile

    for name, text, want in cases:
        with tempfile.TemporaryDirectory() as d:
            wf = Path(d) / "w.yml"
            wf.write_text(text, encoding="utf-8")
            got = len(complaints([wf]))
        ok = (got > 0) == (want > 0)
        print(f"  {'ok  ' if ok else 'FAIL'} {name}: {got} complaint(s)")
        failures += 0 if ok else 1
    print("self-test FAILED" if failures else "self-test passed")
    return 1 if failures else 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        return self_test()

    files = sorted(WORKFLOWS.glob("*.yml"))
    if not files:
        raise SystemExit("check_workflow_paths: no workflows found; refusing to pass on nothing")
    bad = complaints(files)
    if bad:
        print("check_workflow_paths FAILED", file=sys.stderr)
        for line in bad:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"workflow paths: {len(files)} workflows, every script they run is covered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
