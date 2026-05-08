#!/usr/bin/env python3
"""Split meetings.html into one page per meeting.

One-time migration tool. Reads ../meetings.html, extracts every
<article class="section" id="meeting-YYYY-MM-DD">, and writes:

  ../meetings/YYYY-MM-DD.html — full standalone page for each meeting
  ../meetings.html            — replaced with an index/directory page

Each meeting is already a self-contained <article>, so extraction is
straightforward.
"""

from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "meetings.html"
OUT_DIR = REPO_ROOT / "meetings"

ARTICLE_RE = re.compile(
    r'<article class="section" id="meeting-(\d{4}-\d{2}-\d{2})">'
    r'(.*?)'
    r'</article>',
    re.DOTALL,
)
H2_RE = re.compile(
    r'<h2>\s*<time datetime="(\d{4}-\d{2}-\d{2})">([^<]+)</time>\s*(?:&#x2014;|—|--)?\s*([^<]*)</h2>',
)
SUMMARY_RE = re.compile(r'<p>\s*<strong>Quick recap\.</strong>(.*?)</p>', re.DOTALL)


def strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    s = unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    return cut + "…"


def fix_body_links(body: str) -> str:
    """The extracted article body contains internal links written for the
    root-level meetings.html. Per-meeting pages live in /meetings/ so those
    need a "../" prefix. Also replace anchor links to #table-of-contents
    with a link back to the index.
    """
    # 1. Root-relative internal links → ../-relative
    targets = (
        'glossary.html', 'ctfs.html', 'resources.html', 'breach-timeline.html',
        'threat-research.html', 'news.html', 'sessions.html', 'meetings.html',
        'what-is-cloud-security.html', 'learning-path.html',
        'cloud-security-certifications.html', 'github-actions.html',
        'conferences.html', 'faq.html', 'cloud-security-best-practices.html',
        'shared-responsibility-model.html', 'cspm-vs-cnapp.html',
        'presentations.html', 'chat-resources.html',
    )
    pattern = '|'.join(re.escape(t) for t in targets)
    body = re.sub(rf'(href=")({pattern})(["#?])', r'\1../\2\3', body, flags=re.IGNORECASE)

    # 2. The "↑ Back to index" anchor link goes to the per-page meeting index
    body = re.sub(
        r'<p class="small"><a href="#table-of-contents">↑ Back to index</a></p>',
        '<p class="small"><a href="../meetings.html">↑ All meeting recaps</a></p>',
        body,
    )

    return body


def parse_meetings(html: str) -> list[dict]:
    out = []
    for m in ARTICLE_RE.finditer(html):
        date = m.group(1)
        body = m.group(2).strip()
        h2_match = H2_RE.search(body)
        if not h2_match:
            print(f'  ⚠ {date}: no h2 found, skipping', file=sys.stderr)
            continue
        date_text = h2_match.group(2).strip()
        headline = unescape(h2_match.group(3).strip())
        summary_match = SUMMARY_RE.search(body)
        summary_html = summary_match.group(1).strip() if summary_match else ""
        summary_plain = strip_html(summary_html)
        out.append({
            'date': date,
            'date_text': date_text,
            'headline': headline,
            'summary_html': summary_html,
            'summary_plain': summary_plain,
            'body': body,
        })
    return out


