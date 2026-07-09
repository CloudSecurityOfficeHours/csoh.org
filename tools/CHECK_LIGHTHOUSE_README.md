# check_lighthouse.py

Runs [Lighthouse](https://developer.chrome.com/docs/lighthouse) against a representative sample of pages and asserts SEO / accessibility / performance / best-practices thresholds. Print a pass/fail table and exit non-zero if anything misses target - wire into CI to catch regressions before they ship.

## Why

Real audits beat hunches. We've added meta tags, schema, lazy-loading, WebP, resource hints - but a one-line CSS regression or a giant un-optimized image can quietly tank the score. Lighthouse runs the same checks Google Search Console uses, so this is the closest proxy we have to "what does Google think of this page right now."

## Install (once)

```bash
npm install -g lighthouse
```

The script will fall back to `npx --yes lighthouse` if the global binary isn't installed (slower first run).

## Usage

```bash
# Default sample against production
python3 tools/check_lighthouse.py

# Audit local preview
python3 tools/check_lighthouse.py --base http://localhost:8000

# Audit a specific list of pages
python3 tools/check_lighthouse.py --pages /index.html /resources.html

# Relax thresholds (default: perf≥80 a11y≥95 best≥90 seo≥95)
python3 tools/check_lighthouse.py --perf 70
```

## Default sample

The default sample picks one of each kind of page:

- `/` - homepage
- `/what-is-cloud-security.html` - pillar page
- `/cspm-vs-cnapp.html` - comparison pillar
- `/resources.html` - card-heavy listing page
- `/cloud-security-certifications.html` - pillar with FAQ schema
- `/breaches/capital-one.html` - per-breach split page
- `/github-actions.html` - internal docs page

Pass `--pages` to override.

## Output

```
→ https://csoh.org/
  perf= 92 a11y= 98 best= 96 seo=100  ✓
→ https://csoh.org/resources.html
  perf= 78 a11y= 96 best= 96 seo=100  ✗ below: performance

========================================================================
page                                                    perf a11y best  seo
------------------------------------------------------------------------
/                                                         92   98   96  100
/resources.html                                           78   96   96  100 ✗
========================================================================

✗ One or more pages missed thresholds.
```

## Targets and why they're set where they are

- **SEO ≥ 95** - meta tags, structured data, crawlability are non-negotiable. Anything less means we're losing free traffic.
- **Accessibility ≥ 95** - both ethical and an SEO ranking factor; aria/contrast/labels matter.
- **Performance ≥ 80** - strict 90+ would make the card-heavy resource pages noisy. 80 catches major regressions without flagging "many cards = big DOM" as a bug.
- **Best practices ≥ 90** - security headers, no console errors, https everywhere.

Override per-run with `--seo`, `--a11y`, `--perf`, `--best`.
