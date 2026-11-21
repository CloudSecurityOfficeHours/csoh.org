#!/usr/bin/env python3
"""
Parse the plain-text slide outlines in tools/decks/breaches/ and enforce the
breach deck style limits.

Each breach kill chain page in breaches/ can have a slide deck written as an
outline. This module reads an outline into a BDeck and reports every
style-limit breach as a finding. It uses the standard library only, so the
checks run in CI without python-pptx; the renderer lives in a separate module.

Outline format:

    title: <deck title>
    page: breaches/<slug>.html
    as-of: YYYY-MM-DD
    promise: <one sentence>

    == <slide heading>
    layout: <name>              (text when absent)
    stage: 04                   (control lines: layout, stage, phase, source,
    phase: Credential Access     credit; each at most once per slide)
    source: <name> | <url>
    technique: T1552.005 | Cloud Instance Metadata API   (typed line)
    fact: Queried | the cloud Instance Metadata Service
    Prose lines join into one paragraph; a blank line ends it.
    - A bullet
    notes:
    Speaker notes run to the next "== " line. Every slide has them.

Header keys before the first "== " line are exactly title, page, as-of and
promise. A typed line is "key: field | field ..." and every field must be
non-empty. Which typed keys a slide takes, and how many lines and fields, is
set by its layout (see LAYOUTS). Breach outlines have no includes and no code
fences.

Structural problems raise OutlineError("<file>:<line>: ..."): a malformed
header, an unknown layout or typed key, a control line given twice, a typed
line the layout does not take, an empty field, a wrong field count, a missing
notes block. Limit breaches are findings, so one --check run reports them all:
line counts, word limits, dashes, a missing required control line, prose rules
per layout, matrix marks, ragged tables, bar numbers and the slide count.

Usage:
    python3 tools/build_breach_decks.py --self-test
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_howto_decks import (  # noqa: E402
    EM_DASH,
    EN_DASH,
    SPACED_HYPHEN_RE,
    OutlineError,
    _is_iso_date,
    _run_cases,
)

MAX_PROSE_WORDS = 40
MAX_HEADING_WORDS = 12
MAX_FIELD_WORDS = 14
MAX_NOTES_WORDS = 220
MIN_SLIDES = 18
MAX_SLIDES = 36
# The renderer adds a cover, a "how to use this deck" slide and a closing
# slide that the outline does not contain; the slide-count limit applies to
# the total.
GENERATED_SLIDES = 3

HEADER_KEYS = ("title", "page", "as-of", "promise")
HEADER_RE = re.compile(r"^([A-Za-z][A-Za-z-]*):\s?(.*)$")
PAGE_RE = re.compile(r"breaches/[a-z0-9][a-z0-9-]*\.html")
# A lowercase word and a colon at the start of a line. Prose starts with a
# capital, so a line of this shape is a key: one the format knows, or a typo
# that must fail rather than be read as prose.
KEY_LINE_RE = re.compile(r"^([a-z][a-z-]*):(?:\s+(.*))?$")
# A known key at the start of a body line, in any case and with or without
# whitespace after the colon. Such a line is that key or an error, never prose.
KNOWN_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z-]*):\s*(.*)$")
# A field separator is a pipe set off by whitespace. Splitting on the pipe and
# its leading space (not both spaces) keeps "a | | b" as three fields, the
# middle one empty, so the empty field is reported rather than swallowed.
FIELD_SPLIT_RE = re.compile(r"\s+\|(?=\s|$)")

CONTROL_KEYS = ("layout", "stage", "phase", "source", "credit")


@dataclass(frozen=True)
class LayoutSpec:
    # Typed key -> (min lines, max lines, min fields, max fields or None).
    typed: dict[str, tuple[int, int, int, int | None]]
    # "none", "optional", "required" or "prose-only".
    prose: str
    # Control lines that must be present.
    requires: tuple[str, ...] = ()


LAYOUTS: dict[str, LayoutSpec] = {
    "text": LayoutSpec({}, "required"),
    "stats": LayoutSpec({"stat": (2, 4, 3, 3)}, "optional"),
    "stage": LayoutSpec(
        {"technique": (1, 3, 2, 2), "fact": (1, 5, 2, 2)},
        "optional",
        ("stage", "phase"),
    ),
    "background": LayoutSpec({}, "required", ("source",)),
    "question": LayoutSpec({}, "prose-only"),
    "answer": LayoutSpec({}, "required"),
    "checklist": LayoutSpec({"check": (2, 7, 1, 1)}, "optional"),
    "links": LayoutSpec({"link": (1, 8, 2, 2)}, "optional"),
    "flow": LayoutSpec({"step": (3, 8, 4, 4)}, "optional"),
    "layers": LayoutSpec({"layer": (2, 5, 2, 4)}, "optional"),
    "timeline": LayoutSpec({"event": (2, 6, 2, 2)}, "optional"),
    "compare": LayoutSpec({"col": (2, 3, 2, 5)}, "optional"),
    "table": LayoutSpec({"row": (2, 7, 2, 4)}, "optional"),
    "bars": LayoutSpec({"bar": (2, 4, 2, 2)}, "optional"),
    "matrix": LayoutSpec(
        {"columns": (1, 1, 2, 8), "row": (2, 8, 2, 9)}, "optional"
    ),
}

TYPED_KEYS = frozenset(k for spec in LAYOUTS.values() for k in spec.typed)
KNOWN_KEYS = frozenset(CONTROL_KEYS) | TYPED_KEYS


@dataclass
class BSlide:
    heading: str
    layout: str = "text"
    paragraphs: list[str] = field(default_factory=list)
    bullets: list[str] = field(default_factory=list)
    items: dict[str, list[list[str]]] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    stage: str | None = None
    phase: str | None = None
    source: tuple[str, str] | None = None
    credit: str | None = None
    where: str = ""
    # Where prose first follows a bullet. The renderer draws every paragraph
    # above every bullet, so that prose would move; style_findings reports it.
    prose_after_bullet: str | None = None


@dataclass
class BDeck:
    slug: str
    title: str
    page: str
    as_of: str
    promise: str
    slides: list[BSlide]
    # The outline as read; the publish hash is taken over it.
    text: str = ""


def _err(name: str, lineno: int, msg: str) -> OutlineError:
    return OutlineError(f"{name}:{lineno}: {msg}")


def _split_fields(rest: str) -> list[str]:
    return [f.strip() for f in FIELD_SPLIT_RE.split(" " + rest.strip())]


def _fields(name: str, lineno: int, key: str, rest: str) -> list[str]:
    parts = _split_fields(rest)
    if any(not p for p in parts):
        raise _err(name, lineno, f"{key}: line has an empty field")
    return parts


def _parse_header(lines: list[str], name: str) -> dict[str, str]:
    header: dict[str, str] = {}
    for i, line in enumerate(lines):
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
    if not PAGE_RE.fullmatch(header["page"]):
        raise _err(name, 1, f"page must be breaches/<slug>.html, got {header['page']!r}")
    if not _is_iso_date(header["as-of"]):
        raise _err(name, 1, f"as-of {header['as-of']!r} is not a YYYY-MM-DD date")
    return header


def _parse_slides(lines: list[str], first_lineno: int, name: str) -> list[BSlide]:
    slides: list[BSlide] = []
    cur: BSlide | None = None
    para: list[str] = []
    notes: list[str] = []
    in_notes = False
    # Typed lines are checked against the layout when the slide ends, because
    # the layout line may come after them. Each entry keeps its line number.
    typed: list[tuple[int, str, list[str]]] = []
    seen: set[str] = set()

    def flush_para() -> None:
        if para and cur is not None:
            cur.paragraphs.append(" ".join(para))
        para.clear()

    def flush_notes() -> None:
        if notes and cur is not None:
            cur.notes.append(" ".join(notes))
        notes.clear()

    def finish() -> None:
        nonlocal cur, in_notes
        if cur is None:
            return
        flush_para()
        flush_notes()
        at = int(cur.where.rsplit(":", 1)[1])
        spec = LAYOUTS[cur.layout]
        for lineno, key, parts in typed:
            if key not in spec.typed:
                raise _err(name, lineno, f"a {cur.layout} slide does not take {key}: lines")
            lo, hi = spec.typed[key][2], spec.typed[key][3]
            if len(parts) < lo or (hi is not None and len(parts) > hi):
                want = f"{lo}" if lo == hi else f"{lo} to {hi if hi is not None else 'any number of'}"
                raise _err(
                    name, lineno,
                    f"{key}: line has {len(parts)} fields; a {cur.layout} slide takes {want}",
                )
            cur.items.setdefault(key, []).append(parts)
        if not cur.notes:
            raise _err(name, at, "slide has no notes: block")
        slides.append(cur)
        cur = None
        in_notes = False
        typed.clear()
        seen.clear()

    for i, line in enumerate(lines):
        lineno = first_lineno + i
        if line.startswith("== "):
            finish()
            heading = line[3:].strip()
            if not heading:
                raise _err(name, lineno, "slide has no heading")
            if heading.startswith("include:"):
                raise _err(name, lineno, "breach outlines have no includes")
            cur = BSlide(heading=heading, where=f"{name}:{lineno}")
            continue

        if cur is None:
            if line.strip():
                raise _err(name, lineno, "text before the first slide")
            continue

        stripped = line.strip()
        if stripped.startswith("```"):
            raise _err(name, lineno, "breach outlines have no code fences")

        if in_notes:
            if stripped:
                notes.append(stripped)
            else:
                flush_notes()
            continue

        if not stripped:
            flush_para()
            continue
        if stripped == "notes:":
            flush_para()
            in_notes = True
            continue
        if stripped == "-":
            raise _err(name, lineno, "empty bullet")
        if stripped.startswith("- "):
            flush_para()
            cur.bullets.append(stripped[2:].strip())
            continue

        km = KNOWN_KEY_RE.match(stripped)
        if km is not None and km.group(1).lower() in KNOWN_KEYS:
            key, rest = km.group(1).lower(), km.group(2).strip()
        else:
            m = KEY_LINE_RE.match(stripped)
            if m is None:
                if " | " in stripped:
                    raise _err(
                        name, lineno,
                        "prose line contains ' | '; a typed line is missing its key",
                    )
                if cur.bullets and cur.prose_after_bullet is None:
                    cur.prose_after_bullet = f"{name}:{lineno}"
                para.append(stripped)
                continue
            key, rest = m.group(1), (m.group(2) or "").strip()
        flush_para()
        if key in CONTROL_KEYS:
            if key in seen:
                raise _err(name, lineno, f"slide has two {key}: lines")
            seen.add(key)
            if not rest:
                raise _err(name, lineno, f"empty {key}: line")
            if key == "layout":
                if rest not in LAYOUTS:
                    raise _err(
                        name, lineno,
                        f"unknown layout {rest!r}; known: {', '.join(LAYOUTS)}",
                    )
                cur.layout = rest
            elif key == "source":
                parts = _fields(name, lineno, key, rest)
                if len(parts) != 2:
                    raise _err(name, lineno, "source: takes 'name | url'")
                cur.source = (parts[0], parts[1])
            else:
                setattr(cur, key, rest)
        elif key in TYPED_KEYS:
            typed.append((lineno, key, _fields(name, lineno, key, rest)))
        else:
            raise _err(name, lineno, f"unknown line key {key!r}")

    finish()
    return slides


def parse_outline_text(text: str, name: str) -> BDeck:
    lines = text.split("\n")
    body_start = next((i for i, ln in enumerate(lines) if ln.startswith("== ")), len(lines))
    header = _parse_header(lines[:body_start], name)
    slides = _parse_slides(lines[body_start:], body_start + 1, name)
    slug = name[: -len(".deck")] if name.endswith(".deck") else name
    return BDeck(
        slug=slug,
        title=header["title"],
        page=header["page"],
        as_of=header["as-of"],
        promise=header["promise"],
        slides=slides,
        text=text,
    )


def parse_outline(path: Path) -> BDeck:
    return parse_outline_text(path.read_text(encoding="utf-8"), path.name)


def outline_sha256(deck: BDeck) -> str:
    return hashlib.sha256(deck.text.encode("utf-8")).hexdigest()


def _words(text: str) -> int:
    return len(text.split())


def _dash_findings(where: str, texts: list[str]) -> list[str]:
    out: list[str] = []
    for t in texts:
        if EM_DASH in t or EN_DASH in t:
            out.append(f"{where}: em or en dash in {t[:40]!r}")
        if SPACED_HYPHEN_RE.search(t):
            out.append(f"{where}: spaced hyphen used as a dash in {t[:40]!r}")
    return out


BAR_NUMBER_RE = re.compile(r"\d[\d,]*(\.\d+)?\+?")


def _bar_number_ok(value: str) -> bool:
    return BAR_NUMBER_RE.fullmatch(value) is not None


def slide_findings(s: BSlide) -> list[str]:
    """Every style-limit breach on one slide, each starting with its `where`."""
    out: list[str] = []
    spec = LAYOUTS[s.layout]

    for key, (lo, hi, _flo, _fhi) in spec.typed.items():
        n = len(s.items.get(key, []))
        if not lo <= n <= hi:
            want = f"{lo}" if lo == hi else f"{lo} to {hi}"
            out.append(f"{s.where}: {n} {key} lines on a {s.layout} slide; it takes {want}")

    for ctl in spec.requires:
        if not getattr(s, ctl):
            out.append(f"{s.where}: a {s.layout} slide needs a {ctl}: line")

    prose = s.paragraphs + s.bullets
    if spec.prose == "none" and prose:
        out.append(f"{s.where}: a {s.layout} slide takes no prose or bullets")
    needs = spec.prose == "required" and not prose
    needs = needs or (spec.prose == "prose-only" and not s.paragraphs)
    if needs:
        out.append(f"{s.where}: a {s.layout} slide needs prose")
    if spec.prose == "prose-only" and s.bullets:
        out.append(f"{s.where}: a {s.layout} slide takes prose only, not bullets")
    if s.prose_after_bullet:
        out.append(
            f"{s.prose_after_bullet}: prose after a bullet renders above all the "
            "bullets; move it before them or make it a bullet"
        )

    words = sum(_words(t) for t in prose)
    if words > MAX_PROSE_WORDS:
        out.append(f"{s.where}: {words} words of prose; the limit is {MAX_PROSE_WORDS}")
    if _words(s.heading) > MAX_HEADING_WORDS:
        out.append(
            f"{s.where}: heading is {_words(s.heading)} words; the limit is {MAX_HEADING_WORDS}"
        )
    note_words = sum(_words(p) for p in s.notes)
    if note_words > MAX_NOTES_WORDS:
        out.append(f"{s.where}: notes are {note_words} words; the limit is {MAX_NOTES_WORDS}")

    fields = [f for rows in s.items.values() for row in rows for f in row]
    for f in fields:
        if _words(f) > MAX_FIELD_WORDS:
            out.append(
                f"{s.where}: field {f[:30]!r} is {_words(f)} words; the limit is {MAX_FIELD_WORDS}"
            )

    columns = s.items.get("columns", [[]])[0] if s.items.get("columns") else []
    if s.layout == "matrix" and columns:
        for row in s.items.get("row", []):
            for mark in row[1:]:
                if mark != "-" and mark not in columns:
                    out.append(
                        f"{s.where}: row {row[0]!r} has mark {mark!r}, which is not a column"
                    )
    if s.layout == "table":
        widths = {len(row) for row in s.items.get("row", [])}
        if len(widths) > 1:
            out.append(f"{s.where}: table rows have different widths {sorted(widths)}")
    if s.layout == "bars":
        for row in s.items.get("bar", []):
            if not _bar_number_ok(row[0]):
                out.append(f"{s.where}: bar number {row[0]!r} is not a number")

    texts = [s.heading, *prose, *fields, *s.notes]
    for extra in (s.credit, s.phase, s.stage, s.source[0] if s.source else None):
        if extra:
            texts.append(extra)
    out += _dash_findings(s.where, texts)
    return out


def style_findings(deck: BDeck) -> list[str]:
    """Every style-limit breach in the deck. Slide findings start with the
    slide's `where`; deck-level findings start with the deck's file."""
    findings: list[str] = []
    total = len(deck.slides) + GENERATED_SLIDES
    if not MIN_SLIDES <= total <= MAX_SLIDES:
        findings.append(
            f"{deck.slug}.deck: {total} slides including the generated cover, "
            f"how-to-use and closing; the deck must have {MIN_SLIDES} to {MAX_SLIDES}"
        )
    # The cover shows the title and promise, so they follow the slide dash rules.
    findings += _dash_findings(f"{deck.slug}.deck", [deck.title, deck.promise])
    for s in deck.slides:
        findings += slide_findings(s)
    return findings


# ---------------------------------------------------------------------------
# Self-test. CASES holds (name, fn) pairs; each fn takes a scratch directory
# and asserts.
# ---------------------------------------------------------------------------

HEADER = (
    "title: VAPOR PANDA / ARTEX\n"
    "page: breaches/vapor-panda-artex.html\n"
    "as-of: 2026-11-20\n"
    "promise: One operator and 200+ organizations in 11 days.\n"
    "\n"
)

SAMPLE = HEADER + """== The metadata service handed over a fleet
layout: stage
stage: 04
phase: Credential Access
technique: T1552.005 | Cloud Instance Metadata API
fact: Queried | the cloud Instance Metadata Service
fact: Obtained | a role able to command thousands of instances
A role that can command a fleet turns one host into all of them.
notes:
At a US pharmaceutical organization the agent asked the metadata service
for credentials.

