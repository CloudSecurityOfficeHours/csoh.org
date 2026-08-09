#!/usr/bin/env python3
"""Flag stale podcasts / blogs / newsletters on cloud-security-reading-list.html.

For each external URL inside the newsletters, blogs, podcasts, and youtube
sections we:
  1. Try to discover the site's RSS/Atom feed (via <link rel="alternate"> in
     the head, then a short list of common feed paths as fallback).
  2. Fetch the feed and read the newest entry's publish date.
  3. Compare against --max-age-days (default 180). Anything older is flagged.

The page is hand-curated and opinionated; we deliberately do NOT touch its
content. The output is a markdown report meant to be pasted into a tracking
issue so a human can decide whether to drop, replace, or keep each entry.

Usage:
    python3 tools/check_reading_list_staleness.py
    python3 tools/check_reading_list_staleness.py --max-age-days 365
    python3 tools/check_reading_list_staleness.py --output report.md
    python3 tools/check_reading_list_staleness.py --input some-page.html
    python3 tools/check_reading_list_staleness.py --exit-on-stale   # CI gate

Exit code: 0 normally; 1 when --exit-on-stale is set and any feed is stale;
2 if the input file cannot be read.
"""

import argparse
import datetime as dt
import re
import sys
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

READING_LIST_PATH = "cloud-security-reading-list.html"

# Only these sections contain things that have feeds. The books, people, and
# papers sections are by nature one-shot links - no feed to check.
FEED_SECTIONS = ("newsletters", "blogs", "podcasts", "youtube")

# Pretend to be a real browser. A lot of CDNs (Cloudflare in particular) 403
# anything that smells like a script.
USER_AGENT = (
    "Mozilla/5.0 (compatible; csoh-staleness-check/1.0; "
    "+https://csoh.org/cloud-security-reading-list.html)"
)

# Tried in order when the page's <head> doesn't advertise a feed.
FALLBACK_FEED_PATHS = (
    "/feed/", "/feed", "/feed.xml",
    "/rss/", "/rss", "/rss.xml",
    "/atom.xml", "/index.xml",
)

# Per-URL feed overrides. Keyed by the EXACT href as it appears in the reading
# list, valued by the feed to read instead. Two cases this solves, both of which
# auto-discovery gets wrong and re-flags every month:
#   1. Feed lives at a non-standard path the fallback probe doesn't guess
#      (wiz.io serves /feed/rss.xml, not /feed/).
#   2. The page itself is bot-protected (Cloudflare/CDN 403s our User-Agent) so
#      we never even reach feed discovery - but the feed endpoint is open.
# When a URL is overridden we skip the page fetch entirely and read the feed
# directly. Worst case (the feed 403s too) it shows as "feed unreachable" with
# this exact URL - strictly more useful than a bare "no feed discovered".
# Verify a candidate returns parseable, dated entries before adding it here.
FEED_OVERRIDES = {
    "https://www.wiz.io/blog": "https://www.wiz.io/feed/rss.xml",
    "https://awsteele.com/": "https://awsteele.com/feed.xml",
    "https://securitylabs.datadoghq.com/": "https://securitylabs.datadoghq.com/rss/feed.xml",
    # Resilient Cyber moved off resilientcyber.substack.com to this custom
    # domain (still Substack-hosted) in mid-2026; the old host 301s here.
    "https://www.resilientcyber.io/": "https://www.resilientcyber.io/feed",
    # GCP threat-intel blog feed lives on the cloudblog.withgoogle.com host; the
    # cloud.google.com/blog/... path returns HTML, not a feed.
    "https://cloud.google.com/blog/topics/threat-intelligence": "https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/",
    # cisoseries.com Cloudflare-403s every non-browser client; read the flagship
    # CISO Series Podcast from its (open) Libsyn host feed instead.
    "https://cisoseries.com/": "https://rss.libsyn.com/shows/24425/destinations/37324.xml",
    # cloudsecuritypodcast.tv is a JS-rendered SPA with no feed link in its HTML;
    # this is its audio feed (anchor.fm, links back to the site, author TechRiot.io).
    "https://www.cloudsecuritypodcast.tv/": "https://anchor.fm/s/10fb9928/podcast/rss",
    # YouTube intermittently serves a consent/redirect wall to non-browser
    # clients, so the @handle page fetch sporadically yields no <link rel=alternate>
    # ("no feed discovered"). Pin the channel-id Atom feed directly. Every
    # @handle on the reading list is pinned, so none of them can report
    # "no feed discovered" again. Re-derive an id from the handle page with:
    #   curl -s -A '<browser UA>' https://www.youtube.com/@<handle> \
    #     | grep -o '"externalId":"UC[A-Za-z0-9_-]\{22\}"'
    # The feed endpoint rate-limits rapid repeat requests with a 404, so verify
    # one id at a time rather than in a tight loop.
    "https://www.youtube.com/@AWSEventsChannel": "https://www.youtube.com/feeds/videos.xml?channel_id=UCdoadna9HFHsxXWhafhNvKw",
    "https://www.youtube.com/@BlackHatOfficialYT": "https://www.youtube.com/feeds/videos.xml?channel_id=UCJ6q9Ie29ajGqKApbLqfBOg",
    "https://www.youtube.com/@cncf": "https://www.youtube.com/feeds/videos.xml?channel_id=UCvqbFHwN-nwalWPjPUKpvTA",
    "https://www.youtube.com/@DEFCONConference": "https://www.youtube.com/feeds/videos.xml?channel_id=UC6Om9kAkl32dWlDSNlDS9Iw",
    "https://www.youtube.com/@fwdcloudsec": "https://www.youtube.com/feeds/videos.xml?channel_id=UCjfghTrOeq5Qu0WdKjxBpBA",
    "https://www.youtube.com/@SANSCloudSecurity": "https://www.youtube.com/feeds/videos.xml?channel_id=UCMaclFQGtT064H9KNsfomGA",
}

