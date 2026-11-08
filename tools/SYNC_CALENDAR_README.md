# Session Calendar Automation

## How does the calendar page stay current?

The [Calendar page](https://csoh.org/calendar.html) is rendered **automatically from the CSOH Google Calendar**. Nobody edits the page; the organisers edit the calendar in Google, and the site catches up within six hours. In plain English:

1. **GitHub Actions** runs `tools/sync_calendar.py` on a schedule ([`update-calendar.yml`](../.github/workflows/update-calendar.yml), every 6 hours) and whenever a maintainer presses "Run workflow".
2. The script fetches the calendar's **public iCalendar feed**. iCalendar (`.ics`) is the plain-text format every calendar app speaks; Google publishes one for any calendar marked public, and it contains the weekly series as one entry plus a note for any week that was moved, cancelled or edited.
3. The script **expands the series** into the next twelve occurrences, up to six months out, applying the skipped weeks, the moved weeks and the cancellations the same way a calendar app would. It does this with the Python standard library alone, so the CI job installs nothing.
4. It **scrubs anything that must not be published**. The Zoom link is deliberately behind the mailing list, so a join URL on any meeting host (Zoom, Meet, Teams, Webex and the rest) becomes "(Zoom link via the CSOH mailing list)", lines that look like dial-in details ("Meeting ID", "Passcode") are dropped, and email addresses outside csoh.org are removed. Other links are kept and made clickable.
5. It writes the result as ordinary HTML cards between the two marker comments in `calendar.html`, grouped by month, with times in Pacific first and Eastern alongside. Nothing outside the markers is touched: the page's title, description and prose are hand-written.
6. If the page changed, the workflow **opens a pull request**. If the only file in the diff is `calendar.html`, it is approved and merged automatically; anything else waits for a human.
7. The merge is a push to `main`, which runs the normal deploy to the three origins.

The page is static on purpose. A Google Calendar embed is an iframe from a third party, which the site's Content Security Policy forbids, and it would send every visitor to Google. Rendering in CI gives readers the same information as a page of the site, with no script and no tracker. Readers who want the live calendar in their own app use the subscribe links on the page, which point at the same feed.

## Running it by hand

```sh
python3 tools/sync_calendar.py --self-test     # prove the parser and the scrubber
python3 tools/sync_calendar.py                 # fetch the live feed, rewrite calendar.html if it moved
python3 tools/sync_calendar.py --check         # exit 1 if calendar.html is stale, write nothing
python3 tools/sync_calendar.py --ics feed.ics  # render from a saved feed instead of the network
python3 tools/sync_calendar.py --now 2026-12-01T09:00:00-08:00   # reproduce a run from another instant
```

`--check` is deliberately not a CI gate. The page goes stale every Friday on its own, with no commit to blame, so a gate on it would fail weekly for a reason nobody caused. Freshness comes from the scheduled workflow instead, the same arrangement as `sync_next_session.py`.

## What the self-test proves

The self-test is run in CI before every render and refuses a clean verdict unless every planted case is handled:

- a weekly series with one week removed by `EXDATE`;
- an instance moved to another day (`RECURRENCE-ID`), which renders once, at the new time, tagged "Rescheduled";
- an instance edited in place at the same time, which keeps its "Weekly" tag;
- a cancelled instance, which does not render;
- a monthly "first Tuesday" series bounded by `COUNT`;
- an all-day event, anchored to the date rather than to midnight Eastern;
- a one-off event whose description carries a Zoom join URL, a meeting ID, a passcode and an outside email address, none of which reach the page;
- stamping that is a no-op on the second run, a planted stale card that `--check` reports, and a page without markers that is refused.

## Changing what is rendered

| To change | Edit |
| --- | --- |
| Which calendar is read | `CALENDAR_ID` in `tools/sync_calendar.py`, and the subscribe links on `calendar.html` |
| How many occurrences, how far ahead | `LIMIT` and `HORIZON_DAYS` |
| The timezones shown | `SITE_TZ` (first) and `SECOND_TZ` |
| Which hosts count as private join links | `PRIVATE_HOSTS` and `PRIVATE_LINE_RE` |
| How often it runs | the `cron` line in `update-calendar.yml` |

The card markup reuses the site's existing `resource-grid`, `resource-card`, `article-date` and `tag` classes, so there is no calendar-specific CSS to keep in step with the dark theme.
