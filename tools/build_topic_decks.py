#!/usr/bin/env python3
"""
Topic slide decks: the topic kind of the shared deck builder.

Each teaching page carded on topics.html (less EXCLUDED) can have a slide
deck, written as an outline in tools/decks/topics/<slug>.deck, built into a
.pptx with tools/topic_deck_render.py, published to Google Slides and linked
from one line under the page's page-meta line. The parser, style limits,
mapping, stamping, staleness and build loop are build_breach_decks.py's,
run with the TOPIC DeckKind; this module adds what topic pages need.

Outline format (what differs from a breach outline):

    title: <deck title>
    page: <slug>.html
    as-of: YYYY-MM-DD
    promise: <one sentence>

    == <slide heading>
    layout: figure
    section: <id> | <id>
    figure: <figure id>
    Prose lines join into one paragraph.
    notes:
    Speaker notes run to the next "== " line.

- Every slide carries section:, naming the ids of the page sections it draws
  on. An id is the id of the <section> wrapping an h2 in <main>; an h2 with
  no such section gets a slug of its text; the text before the first h2 is
  section "top". `--extract SLUG` lists them.
- Layouts: text, stats, checklist, list, links, layers, timeline, compare, table,
  bars, matrix, question, answer and figure. A figure slide names one of the
  page's diagram figures, inside a section it cites, and the builder places
  the rendered diagram with the page's own caption under it. A deck whose
  page has a diagram figure has at least one figure slide, and shows each
  figure once.
- Every number, technique ID and link in a slide's text and notes appears in
  the sections it cites; the title and promise are held to the whole page.
- On a page that carries the Wiz disclosure, the first slide that shows Wiz
  carries it on the slide, where the audience sees it; notes that name Wiz
  before any slide shows it carry it too.
- A slide cites one or two sections; three or more is a parse error.

published.json maps each slug to its id, outline_sha256, page_sha256, the
hash of the cover's art (cover_sha256), the hash of each section the deck
cites (sections) and the publish date. A section's hash covers its text and
the SVG markup of its figures, so a redrawn diagram flags the deck; --stale
names the cited sections that changed, and a change to a section no slide
cites does not flag the deck. The cover's art (the hero, or the topics.html
tile on a page without one) sits outside <main> and is hashed on its own.

--self-test and --check use the standard library only. --build and
--self-test-render need python-pptx and Pillow, and --build needs Playwright
to render the page's diagrams.

Usage:
    python3 tools/build_topic_decks.py --self-test
    python3 tools/build_topic_decks.py --check
    python3 tools/build_topic_decks.py --extract SLUG [--sections ID,ID]
    python3 tools/build_topic_decks.py --build SLUG [SLUG ...]
    python3 tools/build_topic_decks.py --self-test-render
    python3 tools/build_topic_decks.py --stale [--published-only]
    python3 tools/build_topic_decks.py --status
    python3 tools/build_topic_decks.py --stamp
    python3 tools/build_topic_decks.py --record SLUG PRES_ID
"""

from __future__ import annotations

import hashlib
import html as htmllib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_breach_decks as bbd  # noqa: E402
from build_breach_decks import OutlineError, _capture, _plant, _raises, _rooted, _run_cases  # noqa: E402

# Carded on topics.html, but reference pages rather than teaching topics.
EXCLUDED = frozenset({"glossary.html", "faq.html", "vendor-landscape.html"})
# The id of the text before a page's first h2.
TOP = "top"
TOPIC_PAGE_RE = re.compile(r"[a-z0-9][a-z0-9-]*\.html")
TOPIC_DECK_ATTR = "data-topic-deck"
# The disclosure a page carries where it first names Wiz beside a competitor,
# matched in tag-stripped text (a page may bold the name inside it).
DISCLOSURE_RE = re.compile(r"disclosure: the site(?:['’]s)? author works at Wiz", re.I)
WIZ_RE = re.compile(r"\bWiz\b", re.I)


def _class_re(name: str) -> str:
    """A class attribute holding `name` as one whole class."""
    return r'\bclass="(?:[^"]*\s)?' + re.escape(name) + r'(?:\s[^"]*)?"'


A_TAG_RE = re.compile(r"<a\b[^>]*>", re.I)
CARD_LINK_RE = re.compile(_class_re("card-link"))
HREF_ATTR_RE = re.compile(r'\bhref="([^"]*)"')
ID_ATTR_RE = re.compile(r'\bid="([^"]*)"')
IMG_RE = re.compile(r"<img\b[^>]*>", re.I)
SRC_ATTR_RE = re.compile(r'\bsrc="([^"]*)"')
ALT_ATTR_RE = re.compile(r'\balt="([^"]*)"')
ARIA_LABEL_RE = re.compile(r'\baria-label="([^"]*)"')
PAGE_META_RE = re.compile(r"<p\b[^>]*" + _class_re("page-meta") + r"[^>]*>.*?</p\s*>", re.S | re.I)
TOC_OPEN_RE = re.compile(r"<([a-z][a-z0-9]*)\b[^>]*" + _class_re("toc") + r"[^>]*>", re.I)
HERO_OPEN_RE = re.compile(r"<([a-z][a-z0-9]*)\b[^>]*" + _class_re("hero-illustration") + r"[^>]*>", re.I)
FIGURE_RE = re.compile(r"<figure\b([^>]*)>(.*?)</figure\s*>", re.S | re.I)
SVG_RE = re.compile(r"<svg\b.*</svg\s*>", re.S | re.I)
SVG_TITLE_RE = re.compile(r"<title\b([^>]*)>(.*?)</title\s*>", re.S | re.I)
SVG_DESC_RE = re.compile(r"<desc\b[^>]*>(.*?)</desc\s*>", re.S | re.I)
FIGCAPTION_RE = re.compile(r"<figcaption\b[^>]*>(.*?)</figcaption\s*>", re.S | re.I)
H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1\s*>", re.S | re.I)
TITLE_RE = re.compile(r"<title\b[^>]*>(.*?)</title\s*>", re.S | re.I)
GLOSSARY_A_RE = re.compile(r"<a\b[^>]*" + _class_re("glossary-link") + r"[^>]*>(.*?)</a\s*>", re.S | re.I)
GLOSSARY_HREF_RE = re.compile(r"(?:\.\./)?glossary\.html#term-")
# The one line --stamp writes, and the page-meta line it goes after.
TOPIC_DECK_TAGS = ("p", "details")
TOPIC_DECK_LINE_RE = bbd.deck_line_re(TOPIC_DECK_ATTR, TOPIC_DECK_TAGS)
PAGE_META_LINE_RE = re.compile(
    r"^([ \t]*)<p\b[^>\n]*" + _class_re("page-meta") + r"[^>\n]*>(?:(?!</p>)[^\n])*</p>[ \t]*$", re.M
)
MAIN_OPEN_RE = re.compile(r"<main\b[^>]*>", re.I)


# ---------------------------------------------------------------------------
# The topic pages: topics.html's cards, less EXCLUDED.
# ---------------------------------------------------------------------------


def _cards() -> list[tuple[str, str]]:
    """(href, the card's markup up to its </a>) for every card on topics.html,
    in card order; [] when topics.html cannot be read."""
    try:
        html = (bbd.ROOT / "topics.html").read_text(encoding="utf-8")
    except OSError:
        return []
    out = []
    for m in A_TAG_RE.finditer(html):
        tag = m.group(0)
        href = HREF_ATTR_RE.search(tag)
        if CARD_LINK_RE.search(tag) and href:
            end = html.find("</a>", m.end())
            out.append((htmllib.unescape(href.group(1)), html[m.end(): end if end >= 0 else len(html)]))
    return out


def topic_pages() -> list[str]:
    """Every root-level page carded on topics.html, less EXCLUDED, in card
    order. A new card shows up here without a change to this tool."""
    out: list[str] = []
    for href, _body in _cards():
        if TOPIC_PAGE_RE.fullmatch(href) and href not in EXCLUDED and href not in out:
            out.append(href)
    return out


def topic_page_paths() -> list[Path]:
    return [bbd.ROOT / p for p in topic_pages()]


def topic_tile(slug: str) -> tuple[Path, str] | None:
    """The image on the page's topics.html card and its alt text, or None."""
    for href, body in _cards():
        if href == f"{slug}.html":
            img = IMG_RE.search(body)
            src = SRC_ATTR_RE.search(img.group(0)) if img else None
            if src:
                alt = ALT_ATTR_RE.search(img.group(0))
                return bbd.ROOT / htmllib.unescape(src.group(1)), htmllib.unescape(alt.group(1)) if alt else ""
    return None


def cover_source(slug: str, page_html: str) -> tuple[str, Path | None, str] | None:
    """What the generated cover shows: ("hero", None, its label) when the
    page has a hero illustration, else ("tile", the image, its alt) from the
    page's topics.html card, else None. The renderer and its verify both
    read it, so they cannot disagree."""
    if has_hero(page_html):
        return "hero", None, hero_label(page_html)
    tile = topic_tile(slug)
    return ("tile", tile[0], tile[1]) if tile else None


def cover_sha256(slug: str, page_html: str) -> str:
    """A hash of the cover's art: the hero's SVG markup, or the tile's
    image bytes, path and alt text."""
    source = cover_source(slug, page_html)
    if source is None:
        return _sha("none")
    kind, path, alt = source
    if kind == "hero":
        return _sha("hero\n" + _svg_key(hero_svg(page_html) or ""))
    try:
        image = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        image = "missing"
    return _sha(f"tile\n{bbd._rel(path)}\n{alt}\n{image}")


# ---------------------------------------------------------------------------
# The page model: sections, figures, the hero.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Figure:
    """A diagram on the page: a <figure> in <main> holding an <svg>."""

    id: str
    section: str
    title: str
    desc: str
    caption: str
    # Of the SVG markup with glossary links unwrapped and whitespace
    # collapsed: a redrawn shape changes it, a glossary run does not.
    svg_sha256: str


@dataclass
class Section:
    id: str
    heading: str
    # The extract lines, heading line first: link URLs shown, glossary
    # links as plain text, each figure as one line.
    lines: list[str] = field(default_factory=list)
    # The same text without URLs, figure ids or markup prefixes: what the
    # number gate reads.
    plain: list[str] = field(default_factory=list)
    hrefs: list[str] = field(default_factory=list)
    figures: list[str] = field(default_factory=list)
    numbers: set[str] = field(default_factory=set)
    techniques: set[str] = field(default_factory=set)
    links: set[str] = field(default_factory=set)


@dataclass
class TopicPage:
    path: str
    sections: dict[str, Section]
    figures: dict[str, Figure]
    # Normalized SVG markup per figure, for the section hashes.
    svgs: dict[str, str]

    @property
    def text(self) -> str:
        return "\n".join(ln for s in self.sections.values() for ln in s.plain)


def _svg_key(svg: str) -> str:
    return " ".join(GLOSSARY_A_RE.sub(r"\1", svg).split())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"


def _norm(text: str) -> str:
    return " ".join(text.split())


def _element_end(html: str, open_match: re.Match) -> int:
    """The offset just past the element open_match opens, counting nested
    elements of the same name; the end of html when it never closes."""
    tag = open_match.group(1)
    token = re.compile(rf"<(/?){tag}\b[^>]*>", re.I)
    depth, pos = 1, open_match.end()
    while depth:
        t = token.search(html, pos)
        if t is None:
            return len(html)
        depth += -1 if t.group(1) else 1
        pos = t.end()
    return pos


def _drop(html: str, open_re: re.Pattern[str]) -> str:
    """html without every element open_re opens."""
    out, pos = [], 0
    while (m := open_re.search(html, pos)) is not None:
        out.append(html[pos: m.start()])
        pos = _element_end(html, m)
    out.append(html[pos:])
    return "".join(out)


def hero_svg(page_html: str) -> str | None:
    """The hero illustration's <svg>, or None."""
    m = HERO_OPEN_RE.search(page_html)
    if m is None:
        return None
    svg = SVG_RE.search(page_html[m.end(): _element_end(page_html, m)])
    return svg.group(0) if svg else None


def has_hero(page_html: str) -> bool:
    return hero_svg(page_html) is not None


