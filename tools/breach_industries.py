#!/usr/bin/env python3
"""
The industries a breach kill chain can be tagged with, and the one line on a
card that carries them.

Each card on breach-timeline.html names the industries its breach hit, in one
line written by hand:

    <p class="industries-hit"><span class="industries-hit-label" data-finder-skip>Industries hit:</span> <span class="no-glossary">Finance, Healthcare</span></p>

A chain is tagged with an industry only when its breach page says an
organization in that industry was compromised, lost data, money or access,
or took services offline because of the attack. A chain whose page names no
victim industry has no line.

tools/sync_breach_timeline_index.py validates every card's line against this
vocabulary and offers the industries as buttons in the page's card finder;
tools/sync_breach_deck_index.py copies each line onto the chain's deck card.
The synonyms let a reader who types "bank" find the Finance cards
(card-finder.js), so each one is a single, unambiguous word: "exchange" is
left out because it is also Microsoft Exchange, "cloud" because it is on
every card.

Usage:
    python3 tools/breach_industries.py --self-test   # planted controls

Standard library only.
"""

from __future__ import annotations

import argparse
import html as htmllib
import re
import sys
import unicodedata
from collections.abc import Iterable

INDUSTRIES: dict[str, tuple[str, ...]] = {
    "Crypto": ("cryptocurrency", "bitcoin", "blockchain", "defi", "web3", "ethereum", "stablecoin"),
    "Education": ("university", "universities", "school", "schools", "college", "academic"),
    "Energy": ("utility", "utilities", "oil", "electricity"),
    "Finance": ("bank", "banks", "banking", "financial", "fintech", "insurance", "insurer", "payments",
                "brokerage", "lender"),
    "Government": ("federal", "agency", "agencies", "military", "defense", "gov", "govt"),
    "Healthcare": ("health", "hospital", "hospitals", "medical", "pharmacy", "pharma", "clinic", "patients"),
    "Hospitality": ("hotel", "hotels", "casino", "casinos", "resort", "resorts", "travel", "restaurant"),
    "Legal": ("law", "lawyer", "lawyers", "attorney", "attorneys"),
    "Manufacturing": ("manufacturer", "industrial", "factory", "automotive", "semiconductor"),
    "Media": ("entertainment", "streaming", "news", "publishing", "publisher"),
    "Retail": ("ecommerce", "commerce", "store", "stores", "shopping", "retailer", "retailers"),
    "Technology": ("tech", "software", "saas", "developer", "developers", "hosting"),
    "Telecom": ("telecommunications", "telco", "carrier", "carriers", "wireless", "isp"),
    "Transportation": ("airline", "airlines", "logistics", "aviation", "transit", "rideshare"),
}

LABEL_TEXT = "Industries hit:"

LINE_RE = re.compile(r'<p\b[^>]*\bclass="industries-hit"[^>]*>.*?</p>', re.S)
WORD_RE = re.compile(r"[a-z0-9]+")


def fold(s: str) -> str:
    """What card-finder.js compares: accents dropped, lower-cased, and every
    run of anything but a-z and 0-9 turned into one space."""
    s = re.sub("[̀-ͯ]", "", unicodedata.normalize("NFKD", s)).lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def vocabulary_findings(vocab: dict[str, tuple[str, ...]] | None = None) -> list[str]:
    """Problems with the vocabulary itself. Labels and synonyms must each be
    one word that folding leaves alone (apart from case), so the script's
    word-by-word match can find them, and no word may point at two
    industries."""
    vocab = INDUSTRIES if vocab is None else vocab
    findings: list[str] = []
    labels = {fold(label): label for label in vocab}
    for label in vocab:
        if not WORD_RE.fullmatch(fold(label)) or fold(label) != label.lower():
            findings.append(f'label "{label}" must be one word of letters and digits')
    owner: dict[str, str] = {}
    for label, words in vocab.items():
        for w in words:
            if not WORD_RE.fullmatch(w):
                findings.append(f'{label}: synonym "{w}" must be one lower-case word of letters and digits')
            elif w in labels:
                findings.append(f'{label}: synonym "{w}" is itself the industry {labels[w]}')
            elif w in owner:
                findings.append(f'synonym "{w}" belongs to both {owner[w]} and {label}')
            owner.setdefault(w, label)
    return findings


def synonym_map() -> dict[str, str]:
    """Folded synonym -> folded industry, for the card finder."""
    return {w: fold(label) for label, words in INDUSTRIES.items() for w in words}


def render_line(labels: Iterable[str]) -> str:
    """The canonical line for a card, industries in alphabetical order."""
    names = ", ".join(htmllib.escape(x, quote=False) for x in sorted(set(labels)))
    return (f'<p class="industries-hit"><span class="industries-hit-label" data-finder-skip>{LABEL_TEXT}</span>'
            f' <span class="no-glossary">{names}</span></p>')


