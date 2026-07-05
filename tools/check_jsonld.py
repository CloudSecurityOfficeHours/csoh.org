#!/usr/bin/env python3
"""
CI gate: every JSON-LD block on the site must be valid JSON.

Strict schema.org parsers (Google, Bing, and the LLM crawlers) reject an
entire <script type="application/ld+json"> block when it contains invalid
JSON - a single-quoted string, a trailing comma, an unescaped quote. The
block then contributes *no* structured data, silently. The weekly SEO audit
only checks that a block is *present*, so this class of bug shipped for
months across the meetings archive (82/94 Article + 91/94 BreadcrumbList
blocks were single-quoted and unparseable) without tripping any alarm.

This gate parses every block with json.loads and exits non-zero on the first
failure, printing file:line for each offender.

Usage:
    python3 tools/check_jsonld.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Directories that are build output, third-party, or non-published. Any
# dot-directory (.git, .claude worktrees, etc.) is skipped as well - those
# hold tooling state and, for worktrees, stale copies of the same pages.
EXCLUDE_DIRS = {"dist", "vendor", "node_modules", "__pycache__", "seo-audits"}


def _is_excluded(rel_parts: tuple[str, ...]) -> bool:
    return any(p in EXCLUDE_DIRS or p.startswith(".") for p in rel_parts)

LDJSON_RE = re.compile(
    r'<script\b[^>]*\btype=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def offenders() -> list[tuple[str, int, str]]:
    found: list[tuple[str, int, str]] = []
    for path in sorted(REPO.rglob("*.html")):
        if _is_excluded(path.relative_to(REPO).parts):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in LDJSON_RE.finditer(text):
            try:
                json.loads(m.group(1))
            except json.JSONDecodeError as e:
                line = text[: m.start()].count("\n") + 1
                rel = path.relative_to(REPO)
                found.append((str(rel), line, f"{e.msg} (line {e.lineno} col {e.colno})"))
    return found


def main() -> int:
    bad = offenders()
    if bad:
        print(f"Invalid JSON-LD in {len(bad)} block(s):", file=sys.stderr)
        for rel, line, msg in bad:
            print(f"  {rel}:{line}: {msg}", file=sys.stderr)
        print(
            "\nFix: JSON strings must use double quotes; escape inner quotes. "
            "See tools/add_meeting.py for the meetings generator.",
            file=sys.stderr,
        )
        return 1
    print("JSON-LD OK: all ld+json blocks parse.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
