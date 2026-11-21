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

Publishing machinery mirrors tools/build_howto_decks.py. The mapping
tools/decks/breaches/published.json holds, per slug, the Google Slides id,
the outline hash, the hash of the page's <main> text and the publish date. A
deck is stale when its outline or its page changed since it was recorded.
--stamp writes each mapped page's one deck line (data-breach-deck) right
after the last pm-link line in inc-header.

--build renders an outline to tools/decks/breaches/build/<slug>.pptx with
tools/breach_deck_render.py, the one breach deck module that imports
python-pptx. This tool imports the renderer only on the --build and
--self-test-render paths, so --check and --self-test run without python-pptx.

Usage:
    python3 tools/build_breach_decks.py --self-test
    python3 tools/build_breach_decks.py --check
    python3 tools/build_breach_decks.py --build SLUG [SLUG ...]
    python3 tools/build_breach_decks.py --self-test-render
    python3 tools/build_breach_decks.py --stale [--published-only]
    python3 tools/build_breach_decks.py --status
    python3 tools/build_breach_decks.py --stamp
    python3 tools/build_breach_decks.py --record SLUG PRES_ID
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import html as htmllib
import io
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_howto_decks import (  # noqa: E402
    EM_DASH,
    EN_DASH,
    SPACED_HYPHEN_RE,
    PRES_ID_RE,
    SHA256_RE,
    SLUG_RE,
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
# A flow step's technique field for a stage the page maps to no technique.
NO_TECHNIQUE = "-"


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
    # A stage the page maps to no ATT&CK technique (a detection or response
    # stage) still gets a slide, so a stage slide takes none to three.
    "stage": LayoutSpec(
        {"technique": (0, 3, 2, 2), "fact": (1, 5, 2, 2)},
        "optional",
        ("stage", "phase"),
    ),
    "background": LayoutSpec({}, "required", ("source",)),
    "question": LayoutSpec({}, "prose-only"),
    "answer": LayoutSpec({}, "required"),
    "checklist": LayoutSpec({"check": (2, 7, 1, 1)}, "optional"),
    "links": LayoutSpec({"link": (1, 8, 2, 2)}, "optional"),
    # A step's technique field is NO_TECHNIQUE for a stage with none. A chain
    # of more than eight stages takes more than one flow slide.
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
# Page model and page gate: what a breach page says, and whether a deck says
# only that.
# ---------------------------------------------------------------------------

DECK_ATTR = "data-breach-deck"
# A deck line is one <p> carrying data-breach-deck, alone on its line and
# closed on that line. Nothing it matches can reach past the line, so
# removing a match never takes other page content with it.
DECK_LINE_RE = re.compile(
    r"^[ \t]*<p[^>\n]*\bdata-breach-deck\b[^>\n]*>(?:(?!</p>)[^\n])*</p>[ \t]*(?:\n|\Z)",
    re.MULTILINE,
)

SITE = "https://csoh.org/"

# Hosts a background slide may cite. A host matches when it equals one of
# these or ends with "." plus one, so lookalikes such as evilcsoh.org fail.
BACKGROUND_HOSTS = (
    "csoh.org",
    "attack.mitre.org",
    "owasp.org",
    "cheatsheetseries.owasp.org",
    "learn.microsoft.com",
    "docs.aws.amazon.com",
    "cloud.google.com",
    "kubernetes.io",
    "www.rfc-editor.org",
    "datatracker.ietf.org",
    "docs.oasis-open.org",
)

# Tags that sit inside a line of prose. Removing them without a space keeps
# the page text, and so its hash, the same when the glossary cross-linker
# wraps a word in <a>. Every other tag becomes a space so that adjacent
# blocks ("04</div><div>Title") do not fuse into one token.
INLINE_TAGS = frozenset({"a", "strong", "em", "b", "i", "code", "abbr", "mark", "sup", "sub"})
TAG_RE = re.compile(r"</?([A-Za-z][A-Za-z0-9]*)\b[^>]*>")
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
MAIN_RE = re.compile(r"<main\b[^>]*>(.*)</main>", re.DOTALL | re.IGNORECASE)

# Digits not inside a word (IMDSv2, T1606, artx5v) and not a fragment of a
# larger token. A unit suffix is allowed ("500GB", "5x", "$1.4B" give 500, 5
# and 1.4) so a unit never hides a figure from the gate. The lookahead stops a
# match that backtracked short of a digit or decimal part ("1.4" never yields
# "1" and ".4"). Three or more dot-separated runs (a version such as 8.4.28,
# an IPv4 address, or a CIDR such as 10.0.0.0/8 with its prefix) are one
# token, matched first and compared whole.
NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9.])"
    r"(?:\d+(?:\.\d+){2,}(?:/\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?!\d|\.\d)"
)
TECHNIQUE_RE = re.compile(r"T\d{4}(?:\.\d{3})?")
STAGE_NUM_RE = re.compile(r"\d\d")


@dataclass
class PageStage:
    num: str
    title: str
    # Every ATT&CK link ID in the stage plus every tag chip shaped like a
    # technique ID.
    techniques: set[str] = field(default_factory=set)
    # The name of the phase label above the stage (see phase_name).
    phase: str = ""


@dataclass
class BreachPage:
    path: str
    stages: dict[str, PageStage]
    numbers: set[str]
    techniques: set[str]
    links: set[str]
    text: str


def _strip_tags(fragment: str) -> str:
    fragment = COMMENT_RE.sub("", fragment)
    fragment = TAG_RE.sub(lambda m: "" if m.group(1).lower() in INLINE_TAGS else " ", fragment)
    return " ".join(htmllib.unescape(fragment).split())


def _main_html(html: str) -> str:
    html = DECK_LINE_RE.sub("", html)
    m = MAIN_RE.search(html)
    if m is None:
        raise OutlineError("page has no <main> element")
    return m.group(1)


def main_text(html: str) -> str:
    """The page's <main> as plain text, with every deck line removed."""
    return _strip_tags(_main_html(html))


def page_sha256(html: str) -> str:
    return hashlib.sha256(main_text(html).encode("utf-8")).hexdigest()


def _normalize_number(raw: str) -> str:
    """The form two numbers are compared in: commas and leading zeros dropped
    ("1,500" and "1500" match), except that a dotted token (a version, an
    address or a CIDR) is kept exactly as written."""
    if raw.count(".") >= 2:
        return raw
    whole, dot, frac = raw.replace(",", "").partition(".")
    return (whole.lstrip("0") or "0") + dot + frac


def number_tokens(text: str) -> set[str]:
    return {_normalize_number(m.group(0)) for m in NUMBER_RE.finditer(text)}


def technique_ids(text: str) -> set[str]:
    return set(TECHNIQUE_RE.findall(text))


def normalize_url(url: str, base: str = SITE) -> str:
    """Absolute form with a trailing slash stripped and the fragment kept."""
    bare, frag = urldefrag(urljoin(base, url.strip()))
    return bare.rstrip("/") + (f"#{frag}" if frag else "")


STEP_OPEN_RE = re.compile(r'<div\b[^>]*\bclass="[^"]*\bkc-step\b[^"]*"[^>]*>')
STEP_END_RE = re.compile(r'<div\b[^>]*\bclass="[^"]*\b(?:kc-step|phase-lbl)\b')
STEP_NUM_RE = re.compile(r'class="step-num"[^>]*>\s*(\d+)\s*<')
STEP_TITLE_RE = re.compile(r'class="step-title"[^>]*>(.*?)</div>', re.DOTALL)
STEP_MT_RE = re.compile(r'<a\b[^>]*\bclass="mt[ "][^>]*>(.*?)</a>', re.DOTALL)
STEP_TAGS_RE = re.compile(r'<div\b[^>]*\bclass="step-tags"[^>]*>(.*?)</div>', re.DOTALL)
STAG_RE = re.compile(r'<span\b[^>]*\bclass="stag"[^>]*>(.*?)</span>', re.DOTALL)
HREF_RE = re.compile(r'<a\b[^>]*\bhref="([^"]*)"', re.IGNORECASE)
PHASE_LBL_RE = re.compile(r'<div\b[^>]*\bclass="phase-lbl\b[^"]*"[^>]*>(.*?)</div>', re.DOTALL)
# Emoji and the joiners and variation selectors that build them.
EMOJI_CATEGORIES = frozenset({"So", "Sk", "Cf"})
VARIATION_SELECTORS = frozenset({"︎", "️"})


def phase_name(text: str) -> str:
    """The name in a phase label or a phase: line: the text before its first
    colon, with emoji removed and spaces collapsed. The page's label
    "🔀 Execution and Privilege Escalation: Containers" and the outline's
    "Execution and Privilege Escalation" both give the same name."""
    head = text.split(":", 1)[0]
    kept = "".join(
        ch for ch in head
        if unicodedata.category(ch) not in EMOJI_CATEGORIES and ch not in VARIATION_SELECTORS
    )
    return " ".join(kept.split())


def parse_breach_page(html: str, path: str) -> BreachPage:
    """Read a breach page's <main>: its stages, numbers, technique IDs and links."""
    main = _main_html(html)
    text = _strip_tags(main)
    stages: dict[str, PageStage] = {}
    labels = [(m.start(), phase_name(_strip_tags(m.group(1)))) for m in PHASE_LBL_RE.finditer(main)]
    starts = [m.start() for m in STEP_OPEN_RE.finditer(main)]
    for start in starts:
        nxt = STEP_END_RE.search(main, start + 1)
        chunk = main[start : nxt.start() if nxt else len(main)]
        num = STEP_NUM_RE.search(chunk)
        if num is None:
            continue
        title = STEP_TITLE_RE.search(chunk)
        techniques: set[str] = set()
        # A stage header can carry several ATT&CK links; each one counts.
        for mt in STEP_MT_RE.finditer(chunk):
            techniques |= technique_ids(_strip_tags(mt.group(1)))
        tags = STEP_TAGS_RE.search(chunk)
        if tags:
            for chip in STAG_RE.findall(tags.group(1)):
                chip = _strip_tags(chip)
                if TECHNIQUE_RE.fullmatch(chip):
                    techniques.add(chip)
        phase = next((name for pos, name in reversed(labels) if pos < start), "")
        stages[num.group(1)] = PageStage(
            num.group(1), _strip_tags(title.group(1)) if title else "", techniques, phase
        )
    base = SITE + path
    links = {
        normalize_url(h, base)
        for h in HREF_RE.findall(main)
        if h.strip() and not h.strip().startswith(("#", "mailto:", "javascript:"))
    }
    return BreachPage(
        path=path,
        stages=stages,
        numbers=number_tokens(text),
        techniques=technique_ids(text),
        links=links,
        text=text,
    )


