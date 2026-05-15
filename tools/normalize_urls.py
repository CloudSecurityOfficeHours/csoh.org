#!/usr/bin/env python3
"""
URL Normalizer for CSOH Site

Scans all HTML files, strips tracking parameters, upgrades HTTP to HTTPS,
resolves redirecting URLs, and optionally replaces them in-place.

Usage:
    python3 tools/normalize_urls.py              # Dry-run (default)
    python3 tools/normalize_urls.py --apply       # Apply changes
    python3 tools/normalize_urls.py --skip-resolve # Only strip params + HTTPS upgrade
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

sys.path.insert(0, str(Path(__file__).parent))
from check_url_safety import (resolve_urls_concurrent, SHORTENER_DOMAINS,
                              URLSafetyChecker)
from check_all_site_urls import extract_urls_from_html

# --- Constants -----------------------------------------------------------

TRACKING_PARAMS = {
    # Google / GA4
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'utm_id', 'utm_source_platform', 'utm_creative_format',
    'utm_marketing_tactic',
    # Click IDs
    'fbclid', 'gclid', 'msclkid', 'dclid', 'twclid', 'li_fat_id',
    # Mailchimp
    'mc_cid', 'mc_eid',
    # Eloqua / marketing automation
    '_mc', 'cid', 'sp_aid', 'elq_cid', 'sp_eh', 'sp_cid',
    'elqTrackId', 'elqTrack', 'assetType', 'assetId',
    'recipientId', 'campaignId', 'siteId',
    # HubSpot
    'hsa_cam', 'hsa_grp', 'hsa_mt', 'hsa_src', 'hsa_ad', 'hsa_acc',
    'hsa_net', 'hsa_ver', 'hsa_la', 'hsa_ol', 'hsa_kw', 'hsa_tgt',
    # Misc
    'ref', 'ref_', 'ref_src', 'ref_url', 'rdt',
    # Amazon
    'social_share', 'titlesource', 'bestformat',
    # Beehiiv
    '_bhlid',
}

# Domains that block bots — skip HTTP resolution (sourced from .lychee.toml)
BOT_BLOCKED_DOMAINS = [
    'linkedin.com', 'web.archive.org',
    'blog.appsecco.com', 'bleepingcomputer.com', 'community.sap.com',
    'darkreading.com', 'dl.acm.org', 'fiverr.com', 'glassdoor.com',
    'imdb.com', 'indeed.com', 'instagram.com', 'mdpi.com', 'meco.org',
    'medium.com', 'nexos.ai', 'nytimes.com', 'openai.com',
    'help.otter.ai', 'reddit.com', 'rsaconference.com',
    'sec-consult.com', 'securitytrails.com', 'shodan.io',
    'substack.com', 'training.cloudsecurityalliance.org', 'uber.com',
    'udemy.com', 'upwork.com', 'washingtontimes.com', 'zoomeye.org',
    'blackhat.com', 'euvd.enisa.europa.eu', 'gitconnected.com',
    'jobs.sap.com', 'programs.com', 'trustoncloud.com',
    'careersinaudit.com',
]

# Extend shortener list with Amazon short links
SHORTENER_DOMAINS_EXT = list(SHORTENER_DOMAINS) + ['a.co']

# Domains that only serve HTTP (HTTPS is broken or unsupported).
# upgrade_scheme() will leave these as http:// so links don't break.
HTTP_ONLY_DOMAINS = {
    'flaws.cloud',
    'flaws2.cloud',
}

# --- Utility functions ---------------------------------------------------


def strip_tracking_params(url):
    """Remove tracking/analytics query parameters from a URL."""
    try:
        parsed = urlparse(url)
        if not parsed.query:
            return url
        params = parse_qs(parsed.query, keep_blank_values=True)
        cleaned = {k: v for k, v in params.items()
                   if k.lower() not in TRACKING_PARAMS}
        if cleaned == params:
            return url  # nothing stripped
        new_query = urlencode(cleaned, doseq=True) if cleaned else ''
        return urlunparse(parsed._replace(query=new_query))
    except Exception:
        return url


def upgrade_scheme(url):
    """Upgrade http:// to https:// (skip .onion, localhost, private IPs,
    and domains known to not support HTTPS)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme != 'http':
            return url
        host = (parsed.hostname or '').lower()
        if host.endswith('.onion') or host in ('localhost', '127.0.0.1'):
            return url
        # Skip private and link-local IPs (e.g. 169.254.169.254 AWS metadata)
        if _is_private_ip(host):
            return url
        # Skip domains that don't support HTTPS (upgrade would break the link)
        if host in HTTP_ONLY_DOMAINS:
            return url
        return urlunparse(parsed._replace(scheme='https'))
    except Exception:
        return url


