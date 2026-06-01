#!/usr/bin/env python3
"""Mobile layout regression check.

Renders a representative sample of pages at iPhone-13 viewport and asserts:
  1. The page has no horizontal overflow at the body or document level.
  2. With the hamburger menu OPEN:
     - Every nav link / button is fully inside the viewport horizontally.
     - Tap targets are ≥ 40px tall (Apple's 44pt guideline minus a hair).
     - Sibling rows in the open Learn / Defend / Attend dropdowns line up
       - same `padding-left` and same height, so the menu doesn't look
       jagged.
  3. The hero h1 doesn't visually overflow.

Optional `--screenshots OUT_DIR` writes a screenshot of each tested page
(menu open) to that directory so you can eyeball the result.

Usage:
    python3 tools/check_mobile_layout.py
    python3 tools/check_mobile_layout.py --screenshots /tmp/mobile-shots
    python3 tools/check_mobile_layout.py --pages index.html breach-timeline.html

Exit code: 0 if all checks pass, 1 if any check fails. Designed to be
runnable both locally and as a CI step.
"""

from __future__ import annotations

import argparse
import http.server
import socket
import socketserver
import sys
import threading
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent

# A small but representative sample. Order them so the most surface-area
# pages come first (more likely to expose layout problems).
DEFAULT_PAGES = [
    "index.html",
    "what-is-cloud-security.html",
    "learning-path.html",
    "cloud-security-best-practices.html",
    "shared-responsibility-model.html",
    "cspm-vs-cnapp.html",
    "cloud-security-certifications.html",
    "github-actions.html",
    "resources.html",
    "ctfs.html",
    "conferences.html",
    "glossary.html",
    "meetings.html",
    "breach-timeline.html",
    "news.html",
    "faq.html",
    "sessions.html",
    "presentations.html",
    "breaches/capital-one.html",
    "meetings/2026-04-17.html",
]

# iPhone 13 viewport (logical pixels)
VIEWPORT = {"width": 390, "height": 844}
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 "
    "Mobile/15E148 Safari/604.1"
)

# Apple/Material both recommend ≥ 44pt; we allow 40px to leave a little
# slack for compact accordion rows that are still finger-friendly.
MIN_TAP_TARGET_PX = 40

# How aligned do dropdown sibling rows have to be? Permissive but tight
# enough to catch real misalignments (the kind users actually notice).
MAX_PADDING_VARIANCE_PX = 1.0
MAX_HEIGHT_VARIANCE_PX = 4.0


def find_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args, **_kwargs) -> None:  # silence
        pass


