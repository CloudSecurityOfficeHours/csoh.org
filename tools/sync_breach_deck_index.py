#!/usr/bin/env python3
"""
Keep the deck list on breach-kill-chain-decks.html in step with the published
breach kill chain decks.

tools/decks/breaches/published.json records every breach deck that is public
(`build_breach_decks.py --record` writes it). This tool renders an index of
the decks, grouped by incident year, and one card per entry between the
page's two marker comments:

    <!--breach-decks:start-->
    ...generated...
    <!--breach-decks:end-->

Each card takes its title, promise and as-of date from the deck's outline,
its slide count from the outline plus the slides the renderer generates (the
cover, "how to use this deck" and the closing), its presentation id from the
mapping, and its incident year, platform and "Industries hit" line from the
deck's card on breach-timeline.html. The finder offers a button for each
industry the listed decks carry (tools/breach_industries.py). Cards follow the timeline's order, newest incident
first, so the list reads like the hub it comes from. Above the cards sits a
card finder (tools/card_finder.py, card-finder.js): a search field and an
index of the decks by incident year, each entry linking its card. The slide
count and as-of tags carry data-finder-skip, because every card has them and
a search for this year's number would otherwise match every deck.

The line above the finder says whether every kill chain on the timeline has a
deck. While some do not, it says "so far" and a note below the cards tells
readers a missing deck is still being written. Once every one has a deck, the
line says so and the note is left out. The tool writes both because only it
compares the list with the timeline, so the page cannot keep saying decks are
on their way after the last one is published.

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
from breach_industries import INDUSTRIES, read_line, render_line, synonym_map  # noqa: E402
from card_finder import Entry, render_finder  # noqa: E402
from card_finder import splice as splice_region  # noqa: E402

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
CARD_PROV_RE = re.compile(r'<span\b[^>]*\bclass="prov-tag\b[^"]*"[^>]*>(.*?)</span>', re.S)


@dataclass(frozen=True)
class Deck:
    slug: str
    title: str
    promise: str
    as_of: str
    slides: int
    pres_id: str
    year: str
    provider: str
    industries: tuple[str, ...] = ()


def timeline_order(timeline_html: str) -> dict[str, tuple[int, str, str, tuple[str, ...]]]:
    """slug -> (position, incident year, platform, industries), in the order
    the hub lists them. The platform is the card's plain text, unescaped. The
    industries are whatever the card's line names that the vocabulary knows;
    a wrong line is sync_breach_timeline_index.py's to report."""
    order: dict[str, tuple[int, str, str, tuple[str, ...]]] = {}
    for m in TIMELINE_CARD_RE.finditer(timeline_html):
        card = m.group(1)
        href = CARD_HREF_RE.search(card)
        year = CARD_YEAR_RE.search(card)
        prov = CARD_PROV_RE.search(card)
        provider = " ".join(htmllib.unescape(re.sub(r"<[^>]+>", "", prov.group(1))).split()) if prov else ""
        if href and href.group(1) not in order:
            order[href.group(1)] = (len(order), year.group(1) if year else "", provider,
                                    tuple(read_line(card)[0]))
    return order


def collect(root: Path) -> tuple[list[Deck], list[str], int]:
    """Every published deck that can be listed, newest incident first, a
    finding for each one that cannot, and how many kill chains on the
    timeline have no listed deck."""
    findings: list[str] = []
    mapping_path = root / DECKS_DIR / "published.json"
    try:
        mapping = json.loads(mapping_path.read_text(encoding="utf-8")) if mapping_path.exists() else {}
    except (OSError, ValueError) as e:
        return [], [f"{mapping_path.relative_to(root)}: cannot be read as JSON: {e}"], 0
    if not isinstance(mapping, dict):
        return [], [f"{mapping_path.relative_to(root)}: must be a JSON object keyed by slug"], 0

    timeline_path = root / TIMELINE
    order = timeline_order(timeline_path.read_text(encoding="utf-8")) if timeline_path.exists() else {}
    if mapping and not order:
        # A parse that sees no cards would otherwise report every deck as
        # missing from the timeline, or, worse, pass an empty list.
        findings.append(f"{TIMELINE}: no breach cards found; the timeline markup changed")
        return [], findings, 0

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
        position, year, provider, industries = order[slug]
        placed.append((position, Deck(
            slug=slug,
            title=deck.title,
            promise=deck.promise,
            as_of=deck.as_of,
            slides=len(deck.slides) + GENERATED_SLIDES,
            pres_id=pres_id,
            year=year,
            provider=provider,
            industries=industries,
        )))
    placed.sort(key=lambda p: p[0])
    decks = [d for _, d in placed]
    listed = {d.slug for d in decks}
    missing = sum(1 for slug in order if slug not in listed)
    return decks, findings, missing


def _text(s: str) -> str:
    return htmllib.escape(s, quote=False)