def _host_allowed(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.scheme not in ("http", "https") or not host:
        return False
    return any(host == h or host.endswith("." + h) for h in BACKGROUND_HOSTS)


def _slide_text_fields(s: BSlide) -> list[str]:
    """Every text the page gate reads on a non-background slide. The URL of a
    link line and of source: are left out: they carry digits and technique
    IDs that are not page text, and the link gate checks them."""
    out = [s.heading, *s.paragraphs, *s.bullets]
    for key, rows in s.items.items():
        for row in rows:
            out += row[:1] if key == "link" else row
    if s.credit:
        out.append(s.credit)
    out += s.notes
    return out


def _text_findings(where: str, texts: list[str], page: BreachPage) -> list[str]:
    """Numbers and technique IDs in `texts` that the page does not carry."""
    out: list[str] = []
    seen: set[str] = set()
    for text in texts:
        for m in NUMBER_RE.finditer(text):
            raw = m.group(0)
            if _normalize_number(raw) not in page.numbers and raw not in seen:
                seen.add(raw)
                out.append(f"{where}: number {raw} is not on the page")
        for tid in TECHNIQUE_RE.findall(text):
            if tid not in page.techniques and tid not in seen:
                seen.add(tid)
                out.append(f"{where}: technique {tid} is not on the page")
    return out


def _phase_finding(where: str, what: str, given: str, stage: PageStage) -> str | None:
    """A finding when `given` does not name stage's phase label on the page."""
    got, want = phase_name(given), stage.phase
    if got == want:
        return None
    if not want:
        return f"{where}: {what} {got!r}, but stage {stage.num} has no phase label on the page"
    return f"{where}: {what} {got!r} is not stage {stage.num}'s phase on the page, {want!r}"


def _slide_page_findings(s: BSlide, page: BreachPage) -> list[str]:
    out: list[str] = []
    stage_ok = s.stage is None or s.stage in page.stages
    if s.layout != "background":
        if s.stage is not None and not stage_ok:
            out.append(f"{s.where}: stage {s.stage} is not a stage on {page.path}")
        if stage_ok and s.stage is not None and s.phase is not None:
            f = _phase_finding(s.where, "phase", s.phase, page.stages[s.stage])
            if f:
                out.append(f)
        if s.layout == "stage" and stage_ok and s.stage is not None:
            for row in s.items.get("technique", []):
                if row[0] not in page.stages[s.stage].techniques:
                    out.append(
                        f"{s.where}: technique {row[0]} is not on stage {s.stage} of the page"
                    )
        if s.layout == "flow":
            for row in s.items.get("step", []):
                num, tactic, tech = row[0], row[1], row[3]
                if num not in page.stages:
                    out.append(f"{s.where}: flow step {num} is not a stage on {page.path}")
                    continue
                f = _phase_finding(s.where, f"flow step {num} tactic", tactic, page.stages[num])
                if f:
                    out.append(f)
                if tech != NO_TECHNIQUE and tech not in page.stages[num].techniques:
                    out.append(f"{s.where}: flow step {num} does not carry technique {tech}")
        if s.layout == "matrix":
            for label in s.items.get("columns", [[]])[0] if s.items.get("columns") else []:
                if STAGE_NUM_RE.fullmatch(label) and label not in page.stages:
                    out.append(f"{s.where}: matrix column {label} is not a stage on {page.path}")

        out += _text_findings(s.where, _slide_text_fields(s), page)

        urls = [row[1] for row in s.items.get("link", [])]
        if s.source:
            urls.append(s.source[1])
        for url in urls:
            if normalize_url(url) not in page.links:
                out.append(f"{s.where}: link {url} is not linked from the page")
    elif s.source and not _host_allowed(s.source[1]):
        out.append(
            f"{s.where}: background source {s.source[1]} is not on an allowed host"
        )
    return out


def page_findings(deck: BDeck, page: BreachPage, today: date | None = None) -> list[str]:
    """Every way the deck says something its breach page does not."""
    out: list[str] = []
    if deck.page != page.path:
        out.append(f"{deck.slug}.deck: page {deck.page} is not the parsed page {page.path}")
    if date.fromisoformat(deck.as_of) > (today or date.today()):
        out.append(f"{deck.slug}.deck: as-of {deck.as_of} is in the future")
    # The generated cover shows the title and promise, so they meet the same
    # number and technique gate as a slide.
    out += _text_findings(f"{deck.slug}.deck: title", [deck.title], page)
    out += _text_findings(f"{deck.slug}.deck: promise", [deck.promise], page)
    for s in deck.slides:
        out += _slide_page_findings(s, page)
    return out


# ---------------------------------------------------------------------------
# Paths, deck lines on breach pages, and the mapping file.
# ---------------------------------------------------------------------------

# Paths come from this file's location, not the working directory: a check run
# from elsewhere would find no outlines and no pages, and a check that reads
# nothing reports clean. _set_root() moves all four together for the
# self-test. Breach outlines live in their own subdirectory so the how-to
# tool, which globs tools/decks/*.deck without recursing, never reads them.
ROOT = Path(__file__).resolve().parents[1]
DECKS_DIR = ROOT / "tools" / "decks" / "breaches"
PAGES_DIR = ROOT / "breaches"
MAPPING = DECKS_DIR / "published.json"
BUILD_DIR = DECKS_DIR / "build"


def _set_root(root: Path) -> Path:
    """Point every path at root; returns the previous root."""
    global ROOT, DECKS_DIR, PAGES_DIR, MAPPING, BUILD_DIR
    old = ROOT
    ROOT = root
    DECKS_DIR = root / "tools" / "decks" / "breaches"
    PAGES_DIR = root / "breaches"
    MAPPING = DECKS_DIR / "published.json"
    BUILD_DIR = DECKS_DIR / "build"
    return old


def _rel(path: Path) -> str:
    """path relative to the repository root, for messages."""
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


PRESENTATION_RE = re.compile(r"docs\.google\.com/presentation\b")
ENTRY_KEYS = ("id", "outline_sha256", "page_sha256", "published")
# The indentation of the pm-link lines on every breach page.
PM_INDENT = "    "
HEADER_OPEN_RE = re.compile(r'^([ \t]*)<div\b[^>\n]*\bclass="inc-header"[^>\n]*>[ \t]*$', re.MULTILINE)
PM_LINK_RE = re.compile(r'^([ \t]*)<a class="pm-link"[^\n]*</a>[ \t]*$')


def deck_line_html(pres_id: str, indent: str = PM_INDENT) -> str:
    base = f"https://docs.google.com/presentation/d/{pres_id}"
    ext = 'target="_blank" rel="noopener noreferrer"'
    licence = "https://creativecommons.org/licenses/by-nc/4.0/"
    return (
        f'{indent}<p class="u-mt-075" {DECK_ATTR}><strong>Slides:</strong> '
        f'<a href="{base}/export/pdf" {ext}>download the PDF</a> or '
        f'<a href="{base}/copy" {ext}>make your own editable copy</a> '
        "(copying needs a Google account). The slides are licensed "
        f'<a href="{licence}" {ext}>CC BY-NC 4.0</a>.</p>'
    )


def loose_deck_markup(html: str) -> int:
    """data-breach-deck mentions that are not part of a whole deck line: a
    line missing its </p>, one written inline after other markup, or two on
    one line. --stamp cannot remove these without guessing."""
    return DECK_LINE_RE.sub("", html).count(DECK_ATTR)


def _last_pm_link_end(html: str) -> tuple[int, str] | None:
    """Where the deck line goes: the offset just past the last whole-line
    pm-link inside inc-header (the div opens on its own line and closes on a
    line starting with its own indentation and </div>), and that line's
    indentation. None when there is no such line."""
    m = HEADER_OPEN_RE.search(html)
    if m is None:
        return None
    close = re.compile(r"^" + re.escape(m.group(1)) + r"</div>", re.MULTILINE).search(html, m.end())
    if close is None:
        return None
    end = indent = None
    pos = m.end()
    for line in html[m.end() : close.start()].splitlines(keepends=True):
        pos += len(line)
        link = PM_LINK_RE.match(line.rstrip("\r\n"))
        if link:
            end, indent = pos, link.group(1)
    if end is None:
        return None
    if not html[:end].endswith("\n"):
        return None
    return end, indent


def _insert_deck_line(html: str, pres_id: str) -> str:
    spot = _last_pm_link_end(html)
    if spot is None:
        raise ValueError(
            'no <a class="pm-link"> line inside <div class="inc-header"> to put the deck line after'
        )
    end, indent = spot
    return html[:end] + deck_line_html(pres_id, indent) + "\n" + html[end:]


def stamp_page(html: str, pres_id: str | None) -> str:
    """The page as --stamp writes it: every deck line removed, then, when
    pres_id is given, one deck line right after the last pm-link line in
    inc-header. Raises ValueError when the page holds deck markup that is
    not a whole deck line, the id is not a Drive file id, or there is no
    pm-link line to put the deck line after."""
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
    """Disagreements between a breach page's deck markup and the mapping. A
    page in the mapping must hold exactly the one deck line --stamp writes,
    right after its last pm-link; a page outside it must hold no deck markup.
    Any Google Slides link outside the deck line is a finding either way."""
    page = f"breaches/{slug}.html"
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
    want = deck_line_html(pres_id).strip()
    if not lines and not loose:
        findings.append(f"{page}: {slug!r} is in the mapping but the page has no deck line")
    elif len(lines) > 1:
        findings.append(f"{page}: has {len(lines)} deck lines; it must have exactly one")
    elif lines and lines[0].strip() != want:
        findings.append(
            f"{page}: deck line is not the one --stamp writes for mapping id {pres_id!r}"
        )
    elif lines and not loose:
        try:
            if _insert_deck_line(rest, pres_id) != html:
                findings.append(
                    f"{page}: deck line is not where --stamp puts it (right after the "
                    "last pm-link line in inc-header); run --stamp"
                )
        except ValueError as e:
            findings.append(f"{page}: {e}")
    return findings


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


def save_mapping(mapping: dict) -> None:
    MAPPING.write_text(json.dumps(mapping, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def mapping_findings(mapping: dict, outlines: set[str], pages: set[str]) -> list[str]:
    """Every mapping entry that is malformed or names a deck the repo cannot
    account for: a slug with no outline or no breach page, an id that is not
    a Drive file id, a date that is not ISO, or a hash that is not sha256."""
    findings: list[str] = []
    name = _rel(MAPPING)
    for slug in sorted(mapping):
        entry = mapping[slug]
        where = f"{name}: {slug!r}"
        if not SLUG_RE.fullmatch(slug):
            findings.append(f"{where}: not a breach slug (lowercase letters, digits, hyphens)")
            continue
        if slug not in outlines:
            findings.append(f"{where}: has no outline {_rel(DECKS_DIR)}/{slug}.deck")
        if slug not in pages:
            findings.append(f"{where}: names no breach page")
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
        for key in ("outline_sha256", "page_sha256"):
            sha = entry.get(key)
            if key in entry and not (isinstance(sha, str) and SHA256_RE.fullmatch(sha)):
                findings.append(f"{where}: {key} {sha!r} is not a sha256 hex digest")
    return findings


# ---------------------------------------------------------------------------
# Modes: check, stale, status, stamp, record.
# ---------------------------------------------------------------------------


def outline_paths() -> list[Path]:
    return sorted(DECKS_DIR.glob("*.deck"))


def breach_pages() -> list[Path]:
    return sorted(PAGES_DIR.glob("*.html"))


def tree_problem() -> str | None:
    """Why the outlines or breach pages cannot be found, or None. Every mode
    that reads the tree stops on this rather than report on nothing."""
    if not outline_paths():
        return f"no outlines found in {DECKS_DIR}"
    if not breach_pages():
        return f"no breach pages found in {PAGES_DIR}"
    return None


def outline_findings(path: Path) -> list[str]:
    """Every finding for one outline: a parse error, the style limits, and
    what the deck says that its breach page does not. --check reports these
    and --build refuses an outline that has any."""
    try:
        deck = parse_outline(path)
    except OutlineError as e:
        return [str(e)]
    findings = style_findings(deck)
    want = f"breaches/{deck.slug}.html"
    if deck.page != want:
        findings.append(f"{path.name}: page must be {want}, got {deck.page}")
        return findings
    page_path = ROOT / deck.page
    if not page_path.exists():
        findings.append(f"{path.name}: page {deck.page} does not exist")
        return findings
    try:
        page = parse_breach_page(page_path.read_text(encoding="utf-8"), deck.page)
    except OutlineError as e:
        findings.append(f"{deck.page}: {e}")
        return findings
    return findings + page_findings(deck, page)


def check_all() -> int:
    problem = tree_problem()
    if problem:
        print(f"breach decks: {problem}; nothing was checked")
        return 1
    findings: list[str] = []
    mapping, map_problem = read_mapping()
    if map_problem:
        findings.append(map_problem)
    outlines = outline_paths()
    for path in outlines:
        findings += outline_findings(path)
    pages = breach_pages()
    findings += mapping_findings(mapping, {p.stem for p in outlines}, {p.stem for p in pages})
    # An unreadable mapping would make every deck line read as unmapped.
    if not map_problem:
        for page in pages:
            findings += link_findings(page.stem, page.read_text(encoding="utf-8"), mapping)
    for f in findings:
        print(f)
    print(
        f"breach decks: {len(outlines)} outlines checked, {len(pages)} breach pages checked, "
        f"{len(findings)} findings"
    )
    return 1 if findings else 0


def _stale_reasons(slug: str, entry, path: Path | None) -> list[str]:
    """Why a published deck no longer matches its outline or its page, or []."""
    if path is None:
        return [f"published, but {_rel(DECKS_DIR)}/{slug}.deck is missing"]
    try:
        deck = parse_outline(path)
    except OutlineError as e:
        return [f"outline does not parse, so whether it changed is unknown: {e}"]
    entry = entry if isinstance(entry, dict) else {}
    when = entry.get("published")
    reasons: list[str] = []
    if entry.get("outline_sha256") != outline_sha256(deck):
        reasons.append(
            f"outline changed since it was published on {when}; the public deck needs re-publishing"
        )
    page_path = PAGES_DIR / f"{slug}.html"
    try:
        page_hash = page_sha256(page_path.read_text(encoding="utf-8"))
    except (OSError, OutlineError) as e:
        reasons.append(f"page cannot be read, so whether it changed is unknown: {e}")
    else:
        if entry.get("page_sha256") != page_hash:
            reasons.append(
                f"page changed since it was published on {when}; review the deck against the page"
            )
    return reasons


def stale_report(published_only: bool = False) -> int:
    """Print one line per reason a published deck is behind (its outline or
    its page changed since --record) and, unless published_only, one per
    outline never published, then a summary line starting "stale check:".
    Staleness never fails: it exits 0 whether or not decks are stale, and 1
    only when the outlines, the breach pages or the mapping cannot be read."""
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
        reasons = _stale_reasons(slug, mapping[slug], outlines.get(slug))
        if reasons:
            stale += 1
            for reason in reasons:
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
    for page in breach_pages():
        has_outline = "yes" if page.stem in outlines else "no"
        published = "yes" if page.stem in mapping else "no"
        print(f"{page.stem}: outline {has_outline}, published {published}")
    return 0


def plan_stamps(mapping: dict) -> tuple[dict[Path, str], list[str]]:
    """The new text of every breach page --stamp would change, and every page
    it cannot stamp. Nothing is written."""
    changes: dict[Path, str] = {}
    errors: list[str] = []
    for page in breach_pages():
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
    return changes, errors


def _write_stamps(mapping: dict, label: str, save: bool) -> int:
    """Check the mapping and plan every page first. On any error, print them
    all and write nothing, so no run leaves some pages stamped and others
    not, or a mapping its pages disagree with. Otherwise save the mapping
    when asked, then write the changed pages."""
    pages = {p.stem for p in breach_pages()}
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
        errors.append(f"record: no outline {_rel(DECKS_DIR)}/{slug}.deck")
    if not PRES_ID_RE.fullmatch(pres_id):
        errors.append(f"record: {pres_id!r} is not a Google Slides presentation id")
    if errors:
        print("\n".join(errors))
        return 1
    # A recorded outline must pass --check, or the publish commit fails CI.
    findings = outline_findings(DECKS_DIR / f"{slug}.deck")
    if findings:
        print("\n".join(findings))
        print("record: refused, nothing written; fix the findings above")
        return 1
    try:
        deck = parse_outline(DECKS_DIR / f"{slug}.deck")
        page_hash = page_sha256((PAGES_DIR / f"{slug}.html").read_text(encoding="utf-8"))
    except (OSError, OutlineError) as e:
        print(f"record: {e}")
        return 1
    mapping, problem = read_mapping()
    if problem:
        print(f"record: {problem}")
        return 1
    mapping[slug] = {
        "id": pres_id,
        "outline_sha256": outline_sha256(deck),
        "page_sha256": page_hash,
        "published": date.today().isoformat(),
    }
    return _write_stamps(mapping, "record", save=True)


def build_decks(slugs: list[str]) -> int:
    """Render the named outlines to BUILD_DIR/<slug>.pptx. An unknown slug
    stops the run before anything is built. A deck's old build is removed
    first, so a refused or failed build never leaves a file that looks
    current. An outline with any finding --check reports is refused; a
    written file is reopened and verified, and removed when verification
    finds anything. Every .pptx in the build directory therefore passed
    verification when it was written."""
    known = {p.stem: p for p in outline_paths()}
    unknown = [sl for sl in slugs if sl not in known]
    if unknown:
        for sl in unknown:
            print(f"build: no outline {_rel(DECKS_DIR)}/{sl}.deck")
        return 1
    try:
        import breach_deck_render as render
    except ImportError as e:
        print(f"build: cannot import the renderer (pip install python-pptx): {e}")
        return 1
    bad = 0
    outlines = [known[sl] for sl in dict.fromkeys(slugs)]
    for path in outlines:
        out = BUILD_DIR / f"{path.stem}.pptx"
        out.unlink(missing_ok=True)
        findings = outline_findings(path)
        if findings:
            print("\n".join(findings))
            print(f"{path.name}: refused, fix the findings above")
            bad += 1
            continue
        deck = parse_outline(path)
        try:
            render.render_deck(deck, out)
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


PAGE_PATH = "breaches/vapor-panda-artex.html"


PHASE_01 = "🧰 Resource Development: Agents With a Human at the Decision Points"
PHASE_04 = (
    '🔑 <a class="glossary-link" href="../glossary.html#term-credential-access">'
    "Credential Access</a>: The Metadata Service"
)


def _breach_page(stages=None, body="", links=(), nav="Nav 999"):
    """A synthetic breach page in the real markup. `stages` is a list of
    (num, title, [technique ids], phase label HTML or None); the first
    technique is the stage's ATT&CK link and the rest are tag chips. A stage
    with a label gets a phase-lbl line above it; one without sits under the
    label before it."""
    if stages is None:
        stages = [
            ("01", "Agents planned the run", ["T1588.007", "T1606"], PHASE_01),
            ("04", "The metadata service yielded a role", ["T1552.005", "T1651"], PHASE_04),
        ]
    steps = []
    for num, title, techs, label in stages:
        chips = "".join(f'<span class="stag">{t}</span>' for t in techs[1:])
        if label:
            steps.append(f'    <div class="phase-lbl ph-cred">{label}</div>\n')
        steps.append(
            '    <div class="kc-step step-p">\n'
            f'      <div class="step-num">{num}</div>\n'
            '      <div class="step-body">\n'
            '        <div class="step-hdr">\n'
            f'          <div class="step-title">{title}</div>\n'
            f'          <a class="mt mt-ca" href="https://attack.mitre.org/techniques/x/">{techs[0]} - Name</a>\n'
            "        </div>\n"
            f'        <p class="step-desc">The agent asked for credentials at 140 hosts.</p>\n'
            f'        <div class="step-tags"><span class="stag">IMDS</span>{chips}</div>\n'
            "      </div>\n"
            "    </div>\n"
        )
    pm = "".join(f'    <a class="pm-link" href="{h}">Link</a>\n' for h in links)
    return (
        "<html><body><header><nav>" + nav + "</nav></header>\n"
        '<main class="kc-main kc-page" id="main-content">\n'
        '  <div class="inc-header">\n' + pm + "  </div>\n"
        '  <div class="kill-chain">\n'
        + "".join(steps)
        + body
        + "  </div>\n</main>\n<footer>Footer 888</footer></body></html>\n"
    )


def _gate_html(body: str = "") -> str:
    return _breach_page(
        # The sample header's promise carries 200 and 11, which the cover
        # gate reads.
        body='    <p class="inc-summary">200 organizations in 11 days.</p>\n' + body,
        links=("storm-0940-connectwise.html", "https://example.com/report", "../glossary.html")
    )


def _gate_page(body: str = "") -> BreachPage:
    return parse_breach_page(_gate_html(body), PAGE_PATH)


def _gate(*lines: str, notes: str = "Notes.", page: BreachPage | None = None) -> list[str]:
    deck = _parse(_body("== S", *lines, notes=notes))
    return page_findings(deck, page or _gate_page())


STAGE_LINES = (
    "layout: stage", "stage: 04", "phase: Credential Access",
    "technique: T1552.005 | Cloud Instance Metadata API", "fact: Queried | the service",
)


def _case_page_parse_real(tmp: Path) -> None:
    """The page's structure only, so a rewrite of its prose or glossary links
    does not fail the deck self-test; --check ties the outline's figures to
    the page."""
    path = Path(__file__).resolve().parent.parent / PAGE_PATH
    page = parse_breach_page(path.read_text(encoding="utf-8"), PAGE_PATH)
    assert list(page.stages) == [f"0{i}" for i in range(1, 8)], list(page.stages)
    assert page.stages["04"].techniques == {"T1552.005", "T1651"}, page.stages["04"].techniques
    assert "https://csoh.org/breaches/storm-0940-connectwise.html" in page.links
    # Control: the nav sits outside <main> and is not read.
    assert "Support" not in page.text


def _case_page_parse_synthetic(tmp: Path) -> None:
    page = _gate_page()
    assert list(page.stages) == ["01", "04"]
    assert page.stages["01"].techniques == {"T1588.007", "T1606"}
    assert page.stages["04"].title == "The metadata service yielded a role"
    # The label's emoji, glossary link and subtitle are not part of the name.
    assert page.stages["01"].phase == "Resource Development", page.stages["01"].phase
    assert page.stages["04"].phase == "Credential Access", page.stages["04"].phase
    assert "999" not in page.numbers and "888" not in page.numbers
    assert page.links == {
        "https://csoh.org/breaches/storm-0940-connectwise.html",
        "https://example.com/report",
        "https://csoh.org/glossary.html",
        "https://csoh.org/glossary.html#term-credential-access",
        "https://attack.mitre.org/techniques/x",
    }, page.links


def _case_stage_every_mt_link(tmp: Path) -> None:
    second = '<a class="mt mt-ex" href="https://attack.mitre.org/techniques/T1059/001/">T1059.001 - PowerShell</a>\n'
    first = 'T1552.005 - Name</a>\n'
    page = parse_breach_page(_plant(_gate_html(), first, first + second), PAGE_PATH)
    assert page.stages["04"].techniques == {"T1552.005", "T1651", "T1059.001"}, page.stages["04"]
    assert "T1059.001" not in page.stages["01"].techniques
    # A stage slide and a flow step may name the second link's technique.
    lines = list(STAGE_LINES)
    lines[3] = "technique: T1059.001 | PowerShell"
    assert _gate(*lines, page=page) == []
    flow = ("layout: flow", "step: 01 | Resource Development | Plan | T1588.007",
            "step: 04 | Credential Access | Meta | T1059.001",
            "step: 04 | Credential Access | More | T1651")
    assert _gate(*flow, page=page) == []
    # Control: without the second link it is neither the stage's nor the page's.
    f = _gate(*lines)
    assert len(f) == 2 and "not on stage 04" in f[0] and "not on the page" in f[1], f
    # A real page whose stage header carries two ATT&CK links.
    real = "breaches/3cx-x-trader.html"
    html = (Path(__file__).resolve().parent.parent / real).read_text(encoding="utf-8")
    techniques = parse_breach_page(html, real).stages["01"].techniques
    assert {"T1195.002", "T1204.002"} <= techniques, techniques


def _case_numbers_normalized(tmp: Path) -> None:
    got = number_tokens("1,500+ an hour, 1.4 billion, 70%, IMDSv2, T1606, artx5v, 04")
    assert got == {"1500", "1.4", "70", "4"}, got
    # A unit suffix does not hide the figure; a digit inside a word still does.
    assert number_tokens("4x or 3GB") == {"4", "3"}
    assert number_tokens("$1.4B, 30min, 1st, 500GB") == {"1.4", "30", "1", "500"}
    assert number_tokens("IMDSv2 T1606 artx5v") == set()
    # A sentence-final period does not make a decimal.
    assert number_tokens("It took 11. Then 0.5") == {"11", "0.5"}
    assert technique_ids("T1552.005, T1651 and T12") == {"T1552.005", "T1651"}


def _case_numbers_dotted(tmp: Path) -> None:
    # A version, an address and a CIDR are each one token, kept whole.
    assert number_tokens("PAN-OS 8.4.28 and 10.2.9-h1") == {"8.4.28", "10.2.9"}
    assert number_tokens("from 192.168.1.1 to 10.0.0.0/8.") == {"192.168.1.1", "10.0.0.0/8"}
    assert number_tokens("Python 3.11.4, then 8.4.27/8.4.28") == {"3.11.4", "8.4.27", "8.4.28"}
    assert number_tokens("host 010.0.0.1") == {"010.0.0.1"}
    # Controls: decimals, grouped figures and dates read as before, and a
    # dotted run inside a word is still not a number.
    assert number_tokens("1.4 billion, 1,500+, 2026-11-20, 11/20/2026") == {
        "1.4", "1500", "2026", "11", "20"
    }
    assert number_tokens("X_TRADER_r7.17.90p608.exe") == set()
    page = _gate_page('    <p class="step-desc">Fixed in 8.4.28; 10.0.0.0/8 was open.</p>\n')
    assert _gate("- Patch to 8.4.28, close 10.0.0.0/8.", page=page) == []
    _only(_gate("- Patch to 8.4.29.", page=page), "number 8.4.29 is not on the page")
    _only(_gate("- Close 10.0.0.0/16.", page=page), "10.0.0.0/16")
    # Part of a version is not the version.
    _only(_gate("- Patch to 8.4.", page=page), "number 8.4 is not on the page")


def _case_page_hash_stable(tmp: Path) -> None:
    base = _breach_page()
    h = page_sha256(base)
    # A wrapped word followed by punctuation: a tag turned into a space
    # would leave "hosts ." and change the hash.
    glossed = base.replace(
        "140 hosts.", '140 <a class="glossary-link" href="../glossary.html#x">hosts</a>.', 1)
    assert glossed != base
    assert page_sha256(glossed) == h
    decked = base.replace(
        '  <div class="kill-chain">',
        f'  <p class="deck-line" {DECK_ATTR}="x"><a href="d.pptx">Deck</a></p>\n  <div class="kill-chain">', 1)
    assert decked != base and page_sha256(decked) == h
    assert page_sha256(_breach_page(nav="Other nav 123")) == h
    changed = base.replace("credentials", "secrets", 1)
    assert changed != base and page_sha256(changed) != h
    # A deck line not alone on its line is page content, so it is not removed.
    assert DECK_LINE_RE.search(f'x <p {DECK_ATTR}>a</p>\n') is None


def _case_stage_unknown(tmp: Path) -> None:
    _only(_gate(*STAGE_LINES[:1], "stage: 09", *STAGE_LINES[2:]), "stage 09")
    assert _gate(*STAGE_LINES) == []


def _case_stage_technique_not_on_stage(tmp: Path) -> None:
    lines = list(STAGE_LINES)
    lines[3] = "technique: T1606 | Forge Web Credentials"
    # T1606 is on the page (stage 01), so only the stage check can catch it.
    f = _gate(*lines)
    _only(f, "T1606")
    assert "stage 04" in f[0]


RD, CA = "Resource Development", "Credential Access"


def _case_flow_step_checked(tmp: Path) -> None:
    ok = ("layout: flow", f"step: 01 | {RD} | Plan | T1588.007",
          f"step: 04 | {CA} | Meta | T1552.005", f"step: 04 | {CA} | More | T1651")
    assert _gate(*ok) == []
    bad = ("layout: flow", f"step: 01 | {RD} | Plan | T1588.007",
           f"step: 04 | {CA} | Meta | T1606", f"step: 04 | {CA} | More | T1651")
    _only(_gate(*bad), "does not carry technique T1606")
    unknown = ("layout: flow", f"step: 01 | {RD} | Plan | T1588.007",
               f"step: 09 | {CA} | Meta | T1552.005", f"step: 04 | {CA} | More | T1651")
    assert any("flow step 09" in f for f in _gate(*unknown)), _gate(*unknown)


def _case_stage_without_techniques(tmp: Path) -> None:
    # A stage slide with no technique line parses and meets the limits.
    no_tech = ("layout: stage", "stage: 04", f"phase: {CA}", "fact: Queried | the service")
    deck = _parse(_slide_text(*no_tech))
    assert "technique" not in deck.slides[0].items
    assert [f for s in deck.slides for f in slide_findings(s)] == []
    assert _gate(*no_tech) == []
    # Control: four technique lines are still too many.
    four = [f"technique: T155{i} | n" for i in range(4)]
    _only(_findings_of(*no_tech, *four), "4 technique lines")
    # A flow step for a stage with no technique writes "-" and is not checked.
    flow = ("layout: flow", f"step: 01 | {RD} | Plan | -",
            f"step: 04 | {CA} | Meta | T1552.005", f"step: 04 | {CA} | More | {NO_TECHNIQUE}")
    assert _gate(*flow) == []
    # Control: a technique the stage does not carry is still a finding.
    f = _gate(*flow[:1], f"step: 01 | {RD} | Plan | T9999", *flow[2:])
    assert any("flow step 01 does not carry technique T9999" in x for x in f), f


def _case_phase_checked(tmp: Path) -> None:
    assert phase_name("🔀 Execution and Privilege Escalation: Containers") == (
        "Execution and Privilege Escalation"
    )
    assert phase_name("🛠️  Response") == "Response"
    assert phase_name("Credential Access: The Metadata Service") == CA
    # The real pilot passes --check; here a slide's phase must name its stage's
    # label, with or without a subtitle.
    assert _gate(*STAGE_LINES) == []
    with_subtitle = list(STAGE_LINES)
    with_subtitle[2] = "phase: Credential Access: The Metadata Service"
    assert _gate(*with_subtitle) == []
    planted = list(STAGE_LINES)
    planted[2] = "phase: Stealth"
    f = _gate(*planted)
    _only(f, "phase 'Stealth' is not stage 04's phase on the page, 'Credential Access'")
    # A non-stage slide naming a stage and a phase is held to the same rule.
    _only(_gate("stage: 01", "phase: Discovery", "Text."), "'Resource Development'")
    flow = ("layout: flow", f"step: 01 | {RD} | Plan | T1588.007",
            "step: 04 | Stealth | Meta | T1552.005", f"step: 04 | {CA} | More | T1651")
    _only(_gate(*flow), "flow step 04 tactic 'Stealth' is not stage 04's phase")
    # A stage under no phase label: any phase is a finding that says so.
    bare = parse_breach_page(
        _breach_page(
            stages=[("04", "Untitled", ["T1552.005"], None)],
            body='    <p class="inc-summary">200 organizations in 11 days.</p>\n',
        ),
        PAGE_PATH,
    )
    assert bare.stages["04"].phase == ""
    _only(_gate(*STAGE_LINES, page=bare), "has no phase label on the page")


def _case_matrix_columns_checked(tmp: Path) -> None:
    assert _gate("layout: matrix", "columns: 01 | 04", "row: A | 01", "row: B | -") == []
    f = _gate("layout: matrix", "columns: 01 | 09", "row: A | 01", "row: B | -")
    assert any("matrix column 09" in x for x in f), f
    # A label that is not two digits is a label, not a stage reference.
    assert _gate("layout: matrix", "columns: Yes | No", "row: A | Yes", "row: B | -") == []


def _case_number_not_on_page(tmp: Path) -> None:
    assert _gate("- 140 hosts, 1,500+ or 70%.".replace("1,500+ or 70%", "140")) == []
    f = _gate("- 141 hosts were reached.")
    _only(f, "141")
    assert f[0].startswith("d.deck:"), f
    # Control: a heading is read too.
    deck = _parse(_body("== The 141 hosts", "Text."))
    assert any("141" in x for x in page_findings(deck, _gate_page()))


def _case_unit_suffixed_number(tmp: Path) -> None:
    # The page has 140 but not 500.
    _only(_gate("- 500GB was copied."), "500")
    assert _gate("- 140GB was copied.") == []
    _only(_gate("- About $1.4B."), "1.4")


def _case_source_on_non_background(tmp: Path) -> None:
    on = ("source: Report | https://example.com/report/", "Text.")
    assert _gate(*on) == []
    f = _gate("source: Report | https://example.com/other", "Text.")
    _only(f, "https://example.com/other")


def _case_cover_checked(tmp: Path) -> None:
    deck = _parse(_body("== S", "Text."))
    page = _gate_page()
    deck.promise = "Agents reached 140 hosts."
    assert page_findings(deck, page) == []
    deck.promise = "Agents reached 141 hosts."
    f = page_findings(deck, page)
    _only(f, "141")
    assert f[0].startswith("d.deck: promise"), f
    deck.promise = "Fine."
    deck.title = "T1059 and 4096"
    f = page_findings(deck, page)
    assert len(f) == 2 and all(x.startswith("d.deck: title") for x in f), f


def _case_technique_not_on_page(tmp: Path) -> None:
    _only(_gate("- T1059 ran."), "T1059")
    assert _gate("- T1552.005 ran.") == []


def _case_notes_checked(tmp: Path) -> None:
    _only(_gate("Text.", notes="141 hosts."), "141")
    _only(_gate("Text.", notes="Used T1059."), "T1059")
    bg = ("layout: background", "source: AWS | https://docs.aws.amazon.com/x", "Text 141 T1059.")
    assert _gate(*bg, notes="141 and T1059.") == []


def _case_links_resolve(tmp: Path) -> None:
    ok = ("layout: links", "link: Related | breaches/storm-0940-connectwise.html",
          "link: Report | https://example.com/report/")
    assert _gate(*ok) == []
    f = _gate("layout: links", "link: Related | breaches/storm-0940-connectwise.html",
              "link: Other | https://example.com/other")
    _only(f, "https://example.com/other")
    # Control: the same digits in prose would be a number finding.
    assert _gate("- 0940 hosts.") != []


def _case_background_exempt(tmp: Path) -> None:
    aws = "https://docs.aws.amazon.com/AWSEC2/x"
    assert _gate("layout: background", f"source: AWS | {aws}", "IMDSv2 adds 4096 bytes, T1059.") == []
    f = _gate("layout: background", "source: Blog | https://medium.com/p", "Text.")
    _only(f, "medium.com")
    # A lookalike host is not a subdomain.
    f = _gate("layout: background", "source: X | https://evilcsoh.org/p", "Text.")
    _only(f, "evilcsoh.org")
    assert _gate("layout: background", "source: S | https://www.csoh.org/p", "Text.") == []


def _case_as_of_not_future(tmp: Path) -> None:
    deck = _parse(_body("== S", "Text."))
    page = _gate_page()
    assert page_findings(deck, page, today=date(2026, 11, 20)) == []
    f = page_findings(deck, page, today=date(2026, 11, 19))
    _only(f, "in the future")
    deck.page = "breaches/other.html"
    assert any("not the parsed page" in x for x in page_findings(deck, page))


ID_A = "1" + "A" * 43
ID_B = "1" + "B" * 43
PM_PAGE = _breach_page(links=("https://example.com/a", "https://example.com/b"))
LAST_PM = '    <a class="pm-link" href="https://example.com/b">Link</a>\n'


def _deck_lines(html: str) -> list[str]:
    return [ln for ln in html.split("\n") if DECK_ATTR in ln]


def _plant(s: str, old: str, new: str) -> str:
    """s with old replaced once; fails when the plant would change nothing."""
    out = s.replace(old, new, 1)
    assert out != s, f"plant did nothing: {old!r}"
    return out


def _stamp_refused(html: str, pres_id: str | None, needle: str) -> None:
    try:
        stamp_page(html, pres_id)
    except ValueError as e:
        assert needle in str(e), (needle, str(e))
        return
    raise AssertionError(f"stamp_page accepted a page it should refuse ({needle})")


def _case_stamp_insert(tmp: Path) -> None:
    out = stamp_page(PM_PAGE, ID_A)
    line = deck_line_html(ID_A)
    assert _deck_lines(out) == [line], out
    assert line.startswith("    <p class=\"u-mt-075\" data-breach-deck>"), line
    assert out == _plant(PM_PAGE, LAST_PM, LAST_PM + line + "\n"), out
    # Control: the line is after the last pm-link, not after the first.
    first = '    <a class="pm-link" href="https://example.com/a">Link</a>\n'
    assert first + line not in out


def _case_stamp_idempotent(tmp: Path) -> None:
    once = stamp_page(PM_PAGE, ID_A)
    assert stamp_page(once, ID_A) == once


def _case_stamp_new_id(tmp: Path) -> None:
    out = stamp_page(stamp_page(PM_PAGE, ID_A), ID_B)
    assert _deck_lines(out) == [deck_line_html(ID_B)], out


def _case_stamp_remove(tmp: Path) -> None:
    assert stamp_page(stamp_page(PM_PAGE, ID_A), None) == PM_PAGE
    # A page with no pm-link can still be unstamped.
    assert stamp_page("<main><p>none</p></main>", None) == "<main><p>none</p></main>"


def _case_stamp_no_pm_link(tmp: Path) -> None:
    _stamp_refused(_breach_page(links=()), ID_A, "pm-link")
    _stamp_refused("<main><p>none</p></main>", ID_A, "pm-link")
    # A pm-link outside inc-header does not count.
    outside = _plant(_breach_page(links=()), "</main>", '<a class="pm-link" href="x">x</a>\n</main>')
    _stamp_refused(outside, ID_A, "pm-link")
    _stamp_refused(PM_PAGE, 'X" onmouseover="alert(1)', "not a Google Slides presentation id")


def _case_stamp_normal_form(tmp: Path) -> None:
    """--stamp writes one line, right after the last pm-link, whatever was there."""
    good = stamp_page(PM_PAGE, ID_A)
    line = deck_line_html(ID_A) + "\n"
    extra = _plant(good, "</main>\n", line + "</main>\n")
    second = _plant(good, "</main>\n", deck_line_html(ID_B) + "\n</main>\n")
    moved = _plant(_plant(good, line, ""), '  <div class="kill-chain">\n', line + '  <div class="kill-chain">\n')
    for planted in (extra, second, moved):
        assert stamp_page(planted, ID_A) == good, planted
        assert stamp_page(planted, None) == PM_PAGE, planted


def _case_stamp_refuses_loose_markup(tmp: Path) -> None:
    good = stamp_page(PM_PAGE, ID_A)
    broken = _plant(good, "CC BY-NC 4.0</a>.</p>\n", "CC BY-NC 4.0</a>.\n")
    _stamp_refused(broken, ID_A, "outside a whole deck line")
    _stamp_refused(broken, None, "outside a whole deck line")
    inline = _plant(PM_PAGE, '<div class="inc-header">\n', '<div class="inc-header">' + deck_line_html(ID_A).strip() + "\n")
    _stamp_refused(inline, None, "outside a whole deck line")
    two = _plant(good, ".</p>\n", ".</p>" + deck_line_html(ID_B).strip() + "\n")
    _stamp_refused(two, ID_A, "outside a whole deck line")


def _case_links_unmapped_line(tmp: Path) -> None:
    f = link_findings("g", stamp_page(PM_PAGE, ID_A), {})
    assert len(f) == 1 and "breaches/g.html" in f[0] and "not in the mapping" in f[0], f


def _case_links_missing_line(tmp: Path) -> None:
    f = link_findings("g", PM_PAGE, {"g": {"id": ID_A}})
    assert len(f) == 1 and "no deck line" in f[0], f
    assert link_findings("g", PM_PAGE, {}) == []


def _case_links_wrong_id(tmp: Path) -> None:
    f = link_findings("g", stamp_page(PM_PAGE, ID_A), {"g": {"id": ID_B}})
    assert len(f) == 1 and "not the one --stamp writes" in f[0], f
    assert link_findings("g", stamp_page(PM_PAGE, ID_B), {"g": {"id": ID_B}}) == []
    # A malformed entry is mapping_findings' to report.
    good = stamp_page(PM_PAGE, ID_A)
    assert link_findings("g", good, {"g": {}}) == []
    assert link_findings("g", good, {"g": "not an object"}) == []


def _case_links_every_line(tmp: Path) -> None:
    good = stamp_page(PM_PAGE, ID_A)
    m = {"g": {"id": ID_A}}
    assert link_findings("g", good, m) == []
    line = deck_line_html(ID_A) + "\n"
    planted = {
        "duplicate": (_plant(good, "</main>\n", line + "</main>\n"), "2 deck lines"),
        "moved": (
            _plant(_plant(good, line, ""), '  <div class="kill-chain">\n', line + '  <div class="kill-chain">\n'),
            "not where --stamp puts it",
        ),
        "unclosed": (_plant(good, "CC BY-NC 4.0</a>.</p>\n", "CC BY-NC 4.0</a>.\n"), "outside a whole deck line"),
    }
    for label, (html, needle) in planted.items():
        f = link_findings("g", html, m)
        assert any(needle in x for x in f), (label, f)


def _case_links_slides_link_elsewhere(tmp: Path) -> None:
    other = f"https://docs.google.com/presentation/d/{ID_B}/edit"
    html = _plant(stamp_page(PM_PAGE, ID_A), "</main>", f'<a href="{other}">deck</a></main>')
    f = link_findings("g", html, {"g": {"id": ID_A}})
    assert len(f) == 1 and "outside its deck line" in f[0], f
    f = link_findings("g", _plant(PM_PAGE, "</main>", f'<a href="{other}">deck</a></main>'), {})
    assert len(f) == 1 and "outside its deck line" in f[0], f


def _entry(pres_id: str = ID_A, sha: str = "0" * 64, page_sha: str = "1" * 64,
           published: str = "2026-01-02") -> dict:
    return {"id": pres_id, "outline_sha256": sha, "page_sha256": page_sha, "published": published}


def _case_mapping_findings(tmp: Path) -> None:
    with _rooted(tmp):
        ok = {"g": _entry()}
        assert mapping_findings(ok, {"g"}, {"g"}) == []
        planted = {
            "markup id": ({"g": _entry(pres_id='X" onmouseover="alert(1)')}, "not a Google Slides"),
            "missing key": ({"g": {k: v for k, v in _entry().items() if k != "page_sha256"}}, "keys must be exactly"),
            "extra key": ({"g": {**_entry(), "note": "x"}}, "keys must be exactly"),
            "bad date": ({"g": _entry(published="20 Nov 2026")}, "not a YYYY-MM-DD date"),
            "impossible date": ({"g": _entry(published="2026-02-30")}, "not a YYYY-MM-DD date"),
            "bad outline sha": ({"g": _entry(sha="abc")}, "outline_sha256"),
            "bad page sha": ({"g": _entry(page_sha="abc")}, "page_sha256"),
            "not an object": ({"g": ["x"]}, "must be an object"),
            "bad slug": ({"../g": _entry()}, "not a breach slug"),
        }
        for label, (m, needle) in planted.items():
            f = mapping_findings(m, {"g"}, {"g"})
            assert any(needle in x for x in f), (label, f)
        f = mapping_findings(ok, set(), {"g"})
        assert len(f) == 1 and "has no outline" in f[0], f
        f = mapping_findings(ok, {"g"}, set())
        assert len(f) == 1 and "names no breach page" in f[0], f


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


def _tree_outline(slug: str, extra: str = "") -> str:
    return (
        f"title: T\npage: breaches/{slug}.html\nas-of: 2026-11-20\npromise: P.\n\n"
        f"== S{extra}\nText.\nnotes:\nN.\n"
    )


def _tree(root: Path, outlines: dict[str, str], pages: dict[str, str], mapping: dict | None) -> Path:
    """A scratch repository: outlines in tools/decks/breaches/, pages in
    breaches/, and published.json when mapping is given."""
    decks = root / "tools" / "decks" / "breaches"
    decks.mkdir(parents=True)
    (root / "breaches").mkdir()
    for slug, text in outlines.items():
        (decks / f"{slug}.deck").write_text(text, encoding="utf-8")
    for slug, html in pages.items():
        (root / "breaches" / f"{slug}.html").write_text(html, encoding="utf-8")
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


def _hashes(slug: str, root: Path) -> tuple[str, str]:
    return (
        outline_sha256(parse_outline(DECKS_DIR / f"{slug}.deck")),
        page_sha256((PAGES_DIR / f"{slug}.html").read_text(encoding="utf-8")),
    )


def _case_stale_outline_changed(tmp: Path) -> None:
    slugs = ("aa", "bb", "cc")
    _tree(tmp, {s: _tree_outline(s) for s in slugs}, {s: PM_PAGE for s in slugs}, None)
    with _rooted(tmp):
        sha = {s: _hashes(s, tmp) for s in slugs}
        mapping = {
            "aa": _entry(sha=sha["aa"][0], page_sha=sha["aa"][1]),
            "bb": _entry(sha="f" * 64, page_sha=sha["bb"][1]),
            "dd": _entry(),
        }
        save_mapping(mapping)
        rc, out = _capture(stale_report, True)
        assert rc == 0, out
        assert out.splitlines() == [
            "bb: outline changed since it was published on 2026-01-02; "
            "the public deck needs re-publishing",
            "dd: published, but tools/decks/breaches/dd.deck is missing",
            "stale check: 2 of 3 published decks changed since publishing",
        ], out
        rc, out = _capture(stale_report, False)
        assert rc == 0 and "cc: not published" in out and "outlines never published: 1" in out, out
        # Control: with every published deck matching, nothing is listed, and
        # stamping the deck line into the page changes no hash.
        save_mapping({"aa": _entry(sha=sha["aa"][0], page_sha=sha["aa"][1])})
        (PAGES_DIR / "aa.html").write_text(stamp_page(PM_PAGE, ID_A), encoding="utf-8")
        rc, out = _capture(stale_report, True)
        assert rc == 0 and out.splitlines() == [
            "stale check: 0 of 1 published decks changed since publishing"
        ], out
        MAPPING.write_text("{not json", encoding="utf-8")
        rc, out = _capture(stale_report, True)
        assert rc == 1 and "cannot be read as JSON" in out, out


def _case_stale_page_changed(tmp: Path) -> None:
    _tree(tmp, {"aa": _tree_outline("aa")}, {"aa": PM_PAGE}, None)
    with _rooted(tmp):
        osha, psha = _hashes("aa", tmp)
        save_mapping({"aa": _entry(sha=osha, page_sha=psha)})
        # A changed sentence in <main> flags the deck; the nav does not.
        navbump = _plant(PM_PAGE, "Nav 999", "Other nav 123")
        (PAGES_DIR / "aa.html").write_text(navbump, encoding="utf-8")
        rc, out = _capture(stale_report, True)
        assert rc == 0 and "0 of 1" in out, out
        changed = _plant(PM_PAGE, "credentials", "secrets")
        (PAGES_DIR / "aa.html").write_text(changed, encoding="utf-8")
        rc, out = _capture(stale_report, True)
        assert rc == 0, out
        assert out.splitlines() == [
            "aa: page changed since it was published on 2026-01-02; "
            "review the deck against the page",
            "stale check: 1 of 1 published decks changed since publishing",
        ], out
        # Both changed: two lines, one stale deck.
        (DECKS_DIR / "aa.deck").write_text(_tree_outline("aa", "x"), encoding="utf-8")
        rc, out = _capture(stale_report, True)
        assert out.count("aa: ") == 2 and "1 of 1" in out, out


def _case_stale_exit_zero(tmp: Path) -> None:
    _tree(tmp, {"aa": _tree_outline("aa")}, {"aa": PM_PAGE}, {"aa": _entry(sha="f" * 64)})
    with _rooted(tmp):
        for published_only in (True, False):
            rc, out = _capture(stale_report, published_only)
            assert rc == 0 and "stale check: 1 of 1" in out, out
        # A page that cannot be read as a page is reported, not fatal.
        (PAGES_DIR / "aa.html").write_text("<p>no main</p>", encoding="utf-8")
        rc, out = _capture(stale_report, True)
        assert rc == 0 and "aa:" in out, out


def _case_check_empty_tree(tmp: Path) -> None:
    (tmp / "tools" / "decks" / "breaches").mkdir(parents=True)
    (tmp / "breaches").mkdir()
    with _rooted(tmp):
        for fn in (check_all, stale_report, status_report, stamp_all):
            rc, out = _capture(fn)
            assert rc == 1 and "no outlines found" in out, (fn.__name__, out)
        rc, out = _capture(check_all)
        assert "nothing was checked" in out, out
        rc, out = _capture(record, "aa", ID_A)
        assert rc == 1, out


def _case_check_reports_findings(tmp: Path) -> None:
    pages = {"aa": stamp_page(PM_PAGE, ID_A), "bb": PM_PAGE}
    _tree(tmp, {"aa": _tree_outline("aa")}, pages, {})
    with _rooted(tmp):
        rc, out = _capture(check_all)
        assert rc == 1, out
        # The outline is far under the slide minimum, and aa has a deck line
        # with no mapping entry.
        assert "slides" in out and "not in the mapping" in out, out
        assert "1 outlines checked, 2 breach pages checked" in out, out
        assert outline_findings(DECKS_DIR / "aa.deck"), "helper reports the outline's findings"


def _case_stamp_all_or_nothing(tmp: Path) -> None:
    pages = {"aa": "<main><p>no header</p></main>\n", "bb": PM_PAGE, "cc": "<main></main>\n"}
    _tree(tmp, {s: _tree_outline(s) for s in pages}, pages, {s: _entry() for s in pages})
    before = _snapshot(tmp)
    with _rooted(tmp):
        rc, out = _capture(stamp_all)
    assert rc == 1 and "nothing written" in out, out
    assert "breaches/aa.html" in out and "breaches/cc.html" in out, out
    assert _snapshot(tmp) == before, "a refused --stamp wrote files"
    for s in ("aa", "cc"):
        (tmp / "breaches" / f"{s}.html").write_text(PM_PAGE, encoding="utf-8")
    with _rooted(tmp):
        rc, out = _capture(stamp_all)
        assert rc == 0 and out.count("stamped") == 3, out
        once = _snapshot(tmp)
        rc, out = _capture(stamp_all)
        assert rc == 0 and out == "" and _snapshot(tmp) == once, out


def _case_record_writes_both_hashes(tmp: Path) -> None:
    pages = {"aa": "<main><p>no header</p></main>\n", "bb": PM_PAGE}
    _tree(tmp, {s: _build_outline(s) for s in pages}, pages, {})
    before = _snapshot(tmp)
    with _rooted(tmp):
        for args, needle in (
            (("aa", ID_A), "breaches/aa.html"),
            (("bb", 'X" onmouseover="alert(1)'), "not a Google Slides presentation id"),
            (("../bb", ID_A), "no outline"),
            (("zz", ID_A), "no outline"),
        ):
            rc, out = _capture(record, *args)
            assert rc == 1 and needle in out, (args, out)
            assert _snapshot(tmp) == before, f"a refused --record {args} wrote files"
        rc, out = _capture(record, "bb", ID_A)
        assert rc == 0, out
        want = _hashes("bb", tmp)
    m = json.loads((tmp / "tools/decks/breaches/published.json").read_text(encoding="utf-8"))
    assert sorted(m["bb"]) == sorted(ENTRY_KEYS), m
    assert m["bb"]["id"] == ID_A and _is_iso_date(m["bb"]["published"]), m
    assert (m["bb"]["outline_sha256"], m["bb"]["page_sha256"]) == want, (m, want)
    assert deck_line_html(ID_A) in (tmp / "breaches/bb.html").read_text(encoding="utf-8")
    # The stamped page hashes as it did before stamping.
    assert page_sha256((tmp / "breaches/bb.html").read_text(encoding="utf-8")) == page_sha256(PM_PAGE)


def _case_record_refuses_findings(tmp: Path) -> None:
    """--record refuses an outline --check would fail, so a publish commit
    never records a deck CI then rejects."""
    _tree(tmp, {"bb": _tree_outline("bb")}, {"bb": PM_PAGE}, {})
    before = _snapshot(tmp)
    with _rooted(tmp):
        assert outline_findings(DECKS_DIR / "bb.deck"), "the plant has no finding"
        rc, out = _capture(record, "bb", ID_A)
    assert rc == 1 and "slides" in out and "record: refused, nothing written" in out, out
    assert _snapshot(tmp) == before, "a refused --record wrote files"
    # Control: the same slug with a clean outline records.
    (tmp / "tools/decks/breaches/bb.deck").write_text(_build_outline("bb"), encoding="utf-8")
    with _rooted(tmp):
        rc, out = _capture(record, "bb", ID_A)
    assert rc == 0, out


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
    ("page_parse_real", _case_page_parse_real),
    ("page_parse_synthetic", _case_page_parse_synthetic),
    ("stage_every_mt_link", _case_stage_every_mt_link),
    ("numbers_normalized", _case_numbers_normalized),
    ("numbers_dotted", _case_numbers_dotted),
    ("page_hash_stable", _case_page_hash_stable),
    ("stage_unknown", _case_stage_unknown),
    ("stage_technique_not_on_stage", _case_stage_technique_not_on_stage),
    ("flow_step_checked", _case_flow_step_checked),
    ("stage_without_techniques", _case_stage_without_techniques),
    ("phase_checked", _case_phase_checked),
    ("matrix_columns_checked", _case_matrix_columns_checked),
    ("number_not_on_page", _case_number_not_on_page),
    ("unit_suffixed_number", _case_unit_suffixed_number),
    ("source_on_non_background", _case_source_on_non_background),
    ("cover_checked", _case_cover_checked),
    ("technique_not_on_page", _case_technique_not_on_page),
    ("notes_checked", _case_notes_checked),
    ("links_resolve", _case_links_resolve),
    ("background_exempt", _case_background_exempt),
    ("as_of_not_future", _case_as_of_not_future),
    ("stamp_insert", _case_stamp_insert),
    ("stamp_idempotent", _case_stamp_idempotent),
    ("stamp_new_id", _case_stamp_new_id),
    ("stamp_remove", _case_stamp_remove),
    ("stamp_no_pm_link", _case_stamp_no_pm_link),
    ("stamp_normal_form", _case_stamp_normal_form),
    ("stamp_refuses_loose_markup", _case_stamp_refuses_loose_markup),
    ("links_unmapped_line", _case_links_unmapped_line),
    ("links_missing_line", _case_links_missing_line),
    ("links_wrong_id", _case_links_wrong_id),
    ("links_every_line", _case_links_every_line),
    ("links_slides_link_elsewhere", _case_links_slides_link_elsewhere),
    ("mapping_findings", _case_mapping_findings),
    ("stale_outline_changed", _case_stale_outline_changed),
    ("stale_page_changed", _case_stale_page_changed),
    ("stale_exit_zero", _case_stale_exit_zero),
    ("check_empty_tree", _case_check_empty_tree),
    ("check_reports_findings", _case_check_reports_findings),
    ("stamp_all_or_nothing", _case_stamp_all_or_nothing),
    ("record_writes_both_hashes", _case_record_writes_both_hashes),
    ("record_refuses_findings", _case_record_refuses_findings),
]


# ---------------------------------------------------------------------------
# Render cases. They need python-pptx, so they stay out of CASES (which CI
# runs without it) and run only under --self-test-render.
# ---------------------------------------------------------------------------

RENDER_PAGE = "breaches/vapor-panda-artex.html"
RENDER_URL = f"https://csoh.org/{RENDER_PAGE}"
AWS_IMDS = (
    "https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html"
)


def _rslide(heading: str, layout: str = "text", **kw) -> BSlide:
    kw.setdefault("notes", [f"Say why {heading.lower()} matters.", "Then move on."])
    return BSlide(heading=heading, layout=layout, **kw)


def _render_sample() -> BDeck:
    """A deck using every layout Task 4 renders, each near its fullest."""
    slides = [
        _rslide("At a glance", "stats", items={"stat": [
            ["200+", "organizations targeted", "in at least 14 countries over 11 days"],
            ["9", "confirmed compromises", "per CrowdStrike, with high confidence"],
            ["1,500+", "commands an hour", "at peak, per Check Point"],
            ["40", "commands an hour", "a fast human operator, for comparison"],
        ]}),
        _rslide(
            "Two figures that measure different things", "stats",
            paragraphs=["Nine is the confirmed figure. About 140 comes from an interview "
                        "and includes moderate-confidence cases."],
            items={"stat": [
                ["9", "confirmed", "named in the CrowdStrike report"],
                ["About 140", "compromised", "from an interview, moderate confidence included"],
            ]},
        ),
        _rslide(
            "The metadata service handed over a fleet", "stage", stage="04",
            phase="Credential Access: The Metadata Service",
            items={
                "technique": [["T1552.005", "Cloud Instance Metadata API"],
                              ["T1651", "Cloud Administration Command"]],
                "fact": [["Queried", "the cloud Instance Metadata Service"],
                         ["Obtained", "a role able to command thousands of instances"],
                         ["Where", "a US pharmaceutical organization"]],
            },
            paragraphs=["A role that can command a fleet turns one compromised host into "
                        "all of them, and the request looked like routine traffic."],
        ),
        _rslide(
            "A backdoor and the mail it read", "stage", stage="07",
            phase="Persistence and Collection: BLOODALCHEMY and Mail",
            items={
                "technique": [["T1574.001", "Hijack Execution Flow: DLL"],
                              ["T1114", "Email Collection"],
                              ["T1005", "Data from Local System"]],
                "fact": [["Implant", "BLOODALCHEMY, loaded beside a signed binary"],
                         ["Collected", "mailboxes"]],
            },
            paragraphs=["The implant outlived the agents that placed it."],
        ),
        _rslide(
            "What IMDSv2 changes", "background",
            source=("AWS documentation", AWS_IMDS),
            paragraphs=["IMDSv2 requires a session token, fetched with a PUT request, "
                        "before the metadata service returns credentials."],
            bullets=["A plain GET relayed by a vulnerable app no longer works",
                     "The token's hop limit keeps it inside the instance"],
        ),
        _rslide(
            "Nothing new in technique", "text",
            paragraphs=["Every step used a technique defenders already know. The rate changed."],
            bullets=["Requests every 10 seconds", "Several paths tried in parallel",
                     "No pause for a person to read results"],
            credit="Tempo figures per Check Point",
        ),
        _rslide(
            "What would you add for stages 01 and 07?", "question",
            paragraphs=["The page's defenses leave the first and the last stage open. "
                        "What control would you put there, and what would it cost?"],
        ),
        _rslide(
            "The page offers none for those stages", "answer",
            paragraphs=["Any control you name here is your own suggestion, not the page's."],
            bullets=["Ask what it would have caught", "Ask who reads the alert, and how fast"],
        ),
        _rslide(
            "Check your own environment", "checklist",
            paragraphs=["Answer each for your own estate."],
            items={"check": [
                ["Do any long-lived access keys sit in code or config files?"],
                ["Do instances still answer IMDSv1 requests?"],
                ["Are SAML assertions rejected when unsigned?"],
                ["Which hosts run no endpoint sensor at all?"],
                ["Would a burst of commands every 10 seconds raise an alert?"],
                ["Who can create delegation rights in Active Directory?"],
                ["Is the LAPS password readable by more than its admins?"],
            ]},
        ),
        _rslide(
            "Sources", "links",
            items={"link": [
                ["CrowdStrike: VAPOR PANDA uses ARTEX",
                 "https://www.crowdstrike.com/en-us/blog/vapor-panda-uses-artex-to-scale-global-campaign/"],
                ["Check Point Research: hacking on autopilot",
                 "https://research.checkpoint.com/2026/hacking-on-autopilot-inside-artex-cybercrime-campaigns/"],
                ["Censys: ARTEX consoles", "https://censys.com/blog/artex-agentic-asbestos/"],
                ["CyberScoop", "https://cyberscoop.com/china-vapor-panda-agentic-ai-artex-campaign-crowdstrike/"],
                ["Microsoft: ARTEX abuse expands",
                 "https://www.microsoft.com/en-us/security/blog/2026/11/06/artex-abuse-expands-as-cybercriminals-target-financial-sector/"],
                ["Microsoft: agentic tooling and exposed secrets",
                 "https://www.microsoft.com/en-us/security/blog/2026/11/05/threat-actors-use-agentic-ai-tooling-to-find-and-abuse-exposed-secrets/"],
                ["Related: Storm-0940 and ConnectWise", "breaches/storm-0940-connectwise.html"],
                ["Glossary: guardrails", "https://csoh.org/glossary.html#term-guardrails"],
            ]},
        ),
    ]
    for i, s in enumerate(slides):
        s.where = f"r.deck:{10 * (i + 1)}"
    return BDeck(
        "r", "VAPOR PANDA / ARTEX", RENDER_PAGE, "2026-11-20",
        "One operator, a graph of AI agents, and 200+ organizations in 11 days.", slides, "",
    )


def _reopen(path: Path):
    import breach_deck_render as r

    return r.reopen(path)


def _shapes(slide, name: str) -> list:
    return [sh for sh in slide.shapes if sh.name == name]


def _one(slide, name: str):
    found = _shapes(slide, name)
    assert len(found) == 1, (name, [sh.name for sh in slide.shapes])
    return found[0]


def _paras(shape) -> list[str]:
    return [p.text for p in shape.text_frame.paragraphs]


def _all_text(slide) -> str:
    return "\n".join(sh.text_frame.text for sh in slide.shapes if sh.has_text_frame)


def _notes(slide) -> str:
    return slide.notes_slide.notes_text_frame.text


def _layout_error(fn, needle: str):
    import breach_deck_render as r

    try:
        fn()
    except r.LayoutError as e:
        assert needle in str(e), (needle, str(e))
        return e
    raise AssertionError("LayoutError was not raised")


def _case_render_sample(tmp: Path) -> None:
    import breach_deck_render as r

    deck = _render_sample()
    out = r.render_deck(deck, tmp / "r.pptx")
    found = r.verify_pptx(out, deck)
    assert found == [], "\n".join(found)
    prs = _reopen(out)
    total = len(deck.slides) + GENERATED_SLIDES
    assert len(prs.slides) == total, len(prs.slides)
    slides = list(prs.slides)
    for n, sl in enumerate(slides, start=1):
        assert _one(sl, "footer-left").text_frame.text == f"csoh.org/{RENDER_PAGE}", n
        assert _one(sl, "footer-right").text_frame.text == f"{n} / {total}", n
        assert _notes(sl).endswith(f"Full kill chain: {RENDER_URL}"), (n, _notes(sl))

    cover = _all_text(slides[0])
    for want in (deck.title, deck.promise, "Reflects the csoh.org kill chain as of 2026-11-20",
                 r.ATTRIBUTION, r.LICENSE_LINE):
        assert want in cover, want
    howto = slides[1]
    assert _one(howto, "heading").text_frame.text == "How to use this deck"
    assert _paras(_one(howto, "body")) == [
        "Read it on your own or present it. Every fact about the incident comes from "
        "the csoh.org kill chain and the sources it cites.",
        "Slides marked Background explain a general idea and name their own source. "
        "The speaker notes are a presenter's script.",
        f"Full kill chain: csoh.org/{RENDER_PAGE}. These slides reflect it as of 2026-11-20.",
    ], _paras(_one(howto, "body"))
    closing = slides[-1]
    assert _one(closing, "heading").text_frame.text == "Read the full kill chain"
    assert _paras(_one(closing, "body")) == [
        f"Every step, source and defense in detail: {RENDER_URL}", r.CLOSING_LICENSE,
    ], _paras(_one(closing, "body"))

    # Outline slide i is file slide i + 3 (1-based), after cover and how-to.
    def file_slide(i: int):
        return slides[i + 2]

    for i, s in enumerate(deck.slides):
        assert _notes(file_slide(i)).startswith(s.notes[0]), i

    stats = file_slide(0)
    tiles = _shapes(stats, "stat-tile")
    assert len(tiles) == 4, len(tiles)
    first = tiles[0].text_frame.paragraphs
    assert [p.text for p in first] == ["200+", "organizations targeted",
                                       "in at least 14 countries over 11 days"]
    assert str(first[0].runs[0].font.color.rgb).lower() == r.STYLE["accent"]
    assert len({t.top for t in tiles}) == 1 and len({t.height for t in tiles}) == 1

    stage = file_slide(2)
    band = _one(stage, "phase-band")
    want = "CREDENTIAL ACCESS: THE METADATA SERVICE · STAGE 04"
    assert band.text_frame.text == want, band.text_frame.text
    assert str(band.fill.fore_color.rgb).lower() == r.phase_color("Credential Access")
    assert _one(stage, "stage-number").text_frame.text == "04"
    assert _one(stage, "heading").text_frame.text == deck.slides[2].heading
    chips = [sh.text_frame.text for sh in _shapes(stage, "chip")]
    assert chips == ["T1552.005  Cloud Instance Metadata API",
                     "T1651  Cloud Administration Command"], chips
    labels = [sh.text_frame.text for sh in _shapes(stage, "fact-label")]
    values = [sh.text_frame.text for sh in _shapes(stage, "fact-value")]
    assert labels == ["Queried", "Obtained", "Where"], labels
    assert values[1] == "a role able to command thousands of instances", values
    assert _one(stage, "why-label").text_frame.text == "WHY IT MATTERS"
    assert _one(stage, "why-text").text_frame.text == deck.slides[2].paragraphs[0]
    why = _one(stage, "why")
    assert why.top > max(sh.top + sh.height for sh in _shapes(stage, "fact-value"))
    later = file_slide(3)
    band = _one(later, "phase-band")
    assert band.text_frame.text.startswith("PERSISTENCE AND COLLECTION")
    assert str(band.fill.fore_color.rgb).lower() == r.PHASE_COLORS["Persistence"]
    assert len(_shapes(later, "chip")) == 3

    bg = file_slide(4)
    assert _one(bg, "type-label").text_frame.text == "BACKGROUND"
    assert _one(bg, "credit").text_frame.text == "Source: AWS documentation (docs.aws.amazon.com)"
    assert _one(file_slide(5), "credit").text_frame.text == "Tempo figures per Check Point"
    assert _one(file_slide(6), "type-label").text_frame.text == "DISCUSSION"
    assert _one(file_slide(7), "type-label").text_frame.text == "DISCUSSION: ANSWER"
    # Control: a slide of incident facts carries no type label.
    assert not _shapes(stage, "type-label") and not _shapes(file_slide(5), "type-label")

    checks = file_slide(8)
    assert len(_shapes(checks, "check-box")) == 7
    assert [sh.text_frame.text for sh in _shapes(checks, "check-text")][1] == \
        "Do instances still answer IMDSv1 requests?"

    links = _shapes(file_slide(9), "link")
    assert len(links) == 8
    assert [sh.text_frame.paragraphs[0].text for sh in links] == [
        row[0] for row in deck.slides[9].items["link"]
    ]
    addresses = {r.hyperlink.address for sh in links for p in sh.text_frame.paragraphs
                 for r in p.runs}
    assert "https://csoh.org/breaches/storm-0940-connectwise.html" in addresses, addresses
    assert all(a.startswith("https://") for a in addresses), addresses
    shown = [sh.text_frame.paragraphs[1].text for sh in links]
    # A short address is shown whole; one too long for its line shows its host.
    assert "censys.com/blog/artex-agentic-asbestos" in shown, shown
    assert "microsoft.com" in shown, shown
    # More than four links take two columns, filled left column first.
    assert links[0].left == links[3].left < links[4].left, [sh.left for sh in links]
    assert links[0].top < links[1].top and links[0].top == links[4].top


def _case_phase_contrast(tmp: Path) -> None:
    import colorsys

    import breach_deck_render as r

    tactics = {
        "Reconnaissance", "Resource Development", "Initial Access", "Execution",
        "Persistence", "Privilege Escalation", "Stealth", "Defense Impairment",
        "Credential Access", "Discovery", "Lateral Movement", "Collection",
        "Command and Control", "Exfiltration", "Impact",
    }
    assert set(r.PHASE_COLORS) == tactics, set(r.PHASE_COLORS) ^ tactics
    for tactic, color in [*r.PHASE_COLORS.items(), ("fallback", r.FALLBACK_PHASE)]:
        assert r.contrast("ffffff", color) >= 4.5, (tactic, color, r.contrast("ffffff", color))
    # Darkening keeps the site's hue.
    for tactic, color in r.PHASE_COLORS.items():
        hues = [colorsys.rgb_to_hls(*(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)))[0]
                for c in (color, r.SITE_PHASE_HUES[tactic])]
        assert abs(hues[0] - hues[1]) < 0.02, (tactic, color, hues)
    # Stealth and Defense Impairment, often beside Persistence, Privilege
    # Escalation or Credential Access in a chain, take a hue clear of all three.
    def hue(color: str) -> float:
        return colorsys.rgb_to_hls(*(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4)))[0]

    for tactic in ("Stealth", "Defense Impairment"):
        own = r.PHASE_COLORS[tactic]
        assert own != r.PHASE_COLORS["Persistence"], tactic
        for near in ("Persistence", "Privilege Escalation", "Credential Access"):
            apart = abs(hue(own) - hue(r.PHASE_COLORS[near]))
            assert min(apart, 1 - apart) > 0.1, (tactic, near, apart)
    # Control: the site's own Execution hue fails the bar, so darkening did work.
    assert r.contrast("ffffff", r.SITE_PHASE_HUES["Execution"]) < 4.5
    assert r.PHASE_COLORS["Execution"] != r.SITE_PHASE_HUES["Execution"]
    assert round(r.contrast("ffffff", "000000"), 2) == 21.0
    assert r.contrast("777777", "777777") == 1.0
    cred = r.PHASE_COLORS["Credential Access"]
    assert r.phase_color("Credential Access") == cred
    assert r.phase_color("Credential Access: Keys Nobody Rotated") == cred
    assert r.phase_color("credential access") == cred
    assert r.phase_color("Persistence and Collection: Mail") == r.PHASE_COLORS["Persistence"]
    for unknown in ("Recon & Upstream Compromise", "Impactful: a word, not a tactic", "Background"):
        assert r.phase_color(unknown) == r.FALLBACK_PHASE, unknown


