# Security Documentation - csoh.org

This document describes the security measures in place for [csoh.org](https://csoh.org), a static website for the Cloud Security Office Hours community.

---

## Architecture

csoh.org is a **pure static site** - no server-side code, no database, no user accounts, no cookies, no sessions. This eliminates entire classes of vulnerabilities (SQL injection, RCE, auth bypass, session hijacking, CSRF).

**Hosting is multi-cloud: the same static site is served active/active from three origins** - AWS (private S3 + CloudFront), GCP (Cloud Run), and Azure (Blob static website) - behind a single **Cloudflare** edge that terminates TLS (Full strict to every origin), caches, runs the WAF and security headers, applies legacy redirects, and load-balances across the origins with health-check failover. GitHub Actions builds the site once and publishes to all three via **keyless OIDC** (GCP Workload Identity Federation, an AWS IAM role, an Azure Entra federated credential) - there is no long-lived cloud credential anywhere. The full architecture, cost, and cutover runbook are in [infra/README.md](infra/README.md); the layer-by-layer security walkthrough is the public [cloud-deployment.html](cloud-deployment.html).

The site previously deployed via FTPS to a LiteSpeed shared host. That path was retired after the cutover to GCP - the FTPS step is removed from `site-update-deploy.yml`, the standalone `manual-deploy.yml` workflow is deleted, and the `FTP_*` secrets are gone.

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
img-src 'self' https://csoh.org https://img.youtube.com https://i.ytimg.com https://csoh.goatcounter.com data:;
font-src 'self';
connect-src 'self' https://csoh.goatcounter.com;
frame-src https://www.youtube.com https://web.archive.org https://docs.google.com https://drive.google.com;
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
object-src 'none'
```

Key points:
- **No `unsafe-inline` or `unsafe-eval`** in `script-src` - inline scripts and `eval()` are blocked
- **No wildcards** - every external domain is explicitly listed (`docs.google.com`/`drive.google.com` are present only to allow the embedded Google Slides decks on `presentations.html`)
- **`frame-ancestors 'none'`** - supersedes `X-Frame-Options` for modern browsers
- **`object-src 'none'`** - blocks Flash, Java applets, and other plugin content
- Only YouTube and Web Archive are allowed as iframe sources
- Only YouTube thumbnail domains are allowed as external image sources
- `csoh.goatcounter.com` is allowed in `img-src` + `connect-src` for cookieless, privacy-friendly analytics; the loader is self-hosted at `/vendor/goatcounter-count.js`, so `script-src` stays `'self'`
- The `.htaccess` and `nginx.conf` CSPs are byte-identical (no drift)

In addition to CSP, the following cross-origin isolation headers are set:

- `Cross-Origin-Opener-Policy: same-origin` - only same-origin windows can hold a reference to ours; defends against cross-origin info leaks via `window.opener` and Spectre-class side channels.
- `Cross-Origin-Resource-Policy: same-origin` - resources from this origin can only be loaded by same-origin contexts; stops arbitrary sites from embedding our images/scripts/etc.

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

**Exception - `/.well-known/`:** this is a dotted path, so the hidden-file rule
would 403 it along with `.git` and `.env`. `nginx.conf` carves it out with a
`location ^~ /.well-known/` block placed before the deny; the `^~` modifier
makes nginx stop at that prefix match and never evaluate the regex denies.
`tools/site-publish.filter` has the matching `+ /.well-known/` allow so the
directory actually reaches the S3 and Azure origins. Both are scoped to
`/.well-known/` alone - every other dotted path still 403s, including
directory listing of `/.well-known/` itself and `/.well-known/../.env`.

This matters because `/security.txt` names `https://csoh.org/.well-known/security.txt`
in its `Canonical:` field, and RFC 9116 tooling follows that URL. It used to
return 403, which failed validation.

**Exceptions:** four JSON files are explicitly allowlisted because the site needs to fetch them:
- `preview-mapping.json` - resource preview thumbnails (`main.js`)
- `manifest.json` - PWA "Add to Home Screen" metadata
- `meetings-search-index.json` - meetings.html full-text search index (`meetings.js`)
- `search-index.json` - site-wide search index, lazy-loaded by `search-init.js`

The same four-file allowlist is enforced a second time in `tools/site-publish.filter`, which decides what is uploaded to the object-storage origins at all. Static object hosting has no request-time access rules, so on AWS and Azure the rule is "never upload it" rather than "return 403".

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
1. Calculates SHA-384 hashes for every asset in its `ASSETS` list - currently `style.css`, `main.js`, `chat-resources.js`, `breach-timeline.css`, `breach-timeline.js`, `meetings.js`, `glossary.js`, `404.js`, `search.css`, `search-init.js`, and the vendored `vendor/goatcounter-count.js`. Any new shared asset must be added to that list or it ships with neither an integrity hash nor a cache-bust key
2. Updates the `integrity` attribute in all HTML files
3. Adds cache-busting `?v=` parameters derived from the hash
4. Runs automatically in CI - `site-update-deploy.yml` stamps the repo, and `deploy.yml` re-stamps the build output before staging, so the published artifact is self-consistent even if a commit landed with stale hashes

This means even if the hosting account were compromised and files were tampered with, browsers would refuse to execute the modified scripts.

---

## JavaScript Security

**XSS Prevention:**
- All user input (search queries, URL parameters) is passed through a `sanitize()` function that uses `textContent` encoding - the safest DOM-based sanitization method
- No `eval()`, no `document.write()`, no `Function()` constructors
- `innerHTML` is only used with sanitized or non-user-controlled content

**External Link Protection:**
- All `target="_blank"` links automatically receive `rel="noopener noreferrer"` via JavaScript enforcement on page load
- This prevents reverse tabnapping attacks

**No Third-Party JavaScript:**
- No third-party scripts - the only analytics is GoatCounter (cookieless, no IP storage, no cross-site tracking), and its loader is self-hosted at `/vendor/goatcounter-count.js` so `script-src` stays `'self'`; no tracking pixels, no CDN-hosted libraries
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
| `Cyb3r-Jak3/html5validator-action` | `443b108eb8e134b63a1f8a8ba0c942d552608ed7` | master 2025-09-19 |
| `actions/cache` | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` | v6.1.0 |
| `actions/checkout` | `9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0` | v7.0.0 |
| `actions/create-github-app-token` | `bcd2ba49218906704ab6c1aa796996da409d3eb1` | v3.2.0 |
| `actions/download-artifact` | `3e5f45b2cfb9172054b4087a40e8e0b5a5461e7c` | v8.0.1 |
| `actions/github-script` | `3a2844b7e9c422d3c10d287c895573f7108da1b3` | v9.0.0 |
| `actions/setup-python` | `5fda3b95a4ea91299a34e894583c3862153e4b97` | v7.0.0 |
| `actions/upload-artifact` | `043fb46d1a93c77aae656e7c1c64a875d1fc6a0a` | v7.0.1 |
| `anthropics/claude-code-action` | `af0559ee4f514d1ef21826982bed13f7edc3c35e` | v1.0.178 |
| `astral-sh/ruff-action` | `278981a28ce3188b1e39527901f38254bf3aac89` | v4.1.0 |
| `aws-actions/configure-aws-credentials` | `517a711dbcd0e402f90c77e7e2f81e849156e31d` | v6.2.2 |
| `azure/cli` | `9eb25b8360668fb0ecbafa808d40e2197b2f5f52` | v3.0.0 |
| `azure/login` | `532459ea530d8321f2fb9bb10d1e0bcf23869a43` | v3.0.0 |
| `google-github-actions/auth` | `7c6bc770dae815cd3e89ee6cdf493a5fab2cc093` | v3 |
| `google-github-actions/setup-gcloud` | `aa5489c8933f4cc7a4f7d45035b3b1440c9c10db` | v3.0.1 |
| `lycheeverse/lychee-action` | `e7477775783ea5526144ba13e8db5eec57747ce8` | v2.9.0 |
| `peter-evans/create-pull-request` | `5f6978faf089d4d20b00c7766989d076bb2fc7f1` | v8.1.1 |
| `peter-evans/enable-pull-request-automerge` | `a660677d5469627102a1c1e11409dd063606628d` | v3.0.0 |
| `raven-actions/actionlint` | `3d39aea434753780c3b3d4a1a31c854b4dbf49d7` | v2.2.0 |

Every third-party action used by the workflows is pinned by SHA - no remaining `@v*` major-tag references.

Bumps are normally automatic: `.github/dependabot.yml` watches the `github-actions`
ecosystem weekly and opens **one grouped PR** that updates both the SHA and the
trailing `# vX.Y.Z` comment. Only do it by hand if you are pinning something
Dependabot doesn't cover:

```bash
curl -s "https://api.github.com/repos/actions/checkout/git/ref/tags/v7.0.0" | grep sha
```

The table above drifts every time Dependabot lands a bump. Regenerate it from
the workflows rather than editing rows by hand:

```bash
grep -ho 'uses: [^ ]*@[0-9a-f]\{40\}  *# .*' .github/workflows/*.yml | sed 's/uses: //' | sort -u
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
| `site-update-deploy.yml` | `csoh-ci` App | n/a (housekeeping only - deploy is `deploy.yml`) | direct (App is on ruleset bypass) |
| `update-counts.yml` | `csoh-ci` App | n/a (recomputes counts weekly) | direct (App is on ruleset bypass) |
| `update-resources.yml` | `csoh-ci` App + `CSOH_PAT` (for auto-approve) + `CLAUDE_CODE_OAUTH_TOKEN` (model auth) | n/a | via PR + auto-merge, only if the diff is `resources.html` alone |
| `deploy.yml` | auto-injected `GITHUB_TOKEN` (`id-token: write` for OIDC) | **keyless OIDC - no key** (GCP WIF, AWS IAM role, Azure federated cred) | no |
| `lint.yml`, `validate-html.yml`, `check-broken-links.yml`, `check-url-safety.yml` | auto-injected `GITHUB_TOKEN` | n/a | no |
| `check-pagespeed.yml`, `run-seo-audit.yml`, `check-reading-list-staleness.yml`, `check-meeting-staleness.yml`, `check-conference-staleness.yml` | auto-injected `GITHUB_TOKEN` (the three staleness checkers add `issues: write`; PageSpeed/SEO auditors stay `contents: read` and open issues via App/PAT) | n/a | no |

Every workflow declares an explicit top-level `permissions:` block scoping the auto-injected `GITHUB_TOKEN`. The read-only check workflows use `contents: read` (plus `pull-requests: write` where they post comments). The write-capable workflows (`update-news`, `normalize-urls`, `site-update-deploy`) declare `contents: read` for the auto-injected token, because they handle write access through the App instead - keeping the default token strictly minimal. `deploy.yml` adds `id-token: write` for the OIDC tokens GitHub mints for the three clouds' federation exchanges.

### Why we migrated from PATs to a GitHub App

The original CI design used two personal access tokens belonging to a human (Shawn): `PAT_TOKEN` (push, open PRs, enable auto-merge) and `APPROVAL_PAT_TOKEN` (approve the bot's own PRs, since GitHub blocks self-approval with the same identity). PATs are functional but carry several security properties we wanted to improve:

1. **Long-lived.** PATs don't expire unless you set an explicit expiry. Once granted, the token is valid until manually revoked. A leaked PAT remains useful to an attacker for as long as it takes you to notice.

2. **Broadly scoped (classic PATs especially).** A classic PAT with `repo` scope can read and write *every* repository the owning user has access to - public, private, and forked. Even fine-grained PATs are awkward to constrain to one repository while still permitting all the operations a busy CI pipeline needs.

3. **Tied to a personal identity.** Bot commits authored under a PAT show up as the human account on the audit log, blurring the distinction between automation and operator action. If the human leaves the project (or the org), every workflow that depends on their PAT breaks.

4. **No native rotation.** Rotating a PAT means generating a new one, updating every secret, and revoking the old one - a manual process that tends to get postponed.

A GitHub App fixes all four:

1. **Short-lived tokens.** The App's installation tokens are valid for ~1 hour. A workflow run requests a fresh token at job start; that token is the only thing exposed to the workflow log redaction layer. After the run finishes, the token is useless.

2. **Per-repo scoping by default.** The App is installed on the single `CloudSecurityOfficeHours/csoh.org` repository with the minimum permissions needed (`contents: read+write`, `pull-requests: read+write`). The token GitHub mints from those install settings cannot do more than the App's installation scope allows.

3. **Independent identity.** The App is its own first-class GitHub principal (`csoh-ci[bot]`). Audit logs cleanly distinguish bot pushes from human pushes. The App outlives any individual contributor.

4. **Automatic rotation.** Tokens rotate every hour with no human intervention. The only long-lived secret is the App's RSA private key, which only needs rotating when you suspect it's compromised (or as part of a periodic key-rotation hygiene pass).

In numbers: blast radius of a leaked CI token went from "everything Shawn's PAT can touch, until manual revocation" → "one repo, one workflow run's worth of actions, ~1 hour."

### App configuration

- **Installation:** `csoh-ci` is installed on `CloudSecurityOfficeHours/csoh.org` only - not at the org-wide level.
- **Repository permissions:** `contents: read & write`, `pull-requests: read & write`. No other permissions granted.
- **Webhooks:** disabled. The App is purely an authentication identity; it does not consume events.
- **Branch protection / rulesets:** `csoh-ci` is on the main-branch ruleset bypass list with mode "Always," because `site-update-deploy.yml` does direct in-place commits to `main` (with `[skip ci]` markers) for housekeeping (SRI hashes, sitemap dates, normalized URLs, generated preview images). PRs from `update-news.yml` and `normalize-urls.yml` go through the normal merge path and don't need the bypass.

### Token retrieval pattern

Every workflow that needs write access starts with the same step:

```yaml
- name: Mint installation token
  id: app-token
  uses: actions/create-github-app-token@bcd2ba49218906704ab6c1aa796996da409d3eb1  # v3.2.0
  with:
    client-id: ${{ secrets.CSOH_CI_CLIENT_ID }}
    private-key: ${{ secrets.CSOH_CI_PRIVATE_KEY }}
```

Subsequent steps reference `${{ steps.app-token.outputs.token }}` wherever they previously used `${{ secrets.PAT_TOKEN }}` (e.g., `actions/checkout`'s `token:` input, `peter-evans/create-pull-request`'s `token:` input, `git remote set-url origin "https://x-access-token:${TOKEN}@..."`).

### Why one PAT remains: GitHub auto-merge does not honor ruleset bypass

GitHub does not allow an actor to approve its own PRs (this restriction applies to GitHub Apps too - an App that opens a PR cannot approve it). The main-branch ruleset has a `pull_request` rule requiring 1 approval before merging.

We initially expected that putting the `csoh-ci` App on the ruleset's **bypass list** with mode `Always` would let the App auto-merge its own PRs without any approval - the bypass should apply to *all* rules including `pull_request`, and the merge action is performed by the App. **Empirically, this is not the case.** Verified on 2026-05-08 with PR #650:

- All required status checks: passing
- App on bypass list with `mode: always`
- Auto-merge enabled by the App
- Result: `mergeStateStatus: BLOCKED`, `reviewDecision: REVIEW_REQUIRED` - auto-merge sat indefinitely

GitHub's auto-merge feature evaluates `reviewDecision` independently and does not consult the bypass list. (Bypass *does* work for direct API merges by the same actor - it's specific to the auto-merge scheduler.) So one narrow PAT remains: `CSOH_PAT`, a fine-grained org-scoped token used exclusively to approve PRs that the App has just opened, satisfying the approval rule so that auto-merge can fire.

`normalize-urls.yml` keeps its "human reviews + merges" flow without an auto-approve step; the auto-approve there was a one-click convenience and added no real safety. Removing it is a strict improvement (humans now click both "approve" and "merge" instead of just "merge").

`site-update-deploy.yml` is unaffected - it does direct in-place commits to `main` (not via PR), and the App's bypass *does* apply to direct pushes.

### Repository secrets currently in use

| Secret | Purpose | Type |
|--------|---------|------|
| `CSOH_CI_CLIENT_ID` | GitHub App's Client ID (`Iv23.*`) | identifier (not sensitive on its own) |
| `CSOH_CI_PRIVATE_KEY` | GitHub App's RSA private key | high-sensitivity |
| `CSOH_PAT` | Approve App-opened PRs (auto-merge driver) | medium-sensitivity (narrow scope) |
| `CLAUDE_CODE_OAUTH_TOKEN` | `update-resources.yml` model auth (subscription quota, not API billing) | medium-sensitivity |
| `PSI_API_KEY` | `check-pagespeed.yml` - Google PageSpeed Insights v5, restricted to that one API | low-sensitivity |
| `CLOUDFLARE_API_TOKEN` | `deploy.yml` cache purge - scoped to Zone → Cache Purge on `csoh.org` alone | medium-sensitivity |
| `SSH_PRIVATE_KEY` | **Unused.** No workflow references it - left over from the retired FTPS/shared-host era. A high-sensitivity secret that nothing consumes is pure downside; delete it. | high-sensitivity |

Non-secret identifiers live in repo **Variables**, not Secrets, and are populated
from `terraform output` (see [infra/README.md](infra/README.md)):
`AWS_PUBLISHER_ROLE_ARN`, `AWS_BUCKET_NAME`, `AWS_CLOUDFRONT_DISTRIBUTION_ID`,
`AZURE_CLIENT_ID`, `AZURE_STORAGE_ACCOUNT`, `CLOUDFLARE_ZONE_ID`.

**No origin-cloud secret in this list - that's deliberate, for all three clouds.** The `deploy.yml` workflow needs no service-account key, no AWS access key, no Azure client secret, and no project-scoped PAT. Each cloud authenticates by exchanging GitHub's per-run OIDC token for short-lived (~1-hour) access, gated by a policy that requires the token's repo claim to equal `CloudSecurityOfficeHours/csoh.org` on `main`:

1. **GCP** - Workload Identity Federation exchanges the OIDC token for a token scoped to impersonate `csoh-deployer` (`roles/run.admin`, `roles/artifactregistry.writer`, `iam.serviceAccountUser` on the runtime SA). The runtime SA `csoh-run-runtime` has **zero IAM roles**.
2. **AWS** - `sts:AssumeRoleWithWebIdentity` returns credentials for the `csoh-site-publisher` role, scoped to write the one S3 bucket and invalidate the one CloudFront distribution.
3. **Azure** - an Entra app federated credential yields a token whose service principal holds only "Storage Blob Data Contributor" on the one storage account.

Net effect: a leaked workflow log compromises at most three ~1-hour tokens, each scoped to one repo's publish permissions on one resource per cloud. There is no long-lived credential to rotate or revoke for any of them.

**The one exception is Cloudflare.** Cloudflare offers no OIDC federation, so the
`purge-cloudflare` job in `deploy.yml` uses a stored `CLOUDFLARE_API_TOKEN`. It
is deliberately the narrowest token the API allows: a single permission,
Zone → Cache Purge, with Zone Resources limited to `csoh.org`. It cannot read
DNS, edit rules, view analytics, or touch any other zone - the worst an attacker
could do with it is repeatedly cold the cache. That is worth documenting rather
than glossing: it is the only long-lived credential in the deploy path, and the
only one that needs a manual rotation cadence.

`PAT_TOKEN` (the original CI PAT), `CSOH_CI_APP_ID` (deprecated numeric input, replaced by `CSOH_CI_CLIENT_ID`), and `APPROVAL_PAT_TOKEN` (replaced by `CSOH_PAT`) have all been removed.

`CSOH_PAT` is a **fine-grained PAT** scoped to `CloudSecurityOfficeHours/csoh.org` only, with permissions limited to **Pull requests: Read & Write** (no contents, no actions, no anything else). Even if it leaks, the only damage an attacker can do is approve PRs - they cannot push, merge by themselves, or read code beyond what's already in the public repo. Replaced the broader classic-PAT `APPROVAL_PAT_TOKEN` on 2026-05-08.

### Rotation guidance

| Item | Rotation cadence | Process |
|------|-----------------|---------|
| App installation token | Automatic, every ~1 hour | None - handled by GitHub |
| App private key | Annually or on suspected compromise | Generate new key in App settings; replace `CSOH_CI_PRIVATE_KEY` secret; revoke old key |
| `CSOH_PAT` | Every 6-12 months (or before its set expiry) | Generate new fine-grained PAT (resource owner: `CloudSecurityOfficeHours`, repo: `csoh.org`, permission: pull-requests: write only); replace org-level Actions secret |
| Cloud access tokens (GCP/AWS/Azure) | Automatic, every ~1 hour | None - minted per workflow run via OIDC, no stored credential on any cloud |
| `CLOUDFLARE_API_TOKEN` | Every 6-12 months, or on suspected compromise | Cloudflare → My Profile → API Tokens → roll; recreate as a Custom token with the single permission Zone → Cache Purge, Zone Resources limited to `csoh.org`; replace the Actions secret |
| `CLAUDE_CODE_OAUTH_TOKEN` | On suspected compromise, or when it expires | Re-run `claude setup-token` locally and replace the Actions secret |
| `PSI_API_KEY` | Low urgency - it is rate-limit-scoped, not privileged | Regenerate in Google Cloud console credentials, keep the "PageSpeed Insights API" restriction, replace the Actions secret |
| GCP runtime SA roles | On every Terraform apply | The runtime SA's IAM bindings live in [`infra/terraform/gcp/service_accounts.tf`](infra/terraform/gcp/service_accounts.tf) - review on every change |

---

## Deployment Security

### Multi-cloud deploy

`deploy.yml` builds the site once and publishes it active/active to three cloud origins on every push to `main` that touches site files.

**Authentication - keyless OIDC to every cloud, no stored credential:**
- GitHub Actions mints an OIDC token for the run; each cloud exchanges it for short-lived (~1 hour) access, gated by a policy that requires the token's repo claim to equal `CloudSecurityOfficeHours/csoh.org` on branch `main`:
  - **GCP** - Workload Identity Federation impersonates the `csoh-deployer` SA, scoped to push images + deploy Cloud Run revisions ([`infra/terraform/gcp/wif.tf`](infra/terraform/gcp/wif.tf)).
  - **AWS** - `sts:AssumeRoleWithWebIdentity` into the `csoh-site-publisher` IAM role, scoped to write the one bucket + invalidate the one CloudFront distribution ([`infra/terraform/aws/oidc.tf`](infra/terraform/aws/oidc.tf)).
  - **Azure** - an Entra app federated credential, scoped to "Storage Blob Data Contributor" on the one storage account ([`infra/terraform/azure/identity.tf`](infra/terraform/azure/identity.tf)).
- The GCP runtime SA the container runs as (`csoh-run-runtime`) has **zero IAM roles**. The AWS and Azure origins run no code, so they have no runtime identity to abuse.

**What gets published, and the publish allowlist:**
- The object-storage origins (S3, Azure Blob) have no request-time access rules, so the build never uploads sensitive files. `tools/stage_site.sh` produces a `dist/` containing only the public file set; its allowlist [`tools/site-publish.filter`](tools/site-publish.filter) mirrors the nginx block rules + Dockerfile strip list, and the build fails if a secret-shaped file appears in `dist/`.

**GCP image supply chain (the one origin that ships a container):**
- Base image (`nginx:1.27-alpine`) is **digest-pinned** in the [`Dockerfile`](Dockerfile). A compromised registry tag cannot ship malicious bytes into our build.
- `RUN apk upgrade --no-cache` after `FROM` refreshes Alpine packages on top of the pinned base.
- The container is **Trivy-scanned** for HIGH and CRITICAL CVEs (with fixes available); the build fails if any are found.
- Artifact Registry has `immutable_tags=true` - a pushed tag cannot be overwritten or moved. Cloud Run revisions pin a specific SHA tag, so rollback is `gcloud run services update-traffic --to-revisions <name>=100`.
- Cleanup policy keeps the most recent 30 versions and deletes untagged versions older than 7 days.

**Workflow hardening:**
- `permissions:` block scopes the auto-injected `GITHUB_TOKEN` to `contents: read` + `id-token: write` (id-token is required for the OIDC exchanges; nothing else is granted).
- Every publish job is gated by the `production` GitHub Environment, configured to allow deployments only from `main` and to enforce Code Owners review on the workflow file via [`.github/CODEOWNERS`](.github/CODEOWNERS). A PR from a fork cannot reach this code path even if it could otherwise mint an OIDC token, because protected-environment policies only apply on `main`.

**Edge defenses (Cloudflare, in front of all three origins):**
- **WAF** - Cloudflare's free Managed Ruleset plus a rate-limit rule (lighter than the previous Cloud Armor OWASP CRS; a static site has no SQL/login to attack).
- **TLS** - Full (strict) to every origin; TLS 1.2+ floor; HSTS preload.
- **Security headers + legacy redirects** set once at the edge (mirroring `nginx-security-headers.conf` and the old `.htaccess` rules), applied regardless of which origin serves.
- **Always Use HTTPS** handles HTTP→HTTPS; no origin has a plain-HTTP path.

**Logging:**
- Cloudflare zone analytics + Load Balancer health cover edge/total-traffic visibility and WAF blocks. On GCP, Cloud Run non-2xx, IAM admin activity, and audit logs route to a 400-day retention bucket via the security log sink in [`infra/terraform/gcp/logging.tf`](infra/terraform/gcp/logging.tf) (the default `_Default` sink only retains 30 days).

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
| `seo-audits/` | Internal audit reports |
| `dist/`, `.ruff_cache/` | Build and lint artifacts |
| `Dockerfile`, `docker-compose.yml`, `nginx.conf`, `nginx-security-headers.conf`, `pyproject.toml` | Server/container config - useful to an attacker, useless to a visitor |
| `*.json` except the four allowlisted above | Internal data files |
| `*.bak`, `*.log`, `*.ini`, `*.sql`, `*.config`, `*-report.txt` | Backups, logs, configs, internal reports |
| `*.pem`, `*.key`, `*.crt` | Key material (also a hard build failure - see below) |
| *(not excluded)* `.well-known/` | Explicitly **allowed** past the `- .*` catch-all - it must be public for RFC 9116. See File Access Controls above. |

`tools/stage_site.sh` does not just trust the filter: after staging it runs a
belt-and-braces `find` for `.env*`, `*.pem`, `*.key`, `*.crt`, and `*.py` in
`dist/` and **fails the build** if any are present, plus a sanity floor that
aborts if fewer than 100 files were staged (a near-empty `dist/` means
something upstream broke and would publish a hollow site).

### Docker Security

The `Dockerfile` + `nginx.conf` pair is not a side path - it **is** the GCP Cloud Run
origin, one of the three production origins. It is also what `docker-compose.yml`
runs locally, so the local container behaves like production:
- All sensitive files are removed during the Docker build (`rm -rf .git, tools, *.py, *.md`, etc.)
- `nginx.conf` mirrors all `.htaccess` security headers and access controls
- `server_tokens off` suppresses nginx version disclosure

---

## Vulnerability Disclosure

If you discover a security vulnerability on csoh.org:

- **Email:** admin@csoh.org
- **security.txt:** https://csoh.org/.well-known/security.txt (RFC 9116
  canonical location), mirrored at https://csoh.org/security.txt
- **Community:** Bring it up during our Friday Zoom session

We take security seriously - especially as a cloud security community.

---

## Known Limitations

| Item | Status | Notes |
|------|--------|-------|
| `http://flaws.cloud` link | Intentional | This AWS security training site only serves over HTTP. The link is intentional. |
