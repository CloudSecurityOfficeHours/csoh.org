#!/usr/bin/env python3
"""Generate the card thumbnails used by the compact grids.

Renders a CSOH-branded 480x320 (3:2) tile per card and writes it to
../img/thumbs/<slug>.jpg at 2x, i.e. 960x640.

Why this exists separately from generate_og_images.py
-----------------------------------------------------
Those two produce different things for different places, and conflating
them is what caused the bug this replaced.

An OG image is a 1200x630 social embed: a big headline, a subtitle, a
footer, all sized to be read at full width in a Slack or LinkedIn unfurl.
The compact card grids on index.html and what-practitioners-think.html
render their thumbnail 197-303px wide. Dropping an OG card into that slot
gave a 6px subtitle, a headline that just repeated the <h3> directly
beneath it, and - until the aspect-ratio fix - 12-18% sliced off each side
by object-fit: cover.

A thumbnail at 233px has one job: be recognisable at a glance and say
which topic this is. So these tiles carry a glyph and one category word,
and leave the naming to the card's own heading.

The featured grid still uses OG cards on purpose. At 311px wide they are
legible and the extra prominence suits the four "start here" cards.

Usage:
    /usr/bin/python3 tools/generate_thumbnails.py
    /usr/bin/python3 tools/generate_thumbnails.py --slugs iam zero-trust
    /usr/bin/python3 tools/generate_thumbnails.py --list

Note the interpreter: Playwright is installed under /usr/bin/python3 on
this machine, not the pyenv default. In CI it is on the default python3.

After running, regenerate the WebP siblings and re-stamp SRI:
    python3 tools/generate_webp.py img/thumbs
    python3 update_sri.py
"""

from __future__ import annotations

import argparse
import http.server
import socket
import socketserver
import sys
import threading
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "tools" / "og" / "thumb-template.html"
OUT_DIR = REPO_ROOT / "img" / "thumbs"

# 3:2. The compact box was 160px tall at 233px wide (ratio 1.46) before this
# change, so 1.5 keeps the grid's vertical rhythm almost exactly while being
# a ratio we actually author to instead of one that falls out of a crop.
THUMB_VIEWPORT = {"width": 480, "height": 320}
# 3x, not 2x. The compact grid collapses to a single column below 768px, and
# in the ~600-768px band that makes the tile ~613 CSS px wide - 1226 device px
# on a retina screen, which a 960px asset would have to upscale. 1440x960
# covers it and still lands around 50KB, well under the ~121KB OG cards these
# replaced.
SCALE = 3

# (slug, icon, accent, label)
#
# The accent is what separates 23 tiles from each other at thumbnail size, so
# neighbours in the grid should not share one. Provider accents echo each
# vendor's own brand hue; the rest are chosen to stay distinct from their
# immediate neighbours in the layout. Every one of these clears 4.5:1 against
# the tile's dark gradient.
#
# To add a card: append a tuple, run this script with --slugs <slug>, then
# point the card's <img> at img/thumbs/<slug>.jpg with class
# "resource-preview resource-preview--thumb".
THUMBS = [
    # ── index.html: "Learn the fundamentals" ────────────────────────────────
    ("what-is-cloud-security",     "cloud-check",     "#38bdf8", "Start here"),
    ("shared-responsibility",      "split-panel",     "#2dd4bf", "Foundations"),
    ("aws-security",               "layers",          "#ff9d2e", "AWS"),
    ("azure-security",             "cube",            "#4aa3f0", "Azure"),
    ("gcp-security",               "globe",           "#7dd37d", "GCP"),
    ("iam",                        "key",             "#a78bfa", "Identity"),
    ("zero-trust",                 "shield-keyhole",  "#22d3ee", "Architecture"),
    # "Compare", not "Tooling": the Browse-by-topic grid below already has a
    # "Tools" tile, and two near-identical labels a few cards apart is exactly
    # the ambiguity a thumbnail is supposed to remove.
    ("cspm-vs-cnapp",              "panels",          "#34d399", "Compare"),

    # ── index.html: "Browse by topic" ──────────────────────────────────────
    ("labs",                       "flask",           "#4ade80", "Labs"),
    ("tools",                      "wrench",          "#fbbf24", "Tools"),
    ("certifications",             "award",           "#facc15", "Certs"),
    ("ai-security",                "chip",            "#c084fc", "AI"),
    ("jobs",                       "briefcase",       "#60a5fa", "Jobs"),
    ("degree-programs",            "cap",             "#818cf8", "Education"),
    ("careers",                    "route",           "#38bdf8", "Careers"),
    ("home-lab",                   "rack",            "#2dd4bf", "Home lab"),
    ("about",                      "users",           "#f87171", "About"),

    # ── what-practitioners-think.html: the six digests ─────────────────────
    ("digest-ai-security",         "bubble-chip",     "#c084fc", "AI security"),
    ("digest-breaking-in",         "door-in",         "#38bdf8", "Breaking in"),
    ("digest-vuln-management",     "bug",             "#fb7185", "Vuln mgmt"),
    ("digest-supply-chain",        "links",           "#fb923c", "Supply chain"),
    ("digest-regulation",          "scales",          "#94a3b8", "Regulation"),
    ("digest-conferences",         "mic",             "#f472b6", "Conferences"),
]