def _case_overflow_refused(tmp: Path) -> None:
    import breach_deck_render as r

    long = "the agent asked the metadata service for credentials and received a very powerful role"
    assert _words(long) == MAX_FIELD_WORDS
    why = " ".join(["word"] * MAX_PROSE_WORDS)

    def deck(facts: list[list[str]], para: str) -> BDeck:
        s = _rslide(
            "The metadata service handed over a fleet", "stage", stage="04",
            phase="Credential Access", where="over.deck:9", paragraphs=[para],
            items={"technique": [["T1552.005", "Cloud Instance Metadata API"]], "fact": facts},
        )
        return BDeck("o", "T", RENDER_PAGE, "2026-11-20", "P.", [s], "")

    out = tmp / "o.pptx"
    _layout_error(lambda: r.render_deck(deck([["Step", long]] * 5, why), out), "over.deck:9")
    assert not out.exists(), "a refused render wrote a file"
    # The why box is pinned to the bottom before the facts are placed; when
    # the chips above already reach where it must start, that is refused too.
    chips = deck([["Queried", "the service"]], " ".join(["credentials"] * MAX_PROSE_WORDS))
    chips.slides[0].items["technique"] = [
        [f"T1552.00{i}", " ".join(["Instance"] * MAX_FIELD_WORDS)] for i in range(3)
    ]
    e = _layout_error(lambda: r.render_deck(chips, out), "over.deck:9")
    assert "pinned to the bottom" in str(e), e
    assert not out.exists(), "a refused render wrote a file"
    # Control: the same slide with less on it fits and verifies.
    ok = deck([["Queried", "the service"], ["Obtained", "a role"]], "One host became all of them.")
    r.render_deck(ok, out)
    assert r.verify_pptx(out, ok) == [], r.verify_pptx(out, ok)


