#!/usr/bin/env python3
"""
Stamp the concrete date of the next Friday session into the pages that claim
to know it.

Two consumers, and they have to agree:

  * The visible "Next live session" line on index.html and the "Next session"
    line in sessions.html's hero - every element carrying `data-next-session`.
    main.js overwrites these at runtime with the viewer's own timezone added,
    so what this tool writes is what a reader with JavaScript off sees, and
    what a crawler sees before it runs any script.

  * The `Event` JSON-LD on sessions.html, whose `startDate` and `endDate`
    Google requires (developers.google.com/search/docs/appearance/structured-
    data/event). `startDate` is a REQUIRED property; a recurring `eventSchedule`
    is not a substitute and appears nowhere in Google's documentation.

Google also asks that structured data describe content visible on the page,
which is the reason the visible line and the JSON-LD are stamped by one tool
in one pass rather than by two that can drift apart.

csoh.ics is the source of truth for the cadence and both ends of the hour, the
same claim main.js makes in its own comment, so this reads the calendar rather
than hardcoding "Friday 07:00-08:00" a third time.

Usage:
    python3 tools/sync_next_session.py              # stamp (default)
    python3 tools/sync_next_session.py --check      # report drift, exit 1
    python3 tools/sync_next_session.py --self-test  # prove the machinery works

--check is deliberately NOT wired into CI. The committed date goes stale every
Friday on its own, with no commit to blame, so a gate on it would fail weekly
for a reason nobody caused, and a gate that cries wolf gets muted. The freshness guarantee comes from running this as a
fixer in the deploy build instead, so whatever is published carries the date
that was next at publish time.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
ICS = REPO / "csoh.ics"

# Pages carrying a [data-next-session] element. sessions.html additionally
# carries the Event block; index.html does not, deliberately - one event, one
# URL, per Google's "each event MUST have a unique URL".
VISIBLE_PAGES = ("index.html", "sessions.html")
EVENT_PAGE = "sessions.html"

WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}

# The visible element's text. main.js formats the same instant with
# Intl.DateTimeFormat({weekday:'long', month:'long', day:'numeric'}) and then
# appends " at H:MM AM PT", so a no-JS reader and a JS reader see the same
# sentence rather than two spellings of it.
VISIBLE_RE = re.compile(
    r'(<(?P<tag>p|span)\b[^>]*\bdata-next-session\b[^>]*>)(?P<text>.*?)(</(?P=tag)>)',
    re.DOTALL,
)

EVENT_BLOCK_RE = re.compile(
    r'<script type="application/ld\+json">(?P<json>(?:(?!</script>).)*?"@type":\s*"Event".*?)</script>',
    re.DOTALL,
)


def read_series() -> tuple[str, str, str, str]:
    """(tzid, byday, 'HH:MM:SS' start, 'HH:MM:SS' end) from csoh.ics.

    Unfolds continuation lines first: RFC 5545 wraps long lines with a leading
    space, and a naive line read would hand back a truncated DTSTART.
    """
    raw = ICS.read_text(encoding="utf-8")
    unfolded = re.sub(r"\r?\n[ \t]", "", raw)

    # Scope to the VEVENT. The VTIMEZONE above it carries DTSTART lines of its
    # own (the DST switch rules), and they have no TZID - reading the file's
    # first DTSTART finds one of those, which is a wrong answer rather than an
    # error.
    vevent = re.search(r"BEGIN:VEVENT\r?\n(.*?)END:VEVENT", unfolded, re.DOTALL)
    if not vevent:
        raise SystemExit("csoh.ics: no VEVENT found")
    text = vevent.group(1)

    def prop(name: str) -> str:
        m = re.search(rf"^{name}(;[^:\n]*)?:(?P<v>.*)$", text, re.MULTILINE)
        if not m:
            raise SystemExit(f"csoh.ics: no {name} found")
        return m.group(0)

    dtstart, dtend = prop("DTSTART"), prop("DTEND")
    tz = re.search(r"TZID=([^:;]+)", dtstart)
    if not tz:
        raise SystemExit("csoh.ics: DTSTART carries no TZID")
    byday = re.search(r"RRULE:.*?BYDAY=([A-Z]{2})", text)
    if not byday:
        raise SystemExit("csoh.ics: no weekly BYDAY in RRULE")

    def hhmmss(line: str) -> str:
        m = re.search(r":(\d{8})T(\d{2})(\d{2})(\d{2})", line)
        if not m:
            raise SystemExit(f"csoh.ics: cannot read a time out of {line!r}")
        return f"{m.group(2)}:{m.group(3)}:{m.group(4)}"

    return tz.group(1), byday.group(1), hhmmss(dtstart), hhmmss(dtend)


def resolve(now: datetime) -> tuple[datetime, datetime]:
    """The session worth naming: the one under way, else the next to start.

    Same rule as main.js's resolve(). At 07:30 on a Friday the next *start* is
    six days out, and advertising next week while the room is open is the one
    moment this must not get wrong.
    """
    tzid, byday, start_hms, end_hms = read_series()
    tz = ZoneInfo(tzid)
    local = now.astimezone(tz)
    sh, sm, ss = (int(x) for x in start_hms.split(":"))
    eh, em, es = (int(x) for x in end_hms.split(":"))
    want = WEEKDAYS[byday]

    for delta in range(8):
        day = (local + timedelta(days=delta)).date()
        if day.weekday() != want:
            continue
        start = datetime(day.year, day.month, day.day, sh, sm, ss, tzinfo=tz)
        end = datetime(day.year, day.month, day.day, eh, em, es, tzinfo=tz)
        if end > local:
            return start, end
    raise SystemExit("no occurrence found in the next 8 days")


def visible_text(start: datetime) -> str:
    """'Friday, September 25 at 7:00 AM PT' - no leading zero on the day or
    the hour, matching what Intl gives main.js."""
    clock = start.strftime("%I:%M %p").lstrip("0")
    return (
        f"{start.strftime('%A')}, {start.strftime('%B')} {start.day} "
        f"at {clock} {start.tzname().replace('PDT', 'PT').replace('PST', 'PT')}"
    )


def stamp_text(html: str, start: datetime) -> tuple[str, int]:
    want = visible_text(start)
    hits = 0

    def sub(m: re.Match) -> str:
        nonlocal hits
        if m.group("text").strip() == want:
            return m.group(0)
        hits += 1
        return m.group(1) + want + m.group(4)

    return VISIBLE_RE.sub(sub, html), hits


def stamp_event(html: str, start: datetime, end: datetime) -> tuple[str, int]:
    """Rewrite startDate/endDate inside the Event block only.

    Targeted replacement rather than json.loads + json.dumps: re-serializing
    would reflow the whole block and bury a one-line date change in a
    hundred-line diff.
    """
    m = EVENT_BLOCK_RE.search(html)
    if not m:
        raise SystemExit(f"{EVENT_PAGE}: no Event JSON-LD block found")
    block, hits = m.group(0), 0
    for prop, value in (("startDate", start), ("endDate", end)):
        want = value.isoformat()
        pat = re.compile(rf'("{prop}":\s*")([^"]*)(")')
        if not pat.search(block):
            raise SystemExit(f"{EVENT_PAGE}: Event block has no {prop}")

        def sub(mm: re.Match) -> str:
            nonlocal hits
            if mm.group(2) == want:
                return mm.group(0)
            hits += 1
            return mm.group(1) + want + mm.group(3)

        block = pat.sub(sub, block)
    return html[: m.start()] + block + html[m.end():], hits


def run(check: bool, now: datetime, root: Path = REPO) -> int:
    start, end = resolve(now)
    stale = []
    for name in VISIBLE_PAGES:
        path = root / name
        html = path.read_text(encoding="utf-8")
        out, n = stamp_text(html, start)
        if name == EVENT_PAGE:
            out, m = stamp_event(out, start, end)
            n += m
        if n:
            stale.append(f"{name} ({n} value{'s' if n != 1 else ''})")
            if not check:
                path.write_text(out, encoding="utf-8")
    verb = "stale" if check else "updated"
    print(f"next session: {start.isoformat()} to {end.isoformat()}")
    print(f"  {verb}: {', '.join(stale) if stale else 'nothing - already current'}")
    return 1 if (check and stale) else 0


def self_test() -> int:
    """Prove each detector fires, and that a second run is a no-op.

    An idempotency bug does not exist on the first run: the tool that writes a
    file and the tool that re-reads its own output are the same code taking
    different paths through it, and only one of those runs the first time.
    """
    tz = ZoneInfo("America/Los_Angeles")
    cases = [
        # (probe instant, expected start) - Wednesday, Friday before the hour,
        # mid-session, just after the hour, and either side of both DST edges.
        (datetime(2026, 9, 23, 12, 0, tzinfo=tz), "2026-09-25T07:00:00-07:00"),
        (datetime(2026, 9, 25, 6, 59, tzinfo=tz), "2026-09-25T07:00:00-07:00"),
        (datetime(2026, 9, 25, 7, 30, tzinfo=tz), "2026-09-25T07:00:00-07:00"),
        (datetime(2026, 9, 25, 8, 0, tzinfo=tz), "2026-10-02T07:00:00-07:00"),
        (datetime(2026, 11, 5, 9, 0, tzinfo=tz), "2026-11-06T07:00:00-08:00"),
        (datetime(2026, 3, 5, 9, 0, tzinfo=tz), "2026-03-06T07:00:00-08:00"),
        (datetime(2026, 3, 12, 9, 0, tzinfo=tz), "2026-03-13T07:00:00-07:00"),
    ]
    failed = 0
    for probe, want in cases:
        got = resolve(probe)[0].isoformat()
        ok = got == want
        failed += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {probe.isoformat()} -> {got}")

    now = datetime(2026, 9, 23, 12, 0, tzinfo=tz)
    start, end = resolve(now)

    # Stamp first, so each plant below is planted into a known-current file;
    # otherwise an unstamped page reports "plant did nothing".
    run(check=False, now=now)

    # Plant a stale value in each target and confirm every detector names it.
    # The plant asserts it changed something: a no-op plant would "pass" by
    # finding nothing to replace, which is a control that can only succeed.
    for name, old, new in (
        ("index.html", visible_text(start), "Friday at 7:00 AM PT"),
        (EVENT_PAGE, visible_text(start), "Friday at 7:00 AM PT"),
        (EVENT_PAGE, f'"startDate": "{start.isoformat()}"', '"startDate": "2020-01-03T07:00:00-08:00"'),
        (EVENT_PAGE, f'"endDate": "{end.isoformat()}"', '"endDate": "2020-01-03T08:00:00-08:00"'),
    ):
        path = REPO / name
        original = path.read_text(encoding="utf-8")
        planted = original.replace(old, new, 1)
        if planted == original:
            print(f"  FAIL plant did nothing in {name}: {old!r} not on disk")
            failed += 1
            continue
        path.write_text(planted, encoding="utf-8")
        try:
            detected = run(check=True, now=now) == 1
        finally:
            path.write_text(original, encoding="utf-8")
        print(f"  {'ok  ' if detected else 'FAIL'} planted {new[:28]!r} in {name} -> "
              f"{'detected' if detected else 'MISSED'}")
        failed += not detected

    # Idempotency: stamp, then stamp again and demand the second pass be a
    # no-op rather than trusting that it reads its own output correctly.
    run(check=False, now=now)
    if run(check=True, now=now) != 0:
        print("  FAIL second pass found drift - the tool does not re-read its own output")
        failed += 1
    else:
        print("  ok   second pass is a no-op")

    print("self-test:", "FAILED" if failed else "all detectors fired")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="report drift without writing; exit 1 if stale")
    ap.add_argument("--self-test", action="store_true", help="plant known defects and confirm each is caught")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return run(check=args.check, now=datetime.now(ZoneInfo("America/Los_Angeles")))


if __name__ == "__main__":
    sys.exit(main())
