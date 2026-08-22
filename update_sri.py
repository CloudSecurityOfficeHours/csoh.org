#!/usr/bin/env python3
"""Update SRI (Subresource Integrity) hashes in HTML files.

Calculates SHA-384 SRI hashes for the shared JS/CSS assets listed in ASSETS
below and stamps the integrity attribute on every HTML file (rglob, all
subdirectories). It also appends a ?v=<hash> cache-busting query to each asset
URL and strips any stale crossorigin attribute.

The ?v= key is not cosmetic: nginx.conf serves every *.css / *.js with
`expires 1y; Cache-Control: public, immutable`, so an asset referenced without
one is pinned in browser caches for a year and edits to it never reach
returning visitors. Any shared asset a page links to belongs in ASSETS.
"""

import hashlib
import base64
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple


# Shared assets to stamp, as (repo-relative path, tag name, URL attribute).
# The served URL is the path with a leading slash; the SRI/cache-bust keys
# are the bare filename.
ASSETS: List[Tuple[str, str, str]] = [
    ('style.css', 'link', 'href'),
    ('main.js', 'script', 'src'),
    ('chat-resources.js', 'script', 'src'),
    ('breach-timeline.css', 'link', 'href'),
    ('breach-timeline.js', 'script', 'src'),
    ('meetings.js', 'script', 'src'),
    ('glossary.js', 'script', 'src'),
    ('404.js', 'script', 'src'),
    # Rules that apply only when JavaScript is off. Referenced from a
    # <noscript> link rather than an inline block, because CSP drops
    # inline <style>. See the file's own header.
    ('noscript.css', 'link', 'href'),
    # /search.html's UI + lazy-loaded MiniSearch initializer.
    ('search.css', 'link', 'href'),
    ('search-init.js', 'script', 'src'),
    # GoatCounter's analytics loader, vendored from https://gc.zgo.at/count.js
    # and served first-party (/vendor/) so the strict CSP (script-src 'self')
    # needs no remote script origin. Re-vendor that file and rerun this
    # script to pick up upstream updates.
    ('vendor/goatcounter-count.js', 'script', 'src'),
]


def upsert_attr(tag: str, attr: str, value: str) -> str:
    """Set or replace an HTML attribute on a single tag string."""
    attr_pattern = re.compile(rf'(\s{re.escape(attr)}\s*=\s*)(["\']).*?\2', re.IGNORECASE)
    if attr_pattern.search(tag):
        return attr_pattern.sub(rf'\1"{value}"', tag, count=1)

    closing = re.search(r'\s*/?>\s*$', tag)
    if not closing:
        return tag

    insert_at = closing.start()
    return f'{tag[:insert_at]} {attr}="{value}"{tag[insert_at:]}'


def remove_attr(tag: str, attr: str) -> str:
    """Remove an HTML attribute from a single tag string."""
    attr_pattern = re.compile(rf'\s{re.escape(attr)}\s*=\s*(["\']).*?\1', re.IGNORECASE)
    return attr_pattern.sub('', tag)


def calculate_sri_hash(file_path: Path) -> str:
    """Calculate SHA-384 SRI hash for a file.

    Args:
        file_path: Path to the file to hash

    Returns:
        SRI hash in the format: sha384-{base64_hash}
    """
    sha384 = hashlib.sha384()
    with open(file_path, 'rb') as f:
        sha384.update(f.read())

    hash_bytes = sha384.digest()
    hash_b64 = base64.b64encode(hash_bytes).decode('ascii')
    return f"sha384-{hash_b64}"


def calculate_cache_bust(file_path: Path) -> str:
    """Calculate a short hash for cache-busting query param.

    Returns:
        First 8 hex characters of the file's SHA-256 hash.
    """
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        sha256.update(f.read())
    return sha256.hexdigest()[:8]


def update_html_file(html_path: Path, hashes: Dict[str, str],
                     cache_busts: Dict[str, str]) -> bool:
    """Update SRI hashes and cache-bust params in an HTML file.

    Args:
        html_path: Path to the HTML file
        hashes: Dictionary mapping file names to their SRI hashes
        cache_busts: Dictionary mapping file names to cache-bust strings

    Returns:
        True if file was modified, False otherwise
    """
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    for rel_path, tag, attr in ASSETS:
        name = rel_path.rsplit('/', 1)[-1]
        if name not in hashes:
            continue

        # Match the asset however it is referenced today: bare, ./-relative,
        # or absolute, with or without an existing ?v= key.
        ref = r'(?:\.?/)?' + re.escape(rel_path)
        tag_pattern = re.compile(
            rf'<{tag}\b[^>]*\b{attr}=(["\']){ref}(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )
        url = '/' + rel_path

        def replace(match: re.Match, name=name, attr=attr, ref=ref, url=url) -> str:
            tag_str = match.group(0)
            tag_str = re.sub(
                rf'({attr}=["\']){ref}(?:\?[^"\']*)?(["\'])',
                rf'\g<1>{url}?v={cache_busts[name]}\2',
                tag_str,
                flags=re.IGNORECASE,
            )
            tag_str = upsert_attr(tag_str, 'integrity', hashes[name])
            tag_str = remove_attr(tag_str, 'crossorigin')
            return tag_str

        content = tag_pattern.sub(replace, content)

    if content != original_content:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    return False


def main():
    repo_root = Path(__file__).parent

    files_to_hash = {
        rel_path.rsplit('/', 1)[-1]: repo_root / rel_path
        for rel_path, _tag, _attr in ASSETS
    }

    print("Calculating SRI hashes...")
    hashes = {}
    cache_busts = {}
    missing_files = []

    for name, path in files_to_hash.items():
        if not path.exists():
            missing_files.append(str(path))
            continue

        sri_hash = calculate_sri_hash(path)
        hashes[name] = sri_hash
        cache_busts[name] = calculate_cache_bust(path)
        print(f"  {name}: {sri_hash} (v={cache_busts[name]})")

    if missing_files:
        print(f"Error: Required files not found: {', '.join(missing_files)}", file=sys.stderr)
        return 1

    html_files = list(repo_root.rglob('*.html'))

    if not html_files:
        print("Warning: No HTML files found", file=sys.stderr)
        return 0

    print(f"\nUpdating {len(html_files)} HTML files...")
    modified_count = 0
    for html_path in sorted(html_files):
        if update_html_file(html_path, hashes, cache_busts):
            print(f"  ✓ Updated: {html_path.name}")
            modified_count += 1
        else:
            print(f"  - Unchanged: {html_path.name}")

    print(f"\n✓ Done! Modified {modified_count} of {len(html_files)} files.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
