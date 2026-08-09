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
├── cspm-vs-cwpp.html                # Posture vs workload protection, head to head
├── cnapp-vs-xdr.html                # Where CNAPP ends and XDR/CDR begins
├── vendor-landscape.html            # 360+ cloud-security vendors across 30 categories
├── glossary.html                    # 310 cloud-security terms with live search + cross-links
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
├── non-human-identity.html          # NHI: service accounts, keys, tokens, AI agents
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
├── breach-lessons.html              # Cross-incident synthesis of recurring root causes
├── cloud-breach-year-in-review-2025.html # The breaches that defined 2025
├── kevin-mitnick.html               # Special resource page
├── ctfs.html                        # Cloud CTF directory
│
│  ── Governance + AI ──
├── grc.html                         # Governance, Risk, Compliance for cloud
├── compliance-frameworks.html       # SOC2 / ISO / PCI / HIPAA / FedRAMP / CMMC / GDPR deep dives
├── ai-learning.html                 # Using AI to LEARN cloud security
├── ai-ml-security.html              # Securing AI workloads (OWASP LLM Top 10, ATLAS)
├── mcp-security.html                # Securing the Model Context Protocol
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
├── cloud-security-<role>.html       # 12 role-in-depth pages (engineer, architect, iam-architect,
│                                    #   appsec, cnapp-analyst, detection, IR, pentest, platform,
│                                    #   grc, sales-engineer, customer-success-engineer)
├── breaking-into-cloud-security.html # Help desk → cloud security, the realistic version
├── cloud-security-interview-questions.html # Interview questions with model answers
├── cloud-security-resume-guide.html # Resume structure and phrasing
├── cloud-security-home-lab.html     # Free-tier setups, budget guardrails, kill-switches
├── cloud-security-certifications.html # CCSK / CCSP / AWS / Azure / GCP / CKS comparison
├── cloud-security-portfolio-projects.html # Hub for 7 portfolio walkthroughs (in `portfolio/`)
├── mentorship.html                  # Community mentorship program
├── cloud-security-reading-list.html # Curated books / blogs / people-to-follow
├── community.html                   # Community & Signal chat
├── conferences.html                 # Security & hacker conferences directory
│
│  ── Sessions / news / archives ──
├── sessions.html                    # Weekly Zoom session info
├── speakers.html                    # Guest speaker archive
├── present.html                     # How to pitch a talk
├── meetings.html                    # Weekly meeting recaps → `meetings/`
├── presentations.html               # Recorded presentation archive
├── chat-resources.html              # Community-shared URLs from Zoom chat
├── resources.html                   # 415 curated resources (largest page; auto-refreshed weekly)
├── news.html                        # Auto-generated news articles
├── rss.html                         # RSS subscription landing page (feed.xml + recaps.xml)
├── what-practitioners-think.html    # Session-digest hub → 5 per-topic digests
│
│  ── Behind the scenes ──
├── github-actions.html              # Learn-by-example GitHub Actions explainer
├── cloud-deployment.html            # How CSOH deploys across AWS + GCP + Azure (3 origins, Cloudflare edge, keyless OIDC)
├── terraform.html                   # Learn-by-example Terraform explainer (infra/terraform/)
├── version-control.html             # Git & version-control fundamentals via this repo
├── how-csoh-org-is-secured.html     # The site's own security model, end to end
├── contribute.html                  # How to contribute
├── contribute-resources.html        # Resource submission form
│
│  ── Search ──
├── search.html                      # MiniSearch-powered full-text search
├── search.css                       # Search page styles (extracted from inline for CSP)
├── search-init.js                   # Search frontend: index load, MiniSearch wiring, render
├── search-synonyms.json             # Acronym → expansion map (NHI, CIEM, IRSA, …)
├── search-index.json                # Static JSON index (generated at deploy time)
├── vendor/minisearch-7.1.2.min.js   # Self-hosted MiniSearch library (SRI-pinned)
├── tools/build_search_index.py      # Builds search-index.json from all .html files
│
│  ── Policy / about ──
├── about.html                       # About CSOH: mission and ethos
├── about-shawn-nunley.html          # Author/E-E-A-T page
├── code-of-conduct.html
├── privacy.html
├── security-policy.html
├── 403.html / 404.html              # Custom error pages (404.js powers "did you mean")
│
│  ── Per-breach pages and meeting recaps ──
├── breaches/                        # 20 per-breach kill chain pages (split from breach-timeline.html)
├── meetings/                        # 105 per-meeting recap pages (split from meetings.html)
├── portfolio/                       # 7 per-project portfolio walkthroughs
├── homelab/                         # 4 command-line home-lab walkthroughs (not search-indexed)
│
│  ── Shared assets ──
├── style.css                        # All site styles (includes dark mode)
├── main.js                          # Search, filtering, sorting, dark mode toggle
├── chat-resources.js                # Chat-resources page-specific JS
├── meetings.js                      # Meeting recaps filtering + speaker filter
├── glossary.js                      # Glossary page live search
├── breach-timeline.css / .js        # Breach timeline page-specific assets
├── vendor/                          # Self-hosted third-party JS (MiniSearch, GoatCounter),
│                                    #   SRI-pinned; goatcounter-count.js is locally patched
│                                    #   - read vendor/README.md before re-vendoring
│
├── tools/                  # Python automation scripts (URL safety, normalization, previews, sitemap, presentations schema, glossary cross-linking, OG image generation incl. meeting variant, meeting → topic-page link injection, live edge-header verification)
├── .github/workflows/      # CI/CD pipelines (15 workflows: update-news, update-resources, update-counts, deploy, normalize-urls, check-broken-links, check-url-safety, check-pagespeed, check-reading-list-staleness, check-meeting-staleness, check-conference-staleness, run-seo-audit, validate-html, lint, site-update-deploy)
└── update_news.py          # News aggregation from 62 RSS feeds
```

### Workflows at a Glance

Every workflow has its own header banner - but if you just want to know "what runs when, and what does it touch," this is the one-screen version. Group by purpose, not alphabetical. Times are UTC; the auto-merge column shows whether the workflow can push to `main` without human review.

**Content automation (writes to site)**

| Workflow | When | What it does | Auto-merges? |
| --- | --- | --- | --- |
| [`update-news.yml`](.github/workflows/update-news.yml) | every 3h | Pulls 62 RSS/Atom feeds, rewrites `news.html`, `feed.xml`, `sitemap.xml`; opens a PR | Yes, if diff is news files only |
| [`update-resources.yml`](.github/workflows/update-resources.yml) | Mon 14:00 | `claude-code-action` adds 2-3 fresh entries to each section of `resources.html`; opens a PR. Runs on a tool allowlist with no interpreter on it | Yes, if diff is `resources.html` only |
| [`normalize-urls.yml`](.github/workflows/normalize-urls.yml) | 1st of month, 08:00 | Strips tracking params, upgrades http→https, follows redirects; opens a PR | No - auto-approved, human merges |
| [`site-update-deploy.yml`](.github/workflows/site-update-deploy.yml) | push to `main` on site files | Chained housekeeping commits: SRI hashes, URL safety, normalization, sitemap, OG previews | N/A - commits directly |
| [`update-counts.yml`](.github/workflows/update-counts.yml) | Mon 07:30 | Recomputes every site count (JSON-LD `numberOfItems`, OG-card subtitles) from the real cards and refreshes the count share-cards | N/A - commits directly |

**Deploy**

| Workflow | When | What it does | Auto-merges? |
| --- | --- | --- | --- |
| [`deploy.yml`](.github/workflows/deploy.yml) | push to `main` on site files | Builds once, fans out to publish active/active to AWS (S3+CloudFront), GCP (Cloud Run, Trivy-scanned container), and Azure (Blob `$web`); keyless OIDC per cloud. The final `purge-cloudflare` job clears the edge, then asserts the live site against the repo: SRI hashes, and (via `tools/check_edge_headers.py`) the security headers | N/A - direct deploy |

**PR quality gates (block or warn)**

| Workflow | When | What it does | Blocks PR? |
| --- | --- | --- | --- |
| [`lint.yml`](.github/workflows/lint.yml) | every push + PR | `actionlint` + `ruff` + `yamllint` in parallel | Yes |
| [`validate-html.yml`](.github/workflows/validate-html.yml) | push/PR on `*.html` + Mon 07:00 | W3C HTML5 validator on every `.html` file | Yes, with PR comment |
| [`check-url-safety.yml`](.github/workflows/check-url-safety.yml) | PRs on `*.html` + Mon 06:30 | Flags phishing patterns, suspicious TLDs, shortener domains | Yes |
| [`check-broken-links.yml`](.github/workflows/check-broken-links.yml) | PRs on `*.html` + Mon 06:00 | Lychee crawl of every link; PR comment on failures | No - link rot is everywhere |

**Periodic audits (report-only, never edits the site)**

| Workflow | When | What it does | Where the report lands |
| --- | --- | --- | --- |
| [`check-pagespeed.yml`](.github/workflows/check-pagespeed.yml) | Mon 14:00 | Google PageSpeed Insights (mobile + desktop) | Appends row to `seo-audits/SCORECARD.md`; opens issue on regression |
| [`run-seo-audit.yml`](.github/workflows/run-seo-audit.yml) | Mon 14:15 | Structural SEO check across every indexable page (counted at runtime) | Appends row to `seo-audits/SCORECARD.md`; opens issue on regression |
| [`check-reading-list-staleness.yml`](.github/workflows/check-reading-list-staleness.yml) | 1st of month, 07:00 | RSS-feed staleness check on `cloud-security-reading-list.html` | Opens or refreshes a sticky issue labeled `reading-list-staleness` |
| [`check-meeting-staleness.yml`](.github/workflows/check-meeting-staleness.yml) | Mon 15:00 | Checks the newest meeting recap isn't older than the threshold | Opens or refreshes a sticky issue labeled `meeting-staleness` |
| [`check-conference-staleness.yml`](.github/workflows/check-conference-staleness.yml) | 1st of month, 14:00 | Flags "Next:" dates on `conferences.html` that have already passed | Opens or refreshes a sticky issue labeled `conference-staleness` |

A few patterns worth knowing before you touch any of these:

- **App token vs PAT.** Writes (push, PR, approve, merge) use a `csoh-ci` GitHub App installation token, not the auto-injected `GITHUB_TOKEN` - App tokens can trigger downstream workflows on the PRs they create. `CSOH_PAT` is a separate fine-grained PAT used *only* to approve the bot's own PRs, since GitHub blocks self-approval and auto-merge doesn't honor the ruleset bypass list for the approval requirement. See the comments in `update-news.yml` for the full story.
- **Auto-merge safety valve.** Workflows that auto-merge always check that the diff is restricted to a known set of files. If the bot touches anything outside that set, the PR stays open for a human.
- **Pinned action SHAs.** All `uses:` references pin to a full commit SHA with the version as a trailing comment (`@de0fac…  # v6.0.2`). Don't replace these with tag refs.
- **`permissions:` is `contents: read` unless a step really uses the ambient token.** Every write here (push, PR, approve, merge) goes through the App token or `CSOH_PAT`, both passed explicitly to the step that needs them, so the auto-injected `GITHUB_TOKEN` almost never needs a write scope. `normalize-urls.yml` carried `contents: write` + `pull-requests: write` that no step ever used; it is `contents: read` now, matching every other workflow in the repo. The extra scopes on `check-broken-links.yml`, `check-url-safety.yml`, and `validate-html.yml` (`pull-requests: write`) and on the three staleness workflows (`issues: write`) are real - those steps comment on PRs and manage sticky issues with the default token.
- **`persist-credentials: false` on any checkout handed a write-scoped token.** `actions/checkout` defaults to leaving the token it was given in `.git/config` as an `http.extraheader`, readable by every later step in the job with a plain file read. Set `persist-credentials: false` whenever nothing after the clone talks to git over the network - which is the normal case here, since `peter-evans/create-pull-request` is passed the token directly. It is already set in `update-resources.yml` (the job that runs a model over fetched web pages) and in `deploy.yml`'s `purge-cloudflare` checkout.

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
- The self-hosted third-party files in `vendor/` are SRI-hashed too, but not identically: `vendor/goatcounter-count.js` is in `update_sri.py`'s `ASSETS` list and is re-stamped automatically, while `vendor/minisearch-7.1.2.min.js` carries a hand-stamped `integrity` in `search.html` and no `?v=` cache-bust (the file is pinned to a version and never regenerated). `goatcounter-count.js` is also **not** a pristine upstream copy - it carries two local patches. See [vendor/README.md](vendor/README.md) before you touch or re-vendor anything in that directory