def hero_label(page_html: str) -> str:
    """The hero's alt text: its SVG's <title>, else its aria-label."""
    svg = hero_svg(page_html) or ""
    title = SVG_TITLE_RE.search(svg)
    if title and bbd._strip_tags(title.group(2)):
        return bbd._strip_tags(title.group(2))
    label = ARIA_LABEL_RE.search(svg[: svg.find(">") + 1])
    return htmllib.unescape(label.group(1)) if label else ""


def hero_sha256(page_html: str) -> str:
    return _sha(_svg_key(hero_svg(page_html) or ""))


def _lift_figures(main: str) -> tuple[str, dict[str, tuple[str, str, str, str]]]:
    """main with each <figure> that holds an <svg> replaced by a marker the
    walker turns into one figure line, and per figure key its title, desc,
    caption and normalized SVG. The key is the figure's id, else its SVG
    <title>'s id."""
    found: dict[str, tuple[str, str, str, str]] = {}

    def lift(m: re.Match) -> str:
        attrs, body = m.group(1), m.group(2)
        svg = SVG_RE.search(body)
        if svg is None:
            return m.group(0)
        title = SVG_TITLE_RE.search(svg.group(0))
        fid = ID_ATTR_RE.search(attrs)
        tid = ID_ATTR_RE.search(title.group(1)) if title else None
        key = (fid or tid).group(1) if (fid or tid) else None
        if not key:
            raise OutlineError("a <figure> holding an <svg> has no id, and its SVG <title> has none either")
        if key in found:
            raise OutlineError(f"two figures are keyed {key!r}")
        desc = SVG_DESC_RE.search(svg.group(0))
        caption = FIGCAPTION_RE.search(body[: svg.start()] + body[svg.end():])
        found[key] = (
            bbd._strip_tags(title.group(2)) if title else "",
            bbd._strip_tags(desc.group(1)) if desc else "",
            bbd._strip_tags(caption.group(1)) if caption else "",
            _svg_key(svg.group(0)),
        )
        return f'<div data-deck-figure="{htmllib.escape(key)}"></div>'

    return FIGURE_RE.sub(lift, main), found


BLOCK_TAGS = frozenset({
    "address", "article", "aside", "blockquote", "caption", "dd", "details", "div", "dl", "dt",
    "fieldset", "figcaption", "figure", "footer", "form", "h1", "header", "hr", "li", "main", "nav",
    "ol", "p", "section", "summary", "table", "tbody", "tfoot", "thead", "tr", "ul",
})
SKIP_TAGS = frozenset({"button", "script", "style", "svg", "template"})
HEADING_MARKS = {"h2": "##", "h3": "###", "h4": "####", "h5": "####", "h6": "####"}


class _Walker(HTMLParser):
    """Turns a topic page's cleaned <main> into sections of lines: one per
    paragraph, list item, table row, heading and figure."""

    def __init__(self, path: str, title: str, figs: dict[str, tuple[str, str, str, str]]):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.figs = figs
        top = Section(TOP, title, [f"# {title} {{#{TOP}}}"], [title])
        self.sections: dict[str, Section] = {TOP: top}
        self.cur = top
        self.buf: list[str] = []
        self.pbuf: list[str] = []
        self.skip: list = []  # [tag, depth] while inside a skipped element
        self.open_sections: list[list] = []  # [id or None, whether an h2 claimed it]
        self.heading: str | None = None
        self.items: list[bool] = []  # per open <li>: its "- " is still to be written
        self.pre: list[str] | None = None
        self.row: list[tuple[str, str]] | None = None
        self.cell: tuple[list[str], list[str]] | None = None
        self.anchors: list[str | None] = []

    # Text goes to the open table cell, else to the current block.
    def _text(self, text: str, plain: bool = True) -> None:
        ext, pln = self.cell if self.cell is not None else (self.buf, self.pbuf)
        ext.append(text)
        if plain:
            pln.append(text)

    def _emit(self, line: str, plain: str) -> None:
        self.cur.lines.append(line)
        self.cur.plain.append(plain)

    def _flush(self) -> None:
        text, plain = _norm("".join(self.buf)), _norm("".join(self.pbuf))
        self.buf.clear()
        self.pbuf.clear()
        if not text:
            return
        prefix = ""
        if self.items:
            depth = len(self.items)
            if self.items[-1]:
                prefix = "  " * (depth - 1) + "- "
                self.items[-1] = False
            else:
                prefix = "  " * depth
        self._emit(prefix + text, plain)

    def handle_starttag(self, tag: str, attrs) -> None:
        if self.skip:
            if tag == self.skip[0]:
                self.skip[1] += 1
            return
        if tag in SKIP_TAGS:
            self.skip = [tag, 1]
            return
        a = {k: (v or "") for k, v in attrs}
        if tag == "div" and "data-deck-figure" in a:
            self._flush()
            self._figure(a["data-deck-figure"])
        elif tag in HEADING_MARKS:
            self._flush()
            self.heading = tag
        elif tag == "a":
            href = a.get("href", "").strip()
            self.cur.hrefs.append(href)
            glossary = "glossary-link" in a.get("class", "").split() or GLOSSARY_HREF_RE.match(href)
            self.anchors.append(None if glossary or not href or self.pre is not None else href)
        elif tag == "br":
            self._text(" ")
        elif tag == "pre":
            self._flush()
            self.pre = []
        elif tag == "tr":
            self._flush()
            self.row = []
        elif tag in ("td", "th") and self.row is not None:
            self.cell = ([], [])
        elif tag == "li":
            self._flush()
            self.items.append(True)
        elif tag in BLOCK_TAGS:
            if tag == "section":
                self.open_sections.append([a.get("id") or None, False])
            if self.cell is not None:
                self._text(" ")
            else:
                self._flush()

    def handle_startendtag(self, tag: str, attrs) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in ("br", "hr", "img", "input"):
            self.handle_endtag(tag)

    def handle_endtag(self, tag: str) -> None:
        if self.skip:
            if tag == self.skip[0]:
                self.skip[1] -= 1
                if not self.skip[1]:
                    self.skip = []
            return
        if tag == self.heading:
            self._end_heading()
        elif tag == "a":
            url = self.anchors.pop() if self.anchors else None
            if url:
                self._text(f" ({url})", plain=False)
        elif tag == "pre" and self.pre is not None:
            code = "".join(self.pre).strip("\n").split("\n")
            self.pre = None
            self._emit("```", "")
            for line in code:
                self._emit(line.rstrip(), line.strip())
            self._emit("```", "")
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row.append((_norm("".join(self.cell[0])), _norm("".join(self.cell[1]))))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            if any(ext for ext, _ in self.row):
                self._emit("| " + " | ".join(ext for ext, _ in self.row) + " |",
                           " ".join(p for _, p in self.row))
            self.row = None
        elif tag == "li":
            self._flush()
            if self.items:
                self.items.pop()
        elif tag in BLOCK_TAGS and self.cell is None:
            self._flush()
            if tag == "section" and self.open_sections:
                self.open_sections.pop()

    def handle_data(self, data: str) -> None:
        if self.skip:
            return
        if self.pre is not None:
            self.pre.append(data)
        else:
            self._text(data)

    def _end_heading(self) -> None:
        tag, self.heading = self.heading, None
        text, plain = _norm("".join(self.buf)), _norm("".join(self.pbuf))
        self.buf.clear()
        self.pbuf.clear()
        if tag != "h2":
            if text:
                self._emit(f"{HEADING_MARKS[tag]} {text}", plain)
            return
        inner = self.open_sections[-1] if self.open_sections else None
        if inner and inner[0] and not inner[1]:
            sid = inner[0]
            inner[1] = True
            if sid in self.sections:
                raise OutlineError(f"section id {sid!r} is used twice, or is {TOP!r}, which names the text above the first h2")
        else:
            base = sid = _slug(plain)
            n = 2
            while sid in self.sections:
                sid, n = f"{base}-{n}", n + 1
        self.cur = Section(sid, text, [f"## {text} {{#{sid}}}"], [plain])
        self.sections[sid] = self.cur

    def _figure(self, key: str) -> None:
        title, desc, caption, _svg = self.figs[key]
        line = f"[figure #{key}] {title}" + (f": {desc}" if desc else "") + (f" (caption: {caption})" if caption else "")
        self._emit(line, " ".join(t for t in (title, desc, caption) if t))
        self.cur.figures.append(key)


def parse_topic_page(page_html: str, path: str = "") -> TopicPage:
    """Read a topic page: its sections in order (TOP first), each with its
    extract lines, numbers, technique IDs and links, and its figures. The
    table of contents, page finder, page-meta line and deck line are left
    out. Raises OutlineError when the page has no <main>, a figure cannot be
    keyed, or a section id repeats."""
    m = bbd.MAIN_RE.search(page_html)
    if m is None:
        raise OutlineError("page has no <main> element")
    main = bbd.PAGE_FINDER_RE.sub("", m.group(1))
    main = PAGE_META_RE.sub("", TOPIC_DECK_LINE_RE.sub("", main))
    main = _drop(bbd.COMMENT_RE.sub("", main), TOC_OPEN_RE)
    main, figs = _lift_figures(main)
    h1 = H1_RE.search(page_html) or TITLE_RE.search(page_html)
    walker = _Walker(path, bbd._strip_tags(h1.group(1)) if h1 else "", figs)
    walker.feed(main)
    walker.close()
    walker._flush()
    base = bbd.SITE + path
    figures: dict[str, Figure] = {}
    for sec in walker.sections.values():
        text = "\n".join(sec.plain)
        sec.numbers, sec.techniques = bbd.number_tokens(text), bbd.technique_ids(text)
        sec.links = {
            bbd.normalize_url(h, base) for h in sec.hrefs
            if h and not h.startswith(("#", "mailto:", "javascript:"))
        }
        for key in sec.figures:
            title, desc, caption, svg = figs[key]
            figures[key] = Figure(key, sec.id, title, desc, caption, _sha(svg))
    order = [k for k in figs if k in figures]
    return TopicPage(path, walker.sections, {k: figures[k] for k in order}, {k: figs[k][3] for k in order})


def figures(page_html: str) -> dict[str, Figure]:
    """Every diagram figure in <main>, in page order, keyed by the figure's
    id, or by its SVG <title>'s id where the figure has none."""
    return parse_topic_page(page_html).figures


def sections(page_html: str) -> dict[str, str]:
    """Each section's id and plain text (heading first), TOP first."""
    return {k: "\n".join(s.plain) for k, s in parse_topic_page(page_html).sections.items()}


def _section_hashes(page: TopicPage) -> dict[str, str]:
    return {
        k: _sha("\n".join(s.lines) + "\n" + "\n".join(page.svgs[f] for f in s.figures))
        for k, s in page.sections.items()
    }


def section_hashes(page_html: str) -> dict[str, str]:
    """Each section's hash, over its extract lines (link URLs included,
    glossary links not) and the SVG markup of its figures. The page-meta
    line, the deck line, the nav and the table of contents are outside
    every section."""
    return _section_hashes(parse_topic_page(page_html))


def topic_page_sha256(page_html: str) -> str:
    """One hash over every section's hash: unchanged exactly when no section
    changed."""
    return _sha("\n".join(f"{k} {v}" for k, v in section_hashes(page_html).items()))


def extract_text(page_html: str, path: str, only: list[str] | None = None) -> str:
    """What --extract prints. With `only`, the heading list (the title line
    and every h2 line) and then just those sections, in page order."""
    page = parse_topic_page(page_html, path)
    secs = page.sections
    if only is None:
        chosen = list(secs)
    else:
        unknown = [x for x in only if x not in secs]
        if unknown:
            raise ValueError(
                f"no section {', '.join(map(repr, unknown))} on {path}; its sections are: {', '.join(secs)}"
            )
        chosen = [k for k in secs if k in only]
    body = "\n\n".join("\n".join(secs[k].lines) for k in chosen) + "\n"
    if only is None:
        return body
    return "\n".join(s.lines[0] for s in secs.values()) + "\n\n" + body


def extract(slug: str, only: list[str] | None = None) -> str:
    """The topic page's <main> as text for drafting and review."""
    page = f"{slug}.html"
    if page not in topic_pages():
        raise ValueError(
            f"{page} is not a topic page: topics.html has no card for it, or it is one of "
            f"{', '.join(sorted(EXCLUDED))}"
        )
    return extract_text((bbd.ROOT / page).read_text(encoding="utf-8"), page, only)


