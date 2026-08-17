# CLAUDE.md

Notes for anyone (human or agent) working in this repo.

## Never put a CI-skip token in a commit message

GitHub skips **every** workflow on a push when the head commit's message
contains any of these:

```
[skip ci]  [ci skip]  [no ci]  [skip actions]  [actions skip]
```

It scans the **whole message - subject and body** - and does not care about
backticks or quotes. Writing one while *describing* it is enough to trigger it.

This has bitten us. Commit `7dc15f03` fixed a bug about `[skip ci]`, and quoted
the token in its body to explain the problem. Result: Deploy, Lint, and Validate
HTML all reported `total_count: 0`. The fix sat in `main`, unpublished, and the
push looked successful - nothing fails, nothing warns, no run appears at all.
The same content pushed with the token reworded triggered 2 runs immediately.

To write about the tokens in a commit message, describe them instead:
"a CI-skip marker", "the skip-ci token". Only commit *messages* are affected -
the strings are harmless in files like this one.

Our housekeeping workflow (`site-update-deploy.yml`) uses these tokens on
purpose, so its own commits don't re-trigger a deploy loop. That is deliberate.
The catch worth knowing: anything it fixes lands in `main` but does **not**
reach production until the next real deploy. Never rely on it to repair a live
problem.

## Diagnosing "the site looks unstyled"

Almost always SRI: the browser is refusing `style.css` because its hash doesn't
match the `integrity=` the HTML asks for, so every rule is dropped. Confirm in
one shot - compare what's served against what the page demands:

```sh
curl -s https://csoh.org/ | grep -o 'style\.css?v=[0-9a-f]*'          # what the HTML wants
curl -s "https://csoh.org/style.css?v=<that>" | openssl dgst -sha384 -binary | openssl base64 -A
curl -s https://csoh.org/ | grep -o 'integrity="sha384-[^"]*"' | head -1
```

Two distinct causes, both fixed but worth recognising:

- **Stale hashes shipped.** An asset edit pushed without re-stamping. `deploy.yml`
  now runs `update_sri.py` in the build, so the published artifact is
  self-consistent regardless. Still run it locally to keep the repo tidy.
- **A poisoned edge cache.** The old asset cached under the new `?v=` key and
  pinned by `immutable, max-age=31536000`. The publish jobs now upload assets
  before HTML, and `purge-cloudflare` clears the edge after all three origins
  update. A `cf-cache-status: HIT` serving the wrong bytes is the tell.

The `purge-cloudflare` job re-derives every versioned asset's hash from what the
edge actually serves and fails the deploy on a mismatch, so this should surface
in CI rather than in production.

## Site chrome is generated, not hand-edited

The nav, footer, logo block, and the hamburger/theme-toggle buttons are stamped
onto all ~233 pages by `tools/sync_chrome.py`. Edit the `CANON_*` constants
there and re-run it - never hand-edit the pages, or they drift. The logo drifted
into four shapes this way, and 126 pages silently lost their logo mark entirely.

It is idempotent; running it twice changes nothing the second time.
Full docs: `tools/SYNC_CHROME_README.md`.

## No number on the site should be typed by hand

Counts (resources, recaps, breaches, feeds, glossary terms) appear in JSON-LD
`numberOfItems`, OG-card subtitles, `llms.txt`, and body prose, and they drift
the moment content lands. `tools/sync_counts.py` recomputes all of them from
the real cards and files. When you write a count into a page or a doc, wrap it
in a marker so the script owns it:

```html
Access <!--count:resources_floor-->480+<!--/count--> curated resources.
```

The comment is invisible in rendered HTML *and* in GitHub-rendered Markdown, so
`README.md` uses them too. `python3 tools/sync_counts.py --check` is a CI gate.
Full docs: `tools/SYNC_COUNTS_README.md`.

## `/.well-known/` is deliberately carved out of the dotfile deny

`.well-known` starts with a dot, so the blanket hidden-path rules want to 403 it
along with `.git` and `.env`. Two places say otherwise, and they must stay in
step:

- `nginx.conf` - `location ^~ /.well-known/` placed before `location ~ /\.`.
  The `^~` is what does the work, not the ordering: nginx takes the longest
  matching *prefix* location, and `^~` tells it to stop there and never
  evaluate the regex denies.
- `tools/site-publish.filter` - `+ /.well-known/` before the `- .*` catch-all,
  or the file is never uploaded to the S3 / Azure origins at all.
