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

A well-formed trail can still misdescribe the page. Two pages carried trails
that skipped the middle level their visible breadcrumb shows, and eight
resource category pages showed a breadcrumb that skipped the level their
markup had. So each BreadcrumbList must also name the same pages, in the same
order, as the visible <nav aria-label="Breadcrumb">, with hrefs resolved
against the page and index.html read as its directory. Labels are not
compared: many pages show a short label ("Careers") where the markup names the
page in full ("Cloud Security Careers"). A page with one trail and not the
other fails, unless it is in VISIBLE_TRAIL_ONLY.

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
from urllib.parse import urljoin

REPO = Path(__file__).resolve().parent.parent
SITE = "https://csoh.org/"

# Pages that show a visible breadcrumb but carry no BreadcrumbList, accepted
# as they are. A listed page that gains a BreadcrumbList, loses its visible
# trail or no longer exists fails the check, so the set cannot go stale.
VISIBLE_TRAIL_ONLY = frozenset({
    "403.html", "404.html", "about.html", "chat-resources.html",
    "code-of-conduct.html", "faq.html", "glossary.html", "privacy.html",
    "search.html", "security-policy.html", "topics.html",
})

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
# The visible trail is <nav class="breadcrumb-nav" aria-label="Breadcrumb">.
# Either attribute identifies it, in any order, so a nav that loses one is
# still compared rather than read as a page that shows no trail.
VISIBLE_TRAIL_RE = re.compile(
    r'<nav\b(?=[^>]*(?:\bclass=["\'][^"\']*\bbreadcrumb-nav\b|\baria-label=["\']breadcrumbs?["\']))'
    r'[^>]*>(.*?)</nav>',
    re.DOTALL | re.IGNORECASE,
)
CRUMB_RE = re.compile(r"<li\b[^>]*>(.*?)</li>", re.DOTALL | re.IGNORECASE)
LINK_RE = re.compile(r'<a\b[^>]*\bhref=["\']([^"\']*)["\']', re.IGNORECASE)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


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


def _canonical(text: str) -> str | None:
    link = CANONICAL_RE.search(text)
    href = HREF_RE.search(link.group(0)) if link else None
    return href.group(1) if href else None


def _page_trails(text: str):
    """(line, trail) for every BreadcrumbList in the page's ld+json blocks."""
    for m in LDJSON_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue  # reported by offenders()
        line = text[: m.start()].count("\n") + 1
        for trail in _breadcrumb_lists(obj):
            yield line, trail


def breadcrumb_problems(text: str) -> tuple[int, list[tuple[int, str]]]:
    """(trails found, [(line, problem)]) for one page."""
    canonical = _canonical(text)
    trails, found = 0, []
    for line, trail in _page_trails(text):
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


def _page_url(url):
    """A directory and its index.html are one page."""
    if isinstance(url, str) and url.endswith("/index.html"):
        return url[: -len("index.html")]
    return url


def _fmt(urls: list) -> str:
    """A trail as site paths: / > /resources.html > /resources-ai-security.html."""
    def one(url):
        if isinstance(url, str) and url.startswith(SITE):
            return "/" + url[len(SITE):]
        return "(none)" if url is None else repr(url)
    return " > ".join(one(u) for u in urls)


def _visible_trails(text: str, base: str, own: str) -> list[tuple[int, list]]:
    """(line, [page URL per crumb]) for each visible breadcrumb. hrefs resolve
    against the page's own URL; a last crumb with no link (the aria-current
    one) is the page itself. Comments are blanked first, keeping their
    newlines so line numbers hold: commented-out markup is not shown."""
    text = COMMENT_RE.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    found = []
    for m in VISIBLE_TRAIL_RE.finditer(text):
        links = [LINK_RE.search(li) for li in CRUMB_RE.findall(m.group(1))]
        urls = [_page_url(urljoin(base, a.group(1))) if a else None for a in links]
        if urls and urls[-1] is None:
            urls[-1] = own
        found.append((text[: m.start()].count("\n") + 1, urls))
    return found