# ---------------------------------------------------------------------------
# The deck line: right after the page-meta line at the top of <main>.
# ---------------------------------------------------------------------------


def preview_line_html(pres_id: str, indent: str) -> str:
    """The line --stamp writes under the topic deck line: a closed panel
    holding Google's slide viewer. While it is closed the lazy iframe is not
    rendered, so nothing loads from Google until a reader opens it."""
    src = f"https://docs.google.com/presentation/d/{pres_id}/embed"
    return (
        f'{indent}<details class="deck-preview" {TOPIC_DECK_ATTR}><summary>Preview the slides</summary>'
        f'<div class="deck-frame"><iframe src="{src}" title="Preview of this page\'s slides" '
        'loading="lazy" allowfullscreen></iframe></div></details>'
    )


def insert_deck_line(html: str, pres_id: str) -> str:
    main = MAIN_OPEN_RE.search(html)
    m = PAGE_META_LINE_RE.search(html, main.end()) if main else None
    if m is None:
        raise ValueError('no <p class="page-meta"> line in <main> to put the deck line after')
    end = m.end() + 1 if html[m.end(): m.end() + 1] == "\n" else m.end()
    if end == m.end():
        raise ValueError("the page-meta line is the last line of the file; it needs a newline")
    return html[:end] + bbd.deck_line_html(pres_id, m.group(1), TOPIC) + "\n" + html[end:]


# ---------------------------------------------------------------------------
# The hub: each card on topics.html whose topic has a deck carries the deck's
# links and a closed preview.
# ---------------------------------------------------------------------------

HUB = "topics.html"
HUB_DECK_ATTR = "data-topic-hub-deck"
HUB_CARD_CLASS = "resource-card--topic-deck"
SLIDES_LINK = "docs.google.com/presentation"

# A card is found by its first line and ends at the first line closing it at
# the same indent, so a pattern over its markup cannot run into the next card.
_HUB_START_RE = re.compile(
    r'^(?P<ind> *)(?:(?P<a><a\b[^>\n]*\bclass="card-link"[^>\n]*>)|'
    r'(?P<d><div class="resource-card ' + HUB_CARD_CLASS + r'"[^>\n]*>))',
    re.M,
)
_INNER = r"(?P<inner>(?:(?P=ind)        [^\n]*\n)*)"
_PLAIN_CARD_RE = re.compile(
    r'(?P<ind> *)(?P<a><a\b[^>\n]*\bclass="card-link"[^>\n]*>)\n'
    r'(?P=ind)    <div class="resource-card"(?P<dattr>[^>\n]*)>\n' + _INNER +
    r"(?P=ind)    </div>\n(?P=ind)</a>\n"
)
_DECKED_CARD_RE = re.compile(
    r'(?P<ind> *)<div class="resource-card ' + HUB_CARD_CLASS + r'"(?P<dattr>[^>\n]*)>\n'
    r'(?P=ind)    (?P<a><a\b[^>\n]*\bclass="card-link"[^>\n]*>)\n' + _INNER +
    r"(?P=ind)    </a>\n"
    r'(?P=ind)    <p class="deck-actions" ' + HUB_DECK_ATTR + r'>(?:(?!</p>)[^\n])*</p>\n'
    r'(?P=ind)    <details class="deck-preview" ' + HUB_DECK_ATTR + r'>(?:(?!</details>)[^\n])*</details>\n'
    r"(?P=ind)</div>\n"
)
_H3_RE = re.compile(r"<h3\b[^>]*>(.*?)</h3\s*>", re.S | re.I)


@dataclass
class _HubCard:
    start: int
    end: int
    slug: str | None
    name: str
    decked: bool | None  # None: neither form
    a: str = ""
    dattr: str = ""
    inner: str = ""
    ind: str = ""


def _hub_slug(a_tag: str) -> str | None:
    href = HREF_ATTR_RE.search(a_tag)
    value = htmllib.unescape(href.group(1)) if href else ""
    return value[:-5] if TOPIC_PAGE_RE.fullmatch(value) else None


def _hub_cards(html: str) -> list[_HubCard]:
    cards: list[_HubCard] = []
    pos = 0
    for m in _HUB_START_RE.finditer(html):
        if m.start() < pos:
            continue
        ind, close = m.group("ind"), "</a>" if m.group("a") else "</div>"
        end_m = re.compile(r"^" + ind + close + r"[ \t]*(?:\n|\Z)", re.M).search(html, m.end())
        end = end_m.end() if end_m else html.find("\n", m.start()) + 1 or len(html)
        pos = end
        body = html[m.start(): end]
        form = _DECKED_CARD_RE if m.group("d") else _PLAIN_CARD_RE
        f = form.fullmatch(body)
        a_tag = f.group("a") if f else (A_TAG_RE.search(body, 0 if m.group("a") else len(m.group(0))) or [""])[0]
        slug = _hub_slug(a_tag)
        if f is None:
            where = slug or f"at line {html.count(chr(10), 0, m.start()) + 1}"
            cards.append(_HubCard(m.start(), end, slug, where, None))
            continue
        h3 = _H3_RE.search(f.group("inner"))
        cards.append(_HubCard(m.start(), end, slug, slug or "?", bool(m.group("d")), a_tag, f.group("dattr"),
                              f.group("inner"), ind))
        cards[-1].name = re.sub(r"<[^>]+>", "", h3.group(1)).strip() if h3 else (slug or "?")
    return cards


def _hub_card_html(c: _HubCard, pres_id: str | None) -> str:
    """The card as it is written for pres_id: decked, or plain when None."""
    i = c.ind
    if pres_id is None:
        return (
            f'{i}{c.a}\n{i}    <div class="resource-card"{c.dattr}>\n{c.inner}{i}    </div>\n{i}</a>\n'
        )
    base = f"https://docs.google.com/presentation/d/{pres_id}"
    ext = 'target="_blank" rel="noopener noreferrer"'
    title = c.name.replace('"', "&quot;")
    return (
        f'{i}<div class="resource-card {HUB_CARD_CLASS}"{c.dattr}>\n'
        f'{i}    {c.a}\n{c.inner}{i}    </a>\n'
        f'{i}    <p class="deck-actions" {HUB_DECK_ATTR}><strong>Slides:</strong> '
        f'<a href="{base}/export/pdf" {ext}>PDF</a> <a href="{base}/copy" {ext}>Editable copy</a></p>\n'
        f'{i}    <details class="deck-preview" {HUB_DECK_ATTR}><summary>Preview the slides</summary>'
        f'<div class="deck-frame"><iframe src="{base}/embed" title="Preview of the {title} slides" '
        f'loading="lazy" allowfullscreen></iframe></div></details>\n'
        f'{i}</div>\n'
    )


def _hub_stray(html: str, cards: list[_HubCard]) -> bool:
    """The deck attribute somewhere other than inside a decked card. A card
    of neither form is reported as itself, so its own lines do not count."""
    rest, pos = [], 0
    for c in cards:
        if c.decked is not False:
            rest.append(html[pos: c.start])
            pos = c.end
    rest.append(html[pos:])
    return HUB_DECK_ATTR in "".join(rest)


def _hub_want(c: _HubCard, mapping: dict) -> str | None:
    return bbd._entry_id(mapping.get(c.slug)) if c.slug else None


def stamp_hub(html: str, mapping: dict) -> str:
    """topics.html with every card whose topic is in the mapping (with a
    well-formed id) in its decked form and every other card plain. A card of
    neither form, or the deck attribute outside a decked card, is an error:
    rewriting around it would guess at what to keep."""
    cards = _hub_cards(html)
    for c in cards:
        if c.decked is None:
            raise ValueError(f"{HUB}: the card for {c.name!r} is neither a plain card nor a decked card")
    if _hub_stray(html, cards):
        raise ValueError(f"{HUB}: {HUB_DECK_ATTR} appears outside a decked card")
    out, pos = [], 0
    for c in cards:
        out += [html[pos: c.start], _hub_card_html(c, _hub_want(c, mapping))]
        pos = c.end
    out.append(html[pos:])
    return "".join(out)


def hub_findings(html: str, mapping: dict) -> list[str]:
    """Where topics.html disagrees with the mapping: one finding per card
    that differs from what stamp_hub writes, and any Google Slides link
    outside a decked card's two strip lines."""
    findings: list[str] = []
    cards = _hub_cards(html)
    for c in cards:
        if c.decked is None:
            findings.append(f"{HUB}: the card for {c.name!r} is malformed: neither a plain card nor a decked "
                            "card, so its deck markup cannot be read")
            continue
        want = _hub_want(c, mapping)
        if html[c.start: c.end] == _hub_card_html(c, want):
            continue
        if want and not c.decked:
            findings.append(f"{HUB}: the card for {c.name!r} ({c.slug}) has no deck; it is published")
        elif want:
            findings.append(f"{HUB}: the card for {c.name!r} ({c.slug}) has the wrong deck markup for "
                            "its published id")
        else:
            findings.append(f"{HUB}: the card for {c.name!r} ({c.slug}) carries a deck, but the topic is "
                            "not published")
    if _hub_stray(html, cards):
        findings.append(f"{HUB}: {HUB_DECK_ATTR} appears outside a decked card")
    outside = "\n".join(ln for ln in html.splitlines() if HUB_DECK_ATTR not in ln)
    if SLIDES_LINK in outside:
        findings.append(f"{HUB}: a {SLIDES_LINK} link sits outside a decked card's strip lines")
    return findings


def hub_plan(mapping: dict) -> tuple[dict[Path, str], list[str]]:
    """The new text of topics.html when --stamp would change it, or the
    reason it cannot be stamped. Nothing is written."""
    path = bbd.ROOT / HUB
    try:
        html = path.read_text(encoding="utf-8")
        new = stamp_hub(html, mapping)
    except (OSError, ValueError) as e:
        return {}, [str(e) if isinstance(e, ValueError) else f"{HUB}: {e}"]
    return ({path: new} if new != html else {}), []


def hub_check(mapping: dict) -> list[str]:
    try:
        return hub_findings((bbd.ROOT / HUB).read_text(encoding="utf-8"), mapping)
    except OSError as e:
        return [f"{HUB}: {e}"]


# ---------------------------------------------------------------------------
# The page gate: what a deck may say, section by section.
# ---------------------------------------------------------------------------


@dataclass
class _Scope:
    numbers: set[str]
    techniques: set[str]
    links: set[str]


def _scope(page: TopicPage, ids) -> _Scope:
    secs = [page.sections[i] for i in ids]
    return _Scope(
        set().union(*(s.numbers for s in secs)),
        set().union(*(s.techniques for s in secs)),
        set().union(*(s.links for s in secs)),
    )


def _slide_findings(s: bbd.BSlide, page: TopicPage) -> list[str]:
    if not s.section:
        return [f"{s.where}: slide has no section: line; cite the ids of the sections it draws on"]
    out = [
        f"{s.where}: section {i!r} is not a section on {page.path}" for i in s.section if i not in page.sections
    ]
    known = [i for i in dict.fromkeys(s.section) if i in page.sections]
    if known:
        scope = _scope(page, known)
        on = f"in section{'s' if len(known) > 1 else ''} {', '.join(known)}"
        out += bbd._text_findings(s.where, bbd._slide_text_fields(s), scope, on=on)
        urls = [row[1] for row in s.items.get("link", [])] + ([s.source[1]] if s.source else [])
        for url in urls:
            if bbd.normalize_url(url) not in scope.links:
                out.append(f"{s.where}: link {url} is not linked from {on[3:]}")
    if s.layout == "figure" and s.figure:
        fig = page.figures.get(s.figure)
        if fig is None:
            out.append(
                f"{s.where}: figure {s.figure!r} is not a figure on {page.path}; "
                f"its figures are: {', '.join(page.figures) or 'none'}"
            )
        elif fig.section not in s.section:
            out.append(f"{s.where}: figure {s.figure} is in section {fig.section}, which this slide does not cite")
    return out


NEED_DISCLOSURE = "\"(disclosure: the site's author works at Wiz)\""


def _names_wiz(texts: list[str]) -> bool:
    return any(WIZ_RE.search(t) for t in texts)


def _discloses(texts: list[str]) -> bool:
    return any(DISCLOSURE_RE.search(t) for t in texts)


