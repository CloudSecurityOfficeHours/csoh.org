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

There is a second, subtler kind of rot. A card whose `data-next-date` is "TBA"
or "ongoing" is never compared against today - correctly, since there is no
date to compare - but its *visible text* can still name one. The BSides card
sat at data-next-date="ongoing" advertising "BSides Las Vegas is August 3-5,
2026" four days after that had passed, and this checker reported OK the whole
time, because it only ever looked at the attribute. So the visible text of
every non-dated card is also scanned for dates that have definitively passed,
and a hit counts as stale. Only unambiguously past dates are flagged: a bare
year counts as stale only once the whole year is over, and a month with no year
attached ("historically October") is never flagged at all.

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


# --- Dates written into the visible text of a non-dated card -----------------
# Used only for "ongoing"/"TBA" cards, whose data-next-date cannot be compared
# against today. Three shapes are recognised, from most to least specific, and
# each match consumes its span so a single date is never counted twice (the year
# inside "August 3-5, 2026" must not also register as a bare year).
MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}
# Longest-first so "sept" wins over "sep" and "june" over "jun".
_MONTH_ALT = "|".join(sorted(MONTHS, key=len, reverse=True))

# "August 3-5, 2026" / "August 3, 2026" / "Aug 3 2026". The trailing year is
# required, which is what keeps this from matching the bare month names that
# appear in prose. The day range accepts U+2013 EN DASH (written as a regex
# escape, so this file stays pure ASCII) as well as the house-style ASCII
# hyphen, since a date pasted from an organizer's site often carries one.
MONTH_DAY_YEAR_RE = re.compile(
    rf"\b({_MONTH_ALT})\s+(\d{{1,2}})(?:\s*[-\u2013]\s*(\d{{1,2}}))?,?\s+(\d{{4}})\b",
    re.IGNORECASE,
)
# "October 2026" - a month with a year but no day.
MONTH_YEAR_RE = re.compile(rf"\b({_MONTH_ALT})\s+(\d{{4}})\b", re.IGNORECASE)
# A bare year, e.g. "2026 edition TBA".
YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _end_of_month(year: int, month: int) -> dt.date:
    """Last calendar day of the given month."""
    if month == 12:
        return dt.date(year, 12, 31)
    return dt.date(year, month + 1, 1) - dt.timedelta(days=1)


def find_past_dates(label: str, today: dt.date) -> list[str]:
    """Describe every date in `label` that has definitively passed.

    Deliberately conservative - each shape resolves to the LAST moment it could
    still be current, and is reported only if even that is behind us:

    - "August 3-5, 2026"  -> the 5th (end of the range), not the 3rd
    - "October 2026"      -> 2026-10-31 (end of the month)
    - "2026"              -> 2026-12-31 (end of the year)

    So a card reading "2027 dates TBA" is silent all through 2027, and one
    reading "historically October" is never flagged, having named no year.
    """
    findings: list[str] = []
    consumed = bytearray(len(label))

    def free(m: re.Match) -> bool:
        return not any(consumed[m.start():m.end()])

    def claim(m: re.Match) -> None:
        consumed[m.start():m.end()] = b"\x01" * (m.end() - m.start())

    for m in MONTH_DAY_YEAR_RE.finditer(label):
        if not free(m):
            continue
        # group(3) is the range's end day when present ("3-5" -> 5).
        day = int(m.group(3) or m.group(2))
        try:
            when = dt.date(int(m.group(4)), MONTHS[m.group(1).lower()], day)
        except ValueError:
            continue        # e.g. "February 30, 2026" - malformed, not stale
        claim(m)
        if when < today:
            findings.append(f'"{m.group(0)}" ended {when.isoformat()}')

    for m in MONTH_YEAR_RE.finditer(label):
        if not free(m):
            continue
        when = _end_of_month(int(m.group(2)), MONTHS[m.group(1).lower()])
        claim(m)
        if when < today:
            findings.append(f'"{m.group(0)}" ended {when.isoformat()}')

    for m in YEAR_RE.finditer(label):
        if not free(m):
            continue
        year = int(m.group(1))
        claim(m)
        if year < today.year:
            findings.append(f'"{m.group(0)}" ended {year}-12-31')

    return findings


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

    Cards in the last two groups have no comparable date, so each also gets a
    `past_text` list: dates their visible text names that have already passed.
    A non-empty list is stale in its own right - see the module docstring.
    """
    stale, upcoming, tba, ongoing = [], [], [], []
    for card in cards:
        raw = card["raw"]
        if raw.lower() == "ongoing":
            card["past_text"] = find_past_dates(card["label"], today)
            ongoing.append(card)
            continue
        if raw.upper() == "TBA" or not raw:
            card["past_text"] = find_past_dates(card["label"], today)
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
    # Non-dated cards whose visible text names a date that has already passed.
    # These count toward STALE: the sticky-issue action greps the report for
    # "Status:** STALE" to decide whether to keep the tracking issue open, so a
    # finding that did not flip this string would print and then be auto-closed.
    rotted = [c for c in tba + ongoing if c.get("past_text")]
    status = "STALE" if (stale or rotted) else "OK"
    lines = [
        "# Conference dates freshness",
        "",
        f"- **As of:** {today.isoformat()}",
        f"- **Cards checked:** {len(cards)}",
        f"- **Stale (past 'Next' date):** {len(stale)}",
        f"- **Stale text on non-dated cards:** {len(rotted)}",
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
    if rotted:
        lines += [
            "## Stale text on non-dated cards",
            "",
            "These cards are `ongoing` or `TBA`, so their `data-next-date` is never "
            "compared against today - but the text a reader actually sees names a "
            "date that has already passed. Reword the text so it cannot rot (state "
            "the recurring pattern rather than one edition's dates), or give the "
            "card a real `data-next-date` if the next edition is now known.",
            "",
        ]
        for card in rotted:
            lines.append(
                f"- **{card['title']}** (`{card['raw']}`) - "
                f"{'; '.join(card['past_text'])} - shows \"{card['label']}\""
            )
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
    if not stale and not rotted:
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

    stale, _, tba, ongoing = classify(cards, today)
    rotted = [c for c in tba + ongoing if c.get("past_text")]
    print(
        f"checked {len(cards)} conference cards; "
        f"{len(stale)} stale, {len(rotted)} with stale text on a non-dated card "
        f"({'STALE' if stale or rotted else 'OK'})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