def _trail_urls(trail: dict, own: str) -> list:
    """The page each entry names; a last entry without `item` names this page."""
    entries = trail.get("itemListElement")
    entries = entries if isinstance(entries, list) else []
    urls = []
    for i, entry in enumerate(entries):
        item = entry.get("item") if isinstance(entry, dict) else None
        url = item.get("@id") if isinstance(item, dict) else item
        urls.append(own if url is None and i == len(entries) - 1 else _page_url(url))
    return urls


def parity_problems(rel: str, text: str,
                    visible_only: frozenset[str] = VISIBLE_TRAIL_ONLY) -> list[tuple[int, str]]:
    """[(line, problem)] where one page's BreadcrumbList and visible trail name
    different pages. Labels are deliberately not compared."""
    base = SITE + Path(rel).as_posix()
    own = _page_url(_canonical(text) or base)
    shown = _visible_trails(text, base, own)
    marked = [(line, _trail_urls(trail, own)) for line, trail in _page_trails(text)]
    if rel in visible_only:
        if marked:
            return [(marked[0][0], "is in VISIBLE_TRAIL_ONLY but carries a BreadcrumbList; remove it from the set")]
        if not shown:
            return [(1, "is in VISIBLE_TRAIL_ONLY but shows no breadcrumb; remove it from the set")]
        return []
    if not shown:
        return [(line, "has a BreadcrumbList but no visible breadcrumb; markup must restate a trail the page shows")
                for line, _ in marked]
    if len(shown) > 1:
        return [(shown[1][0], f"shows {len(shown)} visible breadcrumb trails; expected one")]
    nav, vis = shown[0]
    if not marked:
        return [(nav, "shows a breadcrumb but has no BreadcrumbList; copy a sibling's, "
                      "or add the page to VISIBLE_TRAIL_ONLY")]
    found = []
    for line, urls in marked:
        if len(urls) != len(vis):
            found.append((nav, f"visible trail has {len(vis)} levels, BreadcrumbList (line {line}) has "
                               f"{len(urls)}: {_fmt(vis)} vs {_fmt(urls)}"))
            continue
        found += [(nav, f"crumb {i} links {_fmt([a])}, BreadcrumbList (line {line}) item {i} is {_fmt([b])}")
                  for i, (a, b) in enumerate(zip(vis, urls), start=1) if a != b]
    return found


