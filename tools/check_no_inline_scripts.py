#!/usr/bin/env python3
"""
CI gate: refuse inline <script> blocks in HTML files.

The site's strict CSP (`script-src 'self'`) silently blocks inline scripts
in production. JSON-LD blocks (<script type="application/ld+json">) are
allowed because the CSP `script-src` directive only applies to executable
scripts - JSON-LD is data and is not affected.

Exits non-zero if any executable inline <script> block is found, printing
file:line for each offender.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Match a <script ...> open tag and capture its attributes. The closing
# `>` is required so we don't match things like "<scripted">.
OPEN_TAG = re.compile(r"<script\b([^>]*)>", re.IGNORECASE)

# Tag attributes we treat as "not an executable inline script":
#   - has src=...     -> external, fine
#   - type="application/ld+json"  -> data, not executed (CSP-safe)
#   - type="application/json"     -> data
#   - type="text/template"        -> template, not executed
ALLOWED_TYPES = {
    "application/ld+json",
    "application/json",
    "text/template",
    "text/x-template",
    "text/x-handlebars-template",
}

ATTR_RE = re.compile(r'(\w[\w-]*)\s*=\s*"([^"]*)"')


def is_inline_executable(attrs: str) -> bool:
    parsed = dict(ATTR_RE.findall(attrs))
    if "src" in parsed:
        return False
    typ = parsed.get("type", "").lower()
    if typ in ALLOWED_TYPES:
        return False
    return True


def line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def scan(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(errors="replace")
    hits = []
    for m in OPEN_TAG.finditer(text):
        if is_inline_executable(m.group(1)):
            hits.append((line_of(text, m.start()), m.group(0)))
    return hits


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    targets = sorted(
        list(repo.glob("*.html"))
        + list(repo.glob("meetings/*.html"))
        + list(repo.glob("breaches/*.html"))
    )

    failures = []
    for path in targets:
        for line, snippet in scan(path):
            failures.append((path.relative_to(repo), line, snippet))

    if failures:
        print("Inline <script> blocks found (blocked by CSP `script-src 'self'`):", file=sys.stderr)
        for rel, line, snippet in failures:
            print(f"  {rel}:{line}: {snippet}", file=sys.stderr)
        print(
            f"\n{len(failures)} offender(s). Move the script body into an external .js "
            "file and reference it via <script src=\"/foo.js\" defer></script>.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: scanned {len(targets)} file(s); no inline <script> blocks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
