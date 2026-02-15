# URL Safety Checker for Chat Resources

Before adding URLs to the site, check them for malicious patterns and security issues.

## Quick Start

**Check a single URL:**
```bash
python3 tools/check_url_safety.py "https://example.com/article"
```

**Check all URLs across the entire site:**
```bash
python3 tools/check_all_site_urls.py
```

**Check all URLs in chat-resources.html:**
```bash
python3 tools/check_existing_urls.py
```

**Check multiple URLs from a file:**
```bash
python3 tools/check_url_safety.py --batch urls.txt
```

**Interactive mode:**
```bash
python3 tools/check_url_safety.py --interactive
```

## Site-Wide URL Scanning

The `check_all_site_urls.py` script scans **all HTML files** in your site (not just chat-resources.html) and checks every URL for safety issues.

**What it scans:**
- All `href` attributes in `<a>` tags
- All `src` attributes in `<img>`, `<script>`, `<iframe>`, etc.
- Any standalone URLs in content

**Report includes:**
- Per-file URL counts and status
- Comprehensive summary with percentages
- Detailed suspicious and unsafe URL lists
- File-by-file breakdown of issues

This is automatically run by GitHub Actions on every commit that changes HTML files.

## What It Checks

- ✅ **URL Format** - Valid HTTP/HTTPS URLs only
- ⚠️ **HTTP vs HTTPS** - Warns if not using HTTPS
- 🚫 **IP Addresses** - Flags raw IP addresses (potential malware)
- 🚫 **Suspicious Patterns** - Phishing indicators, URL shorteners, free TLDs
- 🚫 **Blocklist** - Known malicious domains
- ✅ **Whitelist** - Trusted domains (github.com, aws.amazon.com, etc.)
- ⚠️ **Long Domains** - Unusually long domain names
- ⚠️ **Many Subdomains** - Excessive subdomain levels

## Examples

**Safe URL:**
```bash
$ python3 tools/check_url_safety.py "https://github.com/org/repo"
✅ SAFE: https://github.com/org/repo
✅ This URL appears safe to add
```

**Suspicious URL:**
```bash
$ python3 tools/check_url_safety.py "http://192.168.1.1/login"
⚠️  SUSPICIOUS (but not blocked): http://192.168.1.1/login
  WARNINGS:
    • Uses HTTP (not HTTPS) - may be insecure
    • Suspicious pattern detected: IP address
⚠️  Review this URL carefully before adding
```

**Blocked URL:**
```bash
$ python3 tools/check_url_safety.py "https://malicious-example.com/phishing"
❌ UNSAFE: https://malicious-example.com/phishing
  ERRORS:
    • Domain 'malicious-example.com' is on blocklist
⛔ This URL should NOT be added to chat-resources.html
```

## Batch Mode

Create a file with one URL per line:

```text
https://wiz.io/blog/article
https://github.com/project/repo
https://docs.aws.amazon.com/guide
```

Then run:
```bash
python3 tools/check_url_safety.py --batch urls.txt
```

Output:
```
============================================================
Checked 3 URLs
  ✅ Safe: 3
  ⚠️  Suspicious: 0
  ❌ Unsafe: 0
============================================================
```

## Customization

Edit `tools/check_url_safety.py` to:

- **Add to whitelist** - Add trusted domains to `WHITELIST` list
- **Add to blocklist** - Add known bad domains to `BLOCKLIST` list
- **Adjust patterns** - Modify `SUSPICIOUS_PATTERNS` regex list
- **API integration** - Add Google Safe Browsing or VirusTotal API calls

## Workflow

1. **Collect URLs** from Zoom chat sessions
2. **Run safety check** on all URLs
3. **Review warnings** for suspicious URLs
4. **Add safe URLs** to `chat-resources.html`
5. **Document decisions** for future reference

## Exit Codes

- `0` - URL is safe
- `1` - URL is unsafe or has critical errors

This makes it easy to use in scripts:

```bash
if python3 tools/check_url_safety.py "$url"; then
    echo "Safe to add"
else
    echo "Do not add"
fi
```