**News Aggregation**
- `update_news.py` pulls from 62 RSS/Atom feeds every 3 hours (via GitHub Actions)
- Generates `news.html` and `feed.xml`, regenerates the `NewsArticle` JSON-LD block on `news.html`, and refreshes `sitemap.xml` lastmod dates
- Preserves cards already on `news.html` across runs so today-dated items don't disappear when RSS feeds rotate
- PRs are auto-created and auto-merged if only `news.html`, `feed.xml`, and `sitemap.xml` changed

**Reading List Staleness Check** (`.github/workflows/check-reading-list-staleness.yml`)
- 1st of each month at 07:00 UTC, `tools/check_reading_list_staleness.py` walks every newsletter / blog / podcast / YouTube channel on `cloud-security-reading-list.html`, discovers each site's RSS or Atom feed (via `<link rel="alternate">` first, then probing common paths), and flags any whose newest entry is older than 180 days
- The reading list is hand-curated; the workflow **never edits the page**. It uploads a markdown report as an artifact and opens-or-updates a sticky GitHub issue (labeled `reading-list-staleness`) so a human can decide what to drop, replace, or keep
- Broken-link detection on the same page is already covered by `check-broken-links.yml`; this workflow exists to surface sources that are still reachable but no longer publishing - which lychee can't see
- See [tools/CHECK_READING_LIST_STALENESS_README.md](tools/CHECK_READING_LIST_STALENESS_README.md) for the discovery rules and known limitations