def _planted(tmp: Path, plant) -> list[str]:
    """Render the sample, apply plant(prs) to the reopened file, save it and
    return what verify_pptx finds in it."""
    import breach_deck_render as r

    deck = _render_sample()
    out = r.render_deck(deck, tmp / "r.pptx")
    prs = _reopen(out)
    plant(prs)
    bad = tmp / "bad.pptx"
    prs.save(str(bad))
    return r.verify_pptx(bad, deck)


def _case_verify_catches_dash(tmp: Path) -> None:
    def plant(prs):
        run = _one(prs.slides[2], "heading").text_frame.paragraphs[0].runs[0]
        run.text = "At a " + chr(0x2013) + " glance"
        prs.slides[3].notes_slide.notes_text_frame.text = "Say it " + chr(0x2014) + " now."

    found = "\n".join(_planted(tmp, plant))
    assert "slide 3: en or em dash in heading" in found, found
    assert "slide 4: en or em dash in the speaker notes" in found, found
    assert _planted(tmp, lambda prs: None) == []


def _case_verify_catches_small_font(tmp: Path) -> None:
    import breach_deck_render as r

    Pt = r.Pt

    def plant(prs):
        _one(prs.slides[2], "heading").text_frame.paragraphs[0].runs[0].font.size = Pt(12)
        _one(prs.slides[4], "footer-left").text_frame.paragraphs[0].runs[0].font.size = Pt(12)
        _shapes(prs.slides[5], "chip")[0].text_frame.paragraphs[0].runs[0].font.size = Pt(16)

    found = "\n".join(_planted(tmp, plant))
    assert "slide 3: heading run is 12.0 pt, below 18" in found, found
    assert "slide 5: footer-left run is 12.0 pt, below 14" in found, found
    # Control: a small label at 16 pt is within its floor.
    assert "slide 6" not in found, found


