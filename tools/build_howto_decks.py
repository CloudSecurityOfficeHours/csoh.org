#!/usr/bin/env python3
"""
Parse the plain-text slide outlines in tools/decks/ and enforce the deck style
limits.

Each how-to guide in howto/ can have a slide deck written as an outline. This
module reads an outline into a Deck and reports every style-limit breach as a
finding. It uses the standard library only, so the checks run in CI without
python-pptx; the renderer lives in a separate module.

Outline format:

    title: <deck title>
    guide: <howto/page.html>
    promise: <one sentence>

    == <slide heading>
    section: <guide heading text>
    Prose lines join into one paragraph; a blank line ends it.
    - A bullet
    ```lang
    code, kept verbatim
    ```
    credit: <source and licence>

    == include: _fragment.deck

Header keys before the first `== ` line are exactly title, guide and promise.
`== include:` splices a fragment's slides in place. The fragment is named by
a bare `_name.deck` file name in tools/decks/. A fragment has no header and
cannot include another, so a deck's text always resolves in one pass.

Paths resolve from the repository root (the parent of this file's directory),
so every mode reads the same tree whatever the working directory.

Usage:
    python3 tools/build_howto_decks.py --self-test
    python3 tools/build_howto_decks.py --check
    python3 tools/build_howto_decks.py --build SLUG [SLUG ...]
    python3 tools/build_howto_decks.py --self-test-render
    python3 tools/build_howto_decks.py --stale [--published-only]
    python3 tools/build_howto_decks.py --status | --stamp
    python3 tools/build_howto_decks.py --record SLUG PRES_ID
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import html as htmllib
import io
import json
import os
import re
import sys
import tempfile
import traceback
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

MAX_PROSE_WORDS = 40
MAX_CODE_LINES = 12
# Characters per row in the code box. Source Code Pro advances 0.6 em, so at
# 16 pt the 11.8 in inner width holds 88 characters; 84 leaves room for a
# substitute font's metrics. The renderer's code size must agree (the render
# self-test checks it).
CODE_WRAP_COLS = 84
MAX_HEADING_WORDS = 12
MIN_SLIDES = 12
MAX_SLIDES = 22
# The renderer adds a cover and a closing slide that the outline does not
# contain; the slide-count limit applies to the total.
GENERATED_SLIDES = 2

# Every path is absolute, from this file's location. A path relative to the
# working directory would find no outlines and no pages when run from
# elsewhere, and a check that reads nothing reports clean. _set_root() moves
# all four together for the self-test.
ROOT = Path(__file__).resolve().parents[1]
DECKS_DIR = ROOT / "tools" / "decks"
HOWTO_DIR = ROOT / "howto"
MAPPING = DECKS_DIR / "published.json"


def _set_root(root: Path) -> Path:
    """Point every path at root; returns the previous root."""
    global ROOT, DECKS_DIR, HOWTO_DIR, MAPPING
    old = ROOT
    ROOT = root
    DECKS_DIR = root / "tools" / "decks"
    HOWTO_DIR = root / "howto"
    MAPPING = DECKS_DIR / "published.json"
    return old


def _rel(path: Path) -> str:
    """path relative to the repository root, for messages."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


# A fragment is named by its bare file name: no directory part, so an include
# can only read a file in tools/decks/.
INCLUDE_NAME_RE = re.compile(r"_[A-Za-z0-9][A-Za-z0-9_.-]*\.deck")

HEADER_KEYS = ("title", "guide", "promise")
HEADER_RE = re.compile(r"^([A-Za-z_]+):\s?(.*)$")
EM_DASH = chr(0x2014)
EN_DASH = chr(0x2013)
# A hyphen used as a dash. Applied to prose only: code keeps its own hyphens.
SPACED_HYPHEN_RE = re.compile(r"(?<=\S) - (?=\S)")


class OutlineError(Exception):
    """A malformed outline. The message starts with "<file>:<line>: "."""


@dataclass
class Slide:
    heading: str
    section: str | None = None
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    code: list[str] | None = None
    code_lang: str | None = None
    # The guide's own label for the block the excerpt comes from; set by the
    # build path, never read from the outline.
    code_label: str | None = None
    # The file a shell heredoc writes when the excerpt is its contents; the
    # renderer prints it on the tab in place of the language label.
    code_file: str | None = None
    credit: str | None = None
    where: str = ""
    # Where prose first follows a bullet. The renderer draws every paragraph
    # above every bullet, so that prose would move; style_findings reports it.
    prose_after_bullet: str | None = None


@dataclass
class Deck:
    slug: str
    title: str
    guide: str
    promise: str
    slides: list[Slide]
    # The outline with includes spliced in; the publish hash is taken over it
    # so a change to a shared fragment re-flags every deck that uses it.
    resolved_text: str


def _err(name: str, lineno: int, msg: str) -> OutlineError:
    return OutlineError(f"{name}:{lineno}: {msg}")


def _parse_slides(
    lines: list[str],
    first_lineno: int,
    name: str,
    include_dir: Path,
    allow_include: bool,
) -> tuple[list[Slide], list[str]]:
    """Parse slide lines. Returns the slides and the lines with includes
    spliced in. `first_lineno` is the 1-based number of lines[0]."""
    slides: list[Slide] = []
    resolved: list[str] = []
    cur: Slide | None = None
    para: list[str] = []
    in_fence = False
    fence_line = 0

    def flush_para() -> None:
        if para and cur is not None:
            cur.paragraphs.append(" ".join(para))
        para.clear()

    def finish() -> None:
        nonlocal cur
        if cur is None:
            return
        flush_para()
        if not (cur.paragraphs or cur.bullets or cur.code):
            raise _err(name, int(cur.where.rsplit(":", 1)[1]), "slide has no content")
        slides.append(cur)
        cur = None

    for i, line in enumerate(lines):
        lineno = first_lineno + i
        if in_fence:
            resolved.append(line)
            if line == "```":
                in_fence = False
                assert cur is not None and cur.code is not None
                if not any(c.strip() for c in cur.code):
                    raise _err(name, fence_line, "empty code block")
            else:
                assert cur is not None and cur.code is not None
                cur.code.append(line)
            continue

        if line.startswith("== "):
            finish()
            heading = line[3:].strip()
            if not heading:
                raise _err(name, lineno, "slide has no heading")
            if heading.startswith("include:"):
                if not allow_include:
                    raise _err(name, lineno, "an included file may not include others")
                frag_name = heading[len("include:"):].strip()
                if not INCLUDE_NAME_RE.fullmatch(frag_name):
                    raise _err(
                        name, lineno,
                        "include must be a bare _name.deck file name beside the outline "
                        f"(no directory part), got {frag_name!r}",
                    )
                frag_path = include_dir / frag_name
                if not frag_path.is_file():
                    raise _err(name, lineno, f"include file not found: {frag_name!r}")
                frag_lines = frag_path.read_text(encoding="utf-8").split("\n")
                for j, fl in enumerate(frag_lines):
                    if fl.startswith("== "):
                        break
                    if fl.strip():
                        raise _err(frag_name, j + 1, "text before the first slide")
                frag_slides, frag_resolved = _parse_slides(
                    frag_lines, 1, frag_name, include_dir, allow_include=False
                )
                slides.extend(frag_slides)
                resolved.extend(frag_resolved)
                continue
            cur = Slide(heading=heading, where=f"{name}:{lineno}")
            resolved.append(line)
            continue

        resolved.append(line)
        if cur is None:
            if line.strip():
                raise _err(name, lineno, "text before the first slide")
            continue

        stripped = line.strip()
        if not stripped:
            flush_para()
        elif stripped.startswith("```"):
            if cur.code is not None:
                raise _err(name, lineno, "a slide may have only one code block")
            flush_para()
            cur.code = []
            cur.code_lang = stripped[3:].strip() or None
            in_fence = True
            fence_line = lineno
        elif stripped.startswith("section:"):
            if cur.section is not None:
                raise _err(name, lineno, "slide has two section lines")
            cur.section = stripped[len("section:"):].strip()
            if not cur.section:
                raise _err(name, lineno, "empty section line")
        elif stripped.startswith("credit:"):
            if cur.credit is not None:
                raise _err(name, lineno, "slide has two credit lines")
            cur.credit = stripped[len("credit:"):].strip()
            if not cur.credit:
                raise _err(name, lineno, "empty credit line")
        elif stripped == "-":
            raise _err(name, lineno, "empty bullet")
        elif stripped.startswith("- "):
            flush_para()
            cur.bullets.append(stripped[2:].strip())
        else:
            if cur.bullets and cur.prose_after_bullet is None:
                cur.prose_after_bullet = f"{name}:{lineno}"
            para.append(stripped)

    if in_fence:
        raise _err(name, fence_line, "code fence is never closed")
    finish()
    return slides, resolved


def parse_outline_text(text: str, name: str, include_dir: Path) -> Deck:
    lines = text.split("\n")
    body_start = next((i for i, ln in enumerate(lines) if ln.startswith("== ")), len(lines))

    header: dict[str, str] = {}
    for i, line in enumerate(lines[:body_start]):
        if not line.strip():
            continue
        m = HEADER_RE.match(line)
        if not m:
            raise _err(name, i + 1, f"header line is not 'key: value': {line!r}")
        key, value = m.group(1), m.group(2).strip()
        if key not in HEADER_KEYS:
            raise _err(name, i + 1, f"unknown header key {key!r}")
        if key in header:
            raise _err(name, i + 1, f"header key {key!r} given twice")
        header[key] = value
    for key in HEADER_KEYS:
        if not header.get(key):
            raise _err(name, 1, f"missing required header key {key!r}")

    slides, resolved = _parse_slides(
        lines[body_start:], body_start + 1, name, include_dir, allow_include=True
    )
    slug = name[: -len(".deck")] if name.endswith(".deck") else name
    return Deck(
        slug=slug,
        title=header["title"],
        guide=header["guide"],
        promise=header["promise"],
        slides=slides,
        resolved_text="\n".join(lines[:body_start] + resolved),
    )


def parse_outline(path: Path) -> Deck:
    return parse_outline_text(path.read_text(encoding="utf-8"), path.name, path.parent)


def _words(text: str) -> int:
    return len(text.split())


def style_findings(deck: Deck) -> list[str]:
    """Every style-limit breach in the deck. Slide findings start with the
    slide's `where`; the slide-count finding starts with the deck's file."""
    findings: list[str] = []

    total = len(deck.slides) + GENERATED_SLIDES
    if not MIN_SLIDES <= total <= MAX_SLIDES:
        findings.append(
            f"{deck.slug}.deck: {total} slides including the generated "
            f"cover and closing; the deck must have {MIN_SLIDES} to {MAX_SLIDES}"
        )

    # The cover slide shows the title and promise, so they follow the same
    # dash rules as slide text.
    for label, t in (("title", deck.title), ("promise", deck.promise)):
        if EM_DASH in t or EN_DASH in t:
            findings.append(f"{deck.slug}.deck: em or en dash in {label} {t[:40]!r}")
        if SPACED_HYPHEN_RE.search(t):
            findings.append(
                f"{deck.slug}.deck: spaced hyphen used as a dash in {label} {t[:40]!r}"
            )

    for s in deck.slides:
        prose = s.paragraphs + s.bullets
        words = sum(_words(t) for t in prose)
        if words > MAX_PROSE_WORDS:
            findings.append(
                f"{s.where}: {words} words of prose; the limit is {MAX_PROSE_WORDS}"
            )
        if _words(s.heading) > MAX_HEADING_WORDS:
            findings.append(
                f"{s.where}: heading is {_words(s.heading)} words; "
                f"the limit is {MAX_HEADING_WORDS}"
            )
        if s.code is not None:
            rows = code_visual_rows(s.code)
            if rows > MAX_CODE_LINES:
                findings.append(
                    f"{s.where}: code takes {rows} rows once long lines wrap; "
                    f"the limit is {MAX_CODE_LINES}"
                )
        if s.prose_after_bullet:
            findings.append(
                f"{s.prose_after_bullet}: prose after a bullet renders above all the "
                "bullets; move it before them or make it a bullet"
            )

        texts = [s.heading, *prose]
        if s.credit:
            texts.append(s.credit)
        for t in texts:
            if EM_DASH in t or EN_DASH in t:
                findings.append(f"{s.where}: em or en dash in {t[:40]!r}")
            if SPACED_HYPHEN_RE.search(t):
                findings.append(f"{s.where}: spaced hyphen used as a dash in {t[:40]!r}")
    return findings


# ---------------------------------------------------------------------------
# Guide-page deck lines and the mapping file.
# ---------------------------------------------------------------------------

DECK_ATTR = "data-howto-deck"
# A deck line is one <p> carrying data-howto-deck, alone on its line and
# closed on that line. Nothing it matches can reach past the line, so
# removing a match never takes other page content with it.
DECK_LINE_RE = re.compile(
    r"^[ \t]*<p[^>\n]*\bdata-howto-deck\b[^>\n]*>(?:(?!</p>)[^\n])*</p>[ \t]*(?:\n|\Z)",
    re.MULTILINE,
)
INFO_BOX_OPEN = '<div class="info-box--blue">'
# The first info box as --stamp edits it: the opening tag ends its line, no
# line inside opens or closes a div, and the box closes on a line starting
# with </div>. The match ends where the deck line goes. Any other shape is
# refused rather than guessed at.
INFO_BOX_RE = re.compile(
    re.escape(INFO_BOX_OPEN) + r"[ \t]*\n(?:(?:(?!</?div\b)[^\n])*\n)*?(?=[ \t]*</div>)"
)
PRESENTATION_RE = re.compile(r"docs\.google\.com/presentation\b")
# A Google Drive file id. Anything else in the mapping would be written into
# an href unescaped.
PRES_ID_RE = re.compile(r"[A-Za-z0-9_-]{25,}")
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA256_RE = re.compile(r"[0-9a-f]{64}")
DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
ENTRY_KEYS = ("id", "outline_sha256", "published")


def outline_sha256(deck: Deck) -> str:
    return hashlib.sha256(deck.resolved_text.encode("utf-8")).hexdigest()


