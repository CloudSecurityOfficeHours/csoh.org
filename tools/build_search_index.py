#!/usr/bin/env python3
"""
Build the site-wide full-text search index used by /search.html.

Output: /search-index.json - a JSON document with two top-level fields:
  - "synonyms": {term: [aliases...]} loaded from search-synonyms.json
  - "docs": [{id, url, page, section, heading, title, text, type}, ...]

Each section of every content page becomes one document. The frontend
(see /search-init.js) feeds the docs into MiniSearch, expands tokens
through the synonyms map at both index and query time, and renders
results that link directly to the relevant #section anchor instead of
the top of a long page.

Design notes:
  - One doc per <section id="..."> when available; one fallback "page"
    doc per file otherwise. This gives "NHI" a hit on iam.html#nhi
    instead of just iam.html.
  - Glossary terms (<dt id="term-...">) each become their own doc so
    direct definition lookups work.
  - Resource cards on the CARD_PAGES each become their own doc, deep
    linked to their category anchor, so searching a resource by name
    ("Tumeryk") finds it. A page-level doc alone cannot: it is capped
    at 2400 chars, which is ~3% of resources.html.
  - News, meetings, presentations, etc. that have their own search
    UX get a single page-level entry (their detail content is indexed
    elsewhere or isn't useful at the section grain).
  - Pages excluded from the index: search itself, error pages, the
    Google verification token file, and CTAs/landing pages that don't
    carry substantive content.

Idempotent: re-running with no content changes produces the same JSON.
Safe to wire into the deploy workflow before the Docker build.
"""

from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Iterable

# ----- Configuration -----------------------------------------------------

REPO = Path(__file__).resolve().parent.parent
OUT_PATH = REPO / "search-index.json"
SYNONYMS_PATH = REPO / "search-synonyms.json"

# Files that should not appear in search results at all.
EXCLUDE_FILES: set[str] = {
    "search.html",          # the search page itself
    "403.html",
    "404.html",
    "google66d489593949bd4c.html",  # search-console verification token
    "rss.html",             # wrapper around feed.xml; not content
}

# Card-list pages: every entry is an <a class="card-link"> wrapping a
# <div class="resource-card">. These pages get a page-level doc *plus* one
# doc per card, because a single truncated page doc indexed ~3% of
# resources.html and left 400+ resources unsearchable by name.
#
# chat-resources.html is deliberately excluded despite having the same
# markup: its 580 cards are links pasted in chat, auto-titled from their
# URL slug ("theregister.com - 2017 - 09 - 19 - Viacom Exposure In Aws3
# Bucket Blunder"). They are the bulk of the index's weight and the least
# useful thing to match on.
CARD_PAGES: set[str] = {
    "resources.html",
    "ctfs.html",
    "conferences.html",
    "threat-research.html",
}

# Pages where we want a single page-level entry rather than per-section docs
# (their content is dynamic, paginated, or already has its own search UI).
# Card pages are listed here too: the page-level doc is still emitted, and
# emit_card_docs() adds the per-card entries on top of it.
PAGE_LEVEL_ONLY: set[str] = {
    "news.html",
    "meetings.html",
    "presentations.html",
    "chat-resources.html",
    "breach-timeline.html",
    "threat-research.html",
    "conferences.html",
    "ctfs.html",
    "resources.html",
    "contribute-resources.html",
    "sessions.html",
}

# Coarse "type" tags to power result filtering. Defaults to "guide".
TYPE_TAGS: dict[str, str] = {
    "glossary.html": "glossary",
    "faq.html": "faq",
    "about.html": "site",
    "about-shawn-nunley.html": "site",
    "privacy.html": "site",
    "code-of-conduct.html": "site",
    "security-policy.html": "site",
    "contribute.html": "site",
    "github-actions.html": "site",
    "cloud-deployment.html": "site",
    "news.html": "feed",
    "meetings.html": "feed",
    "presentations.html": "feed",
    "chat-resources.html": "feed",
    "breach-timeline.html": "feed",
    "threat-research.html": "feed",
    "conferences.html": "feed",
    "ctfs.html": "feed",
    "resources.html": "feed",
    "sessions.html": "feed",
}

