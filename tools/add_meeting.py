#!/usr/bin/env python3
"""Publish a new CSOH meeting recap.

Input is an Apple Notes-style export of a "CSOH YYYY-MM-DD" note, saved to
a file (HTML or plain text). The script:

1. Writes a standalone per-meeting page at /meetings/YYYY-MM-DD.html (using
   the previously-newest meeting page as the template).
2. Inserts a card at the top of /meetings.html and updates counts plus the
   ItemList JSON-LD.
3. Patches the previously-newest meeting page's pager to add a
   "Newer meeting →" link to the new page.
4. Adds an entry to sitemap.xml and meetings-search-index.json.

Supported input formats:

1. Apple Notes HTML export — `<div>`/`<h1>`/`<h2>` soup as returned by the
   Apple Notes MCP `get_note_content` tool.
2. Plain text / Markdown — lines beginning with `#` or `##` are treated as
   headings; everything else is a paragraph belonging to the most recent
   heading.

Expected content:
- An `<h1>` (or `# ...`) with the note title, e.g. `CSOH 2026-04-24`.
- An `<h2>` (or `## Quick recap`) followed by the recap paragraph.
- Any number of `<h2>` / `## ...` subsections followed by a paragraph each.

Usage:

    python3 tools/add_meeting.py path/to/note.html
    python3 tools/add_meeting.py path/to/note.txt --headline "Short headline" \\
        --tag AI --tag "Supply Chain"

Re-running for an existing date replaces the prior page in place.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html as h
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MEETINGS_HTML = REPO_ROOT / "meetings.html"
MEETINGS_DIR = REPO_ROOT / "meetings"
SITEMAP_XML = REPO_ROOT / "sitemap.xml"
SEARCH_INDEX = REPO_ROOT / "meetings-search-index.json"

TITLE_RE = re.compile(r"CSOH\s+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)
ENTITY_FIXES = [
    ("&quot;", '"'),
    ("&quot", '"'),
    ("&amp;", "&"),
    ("&amp", "&"),
    ("&#x27;", "'"),
    ("&#39;", "'"),
    ("&lt;", "<"),
    ("&gt;", ">"),
]


def clean_text(s: str) -> str:
    for before, after in ENTITY_FIXES:
        s = s.replace(before, after)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def strip_tags(fragment: str) -> str:
    return re.sub(r"<[^>]+>", "", fragment)


def parse_html_note(raw: str) -> dict:
    """Parse Apple Notes-style HTML into structured meeting data."""
    # Title (h1 or first CSOH date we find)
    title_match = TITLE_RE.search(raw)
    if not title_match:
        raise ValueError("Could not find a `CSOH YYYY-MM-DD` title in the note.")
    date_iso = title_match.group(1)

    # Normalize whitespace and remove line breaks between tags
    text = raw.replace("\r", "")

    # Find all h1/h2 headings and the content between them.
    pieces = re.split(
        r"<h([12])[^>]*>(.*?)</h\1>",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # re.split with a capturing group returns: [before, lvl, heading, body, lvl, heading, body, ...]
    sections: list[tuple[str, str]] = []  # (heading, body_html)
    # Skip leading text; iterate in groups of 3
    for i in range(1, len(pieces), 3):
        heading_html = pieces[i + 1]
        body_html = pieces[i + 2] if i + 2 < len(pieces) else ""
        heading = clean_text(strip_tags(heading_html))
        if not heading:
            continue
        sections.append((heading, body_html))

    if not sections:
        # Fallback: maybe the note is plain text with h1 only
        raise ValueError("Note has no <h2> sections to parse.")

    # The first section with a CSOH date heading is the title; skip it.
    topics: list[tuple[str, str]] = []
    recap = ""
    for heading, body_html in sections:
        body_text = clean_text(strip_tags(body_html))
        if TITLE_RE.search(heading):
            continue
        if heading.lower() in ("quick recap", "summary") and not recap:
            if heading.lower() == "summary" and not body_text:
                # Some notes have an empty "Summary" heading that precedes topics.
                continue
            recap = body_text
            continue
        if body_text:
            topics.append((heading, body_text))

    if not recap:
        raise ValueError("Could not locate a 'Quick recap' paragraph in the note.")
    if not topics:
        raise ValueError("No topic sections with content found.")

    return {"date": date_iso, "recap": recap, "topics": topics}


def parse_markdown_note(raw: str) -> dict:
    """Parse markdown/plain-text note where lines start with # or ## headings."""
    title_match = TITLE_RE.search(raw)
    if not title_match:
        raise ValueError("Could not find a `CSOH YYYY-MM-DD` title in the note.")
    date_iso = title_match.group(1)

    lines = [ln.strip() for ln in raw.splitlines()]
    sections: list[tuple[str, list[str]]] = []
    current_heading: str | None = None
    current_body: list[str] = []
    for ln in lines:
        m = re.match(r"^(#{1,3})\s+(.*)$", ln)
        if m:
            if current_heading is not None:
                sections.append((current_heading, current_body))
            current_heading = m.group(2).strip()
            current_body = []
        else:
            if current_heading is not None and ln:
                current_body.append(ln)
    if current_heading is not None:
        sections.append((current_heading, current_body))

    recap = ""
    topics: list[tuple[str, str]] = []
    for heading, body in sections:
        body_text = clean_text(" ".join(body))
        if TITLE_RE.search(heading):
            continue
        if heading.lower() in ("quick recap", "summary") and not recap:
            if heading.lower() == "summary" and not body_text:
                continue
            recap = body_text
            continue
        if body_text:
            topics.append((heading, body_text))

    if not recap:
        raise ValueError("Could not locate a 'Quick recap' section in the note.")
    if not topics:
        raise ValueError("No topic sections with content found.")

    return {"date": date_iso, "recap": recap, "topics": topics}


