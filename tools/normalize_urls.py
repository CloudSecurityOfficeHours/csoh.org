#!/usr/bin/env python3
"""
URL Normalizer for CSOH Site

Scans all HTML files, strips tracking parameters, upgrades HTTP to HTTPS,
resolves redirecting URLs, and optionally replaces them in-place.

Usage:
    python3 tools/normalize_urls.py              # Dry-run (default)
    python3 tools/normalize_urls.py --apply       # Apply changes
    python3 tools/normalize_urls.py --skip-resolve # Only strip params + HTTPS upgrade

    # Back redirect resolution with a persistent cache so only new URLs hit
    # the network (per-push CI). Add --refresh-cache to re-resolve everything
    # and rebuild the cache (monthly CI).
    python3 tools/normalize_urls.py --apply --cache tools/url_resolution_cache.json
"""

import argparse
import datetime as dt
import json
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
    # Google's newer pair, used where gclid is unavailable (iOS/consent mode)
    'wbraid', 'gbraid',
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

# Domains that block bots - skip HTTP resolution (sourced from .lychee.toml)
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


# A redirect that lands on a sign-in form says something about *our crawler's*
# auth state, not about the link. Following one rewrites a real destination
# into a login URL carrying that resolve session's throwaway tokens - Google's
# `dsh`/`ifkv`, Atlassian's `orgId`, GitHub's `return_to` - which expire within
# minutes. So the "normalized" link is then broken for everyone, permanently,
# including the readers who could have opened the original.
#
# This is the same shape as the bot-challenge guard in is_meaningful_redirect:
# an auth wall is a property of the fetch, not a canonical destination.
#
# Hosts whose only job is authentication. Landing here is always a wall.
AUTH_WALL_HOSTS = {
    'accounts.google.com', 'id.atlassian.com', 'auth.atlassian.com',
    'login.microsoftonline.com', 'login.live.com', 'account.live.com',
    'signin.aws.amazon.com', 'login.salesforce.com', 'login.okta.com',
}

# Sign-in paths on hosts that also serve real content, so the host alone
# cannot decide (github.com/login, gitlab.com/users/sign_in, SharePoint).
AUTH_WALL_PATH_MARKERS = (
    '/login', '/signin', '/sign_in', '/sso/', '/oauth/authorize',
    '/authenticate', '/session/new', '/users/sign_in', '/accounts/login',
    # GoatCounter sends an unauthenticated GET of the instance root to its
    # signup form with a 303. That rewrote our own analytics endpoint on
    # how-csoh-org-is-secured.html into `.../user/new/count`, which recorded
    # nothing, and put the same URL into the CSP that page documents.
    '/user/new',
    '/_layouts/15/authenticate.aspx',
)

# "Come back here once you have signed in" parameters. Requiring one is what
# separates a login *wall* from a page that merely lives at a /login path -
# github.com/Azure/login is a repository, and must stay resolvable.
AUTH_RETURN_PARAMS = {
    'continue', 'followup', 'return_to', 'returnurl', 'returnto',
    'redirect_uri', 'redirect_to', 'redirecturl', 'next', 'goto',
    'destination', 'relaystate', 'samlrequest',
}


def is_auth_wall(url):
    """Return True if `url` is a sign-in page rather than a real destination.

    Deliberately errs toward True. A false positive costs one un-normalized
    redirect - the original URL stays, and still works. A false negative
    writes an expired login URL into the page, which never works again.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    host = (parsed.hostname or '').lower()
    if any(host == h or host.endswith('.' + h) for h in AUTH_WALL_HOSTS):
        return True

    path = parsed.path.lower().rstrip('/')
    # The whole path IS the sign-in form (zoom.us/signin, github.com/login).
    # No return parameter needed - there is nothing else this page can be.
    if path in AUTH_WALL_PATH_MARKERS:
        return True
    # Otherwise the marker is only a hint, and needs corroborating: it has to
    # be a login path AND carry a "return here after sign-in" parameter.
    if not any(marker in path for marker in AUTH_WALL_PATH_MARKERS):
        return False

    try:
        params = {k.lower() for k in parse_qs(parsed.query,
                                              keep_blank_values=True)}
    except Exception:
        return False
    return bool(params & AUTH_RETURN_PARAMS)


def is_meaningful_redirect(original, resolved):
    """Return True if the redirect is worth normalizing (not just noise)."""
    if original == resolved:
        return False

    # Never follow a redirect onto a sign-in form. This has to sit above the
    # shortener rule below: a shortener expanding onto an auth wall is exactly
    # the case where "always expand" would write the broken URL.
    if is_auth_wall(resolved):
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

    # All other redirects are meaningful - including trailing-slash
    # and www-prefix differences, which are real HTTP 301s that cost
    # an extra round-trip for every visitor.
    return True


# --- Main logic ----------------------------------------------------------


def is_own_domain(url):
    """Return True for URLs pointing at csoh.org itself.

    These must never be rewritten by this script - canonical, og:url,
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

    Same-domain (csoh.org) URLs are excluded - see is_own_domain for why.
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


