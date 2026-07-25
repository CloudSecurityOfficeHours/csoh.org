# 🗓️ Meeting OG Card Generator

Generates per-meeting 1200×630 Open Graph cards for every `meetings/YYYY-MM-DD.html` and rewrites each page's `og:image` + `twitter:image` meta tags to point at its own card.

Sister tool to `generate_og_images.py` - same template (`tools/og/template.html`), same Playwright machinery - but driven by the meeting files on disk instead of a hand-curated `PAGES` list.

## Why

Without this, every meeting recap falls back to the generic `banner.png` for social shares (LinkedIn, Slack, Twitter, AI bots). With it, each meeting gets a date-stamped card with its topic teasers - much more clickable.

## How it works

For each `meetings/YYYY-MM-DD.html`:

1. Parse the date (from the filename).
2. Extract the topic summary from the `<h2><time>…</time> - …</h2>` line (falls back to the hero subhead).
3. HTML-decode the result so apostrophes and other entities render correctly.
4. Render the OG template with `title` = formatted date (e.g. "May 8, 2026"), `subtitle` = topic summary, `badge` = "Meeting Recap".
5. Save the JPG to `img/og/meetings/YYYY-MM-DD.jpg`.
6. Rewrite the meeting page's `og:image` and `twitter:image` meta tags to the absolute URL of the new card.

## Usage

```bash
# Generate cards for all 94 meetings
python3 tools/generate_meeting_og_images.py

# Generate only specific meetings
python3 tools/generate_meeting_og_images.py --pages meetings/2026-05-08.html

# Regenerate JPGs but don't touch HTML meta tags
python3 tools/generate_meeting_og_images.py --skip-html
```

Requires Playwright + Chromium (`pip install playwright && playwright install chromium`). Idempotent - re-running on a meeting whose card already points at the per-meeting JPG produces no HTML diff.

## After adding a new meeting

`tools/add_meeting.py` creates `meetings/YYYY-MM-DD.html` with a `banner.png` OG fallback. To swap in a proper card:

```bash
python3 tools/generate_meeting_og_images.py --pages meetings/<new-date>.html
```

Then commit the new JPG + HTML meta-tag update together.
