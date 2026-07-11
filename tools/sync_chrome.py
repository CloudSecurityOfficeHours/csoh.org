#!/usr/bin/env python3
"""Stamp ONE canonical nav, header buttons, and footer onto every HTML page.

Why this exists
---------------
The nav and footer are hand-copied into each of ~175 static pages (no
templating). Over time they drifted: the breaches/ and meetings/ pages still
carried an older, smaller nav; a couple of root pages had stray extra items;
the footer's "About CSOH" link was present on some pages and missing on
others. This script makes the menu nav, the two header buttons (hamburger and
theme toggle), and the footer *byte-identical* everywhere, with only two
legitimate per-page differences preserved (both apply to the nav/footer only;
the header buttons are the same two lines on every page):

  1. `../` path prefixes on pages inside breaches/ and meetings/.
  2. The current-page markers (`aria-current="page"` on the active link and
     `active` / `aria-expanded="true"` on its dropdown toggle).

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
# This is the current site nav (Learn / Resources / By Cloud / Threat Intel /
# Community / Behind the Scenes / Join Friday Zoom CTA) with the two new
# developer-docs pages added to "Behind the Scenes". Keep the 12-space indent;
# NAV_PATTERN below consumes the existing indentation so this controls it fully.
CANON_NAV = """\
            <nav>
                <ul>
                    <li class="has-dropdown has-mega">
                      <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Learn <span class="caret" aria-hidden="true">▾</span></button>
                      <div class="dropdown-menu mega-menu mega-5col">
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
                          <span class="mega-heading">Workloads &amp; Platform</span>
                          <ul>
                            <li><a href="containers.html">Containers</a></li>
                            <li><a href="kubernetes.html">Kubernetes</a></li>
                            <li><a href="serverless.html">Serverless</a></li>
                            <li><a href="service-mesh-security.html">Service Mesh</a></li>
                            <li><a href="ci-cd.html">CI/CD</a></li>
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
                            <li><a href="ai-learning.html">AI Learning</a></li>
                            <li><a href="ai-ml-security.html">AI/ML Security</a></li>
                            <li><a href="mcp-security.html">MCP Security</a></li>
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
                      <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">By Cloud <span class="caret" aria-hidden="true">&#9662;</span></button>
                      <ul class="dropdown-menu">
                        <li><a href="aws-security.html">AWS Security</a></li>
                        <li><a href="azure-security.html">Azure Security</a></li>
                        <li><a href="gcp-security.html">GCP Security</a></li>
                        <li><a href="cloud-security-comparison.html">AWS vs Azure vs GCP</a></li>
                      </ul>
                    </li>
                    <li class="has-dropdown">
                      <button class="dropdown-toggle" aria-expanded="false" aria-haspopup="true">Threat Intel <span class="caret" aria-hidden="true">▾</span></button>
                      <ul class="dropdown-menu">
                        <li><a href="news.html">News</a></li>
                        <li><a href="threat-research.html">Threat Research</a></li>
                        <li><a href="breach-timeline.html">Breach Kill Chains</a></li>
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
                            <li><a href="is-cloud-security-a-good-career.html">Is It a Good Career?</a></li>
                            <li><a href="get-into-cloud-security-no-experience.html">Start With No Experience</a></li>
                            <li><a href="learning-path.html">Learning Path</a></li>
                            <li><a href="help-desk-to-cloud-security.html">Help Desk → Cloud Security</a></li>
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
                      <div class="dropdown-menu mega-menu mega-2col">
                        <div class="mega-col">
                          <span class="mega-heading">Live</span>
                          <ul>
                            <li><a href="sessions.html">Friday Zoom Sessions</a></li>
                            <li><a href="community.html">Community &amp; Signal</a></li>
                            <li><a href="mentorship.html">Mentorship</a></li>
                            <li><a href="conferences.html">Conferences</a></li>
                            <li><a href="present.html">Present at CSOH</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <span class="mega-heading">Archive</span>
                          <ul>
                            <li><a href="meetings.html">Meeting Recaps</a></li>
                            <li><a href="presentations.html">Presentations</a></li>
                            <li><a href="speakers.html">Guest Speakers</a></li>
                            <li><a href="chat-resources.html">Chat Resources</a></li>
                          </ul>
                        </div>
                      </div>
                    </li>
                    <li class="nav-cta-item"><a href="https://csoh.kit.com/39feb4f397" class="nav-cta" target="_blank" rel="noopener noreferrer">Join Friday Zoom →</a></li>
                </ul>
            </nav>"""

# --- Canonical footer (root-relative) ----------------------------------------
# Includes "About CSOH" (-> index.html#about) in Explore and the two new pages
# in Developer Docs. Keep the 2-space indent; FOOTER_PATTERN consumes the
# existing indentation.
CANON_FOOTER = """\
  <footer>
    <div class="footer-content">
      <div class="footer-section footer-about">
        <h3>CSOH</h3>
        <p>A vendor-neutral community for cloud security professionals. Weekly Zoom sessions and curated resources.</p>
      </div>
      <div class="footer-section">
        <h3>Explore</h3>
        <ul>
          <li><a href="index.html#about">About CSOH</a></li>
          <li><a href="learning-path.html">Learning Path</a></li>
          <li><a href="resources.html">Resources</a></li>
          <li><a href="news.html">News</a></li>
          <li><a href="sessions.html">Zoom Sessions</a></li>
          <li><a href="meetings.html">Meeting Recaps</a></li>
          <li><a href="search.html">Search</a></li>
        </ul>
      </div>
      <div class="footer-section">
        <h3>Connect</h3>
        <ul>
          <li><a href="mailto:admin@csoh.org">Contact</a></li>
          <li><a href="https://csoh.kit.com/39feb4f397" target="_blank" rel="noopener noreferrer">Mailing List</a></li>
          <li><a href="https://github.com/CloudSecurityOfficeHours/csoh.org" target="_blank" rel="noopener noreferrer">GitHub</a></li>
          <li><a href="rss.html">RSS Feed</a></li>
          <li><a href="contribute.html">Contribute</a></li>
          <li><a href="contribute-resources.html">Add a Resource</a></li>
        </ul>
      </div>
      <div class="footer-section">
        <h3>Developer Docs</h3>
        <ul>
          <li><a href="github-actions.html">GitHub Actions</a></li>
          <li><a href="cloud-deployment.html">Multi-Cloud Deploy</a></li>
          <li><a href="terraform.html">Terraform</a></li>
          <li><a href="version-control.html">Git &amp; Version Control</a></li>
        </ul>
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
        new = (f'<button class="dropdown-toggle active" aria-expanded="true" '
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
    new, n_burger = HAMBURGER_PATTERN.subn(lambda _: CANON_HAMBURGER, new, count=1)
    new, n_toggle = THEME_TOGGLE_PATTERN.subn(lambda _: CANON_THEME_TOGGLE, new, count=1)
    new, n_nav = NAV_PATTERN.subn(lambda _: build_nav(path), new, count=1)
    new, n_foot = FOOTER_PATTERN.subn(lambda _: build_footer(path), new, count=1)
    if n_nav == 0 or n_foot == 0 or n_burger == 0 or n_toggle == 0:
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
