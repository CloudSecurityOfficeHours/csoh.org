#!/usr/bin/env python3
"""Fail if a root-level page is neither cross-linked nor deliberately excluded.

`crosslink_pages.py` works from an opt-in `TARGET_PAGES` list. Nothing errors
when a page is missing from it - the page is simply never visited - so a new
page ships with zero glossary cross-links and nothing anywhere reports it. That
has now happened twice. Eight pages were found in August 2026 carrying zero
links while comparable pages carried 45+, and a systematic sweep immediately
after turned up 23 more, including a ~9,500-word page with a single link.

This check closes the loop: every `*.html` at the repo root must appear in
either `TARGET_PAGES` or `DELIBERATELY_UNLINKED`. Adding a page to the second
list is a one-line decision with a reason; forgetting both is now an error.

    python3 tools/check_crosslink_coverage.py

Exits non-zero and names the unaccounted-for pages.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from crosslink_pages import (  # noqa: E402
    DELIBERATELY_UNLINKED,
    TARGET_PAGES,
)

REPO = Path(__file__).resolve().parent.parent


def main() -> int:
    accounted = set(TARGET_PAGES) | set(DELIBERATELY_UNLINKED)
    root_pages = {p.name for p in REPO.glob("*.html")}

    unaccounted = sorted(root_pages - accounted)
    stale = sorted(accounted - root_pages)

    if stale:
        print("Listed but no longer present at the repo root:", file=sys.stderr)
        for name in stale:
            print(f"  {name}", file=sys.stderr)

    if unaccounted:
        print(
            f"\n{len(unaccounted)} root page(s) in neither TARGET_PAGES nor "
            "DELIBERATELY_UNLINKED in tools/crosslink_pages.py:",
            file=sys.stderr,
        )
        for name in unaccounted:
            print(f"  {name}", file=sys.stderr)
        print(
            "\nAdd each to TARGET_PAGES to cross-link it, or to "
            "DELIBERATELY_UNLINKED with a reason if it should stay unlinked.",
            file=sys.stderr,
        )

    if unaccounted or stale:
        return 1

    print(
        f"OK: all {len(root_pages)} root pages accounted for "
        f"({len(TARGET_PAGES)} cross-linked, "
        f"{len(DELIBERATELY_UNLINKED)} deliberately unlinked)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