def find_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args, **_kwargs):
        pass


def serve_repo(port: int) -> socketserver.ThreadingTCPServer:
    def handler(*args, **kwargs):
        return Handler(*args, directory=str(REPO_ROOT), **kwargs)
    server = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate compact-card thumbnails.")
    parser.add_argument("--slugs", nargs="*",
                        help="Subset of slugs to regenerate (default: all)")
    parser.add_argument("--list", action="store_true",
                        help="Print the slug/icon/accent table and exit")
    args = parser.parse_args()

    if args.list:
        for slug, icon, accent, label in THUMBS:
            print(f"{slug:26} {icon:16} {accent}  {label}")
        return 0

    if not TEMPLATE_PATH.exists():
        print(f"missing template: {TEMPLATE_PATH}", file=sys.stderr)
        return 1

    targets = THUMBS
    if args.slugs:
        targets = [t for t in THUMBS if t[0] in args.slugs]
        missing = set(args.slugs) - {t[0] for t in targets}
        if missing:
            print(f"unknown slug(s): {', '.join(sorted(missing))}", file=sys.stderr)
            return 1

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install playwright: pip install playwright && playwright install chromium\n"
              "On this machine Playwright lives under /usr/bin/python3.",
              file=sys.stderr)
        return 2

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    port = find_free_port()
    server = serve_repo(port)
    template_url = f"http://127.0.0.1:{port}/tools/og/thumb-template.html"
    w, h = THUMB_VIEWPORT["width"], THUMB_VIEWPORT["height"]
    print(f"🎨 Generating {len(targets)} thumbnails at {w * SCALE}x{h * SCALE}...\n")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport=THUMB_VIEWPORT,
                device_scale_factor=SCALE,
            )
            page = context.new_page()

            for slug, icon, accent, label in targets:
                params = urllib.parse.urlencode(
                    {"icon": icon, "accent": accent, "label": label})
                page.goto(f"{template_url}?{params}", wait_until="networkidle")
                page.wait_for_timeout(90)

                out_path = OUT_DIR / f"{slug}.jpg"
                page.screenshot(
                    path=str(out_path),
                    type="jpeg",
                    quality=90,
                    full_page=False,
                    clip={"x": 0, "y": 0, "width": w, "height": h},
                )
                kb = out_path.stat().st_size / 1024
                print(f"  ✓ img/thumbs/{slug}.jpg  ({icon}, {accent}, {kb:.0f} KB)")
        finally:
            browser.close()

    server.shutdown()
    print(f"\nGenerated {len(targets)} thumbnails in {OUT_DIR.relative_to(REPO_ROOT)}/.")
    print("Next: python3 tools/generate_webp.py img/thumbs && python3 update_sri.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
