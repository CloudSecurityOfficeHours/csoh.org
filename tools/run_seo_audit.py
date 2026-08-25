#!/usr/bin/env python3
"""Deterministic structural SEO audit for csoh.org.

Mirrors the mechanical checks the /seo-audit skill performs - canonical,
title length, meta description, OG image, Twitter Card completeness, H1
count, JSON-LD presence - across every indexable HTML page in the repo.
Produces a Markdown audit report at seo-audits/YYYY-MM-DD.md and appends
a row to seo-audits/SCORECARD.md's Internal SEO audit table.

Exit code:
  0 - score held, improved, or dropped by only 1 point (REGRESSION_THRESHOLD = 2),
      or there is no previous row to compare against
  1 - score dropped by 2 or more points vs the previous auto-row (regression)
  2 - invalid CLI arguments (argparse only)

Usage:
    python3 tools/run_seo_audit.py             # write audit + scorecard row
    python3 tools/run_seo_audit.py --dry-run   # print summary, write nothing
    python3 tools/run_seo_audit.py --quiet     # just emit the markdown row
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AUDITS_DIR = REPO_ROOT / "seo-audits"
SCORECARD = AUDITS_DIR / "SCORECARD.md"

# Pages we explicitly do NOT audit (error pages, search-engine verification,
# noindexed surfaces).
SKIP = {
    "403.html", "404.html",
    "google66d489593949bd4c.html",
    "chat-resources.html",      # noindex by design (too large)
    "search.html",               # noindex utility
}

# Regex grab-bags. We intentionally use forgiving patterns - production
# HTML often varies attribute order or quoting and we want to match real
# pages, not idealized ones.
TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
META_DESC_RE = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"', re.IGNORECASE)
CANONICAL_RE = re.compile(r'<link\s+rel="canonical"\s+href="([^"]+)"', re.IGNORECASE)
ROBOTS_RE = re.compile(r'<meta\s+name="robots"\s+content="([^"]+)"', re.IGNORECASE)
OG_IMAGE_RE = re.compile(r'<meta\s+property="og:image"\s+content="([^"]+)"', re.IGNORECASE)
TWITTER_CARD_RE = re.compile(r'<meta\s+name="twitter:card"\s+content="([^"]+)"', re.IGNORECASE)
TWITTER_TITLE_RE = re.compile(r'<meta\s+name="twitter:title"\s+content="([^"]+)"', re.IGNORECASE)
TWITTER_DESC_RE = re.compile(r'<meta\s+name="twitter:description"\s+content="([^"]+)"', re.IGNORECASE)
TWITTER_IMAGE_RE = re.compile(r'<meta\s+name="twitter:image"\s+content="([^"]+)"', re.IGNORECASE)
H1_RE = re.compile(r"<h1\b[^>]*>", re.IGNORECASE)
JSON_LD_RE = re.compile(r'<script\s+type="application/ld\+json"', re.IGNORECASE)
LANG_RE = re.compile(r"<html\s+[^>]*\blang=", re.IGNORECASE)
IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
ALT_RE = re.compile(r'\balt="([^"]*)"', re.IGNORECASE)


# Every subdirectory of indexable pages. The audit is only as complete as this
# tuple: a directory missing here is silently never checked, and since the score
# is an average over the pages we DID audit, its absence doesn't even dent the
# number. `homelab` was missing until 2026-07 for exactly that reason - it was
# added after this tuple was written, and nothing flagged the omission.
#
# Adding a new subdirectory of pages? Add it here too. The full list of places a
# new page directory has to be registered is in DEVELOPMENT.md.
AUDITED_SUBDIRS = ("breaches", "portfolio", "meetings", "homelab", "howto")


def discover_pages() -> list[Path]:
    """All HTML files we audit: top-level + every dir in AUDITED_SUBDIRS."""
    pages = list(REPO_ROOT.glob("*.html"))
    for sub in AUDITED_SUBDIRS:
        pages.extend((REPO_ROOT / sub).glob("*.html"))
    return [p for p in pages if p.name not in SKIP]


def expected_canonical(path: Path) -> str:
    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel == "index.html":
        return "https://csoh.org/"
    return f"https://csoh.org/{rel}"


def audit_page(path: Path) -> dict:
    """Return per-page audit results. Each issue is a dict with keys
    `severity` (critical|warning|opportunity), `category`, and `message`."""
    s = path.read_text(encoding="utf-8", errors="replace")
    rel = path.relative_to(REPO_ROOT).as_posix()
    issues: list[dict] = []

    def add(severity: str, category: str, message: str) -> None:
        issues.append({"severity": severity, "category": category, "message": message})

    # ── Critical ────────────────────────────────────────────────────────
    title_m = TITLE_RE.search(s)
    if not title_m:
        add("critical", "on-page", f"{rel}: missing <title>")
        title = ""
    else:
        title = title_m.group(1).strip()
        if not title:
            add("critical", "on-page", f"{rel}: empty <title>")

    desc_m = META_DESC_RE.search(s)
    if not desc_m:
        add("critical", "on-page", f"{rel}: missing meta description")
        desc = ""
    else:
        desc = desc_m.group(1).strip()
        if not desc:
            add("critical", "on-page", f"{rel}: empty meta description")

    canon_m = CANONICAL_RE.search(s)
    if not canon_m:
        add("critical", "technical", f"{rel}: missing canonical")
    else:
        expected = expected_canonical(path)
        if canon_m.group(1) != expected:
            add("critical", "technical",
                f"{rel}: canonical mismatch (got {canon_m.group(1)}, expected {expected})")

    h1_count = len(H1_RE.findall(s))
    if h1_count == 0:
        add("critical", "content", f"{rel}: no <h1>")
    elif h1_count > 1:
        add("critical", "content", f"{rel}: {h1_count} <h1> tags (must be exactly 1)")

    if not OG_IMAGE_RE.search(s):
        add("critical", "on-page", f"{rel}: missing og:image")

    # ── Warnings ────────────────────────────────────────────────────────
    if title and not (30 <= len(title) <= 65):
        add("warning", "on-page",
            f"{rel}: title {len(title)} chars (sweet spot 30-65) - \"{title}\"")
    if desc and not (100 <= len(desc) <= 165):
        add("warning", "on-page",
            f"{rel}: meta description {len(desc)} chars (sweet spot 100-165)")

    og_m = OG_IMAGE_RE.search(s)
    if og_m and "/banner.png" in og_m.group(1) and "/img/og/" not in og_m.group(1):
        add("warning", "on-page", f"{rel}: og:image points at generic banner.png fallback")

    if not ROBOTS_RE.search(s):
        add("warning", "technical", f"{rel}: missing robots meta")

    for label, regex in [
        ("twitter:card", TWITTER_CARD_RE),
        ("twitter:title", TWITTER_TITLE_RE),
        ("twitter:description", TWITTER_DESC_RE),
        ("twitter:image", TWITTER_IMAGE_RE),
    ]:
        if not regex.search(s):
            add("warning", "on-page", f"{rel}: missing {label}")

    if not LANG_RE.search(s):
        add("warning", "a11y", f"{rel}: <html> missing lang attribute")

    # ── Opportunities ───────────────────────────────────────────────────
    if not JSON_LD_RE.search(s):
        add("opportunity", "content", f"{rel}: no JSON-LD schema present")

    # Image alt coverage - count <img> without alt or with empty alt.
    imgs = IMG_RE.findall(s)
    if imgs:
        no_alt = sum(1 for img in imgs if not ALT_RE.search(img))
        empty_alt = sum(1 for img in imgs if ALT_RE.search(img) and not ALT_RE.search(img).group(1).strip())
        bad = no_alt + empty_alt
        if bad and bad / len(imgs) > 0.05:
            pct = round(100 * bad / len(imgs))
            add("opportunity", "a11y",
                f"{rel}: {bad}/{len(imgs)} images ({pct}%) missing or empty alt")

    return {"rel": rel, "issues": issues, "title": title, "desc": desc, "img_count": len(imgs)}


def score_category(issues: list[dict], category: str,
                   crit_weight: int = 5, warn_weight: int = 1, opp_weight: int = 0) -> int:
    """Score a single category 0-100. Each critical drops 5, each warning 1,
    opportunities are informational only. Clamped to [0, 100]."""
    crit = sum(1 for i in issues if i["severity"] == "critical" and i["category"] == category)
    warn = sum(1 for i in issues if i["severity"] == "warning" and i["category"] == category)
    score = 100 - crit * crit_weight - warn * warn_weight
    return max(0, min(100, score))


def build_report(results: list[dict], today: str) -> tuple[str, dict]:
    """Return (markdown_body, scores_dict)."""
    all_issues = [i for r in results for i in r["issues"]]
    crit = [i for i in all_issues if i["severity"] == "critical"]
    warn = [i for i in all_issues if i["severity"] == "warning"]
    opp = [i for i in all_issues if i["severity"] == "opportunity"]

    technical = score_category(all_issues, "technical")
    on_page = score_category(all_issues, "on-page")
    content = score_category(all_issues, "content")
    # The a11y issues collected per page (html-lang, image-alt coverage) feed
    # into the deterministic mobile/a11y floor - a structural ceiling that
    # PSI-derived lab a11y is intersected with below.
    a11y_floor = score_category(all_issues, "a11y")

    # Use the latest mobile PSI row from SCORECARD.md as the source of truth
    # for Performance and Mobile/A11y. Mobile (not desktop) because Google
    # indexes mobile-first. Median across same-day runs guards against PSI
    # lab glitches like the 2026-05-23 desktop 38 → 100 bounce (see commit
    # 63317d48). Falls back to the 95/96 placeholder caps if SCORECARD has
    # no PSI data yet - keeps the script usable in a fresh repo.
    psi = latest_psi_mobile_scores()
    if psi:
        psi_perf, psi_a11y = psi
        performance = psi_perf
        mobile = min(psi_a11y, a11y_floor)
        psi_source = "PSI mobile (latest, median of same-day runs)"
    else:
        performance = 95
        mobile = min(96, a11y_floor)
        psi_source = "placeholder caps (no PSI rows found in SCORECARD)"
    overall = round((technical + on_page + content + performance + mobile) / 5)

    scores = {
        "overall": overall,
        "technical": technical,
        "on_page": on_page,
        "content": content,
        "performance": performance,
        "mobile": mobile,
        "critical": len(crit),
        "warnings": len(warn),
        "opportunities": len(opp),
    }

    def issue_list(issues: list[dict], cap: int = 15) -> str:
        if not issues:
            return "None.\n"
        out = []
        for i in issues[:cap]:
            out.append(f"- **[{i['category']}]** {i['message']}")
        if len(issues) > cap:
            out.append(f"- _…and {len(issues) - cap} more._")
        return "\n".join(out) + "\n"

    body = f"""# SEO Audit - {today}

