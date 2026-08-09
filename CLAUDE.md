# CLAUDE.md

Notes for anyone (human or agent) working in this repo.

## Never put a CI-skip token in a commit message

GitHub skips **every** workflow on a push when the head commit's message
contains any of these:

```
[skip ci]  [ci skip]  [no ci]  [skip actions]  [actions skip]
```

It scans the **whole message — subject and body** — and does not care about
backticks or quotes. Writing one while *describing* it is enough to trigger it.

This has bitten us. Commit `7dc15f03` fixed a bug about `[skip ci]`, and quoted
the token in its body to explain the problem. Result: Deploy, Lint, and Validate
HTML all reported `total_count: 0`. The fix sat in `main`, unpublished, and the
push looked successful — nothing fails, nothing warns, no run appears at all.
The same content pushed with the token reworded triggered 2 runs immediately.

To write about the tokens in a commit message, describe them instead:
"a CI-skip marker", "the skip-ci token". Only commit *messages* are affected —
the strings are harmless in files like this one.

Our housekeeping workflow (`site-update-deploy.yml`) uses these tokens on
purpose, so its own commits don't re-trigger a deploy loop. That is deliberate.
The catch worth knowing: anything it fixes lands in `main` but does **not**
reach production until the next real deploy. Never rely on it to repair a live
problem.

## Diagnosing "the site looks unstyled"

Almost always SRI: the browser is refusing `style.css` because its hash doesn't
match the `integrity=` the HTML asks for, so every rule is dropped. Confirm in
one shot — compare what's served against what the page demands:

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
there and re-run it — never hand-edit the pages, or they drift. The logo drifted
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
Access <!--count:resources_floor-->450+<!--/count--> curated resources.
```

The comment is invisible in rendered HTML *and* in GitHub-rendered Markdown, so
`README.md` uses them too. `python3 tools/sync_counts.py --check` is a CI gate.
Full docs: `tools/SYNC_COUNTS_README.md`.

## `/.well-known/` is deliberately carved out of the dotfile deny

`.well-known` starts with a dot, so the blanket hidden-path rules want to 403 it
along with `.git` and `.env`. Two places say otherwise, and they must stay in
step:

- `nginx.conf` — `location ^~ /.well-known/` placed before `location ~ /\.`.
  The `^~` is what does the work, not the ordering: nginx takes the longest
  matching *prefix* location, and `^~` tells it to stop there and never
  evaluate the regex denies.
- `tools/site-publish.filter` — `+ /.well-known/` before the `- .*` catch-all,
  or the file is never uploaded to the S3 / Azure origins at all.
- `deploy.yml` — `include-hidden-files: true` on the artifact upload, or the
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
`'**.html'` for this reason — with `'*.html'` a commit touching only
`breaches/`, `meetings/`, `portfolio/`, or `homelab/` never triggered a deploy.
Commit `874a813c` is a real instance: it fixed MITRE technique links on
per-breach pages only, and did not publish.

The failure is silent — no error, no warning, the push just looks fine and the
change waits for the next unrelated commit. When you add a published file,
add it to both filters. Re-derive the published set with:

```sh
./tools/stage_site.sh /tmp/dist && find /tmp/dist -maxdepth 1
```

Widening a filter is always the safe direction: a superfluous pattern costs one
redundant deploy of identical bytes; a missing one costs a change that never
goes live.

## A new page subdirectory has to be registered in several places

`portfolio/` and `homelab/` each needed hand-registration, and `homelab/` was
missed in `run_seo_audit.py` for months — invisibly, because the SEO score
averages over the pages it *did* audit, so an absent directory can't drag it
down. Check all of these when adding one:

`tools/sync_chrome.py` (glob + parent page) · `tools/run_seo_audit.py`
(`AUDITED_SUBDIRS`) · `tools/check_all_site_urls.py` · `.lychee.toml` ·
`tools/build_search_index.py` (`SUBDIR_TYPES`) · `tools/crosslink_pages.py`
(`SUBDIR_PATTERNS`) · `sitemap.xml`. The last three are opt-in judgement calls,
not automatic — `homelab/` is deliberately excluded from search and
cross-linking.

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
