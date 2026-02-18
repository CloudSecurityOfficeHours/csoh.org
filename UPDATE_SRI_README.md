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

The workflow uses a **Personal Access Token (PAT)** stored as a GitHub repo secret called `PAT_TOKEN`. This is needed because the GitHub organization restricts what the default `GITHUB_TOKEN` can do.

To set up or rotate the token:

1. Go to [GitHub Token Settings](https://github.com/settings/tokens) and create a **fine-grained token**
2. Grant it access to the `CloudSecurityOfficeHours/csoh.org` repository
3. Give it **Contents** (read/write) and **Pull requests** (read/write) permissions
4. Go to the repo's **Settings > Secrets and variables > Actions** and save it as `PAT_TOKEN`
