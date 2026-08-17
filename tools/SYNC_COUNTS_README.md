# Site Count Sync

Recomputes every number the site quotes about itself - resource totals, recap totals, breach totals, feed counts, glossary size - from the actual cards and files on disk, and rewrites them wherever they appear.

The site repeats the same counts in a lot of places, and every one of them drifts the moment content is added. This script makes drift impossible to ship.

## Quick Start

```bash
python3 tools/sync_counts.py            # apply fixes, print what changed
python3 tools/sync_counts.py --check    # exit 1 if anything is out of sync (no writes)
```

`--check` is what CI runs, via [`update-counts.yml`](../.github/workflows/update-counts.yml) every Monday at 07:30 UTC.

Typical output:

```
Canonical counts: resources=415, meetings=105, breaches=20, feeds=39, glossary_terms=310
All counts already in sync.
```

## Where the counts come from

Nothing is configured. Each number is derived from the thing it describes:

| Count | Source of truth |
|---|---|
| `resources` | Unique `.resource-card` entries on `resources.html`, deduped by URL |
| `meetings` | `meetings/*.html` files on disk |
| `breaches` | `breaches/*.html` files on disk |
| `feeds` | Length of the `FEEDS` list in `update_news.py` |
| `glossary_terms` | `<dt>` elements in `glossary.html` |

## What it rewrites

**1. Managed ItemLists on `resources.html`.** Both structured-data blocks are regenerated from the page's own cards: the standalone `ItemList` enumerates every unique resource in page order, and the `CollectionPage.mainEntity` list enumerates the category sections. `numberOfItems` follows automatically because it is computed, not typed.

**2. Every other ItemList on the site.** These are not regenerated, but the invariant `numberOfItems == number of enumerated ListItems` is enforced. A count can never claim more items than the list actually contains.

**3. `<!--count:...-->` prose markers**, in both HTML pages and Markdown docs. Wrap a number in a marker and it becomes self-maintaining:

```html
Access <!--count:resources_floor-->480+<!--/count--> curated resources.
```

The comment is invisible in rendered HTML *and* in GitHub-rendered Markdown, so `README.md` can use them too. Available keys:

| Key | Renders as | Example |
|---|---|---|
| `resources_floor` | `N+`, floored to the nearest ten | `410+` |
| `resources` | exact | `415` |
| `meetings` | exact | `105` |
| `meetings_floor` | `N+`, floored to the nearest ten | `100+` |
| `breaches` | exact | `20` |
| `feeds` | exact | `39` |

**When you write a count into a page or a doc, wrap it in a marker.** An unmarked number is one nobody will remember to update.

**4. Count phrases where a marker cannot go** - inside `content="..."` meta/Open Graph attributes and inside JSON-LD, where an HTML comment would render as literal text or break the JSON. These are handled by a short list of deliberately narrow regexes (`HTML_PROSE_RULES`), each of which only ever matches a count already spelled as `<number>+ <phrase>`. Adding a new phrasing means adding a rule; the patterns are intentionally not generic.

**5. `llms.txt`** - plain text, so regex rather than markers.

**6. OG-card subtitles in `generate_og_images.py`.** Meetings use the exact count; resources and glossary terms use a floored `N+`. `sync_counts.py` only edits the script; `update-counts.yml` notices that edit and re-renders the three count-bearing cards (`index.html`, `resources.html`, `meetings.html`) rather than rebuilding all ~105 top-level images.

## When to run it

- After adding a resource, meeting recap, breach page, glossary term, or news feed.
- Before opening a PR that adds content, so CI doesn't have to correct you.
- Never by hand for the weekly drift - `update-counts.yml` already does that, and its commit is deliberately **not** CI-skipped so the corrected counts actually deploy.

## See also

- [`SYNC_CHROME_README.md`](SYNC_CHROME_README.md) - the other site-wide stamper, for nav and footer rather than numbers
- [DEVELOPMENT.md → Adding a new page](../DEVELOPMENT.md#adding-a-new-page)