def page_template(*, m: dict, prev_link: str, next_link: str) -> str:
    fixed_body = fix_body_links(m['body'])
    headline_safe = m['headline'].replace('"', '&quot;')
    headline_clean = m['headline'][:90]
    page_title = f"{m['date_text']} — CSOH Meeting Recap"
    meta_desc = truncate(m['summary_plain'] or m['headline'], 155)

    pager = []
    if prev_link:
        pager.append(f'<a class="pager-link pager-prev" href="{prev_link}">← Older meeting</a>')
    pager.append('<a class="pager-link pager-index" href="../meetings.html">All meetings</a>')
    if next_link:
        pager.append(f'<a class="pager-link pager-next" href="{next_link}">Newer meeting →</a>')
    pager_html = '\n            '.join(pager)

    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <meta name="description" content="{meta_desc}">
    <meta name="keywords" content="cloud security meeting recap, CSOH, {m['date']}, Friday Zoom, {headline_clean}">
    <title>{page_title}</title>

    <link rel="canonical" href="https://csoh.org/meetings/{m['date']}.html">
    <link rel="alternate" type="application/rss+xml" title="CSOH Cloud Security News" href="/feed.xml">
    <link rel="icon" type="image/png" href="/favicon.png">
    <meta name="theme-color" content="#2c3e50">

    <meta property="og:title" content="{m['date_text']} CSOH Recap — {headline_safe[:80]}">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://csoh.org/meetings/{m['date']}.html">
    <meta property="og:image" content="https://csoh.org/banner.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{m['date_text']} CSOH Recap">
    <meta name="twitter:description" content="{meta_desc}">
    <meta name="twitter:image" content="https://csoh.org/banner.png">

    <link rel="preload" href="/style.css?v=d6c1acef" as="style"
        integrity="sha384-7hiTc0Mm4ki9PsZFtTA83J5GCJ9J5YjGrRZj4m6o8hkDYb3E+wHwMa7Xt0HcOR6W">
    <link rel="stylesheet" href="/style.css?v=d6c1acef"
        integrity="sha384-7hiTc0Mm4ki9PsZFtTA83J5GCJ9J5YjGrRZj4m6o8hkDYb3E+wHwMa7Xt0HcOR6W">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": {(m['headline'] or m['date_text'])!r},
      "description": "{meta_desc}",
      "author": {{
        "@type": "Organization",
        "name": "Cloud Security Office Hours",
        "url": "https://csoh.org/"
      }},
      "publisher": {{
        "@type": "Organization",
        "name": "Cloud Security Office Hours",
        "logo": {{
          "@type": "ImageObject",
          "url": "https://csoh.org/banner.png"
        }}
      }},
      "datePublished": "{m['date']}",
      "dateModified": "{m['date']}",
      "mainEntityOfPage": "https://csoh.org/meetings/{m['date']}.html",
      "image": "https://csoh.org/banner.png",
      "articleSection": "Meeting Recaps"
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{
          "@type": "ListItem",
          "position": 1,
          "name": "Home",
          "item": "https://csoh.org/"
        }},
        {{
          "@type": "ListItem",
          "position": 2,
          "name": "Meeting Recaps",
          "item": "https://csoh.org/meetings.html"
        }},
        {{
          "@type": "ListItem",
          "position": 3,
          "name": {m['date_text']!r},
          "item": "https://csoh.org/meetings/{m['date']}.html"
        }}
      ]
    }}
    </script>
</head>