def _case_verify_plants(tmp: Path) -> None:
    """Every other verify_pptx detector, each against a planted defect."""
    import breach_deck_render as r

    Inches = r.Inches

    def plant(prs):
        s = prs.slides
        s[1].notes_slide.notes_text_frame.text = ""
        _one(s[2], "footer-left").text_frame.paragraphs[0].runs[0].text = "csoh.org/elsewhere"
        _one(s[3], "footer-right").text_frame.paragraphs[0].runs[0].text = "9 / 9"
        s[4].shapes.add_group_shape()
        s[5].shapes.add_shape(r.MSO_SHAPE.HEXAGON, Inches(1), Inches(1), Inches(1), Inches(1))
        # Slide 7 is the background slide.
        _one(s[6], "heading").top = Inches(6.8)
        _one(s[6], "type-label").text_frame.paragraphs[0].runs[0].text = "NOTES"
        _one(s[6], "credit").text_frame.paragraphs[0].runs[0].text = "Source: somewhere"
        run = _one(s[7], "heading").text_frame.paragraphs[0].runs[0]
        run.font.color.rgb = r._rgb(r.STYLE["light"])
        _one(s[8], "body").text_frame.auto_size = r.MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
        _one(s[9], "heading").left = Inches(2)

    found = "\n".join(_planted(tmp, plant))
    for needle in (
        "slide 2: no speaker notes",
        "slide 3: footer-left is",
        "slide 4: footer-right is",
        "slide 5: shape",
        "slide 6: shape",
        "slide 7: heading ends below",
        "slide 7: type label is",
        "slide 7: credit does not name its source",
        "slide 8: heading run contrast",
        "slide 9: body uses autofit",
        "slide 10: heading runs off the side",
    ):
        assert needle in found, (needle, found)
    deck = _render_sample()
    out = r.render_deck(deck, tmp / "r.pptx")
    deck.slides.pop()
    assert any("slides, expected" in f for f in r.verify_pptx(out, deck))