def _wiz_findings(deck: bbd.BDeck, page: TopicPage) -> list[str]:
    """On a page that carries the Wiz disclosure, two checks that do not
    depend on each other. The first place the audience sees Wiz named (the
    cover's title or promise, else the first slide whose own text names it)
    carries the disclosure there; notes are not shown, so they never satisfy
    it. And notes that name Wiz before any slide shows it carry it too, for
    the presenter who reads them out."""
    if not DISCLOSURE_RE.search(page.text):
        return []
    out: list[str] = []
    shown_yet = _names_wiz([deck.title, deck.promise])
    if shown_yet and not _discloses([deck.title, deck.promise]):
        out.append(f"{deck.slug}.deck: title or promise names Wiz first, so the title or the promise carries "
                   f"{NEED_DISCLOSURE}, as {page.path} does")
    notes_done = shown_yet
    for s in deck.slides:
        if shown_yet and notes_done:
            break
        shown = bbd._slide_text_fields(s, notes=False) + ([s.source[0]] if s.source else [])
        if not shown_yet and _names_wiz(shown):
            shown_yet = notes_done = True
            if not _discloses(shown):
                out.append(f"{s.where}: the first slide to show Wiz carries {NEED_DISCLOSURE} on the "
                           f"slide, as {page.path} does; the notes do not count")
        elif not notes_done and _names_wiz(s.notes):
            notes_done = True
            if not _discloses(s.notes):
                out.append(f"{s.where}: these notes name Wiz before any slide shows it, so they carry "
                           f"{NEED_DISCLOSURE}")
    return out


def topic_page_findings(deck: bbd.BDeck, html: str, today: date | None = None,
                        pages: list[str] | None = None) -> list[str]:
    """Every way the deck says something its cited sections do not, or
    breaks a topic deck rule: a page that is not a topic page, a section or
    figure that is not on the page, a figure outside the slide's sections or
    shown twice, no figure slide on a page with diagrams, and the Wiz
    disclosure. Raises OutlineError when the page cannot be read."""
    where = f"{deck.slug}.deck"
    pages = topic_pages() if pages is None else pages
    if deck.page not in pages:
        if deck.page in EXCLUDED:
            return [f"{where}: page {deck.page} gets no deck; it is in EXCLUDED in build_topic_decks.py"]
        return [f"{where}: page {deck.page} is not a card on topics.html, so it is not a topic page"]
    page = parse_topic_page(html, deck.page)
    out: list[str] = []
    if date.fromisoformat(deck.as_of) > (today or date.today()):
        out.append(f"{where}: as-of {deck.as_of} is in the future")
    # The generated cover shows the title and promise; they may draw on the
    # whole page.
    whole = _scope(page, page.sections)
    out += bbd._text_findings(f"{where}: title", [deck.title], whole)
    out += bbd._text_findings(f"{where}: promise", [deck.promise], whole)
    shown: dict[str, str] = {}
    for s in deck.slides:
        out += _slide_findings(s, page)
        if s.layout == "figure" and s.figure:
            if s.figure in shown:
                out.append(f"{s.where}: figure {s.figure} is already on the slide at {shown[s.figure]}; "
                           "a deck shows each figure once")
            else:
                shown[s.figure] = s.where
    if page.figures and not any(s.layout == "figure" for s in deck.slides):
        n = len(page.figures)
        out.append(f"{where}: {deck.page} has {n} diagram figure{'s' if n != 1 else ''} and the deck "
                   "has no figure slide; give one of them a figure slide")
    return out + _wiz_findings(deck, page)


# ---------------------------------------------------------------------------
# What --record writes about the page, and how --stale reads it.
# ---------------------------------------------------------------------------


def _page_state(deck: bbd.BDeck, html: str) -> dict:
    hashes = section_hashes(html)
    cited = sorted({i for s in deck.slides for i in (s.section or []) if i in hashes})
    return {
        "page_sha256": topic_page_sha256(html),
        "cover_sha256": cover_sha256(deck.slug, html),
        "sections": {i: hashes[i] for i in cited},
    }


def _page_changes(deck: bbd.BDeck, entry: dict, html: str) -> list[str]:
    """Whether the cover's art changed, and which cited sections changed or
    went, since --record. A change anywhere else on the page leaves the
    deck as it is."""
    when = entry.get("published")
    out = []
    if entry.get("cover_sha256") != cover_sha256(deck.slug, html):
        out.append(f"cover art changed since it was published on {when}; the public deck shows "
                   "the old picture and needs re-publishing")
    recorded = entry.get("sections")
    if not isinstance(recorded, dict) or not recorded:
        return out + ["its mapping entry records no sections, so whether the page changed is unknown"]
    if entry.get("page_sha256") == topic_page_sha256(html):
        return out
    hashes = section_hashes(html)
    changed = [i for i in recorded if i in hashes and hashes[i] != recorded[i]]
    gone = [i for i in recorded if i not in hashes]
    if changed:
        out.append(f"sections changed since it was published on {when}: {', '.join(changed)}; "
                   "review the slides that cite them")
    if gone:
        out.append(f"sections no longer on the page: {', '.join(gone)}; "
                   "the slides that cite them need another section")
    return out


TOPIC = bbd.DeckKind(
    name="topic",
    outline_dir=Path("tools") / "decks" / "topics",
    mapping_path=Path("tools") / "decks" / "topics" / "published.json",
    deck_attr=TOPIC_DECK_ATTR,
    deck_line_tags=TOPIC_DECK_TAGS,
    deck_line_extra=preview_line_html,
    header_keys=("title", "page", "as-of", "promise"),
    page_re=TOPIC_PAGE_RE,
    layouts=frozenset({
        "text", "stats", "checklist", "list", "links", "layers", "timeline", "compare", "table", "bars",
        "matrix", "question", "answer", "figure",
    }),
    control_keys=frozenset({"layout", "section", "figure", "source", "credit"}),
    min_slides=15,
    max_slides=30,
    max_notes_words=300,
    pictures=True,
    insert_deck_line=insert_deck_line,
    page_findings=topic_page_findings,
    page_dir=Path("."),
    pages=topic_page_paths,
    renderer="topic_deck_render",
    deck_line_class="page-meta",
    deck_line_place="right after the page-meta line at the top of <main>",
    entry_keys=("id", "outline_sha256", "page_sha256", "cover_sha256", "sections", "published"),
    page_state=_page_state,
    page_changes=_page_changes,
    extra_plan=hub_plan,
    extra_findings=hub_check,
)


# ---------------------------------------------------------------------------
# Self-test. Every case takes a scratch directory and asserts.
# ---------------------------------------------------------------------------

PAGE_PATH = "kube.html"
PAGES = [PAGE_PATH]
ID_A = "1" + "A" * 43
ID_B = "1" + "B" * 43
DISCLOSURE = "(disclosure: the site's author works at Wiz)"
META_LINE = (
    '        <p class="page-meta"><time datetime="2026-10-18">Last updated <strong>2026-10-18</strong>'
    '</time> · <a href="about-shawn-nunley.html" rel="author">By Shawn Nunley</a></p>'
)
HERO = (
    '<div class="hero-illustration" aria-hidden="true"><svg viewBox="0 0 600 480" '
    'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Illustration of a cluster" '
    'width="600" height="480"><rect x="10" y="10" width="200" height="100" fill="#38bdf8"/></svg></div>'
)
SUPPLY_FIGURE = """        <figure class="diagram-figure" id="cluster-supply-chain">
          <svg viewBox="0 0 640 262" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="cluster-supply-chain-title cluster-supply-chain-desc" width="640" height="262">
            <title id="cluster-supply-chain-title">What else runs in the cluster</title>
            <desc id="cluster-supply-chain-desc">Five numbered checks, from 1 to 5.</desc>
            <rect x="0" y="0" width="120" height="40" fill="#0369a1"/>
            <text x="10" y="20">Sign images</text>
          </svg>
          <figcaption>The cluster runs more than your code.</figcaption>
        </figure>
"""
COMPARE_FIGURE = """            <figure class="cnapp-figure">
              <svg viewBox="0 0 400 200" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="cmp-title cmp-desc">
                <title id="cmp-title">Three managed control planes</title>
                <desc id="cmp-desc">EKS, AKS and GKE each host the control plane.</desc>
                <rect x="0" y="0" width="80" height="80" fill="#4338ca"/>
              </svg>
              <figcaption>Each provider runs the control plane for you.</figcaption>
            </figure>
"""
# A topic page in the real markup: an illustrated hero outside <main>; in
# <main> the page-meta line, a preamble, the table of contents with its
# page finder, sections wrapping their h2s, a figure after a section's close
# (it belongs to the h2 above it), a figure keyed by its <title> id, and an
# h2 in a section with no id.
PAGE = f"""<html><head><title>Kubernetes | CSOH</title></head><body>
<header><nav>Nav 999</nav></header>
<section class="hero hero--illustrated"><div class="hero-inner"><div class="hero-text">
<h1>Kubernetes &amp; Managed Kubernetes</h1><p>Lead text 77.</p></div>
{HERO}
</div></section>
<main class="container contribute-article" id="main-content">

{META_LINE}

        <div class="info-box--blue">
            <p><strong>The 30-second version:</strong> A cluster has 3 planes of control.</p>
        </div>

        <div class="toc">
            <h2>On this page</h2>
            <!-- page-finder -->
            <div class="page-finder" role="search"><div class="search-wrapper"><input type="search"></div></div>
            <!-- /page-finder -->
            <ol><li><a href="#what-is">What it is</a></li></ol>
        </div>

        <section id="what-is">
            <h2>What Kubernetes actually is</h2>
            <p>The control plane has 4 parts. Read <a href="https://kubernetes.io/docs/concepts/" target="_blank">the concepts</a> and the <a class="glossary-link" href="glossary.html#term-etcd">etcd</a> notes.</p>
            <ul>
                <li>Worker nodes run 12 pods each</li>
                <li>Pods share a kernel</li>
            </ul>
        </section>

        <section id="why-cloud">
            <h2>Why it runs the cloud</h2>
            <p>Wiz, Snyk, and Datadog all publish reports {DISCLOSURE}. The landscape lists about 1,500 projects.</p>
            <h3>Density</h3>
            <table><tr><th>Mode</th><th>Nodes</th></tr><tr><td>Standard</td><td>50</td></tr></table>
        </section>

        <section id="supply-chain">
            <h2>Supply chain</h2>
            <p>Five checks apply.</p>
        </section>

{SUPPLY_FIGURE}
        <section id="comparison">
            <h2>EKS, AKS, and GKE side by side</h2>
{COMPARE_FIGURE}        </section>

        <section class="cta-section">
            <h2>Where next</h2>
            <p>Read <a href="iam.html">the IAM page</a>.</p>
        </section>
</main>
<footer>Footer 888</footer></body></html>
"""

EXTRACT = """# Kubernetes & Managed Kubernetes {#top}
The 30-second version: A cluster has 3 planes of control.

## What Kubernetes actually is {#what-is}
The control plane has 4 parts. Read the concepts (https://kubernetes.io/docs/concepts/) and the etcd notes.
- Worker nodes run 12 pods each
- Pods share a kernel

## Why it runs the cloud {#why-cloud}
Wiz, Snyk, and Datadog all publish reports (disclosure: the site's author works at Wiz). The landscape lists about 1,500 projects.
### Density
| Mode | Nodes |
| Standard | 50 |

## Supply chain {#supply-chain}
Five checks apply.
[figure #cluster-supply-chain] What else runs in the cluster: Five numbered checks, from 1 to 5. (caption: The cluster runs more than your code.)

## EKS, AKS, and GKE side by side {#comparison}
[figure #cmp-title] Three managed control planes: EKS, AKS and GKE each host the control plane. (caption: Each provider runs the control plane for you.)

## Where next {#where-next}
Read the IAM page (iam.html).
"""

THEADER = "title: Kubernetes\npage: kube.html\nas-of: 2026-11-20\npromise: What a managed cluster runs.\n\n"


def _tslide(*lines: str, notes: str = "Notes.", heading: str = "S") -> str:
    return f"== {heading}\n" + "\n".join(lines) + f"\nnotes:\n{notes}\n\n"


def _tparse(body: str, name: str = "d.deck"):
    return bbd.parse_outline_text(THEADER + body, name, TOPIC)


