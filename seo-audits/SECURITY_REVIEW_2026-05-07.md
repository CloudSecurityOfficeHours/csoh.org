# csoh.org — Security Review

**Date:** 2026-05-07
**Reviewer:** Claude (Opus 4.7)
**Scope:** Static site, GitHub Actions workflows, secrets handling, server config, client-side JS, Python tooling, Docker, documented policy.
**Reference baseline:** `SECURITY.md` in the repo root.

---

## TL;DR

The site is in unusually good shape for a static project: pure static HTML (no auth, no DB), strong CSP without `unsafe-inline`, SRI on all first-party JS/CSS, third-party Actions pinned to commit SHAs, no external client-side dependencies, and a coherent set of file-access blocks in both `.htaccess` and `nginx.conf`.

The real risk is concentrated in three places:

1. **Local secrets hygiene** — `.env` contains live Zoom Server-to-Server OAuth credentials in cleartext, world-readable (`-rw-r--r--`), and shared with this assistant during the review.
2. **The deploy pipeline** — FTP cert verification is disabled (a documented accepted risk), credentials are passed on the lftp command line, multiple workflows lack an explicit top-level `permissions:` block, and a two-PAT auto-approve + auto-merge loop exists for the news refresher.
3. **A few small CSP / hardening gaps** — no `report-uri`, no COOP/CORP, `frame-src` includes domains that probably no longer need to be allowed, and the Dockerfile / `actions/cache` step are not pinned.

Findings below are tagged **CRITICAL / HIGH / MEDIUM / LOW / INFO** and grouped by area.

---

## 1. Secrets & credentials

### 1.1 [CRITICAL] Live Zoom credentials in cleartext on disk
- **File:** `.env` (path: `/Users/shawn/csoh.org/.env`)
- **Contents:** `ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` for a Server-to-Server OAuth app with `recording:read`, `user:read`, `meeting:read` scopes.
- **State:** Gitignored (`.gitignore` excludes `.env` and `.env.*`); never committed (verified with `git log --all -p -S "<secret>"` — no hits in history).
- **Issues:**
  - File mode is `-rw-r--r--` (644) → readable by any local user / process running as anyone on the machine.
  - Plaintext at rest. Any malware/process leaking your home directory exfiltrates these.
  - Credentials were exposed to me via tool output during this review — they are now in this conversation's transcript and any downstream caching.
- **Recommendation (do this first):**
  1. **Rotate `ZOOM_CLIENT_SECRET` now** in the Zoom Marketplace S2S app (regenerate). The Account ID and Client ID are not secret on their own; the Secret is.
  2. `chmod 600 .env` so only your user can read it.
  3. Move the secret out of `.env` into macOS Keychain or 1Password CLI; have `fetch_zoom_transcript.py` read from there instead. As a lighter alternative, keep `.env` but mode 600.
  4. If the account is shared / has any non-Shawn admins, consider rotating Client ID too (regenerate → effectively a new app).

### 1.2 [HIGH] FTPS deploy with TLS verification disabled
- **Where:** `.github/workflows/site-update-deploy.yml:418`, `.github/workflows/manual-deploy.yml:72`
- **Setting:** `set ssl:verify-certificate no`
- **Documented as:** "Accepted risk — server lacks an FQDN-matching certificate" in `SECURITY.md` § Known Limitations.
- **Why it still matters:** With certificate validation off, an on-path attacker between the GitHub runner and the FTP host can present any cert, capture `FTP_USER` / `FTP_PASS`, and gain write access to your site root. `ftp:ssl-force true` only ensures TLS is *negotiated*, not that the server is who it claims to be.
- **Recommendations (pick one, in order of preference):**
  1. **Best:** put a Let's Encrypt cert on the FTP hostname (your hosting panel almost certainly supports this) and flip `ssl:verify-certificate yes`. This is the only way to actually defeat MITM.
  2. **Pin a specific cert fingerprint** with `set ssl:ca-file /tmp/host.pem` so even if you don't validate hostnames, only one specific cert is accepted.
  3. **Switch transport to SFTP** (port 22) — most shared hosts support it. lftp speaks `sftp://` natively and you avoid the TLS-on-FTP class of issues entirely.
  4. **Move `FTP_PASS` behind a GitHub Deployment Environment** with required approval; that way an unintended push to `main` cannot trigger a deploy that exposes the password to a MITM.