def parse_note(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    looks_like_html = "<" in raw and re.search(r"<(div|h1|h2|p|br)\b", raw, re.IGNORECASE)
    parser = parse_html_note if looks_like_html else parse_markdown_note
    return parser(raw)


def human_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso)
    return d.strftime("%A, %B %-d, %Y")


def default_headline(meeting: dict) -> str:
    if meeting["topics"]:
        return meeting["topics"][0][0]
    return "Meeting recap"


def truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    return cut + "…"


def render_article_body(meeting: dict, headline: str) -> str:
    """Render the inner content of <article class="section meeting-page"> for
    a per-meeting page."""
    iso = meeting["date"]
    human = human_date(iso)
    month = iso[:7]
    tags = [month] + list(dict.fromkeys(meeting.get("tags") or []))
    tag_spans = "".join(f'<span class="tag">{h.escape(t)}</span>' for t in tags)
    topic_html = "\n".join(
        f"            <h3>{h.escape(hd)}</h3>\n            <p>{h.escape(bd)}</p>\n"
        for hd, bd in meeting["topics"]
    )
    n = len(meeting["topics"])
    summary_label = f"Show {n} discussion topics" if n != 1 else "Show discussion topic"
    return (
        f'<h2><time datetime="{iso}">{h.escape(human)}</time> — {h.escape(headline)}</h2>\n'
        f'            <p><strong>Quick recap.</strong> {h.escape(meeting["recap"])}</p>\n'
        f'            <div class="resource-tags meeting-tags">{tag_spans}</div>\n'
        f'            <details class="meeting-topics">\n'
        f'                <summary>{summary_label}</summary>\n'
        f'{topic_html}'
        f'            </details>\n'
        f'            <p class="small"><a href="../meetings.html">↑ All meeting recaps</a></p>'
    )


