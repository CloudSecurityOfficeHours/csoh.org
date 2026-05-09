# Security Documentation — csoh.org

This document describes the security measures in place for [csoh.org](https://csoh.org), a static website for the Cloud Security Office Hours community.

---

## Architecture

csoh.org is a **pure static site** — no server-side code, no database, no user accounts, no cookies, no sessions. This eliminates entire classes of vulnerabilities (SQL injection, RCE, auth bypass, session hijacking, CSRF).

**Hosting is being migrated from shared LiteSpeed (FTPS-deployed) to Google Cloud Run (container-based, GitHub Actions-deployed via Workload Identity Federation).** Both paths run in parallel during the transition:

| Path | Status | Domain | Deploy mechanism |
|------|--------|--------|------------------|
| LiteSpeed shared host | Production today | `csoh.org`, `www.csoh.org` | FTPS via `lftp` from `site-update-deploy.yml`, credentials in GitHub Secrets |
| Google Cloud Run | Staging (verified) | `gcp.csoh.org` | Container deploy via `gcp-deploy.yml`, **no service-account key** — auth is short-lived OIDC tokens minted by GitHub and exchanged for GCP access tokens via Workload Identity Federation |

After the Cloudflare DNS cutover (`csoh.org` and `www` move to the GCP load balancer), the FTPS path is retired and FTP secrets are removed from the repo. The full GCP architecture — Cloud Run, HTTPS load balancer, Cloud Armor WAF, Cloud CDN, managed TLS, Workload Identity Federation, Artifact Registry with immutable tags, 400-day log retention — is documented in [infra/README.md](infra/README.md).

---

## HTTP Security Headers

All responses from csoh.org include these security headers, configured in both `.htaccess` (production) and `nginx.conf` (Docker/local):

| Header | Value | Purpose |
|--------|-------|---------|
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains; preload` | Forces HTTPS for 1 year, includes subdomains, eligible for browser preload lists |
| `X-Content-Type-Options` | `nosniff` | Prevents MIME-type sniffing attacks |
| `X-Frame-Options` | `DENY` | Blocks clickjacking by preventing iframe embedding |
| `Content-Security-Policy` | See below | Restricts what the browser can load |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Limits referrer data sent to external sites |
| `Permissions-Policy` | `camera=(), microphone=(), geolocation=(), payment=(), usb=(), magnetometer=(), gyroscope=(), accelerometer=()` | Disables all browser APIs we don't use |

Server version headers (`X-Powered-By`, `Server`) are stripped from HTTPS responses.

### Content Security Policy (CSP)

```
default-src 'self';
script-src 'self';
style-src 'self';
img-src 'self' https://csoh.org https://img.youtube.com https://i.ytimg.com data:;
font-src 'self';
connect-src 'self';
frame-src https://www.youtube.com https://web.archive.org;
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
object-src 'none'
```

Key points:
- **No `unsafe-inline` or `unsafe-eval`** in `script-src` — inline scripts and `eval()` are blocked
- **No wildcards** — every external domain is explicitly listed
- **`frame-ancestors 'none'`** — supersedes `X-Frame-Options` for modern browsers
- **`object-src 'none'`** — blocks Flash, Java applets, and other plugin content
- Only YouTube and Web Archive are allowed as iframe sources
- Only YouTube thumbnail domains are allowed as external image sources
- The `.htaccess` and `nginx.conf` CSPs are byte-identical (no drift)

In addition to CSP, the following cross-origin isolation headers are set:

- `Cross-Origin-Opener-Policy: same-origin` — only same-origin windows can hold a reference to ours; defends against cross-origin info leaks via `window.opener` and Spectre-class side channels.
- `Cross-Origin-Resource-Policy: same-origin` — resources from this origin can only be loaded by same-origin contexts; stops arbitrary sites from embedding our images/scripts/etc.

---

## File Access Controls

The `.htaccess` and `nginx.conf` block direct access to sensitive files:

| Pattern | Status | What's blocked |
|---------|--------|----------------|
| `^\.` (hidden files) | 403 | `.git/`, `.env`, `.htaccess`, `.claude/`, etc. |
| `\.git(/.*)?$` | 403 | Git repository data |
| `\.(py\|pyc\|md\|json)$` | 403 | Python scripts, docs, JSON files |
| `.*-report\.txt$` | 403 | Internal URL safety report files |
| `\.(bak\|config\|sh\|sql\|log\|ini)$` | 403 | Backups, configs, scripts, logs |

**Exceptions:** three JSON files are explicitly allowlisted because the site needs to fetch them:
- `preview-mapping.json` — resource preview thumbnails (`main.js`)
- `manifest.json` — PWA "Add to Home Screen" metadata
- `meetings-search-index.json` — meetings.html full-text search index (`meetings.js`)

Directory listing is disabled globally (`Options -Indexes` / `autoindex off`).

---

## Subresource Integrity (SRI)

All first-party CSS and JavaScript files include SRI hashes:

```html
<link rel="stylesheet" href="/style.css?v=50dcc027"
    integrity="sha384-vK2hvLkL0HnH9vJgt/...">
<script src="/main.js?v=a1b2c3d4"
    integrity="sha384-xyz123..."></script>
```

The `update_sri.py` script:
1. Calculates SHA-384 hashes for every tracked first-party asset (`style.css`, `main.js`, `chat-resources.js`, `breach-timeline.css`, `breach-timeline.js`, `meetings.js`, `glossary.js`)
2. Updates the `integrity` attribute in all HTML files
3. Adds cache-busting `?v=` parameters derived from the hash
4. Runs automatically in CI before every deploy

This means even if the hosting account were compromised and files were tampered with, browsers would refuse to execute the modified scripts.

---

## JavaScript Security

**XSS Prevention:**
- All user input (search queries, URL parameters) is passed through a `sanitize()` function that uses `textContent` encoding — the safest DOM-based sanitization method
- No `eval()`, no `document.write()`, no `Function()` constructors
- `innerHTML` is only used with sanitized or non-user-controlled content

**External Link Protection:**
- All `target="_blank"` links automatically receive `rel="noopener noreferrer"` via JavaScript enforcement on page load
- This prevents reverse tabnapping attacks

**No Third-Party JavaScript:**
- Zero external scripts — no analytics, no tracking pixels, no CDN-hosted libraries
- All JavaScript is first-party, self-hosted, and SRI-hashed

**No Cookies or Tracking:**
- The site sets no cookies of any kind
- `localStorage` is used only for the dark mode theme preference (`theme` key)
- No user data is collected, stored, or transmitted
- See [privacy.html](privacy.html) for the user-facing Privacy Policy

---

## URL Safety Validation

An automated URL safety checker runs in CI on every HTML change:

1. **Trigger:** Any push or PR that modifies `.html` files
2. **Scan:** Extracts all URLs from all HTML files (href, src, embedded)
3. **Checks performed:**
   - URL scheme validation (only `http://` and `https://` allowed)
   - Known phishing pattern detection (login spoofing, credential harvesting keywords)
   - URL shortener detection (`bit.ly`, `goo.gl`, `tinyurl.com`, etc.)
   - Suspicious TLD detection (`.tk`, `.ml`, `.ga`, etc.)
   - Raw IP address detection
   - Excessive subdomain detection
   - Domain length anomaly detection
4. **Result:** If any URL is classified as **unsafe**, the workflow exits with code 1 and blocks the merge
5. **Whitelisted domains:** github.com, youtube.com, aws.amazon.com, owasp.org, cisa.gov, nist.gov, csoh.org, microsoft.com, google.com, cloudflare.com, wikipedia.org

See `tools/CHECK_URL_SAFETY_README.md` for full details.

---

## Supply Chain Security

### Pinned GitHub Actions

All third-party GitHub Actions are pinned to exact commit SHAs rather than mutable version tags. This prevents a compromised action maintainer from injecting malicious code via a tag update.

| Action | Pinned SHA | Version |
|--------|-----------|---------|
| `actions/checkout` | `de0fac2e4500dabe0009e67214ff5f5447ce83dd` | v6.0.2 |
| `actions/setup-python` | `a309ff8b426b58ec0e2a45f0f869d46889d02405` | v6.2.0 |
| `actions/upload-artifact` | `bbbca2ddaa5d8feaa63e36b76fdaad77386f024f` | v7.0.0 |
| `actions/github-script` | `ed597411d8f924073f98dfc5c65a23a2325f34cd` | v8.0.0 |
| `actions/cache` | `27d5ce7f107fe9357f9df03efb73ab90386fccae` | v5.0.5 |
| `actions/create-github-app-token` | `1b10c78c7865c340bc4f6099eb2f838309f1e8c3` | v3.1.1 |
| `peter-evans/create-pull-request` | `c0f553fe549906ede9cf27b5156039d195d2ece0` | v8.1.0 |
| `peter-evans/enable-pull-request-automerge` | `a660677d5469627102a1c1e11409dd063606628d` | v3.0.0 |
| `raven-actions/actionlint` | `205b530c5d9fa8f44ae9ed59f341a0db994aa6f8` | v2.1.2 |
| `astral-sh/ruff-action` | `0ce1b0bf8b818ef400413f810f8a11cdbda0034b` | v4.0.0 |
| `lycheeverse/lychee-action` | `8646ba30535128ac92d33dfc9133794bfdd9b411` | v2.8.0 |
| `Cyb3r-Jak3/html5validator-action` | `443b108eb8e134b63a1f8a8ba0c942d552608ed7` | master 2025-09-19 |

Every third-party action used by the workflows is pinned by SHA — no remaining `@v*` major-tag references. To update a pinned action, look up the commit SHA for the new tag:
```bash
curl -s "https://api.github.com/repos/actions/checkout/git/ref/tags/v6.0.2" | grep sha
```

### No External Dependencies (Client-Side)

The site loads zero external JavaScript libraries, CSS frameworks, or fonts. Everything is self-hosted. This eliminates CDN compromise as an attack vector.

### Minimal Python Dependencies

The CI tooling uses only:
- Python standard library (`urllib`, `hashlib`, `xml.etree.ElementTree`)
- `Playwright` (for screenshot generation)
- `Pillow` (for image optimization)
- `yamllint` (lint job, pinned version)

---

## CI/CD Authentication

CI workflows authenticate to GitHub via a **GitHub App** (`csoh-ci`) rather than a personal access token. This section explains the model, the migration rationale, and what's still on a PAT.

### Authentication model

| Workflow | Auth (GitHub side) | Auth (deploy target) | Pushes to main? |
|----------|---------|----------------------|------|
| `update-news.yml` | `csoh-ci` App + `CSOH_PAT` (for auto-approve) | n/a | via PR + auto-merge |
| `normalize-urls.yml` | `csoh-ci` App | n/a | via PR (human reviews + merges) |
| `site-update-deploy.yml` | `csoh-ci` App | FTPS — `FTP_HOST`/`FTP_USER`/`FTP_PASS` secrets | direct (App is on ruleset bypass) |
| `manual-deploy.yml` | n/a | FTPS — same secrets | no |
| `gcp-deploy.yml` | auto-injected `GITHUB_TOKEN` (`id-token: write` for OIDC) | **WIF — no key** (impersonates `csoh-deployer` SA via OIDC) | no |
| `lint.yml`, `validate-html.yml`, `check-broken-links.yml`, `check-url-safety.yml` | auto-injected `GITHUB_TOKEN` | n/a | no |

Every workflow declares an explicit top-level `permissions:` block scoping the auto-injected `GITHUB_TOKEN`. The four read-only check workflows use `contents: read` (plus `pull-requests: write` where they post comments). The four write-capable workflows (`update-news`, `normalize-urls`, `site-update-deploy`, `manual-deploy`) declare `contents: read` for the auto-injected token, because they handle write access through the App or PAT instead — keeping the default token strictly minimal.

### Why we migrated from PATs to a GitHub App

The original CI design used two personal access tokens belonging to a human (Shawn): `PAT_TOKEN` (push, open PRs, enable auto-merge) and `APPROVAL_PAT_TOKEN` (approve the bot's own PRs, since GitHub blocks self-approval with the same identity). PATs are functional but carry several security properties we wanted to improve:

1. **Long-lived.** PATs don't expire unless you set an explicit expiry. Once granted, the token is valid until manually revoked. A leaked PAT remains useful to an attacker for as long as it takes you to notice.

2. **Broadly scoped (classic PATs especially).** A classic PAT with `repo` scope can read and write *every* repository the owning user has access to — public, private, and forked. Even fine-grained PATs are awkward to constrain to one repository while still permitting all the operations a busy CI pipeline needs.

3. **Tied to a personal identity.** Bot commits authored under a PAT show up as the human account on the audit log, blurring the distinction between automation and operator action. If the human leaves the project (or the org), every workflow that depends on their PAT breaks.

4. **No native rotation.** Rotating a PAT means generating a new one, updating every secret, and revoking the old one — a manual process that tends to get postponed.

A GitHub App fixes all four:

1. **Short-lived tokens.** The App's installation tokens are valid for ~1 hour. A workflow run requests a fresh token at job start; that token is the only thing exposed to the workflow log redaction layer. After the run finishes, the token is useless.

2. **Per-repo scoping by default.** The App is installed on the single `CloudSecurityOfficeHours/csoh.org` repository with the minimum permissions needed (`contents: read+write`, `pull-requests: read+write`). The token GitHub mints from those install settings cannot do more than the App's installation scope allows.

3. **Independent identity.** The App is its own first-class GitHub principal (`csoh-ci[bot]`). Audit logs cleanly distinguish bot pushes from human pushes. The App outlives any individual contributor.

4. **Automatic rotation.** Tokens rotate every hour with no human intervention. The only long-lived secret is the App's RSA private key, which only needs rotating when you suspect it's compromised (or as part of a periodic key-rotation hygiene pass).

In numbers: blast radius of a leaked CI token went from "everything Shawn's PAT can touch, until manual revocation" → "one repo, one workflow run's worth of actions, ~1 hour."

### App configuration

- **Installation:** `csoh-ci` is installed on `CloudSecurityOfficeHours/csoh.org` only — not at the org-wide level.
- **Repository permissions:** `contents: read & write`, `pull-requests: read & write`. No other permissions granted.
- **Webhooks:** disabled. The App is purely an authentication identity; it does not consume events.
- **Branch protection / rulesets:** `csoh-ci` is on the main-branch ruleset bypass list with mode "Always," because `site-update-deploy.yml` does direct in-place commits to `main` (with `[skip ci]` markers) for housekeeping (SRI hashes, sitemap dates, normalized URLs, generated preview images). PRs from `update-news.yml` and `normalize-urls.yml` go through the normal merge path and don't need the bypass.

### Token retrieval pattern

Every workflow that needs write access starts with the same step:

```yaml
- name: Mint installation token
  id: app-token
  uses: actions/create-github-app-token@1b10c78c7865c340bc4f6099eb2f838309f1e8c3  # v3.1.1
  with:
    client-id: ${{ secrets.CSOH_CI_CLIENT_ID }}
    private-key: ${{ secrets.CSOH_CI_PRIVATE_KEY }}
```

Subsequent steps reference `${{ steps.app-token.outputs.token }}` wherever they previously used `${{ secrets.PAT_TOKEN }}` (e.g., `actions/checkout`'s `token:` input, `peter-evans/create-pull-request`'s `token:` input, `git remote set-url origin "https://x-access-token:${TOKEN}@..."`).

### Why one PAT remains: GitHub auto-merge does not honor ruleset bypass

GitHub does not allow an actor to approve its own PRs (this restriction applies to GitHub Apps too — an App that opens a PR cannot approve it). The main-branch ruleset has a `pull_request` rule requiring 1 approval before merging.

We initially expected that putting the `csoh-ci` App on the ruleset's **bypass list** with mode `Always` would let the App auto-merge its own PRs without any approval — the bypass should apply to *all* rules including `pull_request`, and the merge action is performed by the App. **Empirically, this is not the case.** Verified on 2026-05-08 with PR #650:

- All required status checks: passing
- App on bypass list with `mode: always`
- Auto-merge enabled by the App
- Result: `mergeStateStatus: BLOCKED`, `reviewDecision: REVIEW_REQUIRED` — auto-merge sat indefinitely

GitHub's auto-merge feature evaluates `reviewDecision` independently and does not consult the bypass list. (Bypass *does* work for direct API merges by the same actor — it's specific to the auto-merge scheduler.) So one narrow PAT remains: `CSOH_PAT`, a fine-grained org-scoped token used exclusively to approve PRs that the App has just opened, satisfying the approval rule so that auto-merge can fire.

`normalize-urls.yml` keeps its "human reviews + merges" flow without an auto-approve step; the auto-approve there was a one-click convenience and added no real safety. Removing it is a strict improvement (humans now click both "approve" and "merge" instead of just "merge").

`site-update-deploy.yml` is unaffected — it does direct in-place commits to `main` (not via PR), and the App's bypass *does* apply to direct pushes.

### Repository secrets currently in use

| Secret | Purpose | Type |
|--------|---------|------|
| `CSOH_CI_CLIENT_ID` | GitHub App's Client ID (`Iv23.*`) | identifier (not sensitive on its own) |
| `CSOH_CI_PRIVATE_KEY` | GitHub App's RSA private key | high-sensitivity |
| `CSOH_PAT` | Approve App-opened PRs (auto-merge driver) | medium-sensitivity (narrow scope) |
| `FTP_HOST`, `FTP_USER`, `FTP_PASS` | FTPS deploy credentials (**retired post-cutover**) | high-sensitivity |
| `SSH_PRIVATE_KEY` | Reserved for future use | high-sensitivity |

**No GCP secret in this list — that's deliberate.** The `gcp-deploy.yml` workflow needs no service-account key, no project-scoped PAT, and no GCP-side stored secret. It authenticates by:

1. GitHub Actions mints an OIDC token for the run, signed by GitHub's identity provider.
2. Google Cloud's STS exchanges that token for a short-lived (1-hour) access token, gated by a Workload Identity Federation policy that requires:
   - `assertion.repository == 'CloudSecurityOfficeHours/csoh.org'` (other repos cannot mint tokens for this pool)
   - `aud` matching the configured pool/provider
3. The access token is scoped to impersonating one specific service account (`csoh-deployer`) which has narrowly-scoped roles: `roles/run.admin`, `roles/artifactregistry.writer`, plus `iam.serviceAccountUser` on the runtime SA.
4. The runtime SA (`csoh-run-runtime`, what the actual container runs as) has **zero IAM roles** — the static container makes no GCP API calls, so it gets nothing.

Net effect: a leaked workflow log compromises one ~1-hour token scoped to one repo's deploy permissions on one project. There is no long-lived credential to rotate or revoke.

`PAT_TOKEN` (the original CI PAT), `CSOH_CI_APP_ID` (deprecated numeric input, replaced by `CSOH_CI_CLIENT_ID`), and `APPROVAL_PAT_TOKEN` (replaced by `CSOH_PAT`) have all been removed.

`CSOH_PAT` is a **fine-grained PAT** scoped to `CloudSecurityOfficeHours/csoh.org` only, with permissions limited to **Pull requests: Read & Write** (no contents, no actions, no anything else). Even if it leaks, the only damage an attacker can do is approve PRs — they cannot push, merge by themselves, or read code beyond what's already in the public repo. Replaced the broader classic-PAT `APPROVAL_PAT_TOKEN` on 2026-05-08.

### Rotation guidance

| Item | Rotation cadence | Process |
|------|-----------------|---------|
| App installation token | Automatic, every ~1 hour | None — handled by GitHub |
| App private key | Annually or on suspected compromise | Generate new key in App settings; replace `CSOH_CI_PRIVATE_KEY` secret; revoke old key |
| `CSOH_PAT` | Every 6–12 months (or before its set expiry) | Generate new fine-grained PAT (resource owner: `CloudSecurityOfficeHours`, repo: `csoh.org`, permission: pull-requests: write only); replace org-level Actions secret |
| `FTP_PASS` (retired post-cutover) | Every 6–12 months while in use | Rotate via hosting panel; replace secret. After GCP cutover, delete all three FTP secrets. |
| GCP WIF access token | Automatic, every ~1 hour | None — minted per workflow run, no stored credential |
| GCP runtime SA roles | On every Terraform apply | The runtime SA's IAM bindings live in [`infra/terraform/service_accounts.tf`](infra/terraform/service_accounts.tf) — review on every change |

---

## Deployment Security

Two deploy paths run in parallel during the LiteSpeed → GCP migration. After Cloudflare DNS cuts over to the GCP load balancer, the FTPS path is retired and the FTP secrets are deleted.

### Cloud Run Deployment (post-migration target)

`gcp-deploy.yml` builds a container image, scans it, and deploys to Cloud Run on every push to `main` that touches site files.

**Authentication — Workload Identity Federation, no stored credential:**
- GitHub Actions mints an OIDC token for the run.
- A WIF policy in the GCP project gates the exchange: only OIDC tokens whose `repository` claim equals `CloudSecurityOfficeHours/csoh.org` are accepted ([`infra/terraform/wif.tf`](infra/terraform/wif.tf)).
- The exchanged GCP access token is short-lived (~1 hour), scoped to impersonating the `csoh-deployer` service account.
- The deploy SA has only the roles needed to push images and deploy revisions — no broader project access.
- The runtime SA the container runs as (`csoh-run-runtime`) has **zero IAM roles**.

**Image supply chain:**
- Base image (`nginx:1.27-alpine`) is **digest-pinned** in the [`Dockerfile`](Dockerfile). A compromised registry tag cannot ship malicious bytes into our build.
- `RUN apk upgrade --no-cache` after `FROM` refreshes Alpine packages on top of the pinned base — supply-chain integrity for the base layer plus current security patches for libraries.
- Every PR's container is **Trivy-scanned** for HIGH and CRITICAL CVEs (with fixes available); the build fails if any are found.
- Artifact Registry has `immutable_tags=true` — once an image tag is pushed, it cannot be overwritten or moved. Cloud Run revisions pin a specific SHA tag, so rollback is `gcloud run services update-traffic --to-revisions <name>=100` and there is no ambiguity about what bytes ran.
- Cleanup policy keeps the most recent 30 versions and deletes untagged versions older than 7 days.

**Workflow hardening:**
- `permissions:` block scopes the auto-injected `GITHUB_TOKEN` to `contents: read` + `id-token: write` (id-token is required by WIF; nothing else is granted).
- The deploy job is gated by the `production` GitHub Environment, which is configured in repo settings to allow deployments only from `main` and to enforce Code Owners review on the workflow file via [`.github/CODEOWNERS`](.github/CODEOWNERS). A PR from a fork cannot reach this code path even if it could otherwise mint an OIDC token, because protected-environment policies only apply on `main`.

**Edge defenses (load balancer in front of Cloud Run):**
- **Cloud Armor** policy with OWASP Core Rule Set (SQLi, XSS, LFI, RFI, RCE), per-IP rate limit (600 req/min, 10-min ban on exceed), and adaptive L7 DDoS defense ([`infra/terraform/cloud_armor.tf`](infra/terraform/cloud_armor.tf)).
- **Modern TLS policy** — TLS 1.2+ only, restricted cipher suite.
- **HTTP→HTTPS redirect** at the LB; the Cloud Run service's ingress is `internal-and-cloud-load-balancing` so direct hits to the Run URL get blocked at the edge.

**Logging:**
- LB request logs, Cloud Armor decisions, IAM admin activity, and audit logs are routed to a 400-day retention bucket via the security log sink in [`infra/terraform/logging.tf`](infra/terraform/logging.tf) (the default `_Default` sink only retains 30 days).

### FTPS Deployment (legacy, retiring during cutover)

The site currently deploys via FTPS (FTP over TLS) using `lftp` from GitHub Actions to LiteSpeed shared hosting. This path **runs in parallel** with `gcp-deploy.yml` during migration; both publish the same source-of-truth bytes to different hosts.

- `ssl:verify-certificate yes` — **validates the FTP host's TLS cert chain and hostname.** An on-path attacker cannot present a forged cert and capture the FTP credentials.
- `ftp:ssl-force true` — enforces TLS encryption on the control channel (refuses plaintext FTP)
- `ftp:ssl-protect-data true` — encrypts file transfers, not just the control channel
- Credentials are written to a temporary `~/.netrc` (mode 600) at job start and lftp picks them up from there. They are **not** passed on the command line, so `FTP_PASS` never appears in `/proc/<pid>/cmdline`.
- Credentials are stored as GitHub repository secrets (`FTP_HOST`, `FTP_USER`, `FTP_PASS`).

The deploy workflow (`site-update-deploy.yml`) authenticates to GitHub via the `csoh-ci` App for its housekeeping commits (SRI hash updates, sitemap refreshes, etc.) — see [CI/CD Authentication](#cicd-authentication) above. FTP credentials are entirely separate and not affected by App-token rotation.

**Retirement plan:** after Cloudflare DNS for `csoh.org` and `www.csoh.org` is moved to the GCP LB and traffic is verified, the FTP `lftp` step in `site-update-deploy.yml` is removed (the housekeeping steps stay), `manual-deploy.yml` is deleted, and the three FTP secrets are removed from the repo.

### Deployment Exclusions

The following are explicitly excluded from deployment to the web server:

| Excluded | Why |
|----------|-----|
| `.git/` | Repository data |
| `.github/` | CI/CD workflows |
| `.venv/` | Python virtual environment |
| `__pycache__/` | Python bytecode cache |
| `tools/` | Internal tooling scripts |
| `*.sh`, `*.py`, `*.pyc`, `*.pyo` | Scripts |
| `*.md` | Documentation files |
| `.DS_Store` | macOS metadata |
| `README.md`, `LICENSE`, `CONTRIBUTING*.md` | Repo docs |

### Docker Security

The `Dockerfile` and `nginx.conf` provide an alternative deployment path with equivalent security:
- All sensitive files are removed during the Docker build (`rm -rf .git, tools, *.py, *.md`, etc.)
- `nginx.conf` mirrors all `.htaccess` security headers and access controls
- `server_tokens off` suppresses nginx version disclosure

---

## Vulnerability Disclosure

If you discover a security vulnerability on csoh.org:

- **Email:** admin@csoh.org
- **security.txt:** https://csoh.org/.well-known/security.txt (RFC 9116)
- **Community:** Bring it up during our Friday Zoom session

We take security seriously — especially as a cloud security community.

---

## Known Limitations

| Item | Status | Notes |
|------|--------|-------|
| `Server: LiteSpeed` on HTTP redirect | Hosting limitation | The HTTP (port 80) redirect response leaks the server type. The HTTPS response correctly strips it. Requires hosting panel config to suppress. |
| `cancel-in-progress: true` on deploy | Accepted trade-off | If a newer deploy is queued while one is running, the older run is cancelled mid-mirror. Avoids stale-content races but can leave the FTP server with a few files at the new state and others at the old until the next run completes. Worth revisiting if/when we move to a blue-green deploy. |
| `http://flaws.cloud` link | Intentional | This AWS security training site only serves over HTTP. The link is intentional. |
