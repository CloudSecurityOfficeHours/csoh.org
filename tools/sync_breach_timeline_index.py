#!/usr/bin/env python3
"""
Keep the card finder on breach-timeline.html in step with its breach cards.

The timeline's cards are written by hand, one `<li class="breach-card">` per
kill chain. This tool reads them and renders a card finder
(tools/card_finder.py, card-finder.js) between the page's two marker
comments: a search field and an index of every kill chain by incident year,
each entry linking its card's id.

    <!--breach-index:start-->
    ...generated...
    <!--breach-index:end-->

An entry's name is the card title up to its first " - ", the part before the
chain of stages. Entries follow the cards' order, newest incident first.

A card that the index leaves out is one that searching cannot find, so
`--check` (in validate-html.yml) fails when the finder is out of step with the
cards, and also when a card has no id or no title, two cards share an id, or
no cards can be read at all.

The generated text sits in links and `no-glossary` spans, where
tools/crosslink_pages.py does not link glossary terms, so a cross-linking run
never edits it and `--check` stays green after one. `--self-test` asserts that
against the real glossary.

Usage:
    python3 tools/sync_breach_timeline_index.py              # rewrite the finder
    python3 tools/sync_breach_timeline_index.py --check      # exit 1 if out of step
    python3 tools/sync_breach_timeline_index.py --self-test  # planted controls

Standard library only. Idempotent: a second run changes nothing.
"""

from __future__ import annotations

import argparse
import html as htmllib
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from card_finder import Entry, group_by_year, render_finder, splice  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
PAGE = "breach-timeline.html"

START = "<!--breach-index:start-->"
END = "<!--breach-index:end-->"

# A breach card. Attributes are matched loosely so a card that gains one is
# still read rather than silently dropped.
CARD_RE = re.compile(r'<li\b([^>]*\bclass="breach-card"[^>]*)>(.*?)</li>', re.S)
ID_RE = re.compile(r'\bid="([^"]+)"')
TITLE_RE = re.compile(r'<h2\b[^>]*\bclass="breach-card-title"[^>]*>(.*?)</h2>', re.S)
YEAR_RE = re.compile(r'<span\b[^>]*\bclass="inc-year"[^>]*>\s*(\d{4})\s*</span>')


def plain(fragment: str) -> str:
    """Tags stripped, entities decoded, whitespace collapsed."""
    return " ".join(htmllib.unescape(re.sub(r"<[^>]+>", "", fragment)).split())


def collect(page_html: str) -> tuple[list[Entry], list[str]]:
    """One entry per card, in page order, and a finding for each card that
    cannot be indexed."""
    entries: list[Entry] = []
    findings: list[str] = []
    seen: set[str] = set()
    for n, m in enumerate(CARD_RE.finditer(page_html), 1):
        attrs, body = m.group(1), m.group(2)
        cid = ID_RE.search(attrs)
        title = TITLE_RE.search(body)
        where = f"card {n}" + (f" ({cid.group(1)})" if cid else "")
        if not cid:
            findings.append(f"{where}: has no id, so the index cannot link it")
            continue
        if cid.group(1) in seen:
            findings.append(f"{where}: shares its id with an earlier card")
            continue
        seen.add(cid.group(1))
        if not title or not plain(title.group(1)):
            findings.append(f"{where}: has no breach-card-title")
            continue
        name = plain(title.group(1)).split(" - ", 1)[0].strip()
        year = YEAR_RE.search(body)
        entries.append(Entry(cid.group(1), name, year.group(1) if year else ""))
    if not entries and not findings:
        # A parse that sees no cards would otherwise render an empty index
        # and pass.
        findings.append(f"{PAGE}: no breach cards found; the card markup changed")
    return entries, findings


