# Presentations VideoObject Schema Regenerator

Regenerates the `VideoObject` JSON-LD block in `presentations.html` from the YouTube cards already on the page. Gives search engines structured data for each talk (name, description, thumbnail, upload date, publisher) so they can surface video-rich results.

## Quick Start

```bash
python3 tools/update_presentations_schema.py
```

Prints how many `VideoObject` entries were emitted. Idempotent - re-runs report "already up to date". Exits non-zero, writing nothing, if any YouTube card on the page fails to parse.

## How It Works

1. Finds each `.resource-card` block in `presentations.html`, balancing the `.resource-tags` and `.deck-frame` divs nested inside it, and reads the video ID, title (`<h3>`), description (`<p>`), and date prefix (e.g. `"October 10, 2025: ..."`) out of that one block. The card's link must carry `class="card-link"` - a bare YouTube link without it is ignored.
2. Handles all three card shapes on the page, because the href sits somewhere different in each:

   | Shape | Where the card link is | Where `<h3>`/`<p>` are |
   |---|---|---|
   | `.resource-card` | the anchor **wraps** the card | inside it |
   | `.resource-card--with-deck` | the anchor is **inside** the card, around the thumbnail only | siblings of that anchor |
   | `.resource-card--deck` | no video, slides only | n/a - skipped |

   Anchoring on the anchor instead of the card is what used to drop the `--with-deck` cards. See "Failure Modes" below.
3. Emits a `<script type="application/ld+json">` block with `@graph` containing one `VideoObject` per video.
4. Injects the block just before `</head>`, replacing any prior block with the same marker comment:

   ```html
   <!-- Structured Data - Presentations (VideoObject) -->
   ```

## When To Run

- **Automatically**: both `.github/workflows/deploy.yml` and `.github/workflows/site-update-deploy.yml` run it, so adding a new presentation card (and pushing the HTML) regenerates the schema without a manual step. Note that a parse failure therefore **fails the deploy** - see below.
- **Manually**: After editing `presentations.html` locally, to preview the schema change.

## When You Don't Need To Run It

Non-YouTube cards (e.g., the "Community Contributions" section) are ignored. Only cards matching `https://www.youtube.com/watch?v=<id>` contribute entries.

## Requirements

- Python 3.10+ (standard library only; the script uses `X | None` type syntax)
- Run from any directory - the script resolves `presentations.html` relative to the repo root

## Failure Modes

The script refuses to emit a schema that is quietly smaller than the page.

Two `.resource-card--with-deck` cards (`_xaKpSgSvzg`, `Qc5VKP7wamI`) were missing from the JSON-LD for as long as that card shape existed. The old parser matched the card-link anchor and then looked for `<h3>`/`<p>` *inside* it, which only holds for the plain shape; on a deck card those tags are siblings of the anchor, so the lookup failed and a bare `continue` dropped the card. Nothing warned, the run reported success, and the shortfall was invisible unless you counted.

So `main()` now cross-checks two independently derived lists before writing anything:

- the video IDs it parsed out of the card blocks, and
- every `class="card-link"` YouTube ID on the page, swept without reference to card structure.

They must match exactly, in order. A mismatch names the missing IDs and exits 1:

```
presentations schema: page has 13 YouTube card link(s) but 12 parsed into VideoObjects
  missing:    Qc5VKP7wamI
```

A card carrying a video but no `<h3>` or `<p>` raises rather than being skipped.

To check the guard still works, break one card (drop its `<h3>`, or rename its `resource-card` class) and confirm the run fails; restore with `git checkout -- presentations.html`, not a copy, so a run that dies partway cannot leave the planted break behind.
