# URL Safety Check Workflow

This GitHub Actions workflow automatically validates all URLs across **all HTML files** on your site whenever any HTML file is modified.

## When It Runs

The workflow triggers on:
- **Pull Requests** that modify any `.html` file
- **Pushes to main** that modify any `.html` file
- **Manual trigger** via workflow_dispatch

## What It Does

1. **Scans all HTML files** in the site (*.html) using `tools/check_all_site_urls.py`
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

**Just chat-resources.html:**
```bash
python3 tools/check_existing_urls.py
```

**Single URL:**
```bash
python3 tools/check_url_safety.py "https://example.com"
```

**Save report:**
```bash
python3 tools/check_all_site_urls.py > site-wide-url-safety-report.txt 2>&1
```

## Customizing the Check

To adjust what URLs are flagged, edit:
- `tools/check_url_safety.py` - Modify patterns, whitelist, or blocklist
- `tools/check_all_site_urls.py` - Change which files are scanned or report format
- `tools/check_existing_urls.py` - Customize chat-resources.html scanning

## Exit Codes

- `0` - All URLs are safe (or only have warnings)
- `1` - Unsafe URLs detected (will fail the workflow)

## Continuous Protection

This workflow ensures that:
- No unsafe URLs slip through in PRs for **any page** on your site
- The main branch always has validated URLs across all HTML files
- Security issues are caught before deployment
- New pages automatically get URL validation
