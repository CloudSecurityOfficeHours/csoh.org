# From the Friday sessions: topic page blocks

Stamps a "From the Friday sessions" block onto topic pages, listing the most
recent meeting recaps where the community discussed that topic.

## Why

A search visitor landing on `vulnerability-management.html` finds a reference
article and leaves. What CSOH has that no reference article has is 100+ recaps of
practitioners arguing about that same topic on a live call. This block turns a
static page into evidence that a community is still working the problem, and
gives the reader a reason to show up on Friday.

It is the mirror image of [`inject_meeting_topic_links.py`](INJECT_MEETING_TOPIC_LINKS_README.md),
which links **out of** a recap **into** a topic page. This one links **out of** a
topic page **into** recaps. Running both creates the loop.

## How it works

1. Display copy (date, headline, summary) is parsed from the curated cards in
   `meetings.html`, so the blurb a reader sees matches the recap index.
2. Scoring text is the full lowercased recap body from
   `meetings-search-index.json`.
3. For each topic page in `TOPIC_KEYWORDS`, every recap is scored by counting
   keyword occurrences. A recap needs `MIN_SCORE` (2) hits to count, which keeps
   out recaps that mention a term once in passing.
4. The `MAX_RECAPS` (4) most recent qualifying recaps are rendered.
5. A page with fewer than 2 qualifying recaps is skipped entirely. A block with
   one weak entry is worse than no block.

## Usage

```bash
# Report what would change, write nothing
python3 tools/inject_session_blocks.py --dry-run

# Apply to every topic page in the map
python3 tools/inject_session_blocks.py

# Limit to specific pages
python3 tools/inject_session_blocks.py --pages iam.html kubernetes.html
```

Idempotent. The block is delimited by `<!-- SESSION_BLOCK_START -->` and
`<!-- SESSION_BLOCK_END -->` and replaced whole on every run, so re-running after
new meetings land just refreshes the list. Placement is before the
`<aside class="author-card">` if the page has one, else before `</main>`.

## When to run

- After adding meeting recaps (the lists are recency-ordered, so they go stale).
- After adding a new topic page, once you add it to `TOPIC_KEYWORDS`.

## Tuning

Edit `TOPIC_KEYWORDS`. Two failure modes to watch:

- **Keywords too specific: the page gets skipped.** The map was seeded from
  `inject_meeting_topic_links.py`, whose phrases are tuned for prose linking and
  are often narrower than how people actually talk on a call. "azure sentinel"
  and "okta" match zero recaps; "azure" and "entra" match plenty. Check real
  frequency before assuming a topic has no coverage.
- **Keywords too generic: junk matches.** Avoid bare tokens that appear in nearly
  every session, and watch for substring collisions ("wiz" matches "wizard").

Pages currently skipped for thin coverage are listed in the run output. That is
working as intended, not a bug to fix by loosening keywords until something
matches.

## Note on escaping

Display fields are lifted verbatim out of `meetings.html`, where they are already
HTML-escaped. They interpolate raw by design. Escaping them again renders
entities as literal text (`CISA&#x27;s`).
