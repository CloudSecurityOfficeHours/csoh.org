#!/usr/bin/env python3
"""
Check all URLs across every HTML file on the site for safety
(root plus breaches/, meetings/, portfolio/, homelab/, and howto/ subdirectories).

Three-phase pipeline:
  1. Extract  - collect all URLs from every HTML file (root + subdirs), deduplicate
  2. Resolve  - batch-resolve unique URLs concurrently (skip whitelisted domains);
                with --resolve-added-since REV, only URLs added since REV
  3. Check    - run safety checks on resolved URLs, per file
"""

import re
import subprocess
import sys
from pathlib import Path
from check_url_safety import URLSafetyChecker, resolve_urls_concurrent


# Regions whose text is sample content rather than links: code blocks and
# HTML comments. Blanked out before the prose URL sweep in
# extract_urls_from_html (attribute extraction is unaffected).
#
# <script> and <style> are deliberately NOT stripped, though an earlier
# version of this did strip them. Inline scripts are banned site-wide by
# check_no_inline_scripts.py, so the only <script> bodies here are JSON-LD -
# and JSON-LD `sameAs` carries ~66 real external URLs (Wikipedia entity
# pages, cloud-vendor pages, the analytics endpoint) that exist nowhere else
# in the document. Stripping <script> silently dropped every one of them from
# safety checking: not clickable by a reader, but consumed by crawlers and
# part of our entity graph, so still worth checking.
STRIP_NON_PROSE_RE = re.compile(r'(?is)<pre\b.*?</pre>|<code\b.*?</code>|<!--.*?-->')

# URLs that appear ONLY inside those regions. They are sample text rather than
# links a reader can click, so they are not safety-checked - but the count is
# printed on every run rather than dropped quietly. A check that bounds its own
# coverage without saying so reads as "covered everything" when it did not.
SKIPPED_IN_CODE = set()


def extract_urls_from_html(file_path, content=None):
    """Extract all URLs from an HTML file.

    Pass `content` to scan text that is not the file on disk (an earlier
    revision of it). Such a scan leaves SKIPPED_IN_CODE alone, since that
    count describes the pages being checked.
    """
    # XML namespace URIs are identifiers, not fetchable URLs - never normalize.
    # The SVG/XLink/XHTML/XML/MathML namespaces are spec-defined as the http://
    # form and rejected by HTML5 validators if rewritten to https://.
    XML_NAMESPACE_URIS = {
        'http://www.w3.org/2000/svg',
        'http://www.w3.org/1999/xlink',
        'http://www.w3.org/1999/xhtml',
        'http://www.w3.org/XML/1998/namespace',
        'http://www.w3.org/1998/Math/MathML',
        'http://www.w3.org/2001/xml-events',
    }

    urls = []
    note_skipped = content is None
    try:
        if content is None:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

        # Find all href attributes
        href_pattern = r'<a[^>]+href=["\'](https?://[^"\']+)["\']'
        urls.extend(re.findall(href_pattern, content))

        # Find all src attributes (images, scripts, iframes, etc.)
        src_pattern = r'<(?:img|script|iframe|source|video|audio)[^>]+src=["\'](https?://[^"\']+)["\']'
        urls.extend(re.findall(src_pattern, content))

        # Find any other http/https URLs that might be in content.
        #
        # This sweep exists to catch URLs sitting in prose rather than
        # in an attribute. It must NOT look inside <pre>, <code>, or HTML
        # comments: those hold sample text, not links the site offers a
        # reader.
        #
        # howto/regex-for-security.html teaches URL-matching patterns, so
        # it contains strings like `https://[a-z]+\.example\.com$`. That
        # matches the pattern below, and urlparse then reads the `[` as
        # the start of an IPv6 literal and raises. The gate fails closed on
        # a URL it cannot parse - which is the right call for a real URL -
        # so an unparseable *example* would block the whole housekeeping
        # run.
        #
        # href/src extraction above deliberately still runs over the whole
        # document, so a real link inside a <pre> is checked either way and
        # no actual link loses coverage here.
        url_pattern = r'https?://[^\s<>"\']+[^\s<>"\'.,;:!?)]'
        prose = STRIP_NON_PROSE_RE.sub(' ', content)
        prose_urls = re.findall(url_pattern, prose)
        urls.extend(prose_urls)
        if note_skipped:
            SKIPPED_IN_CODE.update(
                set(re.findall(url_pattern, content)) - set(prose_urls) - set(urls))

    except Exception as e:
        print(f"  Warning: Error reading {file_path}: {e}")

    # Remove duplicates while preserving order, and drop XML namespace URIs
    # (which are identifiers, not fetchable links) so the URL normalizer
    # never tries to "upgrade" them to https://.
    seen = set()
    unique_urls = []
    for url in urls:
        if url in XML_NAMESPACE_URIS:
            continue
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls


