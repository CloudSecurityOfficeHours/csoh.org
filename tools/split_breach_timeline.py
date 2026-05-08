#!/usr/bin/env python3
"""Split breach-timeline.html into one page per incident.

One-time migration tool. Reads ../breach-timeline.html, extracts every
<div class="incident-panel">, and writes:

  ../breaches/<slug>.html     — full standalone page for each incident
  ../breach-timeline.html     — replaced with an index page that lists all
                                breaches with cards linking to the per-page
                                URLs (kept as the index URL for inbound-link
                                stability)

Re-runnable: re-running regenerates all per-breach pages from the (already
split) state plus a fresh index. The breach-timeline.html input is the
reference each time, so this only really makes sense to run on the
pre-split source. After the migration, future edits go directly to the
per-breach pages.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "breach-timeline.html"
OUT_DIR = REPO_ROOT / "breaches"

# Pretty slugs for cleaner URLs (drop year suffixes, expand abbreviations)
SLUG_MAP = {
    "capital-one":      "capital-one",
    "uber-2022":        "uber",
    "storm-0558":       "storm-0558",
    "solarwinds":       "solarwinds",
    "ms-sas":           "microsoft-sas-leak",
    "mitnick-novell":   "mitnick-novell",
    "scattered-spider": "scattered-spider-mgm",
    "promptware-2024":  "promptware",
    "snowflake-2024":   "snowflake-unc5537",
    "lastpass-2022":    "lastpass",
}

# Tab nav data → metadata for index cards (year, display name, provider chip)
TAB_RE = re.compile(
    r'<button class="itab[^"]*" data-panel="([^"]+)" data-year="(\d+)"[^>]*>'
    r'(.*?)</button>',
    re.DOTALL,
)
TAB_TEXT_PROV_RE = re.compile(
    r'^(.*?)\s*<span class="itab-prov ([^"]*)">([^<]+)</span>',
    re.DOTALL,
)
# Panel boundaries: each panel starts with `<div id="..." class="incident-panel"`
# Use the START of the next panel (or the closing of <main>) to bound each.
PANEL_START_RE = re.compile(
    r'<div id="([^"]+)" class="incident-panel(?: active)?" role="tabpanel">',
)
TITLE_RE = re.compile(r'<h2 class="inc-title">([^<]+)</h2>')
SUMMARY_RE = re.compile(r'<p class="inc-summary">(.*?)</p>', re.DOTALL)


def strip_html(s: str) -> str:
    """Remove HTML tags for a plain-text excerpt (used in meta descriptions)."""
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 1].rsplit(" ", 1)[0] + "…"


def parse_tabs(html: str) -> list[dict]:
    """Return one dict per incident, in the source order, with metadata."""
    out: list[dict] = []
    for m in TAB_RE.finditer(html):
        panel_id = m.group(1)
        year = m.group(2)
        inner = m.group(3)
        text_match = TAB_TEXT_PROV_RE.match(inner)
        if text_match:
            display = text_match.group(1).strip()
            prov_class = text_match.group(2)
            prov_label = text_match.group(3)
        else:
            display = strip_html(inner)
            prov_class = ""
            prov_label = ""
        out.append({
            "panel_id": panel_id,
            "year": year,
            "display_name": display,
            "prov_class": prov_class,
            "prov_label": prov_label,
            "slug": SLUG_MAP.get(panel_id, panel_id),
        })
    return sorted(out, key=lambda d: int(d["year"]))


def extract_panels(html: str) -> dict[str, str]:
    """Return {panel_id: panel_inner_html} for each incident.

    Uses position-based slicing: each panel runs from its opening
    `<div id=... class="incident-panel"...>` through the matched closing
    `</div>` just before the NEXT such opening (or the end of <main>).
    Robust against missing section-break comments.
    """
    starts = [(m.start(), m.end(), m.group(1)) for m in PANEL_START_RE.finditer(html)]
    if not starts:
        return {}

    # Where does the kc-main / panels region end?
    end_marker = re.search(r'\n</main>', html)
    region_end = end_marker.start() if end_marker else len(html)

    panels: dict[str, str] = {}
    for i, (s, e_open, panel_id) in enumerate(starts):
        # Inner content starts right after the opening <div ...>
        inner_start = e_open
        # Inner content ends at the boundary just before the next panel,
        # or at region_end for the last panel. Then we trim back to the
        # last `</div>` so we don't include the closing wrapper of THIS panel.
        next_boundary = starts[i + 1][0] if i + 1 < len(starts) else region_end
        chunk = html[inner_start:next_boundary]

        # The panel's own closing </div> is the last </div> at column 0
        # (i.e., on its own line, not nested). Find by scanning backwards
        # from the boundary for a `\n</div>\n` pattern.
        close_match = list(re.finditer(r'\n</div>\n', chunk))
        if close_match:
            inner_end = close_match[-1].start()
            panels[panel_id] = chunk[:inner_end]
        else:
            # Fallback: take the whole chunk minus trailing whitespace
            panels[panel_id] = chunk.rstrip()
    return panels


def title_for(panel_html: str, fallback: str) -> str:
    m = TITLE_RE.search(panel_html)
    return m.group(1).strip() if m else fallback


def summary_for(panel_html: str) -> str:
    m = SUMMARY_RE.search(panel_html)
    return m.group(1) if m else ""


def page_template(*, slug: str, panel_id: str, year: str, display_name: str,
                  inc_title: str, summary_html: str, panel_html: str,
                  prev_link: str, next_link: str) -> str:
    """Build the full HTML page for a single incident."""
    summary_plain = strip_html(summary_html)
    meta_desc = truncate(summary_plain, 155)
    short_title = display_name  # used in <title>
    page_title = f"{short_title} ({year}) Breach Kill Chain - CSOH"

    pager_links = []
    if prev_link:
        pager_links.append(f'<a class="pager-link pager-prev" href="{prev_link}">← Previous breach</a>')
    pager_links.append('<a class="pager-link pager-index" href="../breach-timeline.html">All breaches</a>')
    if next_link:
        pager_links.append(f'<a class="pager-link pager-next" href="{next_link}">Next breach →</a>')
    pager_html = '\n            '.join(pager_links)

    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <meta name="description" content="{meta_desc}">
    <meta name="keywords" content="{display_name}, breach analysis, kill chain, MITRE ATT&CK, cloud security incident, post-mortem, {year}">
    <title>{page_title}</title>

    <link rel="canonical" href="https://csoh.org/breaches/{slug}.html">
    <link rel="alternate" type="application/rss+xml" title="CSOH Cloud Security News" href="/feed.xml">
    <link rel="icon" type="image/png" href="/favicon.png">
    <meta name="theme-color" content="#2c3e50">

    <meta property="og:title" content="{short_title} ({year}) Breach Kill Chain">
    <meta property="og:description" content="{meta_desc}">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://csoh.org/breaches/{slug}.html">
    <meta property="og:image" content="https://csoh.org/banner.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{short_title} ({year}) Breach Kill Chain">
    <meta name="twitter:description" content="{meta_desc}">
    <meta name="twitter:image" content="https://csoh.org/banner.png">

    <link rel="preload" href="/style.css?v=d6c1acef" as="style"
        integrity="sha384-7hiTc0Mm4ki9PsZFtTA83J5GCJ9J5YjGrRZj4m6o8hkDYb3E+wHwMa7Xt0HcOR6W">
    <link rel="stylesheet" href="/style.css?v=d6c1acef"
        integrity="sha384-7hiTc0Mm4ki9PsZFtTA83J5GCJ9J5YjGrRZj4m6o8hkDYb3E+wHwMa7Xt0HcOR6W">
    <link rel="stylesheet" href="/breach-timeline.css">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "Article",
      "headline": {inc_title!r},
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
      "datePublished": "{year}-01-01",
      "dateModified": "2026-04-30",
      "mainEntityOfPage": "https://csoh.org/breaches/{slug}.html",
      "image": "https://csoh.org/banner.png",
      "articleSection": "Cloud Security Breach Analysis"
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
          "name": "Breach Kill Chains",
          "item": "https://csoh.org/breach-timeline.html"
        }},
        {{
          "@type": "ListItem",
          "position": 3,
          "name": {short_title!r},
          "item": "https://csoh.org/breaches/{slug}.html"
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
                            <li><a href="../resources.html">Resources</a></li>
                            <li><a href="../ctfs.html">CTFs</a></li>
                            <li><a href="../cloud-security-certifications.html">Certifications</a></li>
                            <li><a href="../github-actions.html">GitHub Actions</a></li>
                            <li><a href="../glossary.html">Glossary</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle active" aria-expanded="false" aria-haspopup="true">Defend <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="../news.html">News</a></li>
                            <li><a href="../threat-research.html">Threat Research</a></li>
                            <li><a href="../breach-timeline.html" aria-current="page">Breach Kill Chains</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Attend <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="../sessions.html">Zoom Sessions</a></li>
                            <li><a href="../conferences.html">Conferences</a></li>
                            <li><a href="../meetings.html">Meeting Recaps</a></li>
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
            <li><a href="../breach-timeline.html">Breach Kill Chains</a></li>
            <li><span aria-current="page">{short_title}</span></li>
        </ol>
    </nav>

    <section class="hero hero--compact">
        <img src="../banner.png" alt="Cloud Security Office Hours Banner" width="1200" height="400" class="hero-img" decoding="async">
        <h1>{short_title} — {year}</h1>
        <p>Step-by-step kill chain mapped to MITRE ATT&amp;CK Cloud, sourced from official post-mortems and primary technical analyses.</p>
    </section>

    <main class="kc-main kc-page" id="main-content">
        <div class="incident-panel active" role="article" id="{panel_id}">
{panel_html}
        </div>

        <nav class="incident-pager" aria-label="Other breach kill chains">
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


def index_page_template(incidents: list[dict], panels: dict[str, str]) -> str:
    """Build the new breach-timeline.html — an index/directory of breaches."""
    cards = []
    for inc in incidents:
        panel_html = panels[inc["panel_id"]]
        title = title_for(panel_html, inc["display_name"])
        summary_html = summary_for(panel_html)
        summary_plain = strip_html(summary_html)
        teaser = truncate(summary_plain, 240)

        # Pull severity badge if present in the panel
        sev_match = re.search(r'<span class="sev-badge sev-([a-z]+)">([^<]+)</span>', panel_html)
        sev_html = (
            f'<span class="sev-badge sev-{sev_match.group(1)}">{sev_match.group(2)}</span>'
            if sev_match else ""
        )

        prov_chip = (
            f'<span class="prov-tag {inc["prov_class"]}">{inc["prov_label"]}</span>'
            if inc["prov_class"] else ""
        )

        cards.append(f"""        <li class="breach-card" id="{inc['panel_id']}">
            <a class="breach-card-link" href="breaches/{inc['slug']}.html">
                <div class="breach-card-meta">
                    <span class="inc-year">{inc['year']}</span>
                    {sev_html}
                    {prov_chip}
                </div>
                <h2 class="breach-card-title">{title}</h2>
                <p class="breach-card-summary">{teaser}</p>
                <span class="breach-card-cta">Read kill chain →</span>
            </a>
        </li>""")

    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="index, follow, max-snippet:-1, max-image-preview:large">
    <meta name="description" content="Step-by-step cloud security breach kill chains mapped to MITRE ATT&CK Cloud — Capital One, SolarWinds, MGM, Snowflake and more, vendor-neutral.">
    <meta name="keywords" content="cloud security breaches, kill chains, MITRE ATT&CK Cloud, Capital One breach, SolarWinds, Storm-0558, Scattered Spider, MGM hack, Snowflake UNC5537, LastPass, Uber breach">
    <title>Cloud Breach Kill Chains - Cloud Security Office Hours</title>

    <link rel="canonical" href="https://csoh.org/breach-timeline.html">
    <link rel="alternate" type="application/rss+xml" title="CSOH Cloud Security News" href="/feed.xml">
    <link rel="icon" type="image/png" href="/favicon.png">
    <meta name="theme-color" content="#2c3e50">

    <meta property="og:title" content="Cloud Breach Kill Chains - CSOH">
    <meta property="og:description" content="Step-by-step cloud security breach kill chains mapped to MITRE ATT&CK Cloud — Capital One, SolarWinds, MGM, Snowflake and more, vendor-neutral.">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://csoh.org/breach-timeline.html">
    <meta property="og:image" content="https://csoh.org/banner.png">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="Cloud Breach Kill Chains">
    <meta name="twitter:description" content="Step-by-step cloud security breach kill chains mapped to MITRE ATT&CK Cloud.">
    <meta name="twitter:image" content="https://csoh.org/banner.png">

    <link rel="preload" href="/style.css?v=d6c1acef" as="style"
        integrity="sha384-7hiTc0Mm4ki9PsZFtTA83J5GCJ9J5YjGrRZj4m6o8hkDYb3E+wHwMa7Xt0HcOR6W">
    <link rel="stylesheet" href="/style.css?v=d6c1acef"
        integrity="sha384-7hiTc0Mm4ki9PsZFtTA83J5GCJ9J5YjGrRZj4m6o8hkDYb3E+wHwMa7Xt0HcOR6W">
    <link rel="stylesheet" href="/breach-timeline.css">

    <script type="application/ld+json">
    {{
      "@context": "https://schema.org",
      "@type": "CollectionPage",
      "name": "Cloud Breach Kill Chains",
      "description": "A vendor-neutral library of cloud security breach kill chains, mapped to MITRE ATT&CK Cloud.",
      "url": "https://csoh.org/breach-timeline.html",
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
          "name": "Breach Kill Chains",
          "item": "https://csoh.org/breach-timeline.html"
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
                            <li><a href="resources.html">Resources</a></li>
                            <li><a href="ctfs.html">CTFs</a></li>
                            <li><a href="cloud-security-certifications.html">Certifications</a></li>
                            <li><a href="github-actions.html">GitHub Actions</a></li>
                            <li><a href="glossary.html">Glossary</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle active" aria-expanded="false" aria-haspopup="true">Defend <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="news.html">News</a></li>
                            <li><a href="threat-research.html">Threat Research</a></li>
                            <li><a href="breach-timeline.html" aria-current="page">Breach Kill Chains</a></li>
                        </ul>
                    </li>
                    <li class="has-dropdown">
                        <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Attend <span class="caret" aria-hidden="true">▾</span></button>
                        <ul class="dropdown-menu">
                            <li><a href="sessions.html">Zoom Sessions</a></li>
                            <li><a href="conferences.html">Conferences</a></li>
                            <li><a href="meetings.html">Meeting Recaps</a></li>
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
            <li><span aria-current="page">Breach Kill Chains</span></li>
        </ol>
    </nav>

    <section class="hero hero--compact">
        <img src="banner.png" alt="Cloud Security Office Hours Banner" width="1200" height="400" class="hero-img" decoding="async">
        <h1>Cloud Breach Kill Chains</h1>
        <p>Real attacks. Real post-mortems. Step-by-step attack progression mapped to MITRE ATT&amp;CK Cloud — so you can understand exactly what happened, and stop it next time.</p>
        <div class="hero-chips">
            <span class="hero-chip chip-mitre">MITRE ATT&amp;CK Cloud Mapped</span>
            <span class="hero-chip chip-steps">Full Attack Chain Per Incident</span>
            <span class="hero-chip chip-src">Official Post-Mortems Sourced</span>
        </div>
    </section>

    <div class="container" style="padding-top:1.5rem; padding-bottom:0;">
        <div class="info-box--blue">
            <p><strong>Want to practice these techniques?</strong> Try the <a href="ctfs.html">cloud security CTF challenges</a> — many cover the same attack patterns (SSRF, IAM exploitation, token abuse). Unfamiliar with terms like IMDSv2, OIDC, or Golden SAML? See the <a href="glossary.html">cloud security glossary</a>. For broader context on threat actors and trends, browse the <a href="threat-research.html">cloud threat research directory</a> or the <a href="what-is-cloud-security.html">cloud security overview</a>.</p>
        </div>
    </div>

    <main class="container kc-page" id="main-content">
        <ul class="breach-list" role="list">
{cards_html}
        </ul>
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
</body>

</html>
"""


