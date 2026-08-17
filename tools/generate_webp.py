#!/usr/bin/env python3
"""Generate .webp siblings for raster images (JPEG + PNG) used on the site.

Why .webp: modern browsers send `Accept: image/webp`; serving WebP saves
~25-35% bandwidth at equivalent quality. Delivery is via <picture><source
type="image/webp"> in the HTML (run tools/wrap_img_webp.py after this) - our
object-storage origins can't do Accept-based negotiation, so there's no
.htaccess trick to lean on.

Encoding: lossy WebP at quality 82 (the sweet spot - visually indistinguishable
from the source at display size, well under half the bytes). Site images (photos
+ page-screenshot thumbnails) are only ever shown scaled down, so lossless would
just bloat git history for no visible gain. A generated .webp that isn't actually
smaller than its source is discarded, so we never serve a larger file (and
wrap_img_webp.py then leaves that <img> alone).

Idempotent: skips files whose .webp sibling is newer than the source.

`--only-existing` refreshes the .webp files that are already committed and
creates no new ones. It exists because these directories are deliberately
partial: img/og holds 90 top-level JPGs but only 4 committed .webp siblings,
because a sibling is only reachable where the image is rendered through a
<picture> element - the four featured cards on index.html. Every other OG
image is an og:image meta target, and a meta tag carries a single URL, so it
can never use a <source srcset>. A bare run over img/og would add the other 86
and commit them.

When a generator re-renders one of those JPGs, its sibling has to be re-encoded
or the browser keeps getting the old image from <source srcset> while the
<img> fallback carries the new one - so pair a card regeneration with
`generate_webp.py <dir> --only-existing`.

Requires Pillow (pip install Pillow). On the deploy runner Pillow is
already installed alongside Playwright for the preview generator.

Usage:
    python3 tools/generate_webp.py                   # all default dirs
    python3 tools/generate_webp.py chat-screenshots  # specific dir
    python3 tools/generate_webp.py --force           # regenerate even if up-to-date
    python3 tools/generate_webp.py img/og --only-existing  # refresh, never add
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DIRS = [
    REPO_ROOT / "img" / "og",
    REPO_ROOT / "img" / "thumbs",
    REPO_ROOT / "img" / "previews",
    REPO_ROOT / "chat-screenshots",
]
# Quality 82 is the sweet spot: indistinguishable from JPEG at the same
# perceived quality, but ~30% smaller. 75 is too soft on text; 90 starts
# bloating without visible benefit.
WEBP_QUALITY = 82


def rel(p: Path) -> str:
    """Display path: repo-relative inside the repo, absolute outside it.

    A caller may legitimately pass a directory that is not under REPO_ROOT - a
    scratch copy, a staging dir, anything absolute. Path.relative_to raises
    ValueError in that case, and because these paths are only ever used for
    progress output, that aborted an otherwise valid run partway through a
    print rather than failing anything real.
    """
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def convert(src: Path, force: bool) -> tuple[str, int, int]:
    """Returns (status, src_bytes, dst_bytes) where status is one of
    'converted', 'uptodate', 'not-smaller'."""
    dst = src.with_suffix(".webp")
    src_b = src.stat().st_size
    if not force and dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return "uptodate", src_b, dst.stat().st_size

    from PIL import Image
    with Image.open(src) as img:
        # Preserve alpha (PNG transparency); coerce palette/other modes to a
        # WebP-friendly one. WebP lossy keeps an alpha channel fine.
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if img.mode in ("P", "LA", "PA") else "RGB")
        img.save(dst, "WEBP", quality=WEBP_QUALITY, method=6)

    dst_b = dst.stat().st_size
    # Never keep a .webp that isn't actually smaller - serving a larger file
    # would defeat the purpose. wrap_img_webp.py then leaves that <img> alone.
    if dst_b >= src_b:
        dst.unlink()
        return "not-smaller", src_b, src_b
    return "converted", src_b, dst_b


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate WebP siblings for JPEGs.")
    parser.add_argument("dirs", nargs="*", help="Subset of dirs to process")
    parser.add_argument("--force", action="store_true",
                        help="Regenerate even if .webp is up to date")
    parser.add_argument("--only-existing", action="store_true",
                        help="Refresh only sources that already have a .webp "
                             "sibling; never create a new one")
    args = parser.parse_args()

    targets = [Path(d) if Path(d).is_absolute() else REPO_ROOT / d for d in args.dirs] or DEFAULT_DIRS

    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        print("Pillow not installed. pip install Pillow", file=sys.stderr)
        return 2

    total_src = 0
    total_dst = 0
    converted = 0
    skipped = 0
    not_smaller = 0
    failed = 0

    for d in targets:
        if not d.exists():
            print(f"  - skip (missing): {rel(d)}")
            continue
        srcs = sorted(d.glob("*.jpg")) + sorted(d.glob("*.jpeg")) + sorted(d.glob("*.png"))
        srcs.sort()
        # Refresh-only mode: keep just the sources that already have a sibling,
        # so a partial directory stays partial. See the module docstring.
        if args.only_existing:
            srcs = [s for s in srcs if s.with_suffix(".webp").exists()]
        if not srcs:
            continue
        print(f"📁 {rel(d)} - {len(srcs)} source images")
        for src in srcs:
            try:
                status, src_b, dst_b = convert(src, force=args.force)
            except Exception as e:
                print(f"  ✗ {src.name}: {e}")
                failed += 1
                continue
            total_src += src_b
            total_dst += dst_b
            if status == "converted":
                converted += 1
            elif status == "not-smaller":
                not_smaller += 1
            else:
                skipped += 1

    if total_src:
        savings_pct = 100 * (total_src - total_dst) / total_src
        print(
            f"\n✓ {converted} converted, {skipped} up-to-date,"
            f" {not_smaller} skipped (webp not smaller), {failed} failed."
            f" Total: {total_src/1024:.0f}KB → {total_dst/1024:.0f}KB"
            f" ({savings_pct:.0f}% smaller)."
        )
    else:
        print("\nNothing to do.")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
