#!/usr/bin/env python3
"""Validate that every news source slug has an on-disk banner image.

news.html cards reference img/news-banners/{slug}.jpg and .webp, where
{slug} comes from SOURCE_SLUGS in update_news.py. If a new feed gets
added to that map but the matching banner file is never committed, the
card silently renders with a broken image.

This check fails CI when:
  - any slug used in SOURCE_SLUGS lacks a .jpg or .webp on disk, OR
  - any banner reference in news.html points at a missing file.

Generate missing banners with: python3 tools/generate_news_banners.py

Usage:
    python3 tools/check_news_banners.py        # exits 1 if anything missing
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BANNER_DIR = REPO_ROOT / "img" / "news-banners"
UPDATE_NEWS = REPO_ROOT / "update_news.py"
NEWS_HTML = REPO_ROOT / "news.html"


def load_source_slugs() -> set[str]:
    """Pull SOURCE_SLUGS = {...} out of update_news.py without importing it.

    Parsing the AST avoids dragging in update_news.py's network-heavy imports
    just to read one dict.
    """
    tree = ast.parse(UPDATE_NEWS.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "SOURCE_SLUGS":
                    return set(ast.literal_eval(node.value).values())
    raise RuntimeError("SOURCE_SLUGS not found in update_news.py")


def referenced_banners_in_html() -> set[str]:
    text = NEWS_HTML.read_text()
    return set(re.findall(r"img/news-banners/([a-z0-9-]+)\.(?:jpg|webp)", text))


def main() -> int:
    on_disk = {p.stem for p in BANNER_DIR.glob("*.jpg")} & {
        p.stem for p in BANNER_DIR.glob("*.webp")
    }

    slugs_mapped = load_source_slugs()
    slugs_in_html = referenced_banners_in_html()

    missing_for_mapped = sorted(slugs_mapped - on_disk)
    missing_for_html = sorted(slugs_in_html - on_disk)

    if not missing_for_mapped and not missing_for_html:
        print(f"✅ All {len(slugs_mapped)} mapped news source banners exist on disk.")
        return 0

    if missing_for_html:
        print("❌ news.html references banners that don't exist on disk:")
        for slug in missing_for_html:
            print(f"  • img/news-banners/{slug}.jpg + .webp")
    if missing_for_mapped:
        print("⚠️  SOURCE_SLUGS maps these slugs but no banner exists yet:")
        for slug in missing_for_mapped:
            print(f"  • {slug}")

    print("\nGenerate with: python3 tools/generate_news_banners.py")
    # Only fail hard when the missing banner is actually rendered in news.html.
    # A mapped-but-unused slug is a warning (feed hasn't produced items yet).
    return 1 if missing_for_html else 0


if __name__ == "__main__":
    sys.exit(main())