<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <header>
        <div class="header-content">
            <a href="../index.html" class="logo-link">
                <div class="logo">
                    <div class="logo-title">CSOH</div>
                    <p>Cloud Security Office Hours</p>
                </div>
            </a>
            <button class="hamburger" aria-label="Toggle navigation" aria-expanded="false">☰</button>
            <button class="theme-toggle" aria-label="Switch to dark mode">🌙</button>
            <nav>
                <ul>
                    <li><a href="../index.html">Home</a></li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Learn <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="../what-is-cloud-security.html">What is Cloud Security?</a></li>
                            <li><a href="../learning-path.html">Learning Path</a></li>
                            <li><a href="../cloud-security-best-practices.html">Best Practices</a></li>
                            <li><a href="../shared-responsibility-model.html">Shared Responsibility</a></li>
                            <li><a href="../cspm-vs-cnapp.html">CSPM vs CNAPP</a></li>
                            <li><a href="../resources.html">Resources</a></li>
                            <li><a href="../ctfs.html">CTFs</a></li>
                            <li><a href="../cloud-security-certifications.html">Certifications</a></li>
                            <li><a href="../github-actions.html">GitHub Actions</a></li>
                            <li><a href="../glossary.html">Glossary</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Defend <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="../news.html">News</a></li>
                            <li><a href="../threat-research.html">Threat Research</a></li>
                            <li><a href="../breach-timeline.html">Breach Kill Chains</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle active" aria-expanded="false" aria-haspopup="true">Attend <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="../sessions.html">Zoom Sessions</a></li>
                            <li><a href="../conferences.html">Conferences</a></li>
                            <li><a href="../meetings.html" aria-current="page">Meeting Recaps</a></li>
                            <li><a href="../presentations.html">Presentations</a></li>
                            <li><a href="../chat-resources.html">Chat Resources</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Contribute <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="../contribute.html">Contribute Overview</a></li>
                            <li><a href="../contribute-resources.html">Add a Resource</a></li>
                        </ul>
                    </li>
                    <li><a href="../faq.html">FAQ</a></li>
                    <li><a href="../index.html#about">About</a></li>
                </ul>
            </nav>
        </div>
    </header>

    <nav class="breadcrumb-nav" aria-label="Breadcrumb">
        <ol>
            <li><a href="../index.html">Home</a></li>
            <li><a href="../meetings.html">Meeting Recaps</a></li>
            <li><span aria-current="page">{m['date_text']}</span></li>
        </ol>
    </nav>

    <section class="hero hero--compact">
        <img src="../banner.png" alt="Cloud Security Office Hours Banner" width="1200" height="400" class="hero-img" decoding="async">
        <h1>{m['date_text']} — Meeting Recap</h1>
        <p>{headline_safe}</p>
    </section>

    <main class="container" id="main-content">
        <article class="section meeting-page">
{fixed_body}
        </article>

        <nav class="incident-pager" aria-label="Other meeting recaps">
            {pager_html}
        </nav>
    </main>

    <footer>
        <div class="footer-content">
            <div class="footer-section">
                <h3>Quick Links</h3>
                <ul>
                    <li><a href="../resources.html">All Resources</a></li>
                    <li><a href="../sessions.html">Zoom Sessions</a></li>
                    <li><a href="../presentations.html">Presentations</a></li>
                    <li><a href="../index.html#about">About CSOH</a></li>
                </ul>
            </div>

            <div class="footer-section">
                <h3>Community</h3>
                <ul>
                    <li><a href="mailto:admin@csoh.org">Contact Us</a></li>
                    <li><a href="https://csoh.kit.com/39feb4f397" target="_blank" rel="noopener noreferrer">Zoom Registration</a></li>
                    <li><a href="https://www.paypal.com/biz/profile/cloudsec" target="_blank" rel="noopener noreferrer">Support CSOH</a></li>
                    <li><a href="../code-of-conduct.html">Code of Conduct</a></li>
                    <li><a href="../privacy.html">Privacy Policy</a></li>
                    <li><a href="/feed.xml">RSS Feed</a></li>
                </ul>
            </div>

            <div class="footer-section">
                <h3>Contributing</h3>
                <ul>
                    <li><a href="../contribute-resources.html">Add a Resource</a></li>
                    <li><a href="../contribute.html">General Contributions</a></li>
                    <li><a href="https://github.com/CloudSecurityOfficeHours/csoh.org" target="_blank" rel="noopener noreferrer">GitHub</a></li>
                </ul>
            </div>

            <div class="footer-section">
                <h3>About CSOH</h3>
                <p>Vendor-neutral community for cloud security professionals. Weekly Zoom sessions, 200+ curated resources, and 120+ news articles.</p>
            </div>
        </div>

        <div class="footer-bottom">
            <p>&copy; 2023-2026 Cloud Security Office Hours. All resources provided for educational purposes.</p>
        </div>
    </footer>

    <script src="/main.js?v=16a0410e" integrity="sha384-yKrYcDmXkjnhwLqJrPgzLbWCCQufgcwyWkce0cE3TRVgIFcU436ZzqRL1L+M/NAH"
        defer></script>