def deck_line_html(pres_id: str) -> str:
    base = f"https://docs.google.com/presentation/d/{pres_id}"
    ext = 'target="_blank" rel="noopener noreferrer"'
    licence = "https://creativecommons.org/licenses/by-nc/4.0/"
    return (
        '            <p class="u-mt-075" data-howto-deck><strong>Slides:</strong> '
        f'<a href="{base}/export/pdf" {ext}>download the PDF</a> or '
        f'<a href="{base}/copy" {ext}>make your own editable copy</a> '
        "(copying needs a Google account). The slides are licensed "
        f'<a href="{licence}" {ext}>CC BY-NC 4.0</a>.</p>'
    )


def loose_deck_markup(html: str) -> int:
    """data-howto-deck mentions that are not part of a whole deck line: a
    line missing its </p>, one written inline after other markup, or two on
    one line. --stamp cannot remove these without guessing."""
    return DECK_LINE_RE.sub("", html).count(DECK_ATTR)


def _insert_deck_line(html: str, pres_id: str) -> str:
    start = html.find(INFO_BOX_OPEN)
    if start < 0:
        raise ValueError(f"no {INFO_BOX_OPEN} to hold the deck line")
    m = INFO_BOX_RE.match(html, start)
    if not m:
        raise ValueError(
            f"the first {INFO_BOX_OPEN} must end its line, hold no other div, and "
            "close on a line starting with </div>"
        )
    return html[: m.end()] + deck_line_html(pres_id) + "\n" + html[m.end():]


def stamp_page(html: str, pres_id: str | None) -> str:
    """The page as --stamp writes it: every deck line removed, then, when
    pres_id is given, one deck line last in the first info box. Raises
    ValueError when the page holds deck markup that is not a whole deck
    line, or the info box is not in the shape it can edit."""
    loose = loose_deck_markup(html)
    if loose:
        raise ValueError(
            f"{loose} {DECK_ATTR} mention(s) outside a whole deck line (one <p> "
            "alone on its line, closed on that line); fix the markup by hand"
        )
    if pres_id is not None and not PRES_ID_RE.fullmatch(pres_id):
        raise ValueError(f"{pres_id!r} is not a Google Slides presentation id")
    bare = DECK_LINE_RE.sub("", html)
    return bare if pres_id is None else _insert_deck_line(bare, pres_id)


def _entry_id(entry) -> str | None:
    """The entry's presentation id when it is well formed, else None."""
    pres_id = entry.get("id") if isinstance(entry, dict) else None
    return pres_id if isinstance(pres_id, str) and PRES_ID_RE.fullmatch(pres_id) else None


def link_findings(slug: str, html: str, mapping: dict) -> list[str]:
    """Disagreements between a guide page's deck markup and the mapping. A
    page in the mapping must hold exactly the one deck line --stamp writes,
    last in its first info box; a page outside it must hold no deck markup.
    Any Google Slides link outside the deck line is a finding either way."""
    page = f"howto/{slug}.html"
    findings: list[str] = []
    lines = DECK_LINE_RE.findall(html)
    rest = DECK_LINE_RE.sub("", html)
    loose = rest.count(DECK_ATTR)
    if loose:
        findings.append(
            f"{page}: {loose} {DECK_ATTR} mention(s) outside a whole deck line "
            "(one <p> alone on its line, closed on that line)"
        )
    if PRESENTATION_RE.search(rest) and not loose:
        findings.append(f"{page}: links a Google Slides deck outside its deck line")
    entry = mapping.get(slug)
    if entry is None:
        if lines:
            findings.append(f"{page}: has a deck line but {slug!r} is not in the mapping")
        return findings
    pres_id = _entry_id(entry)
    if pres_id is None:
        return findings  # mapping_findings reports the entry itself
    want = deck_line_html(pres_id)
    if not lines and not loose:
        findings.append(f"{page}: {slug!r} is in the mapping but the page has no deck line")
    elif len(lines) > 1:
        findings.append(f"{page}: has {len(lines)} deck lines; it must have exactly one")
    elif lines and lines[0].rstrip() != want:
        findings.append(
            f"{page}: deck line is not the one --stamp writes for mapping id {pres_id!r}"
        )
    elif lines and not loose:
        try:
            if _insert_deck_line(rest, pres_id) != html:
                findings.append(
                    f"{page}: deck line is not where --stamp puts it (last in the "
                    "first info box); run --stamp"
                )
        except ValueError as e:
            findings.append(f"{page}: {e}")
    return findings


# ---------------------------------------------------------------------------
# The guides hub: each guide card on cloud-security-how-to.html whose guide
# has a published deck ends with the deck's links and a closed slide preview.
# ---------------------------------------------------------------------------

HUB = "cloud-security-how-to.html"
HUB_DECK_ATTR = "data-howto-hub-deck"
SLIDES_LINK = "docs.google.com/presentation"
# A card opens on a line of its own and ends at the first line closing a div
# at the same indent, so nothing read from one card can run into the next.
_HUB_CARD_START_RE = re.compile(r'^(?P<ind>[ \t]*)<div class="resource-card"[^>\n]*>[ \t]*\n', re.M)
_HUB_GUIDE_RE = re.compile(
    r'<h3\b[^>]*>\s*<a\b[^>]*\bhref="howto/(?P<slug>[a-z0-9][a-z0-9-]*)\.html"[^>]*>(?P<name>.*?)</a\s*>', re.S
)


def preview_html(pres_id: str, attr: str, title: str) -> str:
    """A closed slide preview carrying attr, as --stamp writes it on a topic
    page, on a topics.html card and on a guide card on the guides hub. Its
    iframe names Google's viewer in data-src and has no src: with scripts
    off a browser loads every iframe at page load, closed panel and
    loading="lazy" or not. main.js copies data-src into src when the panel
    opens, so nothing loads from Google until a reader opens it. With
    scripts off, noscript.css hides the empty frame and the open panel shows
    a link to the same viewer instead."""
    src = f"https://docs.google.com/presentation/d/{pres_id}/embed"
    ext = 'target="_blank" rel="noopener noreferrer"'
    return (
        f'<details class="deck-preview" {attr}><summary>Preview the slides</summary>'
        f'<div class="deck-frame"><iframe data-src="{src}" title="{title}" allowfullscreen></iframe></div>'
        f'<noscript><p class="deck-preview-link"><a href="{src}" {ext}>Open the slides in Google Slides</a> '
        "(the preview here needs JavaScript).</p></noscript></details>"
    )


@dataclass
class _HubCard:
    start: int
    end: int
    slug: str
    name: str
    ind: str
    head: str  # the opening line and every inner line but the strip
    tail: str  # the closing line
    decked: bool | None  # None: neither a plain card nor a decked one


def _hub_strip(pres_id: str, ind: str, name: str) -> str:
    base = f"https://docs.google.com/presentation/d/{pres_id}"
    ext = 'target="_blank" rel="noopener noreferrer"'
    title = name.replace('"', "&quot;")
    return (
        f'{ind}    <p class="deck-actions" {HUB_DECK_ATTR}><strong>Slides:</strong> '
        f'<a href="{base}/export/pdf" {ext}>PDF</a> <a href="{base}/copy" {ext}>Editable copy</a></p>\n'
        f'{ind}    {preview_html(pres_id, HUB_DECK_ATTR, f"Preview of the {title} slides")}\n'
    )


def _hub_cards(html: str) -> list[_HubCard]:
    """Every guide card on the hub, in order. A card is a guide card when
    its h3 links a page in howto/; other cards are not read."""
    cards: list[_HubCard] = []
    pos = 0
    for m in _HUB_CARD_START_RE.finditer(html):
        if m.start() < pos:
            continue
        ind = m.group("ind")
        close = re.compile(r"^" + re.escape(ind) + r"</div>[ \t]*(?:\n|\Z)", re.M).search(html, m.end())
        body = html[m.end(): close.start() if close else len(html)]
        guide = _HUB_GUIDE_RE.search(body)
        if guide is None:
            continue
        pos = close.end() if close else len(html)
        name = re.sub(r"<[^>]+>", "", guide.group("name")).strip()
        lines = body.splitlines(keepends=True)
        marked = [i for i, ln in enumerate(lines) if HUB_DECK_ATTR in ln]
        decked: bool | None = None
        if close is None:
            pass
        elif not marked:
            decked = False
        elif marked == [len(lines) - 2, len(lines) - 1] and re.fullmatch(
            re.escape(ind) + r"    <p class=\"deck-actions\" " + HUB_DECK_ATTR + r">(?:(?!</p>)[^\n])*</p>\n"
            + re.escape(ind) + r"    <details class=\"deck-preview\" " + HUB_DECK_ATTR
            + r">(?:(?!</details>)[^\n])*</details>\n",
            lines[-2] + lines[-1],
        ):
            decked = True
        keep = lines[:-2] if decked else lines
        cards.append(_HubCard(m.start(), pos, guide.group("slug"), name, ind,
                              m.group(0) + "".join(keep), close.group(0) if close else "", decked))
    return cards


def _hub_card_html(c: _HubCard, pres_id: str | None) -> str:
    """The card as it is written for pres_id: decked, or plain when None."""
    return c.head + (_hub_strip(pres_id, c.ind, c.name) if pres_id else "") + c.tail


def _hub_want(c: _HubCard, mapping: dict) -> str | None:
    return _entry_id(mapping.get(c.slug))


def _hub_stray(html: str, cards: list[_HubCard]) -> bool:
    """The deck attribute anywhere but inside a guide card. A card of
    neither form is reported as itself, so its own lines do not count."""
    rest, pos = [], 0
    for c in cards:
        rest.append(html[pos: c.start])
        pos = c.end
    rest.append(html[pos:])
    return HUB_DECK_ATTR in "".join(rest)


def stamp_hub(html: str, mapping: dict) -> str:
    """The hub with every guide card whose guide is in the mapping (with a
    well-formed id) decked, and every other guide card plain. A card of
    neither form, or the deck attribute outside a guide card, is an error:
    rewriting around it would guess at what to keep."""
    cards = _hub_cards(html)
    for c in cards:
        if c.decked is None:
            raise ValueError(f"{HUB}: the card for {c.slug} ({c.name!r}) is neither a plain card nor a "
                             "decked card; fix its markup by hand")
    if _hub_stray(html, cards):
        raise ValueError(f"{HUB}: {HUB_DECK_ATTR} appears outside a guide card")
    out, pos = [], 0
    for c in cards:
        out += [html[pos: c.start], _hub_card_html(c, _hub_want(c, mapping))]
        pos = c.end
    out.append(html[pos:])
    return "".join(out)


def hub_findings(html: str, mapping: dict) -> list[str]:
    """Where the hub disagrees with the mapping: one finding per guide card
    that differs from what stamp_hub writes, each published guide with no
    card to carry its deck, and any Google Slides link outside a strip."""
    findings: list[str] = []
    cards = _hub_cards(html)
    for c in cards:
        if c.decked is None:
            findings.append(f"{HUB}: the card for {c.slug} ({c.name!r}) is malformed: neither a plain card "
                            "nor a decked card, so its deck markup cannot be read")
            continue
        want = _hub_want(c, mapping)
        if html[c.start: c.end] == _hub_card_html(c, want):
            continue
        if want and not c.decked:
            findings.append(f"{HUB}: the card for {c.slug} has no deck; the guide's deck is published")
        elif want:
            findings.append(f"{HUB}: the card for {c.slug} has the wrong deck markup for its published id")
        else:
            findings.append(f"{HUB}: the card for {c.slug} carries a deck, but the guide's deck is not published")
    on_hub = {c.slug for c in cards}
    for slug in sorted(mapping):
        if _entry_id(mapping[slug]) and slug not in on_hub:
            findings.append(f"{HUB}: {slug} is published but has no card on the hub (one "
                            f'<div class="resource-card"> per guide, its h3 linking howto/{slug}.html)')
    if _hub_stray(html, cards):
        findings.append(f"{HUB}: {HUB_DECK_ATTR} appears outside a guide card")
    outside = "\n".join(ln for ln in html.splitlines() if HUB_DECK_ATTR not in ln)
    if SLIDES_LINK in outside:
        findings.append(f"{HUB}: a {SLIDES_LINK} link sits outside a guide card's deck strip")
    return findings


def _read_hub() -> str:
    """The hub's text; raises ValueError naming it when it cannot be read."""
    try:
        return (ROOT / HUB).read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"{HUB}: cannot be read ({e.strerror or e})") from None


