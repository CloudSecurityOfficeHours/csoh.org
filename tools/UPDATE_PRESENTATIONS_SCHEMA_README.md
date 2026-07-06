# Presentations VideoObject Schema Regenerator

Regenerates the `VideoObject` JSON-LD block in `presentations.html` from the YouTube cards already on the page. Gives search engines structured data for each talk (name, description, thumbnail, upload date, publisher) so they can surface video-rich results.

## Quick Start

```bash
python3 tools/update_presentations_schema.py
```

Prints how many `VideoObject` entries were emitted. Idempotent - re-runs report "already up to date".

## How It Works

1. Parses each `<a href="https://www.youtube.com/watch?v=..." ... class="card-link">` card in `presentations.html`. The anchor must carry `class="card-link"` - a bare YouTube link without it is ignored.
2. Extracts the video ID, title (`<h3>`), description (`<p>`), and date prefix (e.g. `"October 10, 2025: ..."`) from each card.
3. Emits a `<script type="application/ld+json">` block with `@graph` containing one `VideoObject` per video.
4. Injects the block just before `</head>`, replacing any prior block with the same marker comment:

   ```html
   <!-- Structured Data - Presentations (VideoObject) -->
   ```

## When To Run

- **Automatically**: `.github/workflows/site-update-deploy.yml` runs it before every deploy, so adding a new presentation card (and pushing the HTML) regenerates the schema without a manual step.
- **Manually**: After editing `presentations.html` locally, to preview the schema change.

## When You Don't Need To Run It

Non-YouTube cards (e.g., the "Community Contributions" section) are ignored. Only cards matching `https://www.youtube.com/watch?v=<id>` contribute entries.

## Requirements

- Python 3.9+ (standard library only)
- Run from any directory - the script resolves `presentations.html` relative to the repo root
