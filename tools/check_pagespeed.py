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

    def failing_audits(cat: str) -> list[str]:
        """Return the audit IDs in `cat` that scored < 1.0 (i.e. weren't
        perfect). For categories scored at 100, returns []. Useful for
        pinpointing exactly which Lighthouse audit dragged the category
        score down."""
        cat_data = cats.get(cat, {})
        refs = cat_data.get("auditRefs", [])
        out = []
        for ref in refs:
            aid = ref.get("id")
            audit = audits.get(aid, {})
            s = audit.get("score")
            # Score is None for informational audits — skip those.
            # 1.0 = perfect; anything less is a fail or near-fail.
            if s is not None and s < 1.0:
                out.append(aid)
        return out

    def audit_details(audit_id: str, max_items: int = 8) -> list[str]:
        """Return short human-readable strings for each failing node/item
        in `audit_id`'s details.items[] list. Lighthouse populates this
        for node-based audits like color-contrast, image-alt, link-name."""
        audit = audits.get(audit_id, {})
        items = (audit.get("details") or {}).get("items") or []
        out = []
        for item in items[:max_items]:
            node = item.get("node") or {}
            selector = node.get("selector") or node.get("path") or "?"
            snippet = (node.get("snippet") or "").strip().replace("\n", " ")
            if len(snippet) > 80:
                snippet = snippet[:77] + "…"
            out.append(f"{selector}  {snippet}".strip())
        return out

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
        "a11y_fails": failing_audits("accessibility"),
        "bp_fails": failing_audits("best-practices"),
        "seo_fails": failing_audits("seo"),
    }


