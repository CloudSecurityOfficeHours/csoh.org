#!/usr/bin/env python3
"""Regenerate VideoObject JSON-LD schema in presentations.html.

Emits one VideoObject per YouTube talk on the presentations page and injects
the block just before `</head>`, replacing any prior block with the same
marker comment.

Run whenever presentations are added or edited.

Card shapes
-----------
The page carries three card shapes, and a video's href, title and blurb sit in
different places in each:

1. `.resource-card` - the whole card is wrapped in
   `<a class="card-link" href="...youtube...">`, so the href is on the element
   *enclosing* the card and the `<h3>`/`<p>` are inside it.
2. `.resource-card--with-deck` - the card is a `<div>` and the card-link anchor
   sits *inside* it, wrapping only the thumbnail; the `<h3>`/`<p>` are siblings
   of that anchor, not descendants.
3. `.resource-card--deck` - slides only, no video. Skipped.

This script used to match the anchor and then look for `<h3>`/`<p>` inside it,
which only ever held for shape 1. The two shape-2 cards fell through a bare
`continue` and were dropped from the schema with no warning, for as long as
that shape had existed. Extraction is now anchored on the card `<div>` - one
brace-balanced block per card, every field pulled from that same block - and
`main()` refuses to write a schema holding fewer VideoObjects than the page has
YouTube card links.
"""

import datetime as dt
import html as html_mod
import json
import re
import sys
from pathlib import Path

HTML_PATH = Path(__file__).resolve().parent.parent / "presentations.html"

MARKER = "<!-- Structured Data - Presentations (VideoObject) -->"

CARD_DIV_RE = re.compile(r'<div\b[^>]*\bclass="[^"]*\bresource-card\b[^"]*"[^>]*>')
DIV_TAG_RE = re.compile(r"<(/?)div\b", re.IGNORECASE)
ANCHOR_TAG_RE = re.compile(r"<a\b[^>]*>")
# Shape 1's anchor is the tag immediately preceding the card div.
TRAILING_ANCHOR_RE = re.compile(r"<a\b[^>]*>\s*$")
CLASS_ATTR_RE = re.compile(r'\bclass="([^"]*)"')
YT_HREF_RE = re.compile(
    r'\bhref="(https://www\.youtube\.com/watch\?v=([A-Za-z0-9_-]+)[^"]*)"'
)
H3_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL)
P_RE = re.compile(r"<p[^>]*>(.*?)</p>", re.DOTALL)
DATE_RE = re.compile(r"^([A-Z][a-z]+ \d{1,2}, \d{4}):\s*")


class ExtractionError(RuntimeError):
    """A card could not be parsed. Never swallow this - see the module docstring."""


def strip_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", html_mod.unescape(text)).strip()


def parse_date(prefix: str) -> str | None:
    try:
        return dt.datetime.strptime(prefix, "%B %d, %Y").date().isoformat()
    except ValueError:
        return None


def youtube_card_link(tag: str) -> tuple[str, str] | None:
    """Return (url, video_id) if this `<a>` tag is a YouTube card link, else None.

    Both values are read out of the one tag string, so an href can never be
    paired with a different element's class - the rule CLAUDE.md records after
    an SRI check compared one tag's hash against another tag's integrity.
    """
    class_m = CLASS_ATTR_RE.search(tag)
    if not class_m or "card-link" not in class_m.group(1).split():
        return None
    href_m = YT_HREF_RE.search(tag)
    if not href_m:
        return None
    return href_m.group(1), href_m.group(2)


def card_body(html_text: str, start: int) -> tuple[str, int]:
    """Return (inner HTML, index past `</div>`) for the div whose open tag ends at `start`.

    Cards nest `.resource-tags` and `.deck-frame` divs inside them, so the close
    tag has to be found by balancing rather than by a non-greedy match.
    """
    depth = 1
    for m in DIV_TAG_RE.finditer(html_text, start):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return html_text[start:m.start()], m.end()
    raise ExtractionError("unbalanced <div> inside a resource-card block")


def iter_cards(html_text: str):
    """Yield (link, body) for every `.resource-card` block, in document order.

    `link` is None for a card with no YouTube video (shape 3).
    """
    pos = 0
    while True:
        m = CARD_DIV_RE.search(html_text, pos)
        if not m:
            return
        body, pos = card_body(html_text, m.end())

        link = None
        for tag in ANCHOR_TAG_RE.finditer(body):        # shape 2: anchor inside
            link = youtube_card_link(tag.group(0))
            if link:
                break
        if link is None:                                # shape 1: anchor encloses
            window = html_text[max(0, m.start() - 500):m.start()]
            prev = TRAILING_ANCHOR_RE.search(window)
            if prev:
                link = youtube_card_link(prev.group(0))
        yield link, body