- `deploy.yml` - `include-hidden-files: true` on the artifact upload, or the
  file is dropped between staging and publishing. See the next section; this
  is the one that is easy to miss because nothing errors.

This isn't cosmetic. `/security.txt` names `https://csoh.org/.well-known/security.txt`
in its `Canonical:` field, so RFC 9116 tooling fetches that exact URL; it used
to 403 and fail validation. If you harden the dotfile rules, re-test with:

```sh
curl -sI https://csoh.org/.well-known/security.txt | head -1   # want 200
curl -sI https://csoh.org/.git/config                | head -1   # want 403
```

## `upload-artifact` drops dotfiles by default, and says nothing

Since v4.4, `actions/upload-artifact` defaults to `include-hidden-files: false`
and silently omits every dot-path. It does not warn and does not fail: it prints
a file count, and a count is not something anyone reads as an error.

This is worse here than in most repos because of the fan-out. `build` stages
`dist/` and uploads it; `publish-aws` and `publish-azure` download that artifact,
but `publish-gcp` builds its container from a fresh checkout instead. So a file
missing from the artifact is missing on two origins out of three, and Cloudflare
load-balances across all three. `/.well-known/security.txt` came back 200 on
roughly one request in three - far more annoying to diagnose than a clean 404,
and invisible to any check that fetches a URL once and sees success.

The tell is in the build log, if you go looking: `stage_site.sh` reported 2973
files staged, the artifact carried 2972. One file, no error.

`deploy.yml` now sets `include-hidden-files: true`. That is safe *because*
`tools/site-publish.filter` already excludes every dot-path except
`/.well-known/`, so `dist/` contains exactly one hidden directory and there is
nothing else for the flag to smuggle through. **If you ever widen that filter,
this reasoning has to be rechecked** - the flag stops being a targeted carve-out
and becomes a blanket "ship every dotfile you staged."

It is already earning its keep: `/.well-known/` now holds `mta-sts.txt` as well
as `security.txt`, and MTA-STS would have been dropped on two origins the same
silent way. Anything added under `/.well-known/` from here (MTA-STS, ACME
challenges, `openid-configuration`) rides on this one flag, so verify a new
entry against production rather than assuming, and request it several times so
you actually land on each origin:

```sh
for i in $(seq 1 12); do
  curl -so /dev/null -w '%{http_code} ' "https://csoh.org/.well-known/<file>?cb=$RANDOM"
done; echo   # want twelve 200s, not eight
```

Two general lessons, both of which cost real time here:

- **Verifying one origin is not verifying the deploy.** A local nginx test
  proved the config was right and still could not see this, because the bug
  lived between staging and publishing rather than in any origin's config.
  When a fix touches what gets published, re-test against production and
  request it enough times to land on every origin.
- **A silent count is a failure mode.** Prefer a check that asserts, not one
  that prints. Comparing "files staged" against "files in the artifact" would
  have caught this at the moment it broke.

## Path filters must cover everything `stage_site.sh` publishes

GitHub's `*` does **not** match `/`, so `'*.html'` in a `paths:` filter means
*root-level pages only*. `deploy.yml` and `site-update-deploy.yml` both use
`'**.html'` for this reason - with `'*.html'` a commit touching only
`breaches/`, `meetings/`, `portfolio/`, or `homelab/` never triggered a deploy.
Commit `874a813c` is a real instance: it fixed MITRE technique links on
per-breach pages only, and did not publish.

The failure is silent - no error, no warning, the push just looks fine and the
change waits for the next unrelated commit. When you add a published file,
add it to both filters. Re-derive the published set with:

```sh
./tools/stage_site.sh /tmp/dist && find /tmp/dist -maxdepth 1
```

Widening a filter is always the safe direction: a superfluous pattern costs one
redundant deploy of identical bytes; a missing one costs a change that never
goes live.

## The published Terraform is content, and gets the same link gate as a page

`tools/site-publish.filter` is a **deny-list**: it excludes `*.py`, `*.md`,
`*.sh`, and `/tools/`, and everything not named is published. Nothing names
`infra/`, so `./tools/stage_site.sh` stages all 31 `.tf` files and they serve
live (`curl -sI https://csoh.org/infra/terraform/aws/oidc.tf` returns 200).