**Resources Auto-Refresh** (`.github/workflows/update-resources.yml`)
- Mondays at 14:00 UTC, `anthropics/claude-code-action@v1` invokes Claude with a structured prompt to research and add 2-3 new resources to each of the six `resources.html` sections (CTF, Labs, Tools, Certs, AI Security, Job Search)
- Auth: `CLAUDE_CODE_OAUTH_TOKEN` (subscription quota, not API billing) + the `csoh-ci` GitHub App for write-scoped PRs + `CSOH_PAT` to approve the bot's own PR so auto-merge can satisfy the "1 required approval" rule
- The model checks for duplicates by grepping for URL + name before adding, follows the existing resource-card HTML pattern, and bumps the `<span id="visibleCount">` counter
- **Auto-merge only fires when the diff is purely `resources.html`.** If Claude touches anything else, the PR stays open with a banner asking for human review - important safety valve
- **The `--allowedTools` list must not contain any shell entry.** It is currently `Read,Edit,Glob,Grep,WebSearch,WebFetch` - every entry an in-process tool, no `Bash(...)` pattern of any kind. Two removals got it there. `Bash(python3:*)` went first: that pattern matches `python3 -c '<anything>'`, which is arbitrary code execution and makes the rest of the allowlist decorative. `Bash(grep:*)` and `Bash(wc:*)` went second, and that is the less obvious lesson - `grep` takes a path like nearly every Unix command, so `Bash(grep:*)` was a read primitive over the entire runner filesystem including `/proc/self/environ`. The built-in `Grep` tool that remains searches the checked-out workspace and is not a shell. This step reads pages it does not control (`WebFetch` / `WebSearch`) in a job that also holds `id-token: write` and the `csoh-ci` App token, so a prompt injection in a fetched page is a realistic path to those credentials. If a future prompt genuinely needs Python, add a checked-in script to `tools/` and allowlist that exact path - never the interpreter
- **The `csoh-ci` App token is minted *after* the Claude step, not before it.** The mint step sits immediately above `create-pull-request`, so the repo-write credential does not exist on the runner while the model is reading the open web. Moving it to the top of the job, which is where mint steps usually go, silently removes that protection
- **The job's `actions/checkout` sets `persist-credentials: false`** so the App token isn't left in `.git/config` for the model's step to read. This is safe because `peter-evans/create-pull-request` is handed the token explicitly. Don't drop it while re-arranging the job
- Preview images for newly-added cards are generated post-merge by `site-update-deploy.yml`