REQUEST_TIMEOUT = 20


def fetch(url: str, *, accept: str = "*/*") -> Tuple[Optional[bytes], Optional[str]]:
    """GET a URL. Returns (body, error). Body is None on failure."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read(), None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"network: {e.reason}"
    except Exception as e:                              # noqa: BLE001 - diagnostic only
        return None, f"{type(e).__name__}: {e}"


def extract_section_urls(html_text: str) -> List[Tuple[str, str]]:
    """Return [(section_id, url), ...] for every external link in FEED_SECTIONS.

    Deduplicated per section, preserving the order of first appearance.
    """
    seen: set = set()
    out: List[Tuple[str, str]] = []
    for section in FEED_SECTIONS:
        m = re.search(
            rf'<section id="{re.escape(section)}">(.*?)</section>',
            html_text, re.DOTALL,
        )
        if not m:
            continue
        for url in re.findall(r'href="(https?://[^"]+)"', m.group(1)):
            key = (section, url)
            if key in seen:
                continue
            seen.add(key)
            out.append(key)
    return out


def discover_feed_url(page_url: str, html_text: str) -> Optional[str]:
    """Look for a <link rel="alternate" type="application/(rss|atom)+xml">."""
    # Lower-cased match against the head only - body links to feeds (e.g. a
    # "Subscribe via RSS" button) are not always the canonical feed.
    head_match = re.search(r"<head\b[^>]*>(.*?)</head>", html_text, re.DOTALL | re.IGNORECASE)
    head = head_match.group(1) if head_match else html_text[:8000]

    for link_tag in re.findall(r"<link\b[^>]*>", head, re.IGNORECASE):
        type_match = re.search(r'type=["\']([^"\']+)["\']', link_tag, re.IGNORECASE)
        rel_match = re.search(r'rel=["\']([^"\']+)["\']', link_tag, re.IGNORECASE)
        if not (type_match and rel_match):
            continue
        if "alternate" not in rel_match.group(1).lower():
            continue
        feed_type = type_match.group(1).lower()
        if "rss" not in feed_type and "atom" not in feed_type:
            continue
        href_match = re.search(r'href=["\']([^"\']+)["\']', link_tag, re.IGNORECASE)
        if not href_match:
            continue
        return urljoin(page_url, href_match.group(1))
    return None


def try_fallback_feed(page_url: str) -> Optional[str]:
    """Probe common feed paths.

    Tries each path relative to the URL's own directory FIRST, then falls
    back to the site root. Catches sites like /blog/feed/ on a multi-section
    domain where the root-level feed is wrong or missing.
    """
    parsed = urlparse(page_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    # Walk up the URL path: /blog/section/  -> ["/blog/section/", "/blog/", "/"]
    path = parsed.path or "/"
    if not path.endswith("/"):
        path = path.rsplit("/", 1)[0] + "/"
    bases: List[str] = []
    while path and path != "/":
        bases.append(root + path)
        path = path[:-1].rsplit("/", 1)[0] + "/"
    bases.append(root)                                  # site root, last

    seen: set = set()
    for base in bases:
        for suffix in FALLBACK_FEED_PATHS:
            candidate = base.rstrip("/") + suffix
            if candidate in seen:
                continue
            seen.add(candidate)
            body, err = fetch(candidate, accept="application/rss+xml, application/atom+xml")
            if err or not body:
                continue
            # Cheap sanity check - must look like XML and contain a feed root.
            head = body[:512].lower()
            if b"<rss" in head or b"<feed" in head or b"<rdf" in head:
                return candidate
    return None


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def parse_feed_latest(xml_bytes: bytes) -> Optional[dt.datetime]:
    """Return the newest entry's publish date, or None if we can't parse one."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return None

    date_strings: List[str] = []

    # RSS 2.0 channel/item/pubDate
    for item in root.iter():
        if _strip_ns(item.tag) not in ("item", "entry"):
            continue
        for child in item:
            tag = _strip_ns(child.tag)
            if tag in ("pubDate", "published", "updated", "date") and child.text:
                date_strings.append(child.text.strip())
                break

    dates: List[dt.datetime] = []
    for s in date_strings:
        parsed = _parse_date(s)
        if parsed:
            dates.append(parsed)

    if not dates:
        return None
    return max(dates)