**Site**: csoh.org
**Pages Analyzed**: {len(results)} indexable
**Overall Score**: **{overall}/100**

_Generated by `tools/run_seo_audit.py` (deterministic structural audit)._

## Score Breakdown

| Category | Score |
|---|---|
| Technical SEO | {technical}/100 |
| On-Page SEO | {on_page}/100 |
| Content & Structure | {content}/100 |
| Performance | {performance}/100 |
| Mobile & Accessibility | {mobile}/100 |

## Critical Issues ({len(crit)})

{issue_list(crit)}

## Warnings ({len(warn)})

{issue_list(warn)}

## Opportunities ({len(opp)})

{issue_list(opp)}

## Notes

This audit is mechanically generated and covers structural checks only -
canonical, title/meta length, OG / Twitter completeness, H1 hierarchy,
robots meta, JSON-LD presence, image alt coverage. For deeper qualitative
review (internal-linking strategy, content depth, AI visibility) run the
`/seo-audit` skill manually.

Performance and Mobile/A11y are sourced from {psi_source} - the cells
labeled `Perf / A11y / BP / SEO` in the PageSpeed Insights table below.
Mobile/A11y is then intersected with a codebase-derived a11y floor
({a11y_floor}/100) so structural regressions (missing alt text, html-lang,
etc.) can still drop the score even when PSI says 100. Generate fresh PSI
data with [`tools/check_pagespeed.py`](../tools/check_pagespeed.py); the
weekly workflow runs Mondays.
"""
    return body, scores


def latest_psi_mobile_scores() -> tuple[int, int] | None:
    """Return (perf, a11y) from the most recent mobile PSI row(s) in
    SCORECARD.md, taking the median across same-day runs.

    PSI lab tests bounce on noisy infra (the 2026-05-23 desktop run dipped
    to 38 before snapping back to 100). Median across same-day runs is
    more robust than `latest` while still reflecting recent state. Returns
    None when no PSI rows exist - caller falls back to placeholder caps.
    """
    if not SCORECARD.exists():
        return None
    rows: list[tuple[str, int, int]] = []
    for line in SCORECARD.read_text(encoding="utf-8").splitlines():
        # PSI rows look like `| YYYY-MM-DD | P / A / BP / SEO | ... | ... |`
        # so the second cell starts with two slash-separated ints.
        m = re.match(
            r"^\|\s*(\d{4}-\d{2}-\d{2})\s*\|\s*(\d+)\s*/\s*(\d+)\s*/\s*\d+\s*/\s*\d+\s*\|",
            line,
        )
        if m:
            rows.append((m.group(1), int(m.group(2)), int(m.group(3))))
    if not rows:
        return None
    latest_date = rows[-1][0]
    same_day = [r for r in rows if r[0] == latest_date]
    perfs = sorted(r[1] for r in same_day)
    a11ys = sorted(r[2] for r in same_day)
    return perfs[len(perfs) // 2], a11ys[len(a11ys) // 2]


def previous_scorecard_row() -> tuple[int, str] | None:
    """Return (previous_overall_score, previous_row_markdown) from the
    Internal SEO audit table - but only rows produced by THIS script
    (report filename ends with `-auto-N.md`). The qualitative `/seo-audit`
    skill uses different scoring weights and comparing the two yields
    spurious "regression" alerts (e.g. a `/seo-audit` 99 followed by a
    script 98 isn't a real -1 regression, it's a methodology delta).

    Returns None if no prior auto-row exists yet."""
    text = SCORECARD.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines()
            if re.match(r"^\| \d{4}-\d{2}-\d{2}\s*\|", line) and " / " not in line]
    # Same-methodology rows only - report file matches `-auto-N.md`.
    auto_rows = [r for r in rows if re.search(r"-auto-\d+\.md\)", r)]
    if not auto_rows:
        return None
    last = auto_rows[-1]
    # cells: | date | **score** | technical | on-page | content | perf | a11y | crit | warn | report |
    cells = [c.strip() for c in last.strip("|").split("|")]
    m = re.search(r"(\d+)", cells[1])
    score = int(m.group(1)) if m else 0
    return score, last


def append_scorecard_row(today: str, scores: dict, report_filename: str) -> None:
    text = SCORECARD.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find the Internal SEO audit table. Insert after the last existing row.
    table_header_idx = None
    for i, line in enumerate(lines):
        if "| Overall " in line and "| Technical " in line:
            table_header_idx = i
            break
    if table_header_idx is None:
        raise SystemExit("Could not locate the Internal SEO audit table in SCORECARD.md")

    insert_at = table_header_idx + 2  # header + separator
    while insert_at < len(lines) and lines[insert_at].startswith("|"):
        insert_at += 1

    new_row = (
        f"| {today} | **{scores['overall']}** | "
        f"{scores['technical']} | {scores['on_page']} | {scores['content']} | "
        f"{scores['performance']} | {scores['mobile']} | "
        f"{scores['critical']} | {scores['warnings']} | "
        f"[report]({report_filename}) |"
    )
    lines.insert(insert_at, new_row)
    SCORECARD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Print summary, don't write files")
    parser.add_argument("--quiet", action="store_true",
                        help="Just emit the markdown scorecard row")
    args = parser.parse_args()

    pages = discover_pages()
    if not args.quiet:
        print(f"⏱  Auditing {len(pages)} pages…")

    results = [audit_page(p) for p in pages]
    today = dt.date.today().isoformat()
    body, scores = build_report(results, today)

    # Pick a unique filename if today's audit was already saved.
    report_path = AUDITS_DIR / f"{today}.md"
    suffix = 1
    while report_path.exists():
        report_path = AUDITS_DIR / f"{today}-auto-{suffix}.md"
        suffix += 1
    report_filename = report_path.name

    new_row = (
        f"| {today} | **{scores['overall']}** | "
        f"{scores['technical']} | {scores['on_page']} | {scores['content']} | "
        f"{scores['performance']} | {scores['mobile']} | "
        f"{scores['critical']} | {scores['warnings']} | "
        f"[report]({report_filename}) |"
    )

    prev = previous_scorecard_row()
    # Require a ≥2-point drop to count as a regression. A 1-point drop
    # typically means a single new warning landed (e.g. a new page added with
    # a slightly-long title), which the next routine cleanup pass clears.
    # We don't want to issue-spam for those.
    REGRESSION_THRESHOLD = 2
    regressed = bool(prev and (prev[0] - scores["overall"]) >= REGRESSION_THRESHOLD)

    if args.quiet:
        print(new_row)
    else:
        print(f"\nOverall: {scores['overall']}/100")
        print(f"  Technical: {scores['technical']}  On-Page: {scores['on_page']}  "
              f"Content: {scores['content']}  Perf: {scores['performance']}  "
              f"Mobile/A11y: {scores['mobile']}")
        print(f"Critical: {scores['critical']}  Warnings: {scores['warnings']}  "
              f"Opportunities: {scores['opportunities']}")
        if prev:
            delta = scores["overall"] - prev[0]
            arrow = "↑" if delta > 0 else ("↓" if delta < 0 else "→")
            print(f"Delta vs previous: {prev[0]} {arrow} {scores['overall']} ({delta:+d})")
        print(f"\nScorecard row:\n  {new_row}")

    if not args.dry_run:
        report_path.write_text(body, encoding="utf-8")
        append_scorecard_row(today, scores, report_filename)
        if not args.quiet:
            print(f"\n✓ Wrote {report_path.relative_to(REPO_ROOT)}")
            print(f"✓ Appended row to {SCORECARD.relative_to(REPO_ROOT)}")

    if regressed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
