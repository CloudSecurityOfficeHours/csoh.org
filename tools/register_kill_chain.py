#!/usr/bin/env python3
"""
Register every breach kill chain everywhere it must appear, and check it is.

The cards on breach-timeline.html, in page order (newest incident first), are
the single source of a chain's place. From them `--fix` writes the parts that
follow from that order:

    the ItemList JSON-LD on breach-timeline.html (one ListItem per card,
        named by the card title)
    the prev/next pager at the foot of every breaches/*.html page
    a sitemap.xml entry for any breach page that has none (added after the
        last breach entry; nothing is removed or reordered)

`--check` fails, naming the chain and what is missing, when for any page in
breaches/:

    no timeline card links it, two do, or a card links a page that does not
        exist
    the ItemList or the page's pager differs from what --fix would write
    sitemap.xml has no entry for it, or lists a breach page that is gone
    tools/generate_og_images.py has no tuple for it, img/og/breaches/<slug>.jpg
        is missing, or the page's og:image points elsewhere
    README.md does not link it
    breach-lessons.html lacks its list entry (an <li>) or its table row (a <tr>)
    its incident year is 2021 or later and no year-in-review page links it
        (any year's review counts: some chains are reviewed in a later year)
    tools/decks/breaches/published.json has no deck for it

The prose (page, card, README row, lessons entry, year-review row, preview
tagline, deck) is written by hand; this tool writes only what follows from the
order, and checks that the rest exists.

Usage:
    python3 tools/register_kill_chain.py --fix        # write ItemList, pagers, sitemap
    python3 tools/register_kill_chain.py --check      # exit 1 on anything missing
    python3 tools/register_kill_chain.py --self-test  # planted controls

Standard library only. Idempotent: a second --fix changes nothing.
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_breach_timeline_index import CARD_RE, TITLE_RE, YEAR_RE, plain  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
SITE = "https://csoh.org"
TIMELINE = "breach-timeline.html"
REVIEW_GLOB = "cloud-breach-year-in-review-*.html"  # the year pages; the hub has no year suffix
FIRST_REVIEWED_YEAR = 2021  # the year reviews start at 2021

# The ItemList's fixed fields, used only when the timeline has no ItemList to
# copy them from (the self-test fixture).
ITEMLIST_HEAD = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    "name": "Cloud Breach Kill Chains",
    "description": "Step-by-step cloud security breach kill chains, mapped to MITRE ATT&CK.",
    "itemListOrder": "https://schema.org/ItemListOrderDescending",
}

LINK_RE = re.compile(r'\bhref="breaches/([a-z0-9-]+)\.html"')
JSONLD_RE = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S)
# Any class list holding incident-pager, either quote style, any case: a
# pager someone edited is still the pager, so it is rewritten, not doubled.
PAGER_RE = re.compile(
    r'<nav\b[^>]*\bclass\s*=\s*["\'][^"\']*\bincident-pager\b[^"\']*["\'][^>]*>.*?</nav\s*>', re.S | re.I)
SITEMAP_URL_RE = re.compile(
    r'([ \t]*)<url>\s*<loc>https://csoh\.org/breaches/([a-z0-9-]+)\.html</loc>.*?</url>', re.S)
OG_META_RE = re.compile(r'<meta\b[^>]*\bproperty="og:image"[^>]*>')
FIX_HINT = "run python3 tools/register_kill_chain.py --fix"


@dataclass(frozen=True)
class Chain:
    slug: str
    year: str   # four digits, or "" when the card gives none
    title: str  # the card title as plain text


def read_chains(timeline_html: str) -> tuple[list[Chain], list[str]]:
    """The timeline's cards in page order, and a finding for each card that
    names no breach page or has no title."""
    chains: list[Chain] = []
    problems: list[str] = []
    for n, m in enumerate(CARD_RE.finditer(timeline_html), 1):
        body = m.group(2)
        link, title, year = LINK_RE.search(body), TITLE_RE.search(body), YEAR_RE.search(body)
        if not link:
            problems.append(f"{TIMELINE}: card {n} links no breaches/ page")
            continue
        if not title or not plain(title.group(1)):
            problems.append(f"{link.group(1)}: its timeline card has no title")
            continue
        chains.append(Chain(link.group(1), year.group(1) if year else "", plain(title.group(1))))
    return chains, problems


def itemlist_json(chains: list[Chain], head: dict) -> str:
    """The ItemList as the timeline writes it: the fixed fields, then the
    count and one ListItem per card, named by its title."""
    obj = dict(head)
    obj["numberOfItems"] = len(chains)
    obj["itemListElement"] = [
        {"@type": "ListItem", "position": i, "url": f"{SITE}/breaches/{c.slug}.html", "name": c.title}
        for i, c in enumerate(chains, 1)
    ]
    return json.dumps(obj, indent=2, ensure_ascii=False)


def timeline_with_itemlist(timeline_html: str, chains: list[Chain]) -> str | None:
    """timeline_html with its ItemList block rewritten from the cards; None
    when the page has no ItemList block. Other JSON-LD blocks are untouched."""
    for m in JSONLD_RE.finditer(timeline_html):
        inner = m.group(2)
        try:
            obj = json.loads(inner)
        except ValueError:
            continue
        if not (isinstance(obj, dict) and obj.get("@type") == "ItemList"):
            continue
        head = {k: v for k, v in obj.items() if k not in ("numberOfItems", "itemListElement")}
        lead = inner[: len(inner) - len(inner.lstrip())]
        trail = inner[len(inner.rstrip()):]
        new_inner = lead + itemlist_json(chains, head) + trail
        return timeline_html[: m.start(2)] + new_inner + timeline_html[m.end(2):]
    return None


def pager_html(prev: str | None, next_: str | None, indent: str) -> str:
    """The pager from "<nav" to "</nav>"; continuation lines carry `indent`.
    The first chain has no previous link and the last no next link."""
    lines = ['<nav class="incident-pager" aria-label="Other breach kill chains">']
    if prev:
        lines.append(f'{indent}    <a class="pager-link pager-prev" href="{prev}.html">\u2190 Previous breach</a>')
    lines.append(f'{indent}    <a class="pager-link pager-index" href="../{TIMELINE}">All breaches</a>')
    if next_:
        lines.append(f'{indent}    <a class="pager-link pager-next" href="{next_}.html">Next breach \u2192</a>')
    lines.append(f"{indent}</nav>")
    return "\n".join(lines)


def page_with_pager(page_html: str, prev: str | None, next_: str | None) -> str:
    """page_html with its pager rewritten, or added on its own line before
    </main> when it has none."""
    found = list(PAGER_RE.finditer(page_html))
    if found:
        # Any pager after the first is a stale copy: drop it with its line.
        for extra in reversed(found[1:]):
            start = page_html.rfind("\n", 0, extra.start())
            start = start if page_html[start + 1:extra.start()].strip() == "" else extra.start()
            page_html = page_html[:start] + page_html[extra.end():]
        m = PAGER_RE.search(page_html)
        line_start = page_html.rfind("\n", 0, m.start()) + 1
        indent = re.match(r"[ \t]*", page_html[line_start:]).group(0)
        return page_html[: m.start()] + pager_html(prev, next_, indent) + page_html[m.end():]
    end = re.search(r"\n([ \t]*)</main>", page_html)
    if not end:
        return page_html
    indent = end.group(1) + "    "
    return page_html[: end.start()] + "\n" + indent + pager_html(prev, next_, indent) + page_html[end.start():]


def sitemap_with(sitemap_xml: str, slugs: list[str], today: str) -> str:
    """sitemap_xml with a <url> for each slug it lacks, inserted after the
    last breach entry at that entry's indent. Nothing is removed or moved."""
    have = list(SITEMAP_URL_RE.finditer(sitemap_xml))
    listed = {m.group(2) for m in have}
    missing = [s for s in slugs if s not in listed]
    if not missing:
        return sitemap_xml
    if have:
        pos, ind = have[-1].end(), have[-1].group(1)
    else:
        pos, ind = sitemap_xml.rfind("\n</urlset>"), "  "
    block = "".join(
        f"\n{ind}<url>\n{ind}  <loc>{SITE}/breaches/{s}.html</loc>\n{ind}  <lastmod>{today}</lastmod>\n"
        f"{ind}  <changefreq>monthly</changefreq>\n{ind}  <priority>0.7</priority>\n{ind}</url>"
        for s in missing)
    return sitemap_xml[:pos] + block + sitemap_xml[pos:]


