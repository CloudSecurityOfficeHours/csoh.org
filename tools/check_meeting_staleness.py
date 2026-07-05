#!/usr/bin/env python3
"""Flag a stalled meeting-recap cadence.

The weekly Friday recap is the site's only guaranteed-weekly fresh content
and its strongest freshness signal for search crawlers and AI answer engines.
faq.html promises uninterrupted weekly sessions and the homepage advertises
"updated weekly", so a gap between the newest recap and today quietly breaks
a published promise.

This checker finds the newest meetings/YYYY-MM-DD.html page, compares its
date against today, and - if the gap exceeds --max-age-days (default 14, i.e.
two missed Fridays) - writes a short markdown report meant to be pasted into
a tracking issue. It never edits the site.

It exits 0 whether or not the archive is stale (this is a report, not a gate);
it exits non-zero only on an internal error (e.g. no recaps found).

Usage:
    python3 tools/check_meeting_staleness.py
    python3 tools/check_meeting_staleness.py --max-age-days 21
    python3 tools/check_meeting_staleness.py --output staleness.md
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MEETINGS_DIR = REPO / "meetings"
DATE_FILE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.html$")


def newest_recap() -> tuple[dt.date, Path] | None:
    dated: list[tuple[dt.date, Path]] = []
    for p in MEETINGS_DIR.glob("*.html"):
        m = DATE_FILE_RE.match(p.name)
        if not m:
            continue
        try:
            dated.append((dt.date(int(m[1]), int(m[2]), int(m[3])), p))
        except ValueError:
            continue
    if not dated:
        return None
    return max(dated, key=lambda t: t[0])


def build_report(newest: dt.date, path: Path, today: dt.date, max_age: int) -> str:
    age = (today - newest).days
    stale = age > max_age
    status = "STALE" if stale else "OK"
    lines = [
        "# Meeting recap freshness",
        "",
        f"- **Newest recap:** [{path.name}](../{path.relative_to(REPO)}) ({newest.isoformat()})",
        f"- **As of:** {today.isoformat()}",
        f"- **Age:** {age} days (threshold {max_age})",
        f"- **Status:** {status}",
        "",
    ]
    if stale:
        missed = age // 7
        lines += [
            f"The recap archive has not been updated in {age} days "
            f"(~{missed} missed Friday session{'s' if missed != 1 else ''}). "
            "This contradicts the site's 'every Friday' / 'updated weekly' claims.",
            "",
            "**To clear the backlog:** run `tools/add_meeting.py` for each missing "
            "session, then refresh the chat-resources export and the presentations "
            "page. See DEVELOPMENT.md for the recap pipeline.",
        ]
    else:
        lines.append("Cadence is healthy - no action needed.")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-age-days", type=int, default=14)
    ap.add_argument("--output", type=str, default=None,
                    help="Write the markdown report to this file (else stdout).")
    ap.add_argument("--today", type=str, default=None,
                    help="Override today's date (YYYY-MM-DD) for testing.")
    args = ap.parse_args()

    found = newest_recap()
    if not found:
        print("error: no dated recaps found in meetings/", file=sys.stderr)
        return 1
    newest, path = found
    today = dt.date.fromisoformat(args.today) if args.today else dt.date.today()

    report = build_report(newest, path, today, args.max_age_days)
    if args.output:
        Path(args.output).write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)

    age = (today - newest).days
    print(
        f"newest recap {newest.isoformat()} is {age} days old "
        f"({'STALE' if age > args.max_age_days else 'OK'})",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