That is easy to read as an accident and treat as harmless. It isn't harmless,
because these files are deliberately **65% comments - about 3,100 lines of
teaching prose**, written so a newcomer can read the multi-cloud build end to
end (`README.md`, terraform.html). For a long time they were the only prose on
the site that no gate ever read: `check_docs_consistency.py` globs `*.html` and
`*.md`, `weekly-docs-review.yml` slices `git ls-files '*.html'`, and lychee's
input globs were HTML-only. The prose written to be read was the prose nothing
reviewed.

`check-broken-links.yml` now crawls `./infra/terraform/*/*.tf` as well, and its
`paths:` trigger carries `'**.tf'` (single `*` would match root-level only, per
the section above). lychee treats an unknown extension as plaintext and pulls
URLs out of it, so this needed no new tooling.

The one thing that does need care: **HCL is full of URL-shaped strings that are
identifiers, not destinations** - CSP allowlist hosts, the OIDC issuer
`https://token.actions.githubusercontent.com`, `principal://` IAM members,
placeholder examples like AWS's own `d111.cloudfront.net`. Unfiltered they
produced 12 errors, all false. The excludes for them in `.lychee.toml` are
anchored to the bare host root (`/?$`) precisely so the same host **with a
path** is still checked - `https://img.youtube.com/` is suppressed, the ~10
real `https://img.youtube.com/vi/<id>/hqdefault.jpg` thumbnails are not. Keep
that shape when you add one; a bare `"img\\.youtube\\.com"` would silently stop
checking every video thumbnail on the site.

Adding a CSP host or a federation issuer to a `.tf` file will surface as a
fresh 404 on its bare root. That is expected. Anchor it and add it.

Two things worth knowing about the publishing itself, neither of them changed
here because both are judgement calls rather than bugs:

- **Nothing on the site links to the published copies.** Every reference on
  terraform.html points at `github.com/.../blob/main/infra/...`, and `infra/`
  is not in `sitemap.xml`. The served copies are reachable only by typing the
  URL.
- **They are served with the wrong content-type on at least one origin.**
  `oidc.tf` comes back `binary/octet-stream` (browser downloads it) from one
  origin and `text/plain` (browser displays it) from another, so which one a
  reader gets depends on which origin the load balancer picked.