def _pages(root: Path) -> list[str]:
    return sorted(p.stem for p in (root / "breaches").glob("*.html"))


def _ordered(chains: list[Chain], pages: list[str]) -> list[str]:
    """Slugs in timeline order, once each, for the pages that exist."""
    seen: list[str] = []
    for c in chains:
        if c.slug in pages and c.slug not in seen:
            seen.append(c.slug)
    return seen


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def fix(root: Path, today: str) -> list[str]:
    """Write the ItemList, every pager and missing sitemap entries; return the
    paths (relative to root) that changed."""
    changed: list[str] = []
    tl_path = root / TIMELINE
    tl = _read(tl_path)
    chains, _ = read_chains(tl)
    new_tl = timeline_with_itemlist(tl, chains)
    if new_tl is not None and new_tl != tl:
        tl_path.write_text(new_tl, encoding="utf-8")
        changed.append(TIMELINE)
    pages = _pages(root)
    order = _ordered(chains, pages)
    for i, slug in enumerate(order):
        path = root / "breaches" / f"{slug}.html"
        page = _read(path)
        new = page_with_pager(page, order[i - 1] if i else None, order[i + 1] if i + 1 < len(order) else None)
        if new != page:
            path.write_text(new, encoding="utf-8")
            changed.append(f"breaches/{slug}.html")
    sm_path = root / "sitemap.xml"
    sm = _read(sm_path)
    new_sm = sitemap_with(sm, order + [p for p in pages if p not in order], today)
    if new_sm != sm:
        sm_path.write_text(new_sm, encoding="utf-8")
        changed.append("sitemap.xml")
    return changed