# Subdirectory content that lives outside the root glob. Each page is
# indexed as a single page-level doc so /search.html can surface a specific
# breach kill chain or meeting recap by title, description, or body term.
# (meetings.html also ships a dedicated full-body search; this adds the
# recaps to the global index with their own filter chip.)
SUBDIR_TYPES: list[tuple[str, str]] = [
    ("breaches", "breach"),
    ("meetings", "meeting"),
    ("howto", "guide"),
]

# ----- HTML parsing ------------------------------------------------------

# Pull <main>...</main> if present, else <body>...</body>.
MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.DOTALL | re.IGNORECASE)
BODY_RE = re.compile(r"<body\b[^>]*>(.*?)</body>", re.DOTALL | re.IGNORECASE)
TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title>", re.DOTALL | re.IGNORECASE)
META_DESC_RE = re.compile(
    r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Blocks to strip entirely (chrome, scripts, hidden machinery).
DROP_BLOCKS = [
    re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<noscript\b[^>]*>.*?</noscript>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<svg\b[^>]*>.*?</svg>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<header\b[^>]*>.*?</header>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<footer\b[^>]*>.*?</footer>", re.DOTALL | re.IGNORECASE),
    re.compile(
        r'<nav\b[^>]*class=["\'][^"\']*breadcrumb-nav[^"\']*["\'][^>]*>.*?</nav>',
        re.DOTALL | re.IGNORECASE,
    ),
    re.compile(
        r'<div\b[^>]*class=["\'][^"\']*\btoc\b[^"\']*["\'][^>]*>.*?</div>',
        re.DOTALL | re.IGNORECASE,
    ),
]
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")

# Section extraction: matches <section id="..."> ... </section>. We use a
# non-greedy match on the body and rely on the site's HTML being well-
# formed (sections aren't nested in this codebase).
SECTION_RE = re.compile(
    r'<section\b[^>]*\bid=["\']([^"\']+)["\'][^>]*>(.*?)</section>',
    re.DOTALL | re.IGNORECASE,
)
H2_RE = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.DOTALL | re.IGNORECASE)
H3_RE = re.compile(r"<h3\b[^>]*>(.*?)</h3>", re.DOTALL | re.IGNORECASE)

# Card shape on the CARD_PAGES:
#   <a href="..." class="card-link">
#     <div class="resource-card" data-tooltip="longer blurb">
#       <h3>Name</h3><p>description</p>
#       <div class="resource-tags"><span class="tag">Tag</span>...</div>
# The tooltip lives in an attribute, so strip_html() would drop it; it is
# pulled out separately and appended to the card's indexed text.
CARD_RE = re.compile(
    r'<a\b[^>]*\bhref=["\']([^"\']+)["\'][^>]*\bclass=["\'][^"\']*\bcard-link\b[^"\']*["\']'
    r'[^>]*>(.*?)</a>',
    re.DOTALL | re.IGNORECASE,
)
TOOLTIP_RE = re.compile(r'\bdata-tooltip=["\']([^"\']*)["\']', re.IGNORECASE)
# The card's own opening <a> tag, so its id="" can be read back out. Sliced
# from the start of a CARD_RE match rather than matched independently: the
# two values have to come from the same element or they describe different
# cards.
CARD_OPEN_TAG_RE = re.compile(r"<a\b[^>]*>", re.IGNORECASE)

# Anchor candidates that a card can be attributed to, so a result can deep
# link to the card's category instead of the top of a long page. The card
# pages each group differently:
#   resources.html            <div class="category-section" id="ai-security">
#   ctfs / threat-research    <section class="section" id="aws-ctfs">
#   conferences.html          <h2 id="cloud"> (cards are siblings, not nested)
#   chat-resources.html       no grouping anchors; cards link to the page
# `details` is here because resources.html's category sections collapse and
# are <details class="category-section"> as of 2026-08-23. Leaving it out is
# not an error anyone sees: the tag simply stops matching, every card on the
# page loses its section attribution, and the index still builds. It went
# from 7 sections to 1 that way.
ANCHOR_TAG_RE = re.compile(r"<(section|div|details|h2)\b([^>]*)>", re.IGNORECASE)
ID_ATTR_RE = re.compile(r'\bid=["\']([^"\']+)["\']', re.IGNORECASE)
CLASS_ATTR_RE = re.compile(r'\bclass=["\']([^"\']*)["\']', re.IGNORECASE)

