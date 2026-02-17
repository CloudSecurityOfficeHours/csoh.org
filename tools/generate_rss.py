#!/usr/bin/env python3
"""Generate an RSS 2.0 feed (feed.xml) from the news.html page.

Run after update_news.py to regenerate the RSS feed from the latest
news articles on the site.

Usage:
    python3 tools/generate_rss.py
"""

import datetime as dt
import html
import re
import sys
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString


def extract_articles(news_html: str) -> list:
    """Extract article data from news.html card-link elements."""
    articles = []

    # Match each card-link <a> block
    pattern = re.compile(
        r'<a\s+href="([^"]+)"\s+class="card-link"[^>]*>'
        r'\s*<div\s+class="resource-card"[^>]*>'
        r'\s*<h3>([^<]+)</h3>'
        r'\s*<p\s+class="article-date">([^<]+)</p>'
        r'\s*<p>(.+?)<span\s+class="source">\(([^)]+)\)</span></p>'
        r'\s*<div\s+class="resource-tags">(.*?)</div>',
        re.DOTALL,
    )

    for m in pattern.finditer(news_html):
        url = m.group(1).strip()
        title = html.unescape(m.group(2).strip())
        date_str = m.group(3).strip()
        description = html.unescape(m.group(4).strip())
        source = m.group(5).strip()
        tags_html = m.group(6)

        tags = re.findall(r'<span\s+class="tag[^"]*">([^<]+)</span>', tags_html)

        # Parse date
        pub_date = None
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                pub_date = dt.datetime.strptime(date_str, fmt).replace(
                    tzinfo=dt.timezone.utc
                )
                break
            except ValueError:
                continue

        articles.append({
            "url": url,
            "title": title,
            "description": description,
            "source": source,
            "date": pub_date,
            "date_str": date_str,
            "tags": tags,
        })

    return articles


def build_rss(articles: list) -> str:
    """Build RSS 2.0 XML string from article data."""
    rss = Element("rss", version="2.0")
    rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

    channel = SubElement(rss, "channel")

    SubElement(channel, "title").text = "CSOH - Cloud Security News"
    SubElement(channel, "link").text = "https://csoh.org/news.html"
    SubElement(channel, "description").text = (
        "Latest cloud security news curated by Cloud Security Office Hours. "
        "Covers AWS, Azure, GCP, Kubernetes vulnerabilities, breaches, and more."
    )
    SubElement(channel, "language").text = "en-us"
    SubElement(channel, "managingEditor").text = "admin@csoh.org (CSOH)"
    SubElement(channel, "webMaster").text = "admin@csoh.org (CSOH)"

    now = dt.datetime.now(dt.timezone.utc)
    SubElement(channel, "lastBuildDate").text = now.strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )
    SubElement(channel, "ttl").text = "720"  # 12 hours

    # Atom self-link for feed readers
    atom_link = SubElement(channel, "atom:link")
    atom_link.set("href", "https://csoh.org/feed.xml")
    atom_link.set("rel", "self")
    atom_link.set("type", "application/rss+xml")

    SubElement(channel, "image").text = ""
    image = channel.find("image")
    channel.remove(image)
    img = SubElement(channel, "image")
    SubElement(img, "url").text = "https://csoh.org/favicon.png"
    SubElement(img, "title").text = "CSOH - Cloud Security News"
    SubElement(img, "link").text = "https://csoh.org/news.html"

    # Add items (limit to 50 most recent)
    for article in articles[:50]:
        item = SubElement(channel, "item")
        SubElement(item, "title").text = article["title"]
        SubElement(item, "link").text = article["url"]
        SubElement(item, "description").text = article["description"]
        SubElement(item, "source", url=article["url"]).text = article["source"]

        guid = SubElement(item, "guid")
        guid.set("isPermaLink", "true")
        guid.text = article["url"]

        if article["date"]:
            SubElement(item, "pubDate").text = article["date"].strftime(
                "%a, %d %b %Y %H:%M:%S +0000"
            )

        for tag in article["tags"]:
            SubElement(item, "category").text = tag

    # Pretty print
    raw = tostring(rss, encoding="unicode", xml_declaration=False)
    dom = parseString('<?xml version="1.0" encoding="UTF-8"?>' + raw)
    return dom.toprettyxml(indent="  ", encoding=None)


def main():
    repo_root = Path(__file__).resolve().parent.parent
    news_path = repo_root / "news.html"
    feed_path = repo_root / "feed.xml"

    if not news_path.exists():
        print(f"Error: {news_path} not found", file=sys.stderr)
        return 1

    news_html = news_path.read_text(encoding="utf-8")
    articles = extract_articles(news_html)

    if not articles:
        print("Warning: No articles found in news.html", file=sys.stderr)
        return 1

    rss_xml = build_rss(articles)
    feed_path.write_text(rss_xml, encoding="utf-8")

    print(f"Generated {feed_path.name} with {min(len(articles), 50)} articles")
    return 0


if __name__ == "__main__":
    sys.exit(main())
