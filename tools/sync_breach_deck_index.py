#!/usr/bin/env python3
"""
Keep the deck list on breach-kill-chain-decks.html in step with the published
breach kill chain decks.

tools/decks/breaches/published.json records every breach deck that is public
(`build_breach_decks.py --record` writes it). This tool renders one card per
entry between the page's two marker comments:

    <!--breach-decks:start-->
    ...generated...
    <!--breach-decks:end-->

Each card takes its title, promise and as-of date from the deck's outline,
its slide count from the outline plus the slides the renderer generates (the
cover, "how to use this deck" and the closing), its presentation id from the
mapping, and its incident year from the deck's card on breach-timeline.html.
Cards follow the timeline's order, newest incident first, so the list reads
like the hub it comes from.

A deck that is published but has no card here is a deck readers cannot find,
so `--check` (in validate-html.yml) fails when the list is out of step, and
also when a mapped deck has no outline, no breach page, or no timeline card.

The generated text sits where tools/crosslink_pages.py does not link glossary
terms (headings, links, and `no-glossary` spans), so a cross-linking run never
edits the list and `--check` stays green after one. `--self-test` asserts that
against the real glossary.

Usage:
    python3 tools/sync_breach_deck_index.py              # rewrite the list
    python3 tools/sync_breach_deck_index.py --check      # exit 1 if out of step
    python3 tools/sync_breach_deck_index.py --self-test  # planted controls

Standard library only. Idempotent: a second run changes nothing.
"""

from __future__ import annotations

import argparse
import html as htmllib
import json
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_breach_decks import (  # noqa: E402
    GENERATED_SLIDES,
    OutlineError,
    PRES_ID_RE,
    parse_outline_text,
)

REPO = Path(__file__).resolve().parent.parent
PAGE = "breach-kill-chain-decks.html"
TIMELINE = "breach-timeline.html"
DECKS_DIR = Path("tools") / "decks" / "breaches"

START = "<!--breach-decks:start-->"
END = "<!--breach-decks:end-->"
LICENCE_URL = "https://creativecommons.org/licenses/by-nc/4.0/"
EXT = 'target="_blank" rel="noopener noreferrer"'

# A breach card on the timeline. Attributes are matched loosely so a card that
# gains one is still read rather than silently dropped.
TIMELINE_CARD_RE = re.compile(r'<li\b[^>]*\bclass="breach-card"[^>]*>(.*?)</li>', re.S)
CARD_HREF_RE = re.compile(r'\bhref="breaches/([a-z0-9-]+)\.html"')
CARD_YEAR_RE = re.compile(r'<span\b[^>]*\bclass="inc-year"[^>]*>\s*(\d{4})\s*</span>')


@dataclass(frozen=True)
class Deck:
    slug: str
    title: str
    promise: str
    as_of: str
    slides: int
    pres_id: str
    year: str


def timeline_order(timeline_html: str) -> dict[str, tuple[int, str]]:
    """slug -> (position, incident year), in the order the hub lists them."""
    order: dict[str, tuple[int, str]] = {}
    for m in TIMELINE_CARD_RE.finditer(timeline_html):
        card = m.group(1)
        href = CARD_HREF_RE.search(card)
        year = CARD_YEAR_RE.search(card)
        if href and href.group(1) not in order:
            order[href.group(1)] = (len(order), year.group(1) if year else "")
    return order