def _tgate(*lines: str, notes: str = "Notes.", html: str = PAGE) -> list[str]:
    """The page gate's findings for one slide, leaving out deck-level ones
    (a one-slide deck has no figure slide, for one)."""
    deck = _tparse(_tslide(*lines, notes=notes))
    where = deck.slides[0].where
    return [f for f in topic_page_findings(deck, html, pages=PAGES) if f.startswith(where + ":")]


def _only(findings: list[str], *needles: str) -> None:
    assert len(findings) == 1 and all(n in findings[0] for n in needles), (needles, findings)


def _clean_outline(slug: str = "kube", page: str = "kube.html") -> str:
    """An outline with no findings against PAGE: 12 slides, so 15 with the
    generated three, and the figure slide the page's diagrams require."""
    cites = ["what-is", "why-cloud", "what-is | why-cloud"] * 4
    slides = "".join(
        _tslide(f"section: {c}", "Text.", heading=f"Slide {chr(97 + i)}", notes="Say it.")
        for i, c in enumerate(cites[:11])
    )
    slides += _tslide("layout: figure", "section: supply-chain", "figure: cluster-supply-chain",
                      heading="The supply chain", notes="Say it.")
    return f"title: Kubernetes\npage: {page}\nas-of: 2026-11-01\npromise: What a managed cluster runs.\n\n" + slides


HUB_IND = " " * 16


def _plain_card(href: str, title: str, text: str = "About it.") -> str:
    """A card as topics.html writes it: the link, then the card, then the
    picture, h3 and p at the card's inner indent."""
    i = HUB_IND
    return (
        f'{i}<a href="{href}" class="card-link">\n'
        f'{i}    <div class="resource-card">\n'
        f'{i}        <picture><img src="img/thumbs/x.jpg" alt="X graphic" width="1440" height="960"></picture>\n'
        f'{i}        <h3>{title}</h3>\n'
        f'{i}        <p>{text}</p>\n'
        f'{i}    </div>\n'
        f'{i}</a>\n'
    )


def _hub(*cards: str) -> str:
    return '<main>\n            <div class="resource-grid">\n' + "".join(cards) + "            </div>\n</main>\n"


def _decked_card(href: str, title: str, pres_id: str, text: str = "About it.") -> str:
    i = HUB_IND
    base = f"https://docs.google.com/presentation/d/{pres_id}"
    ext = 'target="_blank" rel="noopener noreferrer"'
    return (
        f'{i}<div class="resource-card resource-card--topic-deck">\n'
        f'{i}    <a href="{href}" class="card-link">\n'
        f'{i}        <picture><img src="img/thumbs/x.jpg" alt="X graphic" width="1440" height="960"></picture>\n'
        f'{i}        <h3>{title}</h3>\n'
        f'{i}        <p>{text}</p>\n'
        f'{i}    </a>\n'
        f'{i}    <p class="deck-actions" data-topic-hub-deck><strong>Slides:</strong> '
        f'<a href="{base}/export/pdf" {ext}>PDF</a> <a href="{base}/copy" {ext}>Editable copy</a></p>\n'
        f'{i}    <details class="deck-preview" data-topic-hub-deck><summary>Preview the slides</summary>'
        f'<div class="deck-frame"><iframe src="{base}/embed" title="Preview of the {title} slides" '
        'loading="lazy" allowfullscreen></iframe></div></details>\n'
        f'{i}</div>\n'
    )


def _topic_tree(root: Path, outlines: dict[str, str], pages: dict[str, str], mapping: dict | None = None,
                cards: tuple[str, ...] | None = None) -> Path:
    """A scratch repository: topics.html carding the given pages (or
    `cards`), the pages at the root, outlines in tools/decks/topics/, and
    published.json when mapping is given."""
    decks = root / "tools" / "decks" / "topics"
    decks.mkdir(parents=True)
    hrefs = cards if cards is not None else tuple(pages)
    (root / "topics.html").write_text(
        "<main>\n" + "".join(_plain_card(h, h) for h in hrefs) + "</main>\n",
        encoding="utf-8",
    )
    for name, html in pages.items():
        (root / name).write_text(html, encoding="utf-8")
    for slug, text in outlines.items():
        (decks / f"{slug}.deck").write_text(text, encoding="utf-8")
    if mapping is not None:
        (decks / "published.json").write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root


def _case_figure_keyed_by_title_id(tmp: Path) -> None:
    figs = figures(PAGE)
    assert list(figs) == ["cluster-supply-chain", "cmp-title"], list(figs)
    cmp = figs["cmp-title"]
    assert (cmp.id, cmp.section, cmp.title) == ("cmp-title", "comparison", "Three managed control planes"), cmp
    assert cmp.desc == "EKS, AKS and GKE each host the control plane." and cmp.caption.startswith("Each provider")
    # A figure after its section's </section> belongs to the h2 above it.
    assert figs["cluster-supply-chain"].section == "supply-chain", figs["cluster-supply-chain"]
    # Control: a figure with an id is keyed by it, not by its title's id.
    assert "cluster-supply-chain-title" not in figs
    assert len(cmp.svg_sha256) == 64 and cmp.svg_sha256 != figs["cluster-supply-chain"].svg_sha256
    assert has_hero(PAGE) and not has_hero(_plant(PAGE, HERO, ""))


def _case_section_unknown(tmp: Path) -> None:
    deck = _tparse(_tslide("section: what-is | nope", "Text."))
    f = [x for x in topic_page_findings(deck, PAGE, pages=PAGES) if "nope" in x]
    _only(f, "'nope'", "kube.html")
    assert f[0].startswith(deck.slides[0].where + ":"), f
    assert _tgate("section: what-is", "Text.") == []
    _only(_tgate("Text."), "section:")


def _case_number_outside_section(tmp: Path) -> None:
    assert _tgate("section: what-is", "- 12 pods on each node.") == []
    _only(_tgate("section: what-is", "- 50 nodes in Standard."), "number 50", "section what-is")
    # Control: citing the section that carries it clears the finding.
    assert _tgate("section: what-is | why-cloud", "- 50 nodes, 12 pods.") == []
    _only(_tgate("section: what-is", "Text.", notes="About 1,500 projects."), "1,500")
    # The figure's description is its section's text; its SVG labels are not.
    assert _tgate("section: supply-chain", "Checks 1 to 5.") == []
    # A number from outside <main> (the hero's lead) is on no section.
    _only(_tgate("section: top", "- 77 of them."), "number 77")


def _case_link_outside_section(tmp: Path) -> None:
    ok = ("section: where-next", "layout: links", "link: The IAM page | iam.html")
    assert _tgate(*ok) == []
    _only(_tgate("section: what-is", "layout: links", "link: The IAM page | iam.html"), "iam.html", "what-is")
    assert _tgate("section: what-is", "layout: links",
                  "link: Concepts | https://kubernetes.io/docs/concepts") == []


def _case_wiz_disclosure(tmp: Path) -> None:
    def wiz(deck, html=PAGE) -> list[str]:
        return [f for f in topic_page_findings(deck, html, pages=PAGES) if "Wiz" in f]

    plain = _tslide("section: why-cloud", "Wiz, Snyk, and Datadog publish reports.")
    later = _tslide("section: why-cloud", f"Wiz again {DISCLOSURE}.")
    deck = _tparse(plain + later)
    f = wiz(deck)
    _only(f, "disclosure")
    assert f[0].startswith(deck.slides[0].where + ":"), f
    # Control: the same deck against a page without the disclosure is clean.
    bare = _plant(PAGE, f" {DISCLOSURE}", "")
    assert wiz(deck, bare) == [], wiz(deck, bare)
    # The first slide to name Wiz carries it: clean.
    assert wiz(_tparse(later + plain)) == []
    # Named on the slide but disclosed only in its notes is a finding.
    f = wiz(_tparse(_tslide("section: why-cloud", "Wiz publishes reports.", notes=f"Note {DISCLOSURE}.")))
    _only(f, "disclosure")
    # Named only in the notes, and disclosed there: clean.
    noted = _tslide("section: why-cloud", "Vendors publish reports.", notes=f"Wiz is one {DISCLOSURE}.")
    assert wiz(_tparse(noted)) == []
    # Notes that name Wiz earlier do not excuse the first slide that shows
    # it: the audience sees that slide, not the notes.
    deck = _tparse(noted + plain)
    f = wiz(deck)
    _only(f, "first slide to show Wiz", "notes do not count")
    assert f[0].startswith(deck.slides[1].where + ":"), f
    # Control: the same deck with the shown slide disclosed is clean.
    assert wiz(_tparse(noted + later)) == []
    # Notes that name Wiz before any slide shows it carry it too.
    bare_notes = _tslide("section: why-cloud", "Vendors publish reports.", notes="Wiz is one.")
    deck = _tparse(bare_notes + later)
    f = wiz(deck)
    _only(f, "notes name Wiz before any slide shows it")
    assert f[0].startswith(deck.slides[0].where + ":"), f
    # Control: notes naming Wiz after a slide has shown it need nothing.
    assert wiz(_tparse(later + bare_notes)) == []
    # A word that contains the name is not a mention.
    assert wiz(_tparse(_tslide("section: why-cloud", "A setup wizard."))) == []
    # The cover counts: a promise naming Wiz needs it there.
    cover = bbd.parse_outline_text(THEADER.replace("What a managed", "Wiz on what a managed") + plain, "d.deck", TOPIC)
    f = wiz(cover)
    assert len(f) == 1 and f[0].startswith("d.deck: title or promise") and "title or the promise carries" in f[0], f
    # The disclosure may sit in either the title or the promise.
    wiz_header = THEADER.replace("What a managed", "Wiz on what a managed")
    for line in ("title: Kubernetes", "promise: Wiz on what a managed cluster runs."):
        disclosed = _plant(wiz_header, line, f"{line} {DISCLOSURE}")
        assert wiz(bbd.parse_outline_text(disclosed + plain, "d.deck", TOPIC)) == [], line


def _case_section_cap(tmp: Path) -> None:
    """A slide cites one or two sections. Three or more is a parse error
    naming the section: line, so a drafter cannot clear a number finding by
    citing most of the page."""
    assert _tparse(_tslide("section: what-is | why-cloud", "Text.")).slides[0].section == ["what-is", "why-cloud"]
    for ids in ("what-is | why-cloud | top",
                "what-is | why-cloud | supply-chain | comparison | where-next | top"):
        # THEADER is five lines, so the slide opens on line 6 and section: is line 7.
        e = _raises(lambda ids=ids: _tparse(_tslide(f"section: {ids}", "Text.")), "one or two")
        assert str(e).startswith("d.deck:7:"), e


def _case_layout_not_allowed(tmp: Path) -> None:
    for layout in ("stage", "stage-group", "flow", "background"):
        _raises(lambda layout=layout: _tparse(_tslide("section: what-is", f"layout: {layout}", "Text.")),
                f"unknown layout '{layout}'")
    _raises(lambda: _tparse(_tslide("section: what-is", "stage: 01", "Text.")), "unknown line key 'stage'")
    # Control: the topic layouts parse, and a breach outline cannot use figure.
    assert _tparse(_tslide("section: what-is", "layout: figure", "figure: x")).slides[0].layout == "figure"
    assert _tparse(_tslide("section: what-is", "layout: list", "item: a", "item: b")).slides[0].layout == "list"
    _raises(lambda: bbd.parse_outline_text(
        bbd.HEADER + "== S\nlayout: list\nitem: a\nitem: b\nnotes:\nN.\n", "d.deck"), "unknown layout 'list'")
    _raises(lambda: bbd.parse_outline_text(
        bbd.HEADER + "== S\nlayout: figure\nnotes:\nN.\n", "d.deck"), "unknown layout 'figure'")
    _raises(lambda: bbd.parse_outline_text(
        bbd.HEADER + "== S\nsection: x\nText.\nnotes:\nN.\n", "d.deck"), "unknown line key 'section'")


