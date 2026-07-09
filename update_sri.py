#!/usr/bin/env python3
"""Update SRI (Subresource Integrity) hashes in HTML files.

Calculates SHA-384 SRI hashes for the site's shared JS/CSS assets - style.css,
main.js, chat-resources.js, breach-timeline.css, breach-timeline.js, meetings.js,
glossary.js, 404.js, and the vendored vendor/goatcounter-count.js - and stamps the
integrity attribute on every HTML file (rglob, all subdirectories). It also
appends a ?v=<hash> cache-busting query to each asset URL and strips any stale
crossorigin attribute.
"""

import hashlib
import base64
import re
import sys
from pathlib import Path
from typing import Dict


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

    if 'style.css' in hashes:
        link_pattern = re.compile(
            r'<link\b[^>]*\bhref=(["\'])(?:\.?/)?style\.css(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_style_link(match: re.Match) -> str:
            tag = match.group(0)
            tag = re.sub(
                r'(href=["\'])(?:\.?/)?style\.css(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/style.css?v={cache_busts["style.css"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['style.css'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = link_pattern.sub(replace_style_link, content)

    if 'main.js' in hashes:
        script_pattern = re.compile(
            r'<script\b[^>]*\bsrc=(["\'])(?:\.?/)?main\.js(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_main_script(match: re.Match) -> str:
            tag = match.group(0)
            tag = re.sub(
                r'(src=["\'])(?:\.?/)?main\.js(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/main.js?v={cache_busts["main.js"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['main.js'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = script_pattern.sub(replace_main_script, content)

    if 'chat-resources.js' in hashes:
        chat_script_pattern = re.compile(
            r'<script\b[^>]*\bsrc=(["\'])(?:\.?/)?chat-resources\.js(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_chat_script(match: re.Match) -> str:
            tag = match.group(0)
            tag = re.sub(
                r'(src=["\'])(?:\.?/)?chat-resources\.js(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/chat-resources.js?v={cache_busts["chat-resources.js"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['chat-resources.js'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = chat_script_pattern.sub(replace_chat_script, content)

    if 'breach-timeline.css' in hashes:
        bt_link_pattern = re.compile(
            r'<link\b[^>]*\bhref=(["\'])(?:\.?/)?breach-timeline\.css(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_bt_style_link(match: re.Match) -> str:
            tag = match.group(0)
            tag = re.sub(
                r'(href=["\'])(?:\.?/)?breach-timeline\.css(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/breach-timeline.css?v={cache_busts["breach-timeline.css"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['breach-timeline.css'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = bt_link_pattern.sub(replace_bt_style_link, content)

    if 'breach-timeline.js' in hashes:
        bt_script_pattern = re.compile(
            r'<script\b[^>]*\bsrc=(["\'])(?:\.?/)?breach-timeline\.js(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_bt_script(match: re.Match) -> str:
            tag = match.group(0)
            tag = re.sub(
                r'(src=["\'])(?:\.?/)?breach-timeline\.js(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/breach-timeline.js?v={cache_busts["breach-timeline.js"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['breach-timeline.js'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = bt_script_pattern.sub(replace_bt_script, content)

    if 'meetings.js' in hashes:
        mtg_script_pattern = re.compile(
            r'<script\b[^>]*\bsrc=(["\'])(?:\.?/)?meetings\.js(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_mtg_script(match: re.Match) -> str:
            tag = match.group(0)
            tag = re.sub(
                r'(src=["\'])(?:\.?/)?meetings\.js(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/meetings.js?v={cache_busts["meetings.js"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['meetings.js'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = mtg_script_pattern.sub(replace_mtg_script, content)

    if 'glossary.js' in hashes:
        glossary_script_pattern = re.compile(
            r'<script\b[^>]*\bsrc=(["\'])(?:\.?/)?glossary\.js(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_glossary_script(match: re.Match) -> str:
            tag = match.group(0)
            tag = re.sub(
                r'(src=["\'])(?:\.?/)?glossary\.js(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/glossary.js?v={cache_busts["glossary.js"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['glossary.js'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = glossary_script_pattern.sub(replace_glossary_script, content)

    if '404.js' in hashes:
        notfound_script_pattern = re.compile(
            r'<script\b[^>]*\bsrc=(["\'])(?:\.?/)?404\.js(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_notfound_script(match: re.Match) -> str:
            tag = match.group(0)
            tag = re.sub(
                r'(src=["\'])(?:\.?/)?404\.js(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/404.js?v={cache_busts["404.js"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['404.js'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = notfound_script_pattern.sub(replace_notfound_script, content)

    if 'goatcounter-count.js' in hashes:
        gc_script_pattern = re.compile(
            r'<script\b[^>]*\bsrc=(["\'])/vendor/goatcounter-count\.js(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_gc_script(match: re.Match) -> str:
            tag = match.group(0)
            tag = re.sub(
                r'(src=["\'])/vendor/goatcounter-count\.js(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/vendor/goatcounter-count.js?v={cache_busts["goatcounter-count.js"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['goatcounter-count.js'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = gc_script_pattern.sub(replace_gc_script, content)

    if content != original_content:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    return False


def main():
    repo_root = Path(__file__).parent

    files_to_hash = {
        'style.css': repo_root / 'style.css',
        'main.js': repo_root / 'main.js',
        'chat-resources.js': repo_root / 'chat-resources.js',
        'breach-timeline.css': repo_root / 'breach-timeline.css',
        'breach-timeline.js': repo_root / 'breach-timeline.js',
        'meetings.js': repo_root / 'meetings.js',
        'glossary.js': repo_root / 'glossary.js',
        '404.js': repo_root / '404.js',
        # GoatCounter's analytics loader, vendored from https://gc.zgo.at/count.js
        # and served first-party (/vendor/) so the strict CSP (script-src 'self')
        # needs no remote script origin. Re-vendor that file and rerun this
        # script to pick up upstream updates.
        'goatcounter-count.js': repo_root / 'vendor' / 'goatcounter-count.js',
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