def find_template_page() -> Path:
    """Find the previously-newest per-meeting page to use as the page template
    (preserves CSS/JS version hashes and any cross-cutting page updates)."""
    candidates = sorted(
        MEETINGS_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html"),
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(f"No existing meeting pages found in {MEETINGS_DIR}")
    return candidates[0]


def render_full_page(meeting: dict, headline: str, prev_iso: str, next_iso: str) -> str:
    """Build the full HTML for /meetings/YYYY-MM-DD.html by deriving from the
    current newest page."""
    import json

    iso = meeting["date"]
    human = human_date(iso)
    body = render_article_body(meeting, headline)
    meta_desc = truncate(meeting["recap"], 155)
    headline_safe = headline.replace('"', "&quot;")
    headline_clean = headline[:90]

    pager_parts = []
    if prev_iso:
        pager_parts.append(
            f'<a class="pager-link pager-prev" href="{prev_iso}.html">← Older meeting</a>'
        )
    pager_parts.append(
        '<a class="pager-link pager-index" href="../meetings.html">All meetings</a>'
    )
    if next_iso:
        pager_parts.append(
            f'<a class="pager-link pager-next" href="{next_iso}.html">Newer meeting →</a>'
        )
    pager_html = "\n            ".join(pager_parts)

    template_path = find_template_page()
    template_date = template_path.stem  # YYYY-MM-DD
    out = template_path.read_text(encoding="utf-8")

    template_human = human_date(template_date)
    out = out.replace(template_human, human)
    out = out.replace(template_date, iso)
    out = re.sub(
        r'<meta name="description" content="[^"]*">',
        f'<meta name="description" content="{h.escape(meta_desc, quote=True)}">',
        out, count=1,
    )
    out = re.sub(
        r'<meta name="keywords" content="[^"]*">',
        f'<meta name="keywords" content="cloud security meeting recap, CSOH, {iso}, Friday Zoom, {h.escape(headline_clean, quote=True)}">',
        out, count=1,
    )
    out = re.sub(
        r"<title>[^<]*</title>",
        f"<title>{human} — CSOH Meeting Recap</title>",
        out, count=1,
    )
    out = re.sub(
        r'<meta property="og:title" content="[^"]*">',
        f'<meta property="og:title" content="{human} CSOH Recap — {h.escape(headline_safe[:80], quote=True)}">',
        out, count=1,
    )
    out = re.sub(
        r'<meta property="og:description" content="[^"]*">',
        f'<meta property="og:description" content="{h.escape(meta_desc, quote=True)}">',
        out, count=1,
    )
    out = re.sub(
        r'<meta name="twitter:title" content="[^"]*">',
        f'<meta name="twitter:title" content="{human} CSOH Recap">',
        out, count=1,
    )
    out = re.sub(
        r'<meta name="twitter:description" content="[^"]*">',
        f'<meta name="twitter:description" content="{h.escape(meta_desc, quote=True)}">',
        out, count=1,
    )
    headline_json = json.dumps(headline)
    out = re.sub(
        r'"headline":\s*"[^"]+",',
        lambda mm: f'"headline": {headline_json},',
        out, count=1,
    )
    desc_json = json.dumps(meta_desc)
    out = re.sub(
        r'"description":\s*"[^"]*"',
        lambda mm: f'"description": {desc_json}',
        out, count=1,
    )
    # Breadcrumb final item (name/item pair). The Apple Notes-generated
    # template uses single quotes around the name, so handle both quote styles.
    name_json = json.dumps(human)
    repl = f'"name": {name_json},\n          "item": "https://csoh.org/meetings/{iso}.html"'
    out = re.sub(
        r"\"name\":\s*['\"][^'\"]+['\"],\s*\n\s*\"item\":\s*\"https://csoh\.org/meetings/[^\"]+\"",
        lambda mm: repl,
        out, count=1,
    )
    out = re.sub(
        r"<h1>[^<]+— Meeting Recap</h1>",
        f"<h1>{human} — Meeting Recap</h1>",
        out, count=1,
    )
    # Hero subtitle <p> immediately after the <h1>
    out = re.sub(
        r'(<section class="hero hero--compact">.*?<h1>[^<]+</h1>\s*<p>)[^<]*(</p>)',
        lambda mm: mm.group(1) + h.escape(headline) + mm.group(2),
        out, count=1, flags=re.DOTALL,
    )
    out = re.sub(
        r'<li><span aria-current="page">[^<]+</span></li>',
        f'<li><span aria-current="page">{human}</span></li>',
        out, count=1,
    )
    out = re.sub(
        r'(<article class="section meeting-page">\s*)(.*?)(\s*</article>)',
        lambda mm: mm.group(1) + body + mm.group(3),
        out, count=1, flags=re.DOTALL,
    )
    out = re.sub(
        r'(<nav class="incident-pager" aria-label="Other meeting recaps">\s*)(.*?)(\s*</nav>)',
        lambda mm: mm.group(1) + pager_html + mm.group(3),
        out, count=1, flags=re.DOTALL,
    )
    return out


def patch_prev_pager(prev_iso: str, new_iso: str) -> None:
    """Add or update a 'Newer meeting →' link on the previously-newest page."""
    p = MEETINGS_DIR / f"{prev_iso}.html"
    if not p.exists():
        return
    txt = p.read_text(encoding="utf-8")
    if re.search(r'class="pager-link pager-next"', txt):
        txt = re.sub(
            r'(<a class="pager-link pager-next" href=")[^"]+(">[^<]*</a>)',
            rf"\g<1>{new_iso}.html\g<2>",
            txt, count=1,
        )
    else:
        txt = re.sub(
            r'(<a class="pager-link pager-index" href="\.\./meetings\.html">All meetings</a>)',
            rf'\1\n            <a class="pager-link pager-next" href="{new_iso}.html">Newer meeting →</a>',
            txt, count=1,
        )
    p.write_text(txt, encoding="utf-8")


def find_existing_newest_other_than(iso: str) -> str:
    """Find the existing newest meeting iso, excluding the supplied one."""
    candidates = sorted(
        (p.stem for p in MEETINGS_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html")),
        reverse=True,
    )
    for d in candidates:
        if d != iso:
            return d
    return ""


def render_card(meeting: dict, headline: str) -> str:
    iso = meeting["date"]
    human = human_date(iso)
    teaser = truncate(meeting["recap"], 240)
    tags = [iso[:7]] + list(dict.fromkeys(meeting.get("tags") or []))
    tags_html = "".join(f'<span class="tag">{h.escape(t)}</span>' for t in tags)
    return (
        f'        <article class="section meeting-card" id="meeting-{iso}">\n'
        f'            <a class="meeting-card-link" href="meetings/{iso}.html">\n'
        f'                <h2><time datetime="{iso}">{h.escape(human)}</time> — {h.escape(headline)}</h2>\n'
        f'                <p class="meeting-card-summary">{h.escape(teaser)}</p>\n'
        f'                <div class="resource-tags meeting-tags">{tags_html}</div>\n'
        f'                <span class="meeting-card-cta">Read recap →</span>\n'
        f'            </a>\n'
        f'        </article>'
    )


def update_meetings_index(meeting: dict, headline: str) -> None:
    """Insert or replace the meeting card in meetings.html and refresh counts
    plus the ItemList JSON-LD."""
    import json

    iso = meeting["date"]
    txt = MEETINGS_HTML.read_text(encoding="utf-8")

    # Replace existing card if present, otherwise insert at top.
    card = render_card(meeting, headline)
    existing_card_re = re.compile(
        rf'        <article class="section meeting-card" id="meeting-{re.escape(iso)}">.*?</article>',
        re.DOTALL,
    )
    if existing_card_re.search(txt):
        txt = existing_card_re.sub(card, txt, count=1)
    else:
        txt = re.sub(
            r'(<div class="meeting-list">\s*\n)',
            rf"\g<1>{card}\n",
            txt, count=1,
        )

    n_now = len(re.findall(r'<article class="section meeting-card"', txt))

    # Rebuild ItemList JSON-LD positions/numberOfItems.
    ld_match = re.search(
        r'(<script type="application/ld\+json">\s*\{[^{}]*"@type":\s*"ItemList".*?</script>)',
        txt, re.DOTALL,
    )
    if ld_match:
        block = ld_match.group(1)
        existing = []
        for em in re.finditer(
            r'\{\s*"@type":\s*"ListItem",\s*"position":\s*\d+,\s*"url":\s*"([^"]+)",\s*"name":\s*"([^"]+)"\s*\}',
            block, re.DOTALL,
        ):
            existing.append((em.group(1), em.group(2)))
        new_url = f"https://csoh.org/meetings/{iso}.html"
        new_name = f"{iso}: {headline.replace(chr(34), chr(39))}"
        # Drop any prior entry for this iso (replace path).
        existing = [(u, n) for (u, n) in existing if iso not in u]
        full = [(new_url, new_name)] + existing
        rebuilt = []
        for pos, (url, name) in enumerate(full, start=1):
            rebuilt.append(
                "    {\n"
                '      "@type": "ListItem",\n'
                f'      "position": {pos},\n'
                f"      \"url\": {json.dumps(url)},\n"
                f"      \"name\": {json.dumps(name)}\n"
                "    }"
            )
        items_str = ",\n".join(rebuilt)
        new_block = re.sub(
            r'"numberOfItems":\s*\d+',
            f'"numberOfItems": {len(full)}',
            block, count=1,
        )
        new_block = re.sub(
            r'"itemListElement":\s*\[.*?\]',
            f'"itemListElement": [\n{items_str}\n  ]',
            new_block, count=1, flags=re.DOTALL,
        )
        txt = txt.replace(block, new_block, 1)

    # Counts in copy + meta tags.
    txt = re.sub(r"(notes from )\d+( CSOH sessions)", rf"\g<1>{n_now}\g<2>", txt)
    txt = re.sub(r"(\b)\d+( CSOH sessions)", rf"\g<1>{n_now}\g<2>", txt)
    txt = re.sub(
        r"(\b)\d+( sessions of vendor-neutral practitioner discussion)",
        rf"\g<1>{n_now}\g<2>", txt,
    )
    txt = re.sub(
        r"(Topic-by-topic recaps from )\d+( weekly CSOH sessions)",
        rf"\g<1>{n_now}\g<2>", txt,
    )
    txt = re.sub(
        r'<p class="meeting-count"><span id="visibleMeetings">\d+(</span> meetings)',
        rf'<p class="meeting-count"><span id="visibleMeetings">{n_now}\g<1>',
        txt,
    )

    MEETINGS_HTML.write_text(txt, encoding="utf-8")


def update_sitemap(iso: str) -> None:
    if not SITEMAP_XML.exists():
        return
    txt = SITEMAP_XML.read_text(encoding="utf-8")
    if f"meetings/{iso}.html" in txt:
        return  # Already present; update_sitemap.py refreshes lastmod separately.
    today = dt.date.today().isoformat()
    # Insert before the closing </urlset>.
    block = (
        "  <url>\n"
        f"    <loc>https://csoh.org/meetings/{iso}.html</loc>\n"
        f"    <lastmod>{today}</lastmod>\n"
        "    <changefreq>yearly</changefreq>\n"
        "    <priority>0.5</priority>\n"
        "  </url>\n"
    )
    txt = txt.replace("</urlset>", block + "</urlset>", 1)
    SITEMAP_XML.write_text(txt, encoding="utf-8")


def update_search_index(meeting: dict, headline: str) -> None:
    if not SEARCH_INDEX.exists():
        return
    import json

    data = json.loads(SEARCH_INDEX.read_text(encoding="utf-8"))
    iso = meeting["date"]
    human = human_date(iso).lower()
    parts = [
        f"{human} — {headline.lower()}",
        "quick recap.", meeting["recap"].lower(),
    ]
    for hd, bd in meeting["topics"]:
        parts.append(hd.lower())
        parts.append(bd.lower())
    parts.append(" ".join((iso[:7], *(meeting.get("tags") or []))).lower())
    record = {
        "id": f"meeting-{iso}",
        "text": re.sub(r"\s+", " ", " ".join(parts)).strip(),
    }
    existing = next((i for i, r in enumerate(data) if r["id"] == record["id"]), None)
    if existing is not None:
        data[existing] = record
    else:
        data.insert(0, record)
    SEARCH_INDEX.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publish a CSOH meeting recap.")
    parser.add_argument("note", type=Path, help="Path to the Apple Notes export (HTML or text)")
    parser.add_argument(
        "--headline",
        type=str,
        default=None,
        help="Short headline for the card and h2 (default: first topic heading).",
    )
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        help="Topical tag to attach (repeatable). Example: --tag AI --tag Conferences",
    )
    parser.add_argument(
        "--meetings-file",
        type=Path,
        default=MEETINGS_HTML,
        help="Path to meetings.html (default: repo-root meetings.html).",
    )
    args = parser.parse_args(argv)

    if not args.note.exists():
        print(f"Error: {args.note} not found", file=sys.stderr)
        return 1

    try:
        meeting = parse_note(args.note)
    except ValueError as exc:
        print(f"Error parsing note: {exc}", file=sys.stderr)
        return 1

    meeting["tags"] = [t.strip() for t in args.tag if t.strip()]
    headline = (args.headline or default_headline(meeting)).strip()

    iso = meeting["date"]
    existing_newest = find_existing_newest_other_than(iso)

    # Per-meeting page. New meeting becomes the newest, so next_iso is empty;
    # prev_iso is the previously-newest (or its prior link if we're replacing).
    page = render_full_page(meeting, headline, prev_iso=existing_newest, next_iso="")
    out_path = MEETINGS_DIR / f"{iso}.html"
    action = "Replaced" if out_path.exists() else "Wrote"
    out_path.write_text(page, encoding="utf-8")
    print(f"{action} {out_path.relative_to(REPO_ROOT)}")

    if existing_newest and existing_newest != iso:
        patch_prev_pager(existing_newest, iso)
        print(f"  patched {existing_newest}.html pager → next={iso}")

    update_meetings_index(meeting, headline)
    update_sitemap(iso)
    update_search_index(meeting, headline)
    print("  updated meetings.html, sitemap.xml, meetings-search-index.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
