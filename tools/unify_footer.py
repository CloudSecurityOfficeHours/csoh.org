#!/usr/bin/env python3
"""
Replace every <footer>...</footer> block across the site with a single
canonical footer. Uses root-relative URLs (/foo.html) so the same markup
works at any directory depth (top-level, /meetings/, /breaches/).

Run from repo root: python3 tools/unify_footer.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CANONICAL = """<footer>
  <div class="footer-content">
    <div class="footer-section">
      <h3>Learn</h3>
      <ul>
        <li><a href="/what-is-cloud-security.html">What is Cloud Security?</a></li>
        <li><a href="/learning-path.html">Learning Path</a></li>
        <li><a href="/cloud-security-best-practices.html">Best Practices</a></li>
        <li><a href="/shared-responsibility-model.html">Shared Responsibility</a></li>
        <li><a href="/cspm-vs-cnapp.html">CSPM vs CNAPP</a></li>
        <li><a href="/cloud-security-certifications.html">Certifications</a></li>
        <li><a href="/glossary.html">Glossary</a></li>
        <li><a href="/faq.html">FAQ</a></li>
      </ul>
    </div>

    <div class="footer-section">
      <h3>Defend</h3>
      <ul>
        <li><a href="/news.html">News</a></li>
        <li><a href="/threat-research.html">Threat Research</a></li>
        <li><a href="/breach-timeline.html">Breach Kill Chains</a></li>
        <li><a href="/resources.html">All Resources</a></li>
        <li><a href="/ctfs.html">Cloud CTFs</a></li>
        <li><a href="/github-actions.html">GitHub Actions</a></li>
      </ul>
    </div>

    <div class="footer-section">
      <h3>Attend</h3>
      <ul>
        <li><a href="/sessions.html">Zoom Sessions</a></li>
        <li><a href="/conferences.html">Conferences</a></li>
        <li><a href="/meetings.html">Meeting Recaps</a></li>
        <li><a href="/presentations.html">Presentations</a></li>
        <li><a href="/chat-resources.html">Chat Resources</a></li>
      </ul>
    </div>

    <div class="footer-section">
      <h3>Community</h3>
      <ul>
        <li><a href="mailto:admin@csoh.org">Contact Us</a></li>
        <li><a href="https://csoh.kit.com/39feb4f397" target="_blank" rel="noopener noreferrer">Mailing List</a></li>
        <li><a href="https://github.com/CloudSecurityOfficeHours/csoh.org" target="_blank" rel="noopener noreferrer">GitHub</a></li>
        <li><a href="/contribute.html">Contribute</a></li>
        <li><a href="/code-of-conduct.html">Code of Conduct</a></li>
        <li><a href="/privacy.html">Privacy Policy</a></li>
        <li><a href="/security-policy.html">Security Policy</a></li>
        <li><a href="/rss.html">RSS Feed</a></li>
      </ul>
    </div>

    <div class="footer-section">
      <h3>About CSOH</h3>
      <p>Cloud Security Office Hours is a vendor-neutral community for cloud
      security professionals. We meet weekly on Zoom and maintain this curated
      collection of resources.</p>
    </div>
  </div>

  <div class="footer-bottom">
    <p>&copy; 2023-2026 Cloud Security Office Hours. All resources are provided as-is for educational purposes.</p>
  </div>
</footer>"""

FOOTER_RE = re.compile(
    r"^(?P<indent>[ \t]*)<footer\b[^>]*>.*?</footer>",
    re.DOTALL | re.MULTILINE,
)


def reindent(block: str, indent: str) -> str:
    return "\n".join((indent + line) if line else line for line in block.splitlines())


def process(path: Path) -> bool:
    original = path.read_text()
    matches = list(FOOTER_RE.finditer(original))
    if not matches:
        return False
    if len(matches) > 1:
        print(f"  WARN: {path} has {len(matches)} footers, replacing all", file=sys.stderr)

    def sub(match: re.Match) -> str:
        return reindent(CANONICAL, match.group("indent"))

    updated = FOOTER_RE.sub(sub, original)
    if updated == original:
        return False
    path.write_text(updated)
    return True


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    targets: list[Path] = []
    targets.extend(sorted(repo.glob("*.html")))
    targets.extend(sorted(repo.glob("meetings/*.html")))
    targets.extend(sorted(repo.glob("breaches/*.html")))

    skip = {"google66d489593949bd4c.html"}

    changed = 0
    untouched = 0
    skipped = 0
    for path in targets:
        if path.name in skip:
            skipped += 1
            continue
        if process(path):
            changed += 1
            print(f"updated: {path.relative_to(repo)}")
        else:
            untouched += 1

    print(f"\n{changed} updated, {untouched} unchanged, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
