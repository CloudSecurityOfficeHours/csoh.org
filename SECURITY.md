# Security Documentation — csoh.org

This document describes the security measures in place for [csoh.org](https://csoh.org), a static website for the Cloud Security Office Hours community.

---

## Architecture

csoh.org is a **pure static site** — no server-side code, no database, no user accounts, no cookies, no sessions. This eliminates entire classes of vulnerabilities (SQL injection, RCE, auth bypass, session hijacking, CSRF). Content is served from shared hosting (LiteSpeed) with FTPS deployment via GitHub Actions.

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
frame-src https://www.youtube.com https://web.archive.org https://www.wired.com;
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

**Exceptions:** `preview-mapping.json` and `resources-data.json` are explicitly allowed because the site's JavaScript needs to fetch them.

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
1. Calculates SHA-384 hashes of `style.css` and `main.js`
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
| `actions/checkout` | `34e114876b0b11c390a56381ad16ebd13914f8d5` | v4.3.1 |
| `actions/setup-python` | `a26af69be951a213d495a4c3e4e4022e16d87065` | v5.6.0 |
| `actions/upload-artifact` | `ea165f8d65b6e75b540449e92b4886f43607fa02` | v4.6.2 |
| `actions/github-script` | `f28e40c7f34bde8b3046d885e986cb6290c5673b` | v7.1.0 |
| `peter-evans/create-pull-request` | `c5a7806660adbe173f04e3e038b0ccdcd758773c` | v6.1.0 |
| `peter-evans/enable-pull-request-automerge` | `a660677d5469627102a1c1e11409dd063606628d` | v3.0.0 |

To update a pinned action, look up the commit SHA for the new tag:
```bash
curl -s "https://api.github.com/repos/actions/checkout/git/ref/tags/v4.3.1" | grep sha
```

### No External Dependencies (Client-Side)

The site loads zero external JavaScript libraries, CSS frameworks, or fonts. Everything is self-hosted. This eliminates CDN compromise as an attack vector.

### Minimal Python Dependencies

The CI tooling uses only:
- Python standard library (`urllib`, `hashlib`, `xml.etree.ElementTree`)
- `Playwright` (for screenshot generation)
- `Pillow` (for image optimization)

---

## Deployment Security

### FTPS Deployment

The site deploys via FTPS (FTP over TLS) using `lftp` from GitHub Actions:
- `ftp:ssl-force true` — enforces TLS encryption on the data channel
- `ftp:ssl-protect-data true` — encrypts file transfers, not just the control channel
- Credentials are stored as GitHub repository secrets (`FTP_HOST`, `FTP_USER`, `FTP_PASS`)

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
| FTP cert verification disabled | Accepted risk | `ssl:verify-certificate no` is set because the server lacks an FQDN-matching certificate. TLS encryption is still enforced. |
| `Server: LiteSpeed` on HTTP redirect | Hosting limitation | The HTTP (port 80) redirect response leaks the server type. The HTTPS response correctly strips it. Requires hosting panel config to suppress. |
| `www.csoh.org` no canonical redirect | Hosting limitation | `www.csoh.org` serves content directly instead of redirecting to `csoh.org`. Requires DNS/hosting config. |
| `http://flaws.cloud` link | Intentional | This AWS security training site only serves over HTTP. The link is intentional. |