If you ever decide the served copies aren't earning their keep, adding `-
/infra/` to the filter is safe from a link perspective: nothing on the site
would 404. Leave the link gate in place regardless - the prose is still
teaching material on GitHub, and a dead link in a comment is dead either way.

## A TOML escape typo disabled link checking for eleven weeks, and CI stayed green

On 2026-05-29 a broken-link triage commit added seven exclude entries to
`.lychee.toml` written like this:

```toml
"news\.ycombinator\.com",     # invalid: \. is not a TOML escape
"news\\.ycombinator\\.com",   # correct
```

The rest of the file already used `\\.`; only these seven were wrong. In a TOML
basic (double-quoted) string, `\.` is an **invalid escape sequence**, and TOML
has no lenient mode: one bad escape fails the *whole file*. So lychee could not
load its config and exited before crawling anything.

Every downstream check then agreed that all was well:

- lychee wrote **no report**, and `lychee-action` runs with `fail: false`.
- The `[Errors]` grep looked for a section header in a file that did not exist,
  found nothing, and set `has_errors=false`.
- The sticky-issue action classified the absent report as **healthy**. Its
  check is `grep -qF -- "$STALE_MARKER" "$REPORT_FILE"` inside an `if`, so a
  missing file fails the grep without tripping `set -e`, and `stale=0`. No
  issue happened to be open, so it did nothing; had one been open it would
  have auto-closed it with "The latest link crawl found no broken links."

Eleven weeks of green runs, zero URLs checked. This is the same shape as the
inert Cloudflare ruleset and the dropped dotfiles: *an instrument that reports
"nothing is there" is indistinguishable from a broken instrument.*

Note the second-order trap in that grep, since the pattern recurs: **"the
marker is absent" and "the file is absent" are the same result to `grep -q`,**
and putting it in an `if` is exactly what suppresses the error that would have
told you which.

The fix is the `Assert the crawl actually ran` step in `check-broken-links.yml`,
which fails the job unless the report exists and its Summary table counts a
non-zero `Total`. That catches a config parse error, a lychee crash, and an
input glob that matches nothing. Note the deliberate asymmetry, and preserve
it: **a broken link never fails this job; a crawl that did not happen always
does.** They are not the same failure.

Validate the config before trusting a green run - the parse error is loud when
you actually ask for it:

```sh
lychee --dump --config .lychee.toml './*.html' | head -1
```

## A new page subdirectory has to be registered in several places

`portfolio/` and `homelab/` each needed hand-registration, and `homelab/` was
missed in `run_seo_audit.py` for months - invisibly, because the SEO score
averages over the pages it *did* audit, so an absent directory can't drag it
down. Check all of these when adding one:

`tools/sync_chrome.py` (glob + parent page) · `tools/run_seo_audit.py`
(`AUDITED_SUBDIRS`) · `tools/check_all_site_urls.py` · `.lychee.toml` ·
`tools/build_search_index.py` (`SUBDIR_TYPES`) · `tools/crosslink_pages.py`
(`SUBDIR_PATTERNS`) · `sitemap.xml`. The last three are opt-in judgement calls,
not automatic - `homelab/` is deliberately excluded from search and
cross-linking.

## `img/og/` and `img/thumbs/` are not interchangeable

Two in-house image sets, two different jobs, and reaching for the wrong one
is easy because both are "the picture for that page".

- **`img/og/`** - 1200×630 social cards from `tools/generate_og_images.py`.
  Built to be read at full width in a Slack or LinkedIn unfurl: headline,
  subtitle, footer.
- **`img/thumbs/`** - 3:2 glyph tiles from `tools/generate_thumbnails.py`.
  Built for the compact card grids on `index.html` and
  `what-practitioners-think.html`, whose columns land at 197-303px. One
  glyph, one category word, no sentences.

The compact grids used OG cards for a while and it failed twice over. The
shared `.resource-card .resource-preview` rule pins previews to a 160px-tall
box with `object-fit: cover` - correct for the ~460 third-party screenshots
in `img/previews/`, which arrive at mixed sizes and need normalising. Against
a 1.905 OG card in a 233px column that box is 1.46, so cover sliced 12-18%
off *each side*: the CSOH wordmark, the badge pill, and the first and last
words of the title. "Cloud Security News" rendered as "oud Security New".
Fixing the crop alone only exposed the second problem - at 233px the card's
6px subtitle was illegible and its headline just repeated the `<h3>` beneath
it.

So: `--og` and `--thumb` modifier classes each pin the box to their asset's
own ratio, and cover is a no-op for both. The four featured "start here"
cards still use OG cards deliberately; at 311px they are legible and the
extra weight suits them.

Both generators need Playwright, which on this machine is under
`/usr/bin/python3`, not the pyenv default. After adding a tile, run
`generate_webp.py img/thumbs` and then `update_sri.py`.

## Never allowlist a bare interpreter in a job that reads the web

`update-resources.yml` runs `anthropics/claude-code-action` behind an
`--allowedTools` list, and the comment beside it calls that list a guardrail
"so it can't, say, push." `Bash(python3:*)` used to be on it. That pattern
matches `python3 -c '<anything>'`, i.e. a whole interpreter, which voids every
other entry: once one tool runs arbitrary code, the rest of the allowlist is
decoration. The step reads pages it does not control via `WebFetch`/`WebSearch`,
and the same job holds the `csoh-ci` App token and `id-token: write`, and
`csoh-ci` is on the `Main` ruleset's `bypass_actors`. Injected page text ->
interpreter -> credential -> push to `main`, with nothing in between.

That job's `actions/checkout` now also sets `persist-credentials: false`. By
default checkout stores the token in `.git/config` as an `http.extraheader` and
leaves it there for the whole run, which turns "can read a file" into "has the
App token" with no shell required. It is safe to drop here because nothing
after the clone talks to git: `peter-evans/create-pull-request` is passed the
token explicitly.

Two rules. Never allowlist a bare interpreter (`Bash(python3:*)` and friends)
in a job that reads untrusted input; if a prompt genuinely needs Python, check
in a script and allowlist that exact path. And set `persist-credentials: false`
on any checkout in such a job.

## The Cloudflare security-header ruleset does not apply your changes

`cloudflare_ruleset.security_headers` in `infra/terraform/cloudflare/rules.tf`
carries `lifecycle { ignore_changes = [rules] }`, a deliberate workaround for a
v4-provider ordering bug. `rules` is the only meaningful attribute of a
`cloudflare_ruleset`, so that makes the resource inert after creation: tighten
the CSP in Git, run `terraform apply`, get a clean plan, and ship nothing. The
repo, the diff, and the reviewer all believe the header changed. Same silent
shape as the path-filter trap above.

Terraform cannot catch this, so CI asserts it from the outside.
`tools/check_edge_headers.py` parses the 8 header name/value pairs out of
`rules.tf` and compares them against what the live site actually serves; the
`purge-cloudflare` job in `deploy.yml` runs it and fails the deploy on any
drift, whether from a forgotten apply, a dashboard edit, or a weakened header.
Run it yourself with `python3 tools/check_edge_headers.py` (defaults to
`https://csoh.org/`, or `--url <origin>` for one origin). Applying a header
edit still has to be done by hand in the dashboard, or by dropping the
`lifecycle` block for a single apply. Delete the checker when the v5 provider
upgrade retires `ignore_changes`.

