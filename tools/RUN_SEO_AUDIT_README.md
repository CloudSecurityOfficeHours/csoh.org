# 🔍 Deterministic SEO Audit

Mechanical structural SEO audit that mirrors the checks the `/seo-audit` skill does, across every indexable HTML page in the repo. Writes a per-day Markdown report under `seo-audits/` and appends a row to `seo-audits/SCORECARD.md`'s Internal SEO audit table. Cheap, repeatable, and free — no LLM/API needed.

Pairs with `check_pagespeed.py` (synthetic-lab side via Google PSI). Together they keep both halves of SCORECARD.md current.

## Why

The `/seo-audit` skill is great for qualitative judgment but it costs Claude calls and has variance run-to-run. This script handles the deterministic baseline — title length, meta description length, canonical, OG / Twitter completeness, single H1, robots meta, JSON-LD presence, image alt coverage, `<html lang>` — so the human-driven audits can focus on strategy (internal linking, topical authority, AI visibility) rather than re-checking the structural floor.

## What it checks

Per page:

- **Critical** (each drops the relevant category score by 5):
  - `<title>` present and non-empty
  - `<meta name="description">` present and non-empty
  - `<link rel="canonical">` present AND matches the expected URL for the file
  - exactly one `<h1>` (zero or multiple both fail)
  - `<meta property="og:image">` present

- **Warning** (each drops the score by 1):
  - title length outside 30–65 chars
  - meta description outside 100–165 chars
  - `og:image` points at the generic `banner.png` fallback (not a per-page card)
  - missing `<meta name="robots">`
  - missing any of `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`
  - `<html>` missing `lang` attribute

- **Opportunity** (informational, doesn't gate):
  - no JSON-LD schema present
  - > 5% of `<img>` tags missing or empty `alt`

Categories scored: Technical SEO, On-Page SEO, Content & Structure. Performance (95) and Mobile/A11y (96) are static placeholders — the real movement on those comes from `check_pagespeed.py` (synthetic lab) and Google Search Console CrUX (real users).

## Usage

```bash
# Default: audit all 178 indexable pages, write report + scorecard row
python3 tools/run_seo_audit.py

# Print results, don't write
python3 tools/run_seo_audit.py --dry-run

# Just emit the markdown scorecard row (useful in CI summaries)
python3 tools/run_seo_audit.py --quiet
```

Exit codes:

- `0` — score held or improved vs the previous Internal audit row
- `1` — score dropped vs previous (regression)
- `2` — script error

## Pages covered

- All top-level `*.html` (excluding `403.html`, `404.html`, the Google site-verification stub, `chat-resources.html` which is noindexed, and `search.html` which is a utility page)
- All `breaches/*.html`
- All `portfolio/*.html`
- All `meetings/*.html` (94 weekly recaps)

Total: 178 indexable pages as of 2026-05-23.

## When to run

- Locally: any time you suspect you might have changed something that affects structural SEO — title trims, schema additions, OG card swaps.
- Automated: the `.github/workflows/run-seo-audit.yml` workflow runs it every Monday at 14:15 UTC, opens a PR with the new SCORECARD row, and files a tracking issue if the overall score dropped.

## Requirements

- Python 3.9+ (standard library only)
- Run from the repo root.