# --- Resolution cache ----------------------------------------------------
#
# Resolving every external URL's redirects over the network is the slowest
# part of a run (thousands of URLs, almost none of which actually redirect).
# The result is stable, so we persist {cleaned_url: {resolved, error}} to a
# JSON file. On an incremental run we only hit the network for URLs we've
# never seen; a periodic full refresh (--refresh-cache, run monthly) re-checks
# everything so a redirect or its destination drifting is still caught. URLs
# that drop off the site are pruned so the file can't grow without bound.
#
# Safety is unchanged: the downstream meaningful-redirect + destination
# safety-check still runs on every URL each run, cache hit or not - the cache
# only skips the *resolution* network call, never the safety decision.

CACHE_VERSION = 1
DEFAULT_CACHE_TTL_DAYS = 30


def load_cache(path):
    """Load the resolution cache, or return a fresh empty one."""
    try:
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and isinstance(data.get('entries'), dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {'version': CACHE_VERSION, 'last_full_refresh': None, 'entries': {}}


def save_cache(path, cache):
    """Write the cache with sorted keys so diffs stay minimal."""
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, indent=2, sort_keys=True)
        f.write('\n')


def _cache_is_stale(cache, ttl_days):
    """True if the cache has never had a full refresh, or it's older than TTL."""
    last = cache.get('last_full_refresh')
    if not last:
        return True
    try:
        last_date = dt.date.fromisoformat(last)
    except (TypeError, ValueError):
        return True
    return (dt.date.today() - last_date).days >= ttl_days


def resolve_urls_cached(urls_to_resolve, cache, *, refresh, ttl_days,
                        workers, timeout):
    """Like resolve_urls_concurrent, but back the network calls with `cache`.

    Mutates `cache` in place (adds newly resolved entries, prunes URLs no
    longer on the site, stamps last_full_refresh on a full run) and returns
    the {url: (resolved, error)} map for every URL in urls_to_resolve.
    """
    entries = cache.setdefault('entries', {})
    full = refresh or _cache_is_stale(cache, ttl_days)

    if full:
        to_fetch = list(urls_to_resolve)
    else:
        to_fetch = [u for u in urls_to_resolve if u not in entries]

    fetched = {}
    if to_fetch:
        fetched = resolve_urls_concurrent(
            to_fetch, max_workers=workers, timeout=timeout,
            skip_domains=BOT_BLOCKED_DOMAINS,
        )
        for url, (resolved, error) in fetched.items():
            entries[url] = {'resolved': resolved, 'error': error}

    resolution_map = {}
    for url in urls_to_resolve:
        if url in fetched:
            resolution_map[url] = fetched[url]
        elif url in entries:
            entry = entries[url]
            resolution_map[url] = (entry.get('resolved', url),
                                   entry.get('error'))
        else:
            resolution_map[url] = (url, None)

    # Prune cached URLs that are no longer referenced anywhere on the site.
    current = set(urls_to_resolve)
    for url in [u for u in entries if u not in current]:
        del entries[url]

    cache['version'] = CACHE_VERSION
    if full:
        cache['last_full_refresh'] = dt.date.today().isoformat()

    print(f"  Cache: {len(to_fetch)} resolved over network, "
          f"{len(urls_to_resolve) - len(to_fetch)} from cache "
          f"({'full refresh' if full else 'incremental'})")
    return resolution_map