def _parse_date(value: str) -> Optional[dt.datetime]:
    """Parse RFC 822 (RSS) and ISO 8601 / RFC 3339 (Atom) date strings."""
    # RFC 822 - what RSS pubDate uses.
    try:
        d = parsedate_to_datetime(value)
        if d is not None:
            return _to_utc(d)
    except (TypeError, ValueError):
        pass
    # ISO 8601 - what Atom <updated>/<published> use. Python's fromisoformat
    # accepts the trailing 'Z' only on 3.11+, which matches our target.
    try:
        return _to_utc(dt.datetime.fromisoformat(value.replace("Z", "+00:00")))
    except ValueError:
        return None


def _to_utc(d: dt.datetime) -> dt.datetime:
    if d.tzinfo is None:
        return d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def check_url(section: str, url: str) -> Dict[str, object]:
    """Return a dict describing the staleness status of one URL."""
    result: Dict[str, object] = {"section": section, "url": url}

    # A known feed for this URL? Skip the page fetch (which may be bot-blocked)
    # and the discovery guesswork - read the feed directly.
    override = FEED_OVERRIDES.get(url)
    if override:
        result["feed_url"] = override
        feed_body, err = fetch(override, accept="application/rss+xml, application/atom+xml")
        if err or not feed_body:
            result["status"] = "feed_unreachable"
            result["detail"] = err or "empty response"
            return result
        latest = parse_feed_latest(feed_body)
        if latest is None:
            result["status"] = "feed_unparseable"
            return result
        result["latest"] = latest
        return result

    body, err = fetch(url, accept="text/html,application/xhtml+xml")
    if err or not body:
        result["status"] = "page_unreachable"
        result["detail"] = err or "empty response"
        return result

    try:
        html_text = body.decode("utf-8", errors="replace")
    except Exception as e:                              # noqa: BLE001
        result["status"] = "page_unreachable"
        result["detail"] = f"decode: {e}"
        return result

    feed_url = discover_feed_url(url, html_text) or try_fallback_feed(url)
    if not feed_url:
        result["status"] = "no_feed"
        return result
    result["feed_url"] = feed_url

    feed_body, err = fetch(feed_url, accept="application/rss+xml, application/atom+xml")
    if err or not feed_body:
        result["status"] = "feed_unreachable"
        result["detail"] = err or "empty response"
        return result

    latest = parse_feed_latest(feed_body)
    if latest is None:
        result["status"] = "feed_unparseable"
        return result

    result["latest"] = latest
    return result