def _attr(s: str) -> str:
    return htmllib.escape(s, quote=True)


def render_card(d: Deck) -> list[str]:
    base = f"https://docs.google.com/presentation/d/{d.pres_id}"
    # (text, searched): every card has a slide count and an as-of date, so the
    # finder leaves them out of the search.
    tags = [(t, searched) for t, searched in ((d.year, True), (d.provider, True),
                                              (f"{d.slides} slides", False), (f"As of {d.as_of}", False)) if t]
    return [
        f'<div class="resource-card resource-card--deck" id="deck-{d.slug}" data-icon="📑">',
        f"    <h3>{_text(d.title)}</h3>",
        f'    <p><span class="no-glossary">{_text(d.promise)}</span></p>',
        *(["    " + render_line(d.industries)] if d.industries else []),
        '    <div class="resource-tags">',
        *[f'        <span class="tag no-glossary"{"" if searched else " data-finder-skip"}>{_text(t)}</span>'
          for t, searched in tags],
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


def render_index(decks: list[Deck]) -> list[str]:
    """The card finder: a search field, a button per industry the listed
    decks carry, and the decks by incident year."""
    return render_finder(
        [Entry(f"deck-{d.slug}", d.title, d.year) for d in decks],
        input_id="deckSearch",
        id_prefix="deck-index",
        label="Search the decks",
        placeholder="Search by company, actor, platform or industry",
        index_label="Deck index",
        noun="deck",
        nouns="decks",
        text_selector="h3, p, .tag",
        filters=sorted({x for d in decks for x in d.industries}),
        filter_label="Industries",
        filter_selector=".industries-hit",
        synonyms=synonym_map(),
    )


def render_region(decks: list[Deck], missing: int) -> list[str]:
    """The lines between the markers, before indentation. `missing` is how
    many kill chains on the timeline have no listed deck."""
    if not decks:
        return ['<p><span class="no-glossary">No decks are published yet.</span></p>']
    n = len(decks)
    noun = "deck" if n == 1 else "decks"
    count = f"{n} {noun} so far" if missing else f"{n} {noun}, one for every kill chain"
    lines = [
        f'<p><span class="no-glossary">{count}, newest incident first.</span></p>',
        *render_index(decks),
        '<div class="resource-grid">',
    ]
    for d in decks:
        lines += ["    " + ln for ln in render_card(d)]
    lines.append("</div>")
    if missing:
        lines.append(
            '<p><span class="no-glossary">Looking for a kill chain that is not listed yet? Its deck is still '
            'being written, and the <a href="breach-timeline.html">full kill chain</a> is there to read in the '
            "meantime.</span></p>"
        )
    return lines


def splice(page_html: str, region: list[str]) -> str:
    """page_html with everything between the markers replaced by region,
    indented to match the start marker. Raises ValueError on bad markers."""
    return splice_region(page_html, START, END, region, PAGE)


def sync(root: Path, check: bool) -> int:
    decks, findings, missing = collect(root)
    for f in findings:
        print(f"FINDING: {f}")
    page_path = root / PAGE
    try:
        raw = page_path.read_text(encoding="utf-8")
        new = splice(raw, render_region(decks, missing))
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


def _fixture(tmp: Path, mapping: dict, timeline: list[tuple], titles: dict[str, str] | None = None) -> Path:
    """`timeline` entries are (slug, year) or (slug, year, industries)."""
    root = tmp / "root"
    (root / DECKS_DIR).mkdir(parents=True)
    (root / "breaches").mkdir()
    (root / DECKS_DIR / "published.json").write_text(json.dumps(mapping), encoding="utf-8")
    cards = "".join(
        f'<li class="breach-card" id="{t[0]}"><a class="breach-card-link" href="breaches/{t[0]}.html">'
        f'<span class="inc-year">{t[1]}</span><span class="prov-tag prov-aws">AWS &amp; {t[0]} · Cloud</span>'
        f'{render_line(t[2]) if len(t) > 2 else ""}</a></li>\n'
        for t in timeline
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
        expect('<span class="tag no-glossary">AWS &amp; aaa · Cloud</span>' in first,
               "the platform comes from the timeline, unescaped once and escaped once")
        nav = first[first.index('<div class="card-finder-index"'):first.index('<div class="resource-grid">')]
        expect(nav.index('href="#deck-bbb"') < nav.index('href="#deck-aaa"'),
               "the index follows the timeline order")
        expect('<a href="#deck-aaa">A &amp; &lt;B&gt;</a>' in nav, "index titles are escaped")
        expect('id="deck-index-2026-and-earlier"' in nav and 'aria-labelledby="deck-index-2026-and-earlier"' in nav,
               "index groups are labelled and carry the deck prefix")
        expect(first.index('class="card-finder"') < first.index('<div class="resource-grid">'),
               "the finder sits above the cards")
        expect('<div class="card-finder-filter is-hidden"' in first and 'id="deckSearch"' in first
               and 'data-finder-text="h3, p, .tag"' in first and 'data-finder-nouns="decks"' in first,
               "the finder ships its field hidden and tells the script what to search")
        expect('<span class="tag no-glossary" data-finder-skip>As of 2026-11-20</span>' in first
               and f'<span class="tag no-glossary" data-finder-skip>{1 + GENERATED_SLIDES} slides</span>' in first
               and '<span class="tag no-glossary">2024</span>' in first,
               "the slide count and as-of tags are left out of the search, the year is not")
        expect("2 decks so far" in first, "the count is plural for two")
        expect("one for every kill chain" not in first,
               "a timeline kill chain with no deck (zzz) keeps the count at 'so far'")
        expect(first.index('<div class="resource-grid">') < first.index("not listed yet"),
               "while a kill chain has no deck, a note below the cards says its deck is being written")
        expect("<p>Before.</p>" in first and "<p>After.</p>" in first and "stale" not in first,
               "only the region between the markers is replaced")
        expect("\n        <div class=\"resource-grid\">\n" in first, "the region takes the start marker's indent")
        for link in (f"{ID_A}/export/pdf", f"{ID_A}/copy", f"{ID_A}/embed", 'href="breaches/aaa.html"'):
            expect(link in first, f"the card links {link}")

        # One deck while another kill chain waits: singular count.
        root = _fixture(tmp / "2", {"aaa": {"id": ID_A}}, [("aaa", "2026"), ("zzz", "2025")])
        sync(root, check=False)
        expect("1 deck so far" in (root / PAGE).read_text(encoding="utf-8"), "the count is singular for one")

        # Every kill chain on the timeline has a deck: the count says so and
        # the "still being written" note is gone.
        root = _fixture(tmp / "2b", {"aaa": {"id": ID_A}, "bbb": {"id": ID_B}}, [("bbb", "2026"), ("aaa", "2024")])
        expect(sync(root, check=False) == 0, "a fully covered timeline rewrites cleanly")
        full = (root / PAGE).read_text(encoding="utf-8")
        expect("2 decks, one for every kill chain, newest incident first." in full,
               "with every kill chain covered, the count says so")
        expect("so far" not in full and "not listed yet" not in full,
               "with every kill chain covered, nothing says more decks are coming")
        expect(sync(root, check=False) == 0 and (root / PAGE).read_text(encoding="utf-8") == full,
               "a second run on a fully covered timeline changes nothing")

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
                               '<span class="inc-year">2023</span>'
                               '<span data-y="2" class="prov-tag prov-gcp">GCP</span></a></li>')
        expect(order == {"q": (0, "2023", "GCP", ())}, "timeline cards with other attributes are still read")

        # Industries come from the timeline cards. bbb carries Finance and
        # Retail; aaa carries none; zzz carries Legal but has no deck.
        root = _fixture(tmp / "10", {"aaa": {"id": ID_A}, "bbb": {"id": ID_B}},
                        [("bbb", "2026", ["Retail", "Finance"]), ("zzz", "2025", ["Legal"]), ("aaa", "2024")])
        expect(sync(root, check=False) == 0, "decks whose chains carry industries rewrite cleanly")
        page = (root / PAGE).read_text(encoding="utf-8")
        card_b = page[page.index('id="deck-bbb"'):page.index('id="deck-aaa"')]
        card_a = page[page.index('id="deck-aaa"'):]
        line = render_line(["Finance", "Retail"])
        expect(line in card_b and card_b.index('<p><span class="no-glossary">What')
               < card_b.index(line) < card_b.index('<div class="resource-tags">'),
               "a deck card carries its chain's industries line, after the promise and before the tags")
        expect("industries-hit" not in card_a[:card_a.index("</iframe>")],
               "a deck whose chain has no line gets none")
        expect(re.findall(r'data-finder-query="([^"]+)"', page) == ["Finance", "Retail"],
               "buttons cover the listed decks' industries only, alphabetical")
        expect('placeholder="Search by company, actor, platform or industry"' in page,
               "the placeholder names industries")
        expect('data-finder-synonyms="' in page and "bank=finance" in page, "the synonym map is rendered")
        expect('data-finder-filter=".industries-hit"' in page,
               "a pressed industry matches only the cards' industries lines")
        expect(sync(root, check=False) == 0 and (root / PAGE).read_text(encoding="utf-8") == page,
               "a second run with industries changes nothing")

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
                     slides=99, pres_id=ID_A, year=words, provider=words, industries=tuple(INDUSTRIES))
        region = "\n".join(render_region([probe, probe], missing=1))
        expect("not listed yet" in region, "the probe region includes the 'still being written' note")
        expect(region.count("data-finder-query=") == len(INDUSTRIES) and "industries-hit" in region,
               "the probe region includes every industry's button and the industries lines")
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