def serve_repo(port: int) -> socketserver.ThreadingTCPServer:
    """Start a tiny static server rooted at the repo. Returns the server
    so the caller can shut it down."""
    def handler(*args, **kwargs):
        return Handler(*args, directory=str(REPO_ROOT), **kwargs)
    server = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def check_page(page, url: str, page_path: str, screenshots_dir: Optional[Path]) -> list[str]:
    """Run all assertions against a single page. Returns a list of failure
    messages - empty if the page passes."""
    failures: list[str] = []
    page.goto(url, wait_until="domcontentloaded")
    # Give CSS animations / fonts a beat to settle.
    page.wait_for_timeout(200)

    # --- 1. No horizontal overflow on the document.
    overflow = page.evaluate(
        "() => ({ body: document.body.scrollWidth, html: document.documentElement.scrollWidth, vw: window.innerWidth })"
    )
    if overflow["body"] > overflow["vw"] + 1 or overflow["html"] > overflow["vw"] + 1:
        failures.append(
            f"horizontal overflow: body={overflow['body']}px, html={overflow['html']}px, viewport={overflow['vw']}px"
        )

    # --- 2. Open the hamburger menu and inspect.
    try:
        page.click("button.hamburger", timeout=2000)
        page.wait_for_timeout(200)
    except Exception as e:
        failures.append(f"could not open hamburger menu: {e}")
        if screenshots_dir:
            page.screenshot(path=str(screenshots_dir / f"{page_path.replace('/', '_')}.png"))
        return failures

    # 2a. Every nav link / button stays inside the viewport horizontally.
    overflows = page.evaluate(
        """() => {
            const items = Array.from(document.querySelectorAll('header nav a, header nav button.dropdown-toggle'));
            const vw = window.innerWidth;
            const bad = [];
            for (const el of items) {
                const r = el.getBoundingClientRect();
                if (r.right > vw + 1 || r.left < -1) {
                    bad.push({ text: (el.textContent || '').trim().slice(0, 40), left: r.left, right: r.right, vw });
                }
            }
            return bad;
        }"""
    )
    for o in overflows:
        failures.append(
            f"nav item overflows viewport: '{o['text']}' (left={o['left']:.0f}, right={o['right']:.0f}, vw={o['vw']})"
        )

    # 2b. Tap targets are tall enough.
    small_targets = page.evaluate(
        f"""() => {{
            const items = Array.from(document.querySelectorAll('header nav a, header nav button.dropdown-toggle'));
            const bad = [];
            for (const el of items) {{
                const r = el.getBoundingClientRect();
                if (r.height > 0 && r.height < {MIN_TAP_TARGET_PX}) {{
                    bad.push({{ text: (el.textContent || '').trim().slice(0, 40), height: r.height }});
                }}
            }}
            return bad;
        }}"""
    )
    for t in small_targets:
        failures.append(f"tap target too small: '{t['text']}' is {t['height']:.0f}px tall (min {MIN_TAP_TARGET_PX})")

    # 2c. Open each dropdown and check that its rows align AND that they
    # look visually distinct from the top-level toggles above them. With
    # 10 sub-items in Learn, the menu is a flat wall of links unless
    # sub-items have a clearly different indent or marker.
    hierarchy = page.evaluate(
        """() => {
            const topLevel = Array.from(document.querySelectorAll('header nav > ul > li > a, header nav > ul > li > .dropdown-toggle'));
            const subItems = Array.from(document.querySelectorAll('header nav .dropdown-menu a'));
            const tlPad = topLevel.length ? parseFloat(getComputedStyle(topLevel[0]).paddingLeft) : 0;
            // Pick a sub-item whose dropdown is currently open (so it's
            // actually rendered/measurable). Fall back to first.
            const measured = subItems.find(a => a.getBoundingClientRect().height > 0) || subItems[0];
            const subPad = measured ? parseFloat(getComputedStyle(measured).paddingLeft) : 0;
            return { tlPad, subPad, gap: subPad - tlPad };
        }"""
    )
    if hierarchy and hierarchy["gap"] < 12:
        # Less than ~12px additional indent and there's no visual cue that
        # a row is "inside" a dropdown - looks like a flat list to the eye.
        failures.append(
            f"weak hierarchy: sub-items only {hierarchy['gap']:.0f}px more indented than top-level "
            f"({hierarchy['tlPad']:.0f} → {hierarchy['subPad']:.0f}). Need clearer visual nesting."
        )

    dropdowns = ["Learn", "Defend", "Attend", "Contribute"]
    for dropdown_label in dropdowns:
        # Find and click the dropdown toggle by visible label.
        try:
            toggle = page.locator(f"header nav button.dropdown-toggle:has-text('{dropdown_label}')").first
            if not toggle.is_visible():
                continue
            toggle.click()
            page.wait_for_timeout(100)
        except Exception:
            continue

        rows = page.evaluate(
            f"""() => {{
                const dd = Array.from(document.querySelectorAll('header nav .has-dropdown'))
                  .find(el => el.querySelector('.dropdown-toggle')?.textContent.trim().startsWith({dropdown_label!r}));
                if (!dd) return [];
                const links = Array.from(dd.querySelectorAll('.dropdown-menu a'));
                return links.map(a => {{
                    const r = a.getBoundingClientRect();
                    const cs = getComputedStyle(a);
                    return {{
                        text: (a.textContent || '').trim().slice(0, 50),
                        left: r.left,
                        right: r.right,
                        height: r.height,
                        paddingLeft: parseFloat(cs.paddingLeft),
                    }};
                }});
            }}"""
        )
        if not rows:
            continue
        # Padding-left should be the same across rows.
        pls = [r["paddingLeft"] for r in rows]
        if max(pls) - min(pls) > MAX_PADDING_VARIANCE_PX:
            failures.append(
                f"{dropdown_label} dropdown: padding-left varies by {max(pls) - min(pls):.1f}px "
                f"(rows: {[round(p, 1) for p in pls]})"
            )
        # Height should be roughly consistent.
        heights = [r["height"] for r in rows]
        if max(heights) - min(heights) > MAX_HEIGHT_VARIANCE_PX:
            outlier_rows = [r for r in rows if r["height"] in (max(heights), min(heights))]
            failures.append(
                f"{dropdown_label} dropdown: row heights vary by {max(heights) - min(heights):.1f}px "
                f"(min {min(heights):.0f}, max {max(heights):.0f}; outliers: {[r['text'] for r in outlier_rows]})"
            )
        # Close it before opening the next one (tap the toggle again to collapse).
        try:
            toggle.click()
            page.wait_for_timeout(50)
        except Exception:
            pass

    # --- 3. Hero h1 visually overflows? (Common on long titles.)
    h1_overflow = page.evaluate(
        """() => {
            const h1 = document.querySelector('section.hero h1, section.hero h2');
            if (!h1) return null;
            const r = h1.getBoundingClientRect();
            return { right: r.right, left: r.left, scrollWidth: h1.scrollWidth, clientWidth: h1.clientWidth };
        }"""
    )
    if h1_overflow and (
        h1_overflow["right"] > overflow["vw"] + 1
        or h1_overflow["scrollWidth"] - h1_overflow["clientWidth"] > 2
    ):
        failures.append(
            f"hero heading overflows: right={h1_overflow['right']:.0f}, "
            f"scrollW={h1_overflow['scrollWidth']:.0f}, clientW={h1_overflow['clientWidth']:.0f}"
        )

    # Save a screenshot if requested. Take TWO frames per page so we see
    # both the menu chrome and the worst-case dropdown (Learn - 10 items).
    if screenshots_dir:
        try:
            slug = page_path.replace("/", "_").replace(".html", "")
            # Frame 1: closed menu, then re-open hamburger so we see the
            # full top of the menu (Home, Learn ▾, Defend ▾, …) from row 1.
            page.evaluate("window.scrollTo(0, 0)")
            page.wait_for_timeout(50)
            # Close any open dropdowns + close & reopen the hamburger so
            # the menu is in a clean opened state from the top.
            page.evaluate(
                "() => document.querySelectorAll('.has-dropdown.open').forEach(el => el.classList.remove('open'))"
            )
            page.wait_for_timeout(50)
            page.screenshot(path=str(screenshots_dir / f"{slug}__menu-top.png"), full_page=False)
            # Frame 2: open the Learn dropdown specifically (worst case
            # because of 10 items) and capture full-page so all sub-rows
            # are visible.
            try:
                learn_toggle = page.locator(
                    "header nav button.dropdown-toggle:has-text('Learn')"
                ).first
                if learn_toggle.is_visible():
                    learn_toggle.click()
                    page.wait_for_timeout(150)
                    # Resize the viewport temporarily so the WHOLE menu fits
                    # in one viewport-height screenshot (much more readable
                    # than full_page=True which compresses to thumbnail).
                    page.set_viewport_size({"width": VIEWPORT["width"], "height": 1400})
                    page.wait_for_timeout(50)
                    page.screenshot(
                        path=str(screenshots_dir / f"{slug}__learn-open.png"),
                        full_page=False,
                    )
                    # Restore default viewport for the next page test.
                    page.set_viewport_size(VIEWPORT)
            except Exception:
                pass
        except Exception:
            pass

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Mobile layout regression check.")
    parser.add_argument("--screenshots", help="Directory to save mobile screenshots to", default=None)
    parser.add_argument(
        "--pages",
        nargs="*",
        help=f"Pages to test (default: {len(DEFAULT_PAGES)} representative pages)",
    )
    args = parser.parse_args()

    pages_to_test = args.pages or DEFAULT_PAGES
    screenshots_dir = Path(args.screenshots) if args.screenshots else None
    if screenshots_dir:
        screenshots_dir.mkdir(parents=True, exist_ok=True)

    port = find_free_port()
    server = serve_repo(port)
    base_url = f"http://127.0.0.1:{port}"
    print(f"📱 Mobile layout check (iPhone 13 / {VIEWPORT['width']}×{VIEWPORT['height']})")
    print(f"   Serving repo at {base_url}\n")

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Install with: pip install playwright && playwright install chromium", file=sys.stderr)
        server.shutdown()
        return 2

    total_failures = 0
    pages_failed = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport=VIEWPORT,
                user_agent=USER_AGENT,
                device_scale_factor=2,
                is_mobile=True,
                has_touch=True,
            )
            page = context.new_page()

            for page_path in pages_to_test:
                url = f"{base_url}/{page_path}"
                failures = check_page(page, url, page_path, screenshots_dir)
                if failures:
                    pages_failed += 1
                    total_failures += len(failures)
                    print(f"  ❌ {page_path}")
                    for f in failures:
                        print(f"       - {f}")
                else:
                    print(f"  ✓ {page_path}")
        finally:
            browser.close()

    server.shutdown()

    print()
    if total_failures:
        print(f"❌ {pages_failed}/{len(pages_to_test)} pages failed, {total_failures} total issue(s).")
        return 1
    print(f"✓ All {len(pages_to_test)} pages passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