def check(root: Path) -> list[str]:
    """One finding per thing a chain is missing, each starting with its slug
    (or the file, for the ItemList)."""
    findings: list[str] = []
    tl = _read(root / TIMELINE)
    chains, problems = read_chains(tl)
    findings += problems
    pages = _pages(root)
    cards: dict[str, int] = {}
    for c in chains:
        cards[c.slug] = cards.get(c.slug, 0) + 1
    for slug, n in cards.items():
        if slug not in pages:
            findings.append(f"{slug}: a timeline card links breaches/{slug}.html, which does not exist")
        elif n > 1:
            findings.append(f"{slug}: more than one timeline card links it")
    findings += [f"{s}: no timeline card links it" for s in pages if s not in cards]

    expected_tl = timeline_with_itemlist(tl, chains)
    if expected_tl is None:
        findings.append(f"{TIMELINE}: has no ItemList JSON-LD block")
    elif expected_tl != tl:
        findings.append(f"{TIMELINE}: the ItemList is out of step with the cards; {FIX_HINT}")
    order = _ordered(chains, pages)
    for i, slug in enumerate(order):
        page = _read(root / "breaches" / f"{slug}.html")
        if len(PAGER_RE.findall(page)) > 1:
            findings.append(f"{slug}: has more than one pager; {FIX_HINT}")
        if page_with_pager(page, order[i - 1] if i else None, order[i + 1] if i + 1 < len(order) else None) != page:
            findings.append(f"{slug}: its pager is out of step with the timeline; {FIX_HINT}")

    listed = {m.group(2) for m in SITEMAP_URL_RE.finditer(_read(root / "sitemap.xml"))}
    findings += [f"{s}: sitemap.xml has no entry for it; {FIX_HINT}" for s in pages if s not in listed]
    findings += [f"{s}: sitemap.xml lists breaches/{s}.html, which does not exist" for s in sorted(listed - set(pages))]

    og_list = _read(root / "tools" / "generate_og_images.py")
    readme = _read(root / "README.md")
    lessons = _read(root / "breach-lessons.html")
    reviews = [_read(p) for p in sorted(root.glob(REVIEW_GLOB))]
    try:
        decks = json.loads(_read(root / "tools" / "decks" / "breaches" / "published.json") or "{}")
    except ValueError:
        decks = {}
        findings.append("tools/decks/breaches/published.json: cannot be read as JSON")
    years = {c.slug: c.year for c in chains}
    for slug in pages:
        page = _read(root / "breaches" / f"{slug}.html")
        link = f"breaches/{slug}.html"
        image = f"{SITE}/img/og/breaches/{slug}.jpg"
        if f'("{link}"' not in og_list:
            findings.append(f"{slug}: tools/generate_og_images.py has no preview-image tuple for it")
        if not (root / "img" / "og" / "breaches" / f"{slug}.jpg").exists():
            findings.append(f"{slug}: img/og/breaches/{slug}.jpg is missing; "
                            f"run python3 tools/generate_og_images.py --pages {link}")
        meta = OG_META_RE.search(page)
        content = re.search(r'\bcontent="([^"]*)"', meta.group(0)) if meta else None
        if not content or content.group(1) != image:
            findings.append(f"{slug}: its og:image does not point at {image}")
        if f"csoh.org/{link}" not in readme:
            findings.append(f"{slug}: README.md has no row linking it")
        for tag, what in (("li", "list entry"), ("tr", "table row")):
            if not re.search(rf"<{tag}\b[^>]*>(?:(?!</{tag}>).)*?{re.escape(link)}", lessons, re.S):
                findings.append(f"{slug}: breach-lessons.html has no {what} for it")
        year = years.get(slug, "")
        if year.isdigit() and int(year) >= FIRST_REVIEWED_YEAR and not any(link in r for r in reviews):
            findings.append(f"{slug}: no {REVIEW_GLOB} page links it")
        if slug not in decks:
            findings.append(f"{slug}: tools/decks/breaches/published.json has no deck for it")
    return findings