def _is_private_ip(host):
    """Check if host is a private, link-local, or loopback IP address."""
    import ipaddress
    try:
        addr = ipaddress.ip_address(host)
        return addr.is_private or addr.is_link_local or addr.is_loopback
    except ValueError:
        return False


def is_shortener(url):
    """Check if URL is from a known shortener domain."""
    try:
        domain = urlparse(url).netloc.lower()
        return any(domain == sd or domain.endswith('.' + sd)
                   for sd in SHORTENER_DOMAINS_EXT)
    except Exception:
        return False


def is_meaningful_redirect(original, resolved):
    """Return True if the redirect is worth normalizing (not just noise)."""
    if original == resolved:
        return False

    # Always expand shortener domains
    if is_shortener(original):
        return True

    try:
        o = urlparse(original)
        r = urlparse(resolved)
    except Exception:
        return False

    # Ignore scheme-only changes (handled by upgrade_scheme)
    if (o._replace(scheme='') == r._replace(scheme='')):
        return False

    # Skip bot-verification / challenge redirects (not real destinations)
    bot_challenge_markers = ('__verifybrowser', '__challenge', 'captcha',
                             '_bot_check')
    if any(marker in r.path.lower() for marker in bot_challenge_markers):
        return False

    # All other redirects are meaningful — including trailing-slash
    # and www-prefix differences, which are real HTTP 301s that cost
    # an extra round-trip for every visitor.
    return True


# --- Main logic ----------------------------------------------------------


def is_own_domain(url):
    """Return True for URLs pointing at csoh.org itself.

    These must never be rewritten by this script — canonical, og:url,
    twitter:image, internal navigation, RSS alternate links, etc. all
    reference our own domain. Following a 301 from /meetings.html to
    /sessions.html (a real same-site redirect) and "normalizing" the
    canonical to point at the redirect target would silently consolidate
    two distinct pages into one in search engines.
    """
    try:
        host = urlparse(url).netloc.lower()
    except Exception:
        return False
    return host == 'csoh.org' or host.endswith('.csoh.org')


def collect_all_urls():
    """Scan all HTML files and return {filepath: [urls]} and deduplicated list.

    Same-domain (csoh.org) URLs are excluded — see is_own_domain for why.
    """
    workspace = Path(__file__).parent.parent
    html_files = sorted(workspace.glob('*.html'))

    file_urls = {}
    all_unique = []
    seen = set()

    for path in html_files:
        urls = [u for u in extract_urls_from_html(path) if not is_own_domain(u)]
        file_urls[path] = urls
        for url in urls:
            if url not in seen:
                seen.add(url)
                all_unique.append(url)

    return file_urls, all_unique