def read_line(card_html: str) -> tuple[list[str], list[str]]:
    """The industries on a card's line, alphabetical (none when the card has
    no line), and a finding for each problem with it. Findings don't name the
    card; the caller does."""
    lines = LINE_RE.findall(card_html)
    if not lines:
        return [], []
    findings: list[str] = []
    if len(lines) > 1:
        findings.append(f"has more than one industries line ({len(lines)})")
    line = lines[0]
    text = " ".join(htmllib.unescape(re.sub(r"<[^>]+>", " ", line)).split())
    if text.startswith(LABEL_TEXT):
        text = text[len(LABEL_TEXT):]
    named = [x.strip() for x in re.split(r"[,·]", text) if x.strip()]
    if not named:
        findings.append("the industries line names no industry")
    known: list[str] = []
    for x in named:
        if x not in INDUSTRIES:
            findings.append(f'"{x}" is not an industry; the industries are: {", ".join(INDUSTRIES)}')
        elif x in known:
            findings.append(f'"{x}" is listed more than once')
        else:
            known.append(x)
    labels = sorted(known)
    # The canonical line can only be offered when every name is known.
    if labels and all(x in INDUSTRIES for x in named) and line != render_line(labels):
        findings.append(f"the industries line should read: {render_line(labels)}")
    return labels, findings


# --- self-test -------------------------------------------------------------

def self_test() -> int:
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            failures.append(what)

    canonical = ('<p class="industries-hit"><span class="industries-hit-label" data-finder-skip>'
                 'Industries hit:</span> <span class="no-glossary">Finance, Healthcare</span></p>')

    expect(vocabulary_findings() == [], "the shipped vocabulary has no problems")
    expect(render_line(["Healthcare", "Finance"]) == canonical,
           "the line is rendered in its canonical form, labels sorted")
    expect(read_line("<li>" + render_line(["Retail", "Finance"]) + "</li>") == (["Finance", "Retail"], []),
           "a canonical line is read back with no findings")
    expect(read_line("<li>no line</li>") == ([], []), "a card with no line has no labels and no findings")

    def findings_for(inner: str, attrs: str = 'class="industries-hit"') -> list[str]:
        return read_line(f'<li><p {attrs}><span class="industries-hit-label" data-finder-skip>'
                         f'Industries hit:</span> <span class="no-glossary">{inner}</span></p></li>')[1]

    found = findings_for("Fintech")
    expect(any('"Fintech" is not an industry' in f for f in found), "an unknown industry is a finding")
    found = findings_for("Finance, Finance")
    expect(any("more than once" in f for f in found), "a repeated industry is a finding")
    expected_line = render_line(["Finance", "Retail"])
    found = findings_for("Retail, Finance")
    expect(any("should read" in f and expected_line in f for f in found),
           "an out-of-order line is a finding that prints the canonical line")
    found = findings_for("Finance · Retail")
    expect(any("should read" in f and expected_line in f for f in found),
           "a middle-dot separator is a finding that prints the canonical line")
    labels, found = read_line("<li>" + render_line(["Finance"]) + render_line(["Retail"]) + "</li>")
    expect(any("more than one" in f for f in found), "two lines in one card is a finding")
    labels, found = read_line('<li><p data-x="1" class="industries-hit"><span class="industries-hit-label" '
                              'data-finder-skip>Industries hit:</span> <span class="no-glossary">Finance</span>'
                              '</p></li>')
    expect(labels == ["Finance"] and any("should read" in f for f in found),
           "a line with an extra attribute is still read, and reported as not canonical")
    labels, found = read_line('<li><p class="industries-hit"><span class="industries-hit-label" '
                              'data-finder-skip>Industries hit:</span> <span class="no-glossary"></span></p></li>')
    expect(labels == [] and any("names no industry" in f for f in found), "an empty line is a finding")

    syn = synonym_map()
    expect(syn.get("bank") == "finance" and syn.get("hospital") == "healthcare",
           "synonyms map a folded word to its folded industry")
    expect(fold("Shai-Hulud Café") == "shai hulud cafe", "fold matches card-finder.js")

    # Planted vocabulary defects, each of which must be reported.
    def vocab_finds(vocab: dict[str, tuple[str, ...]], what: str) -> None:
        expect(bool(vocabulary_findings(vocab)), what)
    vocab_finds({"Real Estate": ()}, "a two-word label is a finding")
    vocab_finds({"Finance": ("retail",), "Retail": ()}, "a synonym equal to another label is a finding")
    vocab_finds({"Finance": ("money",), "Retail": ("money",)}, "a synonym shared by two industries is a finding")
    vocab_finds({"Retail": ("E-commerce",)}, "a synonym that folding changes is a finding")

    print(f"\nself-test: {len(failures)} failure(s)")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    ap.add_argument("--self-test", action="store_true", help="run the planted controls")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