# Glossary term shape: <dt id="term-..."><term text></dt> ... <dd>def</dd>.
# The glossary page is dense enough that we extract each <dt>/<dd> pair as
# its own indexable doc - search for "NHI" should land directly on the
# glossary's NHI entry, not just the page.
GLOSSARY_TERM_RE = re.compile(
    r'<dt\b[^>]*\bid=["\'](term-[^"\']+)["\'][^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>',
    re.DOTALL | re.IGNORECASE,
)


def strip_html(s: str) -> str:
    for pat in DROP_BLOCKS:
        s = pat.sub(" ", s)
    s = TAG_RE.sub(" ", s)
    s = html.unescape(s)
    return WS_RE.sub(" ", s).strip()


def page_title(raw: str) -> str:
    m = TITLE_RE.search(raw)
    if not m:
        return ""
    return html.unescape(WS_RE.sub(" ", m.group(1).strip()))


def page_description(raw: str) -> str:
    m = META_DESC_RE.search(raw)
    if not m:
        return ""
    return html.unescape(m.group(1).strip())


def body(raw: str) -> str:
    m = MAIN_RE.search(raw) or BODY_RE.search(raw)
    return m.group(1) if m else raw


# ----- Doc emission ------------------------------------------------------

def short_page_title(full_title: str) -> str:
    """Trim "Foo - CSOH" / "Foo | CSOH" suffixes for clean display."""
    for sep in (" - ", " - ", " | "):
        if sep in full_title:
            base, tail = full_title.rsplit(sep, 1)
            if tail.strip().lower() in {"csoh", "cloud security office hours"}:
                return base.strip()
    return full_title


def emit_page_level(rel_url: str, raw: str, ptype: str) -> dict | None:
    """Build one page-level doc for a subdirectory content page (breach or
    meeting recap) that the root glob does not reach."""
    title = short_page_title(page_title(raw)) or rel_url
    description = page_description(raw)
    text = (description + " " + strip_html(body(raw))).strip()[:2400]
    if not text:
        return None
    return {
        "id": rel_url.lstrip("/"),
        "url": rel_url,
        "page": title,
        "section": "",
        "heading": title,
        "title": title,
        "text": text,
        "type": ptype,
    }


def card_slug(name: str) -> str:
    """Stable per-card anchor id, derived from the card's <h3> text.

    Both this file and tools/stamp_card_ids.py go through here, so the id
    stamped into the HTML and the id the index links to cannot drift: a
    retitled card re-slugs in both places at once.
    """
    ascii_name = (
        unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    )
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    slug = slug[:60].rstrip("-")
    return f"card-{slug}" if slug else ""


def card_slots(main: str) -> list[tuple["re.Match[str]", str, str]]:
    """Every card on a page as (match, wanted_id, current_id).

    `wanted_id` is what the card should carry; `current_id` is what its <a>
    carries today (empty when unstamped). Duplicate titles - the same tool
    listed under two categories - get a -2, -3 suffix in document order, so
    the ids stay unique per page without anyone hand-picking them.
    """
    used: set[str] = set()
    out: list[tuple["re.Match[str]", str, str]] = []
    for m in CARD_RE.finditer(main):
        h3 = H3_RE.search(m.group(2))
        wanted = card_slug(strip_html(h3.group(1))) if h3 else ""
        if wanted:
            # Suffix against what has actually been handed out, not against a
            # per-base counter: a page holding "Foo", "Foo" and "Foo 2" would
            # give the third card the same id the second one just took.
            base, n = wanted, 1
            while wanted in used:
                n += 1
                wanted = f"{base}-{n}"
            used.add(wanted)
        open_tag = CARD_OPEN_TAG_RE.match(main, m.start())
        current = ""
        if open_tag:
            id_m = ID_ATTR_RE.search(open_tag.group(0))
            current = id_m.group(1) if id_m else ""
        out.append((m, wanted, current))
    return out


