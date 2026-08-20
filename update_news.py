#!/usr/bin/env python3
"""Update news.html with fresh cloud security news.

- Pulls from multiple non-paywalled RSS/Atom feeds.
- Filters for cloud security topics.
- Ensures at least MIN_SOURCES distinct sources per update.
- Avoids duplicates across news.html and resources.html.
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from email.utils import format_datetime, parsedate_to_datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import urlparse


FEEDS = [
    {"name": "AWS Security Blog", "url": "https://aws.amazon.com/blogs/security/feed/"},
    {"name": "AWS Security Bulletins", "url": "https://aws.amazon.com/security/security-bulletins/feed/"},
    {"name": "Google Cloud Blog", "url": "https://cloudblog.withgoogle.com/products/identity-security/rss/"},
    {"name": "Microsoft Security Blog", "url": "https://www.microsoft.com/en-us/security/blog/feed/"},
    {"name": "Cloudflare Blog", "url": "https://blog.cloudflare.com/rss/"},
    {"name": "SANS ISC", "url": "https://isc.sans.edu/rssfeed.xml"},
    {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/"},
    {"name": "The Hacker News", "url": "https://thehackernews.com/feeds/posts/default"},
    {"name": "SecurityWeek", "url": "https://www.securityweek.com/feed/"},
    {"name": "KrebsOnSecurity", "url": "https://krebsonsecurity.com/feed/"},
    {"name": "Dark Reading", "url": "https://www.darkreading.com/rss.xml"},
    {"name": "Help Net Security", "url": "https://www.helpnetsecurity.com/feed/"},
    {"name": "Infosecurity Magazine", "url": "https://www.infosecurity-magazine.com/rss/news/"},
    {"name": "Security Affairs", "url": "https://securityaffairs.com/feed"},
    {"name": "Schneier on Security", "url": "https://www.schneier.com/feed/"},
    {"name": "The Register - Security", "url": "https://www.theregister.com/security/headlines.atom"},
    {"name": "The Register - On-Prem", "url": "https://www.theregister.com/on_prem/headlines.atom"},
    {"name": "The Record", "url": "https://therecord.media/feed"},
    {"name": "CyberScoop", "url": "https://cyberscoop.com/feed/"},
    {"name": "Risky Business News", "url": "https://news.risky.biz/feed/"},
    {"name": "Google Online Security", "url": "https://feeds.feedburner.com/GoogleOnlineSecurityBlog"},
    {"name": "CrowdStrike Blog", "url": "https://www.crowdstrike.com/blog/feed/"},
    {"name": "Palo Alto Networks Unit 42", "url": "https://unit42.paloaltonetworks.com/feed/"},
    {"name": "CISA Alerts", "url": "https://www.cisa.gov/uscert/ncas/alerts.xml"},
    {"name": "CISA Current Activity", "url": "https://www.cisa.gov/uscert/ncas/current-activity.xml"},
    {"name": "CISA Bulletins", "url": "https://www.cisa.gov/uscert/ncas/bulletins.xml"},
    # Cloud Security Research
    {"name": "Wiz Blog", "url": "https://www.wiz.io/feed/rss.xml"},
    {"name": "Orca Security Blog", "url": "https://orca.security/resources/blog/feed/"},
    {"name": "Aqua Security Blog", "url": "https://www.aquasec.com/blog/rss.xml"},
    {"name": "Sysdig Blog", "url": "https://sysdig.com/feed/"},
    {"name": "Datadog Security Labs", "url": "https://securitylabs.datadoghq.com/rss/feed.xml"},
    {"name": "Permiso Security", "url": "https://permiso.io/blog/rss.xml"},
    # Threat Intelligence / Research
    {"name": "Google Threat Intelligence", "url": "https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/"},
    {"name": "Cisco Talos", "url": "https://blog.talosintelligence.com/feed/"},
    {"name": "SentinelLabs", "url": "https://www.sentinelone.com/labs/feed/"},
    {"name": "Elastic Security Labs", "url": "https://www.elastic.co/security-labs/rss/feed.xml"},
    {"name": "FortiGuard Labs", "url": "https://filestore.fortinet.com/fortiguard/rss/threatsignal.xml"},
    {"name": "Recorded Future", "url": "https://www.recordedfuture.com/feed"},
    {"name": "Huntress Blog", "url": "https://www.huntress.com/blog/rss.xml"},
    {"name": "Red Canary Blog", "url": "https://redcanary.com/feed/"},
    {"name": "Zscaler ThreatLabz", "url": "https://www.zscaler.com/blogs/feeds/security-research"},
    {"name": "Check Point Research", "url": "https://research.checkpoint.com/feed/"},
    {"name": "ESET WeLiveSecurity", "url": "https://www.welivesecurity.com/en/rss/feed/"},
    {"name": "Malwarebytes Labs", "url": "https://www.malwarebytes.com/blog/feed/index.xml"},
    {"name": "Volexity", "url": "https://www.volexity.com/feed/"},
    {"name": "NVISO Labs", "url": "https://blog.nviso.eu/feed/"},
    {"name": "The DFIR Report", "url": "https://thedfirreport.com/feed/"},
    # AppSec, Supply Chain & Identity
    {"name": "Snyk Blog", "url": "https://snyk.io/blog/feed/"},
    {"name": "GitGuardian Blog", "url": "https://blog.gitguardian.com/rss/"},
    {"name": "Chainguard Unchained", "url": "https://www.chainguard.dev/unchained/rss.xml"},
    {"name": "StepSecurity Blog", "url": "https://www.stepsecurity.io/blog/rss.xml"},
    {"name": "Okta Security Blog", "url": "https://sec.okta.com/rss.xml"},
    {"name": "ReversingLabs Blog", "url": "https://www.reversinglabs.com/blog/rss.xml"},
    {"name": "JFrog Security Research", "url": "https://jfrog.com/blog/feed/"},
    # Vulnerability Research & Guidance
    {"name": "Project Zero", "url": "https://projectzero.google/feed.xml"},
    {"name": "Rapid7 Blog", "url": "https://www.rapid7.com/blog/rss/"},
    {"name": "OWASP", "url": "https://owasp.org/feed.xml"},
    {"name": "Cloud Security Alliance", "url": "https://cloudsecurityalliance.org/blog/feed/"},
    {"name": "Tenable Blog", "url": "https://www.tenable.com/blog/feed"},
    {"name": "Qualys Blog", "url": "https://blog.qualys.com/feed"},
    {"name": "Trail of Bits Blog", "url": "https://blog.trailofbits.com/feed/"},
    {"name": "watchTowr Labs", "url": "https://labs.watchtowr.com/rss/"},
]

# Concurrency for the two network phases. Modest on purpose: the per-run
# request count is unchanged, so this only affects how fast they are issued,
# and many candidate URLs share a handful of publisher domains.
FEED_WORKERS = 12
RESOLVE_WORKERS = 16

KEYWORDS = {
    "cloud", "aws", "azure", "gcp", "google cloud", "kubernetes", "k8s",
    "iam", "identity", "zero trust", "container", "supply chain",
    "ransomware", "breach", "data leak", "vulnerability", "cve", "exploit",
    "malware", "phishing", "botnet", "security", "patch", "incident", "threat", "research",
    "ai", "llm", "genai", "machine learning", "ml",
    "job", "jobs", "hiring", "career", "layoff", "salary",
    "scam", "fraud", "social engineering", "credential", "identity theft",
    "siem", "ssrf", "misconfiguration", "saml", "oauth", "infostealer",
}

CATEGORY_KEYWORDS = {
    "breach": ["breach", "data leak", "exposed", "leak", "compromise"],
    "vulnerability": ["vulnerability", "cve", "exploit", "rce", "zero-day", "xss", "injection"],
    "report": ["report", "guidance", "alert", "advisory", "bulletin", "update"],
}

TAG_KEYWORDS = {
    "AWS": ["aws", "amazon"],
    "Azure": ["azure", "microsoft"],
    "GCP": ["gcp", "google cloud"],
    "Kubernetes": ["kubernetes", "k8s"],
    "CISA": ["cisa"],
    "Vulnerability": ["vulnerability", "cve", "exploit", "rce", "zero-day"],
    "Breach": ["breach", "data leak", "exposed"],
    "Ransomware": ["ransomware"],
    "Phishing": ["phishing"],
    "Identity": ["iam", "identity"],
    "Supply Chain": ["supply chain"],
    "Zero Trust": ["zero trust"],
    "AI": ["ai", "llm", "genai", "machine learning", "ml"],
    "Jobs": ["job", "jobs", "hiring", "career", "layoff", "salary"],
    "Scam": ["scam", "fraud", "social engineering", "credential"],
    "Threat Research": ["threat research", "threat intelligence", "threat actor", "apt", "campaign"],
}


def fetch_feed(url: str, timeout: int = 15) -> Optional[str]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (CSOH News Bot; +https://csoh.org)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def normalize_dashes(text: str) -> str:
    # Em/en dashes -> hyphens (no AI-looking dashes from external feeds).
    # check_docs_consistency.py gates news.html on this, so every path that
    # renders feed text needs it. Summaries get it via strip_html; titles never
    # pass through strip_html (a security headline may legitimately contain
    # text shaped like an HTML tag), so render_card and build_feed_xml call it
    # directly.
    return text.replace("\u2014", "-").replace("\u2013", "-")


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = normalize_dashes(text)
    text = re.sub(r"\s+", " ", text).strip()
    # Remove HTML5-forbidden code points (C0 except TAB/LF/CR, DEL, C1 except U+0085)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x80-\x84\x86-\x9f]", "", text)
    return text


def parse_date(value: str) -> Optional[dt.datetime]:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        if parsed is None:
            return None
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=dt.timezone.utc)
        return parsed
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(value, fmt)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=dt.timezone.utc)
            return parsed
        except Exception:
            continue
    return None


def _word_match(keyword: str, text: str) -> bool:
    """Match keyword in text using word boundaries for short keywords."""
    if len(keyword) <= 3:
        return bool(re.search(r'\b' + re.escape(keyword) + r'\b', text))
    return keyword in text


def is_relevant(text: str) -> bool:
    lower = text.lower()
    return any(_word_match(kw, lower) for kw in KEYWORDS)


def classify_category(text: str) -> str:
    lower = text.lower()
    for category, keys in CATEGORY_KEYWORDS.items():
        if any(_word_match(k, lower) for k in keys):
            return category
    return "report"


def build_tags(text: str) -> List[str]:
    lower = text.lower()
    tags: List[str] = []
    for tag, keys in TAG_KEYWORDS.items():
        if any(_word_match(k, lower) for k in keys):
            tags.append(tag)
    if not tags:
        tags = ["Cloud Security"]
    return tags[:3]


def normalize_url(url: str) -> str:
    url = url.strip()
    url = re.sub(r"[#?].*$", "", url)
    return url.rstrip("/")


def resolve_url(url: str, timeout: int = 10) -> str:
    """Follow redirects and return the final destination URL."""
    req = urllib.request.Request(
        url,
        method="HEAD",
        headers={
            "User-Agent": "Mozilla/5.0 (CSOH News Bot; +https://csoh.org)",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            final = resp.url
            if final and final != url:
                return final
    except Exception:
        pass
    return url


def resolve_urls(urls: Sequence[str]) -> Dict[str, str]:
    """Resolve many URLs concurrently. Returns {original: final}.

    resolve_url swallows its own errors and falls back to the input URL, so a
    dead host costs one timeout on its own thread instead of failing the run.
    """
    if not urls:
        return {}
    with ThreadPoolExecutor(max_workers=RESOLVE_WORKERS) as pool:
        return dict(zip(urls, pool.map(resolve_url, urls)))


def extract_links(html_text: str) -> List[str]:
    return re.findall(r"href=\"(https?://[^\"]+)\"", html_text, flags=re.IGNORECASE)


def parse_rss(xml_text: str, source_name: str) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items

    tag = root.tag.lower()
    if tag.endswith("feed"):
        ns = "{http://www.w3.org/2005/Atom}"
        for entry in root.findall(f"{ns}entry"):
            title = (entry.findtext(f"{ns}title") or "").strip()
            link = ""
            for link_el in entry.findall(f"{ns}link"):
                rel = link_el.attrib.get("rel", "alternate")
                if rel == "alternate":
                    link = link_el.attrib.get("href", "")
                    break
            published = entry.findtext(f"{ns}published") or entry.findtext(f"{ns}updated") or ""
            summary = entry.findtext(f"{ns}summary") or entry.findtext(f"{ns}content") or ""
            items.append({
                "title": title,
                "link": link,
                "published": published,
                "summary": summary,
                "source": source_name,
            })
        return items

    # RSS
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        published = (item.findtext("pubDate") or item.findtext("date") or "").strip()
        summary = item.findtext("description") or item.findtext("summary") or ""
        items.append({
            "title": title,
            "link": link,
            "published": published,
            "summary": summary,
            "source": source_name,
        })
    return items


def load_existing_urls(news_path: str, resources_path: str) -> set:
    urls = set()
    for path in (news_path, resources_path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                urls.update(normalize_url(u) for u in extract_links(f.read()))
        except FileNotFoundError:
            continue
    return urls


# Matches a full news card anchor block produced by render_card().
EXISTING_CARD_RE = re.compile(
    r'<a\s+href="([^"]+)"\s+class="card-link"[^>]*>\s*'
    r'<div class="resource-card"([^>]*)>(.*?)</div>\s*</a>',
    re.DOTALL,
)
ARTICLE_DATE_RE = re.compile(r'<p class="article-date">([^<]+)</p>')
CARD_H3_RE = re.compile(r'<h3>(.*?)</h3>', re.DOTALL)
CARD_SOURCE_RE = re.compile(r'<span class="source">\(([^)]+)\)</span>')
CARD_TOOLTIP_RE = re.compile(r'data-tooltip="([^"]*)"')
CARD_SUMMARY_P_RE = re.compile(r'<p>(.*?)<span class="source">', re.DOTALL)


def parse_existing_cards(html_text: str) -> List[Dict[str, str]]:
    """Extract previously-rendered news cards from news.html as entry dicts.

    Returns a list suitable for feeding back into render_card / schema builders.
    """
    entries: List[Dict[str, str]] = []
    for match in EXISTING_CARD_RE.finditer(html_text):
        url = html.unescape(match.group(1))
        body = match.group(3)

        h3m = CARD_H3_RE.search(body)
        if not h3m:
            continue
        title = strip_html(html.unescape(h3m.group(1)))

        datem = ARTICLE_DATE_RE.search(body)
        if not datem:
            continue
        try:
            pub_dt = dt.datetime.strptime(datem.group(1).strip(), "%B %d, %Y")
        except ValueError:
            continue
        pub_dt = pub_dt.replace(tzinfo=dt.timezone.utc)

        # Prefer full tooltip summary when present; otherwise fall back to visible text.
        tool_m = CARD_TOOLTIP_RE.search(match.group(2))
        if tool_m:
            summary = html.unescape(tool_m.group(1))
        else:
            sum_m = CARD_SUMMARY_P_RE.search(body)
            summary = strip_html(html.unescape(sum_m.group(1))) if sum_m else ""

        src_m = CARD_SOURCE_RE.search(body)
        source = html.unescape(src_m.group(1)) if src_m else "Unknown Source"

        entries.append({
            "title": title,
            "link": url,
            "summary": summary,
            "published": format_datetime(pub_dt),
            "source": source,
        })
    return entries


def format_date(d: dt.datetime) -> Tuple[str, str]:
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    d_local = d.astimezone(dt.timezone.utc)
    return d_local.strftime("%B %d, %Y"), d_local.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_feed_xml(entries: List[Dict[str, str]], newest_iso: str) -> str:
    rss = ET.Element("rss", attrib={"version": "2.0", "xmlns:atom": "http://www.w3.org/2005/Atom"})
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "CSOH - Cloud Security News"
    ET.SubElement(channel, "link").text = "https://csoh.org/news.html"
    ET.SubElement(channel, "description").text = (
        "Latest cloud security news curated by Cloud Security Office Hours. "
        "Covers AWS, Azure, GCP, Kubernetes vulnerabilities, breaches, and more."
    )
    ET.SubElement(channel, "language").text = "en-us"
    ET.SubElement(channel, "managingEditor").text = "admin@csoh.org (CSOH)"
    ET.SubElement(channel, "webMaster").text = "admin@csoh.org (CSOH)"

    newest_dt = parse_date(newest_iso) or dt.datetime.now(dt.timezone.utc)
    ET.SubElement(channel, "lastBuildDate").text = format_datetime(newest_dt)
    ET.SubElement(channel, "ttl").text = "720"

    ET.SubElement(
        channel,
        "atom:link",
        attrib={
            "href": "https://csoh.org/feed.xml",
            "rel": "self",
            "type": "application/rss+xml",
        },
    )

    image = ET.SubElement(channel, "image")
    ET.SubElement(image, "url").text = "https://csoh.org/favicon.png"
    ET.SubElement(image, "title").text = "CSOH - Cloud Security News"
    ET.SubElement(image, "link").text = "https://csoh.org/news.html"

    for entry in entries:
        title = normalize_dashes(entry.get("title", "")).strip()
        link = entry.get("link", "").strip()
        if not title or not link:
            continue

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = title
        ET.SubElement(item, "link").text = link

        summary = strip_html(entry.get("summary", ""))
        if len(summary) > 220:
            summary = summary[:217].rstrip() + "..."
        ET.SubElement(item, "description").text = summary

        source_name = entry.get("source", "Unknown Source")
        ET.SubElement(item, "source", attrib={"url": link}).text = source_name
        ET.SubElement(item, "guid", attrib={"isPermaLink": "true"}).text = link

        published_dt = parse_date(entry.get("published", "")) or newest_dt
        ET.SubElement(item, "pubDate").text = format_datetime(published_dt)

        tags = build_tags(f"{title} {summary} {source_name}")
        for tag in tags:
            ET.SubElement(item, "category").text = tag

    ET.indent(rss, space="  ")
    return ET.tostring(rss, encoding="unicode", xml_declaration=True)


# Map source display names → slugs (must match img/news-banners/{slug}.jpg)
SOURCE_SLUGS = {
    "AWS Security Blog": "aws-security-blog",
    "Google Cloud Blog": "google-cloud-blog",
    "Microsoft Security Blog": "microsoft-security-blog",
    "Cloudflare Blog": "cloudflare-blog",
    "SANS ISC": "sans-isc",
    "BleepingComputer": "bleepingcomputer",
    "The Hacker News": "thehackernews",
    "SecurityWeek": "securityweek",
    "KrebsOnSecurity": "krebsonsecurity",
    "Dark Reading": "darkreading",
    "Help Net Security": "helpnetsecurity",
    "Infosecurity Magazine": "infosecurity-magazine",
    "Security Affairs": "securityaffairs",
    "Schneier on Security": "schneier",
    "The Register - Security": "theregister",
    "The Register - On-Prem": "theregister",
    "Google Online Security": "google-online-security",
    "CrowdStrike Blog": "crowdstrike",
    "Palo Alto Networks Unit 42": "unit42",
    "CISA Alerts": "cisa",
    "CISA Current Activity": "cisa",
    "CISA Bulletins": "cisa",
    "AWS Security Bulletins": "aws-security-bulletins",
    "The Record": "therecord",
    "Risky Business News": "riskybusiness",
    # Cloud Security Research
    "Wiz Blog": "wiz",
    "Orca Security Blog": "orca-security",
    "Aqua Security Blog": "aqua-security",
    "Sysdig Blog": "sysdig",
    "Datadog Security Labs": "datadog-security-labs",
    "Permiso Security": "permiso",
    # Threat Intelligence / Research
    "Google Threat Intelligence": "google-threat-intelligence",
    "Cisco Talos": "cisco-talos",
    "SentinelLabs": "sentinellabs",
    "Elastic Security Labs": "elastic-security-labs",
    "FortiGuard Labs": "fortiguard-labs",
    "Recorded Future": "recorded-future",
    "Huntress Blog": "huntress",
    "Red Canary Blog": "red-canary",
    "Zscaler ThreatLabz": "zscaler-threatlabz",
    "Check Point Research": "checkpoint-research",
    "ESET WeLiveSecurity": "welivesecurity",
    "Malwarebytes Labs": "malwarebytes",
    "Volexity": "volexity",
    "NVISO Labs": "nviso",
    "The DFIR Report": "dfir-report",
    # AppSec, Supply Chain & Identity
    "Snyk Blog": "snyk",
    "GitGuardian Blog": "gitguardian",
    "Chainguard Unchained": "chainguard",
    "StepSecurity Blog": "stepsecurity",
    "Okta Security Blog": "okta-security",
    "ReversingLabs Blog": "reversinglabs",
    "JFrog Security Research": "jfrog",
    # Vulnerability Research & Guidance
    "Project Zero": "project-zero",
    "Rapid7 Blog": "rapid7",
    "OWASP": "owasp",
    "Cloud Security Alliance": "cloud-security-alliance",
    "Tenable Blog": "tenable",
    "Qualys Blog": "qualys",
    "Trail of Bits Blog": "trail-of-bits",
    "watchTowr Labs": "watchtowr",
}


def render_card(entry: Dict[str, str], indent: str) -> str:
    title = html.escape(normalize_dashes(html.unescape(entry["title"])))
    link = html.escape(html.unescape(entry["link"]))
    full_summary = strip_html(html.unescape(entry.get("summary", "")))
    summary = full_summary
    if len(summary) > 180:
        summary = summary[:177].rstrip() + "..."

    # Build tooltip from the full summary when it's longer than the card text
    tooltip_attr = ""
    if len(full_summary) > 180:
        tooltip_text = full_summary[:400].rstrip()
        if len(full_summary) > 400:
            tooltip_text += "..."
        tooltip_attr = f' data-tooltip="{html.escape(tooltip_text, quote=True)}"'

    published_dt = parse_date(entry.get("published", "")) or dt.datetime.now(dt.timezone.utc)
    date_text, _ = format_date(published_dt)

    category = classify_category(f"{entry['title']} {summary}")
    tags = build_tags(f"{entry['title']} {summary} {entry['source']}")
    source_slug = SOURCE_SLUGS.get(entry["source"], "")

    tag_spans = "\n".join([f"{indent}            <span class=\"tag\">{html.escape(t)}</span>" for t in tags])

    source_attr = f' data-source="{source_slug}"' if source_slug else ""
    banner_img = ""
    if source_slug:
        banner_img = (
            f"{indent}        <picture>"
            f"<source srcset=\"img/news-banners/{source_slug}.webp\" type=\"image/webp\">"
            f"<img src=\"img/news-banners/{source_slug}.jpg\" "
            f"alt=\"{html.escape(entry['source'])}\" "
            f"class=\"resource-preview\" loading=\"lazy\" decoding=\"async\">"
            f"</picture>\n"
        )

    return (
        f"{indent}<a href=\"{link}\" class=\"card-link\" target=\"_blank\" rel=\"noopener noreferrer\">\n"
        f"{indent}    <div class=\"resource-card\" data-category=\"{category}\"{source_attr}{tooltip_attr}>\n"
        f"{banner_img}"
        f"{indent}        <h3>{title}</h3>\n"
        f"{indent}        <p class=\"article-date\">{date_text}</p>\n"
        f"{indent}        <p>{html.escape(summary)} <span class=\"source\">({html.escape(entry['source'])})</span></p>\n"
        f"{indent}        <div class=\"resource-tags\">\n"
        f"{tag_spans}\n"
        f"{indent}        </div>\n"
        f"{indent}    </div>\n"
        f"{indent}</a>"
    )


def replace_grid(html_text: str, cards_html: str) -> str:
    marker = '<div class="resource-grid">'
    idx = html_text.find(marker)
    if idx == -1:
        raise ValueError("Could not find resource-grid container")

    start = idx + len(marker)
    depth = 1
    pattern = re.compile(r"</?div\b", re.IGNORECASE)

    for match in pattern.finditer(html_text, start):
        token = html_text[match.start():match.start() + 5].lower()
        if token.startswith("</div"):
            depth -= 1
        else:
            depth += 1
        if depth == 0:
            end = match.start()
            return html_text[:start] + "\n" + cards_html + "\n" + html_text[end:]

    raise ValueError("Could not find end of resource-grid container")


def update_date_modified(html_text: str, iso_date: str) -> str:
    html_text = re.sub(r'og:updated_time"\s+content="[^"]+"', f'og:updated_time" content="{iso_date}"', html_text, count=1)
    return html_text


def build_newsarticle_schema(entry: Dict[str, str]) -> dict:
    link = entry["link"]
    parsed = urlparse(link)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else "https://csoh.org"

    published_dt = parse_date(entry.get("published", "")) or dt.datetime.now(dt.timezone.utc)
    iso = published_dt.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    title = strip_html(html.unescape(entry["title"])).strip()
    headline = title[:110]
    full_summary = strip_html(html.unescape(entry.get("summary", "")))
    description = full_summary[:250] if full_summary else title

    source = entry["source"]
    tags = build_tags(f"{entry['title']} {full_summary} {source}")
    source_slug = SOURCE_SLUGS.get(source, "")
    image_url = (
        f"https://csoh.org/img/news-banners/{source_slug}.jpg"
        if source_slug
        else "https://csoh.org/banner.png"
    )

    return {
        "@type": "NewsArticle",
        "headline": headline,
        "description": description,
        "url": link,
        "image": image_url,
        "datePublished": iso,
        "dateModified": iso,
        "author": {
            "@type": "Organization",
            "name": source,
            "url": origin,
        },
        "publisher": {
            "@type": "Organization",
            "name": source,
            "logo": {
                "@type": "ImageObject",
                "url": "https://csoh.org/banner.png",
                "width": 600,
                "height": 60,
            },
        },
        "inLanguage": "en-US",
        "keywords": ", ".join(tags),
    }


def build_collection_schema(entries: List[Dict[str, str]], newest_iso: str, limit: int = 20) -> str:
    articles = [build_newsarticle_schema(e) for e in entries[:limit]]
    schema = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "Cloud Security News",
        "description": (
            "Latest cloud security news: AWS/Azure/GCP vulnerabilities, data breaches, "
            "zero-day exploits, security patches, and industry developments. Curated "
            "daily by cloud security professionals."
        ),
        "url": "https://csoh.org/news.html",
        "mainEntity": {
            "@type": "ItemList",
            "name": "Cloud Security News Articles",
            "description": f"{len(entries)} curated cloud security news articles from reputable sources",
            "author": {
                "@type": "Organization",
                "name": "Cloud Security Office Hours",
                "url": "https://csoh.org/",
                "logo": "https://csoh.org/banner.png",
            },
            "dateModified": newest_iso,
            "inLanguage": "en-US",
            "isAccessibleForFree": True,
            "hasPart": articles,
        },
    }
    # Escape every HTML-significant character before this JSON goes inside a
    # <script type="application/ld+json"> block on news.html.
    #
    # This used to escape only `</`, which stops a literal `</script>` from
    # terminating the block but not much else. An HTML parser also ends the
    # block's contents at a `<!--` comment opener, so feed-controlled text
    # containing `<!--` followed by `<script` anywhere later in the same block
    # is enough to swallow the rest of the page. Feed titles and summaries are
    # attacker-influenceable (a compromised vendor blog, a hijacked feed host,
    # an expired-and-re-registered feed domain) and, because these are security
    # news feeds, a legitimate post about an XSS payload can produce the same
    # bytes by accident.
    #
    # `\uXXXX` is a valid JSON string escape, so consumers (Google, schema.org
    # validators, anything doing json.loads) still see the original characters -
    # the structured data is unchanged. Only the HTML parser is affected, and it
    # now sees nothing it can act on.
    out = json.dumps(schema, indent=2, ensure_ascii=False)
    return (
        out.replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def replace_collection_schema(html_text: str, schema_json: str) -> str:
    pattern = re.compile(
        r'(<!-- Structured Data - News Collection for Rich Snippets -->\s*<script type="application/ld\+json">)'
        r'(.*?)'
        r'(</script>)',
        re.DOTALL,
    )

    indented = "\n".join("    " + line if line else line for line in schema_json.split("\n"))

    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}\n{indented}\n    {match.group(3)}"

    new_text, n = pattern.subn(repl, html_text, count=1)
    return new_text if n > 0 else html_text


def _entry_date(entry: Dict[str, str]) -> dt.datetime:
    return (
        parse_date(entry.get("published", ""))
        or dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    )


# Tokens that are common across news headlines and don't carry topic signal.
# 4-char minimum already filters most function words; this list trims the rest.
NEAR_DUP_STOPWORDS = frozenset({
    "about", "across", "after", "against", "amid", "among", "amongst",
    "around", "before", "between", "could", "during", "from", "have",
    "into", "just", "less", "more", "much", "over", "post", "said",
    "says", "should", "such", "than", "that", "their", "them", "then",
    "there", "these", "they", "this", "those", "throughout", "until",
    "upon", "very", "were", "what", "when", "where", "which", "while",
    "with", "would", "appeared", "first", "second", "third", "today",
    "year", "years", "week", "weeks", "month", "months", "monday",
    "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "amid", "amidst", "also", "back", "been", "being", "down", "each",
    "ever", "even", "from", "into", "like", "made", "make", "many",
    "much", "must", "near", "next", "only", "other", "some", "soon",
    "still", "take", "took", "used", "using", "well", "your", "yours",
})


# Long tokens that show up across unrelated cybersec headlines and so don't
# imply same-event when shared. Excluded from the "distinctive" signature.
# (Vendor names, product names, attack names, and topic anchors like
# "ransomware"/"kubernetes"/"vulnerability" are deliberately *not* listed -
# sharing those across two articles is a real signal.)
NEAR_DUP_GENERIC_LONG = frozenset({
    "addressing", "affecting", "announced", "announces", "announcing",
    "announcement", "application", "applications", "assessment",
    "assessments", "automated", "automation", "businesses",
    "compliance", "configuration", "configurations", "continuous",
    "continuously", "critical", "customer", "customers", "developer",
    "developers", "discovered", "discovers", "engineering", "engineers",
    "enterprise", "enterprises", "feature", "features", "generation",
    "generations", "hundreds", "identity", "identities", "industry",
    "industries", "introduced", "introduces", "introducing", "millions",
    "multiple", "operation", "operations", "organization",
    "organizations", "patch", "patched", "patches", "patching",
    "platform", "platforms", "practices", "preventing", "process",
    "processes", "product", "products", "professional", "professionals",
    "providing", "regulations", "regulatory", "release", "released",
    "releases", "releasing", "research", "researcher", "researchers",
    "sensitive", "service", "services", "specific", "strengthens",
    "subscription", "subscriptions", "successful", "successfully",
    "techniques", "thousands", "update", "updated", "updates",
    "updating", "vulnerabilities", "vulnerability", "vulnerable",
    "workload", "workloads",
})


def _signature_tokens(text: str) -> frozenset:
    tokens = re.findall(r"[a-z0-9]{4,}", text.lower())
    return frozenset(t for t in tokens if t not in NEAR_DUP_STOPWORDS)


def near_dup_signature(entry: Dict[str, str]) -> Tuple[frozenset, frozenset, frozenset]:
    """Return (all-tokens, distinctive-tokens, title-tokens) fingerprints.

    `distinctive` keeps tokens of length >= 8 minus generic cybersec filler,
    so its members are typically named entities, product names, or topic
    anchors (BlackCat, kubernetes, anthropic, ransomware, vulnerability).
    `title_tokens` lets us catch same-event coverage where summaries diverge
    but headlines still share the topic anchors.
    """
    title = strip_html(html.unescape(entry.get("title", "")))
    summary = strip_html(html.unescape(entry.get("summary", "")))[:300]
    all_tokens = _signature_tokens(f"{title} {summary}")
    distinctive = frozenset(
        t for t in all_tokens if len(t) >= 8 and t not in NEAR_DUP_GENERIC_LONG
    )
    # Title set drops generic content words too - "AWS Patches Critical X
    # Vulnerability" headlines shouldn't count {patches, critical, vulnerability}
    # toward an event-match against a different vendor's bulletin.
    title_significant = frozenset(
        t for t in _signature_tokens(title) if t not in NEAR_DUP_GENERIC_LONG
    )
    return all_tokens, distinctive, title_significant


def is_near_duplicate(
    sig: Tuple[frozenset, frozenset, frozenset],
    kept: Iterable[Tuple[frozenset, frozenset, frozenset]],
) -> bool:
    """True if `sig` shares enough significant tokens with any `kept` signature.

    Four layered tests catch different shapes of same-event coverage:
      - Jaccard >= 0.30 on all tokens (broad overlap)
      - smaller-side overlap >= 0.55 (one outlet had a long summary)
      - shared distinctive (8+ char, non-generic) tokens >= 3 (same named
        entities/topic anchors even when wording diverges)
      - shared title tokens >= 3 (different summaries, similar headlines)
    """
    sig_all, sig_distinctive, sig_title = sig
    if len(sig_all) < 5:
        return False
    for other_all, other_distinctive, other_title in kept:
        if len(other_all) < 5:
            continue
        intersection = len(sig_all & other_all)
        if intersection >= 3:
            union = len(sig_all | other_all)
            if union and intersection / union >= 0.30:
                return True
            smaller = min(len(sig_all), len(other_all))
            if smaller and intersection / smaller >= 0.55:
                return True
            if len(sig_distinctive & other_distinctive) >= 3:
                return True
        if len(sig_title & other_title) >= 3:
            return True
    return False


def dedupe_near_entries(entries: List[Dict[str, str]]) -> Tuple[List[Dict[str, str]], int]:
    """Drop entries whose title+summary tokens overlap heavily with one already kept.

    Iterates in input order, so callers should pre-sort (typically newest-first
    so the most recent rendering of an event wins). Returns (kept, dropped_count).
    """
    kept: List[Dict[str, str]] = []
    kept_sigs: List[Tuple[frozenset, frozenset, frozenset]] = []
    dropped = 0
    for entry in entries:
        sig = near_dup_signature(entry)
        if is_near_duplicate(sig, kept_sigs):
            dropped += 1
            continue
        kept.append(entry)
        kept_sigs.append(sig)
    return kept, dropped


def select_with_source_cap(
    entries: List[Dict[str, str]],
    max_articles: int,
    per_source_cap: int,
) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    """Take the newest max_articles entries, at most per_source_cap per source.

    Guards against a feed that re-stamps its whole back catalog with a handful
    of recent dates. Mitiga, for one, served 100 items carrying just three
    publish dates, which took 26 of 120 cards on a straight newest-first cut.

    Expects entries pre-sorted newest-first. If the cap leaves the page short
    (a quiet news day, or too few sources reporting), the over-cap remainder
    backfills rather than publishing a half-empty page, so the cap costs
    nothing when there isn't the diversity to satisfy it.

    Returns (selected, held) where held maps source -> page slots it would have
    taken without the cap. That is deliberately measured against the uncapped
    top max_articles rather than against everything over the cap: the archive
    feeds routinely serve hundreds of old entries that were never in contention
    for the page, and counting those would bury the one source that matters.
    """
    if per_source_cap <= 0:
        return entries[:max_articles], {}

    counts: Dict[str, int] = {}
    picked: List[Dict[str, str]] = []
    overflow: List[Dict[str, str]] = []
    for entry in entries:
        source = entry.get("source", "")
        if counts.get(source, 0) >= per_source_cap:
            overflow.append(entry)
            continue
        counts[source] = counts.get(source, 0) + 1
        picked.append(entry)

    selected = picked[:max_articles]
    backfill = overflow[: max(0, max_articles - len(selected))]
    if backfill:
        selected = selected + backfill
        selected.sort(key=_entry_date, reverse=True)

    def by_source(items: List[Dict[str, str]]) -> Dict[str, int]:
        tally: Dict[str, int] = {}
        for entry in items:
            source = entry.get("source", "")
            tally[source] = tally.get(source, 0) + 1
        return tally

    uncapped = by_source(entries[:max_articles])
    final = by_source(selected)
    held = {
        source: n - final.get(source, 0)
        for source, n in uncapped.items()
        if n - final.get(source, 0) > 0
    }
    return selected, held


def build_entries(
    news_path: str,
    resources_path: str,
    max_articles: int,
    min_sources: int,
    today_target: int = 10,
    per_source_cap: int = 12,
) -> Tuple[List[Dict[str, str]], str]:
    # Preserve entries already rendered in news.html so rolling RSS windows
    # don't drop them on the next run. Same-day items especially accumulate
    # across the day as each run adds whatever's freshly in the feeds.
    try:
        with open(news_path, "r", encoding="utf-8") as f:
            news_html = f.read()
        preserved = parse_existing_cards(news_html)
    except FileNotFoundError:
        preserved = []

    existing_urls: set = {normalize_url(e["link"]) for e in preserved}
    try:
        with open(resources_path, "r", encoding="utf-8") as f:
            existing_urls.update(normalize_url(u) for u in extract_links(f.read()))
    except FileNotFoundError:
        pass

    today_date = dt.datetime.now(dt.timezone.utc).date()
    collected: List[Dict[str, str]] = []
    today_fallback: List[Dict[str, str]] = []

    # Both network phases below run concurrently. They used to be serial, which
    # cost ~22 minutes per run for ~4,800 redirect lookups at ~110s of actual
    # CPU. The work is identical, just no longer one-at-a-time.
    with ThreadPoolExecutor(max_workers=FEED_WORKERS) as pool:
        feed_xml = list(pool.map(lambda f: fetch_feed(f["url"]), FEEDS))

    # Gather candidates in FEEDS order so the run stays deterministic, and
    # drop anything already published before paying for a redirect lookup.
    candidates: List[Tuple[str, Dict[str, str]]] = []
    seen_norm: set = set()
    for feed, xml_text in zip(FEEDS, feed_xml):
        if not xml_text:
            continue
        for item in parse_rss(xml_text, feed["name"]):
            if not item.get("title") or not item.get("link"):
                continue
            norm = normalize_url(item["link"])
            if norm in existing_urls or norm in seen_norm:
                continue
            seen_norm.add(norm)
            candidates.append((norm, item))

    resolved_map = resolve_urls([norm for norm, _ in candidates])

    for norm, item in candidates:
        resolved = normalize_url(resolved_map.get(norm, norm))
        if resolved in existing_urls:
            continue
        item["link"] = resolved
        existing_urls.add(resolved)

        combined = f"{item['title']} {item.get('summary', '')}"
        if is_relevant(combined):
            collected.append(item)
        else:
            pub_dt = parse_date(item.get("published", ""))
            if pub_dt and pub_dt.astimezone(dt.timezone.utc).date() == today_date:
                # Today-dated item from a security-focused feed that
                # didn't hit the strict keyword filter. Held in reserve
                # for top-up only if we're short on today items.
                today_fallback.append(item)

    all_entries = preserved + collected
    if not all_entries and not today_fallback:
        raise ValueError("No news items found from feeds or preserved page")

    all_entries.sort(key=_entry_date, reverse=True)
    all_entries, near_dropped = dedupe_near_entries(all_entries)
    selected, held = select_with_source_cap(all_entries, max_articles, per_source_cap)

    today_count = sum(1 for e in selected if _entry_date(e).date() == today_date)
    fallback_used = 0

    if today_count < today_target and today_fallback:
        # Top up today's count from the relaxed-filter pool. Items pass in
        # order of publish time (newest first); we stop once we hit the
        # target or exhaust the pool.
        today_fallback.sort(key=_entry_date, reverse=True)
        needed = today_target - today_count
        selected_urls = {e["link"] for e in selected}
        extras = [e for e in today_fallback if e["link"] not in selected_urls][:needed]
        if extras:
            all_entries = extras + all_entries
            all_entries.sort(key=_entry_date, reverse=True)
            all_entries, extra_dropped = dedupe_near_entries(all_entries)
            near_dropped += extra_dropped
            selected, held = select_with_source_cap(
                all_entries, max_articles, per_source_cap
            )
            fallback_used = len(extras)
            today_count = sum(1 for e in selected if _entry_date(e).date() == today_date)

    sources = {item["source"] for item in selected}
    if len(sources) < min_sources:
        print(
            f"Warning: Only {len(sources)} sources available; expected at least {min_sources}.",
            file=sys.stderr,
        )
    if today_count < today_target:
        print(
            f"Warning: Only {today_count} today-dated entries (target {today_target}); "
            f"feeds may not have enough published items yet.",
            file=sys.stderr,
        )
    if held:
        detail = ", ".join(
            f"{source} (+{n})" for source, n in sorted(held.items(), key=lambda kv: -kv[1])
        )
        print(
            f"Per-source cap of {per_source_cap} held back: {detail}. "
            f"A source far over the cap may be re-stamping old posts.",
            file=sys.stderr,
        )

    print(
        f"Selected {len(selected)} entries ({today_count} from today, "
        f"{len(preserved)} preserved, {len(collected)} new from feeds, "
        f"{fallback_used} relaxed-filter today top-ups, "
        f"{near_dropped} near-duplicates dropped).",
        file=sys.stderr,
    )

    newest = _entry_date(selected[0])
    _, newest_iso = format_date(newest)
    return selected[:max_articles], newest_iso


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Update news.html from RSS feeds")
    parser.add_argument("--news-file", default="news.html")
    parser.add_argument("--resources-file", default="resources.html")
    parser.add_argument("--feed-file", default="feed.xml")
    parser.add_argument("--max-articles", type=int, default=120)
    parser.add_argument("--min-sources", type=int, default=10)
    parser.add_argument(
        "--today-target",
        type=int,
        default=10,
        help="Minimum today-dated entries; tops up from relaxed-filter pool if below.",
    )
    parser.add_argument(
        "--per-source-cap",
        type=int,
        default=12,
        help="Max articles from any one source; 0 disables. Over-cap items "
        "backfill the page if there isn't enough from other sources.",
    )
    args = parser.parse_args(argv)

    try:
        entries, newest_iso = build_entries(
            args.news_file,
            args.resources_file,
            args.max_articles,
            args.min_sources,
            today_target=args.today_target,
            per_source_cap=args.per_source_cap,
        )
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    indent = " " * 16
    # Group cards by formatted date and emit a visible H2 heading before each
    # date's first card. The headings span the full grid width via CSS.
    parts: List[str] = []
    last_date: str = ""
    pending_group: List[Dict[str, str]] = []
    grouped: List[tuple[str, List[Dict[str, str]]]] = []
    for entry in entries:
        published_dt = parse_date(entry.get("published", "")) or dt.datetime.now(dt.timezone.utc)
        date_text, _ = format_date(published_dt)
        if date_text != last_date and pending_group:
            grouped.append((last_date, pending_group))
            pending_group = []
        last_date = date_text
        pending_group.append(entry)
    if pending_group:
        grouped.append((last_date, pending_group))

    for date_text, group_entries in grouped:
        count_label = f"{len(group_entries)} article{'s' if len(group_entries) != 1 else ''}"
        parts.append(
            f'{indent}<h2 class="news-date-heading">'
            f'<span class="news-date-label">{html.escape(date_text)}</span>'
            f' <span class="news-date-count">· {count_label}</span>'
            f'</h2>'
        )
        for entry in group_entries:
            parts.append(render_card(entry, indent))
    cards_html = "\n".join(parts)

    try:
        with open(args.news_file, "r", encoding="utf-8") as f:
            html_text = f.read()
    except FileNotFoundError:
        print(f"Error: {args.news_file} not found", file=sys.stderr)
        return 1

    html_text = replace_grid(html_text, cards_html)
    schema_json = build_collection_schema(entries, newest_iso)
    html_text = replace_collection_schema(html_text, schema_json)
    html_text = update_date_modified(html_text, newest_iso)

    with open(args.news_file, "w", encoding="utf-8") as f:
        f.write(html_text)

    feed_xml = build_feed_xml(entries, newest_iso)
    with open(args.feed_file, "w", encoding="utf-8") as f:
        f.write(feed_xml)

    # Refresh sitemap <lastmod> values so the news.html change is reflected.
    sitemap_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools", "update_sitemap.py")
    if os.path.exists(sitemap_script):
        subprocess.run([sys.executable, sitemap_script], check=False)

    print(
        f"Updated {args.news_file} and {args.feed_file} with {len(entries)} articles "
        f"from {len({e['source'] for e in entries})} sources."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
