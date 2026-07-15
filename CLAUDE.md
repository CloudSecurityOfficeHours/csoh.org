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
onto all ~222 pages by `tools/sync_chrome.py`. Edit the `CANON_*` constants
there and re-run it — never hand-edit the pages, or they drift. The logo drifted
into four shapes this way, and 126 pages silently lost their logo mark entirely.

It is idempotent; running it twice changes nothing the second time.
