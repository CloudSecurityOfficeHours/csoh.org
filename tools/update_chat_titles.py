#!/usr/bin/env python3
import re
from urllib.parse import urlparse, unquote

INPUT = 'chat-resources.html'
BACKUP = INPUT + '.bak'

def humanize_path(path):
    if not path or path == '/':
        return ''
    parts = [p for p in path.split('/') if p]
    # drop common file-like endings
    if parts and re.search(r'\.(html|htm|php|aspx|jsp)$', parts[-1]):
        parts[-1] = re.sub(r'\.(html|htm|php|aspx|jsp)$', '', parts[-1])
    # replace dashes/underscores and numbers
    parts = [re.sub(r'[-_]+', ' ', p) for p in parts]
    return ' – '.join([p.replace('%20',' ') for p in parts])

def title_from_url(url):
    try:
        parsed = urlparse(url)
    except Exception:
        return url
    host = parsed.netloc.replace('www.', '')
    host = host.split(':')[0]
    path_h = humanize_path(unquote(parsed.path))
    if parsed.query:
        q = parsed.query
    else:
        q = ''
    # Special cases for known domains
    special = {
        'youtube.com': 'YouTube',
        'youtu.be': 'YouTube',
        'github.com': 'GitHub',
        'en.wikipedia.org': 'Wikipedia',
        'gemini.google.com': 'Gemini Share',
        'a.co': 'Amazon',
    }
    if host in special and path_h:
        return f"{special[host]}: {path_h}"
    if host in special:
        return special[host]
    if path_h:
        # Title-case the path pieces
        return f"{host} — {path_h.title()}"
    return host

# Read file
with open(INPUT, 'r', encoding='utf-8') as f:
    html = f.read()

# Backup
with open(BACKUP, 'w', encoding='utf-8') as f:
    f.write(html)

# Find all <a ...> ... <h3>URL</h3>
pattern = re.compile(r'(<a[^>]+>\s*<div class="resource-card"[\s\S]*?<h3>)(.*?)(</h3>)', re.IGNORECASE)

changes = 0

def repl(m):
    global changes
    prefix = m.group(1)
    url_text = m.group(2).strip()
    suffix = m.group(3)
    # Sometimes the h3 already contains ellipsis; better to extract href from the enclosing <a>
    # Extract href from the matched prefix (the opening <a ...> is inside group 1)
    a_tag = re.search(r'href=\"([^\"]+)\"', prefix)
    if a_tag:
        href = a_tag.group(1)
    else:
        href = url_text
    title = title_from_url(href)
    changes += 1
    return prefix + title + suffix

new_html = pattern.sub(repl, html)

with open(INPUT, 'w', encoding='utf-8') as f:
    f.write(new_html)

print(f"Updated {changes} titles in {INPUT}, backup saved to {BACKUP}")
