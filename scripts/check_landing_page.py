#!/usr/bin/env python3
"""Every slot on the landing page is filled, checked here rather than by a reader.

    scripts/check_landing_page.py --site _site

The page ships em dashes and fills them from site-data.json at load time, so a
key the generator stopped emitting shows as a dash on the published page and
nowhere else: no build fails, no log line, nothing to grep for.

Lifted out of a heredoc inside .github/workflows/docs-site.yml so that
`make docs-build` runs the same check a deploy does. A check that exists only
in CI is a check nobody runs before pushing.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", type=pathlib.Path, required=True, help="the assembled site root")
    a = ap.parse_args()

    page_path = a.site / "index.html"
    data_path = a.site / "site-data.json"
    for p in (page_path, data_path):
        if not p.is_file():
            print(f"check_landing_page: {p} is missing", file=sys.stderr)
            return 1

    page = page_path.read_text(encoding="utf-8")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    wanted = set(re.findall(r'data-d="(\w+)"', page))
    ev = set(re.findall(r'data-ev="(\w+)"', page))
    # A page that asks for nothing is a page whose attributes were renamed, or
    # a regex that stopped matching. Either way this check would pass forever
    # while guarding nothing.
    if not wanted and not ev:
        print(
            "check_landing_page: the page asks for no counts at all, so either "
            "the data-d/data-ev attributes were renamed or this check is dead.",
            file=sys.stderr,
        )
        return 1

    missing = sorted(wanted - data.keys())
    missing_ev = sorted(ev - set(data.get("evidence", {})))
    if missing or missing_ev:
        print(
            f"check_landing_page: the page asks for {missing + missing_ev} and "
            f"site_data.py does not emit it; those slots would publish as em dashes",
            file=sys.stderr,
        )
        return 1

    print(f"landing page: {len(wanted)} counts + {len(ev)} ledgers, all present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