def render_region(entries: list[Entry]) -> list[str]:
    """The lines between the markers, before indentation."""
    return render_finder(
        entries,
        input_id="breachSearch",
        id_prefix="breach-index",
        label="Search the kill chains",
        placeholder="Search by company, actor or technique",
        index_label="Kill chain index",
        noun="kill chain",
        nouns="kill chains",
        text_selector=".breach-card-meta, .breach-card-title, .breach-card-summary",
    )


def sync(root: Path, check: bool) -> int:
    page_path = root / PAGE
    try:
        raw = page_path.read_text(encoding="utf-8")
    except OSError as e:
        print(f"FINDING: {e}")
        return 1
    entries, findings = collect(raw)
    for f in findings:
        print(f"FINDING: {f}")
    try:
        new = splice(raw, START, END, render_region(entries), PAGE)
    except ValueError as e:
        print(f"FINDING: {e}")
        return 1
    if new == raw:
        print(f"{PAGE}: kill chain index up to date ({len(entries)} listed)")
    elif check:
        print(f"FINDING: {PAGE}: the kill chain index is out of step with the cards; "
              "run python3 tools/sync_breach_timeline_index.py")
        findings.append("stale")
    else:
        page_path.write_text(new, encoding="utf-8")
        print(f"{PAGE}: kill chain index rewritten ({len(entries)} listed)")
    return 1 if findings else 0


# --- self-test -------------------------------------------------------------

def _card(cid: str | None, year: str, title: str) -> str:
    id_attr = f' id="{cid}"' if cid else ""
    return (f'<li class="breach-card"{id_attr}>\n<a class="breach-card-link" href="breaches/{cid}.html">\n'
            f'<div class="breach-card-meta"><span class="inc-year">{year}</span></div>\n'
            f'<h2 class="breach-card-title">{title}</h2>\n<p class="breach-card-summary">x</p>\n</a>\n</li>\n')


def _page(cards: str) -> str:
    return (f"<main>\n<p>Before.</p>\n        {START}\n        <p>stale</p>\n        {END}\n"
            f'<ul class="breach-list" role="list">\n{cards}</ul>\n</main>\n')


