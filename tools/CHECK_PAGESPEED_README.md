# ⏱ PageSpeed Insights Checker

Runs Google PageSpeed Insights against `csoh.org` (mobile + desktop in parallel) and appends a row to `seo-audits/SCORECARD.md`.

## Why

The internal SEO audit (the structural one tracked at the top of SCORECARD.md) is measured from inside the codebase. PSI is the only way to capture the synthetic-lab signal Google actually surfaces — Lighthouse Performance/Accessibility/Best Practices/SEO scores plus the lab-measured Core Web Vitals (LCP, CLS, TBT, FCP, Speed Index). Running it after every meaningful change keeps the second half of SCORECARD.md current.

## One-time setup: API key

The PSI v5 API rejects unauthenticated requests (anonymous quota = 0). A free API key takes ~30 seconds:

1. Go to [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials).
2. Create a new project if needed, then **Create Credentials → API key**.
3. Restrict the key to "PageSpeed Insights API" (optional but recommended).
4. Export it:

```bash
export PSI_API_KEY=AIza…
# Or stash it in your shell profile so it sticks
```

No quota cost for typical hobby use — the default per-project quota is 25,000 queries/day.

## Usage

```bash
# Default: hit https://csoh.org/ on mobile + desktop, append a SCORECARD row
python3 tools/check_pagespeed.py

# Different URL (any page on the site)
python3 tools/check_pagespeed.py --url https://csoh.org/glossary.html

# Print results, don't touch the scorecard
python3 tools/check_pagespeed.py --dry-run

# Just the markdown row (useful for piping into a PR comment / CI summary)
python3 tools/check_pagespeed.py --quiet
```

Output is the four 0-100 category scores per strategy plus a one-line Core Web Vitals summary for the Notes column.

## When to run

- After any change that could affect rendering (CSS, JS, images, layout-shift sources, render-blocking resources).
- Weekly is fine for steady-state monitoring — the score moves slowly absent code changes.
- Pair with a Google Search Console check so you see both the synthetic lab data (PSI) and the real-user CrUX data side by side.

## Requirements

- Python 3.9+ (standard library only)
- A free PSI API key in `$PSI_API_KEY`