def read_mapping() -> tuple[dict, str | None]:
    """The mapping and None, or {} and why it cannot be read. A missing file
    is an empty mapping."""
    if not MAPPING.exists():
        return {}, None
    try:
        mapping = json.loads(MAPPING.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {}, f"{_rel(MAPPING)}: cannot be read as JSON: {e}"
    if not isinstance(mapping, dict):
        return {}, f"{_rel(MAPPING)}: must be a JSON object keyed by slug"
    return mapping, None


def load_mapping() -> dict:
    mapping, problem = read_mapping()
    if problem:
        raise ValueError(problem)
    return mapping


def save_mapping(mapping: dict) -> None:
    MAPPING.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mapping_findings(mapping: dict, outlines: set[str], pages: set[str]) -> list[str]:
    """Every mapping entry that is malformed or names a deck the repo cannot
    account for: a slug with no outline or no guide page, an id that is not a
    Drive file id, a date that is not ISO, or a hash that is not sha256."""
    findings: list[str] = []
    name = _rel(MAPPING)
    for slug in sorted(mapping):
        entry = mapping[slug]
        where = f"{name}: {slug!r}"
        if not SLUG_RE.fullmatch(slug):
            findings.append(f"{where}: not a guide slug (lowercase letters, digits, hyphens)")
            continue
        if slug not in outlines:
            findings.append(f"{where}: has no outline tools/decks/{slug}.deck")
        if slug not in pages:
            findings.append(f"{where}: names no howto page")
        if not isinstance(entry, dict):
            findings.append(f"{where}: entry must be an object with keys {', '.join(ENTRY_KEYS)}")
            continue
        if sorted(entry) != sorted(ENTRY_KEYS):
            findings.append(
                f"{where}: entry keys must be exactly {', '.join(ENTRY_KEYS)}; "
                f"got {', '.join(sorted(entry)) or 'none'}"
            )
        if "id" in entry and _entry_id(entry) is None:
            findings.append(f"{where}: id {entry['id']!r} is not a Google Slides presentation id")
        published = entry.get("published")
        if "published" in entry and not _is_iso_date(published):
            findings.append(f"{where}: published {published!r} is not a YYYY-MM-DD date")
        sha = entry.get("outline_sha256")
        if "outline_sha256" in entry and not (isinstance(sha, str) and SHA256_RE.fullmatch(sha)):
            findings.append(f"{where}: outline_sha256 {sha!r} is not a sha256 hex digest")
    return findings


def _is_iso_date(value) -> bool:
    if not isinstance(value, str) or not DATE_RE.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def code_rows(line: str, cols: int = CODE_WRAP_COLS) -> int:
    """Rows one code line occupies when wrapped at spaces. Greedy fill: words
    separated by single spaces share a row while it stays within cols
    characters, and leading indentation counts toward the first row. A word
    longer than cols is split across ceil(len / cols) rows on its own."""
    rows, cur = 1, 0
    for i, word in enumerate(line.split(" ")):
        if len(word) > cols:
            if i:
                rows += 1
            rows += -(-len(word) // cols) - 1
            cur = cols + 1  # the next word starts a fresh row
        elif i == 0:
            cur = len(word)
        elif cur + 1 + len(word) <= cols:
            cur += 1 + len(word)
        else:
            rows += 1
            cur = len(word)
    return rows


def code_visual_rows(lines: list[str], cols: int = CODE_WRAP_COLS) -> int:
    return sum(code_rows(line, cols) for line in lines)


def outline_paths() -> list[Path]:
    return sorted(p for p in DECKS_DIR.glob("*.deck") if not p.name.startswith("_"))


def guide_pages() -> list[Path]:
    return sorted(HOWTO_DIR.glob("*.html"))


def tree_problem() -> str | None:
    """Why the outlines or guide pages cannot be found, or None. Every mode
    that reads the tree stops on this rather than report on nothing."""
    if not outline_paths():
        return f"no outlines found in {DECKS_DIR}"
    if not guide_pages():
        return f"no guide pages found in {HOWTO_DIR}"
    return None


def check_all() -> int:
    problem = tree_problem()
    if problem:
        print(f"decks: {problem}; nothing was checked")
        return 1
    findings: list[str] = []
    mapping, map_problem = read_mapping()
    if map_problem:
        findings.append(map_problem)
    outlines = outline_paths()
    for path in outlines:
        try:
            deck = parse_outline(path)
        except OutlineError as e:
            findings.append(str(e))
            continue
        findings += style_findings(deck)
        if deck.guide != f"howto/{deck.slug}.html":
            findings.append(f"{path.name}: guide must be howto/{deck.slug}.html, got {deck.guide}")
        elif not (ROOT / deck.guide).exists():
            findings.append(f"{path.name}: guide {deck.guide} does not exist")
        else:
            findings += guide_findings(deck, (ROOT / deck.guide).read_text(encoding="utf-8"))
    pages = guide_pages()
    findings += mapping_findings(mapping, {p.stem for p in outlines}, {p.stem for p in pages})
    # An unreadable mapping would make every deck line read as unmapped.
    if not map_problem:
        for page in pages:
            findings += link_findings(page.stem, page.read_text(encoding="utf-8"), mapping)
        try:
            findings += hub_findings(_read_hub(), mapping)
        except ValueError as e:
            findings.append(str(e))
    for f in findings:
        print(f)
    print(
        f"decks: {len(outlines)} outlines checked, {len(pages)} guide pages checked, "
        f"{len(findings)} findings"
    )
    return 1 if findings else 0


def _stale_reason(slug: str, entry, path: Path | None) -> str | None:
    """Why a published deck no longer matches its outline, or None."""
    if path is None:
        return f"published, but tools/decks/{slug}.deck is missing"
    try:
        deck = parse_outline(path)
    except OutlineError as e:
        return f"outline does not parse, so whether it changed is unknown: {e}"
    recorded = entry.get("outline_sha256") if isinstance(entry, dict) else None
    if recorded == outline_sha256(deck):
        return None
    when = entry.get("published") if isinstance(entry, dict) else None
    return f"outline changed since it was published on {when}; the public deck needs re-publishing"


def stale_report(published_only: bool = False) -> int:
    """Print one line per published deck whose outline changed since --record
    (and, unless published_only, per outline never published), then a
    summary line starting "stale check:". Staleness never fails: it exits 0
    whether or not decks are stale, and 1 only when the outlines, the guide
    pages or the mapping cannot be read."""
    problem = tree_problem()
    if problem:
        print(f"stale check: {problem}")
        return 1
    mapping, problem = read_mapping()
    if problem:
        print(f"stale check: {problem}")
        return 1
    outlines = {p.stem: p for p in outline_paths()}
    stale = unpublished = 0
    for slug in sorted(set(outlines) | set(mapping)):
        if slug not in mapping:
            unpublished += 1
            if not published_only:
                print(f"{slug}: not published")
            continue
        reason = _stale_reason(slug, mapping[slug], outlines.get(slug))
        if reason:
            stale += 1
            print(f"{slug}: {reason}")
    summary = f"stale check: {stale} of {len(mapping)} published decks changed since publishing"
    if not published_only:
        summary += f"; outlines never published: {unpublished}"
    print(summary)
    return 0


def status_report() -> int:
    problem = tree_problem()
    if problem:
        print(f"status: {problem}")
        return 1
    mapping, problem = read_mapping()
    if problem:
        print(f"status: {problem}")
        return 1
    outlines = {p.stem for p in outline_paths()}
    for page in guide_pages():
        has_outline = "yes" if page.stem in outlines else "no"
        published = "yes" if page.stem in mapping else "no"
        print(f"{page.stem}: outline {has_outline}, published {published}")
    return 0


def plan_stamps(mapping: dict) -> tuple[dict[Path, str], list[str]]:
    """The new text of every guide page and of the guides hub that --stamp
    would change, and every one it cannot stamp. Nothing is written."""
    changes: dict[Path, str] = {}
    errors: list[str] = []
    for page in guide_pages():
        html = page.read_text(encoding="utf-8")
        entry = mapping.get(page.stem)
        pres_id = None
        if entry is not None:
            pres_id = _entry_id(entry)
            if pres_id is None:
                errors.append(f"{_rel(page)}: its mapping entry has no valid id, so it cannot be stamped")
                continue
        try:
            new = stamp_page(html, pres_id)
        except ValueError as e:
            errors.append(f"{_rel(page)}: {e}")
            continue
        if new != html:
            changes[page] = new
    try:
        hub = _read_hub()
        new = stamp_hub(hub, mapping)
    except ValueError as e:
        errors.append(str(e))
    else:
        if new != hub:
            changes[ROOT / HUB] = new
    return changes, errors


def _write_stamps(mapping: dict, label: str, save: bool) -> int:
    """Check the mapping and plan every page first. On any error, print them
    all and write nothing, so no run leaves some pages stamped and others
    not, or a mapping its pages disagree with. Otherwise save the mapping
    when asked, then write the changed pages."""
    pages = {p.stem for p in guide_pages()}
    errors = mapping_findings(mapping, {p.stem for p in outline_paths()}, pages)
    changes, stamp_errors = plan_stamps(mapping)
    errors += stamp_errors
    if errors:
        for e in errors:
            print(e)
        print(f"{label}: refused, nothing written; fix the problems above")
        return 1
    if save:
        save_mapping(mapping)
    for page, new in changes.items():
        page.write_text(new, encoding="utf-8")
        print(f"stamped {_rel(page)}")
    return 0


def stamp_all() -> int:
    problem = tree_problem()
    if problem:
        print(f"stamp: {problem}")
        return 1
    mapping, problem = read_mapping()
    if problem:
        print(f"stamp: {problem}")
        return 1
    return _write_stamps(mapping, "stamp", save=False)


def record(slug: str, pres_id: str) -> int:
    problem = tree_problem()
    if problem:
        print(f"record: {problem}")
        return 1
    errors = []
    if not SLUG_RE.fullmatch(slug) or not (DECKS_DIR / f"{slug}.deck").is_file():
        errors.append(f"record: no outline tools/decks/{slug}.deck")
    if not PRES_ID_RE.fullmatch(pres_id):
        errors.append(f"record: {pres_id!r} is not a Google Slides presentation id")
    if errors:
        print("\n".join(errors))
        return 1
    try:
        deck = parse_outline(DECKS_DIR / f"{slug}.deck")
    except OutlineError as e:
        print(f"record: {e}")
        return 1
    mapping, problem = read_mapping()
    if problem:
        print(f"record: {problem}")
        return 1
    mapping[slug] = {
        "id": pres_id,
        "published": date.today().isoformat(),
        "outline_sha256": outline_sha256(deck),
    }
    return _write_stamps(mapping, "record", save=True)


# ---------------------------------------------------------------------------
# Self-test. CASES holds (name, fn) pairs; each fn takes a scratch directory
# and asserts. Cases that need a scratch repository build one with _tree()
# and point every path at it with _rooted().
# ---------------------------------------------------------------------------

SAMPLE = """title: Splunk SPL for cloud security
guide: howto/splunk-spl.html
promise: Five searches that find one leaked AWS key in CloudTrail.

== A search is a pipeline
section: A search is a pipeline
Each command works on the events
the one before it produced.
- Filter first, then shape the results.
```spl
index=cloudtrail readOnly=false
```
credit: Splunk security_content, Apache-2.0

== include: _stub.deck
== Last slide
Done.
"""

STUB = """== Fragment slide
From the fragment.
"""


HEADING_RE = re.compile(r"<h([23])([^>]*)>(.*?)</h\1>", re.DOTALL)
ID_RE = re.compile(r"""\bid\s*=\s*["']([^"']*)["']""")
TAG_RE = re.compile(r"<[^>]+>")


# A <pre> with the code-block wrapper that directly holds it, if any. The
# wrapper's data-lang is what the site draws as the block's header label.
# Blocks and labels both come from this one pattern, so the two lists line up
# by construction and a label can never sit on the wrong block.
LABELLED_PRE_RE = re.compile(
    r'(?:<div class="code-block[^"]*"([^>]*)>\s*)?<pre[^>]*>(.*?)</pre>', re.DOTALL
)
DATA_LANG_RE = re.compile(r'\bdata-lang="([^"]*)"')


def guide_code_blocks(html: str) -> list[list[str]]:
    """Every <pre> block on the page as unescaped lines with trailing
    whitespace removed, so an excerpt compares against what a reader sees."""
    return [
        [ln.rstrip() for ln in htmllib.unescape(m.group(2)).split("\n")]
        for m in LABELLED_PRE_RE.finditer(html)
    ]


def guide_block_labels(html: str) -> list[str | None]:
    """One entry per <pre>, aligned with guide_code_blocks: the data-lang of the
    code-block div that directly wraps it, or None when that div has no
    data-lang or the <pre> has no such wrapper. Output blocks carry no
    data-lang, which is how a reader tells them from input. data-lang="text"
    (stamped on output and on languages the highlighter does not know) also
    gives None: style.css draws those blocks with no label, like an unlabelled
    one, so a slide must not print a tab the guide does not show."""
    out: list[str | None] = []
    for m in LABELLED_PRE_RE.finditer(html):
        lang = DATA_LANG_RE.search(m.group(1) or "")
        out.append(lang.group(1) if lang and lang.group(1) != "text" else None)
    return out


def excerpt_label(html: str, lines: list[str]) -> str | None:
    """The label of the first block holding lines as a contiguous run, or None
    when no block does or that block is unlabelled."""
    for block, label in zip(guide_code_blocks(html), guide_block_labels(html)):
        if is_contiguous_run(lines, block):
            return label
    return None


HEREDOC_RE = re.compile(r"""[>]\s*(\S+)\s*<<-?\s*['"]?(\w+)['"]?\s*$""")


def excerpt_file(html: str, lines: list[str]) -> str | None:
    """The file a heredoc writes when the excerpt lies inside its body, else
    None. The nearest opener above the run (`> FILE <<'WORD'`) counts only if
    its terminator line comes at or after the run's end; a nearer terminator
    closes the heredoc first. The excerpt is file contents, not shell input,
    so its tab names the file rather than the block's bash label."""
    want = [ln.rstrip() for ln in lines]
    n = len(want)
    if n == 0:
        return None
    for block in guide_code_blocks(html):
        start = next((i for i in range(len(block) - n + 1) if block[i : i + n] == want), None)
        if start is None:
            continue
        end = start + n
        for i in range(start - 1, -1, -1):
            m = HEREDOC_RE.search(block[i])
            if not m:
                continue
            close = next((j for j in range(i + 1, len(block)) if block[j].strip() == m.group(2)), None)
            if close is not None and close >= end:
                return m.group(1)
            return None
        return None
    return None


def guide_headings(html: str) -> dict[str, str | None]:
    """Visible text of every h2 and h3 mapped to its id, or None without one."""
    out: dict[str, str | None] = {}
    for m in HEADING_RE.finditer(html):
        text = " ".join(htmllib.unescape(TAG_RE.sub("", m.group(3))).split())
        idm = ID_RE.search(m.group(2))
        out[text] = idm.group(1) if idm else None
    return out


def is_contiguous_run(excerpt: list[str], block: list[str]) -> bool:
    """True when the excerpt equals consecutive lines of the block. A gap or
    a join across two blocks would show readers code the guide never ran."""
    want = [ln.rstrip() for ln in excerpt]
    n = len(want)
    if n == 0:
        return False
    return any(block[i : i + n] == want for i in range(len(block) - n + 1))


def guide_findings(deck: Deck, html: str) -> list[str]:
    """Slide excerpts that are not a contiguous run of one guide code block,
    and `section:` values that name no h2 or h3 on the guide."""
    blocks = guide_code_blocks(html)
    headings = guide_headings(html)
    findings: list[str] = []
    for s in deck.slides:
        if s.code and not any(is_contiguous_run(s.code, b) for b in blocks):
            findings.append(
                f"{s.where}: code is not a contiguous run of whole lines "
                f"from one code block on {deck.guide}"
            )
        if s.section and s.section not in headings:
            findings.append(
                f"{s.where}: section {s.section!r} is not an h2 or h3 on {deck.guide}"
            )
    return findings


def _hdr(body: str) -> str:
    return (
        "title: T\nguide: howto/t.html\npromise: P.\n\n" + body
    )


def _deck_with(n: int, paragraph: str = "Short.") -> Deck:
    slides = [
        Slide(heading=f"Slide {i}", paragraphs=[paragraph], where=f"d.deck:{i}")
        for i in range(n)
    ]
    return Deck("d", "T", "howto/t.html", "P.", slides, "")


def _raises(fn, needle: str | None = None) -> OutlineError:
    try:
        fn()
    except OutlineError as e:
        if needle is not None:
            assert needle in str(e), f"{needle!r} not in {str(e)!r}"
        return e
    raise AssertionError("OutlineError was not raised")


def _case_parse_ok(tmp: Path) -> None:
    (tmp / "_stub.deck").write_text(STUB)
    d = parse_outline_text(SAMPLE, "sample.deck", tmp)
    assert d.slug == "sample" and d.slides[0].heading == "A search is a pipeline"
    assert d.slides[0].paragraphs == [
        "Each command works on the events the one before it produced."
    ]
    assert d.slides[0].bullets == ["Filter first, then shape the results."]
    assert d.slides[0].code == ["index=cloudtrail readOnly=false"]
    assert d.slides[0].code_lang == "spl"
    assert d.slides[0].credit == "Splunk security_content, Apache-2.0"
    assert d.slides[0].section == "A search is a pipeline"
    assert d.slides[0].where == "sample.deck:5"
    assert d.title == "Splunk SPL for cloud security"
    assert d.guide == "howto/splunk-spl.html"


def _case_include_spliced(tmp: Path) -> None:
    (tmp / "_stub.deck").write_text(STUB)
    d = parse_outline_text(SAMPLE, "sample.deck", tmp)
    assert [s.heading for s in d.slides] == [
        "A search is a pipeline",
        "Fragment slide",
        "Last slide",
    ]
    assert d.slides[1].where == "_stub.deck:1"
    assert "From the fragment." in d.resolved_text
    assert "include:" not in d.resolved_text


def _case_nested_include(tmp: Path) -> None:
    (tmp / "_inner.deck").write_text(STUB)
    (tmp / "_outer.deck").write_text("== Outer\nText.\n== include: _inner.deck\n")
    _raises(
        lambda: parse_outline_text(_hdr("== include: _outer.deck\n"), "d.deck", tmp),
        "_outer.deck:3:",
    )


def _case_missing_header(tmp: Path) -> None:
    _raises(
        lambda: parse_outline_text(
            "title: T\npromise: P.\n\n== S\nText.\n", "d.deck", tmp
        ),
        "d.deck:1:",
    )


def _case_unknown_header_key(tmp: Path) -> None:
    _raises(
        lambda: parse_outline_text(
            "title: T\nguide: g\npromise: P.\nauthor: x\n\n== S\nText.\n", "d.deck", tmp
        ),
        "author",
    )


def _case_unterminated_fence(tmp: Path) -> None:
    text = _hdr("== S\nText.\n```sh\nls\n")
    _raises(lambda: parse_outline_text(text, "d.deck", tmp), ":7:")


def _case_two_fences(tmp: Path) -> None:
    text = _hdr("== S\n```sh\nls\n```\n```sh\npwd\n```\n")
    _raises(lambda: parse_outline_text(text, "d.deck", tmp), "one code block")


def _case_empty_slide(tmp: Path) -> None:
    _raises(
        lambda: parse_outline_text(_hdr("== Only a heading\n"), "d.deck", tmp),
        "no content",
    )


def _case_fence_hides_slide_marker(tmp: Path) -> None:
    text = _hdr("== S\n```\n== not a slide\n- not a bullet\n```\n")
    d = parse_outline_text(text, "d.deck", tmp)
    assert len(d.slides) == 1
    assert d.slides[0].code == ["== not a slide", "- not a bullet"]
    assert d.slides[0].bullets == []


def _case_too_many_words(tmp: Path) -> None:
    f = style_findings(_deck_with(10, " ".join(["w"] * 41)))
    hits = [x for x in f if "40" in x and "words of prose" in x]
    assert len(hits) == 10, f
    assert style_findings(_deck_with(10, " ".join(["w"] * 40))) == []


def _case_too_many_code_lines(tmp: Path) -> None:
    d = _deck_with(10)
    d.slides[0].code = ["x"] * 13
    f = style_findings(d)
    assert len(f) == 1 and "12" in f[0] and f[0].startswith("d.deck:0:"), f
    d.slides[0].code = ["x"] * 12
    assert style_findings(d) == []


SPL_LONG = (
    "index=cloudtrail errorCode IN (AccessDenied, AccessDeniedException) "
    "| stats count by userName, eventName, sourceIPAddress | sort -count"
)


def _case_code_rows_basic(tmp: Path) -> None:
    assert code_rows("a" * CODE_WRAP_COLS) == 1
    assert code_rows("a" * (CODE_WRAP_COLS + 1)) == 2
    assert code_rows("") == 1
    # "x " * 60 splits into 60 "x" words plus one empty word. A row of k
    # words is 2k-1 characters, so 42 words (83) fit and a 43rd (85) does
    # not; row 2 holds the remaining 18 words and the empty one (36).
    assert code_rows("x " * 60) == 2


def _case_code_rows_words(tmp: Path) -> None:
    assert len(SPL_LONG) == 135, len(SPL_LONG)
    assert code_rows(SPL_LONG) == 2
    room = CODE_WRAP_COLS - 4
    assert code_rows("    " + "a" * room) == 1 and code_rows("    " + "a" * (room + 1)) == 2


def _case_code_visual_limit(tmp: Path) -> None:
    d = _deck_with(10)
    d.slides[0].code = ["x"] * 11 + [SPL_LONG]
    f = style_findings(d)
    assert len(f) == 1 and "12" in f[0] and "13" in f[0], f
    d.slides[0].code = ["x"] * 10 + [SPL_LONG]
    assert style_findings(d) == []


def _case_long_line_allowed(tmp: Path) -> None:
    d = _deck_with(10)
    d.slides[0].code = [SPL_LONG]
    assert style_findings(d) == []


def _case_heading_too_long(tmp: Path) -> None:
    d = _deck_with(10)
    d.slides[0].heading = " ".join(["h"] * 13)
    assert len(style_findings(d)) == 1
    d.slides[0].heading = " ".join(["h"] * 12)
    assert style_findings(d) == []


def _case_slide_count(tmp: Path) -> None:
    f = style_findings(_deck_with(9))
    assert len(f) == 1 and "11" in f[0], f
    assert style_findings(_deck_with(10)) == []
    top = MAX_SLIDES - GENERATED_SLIDES
    assert style_findings(_deck_with(top)) == []
    f = style_findings(_deck_with(top + 1))
    assert len(f) == 1 and str(MAX_SLIDES + 1) in f[0], f


def _case_dashes(tmp: Path) -> None:
    for ch in (EM_DASH, EN_DASH):
        for place in ("paragraph", "heading", "credit"):
            d = _deck_with(10)
            s = d.slides[0]
            if place == "paragraph":
                s.paragraphs = [f"one{ch}two"]
            elif place == "heading":
                s.heading = f"one{ch}two"
            else:
                s.credit = f"one{ch}two"
            f = style_findings(d)
            assert len(f) == 1 and "dash" in f[0], (ch, place, f)


def _case_spaced_hyphen(tmp: Path) -> None:
    d = _deck_with(10)
    d.slides[0].paragraphs = ["one - two"]
    f = style_findings(d)
    assert len(f) == 1 and "spaced hyphen" in f[0], f
    d = _deck_with(10)
    d.slides[0].code = ["ls - la", "a - b"]
    d.slides[0].paragraphs = ["well-known and -flag"]
    assert style_findings(d) == []


def _case_title_dash(tmp: Path) -> None:
    d = _deck_with(10)
    d.title = f"one{EM_DASH}two"
    f = style_findings(d)
    assert len(f) == 1 and f[0].startswith("d.deck:") and "title" in f[0], f


def _case_promise_spaced_hyphen(tmp: Path) -> None:
    d = _deck_with(10)
    d.promise = "a - b"
    f = style_findings(d)
    assert len(f) == 1 and f[0].startswith("d.deck:") and "promise" in f[0], f
    d.promise = "a-b"
    assert style_findings(d) == []


def _code_deck(code: list[str] | None, section: str = "S") -> Deck:
    sl = Slide(heading="H", section=section, code=code, where="d.deck:5")
    return Deck("d", "T", "howto/t.html", "P.", [sl], "")


def _page(*blocks: str, heading: str = "<h3>S</h3>") -> str:
    pres = "".join(f'<div class="code-block"><pre>{b}</pre></div>' for b in blocks)
    return f"<main>{heading}{pres}</main>"


def _case_excerpt_ok(tmp: Path) -> None:
    html = _page("l1\nl2\nl3\nl4")
    assert guide_findings(_code_deck(["l2", "l3"]), html) == []


def _case_excerpt_gap(tmp: Path) -> None:
    html = _page("l1\nl2\nl3")
    f = guide_findings(_code_deck(["l1", "l3"]), html)
    assert len(f) == 1 and f[0].startswith("d.deck:5"), f


def _case_excerpt_across_blocks(tmp: Path) -> None:
    html = _page("a1\na2", "b1\nb2")
    f = guide_findings(_code_deck(["a2", "b1"]), html)
    assert len(f) == 1 and f[0].startswith("d.deck:5"), f


def _case_excerpt_entities(tmp: Path) -> None:
    html = _page("a &gt; b &amp;&amp; c")
    assert guide_findings(_code_deck(["a > b && c"]), html) == []


def _case_excerpt_trailing_space(tmp: Path) -> None:
    html = _page("x  \ny")
    assert guide_findings(_code_deck(["x", "y"]), html) == []


def _case_excerpt_one_char_changed(tmp: Path) -> None:
    html = _page("index=cloudtrail readOnly=false")
    assert guide_findings(_code_deck(["index=cloudtrail readOnly=false"]), html) == []
    f = guide_findings(_code_deck(["index=cloudtrail readOnly=falsf"]), html)
    assert len(f) == 1, f


def _case_block_labels_basic(tmp: Path) -> None:
    html = (
        '<div class="code-block" data-lang="bash"><pre>mkdir x\ncd x</pre></div>'
        '<div class="code-block"><pre>output one\noutput two</pre></div>'
        "<pre>bare</pre>"
        '<div class="code-block" data-lang="text"><pre>tree one\ntree two</pre></div>'
    )
    assert guide_block_labels(html) == ["bash", None, None, None], guide_block_labels(html)
    assert excerpt_label(html, ["tree two"]) is None
    assert excerpt_label(html, ["cd x"]) == "bash"
    assert excerpt_label(html, ["output two"]) is None
    assert excerpt_label(html, ["not on the page"]) is None


def _case_excerpt_file_basic(tmp: Path) -> None:
    html = (
        '<div class="code-block" data-lang="bash"><pre>'
        "cat &gt; a/b.py &lt;&lt;'EOF'\nx = 1\ny = 2\nEOF\npython3 a/b.py</pre></div>"
        '<div class="code-block" data-lang="bash"><pre>mkdir q\ncd q</pre></div>'
    )
    assert excerpt_file(html, ["x = 1", "y = 2"]) == "a/b.py"
    assert excerpt_file(html, ["y = 2"]) == "a/b.py"
    assert excerpt_file(html, ["python3 a/b.py"]) is None
    assert excerpt_file(html, ["cat > a/b.py <<'EOF'", "x = 1"]) is None
    assert excerpt_file(html, ["cd q"]) is None
    assert excerpt_file(html, ["not on the page"]) is None


def _case_excerpt_file_real(tmp: Path) -> None:
    page = "howto/panther-python-detections.html"
    html = (ROOT / page).read_text(encoding="utf-8")
    first = "# Each of these calls stops, removes or narrows what CloudTrail records."
    got = excerpt_file(html, [first])
    assert got == "rules/trail_tampering.py", (
        f"{page} no longer has the fixture line {first!r} inside its "
        f"rules/trail_tampering.py heredoc (excerpt_file gave {got!r}). If the guide "
        "changed on purpose, point this case at another line in that heredoc; "
        "--check names any outline the change broke"
    )


def _case_excerpt_label_real(tmp: Path) -> None:
    page = "howto/splunk-spl.html"
    html = (ROOT / page).read_text(encoding="utf-8")
    hint = (
        "If the guide changed on purpose, point this case at another line of a block "
        "with that label; --check names any outline the change broke"
    )
    for line, want in (
        ("mkdir -p ~/splunk-lab && cd ~/splunk-lab", "bash"),
        ("index=cloudtrail readOnly=false", "spl"),
    ):
        got = excerpt_label(html, [line])
        assert got == want, f"{page}: fixture line {line!r} has label {got!r}, expected {want!r}. {hint}"
    # Control: the two lists stay aligned, or a label would sit on the wrong block.
    assert len(guide_block_labels(html)) == len(guide_code_blocks(html))


def _case_excerpt_file_two_heredocs(tmp: Path) -> None:
    html = (
        '<div class="code-block" data-lang="bash"><pre>'
        "cat &gt; a.py &lt;&lt;'EOF'\nx = 1\nEOF\n"
        "cat &gt; b.py &lt;&lt;'EOF'\ny = 2\nEOF\npython3 b.py</pre></div>"
    )
    assert excerpt_file(html, ["x = 1"]) == "a.py"
    assert excerpt_file(html, ["y = 2"]) == "b.py"
    # A run that crosses the first terminator is shell input, not one file.
    assert excerpt_file(html, ["EOF", "cat > b.py <<'EOF'"]) is None
    assert excerpt_file(html, ["python3 b.py"]) is None


def _case_section_ok(tmp: Path) -> None:
    html = '<h3 id="step-load">2. Load the lab data</h3>'
    assert guide_headings(html) == {"2. Load the lab data": "step-load"}
    assert guide_findings(_code_deck(None, "2. Load the lab data"), html) == []


def _case_section_with_markup(tmp: Path) -> None:
    html = "<h3>Use <code>stats</code> &amp; count</h3>"
    assert guide_headings(html) == {"Use stats & count": None}
    assert guide_findings(_code_deck(None, "Use stats & count"), html) == []


def _case_section_missing(tmp: Path) -> None:
    f = guide_findings(_code_deck(None, "No such heading"), "<h3>Other</h3>")
    assert len(f) == 1 and f[0].startswith("d.deck:5"), f


# Presentation ids for the cases: Drive file ids are 25 or more characters
# from [A-Za-z0-9_-], which is what the id check accepts.
ID_A = "1" + "A" * 43
ID_B = "1" + "B" * 43

INFO_PAGE = (
    "<main>\n"
    '        <div class="info-box--blue">\n'
    "            <p><strong>Time:</strong> 1 hour</p>\n"
    '            <p class="u-mt-075"><strong>How this page was checked:</strong> run.</p>\n'
    "        </div>\n"
    '        <section id="intro">\n'
    "            <h2>Intro</h2>\n"
    "            <p>First paragraph.</p>\n"
    "        </section>\n"
    "</main>\n"
)
INFO_PAGE_BARE = INFO_PAGE.replace(
    '            <p class="u-mt-075"><strong>How this page was checked:</strong> run.</p>\n',
    "",
)


def _deck_lines(html: str) -> list[str]:
    return [ln for ln in html.split("\n") if "data-howto-deck" in ln]


def _plant(s: str, old: str, new: str) -> str:
    """s with old replaced once; fails when the plant would change nothing."""
    out = s.replace(old, new, 1)
    assert out != s, f"plant did nothing: {old!r}"
    return out


def _case_stamp_insert(tmp: Path) -> None:
    out = stamp_page(INFO_PAGE, ID_A)
    lines = out.split("\n")
    assert _deck_lines(out) == [deck_line_html(ID_A)], out
    assert lines[4] == deck_line_html(ID_A) and lines[5] == "        </div>", out


def _case_stamp_no_checked_line(tmp: Path) -> None:
    out = stamp_page(INFO_PAGE_BARE, ID_A)
    lines = out.split("\n")
    assert lines[3] == deck_line_html(ID_A) and lines[4] == "        </div>", out


def _case_stamp_idempotent(tmp: Path) -> None:
    once = stamp_page(INFO_PAGE, ID_A)
    assert stamp_page(once, ID_A) == once


def _case_stamp_new_id(tmp: Path) -> None:
    out = stamp_page(stamp_page(INFO_PAGE, ID_A), ID_B)
    assert _deck_lines(out) == [deck_line_html(ID_B)], out


def _case_stamp_remove(tmp: Path) -> None:
    assert stamp_page(stamp_page(INFO_PAGE, ID_A), None) == INFO_PAGE


def _case_stamp_no_info_box(tmp: Path) -> None:
    try:
        stamp_page("<main><p>none</p></main>", ID_A)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def _stamp_refused(html: str, pres_id: str | None, needle: str) -> None:
    try:
        stamp_page(html, pres_id)
    except ValueError as e:
        assert needle in str(e), (needle, str(e))
        return
    raise AssertionError(f"stamp_page accepted a page it should refuse ({needle})")


def _case_stamp_normal_form(tmp: Path) -> None:
    """--stamp writes one line, last in the info box, whatever was there."""
    good = stamp_page(INFO_PAGE, ID_A)
    line = deck_line_html(ID_A) + "\n"
    extra = _plant(good, "</main>\n", line + "</main>\n")
    second = _plant(good, "</main>\n", deck_line_html(ID_B) + "\n</main>\n")
    moved = _plant(_plant(good, line, ""), '        <section id="intro">\n', line + '        <section id="intro">\n')
    for planted in (extra, second, moved):
        assert stamp_page(planted, ID_A) == good, planted
        assert stamp_page(planted, None) == INFO_PAGE, planted


def _case_stamp_refuses_unclosed_line(tmp: Path) -> None:
    """A deck line that lost its </p> is refused, never matched to the next
    </p> on the page (which would delete the content in between)."""
    good = stamp_page(INFO_PAGE, ID_A)
    broken = _plant(good, "CC BY-NC 4.0</a>.</p>\n", "CC BY-NC 4.0</a>.\n")
    _stamp_refused(broken, ID_A, "outside a whole deck line")
    _stamp_refused(broken, None, "outside a whole deck line")
    inline = _plant(
        INFO_PAGE, '<div class="info-box--blue">\n',
        '<div class="info-box--blue">' + deck_line_html(ID_A).strip() + "\n",
    )
    _stamp_refused(inline, None, "outside a whole deck line")
    two_on_a_line = _plant(good, ".</p>\n", ".</p>" + deck_line_html(ID_B).strip() + "\n")
    _stamp_refused(two_on_a_line, ID_A, "outside a whole deck line")


def _case_stamp_refuses_info_box_shape(tmp: Path) -> None:
    joined = _plant(INFO_PAGE, "run.</p>\n        </div>\n", "run.</p></div>\n")
    _stamp_refused(joined, ID_A, "first")
    nested = _plant(INFO_PAGE, "            <p><strong>Time", "            <div>x</div>\n            <p><strong>Time")
    _stamp_refused(nested, ID_A, "first")
    # Control: the same page in the expected shape stamps.
    assert deck_line_html(ID_A) in stamp_page(INFO_PAGE, ID_A)


def _case_stamp_refuses_bad_id(tmp: Path) -> None:
    _stamp_refused(INFO_PAGE, 'X" onmouseover="alert(1)', "not a Google Slides presentation id")
    _stamp_refused(INFO_PAGE, "short", "not a Google Slides presentation id")


def _case_links_unmapped_line(tmp: Path) -> None:
    f = link_findings("g", stamp_page(INFO_PAGE, ID_A), {})
    assert len(f) == 1 and "g" in f[0], f


def _case_links_missing_line(tmp: Path) -> None:
    f = link_findings("g", INFO_PAGE, {"g": {"id": ID_A}})
    assert len(f) == 1 and "g" in f[0], f


def _case_links_wrong_id(tmp: Path) -> None:
    f = link_findings("g", stamp_page(INFO_PAGE, ID_A), {"g": {"id": ID_B}})
    assert len(f) == 1, f
    assert link_findings("g", stamp_page(INFO_PAGE, ID_B), {"g": {"id": ID_B}}) == []
    assert link_findings("g", INFO_PAGE, {}) == []


def _case_links_every_line(tmp: Path) -> None:
    """Every deck line on the page is compared, not just the first."""
    good = stamp_page(INFO_PAGE, ID_A)
    m = {"g": {"id": ID_A}}
    assert link_findings("g", good, m) == []
    line = deck_line_html(ID_A) + "\n"
    planted = {
        "duplicate": (_plant(good, "</main>\n", line + "</main>\n"), "2 deck lines"),
        "second id": (_plant(good, "</main>\n", deck_line_html(ID_B) + "\n</main>\n"), "2 deck lines"),
        "moved": (
            _plant(_plant(good, line, ""), '        <section id="intro">\n', line + '        <section id="intro">\n'),
            "not where --stamp puts it",
        ),
        "unclosed": (_plant(good, "CC BY-NC 4.0</a>.</p>\n", "CC BY-NC 4.0</a>.\n"), "outside a whole deck line"),
    }
    for label, (html, needle) in planted.items():
        f = link_findings("g", html, m)
        assert any(needle in x for x in f), (label, f)


def _case_links_unmapped_markup(tmp: Path) -> None:
    """A page with no mapping entry may hold no deck markup and no Slides
    link anywhere, inline or not."""
    inline = _plant(
        INFO_PAGE, '<div class="info-box--blue">\n',
        '<div class="info-box--blue">' + deck_line_html(ID_A).strip() + "\n",
    )
    f = link_findings("g", inline, {})
    assert any("outside a whole deck line" in x for x in f), f
    prose = _plant(
        INFO_PAGE, "<p>First paragraph.</p>",
        f'<p>See <a href="https://docs.google.com/presentation/d/{ID_B}/edit">the slides</a>.</p>',
    )
    f = link_findings("g", prose, {})
    assert len(f) == 1 and "outside its deck line" in f[0], f
    f = link_findings("g", stamp_page(prose, ID_A), {"g": {"id": ID_A}})
    assert len(f) == 1 and "outside its deck line" in f[0], f


def _case_links_bad_entry(tmp: Path) -> None:
    """A malformed entry is mapping_findings' to report; link_findings must
    neither crash on it nor stamp-compare against it."""
    good = stamp_page(INFO_PAGE, ID_A)
    assert link_findings("g", good, {"g": {}}) == []
    assert link_findings("g", good, {"g": {"id": 'X" onmouseover="alert(1)'}}) == []
    assert link_findings("g", good, {"g": "not an object"}) == []


def _entry(pres_id: str = ID_A, sha: str = "0" * 64, published: str = "2026-01-02") -> dict:
    return {"id": pres_id, "outline_sha256": sha, "published": published}


def _case_mapping_findings(tmp: Path) -> None:
    with _rooted(tmp):
        ok = {"g": _entry()}
        assert mapping_findings(ok, {"g"}, {"g"}) == []
        planted = {
            "markup id": ({"g": _entry(pres_id='X" onmouseover="alert(1)')}, "not a Google Slides"),
            "no id": ({"g": {"outline_sha256": "0" * 64, "published": "2026-01-02"}}, "keys must be exactly"),
            "extra key": ({"g": {**_entry(), "note": "x"}}, "keys must be exactly"),
            "bad date": ({"g": _entry(published="20 Nov 2026")}, "not a YYYY-MM-DD date"),
            "impossible date": ({"g": _entry(published="2026-02-30")}, "not a YYYY-MM-DD date"),
            "bad sha": ({"g": _entry(sha="abc")}, "not a sha256"),
            "not an object": ({"g": ["x"]}, "must be an object"),
            "bad slug": ({"../g": _entry()}, "not a guide slug"),
        }
        for label, (m, needle) in planted.items():
            f = mapping_findings(m, {"g"}, {"g"})
            assert any(needle in x for x in f), (label, f)
        f = mapping_findings(ok, set(), {"g"})
        assert len(f) == 1 and "has no outline" in f[0], f
        f = mapping_findings(ok, {"g"}, set())
        assert len(f) == 1 and "names no howto page" in f[0], f


@contextlib.contextmanager
def _rooted(root: Path):
    """Point every path at root for the body of the with block."""
    old = _set_root(root)
    try:
        yield root
    finally:
        _set_root(old)


def _capture(fn, *args) -> tuple[int, str]:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = fn(*args)
    return rc, buf.getvalue()


def _outline(slug: str, slides: int = 10) -> str:
    body = "".join(f"== Slide {i}\nText {i}.\n\n" for i in range(slides))
    return f"title: T\nguide: howto/{slug}.html\npromise: P.\n\n{body}"


def _hub_card(slug: str, name: str) -> str:
    """One guide card as cloud-security-how-to.html writes it, without a deck."""
    return (
        '                <div class="resource-card" data-icon="\N{TELESCOPE}">\n'
        f'                    <h3><a href="howto/{slug}.html">{name}</a></h3>\n'
        f"                    <p>Learn {name} from zero.</p>\n"
        '                    <div class="resource-tags"><span class="tag">Beginner</span></div>\n'
        "                </div>\n"
    )


def _hub(*cards: str) -> str:
    return (
        "<html><body><main>\n            <div class=\"resource-grid\">\n"
        + "".join(cards)
        + "            </div>\n</main></body></html>\n"
    )


def _tree(root: Path, outlines: dict[str, str], pages: dict[str, str], mapping: dict | None) -> Path:
    """A scratch repository: outlines in tools/decks/, pages in howto/, a
    guides hub with one plain card per page, and published.json when mapping
    is given."""
    decks = root / "tools" / "decks"
    decks.mkdir(parents=True)
    (root / "howto").mkdir()
    for slug, text in outlines.items():
        (decks / f"{slug}.deck").write_text(text, encoding="utf-8")
    for slug, html in pages.items():
        (root / "howto" / f"{slug}.html").write_text(html, encoding="utf-8")
    hub_cards = "".join(_hub_card(slug, f"Guide {slug}") for slug in pages)
    (root / "cloud-security-how-to.html").write_text(_hub(hub_cards), encoding="utf-8")
    if mapping is not None:
        (decks / "published.json").write_text(
            json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return root


def _snapshot(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): p.read_text(encoding="utf-8")
        for p in sorted(root.rglob("*")) if p.is_file()
    }


def _case_stamp_all_or_nothing(tmp: Path) -> None:
    """One page --stamp cannot stamp stops the run before anything is
    written, and every error is listed, not just the first."""
    pages = {"aa": "<main><p>no info box</p></main>\n", "bb": INFO_PAGE, "cc": "<main></main>\n"}
    _tree(tmp, {s: _outline(s) for s in pages}, pages, {s: _entry() for s in pages})
    before = _snapshot(tmp)
    with _rooted(tmp):
        rc, out = _capture(stamp_all)
    assert rc == 1 and "nothing written" in out, out
    assert "howto/aa.html" in out and "howto/cc.html" in out, out
    assert _snapshot(tmp) == before, "a refused --stamp wrote files"
    # Control: with every page stampable, all are stamped, the hub with them,
    # and a second run changes nothing.
    for s in ("aa", "cc"):
        (tmp / "howto" / f"{s}.html").write_text(INFO_PAGE, encoding="utf-8")
    with _rooted(tmp):
        rc, out = _capture(stamp_all)
        assert rc == 0 and out.count("stamped") == 4 and "stamped cloud-security-how-to.html" in out, out
        once = _snapshot(tmp)
        rc, out = _capture(stamp_all)
        assert rc == 0 and out == "" and _snapshot(tmp) == once, out


def _case_record_refusals(tmp: Path) -> None:
    """--record validates its arguments and the pages before it writes, so a
    refusal leaves the mapping and every page untouched."""
    pages = {"aa": "<main><p>no info box</p></main>\n", "bb": INFO_PAGE}
    _tree(tmp, {s: _outline(s) for s in pages}, pages, {})
    before = _snapshot(tmp)
    with _rooted(tmp):
        for args, needle in (
            (("aa", ID_A), "howto/aa.html"),
            (("bb", 'X" onmouseover="alert(1)'), "not a Google Slides presentation id"),
            (("../bb", ID_A), "no outline"),
            (("zz", ID_A), "no outline"),
        ):
            rc, out = _capture(record, *args)
            assert rc == 1 and needle in out, (args, out)
            assert _snapshot(tmp) == before, f"a refused --record {args} wrote files"
        # Control: a valid record writes the entry and stamps the page.
        rc, out = _capture(record, "bb", ID_A)
    assert rc == 0, out
    m = json.loads((tmp / "tools/decks/published.json").read_text(encoding="utf-8"))
    assert m["bb"]["id"] == ID_A and _is_iso_date(m["bb"]["published"]), m
    assert deck_line_html(ID_A) in (tmp / "howto/bb.html").read_text(encoding="utf-8")


def _strip_lines(html: str) -> list[str]:
    return [ln for ln in html.splitlines() if "data-howto-hub-deck" in ln]


def _case_hub_stamp_decks_mapped_cards(tmp: Path) -> None:
    """A guide card on the hub whose guide is published ends with the deck's
    links and a closed preview; every other card, and everything outside the
    cards, is left exactly as it was."""
    plain = _hub(_hub_card("kusto-kql", "Kusto Query Language (KQL)"), _hub_card("splunk-spl", "Splunk SPL &amp; more"))
    out = stamp_hub(plain, {"kusto-kql": {"id": ID_A}})
    strip = _strip_lines(out)
    assert len(strip) == 2, out
    # The id appears in the PDF and copy links, the preview's data-src and
    # its no-script link; the preview starts closed.
    assert out.count(ID_A) == 4 and 'title="Preview of the Kusto Query Language (KQL) slides"' in out, out
    assert strip[0].startswith('                    <p class="deck-actions" data-howto-hub-deck><strong>Slides:</strong> ')
    assert strip[1].startswith('                    <details class="deck-preview" data-howto-hub-deck><summary>')
    assert " open" not in out
    # The strip is the card's last two lines, and taking it out gives back
    # the plain hub byte for byte.
    lines = out.splitlines()
    i = lines.index(strip[0])
    assert lines[i + 1] == strip[1] and lines[i + 2] == "                </div>", lines[i - 3: i + 3]
    assert "\n".join(ln for ln in lines if ln not in strip) + "\n" == plain
    # The h3 keeps its entities as written.
    both = stamp_hub(plain, {"kusto-kql": {"id": ID_A}, "splunk-spl": {"id": ID_B}})
    assert 'title="Preview of the Splunk SPL &amp; more slides"' in both, both
    # An entry with no well-formed id decks nothing.
    assert stamp_hub(plain, {"kusto-kql": {"id": "short"}}) == plain


def _case_hub_stamp_reverses_and_is_idempotent(tmp: Path) -> None:
    plain = _hub(_hub_card("kusto-kql", "KQL"), _hub_card("splunk-spl", "SPL"))
    once = stamp_hub(plain, {"kusto-kql": {"id": ID_A}})
    assert once != plain and stamp_hub(once, {"kusto-kql": {"id": ID_A}}) == once
    assert stamp_hub(once, {}) == plain
    swapped = stamp_hub(once, {"kusto-kql": {"id": ID_B}})
    assert swapped.count(ID_B) == 4 and ID_A not in swapped, swapped
    # A card with more attributes on its box survives the round trip.
    odd = plain.replace('<div class="resource-card" data-icon=', '<div class="resource-card" data-y="2" data-icon=', 1)
    assert odd != plain and stamp_hub(stamp_hub(odd, {"kusto-kql": {"id": ID_A}}), {}) == odd
    # A card that is not a guide card is never touched.
    other = plain.replace("</main>", _hub_card("x", "X").replace('href="howto/x.html"', 'href="news.html"') + "</main>")
    assert stamp_hub(other, {"x": {"id": ID_A}, "news": {"id": ID_A}}) == other
    # The attribute outside a decked card is refused, and so is a card of neither form.
    stray = plain.replace("<main>", '<main>\n<p class="x" data-howto-hub-deck>x</p>', 1)
    broken = once.replace("</details>", "", 1)
    moved = once.replace("                    <div class=\"resource-tags\">", "                    <div class=\"resource-tags\">"
                         ).replace(_strip_lines(once)[1] + "\n", "", 1).replace(
                         "                    <p>Learn KQL", _strip_lines(once)[1] + "\n                    <p>Learn KQL", 1)
    for html, mapping, needle in ((stray, {}, "data-howto-hub-deck"),
                                  (broken, {"kusto-kql": {"id": ID_A}}, "kusto-kql"),
                                  (moved, {"kusto-kql": {"id": ID_A}}, "kusto-kql")):
        try:
            stamp_hub(html, mapping)
        except ValueError as e:
            assert needle in str(e), e
        else:
            raise AssertionError(f"stamp_hub accepted a hub with {needle}")


def _case_hub_findings(tmp: Path) -> None:
    plain = _hub(_hub_card("kusto-kql", "KQL"), _hub_card("splunk-spl", "SPL"))
    mapping = {"kusto-kql": {"id": ID_A}}
    good = stamp_hub(plain, mapping)
    assert hub_findings(good, mapping) == [] and hub_findings(plain, {}) == []

    def only(found: list[str], *needles: str) -> None:
        assert len(found) == 1 and all(n in found[0] for n in needles), found

    only(hub_findings(plain, mapping), "cloud-security-how-to.html", "kusto-kql", "no deck")
    only(hub_findings(good.replace(ID_A, ID_B, 1), mapping), "kusto-kql", "wrong")
    only(hub_findings(good, {"kusto-kql": {"id": ID_A}, "splunk-spl": {"id": ID_B}}), "splunk-spl", "no deck")
    only(hub_findings(good, {}), "kusto-kql", "not published")
    only(hub_findings(good.replace("Editable copy</a></p>\n", "Editable copy</a>\n", 1), mapping), "kusto-kql", "malformed")
    link = f"https://docs.google.com/presentation/d/{ID_B}/copy"
    only(hub_findings(good.replace("<p>Learn SPL", f'<p><a href="{link}">Slides</a> Learn SPL'), mapping),
         "docs.google.com/presentation")
    # A published guide with no card on the hub: the card was dropped, or no
    # longer reads as a guide card, so nothing would show its deck.
    only(hub_findings(good, {**mapping, "falco-rules": {"id": ID_B}}), "falco-rules", "no card")
    gone = good.replace('<div class="resource-card" data-icon=', '<div class="resource-card resource-card--x" data-icon=')
    found = hub_findings(gone, mapping)
    assert any("kusto-kql" in f and "no card" in f for f in found), found
    # Control: the strip's own links are not strays, and a clean hub stays clean.
    assert hub_findings(good, mapping) == []


def _case_hub_wired_into_stamp_and_check(tmp: Path) -> None:
    """--record and --stamp rewrite the hub with the guide pages, --check
    reads it, and a hub --stamp cannot read stops the run before anything is
    written."""
    pages = {"aa": INFO_PAGE, "bb": INFO_PAGE}
    _tree(tmp, {s: _outline(s) for s in pages}, pages, {})
    hub, mpath = tmp / "cloud-security-how-to.html", tmp / "tools/decks/published.json"
    plain_hub = hub.read_text(encoding="utf-8")
    with _rooted(tmp):
        rc, out = _capture(record, "aa", ID_A)
        assert rc == 0 and "stamped cloud-security-how-to.html" in out, out
        decked = hub.read_text(encoding="utf-8")
        assert decked == stamp_hub(plain_hub, {"aa": {"id": ID_A}}) and decked != plain_hub, decked
        rc, out = _capture(check_all)
        assert "cloud-security-how-to.html" not in out, out
        # A hub out of step with the mapping fails --check, naming the hub.
        hub.write_text(_plant(decked, f"d/{ID_A}/embed", f"d/{ID_B}/embed"), encoding="utf-8")
        rc, out = _capture(check_all)
        assert rc == 1 and "cloud-security-how-to.html" in out and "aa" in out, out
        # A malformed hub stops --stamp before it writes the hub or any page.
        m = json.loads(mpath.read_text(encoding="utf-8"))
        m["aa"]["id"] = ID_B
        mpath.write_text(json.dumps(m, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        broken = _plant(decked, "</summary>", "</summary>\n")
        hub.write_text(broken, encoding="utf-8")
        before = _snapshot(tmp)
        rc, out = _capture(stamp_all)
        assert rc == 1 and "cloud-security-how-to.html" in out and _snapshot(tmp) == before, out
        # So does a missing hub, and --check names it too.
        hub.unlink()
        rc, out = _capture(stamp_all)
        assert rc == 1 and "cloud-security-how-to.html" in out, out
        rc, out = _capture(check_all)
        assert rc == 1 and "cloud-security-how-to.html" in out, out
        # Control: with the hub mended, the same --stamp moves page and hub to the new id.
        hub.write_text(decked, encoding="utf-8")
        rc, out = _capture(stamp_all)
        assert rc == 0, out
        page = (tmp / "howto/aa.html").read_text(encoding="utf-8")
        assert ID_B in page and ID_A not in page, page
        assert hub.read_text(encoding="utf-8") == stamp_hub(plain_hub, {"aa": {"id": ID_B}})


def _case_crosslink_skips_hub_deck_lines(tmp: Path) -> None:
    """The glossary cross-linker never links inside the hub strip, so
    --check keeps matching what --stamp wrote, while the same term in the
    hub's prose still takes its link."""
    import crosslink_pages as cp

    key = "Slides"
    patterns, slugs = cp.build_term_regexes([key]), {key.lower(): "term-slides"}
    link = '<a class="glossary-link" href="glossary.html#term-slides">Slides</a>'
    hub = stamp_hub(_hub(_hub_card("kusto-kql", "KQL")), {"kusto-kql": {"id": ID_A}})
    hub = hub.replace("</main>", "<p>Read the Slides first.</p>\n</main>")
    strip = _strip_lines(hub)
    assert "Slides" in strip[0], strip
    page = tmp / "x.html"
    old = cp.REPO_ROOT
    cp.REPO_ROOT = tmp
    try:
        page.write_text(hub.replace("Preview the slides", "Preview the Slides"), encoding="utf-8")
        cp.crosslink_page(page, patterns, slugs)
        once = page.read_text(encoding="utf-8")
        lines = once.splitlines()
        assert strip[0] in lines, once
        assert not any(link in ln for ln in lines if "data-howto-hub-deck" in ln), once
        assert once.count(link) == 1 and link in next(ln for ln in lines if "Read the" in ln), once
        # Control: without its attribute the strip takes the link.
        page.write_text(hub.replace(" data-howto-hub-deck>", ">", 1), encoding="utf-8")
        cp.crosslink_page(page, patterns, slugs)
        assert link in next(ln for ln in page.read_text(encoding="utf-8").splitlines() if "deck-actions" in ln)
    finally:
        cp.REPO_ROOT = old


def _case_paths_from_any_cwd(tmp: Path) -> None:
    """Paths come from this file's location, so another working directory
    sees the same outlines and pages."""
    assert ROOT.is_absolute() and DECKS_DIR.is_absolute() and HOWTO_DIR.is_absolute()
    here = os.getcwd()
    os.chdir(tmp)
    try:
        assert outline_paths() and guide_pages(), "no outlines or pages found from another directory"
        assert tree_problem() is None
    finally:
        os.chdir(here)


def _case_empty_tree_refused(tmp: Path) -> None:
    """With nothing to read, every mode that reads the tree exits 1 rather
    than report on nothing."""
    (tmp / "tools" / "decks").mkdir(parents=True)
    (tmp / "howto").mkdir()
    with _rooted(tmp):
        for fn in (check_all, stale_report, status_report, stamp_all):
            rc, out = _capture(fn)
            assert rc == 1 and "no outlines found" in out, (fn.__name__, out)
        rc, out = _capture(record, "aa", ID_A)
        assert rc == 1, out


def _case_stale_report(tmp: Path) -> None:
    outlines = {s: _outline(s) for s in ("aa", "bb", "cc")}
    pages = {s: INFO_PAGE for s in outlines}
    _tree(tmp, outlines, pages, None)
    with _rooted(tmp):
        sha = {s: outline_sha256(parse_outline(DECKS_DIR / f"{s}.deck")) for s in outlines}
        mapping = {"aa": _entry(sha=sha["aa"]), "bb": _entry(sha="f" * 64), "dd": _entry()}
        save_mapping(mapping)
        rc, out = _capture(stale_report, True)
        assert rc == 0, out
        assert out.splitlines() == [
            "bb: outline changed since it was published on 2026-01-02; "
            "the public deck needs re-publishing",
            "dd: published, but tools/decks/dd.deck is missing",
            "stale check: 2 of 3 published decks changed since publishing",
        ], out
        rc, out = _capture(stale_report, False)
        assert rc == 0 and "cc: not published" in out and "outlines never published: 1" in out, out
        # Control: with every published outline matching, nothing is listed.
        save_mapping({"aa": _entry(sha=sha["aa"])})
        rc, out = _capture(stale_report, True)
        assert rc == 0 and out.splitlines() == [
            "stale check: 0 of 1 published decks changed since publishing"
        ], out
        MAPPING.write_text("{not json", encoding="utf-8")
        rc, out = _capture(stale_report, True)
        assert rc == 1 and "cannot be read as JSON" in out, out


def _case_include_bare_name(tmp: Path) -> None:
    decks = tmp / "decks"
    decks.mkdir()
    (tmp / "_outside.deck").write_text(STUB)
    (decks / "_inside.deck").write_text(STUB)
    for name in ("../_outside.deck", str(tmp / "_outside.deck"), "sub/_inside.deck", "inside.deck"):
        _raises(
            lambda name=name: parse_outline_text(_hdr(f"== include: {name}\n"), "d.deck", decks),
            "bare _name.deck",
        )
    # Control: the bare name of a fragment beside the outline is spliced.
    d = parse_outline_text(_hdr("== include: _inside.deck\n"), "d.deck", decks)
    assert [s.heading for s in d.slides] == ["Fragment slide"]


def _case_missing_include(tmp: Path) -> None:
    _raises(
        lambda: parse_outline_text(_hdr("== include: _nope.deck\n"), "d.deck", tmp),
        "include file not found",
    )


def _case_fragment_rules(tmp: Path) -> None:
    (tmp / "_header.deck").write_text("title: T\n== S\nText.\n")
    _raises(
        lambda: parse_outline_text(_hdr("== include: _header.deck\n"), "d.deck", tmp),
        "_header.deck:1: text before the first slide",
    )
    (tmp / "_prose.deck").write_text("\nStray prose.\n== S\nText.\n")
    _raises(
        lambda: parse_outline_text(_hdr("== include: _prose.deck\n"), "d.deck", tmp),
        "_prose.deck:2: text before the first slide",
    )


def _case_duplicate_keys(tmp: Path) -> None:
    _raises(
        lambda: parse_outline_text("title: T\ntitle: U\nguide: g\npromise: P.\n\n== S\nText.\n", "d.deck", tmp),
        "given twice",
    )
    _raises(
        lambda: parse_outline_text(_hdr("== S\nsection: A\nsection: B\nText.\n"), "d.deck", tmp),
        "two section lines",
    )
    _raises(
        lambda: parse_outline_text(_hdr("== S\ncredit: A\ncredit: B\nText.\n"), "d.deck", tmp),
        "two credit lines",
    )
    _raises(
        lambda: parse_outline_text("title: T\nguide: g\npromise: P.\nStray.\n== S\nText.\n", "d.deck", tmp),
        "d.deck:4:",
    )


def _case_empty_fields(tmp: Path) -> None:
    for body, needle in (
        ("== S\nText.\n```\n```\n", "empty code block"),
        ("== S\nText.\n```sh\n\n```\n", "empty code block"),
        ("== S\nsection:\nText.\n", "empty section line"),
        ("== S\nsection:   \nText.\n", "empty section line"),
        ("== S\ncredit:\nText.\n", "empty credit line"),
        ("== S\nText.\n-\n", "empty bullet"),
    ):
        _raises(lambda body=body: parse_outline_text(_hdr(body), "d.deck", tmp), needle)
    # Control: the same fields with values parse.
    d = parse_outline_text(_hdr("== S\nsection: A\ncredit: B\n- c\n```sh\nls\n```\n"), "d.deck", tmp)
    s = d.slides[0]
    assert (s.section, s.credit, s.bullets, s.code) == ("A", "B", ["c"], ["ls"]), s


def _case_prose_after_bullet(tmp: Path) -> None:
    text = _hdr("== S\nThe answer has three parts:\n- first\n- second\nSo parse first.\n- third\n")
    s = parse_outline_text(text, "d.deck", tmp).slides[0]
    assert s.paragraphs == ["The answer has three parts:", "So parse first."]
    deck = _deck_with(10)
    deck.slides[0] = s
    f = [x for x in style_findings(deck) if "prose after a bullet" in x]
    # Line 9 of the outline: four header lines, the heading, then three lines.
    assert len(f) == 1 and f[0].startswith("d.deck:9:"), f
    # Control: prose before the bullets, in one or more paragraphs, is fine.
    text = _hdr("== S\nIntro.\n\nMore intro.\n- first\n- second\n")
    deck.slides[0] = parse_outline_text(text, "d.deck", tmp).slides[0]
    assert style_findings(deck) == [], style_findings(deck)


def _case_run_cases_reports(tmp: Path) -> None:
    def planted(_tmp: Path) -> None:
        raise AssertionError("the planted reason")

    rc, out = _capture(_run_cases, [("planted_case", planted)], "t")
    assert rc == 1, out
    assert out.startswith("t FAILED: planted_case (build_howto_decks.py:"), out
    assert "AssertionError: the planted reason" in out, out
    rc, out = _capture(_run_cases, [("ok", lambda _tmp: None)], "t")
    assert rc == 0 and "1 cases passed" in out, out


def _case_sha_changes(tmp: Path) -> None:
    a = _deck_with(12, "One word here.")
    b = _deck_with(12, "One ward here.")
    a.resolved_text = "one word"
    b.resolved_text = "one ward"
    assert outline_sha256(a) != outline_sha256(b)
    assert outline_sha256(a) == outline_sha256(a)


CASES: list = [
    ("parse_ok", _case_parse_ok),
    ("include_spliced", _case_include_spliced),
    ("nested_include", _case_nested_include),
    ("include_bare_name", _case_include_bare_name),
    ("missing_include", _case_missing_include),
    ("fragment_rules", _case_fragment_rules),
    ("missing_header", _case_missing_header),
    ("unknown_header_key", _case_unknown_header_key),
    ("duplicate_keys", _case_duplicate_keys),
    ("unterminated_fence", _case_unterminated_fence),
    ("two_fences", _case_two_fences),
    ("empty_slide", _case_empty_slide),
    ("empty_fields", _case_empty_fields),
    ("fence_hides_slide_marker", _case_fence_hides_slide_marker),
    ("prose_after_bullet", _case_prose_after_bullet),
    ("too_many_words", _case_too_many_words),
    ("too_many_code_lines", _case_too_many_code_lines),
    ("code_rows_basic", _case_code_rows_basic),
    ("code_rows_words", _case_code_rows_words),
    ("code_visual_limit", _case_code_visual_limit),
    ("long_line_allowed", _case_long_line_allowed),
    ("heading_too_long", _case_heading_too_long),
    ("slide_count", _case_slide_count),
    ("dashes", _case_dashes),
    ("spaced_hyphen", _case_spaced_hyphen),
    ("title_dash", _case_title_dash),
    ("promise_spaced_hyphen", _case_promise_spaced_hyphen),
    ("excerpt_ok", _case_excerpt_ok),
    ("excerpt_gap", _case_excerpt_gap),
    ("excerpt_across_blocks", _case_excerpt_across_blocks),
    ("excerpt_entities", _case_excerpt_entities),
    ("excerpt_trailing_space", _case_excerpt_trailing_space),
    ("excerpt_one_char_changed", _case_excerpt_one_char_changed),
    ("block_labels_basic", _case_block_labels_basic),
    ("excerpt_label_real", _case_excerpt_label_real),
    ("excerpt_file_basic", _case_excerpt_file_basic),
    ("excerpt_file_two_heredocs", _case_excerpt_file_two_heredocs),
    ("excerpt_file_real", _case_excerpt_file_real),
    ("section_ok", _case_section_ok),
    ("section_with_markup", _case_section_with_markup),
    ("section_missing", _case_section_missing),
    ("stamp_insert", _case_stamp_insert),
    ("stamp_no_checked_line", _case_stamp_no_checked_line),
    ("stamp_idempotent", _case_stamp_idempotent),
    ("stamp_new_id", _case_stamp_new_id),
    ("stamp_remove", _case_stamp_remove),
    ("stamp_no_info_box", _case_stamp_no_info_box),
    ("stamp_normal_form", _case_stamp_normal_form),
    ("stamp_refuses_unclosed_line", _case_stamp_refuses_unclosed_line),
    ("stamp_refuses_info_box_shape", _case_stamp_refuses_info_box_shape),
    ("stamp_refuses_bad_id", _case_stamp_refuses_bad_id),
    ("links_unmapped_line", _case_links_unmapped_line),
    ("links_missing_line", _case_links_missing_line),
    ("links_wrong_id", _case_links_wrong_id),
    ("links_every_line", _case_links_every_line),
    ("links_unmapped_markup", _case_links_unmapped_markup),
    ("links_bad_entry", _case_links_bad_entry),
    ("mapping_findings", _case_mapping_findings),
    ("stamp_all_or_nothing", _case_stamp_all_or_nothing),
    ("record_refusals", _case_record_refusals),
    ("hub_stamp_decks_mapped_cards", _case_hub_stamp_decks_mapped_cards),
    ("hub_stamp_reverses_and_is_idempotent", _case_hub_stamp_reverses_and_is_idempotent),
    ("hub_findings", _case_hub_findings),
    ("hub_wired_into_stamp_and_check", _case_hub_wired_into_stamp_and_check),
    ("crosslink_skips_hub_deck_lines", _case_crosslink_skips_hub_deck_lines),
    ("paths_from_any_cwd", _case_paths_from_any_cwd),
    ("empty_tree_refused", _case_empty_tree_refused),
    ("stale_report", _case_stale_report),
    ("run_cases_reports", _case_run_cases_reports),
    ("sha_changes", _case_sha_changes),
]


# Render cases need python-pptx, so they stay out of CASES (which CI runs
# without it) and run only under --self-test-render.
def _render_deck(n: int = 10, **slide_kw) -> Deck:
    slides = [
        Slide(
            heading=f"Slide {i}",
            section="Setup" if i % 2 else None,
            paragraphs=["A short line of prose."],
            bullets=["One point", "Another point"],
            code=["index=main | head 5"],
            credit="Source: example",
            where=f"d.deck:{i}",
            **slide_kw,
        )
        for i in range(n)
    ]
    return Deck("d", "A deck title", "howto/d.html", "One sentence promise.", slides, "")


def _reopen(path: Path):
    from pptx import Presentation

    return Presentation(str(path))


def _slide_text(slide) -> str:
    return "\n".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def _case_render_ok(tmp: Path) -> None:
    import howto_deck_render as r

    deck = _render_deck()
    out = r.render_deck(deck, tmp / "d.pptx", {"Setup": "setup"})
    assert r.verify_pptx(out, deck) == [], r.verify_pptx(out, deck)
    prs = _reopen(out)
    assert len(prs.slides) == 12, len(prs.slides)
    assert (prs.slide_width, prs.slide_height) == (12192000, 6858000)
    for i, sl in enumerate(prs.slides, start=1):
        assert "csoh.org/howto/d.html" in _slide_text(sl), i
        assert f"{i} / 12" in _slide_text(sl), i
        assert sl.notes_slide.notes_text_frame.text.strip(), i
    first, last = _slide_text(prs.slides[0]), _slide_text(prs.slides[-1])
    for want in ("A deck title", "One sentence promise.", r.ATTRIBUTION, r.LICENSE_LINE):
        assert want in first, want
    assert r.CLOSING_HEADING in last and "https://csoh.org/howto/d.html" in last
    assert r.CLOSING_LICENSE in last


def _case_render_notes(tmp: Path) -> None:
    import howto_deck_render as r

    deck = _render_deck(3)
    deck.slides[0].section = "Setup"
    deck.slides[1].section = "No id"
    deck.slides[2].section = None
    out = r.render_deck(deck, tmp / "d.pptx", {"Setup": "setup", "No id": None})
    notes = [s.notes_slide.notes_text_frame.text for s in _reopen(out).slides]
    base = "https://csoh.org/howto/d.html"
    assert notes[1] == f"Guide section: {base}#setup", notes[1]
    assert notes[2] == f'Guide section: "No id" at {base}', notes[2]
    assert notes[3] == f"Full guide: {base}", notes[3]
    assert notes[0] == notes[4] == f"Full guide: {base}", notes
    out2 = r.render_deck(deck, tmp / "e.pptx")
    n2 = _reopen(out2).slides[1].notes_slide.notes_text_frame.text
    assert n2 == f'Guide section: "Setup" at {base}', n2


def _case_render_overflow(tmp: Path) -> None:
    import howto_deck_render as r

    def one(code_lines: int, paras: int) -> Deck:
        s = Slide(
            heading="A heading that wraps onto a second line because it is long enough",
            section="Setup",
            paragraphs=["five words in this line"] * paras,
            code=["x = 1"] * code_lines,
            where="over.deck:7",
        )
        return Deck("d", "T", "howto/d.html", "P.", [s] * 10, "")

    try:
        r.render_deck(one(12, 8), tmp / "o.pptx")
    except r.LayoutError as e:
        assert "over.deck:7" in str(e), e
    else:
        raise AssertionError("LayoutError was not raised")
    assert not (tmp / "o.pptx").exists()
    # Control: the same slide with little on it must fit.
    r.render_deck(one(3, 1), tmp / "ok.pptx")


def _case_render_wrapped_code(tmp: Path) -> None:
    import howto_deck_render as r

    deck = _render_deck()
    deck.slides[1].code = ["x = 1"] * 10 + [SPL_LONG]
    # Twelve code rows at 16 pt fill the slide, so it carries no other prose.
    deck.slides[1].paragraphs, deck.slides[1].bullets = [], []
    out = r.render_deck(deck, tmp / "w.pptx", {})
    assert r.verify_pptx(out, deck) == [], r.verify_pptx(out, deck)
    # Slide 0 of the file is the title slide, so deck slide 1 is file slide 2.
    code = [sh for sh in _reopen(out).slides[2].shapes if sh.name == "code"]
    assert len(code) == 1
    tf = code[0].text_frame
    assert tf.word_wrap is True
    assert SPL_LONG in [p.text for p in tf.paragraphs]


def _case_render_fonts(tmp: Path) -> None:
    import howto_deck_render as r

    # Raising code_pt without lowering CODE_WRAP_COLS would overflow the box.
    assert CODE_WRAP_COLS * 0.6 * r.STYLE["code_pt"] / 72 <= r.STYLE["w"] - 2 * r.STYLE["code_pad"]
    # 14 pt is the floor for code that a room can read from a projector.
    assert r.STYLE["code_pt"] >= 14, f"code is {r.STYLE['code_pt']} pt, below the 14 pt floor"
    deck = _render_deck()
    out = r.render_deck(deck, tmp / "d.pptx", {})
    small = {"footer-left", "footer-right", "guide-line", "credit"}
    seen_code = seen_body = 0
    for sl in _reopen(out).slides:
        for sh in sl.shapes:
            if not sh.has_text_frame:
                continue
            for p in sh.text_frame.paragraphs:
                for run in p.runs:
                    if sh.name == "code":
                        seen_code += 1
                        assert run.font.size.pt == r.STYLE["code_pt"], run.font.size.pt
                    elif sh.name not in small:
                        seen_body += 1
                        assert run.font.size.pt >= 18, (sh.name, run.font.size.pt)
    assert seen_code and seen_body
    # Control: a body run shrunk to 12 pt in the saved file must be reported.
    prs = _reopen(out)
    for sh in prs.slides[1].shapes:
        if sh.name == "body":
            from pptx.util import Pt

            sh.text_frame.paragraphs[0].runs[0].font.size = Pt(12)
    bad = tmp / "bad.pptx"
    prs.save(str(bad))
    found = r.verify_pptx(bad, deck)
    assert any("below 18" in f for f in found), found


def _case_render_code_label(tmp: Path) -> None:
    import howto_deck_render as r

    deck = _render_deck(10)
    deck.slides[1].code_label = "spl"
    out = r.render_deck(deck, tmp / "l.pptx", {})
    assert r.verify_pptx(out, deck) == [], r.verify_pptx(out, deck)
    prs = _reopen(out)
    shapes = prs.slides[2].shapes
    tabs = [sh for sh in shapes if sh.name == "code-label"]
    assert len(tabs) == 1
    tab = tabs[0]
    box = next(sh for sh in shapes if sh.name == "code")
    assert tab.text_frame.text == "SPL", tab.text_frame.text
    assert tab.top < box.top < tab.top + tab.height, (tab.top, box.top, tab.height)
    assert tab.left == box.left
    # The first code row starts one pad below the box top, clear of the tab.
    first_row = box.top + int(r.STYLE["code_pad"] * 914400)
    assert tab.top + tab.height < first_row
    # Control: a slide whose code has no label gets no tab.
    assert not [sh for sh in prs.slides[3].shapes if sh.name == "code-label"]


def _case_render_code_file(tmp: Path) -> None:
    import howto_deck_render as r

    deck = _render_deck(10)
    deck.slides[1].code_label = "bash"
    deck.slides[1].code_file = "rules/Trail_tampering.py"
    out = r.render_deck(deck, tmp / "f.pptx", {})
    assert r.verify_pptx(out, deck) == [], r.verify_pptx(out, deck)
    prs = _reopen(out)
    tabs = [sh for sh in prs.slides[2].shapes if sh.name == "code-label"]
    assert len(tabs) == 1
    assert tabs[0].text_frame.text == "rules/Trail_tampering.py", tabs[0].text_frame.text


def _case_render_verify_plants(tmp: Path) -> None:
    import howto_deck_render as r

    deck = _render_deck()
    out = r.render_deck(deck, tmp / "d.pptx", {})
    prs = _reopen(out)
    prs.slides[2].notes_slide.notes_text_frame.text = ""
    for sh in prs.slides[3].shapes:
        if sh.name == "footer-left":
            sh.text_frame.paragraphs[0].runs[0].text = "csoh.org/elsewhere"
    for sh in prs.slides[4].shapes:
        if sh.name == "heading":
            sh.text_frame.paragraphs[0].runs[0].text = "Bad " + chr(0x2014) + " dash"
    bad = tmp / "bad.pptx"
    prs.save(str(bad))
    found = "\n".join(r.verify_pptx(bad, deck))
    for needle in ("slide 3: no speaker notes", "slide 4: footer lacks", "slide 5: contains an en or em dash"):
        assert needle in found, (needle, found)
    short = _render_deck(9)
    assert any("slides, expected" in f for f in r.verify_pptx(out, short))


def _case_render_cover_title(tmp: Path) -> None:
    import howto_deck_render as r

    def geometry(title: str) -> tuple[int, int, int]:
        deck = _render_deck()
        deck.title = title
        out = r.render_deck(deck, tmp / "c.pptx", {})
        shapes = {sh.name: sh for sh in _reopen(out).slides[0].shapes}
        return shapes["title"].top, shapes["title"].height, shapes["promise"].top

    one_line = r.STYLE["cover_title_pt"] * r.STYLE["line_heading"] / 72
    # Narrow letters, so the character count alone decides: 30 fit, 34 wrap.
    for title, rows in (("l" * 30, 1), ("l" * 34, 2)):
        top, height, promise_top = geometry(title)
        assert height >= int(rows * one_line * 914400), (len(title), rows, height)
        assert promise_top >= top + height, (len(title), top, height, promise_top)
    # Control: a 30-character title keeps one line, so it must be shorter.
    assert geometry("l" * 30)[1] < geometry("l" * 34)[1]
    # Thirty wide letters are within the count but wider than the 11.5 in
    # title box in the heading face (592 thousandths of an em each, unkerned,
    # as a browser canvas measures Space Grotesk Bold), so they get two rows.
    assert 30 * 592 / 1000 * r.STYLE["cover_title_pt"] / 72 > 11.5
    assert geometry("x" * 30)[1] == geometry("l" * 34)[1]


def _case_render_heading_wrap(tmp: Path) -> None:
    """A heading long enough to wrap gets two rows of height, so the guide
    line below it starts under the second row instead of on it."""
    import howto_deck_render as r

    per_line = r.STYLE["heading_chars_per_line"]
    assert per_line <= 46, f"heading_chars_per_line {per_line} lets a 47-character heading overprint"
    row = r.STYLE["heading_pt"] * r.STYLE["line_heading"] / 72
    for length, rows in ((per_line, 1), (per_line + 1, 2)):
        deck = _render_deck()
        deck.slides[0].heading = "x" * length
        deck.slides[0].section = "Setup"
        out = r.render_deck(deck, tmp / "h.pptx", {})
        shapes = {sh.name: sh for sh in _reopen(out).slides[1].shapes}
        heading, guide = shapes["heading"], shapes["guide-line"]
        assert heading.height >= int(rows * row * 914400), (length, heading.height)
        assert guide.top >= heading.top + int(rows * row * 914400), (length, heading.top, guide.top)


def _case_render_heading_measured(tmp: Path) -> None:
    """A heading within the character count that Google Slides wraps,
    measured in its face, gets two rows, so the guide line starts under the
    second."""
    import howto_deck_render as r

    # Whole headings in thousandths of an em, as a browser canvas measures
    # them in Space Grotesk Bold (fonts/space-grotesk-700.woff2) with
    # kerning. Google Slides wrapped the first at 36 pt across the 12.1 in
    # heading box and kept the second on one line.
    em = {
        "ignore_changes can quietly unmanage a resource": (24200, 2),
        "Envelope encryption: how every cloud KMS works": (23937, 1),
    }
    pt, w = r.STYLE["heading_pt"], r.STYLE["w"]
    row = pt * r.STYLE["line_heading"] / 72
    for text, (width, rows) in em.items():
        assert len(text) <= r.STYLE["heading_chars_per_line"], text
        assert (width / 1000 * pt / 72 >= w) == (rows == 2), text
        deck = _render_deck()
        deck.slides[0].heading = text
        deck.slides[0].section = "Setup"
        out = r.render_deck(deck, tmp / "h.pptx", {})
        assert r.verify_pptx(out, deck) == [], r.verify_pptx(out, deck)
        shapes = {sh.name: sh for sh in _reopen(out).slides[1].shapes}
        heading, guide = shapes["heading"], shapes["guide-line"]
        held = (heading.height / 914400 - 0.1) / row
        assert abs(held - rows) < 0.01, (text, held)
        assert guide.top >= heading.top + heading.height, (text, heading.top, guide.top)


def _case_render_build_cleanup(tmp: Path) -> None:
    """--build removes a deck's old .pptx before rendering and removes a new
    one that fails verification, so a failed build never leaves a file that
    looks current."""
    import howto_deck_render as r

    _tree(tmp, {"aa": _outline("aa")}, {"aa": INFO_PAGE}, {})
    out = tmp / "tools" / "decks" / "build" / "aa.pptx"

    def layout_error(deck, path, headings=None):
        raise r.LayoutError("aa.deck:5: planted overflow")

    def verify_problem(path, deck):
        return [f"{path.name} slide 2: planted problem"]

    real_render, real_verify = r.render_deck, r.verify_pptx
    with _rooted(tmp):
        try:
            for name, patch in (("render_deck", layout_error), ("verify_pptx", verify_problem)):
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_bytes(b"an older build")
                setattr(r, name, patch)
                try:
                    rc, text = _capture(build_decks, ["aa"])
                finally:
                    r.render_deck, r.verify_pptx = real_render, real_verify
                assert rc == 1 and "planted" in text, (name, text)
                assert not out.exists(), f"{name}: a failed build left {out.name} behind"
            # Control: an unpatched build writes the file.
            rc, text = _capture(build_decks, ["aa"])
        finally:
            r.render_deck, r.verify_pptx = real_render, real_verify
    assert rc == 0 and out.exists() and "built tools/decks/build/aa.pptx" in text, text


RENDER_CASES: list = [
    ("render_ok", _case_render_ok),
    ("render_notes", _case_render_notes),
    ("render_overflow", _case_render_overflow),
    ("render_wrapped_code", _case_render_wrapped_code),
    ("render_fonts", _case_render_fonts),
    ("render_code_label", _case_render_code_label),
    ("render_code_file", _case_render_code_file),
    ("render_verify_plants", _case_render_verify_plants),
    ("render_cover_title", _case_render_cover_title),
    ("render_heading_wrap", _case_render_heading_wrap),
    ("render_heading_measured", _case_render_heading_measured),
    ("render_build_cleanup", _case_render_build_cleanup),
]


def _run_cases(cases: list, label: str) -> int:
    """Run every case. A failure prints the case name, the line that raised,
    and the exception's message, so a CI log says what broke."""
    failed = 0
    for name, fn in cases:
        with tempfile.TemporaryDirectory() as td:
            try:
                fn(Path(td))
            except Exception as e:  # a failing case must not hide the others
                failed += 1
                frame = traceback.extract_tb(e.__traceback__)[-1]
                at = f"{Path(frame.filename).name}:{frame.lineno}"
                print(f"{label} FAILED: {name} ({at}): {type(e).__name__}: {e}")
    if failed:
        return 1
    print(f"{label}: {len(cases)} cases passed")
    return 0


def self_test_render() -> int:
    try:
        import howto_deck_render  # noqa: F401
    except ImportError as e:
        print(f"self-test-render: cannot import the renderer: {e}")
        return 1
    return _run_cases(RENDER_CASES, "self-test-render")


def build_decks(slugs: list[str]) -> int:
    """Render the named outlines to DECKS_DIR/build/<slug>.pptx. A deck with
    any --check finding is refused; a written file is reopened and verified.
    An unknown slug stops the run before anything is built. A deck's old
    build is removed before it renders, and a file that fails verification
    is removed too, so every .pptx in build/ passed verification when it
    was written."""
    known = {p.stem: p for p in outline_paths()}
    unknown = [sl for sl in slugs if sl not in known]
    if unknown:
        for sl in unknown:
            print(f"build: no outline tools/decks/{sl}.deck")
        return 1
    try:
        import howto_deck_render as render
    except ImportError as e:
        print(f"build: cannot import the renderer (pip install python-pptx): {e}")
        return 1
    bad = 0
    outlines = [known[sl] for sl in dict.fromkeys(slugs)]
    for path in outlines:
        try:
            deck = parse_outline(path)
        except OutlineError as e:
            print(e)
            bad += 1
            continue
        guide = ROOT / deck.guide
        if deck.guide != f"howto/{deck.slug}.html" or not guide.exists():
            print(f"{path.name}: guide must be an existing howto/{deck.slug}.html, got {deck.guide}")
            bad += 1
            continue
        html = guide.read_text(encoding="utf-8")
        findings = style_findings(deck) + guide_findings(deck, html)
        if findings:
            print("\n".join(findings))
            print(f"{path.name}: refused, fix the findings above")
            bad += 1
            continue
        for sl in deck.slides:
            if sl.code:
                sl.code_label = excerpt_label(html, sl.code)
                sl.code_file = excerpt_file(html, sl.code)
        out = DECKS_DIR / "build" / f"{deck.slug}.pptx"
        out.unlink(missing_ok=True)
        try:
            render.render_deck(deck, out, guide_headings(html))
        except render.LayoutError as e:
            print(e)
            bad += 1
            continue
        problems = render.verify_pptx(out, deck)
        if problems:
            print("\n".join(problems))
            out.unlink(missing_ok=True)
            print(f"{path.name}: removed {_rel(out)}, which failed verification")
            bad += 1
            continue
        print(f"built {_rel(out)}")
    print(f"build: {len(outlines)} outlines, {bad} failed")
    return 1 if bad else 0


def self_test() -> int:
    return _run_cases(CASES, "self-test")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--self-test", action="store_true", help="run the built-in cases")
    ap.add_argument("--check", action="store_true", help="check outlines and guide-page links")
    ap.add_argument("--build", nargs="+", metavar="SLUG", help="render the named outlines to .pptx")
    ap.add_argument(
        "--self-test-render", action="store_true", help="run the renderer cases (needs python-pptx)"
    )
    ap.add_argument("--stale", action="store_true", help="list decks whose outline changed")
    ap.add_argument(
        "--published-only", action="store_true",
        help="with --stale, leave out outlines that were never published",
    )
    ap.add_argument("--status", action="store_true", help="list outline and publish state")
    ap.add_argument("--stamp", action="store_true", help="rewrite guide pages from the mapping")
    ap.add_argument(
        "--record", nargs=2, metavar=("SLUG", "PRES_ID"), help="record a published deck"
    )
    args = ap.parse_args()
    if args.published_only and not args.stale:
        ap.error("--published-only goes with --stale")
    if args.self_test:
        return self_test()
    if args.self_test_render:
        return self_test_render()
    if args.check:
        return check_all()
    if args.build:
        return build_decks(args.build)
    if args.stale:
        return stale_report(args.published_only)
    if args.status:
        return status_report()
    if args.stamp:
        return stamp_all()
    if args.record:
        return record(*args.record)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