def card_link_ids(html_text: str) -> list[str]:
    """Every YouTube card-link id on the page, found without reference to card structure.

    Deliberately independent of `iter_cards()`: it is the yardstick the parsed
    result is measured against, so it must not share the assumption under test.
    """
    ids = []
    for tag in ANCHOR_TAG_RE.finditer(html_text):
        link = youtube_card_link(tag.group(0))
        if link:
            ids.append(link[1])
    return ids


def extract_videos(html_text: str) -> list[dict]:
    videos = []
    for link, body in iter_cards(html_text):
        if link is None:
            continue  # slides-only card; there is no video to describe
        url, video_id = link
        h3m = H3_RE.search(body)
        pm = P_RE.search(body)
        if not h3m or not pm:
            raise ExtractionError(
                f"card for video {video_id} has no {'<h3>' if not h3m else '<p>'}; "
                "refusing to omit it silently"
            )
        title = strip_tags(h3m.group(1))
        desc = strip_tags(pm.group(1))
        date_match = DATE_RE.match(title)
        upload_date = parse_date(date_match.group(1)) if date_match else None
        name = DATE_RE.sub("", title) or title
        videos.append(
            {
                "video_id": video_id,
                "url": url,
                "name": name,
                "description": desc,
                "thumbnail": f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
                "upload_date": upload_date,
            }
        )
    return videos


def build_items(videos):
    items = []
    for v in videos:
        item = {
            "@type": "VideoObject",
            "name": v["name"],
            "description": v["description"],
            "thumbnailUrl": v["thumbnail"],
            "contentUrl": v["url"],
            "embedUrl": f"https://www.youtube.com/embed/{v['video_id']}",
            "publisher": {
                "@type": "Organization",
                "name": "Cloud Security Office Hours",
                "logo": {
                    "@type": "ImageObject",
                    "url": "https://csoh.org/banner.png",
                },
            },
        }
        if v["upload_date"]:
            item["uploadDate"] = v["upload_date"]
        items.append(item)
    return items


def render_block(items) -> str:
    schema = {"@context": "https://schema.org", "@graph": items}
    payload = json.dumps(schema, indent=2, ensure_ascii=False).replace("</", "<\\/")
    indented = "\n".join(("    " + line) if line else line for line in payload.split("\n"))
    return (
        f"    {MARKER}\n"
        f'    <script type="application/ld+json">\n'
        f"{indented}\n"
        f"    </script>\n"
    )


def inject(html_text: str, block: str) -> str:
    existing = re.compile(
        rf"\s*{re.escape(MARKER)}\s*<script type=\"application/ld\+json\">.*?</script>\n?",
        re.DOTALL,
    )
    if existing.search(html_text):
        return existing.sub("\n" + block, html_text, count=1)
    return html_text.replace("</head>", block + "</head>", 1)


def main() -> int:
    html_text = HTML_PATH.read_text(encoding="utf-8")

    expected = card_link_ids(html_text)
    if not expected:
        print("No YouTube cards found", file=sys.stderr)
        return 1

    try:
        videos = extract_videos(html_text)
    except ExtractionError as exc:
        print(f"presentations schema: {exc}", file=sys.stderr)
        return 1

    # A shortfall here means the page grew a card shape this parser does not
    # understand, which is exactly how two `--with-deck` cards went missing for
    # as long as that shape existed. Comparing the lists rather than just their
    # lengths also catches an href paired with the wrong card. Refuse to write a
    # partial schema; a deploy that fails is cheaper than one that silently
    # ships less than the page claims.
    got = [v["video_id"] for v in videos]
    if got != expected:
        missing = [vid for vid in expected if vid not in got]
        extra = [vid for vid in got if vid not in expected]
        print(
            f"presentations schema: page has {len(expected)} YouTube card link(s) "
            f"but {len(got)} parsed into VideoObjects",
            file=sys.stderr,
        )
        if missing:
            print(f"  missing:    {', '.join(missing)}", file=sys.stderr)
        if extra:
            print(f"  unexpected: {', '.join(extra)}", file=sys.stderr)
        if not missing and not extra:
            print("  same ids, different order", file=sys.stderr)
        return 1

    items = build_items(videos)
    block = render_block(items)
    new_text = inject(html_text, block)
    if new_text != html_text:
        HTML_PATH.write_text(new_text, encoding="utf-8")
        print(f"Updated presentations.html with {len(items)} VideoObject entries")
    else:
        print(f"presentations.html schema already up to date ({len(items)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
