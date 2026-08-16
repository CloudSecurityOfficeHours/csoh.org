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
4. Recaps listed in `INELIGIBLE` are dropped here regardless of score. See
   *Ineligible recaps* below.
5. Each surviving recap gets a blurb. See *What the blurb says* below.
6. The `MAX_RECAPS` (4) most recent qualifying recaps are rendered.
7. A page with fewer than 2 qualifying recaps is skipped entirely. A block with
   one weak entry is worse than no block.

## What the blurb says

The curated card summary in `meetings.html` describes the **whole meeting**. On a
page about one topic that is frequently filler: a session that spent forty minutes
debriefing Black Hat surfaced on `conferences.html` as "Shawn greeted the group
from his vacation at Disney World." The recap *selection* was right; the display
copy was off-topic, under a heading promising the community worked the topic
through.

So the blurb is chosen in this order:

1. The card summary, if it already names the topic.
2. Otherwise a passage quoted from the recap page's own `<h3>`/`<p>` sections -
   the highest-scoring section body, trimmed to whole sentences near
   `EXCERPT_CHARS` (280), **starting at the first sentence that names the topic**.
   Anchoring on the keyword rather than the paragraph's opening is what makes
   "the copy we display mentions the topic" true rather than merely likely.
3. If no section names the topic at all, the recap is **dropped from this page**.
   It came up in scattered asides, which is not what the heading claims.

Two details worth keeping:

- Sections are ranked on their **body** text alone. A section matching only in
  its heading has no sentence to quote, and the heading is never displayed.
- Anchors are unwrapped from quoted passages. A recap's links are written for a
  page one directory down (`../glossary.html`) and are auto-inserted, so a
  paragraph pulled onto `incident-response.html` could easily contain a link
  back to `incident-response.html`. Unwrapping sidesteps both.

## Ineligible recaps

`INELIGIBLE` maps a recap date to why it may never be echoed onto a topic page.

The recap page itself stays exactly where it is. The archive is an accurate
record of what was said on the call, and the archive is not the problem: what is
wrong is auto-promoting a recap onto a technical reference page under a heading
saying the community worked *this topic* through, where a reader reads it as
CSOH's position. `docs/EDITORIAL_STANDARDS.md` §3 puts party politics off-topic
"including when they arrive indirectly through an auto-surfaced session recap."

Scoring cannot catch these. A session that spent its first ten minutes on an
election and its next hour on incident response scores high on "incident
response" precisely because the technical half was real.

Filtering happens in `pick()`, not at load time, so an ineligible recap still
counts toward the "browse all N recaps" total in the block's footer.

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

Display fields are lifted verbatim out of `meetings.html`, and quoted passages
out of the recap pages under `meetings/`. Both are already HTML-escaped. They
interpolate raw by design. Escaping them again renders entities as literal text
(`CISA&#x27;s`).