DIAGRAMS = ("flow", "layers", "timeline", "compare", "table", "bars", "matrix")


def _diagram_sample() -> BDeck:
    """A deck using every diagram layout at its maximum counts (lines and
    fields), each with a line of prose under it."""
    slides = [
        _rslide(
            "Eight stages on one slide", "flow",
            paragraphs=["Each box is one stage, coloured by its phase."],
            items={"step": [
                ["01", "Resource Development", "Agents planned", "T1588.007"],
                ["02", "Initial Access", "Public apps", "T1190"],
                ["03", "Credential Access", "Keys in code", "T1552.001"],
                ["04", "Credential Access", "Metadata service", "T1552.005"],
                ["05", "Privilege Escalation", "Containers and AD", "T1611"],
                ["06", "Stealth", "Unwatched hosts", "T1518.001"],
                ["07", "Persistence", "BLOODALCHEMY", "T1574.001"],
                ["08", "Collection", "Mailboxes read", "T1114"],
            ]},
        ),
        _rslide(
            "How ARTEX is put together", "layers",
            paragraphs=["Every agent reads and writes the same graph."],
            items={"layer": [
                ["Operator", "One person approves targets and next steps"],
                ["Main agent", "Holds the goal and hands out work"],
                ["Sub-agents", "Planner agents", "Worker agents", "Reporting agents"],
                ["Tools", "Scanners and exploit kits", "Cloud and directory clients"],
                ["Shared graph", "Facts, findings and goals that every agent uses"],
            ]},
        ),
        _rslide(
            "Eleven days, then the counts", "timeline",
            paragraphs=["Only the dates the page gives; the spacing is not to scale."],
            items={"event": [
                ["October 17", "First activity at the first target"],
                ["October 18", "Keys found in code and config files"],
                ["October 27", "The eleventh day of activity"],
                ["October 30", "Reported active, per CyberScoop"],
                ["Early November", "Censys counts exposed consoles"],
                ["November 6", "Microsoft reports wider abuse"],
            ]},
        ),
        _rslide(
            "Three figures that measure different things", "compare",
            paragraphs=["Quote each figure with what it counts."],
            items={"col": [
                ["9 confirmed", "Named in the CrowdStrike report", "High confidence only",
                 "Counts what it could prove", "The figure to quote"],
                ["About 140 compromised", "From an interview",
                 "Moderate-confidence cases included", "Not broken down by victim",
                 "Quote it with its caveat"],
                ["200+ targeted", "Organizations on the target list", "In at least 14 countries",
                 "Targeted, not compromised", "The widest of the three"],
            ]},
        ),
        _rslide(
            "Exposed consoles by method", "table",
            paragraphs=["Each count answers a different question."],
            items={"row": [
                ["Source", "Method", "Count", "Caveat"],
                ["Censys", "Hosts serving the console", "1,465", "Includes authorized testers"],
                ["Censys", "Distinct-looking deployments", "About 815", "Grouped by content"],
                ["Check Point", "Live consoles", "1,608", "At the time of the scan"],
                ["Check Point", "Ever seen", "2,557", "Across the whole window"],
                ["Check Point", "Summary figure", "1,800+", "As written in the summary"],
                ["Microsoft", "Abuse reports", "Not given", "Counts no consoles"],
            ]},
        ),
        _rslide(
            "Commands an hour, drawn to scale", "bars",
            paragraphs=["One scale from zero for every bar."],
            items={"bar": [
                ["1,500+", "Agents at peak, per Check Point"],
                ["600", "Agents on an average hour"],
                ["40", "A fast human operator"],
                ["10", "A careful human operator"],
            ]},
        ),
        _rslide(
            "Eight defenses against eight stages", "matrix",
            paragraphs=["A mark means the page ties that defense to that stage."],
            items={
                "columns": [["01", "02", "03", "04", "05", "06", "07", "08"]],
                "row": [
                    ["Rotate and vault long-lived keys", "03"],
                    ["Require IMDSv2 on every instance", "04"],
                    ["Reject unsigned SAML assertions", "02"],
                    ["Close endpoint sensor gaps", "06"],
                    ["Watch for orchestration tooling", "05", "06"],
                    ["Segment every network", "01", "02", "03", "04", "05", "06", "07", "08"],
                    ["Hunt for ARTEX markers", "-"],
                    ["Plant decoy credentials", "-"],
                ],
            },
        ),
    ]
    for i, s in enumerate(slides):
        s.where = f"g.deck:{10 * (i + 1)}"
    return BDeck("g", "Diagram sample", RENDER_PAGE, "2026-11-20", "Every diagram layout.",
                 slides, "")


