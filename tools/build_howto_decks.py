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
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import dataclass, field
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
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