### 1.3 [MEDIUM] FTP credentials on the lftp command line
- **Where:** both deploy workflows construct `LFTP_CONN="...; open -u ${FTP_USER},${FTP_PASS} ${FTP_HOST}"` and pass it via `lftp -e "${LFTP_CONN}; ..."`.
- **Risk:** On a multi-tenant runner (you're on `ubuntu-latest`, single-tenant in practice), credentials in `argv` are visible via `/proc/<pid>/cmdline` to anything else running as the same user. On GitHub-hosted runners the blast radius is small; on a self-hosted runner it would be a hard fail.
- **Recommendation:** use lftp's password-via-stdin or env var pattern. Example:
  ```bash
  LFTP_PASSWORD="$FTP_PASS" lftp --env-password -e "set ...; \
    open -u $FTP_USER ftps://$FTP_HOST; mirror -R ..."
  ```
  This keeps `FTP_PASS` out of `argv`.

### 1.4 [LOW] PAT injected into the git remote URL
- **Where:** `site-update-deploy.yml:321`
  ```
  git remote set-url origin "https://x-access-token:${PAT_TOKEN}@github.com/${{ github.repository }}.git"
  ```
- **Risk:** Any later step that runs `git remote -v`, `git fetch --verbose`, or any command that echoes git's stderr will print the URL — and therefore the token — into the workflow log. GitHub auto-redacts known secrets, but only the *exact* registered values; URL-encoded forms or partial echoes can slip through.
- **Recommendation:** use the `extraheader` pattern instead, which keeps the token out of the URL:
  ```bash
  git -c "http.https://github.com/.extraheader=Authorization: Bearer $PAT_TOKEN" push
  ```
  Or rely on `actions/checkout`'s `persist-credentials: true` (the default) plus `token: ${{ secrets.PAT_TOKEN }}` and skip `git remote set-url` entirely.

### 1.5 [MEDIUM] PAT scope is opaque + auto-approve loop
- **Tokens used:** `PAT_TOKEN` (used to checkout, push, open PRs), `APPROVAL_PAT_TOKEN` (used to approve the bot's own PRs in `update-news.yml:131` and `normalize-urls.yml:115`).
- **Risk model:** Two tokens with write access to the repo, one of which automatically approves whatever the other one opens. If `PAT_TOKEN` leaks (log, stale dotenv, malicious PR injecting into a workflow), an attacker has a one-token path to "open + auto-approve + auto-merge to main" → triggers `site-update-deploy` → ships their files to the live FTP host. The auto-merge gate in `update-news.yml` only fires when the diff is `news.html|feed.xml|sitemap.xml`, which is decent — but `normalize-urls.yml` has no such allowlist (it relies on human review).
- **Recommendations:**
  1. **Migrate to a GitHub App** with installation tokens scoped per-workflow. Apps avoid PATs entirely, get short-lived tokens, and let you constrain permissions to "contents: write, pull-requests: write" only.
  2. If you keep PATs, switch to **fine-grained PATs** scoped to *only* `CloudSecurityOfficeHours/csoh.org` with the smallest set of permissions that work.
  3. Add **branch protection on `main`** that requires status checks (lint, validate-html, check-url-safety) and a non-bot review. Today, a bot pair can theoretically merge without a human in the loop.
  4. Tighten `normalize-urls.yml` so auto-approve fires only when the diff is contained to `*.html` URL changes — same shape as `update-news.yml`.

### 1.6 [INFO] No secret scanning enabled
- **Recommendation:** turn on GitHub Secret Scanning + Push Protection at the org level (`CloudSecurityOfficeHours`). It's free for public repos and would have caught a `.env` if it had ever been committed.

---

## 2. GitHub Actions workflows

### 2.1 [MEDIUM] Missing top-level `permissions:` blocks
Workflows without `permissions:` get the org/repo default `GITHUB_TOKEN` permissions (typically `contents: write` everywhere). Principle of least privilege:

| Workflow | Has `permissions:`? | Notes |
|---|---|---|
| `lint.yml` | ✅ `contents: read` | Good |
| `validate-html.yml` | ✅ `contents: read, pull-requests: write` | Good |
| `check-broken-links.yml` | ✅ same | Good |
| `check-url-safety.yml` | ✅ same | Good |
| `normalize-urls.yml` | ✅ `contents: write, pull-requests: write` | Could be tighter on the lint step |
| `update-news.yml` | ❌ **missing** | Add explicit block |
| `site-update-deploy.yml` | ❌ **missing** | Add explicit block |
| `manual-deploy.yml` | ❌ **missing** | Add explicit block |

For the missing ones, declare:
```yaml
permissions:
  contents: write       # site-update-deploy / update-news need it for [skip ci] commits
  pull-requests: write  # update-news / normalize-urls open PRs
```
(`manual-deploy.yml` should be `contents: read` only — it does no commits.)

### 2.2 [LOW] `actions/cache@v4` not pinned by SHA
- **Where:** `check-broken-links.yml:49` — the only third-party action not pinned.
- **Recommendation:** pin it to a specific commit SHA, matching the pattern used elsewhere in the repo.

### 2.3 [LOW] `cancel-in-progress: true` on the deploy pipeline can leave the server half-mirrored
- **Where:** `site-update-deploy.yml:55`
- **Why it exists:** documented in the file header — prevents stale-content races when a newer deploy supersedes an in-flight one.
- **Trade-off:** lftp `mirror` is not transactional; cancelling mid-mirror can leave a few files at the new state and others at the old. For a static content site this is usually fine, but consider:
  - moving the deploy to a "blue-green" pattern (rsync to a sibling directory, then atomic symlink swap), or
  - using lftp's `--no-empty-dirs` plus a final pass that re-runs after the cancel-survivor lands.

### 2.4 [INFO] No `pull_request_target` usage — good
None of the workflows use `pull_request_target`, which is the highest-blast-radius CI mistake. Keep it that way.

### 2.5 [INFO] No script-injection sinks via untrusted GitHub context
I scanned every `run:` block for `${{ github.event.* }}` interpolation that originates from PR titles, commit messages, or branch names — none found. All `${{ … }}` references in shell scripts are to internal step outputs (`steps.x.outputs.y`), `github.repository`, or `github.ref`, all of which are either constant or already-sanitised. Solid.

### 2.6 [LOW] `tools/check_url_safety.py` `resolve_url` accepts any scheme
- **Where:** `tools/check_url_safety.py:79`
- **Risk:** `urllib.request.urlopen` happily handles `file://`, `ftp://`, etc. A PR that adds `<a href="file:///etc/passwd">` would cause the safety-check workflow to read runner-local files and (depending on redirect handling) leak content into a PR comment. Risk is low (PR diffs make this loud, and the comment template only includes a regex-bounded "SUMMARY" block), but it's worth tightening:
  ```python
  parsed = urlparse(url)
  if parsed.scheme not in {"http", "https"}:
      return url, "unsupported scheme"
  ```
  Add this before any `urlopen` call.

### 2.7 [INFO] Lychee, Playwright, jpegoptim install steps run as the workflow user — fine.
No `sudo` mishaps, no `curl | sh` anywhere. Supply-chain surface is small.

---

## 3. HTTP security headers & server config

### 3.1 [LOW] CSP has no reporting endpoint
- **Where:** `.htaccess:27`, `nginx.conf:15`
- **Today's CSP:** strict, no `unsafe-inline`, all sources explicit. Good baseline.
- **Gap:** No `report-uri` / `report-to` directive. You have no visibility when a CSP rule fires in the wild — you'd only learn about a broken page from a user.
- **Recommendation:** add a free reporting endpoint (e.g., report-uri.com) and append `; report-uri https://your-endpoint.report-uri.com/r/d/csp/enforce` to the CSP string. Costs nothing, gives you a feedback loop.

### 3.2 [LOW] Drift between `.htaccess` and `nginx.conf` CSP
- `.htaccess` CSP: `script-src 'self'`, `connect-src 'self'`
- `nginx.conf` CSP: `script-src 'self' https://static.cloudflareinsights.com`, `connect-src 'self' https://cloudflareinsights.com`
- **Why it matters:** if you ever switch from LiteSpeed (.htaccess) to the Docker/nginx path, your CSP suddenly becomes laxer than today's production. Pick one canonical CSP and keep them identical, or document the drift explicitly.

### 3.3 [LOW] `frame-src` allows `web.archive.org` and `www.wired.com`
- **Where:** both CSP strings.
- **Why this exists:** presumably one or two pages embed these as iframes.
- **Risk:** any XSS *inside* those framed pages could read/manipulate the iframe contents (it can't touch your origin), but they can also navigate the *top* window via `top.location =` if you don't sandbox the iframe. This isn't an XSS in your origin — it's a UX hijack: a Wired iframe could redirect a CSOH visitor away.
- **Recommendation:**
  1. Search HTML for actual `<iframe src="...wired.com">` and `...web.archive.org">` usage; if any are stale, drop them from CSP.
  2. For ones that remain, add `sandbox="allow-same-origin allow-scripts"` (or stricter) to the iframe — this prevents `top.location` navigation.

### 3.4 [LOW] Missing modern hardening headers
Add to both `.htaccess` and `nginx.conf`:
```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp   # only if no third-party iframes break
```
COOP/CORP defend against cross-origin Spectre-class leaks and the "tab steals window.opener" pattern your `rel="noopener"` already guards against in JS — belt-and-braces.

### 3.5 [LOW] HSTS preload status not verified
- Header is correct: `max-age=31536000; includeSubDomains; preload`. Good.
- **Action:** check status at https://hstspreload.org/?domain=csoh.org and submit if not already preloaded. Once preloaded, you must keep the header — removal requires a request to be unlisted.

### 3.6 [INFO] No `X-XSS-Protection` header
Correct — that header is deprecated and Chrome ignores it. No action needed.

### 3.7 [LOW] `.htaccess` blocks `*.json` but explicit allowlist may grow stale
- **Where:** `.htaccess:67-92` blocks `\.json$` and adds exceptions for `preview-mapping.json` and `manifest.json`.
- **Risk:** `meetings-search-index.json` (487 KB) is fetched by `meetings.js` — if it's not in the allowlist, search breaks; if it is, it should be added explicitly. Quick check: site appears to load it via fetch from `meetings.html`. Verify with an HTTP request to `https://csoh.org/meetings-search-index.json`. If it 403s, add an explicit `<Files>` exception.
- **Recommendation:** also keep the nginx.conf allowlist in sync. Today nginx blocks all JSON except `preview-mapping.json`.

### 3.8 [INFO] `Permissions-Policy` covers the right surfaces
You explicitly disable camera, mic, geolocation, payment, USB, magnetometer, gyroscope, accelerometer. Could optionally add `interest-cohort=(), browsing-topics=()` for FLoC/Topics opt-out. Cosmetic.

---

## 4. Client-side JavaScript

### 4.1 [INFO] DOM XSS surface is small and well-handled
I scanned `main.js`, `chat-resources.js`, `breach-timeline.js`, `meetings.js`, `glossary.js`, `404.js` for the usual sinks (`innerHTML`, `outerHTML`, `document.write`, `eval`, `new Function`, `setTimeout` with strings, `insertAdjacentHTML`).

- `innerHTML` is used in ~8 places. Every instance is one of:
  - `= ''` (clearing a container — safe)
  - templated strings where the inserted values pass through `sanitize()` (which does `textContent` → `innerHTML` round-trip, the canonical safe escape)
  - templated strings using `encodeURIComponent()` of card link hrefs and `<h3>` text — encodeURIComponent escapes `<`, `>`, `"`, `'`, `&` so URL-attribute insertion is safe.
- `?q=` from the URL (`main.js:99`) flows through `sanitize()` before reaching the DOM.
- `404.js` builds redirect targets from `?from=` and `location.hash`, but only against a hard-coded slug allowlist (`knownBreaches`) or a strict `\d{4}-\d{2}-\d{2}` regex. No template-string concat with user input.
- No `eval`, no `Function()`, no `document.write`, no string-form `setTimeout`/`setInterval`.
- `target="_blank"` enforcement adds `rel="noopener noreferrer"` on every page load.

I did not find a usable XSS path.

### 4.2 [LOW] `sanitize()` is fine but worth a comment
The function (`main.js:19`) uses the textContent → innerHTML round-trip, which is the right pattern. Add a one-line comment naming it as such so a future contributor doesn't "improve" it into a regex-replace.

### 4.3 [INFO] No third-party JS, no cookies, no localStorage beyond `theme`
Confirmed by grep. Privacy posture is excellent.

---

## 5. Python tooling

### 5.1 [INFO] No shell injection
Every `subprocess.run` / `subprocess.call` in `tools/` and root scripts uses an arg-list, never `shell=True`. Verified across `submit_ctf.py`, `submit_news_source.py`, `submit_resource.py`, `update_news.py`, `update_sitemap.py`, `check_lighthouse.py`, `backfill_zoom_summaries.py`. Good.

### 5.2 [LOW] `fetch_zoom_transcript.py` follows Zoom's `download_url` blindly
- **Where:** `tools/fetch_zoom_transcript.py:317-323` — the script takes whatever URL Zoom returns in the `download_url` field and `urlopen`s it with the bearer token attached.
- **Risk:** Low (you trust the Zoom API), but if the response were ever spoofed/MITMed and the URL pointed somewhere else, the bearer token would leak. Default urllib trusts CA bundle so MITM is hard, but worth defending in depth:
  - Validate the host of `download_url` is `*.zoom.us` before sending the bearer.

### 5.3 [LOW] `.env` loader doesn't validate keys
`tools/fetch_zoom_transcript.py:59-71` (`load_dotenv`) doesn't reject keys that start with `LD_PRELOAD`, `PYTHON*`, `PATH`, etc. If `.env` is ever generated/edited by an untrusted process, an attacker could set malicious env vars. Practical risk near zero (you author `.env` yourself), but cheap to fix:
```python
ALLOWED = {"ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"}
if k not in ALLOWED:
    continue
```

---

## 6. Docker / supply chain

### 6.1 [MEDIUM] `Dockerfile` uses an unpinned base
- **Where:** `Dockerfile:1` — `FROM nginx:alpine`
- **Risk:** Each `docker build` resolves to whatever `nginx:alpine` points to today. A compromised tag = compromised image.
- **Recommendation:** pin to a digest:
  ```Dockerfile
  FROM nginx:1.27-alpine@sha256:<digest>
  ```
  Update via Dependabot if you want it automatic.

### 6.2 [LOW] Dockerfile `RUN find ... -delete` is correct but fragile
- The dual `RUN rm -rf` + `find -delete` blocks remove sensitive files post-COPY. They work, but if anyone adds a new sensitive extension (`.env.local`, `.pem`, `.key`) the find pattern won't catch it.
- **Recommendation:** add `*.pem`, `*.key`, `.env*` to the `find` patterns and the `.dockerignore` file (better — exclude before COPY rather than delete after).

### 6.3 [INFO] `.dockerignore`
93-byte file, did not read in detail — recommend it explicitly excludes `.env`, `.env.*`, `*.pem`, `*.key`, `.git/`, `.github/`, `tools/`, `__pycache__/`, `.venv/`, `seo-audits/`. If any of those make it into the image you've leaked secrets or expanded attack surface for nothing.

---

## 7. Documentation & disclosure

### 7.1 [INFO] `security.txt` and `SECURITY.md` are well-formed
- `.well-known/security.txt` is RFC 9116-compliant. Contact + Expires + Canonical + Policy all present. Expiry 2027-02-11 — set a calendar reminder for 2027-01.
- `SECURITY.md` is detailed, accurate, and acknowledges the FTPS cert issue as an accepted risk. Good.

### 7.2 [LOW] `SECURITY.md` SRI table cites old SHAs
- The "Pinned GitHub Actions" table in `SECURITY.md:140-150` lists older SHAs (e.g., `actions/checkout@34e114876b…` v4.3.1) than the workflows themselves use (`actions/checkout@de0fac2e4500…` v6.0.2). The workflows are newer; the table is stale.
- **Recommendation:** update the table or replace it with a "see workflow files" pointer that won't drift.

---

## 8. Things I checked and didn't find

- **Tracked secrets in git history** — `git log -p -S "<zoom secret>"` returned no hits. Clean.
- **`pull_request_target` workflows** — none.
- **`shell=True` in Python** — none.
- **`eval` / `document.write` / `Function()` in JS** — none.
- **External CDN scripts** — none. CSP `script-src 'self'` is enforceable.
- **Server signature leakage** — `X-Powered-By` and `Server` are unset in both configs (`.htaccess:34-35`, `nginx.conf:18`).
- **Directory listing** — disabled (`Options -Indexes`, `autoindex off`).
- **`.git/` web exposure** — blocked by both `.htaccess` and `nginx.conf`. Worth a one-time `curl https://csoh.org/.git/HEAD` to confirm the live host honours the rule.

---

## 9. Prioritized action list

**Immediate (this week):**
1. **Rotate `ZOOM_CLIENT_SECRET`** in Zoom Marketplace.
2. `chmod 600 /Users/shawn/csoh.org/.env`.
3. Add explicit `permissions:` blocks to `update-news.yml`, `site-update-deploy.yml`, `manual-deploy.yml`.
4. Pin `actions/cache@v4` by SHA in `check-broken-links.yml`.
5. Add an HTTP/HTTPS scheme allowlist to `tools/check_url_safety.py`'s `resolve_url`.

**Soon (this month):**
6. Get a Let's Encrypt cert on the FTP host and turn on `ssl:verify-certificate yes`. (Or move to SFTP.)
7. Move `FTP_PASS` into a GitHub Deployment Environment with required approval.
8. Use `--env-password` so `FTP_PASS` is no longer in `lftp` `argv`.
9. Tighten `normalize-urls.yml` so auto-approve only fires when the diff is bounded to URL-only changes (mirror the `update-news.yml` allowlist).
10. Pin `nginx:alpine` by digest in `Dockerfile`.
11. Add a CSP `report-uri` and add COOP / CORP headers in both `.htaccess` and `nginx.conf`.

**Eventually (this quarter):**
12. Migrate `PAT_TOKEN` + `APPROVAL_PAT_TOKEN` to a GitHub App with installation tokens.
13. Verify HSTS preload status; submit to the preload list if eligible.
14. Reconcile `.htaccess` and `nginx.conf` CSPs (or document the drift).
15. Re-evaluate whether `frame-src` still needs `web.archive.org` and `www.wired.com`; if yes, add `sandbox` to those iframes.
16. Update the Pinned-Actions table in `SECURITY.md` (or replace with a pointer).
17. Enable Secret Scanning + Push Protection at the org level.

---

*End of report.*
