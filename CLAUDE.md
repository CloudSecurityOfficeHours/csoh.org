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
Access <!--count:resources_floor-->410+<!--/count--> curated resources.
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

This isn't cosmetic. `/security.txt` names `https://csoh.org/.well-known/security.txt`
in its `Canonical:` field, so RFC 9116 tooling fetches that exact URL; it used
to 403 and fail validation. If you harden the dotfile rules, re-test with:

```sh
curl -sI https://csoh.org/.well-known/security.txt | head -1   # want 200
curl -sI https://csoh.org/.git/config                | head -1   # want 403
```

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
