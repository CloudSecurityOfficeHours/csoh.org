#!/usr/bin/env python3
"""Flag conference "Next:" dates on conferences.html that have gone stale.

conferences.html lists ~26 security/hacker conferences. Each card carries a
prominent "Next: <dates>" line whose machine-readable start date lives in a
`data-next-date="YYYY-MM-DD"` attribute (or the literal "TBA" when the next
edition has not been officially announced yet).

Because the site is static and hand-maintained, those concrete dates rot: the
moment an edition's start date slips into the past, the card advertises a
"Next" date that has already happened, which reads as neglect. This checker is
the self-policing half of that trade-off. It scans conferences.html, pairs each
`data-next-date` with its card's <h3> title, and - if any confirmed date is in
the past - writes a short markdown report meant to be pasted into a tracking
issue. It never edits the site.

TBA entries are not stale (nothing to rot), but they are listed separately as a
gentle reminder to fill them in once the organizer announces dates.

It exits 0 whether or not anything is stale (this is a report, not a gate); it
exits non-zero only on an internal error (e.g. conferences.html not found or no
date lines present, which would mean the markup changed out from under it).

Usage:
    python3 tools/check_conference_staleness.py
    python3 tools/check_conference_staleness.py --output staleness.md
    python3 tools/check_conference_staleness.py --today 2026-12-31
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CONFERENCES = REPO / "conferences.html"

# The date line looks like:
#   <p class="conf-next" data-next-date="2026-08-06"><strong>Next:</strong> ...</p>
# We capture the attribute value and the visible label text so the report can
# quote exactly what a reader sees on the card.
NEXT_RE = re.compile(
    r'<p class="conf-next" data-next-date="([^"]*)">(.*?)</p>',
    re.DOTALL,
)
# Card titles. Used to name each stale entry by finding the nearest <h3> that
# precedes the date line in document order.
H3_RE = re.compile(r"<h3>(.*?)</h3>", re.DOTALL)
TAG_RE = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    """Strip tags + unescape entities, collapsing whitespace to single spaces."""
    return html.unescape(re.sub(r"\s+", " ", TAG_RE.sub("", fragment))).strip()


def parse_cards(source: str) -> list[dict]:
    """Return one dict per conference card: title, raw date attr, visible label."""
    h3s = [(m.start(), _text(m.group(1))) for m in H3_RE.finditer(source)]
    cards: list[dict] = []
    for m in NEXT_RE.finditer(source):
        pos = m.start()
        # The card's title is the last <h3> that appears before this date line.
        title = next(
            (t for start, t in reversed(h3s) if start < pos),
            "(unknown conference)",
        )
        cards.append(
            {
                "title": title,
                "raw": m.group(1).strip(),
                "label": _text(m.group(2)),
            }
        )
    return cards


def classify(
    cards: list[dict], today: dt.date
) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    """Split cards into (stale, upcoming, tba, ongoing).

    - stale:    a concrete start date that is now in the past
    - upcoming: a concrete start date still ahead of today
    - tba:      awaiting the organizer's announcement (data-next-date="TBA")
    - ongoing:  perpetual / year-round events (data-next-date="ongoing", e.g.
                the BSides network) - never stale, and not a reminder to chase.
    """
    stale, upcoming, tba, ongoing = [], [], [], []
    for card in cards:
        raw = card["raw"]
        if raw.lower() == "ongoing":
            ongoing.append(card)
            continue
        if raw.upper() == "TBA" or not raw:
            tba.append(card)
            continue
        try:
            start = dt.date.fromisoformat(raw)
        except ValueError:
            # A malformed data-next-date is itself worth flagging as stale so a
            # human notices and fixes the markup.
            card["error"] = f"unparseable date {raw!r}"
            stale.append(card)
            continue
        card["start"] = start
        (stale if start < today else upcoming).append(card)
    return stale, upcoming, tba, ongoing


def build_report(cards: list[dict], today: dt.date) -> str:
    stale, upcoming, tba, ongoing = classify(cards, today)
    status = "STALE" if stale else "OK"
    lines = [
        "# Conference dates freshness",
        "",
        f"- **As of:** {today.isoformat()}",
        f"- **Cards checked:** {len(cards)}",
        f"- **Stale (past 'Next' date):** {len(stale)}",
        f"- **Upcoming (dated):** {len(upcoming)}",
        f"- **Awaiting announcement (TBA):** {len(tba)}",
        f"- **Year-round / ongoing:** {len(ongoing)}",
        f"- **Status:** {status}",
        "",
    ]
    if stale:
        lines += [
            "## Stale - update these on conferences.html",
            "",
            "These cards show a `Next:` date that has already started or passed. "
            "Look up the following edition, then update both the visible text and "
            "the `data-next-date` attribute.",
            "",
        ]
        for card in sorted(stale, key=lambda c: c.get("start") or today):
            detail = card.get("error") or f"was {card['start'].isoformat()}"
            lines.append(f"- **{card['title']}** ({detail}) - shows \"{card['label']}\"")
        lines.append("")
    if tba:
        lines += [
            "## Awaiting announcement",
            "",
            "Not stale, but worth a periodic look - fill in a concrete date once "
            "the organizer announces the next edition.",
            "",
        ]
        for card in tba:
            lines.append(f"- {card['title']}")
        lines.append("")
    if not stale:
        lines.append("All dated conference cards are still upcoming - no action needed.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=str, default=None,
                    help="Write the markdown report to this file (else stdout).")
    ap.add_argument("--today", type=str, default=None,
                    help="Override today's date (YYYY-MM-DD) for testing.")
    args = ap.parse_args()

    if not CONFERENCES.exists():
        print(f"error: {CONFERENCES} not found", file=sys.stderr)
        return 1

    source = CONFERENCES.read_text(encoding="utf-8")
    cards = parse_cards(source)
    if not cards:
        print("error: no conf-next date lines found in conferences.html "
              "(did the card markup change?)", file=sys.stderr)
        return 1

    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()
    report = build_report(cards, today)

    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)

    stale, _, _, _ = classify(cards, today)
    print(
        f"checked {len(cards)} conference cards; "
        f"{len(stale)} stale ({'STALE' if stale else 'OK'})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
