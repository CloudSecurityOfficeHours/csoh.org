#!/usr/bin/env python3
"""Generate per-meeting 1200x630 OG cards.

Reads the date and topic summary out of each meetings/YYYY-MM-DD.html file,
renders a CSOH-branded card via tools/og/template.html (same template the
top-level generate_og_images.py uses), saves to img/og/meetings/<date>.jpg,
and rewrites the page's og:image + twitter:image meta tags.

Usage:
    python3 tools/generate_meeting_og_images.py
    python3 tools/generate_meeting_og_images.py --pages meetings/2026-05-08.html
    python3 tools/generate_meeting_og_images.py --skip-html
"""

from __future__ import annotations

import argparse
import html as html_lib
import http.server
import re
import socket
import socketserver
import sys
import threading
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "tools" / "og" / "template.html"
MEETINGS_DIR = REPO_ROOT / "meetings"
OUT_DIR = REPO_ROOT / "img" / "og" / "meetings"
OG_VIEWPORT = {"width": 1200, "height": 630}

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
H1_RE = re.compile(r"<h1>([^<]+)</h1>")
# The hero subhead carries the topic teasers, e.g.
#   <p>Cloud backup strategies, securing local AI agents, ServiceNow…</p>
HERO_SUBHEAD_RE = re.compile(
    r'<section class="hero hero--compact">.*?<h1>[^<]+</h1>\s*<p>(.*?)</p>',
    re.DOTALL,
)
H2_LINE_RE = re.compile(
    r'<h2><time datetime="\d{4}-\d{2}-\d{2}">[^<]+</time>\s*[\u2014\u2013-]\s*(.*?)</h2>',
    re.DOTALL,
)

MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def strip_inline_tags(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def date_string(yyyy_mm_dd: str) -> str:
    m = DATE_RE.match(yyyy_mm_dd)
    if not m:
        return yyyy_mm_dd
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"{MONTHS[mo - 1]} {d}, {y}"


def extract_meeting_meta(html: str, slug: str) -> tuple[str, str]:
    """Return (title, subtitle) suitable for the OG template."""
    title = date_string(slug)

    # Prefer the dated <h2> topic summary because it's more descriptive than
    # the hero subhead (which is the previous week's news teaser).
    m = H2_LINE_RE.search(html)
    if m:
        subtitle = strip_inline_tags(m.group(1))
    else:
        m = HERO_SUBHEAD_RE.search(html)
        subtitle = strip_inline_tags(m.group(1)) if m else "Weekly Cloud Security Office Hours recap"

    # Keep subtitle short enough that the template doesn't have to clamp.
    if len(subtitle) > 140:
        subtitle = subtitle[:137].rsplit(" ", 1)[0] + "…"

    return title, subtitle


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


def update_html_meta(html_path: Path, og_path: str) -> bool:
    s = html_path.read_text(encoding="utf-8")
    original = s
    abs_url = f"https://csoh.org/{og_path}"
    s = re.sub(
        r'(<meta\s+property="og:image"\s+content=")[^"]+(")',
        rf'\1{abs_url}\2',
        s,
        count=1,
    )
    s = re.sub(
        r'(<meta\s+name="twitter:image"\s+content=")[^"]+(")',
        rf'\1{abs_url}\2',
        s,
        count=1,
    )
    if s != original:
        html_path.write_text(s, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate per-meeting OG images.")
    parser.add_argument("--pages", nargs="*",
                        help="Subset of meeting files (e.g. meetings/2026-05-08.html)")
    parser.add_argument("--skip-html", action="store_true",
                        help="Only regenerate JPGs, don't rewrite the meta tags")
    args = parser.parse_args()

    if not TEMPLATE_PATH.exists():
        print(f"missing template: {TEMPLATE_PATH}", file=sys.stderr)
        return 1

    if args.pages:
        targets = [Path(p) for p in args.pages]
        targets = [p if p.is_absolute() else (REPO_ROOT / p) for p in targets]
        targets = [p for p in targets if p.exists()]
    else:
        targets = sorted(MEETINGS_DIR.glob("*.html"))

    if not targets:
        print("No meeting files matched", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install playwright: pip install playwright && playwright install chromium",
              file=sys.stderr)
        return 2

    port = find_free_port()
    server = serve_repo(port)
    template_url = f"http://127.0.0.1:{port}/tools/og/template.html"
    print(f"🎨 Generating {len(targets)} meeting OG images at "
          f"{OG_VIEWPORT['width']}x{OG_VIEWPORT['height']}...\n")

    generated = 0
    html_updated = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport=OG_VIEWPORT,
                device_scale_factor=2,
            )
            page = context.new_page()

            for html_path in targets:
                slug = html_path.stem  # e.g. 2026-05-08
                html = html_path.read_text(encoding="utf-8")
                title, subtitle = extract_meeting_meta(html, slug)

                params = urllib.parse.urlencode({
                    "title": title,
                    "subtitle": subtitle,
                    "badge": "Meeting Recap",
                })
                url = f"{template_url}?{params}"
                page.goto(url, wait_until="networkidle")
                page.wait_for_timeout(120)

                out_path = OUT_DIR / f"{slug}.jpg"
                page.screenshot(
                    path=str(out_path),
                    type="jpeg",
                    quality=88,
                    full_page=False,
                    clip={"x": 0, "y": 0,
                          "width": OG_VIEWPORT["width"],
                          "height": OG_VIEWPORT["height"]},
                )
                generated += 1

                rel = out_path.relative_to(REPO_ROOT).as_posix()
                if not args.skip_html:
                    if update_html_meta(html_path, rel):
                        html_updated += 1
                        print(f"  ✓ {html_path.relative_to(REPO_ROOT)} → {rel}")
                    else:
                        print(f"    {html_path.relative_to(REPO_ROOT)} → {rel} (meta already set)")
                else:
                    print(f"  ✓ {rel}")
        finally:
            browser.close()

    server.shutdown()
    print(f"\nGenerated {generated} images. Updated {html_updated} HTML files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