# --- self-test -------------------------------------------------------------

PAGE_T = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta property="og:image" content="https://csoh.org/img/og/breaches/{slug}.jpg">
</head>
<body>
    <main class="kc-main">
        <p class="inc-summary">About {slug}.</p>
{pager}
    </main>
</body>
</html>
"""

TIMELINE_T = """<!DOCTYPE html>
<html>
<head>
    <script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "Other block"
}}
    </script>
    <script type="application/ld+json">
{itemlist}
    </script>
</head>
<body>
<ul class="breach-list" role="list">
{cards}</ul>
</body>
</html>
"""


def _card_html(slug: str, year: str, title: str) -> str:
    return (f'        <li class="breach-card" id="{slug}">\n'
            f'            <a class="breach-card-link" href="breaches/{slug}.html">\n'
            f'                <div class="breach-card-meta"><span class="inc-year">{year}</span></div>\n'
            f'                <h2 class="breach-card-title">{title}</h2>\n'
            f'                <p class="breach-card-summary">x</p>\n'
            f'            </a>\n        </li>\n')


def _sitemap_html(slugs: list[str]) -> str:
    urls = "".join(f"  <url>\n    <loc>https://csoh.org/breaches/{s}.html</loc>\n    <lastmod>2026-01-01</lastmod>\n"
                   f"    <changefreq>monthly</changefreq>\n    <priority>0.7</priority>\n  </url>\n" for s in slugs)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            "  <url>\n    <loc>https://csoh.org/</loc>\n  </url>\n" + urls
            + "  <url>\n    <loc>https://csoh.org/zz-after.html</loc>\n  </url>\n</urlset>")


def _fixture(root: Path, chains: list[tuple[str, str, str]]) -> None:
    """A small site where every chain is fully registered."""
    (root / "breaches").mkdir(parents=True)
    (root / "img" / "og" / "breaches").mkdir(parents=True)
    (root / "tools" / "decks" / "breaches").mkdir(parents=True)
    objs = [Chain(s, y, plain(t)) for s, y, t in chains]
    (root / "breach-timeline.html").write_text(
        TIMELINE_T.format(itemlist=itemlist_json(objs, ITEMLIST_HEAD),
                          cards="".join(_card_html(*c) for c in chains)), encoding="utf-8")
    slugs = [c[0] for c in chains]
    for i, s in enumerate(slugs):
        prev = slugs[i - 1] if i > 0 else None
        nxt = slugs[i + 1] if i + 1 < len(slugs) else None
        (root / "breaches" / f"{s}.html").write_text(
            PAGE_T.format(slug=s, pager="        " + pager_html(prev, nxt, "        ")), encoding="utf-8")
        (root / "img" / "og" / "breaches" / f"{s}.jpg").write_bytes(b"jpg")
    (root / "sitemap.xml").write_text(_sitemap_html(slugs), encoding="utf-8")
    (root / "tools" / "generate_og_images.py").write_text(
        "PAGES = [\n" + "".join(f'    ("breaches/{s}.html",\n     "T", "S", "Breach Kill Chain"),\n' for s in slugs)
        + "]\n", encoding="utf-8")
    (root / "README.md").write_text("".join(f"| [{s}](https://csoh.org/breaches/{s}.html) | x |\n" for s in slugs),
                                    encoding="utf-8")
    (root / "breach-lessons.html").write_text(
        "<ul>\n" + "".join(f'<li><a href="breaches/{s}.html">{s}</a>: lesson</li>\n' for s in slugs) + "</ul>\n"
        "<table>\n" + "".join(f'<tr><td><a href="breaches/{s}.html">{s}</a></td><td>row</td></tr>\n' for s in slugs)
        + "</table>\n", encoding="utf-8")
    reviewed = [s for s, y, _ in chains if int(y) >= 2021]
    (root / "cloud-breach-year-in-review-2026-h1.html").write_text(
        "".join(f'<a href="breaches/{s}.html">{s}</a>\n' for s in reviewed), encoding="utf-8")
    (root / "cloud-breach-year-in-review.html").write_text('<a href="cloud-breach-year-in-review-2026-h1.html">2026</a>\n',
                                                          encoding="utf-8")
    (root / "tools" / "decks" / "breaches" / "published.json").write_text(
        json.dumps({s: {"id": "x"} for s in slugs}, indent=2), encoding="utf-8")


CHAINS = [("new-one", "2026", "New One - A → B"), ("mid-one", "2023", "Mid &amp; One - C"),
          ("old-one", "2019", "Old One - D")]


def self_test() -> int:
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            failures.append(what)

    def fresh(tmp: Path, name: str) -> Path:
        root = tmp / name
        _fixture(root, CHAINS)
        return root

    def has(findings: list[str], *parts: str) -> bool:
        return any(all(p in f for p in parts) for f in findings)

    def snapshot(root: Path) -> dict[str, bytes]:
        return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)

        root = fresh(tmp, "clean")
        expect(check(root) == [], "a fully registered site has no findings")
        before = snapshot(root)
        expect(fix(root, "2026-11-23") == [] and snapshot(root) == before, "--fix changes nothing on a registered site")
        chains, problems = read_chains((root / "breach-timeline.html").read_text(encoding="utf-8"))
        expect([c.slug for c in chains] == ["new-one", "mid-one", "old-one"] and problems == [],
               "cards are read in page order")
        expect(chains[1].title == "Mid & One - C" and chains[2].year == "2019",
               "titles are plain text and years are read")

        # One planted defect at a time, each named with its chain.
        def planted(name: str, mutate) -> list[str]:
            r = fresh(tmp, name)
            mutate(r)
            return check(r)

        def edit(r: Path, rel: str, old: str, new: str) -> None:
            p = r / rel
            s = p.read_text(encoding="utf-8")
            assert old in s, f"plant did nothing: {rel} lacks {old!r}"
            p.write_text(s.replace(old, new, 1), encoding="utf-8")

        f = planted("nocard", lambda r: edit(r, "breach-timeline.html", _card_html(*CHAINS[1]), ""))
        expect(has(f, "mid-one", "no timeline card"), "a page with no card is a finding")
        f = planted("dupcard", lambda r: edit(r, "breach-timeline.html", _card_html(*CHAINS[1]),
                                              _card_html(*CHAINS[1]) * 2))
        expect(has(f, "mid-one", "more than one"), "two cards for one page is a finding")
        f = planted("ghostcard", lambda r: (r / "breaches" / "old-one.html").unlink())
        expect(has(f, "old-one", "does not exist"), "a card that links a missing page is a finding")
        f = planted("nositemap", lambda r: edit(
            r, "sitemap.xml", "  <url>\n    <loc>https://csoh.org/breaches/mid-one.html</loc>", "  <url>\n    <loc>x</loc>"))
        expect(has(f, "mid-one", "sitemap"), "a page with no sitemap entry is a finding")
        f = planted("orphan", lambda r: edit(r, "sitemap.xml", "https://csoh.org/zz-after.html",
                                             "https://csoh.org/breaches/gone-one.html"))
        expect(has(f, "gone-one", "does not exist"), "a sitemap entry for a missing page is a finding")
        f = planted("notuple", lambda r: edit(r, "tools/generate_og_images.py", '("breaches/mid-one.html"', '("x.html"'))
        expect(has(f, "mid-one", "generate_og_images.py"), "a page with no preview-image tuple is a finding")
        f = planted("nojpg", lambda r: (r / "img" / "og" / "breaches" / "mid-one.jpg").unlink())
        expect(has(f, "mid-one", ".jpg"), "a missing preview image is a finding")
        f = planted("ogimage", lambda r: edit(r, "breaches/mid-one.html", "og/breaches/mid-one.jpg", "og/other.jpg"))
        expect(has(f, "mid-one", "og:image"), "an og:image pointing elsewhere is a finding")
        f = planted("readme", lambda r: edit(r, "README.md", "csoh.org/breaches/mid-one.html", "csoh.org/x.html"))
        expect(has(f, "mid-one", "README.md"), "a page missing from README.md is a finding")
        f = planted("lessonsli", lambda r: edit(r, "breach-lessons.html",
                                                '<li><a href="breaches/mid-one.html">', '<li><a href="x.html">'))
        expect(has(f, "mid-one", "list entry"), "a missing lessons list entry is a finding")
        f = planted("lessonstr", lambda r: edit(r, "breach-lessons.html",
                                                '<tr><td><a href="breaches/mid-one.html">', '<tr><td><a href="x.html">'))
        expect(has(f, "mid-one", "table row"), "a missing lessons table row is a finding")
        f = planted("review", lambda r: edit(r, "cloud-breach-year-in-review-2026-h1.html",
                                             'href="breaches/mid-one.html"', 'href="x.html"'))
        expect(has(f, "mid-one", "year-in-review"), "a 2021+ chain absent from every review is a finding")
        expect(not has(f, "old-one"), "a chain before 2021 needs no review")
        f = planted("hubonly", lambda r: (edit(r, "cloud-breach-year-in-review-2026-h1.html",
                                               'href="breaches/mid-one.html"', 'href="x.html"'),
                                          edit(r, "cloud-breach-year-in-review.html", "</a>",
                                               '</a><a href="breaches/mid-one.html">m</a>')))
        expect(has(f, "mid-one", "year-in-review"), "a link from the review hub alone does not count")
        f = planted("nodeck", lambda r: (r / "tools/decks/breaches/published.json").write_text(
            json.dumps({"new-one": {}, "old-one": {}}), encoding="utf-8"))
        expect(has(f, "mid-one", "deck"), "a chain with no published deck is a finding")

        # A new card in the middle of the timeline (an older incident
        # disclosed late): the ItemList and both neighbours' pagers change.
        r = fresh(tmp, "insert")
        edit(r, "breach-timeline.html", _card_html(*CHAINS[1]),
             _card_html("late-one", "2024", "Late One - E") + _card_html(*CHAINS[1]))
        shutil.copy(r / "breaches" / "mid-one.html", r / "breaches" / "late-one.html")
        f = check(r)
        expect(has(f, "ItemList") and has(f, "new-one", "pager") and has(f, "mid-one", "pager")
               and has(f, "late-one", "pager") and not has(f, "old-one", "pager"),
               "an inserted card puts the ItemList and the pagers around it out of step")
        changed = fix(r, "2026-11-23")
        expect(sorted(changed) == sorted(["breach-timeline.html", "breaches/late-one.html", "breaches/mid-one.html",
                                          "breaches/new-one.html", "sitemap.xml"]),
               f"--fix rewrites exactly the ItemList, the three pagers and the sitemap ({sorted(changed)})")
        after = snapshot(r)
        expect(fix(r, "2026-11-23") == [] and snapshot(r) == after, "a second --fix changes nothing")
        f = check(r)
        expect(not has(f, "pager") and not has(f, "ItemList") and not has(f, "sitemap"),
               "after --fix the ordered parts are in step")
        expect(has(f, "late-one", "README.md") and has(f, "late-one", "deck"),
               "after --fix the new chain's hand-written parts are still reported")
        page = (r / "breaches" / "mid-one.html").read_text(encoding="utf-8")
        expect('pager-prev" href="late-one.html"' in page and 'pager-next" href="old-one.html"' in page,
               "the pager links the cards above and below")
        top = (r / "breaches" / "new-one.html").read_text(encoding="utf-8")
        expect("pager-prev" not in top and 'pager-next" href="late-one.html"' in top,
               "the first card has no previous link")
        items = json.loads(re.search(r'<script type="application/ld\+json">\s*(\{[^<]*"ItemList".*?)</script>',
                                     (r / "breach-timeline.html").read_text(encoding="utf-8"), re.S).group(1))
        expect([i["position"] for i in items["itemListElement"]] == [1, 2, 3, 4] and items["numberOfItems"] == 4
               and items["itemListElement"][1]["name"] == "Late One - E",
               "the ItemList is renumbered and names the new card")
        tl = (r / "breach-timeline.html").read_text(encoding="utf-8")
        expect('"name": "Other block"' in tl, "other JSON-LD blocks are left alone")
        sm = (r / "sitemap.xml").read_text(encoding="utf-8")
        expect(sm.index("breaches/old-one.html") < sm.index("breaches/late-one.html") < sm.index("zz-after.html")
               and "<lastmod>2026-11-23</lastmod>" in sm,
               "a new sitemap entry goes after the last breach entry, dated today")

        # A pager a person edited (extra whitespace and an attribute) is
        # still found, and nothing outside it moves.
        r = fresh(tmp, "handpager")
        p = r / "breaches" / "mid-one.html"
        s = p.read_text(encoding="utf-8")
        messy = s.replace('<nav class="incident-pager"', '<nav  data-x="1" class="incident-pager"').replace(
            "All breaches</a>", "All breaches</a>   ")
        p.write_text(messy, encoding="utf-8")
        expect(has(check(r), "mid-one", "pager"), "a hand-edited pager is out of step")
        fix(r, "2026-11-23")
        expect(p.read_text(encoding="utf-8") == s, "--fix restores the pager and leaves the rest byte-identical")

        # Other realistic edits: a utility class beside incident-pager,
        # single quotes, upper case and a spaced closing tag are all still
        # the pager, so --fix rewrites it in place instead of adding a second.
        for label, mutate in (
                ("an extra class", lambda t: t.replace('class="incident-pager"', 'class="incident-pager u-mt-1"')),
                ("single quotes", lambda t: t.replace('class="incident-pager"', "class='incident-pager'")),
                ("upper case and </nav >", lambda t: t.replace("<nav class", "<NAV class").replace("</nav>", "</nav >"))):
            r = fresh(tmp, "variant-" + label.split()[0])
            p = r / "breaches" / "mid-one.html"
            s = p.read_text(encoding="utf-8")
            v = mutate(s)
            assert v != s, f"plant did nothing: {label}"
            p.write_text(v, encoding="utf-8")
            expect(has(check(r), "mid-one", "pager"), f"a pager with {label} is out of step")
            fix(r, "2026-11-23")
            expect(p.read_text(encoding="utf-8") == s, f"--fix rewrites a pager with {label} in place, in one run")

        # A second, stale pager on the same page is caught and removed.
        r = fresh(tmp, "twopagers")
        p = r / "breaches" / "mid-one.html"
        s = p.read_text(encoding="utf-8")
        stale = '        <nav class="incident-pager" aria-label="x"><a href="gone.html">Old</a></nav>\n'
        p.write_text(s.replace("    </main>", stale + "    </main>"), encoding="utf-8")
        expect(has(check(r), "mid-one", "more than one pager"), "a page with two pagers is a finding")
        fix(r, "2026-11-23")
        expect(p.read_text(encoding="utf-8") == s, "--fix leaves exactly one pager")

        # A page with no pager gets one before </main>.
        r = fresh(tmp, "nopager")
        p = r / "breaches" / "old-one.html"
        s = p.read_text(encoding="utf-8")
        p.write_text(re.sub(r"\n[ \t]*<nav\b.*?</nav>", "", s, flags=re.S), encoding="utf-8")
        expect(has(check(r), "old-one", "pager"), "a page with no pager is a finding")
        fix(r, "2026-11-23")
        expect(p.read_text(encoding="utf-8") == s, "--fix adds the pager where the template has it")

    print(f"\nself-test: {len(failures)} failure(s)")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--fix", action="store_true", help="write the ItemList, pagers and sitemap entries")
    mode.add_argument("--check", action="store_true", help="exit 1 if any chain is not fully registered")
    mode.add_argument("--self-test", action="store_true", help="run the planted controls")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.fix:
        changed = fix(REPO, datetime.date.today().isoformat())
        print("\n".join(f"rewrote {c}" for c in changed) or "everything already in step")
        return 0
    if args.check:
        findings = check(REPO)
        for f in findings:
            print(f"FINDING: {f}")
        print(f"kill chain registration: {len(findings)} finding(s)")
        return 1 if findings else 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
