# SEO Scorecard - csoh.org

Track audit scores over time. Add a new row each time `/seo-audit` is run. Lower scores = regression; investigate.

## Internal SEO audit

| Date | Overall | Technical | On-Page | Content | Performance | Mobile/A11y | Critical | Warnings | Report |
|---|---|---|---|---|---|---|---|---|---|
| 2026-04-30 | **88** | 95 | 90 | 88 | 75 | 95 | 2 | 6 | [baseline](2026-04-30-baseline.md) |
| 2026-05-03 | **96** | 97 | 95 | 96 | 92 | 96 | 0 | 1 | [report](2026-05-03.md) |
| 2026-05-03 (rerun) | **96** | 95 | 96 | 97 | 93 | 96 | 1 | 1 | [report](2026-05-03-rerun.md) |
| 2026-05-03 (final) | **97** | 98 | 98 | 97 | 94 | 96 | 0 | 2 | [report](2026-05-03-final.md) |
| 2026-05-03 (followup) | **98** | 99 | 99 | 99 | 94 | 96 | 0 | 0 | [report](2026-05-03-followup.md) |
| 2026-05-06 | **98** | 99 | 100 | 99 | 95 | 96 | 0 | 0 | [report](2026-05-06.md) |
| 2026-05-08 | **98** | 99 | 100 | 99 | 95 | 96 | 0 | 0 | [report](2026-05-08.md) |
| 2026-05-09 | **98** | 99 | 100 | 99 | 95 | 96 | 0 | 0 | [report](2026-05-09.md) |
| 2026-05-17 | **99** | 100 | 100 | 100 | 95 | 96 | 0 | 0 | [report](2026-05-17.md) |
| 2026-05-18 | **98** | 100 | 100 | 98 | 95 | 96 | 0 | 1 | [report](2026-05-18.md) |
| 2026-05-23 | **99** | 100 | 100 | 100 | 95 | 96 | 0 | 0 | [report](2026-05-23.md) |
| 2026-05-23 | **98** | 100 | 100 | 100 | 95 | 96 | 0 | 0 | [report](2026-05-23-auto-1.md) |

## PageSpeed Insights - homepage (https://csoh.org/)

Each cell is `Performance / Accessibility / Best Practices / SEO` (out of 100). Run at [pagespeed.web.dev](https://pagespeed.web.dev/analysis?url=https%3A%2F%2Fcsoh.org%2F).

| Date | Mobile | Desktop | Notes |
|---|---|---|---|
| 2026-05-06 | 96 / 100 / 92 / 92 | 100 / 100 / 92 / 92 | Post fixes: contrast, CLS (mobile-nav shift), LCP image, tooltip a11y |

## How to use

1. Run `/seo-audit csoh.org` (uses the SearchFit SEO skill) or invoke the seo-auditor agent.
2. Save the full report as `seo-audits/YYYY-MM-DD.md`.
3. Append a row to the **Internal SEO audit** table with the new scores.
4. Run [PageSpeed Insights](https://pagespeed.web.dev/analysis?url=https%3A%2F%2Fcsoh.org%2F) for both Mobile and Desktop tabs and append a row to the **PageSpeed Insights** table.
5. Diff against the previous row - celebrate gains, investigate drops.

## External signals to track alongside this

- **Google Search Console** - impressions, clicks, average position, CTR (set up email alerts for coverage/index drops)
- **CrUX / Core Web Vitals** - real-user LCP, INP, CLS (the lab scores above are synthetic; CrUX appears in PSI's "Discover what your real users are experiencing" panel once enough traffic accumulates)
- **Bing Webmaster Tools** - secondary search source

The scores in this scorecard measure on-site/codebase health. Search Console measures actual ranking outcomes. Both matter.
