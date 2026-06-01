# Backfill Zoom AI Companion Summaries

Bulk-imports CSOH meeting recaps into [`meetings.html`](../meetings.html) from Zoom's AI Companion meeting summaries. Complementary to [`fetch_zoom_transcript.py`](fetch_zoom_transcript.py) - that tool pulls VTT transcripts one at a time; this one pulls every AI-generated summary on the account in a single batch.

## When you'd use each

| Tool | Source | Content | Good for |
|---|---|---|---|
| `fetch_zoom_transcript.py` | Cloud recording VTT | Raw transcript (speakers + timestamps) | A specific meeting; when you want a rich recap summarized from the verbatim transcript |
| `backfill_zoom_summaries.py` | AI Companion `summary_content` | Zoom's own recap (overview + topic sections) | Bulk backfill across the full history, no per-meeting summarization step |

## Setup

Requires all the usual Zoom Server-to-Server OAuth credentials (`ZOOM_ACCOUNT_ID`, `ZOOM_CLIENT_ID`, `ZOOM_CLIENT_SECRET` in `.env`) **plus** the summary-specific scopes added to the app:

- `meeting:read:list_summaries:admin`
- `meeting:read:list_meetings:admin`
- `meeting:read:summary:admin`

See [FETCH_ZOOM_TRANSCRIPT_README.md](FETCH_ZOOM_TRANSCRIPT_README.md) for the full one-time Zoom app setup.

## Usage

```bash
# Dry run - list candidate dates + inferred tags, make no changes
python3 tools/backfill_zoom_summaries.py --dry-run

# Full backfill (skips dates already on the page)
python3 tools/backfill_zoom_summaries.py

# Just the newest N for a quick sample
python3 tools/backfill_zoom_summaries.py --limit 5

# Also replace dates already on the page (clobbers hand-authored content)
python3 tools/backfill_zoom_summaries.py --replace-existing
```

### Flags

- `--dry-run` - print the plan, make no changes.
- `--limit N` - process at most N dates (useful to preview quality on a small sample).
- `--replace-existing` - regenerate entries that are already on the page. Off by default to preserve hand-authored content.
- `--months-back N` - how far back to scan (default 60).
- `--target-hour H` / `--hour-slack MINS` - Pacific time target for the Friday filter (defaults: 7:00 PT, 90-minute slack).
- `--env-file PATH` - use a non-default `.env`.

## How it selects the summary per date

Zoom's AI Companion often produces multiple `summary_content` records for one Friday - if the host stopped and restarted the recording, each instance has its own summary. The script picks the **longest-duration** candidate per date. If that one has empty content (can happen for very short fragments), it falls back to the next-longest.

## What it does to `meetings.html`

For each selected date, the script:

1. Fetches the full summary content from Zoom (`summary_overview`, `summary_details`, formatted `summary_content` markdown).
2. Infers 1-4 topical tags by keyword-matching the overview + topic headings against the existing tag vocabulary (AI, Supply Chain, Vulnerabilities, Conferences, Governance, Guest Speaker, Community, etc.).
3. Prepends `# CSOH YYYY-MM-DD` so `add_meeting.py` can parse it.
4. Runs `add_meeting.py --tag …` for each inferred tag.
5. Each new meeting lands in the list, the table of contents picks it up, and the filter-bar month/tag facets auto-populate on next page load.

## Caveats

- **AI transcription quirks.** Summaries are generated from Zoom's transcription, which occasionally mis-hears names (`Axi` → `XZ`, `Cisa` → `CISA`, `Psi Ops` → `Psy Ops`, etc.). Spot-check a few entries after a big backfill and apply targeted fixes with `sed` or an editor pass.
- **Tag inference is rule-based.** Simple keyword matching, not an LLM. Some meetings will land with only 1-2 tags where a richer set would fit. Edit by hand after the fact, or extend `TAG_RULES` in the script.
- **Date selection assumes ~7am PT Friday.** Meetings scheduled elsewhere (different time, different day, one-off sessions) won't match the filter.
- **Scope of published content.** The script only touches `meetings.html` articles + TOC. It doesn't commit, doesn't push. Review with `git diff` and commit yourself.

## Requirements

- Python 3.9+ (standard library only - `zoneinfo` used for US/Pacific conversion)
- An active Zoom Server-to-Server OAuth app with the three summary scopes listed above
