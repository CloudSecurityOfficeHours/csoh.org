# SRI Hash & Cache-Busting Automation

## What Is SRI and Why Do We Use It?

**SRI (Subresource Integrity)** is a browser security feature that protects your website's visitors. Here's the idea in plain English:

Every time someone visits csoh.org, their browser downloads files like `style.css` (which controls how the site looks) and `main.js` (which powers search and filtering). SRI adds a **fingerprint** (a cryptographic hash) to each of those files. When the browser downloads the file, it checks: "Does this file's fingerprint match what the HTML page says it should be?" If it doesn't match - maybe the file was tampered with or corrupted - the browser **refuses to use it**. This protects visitors from loading malicious code.

In our HTML, it looks like this:

```html
<link rel="stylesheet" href="/style.css?v=892ae8aa"
  integrity="sha384-UmMu+V7pIRzpjQe5g9nD/fa/7i08YXu8TIfTeY4HaXp3ZnbIZHlsFmMRkblktE/G">
```

- `integrity="sha384-..."` is the fingerprint
- `?v=892ae8aa` is a **cache-busting** parameter (explained below)

---

## What Is Cache-Busting?

Browsers **cache** (save a local copy of) CSS and JS files to make pages load faster on repeat visits. The problem: if we update `style.css`, returning visitors might still see the old cached version for days or even months.

**Cache-busting** solves this by adding a version tag to the file URL: `/style.css?v=892ae8aa`. The `?v=` value is based on the file's content - so when the file changes, the version tag changes, and the browser treats it as a brand new file and downloads the fresh version.

---


## How It Works Automatically

Whenever someone changes `style.css` or `main.js` and pushes to the `main` branch (or opens a pull request), the **unified site-update-deploy.yml workflow** automatically:

1. Calculates a new SHA-384 fingerprint for each file
2. Generates a new cache-busting version tag from the file content
3. Updates every HTML file with the new fingerprint and version tag
4. Commits and pushes the updated HTML files (if needed)
5. Deploys the site to the web server (after merge to main)

```
You push a change to style.css or main.js
        |
        v
  Unified workflow runs update_sri.py
        |
        v
  Script calculates new fingerprint + version tag
        |
        v
  All HTML files are updated automatically
        |
        v
  Changes committed and pushed to main (if needed)
        |
        v
  Site is deployed after merge
```

You never have to manually update fingerprints or worry about visitors seeing stale CSS/JS.

---

## The Script: `update_sri.py`

This Python script does all the work. Note that `style.css` includes a large dark mode section (~500 lines of overrides), so any changes to dark mode styling will trigger SRI hash recalculation. When run, the script:

1. Reads each tracked asset from the repo:
   - `style.css`, `main.js`
   - `chat-resources.js`, `breach-timeline.css`, `breach-timeline.js`
   - `meetings.js`, `glossary.js`, `404.js`
   - `vendor/goatcounter-count.js` (the vendored analytics counter)
2. Calculates a **SHA-384 hash** (the fingerprint) for each file
3. Calculates a **short SHA-256 hash** (the cache-bust `?v=` tag) for each file
4. Scans every `.html` file in the repo
5. Updates the `integrity` attribute with the new fingerprint
6. Updates the `href`/`src` URL with the new `?v=` tag
7. Removes any `crossorigin` attribute (not needed for same-origin files - having it caused mobile browsers to block the CSS)

To add a new tracked asset, append a line to the `files_to_hash` map and a corresponding regex block in `update_html_file` - see how `meetings.js` and `glossary.js` are wired up.

### Running manually

```bash
python3 update_sri.py
```

Example output:

```
Calculating SRI hashes...
  style.css: sha384-UmMu+V7pI... (v=892ae8aa)
  main.js: sha384-VaUAqRVQ5... (v=f5430db3)

Updating 12 HTML files...
  - Unchanged: 403.html
  - Unchanged: 404.html
  ...
Done! Modified 0 of 12 files.
```

### Requirements

- Python 3.x (standard library only - no `pip install` needed)

---


## The Workflow: `.github/workflows/site-update-deploy.yml`

SRI and cache-busting are handled as part of the unified workflow, not a separate workflow.

### Triggers

- **On push to main:** Runs automatically when any `*.html` file, `style.css`, `main.js`, `chat-resources.js`, `breach-timeline.css`, `breach-timeline.js`, `update_sri.py`, `.htaccess`, or `chat-screenshots/**` change
- **Manual:** Can be triggered from the GitHub Actions tab

### What it does