def collect(root: Path) -> tuple[list[Deck], list[str]]:
    """Every published deck that can be listed, newest incident first, and a
    finding for each one that cannot."""
    findings: list[str] = []
    mapping_path = root / DECKS_DIR / "published.json"
    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
    except (OSError, ValueError) as e:
        return [], [f"{mapping_path.relative_to(root)}: cannot be read as JSON: {e}"]
    if not isinstance(mapping, dict):
        return [], [f"{mapping_path.relative_to(root)}: must be a JSON object keyed by slug"]

    timeline_path = root / TIMELINE
    order = timeline_order(timeline_path.read_text(encoding="utf-8")) if timeline_path.exists() else {}
    if mapping and not order:
        # A parse that sees no cards would otherwise report every deck as
        # missing from the timeline, or, worse, pass an empty list.
        findings.append(f"{TIMELINE}: no breach cards found; the timeline markup changed")
        return [], findings

    placed: list[tuple[int, Deck]] = []
    for slug in sorted(mapping):
        entry = mapping[slug]
        pres_id = entry.get("id") if isinstance(entry, dict) else None
        if not (isinstance(pres_id, str) and PRES_ID_RE.fullmatch(pres_id)):
            findings.append(f"{slug}: published.json has no well-formed presentation id")
            continue
        outline = root / DECKS_DIR / f"{slug}.deck"
        if not outline.exists():
            findings.append(f"{slug}: published, but {outline.relative_to(root)} does not exist")
            continue
        try:
            deck = parse_outline_text(outline.read_text(encoding="utf-8"), f"{slug}.deck")
        except OutlineError as e:
            findings.append(f"{slug}: outline does not parse: {e}")
            continue
        page = f"breaches/{slug}.html"
        if deck.page != page:
            findings.append(f"{slug}: outline names {deck.page}, expected {page}")
            continue
        if not (root / page).exists():
            findings.append(f"{slug}: published, but {page} does not exist")
            continue
        if slug not in order:
            findings.append(f"{slug}: no card links {page} on {TIMELINE}, so the deck has no place in the list")
            continue
        position, year = order[slug]
        placed.append((position, Deck(
            slug=slug,
            title=deck.title,
            promise=deck.promise,
            as_of=deck.as_of,
            slides=len(deck.slides) + GENERATED_SLIDES,
            pres_id=pres_id,
            year=year,
        )))
    placed.sort(key=lambda p: p[0])
    return [d for _, d in placed], findings


def _text(s: str) -> str:
    return htmllib.escape(s, quote=False)


def _attr(s: str) -> str:
    return htmllib.escape(s, quote=True)


def render_card(d: Deck) -> list[str]:
    base = f"https://docs.google.com/presentation/d/{d.pres_id}"
    tags = [t for t in (d.year, f"{d.slides} slides", f"As of {d.as_of}") if t]
    return [
        f'<div class="resource-card resource-card--deck" id="deck-{d.slug}" data-icon="📑">',
        f"    <h3>{_text(d.title)}</h3>",
        f'    <p><span class="no-glossary">{_text(d.promise)}</span></p>',
        '    <div class="resource-tags">',
        *[f'        <span class="tag no-glossary">{_text(t)}</span>' for t in tags],
        "    </div>",
        '    <div class="deck-actions">',
        f'        <a class="card-action" href="{base}/export/pdf" {EXT}>Download the PDF</a>',
        f'        <a class="card-action" href="{base}/copy" {EXT}>Make your own copy</a>',
        f'        <a class="card-action" href="breaches/{d.slug}.html">Read the kill chain</a>',
        "    </div>",
        # The preview shows without a toggle; loading="lazy" holds each
        # iframe back until its card nears the viewport.
        '    <div class="deck-frame">',
        f'        <iframe src="{base}/embed" title="{_attr(d.title)} slide deck" loading="lazy" allowfullscreen></iframe>',
        "    </div>",
        "</div>",
    ]


def render_region(decks: list[Deck]) -> list[str]:
    """The lines between the markers, before indentation."""
    if not decks:
        return ['<p><span class="no-glossary">No decks are published yet.</span></p>']
    n = len(decks)
    count = f"{n} deck so far" if n == 1 else f"{n} decks so far"
    lines = [
        f'<p><span class="no-glossary">{count}, newest incident first.</span></p>',
        '<div class="resource-grid">',
    ]
    for d in decks:
        lines += ["    " + ln for ln in render_card(d)]
    lines.append("</div>")
    return lines


def splice(page_html: str, region: list[str]) -> str:
    """page_html with everything between the markers replaced by region,
    indented to match the start marker. Raises ValueError on bad markers."""
    starts = page_html.count(START)
    ends = page_html.count(END)
    if starts != 1 or ends != 1:
        raise ValueError(f"{PAGE} needs exactly one {START} and one {END} (found {starts} and {ends})")
    m = re.search(r"^([ \t]*)" + re.escape(START) + r"[ \t]*\n(.*?)^[ \t]*" + re.escape(END), page_html, re.S | re.M)
    if not m:
        raise ValueError(f"{PAGE}: {START} and {END} must each sit on a line of their own, start first")
    indent = m.group(1)
    body = "".join(f"{indent}{ln}\n" if ln else "\n" for ln in region)
    return page_html[: m.start(2)] + body + page_html[m.start(2) + len(m.group(2)):]