def parity_offenders(pages=None,
                     visible_only: frozenset[str] = VISIBLE_TRAIL_ONLY) -> dict[str, list[tuple[int, str]]]:
    found, seen = {}, set()
    for rel, text in (_pages() if pages is None else pages):
        seen.add(rel)
        problems = parity_problems(rel, text, visible_only)
        if problems:
            found[rel] = problems
    for rel in sorted(visible_only - seen):
        found[rel] = [(0, "is in VISIBLE_TRAIL_ONLY but no such page exists; remove it from the set")]
    return found


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

    # Visible trail vs BreadcrumbList, planted on a page in a subdirectory so
    # its relative hrefs have to resolve. No visible label matches its JSON-LD
    # name, which the comparison must ignore.
    sub, hub = f"{SITE}sub/x.html", f"{SITE}hub.html"
    canon = f'<link rel="canonical" href="{sub}">\n'

    def shows(*hrefs: str | None) -> str:  # None: the page's own aria-current crumb
        items = "".join(f'<li><a href="{h}">Label</a></li>' if h else
                        '<li><span aria-current="page">Label</span></li>' for h in hrefs)
        return f'<nav class="breadcrumb-nav" aria-label="Breadcrumb"><ol>{items}</ol></nav>\n'

    def marks(*urls: str | None) -> str:  # None: a last entry that omits `item`
        trail = {"@context": "https://schema.org", "@type": "BreadcrumbList",
                 "itemListElement": [{"@type": "ListItem", "position": i, "name": "Name",
                                      **({"item": u} if u else {})}
                                     for i, u in enumerate(urls, start=1)]}
        return f'<script type="application/ld+json">{json.dumps(trail)}</script>\n'

    up = ("../index.html", "../hub.html", None)
    bare_nav = '<nav id="t" aria-label="breadcrumb"><ol><li><a href="/">H</a></li><li>X</li></ol></nav>\n'
    parity_cases = [  # (rel, planted page, text a problem must contain; None = must stay clean)
        ("sub/x.html", canon + shows(*up) + marks(SITE, hub, sub), None),
        ("sub/x.html", canon + shows(*up) + marks(SITE, hub, None), None),
        ("sub/x.html", canon + shows("../index.html", "index.html", None) + marks(SITE, f"{SITE}sub/", sub), None),
        ("sub/x.html", canon + bare_nav + marks(SITE, sub), None),
        ("sub/index.html", f'<link rel="canonical" href="{SITE}sub/index.html">\n' + shows("../index.html", None)
         + marks(SITE, f"{SITE}sub/"), None),
        ("sub/x.html", canon + shows(*up) + marks(SITE, sub), "visible trail has 3 levels"),
        ("sub/x.html", canon + shows("../index.html", None) + marks(SITE, hub, sub), "visible trail has 2 levels"),
        ("sub/x.html", canon + shows("../index.html", "../y.html", None) + marks(SITE, hub, sub),
         "crumb 2 links /y.html"),
        ("sub/x.html", canon + marks(SITE, sub), "no visible breadcrumb"),
        ("sub/x.html", canon + "<!--\n" + shows(*up) + "-->\n" + marks(SITE, hub, sub), "no visible breadcrumb"),
        ("sub/x.html", canon + shows(*up), "no BreadcrumbList"),
        ("sub/x.html", canon + shows(*up) * 2 + marks(SITE, hub, sub), "2 visible breadcrumb trails"),
        ("listed.html", shows("index.html", None), None),
        ("listed.html", shows("index.html", None) + marks(SITE, None), "carries a BreadcrumbList"),
        ("listed.html", "", "shows no breadcrumb"),
    ]
    for rel, html, expect in parity_cases:
        got = " | ".join(p for _, p in parity_problems(rel, html, frozenset({"listed.html"})))
        if expect is None and got:
            broken.append(f"flagged trails that agree ({got}): {rel}: {html}")
        elif expect is not None and expect not in got:
            broken.append(f"did not report '{expect}' (got: {got or 'nothing'}): {rel}: {html}")
    gone = parity_offenders(pages=[], visible_only=frozenset({"gone.html"}))
    if "no such page" not in " | ".join(p for problems in gone.values() for _, p in problems):
        broken.append("did not report a VISIBLE_TRAIL_ONLY entry whose page is gone")
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

    drift = parity_offenders()
    if drift:
        print(f"\nVisible breadcrumb and BreadcrumbList disagree on {len(drift)} page(s):", file=sys.stderr)
        for rel, problems in drift.items():
            for line, msg in problems[:5]:
                print(f"  {rel}:{line}: {msg}", file=sys.stderr)
            if len(problems) > 5:
                print(f"  {rel}: ... and {len(problems) - 5} more", file=sys.stderr)
        print(
            '\nFix: the BreadcrumbList restates the visible <nav aria-label="Breadcrumb">, so both '
            "name the same pages in the same order (labels may differ). Either side can be the "
            "stale one: decide from where the page sits in the site.",
            file=sys.stderr,
        )
    if not trails:
        # Nearly every page carries a trail, so zero means the scan went blind.
        print("\nFound no BreadcrumbList on any page - the scan is broken, not the site.",
              file=sys.stderr)
        return 1
    if bad or crumbs or drift:
        return 1
    print(f"JSON-LD OK: all ld+json blocks parse; {trails} breadcrumb trails are well-formed and "
          f"match their visible trail ({len(VISIBLE_TRAIL_ONLY)} pages show a visible trail only).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
