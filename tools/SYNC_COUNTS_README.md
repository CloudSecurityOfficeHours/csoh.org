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
Canonical counts: resources=485, meetings=107, breaches=45, feeds=62, glossary_terms=317,
ctfs=52, conferences=26, long_form=83, vendors=308, vendor_categories=32, og_images=249,
resource_categories=6, sitemap_urls=265, news_banners=58, faq_pages=64,
author_card_pages=91, schema_types=39
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
| `glossary_terms` | `id="term-…"` anchors in `glossary.html` |
| `ctfs` / `conferences` | `.resource-card` articles on that directory page |
| `long_form` | Root pages that are not utility pages and carry >= 1,500 words of body copy |
| `vendors` / `vendor_categories` | Distinct `<li><strong>` names and `<h2>` sections on `vendor-landscape.html` |
| `og_images` | `img/og/**/*.jpg` on disk |
| `resource_categories` | `<h2>` sections on `resources.html` |
| `workflows` | `*.yml` files in `.github/workflows/` (the `*_README.md` docs there are not workflows) |
| `session_digests` | `what-practitioners-think-about-*.html` (the hub page is the index, not a digest) |
| `cards_per_category` | `.resource-card` entries within each category section (see note below) |
| `sitemap_urls` | `<loc>` entries in `sitemap.xml` |
| `news_banners` | `img/news-banners/*.jpg` (the `.webp` siblings are not counted twice) |
| `faq_pages` | Published pages carrying `"@type": "FAQPage"` |
| `author_card_pages` | Published pages carrying an "About the author" card |
| `schema_types` | Distinct schema.org `@type` values across the site |

`cards_per_category` counts per section rather than deduping site-wide, so the
six section totals sum to more than `resources`, because a number of entries
are filed under two categories. Both figures are correct; they answer different questions.

## What it rewrites

**1. Managed ItemLists on `resources.html`.** Both structured-data blocks are regenerated from the page's own cards: the standalone `ItemList` enumerates every unique resource in page order, and the `CollectionPage.mainEntity` list enumerates the category sections. `numberOfItems` follows automatically because it is computed, not typed.

**2. Every other ItemList on the site.** These are not regenerated, but the invariant `numberOfItems == number of enumerated ListItems` is enforced. A count can never claim more items than the list actually contains.

**3. `<!--count:...-->` prose markers**, in both HTML pages and Markdown docs. Wrap a number in a marker and it becomes self-maintaining:

```html
Access <!--count:resources_floor-->520+<!--/count--> curated resources.
```

The comment is invisible in rendered HTML *and* in GitHub-rendered Markdown, so `README.md` can use them too - **except inside a fenced code block**, which renders its contents verbatim and will display the marker to the reader. Four counts in README.md's directory tree were doing exactly that; those are handled by `MD_PROSE_RULES` instead (see item 4). Available keys:

| Key | Renders as | Example |
|---|---|---|
| `resources` / `resources_floor` | exact / `N+` floored to ten | `485` / `480+` |
| `meetings` / `meetings_floor` | exact / `N+` floored to ten | `107` / `100+` |
| `glossary_terms` / `glossary_terms_floor` | exact / `N+` floored to ten | `317` / `310+` |
| `ctfs` / `ctfs_floor` | exact / `N+` floored to ten | `52` / `50+` |
| `vendors_floor` / `vendor_categories` | `N+` floored to ten / exact | `300+` / `32` |
| `breaches` | exact | `45` |
| `feeds` | exact | `62` |
| `conferences` | exact | `26` |
| `long_form_floor` | `N+`, floored to the nearest ten | `80+` |
| `og_images` | exact | `249` |
| `resource_categories` | exact | `6` |
| `workflows` | exact | `21` |
| `session_digests` | exact | `5` |
| `sitemap_urls` | exact | `265` |
| `news_banners` | exact | `58` |
| `faq_pages` | exact | `64` |
| `author_card_pages` | exact | `91` |
| `schema_types` / `schema_types_floor` | exact / `N+` floored to **five** | `39` / `35+` |
| `cat_ctf_floor`, `cat_labs_floor`, `cat_tools_floor`,<br>`cat_certs_floor`, `cat_ai_floor`, `cat_jobs_floor` | `N+` floored to ten, per resources.html category | `100+` |

**When you write a count into a page or a doc, wrap it in a marker.** An unmarked number is one nobody will remember to update.

**4. Count phrases where a marker cannot go** - inside `content="..."` meta/Open Graph attributes and inside JSON-LD, where an HTML comment would render as literal text or break the JSON. These are handled by a short list of deliberately narrow regexes (`HTML_PROSE_RULES`), each of which only ever matches a count already spelled as `<number>+ <phrase>`. Adding a new phrasing means adding a rule; the patterns are intentionally not generic.

**5. `llms.txt`** - plain text, so regex rather than markers. Markdown docs get the same treatment via `MD_PROSE_RULES`, for counts that sit inside a fenced code block where a marker would render as literal text - README.md's directory tree is the case that forced this. Same discipline as the HTML rules: each pattern is anchored to the words around the number, never generic.

**6. OG-card subtitles in `generate_og_images.py`.** Meetings use the exact count; resources and glossary terms use a floored `N+`. `sync_counts.py` only edits the script; `update-counts.yml` notices that edit and re-renders the three count-bearing cards (`index.html`, `resources.html`, `meetings.html`) rather than rebuilding all ~105 top-level images.

## When to run it

- After adding a resource, meeting recap, breach page, glossary term, or news feed.
- Before opening a PR that adds content, so CI doesn't have to correct you.
- Never by hand for the weekly drift - `update-counts.yml` already does that, and its commit is deliberately **not** CI-skipped so the corrected counts actually deploy.

## See also

- [`SYNC_CHROME_README.md`](SYNC_CHROME_README.md) - the other site-wide stamper, for nav and footer rather than numbers
- [DEVELOPMENT.md → Adding a new page](../DEVELOPMENT.md#adding-a-new-page)