def urls_added_since(rev, workspace_root, file_urls):
    """URLs on the site now that were nowhere on it at git revision `rev`.

    Only files that changed since `rev` can hold a URL the site did not
    already have, so earlier revisions are read for those files alone.
    Returns None if git cannot answer, so the caller resolves everything.
    """
    def git(*args):
        return subprocess.run(['git', '-C', str(workspace_root), *args],
                              capture_output=True, text=True)

    # Compare the merge base with the working tree, not with HEAD, and add
    # untracked files: the URLs being checked are read from disk, so an
    # uncommitted page must count as changed.
    base = git('merge-base', rev, 'HEAD')
    if base.returncode == 0:
        rev = base.stdout.strip()
        diff = git('diff', '--name-only', rev)
        untracked = git('ls-files', '--others', '--exclude-standard')
    if base.returncode or diff.returncode or untracked.returncode:
        failed = base if base.returncode else diff if diff.returncode else untracked
        print(f"::warning::cannot diff against {rev} ({failed.stderr.strip()}); "
              "resolving every URL instead")
        return None
    changed = set(diff.stdout.splitlines()) | set(untracked.stdout.splitlines())

    before = set()
    unchanged_now = set()
    for path, urls in file_urls.items():
        rel = path.relative_to(workspace_root).as_posix()
        if rel not in changed:
            unchanged_now.update(urls)
            continue
        old = git('show', f'{rev}:{rel}')
        if old.returncode == 0:      # absent at rev means the file is new
            before.update(extract_urls_from_html(path, content=old.stdout))

    changed_now = {u for p, urls in file_urls.items()
                   if p.relative_to(workspace_root).as_posix() in changed
                   for u in urls}
    return changed_now - before - unchanged_now