def _case_page_not_a_topic(tmp: Path) -> None:
    outlines = {s: _clean_outline(s, f"{s}.html") for s in ("kube", "glossary", "about")}
    pages = {"kube.html": PAGE, "glossary.html": PAGE, "about.html": PAGE}
    _topic_tree(tmp, outlines, pages, {}, cards=("kube.html", "glossary.html", "faq.html"))
    # Attribute order on a card does not matter.
    (tmp / "topics.html").write_text(
        (tmp / "topics.html").read_text(encoding="utf-8").replace(
            '<a href="kube.html" class="card-link">', '<a class="card-link" href="kube.html">'),
        encoding="utf-8")
    with _rooted(tmp):
        assert topic_pages() == ["kube.html"], topic_pages()
        decks = tmp / "tools" / "decks" / "topics"
        f = bbd.outline_findings(decks / "glossary.deck", TOPIC)
        assert any("glossary.html" in x and "gets no deck" in x for x in f), f
        f = bbd.outline_findings(decks / "about.deck", TOPIC)
        assert any("about.html" in x and "not a card on topics.html" in x for x in f), f
        assert bbd.outline_findings(decks / "kube.deck", TOPIC) == []


def _case_figure_unknown(tmp: Path) -> None:
    _only(_tgate("layout: figure", "section: supply-chain", "figure: nope"), "'nope'", "not a figure")
    bare = _tparse(_tslide("layout: figure", "section: supply-chain")).slides[0]
    _only(bbd.slide_findings(bare, TOPIC), "needs a figure: line")
    _raises(lambda: _tparse(_tslide("section: what-is", "figure: cmp-title", "Text.")),
            "does not take a figure: line")


def _case_figure_outside_section(tmp: Path) -> None:
    _only(_tgate("layout: figure", "section: what-is", "figure: cluster-supply-chain"),
          "cluster-supply-chain", "section supply-chain")
    assert _tgate("layout: figure", "section: supply-chain", "figure: cluster-supply-chain") == []
    assert _tgate("layout: figure", "section: comparison", "figure: cmp-title") == []


def _case_figure_twice(tmp: Path) -> None:
    fig = ("layout: figure", "section: supply-chain", "figure: cluster-supply-chain")
    deck = _tparse(_tslide(*fig) + _tslide(*fig))
    f = [x for x in topic_page_findings(deck, PAGE, pages=PAGES) if "once" in x]
    _only(f, "cluster-supply-chain")
    assert f[0].startswith(deck.slides[1].where + ":"), f
    other = _tparse(_tslide(*fig) + _tslide("layout: figure", "section: comparison", "figure: cmp-title"))
    assert [x for x in topic_page_findings(other, PAGE, pages=PAGES) if "once" in x] == []


def _case_figure_required(tmp: Path) -> None:
    deck = _tparse(_tslide("section: what-is", "Text."))
    f = [x for x in topic_page_findings(deck, PAGE, pages=PAGES) if "figure slide" in x]
    _only(f, "2 diagram figures")
    assert f[0].startswith("d.deck:"), f
    no_figs = _plant(_plant(PAGE, SUPPLY_FIGURE, ""), COMPARE_FIGURE, "")
    assert [x for x in topic_page_findings(deck, no_figs, pages=PAGES) if "figure slide" in x] == []
    with_fig = _tparse(_tslide("layout: figure", "section: comparison", "figure: cmp-title"))
    assert [x for x in topic_page_findings(with_fig, PAGE, pages=PAGES) if "figure slide" in x] == []


def _case_figure_prose_limit(tmp: Path) -> None:
    def style(*lines: str) -> list[str]:
        return [f for s in _tparse(_tslide(*lines)).slides for f in bbd.slide_findings(s, TOPIC)]

    fig = ("layout: figure", "section: supply-chain", "figure: cluster-supply-chain")
    assert style(*fig, " ".join(["word"] * 25)) == []
    _only(style(*fig, " ".join(["word"] * 26)), "26 words of prose; the limit is 25")
    # Control: a text slide keeps the 40-word limit.
    assert style("section: what-is", " ".join(["word"] * 26)) == []
    # Notes may run to 300 words on a topic deck.
    deck =_tparse(_tslide("section: what-is", "Text.", notes=" ".join(["n"] * 300)))
    assert bbd.slide_findings(deck.slides[0], TOPIC) == []
    deck = _tparse(_tslide("section: what-is", "Text.", notes=" ".join(["n"] * 301)))
    _only(bbd.slide_findings(deck.slides[0], TOPIC), "notes are 301 words; the limit is 300")


def _extract_tree(tmp: Path) -> Path:
    return _topic_tree(tmp, {}, {"kube.html": PAGE})


def _case_extract_format(tmp: Path) -> None:
    _extract_tree(tmp)
    with _rooted(tmp):
        got = extract("kube")
    assert got == EXTRACT, "\n" + got


def _case_extract_drops_glossary_links(tmp: Path) -> None:
    _extract_tree(tmp)
    with _rooted(tmp):
        got = extract("kube")
    want = "The control plane has 4 parts. Read the concepts (https://kubernetes.io/docs/concepts/) and the etcd notes."
    assert want + "\n" in got, got
    assert "glossary.html" not in got, got
    # Control: a link that is not a glossary link keeps its URL.
    assert "Read the IAM page (iam.html)." in got, got


def _case_extract_lists_figures(tmp: Path) -> None:
    _extract_tree(tmp)
    with _rooted(tmp):
        got = extract("kube").splitlines()
    line = ("[figure #cluster-supply-chain] What else runs in the cluster: Five numbered checks, from 1 to 5. "
            "(caption: The cluster runs more than your code.)")
    assert line in got, got
    # Where it sits: after its section's prose, before the next h2.
    assert got.index("Five checks apply.") < got.index(line) < got.index("## EKS, AKS, and GKE side by side {#comparison}")
    assert any(x.startswith("[figure #cmp-title] Three managed control planes: ") for x in got), got
    # The SVG's own labels are not in the extract, and neither are the toc,
    # the page finder or the page-meta line.
    text = "\n".join(got)
    for gone in ("Sign images", "On this page", "What it is", "search", "Last updated", "Shawn"):
        assert gone not in text, gone


def _case_extract_sections_only(tmp: Path) -> None:
    _extract_tree(tmp)
    with _rooted(tmp):
        got = extract("kube", ["why-cloud"])
        assert extract("kube", ["why-cloud", "top"]) == extract("kube", ["top", "why-cloud"])
        try:
            extract("kube", ["nope"])
        except ValueError as e:
            assert "nope" in str(e) and "what-is" in str(e), e
        else:
            raise AssertionError("an unknown section id was accepted")
        try:
            extract("glossary")
        except ValueError as e:
            assert "glossary.html" in str(e), e
        else:
            raise AssertionError("a page that is not a topic page was extracted")
    heads = [ln for ln in EXTRACT.splitlines() if ln.startswith(("# ", "## "))]
    lines = got.splitlines()
    assert lines[: len(heads)] == heads, lines
    body = "\n".join(lines[len(heads):])
    assert "### Density" in body and "| Standard | 50 |" in body, body
    # Control: the other sections' text is left out.
    assert "12 pods" not in got and "Five checks apply." not in got and "3 planes" not in got, got


def _case_section_hash_scoped(tmp: Path) -> None:
    base = section_hashes(PAGE)
    assert list(base) == ["top", "what-is", "why-cloud", "supply-chain", "comparison", "where-next"], list(base)
    assert list(sections(PAGE)) == list(base)
    assert "12 pods" in sections(PAGE)["what-is"]

    def changed(html: str) -> set[str]:
        new = section_hashes(html)
        assert list(new) == list(base), list(new)
        return {k for k in base if new[k] != base[k]}

    assert changed(_plant(PAGE, "has 4 parts", "has 5 parts")) == {"what-is"}
    assert changed(_plant(PAGE, "https://kubernetes.io/docs/concepts/", "https://kubernetes.io/docs/home/")) == {"what-is"}
    assert changed(_plant(PAGE, "3 planes", "4 planes")) == {"top"}
    # Neither the page-meta date, a glossary link, a deck line nor the nav
    # changes any section.
    assert changed(_plant(PAGE, "2026-10-18</strong>", "2026-11-01</strong>")) == set()
    assert changed(_plant(PAGE, "Five checks apply.",
                          'Five <a class="glossary-link" href="glossary.html#term-check">checks</a> apply.')) == set()
    assert changed(bbd.stamp_page(PAGE, ID_A, TOPIC)) == set()
    assert changed(_plant(PAGE, "Nav 999", "Nav 123")) == set()


def _case_section_hash_sees_svg(tmp: Path) -> None:
    base, figs = section_hashes(PAGE), figures(PAGE)
    wider = _plant(PAGE, 'width="120"', 'width="130"')
    new = section_hashes(wider)
    assert {k for k in base if new[k] != base[k]} == {"supply-chain"}, new
    assert figures(wider)["cluster-supply-chain"].svg_sha256 != figs["cluster-supply-chain"].svg_sha256
    assert figures(wider)["cmp-title"] == figs["cmp-title"]
    recolour = _plant(PAGE, 'fill="#4338ca"', 'fill="#059669"')
    assert {k for k in base if section_hashes(recolour)[k] != base[k]} == {"comparison"}
    # Control: a glossary link wrapped round an SVG label changes nothing.
    linked = _plant(PAGE, ">Sign images<", '>Sign <a class="glossary-link" href="glossary.html#term-image">images</a><')
    assert section_hashes(linked) == base and figures(linked) == figs


def _case_stale_names_sections(tmp: Path) -> None:
    outline = (THEADER + _tslide("section: what-is", "Text.", heading="A")
               + _tslide("section: why-cloud", "Text.", heading="B"))
    _topic_tree(tmp, {"kube": outline}, {"kube.html": PAGE})
    with _rooted(tmp):
        deck = bbd.parse_outline(tmp / "tools/decks/topics/kube.deck", TOPIC)
        entry = {"id": ID_A, "outline_sha256": bbd.outline_sha256(deck),
                 **TOPIC.page_state(deck, PAGE), "published": "2026-01-02"}
        assert sorted(entry) == sorted(TOPIC.entry_keys), entry
        assert sorted(entry["sections"]) == ["what-is", "why-cloud"], entry
        bbd.save_mapping({"kube": entry}, TOPIC)

        def stale(html: str) -> list[str]:
            (tmp / "kube.html").write_text(html, encoding="utf-8")
            rc, out = _capture(bbd.stale_report, True, TOPIC)
            assert rc == 0, out
            return out.splitlines()

        assert stale(PAGE) == ["stale check: 0 of 1 published decks changed since publishing"]
        assert stale(_plant(PAGE, "has 4 parts", "has 5 parts")) == [
            "kube: sections changed since it was published on 2026-01-02: what-is; "
            "review the slides that cite them",
            "stale check: 1 of 1 published decks changed since publishing",
        ]
        # A section no slide cites, the page-meta date and the stamped deck
        # line do not make the deck stale.
        assert stale(_plant(PAGE, "Five checks apply.", "Six checks apply."))[0].startswith("stale check: 0 of 1")
        assert stale(_plant(PAGE, "2026-10-18</strong>", "2026-12-01</strong>"))[0].startswith("stale check: 0 of 1")
        assert stale(bbd.stamp_page(PAGE, ID_A, TOPIC))[0].startswith("stale check: 0 of 1")
        gone = stale(_plant(PAGE, '<section id="why-cloud">', '<section id="why-the-cloud">'))
        assert gone[0] == ("kube: sections no longer on the page: why-cloud; "
                           "the slides that cite them need another section"), gone


TILE_CARD = (
    '<a href="kube.html" class="card-link"><div class="resource-card"><picture>'
    '<img class="resource-preview" src="img/thumbs/kube.jpg" alt="Kube graphic" width="1440" height="960">'
    '</picture><h3>K</h3></div></a>\n'
)


