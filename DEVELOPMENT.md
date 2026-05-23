# Local Development Guide

This guide gets you set up to make and preview changes to [csoh.org](https://csoh.org) on your own machine.

---

## Prerequisites

| Tool | Required for | Install |
|------|-------------|---------|
| **Git** | Cloning the repo, creating branches | [git-scm.com](https://git-scm.com) |
| **Python 3** | Running the local server and automation tools | [python.org](https://python.org) |
| **Web browser** | Previewing changes | Any modern browser (Chrome, Firefox, Safari, Edge) |

That's it. No Node.js, no build tools, no package manager. The site is pure HTML/CSS/JS.

---

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/CloudSecurityOfficeHours/csoh.org.git
cd csoh.org

# 2. Start the local server
python3 -m http.server 8091

# 3. Open in your browser
# Visit http://localhost:8091
```

You should see the full site running locally. Any file you edit will be reflected when you refresh the page.

---

## Making Changes

### Typical Workflow

```bash
# Create a branch for your change
git checkout -b fix/typo-on-resources-page

# Edit files with your preferred editor
# Preview at http://localhost:8091

# Stage and commit
git add resources.html
git commit -m "fix: correct typo in AWS CloudTrail description"

# Push and create a PR
git push -u origin fix/typo-on-resources-page
```

### Branch Naming Conventions

| Type | Pattern | Example |
|------|---------|---------|
| Bug fix | `fix/short-description` | `fix/broken-link-on-sessions` |
| New resource | `resource/resource-name` | `resource/aws-security-hub` |
| New feature | `feat/short-description` | `feat/add-search-filters` |
| Kill chain | `kill-chain/incident-name-year` | `kill-chain/okta-breach-2023` |
| Content update | `content/short-description` | `content/update-session-times` |

---

## Project Architecture

### Site Structure

The site is a **static HTML website** with no build step or framework. Each page is a standalone `.html` file that loads shared CSS and JS.

```
csoh.org/
├── index.html              # Homepage
│
│  ── Foundations ──
├── what-is-cloud-security.html      # Pillar: vendor-neutral cloud security overview
├── shared-responsibility-model.html # Provider vs. customer security split
├── cspm-vs-cnapp.html               # Tool-category comparison (CSPM/CNAPP/CWPP/CIEM/DSPM)
├── vendor-landscape.html            # 350+ cloud-security vendors across 30 categories
├── glossary.html                    # 300+ cloud-security terms with live search + cross-links
├── faq.html                         # Frequently asked questions
│
│  ── Platform topics ──
├── containers.html                  # Container security: boundary, escapes, IMDS, supply chain
├── kubernetes.html                  # EKS / AKS / GKE security
├── serverless.html                  # Lambda / Azure Functions / Cloud Functions security
├── service-mesh-security.html       # Istio / Linkerd / Cilium / Consul; mTLS; SPIFFE/SPIRE
├── ci-cd.html                       # CI/CD pipelines for cloud (OIDC federation)
├── landing-zones.html               # Cloud foundations (Control Tower / CAF / GCP blueprint)
│
│  ── Discipline topics ──
├── iam.html                         # IAM & cloud identity, RBAC/ABAC, workload identity, priv-esc paths
├── zero-trust.html                  # NIST SP 800-207, BeyondCorp, CISA Maturity Model
├── network-security.html            # VPC, private endpoints, egress controls, WAF/DDoS, SASE/ZTNA
├── data-security.html               # KMS, envelope encryption, BYOK/HSM, secrets, key rotation
├── vulnerability-management.html    # CVSS/EPSS/KEV, reachability, SAST/SCA/DAST, SBOM, ASPM
├── api-security.html                # OWASP API Top 10, BOLA, JWT, GraphQL/gRPC, gateways
├── saas-security.html               # SSPM, OAuth-app risk, M365/Workspace/Salesforce/GitHub
├── backup-dr.html                   # 3-2-1-1-0, immutability, ransomware kill chain
├── threat-modeling.html             # STRIDE/PASTA/LINDDUN, attack trees, ATT&CK Cloud
├── cloud-security-best-practices.html # Practitioner's controls checklist
│
│  ── Detection / response / offense ──
├── cloud-soc.html                   # Cloud SOC, log-driven detection, SIEM
├── detection-engineering.html       # Sigma, detection-as-code, ATT&CK Cloud Matrix
├── incident-response.html           # IR lifecycle, cloud forensics, runbooks
├── cloud-pentesting.html            # AWS/Azure/GCP attack paths, Pacu/ROADtools/BloodHound
├── threat-research.html             # Curated cloud threat research directory (incl. supply chain)
├── breach-timeline.html             # Cloud breach kill chain index → `breaches/`
├── ctfs.html                        # Cloud CTF directory
│
│  ── Governance + AI ──
├── grc.html                         # Governance, Risk, Compliance for cloud
├── compliance-frameworks.html       # SOC2 / ISO / PCI / HIPAA / FedRAMP / CMMC / GDPR deep dives
├── ai-learning.html                 # Using AI to LEARN cloud security
├── ai-ml-security.html              # Securing AI workloads (OWASP LLM Top 10, ATLAS)
│
│  ── Per-cloud SEO hubs ──
├── aws-security.html                # AWS security hub (high-volume search target)
├── azure-security.html              # Azure security hub
├── gcp-security.html                # GCP security hub
├── cloud-security-comparison.html   # AWS vs Azure vs GCP - 10 comparison tables + scorecard
│
│  ── Career / community ──
├── learning-path.html               # Beginner→advanced learning roadmap (HowTo schema)
├── cloud-security-degree-programs.html # Academic paths + university programs
├── cloud-security-careers.html      # Roles, salaries, interviews, portfolio
├── cloud-security-home-lab.html     # Free-tier setups, budget guardrails, kill-switches
├── cloud-security-certifications.html # CCSK / CCSP / AWS / Azure / GCP / CKS comparison
├── cloud-security-portfolio-projects.html # Hub for 7 portfolio walkthroughs (in `portfolio/`)
├── cloud-security-reading-list.html # Curated books / blogs / people-to-follow
├── community.html                   # Community & Signal chat
├── conferences.html                 # Security & hacker conferences directory
│
│  ── Sessions / news / archives ──
├── sessions.html                    # Weekly Zoom session info
├── meetings.html                    # Weekly meeting recaps → `meetings/`
├── presentations.html               # Recorded presentation archive
├── chat-resources.html              # Community-shared URLs from Zoom chat
├── resources.html                   # 240+ curated resources (largest page; auto-refreshed weekly)
├── news.html                        # Auto-generated news articles
├── rss.html                         # RSS subscription landing page
│
│  ── Behind the scenes ──
├── github-actions.html              # Learn-by-example GitHub Actions explainer
├── cloud-deployment.html            # How CSOH deploys to GCP (Cloud Run + WIF + CDN + Armor)
├── contribute.html                  # How to contribute
├── contribute-resources.html        # Resource submission form
│
│  ── Search ──
├── search.html                      # Pagefind-powered full-text search
├── search.css                       # Search page styles (extracted from inline for CSP)
├── pagefind-init.js                 # Pagefind UI bootstrap (extracted from inline for CSP)
├── pagefind/                        # Pagefind static search index (generated at deploy time)
│
│  ── Policy / about ──
├── about-shawn-nunley.html          # Author/E-E-A-T page
├── code-of-conduct.html
├── privacy.html
├── security-policy.html
│
│  ── Per-breach pages and meeting recaps ──
├── breaches/                        # 10 per-breach kill chain pages (split from breach-timeline.html)
├── meetings/                        # 94 per-meeting recap pages (split from meetings.html)
├── portfolio/                       # 7 per-project portfolio walkthroughs
│
│  ── Shared assets ──
├── style.css                        # All site styles (includes dark mode)
├── main.js                          # Search, filtering, sorting, dark mode toggle
├── chat-resources.js                # Chat-resources page-specific JS
├── meetings.js                      # Meeting recaps filtering + speaker filter
├── glossary.js                      # Glossary page live search
├── breach-timeline.css / .js        # Breach timeline page-specific assets
│
├── tools/                  # Python automation scripts (URL safety, normalization, previews, sitemap, presentations schema, glossary cross-linking, OG image generation incl. meeting variant, meeting → topic-page link injection)
├── .github/workflows/      # CI/CD pipelines (11 workflows: update-news, update-resources, gcp-deploy, normalize-urls, check-broken-links, check-url-safety, check-pagespeed, run-seo-audit, validate-html, lint, site-update-deploy)
└── update_news.py          # News aggregation from 39 RSS feeds
```

### How Key Features Work

**Dark Mode**
- CSS: Uses `[data-theme="dark"]` selectors in `style.css` to override colors
- CSS: Also supports `@media (prefers-color-scheme: dark)` for automatic OS detection
- JS: Toggle button in `main.js` sets `data-theme` attribute on the `<html>` element
- Preference is saved to `localStorage`

**Hover Tooltips** (resources.html)
- Each `.resource-card` has a `data-tooltip` attribute with an extended 2-3 sentence description
- A single reusable `<div class="resource-tooltip">` is appended to `<body>` by `initTooltips()` in `main.js`
- Event delegation on `#main-content` (mouseover/mousemove/mouseout) with a 300ms show delay
- Tooltip positions near the cursor and flips direction when close to viewport edges
- Hidden on touch devices via `@media (hover: none) and (pointer: coarse)`
- Dark mode styled via `[data-theme="dark"] .resource-tooltip`
- Tooltip text is NOT included in search/filter - only `data-tooltip` attribute, not visible DOM text

**Search & Filtering** (resources.html)
- `main.js` reads resource cards from the DOM
- Filters by text input (title, description, tags) and category buttons
- Tag-based filtering with toggle buttons
- All client-side, no server needed

**SRI Hashes & Cache Busting**
- Every CSS/JS file has a `integrity="sha384-..."` attribute for security
- Query params like `?v=d2217342` bust browser caches on file changes
- Both are auto-generated by `update_sri.py` and committed via GitHub Actions
- **You do not need to update SRI hashes manually** -- CI handles it on merge

**News Aggregation**
- `update_news.py` pulls from 39 RSS/Atom feeds every 3 hours (via GitHub Actions)
- Generates `news.html` and `feed.xml`, regenerates the `NewsArticle` JSON-LD block on `news.html`, and refreshes `sitemap.xml` lastmod dates
- Preserves cards already on `news.html` across runs so today-dated items don't disappear when RSS feeds rotate
- PRs are auto-created and auto-merged if only `news.html`, `feed.xml`, and `sitemap.xml` changed

**Resources Auto-Refresh** (`.github/workflows/update-resources.yml`)
- Mondays at 14:00 UTC, `anthropics/claude-code-action@v1` invokes Claude with a structured prompt to research and add 2-3 new resources to each of the six `resources.html` sections (CTF, Labs, Tools, Certs, AI Security, Job Search)
- Auth: `CLAUDE_CODE_OAUTH_TOKEN` (subscription quota, not API billing) + the `csoh-ci` GitHub App for write-scoped PRs + `CSOH_PAT` to approve the bot's own PR so auto-merge can satisfy the "1 required approval" rule
- The model checks for duplicates by grepping for URL + name before adding, follows the existing resource-card HTML pattern, and bumps the `<span id="visibleCount">` counter
- **Auto-merge only fires when the diff is purely `resources.html`.** If Claude touches anything else, the PR stays open with a banner asking for human review - important safety valve
- Preview images for newly-added cards are generated post-merge by `site-update-deploy.yml`

**Site-wide Search** (`search.html`, Pagefind)
- [Pagefind](https://pagefind.app) builds a static, client-side search index from the deployed HTML - no server, no JS framework
- The index is generated at deploy time and served from `/pagefind/`
- `search.css` and `pagefind-init.js` are external files (not inline) because the site's strict Content-Security-Policy blocks inline styles and scripts
- The search page has a 60-second `Cache-Control` cap so CSS tweaks propagate fast during iteration

---

## Testing Your Changes

### Visual Testing

After starting the local server (`python3 -m http.server 8091`), check these:

| What to test | How |
|-------------|-----|
| **Light mode** | Default appearance at `http://localhost:8091` |
| **Dark mode** | Click the moon/sun toggle in the header |
| **Mobile layout** | Open DevTools (F12) and toggle device toolbar (Ctrl+Shift+M / Cmd+Shift+M) |
| **Tablet layout** | Set device toolbar to 768px width |
| **Links** | Click any links you added or changed |

### Common Pages to Check

If you changed shared files (`style.css`, `main.js`), verify these pages:

- `http://localhost:8091/index.html` -- Homepage
- `http://localhost:8091/resources.html` -- Resources (search, filters, tags)
- `http://localhost:8091/news.html` -- News articles
- `http://localhost:8091/chat-resources.html` -- Chat resources (separate JS)
- `http://localhost:8091/glossary.html` -- Glossary (separate JS, search + cross-links)
- `http://localhost:8091/meetings.html` -- Meeting recaps (separate JS, speaker filter)
- `http://localhost:8091/faq.html` -- FAQ (FAQPage schema, collapsible details)
- `http://localhost:8091/what-is-cloud-security.html` -- Pillar overview (FAQ schema)
- `http://localhost:8091/learning-path.html` -- Beginner → advanced roadmap (HowTo schema)
- `http://localhost:8091/cloud-security-degree-programs.html` -- Academic paths + universities (FAQ schema)
- `http://localhost:8091/cloud-security-careers.html` -- Roles, salaries, interviews, portfolio (FAQ schema)
- `http://localhost:8091/cloud-security-home-lab.html` -- Free-tier setups, budget guardrails
- `http://localhost:8091/cloud-security-best-practices.html` -- Controls checklist
- `http://localhost:8091/shared-responsibility-model.html` -- Provider vs. customer split
- `http://localhost:8091/cspm-vs-cnapp.html` -- Tool category comparison
- `http://localhost:8091/landing-zones.html` -- Cloud foundations (AWS / Azure / GCP)
- `http://localhost:8091/containers.html` -- Container security
- `http://localhost:8091/kubernetes.html` -- Kubernetes & managed Kubernetes
- `http://localhost:8091/serverless.html` -- Serverless functions (Lambda / Functions) security
- `http://localhost:8091/ci-cd.html` -- CI/CD for cloud deployments
- `http://localhost:8091/cloud-soc.html` -- Cloud SOC & threat monitoring
- `http://localhost:8091/cloud-security-certifications.html` -- Certification comparison
- `http://localhost:8091/conferences.html` -- Conference directory
- `http://localhost:8091/ctfs.html` -- Cloud CTF directory
- `http://localhost:8091/breach-timeline.html` -- Breach kill chain index (per-breach pages in `breaches/`)
- `http://localhost:8091/threat-research.html` -- Cloud threat research source directory
- `http://localhost:8091/github-actions.html` -- GitHub Actions explainer
- `http://localhost:8091/code-of-conduct.html` -- Community standards
- `http://localhost:8091/privacy.html` -- Privacy policy

### Automated Checks (run by CI on your PR)

These run automatically when you push, but you can run them locally too:

```bash
# Check URLs for safety issues (phishing, suspicious patterns)
python3 tools/check_all_site_urls.py

# Validate a specific resource URL
python3 tools/check_url_safety.py "https://example.com/resource"

# Normalize URLs (strip tracking params, upgrade HTTP, resolve redirects)
# Dry run (preview changes):
python3 tools/normalize_urls.py
# Apply changes:
python3 tools/normalize_urls.py --apply
```

### Linting (run by `lint.yml` on every push/PR)

```bash
# One-time install (Homebrew on macOS; Linux: apt or pip equivalents)
brew install actionlint ruff yamllint shellcheck

# Lint GitHub Actions YAML + the inline shell inside each `run:` block
actionlint

# Lint Python (the housekeeping scripts in tools/ and the repo root)
ruff check .
ruff check --fix .   # auto-fix the easy stuff (unused imports, whitespace, etc.)

# Lint every YAML file (config in .yamllint.yml)
yamllint .
```

Configs: `pyproject.toml` (ruff) and `.yamllint.yml` (yamllint). All three commands should exit 0 before opening a PR.

---

## Common Contribution Recipes

### Adding a Resource

The fastest way:

```bash
python3 tools/submit_resource.py
```

This walks you through everything interactively. See [SUBMIT_RESOURCE_README.md](tools/SUBMIT_RESOURCE_README.md) for details.

### Adding a News Source

```bash
python3 tools/submit_news_source.py
```

See [SUBMIT_NEWS_SOURCE_README.md](tools/SUBMIT_NEWS_SOURCE_README.md) for details.

### Fixing a Typo or Content Issue

1. Find the file (e.g., `resources.html`)
2. Search for the text you want to fix
3. Edit, preview locally, commit, and push

### Modifying Styles

1. Edit `style.css`
2. Check both light and dark mode
3. Check at mobile, tablet, and desktop widths
4. The CI will auto-update SRI hashes on merge -- do not update them yourself

### Adding a Kill Chain

See [CONTRIBUTING_KILL_CHAINS.md](CONTRIBUTING_KILL_CHAINS.md) for the full process and HTML template.

### Adding a Glossary Term

1. Edit `glossary.html` and locate the right `<h2 id="...">` section.
2. Add a new `<dt>...</dt>` + `<dd>...</dd>` pair inside that section's `<dl class="glossary-list">`.
3. Run the cross-linker:

   ```bash
   python3 tools/crosslink_glossary.py
   ```

   It will give your new `<dt>` an `id="term-..."` slug, hyperlink any existing terms in your new definition, and hyperlink your new term wherever it's mentioned in other definitions. The script is idempotent and safe to re-run.

4. Run the **cross-page** linker to hyperlink the term wherever it's mentioned outside `glossary.html`:

   ```bash
   python3 tools/crosslink_pages.py
   ```

   Same idempotent behavior - strips and rebuilds every cross-page link. See [tools/CROSSLINK_PAGES_README.md](tools/CROSSLINK_PAGES_README.md).

5. If the term count crosses a round number (e.g. 200 → 250), update the search-bar placeholder and `<span id="visibleTerms">` count in `glossary.html`.

See [tools/CROSSLINK_GLOSSARY_README.md](tools/CROSSLINK_GLOSSARY_README.md) for more.

---

## SEO Conventions

The site is search-optimized for cloud-security queries. The conventions below are enforced manually - none of the build scripts validate them, so please follow them when adding pages or editing existing ones. Regressing them silently hurts ranking for "cloud security" terms.

### Page metadata

- **`<title>`** - pattern: `Topic - Cloud Security Office Hours` (or `Topic - CSOH` on shorter pages). Front-load the topic, keep it under ~60 chars.
- **`<meta name="description">`** - **strict 155-char limit** (Google truncates above ~155). Front-load "cloud security" + the page's distinct angle. Don't pad.
- **Canonical** - every page must have `<link rel="canonical" href="https://csoh.org/PAGE.html">`.
- **Open Graph / Twitter Card** - set both `og:title`/`og:description` and `twitter:title`/`twitter:description`. The OG description doesn't have the 155-char rule, but keep it tight.

### Headings

- **One `<h1>` per page.** Place it inside the hero (`<section class="hero hero--compact">` or `<section class="hero">`). The hero CSS already styles both `h1` and `h2` identically, so use `<h1>`.
- **The `<h1>` must include cloud-security keywords** - e.g. `Cloud Security Resources`, not `Resources`. The page title should match what someone would Google.
- **Do NOT put `<h1>` in the logo.** The logo is `<div class="logo-title">CSOH</div>` (a div, not a heading) - same on every page. Don't change this back to `<h1>`.
- **Subsequent headings** are `<h2>` (section heads), then `<h3>` (subsections). Don't skip levels - TOC blocks (`<div class="toc">`) must use `<h2>`, never `<h3>`, since they sit directly under the page `<h1>`.

### Images

Every `<img>` needs descriptive attributes - search engines and Core Web Vitals both care:

- **`alt`** - descriptive, never `alt="Preview"` or generic placeholders. For card thumbnails generated by `submit_resource.py` / `submit_ctf.py` / `update_news.py`, the alt is derived from the resource name automatically. If you hand-author a card, follow the same pattern: `alt="Resource Name preview"`.
- **`loading="lazy"`** on every below-the-fold image. The only exceptions are hero images (`class="hero-img"`), which should use `loading="eager"` so the LCP isn't deferred.
- **`decoding="async"`** on every image, including hero images.
- **`width` / `height`** attributes on hero images and any image with a known intrinsic size, to prevent CLS.
- **OG / social-card images** (`og:image`, `twitter:image`) must be the per-page `img/og/<page>.jpg` (1200×630) - never `banner.png` (1200×400, wrong aspect ratio for social cards).

### Adding a new page

When you add a new HTML page, do all of the following - none are automated:

1. Copy an existing page that's structurally similar (e.g., `what-is-cloud-security.html` for an article-style pillar page; `resources.html` for a card directory).
2. Write a < 155-char meta description, front-loaded with cloud-security keywords.
3. Use a `Topic - Cloud Security Office Hours` title.
4. Set `<link rel="canonical" href="https://csoh.org/yourpage.html">`.
5. Add a `BreadcrumbList` JSON-LD block (`Home > Your Page`).
6. Add a single keyword-rich `<h1>` in the hero.
7. **Add the page to `sitemap.xml`** (a new `<url>` block). `update_sitemap.py` only refreshes `<lastmod>` for entries already in the sitemap - it does not auto-discover new pages.
8. **Add the page to the nav** (`<ul class="dropdown-menu">` or mega-menu column) **on every existing HTML page**. The nav is duplicated per page, not shared - there is no shared template. Pick the right slot:

   - **Learn → Foundations** (mega-menu col) - orientation pages (what-is, shared responsibility, glossary, FAQ, vendor landscape)
   - **Learn → Topics** (mega-menu col) - discipline / platform reference pages (IAM, networking, K8s, etc.)
   - **Learn → Career & Growth** (mega-menu col) - careers, certs, learning path, home lab
   - **Resources** (top-level link) - the catalog
   - **By Cloud** (dropdown) - AWS / Azure / GCP / comparison hubs
   - **Threat Intel** (dropdown) - news, threat research, kill chains, SOC, detection engineering, IR, pentesting, CTFs
   - **Community** (mega-menu) - sessions, conferences, recaps, presentations, chat resources
   - **Behind the Scenes** (dropdown) - the dogfooded ops pages (Deploy to GCP, GitHub Actions) plus Contribute / Add a Resource

   The fastest way to apply changes site-wide is a small Python script - see `/tmp/update_nav_v3.py` from the May 2026 batch as a template. It uses regex to replace the mega-menu columns and dropdown `<ul>`s and re-applies `aria-current="page"` per file. Doing it by hand across 60+ pages is bug-prone (you'll inevitably drift on indent or aria attributes).
9. **Add the page to `TARGET_PAGES` in `tools/crosslink_pages.py`** so glossary terms get auto-linked across the new page. Then run:
   ```bash
   python3 tools/crosslink_pages.py
   ```
10. **If your new page has external `card-link` URLs** (resource cards with screenshots), add it to the `pages` list near the bottom of `tools/generate_preview.py` so the deploy workflow auto-generates preview images for those URLs.
11. **Add the page to the `PAGES` list in `tools/generate_og_images.py`** with a short title, subtitle, and badge, then run `python3 tools/generate_og_images.py --pages yourpage.html`. This produces a 1200×630 social-card JPG at `img/og/yourpage.jpg` and rewrites the page's `og:image`/`twitter:image` meta tags. Without this step the page falls back to `banner.png` (1200×400, wrong aspect ratio).
12. Update the file structure trees in `README.md` and `DEVELOPMENT.md`, and (if it's an educational/feature page) add a per-page section to `README.md` describing it.
13. Let CI regenerate SRI hashes (`update_sri.py` runs on deploy) or run it locally.
14. **Verify structural SEO**: run `python3 tools/run_seo_audit.py --dry-run` and check the new page doesn't introduce critical issues or warnings. The weekly cron will catch any regression on Monday and open a tracking issue, but local verification on your PR is faster.

### Cross-linking

- Inside the body of educational pages, link to the glossary, CTFs, breach kill chains, and pillar pages with **keyword-rich anchor text** ("cloud security CTF challenges", not "click here").
- The hub-and-spoke pattern matters for SEO: `what-is-cloud-security.html` is the hub; pillar pages, glossary, CTFs, breach kill chains, certifications, and learning path are spokes that link back to the hub. Don't break this when refactoring.

### Scripts that touch HTML are SEO-safe by design

`update_news.py`, `add_meeting.py`, `submit_resource.py`, `submit_ctf.py`, `update_presentations_schema.py`, `crosslink_glossary.py`, and `crosslink_pages.py` all modify *content regions* (cards, meeting entries, schema JSON, glossary `<dd>` blocks, inline term anchors) - they never rewrite `<title>`, `<meta name="description">`, or `<h1>` tags. If you add a new HTML-generating script, follow the same rule: leave page-level SEO metadata alone.

### Scripts must only write when content actually changes

Every script in `tools/` (and `update_sri.py`, `update_news.py` at the repo root) wraps its file writes in a `if content != original_content` check. Two reasons:

1. **Clean git history.** A no-op run produces no diff and no commits.
2. **Cheap downstream deploys.** `gcp-deploy.yml` triggers off the housekeeping commits this workflow produces. If your script `open(..., 'w')`s a file unconditionally, every run produces a no-op commit that pointlessly triggers a full container rebuild and Cloud Run revision deploy. Don't.

If your script needs to be sure it overwrote even an identical file (e.g., to re-run a destructive transformation), do that work explicitly - don't make it the default.

### Tracking SEO performance

Three complementary signals — codebase health, synthetic lab data, real-user truth. All three feed into `seo-audits/SCORECARD.md` (the first two automatically).

#### 1. The codebase scorecard — Internal SEO audit (this repo, auto-cron)

Lives in `seo-audits/SCORECARD.md` (top table). Updated automatically by `.github/workflows/run-seo-audit.yml` every **Monday at 14:15 UTC** (07:15 PT). The workflow runs `tools/run_seo_audit.py` — a deterministic structural checker that mirrors what the `/seo-audit` skill mechanically tests across every indexable HTML page in the repo: canonical, title 30–65 chars, meta description 100–165 chars, og:image ≠ banner.png, full Twitter Card, single H1, robots meta, JSON-LD presence, image alt coverage, `<html lang>`.

Each weekly run:
- Writes a per-day report to `seo-audits/YYYY-MM-DD.md`
- Appends a row to SCORECARD's Internal SEO audit table
- Opens a PR with `[skip ci]` (auto-merged — SCORECARD is a tracking artifact, not site content)
- Files a tracking issue if the overall score dropped vs the previous run

Run off-cycle locally with `python3 tools/run_seo_audit.py` (stdlib-only, no deps). See [tools/RUN_SEO_AUDIT_README.md](tools/RUN_SEO_AUDIT_README.md). For qualitative depth (internal-linking strategy, content depth, AI visibility) that the deterministic script can't reason about, invoke `/seo-audit` from Claude Code manually.

What this catches: missing meta tags, broken JSON-LD, generic alt text, heading-hierarchy skips, OG-image regressions, stale `<meta>` content. What it can't see: actual rankings or real-user performance — that's signals #2 and #3 below.

#### 1b. PageSpeed Insights — Synthetic lab scores (this repo, auto-cron)

Lives in the same `seo-audits/SCORECARD.md` (second table). Updated automatically by `.github/workflows/check-pagespeed.yml` every **Monday at 14:00 UTC** (15 min before the Internal audit, so the two SCORECARD updates land as separate PRs). The workflow runs `tools/check_pagespeed.py` which hits Google's PageSpeed Insights v5 API — mobile + desktop in parallel — pulls the 4 category scores (Performance / Accessibility / Best Practices / SEO), lab Core Web Vitals (LCP, CLS, TBT, FCP, Speed Index), and a list of any audit IDs that scored < 100 with their failing DOM nodes.

Requires `PSI_API_KEY` in repo secrets (free key from <https://console.cloud.google.com/apis/credentials> with restriction "PageSpeed Insights API"). Run locally with `export PSI_API_KEY=… && python3 tools/check_pagespeed.py`. See [tools/CHECK_PAGESPEED_README.md](tools/CHECK_PAGESPEED_README.md).

What this catches: synthetic Lighthouse regressions — color-contrast failures, image-alt gaps, render-blocking resources, third-party script issues (CSP violations get surfaced as console errors and dock Best Practices). What it can't see: real-user variance — that's signal #2.

#### 2. Google Search Console (external truth)

<https://search.google.com/search-console> → property `csoh.org` (verified via `google66d489593949bd4c.html` in the repo root).

Four reports to check on a recurring cadence:

| Report | Path | Cadence | What to do |
|---|---|---|---|
| **Performance** | Reports → Performance → Search results | Weekly | Set comparison to "Last 28 days vs previous period." Sort queries by impressions. Pages in positions 5-15 with cloud-security terms = your low-hanging-fruit list for content tweaks. High impressions + low CTR = improve title/meta description. |
| **Pages (Indexing)** | Indexing → Pages | After every deploy | Confirm nothing landed in "Page with redirect" (the recurring `.htaccess` gotcha) or "Crawled - currently not indexed." Anything in "Excluded by 'noindex' tag" should match what we deliberately noindex (`chat-resources.html`). |
| **Sitemaps** | Indexing → Sitemaps | One-time submit | Submit `https://csoh.org/sitemap.xml` once. After that GSC shows submitted-vs-indexed gap automatically. |
| **Core Web Vitals** | Experience → Core Web Vitals | Monthly | Real Chrome user data (CrUX). LCP < 2.5s, INP < 200ms, CLS < 0.1. This is the data the codebase audit can't see - only real users generate it. |

**Set up GSC email alerts** under Settings → Email preferences. GSC will email you when coverage drops or new errors appear.

After every deploy that touches HTML structure or `.htaccess`, spot-check live URLs in the **URL Inspection** tool (top search bar in GSC) - paste a URL, click "Request Indexing" if you want Google to re-crawl sooner than its default cadence (~days).

#### When the signals disagree

- **Codebase scorecard says 100, PSI says a category dropped** → something at the live-site layer is being injected or rewritten that the source HTML doesn't reflect. Common culprits: Cloudflare Browser Insights injecting a beacon script (caught and disabled 2026-05-23 — Accessibility 100 → 96 was a `color-contrast` regression on `.card-action` links, surfaced because PSI tests the rendered page); Cloudflare's "Managed robots.txt" appending `Content-Signal:` directives Lighthouse's parser doesn't recognize.

- **Codebase scorecard says 100, GSC says traffic dropped** → something at the server/CDN/redirect layer is undoing what the HTML claims. That's how we caught the `.htaccess` `meetings.html → sessions.html` stale redirect: HTML had the right canonical, but the live site was 301'ing away from it.

Always trust the live-site signals (PSI + GSC) over the codebase scorecard. The codebase scorecard tells you what *should* be true; PSI and GSC tell you what *is* true.

---

## File Reference

| File | What it does | When to edit |
|------|-------------|--------------|
| `style.css` | All site styles | Changing appearance or layout |
| `main.js` | Search, filters, dark mode, interactions | Changing site behavior |
| `resources.html` | Resource cards and categories | Adding/editing resources |
| `news.html` | News article display | **Don't edit** -- auto-generated |
| `feed.xml` | RSS feed | **Don't edit** -- auto-generated |
| `update_news.py` | News feed aggregation script | Adding/removing RSS sources |
| `tools/normalize_urls.py` | URL normalizer (tracking params, HTTPS upgrade, redirects) | **Don't edit** -- runs in CI |
| `tools/check_all_site_urls.py` | Site-wide URL safety scanner | Running local safety audits |
| `tools/update_sitemap.py` | Refreshes `<lastmod>` dates in `sitemap.xml` from git history | **Don't edit** -- runs in CI and alongside `update_news.py` |
| `tools/update_presentations_schema.py` | Regenerates `VideoObject` JSON-LD on `presentations.html` | **Don't edit** -- runs in CI on every deploy |
| `tools/crosslink_glossary.py` | Adds `id="term-..."` to glossary `<dt>`s and hyperlinks every term mention in `<dd>`s | Run after adding/editing glossary entries |
| `tools/crosslink_pages.py` | Hyperlinks first occurrence of each glossary term across all content pages | Run after adding/editing glossary entries (or after adding a new content page) |
| `glossary.html` | Cloud-security glossary (300+ terms) with live search and cross-linked definitions | Adding/editing terms; run `crosslink_glossary.py` *and* `crosslink_pages.py` after |
| `glossary.js` | Live search/filter for `glossary.html` | Changing search behavior |
| `meetings.js` | Filters + auto-detected speaker filter for `meetings.html` | Adding new recurring speakers (`SPEAKERS` list) |
| `sitemap.xml` | XML sitemap for search engines | **Don't edit** -- lastmod refreshed automatically |
| `update_sri.py` | SRI hash generator (handles main.js, style.css, chat-resources.js, breach-timeline.css, breach-timeline.js, meetings.js, glossary.js) | **Don't edit** -- runs in CI |
| `.htaccess` | Apache server config (security headers, caching, compression) | Server configuration changes |
| `nginx.conf` | Nginx server config (Docker deployments) | Server configuration changes |

---

## Troubleshooting

**Server won't start: `Address already in use`**
```bash
# Use a different port
python3 -m http.server 8092
```

**Changes not showing up**
- Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
- Or open in an incognito/private window

**Python not found**
- Try `python` instead of `python3`
- Install from [python.org](https://python.org) if needed

**Git push rejected**
- Make sure you're on a feature branch, not `main`
- Pull latest: `git pull origin main` then rebase your branch

---

## Need Help?

- **Contributing guide:** [CONTRIBUTING.md](CONTRIBUTING.md)
- **Resource submissions:** [CONTRIBUTING_RESOURCES.md](CONTRIBUTING_RESOURCES.md)
- **Kill chains:** [CONTRIBUTING_KILL_CHAINS.md](CONTRIBUTING_KILL_CHAINS.md)
- **Mailing list:** [Sign up](https://csoh.kit.com/39feb4f397) to get the Friday Zoom link and bring questions live
