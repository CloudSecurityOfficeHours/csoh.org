#!/usr/bin/env python3
"""Wrap <img> tags in <picture> with a WebP <source> for transparent WebP delivery.

Our object-storage origins (S3, Azure Blob) can't do Accept-based content
negotiation, so we can't transparently swap a .jpg for its .webp at the edge on
the free plan. Instead we serve WebP the origin-agnostic way: a
<picture><source type="image/webp"> in the HTML. WebP-capable browsers fetch the
~30% smaller .webp; everything else falls back to the original <img>.

Eligibility for wrapping:
  - <img> src is a local .jpg/.jpeg/.png (skips data:, http(s):, protocol-rel,
    SVG, and anything with a query string),
  - a .webp sibling already exists on disk (run tools/generate_webp.py first),
  - the <img> is NOT already inside a <picture> (idempotent — re-runs are safe).

The <source srcset> reuses the img's exact src path with the extension swapped,
so it resolves from the same location (absolute "/img/..", page-relative
"img/..", or "../banner.png").

Pair this with `picture { display: contents }` in style.css so the wrapper is
layout-neutral (the <img> keeps behaving as the flex/grid child it was).

Usage:
    python3 tools/wrap_img_webp.py --dry-run          # report only, change nothing
    python3 tools/wrap_img_webp.py                    # all source HTML
    python3 tools/wrap_img_webp.py news.html faq.html # specific files
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

IMG_RE = re.compile(r"<img\b[^>]*>", re.DOTALL | re.IGNORECASE)
PICTURE_RE = re.compile(r"<picture\b.*?</picture>", re.DOTALL | re.IGNORECASE)
SRC_RE = re.compile(r'\bsrc\s*=\s*"([^"]+)"', re.IGNORECASE)
LOCAL_IMG_EXT_RE = re.compile(r"^(?P<base>.+)\.(?P<ext>jpe?g|png)$", re.IGNORECASE)


def webp_for(src: str, html_path: Path) -> str | None:
    """If `src` is a local raster image whose .webp sibling exists on disk,
    return the .webp src string to use in the <source>; else None."""
    if src.startswith(("http://", "https://", "//", "data:", "#")):
        return None
    m = LOCAL_IMG_EXT_RE.match(src)
    if not m:
        return None  # not .jpg/.jpeg/.png, or has a query string/fragment
    webp_src = m.group("base") + ".webp"

    if src.startswith("/"):
        fs = REPO_ROOT / src.lstrip("/")
    else:
        fs = html_path.parent / src
    webp_fs = (fs.parent / (fs.stem + ".webp")).resolve()
    return webp_src if webp_fs.is_file() else None


def process(path: Path, dry_run: bool) -> tuple[int, Counter]:
    s = path.read_text(encoding="utf-8")
    picture_spans = [(m.start(), m.end()) for m in PICTURE_RE.finditer(s)]
    wrapped = 0
    skipped_no_webp: Counter = Counter()

    def in_existing_picture(pos: int) -> bool:
        return any(a <= pos < b for a, b in picture_spans)

    def replace(m: re.Match) -> str:
        nonlocal wrapped
        tag = m.group(0)
        if in_existing_picture(m.start()):
            return tag
        sm = SRC_RE.search(tag)
        if not sm:
            return tag
        src = sm.group(1)
        webp_src = webp_for(src, path)
        if not webp_src:
            mm = LOCAL_IMG_EXT_RE.match(src)
            if mm:  # a local raster with no .webp sibling — report it
                skipped_no_webp[src] += 1
            return tag
        wrapped += 1
        return f'<picture><source srcset="{webp_src}" type="image/webp">{tag}</picture>'

    new = IMG_RE.sub(replace, s)
    if not dry_run and new != s:
        path.write_text(new, encoding="utf-8")
    return wrapped, skipped_no_webp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*", help="specific HTML files (default: all source HTML)")
    ap.add_argument("--dry-run", action="store_true", help="report only; write nothing")
    args = ap.parse_args()

    if args.files:
        paths = [REPO_ROOT / p for p in args.files]
    else:
        paths = (
            list(REPO_ROOT.glob("*.html"))
            + list(REPO_ROOT.glob("breaches/*.html"))
            + list(REPO_ROOT.glob("meetings/*.html"))
            + list(REPO_ROOT.glob("portfolio/*.html"))
        )

    total, files_changed = 0, 0
    all_skipped: Counter = Counter()
    for p in sorted(paths):
        if not p.exists():
            print(f"  - skip (missing): {p}")
            continue
        wrapped, skipped = process(p, args.dry_run)
        all_skipped.update(skipped)
        if wrapped:
            files_changed += 1
            total += wrapped
            print(f"  {'would wrap' if args.dry_run else '✓'} {p.relative_to(REPO_ROOT)}: {wrapped}")

    verb = "Would wrap" if args.dry_run else "Wrapped"
    print(f"\n{verb} {total} <img> across {files_changed} file(s).")
    if all_skipped:
        print(f"\nLocal images with NO .webp sibling (skipped, {sum(all_skipped.values())} refs):")
        for src, n in all_skipped.most_common(20):
            print(f"  {n:4}  {src}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