**Site-wide Search** (`search.html`, MiniSearch)
- `tools/build_search_index.py` walks every `.html` file at repo root at deploy time and emits one entry per `<section id="…">` plus one per glossary `<dt id="term-…">` to `search-index.json` (~3.4MB raw, ~1.0MB gzipped)
- The index ships with the static site; `search-init.js` lazy-loads it on first keystroke and feeds it into [MiniSearch](https://lucaong.github.io/minisearch/) (self-hosted at `vendor/minisearch-*.min.js` with SRI)
- `search-synonyms.json` provides acronym ↔ expansion mappings (`NHI ↔ non-human identity`, `CIEM ↔ cloud infrastructure entitlement management`, etc.) - expanded at both index-time and query-time so `NHI` matches docs that only spell out "non-human identity" and vice versa
- Results return with section anchors (`iam.html#nhi`), grouped by URL, with a "+ N more sections on this page" sublist when multiple sections of one page match
- `search.css`, `search-init.js`, and the vendored MiniSearch are external files (not inline) because the site's strict Content-Security-Policy blocks inline styles and scripts; CSP is `script-src 'self'` with no `unsafe-eval`, no `unsafe-inline`, no `wasm-unsafe-eval`
- The search page has a 60-second `Cache-Control` cap so CSS tweaks propagate fast during iteration
- To add a new acronym/alias: edit `search-synonyms.json`, run `python3 tools/build_search_index.py`, ship

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
# CI adds `--cache tools/url_resolution_cache.json` so it only re-resolves new
# URLs. Don't pass --cache locally or commit the cache - it's CI-seeded and
# redirect resolution is IP-dependent.
```

The three structural gates below run inside `validate-html.yml` alongside the W3C
validator and **fail** the PR. They are stdlib-only and take about a second each:

```bash
python3 tools/check_no_inline_scripts.py  # the strict CSP forbids inline <script>
python3 tools/check_svg_dimensions.py     # width/height on every <svg> with a viewBox
python3 tools/check_jsonld.py             # every ld+json block must parse
```

Three more checks run post-merge rather than on the PR, but are worth running
locally if you touched what they cover:

```bash
python3 tools/check_news_banners.py    # site-update-deploy.yml: every news source has a banner
python3 tools/sync_counts.py --check   # update-counts.yml: no count on the site may lie
python3 tools/check_edge_headers.py    # deploy.yml: the live security headers match rules.tf
```

The last one asserts against the **live site**, not the working tree, so it will
report whatever is deployed right now. That is the point: the Cloudflare ruleset
it checks is pinned with `ignore_changes = [rules]`, so a header edited in Git
can pass `terraform apply` without ever reaching the edge. See the `File
Reference` entry below.

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

### Updating a Vendored Library (`vendor/`)

Read [vendor/README.md](vendor/README.md) first. Two things there are easy to
undo by accident:

1. **`vendor/goatcounter-count.js` is patched.** Two lines are changed from
   upstream so the analytics beacon stops transmitting the query string
   (`q: location.search` → `q: ''`, and `get_path()` returns `loc.pathname`
   instead of `loc.pathname + loc.search`). Without them, a shared
   `/search.html?q=<term>` URL sends the visitor's search term to
   `csoh.goatcounter.com`, which contradicts what `privacy.html` and `llms.txt`
   promise. Both edits are marked in the source with a `CSOH LOCAL MODIFICATION`
   comment. **Dropping a newer upstream release over the file silently reverts
   them** - re-apply the modifications as part of the same commit.
2. **Re-run the SRI stamper afterward**, or every page will ask for a hash the
   file no longer has and the browser will refuse to execute it:

   ```bash
   python3 update_sri.py
   ```

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

   - **Learn** (6-column mega-menu):
     - **Foundations** - orientation pages (what-is, shared responsibility, CSPM vs CNAPP, best practices, vendor landscape, glossary, FAQ)
     - **By Cloud** - AWS / Azure / GCP hubs and the AWS-vs-Azure-vs-GCP comparison
     - **Workloads & Platform** - containers, Kubernetes, serverless, service mesh, CI/CD, landing zones
     - **Security Domains** - IAM, NHI, zero trust, network, data, vuln mgmt, API, SaaS
     - **Governance & AI** - backup/DR, threat modeling, GRC, compliance, AI learning, AI/ML security, MCP security
     - **Build It** - the dogfooded ops pages (Multi-Cloud Deploy, GitHub Actions, Terraform, Git & Version Control)
   - **Resources** (top-level link) - the catalog
   - **Threat Intel** (dropdown) - news, threat research, kill chains, SOC, detection engineering, IR, pentesting, CTFs
   - **Careers** (3-column mega-menu) - Getting Started / Engineering Roles / Specialist & Field Roles
   - **Community** (3-column mega-menu) - Live (sessions, Signal, mentorship, conferences, present) / Archive (recaps, session digests, presentations, speakers, chat resources) / Connect (contact, mailing list, GitHub, RSS, contribute)

   Session-digest pages (`what-practitioners-think-*.html`) sit as `mega-featured` entries inside the column of the topic they belong to, not in a section of their own.

   The canonical nav **and** footer are generated by `tools/sync_chrome.py` - edit `CANON_NAV` / `CANON_FOOTER` there, then run `python3 tools/sync_chrome.py` from the repo root. It regenerates `<nav>` and `<footer>` on all ~233 pages (root + `breaches/` + `meetings/` + `portfolio/` + `homelab/`), handles `../` prefixes for subdirectories, re-applies `aria-current="page"` + active dropdown state per file, and is idempotent (confirm exactly one nav + one footer variant afterward). Editing by hand is bug-prone (you'll drift on indent or aria attributes), so always use the script - and never run the removed `sync_navs.py` / `redesign_nav.py` / `unify_footer.py`, which encoded an older nav and would clobber the current one.
9. **Add the page to `TARGET_PAGES` in `tools/crosslink_pages.py`** so glossary terms get auto-linked across the new page. Then run:
   ```bash
   python3 tools/crosslink_pages.py
   ```
   Only root-level pages are listed explicitly; `breaches/*.html` and `meetings/*.html` are auto-discovered via `SUBDIR_PATTERNS`. `portfolio/` and `homelab/` are deliberately **not** cross-linked - if you add a third subdirectory that should be, add its glob there.
10. **If your new page has external `card-link` URLs** (resource cards with screenshots), add it to the `pages` list near the bottom of `tools/generate_preview.py` so the deploy workflow auto-generates preview images for those URLs.
11. **Add the page to the `PAGES` list in `tools/generate_og_images.py`** with a short title, subtitle, and badge, then run `python3 tools/generate_og_images.py --pages yourpage.html`. This produces a 1200×630 social-card JPG at `img/og/yourpage.jpg` and rewrites the page's `og:image`/`twitter:image` meta tags. Without this step the page falls back to `banner.png` (1200×400, wrong aspect ratio).
12. **Rebuild the search index** so the page is findable at `/search.html`:
    ```bash
    python3 tools/build_search_index.py
    ```
    Root-level pages are picked up automatically (minus `EXCLUDE_FILES`); `breaches/` and `meetings/` are indexed page-level via `SUBDIR_TYPES`. `portfolio/` and `homelab/` are intentionally excluded.
13. **Re-sync the site chrome and counts**:
    ```bash
    python3 tools/sync_chrome.py     # nav + header buttons + footer
    python3 tools/sync_counts.py     # numberOfItems, count markers, OG subtitles
    ```
    `sync_counts.py --check` is what CI runs; a mismatch fails the build.
14. Update the file structure trees in `README.md` and `DEVELOPMENT.md`, and (if it's an educational/feature page) add a per-page section to `README.md` describing it.
15. Let CI regenerate SRI hashes (`update_sri.py` runs on deploy) or run it locally.
16. **Run the local CI gates** before you push - these all block the PR:
    ```bash
    python3 tools/check_jsonld.py            # every JSON-LD block must parse
    python3 tools/check_no_inline_scripts.py # the CSP forbids inline <script>
    python3 tools/check_svg_dimensions.py    # width/height on every <svg> with a viewBox
    python3 tools/check_all_site_urls.py     # URL safety
    ```
17. **Verify structural SEO**: run `python3 tools/run_seo_audit.py --dry-run` and check the new page doesn't introduce critical issues or warnings. The weekly cron will catch any regression on Monday and open a tracking issue, but local verification on your PR is faster.

### Cross-linking

- Inside the body of educational pages, link to the glossary, CTFs, breach kill chains, and pillar pages with **keyword-rich anchor text** ("cloud security CTF challenges", not "click here").
- The hub-and-spoke pattern matters for SEO: `what-is-cloud-security.html` is the hub; pillar pages, glossary, CTFs, breach kill chains, certifications, and learning path are spokes that link back to the hub. Don't break this when refactoring.

### Scripts that touch HTML are SEO-safe by design

`update_news.py`, `add_meeting.py`, `submit_resource.py`, `submit_ctf.py`, `update_presentations_schema.py`, `crosslink_glossary.py`, and `crosslink_pages.py` all modify *content regions* (cards, meeting entries, schema JSON, glossary `<dd>` blocks, inline term anchors) - they never rewrite `<title>`, `<meta name="description">`, or `<h1>` tags. If you add a new HTML-generating script, follow the same rule: leave page-level SEO metadata alone.

### Scripts must only write when content actually changes

Every script in `tools/` (and `update_sri.py`, `update_news.py` at the repo root) wraps its file writes in a `if content != original_content` check. Two reasons:

1. **Clean git history.** A no-op run produces no diff and no commits.
2. **Cheap downstream deploys.** `deploy.yml` triggers off the housekeeping commits this workflow produces. If your script `open(..., 'w')`s a file unconditionally, every run produces a no-op commit that pointlessly triggers a full three-cloud rebuild and publish. Don't.

If your script needs to be sure it overwrote even an identical file (e.g., to re-run a destructive transformation), do that work explicitly - don't make it the default.

### Tracking SEO performance

Three complementary signals - codebase health, synthetic lab data, real-user truth. All three feed into `seo-audits/SCORECARD.md` (the first two automatically).

#### 1. The codebase scorecard - Internal SEO audit (this repo, auto-cron)

Lives in `seo-audits/SCORECARD.md` (top table). Updated automatically by `.github/workflows/run-seo-audit.yml` every **Monday at 14:15 UTC** (07:15 PT). The workflow runs `tools/run_seo_audit.py` - a deterministic structural checker that mirrors what the `/seo-audit` skill mechanically tests across every indexable HTML page in the repo: canonical, title 30-65 chars, meta description 100-165 chars, og:image ≠ banner.png, full Twitter Card, single H1, robots meta, JSON-LD presence, image alt coverage, `<html lang>`.

Each weekly run:
- Writes a per-day report to `seo-audits/YYYY-MM-DD.md`
- Appends a row to SCORECARD's Internal SEO audit table
- Opens a PR (auto-merged) - the deploy workflows' path filters exclude `seo-audits/`, so SCORECARD-only changes don't trigger a build
- Files a tracking issue if the overall score dropped vs the previous run

Run off-cycle locally with `python3 tools/run_seo_audit.py` (stdlib-only, no deps). See [tools/RUN_SEO_AUDIT_README.md](tools/RUN_SEO_AUDIT_README.md). For qualitative depth (internal-linking strategy, content depth, AI visibility) that the deterministic script can't reason about, invoke `/seo-audit` from Claude Code manually.

What this catches: missing meta tags, broken JSON-LD, generic alt text, heading-hierarchy skips, OG-image regressions, stale `<meta>` content. What it can't see: actual rankings or real-user performance - that's signals #2 and #3 below.

#### 1b. PageSpeed Insights - Synthetic lab scores (this repo, auto-cron)

Lives in the same `seo-audits/SCORECARD.md` (second table). Updated automatically by `.github/workflows/check-pagespeed.yml` every **Monday at 14:00 UTC** (15 min before the Internal audit, so the two SCORECARD updates land as separate PRs). The workflow runs `tools/check_pagespeed.py` which hits Google's PageSpeed Insights v5 API - mobile + desktop in parallel - pulls the 4 category scores (Performance / Accessibility / Best Practices / SEO), lab Core Web Vitals (LCP, CLS, TBT, FCP, Speed Index), and a list of any audit IDs that scored < 100 with their failing DOM nodes.

Requires `PSI_API_KEY` in repo secrets (free key from <https://console.cloud.google.com/apis/credentials> with restriction "PageSpeed Insights API"). Run locally with `export PSI_API_KEY=… && python3 tools/check_pagespeed.py`. See [tools/CHECK_PAGESPEED_README.md](tools/CHECK_PAGESPEED_README.md).

What this catches: synthetic Lighthouse regressions - color-contrast failures, image-alt gaps, render-blocking resources, third-party script issues (CSP violations get surfaced as console errors and dock Best Practices). What it can't see: real-user variance - that's signal #2.

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

- **Codebase scorecard says 100, PSI says a category dropped** → something at the live-site layer is being injected or rewritten that the source HTML doesn't reflect. Common culprits: Cloudflare Browser Insights injecting a beacon script (caught and disabled 2026-05-23 - Accessibility 100 → 96 was a `color-contrast` regression on `.card-action` links, surfaced because PSI tests the rendered page); Cloudflare's "Managed robots.txt" appending `Content-Signal:` directives Lighthouse's parser doesn't recognize.

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
| `tools/url_resolution_cache.json` | Cached redirect resolutions so the per-push CI run only re-resolves *new* URLs (kept the Normalize step from re-checking ~2,650 links every run) | **Don't edit** -- CI-seeded; never commit a local copy (redirect resolution is IP-dependent, so a workstation seed can differ from CI and falsely block deploys) |
| `tools/check_all_site_urls.py` | Site-wide URL safety scanner | Running local safety audits |
| `tools/update_sitemap.py` | Refreshes `<lastmod>` dates in `sitemap.xml` from git history | **Don't edit** -- runs in CI and alongside `update_news.py` |
| `tools/update_presentations_schema.py` | Regenerates `VideoObject` JSON-LD on `presentations.html` | **Don't edit** -- runs in CI on every deploy |
| `tools/crosslink_glossary.py` | Adds `id="term-..."` to glossary `<dt>`s and hyperlinks every term mention in `<dd>`s | Run after adding/editing glossary entries |
| `tools/crosslink_pages.py` | Hyperlinks first occurrence of each glossary term across all content pages | Run after adding/editing glossary entries (or after adding a new content page) |
| `glossary.html` | Cloud-security glossary (310 terms) with live search and cross-linked definitions | Adding/editing terms; run `crosslink_glossary.py` *and* `crosslink_pages.py` after |
| `glossary.js` | Live search/filter for `glossary.html` | Changing search behavior |
| `meetings.js` | Filters + auto-detected speaker filter for `meetings.html` | Adding new recurring speakers (`SPEAKERS` list) |
| `sitemap.xml` | XML sitemap for search engines | **Don't edit** -- lastmod refreshed automatically |
| `update_sri.py` | SRI hash generator. The `ASSETS` list is the source of truth: `style.css`, `main.js`, `chat-resources.js`, `breach-timeline.css`, `breach-timeline.js`, `meetings.js`, `glossary.js`, `404.js`, `search.css`, `search-init.js`, `vendor/goatcounter-count.js`. Any new shared asset must be added there or it ships uncached-busted and unhashed | Adding a shared CSS/JS asset; otherwise **don't edit** -- runs in CI |
| `tools/check_edge_headers.py` | Edge security-header drift gate. Parses the header name/value pairs out of the `set_security_headers` rule in `infra/terraform/cloudflare/rules.tf` and asserts each one against what the live site actually returns, failing on anything missing or changed. It exists because that ruleset carries `lifecycle { ignore_changes = [rules] }` (a cloudflare v4 provider workaround), which makes the resource inert: you can tighten the CSP in Git, get a clean `terraform apply`, and ship nothing. Those headers are also the only source of CSP/HSTS for the Azure origin, which cannot set response headers itself | Run it (`python3 tools/check_edge_headers.py`, or `--url <origin>` for one origin) after any edge-header change, since `terraform apply` will not tell you. It is a **CI gate in the `purge-cloudflare` job of `deploy.yml`**, so drift fails the deploy. Delete the whole script once the cloudflare v5 provider upgrade lets `ignore_changes` go |
| `tools/add_meeting.py` | Publishes a meeting recap from a note export: writes `meetings/YYYY-MM-DD.html`, inserts the card on `meetings.html`, rewires the pager links on both chronological neighbors, and updates `sitemap.xml` + `meetings-search-index.json` | Changing recap structure. Note the `scrub_emails()` guard in `clean_text()` (the shared funnel for both the HTML and Markdown parsers): Zoom summaries name people by display name, and some people's display name is their work email address, so any address in recap prose is replaced with "one attendee" (`@csoh.org` is exempt). It **warns and continues** rather than failing, so a publish is never blocked -- read the warning and substitute a first name if one is appropriate |
| `vendor/` | Self-hosted third-party browser libraries (MiniSearch, GoatCounter), SRI-pinned because the CSP is `script-src 'self'`. `goatcounter-count.js` is deliberately patched, not pristine | **Read [vendor/README.md](vendor/README.md) first.** A re-vendor must re-apply the local modifications and re-run `update_sri.py` |
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