def sync(root: Path, check: bool) -> int:
    decks, findings = collect(root)
    for f in findings:
        print(f"FINDING: {f}")
    page_path = root / PAGE
    try:
        raw = page_path.read_text(encoding="utf-8")
        new = splice(raw, render_region(decks))
    except (OSError, ValueError) as e:
        print(f"FINDING: {e}")
        return 1
    if new == raw:
        print(f"{PAGE}: deck list up to date ({len(decks)} listed)")
    elif check:
        print(f"FINDING: {PAGE}: deck list is out of step with {DECKS_DIR}/published.json; "
              "run python3 tools/sync_breach_deck_index.py")
        findings.append("stale")
    else:
        page_path.write_text(new, encoding="utf-8")
        print(f"{PAGE}: deck list rewritten ({len(decks)} listed)")
    return 1 if findings else 0


# --- self-test -------------------------------------------------------------

OUTLINE = """title: {title}
page: breaches/{slug}.html
as-of: 2026-11-20
promise: {promise}

== {heading}
notes:
Notes.
"""

PAGE_SKELETON = f"""<main>
<p>Before.</p>
        {START}
        <p>stale</p>
        {END}
<p>After.</p>
</main>
"""


def _fixture(tmp: Path, mapping: dict, timeline: list[tuple[str, str]], titles: dict[str, str] | None = None) -> Path:
    root = tmp / "root"
    (root / DECKS_DIR).mkdir(parents=True)
    (root / "breaches").mkdir()
    (root / DECKS_DIR / "published.json").write_text(json.dumps(mapping), encoding="utf-8")
    cards = "".join(
        f'<li class="breach-card" id="{s}"><a class="breach-card-link" href="breaches/{s}.html">'
        f'<span class="inc-year">{y}</span></a></li>\n'
        for s, y in timeline
    )
    (root / TIMELINE).write_text(f"<ol>\n{cards}</ol>\n", encoding="utf-8")
    for slug in mapping:
        title = (titles or {}).get(slug, slug.upper())
        (root / DECKS_DIR / f"{slug}.deck").write_text(
            OUTLINE.format(title=title, slug=slug, promise=f"What {title} did.", heading="Slide"),
            encoding="utf-8",
        )
        (root / "breaches" / f"{slug}.html").write_text("<html></html>\n", encoding="utf-8")
    (root / PAGE).write_text(PAGE_SKELETON, encoding="utf-8")
    return root


ID_A = "1ExOZRRQkI7J50ZcIsKXauhiBhmZU_5Sw4M8mL9Gbtgg"
ID_B = "1Aty73b-UmRXItQ-dC51cEAYf56ZvseqmrfUzMNpwP3c"