def extract_crux(payload: dict) -> dict | None:
    """Pull CrUX field data (real-user p75) from a PSI payload.

    PSI exposes CrUX in two slots: `loadingExperience` (this URL) and
    `originLoadingExperience` (whole origin). Prefer URL-specific data
    when present and not flagged `origin_fallback`; otherwise fall back
    to origin. Returns None when neither has data — Google requires a
    minimum traffic threshold before CrUX exposes anything.

    Metric units in CrUX:
      LARGEST_CONTENTFUL_PAINT_MS, FIRST_CONTENTFUL_PAINT_MS — ms p75
      INTERACTION_TO_NEXT_PAINT                              — ms p75
      CUMULATIVE_LAYOUT_SHIFT_SCORE                          — score × 100
        (so a `percentile` of 5 means a real CLS of 0.05)
    """
    page = payload.get("loadingExperience") or {}
    origin = payload.get("originLoadingExperience") or {}
    use_page = bool(page.get("metrics")) and not page.get("origin_fallback")
    src = page if use_page else origin
    metrics = src.get("metrics") or {}
    if not metrics:
        return None

    def fmt(key: str, unit: str) -> str | None:
        m = metrics.get(key) or {}
        v = m.get("percentile")
        if v is None:
            return None
        cat = m.get("category", "NONE")
        if unit == "s":
            return f"{v/1000:.2f}s ({cat})"
        if unit == "ms":
            return f"{int(v)}ms ({cat})"
        # CLS percentile is the actual CLS score × 100.
        return f"{v/100:.3f} ({cat})"

    return {
        "scope": "page" if use_page else "origin",
        "lcp": fmt("LARGEST_CONTENTFUL_PAINT_MS", "s"),
        "inp": fmt("INTERACTION_TO_NEXT_PAINT", "ms"),
        "cls": fmt("CUMULATIVE_LAYOUT_SHIFT_SCORE", "cls"),
        "fcp": fmt("FIRST_CONTENTFUL_PAINT_MS", "s"),
        "overall": src.get("overall_category"),
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


def fmt_crux(c: dict) -> str:
    """One-line CrUX field summary."""
    parts = []
    for key in ("lcp", "inp", "cls"):
        v = c.get(key)
        if v:
            parts.append(f"{key.upper()} {v}")
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
    mobile_crux = extract_crux(mobile_raw)
    desktop_crux = extract_crux(desktop_raw)

    today = dt.date.today().isoformat()
    notes_parts = [f"Mobile: {fmt_metrics(mobile)}"]
    # Real-user CrUX data sits alongside the lab metrics. Surfaced separately
    # so it's clear which numbers are field (CrUX) vs lab (Lighthouse).
    # CrUX is absent for low-traffic pages — silently skipped when missing.
    if mobile_crux:
        crux_line = fmt_crux(mobile_crux)
        if crux_line:
            notes_parts.append(f"CrUX-M ({mobile_crux['scope']}): {crux_line}")
    if desktop_crux:
        crux_line = fmt_crux(desktop_crux)
        if crux_line:
            notes_parts.append(f"CrUX-D ({desktop_crux['scope']}): {crux_line}")
    # Surface failing-audit IDs in the SCORECARD notes column when any of the
    # 0-100 categories isn't 100. Lets you see at a glance which audit dragged
    # the score down without re-running PSI.
    for label, summary in [("M", mobile), ("D", desktop)]:
        if summary["a11y"] < 100 and summary.get("a11y_fails"):
            notes_parts.append(f"{label}-a11y: {','.join(summary['a11y_fails'])}")
        if summary["bp"] < 100 and summary.get("bp_fails"):
            notes_parts.append(f"{label}-bp: {','.join(summary['bp_fails'])}")
        if summary["seo"] < 100 and summary.get("seo_fails"):
            notes_parts.append(f"{label}-seo: {','.join(summary['seo_fails'])}")
    notes = " · ".join(notes_parts)

    row = f"| {today} | {fmt_cell(mobile)} | {fmt_cell(desktop)} | {notes} |"

    if args.quiet:
        print(row)
    else:
        print("\nResults — `Perf / A11y / Best Practices / SEO` (out of 100)\n")
        print(f"  Mobile  : {fmt_cell(mobile)}  ({fmt_metrics(mobile)})")
        print(f"  Desktop : {fmt_cell(desktop)}  ({fmt_metrics(desktop)})")
        for label, crux in [("Mobile", mobile_crux), ("Desktop", desktop_crux)]:
            if crux and fmt_crux(crux):
                print(f"  CrUX {label[:1]} ({crux['scope']}, real-user p75): {fmt_crux(crux)}")
        # When a category scored < 100, list which audits dragged it down.
        # Lets you pinpoint regressions without re-running PSI in a browser.
        for label, summary, raw in [("Mobile", mobile, mobile_raw),
                                     ("Desktop", desktop, desktop_raw)]:
            for cat_key, cat_label, cat_score in [
                ("a11y_fails", "Accessibility", summary["a11y"]),
                ("bp_fails", "Best Practices", summary["bp"]),
                ("seo_fails", "SEO", summary["seo"]),
            ]:
                if cat_score < 100 and summary.get(cat_key):
                    fails = ", ".join(summary[cat_key])
                    print(f"  ⚠ {label} {cat_label} ({cat_score}): {fails}")
                    # For each failing audit, list the specific DOM nodes
                    # Lighthouse flagged. Indented under the audit summary.
                    raw_audits = raw["lighthouseResult"]["audits"]
                    for aid in summary[cat_key]:
                        a = raw_audits.get(aid, {})
                        items = (a.get("details") or {}).get("items") or []
                        # Some audits (errors-in-console, robots-txt) expose
                        # an explanation field on the audit itself, not in
                        # details.items[].
                        expl = (a.get("explanation") or a.get("displayValue") or "").strip().replace("\n", " ")
                        if expl:
                            if len(expl) > 110:
                                expl = expl[:107] + "…"
                            print(f"      ↳ {aid}: {expl}")
                        if not items:
                            continue
                        for item in items[:5]:
                            # Different audits expose details differently —
                            # node.selector for DOM audits, source/url/
                            # description for console / network / robots-txt.
                            node = item.get("node") or {}
                            sel = node.get("selector") or ""
                            snip = (node.get("snippet") or "").strip().replace("\n", " ")
                            source = item.get("source") or ""
                            desc = (item.get("description") or "").strip().replace("\n", " ")
                            url = item.get("url") or ""
                            line = item.get("line")
                            loc = item.get("sourceLocation") or {}
                            loc_url = loc.get("url", "") if isinstance(loc, dict) else ""
                            parts = [p for p in [sel, snip, source, url, loc_url, desc] if p]
                            line_str = f":{line}" if line is not None else ""
                            text = "  ".join(parts) + line_str
                            if len(text) > 140:
                                text = text[:137] + "…"
                            print(f"      ↳ {aid}: {text}".rstrip() if text else f"      ↳ {aid}: (no detail)")
                        if len(items) > 5:
                            print(f"      ↳ {aid}: …+{len(items)-5} more")
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