def main() -> int:
    if not SOURCE.exists():
        print(f"missing: {SOURCE}", file=sys.stderr)
        return 1
    html = SOURCE.read_text(encoding="utf-8")

    incidents = parse_tabs(html)
    panels = extract_panels(html)
    if len(panels) != len(incidents):
        print(f"warning: {len(incidents)} tabs vs {len(panels)} panels", file=sys.stderr)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Sort by year for prev/next pager links
    print(f"Generating {len(incidents)} per-breach pages in {OUT_DIR.relative_to(REPO_ROOT)}/")
    for i, inc in enumerate(incidents):
        if inc["panel_id"] not in panels:
            print(f"  ✗ {inc['panel_id']}: panel not found")
            continue
        panel_html = panels[inc["panel_id"]]
        inc_title = title_for(panel_html, inc["display_name"])
        summary_html = summary_for(panel_html)

        prev_link = ""
        next_link = ""
        if i > 0:
            prev_link = incidents[i - 1]["slug"] + ".html"
        if i + 1 < len(incidents):
            next_link = incidents[i + 1]["slug"] + ".html"

        # Strip the ` active` from the wrapping panel — each per-page has its
        # own <div class="incident-panel active"> wrapper applied by template.
        # Also remove the outer <div id=...> wrap because the template adds its
        # own. Actually — simpler: just keep the inner contents (header +
        # kill-chain). Pull just everything between the open tag and close tag
        # of the panel, which is what `panels[id]` already gives us.

        page = page_template(
            slug=inc["slug"],
            panel_id=inc["panel_id"],
            year=inc["year"],
            display_name=inc["display_name"],
            inc_title=inc_title,
            summary_html=summary_html,
            panel_html=panel_html,
            prev_link=prev_link,
            next_link=next_link,
        )

        out_path = OUT_DIR / f"{inc['slug']}.html"
        out_path.write_text(page, encoding="utf-8")
        print(f"  ✓ {out_path.relative_to(REPO_ROOT)}")

    # Now write the new breach-timeline.html (the index)
    index_html = index_page_template(incidents, panels)
    SOURCE.write_text(index_html, encoding="utf-8")
    print(f"\n✓ Replaced {SOURCE.relative_to(REPO_ROOT)} with index/directory page")
    return 0


if __name__ == "__main__":
    sys.exit(main())