def _case_stale_sees_cover(tmp: Path) -> None:
    """The cover's art sits outside <main>, where no section hash reaches:
    a redrawn hero, or on a page with none a changed topics.html tile,
    makes the deck stale."""
    outline = THEADER + _tslide("section: what-is", "Text.", heading="A")
    nohero = _plant(PAGE, HERO, "")
    _topic_tree(tmp, {"kube": outline}, {"kube.html": PAGE})
    (tmp / "img" / "thumbs").mkdir(parents=True)
    (tmp / "img" / "thumbs" / "kube.jpg").write_bytes(b"tile one")
    (tmp / "topics.html").write_text(TILE_CARD, encoding="utf-8")
    with _rooted(tmp):
        deck = bbd.parse_outline(tmp / "tools/decks/topics/kube.deck", TOPIC)

        def record(html: str) -> None:
            (tmp / "kube.html").write_text(html, encoding="utf-8")
            bbd.save_mapping({"kube": {"id": ID_A, "outline_sha256": bbd.outline_sha256(deck),
                                       **TOPIC.page_state(deck, html), "published": "2026-01-02"}}, TOPIC)

        def stale(html: str) -> list[str]:
            (tmp / "kube.html").write_text(html, encoding="utf-8")
            rc, out = _capture(bbd.stale_report, True, TOPIC)
            assert rc == 0, out
            return out.splitlines()

        record(PAGE)
        assert stale(PAGE) == ["stale check: 0 of 1 published decks changed since publishing"]
        redrawn = _plant(PAGE, 'width="200" height="100" fill="#38bdf8"', 'width="260" height="100" fill="#38bdf8"')
        assert stale(redrawn) == [
            "kube: cover art changed since it was published on 2026-01-02; the public deck shows "
            "the old picture and needs re-publishing",
            "stale check: 1 of 1 published decks changed since publishing",
        ]
        # On a page with no hero the cover shows the tile: its image and its
        # alt text both count, and the hero's absence is not a change.
        record(nohero)
        assert stale(nohero)[0].startswith("stale check: 0 of 1")
        (tmp / "img" / "thumbs" / "kube.jpg").write_bytes(b"tile two")
        assert stale(nohero)[0].startswith("kube: cover art changed")
        record(nohero)
        (tmp / "topics.html").write_text(TILE_CARD.replace("Kube graphic", "Cluster graphic"), encoding="utf-8")
        assert stale(nohero)[0].startswith("kube: cover art changed")


def _case_stamp_after_page_meta(tmp: Path) -> None:
    out = bbd.stamp_page(PAGE, ID_A, TOPIC)
    line = bbd.deck_line_html(ID_A, "        ", TOPIC)
    assert line.startswith('        <p class="page-meta" data-topic-deck><strong>Slides:</strong> '), line
    assert out == _plant(PAGE, META_LINE + "\n", META_LINE + "\n" + line + "\n"), out
    # The breach deck line's link text, behind the topic deck line's tag,
    # and under it one closed preview panel embedding the same deck.
    first, preview = line.split("\n")
    assert first.split(">", 1)[1] == bbd.deck_line_html(ID_A).split(">", 1)[1]
    assert preview.startswith('        <details class="deck-preview" data-topic-deck><summary>'), preview
    assert f'src="https://docs.google.com/presentation/d/{ID_A}/embed"' in preview and 'loading="lazy"' in preview
    assert " open" not in preview.split(">", 1)[0], "the preview must start closed"
    # A page-meta line at column 0 gets a deck line at column 0.
    flush = _plant(PAGE, META_LINE, META_LINE.lstrip())
    assert bbd.deck_line_html(ID_A, "", TOPIC) + "\n" in bbd.stamp_page(flush, ID_A, TOPIC)
    for bad in (_plant(PAGE, META_LINE + "\n", ""),
                _plant(_plant(PAGE, META_LINE + "\n", ""), "<header>", "<header>" + META_LINE.strip())):
        try:
            bbd.stamp_page(bad, ID_A, TOPIC)
        except ValueError as e:
            assert "page-meta" in str(e), e
        else:
            raise AssertionError("stamped a page with no page-meta line in <main>")
    # --check agrees with --stamp, and names a line that moved.
    mapping = {"kube": {"id": ID_A}}
    assert bbd.link_findings("kube", out, mapping, TOPIC) == []
    _only(bbd.link_findings("kube", PAGE, mapping, TOPIC), "kube.html", "no deck line")
    moved = _plant(_plant(out, line + "\n", ""), "        <div class=\"info-box--blue\">",
                   line + "\n        <div class=\"info-box--blue\">")
    _only(bbd.link_findings("kube", moved, mapping, TOPIC), "right after the page-meta line")
    _only(bbd.link_findings("kube", out, {}, TOPIC), "not in the mapping")
    # A deck line without its preview, a preview of another deck, or a second
    # preview is not what --stamp writes; a stray embed elsewhere is a link
    # outside the deck lines.
    _only(bbd.link_findings("kube", _plant(out, preview + "\n", ""), mapping, TOPIC), "not the one --stamp writes")
    _only(bbd.link_findings("kube", _plant(out, f"d/{ID_A}/embed", f"d/{ID_B}/embed"), mapping, TOPIC),
          "not the one --stamp writes")
    _only(bbd.link_findings("kube", _plant(out, preview + "\n", preview + "\n" + preview + "\n"), mapping, TOPIC),
          "it must have exactly 2")
    _only(bbd.link_findings("kube", _plant(out, first + "\n" + preview + "\n", preview + "\n" + first + "\n"),
                            mapping, TOPIC), "not the one --stamp writes")
    # Stray deck markup names the topic kind's own line shapes.
    broken = bbd.link_findings("kube", _plant(out, "</summary>", "</summary>\n"), mapping, TOPIC)
    assert any("(one <p> or <details> alone on its line" in f for f in broken), broken
    stray = _plant(out, "        <div class=\"info-box--blue\">",
                   f'        <p><iframe src="https://docs.google.com/presentation/d/{ID_A}/embed"></iframe></p>\n'
                   "        <div class=\"info-box--blue\">")
    _only(bbd.link_findings("kube", stray, mapping, TOPIC), "outside its deck line")


def _case_stamp_idempotent(tmp: Path) -> None:
    once = bbd.stamp_page(PAGE, ID_A, TOPIC)
    assert bbd.stamp_page(once, ID_A, TOPIC) == once
    assert bbd.stamp_page(once, None, TOPIC) == PAGE
    swapped = bbd.stamp_page(once, ID_B, TOPIC)
    assert swapped.count("data-topic-deck") == 2 and ID_B in swapped and ID_A not in swapped
    # A breach stamp leaves a topic deck line alone, and the reverse.
    assert bbd.stamp_page(once, None) == once
    breach_line = bbd.deck_line_html(ID_B)
    both = _plant(PAGE, "            <h2>Supply chain</h2>\n",
                  "            <h2>Supply chain</h2>\n" + breach_line + "\n")
    assert bbd.stamp_page(both, None, TOPIC) == both
    topic = bbd.stamp_page(both, ID_A, TOPIC)
    assert topic.count(breach_line + "\n") == 1 and topic.count("data-topic-deck") == 2, topic
    assert bbd.stamp_page(topic, None, TOPIC) == both


def _case_hub_stamp_decks_mapped_cards(tmp: Path) -> None:
    plain = _hub(_plain_card("kube.html", "Kubernetes"), _plain_card("serverless.html", "Serverless &amp; more"))
    out = stamp_hub(plain, {"kube": {"id": ID_A}})
    assert out == _hub(_decked_card("kube.html", "Kubernetes", ID_A), _plain_card("serverless.html", "Serverless &amp; more"))
    assert out.count(ID_A) == 3 and 'title="Preview of the Kubernetes slides"' in out, out
    assert "<details class=\"deck-preview\" data-topic-hub-deck><summary>" in out and " open" not in out
    # The h3 keeps its entities as written.
    both = stamp_hub(plain, {"kube": {"id": ID_A}, "serverless": {"id": ID_B}})
    assert 'title="Preview of the Serverless &amp; more slides"' in both, both
    # An entry with no well-formed id decks nothing.
    assert stamp_hub(plain, {"kube": {"id": "short"}}) == plain


def _case_hub_stamp_reverses_and_is_idempotent(tmp: Path) -> None:
    plain = _hub(_plain_card("kube.html", "Kubernetes"), _plain_card("serverless.html", "Serverless"))
    once = stamp_hub(plain, {"kube": {"id": ID_A}})
    assert stamp_hub(once, {"kube": {"id": ID_A}}) == once
    assert stamp_hub(once, {}) == plain
    swapped = stamp_hub(once, {"kube": {"id": ID_B}})
    assert swapped.count(ID_B) == 3 and ID_A not in swapped, swapped
    # A card with extra attributes on its link and box survives the round trip.
    odd = plain.replace('class="card-link">', 'class="card-link" data-x="1">', 1).replace(
        '<div class="resource-card">', '<div class="resource-card" data-y="2">', 1)
    assert stamp_hub(stamp_hub(odd, {"kube": {"id": ID_A}}), {}) == odd
    # The attribute outside a decked card is refused, and so is a card of neither form.
    stray = plain.replace("<main>", '<main>\n<p class="x" data-topic-hub-deck>x</p>', 1)
    broken = once.replace("</details>", "", 1)
    for html, mapping, needle in ((stray, {}, "data-topic-hub-deck"), (broken, {"kube": {"id": ID_A}}, "'kube'")):
        try:
            stamp_hub(html, mapping)
        except ValueError as e:
            assert needle in str(e), e
        else:
            raise AssertionError(f"stamp_hub accepted a hub with {needle}")


def _case_hub_findings(tmp: Path) -> None:
    plain = _hub(_plain_card("kube.html", "Kubernetes"), _plain_card("serverless.html", "Serverless"))
    mapping = {"kube": {"id": ID_A}}
    good = stamp_hub(plain, mapping)
    assert hub_findings(good, mapping) == [] and hub_findings(plain, {}) == []
    missing = hub_findings(plain, mapping)
    assert len(missing) == 1 and "topics.html" in missing[0] and "kube" in missing[0] and "no deck" in missing[0], missing
    wrong = hub_findings(good.replace(ID_A, ID_B, 1), mapping)
    assert len(wrong) == 1 and "kube" in wrong[0] and "wrong" in wrong[0], wrong
    extra = hub_findings(good, {"kube": {"id": ID_A}, "serverless": {"id": ID_B}})
    assert len(extra) == 1 and "serverless" in extra[0] and "no deck" in extra[0], extra
    unmapped = hub_findings(good, {})
    assert len(unmapped) == 1 and "kube" in unmapped[0] and "not published" in unmapped[0], unmapped
    bad = hub_findings(good.replace("Editable copy</a></p>\n", "Editable copy</a>\n", 1), mapping)
    assert len(bad) == 1 and "kube" in bad[0] and "malformed" in bad[0], bad
    link = f"https://docs.google.com/presentation/d/{ID_B}/copy"
    stray = hub_findings(good.replace("<h3>Serverless</h3>", f'<h3><a href="{link}">Serverless</a></h3>'), mapping)
    assert len(stray) == 1 and "docs.google.com/presentation" in stray[0], stray
    # Control: the strip's own links are not strays.
    assert hub_findings(good, mapping) == []


def _case_crosslink_skips_hub_deck_lines(tmp: Path) -> None:
    import crosslink_pages as cp

    key = "Slides"
    patterns, slugs = cp.build_term_regexes([key]), {key.lower(): "term-slides"}
    link = '<a class="glossary-link" href="glossary.html#term-slides">Slides</a>'
    hub = stamp_hub(_hub(_plain_card("kube.html", "Kubernetes")), {"kube": {"id": ID_A}})
    hub = hub.replace("</main>", "<p>Read the Slides first.</p>\n</main>")
    strip = next(ln for ln in hub.splitlines() if 'class="deck-actions"' in ln)
    assert "Slides" in strip, strip
    page = tmp / "x.html"
    old = cp.REPO_ROOT
    cp.REPO_ROOT = tmp
    try:
        page.write_text(hub.replace("Preview the slides", "Preview the Slides"), encoding="utf-8")
        cp.crosslink_page(page, patterns, slugs)
        once = page.read_text(encoding="utf-8")
        lines = once.splitlines()
        assert strip in lines and "Preview the Slides" in next(ln for ln in lines if "deck-preview" in ln), once
        assert not any(link in ln for ln in lines if "data-topic-hub-deck" in ln), once
        assert once.count(link) == 1 and link in next(ln for ln in lines if "Read the" in ln), once
        # Control: without its attribute the strip takes the link.
        page.write_text(hub.replace(" data-topic-hub-deck>", ">", 1), encoding="utf-8")
        cp.crosslink_page(page, patterns, slugs)
        assert link in next(ln for ln in page.read_text(encoding="utf-8").splitlines() if "deck-actions" in ln)
    finally:
        cp.REPO_ROOT = old