def build_replacement_map(all_unique, skip_resolve=False, timeout=10,
                          workers=10, cache=None, refresh_cache=False,
                          ttl_days=DEFAULT_CACHE_TTL_DAYS):
    """Build {original_url: final_url} for all URLs that need changing."""
    replacements = {}  # original -> final
    categories = {
        'tracking_stripped': [],
        'scheme_upgraded': [],
        'redirect_resolved': [],
        'skipped_bot_blocked': [],
        'skipped_auth_wall': [],
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

        if cache is not None:
            resolution_map = resolve_urls_cached(
                urls_to_resolve, cache,
                refresh=refresh_cache, ttl_days=ttl_days,
                workers=workers, timeout=timeout,
            )
        else:
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

                # Reject a destination that is not safe to embed in HTML before
                # anything else looks at it.
                #
                # `resolved` can come straight from an external site's 308
                # Location header (see resolve_url in check_url_safety.py), and
                # a few lines below it is substituted into page text with a
                # plain str.replace - i.e. straight inside href="...". A server
                # that answers with
                #     Location: https://ok.example/a"><script src=...></script>
                # would have that markup written into every page linking to it,
                # committed by site-update-deploy.yml, and deployed. The most
                # realistic route in is a link whose domain expired and was
                # re-registered, which this repo already tracks as a recurring
                # class of dead link.
                #
                # A real URL never contains these characters unescaped, so
                # refusing them costs nothing and closes the injection.
                unsafe_chars = [c for c in '"\'<>`\\ \t\r\n' if c in resolved]
                if unsafe_chars or not resolved.startswith(('http://', 'https://')):
                    reason = (
                        f"illegal characters in redirect destination: "
                        f"{unsafe_chars!r}" if unsafe_chars
                        else "redirect destination is not an http(s) URL"
                    )
                    categories['skipped_unsafe_destination'].append(
                        (original_url, cleaned_url, resolved, [reason], []))
                    if cleaned_url != original_url:
                        replacements[original_url] = cleaned_url
                    continue

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
                if resolved != cleaned_url and is_auth_wall(resolved):
                    categories['skipped_auth_wall'].append(
                        (original_url, cleaned_url, resolved))
                elif resolved != cleaned_url:
                    categories['skipped_trivial'].append(
                        (original_url, cleaned_url, resolved))
                # Still apply param-strip / scheme-upgrade
                if cleaned_url != original_url:
                    replacements[original_url] = cleaned_url
    else:
        # No resolution - only apply param strip + scheme upgrade
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

    if categories['skipped_auth_wall']:
        print(f"Skipped (redirects to a sign-in wall): "
              f"{len(categories['skipped_auth_wall'])}")
        print("  These links were LEFT AS-IS on purpose. The destination is a "
              "login\n  form with single-use tokens, not a real page - see "
              "is_auth_wall().")
        for orig, cleaned, resolved in categories['skipped_auth_wall']:
            print(f"  {cleaned}")
            print(f"    -> (wall) {resolved[:110]}"
                  f"{'...' if len(resolved) > 110 else ''}")
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
    parser.add_argument('--cache', metavar='PATH', default=None,
                        help='Persist/reuse redirect resolutions at PATH. '
                             'Incremental: only new URLs hit the network.')
    parser.add_argument('--cache-ttl-days', type=int,
                        default=DEFAULT_CACHE_TTL_DAYS,
                        help='Force a full re-resolve when the cache is older '
                             f'than this (default: {DEFAULT_CACHE_TTL_DAYS})')
    parser.add_argument('--refresh-cache', action='store_true',
                        help='Re-resolve every URL and rebuild the cache now')
    args = parser.parse_args()

    dry_run = not args.apply

    print("Scanning HTML files for URLs...")
    file_urls, all_unique = collect_all_urls()
    total_refs = sum(len(u) for u in file_urls.values())
    print(f"Found {total_refs} URL references ({len(all_unique)} unique) "
          f"across {len(file_urls)} files\n")

    cache = load_cache(args.cache) if args.cache else None

    if not args.skip_resolve:
        print("Resolving URLs (this may take a minute)...")
    replacements, categories = build_replacement_map(
        all_unique,
        skip_resolve=args.skip_resolve,
        timeout=args.timeout,
        workers=args.workers,
        cache=cache,
        refresh_cache=args.refresh_cache,
        ttl_days=args.cache_ttl_days,
    )

    # Persist the cache even in dry-run - resolutions are read-only facts and
    # seeding the cache locally is the point of a dry-run with --cache.
    if args.cache and cache is not None and not args.skip_resolve:
        save_cache(args.cache, cache)

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

    # Fail loudly if any redirect resolved to an unsafe destination -
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