1. Checks out the latest code
2. Runs `python3 update_sri.py` to recalculate SRI hashes and `?v=` cache-busting params
3. Commits and pushes updated HTML files if hashes changed
4. Checks URL safety - blocks deploy if unsafe URLs are detected (using `check_all_site_urls.py`)
5. Normalizes URLs - strips tracking parameters, upgrades HTTP to HTTPS, resolves redirects (using `normalize_urls.py`)
6. Generates preview images for any new resources in `resources.html`
7. Checks for broken links (non-blocking warning)
8. Deploys the site via FTP in smart passes:
   - **Pass 1:** When deploy is triggered - all HTML/CSS/JS and site files (skips image directories)
   - **Pass 2:** Only when new previews were generated - uploads `img/previews/`
   - **Pass 3:** Always syncs news source banner images (`img/news-banners/`)
   - **Pass 4:** Only when new files exist in `chat-screenshots/` - uploads `chat-screenshots/`

---

## Manual Hash Calculation

If you just want to check a file's hash without running the full script:

```bash
openssl dgst -sha384 -binary style.css | openssl base64 -A
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| CSS not loading on mobile | SRI fingerprint doesn't match the file content | Run `python3 update_sri.py` and deploy |
| CSS not loading despite correct hash | `crossorigin="anonymous"` attribute present | Remove `crossorigin` from the HTML tags - the script does this automatically |
| Visitors seeing old styles after a CSS update | Browser cache serving the old file | The `?v=` cache-busting parameter should prevent this - run `update_sri.py` to regenerate |
| Workflow fails at "Mint installation token" | App private key missing/expired/revoked | Generate a new key in the `csoh-ci` GitHub App settings and update the `CSOH_CI_PRIVATE_KEY` org-level secret |
| Workflow fails at "Auto approve" with HTTP 401 | `CSOH_PAT` expired or revoked | Regenerate the fine-grained PAT (see `UPDATE_NEWS_README.md` → Setup Requirements) and replace the `CSOH_PAT` org secret |

---

## Setup Requirements

### Authentication and secrets

The workflow now uses a **GitHub App** (`csoh-ci`) rather than a long-lived PAT for committing back to `main` and managing PRs. The full model is documented in [SECURITY.md → CI/CD Authentication](../SECURITY.md#cicd-authentication). What matters here:

| Secret | Where it lives | Purpose |
|--------|---------------|---------|
| `CSOH_CI_CLIENT_ID` | Org-level | GitHub App's Client ID (`Iv23.*`); used to mint short-lived installation tokens |
| `CSOH_CI_PRIVATE_KEY` | Org-level | GitHub App's RSA private key (PEM); used to sign the JWT for token minting |
| `CSOH_PAT` | Org-level | Fine-grained PAT scoped to `csoh.org` with `Pull requests: Read & Write` only - used solely to auto-approve App-opened PRs (GitHub blocks self-approval) |
| `FTP_HOST` | Repo-level | FTP hostname of the web server (must match the host's TLS cert subject) |
| `FTP_USER` | Repo-level | FTP username |
| `FTP_PASS` | Repo-level | FTP password |

`PAT_TOKEN` and `APPROVAL_PAT_TOKEN` (the previous two long-lived PATs) have been removed.

### Setting up the FTP credentials

The workflow deploys via FTPS (FTP over TLS) using lftp.

1. Set `FTP_HOST` to your web server's FTP hostname
2. Set `FTP_USER` to the FTP username
3. Set `FTP_PASS` to the FTP password
4. All three should be saved as repository secrets under **Settings > Secrets and variables > Actions**

### Pinned GitHub Actions

All actions in the workflows are pinned to exact commit SHAs (not mutable version tags) as a supply chain security measure. When updating an action to a newer version, look up the commit SHA for the new tag and update it manually:

```bash
# Example: find the SHA for a specific tag
curl -s "https://api.github.com/repos/actions/checkout/git/ref/tags/v4.3.1" | grep sha
```

Current pinned versions:

| Action | SHA | Version |
|--------|-----|---------|
| `actions/checkout` | `de0fac2e...` | v6.0.2 |
| `actions/setup-python` | `a309ff8b...` | v6.2.0 |
| `actions/upload-artifact` | `bbbca2dd...` | v7.0.0 |
| `actions/github-script` | `ed597411...` | v8.0.0 |
| `peter-evans/create-pull-request` | `c0f553fe...` | v8.1.0 |
| `peter-evans/enable-pull-request-automerge` | `a660677d...` | v3.0.0 |
| `lycheeverse/lychee-action` | `8646ba30...` | v2.8.0 |
| `Cyb3r-Jak3/html5validator-action` | `443b108e...` | master (2025-09-19) |