Header values now live in **three** places that must stay in step:

- `infra/terraform/cloudflare/rules.tf`: the edge, in front of all origins.
- `infra/terraform/aws/cloudfront.tf`:
  `aws_cloudfront_response_headers_policy.security`, wired into
  `default_cache_behavior`. This is new. The distribution's `*.cloudfront.net`
  hostname is public, and without it a direct request got a fully working copy
  of the site with no CSP, no HSTS, and no X-Frame-Options.
- `nginx-security-headers.conf`: the GCP origin, which always set its own.

Azure Blob static websites cannot emit custom response headers at all, so that
origin still depends entirely on the edge. That gap is known and cannot be
closed from this repo.

## A health check is one request multiplied by every Cloudflare data center

The load balancer monitor in `infra/terraform/cloudflare/load_balancer.tf` runs
against **all three origins from every Cloudflare data center**. At `interval =
60` that worked out to roughly 757 probe sources per cycle, about **1.09M probes
per origin per day**. Whatever that probe fetches, you are buying it a million
times a day.

It used to fetch `GET /`. Azure Blob static websites cannot gzip, so each probe
shipped the full uncompressed `index.html`: 52,425 bytes, against 11,193
gzipped. That is ~57 GB/day of billed egress, and it produced a **$119.77**
Azure bandwidth bill for July 2026 plus $12.66 of read operations. Commit
`e4eab64c` switched the monitor to `method = "HEAD"`, which took the per-probe
wire cost from 52,425 bytes to **372**, and the month from 1,771 GB to 12 GB -
back inside Azure's 100 GB/month free allowance, so the line went to zero.

HEAD is only safe here because `expected_body` is not set, so the body was
downloaded and discarded anyway. **If you ever set `expected_body`, this has to
go back to GET**, and the bill comes back with it.

Two things about this that cost real time:

- **It reads as traffic, not as configuration.** The daily egress curve was
  almost perfectly flat, ~40 GB/day rising to ~50 GB/day, with no weekday or
  weekend variation at all. Human traffic is never that smooth; a flat curve is
  a machine. The confirmation was in the origin access logs, where **97.8% of
  requests were `Cloudflare-Traffic-Manager/1.0` asking for `/`**.
- **One origin's bill does not tell you where the traffic enters.** The obvious
  theory was that someone had found the public `*.web.core.windows.net` endpoint
  and was scraping it directly, bypassing the edge. Comparing a second origin
  killed that in one query: GCP Cloud Run was serving ~1.05M requests/day
  against Azure's ~1.09M, i.e. an even split, which only happens if Cloudflare's
  load balancer is the thing generating it.

The check that answers "who is actually hitting the origins":

```sh
gcloud logging read 'resource.type="cloud_run_revision"' \
  --limit=1000 --freshness=30m --project=csoh-org-495800 \
  --format='value(httpRequest.userAgent)' | sort | uniq -c | sort -rn | head
```

`check_regions` is what bounds the fan-out, and there are two traps in it. It
lives on `cloudflare_load_balancer_pool`, **not** on the monitor - the v4
provider has no such attribute on `cloudflare_load_balancer_monitor` at all, so
setting it there validates fine and does nothing. And the plan caps how many
regions you may list: three returned `the number of probe regions exceeds the
allowed maximum: validation failed (1002)`. Leaving it unset means every data
center, which is the expensive default.

