# Security Documentation - csoh.org

This document describes the security measures in place for [csoh.org](https://csoh.org), a static website for the Cloud Security Office Hours community.

---

## Architecture

csoh.org is a **pure static site** - no server-side code, no database, no user accounts, no cookies, no sessions. This eliminates entire classes of vulnerabilities (SQL injection, RCE, auth bypass, session hijacking, CSRF).

**Hosting is multi-cloud: the same static site is served active/active from three origins** - AWS (private S3 + CloudFront), GCP (Cloud Run), and Azure (Blob static website) - behind a single **Cloudflare** edge that terminates TLS (Full strict to every origin), caches, runs the WAF and security headers, applies legacy redirects, and load-balances across the origins with health-check failover. GitHub Actions builds the site once and publishes to all three via **keyless OIDC** (GCP Workload Identity Federation, an AWS IAM role, an Azure Entra federated credential) - there is no long-lived cloud credential anywhere. The full architecture, cost, and cutover runbook are in [infra/README.md](infra/README.md); the layer-by-layer security walkthrough is the public [cloud-deployment.html](cloud-deployment.html).

The site previously deployed via FTPS to a LiteSpeed shared host. That path was retired after the cutover to GCP - the FTPS step is removed from `site-update-deploy.yml`, the standalone `manual-deploy.yml` workflow is deleted, and the `FTP_*` secrets are gone.

---

## HTTP Security Headers

All responses from csoh.org include these security headers. They are declared in
**three** places, and all three have to stay in step by hand - CI asserts only
the first row (see [Edge header drift is a CI gate](#edge-header-drift-is-a-ci-gate)):

| Where | Covers | File |
|-------|--------|------|
| Cloudflare edge ruleset (`csoh-security-headers`) | every response, whichever origin served it | [`infra/terraform/cloudflare/rules.tf`](infra/terraform/cloudflare/rules.tf) |
| GCP origin (nginx on Cloud Run) | responses served by that origin directly | [`nginx-security-headers.conf`](nginx-security-headers.conf), `include`d into every `location` block of `nginx.conf` |
| AWS origin (CloudFront response headers policy) | responses served by that distribution directly | [`infra/terraform/aws/cloudfront.tf`](infra/terraform/aws/cloudfront.tf) |

The origin-level copies are not redundancy for its own sake. Each origin
hostname is reachable on its own (CloudFront's `*.cloudfront.net` name is
public), so an origin without its own headers is a fully functional, header-free
mirror of the site for anyone who finds it, and it has no defense of its own if
the edge is misconfigured. The AWS distribution was in exactly that state until
2026-07-25; see [Security Remediation - 2026-07-25](#security-remediation---2026-07-25).

**Azure Blob static websites cannot emit custom response headers at all**, so
that origin has no independent copy and depends entirely on the edge. That is a
known, accepted gap rather than an oversight.

`.htaccess` is **not** a fourth source. It is a vestige of the retired LiteSpeed
shared host - the Docker build deletes it from the image and the publish filter
never uploads it to the object-storage origins. Do not edit it expecting a
production effect.

The header values themselves:

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
- The CSP string is byte-identical in all three sources listed above (`rules.tf`, `nginx-security-headers.conf`, `cloudfront.tf`). Drift between the repo and the live edge is a CI failure, not a silent regression - see [Edge header drift is a CI gate](#edge-header-drift-is-a-ci-gate)

In addition to CSP, the following cross-origin isolation headers are set:

- `Cross-Origin-Opener-Policy: same-origin` - only same-origin windows can hold a reference to ours; defends against cross-origin info leaks via `window.opener` and Spectre-class side channels.
- `Cross-Origin-Resource-Policy: same-origin` - resources from this origin can only be loaded by same-origin contexts; stops arbitrary sites from embedding our images/scripts/etc.

### Edge header drift is a CI gate

The `csoh-security-headers` ruleset in `rules.tf` carries
`lifecycle { ignore_changes = [rules] }`, a deliberate workaround for a
cloudflare v4 provider bug that returns the multi-header block in a
non-deterministic order. **Know what that workaround costs:** `rules` is the
only meaningful attribute of a `cloudflare_ruleset`, so ignoring it leaves the
resource inert after creation. You can tighten the CSP in Git, run
`terraform apply`, get a clean plan, and ship nothing - while the diff, the
commit, and any reviewer all believe the change went live.

Terraform cannot police that, so CI asserts it from the outside.
[`tools/check_edge_headers.py`](tools/check_edge_headers.py) parses the eight
header name/value pairs out of `rules.tf` and compares them against what the
live site actually returns:

```bash
python3 tools/check_edge_headers.py                       # 40 samples of https://csoh.org/
python3 tools/check_edge_headers.py --url <origin> --samples 1   # one origin directly
```

**It samples, and the sampling is the point.** The apex is a load balancer over
three origins, and AWS and GCP now set these headers themselves - so a response
from either looks correct *even if the Cloudflare ruleset were deleted
outright*. Only an Azure-served response actually exercises the edge, because
Azure Blob cannot emit custom headers at all. A single request has no say in
which origin answers, so the checker makes 40 cache-busted requests by default
(`--samples`, each with a unique query string so a cached response cannot
re-confirm whichever origin replied first), prints which origins it reached,
and warns when it never reached Azure - because such a run did not test what it
claims to. That default is empirical, not a guess: on 2026-07-26 two
consecutive 25-sample runs reached Azure zero times. Use `--samples 1` only
when pointing at a single origin hostname, where there is nothing to sample.

**It checks the edge, and only the edge.** The CloudFront response-headers
policy and `nginx-security-headers.conf` are *not* asserted by CI against
anything. See invariant 4 below: keeping the three locations in step is a
manual discipline, and a run against the apex that happens to sample only
AWS/GCP responses tells you the origins are healthy, not that the edge is.

The `purge-cloudflare` job in `deploy.yml` runs it after the existing SRI
verification and **fails the deploy on any drift** - a forgotten apply, a
dashboard edit, or someone with the Cloudflare API token weakening a header.
That job had no checkout of its own, so an `actions/checkout` step (with
`persist-credentials: false`) was added just to fetch the checker.

Delete the script and that step when the cloudflare v5 provider upgrade lets
`ignore_changes` go away and Terraform manages the ruleset for real again.

---

## File Access Controls

`nginx.conf` (the GCP origin, and the local Docker container) blocks direct
access to sensitive files. `.htaccess` still carries the equivalent Apache rules
but is inert - see the note under HTTP Security Headers. On the two
object-storage origins there is no request-time rule to apply, so the equivalent
control is "never upload it": see `tools/site-publish.filter` below.

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
1. Calculates SHA-384 hashes for every asset in its `ASSETS` list - currently `style.css`, `main.js`, `chat-resources.js`, `breach-timeline.css`, `breach-timeline.js`, `meetings.js`, `glossary.js`, `404.js`, `search.css`, `search-init.js`, and the vendored `vendor/goatcounter-count.js`. Any new shared asset must be added to that list or it ships with neither an integrity hash nor a cache-bust key. **`vendor/minisearch-7.1.2.min.js` is deliberately not on the list**: it is a pinned, never-edited upstream release, so its hash is stable and is written directly into `search.html` with a comment saying so. If you ever bump that pin, the hash is yours to update by hand - `update_sri.py` will not notice
2. Updates the `integrity` attribute in all HTML files
3. Adds cache-busting `?v=` parameters derived from the hash
4. Runs automatically in CI - `site-update-deploy.yml` stamps the repo, and `deploy.yml` re-stamps the build output before staging, so the published artifact is self-consistent even if a commit landed with stale hashes

This means even if the hosting account were compromised and files were tampered with, browsers would refuse to execute the modified scripts.

**The vendored files are not pristine upstream copies.**
`vendor/goatcounter-count.js` carries two local modifications, each marked in
the source with a `CSOH LOCAL MODIFICATION` comment.
[`vendor/README.md`](vendor/README.md) documents both vendored libraries, their
licenses, and those edits. Re-vendoring a newer upstream release overwrites them
silently, which in the GoatCounter case would quietly resume sending data
`privacy.html` promises we do not collect. Re-apply the modifications and re-run
`python3 update_sri.py` after any re-vendor.

---

## JavaScript Security

**XSS Prevention:**
- All user input (search queries, URL parameters) is passed through a `sanitize()` function that uses `textContent` encoding - the safest DOM-based sanitization method
- No `eval()`, no `document.write()`, no `Function()` constructors
- `innerHTML` is only used with sanitized or non-user-controlled content

**External Link Protection:**
- All `target="_blank"` links automatically receive `rel="noopener noreferrer"` via JavaScript enforcement on page load
- This prevents reverse tabnapping attacks

**No Remotely-Loaded JavaScript:**
- **Nothing is fetched from a third-party host.** Every `<script>` on the site points at `csoh.org`, so `script-src` stays `'self'` and a CDN compromise is not an attack path. There are no tracking pixels and no remote libraries
- **Two of those scripts are third-party *code*, vendored and served first-party**, and the distinction matters when you audit supply chain rather than network origin: [`vendor/goatcounter-count.js`](vendor/goatcounter-count.js) (the GoatCounter loader, on every page) and [`vendor/minisearch-7.1.2.min.js`](vendor/minisearch-7.1.2.min.js) (MiniSearch, on `/search.html` only). Both carry an SRI `integrity` attribute, so a tampered copy is refused by the browser even though it is served from our own origin. MiniSearch is pinned to an exact version and hand-stamped in `search.html` rather than managed by `update_sri.py` - the file is static and never regenerated, so its hash does not move
- **Analytics: the script is ours, the service is not.** The loader is self-hosted, but it beacons to `csoh.goatcounter.com`, which is where the counting actually happens - that is why `csoh.goatcounter.com` appears in `img-src` and `connect-src` in the CSP. GoatCounter is cookieless, stores no IP address, and does no cross-site tracking, but it is still a third party receiving a request per pageview
- **What the beacon carries, precisely:** page path, `Referer`, page title, an event flag, screen width, and a bot flag; the receiving end additionally sees the `User-Agent`, from which GoatCounter derives browser and OS. Not "page path only"
- **The query string is stripped from what the beacon sends.** Upstream GoatCounter transmits `location.search` twice - as a dedicated `q` field and appended to the `p` (path) field. On this site that leaked visitor search terms, because `/search.html?q=<term>` is a deep-linkable URL (`search-init.js` reads `params.get('q')`). Both are patched out locally (`q: ''`, and `get_path` returns `loc.pathname` alone), so no search term leaves the browser. See [`vendor/README.md`](vendor/README.md)

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

### Redirect destinations are not trusted markup

`tools/normalize_urls.py` follows redirects and rewrites links to their final
destination. That destination comes verbatim from an external site's `Location`
header (via `resolve_url` in `check_url_safety.py`) and is substituted into page
HTML with a plain `str.replace`, i.e. straight inside `href="..."`. Because
`site-update-deploy.yml` runs `normalize_urls.py --apply` on every push to `main`
that touches HTML - holding a repo-write App token - a host answering with

```
Location: https://ok.example/a"><script src=...></script>
```

would have gotten that markup written into every page linking to it, committed,
and deployed. The realistic route in is a linked domain that expired and was
re-registered, which this repo already tracks as a recurring class of dead link.

Before the reputation check runs, any resolved URL containing `"`, `'`, `<`,
`>`, a backtick, a backslash, or whitespace - or not starting with `http://` or
`https://` - is now rejected into the existing `skipped_unsafe_destination`
category, and the pre-resolution URL is kept instead. A real URL never contains
those characters unescaped, so the check costs nothing.

### Feed text inside JSON-LD

`update_news.py` writes a `<script type="application/ld+json">` block into
`news.html` from RSS feed titles and summaries, which are attacker-influenceable
(compromised vendor blog, hijacked feed host, expired-and-re-registered feed
domain) - and, since these are security news feeds, a legitimate post about an
XSS payload can produce the same bytes by accident. It used to escape only `</`,
which stops a literal `</script>` but nothing else: an HTML parser also ends a
script block's contents at a `<!--` comment opener. It now rewrites every `<`,
`>`, and `&` to `\u003c`, `\u003e`, and `\u0026` after `json.dumps`. Those are
valid JSON string escapes, so Google, schema.org validators, and anything doing
`json.loads` still see the original characters - the structured data is
unchanged, and only the HTML parser is affected.

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

The browser fetches nothing from a third-party host: no CDN-hosted JavaScript, no CSS framework, no web fonts. This eliminates CDN compromise as an attack vector. Two third-party *libraries* are in the tree - `vendor/goatcounter-count.js` and `vendor/minisearch-7.1.2.min.js` - but both are vendored, version-pinned, and served from `csoh.org` under an SRI hash, so a supply-chain change can only arrive through a commit in this repo.

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
| `update-resources.yml` | `csoh-ci` App (checked out with `persist-credentials: false`) + `CSOH_PAT` (for auto-approve) + `CLAUDE_CODE_OAUTH_TOKEN` (model auth) | n/a | via PR + auto-merge, only if the diff is `resources.html` alone |
| `deploy.yml` | auto-injected `GITHUB_TOKEN` (`id-token: write` for OIDC) | **keyless OIDC - no key** (GCP WIF, AWS IAM role, Azure federated cred) | no |
| `lint.yml`, `validate-html.yml`, `check-broken-links.yml`, `check-url-safety.yml` | auto-injected `GITHUB_TOKEN` | n/a | no |
| `check-pagespeed.yml`, `run-seo-audit.yml`, `check-reading-list-staleness.yml`, `check-meeting-staleness.yml`, `check-conference-staleness.yml` | auto-injected `GITHUB_TOKEN` (the three staleness checkers add `issues: write`; PageSpeed/SEO auditors stay `contents: read` and open issues via App/PAT) | n/a | no |

Every workflow declares an explicit top-level `permissions:` block scoping the auto-injected `GITHUB_TOKEN`. The read-only check workflows use `contents: read` (plus `pull-requests: write` where they post comments). The write-capable workflows (`update-news`, `normalize-urls`, `site-update-deploy`) declare `contents: read` for the auto-injected token, because they handle write access through the App instead - keeping the default token strictly minimal. `deploy.yml` adds `id-token: write` for the OIDC tokens GitHub mints for the three clouds' federation exchanges.

`normalize-urls.yml` was the exception until 2026-07-25: it granted the ambient
token `contents: write` + `pull-requests: write` even though no step used
either - both `actions/checkout` and `peter-evans/create-pull-request` are
handed the App token explicitly, and nothing in the job calls `gh` or reads
`GITHUB_TOKEN`. It is now `contents: read`, which every other workflow in the
repo already declared. When you
copy a workflow as a starting point, re-derive its `permissions:` from what its
steps actually do rather than inheriting the block.

### Untrusted input meets a credential: `update-resources.yml`

This is the one workflow where a model reads attacker-influenceable content
(`WebFetch`/`WebSearch` over the open web) inside a job that holds real
credentials: the `csoh-ci` installation token, `CLAUDE_CODE_OAUTH_TOKEN`, and
`id-token: write` at workflow scope. Three properties keep that from being an
arbitrary-code-execution path, and **none may be relaxed**:

1. **No shell at all in `--allowedTools`.** The allowlist is exactly
   `Read,Edit,Glob,Grep,WebSearch,WebFetch`. Every entry is an in-process tool
   and no `Bash(...)` pattern remains. It got there in two removals.
   `Bash(python3:*)` went first: it matches `python3 -c '<anything>'`, i.e. a
   full interpreter reachable by prompt injection in a fetched page, which made
   the rest of the list decorative. `Bash(grep:*)` and `Bash(wc:*)` went second,
   and that is the subtler one - `grep` takes a path like nearly every Unix
   command, so `Bash(grep:*)` was a read primitive over the whole runner
   filesystem, `/proc/self/environ` included. The built-in `Grep` tool that
   remains searches the checked-out workspace and is not a shell. If a future
   prompt genuinely needs Python, add a checked-in script and allowlist that
   exact path - never the interpreter itself.
2. **The `csoh-ci` App token is minted after the model step, not before.** The
   mint step sits immediately above the create-PR step that consumes it, so the
   credential that can write to this repo does not exist on the runner while the
   model is reading the open web. Moving it back to the top of the job, where
   mint steps conventionally go, silently undoes this. What is reachable during
   the research pass is `CLAUDE_CODE_OAUTH_TOKEN`, which buys model usage and
   grants nothing in this repo or in any cloud account.
3. **`persist-credentials: false` on that job's `actions/checkout`.** By default
   checkout leaves whatever token it used in `.git/config` as an
   `http.extraheader` for the remainder of the job, where any later step could
   read it back out with a plain file read. Nothing after the clone talks to git;
   the `create-pull-request` step is passed the token explicitly.

Properties 2 and 3 matter more than they look because `csoh-ci` is on the `Main`
ruleset's bypass list with mode "Always" (see [App configuration](#app-configuration)),
so a leaked installation token is a direct push to `main`, not just a PR.

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

### Repository secrets

Everything below is a live secret. **Do not read this table by itself as the
inventory** - it is a description of the inventory, and the two drift apart. It
did: this table carried an `SSH_PRIVATE_KEY` row marked "live but unreferenced,
flagged for removal, still present", re-confirmed by hand on 2026-07-26. The
secret had in fact already been deleted, and the `ZOOM_*` set was live and
undocumented here at the same time. A hand-maintained list of secrets is exactly
as trustworthy as the last time somebody diffed it against the API.

So the diff is now a script rather than a habit:

```bash
python3 tools/rotate_secrets.py            # inventory, drift, rotation ages
python3 tools/rotate_secrets.py audit --check   # exit 1 on drift (CI gate)
```

It derives what is *referenced* by scanning the workflows, reads what *exists*
from the API, and fails on any of: a referenced secret that does not exist, an
existing secret nothing reads, a referenced secret with no registry entry (and
therefore no rotation plan), or anything past its cadence. It also prints which
of its checks it could not run and why, because org-level secrets need
`admin:org` and neither `GITHUB_TOKEN` nor the default local token has it. Full
rationale in [tools/ROTATE_SECRETS_README.md](tools/ROTATE_SECRETS_README.md).

To check by hand anyway:

```bash
gh api repos/CloudSecurityOfficeHours/csoh.org/actions/secrets \
  --jq '.secrets[] | "\(.name) \(.updated_at)"'          # what exists
grep -rhoE 'secrets\.[A-Z_0-9]+' .github/workflows/ | sort -u   # what is referenced
```

(The first command lists repo-level secrets only. `CSOH_CI_CLIENT_ID`,
`CSOH_CI_PRIVATE_KEY` and `CSOH_PAT` are org-level, so they appear in the second
list and not the first. The second over-reports: six workflows document the
`${{ secrets.NAME }}` syntax in comments, so `NAME` shows up as a secret.)

| Secret | Scope | Purpose | Type |
|--------|-------|---------|------|
| `CSOH_CI_CLIENT_ID` | org | GitHub App's Client ID (`Iv23.*`) | identifier (not sensitive on its own) |
| `CSOH_CI_PRIVATE_KEY` | org | GitHub App's RSA private key | high-sensitivity |
| `CSOH_PAT` | org | Approve App-opened PRs (auto-merge driver) | medium-sensitivity (narrow scope) |
| `CLAUDE_CODE_OAUTH_TOKEN` | repo | `update-resources.yml` model auth (subscription quota, not API billing) | medium-sensitivity |
| `PSI_API_KEY` | repo | `check-pagespeed.yml` - Google PageSpeed Insights v5, restricted to that one API | low-sensitivity |
| `CLOUDFLARE_API_TOKEN` | repo | `deploy.yml` cache purge - scoped to Zone → Cache Purge on `csoh.org` alone | medium-sensitivity |
| `ZOOM_ACCOUNT_ID` | repo | `publish-recaps.yml` - Zoom account id for the Server-to-Server OAuth grant | identifier |
| `ZOOM_CLIENT_ID` | repo | `publish-recaps.yml` - S2S OAuth app client id | identifier |
| `ZOOM_CLIENT_SECRET` | repo | `publish-recaps.yml` - S2S OAuth app secret; the grant it buys is scoped to reading meetings, summaries and recordings, with no user or write scopes | medium-sensitivity |

The **Scope** column is load-bearing, not decorative. A repo-level secret
shadows an org-level one of the same name, so writing the value at the wrong
level updates something nothing reads: the write succeeds, the inventory looks
right, and CI keeps using the old credential. `rotate_secrets.py` resolves the
scope from the API rather than from this table for exactly that reason.

`SSH_PRIVATE_KEY` (a leftover from the retired FTPS/shared-host era, last
updated 2026-02-18, read by no workflow) has been deleted. Confirmed absent from
the repo's secret list on 2026-08-09.

Non-secret identifiers live in repo **Variables**, not Secrets, and are populated
from `terraform output` (see [infra/README.md](infra/README.md)):
`AWS_PUBLISHER_ROLE_ARN`, `AWS_BUCKET_NAME`, `AWS_CLOUDFRONT_DISTRIBUTION_ID`,
`AZURE_CLIENT_ID`, `AZURE_STORAGE_ACCOUNT`, `CLOUDFLARE_ZONE_ID`.

**No origin-cloud secret in this list - that's deliberate, for all three clouds.** The `deploy.yml` workflow needs no service-account key, no AWS access key, no Azure client secret, and no project-scoped PAT. Each cloud authenticates by exchanging GitHub's per-run OIDC token for short-lived (~1-hour) access. **All three now pin the same OIDC subject:** `repo:CloudSecurityOfficeHours/csoh.org:environment:production`. Repo alone is not enough - it would trust every workflow in the repo on every branch, including the scheduled jobs that read untrusted web content. Pinning the *environment* is stronger than pinning the ref, because the `production` GitHub Environment is itself restricted to `main` by a deployment branch policy, so the environment pin enforces the branch transitively **and** requires the job to actually declare `environment: production`.

1. **GCP** - Workload Identity Federation exchanges the OIDC token for a token scoped to impersonate `csoh-deployer` (`roles/run.admin`, `roles/artifactregistry.writer`, `iam.serviceAccountUser` on the runtime SA). The trust is pinned in two places in [`wif.tf`](infra/terraform/gcp/wif.tf): the provider's `attribute_condition` requires both `assertion.repository` and `assertion.sub == 'repo:<owner>/<repo>:environment:production'`, and the IAM member is a `principal://.../subject/repo:<owner>/<repo>:environment:production` rather than a repo-wide `principalSet://`. The runtime SA `csoh-run-runtime` has **zero IAM roles**.
2. **AWS** - `sts:AssumeRoleWithWebIdentity` returns credentials for the `csoh-site-publisher` role, scoped to write the one S3 bucket and invalidate the one CloudFront distribution. `oidc.tf` pins `sub` with `StringEquals` to the same subject string.
3. **Azure** - an Entra app federated credential yields a token whose service principal holds only "Storage Blob Data Contributor" on the one storage account. `identity.tf` sets `subject` to the same string.

`var.github_branch` in [`infra/terraform/gcp/variables.tf`](infra/terraform/gcp/variables.tf) is **not** referenced by the WIF trust and never was. It is kept because it documents the intended branch and is consumed by the equivalent variables files in `aws/` and `azure/`; its comment now says so explicitly, so nobody reads it as evidence that branch enforcement lives in `wif.tf`.

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

Rotate with `python3 tools/rotate_secrets.py roll <SECRET>` (or `roll --due`)
rather than by hand. The manual columns below are what the script does, kept
here so the intent survives the script.

The script's value is the ordering and the checks, not the typing. It always
goes **mint → verify → write → confirm the write landed → revoke the old**, and
it verifies each new credential three ways before anything depends on it: the
operation CI performs must succeed, a deliberately corrupted copy must *fail*
(otherwise the probe proves nothing), and an operation the credential should be
too narrow for must be denied (otherwise the token is over-scoped and shipping
it is worse than shipping a broken one). Rotating by hand skips all of that:
`gh secret set` reports success against a typo, a truncated paste, or a token
created with the wrong permissions, and the first sign of trouble is a red
scheduled run days later.

| Item | Rotation cadence | Process |
|------|-----------------|---------|
| App installation token | Automatic, every ~1 hour | None - handled by GitHub |
| App private key | Annually or on suspected compromise | `roll CSOH_CI_PRIVATE_KEY`. GitHub has no API to generate an App key, so the script prints the App settings URL, takes the downloaded `.pem`, then signs a JWT with it and mints a real installation token to confirm it authenticates as `csoh-ci` and still grants `contents`+`pull_requests` write. Delete the old key only after that passes. |
| `CSOH_PAT` | Every 6-12 months (or before its set expiry) | `roll CSOH_PAT`. No API to create a fine-grained PAT; the script prints the exact settings (resource owner `CloudSecurityOfficeHours`, repo `csoh.org`, permission pull-requests: write only) and then verifies the new token can read PRs **and cannot read Actions secrets** - the latter is what makes the "even if it leaks, all it can do is approve PRs" claim above true rather than assumed. |
| Cloud access tokens (GCP/AWS/Azure) | Automatic, every ~1 hour | None - minted per workflow run via OIDC, no stored credential on any cloud |
| `CLOUDFLARE_API_TOKEN` | Every 6-12 months, or on suspected compromise | `roll CLOUDFLARE_API_TOKEN`. **Create a new Custom token (Zone → Cache Purge, Zone Resources `csoh.org` only) - do not use "Roll" on the existing one.** Rolling invalidates the value CI holds before a replacement has been verified, and Actions secrets are write-only, so there is no undo. Verification purges one harmless file and then confirms the token *cannot* read DNS. Fully automatic if `CLOUDFLARE_TOKENS_API_TOKEN` (User → API Tokens → Edit) is in `.env`; the Terraform token cannot do it (`9109`). |
| `ZOOM_CLIENT_SECRET` | Every 6-12 months, or on suspected compromise | `roll ZOOM_CLIENT_SECRET`. Regenerate in the Zoom Marketplace S2S OAuth app. Zoom invalidates the old secret **immediately**, so `publish-recaps.yml` is broken from that moment until the new value is written - keep the window short. Verification performs the account-credentials grant and then lists recordings, the exact call `tools/fetch_zoom_transcript.py` makes. |
| `CLAUDE_CODE_OAUTH_TOKEN` | On suspected compromise, or when it expires | `roll CLAUDE_CODE_OAUTH_TOKEN`, which runs `claude setup-token`. Note the verification deliberately also runs with a corrupted token: `claude -p` falls back to the logged-in local session when the supplied token is bad, so without that control the check would pass for any string. |
| `PSI_API_KEY` | Low urgency - it is rate-limit-scoped, not privileged | `roll PSI_API_KEY`, fully automatic. Creates a new key restricted to `pagespeedonline.googleapis.com`, confirms it works, confirms it is refused by a second Google API (proving the restriction stuck), writes the secret, deletes the old key. |
| GCP runtime SA roles | On every Terraform apply | The runtime SA's IAM bindings live in [`infra/terraform/gcp/service_accounts.tf`](infra/terraform/gcp/service_accounts.tf) - review on every change |

Rotation ages are not tracked in this file - `updated_at` from the API is the
only honest source, and `rotate_secrets.py` reports it against the cadences
above. The org-level rows are unreadable without `admin:org`, and the script
reports those ages as *unknown* rather than as clean.

---

## DNS & Email Security

The site is static and sends no mail, but the domain still has to be defended:
DNS is the layer every other control ultimately rests on, and an unprotected
domain is worth spoofing even when it has no inbox to compromise. All of the
records below are managed in Terraform under
[`infra/terraform/cloudflare/`](infra/terraform/cloudflare/) - `dns_caa.tf`,
`dns_dnssec.tf`, and `dns_mail.tf` - so they are reviewable and reproducible
rather than dashboard state.

| Control | Value | What it stops |
|---|---|---|
| **CAA** | 5 authorized CAs (Let's Encrypt, DigiCert, Google Trust Services, Sectigo/Comodo, SSL.com), `issue` + `issuewild` each, plus `iodef: mailto:admin@csoh.org` | Any other CA issuing a certificate for `csoh.org`. The `iodef` address gets notified on a rejected issuance attempt. |
| **DNSSEC** | **Signed and delegated** - zone signed at Cloudflare, `DS 2371 13 2` published at `.org`, `whois` reports `signedDelegation`. Verified 2026-08-09. See below. | Forged DNS answers, which is what makes CAA and DMARC mean anything - both are just DNS records, so an attacker who could forge a response would strip either. A validating resolver now rejects the forgery instead of serving it. |
| **SPF** | `v=spf1 include:_spf.google.com ~all` | Unauthorized hosts sending as `@csoh.org`. |
| **DKIM** | **Two** selectors, both RSA: `google._domainkey` (Google Workspace) and `default._domainkey` (a second sender). See below. | Tampering with, or forging, message bodies in transit. |
| **DMARC** | `p=quarantine; sp=quarantine; pct=100`, aggregate reports to Cloudflare | Spoofed mail reaching inboxes. Moved up from `p=none` (monitor-only) - the policy now actually does something. |
| **MTA-STS** | `mode: testing`, `max_age: 604800`, policy at `/.well-known/mta-sts.txt` | Downgrade and MITM attacks on inbound mail delivery. |
| **TLS-RPT** | `v=TLSRPTv1; rua=mailto:admin@csoh.org` | Nothing on its own - it reports TLS delivery failures so an active downgrade attempt is visible. |

Three operational notes that matter more than the table:

**There are two DKIM selectors, and the second one is why `p=quarantine` was
safe.** SPF authorizes Google and nothing else (`v=spf1
include:_spf.google.com ~all`), so read on its own it says any other sender is
unauthorized. But DMARC passes on **either** aligned SPF or aligned DKIM, not
both, so a second sender that signs with a valid DKIM signature for `csoh.org`
survives enforcement even though SPF never lists it. Confirm both selectors
exist before touching SPF or the DMARC policy:

```sh
dig +short TXT google._domainkey.csoh.org     # Google Workspace
dig +short TXT default._domainkey.csoh.org    # the second sender
```

An earlier draft of the runbook claimed `default._domainkey` did not exist, and
that error pointed straight at tightening SPF - which would have broken the
second sender for no gain. The caution and the reasoning are in
[`infra/MANUAL_SECURITY_STEPS.md`](infra/MANUAL_SECURITY_STEPS.md) section 2.
**Do not narrow SPF, and do not move to `p=reject`, on DNS inference alone.**
The DMARC aggregate reports (Cloudflare dashboard → Email Security → DMARC
Management) are the only source that shows what is actually sending as
`csoh.org` and whether it authenticates.

**MTA-STS is a two-part control and both halves must agree.** The `_mta-sts` TXT
record carries an `id` that receivers use to detect policy changes, and the
policy itself is the file at `https://mta-sts.csoh.org/.well-known/mta-sts.txt`.
That hostname is a proxied CNAME to the apex, so the policy is served by the
same three origins as the site - which means it depends on the same
`/.well-known/` carve-out described under File Access Controls, and on
`include-hidden-files: true` in `deploy.yml`. If either regresses, MTA-STS
breaks silently on two origins out of three. **When you change the policy file,
bump the `id` in `dns_mail.tf`** or receivers will keep using the cached one.

It is deliberately at `mode: testing`, which reports failures without bouncing
mail. Moving to `mode: enforce` is a separate decision that should follow a
period of clean TLS-RPT reports, not ride along with an unrelated change.

**DNSSEC is signed and delegated, and there is nothing left to submit.** Signing
the zone was never the same as DNSSEC being live: the parent zone also has to
publish a DS record delegating trust. Both halves are done, verified 2026-08-09:

| Check | Result |
|---|---|
| `dig DNSKEY csoh.org` | 2 keys - KSK (257) + ZSK (256), alg 13 |
| `dig csoh.org A +dnssec` | RRSIG present - the zone is signed |
| `dig +short DS csoh.org` | `2371 13 2 17867E31182375DA5E7C315D67552D70600A7EFB2475404F2B7414B7B097F734` |
| `whois csoh.org` | `DNSSEC: signedDelegation` at the registry |
| Google DoH + Cloudflare DoH | both return `AD=true` - the chain validates |

**Do not submit a DS record.** An earlier version of this section ended with
instructions to do exactly that, and pinned a KSK to submit. It is already
published. Submitting a second one, or submitting a DS for anything other than
the current KSK, is the one DNSSEC mistake that takes a domain offline for every
validating resolver: the name does not degrade, it stops resolving. Key rotation
is Cloudflare's job here and it keeps the registry in step; the only reason to
touch the DS by hand is a registrar transfer, which is covered in the runbook.

Two corrections from getting here are worth keeping, because each cost real
time. First, `cloudflare_zone_dnssec` turns on **signing** only. An earlier draft
reasoned that because Cloudflare is both registrar and DNS provider
(`whois` does confirm `Registrar: Cloudflare, Inc.`) the DS would be published
automatically. It is not: delegation was a separate manual step in the
dashboard, and assuming otherwise left the zone undelegated for two weeks.

Second, and the reason the gap went unnoticed that long: **the obvious `ad`-flag
check is unreliable on some network paths.** This section used to recommend

```sh
dig +dnssec csoh.org A @1.1.1.1 | grep 'flags:'   # expect the "ad" flag
```

On at least one network here that returns `flags: qr rd ra` with no `ad`, and it
does the same for known-good signed domains - `cloudflare.com` and
`internetsociety.org` both fail it identically. The AD bit is being stripped in
transit, so the command measures the path, not the zone. Reading it as a verdict
on `csoh.org` is what produced the wrong "delegation never happened" conclusion.
Ask a resolver that reports its validation result over HTTPS instead:

```sh
dig +short DNSKEY csoh.org      # zone is signed         (expect 2 keys)
dig +short DS     csoh.org      # parent delegates trust (expect 2371 13 2 ...)
whois csoh.org | grep -i dnssec # registry view          (expect signedDelegation)

# The one that counts: did a validating resolver check the signatures?
curl -s "https://dns.google/resolve?name=csoh.org&type=A"
curl -s -H 'accept: application/dns-json' \
     "https://cloudflare-dns.com/dns-query?name=csoh.org&type=A"
# read the "AD" field in each - want true from both
```

Two independent resolvers because one agreeing with you is not corroboration.
And whichever method you use, **run it against a control domain in the same
breath**: a known-good signed zone that fails your check tells you the
measurement is broken, and a broken measurement is indistinguishable from a
broken zone until you have that second data point. **A DS present with no
validation from any resolver means signing and delegation genuinely disagree;
investigate rather than assume propagation lag.**

The full runbook, including what to do before transferring the domain to another
registrar, is
[`infra/MANUAL_SECURITY_STEPS.md`](infra/MANUAL_SECURITY_STEPS.md) section 4.

## Deployment Security

### Multi-cloud deploy

`deploy.yml` builds the site once and publishes it active/active to three cloud origins on every push to `main` that touches site files.

**Authentication - keyless OIDC to every cloud, no stored credential:**
- GitHub Actions mints an OIDC token for the run; each cloud exchanges it for short-lived (~1 hour) access, gated by a policy that requires the token's subject to equal `repo:CloudSecurityOfficeHours/csoh.org:environment:production` - so only a job that declares `environment: production` (and therefore only on `main`, per that environment's branch policy) can trade the token in, on any of the three clouds:
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
- `nginx.conf` carries the same access controls, and `include`s `nginx-security-headers.conf` in every `location` block so no location can silently drop the headers (nginx *replaces* rather than inherits `add_header` when a location sets one of its own)
- `server_tokens off` suppresses nginx version disclosure

---

## Security Remediation - 2026-07-25

A full security review of the repo, the workflows, the Terraform, and the live
site landed ten changes on 2026-07-25. The sections above already describe the
end state; this section is the record of what moved and, more importantly, the
invariants a future change must not quietly undo. Each finding is written up in
detail in a comment at the code it touches, so start there.

### What changed

| # | Area | File(s) | Change |
|---|------|---------|--------|
| 1 | Arbitrary code execution in CI | `.github/workflows/update-resources.yml` | Dropped `Bash(python3:*)` from `--allowedTools`; added `persist-credentials: false` to that job's `actions/checkout` |
| 2 | Cloud trust boundary | `infra/terraform/gcp/wif.tf`, `gcp/variables.tf` | WIF `attribute_condition` and IAM member both pinned to `repo:<owner>/<repo>:environment:production`, matching AWS and Azure |
| 3 | Third-party PII on live pages | `meetings/2024-07-19.html`, `meetings/2024-08-30.html`, both search indexes, `tools/add_meeting.py` | Removed a participant's corporate email address from two recaps; added `scrub_emails()` so it cannot recur |
| 4 | Redirect loop on `www` over HTTP | `infra/terraform/cloudflare/rules.tf` | `target_url` now `concat("https://csoh.org", http.request.uri.path)` instead of a `wildcard_replace` on `full_uri` |
| 5 | Header drift undetectable | new `tools/check_edge_headers.py`, `.github/workflows/deploy.yml`, `cloudflare/rules.tf` | CI now asserts the live **edge** headers against `rules.tf` and fails the deploy on drift. Extended 2026-07-26 to sample 40 cache-busted requests and report origin coverage, after single-request runs were found to pass without ever reaching the one origin that depends on the ruleset |
| 6 | AWS origin had no headers | `infra/terraform/aws/cloudfront.tf` | New `aws_cloudfront_response_headers_policy.security`, wired into `default_cache_behavior` |
| 7 | JSON-LD escaping | `update_news.py` | Escapes `<`, `>`, `&` rather than only `</` |
| 8 | Redirect-header injection | `tools/normalize_urls.py` | Rejects resolved destinations containing markup characters or a non-http(s) scheme |
| 9 | Analytics wider than the policy | `vendor/goatcounter-count.js`, new `vendor/README.md`, `privacy.html`, `llms.txt` | Query string stripped from the beacon; local modifications documented; `llms.txt` no longer claims "no analytics" |
| 10 | Least privilege | `.github/workflows/normalize-urls.yml` | `permissions:` dropped from `contents: write` + `pull-requests: write` to `contents: read` |

`update_sri.py` was re-run as part of #9, which is why that commit re-stamps the
`?v=` key and `integrity` attribute for `vendor/goatcounter-count.js` on every
page: the vendored asset is SRI-hashed, so editing it rewrites the whole site.

### Invariants - do not undo these

1. **No shell entry at all in an allowlist for a job that reads untrusted input.**
   `update-resources.yml` reads the open web with `WebFetch`/`WebSearch` while
   holding the `csoh-ci` token, `CLAUDE_CODE_OAUTH_TOKEN`, and `id-token: write`.
   Its allowlist is `Read,Edit,Glob,Grep,WebSearch,WebFetch` and must stay free
   of `Bash(...)` entries. `Bash(python3:*)` matches `python3 -c '<anything>'`,
   which makes every other entry on the list decorative; the same reasoning
   applies to any future `Bash(sh:*)`, `Bash(node:*)`, `Bash(perl:*)`, or
   similar. The broader form of the rule, learned from `Bash(grep:*)`: **an
   entry naming a command that accepts a path is a filesystem-read capability**,
   however read-only the command looks. If a prompt needs Python, check in a
   script and allowlist that exact path.
2. **`persist-credentials: false` on that checkout stays.** Otherwise the App
   token sits in `.git/config` as an `http.extraheader` for the rest of the job,
   readable by a plain file read from any later step. `csoh-ci` is on the `Main`
   ruleset bypass list, so that token is a direct push to `main`.
3. **The WIF subject pin stays.** GCP must require
   `assertion.sub == 'repo:<owner>/<repo>:environment:production'`, not just
   `assertion.repository`. Repo-only trust lets every workflow in the repo, on
   every branch, mint `csoh-deployer` credentials. If you ever need a second job
   to authenticate to GCP, give it `environment: production` rather than
   loosening the condition.
4. **The three header locations stay in step, and nothing automated checks
   that.** `infra/terraform/cloudflare/rules.tf`,
   `infra/terraform/aws/cloudfront.tf`, and `nginx-security-headers.conf`.
   Change a header in one, change it in all three.
   `tools/check_edge_headers.py` asserts the **edge** against `rules.tf` and
   nothing else: it never compares the three files to each other, and the
   CloudFront policy and the nginx config have no CI gate of their own. Point
   it at an origin hostname by hand (`--url <origin> --samples 1`) after
   editing that origin's headers, because CI will not do it for you.
5. **`tools/add_meeting.py` keeps scrubbing emails.** Zoom AI summaries name
   people by display name, and some display names are work email addresses. The
   scrub lives in `clean_text()`, which is the shared funnel for both the HTML
   and Markdown note parsers, so both paths are covered. It warns rather than
   fails, so a late-Friday publish is never blocked. **Read the warning** and
   give the person a first name if one reads better. `@csoh.org` is exempt.

### The three Terraform applies - done and verified

Three of the changes (#2, #4, #6) were Terraform, and Terraform in a repo is
just a proposal until someone runs `apply`. **All three were applied on
2026-07-25 and re-verified against production on 2026-07-26.** The deployed
state and the repo agree:

| # | Stack | What it changed | Verified by |
|---|---|---|---|
| 2 | `gcp/` | WIF trust pinned to `environment:production` | live `attribute_condition` and the `principal://.../subject/...` IAM member both carry `repo:CloudSecurityOfficeHours/csoh.org:environment:production`; the deploy afterward still authenticated |
| 4 | `cloudflare/` | `www` redirect target no longer derived from the request | `curl -sI http://www.csoh.org/about.html` returns `Location: https://csoh.org/about.html`, not a redirect to itself |
| 6 | `aws/` | CloudFront response-headers policy | `check_edge_headers.py --url https://<dist>.cloudfront.net/ --samples 1` reports all 8 headers matching |

Re-check them at any time with:

```bash
terraform -chdir=infra/terraform/gcp state show \
  google_iam_workload_identity_pool_provider.github | grep attribute_condition
curl -sI http://www.csoh.org/about.html | grep -i -E 'HTTP/|^location'
python3 tools/check_edge_headers.py --samples 1 \
  --url "https://$(terraform -chdir=infra/terraform/aws output -raw cloudfront_domain)/"
```

The AWS stack used to carry a caveat here - it never planned clean, because
`viewer_certificate.minimum_protocol_version` could not converge while the
default `*.cloudfront.net` certificate is in use, and that one inert argument
kept three resources permanently in the diff. Commit `288fcec3` deleted it, so
"clean plan" is now the signal to look for on all four stacks. The reasoning is
preserved in a comment where the argument used to be, in
`infra/terraform/aws/cloudfront.tf`. The per-apply record and the local
toolchain traps that cost hours on the day are in
[`infra/MANUAL_SECURITY_STEPS.md`](infra/MANUAL_SECURITY_STEPS.md) section 1.

The Cloudflare **header** ruleset remains the standing exception, and applying
these three did not change that: `ignore_changes = [rules]` means `apply` will
not push header edits, so any change to those values still has to go in by hand
in the dashboard (or by dropping the `lifecycle` block for one apply).
See [Edge header drift is a CI gate](#edge-header-drift-is-a-ci-gate).

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
| Azure origin sets no security headers | Accepted | Azure Blob static websites cannot emit custom response headers. That origin relies entirely on the Cloudflare edge ruleset; the other two set their own. Revisit if the origin is ever fronted by Azure Front Door or a Function. |
| Cloudflare header ruleset is inert to `terraform apply` | Workaround | `lifecycle { ignore_changes = [rules] }` in `infra/terraform/cloudflare/rules.tf`, for a cloudflare v4 provider ordering bug. `tools/check_edge_headers.py` compensates by failing the deploy on live drift. Remove both on the v5 provider upgrade. |
