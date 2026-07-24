#!/usr/bin/env python3
"""Generate recaps.xml, an RSS 2.0 feed of CSOH meeting recaps.

feed.xml carries curated external news. This is the other half: the community's
own record of what it discussed each Friday. Members who want the recap without
checking the site (or who want it piped into Slack or Teams) subscribe here.

Unlike the news feed, every item points at a page on csoh.org, so the guid is a
stable permalink and the pubDate is the meeting date rather than a scrape time.

Usage:
    python3 tools/generate_recaps_rss.py
"""

import datetime as dt
import html
import re
import sys
from pathlib import Path
from xml.dom.minidom import parseString
from xml.etree.ElementTree import Element, SubElement, tostring

SITE = "https://csoh.org"
MAX_ITEMS = 50

CARD_RE = re.compile(
    r'<article class="section meeting-card" id="meeting-(?P<date>\d{4}-\d{2}-\d{2})">'
    r'.*?<h2><time datetime="[^"]*">(?P<human>[^<]*)</time>\s*-\s*(?P<headline>[^<]*)</h2>'
    r'.*?<p class="meeting-card-summary">(?P<summary>.*?)</p>'
    r'(?P<rest>.*?)</article>',
    re.DOTALL,
)

TAG_RE = re.compile(r'<span class="tag[^"]*">([^<]+)</span>')


def extract_recaps(meetings_html: str) -> list[dict]:
    out = []
    for m in CARD_RE.finditer(meetings_html):
        date = m.group("date")
        try:
            pub = dt.datetime.strptime(date, "%Y-%m-%d").replace(
                hour=7, tzinfo=dt.timezone(dt.timedelta(hours=-7))
            )
        except ValueError:
            continue
        # Tags live in the card markup between the summary and </article>. The
        # first is always the YYYY-MM month facet, which is noise in a reader.
        tags = [t for t in TAG_RE.findall(m.group("rest"))
                if not re.fullmatch(r"\d{4}-\d{2}", t)]
        out.append({
            "date": date,
            "url": f"{SITE}/meetings/{date}.html",
            "title": f'{m.group("human").strip()}: {html.unescape(m.group("headline").strip())}',
            "description": html.unescape(re.sub(r"<[^>]+>", "", m.group("summary")).strip()),
            "pub": pub,
            "tags": tags,
        })
    out.sort(key=lambda r: r["date"], reverse=True)
    return out


def build_rss(recaps: list[dict]) -> str:
    rss = Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")
    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "CSOH - Weekly Meeting Recaps"
    SubElement(channel, "link").text = f"{SITE}/meetings.html"
    SubElement(channel, "description").text = (
        "Topic-by-topic recaps of the Cloud Security Office Hours Friday Zoom "
        "session. What a room of cloud security practitioners actually discussed "
        "each week: breaches, tooling, careers, and the arguments in between."
    )
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "managingEditor").text = "admin@csoh.org (CSOH)"
    SubElement(channel, "webMaster").text = "admin@csoh.org (CSOH)"

    now = dt.datetime.now(dt.timezone.utc)
    SubElement(channel, "lastBuildDate").text = now.strftime("%a, %d %b %Y %H:%M:%S +0000")
    SubElement(channel, "ttl").text = "1440"  # recaps land weekly; 24h is plenty

    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", f"{SITE}/recaps.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    img = SubElement(channel, "image")
    SubElement(img, "url").text = f"{SITE}/favicon.png"
    SubElement(img, "title").text = "CSOH - Weekly Meeting Recaps"
    SubElement(img, "link").text = f"{SITE}/meetings.html"

    for r in recaps[:MAX_ITEMS]:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = r["title"]
        SubElement(item, "link").text = r["url"]
        SubElement(item, "description").text = r["description"]
        guid = SubElement(item, "guid")
        guid.set("isPermaLink", "true")
        guid.text = r["url"]
        SubElement(item, "pubDate").text = r["pub"].strftime("%a, %d %b %Y %H:%M:%S %z")
        for tag in r["tags"]:
            SubElement(item, "category").text = tag

    raw = tostring(rss, encoding="unicode", xml_declaration=False)
    dom = parseString('<?xml version="1.0" encoding="UTF-8"?>' + raw)
    return dom.toprettyxml(indent="  ", encoding=None)


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    meetings_path = repo / "meetings.html"
    feed_path = repo / "recaps.xml"

    if not meetings_path.exists():
        print(f"Error: {meetings_path} not found", file=sys.stderr)
        return 1

    recaps = extract_recaps(meetings_path.read_text(encoding="utf-8"))
    if not recaps:
        print("Warning: no recap cards found in meetings.html", file=sys.stderr)
        return 1

    feed_path.write_text(build_rss(recaps), encoding="utf-8")
    print(f"Generated {feed_path.name} with {min(len(recaps), MAX_ITEMS)} of {len(recaps)} recaps "
          f"(newest {recaps[0]['date']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
