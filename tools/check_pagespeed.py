#!/usr/bin/env python3
"""Run Google PageSpeed Insights against csoh.org (mobile + desktop) and
append a row to seo-audits/SCORECARD.md.

Uses the public PageSpeed Insights v5 API. An API key is required —
anonymous requests are rejected. Get a free key in ~30 seconds:
https://developers.google.com/speed/docs/insights/v5/get-started

Pass the key via --api-key, or set the PSI_API_KEY environment variable.

Usage:
    export PSI_API_KEY=AIza…
    python3 tools/check_pagespeed.py

    # Different URL
    python3 tools/check_pagespeed.py --url https://csoh.org/glossary.html

    # Print results, don't touch the scorecard
    python3 tools/check_pagespeed.py --dry-run

    # Emit just the markdown row (useful for piping into a PR comment)
    python3 tools/check_pagespeed.py --quiet
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCORECARD = REPO_ROOT / "seo-audits" / "SCORECARD.md"
PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
DEFAULT_URL = "https://csoh.org/"
CATEGORIES = ["performance", "accessibility", "best-practices", "seo"]


def run_psi(url: str, strategy: str, api_key: str) -> dict:
    """Return the parsed PSI response for one strategy."""
    params = [("url", url), ("strategy", strategy), ("key", api_key)]
    for cat in CATEGORIES:
        params.append(("category", cat))
    full = f"{PSI_ENDPOINT}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(full, headers={"User-Agent": "csoh-pagespeed-check/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def extract_summary(payload: dict) -> dict:
    """Pull the four 0-100 category scores + core web vitals from a PSI payload."""
    lh = payload["lighthouseResult"]
    cats = lh["categories"]
    audits = lh["audits"]

    def score(cat: str) -> int:
        s = cats.get(cat, {}).get("score")
        return round(s * 100) if s is not None else 0

    def num(audit_id: str, unit: str = "s", places: int = 2) -> str | None:
        a = audits.get(audit_id)
        if not a or a.get("numericValue") is None:
            return None
        v = a["numericValue"]
        if unit == "s":
            return f"{v/1000:.{places}f}"
        if unit == "ms":
            return f"{int(v)}"
        return f"{v:.{places}f}"

    return {
        "perf": score("performance"),
        "a11y": score("accessibility"),
        "bp": score("best-practices"),
        "seo": score("seo"),
        "lcp": num("largest-contentful-paint", "s"),
        "cls": num("cumulative-layout-shift", "raw", 3),
        "tbt": num("total-blocking-time", "ms"),
        "fcp": num("first-contentful-paint", "s"),
        "si": num("speed-index", "s"),
    }


def fmt_cell(s: dict) -> str:
    """A scorecard cell: `Perf / A11y / BP / SEO`."""
    return f"{s['perf']} / {s['a11y']} / {s['bp']} / {s['seo']}"


def fmt_metrics(s: dict) -> str:
    """One-line CWV summary for the Notes column."""
    parts = []
    if s["lcp"]:
        parts.append(f"LCP {s['lcp']}s")
    if s["cls"]:
        parts.append(f"CLS {s['cls']}")
    if s["tbt"]:
        parts.append(f"TBT {s['tbt']}ms")
    if s["fcp"]:
        parts.append(f"FCP {s['fcp']}s")
    return " · ".join(parts)


def append_row(date: str, mobile: dict, desktop: dict, notes: str) -> None:
    """Insert a row into the PageSpeed table in SCORECARD.md."""
    text = SCORECARD.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find the PageSpeed table — its header row contains "Mobile | Desktop"
    psi_header_idx = None
    for i, line in enumerate(lines):
        if "| Mobile" in line and "| Desktop" in line:
            psi_header_idx = i
            break
    if psi_header_idx is None:
        raise SystemExit("Could not locate the PageSpeed table in SCORECARD.md")

    # The new row goes at the end of the table — find the first non-table
    # line after the header.
    insert_at = psi_header_idx + 2  # skip header + separator
    while insert_at < len(lines) and lines[insert_at].startswith("|"):
        insert_at += 1

    new_row = f"| {date} | {fmt_cell(mobile)} | {fmt_cell(desktop)} | {notes} |"
    lines.insert(insert_at, new_row)
    SCORECARD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=DEFAULT_URL,
                        help=f"URL to test (default: {DEFAULT_URL})")
    parser.add_argument("--api-key", default=os.environ.get("PSI_API_KEY"),
                        help="PSI API key (default: $PSI_API_KEY env var)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print results, don't modify SCORECARD.md")
    parser.add_argument("--quiet", action="store_true",
                        help="Emit just the markdown row, no commentary")
    args = parser.parse_args()

    if not args.api_key:
        print("ERROR: PSI API key required. Set $PSI_API_KEY or pass --api-key.",
              file=sys.stderr)
        print("Get a free key: https://developers.google.com/speed/docs/insights/v5/get-started",
              file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"⏱  Running PageSpeed Insights against {args.url} (mobile + desktop in parallel)…")

    # Fan out both strategies in parallel — each PSI run takes 20-40s.
    with ThreadPoolExecutor(max_workers=2) as ex:
        fut_mobile = ex.submit(run_psi, args.url, "mobile", args.api_key)
        fut_desktop = ex.submit(run_psi, args.url, "desktop", args.api_key)
        try:
            mobile_raw = fut_mobile.result()
            desktop_raw = fut_desktop.result()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:500]
            print(f"ERROR: PSI HTTP {e.code} — {body}", file=sys.stderr)
            return 1

    mobile = extract_summary(mobile_raw)
    desktop = extract_summary(desktop_raw)

    today = dt.date.today().isoformat()
    notes = f"Mobile: {fmt_metrics(mobile)}"

    row = f"| {today} | {fmt_cell(mobile)} | {fmt_cell(desktop)} | {notes} |"

    if args.quiet:
        print(row)
    else:
        print("\nResults — `Perf / A11y / Best Practices / SEO` (out of 100)\n")
        print(f"  Mobile  : {fmt_cell(mobile)}  ({fmt_metrics(mobile)})")
        print(f"  Desktop : {fmt_cell(desktop)}  ({fmt_metrics(desktop)})")
        print(f"\nScorecard row:\n  {row}")

    if not args.dry_run:
        append_row(today, mobile, desktop, notes)
        if not args.quiet:
            print(f"\n✓ Appended to {SCORECARD.relative_to(REPO_ROOT)}")
    elif not args.quiet:
        print("\n(--dry-run: scorecard not modified)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