def build_replacement_map(all_unique, skip_resolve=False, timeout=10,
                          workers=10):
    """Build {original_url: final_url} for all URLs that need changing."""
    replacements = {}  # original -> final
    categories = {
        'tracking_stripped': [],
        'scheme_upgraded': [],
        'redirect_resolved': [],
        'skipped_bot_blocked': [],
        'skipped_error': [],
        'skipped_trivial': [],
        'skipped_unsafe_destination': [],
    }

    safety_checker = URLSafetyChecker()

    # Phase 1: Strip tracking params
    after_strip = {}
    for url in all_unique:
        stripped = strip_tracking_params(url)
        after_strip[url] = stripped
        if stripped != url:
            categories['tracking_stripped'].append((url, stripped))

    # Phase 2: Upgrade HTTP -> HTTPS
    after_scheme = {}
    for url, stripped in after_strip.items():
        upgraded = upgrade_scheme(stripped)
        after_scheme[url] = upgraded
        if upgraded != stripped:
            categories['scheme_upgraded'].append((url, upgraded))

    # Phase 3: Resolve redirects
    if not skip_resolve:
        # Resolve the post-cleanup URLs (not originals) to avoid double-redirects
        urls_to_resolve = list(set(after_scheme.values()))

        resolution_map = resolve_urls_concurrent(
            urls_to_resolve,
            max_workers=workers,
            timeout=timeout,
            skip_domains=BOT_BLOCKED_DOMAINS,
        )

        for original_url in all_unique:
            cleaned_url = after_scheme[original_url]
            resolved, error = resolution_map.get(cleaned_url,
                                                 (cleaned_url, None))

            if error:
                categories['skipped_error'].append(
                    (original_url, cleaned_url, error))
                # Still apply param-strip / scheme-upgrade even if resolve fails
                if cleaned_url != original_url:
                    replacements[original_url] = cleaned_url
                continue

            # Check if the domain was bot-blocked (resolved == cleaned means skipped)
            try:
                domain = urlparse(cleaned_url).netloc.lower()
                if any(bd in domain for bd in BOT_BLOCKED_DOMAINS):
                    categories['skipped_bot_blocked'].append(original_url)
                    if cleaned_url != original_url:
                        replacements[original_url] = cleaned_url
                    continue
            except Exception:
                pass

            if is_meaningful_redirect(cleaned_url, resolved):
                # Strip tracking params from the resolved URL too
                resolved = strip_tracking_params(resolved)

                # Safety-check the resolved destination before writing it.
                # A URL that was safe at check-time can redirect to an
                # unsafe destination (shortener flip, stale redirect, etc.).
                # Block the replacement if the destination fails safety.
                safety = safety_checker.check_url(resolved)
                if not safety.get('safe', True) or safety.get('errors'):
                    categories['skipped_unsafe_destination'].append(
                        (original_url, cleaned_url, resolved,
                         safety.get('errors', []),
                         safety.get('warnings', [])))
                    # Fall back to the pre-resolution URL (param-stripped +
                    # scheme-upgraded) rather than writing an unsafe target.
                    if cleaned_url != original_url:
                        replacements[original_url] = cleaned_url
                    continue

                categories['redirect_resolved'].append(
                    (original_url, cleaned_url, resolved))
                replacements[original_url] = resolved
            else:
                if resolved != cleaned_url:
                    categories['skipped_trivial'].append(
                        (original_url, cleaned_url, resolved))
                # Still apply param-strip / scheme-upgrade
                if cleaned_url != original_url:
                    replacements[original_url] = cleaned_url
    else:
        # No resolution — only apply param strip + scheme upgrade
        for original_url in all_unique:
            cleaned_url = after_scheme[original_url]
            if cleaned_url != original_url:
                replacements[original_url] = cleaned_url

    return replacements, categories


def apply_to_file(filepath, replacements, dry_run=True):
    """Apply URL replacements to a single HTML file. Returns change count."""
    content = filepath.read_text(encoding='utf-8')
    original_content = content
    count = 0

    for old_url, new_url in replacements.items():
        if old_url in content:
            content = content.replace(old_url, new_url)
            count += content != original_content  # at least one change

    if content != original_content:
        count = sum(1 for old in replacements if old in original_content)
        if not dry_run:
            filepath.write_text(content, encoding='utf-8')

    return count


