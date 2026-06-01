#!/usr/bin/env python3
"""Run Lighthouse against a sample of pages and assert SEO/a11y/perf thresholds.

Wraps the `lighthouse` CLI (Node.js). Picks a representative sample -
homepage, a pillar page, a card page, a per-meeting page, a per-breach
page - runs each in headless Chrome, parses the JSON report, and prints
a pass/fail table.

Targets (override via flags):
  SEO           >= 95
  Accessibility >= 95
  Performance   >= 80
  Best practices >= 90

Install once:
    npm install -g lighthouse
    # or use npx (slower first run): npx lighthouse ...

Usage:
    python3 tools/check_lighthouse.py                  # default sample
    python3 tools/check_lighthouse.py --base https://csoh.org
    python3 tools/check_lighthouse.py --pages index.html resources.html
    python3 tools/check_lighthouse.py --seo 90 --perf 70  # relax thresholds

Exit code is non-zero if any sampled page misses any threshold - wire
into CI to catch regressions.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_BASE = "https://csoh.org"
DEFAULT_SAMPLE = [
    "/",
    "/what-is-cloud-security.html",
    "/cspm-vs-cnapp.html",
    "/resources.html",
    "/cloud-security-certifications.html",
    "/breaches/capital-one-2019.html",
    "/github-actions.html",
]

CATEGORIES = ("performance", "accessibility", "best-practices", "seo")


def find_lighthouse() -> list[str] | None:
    """Returns the command prefix to invoke Lighthouse, or None if missing."""
    if shutil.which("lighthouse"):
        return ["lighthouse"]
    if shutil.which("npx"):
        return ["npx", "--yes", "lighthouse"]
    return None


def run_lighthouse(cmd: list[str], url: str) -> dict | None:
    with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as tmp:
        out_path = tmp.name
    try:
        full = [
            *cmd, url,
            "--output=json",
            f"--output-path={out_path}",
            "--quiet",
            "--chrome-flags=--headless=new --no-sandbox",
            "--only-categories=" + ",".join(CATEGORIES),
            "--max-wait-for-load=45000",
        ]
        result = subprocess.run(full, capture_output=True, text=True, timeout=180)
        if result.returncode != 0:
            print(f"  ✗ lighthouse exited {result.returncode}", file=sys.stderr)
            stderr = (result.stderr or "").strip().splitlines()[-3:]
            for line in stderr:
                print(f"    {line}", file=sys.stderr)
            return None
        return json.loads(Path(out_path).read_text())
    except subprocess.TimeoutExpired:
        print(f"  ✗ timeout after 180s on {url}", file=sys.stderr)
        return None
    finally:
        Path(out_path).unlink(missing_ok=True)


def score(report: dict, category: str) -> int:
    cat = report.get("categories", {}).get(category, {})
    raw = cat.get("score")
    return round(raw * 100) if raw is not None else 0


def main() -> int:
    p = argparse.ArgumentParser(description="Run Lighthouse against sample pages.")
    p.add_argument("--base", default=DEFAULT_BASE, help="Base URL (default: %(default)s)")
    p.add_argument("--pages", nargs="*", default=DEFAULT_SAMPLE,
                   help="Paths or URLs to audit")
    p.add_argument("--seo", type=int, default=95)
    p.add_argument("--a11y", type=int, default=95)
    p.add_argument("--perf", type=int, default=80)
    p.add_argument("--best", type=int, default=90)
    args = p.parse_args()

    cmd = find_lighthouse()
    if cmd is None:
        print("Lighthouse not found. Install with `npm install -g lighthouse`",
              file=sys.stderr)
        return 2

    thresholds = {
        "performance": args.perf,
        "accessibility": args.a11y,
        "best-practices": args.best,
        "seo": args.seo,
    }

    print(f"Running Lighthouse via: {' '.join(cmd)}")
    print(f"Thresholds: perf≥{args.perf} a11y≥{args.a11y} best≥{args.best} seo≥{args.seo}\n")

    rows: list[tuple[str, dict[str, int], list[str]]] = []
    any_fail = False

    for page in args.pages:
        url = page if page.startswith("http") else args.base.rstrip("/") + page
        print(f"→ {url}")
        report = run_lighthouse(cmd, url)
        if report is None:
            any_fail = True
            rows.append((url, {c: 0 for c in CATEGORIES}, ["error"]))
            continue
        scores = {c: score(report, c) for c in CATEGORIES}
        failed = [c for c, t in thresholds.items() if scores[c] < t]
        if failed:
            any_fail = True
        rows.append((url, scores, failed))
        print(f"  perf={scores['performance']:>3} a11y={scores['accessibility']:>3} "
              f"best={scores['best-practices']:>3} seo={scores['seo']:>3}"
              + (f"  ✗ below: {', '.join(failed)}" if failed else "  ✓"))

    print("\n" + "=" * 72)
    print(f"{'page':<55} perf a11y best  seo")
    print("-" * 72)
    for url, scores, failed in rows:
        path = url.replace(args.base, "") or "/"
        path = path[:54]
        marker = " ✗" if failed else ""
        print(f"{path:<55} {scores['performance']:>4} {scores['accessibility']:>4} "
              f"{scores['best-practices']:>4} {scores['seo']:>4}{marker}")
    print("=" * 72)

    if any_fail:
        print("\n✗ One or more pages missed thresholds.")
        return 1
    print("\n✓ All sampled pages meet thresholds.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
