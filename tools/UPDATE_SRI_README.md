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

`deploy.yml` then re-runs the same script on the build output before staging, so
the published artifact always names hashes that match the assets shipped with it.

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
  deploy.yml re-stamps the build, then publishes to AWS + GCP + Azure
```

You never have to manually update fingerprints or worry about visitors seeing stale CSS/JS.

---

## The Script: `update_sri.py`

This Python script does all the work. Note that `style.css` includes a large dark mode section (~500 lines of overrides), so any changes to dark mode styling will trigger SRI hash recalculation. When run, the script:

1. Reads each asset in the `ASSETS` list at the top of the script:
   - `style.css`, `main.js`
   - `chat-resources.js`, `breach-timeline.css`, `breach-timeline.js`
   - `meetings.js`, `glossary.js`, `404.js`
   - `search.css`, `search-init.js` (the `/search.html` UI + MiniSearch initializer)
   - `vendor/goatcounter-count.js` (the vendored analytics counter)
2. Calculates a **SHA-384 hash** (the fingerprint) for each file
3. Calculates a **short SHA-256 hash** (the cache-bust `?v=` tag) for each file
4. Scans every `.html` file in the repo
5. Updates the `integrity` attribute with the new fingerprint
6. Updates the `href`/`src` URL with the new `?v=` tag
7. Removes any `crossorigin` attribute (not needed for same-origin files - having it caused mobile browsers to block the CSS)

To add a new tracked asset, append one `(path, tag, attr)` tuple to `ASSETS` -
that is the whole change. There is no per-asset regex to write; the stamping is
generic over the tuple. For example:

```python
ASSETS: List[Tuple[str, str, str]] = [
    ...
    ('my-new-widget.js', 'script', 'src'),
]
```

**Any shared asset a page links to belongs in `ASSETS`.** `nginx.conf` serves
every `*.css` / `*.js` with `expires 1y; Cache-Control: public, immutable`, so an
asset referenced without a `?v=` key is pinned in browser caches for a year and
your edits never reach returning visitors.

### Running manually

```bash
python3 update_sri.py
```

Example output:

```
Calculating SRI hashes...
  style.css: sha384-UmMu+V7pI... (v=892ae8aa)
  main.js: sha384-VaUAqRVQ5... (v=f5430db3)

Updating 233 HTML files...
  - Unchanged: 403.html
  - Unchanged: 404.html
  ...
Done! Modified 0 of 233 files.
```

### Requirements

- Python 3.x (standard library only - no `pip install` needed)

---


## The Workflow: `.github/workflows/site-update-deploy.yml`

SRI and cache-busting are handled as part of the unified workflow, not a separate workflow.

### Triggers

- **On push to main:** Runs automatically when any `*.html` file, `style.css`, `main.js`, `chat-resources.js`, `breach-timeline.css`, `breach-timeline.js`, `update_sri.py`, `img/**`, `vendor/**`, or `chat-screenshots/**` change (the authoritative list is the `paths:` block in the workflow)
- **Also stamped at build time:** `deploy.yml` re-runs `update_sri.py` before staging `dist/`. That is the load-bearing one - housekeeping commits carry a CI-skip marker, so a fix committed there does not itself reach production. Re-stamping in the build makes the published artifact self-consistent by construction.
- **Manual:** Can be triggered from the GitHub Actions tab

### What it does

1. Mints a short-lived `csoh-ci` GitHub App installation token and checks out the repo with it
2. Runs `python3 update_sri.py` to recalculate SRI hashes and `?v=` cache-busting params
3. Commits and pushes updated HTML files if hashes changed
4. Checks URL safety - **blocks the rest of the run** if unsafe URLs are detected (`check_all_site_urls.py`)
5. Normalizes URLs - strips tracking parameters, upgrades HTTP to HTTPS, resolves redirects (`normalize_urls.py`)
6. Refreshes the `VideoObject` JSON-LD on `presentations.html` (`update_presentations_schema.py`)
7. Rebuilds the meetings search index (`build_meetings_search_index.py`)
8. Refreshes `<lastmod>` dates in `sitemap.xml` (`update_sitemap.py`)
9. Verifies every news source has a banner image (`check_news_banners.py`)
10. Generates preview images for any new resource cards, optimizes them, writes WebP siblings, and syncs the mapping

Each step that changes a file commits and pushes it back to `main` on its own,
with a CI-skip marker so the commit doesn't re-trigger the workflow.

**This workflow does not deploy.** Publishing is `deploy.yml`'s job - it builds
once and fans out to AWS, GCP, and Azure. The old FTPS-to-shared-host path
(the "smart passes" this document used to describe) was retired with the move to
multi-cloud; see [SECURITY.md → Architecture](../SECURITY.md#architecture).

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

`PAT_TOKEN` and `APPROVAL_PAT_TOKEN` (the previous two long-lived PATs) have been removed,
as have `FTP_HOST` / `FTP_USER` / `FTP_PASS` - this workflow no longer deploys
anywhere, so it needs no hosting credential at all. Publishing moved to
`deploy.yml`, which authenticates to AWS, GCP, and Azure with keyless OIDC.

### Pinned GitHub Actions

All actions in the workflows are pinned to exact commit SHAs (not mutable
version tags) as a supply-chain measure. Bumps arrive as one grouped weekly
Dependabot PR (`.github/dependabot.yml`).

The canonical, up-to-date list of pinned SHAs lives in
[SECURITY.md → Pinned GitHub Actions](../SECURITY.md#pinned-github-actions).
It is not duplicated here, because a second copy just drifts. To read the live
values straight from the workflows:

```bash
grep -ho 'uses: [^ ]*@[0-9a-f]\{40\}  *# .*' .github/workflows/*.yml | sed 's/uses: //' | sort -u
```
