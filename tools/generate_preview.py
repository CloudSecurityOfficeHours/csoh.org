#!/usr/bin/env python3
"""
Preview Image Generator for CSOH Resources

Automatically captures and optimizes screenshots of resource URLs
to use as preview images.

Features:
- Multiple capture methods, tried in order: (1) the page's own og:image
  social card, (2) a Playwright screenshot, (3) the thum.io screenshot API,
  (4) a generated placeholder.
- Image optimization and resizing (needs Pillow for every path)
- Automatic preview-mapping.json updates
- Fallback to placeholder images

Usage:
    python3 tools/generate_preview.py <url> [output_filename]  # one URL
    python3 tools/generate_preview.py --check resources.html   # report missing
    python3 tools/generate_preview.py --batch-auto             # fill all gaps
    python3 tools/generate_preview.py --fix-html               # repair <img> src paths
"""

import sys
import os
import json
from pathlib import Path
from urllib.parse import urlparse
import time

# Configuration
PREVIEW_DIR = Path(__file__).parent.parent / 'img' / 'previews'
PREVIEW_MAPPING = Path(__file__).parent.parent / 'preview-mapping.json'
TARGET_WIDTH = 400
TARGET_HEIGHT = 300
SCREENSHOT_TIMEOUT = 30  # seconds
MIN_PREVIEW_SIZE_KB = 8  # Real Playwright screenshots ~10-22KB; placeholders ~3KB

# URLs that consistently fail to produce useful previews - bot detection,
# JS-heavy SPAs that render blank, login walls, etc. The --check command
# will skip these so they don't block the deploy workflow on every run.
PREVIEW_IGNORE_URLS = {
    'https://www.sentinelone.com/labs/',
    'https://www.ibm.com/reports/threat-intelligence',
    'https://www.sophos.com/en-us/content/state-of-ransomware',
    'https://blog.lastpass.com/posts/2023/03/security-incident-update-recommended-actions',
    'https://otx.alienvault.com/',
    'https://www.cyber.gov.au/about-us/advisories',
    # Conferences pages with bot detection / JS-rendered hero / login walls
    # that defeat headless screenshots - keep their existing placeholder JPGs.
    'https://www.rsaconference.com/',
    'https://cloud.withgoogle.com/next',
    'https://www.blackhat.com/upcoming.html',
    # Substack / blog / podcast sites that block headless screenshots
    # or render blank without full JS execution.
    'https://www.resilientcyber.io/',
    'https://orca.security/resources/blog/',
    'https://www.philvenables.com/',
    'https://www.cloudsecuritypodcast.tv/',
}


def _placeholder_marker_path(preview_path):
    """Return the Path of the sidecar marker that flags a preview as a placeholder."""
    full_path = Path(__file__).parent.parent / preview_path
    return full_path.parent / '.placeholders' / (full_path.name + '.placeholder')


def is_preview_good(preview_path):
    """Return True if the preview file exists and is not a generated placeholder.

    We used to also require a minimum file size, but real Playwright screenshots
    of sparse pages (grep.app, offline pages, etc.) can legitimately be 1-4 KB.
    We now distinguish placeholders by a sidecar marker written at generation
    time - any file without a marker is trusted.
    """
    full_path = Path(__file__).parent.parent / preview_path
    if not full_path.exists():
        return False
    if _placeholder_marker_path(preview_path).exists():
        return False
    return True

def generate_filename_from_url(url):
    """Generate a safe filename from URL."""
    parsed = urlparse(url)
    domain = parsed.netloc.replace('www.', '')
    path = parsed.path.strip('/').replace('/', '-')

    if path:
        filename = f"{domain}-{path}"
    else:
        filename = domain

    # Clean up filename
    filename = filename.lower()
    filename = ''.join(c if c.isalnum() or c in ['-', '_'] else '-' for c in filename)
    filename = filename[:100]  # Limit length

    return f"{filename}.jpg"

# Minimum byte size for an og:image to count as a real preview. Anything
# smaller is almost always a 1x1 tracking pixel, a tiny favicon, or a SVG
# icon - none of which look good at our 400x300 card size.
MIN_OG_IMAGE_BYTES = 4_000


