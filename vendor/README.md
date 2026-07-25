# `vendor/` - third-party browser libraries, served from our own origin

Everything here is a third-party file that the site loads at runtime. It is
**self-hosted on purpose**: the CSP (`script-src 'self'`) allows no remote
script origins, so a CDN `<script src>` would simply be blocked. Self-hosting
also means a compromise of someone else's CDN cannot change what our visitors
execute.

Every file here is referenced with an `integrity="sha384-..."` attribute.
**After editing anything in this directory you must re-stamp those hashes**, or
browsers will refuse the file and the feature silently dies:

```bash
python3 update_sri.py
```

See `tools/UPDATE_SRI_README.md` for the full story.

## Files

| File | Upstream | License |
| --- | --- | --- |
| `goatcounter-count.js` | <https://www.goatcounter.com> | ISC |
| `minisearch-7.1.2.min.js` | <https://github.com/lucaong/minisearch> | MIT |

## Local modifications

`minisearch-7.1.2.min.js` is a pristine upstream copy.
`goatcounter-count.js` is **not** - it carries two local patches, each marked in
the source with a `CSOH LOCAL MODIFICATION` comment. If you ever re-vendor a
newer upstream release, you must re-apply them: a straight overwrite silently
reverts the change and resumes sending data we tell visitors we do not collect.

The two files are also hashed differently. `goatcounter-count.js` is in
`update_sri.py`'s `ASSETS` list, so it gets an `integrity=` and a `?v=` cache-bust
key stamped automatically. `minisearch-7.1.2.min.js` is not: its `integrity=` is
hand-stamped in `search.html` and it carries no `?v=` (the version is in the
filename).

### `goatcounter-count.js`

Two changes, both narrowing what the analytics beacon transmits. Neither
affects page-view counting.

1. **`q: location.search` → `q: ''`** (in `get_data`)
2. **`return (loc.pathname + loc.search)` → `return loc.pathname`** (in `get_path`)

**Why.** Upstream sends the full query string to the analytics host, both as a
dedicated `q` field and appended to the `p` (path) field. On this site that
leaks visitor search terms: `/search.html?q=<term>` is a deep-linkable URL
(`search-init.js` reads `params.get('q')` and pre-fills the box), and
`/resources.html?q=`/`?category=` behave the same way. So a shared or
bookmarked search URL sent the search term to `csoh.goatcounter.com`.

That contradicted our own published privacy statement, which says the analytics
record "only the page path, referrer, browser and OS, and screen size, in
aggregate" (`privacy.html`). Rather than weaken the promise, we narrowed the
beacon to match it.

The related Do Not Track / Global Privacy Control opt-out is **not** here - it
lives in `main.js`, which sets `window.goatcounter.no_onload = true` before this
deferred script runs, so the vendored file stays closer to upstream.
