#!/usr/bin/env python3
"""Redesign the site nav and footer across all HTML pages.

New IA:
  - Learn (mega-menu, 3 cols: Foundations / Topics / Career & Growth)
  - Resources (direct link)
  - Threat Intel (dropdown; News promoted here)
  - Community (mega-menu, 2 cols: Live / Archive)
  - About (dropdown; absorbs Contribute)
  - Join Friday Zoom (CTA button)

Footer adds a 'Developer Docs' column for github-actions + cloud-deployment.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# basename -> (top_menu_label, link_text) — used to set aria-current + active
ACTIVE_MAP: dict[str, tuple[str, str]] = {
    # Threat Intel
    "news.html": ("Threat Intel", "News"),
    "threat-research.html": ("Threat Intel", "Threat Research"),
    "breach-timeline.html": ("Threat Intel", "Breach Kill Chains"),
    "cloud-soc.html": ("Threat Intel", "Cloud SOC"),
    "ctfs.html": ("Threat Intel", "CTFs"),
    # Learn > Foundations
    "what-is-cloud-security.html": ("Learn", "What is Cloud Security?"),
    "shared-responsibility-model.html": ("Learn", "Shared Responsibility"),
    "cspm-vs-cnapp.html": ("Learn", "CSPM vs CNAPP"),
    "glossary.html": ("Learn", "Glossary"),
    "faq.html": ("Learn", "FAQ"),
    # Learn > Topics
    "cloud-security-best-practices.html": ("Learn", "Best Practices"),
    "containers.html": ("Learn", "Containers"),
    "kubernetes.html": ("Learn", "Kubernetes"),
    "serverless.html": ("Learn", "Serverless"),
    "ci-cd.html": ("Learn", "CI/CD"),
    "landing-zones.html": ("Learn", "Landing Zones"),
    "grc.html": ("Learn", "GRC"),
    "ai-learning.html": ("Learn", "AI Learning"),
    # Learn > Career & Growth
    "learning-path.html": ("Learn", "Learning Path"),
    "cloud-security-certifications.html": ("Learn", "Certifications"),
    "cloud-security-degree-programs.html": ("Learn", "Degree Programs"),
    "cloud-security-home-lab.html": ("Learn", "Home Lab"),
    "cloud-security-portfolio-projects.html": ("Learn", "Portfolio Projects"),
    "cloud-security-careers.html": ("Learn", "Careers"),
    "cloud-security-reading-list.html": ("Learn", "Reading List"),
    # Resources
    "resources.html": ("__TOP__", "Resources"),
    # Community
    "sessions.html": ("Community", "Friday Zoom Sessions"),
    "community.html": ("Community", "Community &amp; Signal"),
    "conferences.html": ("Community", "Conferences"),
    "meetings.html": ("Community", "Meeting Recaps"),
    "presentations.html": ("Community", "Presentations"),
    "chat-resources.html": ("Community", "Chat Resources"),
    # About
    "about-shawn-nunley.html": ("About", "About Shawn"),
    "contribute.html": ("About", "Contribute"),
    "contribute-resources.html": ("About", "Add a Resource"),
}

# Subdir basename heuristics: any meeting page → Meeting Recaps; etc.
SUBDIR_ACTIVE: dict[str, tuple[str, str]] = {
    "meetings": ("Community", "Meeting Recaps"),
    "breaches": ("Threat Intel", "Breach Kill Chains"),
    "portfolio": ("Learn", "Portfolio Projects"),
}


def nav_html(prefix: str, active_top: str | None, active_link: str | None) -> str:
    """Build the new <nav>...</nav> markup.

    prefix: '' for root pages, '../' for subdir pages.
    active_top: top-level menu to mark active (or None / '__TOP__' for direct links).
    active_link: the leaf link text to mark with aria-current.
    """
    P = prefix

    def is_top(label: str) -> bool:
        return active_top == label

    def is_link(text: str) -> bool:
        return active_link == text

    def cur(text: str) -> str:
        return ' aria-current="page"' if is_link(text) else ''

    def toggle_attrs(label: str) -> str:
        active = is_top(label)
        cls = "dropdown-toggle active" if active else "dropdown-toggle"
        expanded = "true" if active else "false"
        return f'class="{cls}" aria-expanded="{expanded}" aria-haspopup="true"'

    resources_attrs = ' aria-current="page"' if active_top == "__TOP__" and active_link == "Resources" else ''
    resources_cls = ' class="active"' if resources_attrs else ''

    return f'''<nav>
                <ul>
                    <li class="has-dropdown has-mega">
                      <button {toggle_attrs("Learn")}>Learn <span class="caret" aria-hidden="true">▾</span></button>
                      <div class="dropdown-menu mega-menu mega-3col">
                        <div class="mega-col">
                          <h4 class="mega-heading">Foundations</h4>
                          <ul>
                            <li><a href="{P}what-is-cloud-security.html"{cur("What is Cloud Security?")}>What is Cloud Security?</a></li>
                            <li><a href="{P}shared-responsibility-model.html"{cur("Shared Responsibility")}>Shared Responsibility</a></li>
                            <li><a href="{P}cspm-vs-cnapp.html"{cur("CSPM vs CNAPP")}>CSPM vs CNAPP</a></li>
                            <li><a href="{P}glossary.html"{cur("Glossary")}>Glossary</a></li>
                            <li><a href="{P}faq.html"{cur("FAQ")}>FAQ</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <h4 class="mega-heading">Topics</h4>
                          <ul>
                            <li><a href="{P}cloud-security-best-practices.html"{cur("Best Practices")}>Best Practices</a></li>
                            <li><a href="{P}containers.html"{cur("Containers")}>Containers</a></li>
                            <li><a href="{P}kubernetes.html"{cur("Kubernetes")}>Kubernetes</a></li>
                            <li><a href="{P}serverless.html"{cur("Serverless")}>Serverless</a></li>
                            <li><a href="{P}ci-cd.html"{cur("CI/CD")}>CI/CD</a></li>
                            <li><a href="{P}landing-zones.html"{cur("Landing Zones")}>Landing Zones</a></li>
                            <li><a href="{P}grc.html"{cur("GRC")}>GRC</a></li>
                            <li><a href="{P}ai-learning.html"{cur("AI Learning")}>AI Learning</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <h4 class="mega-heading">Career &amp; Growth</h4>
                          <ul>
                            <li><a href="{P}learning-path.html"{cur("Learning Path")}>Learning Path</a></li>
                            <li><a href="{P}cloud-security-certifications.html"{cur("Certifications")}>Certifications</a></li>
                            <li><a href="{P}cloud-security-degree-programs.html"{cur("Degree Programs")}>Degree Programs</a></li>
                            <li><a href="{P}cloud-security-home-lab.html"{cur("Home Lab")}>Home Lab</a></li>
                            <li><a href="{P}cloud-security-portfolio-projects.html"{cur("Portfolio Projects")}>Portfolio Projects</a></li>
                            <li><a href="{P}cloud-security-careers.html"{cur("Careers")}>Careers</a></li>
                            <li><a href="{P}cloud-security-reading-list.html"{cur("Reading List")}>Reading List</a></li>
                          </ul>
                        </div>
                      </div>
                    </li>
                    <li><a href="{P}resources.html"{resources_cls}{resources_attrs}>Resources</a></li>
                    <li class="has-dropdown">
                      <button {toggle_attrs("Threat Intel")}>Threat Intel <span class="caret" aria-hidden="true">▾</span></button>
                      <ul class="dropdown-menu">
                        <li><a href="{P}news.html"{cur("News")}>News</a></li>
                        <li><a href="{P}threat-research.html"{cur("Threat Research")}>Threat Research</a></li>
                        <li><a href="{P}breach-timeline.html"{cur("Breach Kill Chains")}>Breach Kill Chains</a></li>
                        <li><a href="{P}cloud-soc.html"{cur("Cloud SOC")}>Cloud SOC</a></li>
                        <li><a href="{P}ctfs.html"{cur("CTFs")}>CTFs</a></li>
                      </ul>
                    </li>
                    <li class="has-dropdown has-mega">
                      <button {toggle_attrs("Community")}>Community <span class="caret" aria-hidden="true">▾</span></button>
                      <div class="dropdown-menu mega-menu mega-2col">
                        <div class="mega-col">
                          <h4 class="mega-heading">Live</h4>
                          <ul>
                            <li><a href="{P}sessions.html"{cur("Friday Zoom Sessions")}>Friday Zoom Sessions</a></li>
                            <li><a href="{P}community.html"{cur("Community &amp; Signal")}>Community &amp; Signal</a></li>
                            <li><a href="{P}conferences.html"{cur("Conferences")}>Conferences</a></li>
                          </ul>
                        </div>
                        <div class="mega-col">
                          <h4 class="mega-heading">Archive</h4>
                          <ul>
                            <li><a href="{P}meetings.html"{cur("Meeting Recaps")}>Meeting Recaps</a></li>
                            <li><a href="{P}presentations.html"{cur("Presentations")}>Presentations</a></li>
                            <li><a href="{P}chat-resources.html"{cur("Chat Resources")}>Chat Resources</a></li>
                          </ul>
                        </div>
                      </div>
                    </li>
                    <li class="has-dropdown">
                      <button {toggle_attrs("About")}>About <span class="caret" aria-hidden="true">▾</span></button>
                      <ul class="dropdown-menu">
                        <li><a href="{P}about-shawn-nunley.html"{cur("About Shawn")}>About Shawn</a></li>
                        <li><a href="{P}contribute.html"{cur("Contribute")}>Contribute</a></li>
                        <li><a href="{P}contribute-resources.html"{cur("Add a Resource")}>Add a Resource</a></li>
                      </ul>
                    </li>
                    <li class="nav-cta-item"><a href="https://csoh.kit.com/39feb4f397" class="nav-cta" target="_blank" rel="noopener noreferrer">Join Friday Zoom →</a></li>
                </ul>
            </nav>'''


def footer_html(prefix: str) -> str:
    P = prefix
    return f'''<footer>
    <div class="footer-content">
      <div class="footer-section footer-about">
        <h3>CSOH</h3>
        <p>A vendor-neutral community for cloud security professionals. Weekly Zoom sessions and curated resources.</p>
      </div>
      <div class="footer-section">
        <h3>Explore</h3>
        <ul>
          <li><a href="{P}learning-path.html">Learning Path</a></li>
          <li><a href="{P}resources.html">Resources</a></li>
          <li><a href="{P}news.html">News</a></li>
          <li><a href="{P}sessions.html">Zoom Sessions</a></li>
          <li><a href="{P}meetings.html">Meeting Recaps</a></li>
        </ul>
      </div>
      <div class="footer-section">
        <h3>Connect</h3>
        <ul>
          <li><a href="mailto:admin@csoh.org">Contact</a></li>
          <li><a href="https://csoh.kit.com/39feb4f397" target="_blank" rel="noopener noreferrer">Mailing List</a></li>
          <li><a href="https://github.com/CloudSecurityOfficeHours/csoh.org" target="_blank" rel="noopener noreferrer">GitHub</a></li>
          <li><a href="{P}rss.html">RSS Feed</a></li>
          <li><a href="{P}contribute.html">Contribute</a></li>
        </ul>
      </div>
      <div class="footer-section">
        <h3>Developer Docs</h3>
        <ul>
          <li><a href="{P}github-actions.html">GitHub Actions</a></li>
          <li><a href="{P}cloud-deployment.html">Deploy to GCP</a></li>
        </ul>
      </div>
    </div>
    <div class="footer-bottom">
      <p>&copy; 2023-2026 Cloud Security Office Hours</p>
      <ul class="footer-legal">
        <li><a href="{P}privacy.html">Privacy</a></li>
        <li><a href="{P}code-of-conduct.html">Code of Conduct</a></li>
        <li><a href="{P}security-policy.html">Security</a></li>
      </ul>
    </div>
  </footer>'''


NAV_RE = re.compile(r'<nav>\s*<ul>.*?</ul>\s*</nav>', re.DOTALL)
FOOTER_RE = re.compile(r'<footer>.*?</footer>', re.DOTALL)


def update_file(path: Path) -> bool:
    """Return True if file was modified."""
    text = path.read_text(encoding='utf-8')

    # Determine prefix
    rel = path.relative_to(ROOT)
    depth = len(rel.parts) - 1
    prefix = '../' * depth

    # Determine active state
    basename = path.name
    if depth == 0:
        active_top, active_link = (None, None)
        if basename in ACTIVE_MAP:
            active_top, active_link = ACTIVE_MAP[basename]
    else:
        subdir = rel.parts[0]
        active_top, active_link = SUBDIR_ACTIVE.get(subdir, (None, None))

    new_nav = nav_html(prefix, active_top, active_link)
    new_footer = footer_html(prefix)

    new_text = text
    nav_match = NAV_RE.search(new_text)
    if nav_match:
        new_text = new_text[:nav_match.start()] + new_nav + new_text[nav_match.end():]
    footer_match = FOOTER_RE.search(new_text)
    if footer_match:
        new_text = new_text[:footer_match.start()] + new_footer + new_text[footer_match.end():]

    if new_text != text:
        path.write_text(new_text, encoding='utf-8')
        return True
    return False


def main() -> int:
    files: list[Path] = []
    files.extend(sorted(ROOT.glob('*.html')))
    files.extend(sorted(ROOT.glob('meetings/*.html')))
    files.extend(sorted(ROOT.glob('breaches/*.html')))
    files.extend(sorted(ROOT.glob('portfolio/*.html')))

    # Skip files we don't want to touch
    skip = {'google66d489593949bd4c.html'}

    changed = 0
    skipped = 0
    for f in files:
        if f.name in skip:
            skipped += 1
            continue
        if not NAV_RE.search(f.read_text(encoding='utf-8')):
            print(f"  skip (no nav): {f.relative_to(ROOT)}")
            skipped += 1
            continue
        if update_file(f):
            changed += 1
        else:
            skipped += 1
    print(f"Updated {changed} files, skipped {skipped}.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
