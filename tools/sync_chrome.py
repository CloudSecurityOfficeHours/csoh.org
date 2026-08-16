#!/usr/bin/env python3
"""Stamp ONE canonical nav, header buttons, and footer onto every HTML page.

Why this exists
---------------
The nav and footer are hand-copied into each of ~233 static pages (no
templating). Over time they drifted: the breaches/ and meetings/ pages still
carried an older, smaller nav; a couple of root pages had stray extra items;
the footer's "About CSOH" link was present on some pages and missing on
others. This script makes the menu nav, the two header buttons (hamburger and
theme toggle), and the footer *byte-identical* everywhere, with only two
legitimate per-page differences preserved (both apply to the nav/footer only;
the header buttons are the same two lines on every page):

  1. `../` path prefixes on pages inside breaches/, meetings/, portfolio/,
     and homelab/.
  2. The current-page markers (`aria-current="page"` on the active link and
     the `active` class on its dropdown toggle).

It replaces three older scripts (sync_navs.py, redesign_nav.py, unify_footer.py)
that encoded an earlier nav design and were removed in favor of this one. Run
from the repo root:

    python3 tools/sync_chrome.py

It is idempotent: running it twice changes nothing the second time.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# --- Canonical logo block (first child of .header-content) -------------------
# The logo was the last piece of the header nothing stamped, and it had drifted
# into four shapes. Snapshot of the damage at the time this was written, when
# the site was 222 pages (it is ~233 now - the shape of the problem is the
# point, not the exact counts):
#
#   126 pages (breaches/, meetings/)  <a href="../index.html"> with NO logo mark
#    87 pages                         <a href="index.html"> wrapping svg + .logo
#     8 pages                         this shape
#     1 page  (index.html)            as above, different whitespace
#
# Two things fall out of that. Over half the site was missing the cloud mark
# entirely. And the wrapping shapes put the svg *beside* the tagline, making the
# block 231px instead of 185px - 46px that decided whether the theme toggle fit
# on the header's one line, which is why the wrap appeared on some pages and not
# others.
#
# This shape is the one the CSS is written for: `.logo` is the flex column,
# `.logo .logo-title` and `.logo p` are its descendants, and the tagline sits
# outside the link (clicking "Cloud Security Office Hours" shouldn't navigate).
# href="/" is root-relative, so unlike the nav this needs no ../ prefixing on
# subdirectory pages - add_prefix() skips it. Keep the 12-space indent;
# LOGO_PATTERN consumes the existing indentation so this controls it fully.
CANON_LOGO = '''\
            <div class="logo">
                <a href="/" class="logo-link">
                    <svg class="logo-mark" viewBox="0 0 32 32" width="32" height="32" role="img" aria-label="CSOH logo"><defs><linearGradient id="lm-cloud" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#7dd3fc"/><stop offset="100%" stop-color="#0284c7"/></linearGradient></defs><path d="M7 19 a4 4 0 0 1 4-4 a6 6 0 0 1 11 0 a3.5 3.5 0 0 1 3.5 3.5 a3.5 3.5 0 0 1 -3.5 3.5 H8 a3.5 3.5 0 0 1 -1-7 z" fill="url(#lm-cloud)"/><path d="M11 13 L21 13 L21 18 a5 5.5 0 0 1 -5 5 a5 5.5 0 0 1 -5 -5 z" fill="#f59e0b"/><path d="M13.5 16.7 L15.3 18.4 L18.6 15" stroke="#fff" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>
                    <div class="logo-title">CSOH</div>
                </a>
                <p>Cloud Security Office Hours</p>
            </div>'''

# --- Canonical header buttons (between the logo and the nav) -----------------
# The hamburger and theme toggle live in every header but belong to neither the
# <nav> block nor the <footer>, so nothing enforced them and they drifted:
# about.html and rss.html picked up HTML-entity glyphs (&#9776; / &#127769;)
# that the June 2026 docs review (PR #953) had to patch by hand. Stamping them
# here keeps both lines byte-identical everywhere, same as the nav and footer.
# They contain no links and no active state, so unlike the nav/footer there are
# no per-page differences: no ../ prefixing, no current-page markers. Keep the
# 12-space indent; the button patterns below consume the existing indentation
# so these lines control it fully.
CANON_HAMBURGER = '            <button class="hamburger" aria-label="Toggle navigation" aria-expanded="false">☰</button>'
CANON_THEME_TOGGLE = '            <button class="theme-toggle" aria-label="Switch to dark mode">🌙</button>'

# --- Canonical menu nav (root-relative, no active markers) -------------------
# Top level: Learn / Resources / Threat Intel / Careers / Community, then the
# Support + Join Friday Zoom pair (main.js injects "Search" ahead of them).
#
# "By Cloud" used to be a sixth top-level dropdown. It moved into Learn as a
# column: with it in the bar, logo + nav came to 1140px inside a 1136px content
# box, so the theme toggle wrapped to its own line on any page whose logo
# markup is the wider variant. Its 4 links are a natural Learn column, and
# folding them in buys ~95px of slack rather than shaving pixels.
#
# Keep the 12-space indent; NAV_PATTERN below consumes the existing
# indentation so this controls it fully.
CANON_NAV = """\
            <nav>
                <ul>
                    <li class="has-dropdown has-mega">
                      <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Learn <span class="caret" aria-hidden="true">▾</span></button>
                      <div class="dropdown-menu mega-menu mega-6col">
                        <div class="mega-col">
                          <span class="mega-heading">Foundations</span>
                          <ul>
                            <li><a href="what-is-cloud-security.html">What is Cloud Security?</a></li>
                            <li><a href="shared-responsibility-model.html">Shared Responsibility</a></li>
                            <li><a href="cspm-vs-cnapp.html">CSPM vs CNAPP</a></li>
                            <li><a href="cloud-security-best-practices.html">Best Practices</a></li>
                            <li><a href="vendor-landscape.html">Vendor Landscape</a></li>
                            <li><a href="glossary.html">Glossary</a></li>
                            <li><a href="faq.html">FAQ</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">By Cloud</span>
                          <ul>
                            <li><a href="aws-security.html">AWS Security</a></li>
                            <li><a href="azure-security.html">Azure Security</a></li>
                            <li><a href="gcp-security.html">GCP Security</a></li>
                            <li><a href="cloud-security-comparison.html">AWS vs Azure vs GCP</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">Workloads &amp; Platform</span>
                          <ul>
                            <li><a href="containers.html">Containers</a></li>
                            <li><a href="kubernetes.html">Kubernetes</a></li>
                            <li><a href="serverless.html">Serverless</a></li>
                            <li><a href="service-mesh-security.html">Service Mesh</a></li>
                            <li><a href="ci-cd.html">CI/CD</a></li>
                            <li class="mega-featured"><a href="what-practitioners-think-about-supply-chain-security.html">What Practitioners Think About Supply Chain<span class="mega-tag">From the Friday sessions</span></a></li>
                            <li><a href="landing-zones.html">Landing Zones</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">Security Domains</span>
                          <ul>
                            <li><a href="iam.html">IAM &amp; Identity</a></li>
                            <li><a href="non-human-identity.html">Non-Human Identity</a></li>
                            <li><a href="zero-trust.html">Zero Trust</a></li>
                            <li><a href="network-security.html">Network Security</a></li>
                            <li><a href="data-security.html">Data Security &amp; KMS</a></li>
                            <li><a href="vulnerability-management.html">Vulnerability Management</a></li>
                            <li class="mega-featured"><a href="what-practitioners-think-about-vulnerability-management.html">What Practitioners Think About Vuln Mgmt<span class="mega-tag">From the Friday sessions</span></a></li>
                            <li><a href="api-security.html">API Security</a></li>
                            <li><a href="saas-security.html">SaaS Security (SSPM)</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">Governance &amp; AI</span>
                          <ul>
                            <li><a href="backup-dr.html">Backup, DR &amp; Ransomware</a></li>
                            <li><a href="threat-modeling.html">Threat Modeling</a></li>
                            <li><a href="grc.html">GRC</a></li>
                            <li><a href="compliance-frameworks.html">Compliance Frameworks</a></li>
                            <li class="mega-featured"><a href="what-practitioners-think-about-security-regulation.html">What Practitioners Think About Regulation<span class="mega-tag">From the Friday sessions</span></a></li>
                            <li><a href="ai-learning.html">AI Learning</a></li>
                            <li><a href="ai-ml-security.html">AI/ML Security</a></li>
                            <li><a href="mcp-security.html">MCP Security</a></li>
                            <li class="mega-featured"><a href="what-practitioners-think-about-ai-security.html">What Practitioners Think About AI<span class="mega-tag">From the Friday sessions</span></a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">Build It</span>
                          <ul>
                            <li class="mega-featured"><a href="cloud-deployment.html">Multi-Cloud Secure Deploy<span class="mega-tag">AWS &middot; GCP &middot; Azure, end to end</span></a></li>
                            <li><a href="github-actions.html">GitHub Actions</a></li>
                            <li><a href="terraform.html">Terraform</a></li>
                            <li><a href="version-control.html">Git &amp; Version Control</a></li>
                          </ul>
                        </div>
                      </div>
                    </li>
                    <li><a href="resources.html">Resources</a></li>
                    <li class="has-dropdown">
                      <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Threat Intel <span class="caret" aria-hidden="true">▾</span></button>
                      <ul class="dropdown-menu">
                        <li><a href="news.html">News</a></li>
                        <li><a href="threat-research.html">Threat Research</a></li>
                        <li><a href="breach-timeline.html">Breach Kill Chains</a></li>
                        <li><a href="cloud-breach-year-in-review.html">Year in Review</a></li>
                        <li><a href="cloud-soc.html">Cloud SOC</a></li>
                        <li><a href="detection-engineering.html">Detection Engineering</a></li>
                        <li><a href="incident-response.html">Incident Response</a></li>
                        <li><a href="cloud-pentesting.html">Cloud Pentesting</a></li>
                        <li><a href="ctfs.html">CTFs</a></li>
                      </ul>
                    </li>
                    <li class="has-dropdown has-mega">
                      <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Careers <span class="caret" aria-hidden="true">▾</span></button>
                      <div class="dropdown-menu mega-menu mega-3col">
                        <div class="mega-col">
                          <span class="mega-heading">Getting Started</span>
                          <ul>
                            <li><a href="cloud-security-careers.html">Careers Overview</a></li>
                            <li><a href="breaking-into-cloud-security.html">Breaking In</a></li>
                            <li class="mega-featured"><a href="what-breaking-into-cloud-security-really-takes.html">What Breaking In Really Takes<span class="mega-tag">From the Friday sessions</span></a></li>
                            <li><a href="learning-path.html">Learning Path</a></li>
                            <li><a href="cloud-security-certifications.html">Certifications</a></li>
                            <li><a href="cloud-security-degree-programs.html">Degree Programs</a></li>
                            <li><a href="cloud-security-home-lab.html">Home Lab</a></li>
                            <li><a href="cloud-security-portfolio-projects.html">Portfolio Projects</a></li>
                            <li><a href="cloud-security-reading-list.html">Reading List</a></li>
                            <li><a href="cloud-security-interview-questions.html">Interview Questions</a></li>
                            <li><a href="cloud-security-resume-guide.html">Resume Guide</a></li>
                            <li><a href="mentorship.html">Mentorship</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">Engineering Roles</span>
                          <ul>
                            <li><a href="cloud-security-engineer.html">Cloud Security Engineer</a></li>
                            <li><a href="cloud-security-architect.html">Security Architect</a></li>
                            <li><a href="cloud-security-platform-engineer.html">Platform / Security SRE</a></li>
                            <li><a href="cloud-security-appsec-engineer.html">AppSec / IaC Engineer</a></li>
                            <li><a href="cloud-security-cnapp-analyst.html">CSPM / CNAPP Analyst</a></li>
                            <li><a href="cloud-security-iam-architect.html">IAM / Identity Architect</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">Specialist &amp; Field Roles</span>
                          <ul>
                            <li><a href="cloud-security-detection-engineer.html">Detection Engineer</a></li>
                            <li><a href="cloud-security-incident-responder.html">Incident Responder (DFIR)</a></li>
                            <li><a href="cloud-security-penetration-tester.html">Penetration Tester / Red Team</a></li>
                            <li><a href="cloud-security-grc-engineer.html">GRC / Compliance Engineer</a></li>
                            <li><a href="cloud-security-sales-engineer.html">Sales Engineer</a></li>
                            <li><a href="cloud-security-customer-success-engineer.html">Customer Success Engineer</a></li>
                          </ul>
                        </div>
                      </div>
                    </li>
                    <li class="has-dropdown has-mega">
                      <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Community <span class="caret" aria-hidden="true">▾</span></button>
                      <div class="dropdown-menu mega-menu mega-3col">
                        <div class="mega-col">
                          <span class="mega-heading">Live</span>
                          <ul>
                            <li><a href="sessions.html">Friday Zoom Sessions</a></li>
                            <li><a href="community.html">Community &amp; Signal</a></li>
                            <li><a href="mentorship.html">Mentorship</a></li>
                            <li><a href="conferences.html">Conferences</a></li>
                            <li class="mega-featured"><a href="what-practitioners-think-about-security-conferences.html">What Practitioners Think About Conferences<span class="mega-tag">From the Friday sessions</span></a></li>
                            <li><a href="present.html">Present at CSOH</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">Archive</span>
                          <ul>
                            <li><a href="meetings.html">Meeting Recaps</a></li>
                            <li class="mega-featured"><a href="what-practitioners-think.html">What Practitioners Think<span class="mega-tag">All the session digests</span></a></li>
                            <li><a href="presentations.html">Presentations</a></li>
                            <li><a href="speakers.html">Guest Speakers</a></li>
                            <li><a href="chat-resources.html">Chat Resources</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">Connect</span>
                          <ul>
                            <li><a href="mailto:admin@csoh.org">Contact</a></li>
                            <li><a href="https://csoh.kit.com/39feb4f397" target="_blank" rel="noopener noreferrer">Mailing List</a></li>
                            <li><a href="https://github.com/CloudSecurityOfficeHours/csoh.org" target="_blank" rel="noopener noreferrer">GitHub</a></li>
                            <li><a href="rss.html">RSS Feed</a></li>
                            <li><a href="contribute.html">Contribute</a></li>
                            <li><a href="contribute-resources.html">Add a Resource</a></li>
                          </ul>
                        </div>
                      </div>
                    </li>
                    <li class="nav-coffee-item"><a href="https://buymeacoffee.com/csoh" class="nav-coffee" target="_blank" rel="noopener noreferrer" title="Support CSOH on Buy Me a Coffee" aria-label="Support CSOH on Buy Me a Coffee"><span class="nav-coffee-icon" aria-hidden="true">☕</span> <span class="nav-coffee-label">Support</span></a></li>
                    <li class="nav-cta-item"><a href="https://csoh.kit.com/39feb4f397" class="nav-cta" target="_blank" rel="noopener noreferrer">Join Friday Zoom →</a></li>
                </ul>
            </nav>"""

# --- Canonical footer (root-relative) ----------------------------------------
# The CSOH blurb, the Buy Me a Coffee ask beside it, and the legal row.
#
# It used to carry "Explore", "Developer Docs" and "Connect" as link columns.
# All three now live in the top nav, which is reachable from every page and does
# not require scrolling to the bottom: Developer Docs was already duplicated in
# Learn > Build It, 5 of Explore's 7 links were already top-level items, and
# Connect moved into Community as its own column. Nothing is orphaned - see the
# inbound-link check in the commit that moved each one.
#
# That left the blurb alone on a wide row, so the coffee ask takes the other
# half. Unlike the nav's deliberately quiet outline link, this one is a filled
# button: someone who has scrolled to the bottom has read the whole page, and
# there is no Zoom CTA down here for it to compete with.
#
# Keep the 2-space indent; FOOTER_PATTERN consumes the existing indentation.
CANON_FOOTER = """\
  <footer>
    <div class="footer-content">
      <div class="footer-section footer-about">
        <h3>CSOH</h3>
        <p>A vendor-neutral community for cloud security professionals. Weekly Zoom sessions and curated resources.</p>
      </div>
      <div class="footer-section footer-support">
        <h3>Support CSOH</h3>
        <p>Free since 2023, and staying that way. If it has helped you, a coffee covers the hosting.</p>
        <a href="https://buymeacoffee.com/csoh" class="footer-coffee" target="_blank" rel="noopener noreferrer"><span class="footer-coffee-icon" aria-hidden="true">&#9749;</span> Buy me a coffee</a>
      </div>
    </div>
    <div class="footer-bottom">
      <p>&copy; 2023-2026 Cloud Security Office Hours</p>
      <ul class="footer-legal">
        <li><a href="about.html">About</a></li>
        <li><a href="privacy.html">Privacy</a></li>
        <li><a href="code-of-conduct.html">Code of Conduct</a></li>
        <li><a href="security-policy.html">Security</a></li>
      </ul>
    </div>
  </footer>"""

# Match the menu nav: an open `<nav>` (no class attr) wrapping a <ul>. The
# breadcrumb uses `<nav class="breadcrumb-nav">` and won't match. Leading
# indentation is consumed so the replacement controls indent fully.
NAV_PATTERN = re.compile(r'(?m)^[ \t]*<nav>\s*<ul>[\s\S]*?</ul>\s*</nav>')
FOOTER_PATTERN = re.compile(r'(?m)^[ \t]*<footer>[\s\S]*?</footer>')

# Match a whole header-button line whatever its attribute drift or glyph
# encoding (literal vs HTML entity). The nav's dropdown buttons use different
# classes (dropdown-toggle) and never match. Leading indentation is consumed
# so the canonical lines control it, same as nav/footer.
# Match the logo block: everything between the .header-content open tag and the
# hamburger button that follows it. Anchoring on those two fixed landmarks -
# rather than on the logo's own markup - is what lets one pattern catch all four
# drifted shapes (with and without the svg, <a>-wrapped and <div>-wrapped). The
# open tag is kept via a capture group; the leading indentation of the block
# itself is consumed so CANON_LOGO controls it fully.
LOGO_PATTERN = re.compile(
    r'(?ms)(<div class="header-content">\n)[ \t]*.*?\n(?=[ \t]*<button[^>]*class="hamburger")')

HAMBURGER_PATTERN = re.compile(
    r'(?m)^[ \t]*<button[^>]*class="hamburger"[^>]*>[^<]*</button>')
THEME_TOGGLE_PATTERN = re.compile(
    r'(?m)^[ \t]*<button[^>]*class="theme-toggle"[^>]*>[^<]*</button>')

# Build href -> enclosing top-level dropdown label, by scanning CANON_NAV.
# Each dropdown <button> starts a new section; every page href that follows
# belongs to it until the next button. resources.html is the lone top-level
# link (no dropdown) and is fixed up afterwards.
def _build_dropdown_map() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    current: str | None = None
    btn = re.compile(r'<button class="dropdown-toggle"[^>]*>([^<]+?)\s*<span')
    href = re.compile(r'<a href="([a-z0-9][a-z0-9\-]*\.html)"')
    for line in CANON_NAV.splitlines():
        m = btn.search(line)
        if m:
            current = m.group(1).strip()
            continue
        h = href.search(line)
        if h:
            out.setdefault(h.group(1), current)
    out['resources.html'] = None  # top-level link, not inside a dropdown
    return out

NAV_DROPDOWN = _build_dropdown_map()


def add_prefix(block: str) -> str:
    """Rewrite root-relative internal links to ../ for subdirectory pages."""
    return re.sub(r'href="(?!https?:|mailto:|#|/|\.\./)', 'href="../', block)


def mark_active(nav: str, active_href: str | None) -> str:
    """Set aria-current on the active link and `active` on its dropdown toggle.

    Operates on the unprefixed nav (active_href is a bare 'name.html').

    The current-section marker is the `active` class and nothing else.
    `aria-expanded` is deliberately left at "false": it means "the menu this
    button controls is open right now", not "this is the section you are in",
    and the dropdown is closed on load. Stamping "true" here told every screen
    reader that the menu was already open on all 254 pages, so the first arrow
    press went somewhere the user was not expecting. main.js owns the attribute
    from load onward (initDropdownNav sets it on click and clears it on close
    and on Escape); the only correct static value is "false". "You are here" is
    already carried by `aria-current="page"` on the link just below, and the
    visual pill is `.dropdown-toggle.active` in style.css, so neither depends
    on the lie.
    """
    if not active_href or active_href not in NAV_DROPDOWN:
        return nav
    link = f'<a href="{active_href}">'
    if link not in nav:
        return nav
    nav = nav.replace(link, f'<a href="{active_href}" aria-current="page">', 1)
    label = NAV_DROPDOWN.get(active_href)
    if label:
        old = (f'<button class="dropdown-toggle" aria-expanded="false" '
               f'aria-haspopup="true">{label} ')
        new = (f'<button class="dropdown-toggle active" aria-expanded="false" '
               f'aria-haspopup="true">{label} ')
        nav = nav.replace(old, new, 1)
    return nav


def active_href_for(path: Path) -> str | None:
    parent = path.parent.name
    if parent == 'breaches':
        return 'breach-timeline.html'
    if parent == 'meetings':
        return 'meetings.html'
    if parent == 'portfolio':
        return 'cloud-security-portfolio-projects.html'
    if parent == 'homelab':
        return 'cloud-security-home-lab.html'
    # Every per-year review highlights the series hub in the nav, the same way
    # a breaches/ page highlights the kill-chain index.
    if path.name.startswith('cloud-breach-year-in-review-'):
        return 'cloud-breach-year-in-review.html'
    return path.name


def build_nav(path: Path) -> str:
    is_sub = path.parent.name in ('breaches', 'meetings', 'portfolio', 'homelab')
    nav = mark_active(CANON_NAV, active_href_for(path))
    return add_prefix(nav) if is_sub else nav


def build_footer(path: Path) -> str:
    is_sub = path.parent.name in ('breaches', 'meetings', 'portfolio', 'homelab')
    return add_prefix(CANON_FOOTER) if is_sub else CANON_FOOTER


def process(path: Path) -> str:
    """Return 'updated', 'unchanged', or 'skipped' for one file."""
    text = path.read_text(encoding='utf-8')
    if '<nav>' not in text or '<footer>' not in text:
        return 'skipped'
    new = text
    new, n_logo = LOGO_PATTERN.subn(lambda m: m.group(1) + CANON_LOGO + '\n', new, count=1)
    new, n_burger = HAMBURGER_PATTERN.subn(lambda _: CANON_HAMBURGER, new, count=1)
    new, n_toggle = THEME_TOGGLE_PATTERN.subn(lambda _: CANON_THEME_TOGGLE, new, count=1)
    new, n_nav = NAV_PATTERN.subn(lambda _: build_nav(path), new, count=1)
    new, n_foot = FOOTER_PATTERN.subn(lambda _: build_footer(path), new, count=1)
    if n_nav == 0 or n_foot == 0 or n_burger == 0 or n_toggle == 0 or n_logo == 0:
        return 'skipped'
    if new == text:
        return 'unchanged'
    path.write_text(new, encoding='utf-8')
    return 'updated'


def main() -> None:
    paths: list[Path] = []
    paths.extend(REPO.glob('*.html'))
    paths.extend((REPO / 'breaches').glob('*.html'))
    paths.extend((REPO / 'meetings').glob('*.html'))
    paths.extend((REPO / 'portfolio').glob('*.html'))
    paths.extend((REPO / 'homelab').glob('*.html'))

    tally = {'updated': 0, 'unchanged': 0, 'skipped': 0}
    skipped: list[str] = []
    for p in sorted(paths):
        result = process(p)
        tally[result] += 1
        if result == 'skipped':
            skipped.append(p.relative_to(REPO).as_posix())
    print(f"updated={tally['updated']} unchanged={tally['unchanged']} "
          f"skipped={tally['skipped']}")
    if skipped:
        print('skipped files:', ', '.join(skipped))


if __name__ == '__main__':
    main()
