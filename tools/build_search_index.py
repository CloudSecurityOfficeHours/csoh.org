#!/usr/bin/env python3
"""
Build the site-wide full-text search index used by /search.html.

Output: /search-index.json — a JSON document with two top-level fields:
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

# Pages where we want a single page-level entry rather than per-section docs
# (their content is dynamic, paginated, or already has its own search UI).
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

# Glossary term shape: <dt id="term-..."><term text></dt> ... <dd>def</dd>.
# The glossary page is dense enough that we extract each <dt>/<dd> pair as
# its own indexable doc — search for "NHI" should land directly on the
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
    for sep in (" - ", " — ", " | "):
        if sep in full_title:
            base, tail = full_title.rsplit(sep, 1)
            if tail.strip().lower() in {"csoh", "cloud security office hours"}:
                return base.strip()
    return full_title


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
        # No <section id="..."> structure — emit one page-level doc.
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
        # 4000 chars is roughly 600-700 words — plenty for snippet hits.
        text = text[:2400]
        yield {
            "id": f"{filename}#{section_id}",
            "url": f"/{filename}#{section_id}",
            "page": title,
            "section": heading,
            "heading": heading,
            "title": f"{heading} — {title}",
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
            # Skip empty entries (defensive — should not happen).
            if not doc.get("text") and not doc.get("heading"):
                continue
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
