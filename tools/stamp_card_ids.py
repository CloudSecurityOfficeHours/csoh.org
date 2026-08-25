#!/usr/bin/env python3
"""
Stamp a stable `id` onto every resource card on the card-list pages, so a
search result can deep link to the card itself.

Why this exists
---------------
build_search_index.py emits one search doc per card, but a card had no id of
its own, so the doc's URL fell back to the card's *category* anchor. That is
correct and nearly useless: /resources.html#security-tools holds 83 cards, and
the "Open Policy Agent (OPA)" result landed the reader 6,396px above the OPA
card with nothing on screen to suggest the page held it at all. It reads as a
broken link rather than a coarse one. 647 of the 666 card results shared an
anchor with more than five other cards.

The id is derived from the card's <h3> text by card_slug() in
build_search_index.py, which is also what the indexer reads back. One
definition, so the id in the HTML and the id in the index cannot disagree - a
card that is retitled re-slugs in both places on the next run.

The indexer reads the id out of the HTML rather than recomputing it. So a card
added by hand and never stamped keeps the old category-anchor URL instead of
getting a link to an anchor that is not there: this tool going unrun degrades
the result, it does not break it. `--check` is the gate that says so out loud.

Usage:
    python3 tools/stamp_card_ids.py            # stamp in place
    python3 tools/stamp_card_ids.py --check    # exit 1 if anything is unstamped

Idempotent: a second run changes nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_search_index import (  # noqa: E402
    CARD_OPEN_TAG_RE,
    CARD_PAGES,
    ID_ATTR_RE,
    card_slots,
    body,
)

REPO = Path(__file__).resolve().parent.parent


def stamp(raw: str) -> tuple[str, int, int]:
    """Return (new_html, stamped, already_correct).

    Cards are rewritten back-to-front so each edit cannot move the offsets of
    the ones still to be processed.
    """
    main = body(raw)
    if main not in raw:
        raise SystemExit("main content not found verbatim in page")
    base = raw.index(main)

    edits: list[tuple[int, int, str]] = []
    stamped = correct = 0
    for m, wanted, current in card_slots(main):
        if not wanted:
            continue
        if current == wanted:
            correct += 1
            continue
        open_tag = CARD_OPEN_TAG_RE.match(main, m.start())
        if not open_tag:
            continue
        tag = open_tag.group(0)
        id_m = ID_ATTR_RE.search(tag)
        if id_m:
            new_tag = tag[: id_m.start()] + f'id="{wanted}"' + tag[id_m.end() :]
        else:
            # First attribute, before href: CARD_RE wants href then class,
            # and `<a [^>]*href=` still matches with an id in front.
            new_tag = f'<a id="{wanted}"' + tag[2:]
        edits.append((base + open_tag.start(), base + open_tag.end(), new_tag))
        stamped += 1

    out = raw
    for start, end, new_tag in reversed(edits):
        out = out[:start] + new_tag + out[end:]
    return out, stamped, correct


def main() -> int:
    check = "--check" in sys.argv
    total_stamped = total_correct = 0
    failures: list[str] = []

    for name in sorted(CARD_PAGES):
        path = REPO / name
        if not path.exists():
            failures.append(f"{name}: missing")
            continue
        raw = path.read_text(encoding="utf-8")
        new, stamped, correct = stamp(raw)
        total_stamped += stamped
        total_correct += correct
        if stamped:
            if check:
                failures.append(f"{name}: {stamped} card(s) without a current id")
            else:
                path.write_text(new, encoding="utf-8")
        print(f"{name:<24} {correct:>4} stamped, {stamped:>4} {'need' if check else 'updated'}")

    if check and failures:
        print("\nFAIL: run `python3 tools/stamp_card_ids.py`, then rebuild the")
        print("search index so the result links point at the new anchors:")
        for f in failures:
            print(f"  - {f}")
        return 1

    verb = "would update" if check else "updated"
    print(f"\n{total_correct} card ids current, {total_stamped} {verb}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