def _one_slide(heading: str, layout: str, where: str, **items) -> BDeck:
    s = _rslide(heading, layout, where=where, items={k: list(v) for k, v in items.items()})
    return BDeck("d", "T", RENDER_PAGE, "2026-11-20", "P.", [s], "")


def _rendered(tmp: Path, deck: BDeck) -> list:
    """Render deck, assert it verifies clean, and return its outline slides
    as saved (the cover, "how to use" and closing left out)."""
    import breach_deck_render as r

    out = r.render_deck(deck, tmp / f"{deck.slug}.pptx")
    found = r.verify_pptx(out, deck)
    assert found == [], "\n".join(found)
    return list(_reopen(out).slides)[2:-1]


def _texts(slide, name: str) -> list[str]:
    return [sh.text_frame.text for sh in _shapes(slide, name)]


def _fill(shape) -> str:
    return str(shape.fill.fore_color.rgb).lower()


def _cx(shape) -> float:
    return shape.left + shape.width / 2


def _cy(shape) -> float:
    return shape.top + shape.height / 2


def _rows_by_top(shapes: list) -> list[list]:
    """Shapes grouped into rows by their top, top row first, each row left
    to right."""
    tops = sorted({sh.top for sh in shapes})
    return [sorted((sh for sh in shapes if sh.top == t), key=lambda sh: sh.left) for t in tops]


def _matrix_marks(slide) -> set[tuple[str, str]]:
    """(row label, column label) for every marker, read from where it sits."""
    cols = [(_cx(c), c.text_frame.text) for c in _shapes(slide, "matrix-col")]
    rows = [(sh.top, sh.top + sh.height, sh.text_frame.text)
            for sh in _shapes(slide, "matrix-label")]
    out = set()
    for m in _shapes(slide, "matrix-mark"):
        col = [t for x, t in cols if abs(x - _cx(m)) <= 2]
        row = [t for top, bottom, t in rows if top <= _cy(m) <= bottom]
        assert len(col) == 1 and len(row) == 1, (col, row)
        out.add((row[0], col[0]))
    return out


def _case_render_diagrams(tmp: Path) -> None:
    import breach_deck_render as r

    assert set(r.RENDERERS) == set(LAYOUTS), set(r.RENDERERS) ^ set(LAYOUTS)
    deck = _diagram_sample()
    assert tuple(s.layout for s in deck.slides) == DIAGRAMS
    # The sample is at every maximum: line counts and fields per line.
    for s in deck.slides:
        assert slide_findings(s) == [], slide_findings(s)
        for key, (_lo, hi, _flo, fhi) in LAYOUTS[s.layout].typed.items():
            rows = s.items[key]
            assert len(rows) == hi and max(len(row) for row in rows) == fhi, (s.layout, key)
    flow, layers, timeline, compare, table, bars, matrix = _rendered(tmp, deck)
    sl = dict(zip(DIAGRAMS, deck.slides))

    steps = sl["flow"].items["step"]
    boxes = _shapes(flow, "flow-step")
    assert [_paras(b) for b in boxes] == steps, [_paras(b) for b in boxes]
    assert [_fill(b) for b in boxes] == [r.phase_color(step[1]) for step in steps]
    # Stealth (06) and Persistence (07) sit side by side in different colours.
    assert _fill(boxes[5]) != _fill(boxes[6])
    arrows = _shapes(flow, "flow-arrow")
    assert len(arrows) == 6, len(arrows)
    assert all(a.auto_shape_type == r.MSO_SHAPE.RIGHT_ARROW for a in arrows)

    rows = sl["layers"].items["layer"]
    assert _texts(layers, "layer-tier") == [row[0] for row in rows]
    boxes = _shapes(layers, "layer-box")
    assert [b.text_frame.text for b in boxes] == [f for row in rows for f in row[1:]]
    grid = _rows_by_top(boxes)
    assert [len(g) for g in grid] == [len(row) - 1 for row in rows], [len(g) for g in grid]
    # One down arrow in each gap between consecutive rows, and nothing else.
    arrows = _shapes(layers, "layer-arrow")
    assert len(arrows) == len(rows) - 1, len(arrows)
    for a, above, below in zip(arrows, grid, grid[1:]):
        assert a.auto_shape_type == r.MSO_SHAPE.DOWN_ARROW
        assert max(b.top + b.height for b in above) <= a.top
        assert a.top + a.height <= min(b.top for b in below)
    assert {sh.auto_shape_type for sh in _shapes(layers, "layer-box")} == {
        r.MSO_SHAPE.ROUNDED_RECTANGLE
    }

    events = sl["timeline"].items["event"]
    assert _texts(timeline, "timeline-when") == [e[0] for e in events]
    assert _texts(timeline, "timeline-what") == [e[1] for e in events]
    rule = _one(timeline, "timeline-rule")
    markers = _shapes(timeline, "timeline-marker")
    assert len(markers) == len(events)
    assert all(m.auto_shape_type == r.MSO_SHAPE.OVAL for m in markers)
    for m, when, what in zip(markers, _shapes(timeline, "timeline-when"),
                             _shapes(timeline, "timeline-what")):
        assert when.top + when.height <= m.top and what.top >= m.top + m.height
        assert abs(_cx(when) - _cx(m)) <= 2 and abs(_cx(what) - _cx(m)) <= 2
        assert rule.top <= _cy(m) <= rule.top + rule.height

    cols = sl["compare"].items["col"]
    heads, bodies = _shapes(compare, "compare-head"), _shapes(compare, "compare-body")
    assert [h.text_frame.text for h in heads] == [c[0] for c in cols]
    assert [_paras(b) for b in bodies] == [[f"• {ln}" for ln in c[1:]] for c in cols]
    assert len({sh.width for sh in heads + bodies}) == 1
    assert len({h.top for h in heads}) == 1 and len({b.top for b in bodies}) == 1
    assert len({b.height for b in bodies}) == 1
    # Each panel starts where its band ends (positions round to whole EMUs).
    assert all(abs(h.top + h.height - b.top) <= 1 for h, b in zip(heads, bodies))

    rows = sl["table"].items["row"]
    cells = _shapes(table, "table-cell")
    assert [c.text_frame.text for c in cells] == [f for row in rows for f in row]
    grid = _rows_by_top(cells)
    assert [len(g) for g in grid] == [4] * len(rows)
    assert {_fill(c) for c in grid[0]} == {r.STYLE["dark"]}
    assert all(run.font.bold for c in grid[0] for p in c.text_frame.paragraphs for run in p.runs)
    shades = [{_fill(c) for c in g} for g in grid[1:]]
    assert all(len(s) == 1 for s in shades), shades
    odd, even = shades[0::2], shades[1::2]
    assert all(s == odd[0] for s in odd) and all(s == even[0] for s in even), shades
    assert odd[0] != even[0] and r.STYLE["dark"] not in odd[0] | even[0], shades
    # Columns line up from row to row.
    assert all([c.left for c in g] == [c.left for c in grid[0]] for g in grid)

    rows = sl["bars"].items["bar"]
    assert _texts(bars, "bars-value") == ["1,500+", "600", "40", "10"]
    assert _texts(bars, "bars-label") == [row[1] for row in rows]
    rects = _shapes(bars, "bars-bar")
    assert len(rects) == 4 and len({b.left for b in rects}) == 1
    assert abs(rects[1].width / rects[0].width - 600 / 1500) < 0.01 * 600 / 1500

    columns = sl["matrix"].items["columns"][0]
    assert _texts(matrix, "matrix-col") == columns
    rows = sl["matrix"].items["row"]
    assert _texts(matrix, "matrix-label") == [
        row[0] if row[1:] != ["-"] else f"{row[0]} (no stage named)" for row in rows
    ]
    want = {(row[0], m) for row in rows for m in row[1:] if m != "-"}
    assert _matrix_marks(matrix) == want


