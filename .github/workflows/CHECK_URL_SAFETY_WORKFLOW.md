# URL Safety Check Workflow

This GitHub Actions workflow automatically validates all URLs across **all HTML files** on this site whenever any HTML file is modified.

## When It Runs

The standalone workflow (`.github/workflows/check-url-safety.yml`) triggers on:
- **Pull Requests** that modify any `.html` file
- **Weekly schedule** - every Monday at 06:30 UTC
- **Manual trigger** via workflow_dispatch

URL safety checks also run as a **blocking gate** inside two other workflows:
- **`site-update-deploy.yml`** - runs after SRI hashes, blocks normalization/preview/deploy if unsafe URLs are found
- **`normalize-urls.yml`** - runs before URL normalization, blocks the entire workflow if unsafe URLs are found

## What It Does

1. **Scans every published HTML file** using `tools/check_all_site_urls.py` - the root pages plus the `breaches/`, `meetings/`, `portfolio/`, and `homelab/` subdirectories
2. **Extracts all URLs** from:
   - `<a href="">` links
   - `<img src="">`, `<script src="">`, and other resource URLs
   - Any standalone URLs in content
3. **Generates a comprehensive report** showing:
   - ✅ Safe URLs (per file and total)
   - ⚠️ Suspicious URLs (warnings)
   - ❌ Unsafe URLs (errors)
   - Per-file breakdown of issues
4. **Uploads the report** as a workflow artifact (available for 30 days)
5. **Fails the workflow** if any unsafe URLs are detected
6. **Comments on PRs** with a summary if unsafe URLs are found

## Workflow File

Location: `.github/workflows/check-url-safety.yml`

## How to View Results

### On Pull Requests

If unsafe URLs are detected, the workflow will:
- ❌ Mark the check as failed
- 💬 Post a comment with the summary
- 📎 Attach the full report as an artifact

### On Manual Runs

1. Go to the "Actions" tab
2. Select "Check URL Safety" workflow
3. Click "Run workflow"
4. Click on the workflow run to see results
5. Download the "site-wide-url-safety-report" artifact for full details

## Local Testing

Before pushing changes, you can run the checks locally:

**Full site scan (all HTML files):**
```bash
python3 tools/check_all_site_urls.py
```

**Single URL:**
```bash
python3 tools/check_url_safety.py "https://example.com"
```

**Save report:**
```bash
python3 tools/check_all_site_urls.py > site-wide-url-safety-report.txt 2>&1
```

## What "safe" means here

This is **static analysis, not a threat-intel lookup**. There is no malware
database or reputation API behind it. `tools/check_url_safety.py` flags:

- structural red flags (an `@` in the URL, a raw-IP host, an executable file
  extension, excessive-dash obfuscation)
- throwaway TLDs (`.tk`, `.ml`, `.ga`, `.cf`, `.gq`)
- brand-impersonation and account-panic phrasing in the path
- URL shorteners and redirectors (`bit.ly`, `t.co`, …), which hide the real
  destination from review
- a small hand-maintained `BLOCKLIST` in the same file

It resolves redirects first, so the **final** destination is what gets judged.
It will not catch a freshly-compromised legitimate domain - nothing static
would. It exists to catch the realistic failure mode: a link pasted from Zoom
chat that turns out to be a shortener or a lookalike domain.

## Customizing the Check

To adjust what URLs are flagged, edit:
- `tools/check_url_safety.py` - Modify patterns, whitelist, or blocklist
- `tools/check_all_site_urls.py` - Change which files are scanned or report format

## Exit Codes

- `0` - All URLs are safe (or only have warnings)
- `1` - Unsafe URLs detected (will fail the workflow)

## Continuous Protection

This workflow ensures that:
- No unsafe URLs slip through in PRs for **any page** on your site
- Weekly scans catch URLs that may have gone bad since they were added
- Security issues are caught before deployment - the deploy and normalize workflows both block on unsafe URLs
- URLs are verified safe before any normalization or preview generation occurs
- New pages automatically get URL validation