Worse, **a rejected pool apply still writes the value into Terraform state**.
After that failure, state claimed `["ENAM","WEU","WNAM"]` while live Cloudflare
had none. `terraform plan -refresh-only` surfaces the drift; a normal plan
refreshes first so it self-corrects in memory, but do not trust a state read on
its own after a failed apply.

The general lesson, which applies past health checks: **anything on a timer
against an origin is a unit cost multiplied by a fan-out you did not choose.**
At this probe rate every 1 KB added to `index.html` was worth about $3/month,
which is not a tradeoff anyone would have accepted if it had been visible. Ask
what the fan-out is before asking whether the payload is small.

## Cache rules match on file extension, and the last match wins

`cloudflare_ruleset.cache` in `rules.tf` keys off
`http.request.uri.path.extension`. That field is **empty** for `/` and for any
clean URL like `/about`, so those matched no tier at all, fell through to
Cloudflare's default - which does not cache HTML - and came back
`cf-cache-status: DYNAMIC`. The home page was being fetched from an origin on
every single request. `/search-index.json` (3.5 MB, the largest file on the
site) was uncached for the same reason, as was `llms.txt`.

The rule now also matches `json`, `txt`, the empty extension, and
`ends_with(path, "/")`. Note that `matches` is not available: this zone has no
regex support in rule expressions, so extensionless paths have to be caught with
plain string functions.

The second half is the one that will bite you again: **cache rules apply the
last matching rule, not the first.** The tier-1 rule pinning `/search.html` to
60 seconds sits above the general HTML rule, and had been silently overridden
since it was written - production served `search.html` with `max-age=3600`. The
general rule now carries `and http.request.uri.path ne "/search.html"`, which
makes the outcome independent of ordering rather than dependent on getting the
order right. Prefer that shape: an explicit exclusion survives someone inserting
a rule above it, a carefully ordered list does not.

Caching `json`/`txt` for an hour is safe only because `purge-cloudflare` clears
the edge on every deploy. If that job is ever removed, these TTLs need rethinking.

Verify by asking for the same URL twice - the second must not say `DYNAMIC`:

```sh
for u in / /about /search-index.json /search.html; do
  printf '%-22s ' "$u"
  curl -sI "https://csoh.org$u" | grep -i '^cf-cache-status' | tr -d '\r'
done
```

## `vendor/` files are patched, and a re-vendor silently reverts the patch

`vendor/goatcounter-count.js` is not a pristine upstream copy. Two lines are
changed so the analytics beacon stops transmitting the query string:
`q: location.search` becomes `q: ''`, and `get_path()` returns `loc.pathname`
instead of `loc.pathname + loc.search`. It matters because `/search.html?q=<term>`
is deep-linkable here, so the query string carried visitors' search terms, and
`privacy.html` and `llms.txt` both promise it is not collected. Dropping a
newer upstream release over the top reverts both edits and quietly resumes
collecting the thing the site says it does not, with the docs still claiming
otherwise.

Each edit is marked in the source with a `CSOH LOCAL MODIFICATION` comment and
listed in `vendor/README.md`. Everything in `vendor/` is SRI-stamped, so re-run
`python3 update_sri.py` after any edit there or browsers refuse the file.

## A workflow that needs cloud credentials must declare `environment: production`

All three clouds pin their OIDC trust to the same subject,
`repo:<owner>/<repo>:environment:production`: `infra/terraform/aws/oidc.tf`
(`StringEquals` on the `sub` claim), `infra/terraform/azure/identity.tf`
(`subject =`), and `infra/terraform/gcp/wif.tf` (both the `attribute_condition`
and the `principal://.../subject/...` IAM member). GCP was the outlier: it
gated on `assertion.repository` alone, which trusted every workflow in the
repo, on any branch, in any environment or none, to impersonate the deployer
service account.

This is a deliberate gate, not boilerplate. A new job that calls
`google-github-actions/auth` or `aws-actions/configure-aws-credentials` without
`environment: production` will fail to authenticate, and the error will not
explain why. `id-token: write` alone is not enough. The `production`
environment is itself restricted to `main` by a deployment branch policy, so
the environment pin enforces the branch transitively;
`var.github_branch` in `infra/terraform/gcp/variables.tf` documents that intent
but is not referenced by the trust.

## Two Cloudflare tokens, and only one of them is on this machine