def print_report(replacements, categories, file_changes, dry_run):
    """Print a human-readable summary."""
    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"\n{'=' * 70}")
    print(f"URL NORMALIZATION REPORT ({mode})")
    print(f"{'=' * 70}\n")

    if categories['tracking_stripped']:
        print(f"Tracking parameters stripped: {len(categories['tracking_stripped'])}")
        for old, new in categories['tracking_stripped']:
            print(f"  {old}")
            print(f"    -> {new}")
        print()

    if categories['scheme_upgraded']:
        print(f"HTTP upgraded to HTTPS: {len(categories['scheme_upgraded'])}")
        for old, new in categories['scheme_upgraded']:
            print(f"  {old}")
            print(f"    -> {new}")
        print()

    if categories['redirect_resolved']:
        print(f"Redirects resolved: {len(categories['redirect_resolved'])}")
        for orig, cleaned, resolved in categories['redirect_resolved']:
            if cleaned != orig:
                print(f"  {orig}")
                print(f"    (cleaned) {cleaned}")
                print(f"    -> {resolved}")
            else:
                print(f"  {orig}")
                print(f"    -> {resolved}")
        print()

    if categories['skipped_trivial']:
        print(f"Skipped (trivial redirect): {len(categories['skipped_trivial'])}")
        for orig, cleaned, resolved in categories['skipped_trivial']:
            print(f"  {cleaned} -> {resolved}")
        print()

    if categories['skipped_bot_blocked']:
        print(f"Skipped (bot-blocked domain): {len(categories['skipped_bot_blocked'])}")
        print()

    if categories['skipped_error']:
        print(f"Skipped (resolution error): {len(categories['skipped_error'])}")
        for orig, cleaned, error in categories['skipped_error']:
            print(f"  {cleaned}: {error}")
        print()

    if categories['skipped_unsafe_destination']:
        print(f"❌ UNSAFE redirect destinations (blocked): "
              f"{len(categories['skipped_unsafe_destination'])}")
        for orig, cleaned, resolved, errors, warnings in \
                categories['skipped_unsafe_destination']:
            print(f"  {orig}")
            print(f"    -> resolved to: {resolved}")
            for err in errors:
                print(f"    • {err}")
            for warn in warnings:
                print(f"    ⚠ {warn}")
        print()

    # Per-file summary
    changed_files = {f: c for f, c in file_changes.items() if c > 0}
    if changed_files:
        print(f"Files {'to update' if dry_run else 'updated'}: {len(changed_files)}")
        for filepath, count in sorted(changed_files.items(),
                                       key=lambda x: x[0].name):
            print(f"  {filepath.name}: {count} URL(s)")
        print()

    total = len(replacements)
    print(f"{'=' * 70}")
    print(f"Total URL changes: {total}")
    if dry_run and total > 0:
        print("Run with --apply to write changes.")
    print(f"{'=' * 70}\n")

    return total


def main():
    parser = argparse.ArgumentParser(
        description='Normalize URLs across CSOH HTML files')
    parser.add_argument('--apply', action='store_true',
                        help='Apply changes (default is dry-run)')
    parser.add_argument('--skip-resolve', action='store_true',
                        help='Only strip tracking params + HTTPS upgrade')
    parser.add_argument('--timeout', type=int, default=10,
                        help='HTTP timeout per URL in seconds (default: 10)')
    parser.add_argument('--workers', type=int, default=10,
                        help='Concurrent resolution workers (default: 10)')
    args = parser.parse_args()

    dry_run = not args.apply

    print("Scanning HTML files for URLs...")
    file_urls, all_unique = collect_all_urls()
    total_refs = sum(len(u) for u in file_urls.values())
    print(f"Found {total_refs} URL references ({len(all_unique)} unique) "
          f"across {len(file_urls)} files\n")

    if not args.skip_resolve:
        print("Resolving URLs (this may take a minute)...")
    replacements, categories = build_replacement_map(
        all_unique,
        skip_resolve=args.skip_resolve,
        timeout=args.timeout,
        workers=args.workers,
    )

    # Apply to each file
    file_changes = {}
    for filepath, urls in file_urls.items():
        # Filter replacements to only URLs in this file
        file_repls = {old: new for old, new in replacements.items()
                      if old in urls}
        if file_repls:
            count = apply_to_file(filepath, file_repls, dry_run=dry_run)
            file_changes[filepath] = count
        else:
            file_changes[filepath] = 0

    total = print_report(replacements, categories, file_changes, dry_run)

    # Fail loudly if any redirect resolved to an unsafe destination —
    # block deploy regardless of dry-run / apply mode.
    if categories['skipped_unsafe_destination']:
        print("::error::One or more URLs on the site redirect to unsafe "
              "destinations. The originals were kept in HTML, but manual "
              "review is required. See the report above.")
        return 2

    # Exit 1 in dry-run mode if there are changes (useful for CI)
    if dry_run and total > 0:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