def self_test() -> int:
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            failures.append(what)

    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)

        # Two decks, listed in the timeline's order (b before a), not the
        # mapping's, with year, slide count, escaping and the plural count.
        root = _fixture(tmp / "1", {"aaa": {"id": ID_A}, "bbb": {"id": ID_B}},
                        [("bbb", "2026"), ("zzz", "2025"), ("aaa", "2024")],
                        titles={"aaa": "A & <B>"})
        expect(sync(root, check=True) == 1, "a stale list fails --check")
        expect(sync(root, check=False) == 0, "a rewrite succeeds")
        first = (root / PAGE).read_text(encoding="utf-8")
        expect(sync(root, check=False) == 0 and (root / PAGE).read_text(encoding="utf-8") == first,
               "a second run changes nothing")
        expect(sync(root, check=True) == 0, "--check passes after a rewrite")
        expect(first.index('id="deck-bbb"') < first.index('id="deck-aaa"'), "cards follow the timeline order")
        expect("<h3>A &amp; &lt;B&gt;</h3>" in first and 'title="A &amp; &lt;B&gt; slide deck"' in first,
               "titles are escaped in text and attributes")
        expect(f"{1 + GENERATED_SLIDES} slides" in first, "the slide count adds the generated slides")
        expect('<span class="tag no-glossary">2024</span>' in first, "the incident year comes from the timeline")
        expect("2 decks so far" in first, "the count is plural for two")
        expect("<p>Before.</p>" in first and "<p>After.</p>" in first and "stale" not in first,
               "only the region between the markers is replaced")
        expect("\n        <div class=\"resource-grid\">\n" in first, "the region takes the start marker's indent")
        for link in (f"{ID_A}/export/pdf", f"{ID_A}/copy", f"{ID_A}/embed", 'href="breaches/aaa.html"'):
            expect(link in first, f"the card links {link}")

        # One deck: singular count.
        root = _fixture(tmp / "2", {"aaa": {"id": ID_A}}, [("aaa", "2026")])
        sync(root, check=False)
        expect("1 deck so far" in (root / PAGE).read_text(encoding="utf-8"), "the count is singular for one")

        # Each way a mapped deck can fail to be listed is a finding.
        root = _fixture(tmp / "3", {"aaa": {"id": ID_A}}, [("other", "2026")])
        expect(sync(root, check=False) == 1, "a deck missing from the timeline is a finding")
        root = _fixture(tmp / "4", {"aaa": {"id": "not-an-id"}}, [("aaa", "2026")])
        expect(sync(root, check=False) == 1, "a malformed presentation id is a finding")
        root = _fixture(tmp / "5", {"aaa": {"id": ID_A}}, [("aaa", "2026")])
        (root / DECKS_DIR / "aaa.deck").unlink()
        expect(sync(root, check=False) == 1, "a published deck with no outline is a finding")
        root = _fixture(tmp / "6", {"aaa": {"id": ID_A}}, [("aaa", "2026")])
        (root / "breaches" / "aaa.html").unlink()
        expect(sync(root, check=False) == 1, "a published deck with no breach page is a finding")
        root = _fixture(tmp / "7", {"aaa": {"id": ID_A}}, [("aaa", "2026")])
        (root / TIMELINE).write_text("<ul><li class=\"other\">x</li></ul>\n", encoding="utf-8")
        expect(sync(root, check=False) == 1, "a timeline with no readable cards is a finding")
        root = _fixture(tmp / "8", {"aaa": {"id": ID_A}}, [("aaa", "2026")])
        (root / PAGE).write_text("<main></main>\n", encoding="utf-8")
        expect(sync(root, check=False) == 1, "a page without the markers is a finding")

        # A card with an extra attribute on the timeline is still read.
        order = timeline_order('<li data-x="1" class="breach-card" id="q"><a href="breaches/q.html">'
                               '<span class="inc-year">2023</span></a></li>')
        expect(order == {"q": (0, "2023")}, "timeline cards with other attributes are still read")

        # No decks: the region says so rather than rendering an empty grid.
        root = _fixture(tmp / "9", {}, [("aaa", "2026")])
        expect(sync(root, check=False) == 0, "an empty mapping is not an error")
        expect("No decks are published yet." in (root / PAGE).read_text(encoding="utf-8"),
               "an empty mapping says no decks are published")

    # The cross-linker must leave the generated text alone, judged with the
    # real glossary. A card built from every glossary key as its words would
    # be linked somewhere if any generated text were outside a skip zone.
    try:
        import crosslink_pages as cl
        keys_to_slug, keys = cl.load_glossary_terms()
        patterns = cl.build_term_regexes(keys)
        words = " ".join(keys)
        probe = Deck(slug="probe", title=words, promise=words, as_of=words,
                     slides=99, pres_id=ID_A, year=words)
        region = "\n".join(render_region([probe, probe]))
        masked, placeholders = cl.mask_skip_zones(region)
        linked, linked_words = cl.link_text_segments(masked, patterns, keys_to_slug, "")
        expect(not linked_words, "no glossary key is linked inside the generated list")
        # Control: the same words outside a skip zone are linked.
        masked, _ = cl.mask_skip_zones(f"<p>{_text(words)}</p>")
        _, control_words = cl.link_text_segments(masked, patterns, keys_to_slug, "")
        expect(bool(control_words), "control: the same words in a plain paragraph are linked")
    except Exception as e:  # noqa: BLE001 - report, never pass silently
        expect(False, f"cross-linker check could not run: {e!r}")

    print(f"\nself-test: {len(failures)} failure(s)")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit 1 if the list is out of step")
    mode.add_argument("--self-test", action="store_true", help="run the planted controls")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return sync(REPO, check=args.check)


if __name__ == "__main__":
    sys.exit(main())