There are two, deliberately. The **cache-purge** token has a single permission,
**Zone → Cache Purge**, scoped to `csoh.org`, because the deploy path should not
hold a credential able to rewrite the security headers. The **Terraform** token
is much broader and must stay out of CI.

The purge token now lives **only** in the GitHub Actions secret
`CLOUDFLARE_API_TOKEN`, which `deploy.yml`'s `purge-cloudflare` job reads. It is
not in `.env` and cannot be recovered from CI - Actions secrets are write-only.
If you need to purge by hand, make a *new* Custom token (Zone → Cache Purge,
Zone Resources `csoh.org` only) rather than rolling the existing one; rolling
invalidates what CI holds and the next deploy's purge job fails. The rotation
procedure, which does include replacing the Actions secret, is in
`SECURITY.md`.

`.env` holds `CLOUDFLARE_TF_API_TOKEN` - the broad Terraform one. The provider
only reads `CLOUDFLARE_API_TOKEN`, so map it for the run and do not export it
globally:

```sh
set -a; . ./.env; set +a
export CLOUDFLARE_API_TOKEN="$CLOUDFLARE_TF_API_TOKEN"
```

`.env` also carries `TF_VAR_account_id`, `TF_VAR_zone_id`, and the three
`TF_VAR_*_origin_host` values, so plan and apply need no `-var` flags and no
AWS/GCP/Azure logins. The origin hostnames come from the `csoh-origins` LB pool.

Two ways this misleads you when it goes wrong:

- **A stale or invalid token reads as a scope problem.** Both Cloudflare values
  in `.env` were silently invalid for a while, and CI never noticed because it
  uses the Actions secret, not the file. If the API says `Invalid API Token`,
  check the value before the permissions. Token length is *not* a validity
  signal - these are ~53 characters with a short `prefix_`, not 40.
- **A genuinely under-scoped token looks valid.** `/user/tokens/verify` reports
  `active` regardless of scope, and Cloudflare gates each **ruleset phase**
  behind its own permission group. This stack spans three phases plus DNS, load
  balancing, and zone settings, so a partly-scoped token fails only the
  resources it cannot reach and the missing permissions surface two at a time
  over several runs. `Authentication error (10000)` and `Unauthorized to access
  requested resource (9109)` naming individual resources is that shape. The full
  eight-group list is in `infra/README.md`.

One more thing that will surprise you: a plan of this stack always shows
`cloudflare_record.dmarc`, `.mta_sts_id`, and `.smtp_tls_reporting` changing.
That is quote-stripping drift in Terraform *state* - live DNS already serves the
unquoted content - so it is a no-op, but it means an unscoped `apply` writes to
production DMARC and MTA-STS as a side effect. Scope edge-config applies with
`-target=cloudflare_ruleset.redirects`, and reconcile the DNS deliberately if
you ever want it to stop appearing.

## Terraform must be a native arm64 build on this machine

Check with `file "$(which terraform)"` before debugging anything else. Intel
Homebrew lives at `/usr/local` and installs an x86_64 Terraform, which then
downloads x86_64 **providers**, which then run under Rosetta. The AWS provider
binary is ~725 MB and translating it exceeds Terraform's plugin-start timeout.

The symptom is not an error that names any of this: a provider process pegged
at 100% CPU with **zero network connections**, and
`timeout while waiting for plugin to start` roughly half the time, so it looks
flaky rather than broken. Only the AWS stack really suffers; the Google and
Cloudflare providers are small enough to translate in time. After switching to
a native build, re-run `terraform init` in all four stack directories -
`azure/` is easy to miss until `terraform output` fails with
`Required plugins are not installed`.

Related, same debugging session: keep `AWS_EC2_METADATA_DISABLED=true`
exported. Local AWS auth is `aws login` with a `login_session` in
`~/.aws/config`, and the Terraform provider does not implement that mechanism -
it needs `aws configure export-credentials --format env`. When the session
expires, the provider falls through the credential chain to EC2 instance
metadata, which does not exist on a laptop, and hangs for minutes before
failing with `no EC2 IMDS role found`. That message points at IMDS instead of
at the expired session. `aws sts get-caller-identity` gives the real answer in
one line.

And if a run dies wedged, never reach for `-lock=false`. It does not clear the
lock, it starts a *second* concurrent apply against the same state. Confirm no
terraform process is alive first (a plugin whose parent is `PPID 1` is an
orphan), then `force-unlock` with the ID from the error.