def format_report(results: List[Dict[str, object]], max_age_days: int) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=max_age_days)

    stale: List[Dict[str, object]] = []
    no_feed: List[Dict[str, object]] = []
    unreachable: List[Dict[str, object]] = []
    healthy: List[Dict[str, object]] = []

    for r in results:
        status = r.get("status")
        if status in ("page_unreachable", "feed_unreachable", "feed_unparseable"):
            unreachable.append(r)
        elif status == "no_feed":
            no_feed.append(r)
        else:
            latest = r["latest"]                        # type: ignore[index]
            assert isinstance(latest, dt.datetime)
            r["age_days"] = (now - latest).days
            (stale if latest < cutoff else healthy).append(r)

    lines: List[str] = []
    lines.append(f"_Reading list staleness check - generated {now.strftime('%Y-%m-%d')} UTC_")
    lines.append("")
    lines.append(
        f"Threshold: any feed whose newest entry is older than **{max_age_days} days** is flagged. "
        "This page is hand-curated, so nothing is auto-edited - use this report to decide what to "
        "refresh, replace, or drop."
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Status | Count |")
    lines.append("| --- | ---: |")
    lines.append(f"| Stale (>{max_age_days}d) | {len(stale)} |")
    lines.append(f"| No feed discovered | {len(no_feed)} |")
    lines.append(f"| Unreachable / unparseable | {len(unreachable)} |")
    lines.append(f"| Healthy | {len(healthy)} |")
    lines.append("")

    def render_group(title: str, items: List[Dict[str, object]], *, show_age: bool = False) -> None:
        if not items:
            return
        lines.append(f"## {title}")
        lines.append("")
        for r in sorted(items, key=lambda x: (x["section"], x["url"])):
            url = r["url"]
            section = r["section"]
            extras = []
            if show_age and "age_days" in r:
                age = r["age_days"]
                latest = r["latest"].strftime("%Y-%m-%d")  # type: ignore[union-attr]
                extras.append(f"last post {latest} ({age}d ago)")
            if "feed_url" in r:
                extras.append(f"[feed]({r['feed_url']})")
            if "detail" in r:
                extras.append(f"_{r['detail']}_")
            suffix = f" - {' · '.join(extras)}" if extras else ""
            lines.append(f"- **{section}** · <{url}>{suffix}")
        lines.append("")

    render_group(f"Stale feeds (newest entry > {max_age_days}d old)", stale, show_age=True)
    render_group("No feed discovered", no_feed)
    render_group("Unreachable or unparseable", unreachable)
    render_group("Healthy (for completeness)", healthy, show_age=True)

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-age-days", type=int, default=180,
                        help="flag feeds whose newest entry is older than this (default: 180)")
    parser.add_argument("--input", default=READING_LIST_PATH,
                        help=f"path to the reading list HTML (default: {READING_LIST_PATH})")
    parser.add_argument("--output", default=None,
                        help="write the report to this file (default: stdout)")
    parser.add_argument("--exit-on-stale", action="store_true",
                        help="exit 1 if any feed is stale (useful for CI gating)")
    args = parser.parse_args()

    try:
        with open(args.input, encoding="utf-8") as f:
            html_text = f.read()
    except OSError as e:
        print(f"error: cannot read {args.input}: {e}", file=sys.stderr)
        return 2

    pairs = extract_section_urls(html_text)
    print(f"checking {len(pairs)} URLs across {len(FEED_SECTIONS)} sections...", file=sys.stderr)

    results: List[Dict[str, object]] = []
    for section, url in pairs:
        print(f"  [{section}] {url}", file=sys.stderr)
        results.append(check_url(section, url))

    report = format_report(results, args.max_age_days)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"wrote report to {args.output}", file=sys.stderr)
    else:
        print(report)

    if args.exit_on_stale:
        stale_count = sum(
            1 for r in results
            if isinstance(r.get("latest"), dt.datetime)
            and (dt.datetime.now(dt.timezone.utc) - r["latest"]).days > args.max_age_days
        )
        if stale_count:
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
