#!/usr/bin/env python3
"""
CI gate: every JSON-LD block on the site must be valid JSON, and every
BreadcrumbList must be a trail Google can read.

Strict schema.org parsers (Google, Bing, and the LLM crawlers) reject an
entire <script type="application/ld+json"> block when it contains invalid
JSON - a single-quoted string, a trailing comma, an unescaped quote. The
block then contributes *no* structured data, silently. The weekly SEO audit
only checks that a block is *present*, so it cannot catch this.

Valid JSON is not enough for a breadcrumb. resources-github-projects.html
shipped a BreadcrumbList whose entries were the page's own resource cards,
each carrying `url` where a breadcrumb needs `item`. It parsed, so this gate
passed it, and Search Console's Breadcrumbs report flagged the `item` field.
Each trail is therefore also held to Google's rules and to the shape every
trail on the site shares:

  - each entry is a ListItem, numbered 1..n in order, with a name;
  - each entry but the last has an `item`: an absolute https://csoh.org/ page
    URL, not a #fragment within one (Google lets the last entry omit `item`
    and uses the page's own URL);
  - the trail ends at the page it sits on: a last `item` must equal the
    page's <link rel="canonical">.

Every run first proves each breadcrumb detector fires on a planted page
(self_test) and refuses a verdict if one stays silent.

This gate parses every block with json.loads and exits non-zero on any
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
SITE = "https://csoh.org/"

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
CANONICAL_RE = re.compile(r'<link\b[^>]*\brel=["\']canonical["\'][^>]*>', re.IGNORECASE)
HREF_RE = re.compile(r'\bhref=["\']([^"\']+)["\']', re.IGNORECASE)


def _pages():
    for path in sorted(REPO.rglob("*.html")):
        if _is_excluded(path.relative_to(REPO).parts):
            continue
        yield str(path.relative_to(REPO)), path.read_text(encoding="utf-8", errors="replace")


def offenders() -> list[tuple[str, int, str]]:
    found: list[tuple[str, int, str]] = []
    for rel, text in _pages():
        for m in LDJSON_RE.finditer(text):
            try:
                json.loads(m.group(1))
            except json.JSONDecodeError as e:
                line = text[: m.start()].count("\n") + 1
                found.append((rel, line, f"{e.msg} (line {e.lineno} col {e.colno})"))
    return found


def _breadcrumb_lists(obj):
    """Every BreadcrumbList in a parsed block, however it is nested (@graph,
    a WebPage's `breadcrumb` property)."""
    if isinstance(obj, dict):
        types = obj.get("@type")
        if "BreadcrumbList" in (types if isinstance(types, list) else [types]):
            yield obj
        for v in obj.values():
            yield from _breadcrumb_lists(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _breadcrumb_lists(v)


def trail_problems(trail: dict, canonical: str | None) -> list[str]:
    entries = trail.get("itemListElement")
    if not isinstance(entries, list) or not entries:
        return ["BreadcrumbList has no itemListElement entries"]
    bad: list[str] = []
    last = len(entries) - 1
    for i, entry in enumerate(entries):
        at = f"itemListElement[{i}]"
        if not isinstance(entry, dict) or entry.get("@type") != "ListItem":
            bad.append(f"{at} is not a ListItem")
            continue
        if entry.get("position") != i + 1:
            bad.append(f"{at} has position {entry.get('position')!r}, expected {i + 1}")
        # `item` is either the URL itself or a Thing carrying it as @id.
        item = entry.get("item")
        url = item.get("@id") if isinstance(item, dict) else item
        if not (entry.get("name") or (isinstance(item, dict) and item.get("name"))):
            bad.append(f"{at} has no name")
        if item is None:
            if i != last:
                bad.append(f"{at} is missing 'item' (has {', '.join(sorted(entry))})")
        elif not isinstance(url, str) or not url.startswith(SITE):
            bad.append(f"{at} item {url!r} is not an absolute {SITE} URL")
        elif "#" in url:
            bad.append(f"{at} item {url} points inside a page; a trail links pages")
        elif i == last and canonical and url != canonical:
            bad.append(f"trail ends at {url}, not at this page ({canonical})")
    return bad


def breadcrumb_problems(text: str) -> tuple[int, list[tuple[int, str]]]:
    """(trails found, [(line, problem)]) for one page."""
    link = CANONICAL_RE.search(text)
    href = HREF_RE.search(link.group(0)) if link else None
    canonical = href.group(1) if href else None
    trails, found = 0, []
    for m in LDJSON_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue  # reported by offenders()
        line = text[: m.start()].count("\n") + 1
        for trail in _breadcrumb_lists(obj):
            trails += 1
            found += [(line, p) for p in trail_problems(trail, canonical)]
    return trails, found


def breadcrumb_offenders() -> tuple[int, dict[str, list[tuple[int, str]]]]:
    trails, found = 0, {}
    for rel, text in _pages():
        n, problems = breadcrumb_problems(text)
        trails += n
        if problems:
            found[rel] = problems
    return trails, found


def self_test() -> list[str]:
    """Prove every breadcrumb detector fires on a planted page, and that a
    well-formed trail stays clean. A detector that cannot fire would pass the
    next broken trail exactly as the syntax-only gate passed the last one."""
    here = f"{SITE}x.html"

    def page(*entries: dict, wrap=lambda trail: trail) -> str:
        trail = {"@context": "https://schema.org", "@type": "BreadcrumbList",
                 "itemListElement": [{"@type": "ListItem", "position": i, **e}
                                     for i, e in enumerate(entries, start=1)]}
        return (f'<link rel="canonical" href="{here}">\n'
                f'<script type="application/ld+json">{json.dumps(wrap(trail))}</script>')

    home, this = {"name": "Home", "item": SITE}, {"name": "X", "item": here}
    elsewhere = {"name": "Y", "item": f"{SITE}y.html"}
    cases = [  # (planted page, text a problem must contain; None = must stay clean)
        (page(home, this), None),
        (page(home, {"name": "X"}), None),
        (page(), "no itemListElement"),
        (page({"name": "A", "url": f"{here}#card-a"}, {"name": "B", "url": f"{here}#card-b"}),
         "missing 'item'"),
        (page({"name": "Home", "item": "/"}, this), "not an absolute"),
        (page(home, {"name": "C", "item": f"{here}#card-c"}, this), "points inside"),
        (page(home, elsewhere), "trail ends at"),
        (page(home, elsewhere, wrap=lambda trail: {"@graph": [trail]}), "trail ends at"),
        (page(home, {**this, "position": 3}), "expected 2"),
        (page(home, {"item": here}), "has no name"),
        (page({**home, "@type": "Thing"}, this), "not a ListItem"),
    ]
    broken = []
    for html, expect in cases:
        trails, problems = breadcrumb_problems(html)
        got = " | ".join(p for _, p in problems)
        if trails != 1:
            broken.append(f"found {trails} trails in a page planted with one: {html}")
        elif expect is None and problems:
            broken.append(f"flagged a well-formed trail ({got}): {html}")
        elif expect is not None and expect not in got:
            broken.append(f"did not report '{expect}' (got: {got or 'nothing'}): {html}")
    return broken


def main() -> int:
    broken = self_test()
    if broken:
        print("SELF-TEST FAILED - the breadcrumb check cannot be trusted:", file=sys.stderr)
        for b in broken:
            print(f"  {b}", file=sys.stderr)
        return 1

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

    trails, crumbs = breadcrumb_offenders()
    if crumbs:
        print(f"\nMalformed BreadcrumbList on {len(crumbs)} page(s):", file=sys.stderr)
        for rel, problems in crumbs.items():
            for line, msg in problems[:5]:
                print(f"  {rel}:{line}: {msg}", file=sys.stderr)
            if len(problems) > 5:
                print(f"  {rel}: ... and {len(problems) - 5} more", file=sys.stderr)
        print(
            "\nFix: a trail runs Home > ... > this page; every entry is a ListItem "
            f"with a name and an item (an absolute {SITE} URL). Copy the block "
            "from a sibling page.",
            file=sys.stderr,
        )
    if not trails:
        # Nearly every page carries a trail, so zero means the scan went blind.
        print("\nFound no BreadcrumbList on any page - the scan is broken, not the site.",
              file=sys.stderr)
        return 1
    if bad or crumbs:
        return 1
    print(f"JSON-LD OK: all ld+json blocks parse; {trails} breadcrumb trails are well-formed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
