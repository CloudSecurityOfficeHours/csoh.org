#!/usr/bin/env python3
"""
CI gate: require width/height attributes on every <svg> that has a viewBox.

Without width/height, the browser can't derive an aspect ratio until layout
runs, so the element is laid out at a default size first and then jumps to
the CSS-driven size once styles apply. That jump is a Cumulative Layout
Shift (CLS) and tanks the page's Core Web Vitals score.

Adding width and height attributes (matching the viewBox numbers) lets the
browser compute the SVG's aspect ratio at parse time and reserve the right
space on first paint. CSS `width: 100%; height: auto` still wins for the
final rendered size - the attributes only provide the aspect ratio.

Exits non-zero if any offender is found, printing file:line for each.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Match an opening <svg ...> tag and capture its attributes. The closing `>`
# is required so we don't match e.g. "<svgsymbol".
SVG_TAG = re.compile(r"<svg\b([^>]*)>", re.DOTALL | re.IGNORECASE)

HAS_VIEWBOX = re.compile(r"\bviewBox\s*=", re.IGNORECASE)
HAS_WIDTH = re.compile(r"\bwidth\s*=", re.IGNORECASE)
HAS_HEIGHT = re.compile(r"\bheight\s*=", re.IGNORECASE)


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def scan(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(errors="replace")
    hits = []
    for m in SVG_TAG.finditer(text):
        attrs = m.group(1)
        if not HAS_VIEWBOX.search(attrs):
            continue
        if HAS_WIDTH.search(attrs) and HAS_HEIGHT.search(attrs):
            continue
        # Trim the snippet so the error message stays readable.
        snippet = m.group(0)
        if len(snippet) > 140:
            snippet = snippet[:137] + "..."
        hits.append((line_of(text, m.start()), snippet))
    return hits


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    targets = sorted(
        list(repo.glob("*.html"))
        + list(repo.glob("portfolio/*.html"))
        + list(repo.glob("meetings/*.html"))
        + list(repo.glob("breaches/*.html"))
    )

    failures = []
    for path in targets:
        for line, snippet in scan(path):
            failures.append((path.relative_to(repo), line, snippet))

    if failures:
        print(
            "SVGs with viewBox but no width/height attributes (CLS risk):",
            file=sys.stderr,
        )
        for rel, line, snippet in failures:
            print(f"  {rel}:{line}: {snippet}", file=sys.stderr)
        print(
            f"\n{len(failures)} offender(s). Add width=\"W\" height=\"H\" matching "
            "the last two viewBox numbers so the browser can reserve aspect-ratio "
            "space on first paint.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: scanned {len(targets)} file(s); every <svg viewBox> has width/height.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
