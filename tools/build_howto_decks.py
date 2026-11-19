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
`== include:` splices a fragment's slides in place. A fragment has no header
and cannot include another, so a deck's text always resolves in one pass.

Usage:
    python3 tools/build_howto_decks.py --self-test
    python3 tools/build_howto_decks.py --check
    python3 tools/build_howto_decks.py --stale | --status | --stamp
    python3 tools/build_howto_decks.py --record SLUG PRES_ID
"""

from __future__ import annotations

import argparse
import hashlib
import html as htmllib
import json
import re
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

MAX_PROSE_WORDS = 40
MAX_CODE_LINES = 12
MAX_CODE_COLS = 90
MAX_HEADING_WORDS = 12
MIN_SLIDES = 12
MAX_SLIDES = 20
# The renderer adds a cover and a closing slide that the outline does not
# contain; the slide-count limit applies to the total.
GENERATED_SLIDES = 2
DECKS_DIR = Path("tools/decks")

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
    credit: str | None = None
    where: str = ""


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
                frag_path = include_dir / frag_name
                if not frag_name or not frag_path.is_file():
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
        elif stripped.startswith("section: "):
            if cur.section is not None:
                raise _err(name, lineno, "slide has two section lines")
            cur.section = stripped[len("section: "):].strip()
        elif stripped.startswith("credit: "):
            if cur.credit is not None:
                raise _err(name, lineno, "slide has two credit lines")
            cur.credit = stripped[len("credit: "):].strip()
        elif stripped.startswith("- "):
            flush_para()
            cur.bullets.append(stripped[2:].strip())
        else:
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
            if len(s.code) > MAX_CODE_LINES:
                findings.append(
                    f"{s.where}: {len(s.code)} code lines; the limit is {MAX_CODE_LINES}"
                )
            for n, line in enumerate(s.code, 1):
                if len(line) > MAX_CODE_COLS:
                    findings.append(
                        f"{s.where}: code line {n} is {len(line)} columns; "
                        f"the limit is {MAX_CODE_COLS}"
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
# Self-test. Later tasks append (name, fn) pairs to CASES; each fn takes a
# scratch directory and asserts.
# ---------------------------------------------------------------------------

MAPPING = DECKS_DIR / "published.json"
HOWTO_DIR = Path("howto")
INFO_BOX_RE = re.compile(r'(<div class="info-box--blue">.*?\n)([ \t]*</div>)', re.DOTALL)
DECK_LINE_RE = re.compile(
    r"^[ \t]*<p[^>]*data-howto-deck[^>]*>.*?</p>\n?", re.DOTALL | re.MULTILINE
)


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


def stamp_page(html: str, pres_id: str | None) -> str:
    """Put the deck line last in the page's first info box, replace the one
    already there, or remove it when pres_id is None."""
    if pres_id is None:
        return DECK_LINE_RE.sub("", html)
    line = deck_line_html(pres_id) + "\n"
    if DECK_LINE_RE.search(html):
        return DECK_LINE_RE.sub(lambda _m: line, html, count=1)
    if not INFO_BOX_RE.search(html):
        raise ValueError('no <div class="info-box--blue"> to hold the deck line')
    return INFO_BOX_RE.sub(lambda m: m.group(1) + line + m.group(2), html, count=1)


def link_findings(slug: str, html: str, mapping: dict) -> list[str]:
    """Disagreements between the deck line on a guide page and the mapping."""
    has_line = DECK_LINE_RE.search(html) is not None
    entry = mapping.get(slug)
    if has_line and entry is None:
        return [f"howto/{slug}.html: has a deck line but {slug!r} is not in the mapping"]
    if entry is None:
        return []
    if not has_line:
        return [f"howto/{slug}.html: {slug!r} is in the mapping but the page has no deck line"]
    if stamp_page(html, entry["id"]) != html:
        return [f"howto/{slug}.html: deck line does not match the mapping id {entry['id']!r}"]
    return []


def load_mapping(path: Path = MAPPING) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_mapping(mapping: dict, path: Path = MAPPING) -> None:
    path.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def outline_paths() -> list[Path]:
    return sorted(p for p in DECKS_DIR.glob("*.deck") if not p.name.startswith("_"))


def guide_pages() -> list[Path]:
    return sorted(HOWTO_DIR.glob("*.html"))


def check_all() -> int:
    mapping = load_mapping()
    findings: list[str] = []
    outlines = outline_paths()
    for path in outlines:
        try:
            deck = parse_outline(path)
        except OutlineError as e:
            findings.append(str(e))
            continue
        findings += style_findings(deck)
        guide = Path(deck.guide)
        if guide != HOWTO_DIR / f"{deck.slug}.html":
            findings.append(f"{path.name}: guide must be howto/{deck.slug}.html, got {deck.guide}")
        elif not guide.exists():
            findings.append(f"{path.name}: guide {deck.guide} does not exist")
        else:
            findings += guide_findings(deck, guide.read_text(encoding="utf-8"))
    pages = guide_pages()
    for page in pages:
        findings += link_findings(page.stem, page.read_text(encoding="utf-8"), mapping)
    for slug in sorted(mapping):
        if not (HOWTO_DIR / f"{slug}.html").exists():
            findings.append(f"mapping: {slug!r} names no howto page")
    for f in findings:
        print(f)
    print(
        f"decks: {len(outlines)} outlines checked, {len(pages)} guide pages checked, "
        f"{len(findings)} findings"
    )
    return 1 if findings else 0


def stale_report() -> int:
    mapping = load_mapping()
    for path in outline_paths():
        deck = parse_outline(path)
        entry = mapping.get(deck.slug)
        if entry is None:
            print(f"{deck.slug}: not published")
        elif entry["outline_sha256"] != outline_sha256(deck):
            print(f"{deck.slug}: outline changed since publish on {entry['published']}")
    return 0


def status_report() -> int:
    mapping = load_mapping()
    outlines = {p.stem for p in outline_paths()}
    for page in guide_pages():
        has_outline = "yes" if page.stem in outlines else "no"
        published = "yes" if page.stem in mapping else "no"
        print(f"{page.stem}: outline {has_outline}, published {published}")
    return 0


def stamp_all() -> int:
    mapping = load_mapping()
    for page in guide_pages():
        html = page.read_text(encoding="utf-8")
        entry = mapping.get(page.stem)
        new = stamp_page(html, entry["id"] if entry else None)
        if new != html:
            page.write_text(new, encoding="utf-8")
            print(f"stamped {page}")
    return 0


def record(slug: str, pres_id: str) -> int:
    deck = parse_outline(DECKS_DIR / f"{slug}.deck")
    mapping = load_mapping()
    mapping[slug] = {
        "id": pres_id,
        "published": date.today().isoformat(),
        "outline_sha256": outline_sha256(deck),
    }
    save_mapping(mapping)
    return stamp_all()


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


PRE_RE = re.compile(r"<pre[^>]*>(.*?)</pre>", re.DOTALL)
HEADING_RE = re.compile(r"<h([23])([^>]*)>(.*?)</h\1>", re.DOTALL)
ID_RE = re.compile(r"""\bid\s*=\s*["']([^"']*)["']""")
TAG_RE = re.compile(r"<[^>]+>")


def guide_code_blocks(html: str) -> list[list[str]]:
    """Every <pre> block on the page as unescaped lines with trailing
    whitespace removed, so an excerpt compares against what a reader sees."""
    return [
        [ln.rstrip() for ln in htmllib.unescape(m.group(1)).split("\n")]
        for m in PRE_RE.finditer(html)
    ]


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


def _case_code_too_wide(tmp: Path) -> None:
    d = _deck_with(10)
    d.slides[0].code = ["x" * 91]
    f = style_findings(d)
    assert len(f) == 1 and "90" in f[0], f
    d.slides[0].code = ["x" * 90]
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
    assert style_findings(_deck_with(18)) == []
    assert len(style_findings(_deck_with(19))) == 1


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


INFO_PAGE = (
    "<main>\n"
    '        <div class="info-box--blue">\n'
    "            <p><strong>Time:</strong> 1 hour</p>\n"
    '            <p class="u-mt-075"><strong>How this page was checked:</strong> run.</p>\n'
    "        </div>\n"
    "</main>\n"
)
INFO_PAGE_BARE = INFO_PAGE.replace(
    '            <p class="u-mt-075"><strong>How this page was checked:</strong> run.</p>\n',
    "",
)


def _deck_lines(html: str) -> list[str]:
    return [ln for ln in html.split("\n") if "data-howto-deck" in ln]


def _case_stamp_insert(tmp: Path) -> None:
    out = stamp_page(INFO_PAGE, "A")
    assert _deck_lines(out) == [deck_line_html("A")], out
    assert out.split("\n")[-4:-3] == [deck_line_html("A")], out
    assert out.split("\n")[-3] == "        </div>", out


def _case_stamp_no_checked_line(tmp: Path) -> None:
    out = stamp_page(INFO_PAGE_BARE, "A")
    lines = out.split("\n")
    assert lines[3] == deck_line_html("A") and lines[4] == "        </div>", out


def _case_stamp_idempotent(tmp: Path) -> None:
    once = stamp_page(INFO_PAGE, "A")
    assert stamp_page(once, "A") == once


def _case_stamp_new_id(tmp: Path) -> None:
    out = stamp_page(stamp_page(INFO_PAGE, "A"), "B")
    assert _deck_lines(out) == [deck_line_html("B")], out


def _case_stamp_remove(tmp: Path) -> None:
    assert stamp_page(stamp_page(INFO_PAGE, "A"), None) == INFO_PAGE


def _case_stamp_no_info_box(tmp: Path) -> None:
    try:
        stamp_page("<main><p>none</p></main>", "A")
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def _case_links_unmapped_line(tmp: Path) -> None:
    f = link_findings("g", stamp_page(INFO_PAGE, "A"), {})
    assert len(f) == 1 and "g" in f[0], f


def _case_links_missing_line(tmp: Path) -> None:
    f = link_findings("g", INFO_PAGE, {"g": {"id": "A"}})
    assert len(f) == 1 and "g" in f[0], f


def _case_links_wrong_id(tmp: Path) -> None:
    f = link_findings("g", stamp_page(INFO_PAGE, "A"), {"g": {"id": "B"}})
    assert len(f) == 1, f
    assert link_findings("g", stamp_page(INFO_PAGE, "B"), {"g": {"id": "B"}}) == []
    assert link_findings("g", INFO_PAGE, {}) == []


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
    ("missing_header", _case_missing_header),
    ("unknown_header_key", _case_unknown_header_key),
    ("unterminated_fence", _case_unterminated_fence),
    ("two_fences", _case_two_fences),
    ("empty_slide", _case_empty_slide),
    ("fence_hides_slide_marker", _case_fence_hides_slide_marker),
    ("too_many_words", _case_too_many_words),
    ("too_many_code_lines", _case_too_many_code_lines),
    ("code_too_wide", _case_code_too_wide),
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
    ("section_ok", _case_section_ok),
    ("section_with_markup", _case_section_with_markup),
    ("section_missing", _case_section_missing),
    ("stamp_insert", _case_stamp_insert),
    ("stamp_no_checked_line", _case_stamp_no_checked_line),
    ("stamp_idempotent", _case_stamp_idempotent),
    ("stamp_new_id", _case_stamp_new_id),
    ("stamp_remove", _case_stamp_remove),
    ("stamp_no_info_box", _case_stamp_no_info_box),
    ("links_unmapped_line", _case_links_unmapped_line),
    ("links_missing_line", _case_links_missing_line),
    ("links_wrong_id", _case_links_wrong_id),
    ("sha_changes", _case_sha_changes),
]


def self_test() -> int:
    failed = 0
    for name, fn in CASES:
        with tempfile.TemporaryDirectory() as td:
            try:
                fn(Path(td))
            except Exception as e:  # a failing case must not hide the others
                failed += 1
                print(f"self-test FAILED: {name}: {type(e).__name__}: {e}")
    if failed:
        return 1
    print(f"self-test: {len(CASES)} cases passed")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--self-test", action="store_true", help="run the built-in cases")
    ap.add_argument("--check", action="store_true", help="check outlines and guide-page links")
    ap.add_argument("--stale", action="store_true", help="list decks whose outline changed")
    ap.add_argument("--status", action="store_true", help="list outline and publish state")
    ap.add_argument("--stamp", action="store_true", help="rewrite guide pages from the mapping")
    ap.add_argument(
        "--record", nargs=2, metavar=("SLUG", "PRES_ID"), help="record a published deck"
    )
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if args.check:
        return check_all()
    if args.stale:
        return stale_report()
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