def _case_crosslink_skips_topic_deck_line(tmp: Path) -> None:
    import crosslink_pages as cp

    key = "Google account"
    patterns, slugs = cp.build_term_regexes([key]), {key.lower(): "term-google-account"}
    link = f'<a class="glossary-link" href="glossary.html#term-google-account">{key}</a>'
    line = bbd.deck_line_html(ID_A, "", TOPIC)
    assert key in line and "data-topic-deck" in line, line
    html = f"<html><body><main>\n{line}\n<p>Copying a deck needs a Google account of your own.</p>\n</main></body></html>\n"
    page = tmp / "x.html"
    old = cp.REPO_ROOT
    cp.REPO_ROOT = tmp
    try:
        page.write_text(html, encoding="utf-8")
        cp.crosslink_page(page, patterns, slugs)
        once = page.read_text(encoding="utf-8")
        assert line + "\n" in once and once.count(link) == 1 and link in once.split(line)[1], once
        cp.crosslink_page(page, patterns, slugs)
        assert page.read_text(encoding="utf-8") == once
        # The preview panel is a deck line too: a term in its summary takes no
        # link, while the same term in prose below does.
        pv_patterns, pv_slugs = cp.build_term_regexes(["slides"]), {"slides": "term-slides"}
        pv_link = '<a class="glossary-link" href="glossary.html#term-slides">slides</a>'
        page.write_text(f"<html><body><main>\n{line}\n<p>Read the slides first.</p>\n</main></body></html>\n",
                        encoding="utf-8")
        cp.crosslink_page(page, pv_patterns, pv_slugs)
        pv = page.read_text(encoding="utf-8")
        assert line + "\n" in pv and pv.count(pv_link) == 1 and pv_link in pv.split(line)[1], pv
        page.write_text(html, encoding="utf-8")
        # Control: without its deck attribute the line takes the link.
        page.write_text(_plant(html, " data-topic-deck>", ">"), encoding="utf-8")
        cp.crosslink_page(page, patterns, slugs)
        bare = page.read_text(encoding="utf-8")
        assert bare.count(link) == 1 and link in bare.split("</p>")[0], bare
    finally:
        cp.REPO_ROOT = old


def _case_record_writes_sections(tmp: Path) -> None:
    _topic_tree(tmp, {"kube": _clean_outline()}, {"kube.html": PAGE}, {})
    with _rooted(tmp):
        rc, out = _capture(bbd.record, "kube", ID_A, TOPIC)
        assert rc == 0, out
        rc, out = _capture(bbd.check_all, TOPIC)
        assert rc == 0 and "topic decks: 1 outlines checked, 1 topic pages checked, 0 findings" in out, out
    m = json.loads((tmp / "tools/decks/topics/published.json").read_text(encoding="utf-8"))["kube"]
    assert sorted(m) == sorted(TOPIC.entry_keys), m
    want = section_hashes(PAGE)
    assert m["sections"] == {k: want[k] for k in ("supply-chain", "what-is", "why-cloud")}, m
    stamped = (tmp / "kube.html").read_text(encoding="utf-8")
    assert stamped == bbd.stamp_page(PAGE, ID_A, TOPIC)
    assert section_hashes(stamped) == want


def _case_hub_wired_into_stamp_and_check(tmp: Path) -> None:
    _topic_tree(tmp, {"kube": _clean_outline()}, {"kube.html": PAGE}, {})
    hub, page, mpath = tmp / "topics.html", tmp / "kube.html", tmp / "tools/decks/topics/published.json"
    plain_hub = hub.read_text(encoding="utf-8")
    with _rooted(tmp):
        rc, out = _capture(bbd.record, "kube", ID_A, TOPIC)
        assert rc == 0, out
        decked = hub.read_text(encoding="utf-8")
        assert decked != plain_hub and decked == stamp_hub(plain_hub, {"kube": {"id": ID_A}}), decked
        # A hub out of step with the mapping fails --check, naming the hub.
        hub.write_text(_plant(decked, f"d/{ID_A}/embed", f"d/{ID_B}/embed"), encoding="utf-8")
        rc, out = _capture(bbd.check_all, TOPIC)
        assert rc == 1 and "topics.html" in out, out
        # With the mapping moved to a new id, a malformed hub stops --stamp
        # before it writes the hub or the page.
        m = json.loads(mpath.read_text(encoding="utf-8"))
        m["kube"]["id"] = ID_B
        mpath.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        page_before = page.read_text(encoding="utf-8")
        broken = _plant(decked, "<summary>Preview the slides</summary>", "<summary>Preview the slides</summary>\n")
        hub.write_text(broken, encoding="utf-8")
        rc, out = _capture(bbd.stamp_all, TOPIC)
        assert rc != 0, out
        assert page.read_text(encoding="utf-8") == page_before and hub.read_text(encoding="utf-8") == broken
        # Control: with the hub mended, the same --stamp moves both to the new id.
        hub.write_text(decked, encoding="utf-8")
        rc, out = _capture(bbd.stamp_all, TOPIC)
        assert rc == 0, out
        assert ID_B in page.read_text(encoding="utf-8") and ID_A not in page.read_text(encoding="utf-8")
        assert hub.read_text(encoding="utf-8") == stamp_hub(plain_hub, {"kube": {"id": ID_B}})


def _case_check_empty_tree(tmp: Path) -> None:
    _topic_tree(tmp, {}, {"kube.html": PAGE}, {})
    with _rooted(tmp):
        rc, out = _capture(bbd.check_all, TOPIC)
        assert rc == 1 and "no outlines found" in out and "nothing was checked" in out, out
        (tmp / "topics.html").write_text("<main></main>\n", encoding="utf-8")
        (tmp / "tools/decks/topics/kube.deck").write_text(_clean_outline(), encoding="utf-8")
        rc, out = _capture(bbd.check_all, TOPIC)
        assert rc == 1 and "no topic pages found" in out, out


def _page_invariants(name: str, html: str) -> None:
    """What holds for any page, whatever it says: it parses or raises
    OutlineError, every figure sits in a section it lists, the extract
    carries every section's heading line, and stamping either refuses with
    ValueError or gives the page back unchanged once unstamped, with every
    section hash as it was."""
    try:
        page = parse_topic_page(html, name)
    except OutlineError:
        return
    assert all(f.section in page.sections for f in page.figures.values()), name
    text = extract_text(html, name)
    assert all(s.lines[0] in text.splitlines() for s in page.sections.values()), name
    bare = bbd.stamp_page(html, None, TOPIC) if not bbd.loose_deck_markup(html, TOPIC) else html
    try:
        stamped = bbd.stamp_page(bare, ID_A, TOPIC)
    except ValueError:
        return
    assert bbd.stamp_page(stamped, None, TOPIC) == bare, name
    assert section_hashes(stamped) == section_hashes(bare), name


def _case_real_pages(tmp: Path) -> None:
    """The invariants on every real topic page. Nothing here reads what a
    page says, so an edit to a page cannot fail the self-test unless it
    meets a defect in this tool; whether a page suits a deck is --check's
    business, for the pages that have one."""
    pages = topic_pages()
    assert pages and not set(pages) & EXCLUDED, pages
    for name in pages:
        _page_invariants(name, (bbd.ROOT / name).read_text(encoding="utf-8"))
    # Control: pages that break the deck rules (a figure with no id, no
    # page-meta line, two sections with one id) pass the invariants.
    for broken in (
        _plant(PAGE, 'id="cmp-title"', ""),
        _plant(PAGE, META_LINE + "\n", ""),
        _plant(PAGE, '<section id="supply-chain">', '<section id="what-is">'),
    ):
        _page_invariants(PAGE_PATH, broken)


def _case_slug_from_plain_text(tmp: Path) -> None:
    """An h2 outside an id'd section takes a slug of its text, without the
    URL the extract shows after a link in it."""
    linked = _plant(PAGE, "<h2>Where next</h2>", '<h2>Where <a href="https://example.com/next">next</a></h2>')
    assert list(section_hashes(linked))[-1] == "where-next", list(section_hashes(linked))
    assert "## Where next (https://example.com/next) {#where-next}" in extract_text(linked, PAGE_PATH)


def _case_slide_count_bounds(tmp: Path) -> None:
    """15 to 30 slides, counting the three generated ones."""
    def count_findings(n: int) -> list[str]:
        body = "".join(_tslide("section: what-is", "Text.", heading=f"S{i}") for i in range(n))
        return [f for f in bbd.style_findings(_tparse(body), TOPIC) if "slides including" in f]

    for outline_slides, ok in ((11, False), (12, True), (27, True), (28, False)):
        f = count_findings(outline_slides)
        total = outline_slides + bbd.GENERATED_SLIDES
        assert (f == []) == ok, (total, f)
        if not ok:
            _only(f, f"{total} slides", "15 to 30")


CASES: list = [
    ("figure_keyed_by_title_id", _case_figure_keyed_by_title_id),
    ("section_unknown", _case_section_unknown),
    ("number_outside_section", _case_number_outside_section),
    ("link_outside_section", _case_link_outside_section),
    ("wiz_disclosure", _case_wiz_disclosure),
    ("section_cap", _case_section_cap),
    ("layout_not_allowed", _case_layout_not_allowed),
    ("page_not_a_topic", _case_page_not_a_topic),
    ("figure_unknown", _case_figure_unknown),
    ("figure_outside_section", _case_figure_outside_section),
    ("figure_twice", _case_figure_twice),
    ("figure_required", _case_figure_required),
    ("figure_prose_limit", _case_figure_prose_limit),
    ("extract_format", _case_extract_format),
    ("extract_drops_glossary_links", _case_extract_drops_glossary_links),
    ("extract_lists_figures", _case_extract_lists_figures),
    ("extract_sections_only", _case_extract_sections_only),
    ("section_hash_scoped", _case_section_hash_scoped),
    ("section_hash_sees_svg", _case_section_hash_sees_svg),
    ("stale_names_sections", _case_stale_names_sections),
    ("stamp_after_page_meta", _case_stamp_after_page_meta),
    ("stamp_idempotent", _case_stamp_idempotent),
    ("crosslink_skips_topic_deck_line", _case_crosslink_skips_topic_deck_line),
    ("hub_stamp_decks_mapped_cards", _case_hub_stamp_decks_mapped_cards),
    ("hub_stamp_reverses_and_is_idempotent", _case_hub_stamp_reverses_and_is_idempotent),
    ("hub_findings", _case_hub_findings),
    ("crosslink_skips_hub_deck_lines", _case_crosslink_skips_hub_deck_lines),
    ("record_writes_sections", _case_record_writes_sections),
    ("hub_wired_into_stamp_and_check", _case_hub_wired_into_stamp_and_check),
    ("check_empty_tree", _case_check_empty_tree),
    ("real_pages", _case_real_pages),
    ("stale_sees_cover", _case_stale_sees_cover),
    ("slug_from_plain_text", _case_slug_from_plain_text),
    ("slide_count_bounds", _case_slide_count_bounds),
]


def self_test() -> int:
    return _run_cases(CASES, "self-test")


def self_test_render() -> int:
    try:
        import topic_deck_render
    except ImportError as e:
        print(f"self-test-render: cannot import the renderer: {e}")
        return 1
    return _run_cases(topic_deck_render.RENDER_CASES, "self-test-render")


def main() -> int:
    ap = bbd.arg_parser(TOPIC, __doc__.split("\n\n")[0])
    ap.add_argument(
        "--extract", metavar="SLUG",
        help="print a topic page's <main> as text, with section ids and one line per figure",
    )
    ap.add_argument(
        "--sections", metavar="ID,ID",
        help="with --extract, print the heading list and then only these sections",
    )
    args = ap.parse_args()
    if args.sections and not args.extract:
        ap.error("--sections goes with --extract")
    if args.extract:
        only = [x.strip() for x in args.sections.split(",") if x.strip()] if args.sections else None
        try:
            print(extract(args.extract, only), end="")
        except (OSError, ValueError, OutlineError) as e:
            print(f"extract: {e}")
            return 1
        return 0
    if args.status:
        rc = bbd.status_report(TOPIC)
        if rc == 0:
            print(f"no deck by design: {', '.join(sorted(EXCLUDED))}")
        return rc
    return bbd.run_mode(ap, args, TOPIC, self_test, self_test_render)


if __name__ == "__main__":
    sys.exit(main())
