# Reading List Staleness Check

Monthly health check on the third-party sources we recommend in [cloud-security-reading-list.html](../cloud-security-reading-list.html). For every URL in the newsletters, blogs, podcasts, and YouTube sections, the script discovers the site's RSS or Atom feed and reports the date of the newest entry. Anything older than the threshold (default 180 days) is flagged.

Stdlib-only, no LLM, no API keys. Pairs with `check-broken-links.yml` (which already runs lychee against every link on the site) - that workflow catches dead URLs; this one catches *quiet* sources that are still reachable but no longer publishing.

## Why

The reading list is hand-curated and opinionated - its whole pitch is "only what we'd actually re-recommend right now." Full content automation (auto-adding "trending" blogs or removing inactive ones) would defeat that. But a podcast going dark, or a newsletter author moving on, is information a human curator *wants* surfaced. This script does that, and stops there. **It never edits the reading list.**

## What it checks

Per URL inside `<section id="newsletters|blogs|podcasts|youtube">`:

1. **Fetch the page** with a browser-shaped User-Agent (a lot of CDNs 403 anything scriptier).
2. **Discover the feed**:
   - First, look in `<head>` for `<link rel="alternate" type="application/rss+xml|atom+xml">`. This catches the common case including YouTube channel pages (where the head advertises `/feeds/videos.xml?channel_id=…`).
   - If absent, probe common feed paths (`/feed/`, `/rss.xml`, `/atom.xml`, `/index.xml`, etc.) walking from the URL's own directory up to the site root. Each candidate must respond with content that starts with `<rss`, `<feed`, or `<rdf` to count.
3. **Parse the feed** with `xml.etree.ElementTree`, then take the newest `<pubDate>` / `<updated>` / `<published>` across all entries. Dates are parsed via `email.utils.parsedate_to_datetime` (RFC 822, what RSS uses) and `datetime.fromisoformat` (ISO 8601, what Atom uses) and normalized to UTC.
4. **Classify** the URL into one of:
   - **Stale** - feed parsed; newest entry older than `--max-age-days`
   - **No feed** - page loaded but no feed could be discovered
   - **Unreachable** - page or feed returned an error (HTTP 4xx/5xx, DNS, decode failure)
   - **Healthy** - feed parsed and newest entry within the threshold

The books, people, and papers sections are intentionally excluded - they're one-shot links with no feed to check.

## Usage

```bash
# Default: 180-day threshold, write report to stdout
python3 tools/check_reading_list_staleness.py

# Tighter threshold
python3 tools/check_reading_list_staleness.py --max-age-days 90

# Write to a file (what the workflow does)
python3 tools/check_reading_list_staleness.py --output staleness.md

# Gate CI on staleness (exit 1 if anything is stale)
python3 tools/check_reading_list_staleness.py --exit-on-stale
```

Exit codes:

- `0` - script ran successfully
- `1` - only with `--exit-on-stale`: at least one feed is stale
- `2` - couldn't read the reading list HTML

## When to run

- **Locally**: any time you're considering an edit to the reading list, to see which entries are due for a refresh.
- **Automated**: `.github/workflows/check-reading-list-staleness.yml` runs it on the **1st of each month at 07:00 UTC**, plus on demand. The workflow uploads the markdown report as an artifact and opens (or refreshes) a sticky GitHub issue labeled `reading-list-staleness` with the contents. Close the issue when you've made your decisions - the next monthly run will reopen it if anything is still flagged.

## Known limitations

- **Bot-protected sites** (Cloudflare 403, Datadog labs, etc.) come back as "unreachable" no matter what User-Agent the script uses. A headless browser would fix it but is overkill for a monthly report. If the site's *feed* endpoint is open even when the page isn't, add it to `FEED_OVERRIDES` (below) - the override reads the feed directly and skips the blocked page fetch.
- **Sites with non-standard feed URLs** that don't advertise the feed in `<head>` (`wiz.io/blog` → `/feed/rss.xml`, for example) come back as "no feed discovered." The fix for a recurring offender is `FEED_OVERRIDES` - a small per-URL `{page: feed}` map at the top of the script - not more discovery heuristics. Keys must match the href exactly as it appears in the reading list; verify the feed returns parseable, dated entries before adding it. Currently overridden: `wiz.io/blog`, `awsteele.com`, `securitylabs.datadoghq.com`, `resilientcyber.substack.com`.
- **YouTube** feeds are limited to the most recent 15 videos - fine for staleness, but you can't infer overall posting volume from them.
- The default 180-day threshold is generous on purpose. Annual conference channels (fwd:cloudsec, DEF CON) will trip it once a year between events; that's a feature, not a bug.

## Requirements

- Python 3.11+ (uses `datetime.fromisoformat` accepting trailing `Z`)
- Standard library only
- Run from the repo root.