## Local `dig` lies on this machine. Verify DNS over DoH, with a control.

Two separate wrong answers in one day, both from `dig` on this laptop, both
costing real time. Neither looked like a tooling problem at the time; both
looked like the infrastructure was broken.

**It strips the DNSSEC AD bit.** `dig +dnssec csoh.org A @1.1.1.1 | grep flags:`
returns `qr rd ra` with no `ad`, which reads as "DNSSEC is not validating". It
is. The zone has been signed and delegated since late July, and both Google and
Cloudflare DNS-over-HTTPS return `AD=true`. That false negative was believed for
two weeks and written into three documents, one of which then instructed an
operator to submit a DS record for an already-delegated zone: the single DNSSEC
mistake that takes a domain fully dark for every validating resolver.

**It serves stale records after a change.** Immediately after a `terraform
apply` that added a second `rua` address to `_dmarc`, `dig @rosalie.ns.cloudflare.com`
- the zone's own authoritative nameserver - still returned the OLD value, while
Terraform state and both DoH resolvers showed the new one. Trusting `dig` there
would have meant concluding the apply failed and re-running it.

So: **do not verify a DNS change with local `dig`.** Ask a resolver that answers
over HTTPS, and ask two of them:

```sh
curl -s "https://dns.google/resolve?name=csoh.org&type=A" | grep -o '"AD":[a-z]*'
curl -s -H 'accept: application/dns-json' \
  "https://cloudflare-dns.com/dns-query?name=_dmarc.csoh.org&type=TXT"
```

**And run a control query before believing any negative result.** This is the
cheap move that would have caught both cases in seconds:

- For the AD bit, ask about a domain that is definitely signed. `cloudflare.com`
  and `internetsociety.org` fail the same `dig` check here. If a known-good
  domain fails your test, the test is wrong, not the zone.
- For a stale record, compare against a record you did *not* just change.
  `_mta-sts` read identically via `dig` and DoH at the same moment `_dmarc` did
  not, which located the problem immediately: not a broken resolver, a stale
  answer for exactly the record that had changed.

The general form, since this file already records two other instances of it (the
inert Cloudflare ruleset, and `terraform apply` reporting success while shipping
nothing): **an instrument that reports "nothing is there" is indistinguishable
from a broken instrument until you point it at something you know is there.**

## There is a QA site now, and `main` is still production

`qa.csoh.org` is a staging copy of the site, deployed from the `qa` branch to a
second Cloud Run service. `main` still means production and still deploys the
moment anything lands on it - the QA branch is an addition, not a redirection.
Promotion is **Actions → Promote QA to production**, which fast-forwards `main`.

Work on QA in `../csoh-qa`, a worktree permanently on `qa`. Do not `git switch
qa` in the main checkout: several Claude sessions share it, and switching moves
all of them mid-task.

Four things here are load-bearing and look like mistakes:

- **`deploy-qa.yml` has no `paths:` filter, on purpose.** A third filter to keep
  in step with `deploy.yml` and `site-update-deploy.yml` is a third chance to
  repeat the `'*.html'` bug above. And `promote-qa.yml`'s "was this commit
  actually QA-tested?" gate only works because every push to `qa` produces a run.
  Adding a filter there makes filtered-out commits unpromotable.
- **The QA container config must stay identical to production's.** Promotion
  reuses the image QA built, by tag, from the shared Artifact Registry repo.
  A QA-only container setting silently turns promotion back into a rebuild.
  Anything QA-specific belongs at the Cloudflare edge.
- **QA is deliberately outside the load balancer pool.** See the health-check
  section above: pool membership means being probed from every data center,
  around the clock, and never scaling to zero.
- **The Host rewrite is a Worker, not an Origin Rule.** Cloud Run picks a
  service by `Host`, and Host Header Override is a paid-plan feature this zone
  does not have. The entitlement is checked at apply, not at plan, so the config
  validates and plans cleanly and then fails - another instance of the pattern
  this file keeps recording, where the instrument reports success for something
  that will not work.

`qa.csoh.org` sits behind Cloudflare Access, but its origin's `*.run.app`
hostname is publicly reachable exactly as production's is. Access is not a
secrecy boundary; do not stage anything there that would harm you if read early.

Full docs, including the ten Cloudflare token permission groups, what each error
code actually means, and the registry race between the two deploy workflows:
`.github/workflows/QA_PIPELINE_README.md`.
