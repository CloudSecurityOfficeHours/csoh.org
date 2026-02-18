# SRI Hash & Cache-Busting Automation

## What Is SRI and Why Do We Use It?

**SRI (Subresource Integrity)** is a browser security feature that protects your website's visitors. Here's the idea in plain English:

Every time someone visits csoh.org, their browser downloads files like `style.css` (which controls how the site looks) and `main.js` (which powers search and filtering). SRI adds a **fingerprint** (a cryptographic hash) to each of those files. When the browser downloads the file, it checks: "Does this file's fingerprint match what the HTML page says it should be?" If it doesn't match — maybe the file was tampered with or corrupted — the browser **refuses to use it**. This protects visitors from loading malicious code.

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

**Cache-busting** solves this by adding a version tag to the file URL: `/style.css?v=892ae8aa`. The `?v=` value is based on the file's content — so when the file changes, the version tag changes, and the browser treats it as a brand new file and downloads the fresh version.

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

1. Reads `style.css` and `main.js` from the repo
2. Calculates a **SHA-384 hash** (the fingerprint) for each file
3. Calculates a **short SHA-256 hash** (the cache-bust `?v=` tag) for each file
4. Scans every `.html` file in the repo
5. Updates the `integrity` attribute with the new fingerprint
6. Updates the `href`/`src` URL with the new `?v=` tag
7. Removes any `crossorigin` attribute (not needed for same-origin files — having it caused mobile browsers to block the CSS)

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

- Python 3.x (standard library only — no `pip install` needed)

---


## The Workflow: `.github/workflows/site-update-deploy.yml`

SRI and cache-busting are handled as part of the unified workflow, not a separate workflow.

### Triggers

- **On push to main:** Runs automatically when `style.css`, `main.js`, `chat-resources.js`, `update_sri.py`, `resources.html`, `chat-resources.html`, or `chat-screenshots/**` change
- **Manual:** Can be triggered from the GitHub Actions tab

### What it does

1. Checks out the latest code
2. Runs `python3 update_sri.py` to recalculate SRI hashes and `?v=` cache-busting params
3. Commits and pushes updated HTML files if hashes changed
4. Generates preview images for any new resources in `resources.html`
5. Deploys the site via rsync over SSH in smart passes:
   - **Pass 1:** Always — all HTML/CSS/JS and site files (skips image directories)
   - **Pass 2:** Only when new previews were generated — uploads `img/previews/`
   - **Pass 3:** Only when new files exist in `chat-screenshots/` — uploads `chat-screenshots/`

---

## Manual Hash Calculation

If you just want to check a file's hash without running the full script, there's also a shell script:

```bash
./calculate-sri.sh main.js style.css
```

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| CSS not loading on mobile | SRI fingerprint doesn't match the file content | Run `python3 update_sri.py` and deploy |
| CSS not loading despite correct hash | `crossorigin="anonymous"` attribute present | Remove `crossorigin` from the HTML tags — the script does this automatically |
| Visitors seeing old styles after a CSS update | Browser cache serving the old file | The `?v=` cache-busting parameter should prevent this — run `update_sri.py` to regenerate |
| Workflow can't push commits | Missing or expired PAT | Create a new fine-grained PAT with Contents permissions and save it as the `PAT_TOKEN` repo secret |

---

## Setup Requirements

### GitHub Secrets

The workflow requires the following secrets under **Settings > Secrets and variables > Actions**:

| Secret | Purpose |
|--------|---------|
| `PAT_TOKEN` | Fine-grained PAT for committing SRI/preview changes and managing PRs |
| `APPROVAL_PAT_TOKEN` | Separate PAT used to auto-approve news PRs (must be a different user) |
| `FTP_HOST` | SSH/SFTP hostname of the web server |
| `FTP_USER` | SSH username on the web server |
| `SSH_PRIVATE_KEY` | Ed25519 private key used for passwordless SSH deployment |

### Setting up `PAT_TOKEN`

1. Go to [GitHub Token Settings](https://github.com/settings/tokens) and create a **fine-grained token**
2. Grant it access to the `CloudSecurityOfficeHours/csoh.org` repository
3. Give it **Contents** (read/write) and **Pull requests** (read/write) permissions
4. Save it as `PAT_TOKEN` in repo secrets

### Setting up the SSH deploy key (`SSH_PRIVATE_KEY`)

The workflow deploys via rsync over SSH using a dedicated ed25519 key pair — no FTP password involved.

To rotate or set up from scratch:

1. Generate a new key pair locally:
   ```bash
   ssh-keygen -t ed25519 -C "github-actions@csoh.org" -f ./deploy_key -N ""
   ```
2. Add the **public key** (`deploy_key.pub`) to `~/.ssh/authorized_keys` on the web server (via hosting control panel → SSH Keys)
3. Add the **private key** (`deploy_key` contents) as the `SSH_PRIVATE_KEY` repo secret
4. Delete both key files from your local machine

### Pinned GitHub Actions

All actions in the workflows are pinned to exact commit SHAs (not mutable version tags) as a supply chain security measure. When updating an action to a newer version, look up the commit SHA for the new tag and update it manually:

```bash
# Example: find the SHA for a specific tag
curl -s "https://api.github.com/repos/actions/checkout/git/ref/tags/v4.3.1" | grep sha
```

Current pinned versions:

| Action | SHA | Version |
|--------|-----|---------|
| `actions/checkout` | `34e11487...` | v4.3.1 |
| `actions/setup-python` | `a26af69b...` | v5.6.0 |
| `actions/upload-artifact` | `ea165f8d...` | v4.6.2 |
| `actions/github-script` | `f28e40c7...` | v7.1.0 |
| `peter-evans/create-pull-request` | `c5a78066...` | v6.1.0 |
| `peter-evans/enable-pull-request-automerge` | `a660677d...` | v3.0.0 |
