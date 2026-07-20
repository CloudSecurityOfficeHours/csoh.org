#!/usr/bin/env python3
"""
retire_merged_career_pages.py  —  run from the csoh.org site root.

The three entry-path career pages
    is-cloud-security-a-good-career.html
    get-into-cloud-security-no-experience.html
    help-desk-to-cloud-security.html
were merged into breaking-into-cloud-security.html.

Server-side 301s in .htaccess already redirect the old URLs, so this pass is
cleanliness/SEO: it repoints inbound links so the nav and body point straight at
the live page (no redirect hop). It:
  1) collapses the three "Getting Started" nav entries into one "Breaking In" link
  2) repoints any remaining links to those slugs, preserving each link's path
     prefix (""/"/"/"../") and any #fragment.

Usage:   python3 retire_merged_career_pages.py
Then review `git diff` and commit. Safe to re-run (idempotent).
"""
import re
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
OLD = ["is-cloud-security-a-good-career",
       "get-into-cloud-security-no-experience",
       "help-desk-to-cloud-security"]
NEW = "breaking-into-cloud-security"
SKIP_DIRS = {".git", ".github", ".venv", ".ruff_cache", "__pycache__", "vendor", "dist", "node_modules"}

def process(text: str) -> str:
    # 1) nav: rename the "good career" entry to "Breaking In"; drop the other two.
    #    ([^"]*) captures any path prefix so subpages keep resolving correctly.
    text = re.sub(
        r'<li><a href="([^"]*)is-cloud-security-a-good-career\.html"[^>]*>\s*Is It a Good Career\?\s*</a></li>',
        lambda m: f'<li><a href="{m.group(1)}{NEW}.html">Breaking In</a></li>', text)
    text = re.sub(
        r'\s*<li><a href="[^"]*get-into-cloud-security-no-experience\.html"[^>]*>\s*Start With No Experience\s*</a></li>',
        "", text)
    text = re.sub(
        r'\s*<li><a href="[^"]*help-desk-to-cloud-security\.html"[^>]*>\s*Help Desk[^<]*Cloud Security\s*</a></li>',
        "", text)
    # 2) any remaining links to the retired slugs -> merged page (keep prefix + #fragment)
    for slug in OLD:
        text = re.sub(
            r'href="([^"]*?)' + re.escape(slug) + r'\.html((?:#[^"]*)?)"',
            lambda m: f'href="{m.group(1)}{NEW}.html{m.group(2)}"', text)
    return text

def main():
    skip_root_files = {f"{s}.html" for s in OLD} | {f"{NEW}.html"}
    changed = 0
    for p in ROOT.rglob("*.html"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.parent == ROOT and p.name in skip_root_files:
            continue
        s = p.read_text(encoding="utf-8", errors="ignore")
        out = process(s)
        if out != s:
            p.write_text(out, encoding="utf-8")
            changed += 1
            print("updated", p.relative_to(ROOT))
    print(f"\nDone. {changed} file(s) updated.")

if __name__ == "__main__":
    main()
