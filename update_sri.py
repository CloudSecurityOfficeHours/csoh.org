#!/usr/bin/env python3
"""Update SRI (Subresource Integrity) hashes in HTML files.

Calculates SHA-384 hashes for main.js and style.css and updates all HTML files
with the new integrity attributes automatically.
"""

import hashlib
import base64
import re
import sys
from pathlib import Path
from typing import Dict, List


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

    # Update style.css: SRI hash, cache-bust param, remove crossorigin
    if 'style.css' in hashes:
        link_pattern = re.compile(
            r'<link\b[^>]*\bhref=(["\'])(?:\.?/)?style\.css(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_style_link(match: re.Match) -> str:
            tag = match.group(0)
            # Update href to include cache-bust query param
            tag = re.sub(
                r'(href=["\'])(?:\.?/)?style\.css(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/style.css?v={cache_busts["style.css"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['style.css'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = link_pattern.sub(replace_style_link, content)

    # Update main.js: SRI hash, cache-bust param, remove crossorigin
    if 'main.js' in hashes:
        script_pattern = re.compile(
            r'<script\b[^>]*\bsrc=(["\'])(?:\.?/)?main\.js(?:\?[^"\']*)?(\1)[^>]*>',
            re.IGNORECASE,
        )

        def replace_main_script(match: re.Match) -> str:
            tag = match.group(0)
            # Update src to include cache-bust query param
            tag = re.sub(
                r'(src=["\'])(?:\.?/)?main\.js(?:\?[^"\']*)?(["\'])',
                rf'\g<1>/main.js?v={cache_busts["main.js"]}\2',
                tag,
            )
            tag = upsert_attr(tag, 'integrity', hashes['main.js'])
            tag = remove_attr(tag, 'crossorigin')
            return tag

        content = script_pattern.sub(replace_main_script, content)

    # Update chat-resources.js: SRI hash, cache-bust param, remove crossorigin
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

    # Write back if changed
    if content != original_content:
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True

    return False


def main():
    """Main function to update SRI hashes in all HTML files."""
    # Get the repository root directory
    repo_root = Path(__file__).parent
    
    # Files to calculate hashes for
    files_to_hash = {
        'style.css': repo_root / 'style.css',
        'main.js': repo_root / 'main.js',
        'chat-resources.js': repo_root / 'chat-resources.js',
    }
    
    # Calculate SRI hashes and cache-bust strings
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

    # If any required files are missing, exit with error
    if missing_files:
        print(f"Error: Required files not found: {', '.join(missing_files)}", file=sys.stderr)
        return 1

    # Find all HTML files recursively in the repository
    html_files = list(repo_root.rglob('*.html'))

    if not html_files:
        print("Warning: No HTML files found", file=sys.stderr)
        return 0

    # Update each HTML file
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