def _case_render_without_techniques(tmp: Path) -> None:
    """A stage slide with no technique draws no chip row, and its facts take
    the room; a flow step whose technique is "-" shows no ID line."""

    def stage(techniques: list[list[str]], where: str) -> BSlide:
        items = {"fact": [["Detected", "the burst of commands"], ["By", "the endpoint sensor"]]}
        if techniques:
            items["technique"] = techniques
        return _rslide("A sensor caught the burst", "stage", stage="06", phase="Detection",
                       items=items, paragraphs=["Coverage decided what was seen."], where=where)

    deck = BDeck("n", "T", RENDER_PAGE, "2026-11-20", "P.", [
        stage([], "n.deck:3"),
        stage([["T1518.001", "Security Software Discovery"]], "n.deck:12"),
    ], "")
    import breach_deck_render as r

    bare, chipped = _rendered(tmp, deck)
    assert not _shapes(bare, "chip") and len(_shapes(chipped, "chip")) == 1
    # With no chips, the facts start one section gap below the heading, with
    # no space kept for a chip row.
    heading = _one(bare, "heading")
    want = heading.top + heading.height + r.Inches(r.LOOK["section_gap"])
    got = _shapes(bare, "fact-label")[0].top
    assert abs(got - want) <= 2, (got, want)
    first_fact = [_shapes(sl, "fact-label")[0].top for sl in (bare, chipped)]
    assert first_fact[0] < first_fact[1], first_fact
    steps = [["01", "Initial Access", "Phished", "T1566"],
             ["02", "Detection", "Sensor alert", NO_TECHNIQUE],
             ["03", "Response", "Contained", NO_TECHNIQUE]]
    (flow,) = _rendered(tmp, _one_slide("The chain", "flow", "f.deck:3", step=steps))
    boxes = _shapes(flow, "flow-step")
    assert [_paras(b) for b in boxes] == [steps[0], steps[1][:3], steps[2][:3]], [
        _paras(b) for b in boxes
    ]
    # Boxes in a row still share one height.
    assert len({b.height for b in boxes}) == 1


def _case_bars_to_scale(tmp: Path) -> None:
    import breach_deck_render as r

    def drawn(*bars):
        (sl,) = _rendered(tmp, _one_slide("Commands an hour", "bars", "b.deck:4", bar=bars))
        return _shapes(sl, "bars-bar"), _shapes(sl, "bars-value")

    # 40 is 2.67% of 1,500, above the 2% floor: drawn to scale within 1%.
    (small, big), values = drawn(["40", "a fast human operator"], ["1,500", "agents at peak"])
    assert abs((small.width / big.width) / (40 / 1500) - 1) < 0.01, small.width / big.width
    assert [v.text_frame.text for v in values] == ["40", "1,500"]
    assert small.left == big.left
    # Each written value sits just past the end of its own bar.
    for bar, value in zip((small, big), values):
        gap = value.left - (bar.left + bar.width)
        assert 0 <= gap <= r.Inches(0.3), gap
        assert abs(_cy(value) - _cy(bar)) <= 2
    # 10 is 0.67% of 1,500: drawn at the minimum visible width, not to scale,
    # and its written value is still printed.
    (tiny, big), values = drawn(["10", "a careful operator"], ["1,500", "agents at peak"])
    floor = r.LOOK["bar_min_frac"]
    assert abs(tiny.width / big.width - floor) < 0.001, tiny.width / big.width
    assert tiny.width > big.width * 10 / 1500
    assert [v.text_frame.text for v in values] == ["10", "1,500"]
    # Zero draws no bar at all, and its value sits at the zero line.
    (big,), values = drawn(["0", "a careful operator"], ["1,500", "agents at peak"])
    assert [v.text_frame.text for v in values] == ["0", "1,500"]
    assert abs(values[0].left - big.left) <= r.Inches(0.3)
    deck = _one_slide("Nothing", "bars", "z.deck:4", bar=[["0", "a"], ["0", "b"]])
    _layout_error(lambda: r.render_deck(deck, tmp / "z.pptx"), "z.deck:4")


def _case_flow_two_rows(tmp: Path) -> None:
    def rows(n: int) -> list[list]:
        steps = [[f"{i:02d}", "Execution", f"Step {i}", "T1059"] for i in range(1, n + 1)]
        (sl,) = _rendered(tmp, _one_slide("The chain", "flow", "f.deck:3", step=steps))
        grid = _rows_by_top(_shapes(sl, "flow-step"))
        # Reading order: left to right along each row, top row first.
        order = [b.text_frame.paragraphs[0].text for row in grid for b in row]
        assert order == [s[0] for s in steps], order
        # One right arrow between neighbours in a row; none between rows.
        arrows = _shapes(sl, "flow-arrow")
        assert len(arrows) == n - len(grid), (n, len(arrows))
        pairs = [(a, b) for row in grid for a, b in zip(row, row[1:])]
        for arrow, (a, b) in zip(arrows, pairs):
            assert a.left + a.width <= arrow.left and arrow.left + arrow.width <= b.left
            assert a.top <= _cy(arrow) <= a.top + a.height
        return grid

    grid = rows(7)
    assert [len(g) for g in grid] == [4, 3], [len(g) for g in grid]
    # The second row sits on the first row's columns.
    assert [b.left for b in grid[1]] == [b.left for b in grid[0][:3]]
    assert grid[0][0].top + grid[0][0].height < grid[1][0].top
    # Controls: one row up to four steps, two balanced rows from five.
    for n, want in ((3, [3]), (4, [4]), (5, [3, 2]), (8, [4, 4])):
        assert [len(g) for g in rows(n)] == want, n


def _case_timeline_even(tmp: Path) -> None:
    def centres(*events) -> list[float]:
        (sl,) = _rendered(tmp, _one_slide("When", "timeline", "t.deck:3", event=events))
        return [_cx(m) for m in _shapes(sl, "timeline-marker")]

    # One day apart, then twelve, then about a week: the spacing is still even.
    uneven = centres(["October 17", "Started"], ["October 18", "Keys found"],
                     ["October 30", "Reported active"], ["Early November", "Consoles counted"])
    steps = [b - a for a, b in zip(uneven, uneven[1:])]
    assert max(steps) - min(steps) <= 2, steps
    # Control: other dates and texts give the very same positions.
    even = centres(["Day 1", "A"], ["Day 2", "B"], ["Day 3", "C"], ["Day 4", "D"])
    assert all(abs(a - b) <= 2 for a, b in zip(uneven, even)), (uneven, even)
    for n in (2, 6):
        xs = centres(*[[f"Day {i}", "Something happened"] for i in range(n)])
        steps = [b - a for a, b in zip(xs, xs[1:])]
        assert len(xs) == n and max(steps) - min(steps) <= 2, steps


def _case_matrix_marks(tmp: Path) -> None:
    deck = _one_slide(
        "Defenses against stages", "matrix", "m.deck:3",
        columns=[["01", "02", "03", "04"]],
        row=[["Rotate keys", "03", "01"], ["Plant decoys", "-"], ["Require IMDSv2", "04"]],
    )
    (sl,) = _rendered(tmp, deck)
    # A marker only where the outline marks, an empty cell everywhere else.
    assert _matrix_marks(sl) == {("Rotate keys", "01"), ("Rotate keys", "03"),
                                 ("Require IMDSv2", "04")}
    labels = _shapes(sl, "matrix-label")
    assert [sh.text_frame.text for sh in labels] == [
        "Rotate keys", "Plant decoys (no stage named)", "Require IMDSv2"
    ]
    italic = [all(run.font.italic for p in sh.text_frame.paragraphs for run in p.runs)
              for sh in labels]
    assert italic == [False, True, False], italic


def _case_diagram_overflow_refused(tmp: Path) -> None:
    import breach_deck_render as r

    long = "the agent asked the metadata service for credentials and received a very powerful role"
    assert _words(long) == MAX_FIELD_WORDS
    out = tmp / "d.pptx"
    for layout, key, rows in (
        ("table", "row", [[long] * 4] * 7),
        ("flow", "step", [[f"0{i}", "Execution", long, "T1059"] for i in range(1, 9)]),
        ("layers", "layer", [["Tier", long, long, long]] * 5),
    ):
        deck = _one_slide("Too much", layout, f"{layout}.deck:7", **{key: rows})
        _layout_error(lambda deck=deck: r.render_deck(deck, out),
                      f"{layout}.deck:7: content would end at")
        assert not out.exists(), f"a refused {layout} wrote a file"


def _build_outline(slug: str, as_of: str = "2026-11-01") -> str:
    slides = "".join(f"== Slide {chr(97 + i)}\nText.\nnotes:\nSay it.\n\n" for i in range(15))
    return f"title: T\npage: breaches/{slug}.html\nas-of: {as_of}\npromise: P.\n\n" + slides


def _case_build_refuses_and_cleans(tmp: Path) -> None:
    """--build refuses an outline with findings and removes a deck's old
    .pptx first; a render that raises or a file that fails verification
    leaves no file; a clean outline builds and verifies."""
    import breach_deck_render as r

    outlines = {"aa": _build_outline("aa"), "bb": _tree_outline("bb")}
    _tree(tmp, outlines, {"aa": PM_PAGE, "bb": PM_PAGE}, None)
    build = tmp / "tools" / "decks" / "breaches" / "build"

    def raises(deck, out):
        raise r.LayoutError("aa.deck:5: planted overflow")

    def problems(path, deck):
        return [f"{path.name} slide 2: planted problem"]

    real = (r.render_deck, r.verify_pptx)
    with _rooted(tmp):
        try:
            build.mkdir(parents=True)
            (build / "bb.pptx").write_bytes(b"an older build")
            rc, out = _capture(build_decks, ["bb"])
            assert rc == 1 and "bb.deck: refused" in out and "slides" in out, out
            assert not (build / "bb.pptx").exists(), "a refused build left the old file"
            for name, patch in (("render_deck", raises), ("verify_pptx", problems)):
                (build / "aa.pptx").write_bytes(b"an older build")
                setattr(r, name, patch)
                try:
                    rc, out = _capture(build_decks, ["aa"])
                finally:
                    r.render_deck, r.verify_pptx = real
                assert rc == 1 and "planted" in out, (name, out)
                assert not (build / "aa.pptx").exists(), f"{name}: a failed build left a file"
            rc, out = _capture(build_decks, ["zz"])
            assert rc == 1 and "no outline tools/decks/breaches/zz.deck" in out, out
            # Control: the clean outline builds.
            rc, out = _capture(build_decks, ["aa"])
            assert rc == 0 and "built tools/decks/breaches/build/aa.pptx" in out, out
            assert r.verify_pptx(build / "aa.pptx", parse_outline(DECKS_DIR / "aa.deck")) == []
        finally:
            r.render_deck, r.verify_pptx = real


def _case_checklist_even(tmp: Path) -> None:
    """Checklist items that fit on one line sit at one even pitch, including
    a long one that a character count would wrap; an item that does wrap
    gets the room for its lines, so the next item starts below it."""
    import breach_deck_render as r

    pt, width = r.LOOK["list_pt"], r.W - r.LOOK["check_indent"]
    long_one = "Can you list every long-lived signing and export key, and when each was rotated?"
    two = f"{long_one} {long_one}"
    # Control: counting characters gives the long line two rows, so an even
    # pitch below shows the measurement is in use.
    assert r._rows(long_one, r._per_line(width, pt)) == 2
    assert r._measured_rows(long_one, width, pt) == 1
    assert r._measured_rows(two, width, pt) == 2
    checks = [["Short?"], [long_one], ["Also short?"], [two], ["Last?"]]
    (sl,) = _rendered(tmp, _one_slide("Check", "checklist", "c.deck:3", check=checks))
    texts = _shapes(sl, "check-text")
    tops, heights = [sh.top for sh in texts], [sh.height for sh in texts]
    pitch = [b - a for a, b in zip(tops, tops[1:])]
    assert max(pitch[:3]) - min(pitch[:3]) <= 100, pitch
    assert pitch[3] > pitch[2] + 100 and heights[3] > heights[0] + 100, (pitch, heights)
    for top, height, below in zip(tops, heights, tops[1:]):
        assert top + height <= below, (tops, heights)
    # Each box lines up with its item's first line.
    boxes = _shapes(sl, "check-box")
    offsets = [_cy(b) - t for b, t in zip(boxes, tops)]
    assert len(offsets) == 5 and max(offsets) - min(offsets) <= 100, offsets


RENDER_CASES: list = [
    ("render_sample", _case_render_sample),
    ("phase_contrast", _case_phase_contrast),
    ("overflow_refused", _case_overflow_refused),
    ("verify_catches_dash", _case_verify_catches_dash),
    ("verify_catches_small_font", _case_verify_catches_small_font),
    ("verify_plants", _case_verify_plants),
    ("render_diagrams", _case_render_diagrams),
    ("render_without_techniques", _case_render_without_techniques),
    ("bars_to_scale", _case_bars_to_scale),
    ("flow_two_rows", _case_flow_two_rows),
    ("timeline_even", _case_timeline_even),
    ("checklist_even", _case_checklist_even),
    ("matrix_marks", _case_matrix_marks),
    ("diagram_overflow_refused", _case_diagram_overflow_refused),
    ("build_refuses_and_cleans", _case_build_refuses_and_cleans),
]


def self_test() -> int:
    return _run_cases(CASES, "self-test")


def self_test_render() -> int:
    try:
        import breach_deck_render  # noqa: F401
    except ImportError as e:
        print(f"self-test-render: cannot import the renderer: {e}")
        return 1
    return _run_cases(RENDER_CASES, "self-test-render")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--self-test", action="store_true", help="run the built-in cases")
    ap.add_argument("--check", action="store_true", help="check outlines and breach-page links")
    ap.add_argument("--build", nargs="+", metavar="SLUG", help="render the named outlines to .pptx")
    ap.add_argument(
        "--self-test-render", action="store_true", help="run the renderer cases (needs python-pptx)"
    )
    ap.add_argument("--stale", action="store_true", help="list decks whose outline or page changed")
    ap.add_argument(
        "--published-only", action="store_true",
        help="with --stale, leave out outlines that were never published",
    )
    ap.add_argument("--status", action="store_true", help="list outline and publish state")
    ap.add_argument("--stamp", action="store_true", help="rewrite breach pages from the mapping")
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