</body>

</html>
"""


def index_template(meetings: list[dict]) -> str:
    """Replace meetings.html with a directory page that lists every meeting
    as a card linking to /meetings/<date>.html. Preserves the existing JS
    speaker filter and search by keeping the same overall structure."""
    # Sort newest first
    sorted_meetings = sorted(meetings, key=lambda m: m['date'], reverse=True)

    cards = []
    for m in sorted_meetings:
        teaser = truncate(m['summary_plain'] or m['headline'], 240)
        # Extract tags (year-month + topic tags) from the original article body
        tag_match = re.search(r'<div class="resource-tags meeting-tags">(.*?)</div>',
                              m['body'], re.DOTALL)
        tags_html = tag_match.group(1) if tag_match else ""
        cards.append(f"""        <article class="section meeting-card" id="meeting-{m['date']}">
            <a class="meeting-card-link" href="meetings/{m['date']}.html">
                <h2><time datetime="{m['date']}">{m['date_text']}</time> — {m['headline'].replace('"', '&quot;')}</h2>
                <p class="meeting-card-summary">{teaser}</p>
                <div class="resource-tags meeting-tags">{tags_html}</div>
                <span class="meeting-card-cta">Read recap →</span>
            </a>
        </article>""")

    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <meta name="description" content="Weekly cloud security meeting recaps from CSOH — topic-by-topic notes on AI governance, supply-chain attacks, conferences and community discussions.">
    <meta name="keywords" content="cloud security meeting recaps, CSOH meetings, weekly cloud security, Friday Zoom, AI security, supply chain, cloud incidents">
    <title>Cloud Security Meeting Recaps - Cloud Security Office Hours</title>

    <link rel="canonical" href="https://csoh.org/meetings.html">
    <link rel="alternate" type="application/rss+xml" title="CSOH Cloud Security News" href="/feed.xml">
    <link rel="icon" type="image/png" href="/favicon.png">
    <meta name="theme-color" content="#2c3e50">

    <meta property="og:title" content="Cloud Security Meeting Recaps - CSOH">
    <meta property="og:description" content="Weekly cloud security meeting recaps from CSOH — {len(meetings)} sessions of vendor-neutral practitioner discussion.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://csoh.org/meetings.html">
    <meta property="og:image" content="https://csoh.org/banner.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Cloud Security Meeting Recaps">
    <meta name="twitter:description" content="Weekly cloud security meeting recaps from {len(meetings)} CSOH sessions.">
    <meta name="twitter:image" content="https://csoh.org/banner.png">

    <link rel="preload" href="/style.css?v=d6c1acef" as="style"
        integrity="sha384-7hiTc0Mm4ki9PsZFtTA83J5GCJ9J5YjGrRZj4m6o8hkDYb3E+wHwMa7Xt0HcOR6W">
    <link rel="stylesheet" href="/style.css?v=d6c1acef"
        integrity="sha384-7hiTc0Mm4ki9PsZFtTA83J5GCJ9J5YjGrRZj4m6o8hkDYb3E+wHwMa7Xt0HcOR6W">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "name": "Cloud Security Meeting Recaps",
      "description": "Weekly cloud security meeting recaps — topic-by-topic notes from {len(meetings)} CSOH sessions.",
      "url": "https://csoh.org/meetings.html",
      "isAccessibleForFree": true,
      "inLanguage": "en-US",
      "publisher": {{
        "@type": "Organization",
        "name": "Cloud Security Office Hours",
        "url": "https://csoh.org/",
        "logo": "https://csoh.org/banner.png"
      }}
    }}
    </script>
    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "BreadcrumbList",
      "itemListElement": [
        {{
          "@type": "ListItem",
          "position": 1,
          "name": "Home",
          "item": "https://csoh.org/"
        }},
        {{
          "@type": "ListItem",
          "position": 2,
          "name": "Meeting Recaps",
          "item": "https://csoh.org/meetings.html"
        }}
      ]
    }}
    </script>
</head>

<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>

    <header>
        <div class="header-content">
            <a href="index.html" class="logo-link">
                <div class="logo">
                    <div class="logo-title">CSOH</div>
                    <p>Cloud Security Office Hours</p>
                </div>
            </a>
            <button class="hamburger" aria-label="Toggle navigation" aria-expanded="false">☰</button>
            <button class="theme-toggle" aria-label="Switch to dark mode">🌙</button>
            <nav>
                <ul>
                    <li><a href="index.html">Home</a></li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Learn <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="what-is-cloud-security.html">What is Cloud Security?</a></li>
                            <li><a href="learning-path.html">Learning Path</a></li>
                            <li><a href="cloud-security-best-practices.html">Best Practices</a></li>
                            <li><a href="shared-responsibility-model.html">Shared Responsibility</a></li>
                            <li><a href="cspm-vs-cnapp.html">CSPM vs CNAPP</a></li>
                            <li><a href="resources.html">Resources</a></li>
                            <li><a href="ctfs.html">CTFs</a></li>
                            <li><a href="cloud-security-certifications.html">Certifications</a></li>
                            <li><a href="github-actions.html">GitHub Actions</a></li>
                            <li><a href="glossary.html">Glossary</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Defend <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="news.html">News</a></li>
                            <li><a href="threat-research.html">Threat Research</a></li>
                            <li><a href="breach-timeline.html">Breach Kill Chains</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle active" aria-expanded="false" aria-haspopup="true">Attend <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="sessions.html">Zoom Sessions</a></li>
                            <li><a href="conferences.html">Conferences</a></li>
                            <li><a href="meetings.html" aria-current="page">Meeting Recaps</a></li>
                            <li><a href="presentations.html">Presentations</a></li>
                            <li><a href="chat-resources.html">Chat Resources</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Contribute <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="contribute.html">Contribute Overview</a></li>
                            <li><a href="contribute-resources.html">Add a Resource</a></li>
                        </ul>
                    </li>
                    <li><a href="faq.html">FAQ</a></li>
                    <li><a href="index.html#about">About</a></li>
                </ul>
            </nav>
        </div>
    </header>

    <nav class="breadcrumb-nav" aria-label="Breadcrumb">
        <ol>
            <li><a href="index.html">Home</a></li>
            <li><span aria-current="page">Meeting Recaps</span></li>
        </ol>
    </nav>

    <section class="hero hero--compact">
        <img src="banner.png" alt="Cloud Security Office Hours Banner" width="1200" height="400" class="hero-img" decoding="async">
        <h1>Cloud Security Meeting Recaps</h1>
        <p>Topic-by-topic recaps from {len(meetings)} weekly CSOH sessions. Search by topic or speaker, click any recap to read the full discussion.</p>
    </section>

    <main class="container" id="main-content">
        <section class="section">
            <p class="meeting-count">{len(meetings)} meetings, newest first.</p>
            <div class="search-box">
                <label for="meetingSearch" class="visually-hidden">Search meeting recaps</label>
                <input type="text" id="meetingSearch" placeholder="Search by topic or date — try &quot;AI&quot; or &quot;2026-04&quot;…" autocomplete="off" spellcheck="false">
            </div>
            <p id="noMeetingResults" class="no-results is-hidden">No meetings match your search.</p>
        </section>

        <div class="meeting-list">
{cards_html}
        </div>
    </main>

    <footer>
        <div class="footer-content">
            <div class="footer-section">
                <h3>Quick Links</h3>
                <ul>
                    <li><a href="resources.html">All Resources</a></li>
                    <li><a href="sessions.html">Zoom Sessions</a></li>
                    <li><a href="presentations.html">Presentations</a></li>
                    <li><a href="index.html#about">About CSOH</a></li>
                </ul>
            </div>

            <div class="footer-section">
                <h3>Community</h3>
                <ul>
                    <li><a href="mailto:admin@csoh.org">Contact Us</a></li>
                    <li><a href="https://csoh.kit.com/39feb4f397" target="_blank" rel="noopener noreferrer">Zoom Registration</a></li>
                    <li><a href="https://www.paypal.com/biz/profile/cloudsec" target="_blank" rel="noopener noreferrer">Support CSOH</a></li>
                    <li><a href="/code-of-conduct.html">Code of Conduct</a></li>
                    <li><a href="/privacy.html">Privacy Policy</a></li>
                    <li><a href="/feed.xml">RSS Feed</a></li>
                </ul>
            </div>

            <div class="footer-section">
                <h3>Contributing</h3>
                <ul>
                    <li><a href="contribute-resources.html">Add a Resource</a></li>
                    <li><a href="contribute.html">General Contributions</a></li>
                    <li><a href="https://github.com/CloudSecurityOfficeHours/csoh.org" target="_blank" rel="noopener noreferrer">GitHub</a></li>
                </ul>
            </div>

            <div class="footer-section">
                <h3>About CSOH</h3>
                <p>Vendor-neutral community for cloud security professionals. Weekly Zoom sessions, 200+ curated resources, and 120+ news articles.</p>
            </div>
        </div>

        <div class="footer-bottom">
            <p>&copy; 2023-2026 Cloud Security Office Hours. All resources provided for educational purposes.</p>
        </div>
    </footer>

    <script src="/main.js?v=16a0410e" integrity="sha384-yKrYcDmXkjnhwLqJrPgzLbWCCQufgcwyWkce0cE3TRVgIFcU436ZzqRL1L+M/NAH"
        defer></script>
    <!-- Simple client-side filter — meetings.js had heavier per-topic search;
         here on the index we just filter cards by date / topic / headline text. -->
    <script>
    (function() {{
      const input = document.getElementById('meetingSearch');
      const cards = Array.from(document.querySelectorAll('.meeting-card'));
      const noRes = document.getElementById('noMeetingResults');
      if (!input || !cards.length) return;
      input.addEventListener('input', () => {{
        const q = input.value.toLowerCase().trim();
        let visible = 0;
        cards.forEach(card => {{
          const txt = card.textContent.toLowerCase();
          const match = !q || txt.includes(q);
          card.style.display = match ? '' : 'none';
          if (match) visible++;
        }});
        if (noRes) noRes.classList.toggle('is-hidden', visible !== 0);
      }});
    }})();
    </script>
</body>

</html>
"""


def main() -> int:
    if not SOURCE.exists():
        print(f"missing: {SOURCE}", file=sys.stderr)
        return 1
    html = SOURCE.read_text(encoding="utf-8")

    meetings = parse_meetings(html)
    if not meetings:
        print("no meetings extracted", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Generating {len(meetings)} per-meeting pages in {OUT_DIR.relative_to(REPO_ROOT)}/")

    # Sort chronologically for prev/next pager
    chrono = sorted(meetings, key=lambda m: m['date'])
    for i, m in enumerate(chrono):
        prev_link = f"{chrono[i-1]['date']}.html" if i > 0 else ""
        next_link = f"{chrono[i+1]['date']}.html" if i + 1 < len(chrono) else ""
        page = page_template(m=m, prev_link=prev_link, next_link=next_link)
        out_path = OUT_DIR / f"{m['date']}.html"
        out_path.write_text(page, encoding="utf-8")
    print(f"  ✓ wrote {len(chrono)} pages")

    # Replace meetings.html with the index
    SOURCE.write_text(index_template(meetings), encoding="utf-8")
    print(f"\n✓ Replaced {SOURCE.relative_to(REPO_ROOT)} with index/directory page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