def self_test() -> int:
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            failures.append(what)

    cards = (_card("new", "2026", "A &amp; &lt;B&gt; - Stage One → Stage Two")
             + _card("mid", "2025", "Mid - Stage")
             + _card("old", "2019", "No Stages Here")
             + _card("x", "2026", "Second 2026 - Stage"))

    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        (root / PAGE).write_text(_page(cards), encoding="utf-8")
        expect(sync(root, check=True) == 1, "a stale index fails --check")
        expect(sync(root, check=False) == 0, "a rewrite succeeds")
        first = (root / PAGE).read_text(encoding="utf-8")
        expect(sync(root, check=False) == 0 and (root / PAGE).read_text(encoding="utf-8") == first,
               "a second run changes nothing")
        expect(sync(root, check=True) == 0, "--check passes after a rewrite")
        expect("<p>Before.</p>" in first and "stale" not in first and first.count('class="breach-card"') == 4,
               "only the region between the markers is replaced")
        expect("\n        <div class=\"card-finder\"" in first, "the region takes the start marker's indent")
        expect('<a href="#new">A &amp; &lt;B&gt;</a>' in first, "the name stops at the first ' - ' and is escaped once")
        expect('<a href="#old">No Stages Here</a>' in first, "a title with no stages is used whole")
        expect('<div class="card-finder-filter is-hidden"' in first and 'id="breachSearch"' in first
               and 'data-finder-text=".breach-card-meta, .breach-card-title, .breach-card-summary"' in first,
               "the finder ships its field hidden and tells the script what to search")

        # Adding a card makes the index stale until the tool runs again.
        (root / PAGE).write_text(first.replace("</ul>\n</main>", _card("added", "2026", "Added - S") + "</ul>\n</main>"),
                                 encoding="utf-8")
        expect(sync(root, check=True) == 1, "a card added by hand fails --check until the tool runs")
        sync(root, check=False)
        expect('<a href="#added">Added</a>' in (root / PAGE).read_text(encoding="utf-8"),
               "a rewrite picks up the added card")

        # Each way a card can fail to be indexed is a finding.
        (root / PAGE).write_text(_page(_card(None, "2026", "No Id - S")), encoding="utf-8")
        expect(sync(root, check=False) == 1, "a card with no id is a finding")
        (root / PAGE).write_text(_page(_card("a", "2026", "A - S") + _card("a", "2025", "B - S")), encoding="utf-8")
        expect(sync(root, check=False) == 1, "two cards sharing an id is a finding")
        (root / PAGE).write_text(_page(_card("a", "2026", "")), encoding="utf-8")
        expect(sync(root, check=False) == 1, "a card with no title is a finding")
        (root / PAGE).write_text(_page('<li class="other">x</li>\n'), encoding="utf-8")
        expect(sync(root, check=False) == 1, "a page with no readable cards is a finding")
        (root / PAGE).write_text("<main></main>\n", encoding="utf-8")
        expect(sync(root, check=False) == 1, "a page without the markers is a finding")

    # A card with other attributes, in another order, is still read.
    entries, _ = collect('<li data-x="1" id="q" class="breach-card"><span class="inc-year">2023</span>'
                         '<h2 data-y="2" class="breach-card-title">Q - S</h2></li>')
    expect(entries == [Entry("q", "Q", "2023")], "cards with other attributes are still read")

    # Grouping (tools/card_finder.py), shared with the deck list page.
    def e(i: str, y: str) -> Entry:
        return Entry(i, i, y)
    groups = group_by_year([e("a", "2026"), e("b", "2025"), e("c", "2026"), e("d", "2026"),
                            e("f", "2025"), e("g", "2025"), e("h", "2024"), e("i", "2019"), e("u", "")])
    expect([(label, [x.target for x in m]) for label, m in groups]
           == [("2026", ["a", "c", "d"]), ("2025", ["b", "f", "g"]),
               ("2024 and earlier", ["h", "i"]), ("Undated", ["u"])],
           "years run newest first, and the first thin year opens one closing group")
    groups = group_by_year([e("a", "2026"), e("b", "2026"), e("c", "2026"), e("d", "2021")])
    expect([label for label, _ in groups] == ["2026", "2021"], "a closing group of one year keeps the year")
    groups = group_by_year([e("a", "2026"), e("b", "2025"), e("c", "2025"), e("d", "2025")])
    expect([label for label, _ in groups] == ["2026 and earlier"],
           "a thin newest year folds everything, rather than splitting years out of order")

    # The cross-linker must leave the generated text alone, judged with the
    # real glossary: an index whose names are every glossary key would be
    # linked somewhere if any generated text were outside a skip zone.
    try:
        import crosslink_pages as cl
        keys_to_slug, keys = cl.load_glossary_terms()
        patterns = cl.build_term_regexes(keys)
        words = " ".join(keys)
        region = "\n".join(render_region([Entry("p", words, words), Entry("q", words, "")]))
        masked, _ = cl.mask_skip_zones(region)
        _, linked_words = cl.link_text_segments(masked, patterns, keys_to_slug, "")
        expect(not linked_words, "no glossary key is linked inside the generated finder")
        masked, _ = cl.mask_skip_zones(f"<p>{htmllib.escape(words, quote=False)}</p>")
        _, control_words = cl.link_text_segments(masked, patterns, keys_to_slug, "")
        expect(bool(control_words), "control: the same words in a plain paragraph are linked")
    except Exception as exc:  # noqa: BLE001 - report, never pass silently
        expect(False, f"cross-linker check could not run: {exc!r}")

    print(f"\nself-test: {len(failures)} failure(s)")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit 1 if the finder is out of step")
    mode.add_argument("--self-test", action="store_true", help="run the planted controls")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return sync(REPO, check=args.check)


if __name__ == "__main__":
    sys.exit(main())
