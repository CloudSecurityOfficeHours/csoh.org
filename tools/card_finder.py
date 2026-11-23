"""
Markup for a card finder: one box holding a search field and an index of a
page's cards, grouped by year, each entry linking its card's id.
card-finder.js reveals the field (it ships hidden) and filters the index and
the cards together, so a reader without scripts gets a working index and no
dead search box.

Used by tools/sync_breach_deck_index.py (breach-kill-chain-decks.html) and
tools/sync_breach_timeline_index.py (breach-timeline.html). The script needs
no per-page code; it reads everything from the markup rendered here:

    href="#<card id>"     each index link; the cards are found through them
    data-finder-text      selector for the parts of a card that are searched
    data-finder-skip      on anything inside a card that must not be searched
    data-finder-noun(s)   words for the status line ("Showing 3 of 40 decks.")
    data-finder-query     on a filter button: what it puts in the search field
    data-finder-synonyms  "word=term" pairs: typing the word also finds the term

Filter buttons sit inside the search bar, so like the field they stay hidden
for a reader without scripts, who could not use them.

Every visible word in the box sits in a link or a `no-glossary` span, so
tools/crosslink_pages.py never links a glossary term inside it; each tool's
--self-test runs the real cross-linker over its region to prove it.

Standard library only.
"""

from __future__ import annotations

import html as htmllib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class Entry:
    target: str  # id of the card the entry links
    title: str   # plain text, unescaped
    year: str    # four digits, or "" when the card gives none


def _text(s: str) -> str:
    return htmllib.escape(s, quote=False)


def _attr(s: str) -> str:
    return htmllib.escape(s, quote=True)


def group_by_year(entries: list[Entry], min_group: int = 3) -> list[tuple[str, list[Entry]]]:
    """(label, entries) pairs, newest year first, entries in page order.

    Walking down from the newest year, the first year with fewer than
    `min_group` entries opens one closing group that also takes every older
    year ("2020 and earlier"), so a tail of one-incident years does not become
    a stack of one-line groups. A closing group of one year keeps that year as
    its label. Cards with no year come last, as "Undated"."""
    by_year: dict[str, list[Entry]] = {}
    for e in entries:
        by_year.setdefault(e.year, []).append(e)
    years = sorted((y for y in by_year if y), reverse=True)
    groups: list[tuple[str, list[Entry]]] = []
    for i, y in enumerate(years):
        if len(by_year[y]) < min_group:
            tail = years[i:]
            members = [e for e in entries if e.year in tail]
            groups.append((y if len(tail) == 1 else f"{y} and earlier", members))
            break
        groups.append((y, by_year[y]))
    if "" in by_year:
        groups.append(("Undated", by_year[""]))
    return groups


def _slug(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")


def render_finder(
    entries: list[Entry],
    *,
    input_id: str,
    id_prefix: str,
    label: str,
    placeholder: str,
    index_label: str,
    noun: str,
    nouns: str,
    text_selector: str,
    min_group: int = 3,
    filters: Sequence[str] = (),
    filter_label: str = "",
    synonyms: Mapping[str, str] | None = None,
) -> list[str]:
    """The finder's lines, before indentation.

    `filters` become buttons under the field, in the order given, each
    putting its own text in the field; `filter_label` names the row.
    `synonyms` maps a folded word a reader might type to the folded term it
    should also find.

    The index is a <div> with the navigation role rather than a <nav>:
    style.css styles bare `nav ul` and `nav a` for the site header, and those
    rules would lay the index out as a header menu. Being a <div>, it is not a
    cross-linker skip zone either, which is why the labels carry
    `no-glossary`."""
    syn_attr = ""
    if synonyms:
        pairs = " ".join(f"{w}={t}" for w, t in sorted(synonyms.items()))
        syn_attr = f' data-finder-synonyms="{_attr(pairs)}"'
    lines = [
        f'<div class="card-finder" data-finder-text="{_attr(text_selector)}"'
        f' data-finder-noun="{_attr(noun)}" data-finder-nouns="{_attr(nouns)}"{syn_attr}>',
        '    <div class="card-finder-filter is-hidden" role="search">',
        f'        <label for="{input_id}" class="visually-hidden"><span class="no-glossary">{_text(label)}</span></label>',
        '        <div class="search-wrapper">',
        f'            <input type="text" class="card-finder-input" id="{input_id}" placeholder="{_attr(placeholder)}"'
        ' autocomplete="off" spellcheck="false">',
        "        </div>",
    ]
    if filters:
        label_id = f"{id_prefix}-filter-label"
        lines += [
            f'        <div class="card-finder-buttons" role="group" aria-labelledby="{label_id}">',
            f'            <span class="card-finder-buttons-label" id="{label_id}"><span class="no-glossary">'
            f"{_text(filter_label)}</span></span>",
            *[f'            <button type="button" class="filter-btn card-finder-btn" data-finder-query="{_attr(f)}"'
              f' aria-pressed="false"><span class="no-glossary">{_text(f)}</span></button>' for f in filters],
            "        </div>",
        ]
    lines += [
        '        <p class="card-finder-status"><span class="card-finder-count" role="status"></span>'
        ' <button class="clear-search-btn card-finder-clear is-hidden" type="button">Clear the search</button></p>',
        "    </div>",
        f'    <div class="card-finder-index" role="navigation" aria-label="{_attr(index_label)}">',
    ]
    for group_label, members in group_by_year(entries, min_group):
        gid = f"{id_prefix}-{_slug(group_label)}"
        lines += [
            '        <div class="card-finder-group">',
            f'            <p class="card-finder-year" id="{gid}"><span class="no-glossary">{_text(group_label)}</span></p>',
            f'            <ul class="card-finder-list" aria-labelledby="{gid}">',
            *[f'                <li><a href="#{_attr(e.target)}">{_text(e.title)}</a></li>' for e in members],
            "            </ul>",
            "        </div>",
        ]
    lines += ["    </div>", "</div>"]
    return lines


def splice(page_html: str, start: str, end: str, region: list[str], page: str) -> str:
    """page_html with everything between the two marker lines replaced by
    region, indented to match the start marker. Raises ValueError on bad
    markers."""
    starts = page_html.count(start)
    ends = page_html.count(end)
    if starts != 1 or ends != 1:
        raise ValueError(f"{page} needs exactly one {start} and one {end} (found {starts} and {ends})")
    m = re.search(r"^([ \t]*)" + re.escape(start) + r"[ \t]*\n(.*?)^[ \t]*" + re.escape(end), page_html, re.S | re.M)
    if not m:
        raise ValueError(f"{page}: {start} and {end} must each sit on a line of their own, start first")
    indent = m.group(1)
    body = "".join(f"{indent}{ln}\n" if ln else "\n" for ln in region)
    return page_html[: m.start(2)] + body + page_html[m.start(2) + len(m.group(2)):]