def card_anchors(main: str) -> list[tuple[int, str, str]]:
    """Offsets of the anchors a card can be attributed to, as
    (offset, id, heading), sorted by offset so a card can scan for the
    nearest preceding one."""
    out: list[tuple[int, str, str]] = []
    for m in ANCHOR_TAG_RE.finditer(main):
        tag = m.group(1).lower()
        attrs = m.group(2)
        id_m = ID_ATTR_RE.search(attrs)
        if not id_m:
            continue
        classes = CLASS_ATTR_RE.search(attrs)
        classes = classes.group(1).split() if classes else []
        if tag == "h2":
            # The h2's own text is the heading.
            h2 = H2_RE.match(main, m.start())
            heading = strip_html(h2.group(1)) if h2 else id_m.group(1)
        elif (tag == "section" and "section" in classes) or (
            tag in ("div", "details") and "category-section" in classes
        ):
            # Heading is the first h2 inside the container.
            h2 = H2_RE.search(main, m.end())
            heading = strip_html(h2.group(1)) if h2 else id_m.group(1)
        else:
            # Some other div that merely happens to carry an id (filter
            # widgets on chat-resources.html) - not a real card grouping.
            continue
        out.append((m.start(), id_m.group(1), heading))
    out.sort(key=lambda t: t[0])
    return out


def emit_card_docs(filename: str, main: str, page_title_: str) -> Iterable[dict]:
    """One doc per resource card. Without these, a card page's only entry
    is a page-level doc truncated to 2400 chars, so a search for a
    resource by name (e.g. "Tumeryk") finds nothing at all."""
    anchors = card_anchors(main)
    for n, (m, _wanted_id, card_id) in enumerate(card_slots(main)):
        href = html.unescape(m.group(1).strip())
        card_html = m.group(2)
        h3 = H3_RE.search(card_html)
        if not h3:
            # Not a titled card (e.g. a bare "see also" link styled as one).
            continue
        name = strip_html(h3.group(1))
        if not name:
            continue
        tooltip = TOOLTIP_RE.search(card_html)
        tooltip = html.unescape(tooltip.group(1).strip()) if tooltip else ""
        body_text = strip_html(card_html)
        # The card's own text, its tooltip blurb, and the destination host
        # all describe the resource; index them together so "tumeryk.com"
        # and the tooltip's wording both hit.
        text = " ".join(x for x in (body_text, tooltip, href) if x)[:2400]

        anchor = ""
        section = ""
        for offset, aid, heading in anchors:
            if offset > m.start():
                break
            anchor, section = aid, heading

        # Prefer the card's own id. The category anchor is a fallback that
        # is correct and nearly useless: #security-tools holds 83 cards, so
        # a result promising "Open Policy Agent (OPA)" landed the reader
        # 6,400px above it with no way to tell the page was not simply
        # missing the thing they clicked. Read the id off the HTML rather
        # than recomputing it, so an unstamped card degrades to the old
        # category link instead of to an anchor that does not exist.
        url = f"/{filename}#{card_id or anchor}" if (card_id or anchor) else f"/{filename}"
        yield {
            "id": f"{filename}#card-{n}",
            "url": url,
            "page": page_title_,
            "section": section,
            "heading": name,
            "title": f"{name} - {page_title_}",
            "text": text,
            "type": "resource",
        }