def main():
    no_resolve = '--no-resolve' in sys.argv
    # --resolve-added-since REV: follow redirects only for URLs added since
    # REV. A pull request can only introduce the URLs it adds; the rest were
    # resolved when they arrived, and the weekly run and the push-to-main
    # gate re-resolve all of them. Every URL still gets the static checks.
    added_since = None
    if '--resolve-added-since' in sys.argv:
        added_since = sys.argv[sys.argv.index('--resolve-added-since') + 1]

    # Find all HTML files
    workspace_root = Path(__file__).parent.parent
    # Site-wide: root plus every published subdirectory of HTML pages.
    html_files = sorted(
        list(workspace_root.glob('*.html'))
        + list(workspace_root.glob('breaches/*.html'))
        + list(workspace_root.glob('meetings/*.html'))
        + list(workspace_root.glob('portfolio/*.html'))
        + list(workspace_root.glob('homelab/*.html'))
        + list(workspace_root.glob('howto/*.html'))
    )

    print("=" * 80)
    print("COMPREHENSIVE SITE-WIDE URL SAFETY CHECK")
    print("=" * 80)
    print()

    checker = URLSafetyChecker()

    # --- Phase 1: Extract all URLs from all files ---
    file_urls = {}  # {path: [urls]}
    all_unique_urls = []
    seen = set()

    for html_file in html_files:
        urls = extract_urls_from_html(html_file)
        file_urls[html_file] = urls
        for url in urls:
            if url not in seen:
                seen.add(url)
                all_unique_urls.append(url)

    total_urls = sum(len(u) for u in file_urls.values())
    print(f"Found {total_urls} URLs ({len(all_unique_urls)} unique) across {len(html_files)} files")
    if SKIPPED_IN_CODE:
        print(f"Not swept: {len(SKIPPED_IN_CODE)} URL-shaped strings found only "
              "inside <pre>/<code>/comments (sample text, not clickable links)")
    print()

    # --- Phase 2: Resolve unique URLs concurrently ---
    resolution_map = {}
    if not no_resolve:
        to_resolve = all_unique_urls
        added = urls_added_since(added_since, workspace_root, file_urls) if added_since else None
        if added is not None:
            to_resolve = [u for u in all_unique_urls if u in added]
            print(f"Resolving the {len(to_resolve)} URL(s) added since {added_since}; "
                  f"the other {len(all_unique_urls) - len(to_resolve)} get the "
                  "static checks only")
        print("Resolving URLs (skipping whitelisted domains)...")
        resolution_map = resolve_urls_concurrent(to_resolve)

        resolved_count = sum(1 for u, (r, _) in resolution_map.items() if r != u)
        error_count = sum(1 for _, (_, e) in resolution_map.items() if e)
        print(f"  Resolved: {resolved_count} URLs redirected to different destinations")
        if error_count:
            print(f"  Errors: {error_count} URLs could not be resolved (checking original)")
        print()
    else:
        print("Skipping URL resolution (--no-resolve)\n")

    # --- Phase 3: Check each file's URLs using resolution data ---
    all_results = {
        'safe': [],
        'suspicious': [],
        'unsafe': []
    }

    file_results = {}

    for html_file in html_files:
        urls = file_urls[html_file]
        print(f"Checking: {html_file.name}")

        if not urls:
            print("   No URLs found\n")
            continue

        print(f"   Found {len(urls)} URL(s)")

        file_safe = []
        file_suspicious = []
        file_unsafe = []

        for url in urls:
            resolved, error = resolution_map.get(url, (url, None))
            result = checker.check_url(url, resolved_url=resolved, resolve_error=error)

            if not result['safe']:
                file_unsafe.append((url, result))
                all_results['unsafe'].append((html_file.name, url, result))
            elif result['suspicious']:
                file_suspicious.append((url, result))
                all_results['suspicious'].append((html_file.name, url, result))
            else:
                file_safe.append((url, result))
                all_results['safe'].append((html_file.name, url, result))

        file_results[html_file.name] = {
            'safe': file_safe,
            'suspicious': file_suspicious,
            'unsafe': file_unsafe,
            'total': len(urls)
        }

        print(f"   Safe: {len(file_safe)}")
        if file_suspicious:
            print(f"   Suspicious: {len(file_suspicious)}")
        if file_unsafe:
            print(f"   Unsafe: {len(file_unsafe)}")
        print()

    # Print summary
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print()

    total_checked = len(all_results['safe']) + len(all_results['suspicious']) + len(all_results['unsafe'])

    print(f"Total HTML files scanned: {len(html_files)}")
    print(f"Total URLs checked: {total_checked}")
    print()
    print(f"  Safe:        {len(all_results['safe'])} ({len(all_results['safe'])/total_checked*100:.1f}%)")
    print(f"  Suspicious:  {len(all_results['suspicious'])} ({len(all_results['suspicious'])/total_checked*100:.1f}%)")
    print(f"  Unsafe:      {len(all_results['unsafe'])} ({len(all_results['unsafe'])/total_checked*100:.1f}%)")
    print()

    # Detailed results by file
    if any(file_results[f]['suspicious'] or file_results[f]['unsafe'] for f in file_results):
        print("=" * 80)
        print("DETAILED RESULTS BY FILE")
        print("=" * 80)
        print()

        for filename in sorted(file_results.keys()):
            results = file_results[filename]

            if results['suspicious'] or results['unsafe']:
                print(f"  {filename}")
                print(f"   Total URLs: {results['total']}")
                print()

                if results['unsafe']:
                    print("   UNSAFE URLs:")
                    for url, result in results['unsafe']:
                        print(f"      {url}")
                        if result.get('redirected') and result.get('resolved_url'):
                            print(f"        -> Resolved to: {result['resolved_url']}")
                        for reason in result['errors']:
                            print(f"        - {reason}")
                    print()

                if results['suspicious']:
                    print("   SUSPICIOUS URLs:")
                    for url, result in results['suspicious']:
                        print(f"      {url}")
                        if result.get('redirected') and result.get('resolved_url'):
                            print(f"        -> Resolved to: {result['resolved_url']}")
                        for reason in result['warnings']:
                            print(f"        - {reason}")
                    print()

    # Print all suspicious URLs summary
    if all_results['suspicious']:
        print("=" * 80)
        print(f"SUSPICIOUS URLS ({len(all_results['suspicious'])})")
        print("=" * 80)
        print()
        for filename, url, result in all_results['suspicious']:
            print(f"  {filename}")
            print(f"   {url}")
            if result.get('redirected') and result.get('resolved_url'):
                print(f"   -> Resolved to: {result['resolved_url']}")
            for reason in result['warnings']:
                print(f"   - {reason}")
            print()

    # Print all unsafe URLs summary
    if all_results['unsafe']:
        print("=" * 80)
        print(f"UNSAFE URLS ({len(all_results['unsafe'])})")
        print("=" * 80)
        print()
        for filename, url, result in all_results['unsafe']:
            print(f"  {filename}")
            print(f"   {url}")
            if result.get('redirected') and result.get('resolved_url'):
                print(f"   -> Resolved to: {result['resolved_url']}")
            for reason in result['errors']:
                print(f"   - {reason}")
            print()

    print("=" * 80)

    # Exit with error code if unsafe URLs found
    if all_results['unsafe']:
        print("\n❌ FAILED: Unsafe URLs detected")
        return 1

    print("\n✅ PASSED: No unsafe URLs detected")
    return 0

if __name__ == '__main__':
    exit(main())