def _is_svg(data, content_type):
    """Return True if an og:image response is SVG rather than a raster image.

    Pillow can't open SVG, so accepting one writes vector markup to a .jpg
    path: optimize_image() then fails, the raw bytes stay, and the card
    renders broken (served as image/jpeg, decoded as XML). The size guard
    above doesn't catch it - therecord.media's og:image is a 5KB Illustrator
    logo, comfortably over the minimum. Sniff the bytes as well as the
    Content-Type, since some CDNs serve SVG as application/octet-stream.
    """
    if 'svg' in content_type:
        return True
    head = data[:512].lstrip()
    return head.startswith(b'<?xml') or head.startswith(b'<svg')


# A modern desktop UA. Some sites (e.g. *.microsoft.com) return a stripped
# response or block entirely when they see urllib's default UA.
_BROWSER_UA = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/123.0.0.0 Safari/537.36'
)


def capture_from_og_image(url, output_path):
    """Try to use the page's own <meta property="og:image"> as the preview.

    This is the highest-ROI capture method for cloud-security resources:
    most vendor docs, GitHub repos, and marketing pages set a curated OG
    image specifically for social sharing. Fetching that image is
    - faster than a headless browser screenshot,
    - higher quality than a viewport-cropped page render,
    - immune to cookie banners and Cloudflare bot challenges (we never
      render the page, we just parse the HTML head).
    Returns (True, message) on success - output_path will hold the raw
    bytes of the OG image, ready for optimize_image() to resize/recompress.
    """
    try:
        import re as _re
        import urllib.request
        import urllib.error
        from urllib.parse import urljoin

        print(f"  🔗 Trying og:image for {url}")

        # Fetch the page HTML. We don't need the full page - head/meta tags
        # are at the top, so a partial read of the first 256 KB is plenty
        # and avoids waiting on slow asset loads.
        req = urllib.request.Request(url, headers={
            'User-Agent': _BROWSER_UA,
            'Accept': 'text/html,application/xhtml+xml',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                final_url = resp.geturl()
                html = resp.read(256 * 1024).decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            return False, f"og:image fetch HTTP {e.code}"
        except Exception as e:
            return False, f"og:image fetch error: {e}"

        # Look for og:image first (Open Graph), then twitter:image as
        # backup. We tolerate either property/name attribute ordering and
        # either single or double quotes around values. Stop at the first
        # match per tag to keep this cheap.
        candidates = []
        patterns = [
            r'<meta[^>]+property=["\']og:image(?::secure_url)?["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image(?::secure_url)?["\']',
            r'<meta[^>]+name=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image(?::src)?["\']',
        ]
        for pat in patterns:
            m = _re.search(pat, html, _re.IGNORECASE)
            if m:
                candidates.append(m.group(1))

        if not candidates:
            return False, "no og:image / twitter:image meta tag"

        # Try each candidate in order - the first one that downloads as a
        # real, non-trivial image wins.
        for img_url in candidates:
            # Resolve relative URLs (//cdn.example.com/foo.png, /foo.png)
            # against the page's final URL (after redirects).
            abs_url = urljoin(final_url, img_url.strip())
            try:
                img_req = urllib.request.Request(abs_url, headers={
                    'User-Agent': _BROWSER_UA,
                    'Accept': 'image/avif,image/webp,image/png,image/jpeg,image/*;q=0.8',
                    'Referer': final_url,
                })
                with urllib.request.urlopen(img_req, timeout=15) as img_resp:
                    ctype = (img_resp.headers.get('Content-Type') or '').lower()
                    data = img_resp.read()
            except Exception as e:
                print(f"    ↳ candidate {abs_url} failed: {e}")
                continue

            if 'image/' not in ctype:
                print(f"    ↳ candidate {abs_url} returned {ctype or 'unknown type'}")
                continue
            if len(data) < MIN_OG_IMAGE_BYTES:
                print(f"    ↳ candidate {abs_url} too small ({len(data)} bytes)")
                continue
            if _is_svg(data, ctype):
                print(f"    ↳ candidate {abs_url} is SVG - Pillow can't rasterize it")
                continue

            # Pillow handles the format conversion - we write raw bytes
            # here and let optimize_image() convert to JPEG + resize.
            with open(output_path, 'wb') as f:
                f.write(data)
            return True, f"og:image captured from {abs_url} ({len(data) // 1024}KB)"

        return False, "all og:image candidates were too small / wrong type"

    except Exception as e:
        return False, f"og:image error: {e}"


# CSS that hides the cookie / consent banners that block the top half of
# most vendor pages. We inject this before screenshot so the actual page
# content shows through. Covers OneTrust, Cookiebot, Drupal cookie-notice,
# Hubspot, and a catch-all for anything with "cookie"/"consent" in its id
# or class. The `display: none !important` wins over the banner's own
# fixed-position styling.
_COOKIE_BANNER_HIDE_CSS = """
#onetrust-banner-sdk, #onetrust-consent-sdk, #onetrust-pc-sdk,
#CybotCookiebotDialog, #CybotCookiebotDialogBodyUnderlay,
#cookie-notice, #cookie-banner, #cookie-law-info-bar,
.cookie-banner, .cookie-notice, .cookie-consent, .cc-banner,
.cc-window, .cookies-eu-banner, .gdpr-banner,
[id*="cookie-banner" i], [id*="cookie-notice" i],
[id*="cookie-consent" i], [id*="consent-banner" i],
[class*="cookie-banner" i], [class*="cookie-notice" i],
[class*="cookie-consent" i], [class*="consent-banner" i],
[aria-label*="cookie" i], [aria-label*="consent" i] {
    display: none !important;
    visibility: hidden !important;
}
"""


def capture_with_playwright(url, output_path):
    """Capture screenshot using Playwright (best quality)."""
    try:
        from playwright.sync_api import sync_playwright

        print(f"  📸 Using Playwright to capture {url}")

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent=_BROWSER_UA,
            )
            page = context.new_page()

            # Set timeout
            page.set_default_timeout(SCREENSHOT_TIMEOUT * 1000)

            # Navigate. `domcontentloaded` returns as soon as the HTML is
            # parsed - way more reliable than `networkidle`, which hangs
            # on pages with WebSockets, analytics beacons, or other
            # long-lived connections. We add an explicit settle delay
            # below so JS still has time to render.
            try:
                page.goto(url, wait_until='domcontentloaded')
            except Exception as e:
                # If even DOMContentLoaded fails (e.g. ERR_TIMED_OUT on a
                # really slow page), continue anyway - we may still have
                # enough of the page to screenshot.
                print(f"    ⚠️  navigation warning: {e}")

            # Let async JS render. Most cookie banners and hero sections
            # finish first paint within ~3s.
            time.sleep(3)

            # Hide cookie / consent banners so they don't cover the
            # screenshot. Best-effort - if injection fails, fall through.
            try:
                page.add_style_tag(content=_COOKIE_BANNER_HIDE_CSS)
            except Exception:
                pass

            # Scroll to top in case any "back to top" rendering shifted
            # the viewport, then take the screenshot.
            try:
                page.evaluate("window.scrollTo(0, 0)")
            except Exception:
                pass

            # Take screenshot
            page.screenshot(path=str(output_path), full_page=False)

            browser.close()

        return True, "Screenshot captured with Playwright"

    except ImportError:
        return False, "Playwright not installed (pip install playwright)"
    except Exception as e:
        return False, f"Playwright error: {str(e)}"

def capture_with_screenshot_api(url, output_path):
    """Capture screenshot using screenshot.guru free API (no auth needed)."""
    try:
        import urllib.request

        print(f"  🌐 Using Screenshot API for {url}")

        # screenshot.guru free API endpoint
        api_url = f"https://image.thum.io/get/width/800/crop/600/{url}"

        # Download screenshot
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        request = urllib.request.Request(api_url, headers=headers)

        with urllib.request.urlopen(request, timeout=SCREENSHOT_TIMEOUT) as response:
            content_type = (response.headers.get('Content-Type') or '').lower()
            data = response.read()

        # thum.io returns a GIF loading spinner when it can't capture the page.
        # Reject anything that isn't a JPEG so we fall through to the placeholder.
        if 'jpeg' not in content_type and not data.startswith(b'\xff\xd8\xff'):
            return False, f"API returned non-JPEG content ({content_type or 'unknown'}) - likely a placeholder"

        with open(output_path, 'wb') as f:
            f.write(data)

        return True, "Screenshot captured with API"

    except Exception as e:
        return False, f"API error: {str(e)}"

def capture_with_screencapture(url, output_path):
    """Fallback: Use macOS screencapture with Safari (macOS only)."""
    try:
        print(f"  🖥️  Using macOS Safari to capture {url}")

        # Open URL in Safari and take screenshot (requires macOS)
        # This is a fallback and requires manual interaction
        # Not recommended for automation

        return False, "macOS screencapture requires manual interaction"

    except Exception as e:
        return False, f"screencapture error: {str(e)}"

def create_placeholder_image(output_path, message="Preview Not Available"):
    """Create a simple placeholder image."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Create blank image
        img = Image.new('RGB', (TARGET_WIDTH, TARGET_HEIGHT), color='#2c3e50')
        draw = ImageDraw.Draw(img)

        # Add text
        try:
            # Try to use a nice font
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        except (OSError, IOError):
            font = ImageFont.load_default()

        # Center text
        text = message
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        position = ((TARGET_WIDTH - text_width) // 2, (TARGET_HEIGHT - text_height) // 2)
        draw.text(position, text, fill='#ecf0f1', font=font)

        # Save
        img.save(output_path, 'JPEG', quality=85, optimize=True)

        # Write a sidecar marker so is_preview_good() knows this is a placeholder
        # (and the next run should retry capture) regardless of file size.
        out_path = Path(output_path)
        marker_dir = out_path.parent / '.placeholders'
        marker_dir.mkdir(parents=True, exist_ok=True)
        (marker_dir / (out_path.name + '.placeholder')).touch()

        return True, "Created placeholder image"

    except ImportError:
        return False, "Pillow not installed (pip install Pillow)"
    except Exception as e:
        return False, f"Placeholder error: {str(e)}"

def _pillow_available():
    """Return True if Pillow can be imported.

    Lets callers tell "this capture is garbage" apart from "this machine
    can't process images at all" - optimize_image() reports both as a
    plain False, but they call for opposite responses.
    """
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def optimize_image(image_path):
    """Optimize and resize image to target dimensions.

    Doubles as the decode check for a fresh capture: a file Pillow can't
    open is not a usable preview, whatever the capture method claimed.
    """
    try:
        from PIL import Image

        print("  🔧 Optimizing image...")

        # Open image
        img = Image.open(image_path)

        # Convert to RGB if needed
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Calculate resize dimensions (maintain aspect ratio)
        aspect = img.width / img.height
        if aspect > TARGET_WIDTH / TARGET_HEIGHT:
            # Width is limiting factor
            new_width = TARGET_WIDTH
            new_height = int(TARGET_WIDTH / aspect)
        else:
            # Height is limiting factor
            new_height = TARGET_HEIGHT
            new_width = int(TARGET_HEIGHT * aspect)

        # Resize with high-quality algorithm
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Save optimized
        img.save(image_path, 'JPEG', quality=85, optimize=True)

        file_size = os.path.getsize(image_path)
        print(f"  ✅ Optimized to {file_size // 1024}KB ({new_width}x{new_height})")

        return True, f"Optimized to {file_size // 1024}KB"

    except ImportError:
        return False, "Pillow not installed"
    except Exception as e:
        return False, f"Optimization error: {str(e)}"

def update_preview_mapping(url, image_filename):
    """Update preview-mapping.json with new entry."""
    try:
        # Load existing mapping
        if PREVIEW_MAPPING.exists():
            with open(PREVIEW_MAPPING, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
        else:
            mapping = {}

        # Add new entry
        mapping[url] = f"img/previews/{image_filename}"

        # Sort by URL for consistency
        mapping = dict(sorted(mapping.items()))

        # Save
        with open(PREVIEW_MAPPING, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)
            f.write('\n')  # Add trailing newline

        print("  📋 Updated preview-mapping.json")
        return True

    except Exception as e:
        print(f"  ⚠️  Could not update preview-mapping.json: {e}")
        return False

def check_existing_preview(url):
    """Check if a good preview already exists for this URL."""
    if not PREVIEW_MAPPING.exists():
        return None

    try:
        with open(PREVIEW_MAPPING, 'r', encoding='utf-8') as f:
            mapping = json.load(f)

        preview_path = mapping.get(url)
        if preview_path and is_preview_good(preview_path):
            return preview_path

        return None

    except Exception:
        return None

def generate_preview(url, output_filename=None, force=False):
    """
    Generate preview image for a URL.

    Args:
        url: URL to capture
        output_filename: Optional custom filename
        force: Force regeneration even if exists

    Returns:
        (success, image_path, message)
    """
    print(f"\n🖼️  Generating preview for: {url}")

    # Check if preview already exists
    if not force:
        existing = check_existing_preview(url)
        if existing:
            print(f"  ✅ Preview already exists: {existing}")
            return True, existing, "Preview already exists"

    # Generate filename
    if not output_filename:
        output_filename = generate_filename_from_url(url)

    # Ensure it ends with .jpg
    if not output_filename.endswith('.jpg'):
        output_filename += '.jpg'

    # Create output path
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    output_path = PREVIEW_DIR / output_filename

    print(f"  📁 Output: img/previews/{output_filename}")

    # Try capture methods in order of preference. og:image first because
    # for resources that have one it's free, fast, and higher quality than
    # a viewport screenshot. Playwright handles everything else.
    methods = [
        capture_from_og_image,
        capture_with_playwright,
        capture_with_screenshot_api,
        # capture_with_screencapture,  # Skip manual method
    ]

    # Capture into a temp sibling and promote it only once Pillow proves it
    # decodes. Two reasons this isn't written straight to output_path:
    # a method that reports success while writing bytes Pillow can't read
    # would otherwise leave that file on disk as the preview (an SVG og:image
    # did exactly that), and a failed regeneration would clobber a good
    # existing preview. The name keeps a .jpg extension because Playwright
    # picks its output format from the path's suffix.
    tmp_path = output_path.with_name(output_path.stem + '.capture-tmp.jpg')
    marker = output_path.parent / '.placeholders' / (output_path.name + '.placeholder')

    success = False
    try:
        for method in methods:
            result, message = method(url, tmp_path)
            if not result:
                print(f"  ⚠️  {message}")
                tmp_path.unlink(missing_ok=True)
                continue
            print(f"  ✅ {message}")

            # Decode check - see optimize_image's docstring. A capture that
            # can't be opened doesn't count as one, so fall through to the
            # next method rather than shipping an unreadable file.
            optimize_result, optimize_msg = optimize_image(tmp_path)
            if optimize_result:
                success = True
                break
            print(f"  ⚠️  {optimize_msg}")
            tmp_path.unlink(missing_ok=True)
            if not _pillow_available():
                # Environment problem, not a bad capture. Every remaining
                # path needs Pillow too, so stop instead of burning a
                # Playwright launch and a thum.io request to fail the same way.
                return False, None, "Pillow not installed - cannot generate previews"
            print("  🗑️  Discarded undecodable capture, trying next method")

        if success:
            tmp_path.replace(output_path)
            # Real capture - clear any stale placeholder marker from a prior run.
            if marker.exists():
                marker.unlink()
        else:
            if output_path.exists() and not marker.exists():
                # Every method failed, but a real preview from an earlier run
                # is already on disk. Keep it: stamping "Preview Not Available"
                # over a working screenshot because of one transient failure
                # is a downgrade, and --batch-auto never reaches here anyway
                # (it only processes URLs with no good preview).
                print("  ↩️  All capture methods failed - keeping existing preview")
            else:
                print("  📝 Creating placeholder image...")
                result, message = create_placeholder_image(output_path)
                if not result:
                    return False, None, "Failed to create preview or placeholder"
                print(f"  ✅ {message}")
                optimize_result, optimize_msg = optimize_image(output_path)
                if not optimize_result:
                    print(f"  ⚠️  {optimize_msg}")
    finally:
        # Never leave a half-written capture behind for generate_webp.py
        # or a later run to trip over.
        tmp_path.unlink(missing_ok=True)

    # Update mapping
    update_preview_mapping(url, output_filename)

    relative_path = f"img/previews/{output_filename}"
    return True, relative_path, "Preview generated successfully"

def fix_html_image_paths():
    """Rewrite every card's <img src> in the catalog pages to match
    preview-mapping.json.

    Why this exists: contributors (including the weekly Update Resources
    workflow's model) add new cards with `<img src="img/previews/foo.jpg">`
    using whatever filename they happen to pick. The screenshot generator
    derives its own filename from the URL via generate_filename_from_url()
    and writes to that path - so the file on disk and the path the HTML
    points to drift, leaving broken image references on the live site.

    Using preview-mapping.json as the source of truth, this function walks
    every resource card in the listed pages and rewrites its <img src>
    to whatever the mapping says. Cards whose URL isn't in the mapping
    yet are skipped (the screenshot step will populate them on a future
    run, which then re-runs this).

    Returns the count of cards rewritten.
    """
    import re

    if not PREVIEW_MAPPING.exists():
        print("⚠️  preview-mapping.json not found - nothing to rewrite.")
        return 0

    with open(PREVIEW_MAPPING, 'r', encoding='utf-8') as f:
        mapping = json.load(f)

    repo_root = Path(__file__).parent.parent
    pages = [
        repo_root / 'resources.html',
        repo_root / 'ctfs.html',
        repo_root / 'threat-research.html',
        repo_root / 'conferences.html',
        repo_root / 'cloud-security-reading-list.html',
    ]

    # Match a full resource-card block (anchor through the closing </a>)
    # in either of the two layouts the site uses. The DOTALL flag lets `.`
    # span newlines so the card body matches.
    card_patterns = [
        # Resources / CTFs / threat-research / conferences: card-link wraps
        # the whole card and points to the external URL.
        re.compile(
            r'(<a\s+href="(?P<url>[^"]+)"[^>]*class="card-link"[^>]*>'
            r'(?P<body>.*?)'
            r'</a>)',
            re.DOTALL,
        ),
        # Reading-list layout: <a> sits inside an <h3> inside .resource-card.
        # The img is a sibling of the h3 within the same .resource-card.
        re.compile(
            r'(<div\s+class="resource-card"[^>]*>\s*'
            r'<h3>\s*<a\s+href="(?P<url>[^"]+)"[^>]*>[^<]*</a>\s*</h3>'
            r'(?P<body>.*?)'
            r'</div>)',
            re.DOTALL,
        ),
    ]

    img_src_re = re.compile(r'(<img\b[^>]*\bsrc=")([^"]+)(")')
    # The <img> is usually wrapped in <picture> with a WebP <source> (see
    # tools/wrap_img_webp.py). The <source srcset> must track the <img src>:
    # a WebP-capable browser fetches the srcset and does NOT fall back to the
    # <img> if it 404s, so a stale srcset is a *broken* card, not a slow one.
    source_srcset_re = re.compile(r'(<source\b[^>]*\bsrcset=")([^"]+)(")')
    picture_re = re.compile(
        r'<picture\b[^>]*>\s*(?:<source\b[^>]*>\s*)*(?P<img><img\b[^>]*>)\s*</picture>',
        re.DOTALL | re.IGNORECASE,
    )

    def unwrap_picture(html: str) -> str:
        """Reduce <picture><source ...><img ...></picture> to the bare <img>."""
        return picture_re.sub(lambda m: m.group('img'), html)

    total_rewrites = 0
    for page in pages:
        if not page.exists():
            continue
        original = page.read_text(encoding='utf-8')
        rewrites_this_page = 0

        def rewrite_card(match, _mapping=mapping):
            # `match` is the whole card block. We only want to touch the
            # <img src> *inside* this card, not anywhere else on the page.
            nonlocal rewrites_this_page
            full = match.group(0)
            url = match.group('url')
            correct_path = _mapping.get(url)
            if not correct_path:
                # Not in the mapping yet - leave the card alone.
                return full
            # Some entries in the wild use a leading slash. Normalize to
            # the same form the HTML uses (no leading slash, relative).
            correct_path = correct_path.lstrip('/')

            def swap_src(m):
                nonlocal rewrites_this_page
                old = m.group(2)
                # Only rewrite if this is a preview image and the path is
                # actually different - avoids gratuitous edits and skips
                # things like the site logo if it ever appears in a card.
                if 'img/previews/' not in old:
                    return m.group(0)
                if old.lstrip('/') == correct_path:
                    return m.group(0)
                rewrites_this_page += 1
                return f'{m.group(1)}{correct_path}{m.group(3)}'

            webp_path = re.sub(r'\.(jpe?g|png)$', '.webp', correct_path, flags=re.I)
            webp_exists = (
                webp_path != correct_path and (repo_root / webp_path).is_file()
            )

            def swap_srcset(m):
                nonlocal rewrites_this_page
                old = m.group(2)
                if 'img/previews/' not in old:
                    return m.group(0)
                if old.lstrip('/') == webp_path:
                    return m.group(0)
                rewrites_this_page += 1
                return f'{m.group(1)}{webp_path}{m.group(3)}'

            full = img_src_re.sub(swap_src, full)
            if webp_exists:
                full = source_srcset_re.sub(swap_srcset, full)
            else:
                # No WebP for the mapped path, so there's nothing valid for a
                # <source> to point at. Unwrap to a bare <img>; a later
                # generate_webp.py + wrap_img_webp.py run re-wraps it.
                unwrapped = unwrap_picture(full)
                if unwrapped != full:
                    rewrites_this_page += 1
                full = unwrapped
            return full

        updated = original
        for pat in card_patterns:
            updated = pat.sub(rewrite_card, updated)

        if updated != original:
            page.write_text(updated, encoding='utf-8')
            print(f"  ✏️  {page.name}: rewrote {rewrites_this_page} <img src> path(s)")
            total_rewrites += rewrites_this_page

    if total_rewrites == 0:
        print("✅ All preview image paths already match preview-mapping.json")
    else:
        print(f"\n✅ Rewrote {total_rewrites} <img src> path(s) total")
    return total_rewrites


def extract_urls_from_resources_html():
    """Extract card-link URLs from pages that render preview images without good previews."""
    import re

    repo_root = Path(__file__).parent.parent
    pages = [
        repo_root / 'resources.html',
        repo_root / 'ctfs.html',
        repo_root / 'threat-research.html',
        repo_root / 'conferences.html',
        repo_root / 'cloud-security-reading-list.html',
    ]
    # Match either `<a class="card-link" href="...">` (resources/ctfs/etc.)
    # or `<h3><a href="...">` inside a .resource-card (reading-list pattern).
    patterns = [
        re.compile(r'<a\s+href="([^"]+)"[^>]*class="card-link"'),
        re.compile(r'<div\s+class="resource-card"[^>]*>\s*<h3>\s*<a\s+href="([^"]+)"', re.DOTALL),
    ]

    all_urls = []
    seen = set()
    for page in pages:
        if not page.exists():
            continue
        content = page.read_text(encoding='utf-8')
        for pattern in patterns:
            for url in pattern.findall(content):
                # Skip relative / internal links - we only screenshot external URLs
                if not url.startswith(('http://', 'https://')):
                    continue
                if url not in seen:
                    seen.add(url)
                    all_urls.append(url)

    urls_needing_previews = [
        u for u in all_urls
        if u not in PREVIEW_IGNORE_URLS and not check_existing_preview(u)
    ]
    return urls_needing_previews

def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python3 tools/generate_preview.py <url> [output_filename]")
        print("  python3 tools/generate_preview.py --check resources.html")
        print("  python3 tools/generate_preview.py --batch urls.txt")
        print("  python3 tools/generate_preview.py --fix-html")
        return 1

    if sys.argv[1] == '--fix-html':
        print("🔧 Rewriting card <img src> paths to match preview-mapping.json")
        fix_html_image_paths()
        return 0

    if sys.argv[1] == '--check':
        print("🔍 Checking for resources without previews...")
        urls = extract_urls_from_resources_html()

        if not urls:
            print("✅ All resources have preview images!")
            return 0

        print(f"\n📋 Found {len(urls)} resources without previews:\n")
        for url in urls:
            print(f"  • {url}")

        print("\n💡 Generate previews with:")
        print("   python3 tools/generate_preview.py --batch-auto")

        return 0

    elif sys.argv[1] == '--batch-auto':
        print("🔄 Generating previews for all resources without images...")
        urls = extract_urls_from_resources_html()

        if not urls:
            print("✅ All resources have preview images!")
            return 0

        print(f"\n📋 Processing {len(urls)} URLs...\n")

        success_count = 0
        for i, url in enumerate(urls, 1):
            print(f"\n[{i}/{len(urls)}] Processing {url}")
            result, path, message = generate_preview(url)
            if result:
                success_count += 1
            time.sleep(1)  # Rate limiting

        print(f"\n✅ Generated {success_count}/{len(urls)} previews")
        return 0

    else:
        # Single URL
        url = sys.argv[1]
        output_filename = sys.argv[2] if len(sys.argv) > 2 else None

        result, path, message = generate_preview(url, output_filename, force=True)

        if result:
            print(f"\n✅ Success! Preview saved to: {path}")
            return 0
        else:
            print(f"\n❌ Failed: {message}")
            return 1

if __name__ == '__main__':
    sys.exit(main())
