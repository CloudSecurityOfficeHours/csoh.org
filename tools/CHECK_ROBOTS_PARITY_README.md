# Robots.txt Parity Check

Asserts that the `robots.txt` csoh.org actually serves is the one in
[`robots.txt`](../robots.txt) in this repo.

Exits non-zero on any difference. It is a CI gate in waiting - **not yet wired into
`deploy.yml`**, because it fails today. See
[Not in CI yet, on purpose](#not-in-ci-yet-on-purpose).

## Quick Start

```bash
python3 tools/check_robots_parity.py                                # checks https://csoh.org/robots.txt
python3 tools/check_robots_parity.py --url https://csoh.org/        # same, robots.txt is appended
python3 tools/check_robots_parity.py --url http://127.0.0.1:8000/robots.txt
```

Passing run (against a local `python3 -m http.server` serving the repo's own file):

```
Checking robots.txt from robots.txt against http://127.0.0.1:8731/robots.txt
  ok  99 lines match, byte-for-byte after whitespace normalization

OK: robots.txt at http://127.0.0.1:8731/robots.txt matches the repo.
```

Standard library only. No `pip install`, no Cloudflare API token: it does a plain `GET`
and compares the body against the file on disk.

`--url` is the only flag, same as [`check_edge_headers.py`](check_edge_headers.py). A URL
with no path (or a bare `/`) gets `robots.txt` appended, so the flag can be copy-pasted
from the header-check step without silently comparing the homepage against robots.txt.

## Why this exists: the edge rewrites the file

`robots.txt` here is a policy document, not a formality. It explicitly **invites** the AI
crawlers by name - GPTBot, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended,
CCBot, Bytespider, Meta-ExternalAgent and more - because CSOH is a public community
resource and being cited in AI-generated answers is the point.
[`llms.txt`](../llms.txt) states it out loud:

> The robots.txt explicitly allows GPTBot, ClaudeBot, PerplexityBot, Google-Extended,
> Applebot-Extended, CCBot and friends.

Cloudflare can overwrite that from outside the repo. **AI Crawl Control** (dashboard:
Security -> Bots -> AI Crawl Control -> managed robots.txt) rewrites the `/robots.txt`
response at the edge, prepending a Content-Signal preamble and a
`# BEGIN Cloudflare Managed content` block ahead of the origin's file. That block carries
`Disallow: /` for the crawlers the repo Allows.

It is enabled on this zone right now. Confirm in two commands:

```sh
curl -s https://csoh.org/robots.txt | grep -c 'Cloudflare Managed'   # 2
grep -c 'Cloudflare Managed' robots.txt                              # 0
```

The origin file is untouched and still present, immediately below the injection. That is
what makes it hard to notice: `git diff` is clean, all three origins serve the right
bytes, `terraform plan` is clean (nothing in `infra/terraform/cloudflare/` declares this
toggle), and only the edge disagrees.

What crawlers then do is genuinely undefined. RFC 9309 says records sharing a user-agent
token should be merged, in which case an `Allow: /` and a `Disallow: /` of equal
specificity resolve to the least restrictive rule - but plenty of crawlers take the first
matching group and stop. Either way the file the world reads no longer says what this repo
says, and the llms.txt promise becomes false.

Same failure class as [`check_edge_headers.py`](CHECK_EDGE_HEADERS_README.md): a control
plane outside Terraform quietly overriding policy that lives in Git, with nothing in the
repo, the diff, or the deploy log to show for it. Same remedy - assert it from the outside.

## What it checks

One thing: the served bytes versus `robots.txt` on disk, as normalized line lists.

**Normalized (trivia only):**

| Normalized away | Why it is safe |
|---|---|
| CRLF and lone CR line endings | S3 and Blob round-trip bytes faithfully, but a Windows checkout or a dashboard paste would not. No crawler cares. |
| Trailing whitespace on each line | Invisible, and no directive's meaning depends on it. |
| Runs of blank lines, and leading/trailing blanks | Blank lines only separate groups; a doubled one changes nothing. |

**Deliberately NOT normalized:** case, directive order, indentation, duplicate rules, and
**comments**. Comments especially - the Cloudflare injection is more than half comment
text, so normalizing comments away would blind the check to the entire preamble.

On mismatch it prints a `difflib.unified_diff` with two lines of context (capped at 80
diff lines, remainder counted and suppressed) rather than dumping both files, then tries
to attribute the cause.

The pass/fail decision is the plain text comparison and nothing else. The robots.txt
group parser in the script is used **only** to explain a failure in human terms, so a
parser bug can never make a drifted file look clean.

## When it fails

A real run against production today, abridged (the script prints the full 60-line
injected block in the diff; exit status 1):

```
Checking robots.txt from robots.txt against https://csoh.org/robots.txt

FAIL: the robots.txt served at https://csoh.org/robots.txt is not the one in this repo (160 lines served vs 99 in Git).

  --- repo robots.txt
  +++ https://csoh.org/robots.txt
  @@ -1,2 +1,63 @@
  +# As a condition of accessing this website, you agree to abide by the following
  +# content signals:
  ...
  +# BEGIN Cloudflare Managed content
  +
  +User-agent: *
  +Content-Signal: search=yes,ai-train=no,use=reference
  +Allow: /
  +
  +User-agent: Amazonbot
  +Disallow: /
  ...
  +# END Cloudflare Managed Content
  +
   # Cloud Security Office Hours - Robots.txt
   # Updated: April 2026

CAUSE: Cloudflare's managed robots.txt is prepending 60 line(s) at the edge.

  7 crawler(s) the repo explicitly Allows are Disallowed by the injected block:
    - Applebot-Extended
    - Bytespider
    - CCBot
    - ClaudeBot
    - Google-Extended
    - GPTBot
    - Meta-ExternalAgent

  robots.txt and llms.txt both promise these crawlers are welcome. The edge
  is contradicting that, and RFC 9309 leaves the outcome of two conflicting
  groups for the same token up to the crawler.

  Also Disallowed by the injection (not named in the repo): amazonbot, cloudflarebrowserrenderingcrawler

  Turn it off at: Cloudflare dashboard -> Security -> Bots -> AI Crawl Control -> managed robots.txt
  It is a zone-level toggle, not Terraform-managed - infra/terraform/cloudflare/
  does not declare it, so `terraform apply` will neither report nor fix this.
```

The conflict list is computed, not hardcoded: it intersects the user agents the injected
block Disallows with the ones the repo's file Allows, and prints them in the repo's own
spelling so they can be grepped straight out of `robots.txt`.

**If the injection is not the cause**, the script says so and points elsewhere:

```
CAUSE: not the known Cloudflare injection. Check for a stale edge cache (a
`cf-cache-status: HIT` serving old bytes), an origin that missed the last publish,
or a hand-edit at one origin - ./tools/stage_site.sh /tmp/dist shows what should ship.
```

Two other exits, both status 1: a non-200 response (`error: <url> returned HTTP 404 ...`)
and an unreachable host (`error: could not fetch <url>: ...`). Unlike
`check_edge_headers.py`, an error page is **not** something to assert against here - this
script compares a body, and a 404 body is not a robots.txt.

## Not in CI yet, on purpose

**Do not add this to `deploy.yml` today.** The Cloudflare injection is still enabled, so
the check fails against production right now, and adding it as a gate would break every
deploy. Follow this order:

1. **Turn the feature off.** Cloudflare dashboard -> Security -> Bots -> AI Crawl Control
   -> managed robots.txt. It is a zone-level toggle and is not declared in
   `infra/terraform/cloudflare/`, so there is nothing to `terraform apply`.
2. **Confirm the edge caught up.** The edge caches robots.txt; a deploy's
   `purge-cloudflare` job clears it, or purge by hand.
   ```sh
   curl -s https://csoh.org/robots.txt | grep -c 'Cloudflare Managed'   # want 0
   python3 tools/check_robots_parity.py                                 # want exit 0
   ```
3. **Only then, add the CI step.** Append it to the `purge-cloudflare` job in
   [`deploy.yml`](../.github/workflows/deploy.yml), immediately after
   `Verify live security headers match the repo`. That job already `needs:` all three
   publishers and already checks out the repo (with `persist-credentials: false`) to get
   `check_edge_headers.py`, so this needs no new checkout - just the step:

   ```yaml
         # Cloudflare's AI Crawl Control can prepend a managed block to
         # /robots.txt at the edge, Disallowing the AI crawlers this repo's
         # robots.txt deliberately Allows and llms.txt advertises. Nothing in
         # infra/terraform/cloudflare/ declares that toggle, so terraform can
         # neither report nor fix it - assert the served file from outside.
         - name: Verify live robots.txt matches the repo
           run: python3 tools/check_robots_parity.py --url https://csoh.org/
   ```

   Nothing else needs changing: `robots.txt` is already in `deploy.yml`'s `paths:` filter
   and in the published file set, and the script is standard library only.

Until step 3 lands, run it by hand after any `robots.txt` edit.

## Delete this script when...

...Cloudflare's managed robots.txt is gone for good, or the site decides it **wants** the
edge to own robots.txt. The second case is a real decision, not a shortcut: `robots.txt`,
`llms.txt`, and the AI-crawler stance described on the site would all have to change to
match, and the repo's file should then stop claiming to be authoritative.

## See also

- [`CHECK_EDGE_HEADERS_README.md`](CHECK_EDGE_HEADERS_README.md) - the same "does the live
  site match the repo" shape, for security headers instead of robots.txt
- [`UPDATE_SRI_README.md`](UPDATE_SRI_README.md) - the third such gate, for asset bytes
- [SECURITY.md](../SECURITY.md) - the multi-origin architecture behind the edge