def emit_docs(filename: str, raw: str) -> Iterable[dict]:
    title = short_page_title(page_title(raw)) or filename
    description = page_description(raw)
    ptype = TYPE_TAGS.get(filename, "guide")
    main = body(raw)

    if filename in PAGE_LEVEL_ONLY:
        text = description + " " + strip_html(main)
        yield {
            "id": filename,
            "url": "/" + filename,
            "page": title,
            "section": "",
            "heading": title,
            "title": title,
            "text": text[:2400],
            "type": ptype,
        }
        if filename in CARD_PAGES:
            yield from emit_card_docs(filename, main, title)
        return

    if filename == "glossary.html":
        # One doc per glossary term so direct lookups work.
        # Also keep a page-level doc so glossary-wide queries surface.
        yield {
            "id": "glossary.html",
            "url": "/glossary.html",
            "page": title,
            "section": "",
            "heading": title,
            "title": title,
            "text": description,
            "type": "glossary",
        }
        for m in GLOSSARY_TERM_RE.finditer(main):
            term_id = m.group(1)
            term_text = strip_html(m.group(2))
            def_text = strip_html(m.group(3))
            yield {
                "id": f"glossary.html#{term_id}",
                "url": f"/glossary.html#{term_id}",
                "page": "Glossary",
                "section": term_text,
                "heading": term_text,
                "title": f"{term_text} (Glossary)",
                "text": def_text,
                "type": "glossary",
            }
        return

    sections = list(SECTION_RE.finditer(main))
    if not sections:
        # No <section id="..."> structure - emit one page-level doc.
        text = (description + " " + strip_html(main))[:2400]
        yield {
            "id": filename,
            "url": "/" + filename,
            "page": title,
            "section": "",
            "heading": title,
            "title": title,
            "text": text,
            "type": ptype,
        }
        return

    # Always include a page-level entry so generic queries surface the
    # page itself before any of its sections.
    yield {
        "id": filename,
        "url": "/" + filename,
        "page": title,
        "section": "",
        "heading": title,
        "title": title,
        "text": (description or strip_html(main)[:600]),
        "type": ptype,
    }

    for m in sections:
        section_id = m.group(1)
        section_body = m.group(2)
        h2_match = H2_RE.search(section_body)
        heading = strip_html(h2_match.group(1)) if h2_match else section_id
        # Concatenate the section's text. Subheadings (h3) are weighted
        # by sheer repetition: their text already appears in the body
        # extract. No need to over-engineer field weights at index time;
        # MiniSearch handles per-field boosts on the frontend.
        text = strip_html(section_body)
        # Truncate very long sections to keep the index tractable.
        # 2400 chars is roughly 350-400 words - plenty for snippet hits.
        text = text[:2400]
        yield {
            "id": f"{filename}#{section_id}",
            "url": f"/{filename}#{section_id}",
            "page": title,
            "section": heading,
            "heading": heading,
            "title": f"{heading} - {title}",
            "text": text,
            "type": ptype,
        }


# ----- Driver ------------------------------------------------------------

def load_synonyms() -> dict[str, list[str]]:
    if not SYNONYMS_PATH.exists():
        return {}
    with SYNONYMS_PATH.open(encoding="utf-8") as fh:
        data = json.load(fh)
    # Lowercase keys and values for case-insensitive matching at runtime.
    norm: dict[str, list[str]] = {}
    for term, aliases in data.items():
        norm[term.lower()] = [a.lower() for a in aliases]
    return norm


def main() -> int:
    docs: list[dict] = []
    for path in sorted(REPO.glob("*.html")):
        if path.name in EXCLUDE_FILES:
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        for doc in emit_docs(path.name, raw):
            # Skip empty entries (defensive - should not happen).
            if not doc.get("text") and not doc.get("heading"):
                continue
            docs.append(doc)

    # Subdirectory content pages (breaches/, meetings/) - one doc each.
    for subdir, ptype in SUBDIR_TYPES:
        for path in sorted((REPO / subdir).glob("*.html")):
            raw = path.read_text(encoding="utf-8", errors="replace")
            doc = emit_page_level(f"/{subdir}/{path.name}", raw, ptype)
            if doc:
                docs.append(doc)

    synonyms = load_synonyms()
    out = {
        "version": 1,
        "generatedDocCount": len(docs),
        "synonyms": synonyms,
        "docs": docs,
    }
    # Sort keys + compact separators so the file diffs cleanly day-to-day.
    OUT_PATH.write_text(
        json.dumps(out, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    size_kb = OUT_PATH.stat().st_size / 1024
    print(
        f"search-index.json: {len(docs)} docs, "
        f"{len(synonyms)} synonym groups, "
        f"{size_kb:.1f} KB"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