It got a role that could administer thousands of instances.

== Two numbers
layout: stats
stat: 200+ | organizations | named on the leak site
stat: 11 | days | from first login to the last
notes:
The scale in two numbers.

== What IMDSv2 changes
layout: background
source: AWS documentation | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html
IMDSv2 requires a session token before it returns credentials.
notes:
Background only.
"""


def _body(*lines: str, notes: str = "Notes.") -> str:
    return "\n".join(lines) + f"\nnotes:\n{notes}\n"


def _outline(body: str, header: str = HEADER) -> str:
    return header + body


def _parse(body: str, name: str = "d.deck") -> BDeck:
    return parse_outline_text(_outline(body), name)


def _slide_text(*lines: str) -> str:
    return _body("== S", *lines)


def _findings_of(*lines: str) -> list[str]:
    deck = _parse(_slide_text(*lines))
    return [f for s in deck.slides for f in slide_findings(s)]


def _deck_with(n: int) -> BDeck:
    slides = [
        BSlide(heading=f"Slide {i}", paragraphs=["Short."], notes=["N."], where=f"d.deck:{i}")
        for i in range(n)
    ]
    return BDeck("d", "T", "breaches/t.html", "2026-11-20", "P.", slides, "")


def _raises(fn, needle: str | None = None) -> OutlineError:
    try:
        fn()
    except OutlineError as e:
        if needle is not None:
            assert needle in str(e), f"{needle!r} not in {str(e)!r}"
        return e
    raise AssertionError("OutlineError was not raised")


def _only(findings: list[str], needle: str) -> None:
    assert len(findings) == 1 and needle in findings[0], findings


def _case_parse_ok(tmp: Path) -> None:
    d = parse_outline_text(SAMPLE, "sample.deck")
    assert d.slug == "sample" and d.page == "breaches/vapor-panda-artex.html"
    assert d.as_of == "2026-11-20" and d.title == "VAPOR PANDA / ARTEX"
    assert len(d.slides) == 3
    s0, s1, s2 = d.slides
    assert s0.layout == "stage" and s0.stage == "04" and s0.phase == "Credential Access"
    assert s0.items["fact"][0] == ["Queried", "the cloud Instance Metadata Service"]
    assert s0.items["technique"] == [["T1552.005", "Cloud Instance Metadata API"]]
    assert s0.paragraphs == ["A role that can command a fleet turns one host into all of them."]
    assert s0.where == "sample.deck:6"
    assert len(s0.notes) == 2 and s0.notes[0].startswith("At a US pharmaceutical")
    assert s1.items["stat"][0] == ["200+", "organizations", "named on the leak site"]
    assert s2.source is not None and s2.source[1].startswith("https://")
    assert s2.source[0] == "AWS documentation"
    assert all(s.notes for s in d.slides)
    # Control: the sample carries no findings of its own beyond the slide count.
    assert [f for s in d.slides for f in slide_findings(s)] == []


def _case_missing_header(tmp: Path) -> None:
    for key in HEADER_KEYS:
        text = "".join(
            ln + "\n" for ln in HEADER.splitlines() if ln and not ln.startswith(key + ":")
        )
        _raises(
            lambda text=text: parse_outline_text(text + "\n== S\nText.\nnotes:\nN.\n", "d.deck"),
            f"d.deck:1: missing required header key {key!r}",
        )


def _case_unknown_header_key(tmp: Path) -> None:
    text = HEADER.replace("\n\n", "\nauthor: x\n\n")
    _raises(lambda: parse_outline_text(text + "== S\nText.\nnotes:\nN.\n", "d.deck"), "author")


def _case_bad_as_of(tmp: Path) -> None:
    text = HEADER.replace("2026-11-20", "2026-11-31x")
    _raises(lambda: parse_outline_text(text, "d.deck"), "as-of")
    text = HEADER.replace("2026-11-20", "2026-11-31")
    _raises(lambda: parse_outline_text(text, "d.deck"), "as-of")


def _case_page_not_breaches(tmp: Path) -> None:
    text = HEADER.replace("breaches/vapor-panda-artex.html", "howto/x.html")
    _raises(lambda: parse_outline_text(text, "d.deck"), "breaches/<slug>.html")


def _case_unknown_layout(tmp: Path) -> None:
    e = _raises(lambda: _parse(_body("== S", "layout: carousel")), "unknown layout")
    assert str(e).startswith("d.deck:7:"), e


def _case_control_line_twice(tmp: Path) -> None:
    e = _raises(
        lambda: _parse(_body("== S", "layout: stage", "stage: 01", "stage: 02")),
        "two stage:",
    )
    assert str(e).startswith("d.deck:9:"), e


def _case_unknown_line_key(tmp: Path) -> None:
    _raises(lambda: _parse(_slide_text("fnord: a | b")), "unknown line key")
    # Control: a capitalised word before a colon is prose.
    assert _parse(_slide_text("Note: this is prose.")).slides[0].paragraphs == [
        "Note: this is prose."
    ]


def _case_key_never_becomes_prose(tmp: Path) -> None:
    for bad in ("fact:Queried | x", "Fact: Queried | x"):
        body = _body("== S", "layout: stage", "stage: 01", "phase: P", "technique: T1 | n", bad)
        assert len(_parse(body).slides[0].items["fact"]) == 1
    _raises(lambda: _parse(_slide_text("layout: stats", "stat:200+ | a")), "2 fields")
    assert _parse(_slide_text("Stage: 04", "Text.")).slides[0].stage == "04"
    e = _raises(lambda: _parse(_slide_text("Queried | x")), "' | '")
    assert str(e).startswith("d.deck:7:"), e


def _case_notes_stay_notes(tmp: Path) -> None:
    notes = "note: a thing.\nartx-prefixed roles: were used.\nstage: x\nstage: y\nfact: a | b\nA | b"
    d = _parse(_body("== S", "Text.", notes=notes))
    assert d.slides[0].stage is None and d.slides[0].items == {}
    assert "stage: y" in d.slides[0].notes[0] and "fact: a | b" in d.slides[0].notes[0]


def _case_typed_line_empty_field(tmp: Path) -> None:
    body = _body("== S", "layout: stats", "stat: 200+ | | x", "stat: 1 | a | b")
    e = _raises(lambda: _parse(body), "empty field")
    assert str(e).startswith("d.deck:8:"), e
    for bad in ("stat: | a | b", "stat: 1 | a |", "stat: 1 |  | b"):
        body = _body("== S", "layout: stats", bad, "stat: 1 | a | b")
        _raises(lambda body=body: _parse(body), "empty field")


def _case_typed_line_wrong_layout(tmp: Path) -> None:
    body = _body("== S", "layout: stats", "stat: 1 | a | b", "fact: Queried | x")
    e = _raises(lambda: _parse(body), "does not take fact:")
    assert str(e).startswith("d.deck:9:"), e
    # A typed line on a text slide (default layout) fails the same way.
    _raises(lambda: _parse(_slide_text("Text.", "check: a")), "does not take check:")


def _case_wrong_field_count(tmp: Path) -> None:
    body = _body("== S", "layout: stats", "stat: 1 | a", "stat: 2 | b | c")
    e = _raises(lambda: _parse(body), "2 fields")
    assert str(e).startswith("d.deck:8:"), e
    _raises(lambda: _parse(_slide_text("layout: flow", "step: 01 | a | b")), "3 fields")


def _case_count_out_of_range(tmp: Path) -> None:
    _only(_findings_of("layout: stats", "stat: 1 | a | b"), "1 stat lines")
    facts = [f"fact: L{i} | v" for i in range(6)]
    _only(
        _findings_of("layout: stage", "stage: 01", "phase: P", "technique: T1 | n", *facts),
        "6 fact lines",
    )
    # Control: the top of each range is clean.
    five = [f"fact: L{i} | v" for i in range(5)]
    assert _findings_of("layout: stage", "stage: 01", "phase: P", "technique: T1 | n", *five) == []
    assert _findings_of("layout: stats", *[f"stat: {i} | a | b" for i in range(4)]) == []


def _case_stage_requires_stage_and_phase(tmp: Path) -> None:
    base = ("layout: stage", "technique: T1 | n", "fact: L | v")
    _only(_findings_of(*base, "phase: P"), "needs a stage: line")
    _only(_findings_of(*base, "stage: 01"), "needs a phase: line")
    assert _findings_of(*base, "stage: 01", "phase: P") == []


def _case_background_requires_source(tmp: Path) -> None:
    _only(_findings_of("layout: background", "Text."), "needs a source: line")
    assert _findings_of("layout: background", "source: A | https://a.example/", "Text.") == []
    _raises(
        lambda: _parse(_slide_text("layout: background", "source: only a name", "Text.")),
        "source:",
    )


def _case_question_rejects_bullets(tmp: Path) -> None:
    _only(_findings_of("layout: question", "A question?", "- a bullet"), "prose only")
    assert _findings_of("layout: question", "A question?") == []
    assert any("needs prose" in f for f in _findings_of("layout: question", "- a bullet"))
    _only(_findings_of("layout: text"), "needs prose")


def _case_matrix_unknown_mark(tmp: Path) -> None:
    lines = ("layout: matrix", "columns: 01 | 02 | 03")
    assert _findings_of(*lines, "row: A | 01 | 02", "row: B | -") == []
    _only(_findings_of(*lines, "row: A | 01 | 09", "row: B | -"), "'09'")


def _case_table_ragged(tmp: Path) -> None:
    ok = ("layout: table", "row: A | B", "row: C | D")
    assert _findings_of(*ok) == []
    _only(_findings_of("layout: table", "row: A | B", "row: C | D | E"), "different widths")


def _case_bars_non_number(tmp: Path) -> None:
    _only(_findings_of("layout: bars", "bar: many | x", "bar: 5 | y"), "'many'")
    assert _findings_of("layout: bars", "bar: 1,500+ | x", "bar: 2.5 | y") == []
    for bad in ("inf", "nan", "1e5", "-3"):
        _only(_findings_of("layout: bars", f"bar: {bad} | x", "bar: 5 | y"), repr(bad))


def _case_missing_notes(tmp: Path) -> None:
    e = _raises(lambda: parse_outline_text(_outline("== S\nText.\n"), "d.deck"), "notes")
    assert str(e).startswith("d.deck:6:"), e
    _raises(lambda: parse_outline_text(_outline("== S\nText.\nnotes:\n\n"), "d.deck"), "notes")


def _case_slide_count(tmp: Path) -> None:
    for n, ok in ((14, False), (15, True), (33, True), (34, False)):
        f = style_findings(_deck_with(n))
        total = n + GENERATED_SLIDES
        if ok:
            assert f == [], (n, f)
        else:
            assert len(f) == 1 and f[0].startswith("d.deck:") and str(total) in f[0], (n, f)


def _case_too_many_words(tmp: Path) -> None:
    _only(_findings_of(" ".join(["w"] * 41)), "41 words")
    assert _findings_of(" ".join(["w"] * 40)) == []
    # Paragraphs and bullets count together.
    _only(_findings_of(" ".join(["w"] * 21), "- " + " ".join(["w"] * 20)), "41 words")


def _case_field_too_long(tmp: Path) -> None:
    long = " ".join(["w"] * 15)
    _only(_findings_of("layout: checklist", f"check: {long}", "check: ok"), "15 words")
    assert _findings_of("layout: checklist", "check: " + " ".join(["w"] * 14), "check: ok") == []


def _case_notes_too_long(tmp: Path) -> None:
    deck = _parse(_body("== S", "Text.", notes=" ".join(["w"] * 221)))
    _only(slide_findings(deck.slides[0]), "221 words")
    deck = _parse(_body("== S", "Text.", notes=" ".join(["w"] * 220)))
    assert slide_findings(deck.slides[0]) == []


def _case_heading_too_long(tmp: Path) -> None:
    h13 = " ".join(["h"] * 13)
    deck = _parse(_body(f"== {h13}", "Text."))
    _only(slide_findings(deck.slides[0]), "13 words")
    deck = _parse(_body("== " + " ".join(["h"] * 12), "Text."))
    assert slide_findings(deck.slides[0]) == []


def _case_dashes(tmp: Path) -> None:
    _only(
        _findings_of("layout: stage", "stage: 01", "phase: P", "technique: T1 | n",
                     f"fact: Queried | one{EN_DASH}two"),
        "dash",
    )
    _only(
        _findings_of("layout: stage", "stage: 01", "phase: P", "technique: T1 | n",
                     f"fact: one{EM_DASH}two | v"),
        "dash",
    )
    # The promise is shown on the cover, so it follows the same rule.
    deck = _deck_with(15)
    deck.promise = "a - b"
    f = style_findings(deck)
    assert len(f) == 1 and f[0].startswith("d.deck:") and "spaced hyphen" in f[0], f
    deck.promise = "a-b"
    assert style_findings(deck) == []
    # Control: a hyphen inside a word is fine.
    assert _findings_of("A well-known pipeline.") == []


def _case_notes_dash(tmp: Path) -> None:
    deck = _parse(_body("== S", "Text.", notes=f"one{EM_DASH}two"))
    _only(slide_findings(deck.slides[0]), "dash")
    deck = _parse(_body("== S", "Text.", notes="one - two"))
    _only(slide_findings(deck.slides[0]), "spaced hyphen")


def _case_prose_after_bullet(tmp: Path) -> None:
    f = _findings_of("Intro.", "- first", "Late prose.")
    _only(f, "prose after a bullet")
    # Line 9 of the outline: five header lines, the heading, then Intro, a bullet and the late prose.
    assert f[0].startswith("d.deck:9:"), f
    assert _findings_of("Intro.", "", "More intro.", "- first", "- second") == []


def _case_no_includes_or_fences(tmp: Path) -> None:
    _raises(lambda: _parse("== include: _x.deck\n"), "no includes")
    _raises(lambda: _parse(_slide_text("```", "code", "```")), "no code fences")


def _case_sha_changes(tmp: Path) -> None:
    a = parse_outline_text(SAMPLE, "a.deck")
    b = parse_outline_text(SAMPLE.replace("fleet", "fleat", 1), "a.deck")
    assert outline_sha256(a) == outline_sha256(parse_outline_text(SAMPLE, "a.deck"))
    assert outline_sha256(a) != outline_sha256(b)


CASES: list = [
    ("parse_ok", _case_parse_ok),
    ("missing_header", _case_missing_header),
    ("unknown_header_key", _case_unknown_header_key),
    ("bad_as_of", _case_bad_as_of),
    ("page_not_breaches", _case_page_not_breaches),
    ("unknown_layout", _case_unknown_layout),
    ("control_line_twice", _case_control_line_twice),
    ("unknown_line_key", _case_unknown_line_key),
    ("key_never_becomes_prose", _case_key_never_becomes_prose),
    ("notes_stay_notes", _case_notes_stay_notes),
    ("typed_line_empty_field", _case_typed_line_empty_field),
    ("typed_line_wrong_layout", _case_typed_line_wrong_layout),
    ("wrong_field_count", _case_wrong_field_count),
    ("count_out_of_range", _case_count_out_of_range),
    ("stage_requires_stage_and_phase", _case_stage_requires_stage_and_phase),
    ("background_requires_source", _case_background_requires_source),
    ("question_rejects_bullets", _case_question_rejects_bullets),
    ("matrix_unknown_mark", _case_matrix_unknown_mark),
    ("table_ragged", _case_table_ragged),
    ("bars_non_number", _case_bars_non_number),
    ("missing_notes", _case_missing_notes),
    ("slide_count", _case_slide_count),
    ("too_many_words", _case_too_many_words),
    ("field_too_long", _case_field_too_long),
    ("notes_too_long", _case_notes_too_long),
    ("heading_too_long", _case_heading_too_long),
    ("dashes", _case_dashes),
    ("notes_dash", _case_notes_dash),
    ("prose_after_bullet", _case_prose_after_bullet),
    ("no_includes_or_fences", _case_no_includes_or_fences),
    ("sha_changes", _case_sha_changes),
]


def self_test() -> int:
    return _run_cases(CASES, "self-test")


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
