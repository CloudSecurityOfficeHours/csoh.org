#!/usr/bin/env python3
"""Insert the render-blocking <script src="/theme.js"> into every page's <head>.

theme.js has to run before the first paint, so the tag goes immediately above
the first /style.css link on the page - the preload where there is one, the
stylesheet link otherwise. update_sri.py stamps the ?v= and integrity onto it
afterwards, exactly as it does for every other shared asset.

Idempotent: a page that already carries the tag is left alone. Run it again
after adding a page; a page that links style.css and has no theme.js tag is a
page that will flash.

Usage:  python3 tools/add_theme_script.py [--check]
"""
import pathlib
import re
import sys

TAG = '    <script src="/theme.js"></script>\n'
SKIP_DIRS = {'.claude', '.venv', 'node_modules', '.git', 'dist'}
# Verification stub Google serves as-is; it has no <head> of ours to edit.
SKIP_FILES = {'google66d489593949bd4c.html'}

PRELOAD = re.compile(r'^[ \t]*<link rel="preload" href="/style\.css', re.M)
SHEET = re.compile(r'^[ \t]*<link rel="stylesheet" href="/style\.css', re.M)


def main() -> int:
    check = '--check' in sys.argv
    root = pathlib.Path(__file__).resolve().parent.parent
    changed, already, skipped = [], 0, []

    for f in sorted(root.rglob('*.html')):
        rel = f.relative_to(root)
        if SKIP_DIRS.intersection(rel.parts[:-1]) or f.name in SKIP_FILES:
            continue
        text = f.read_text(encoding='utf-8')
        if '/theme.js' not in text and 'style.css' not in text:
            continue  # not one of ours
        if '/theme.js' in text:
            already += 1
            continue
        m = PRELOAD.search(text) or SHEET.search(text)
        if not m:
            skipped.append(str(rel))
            continue
        if not check:
            f.write_text(text[:m.start()] + TAG + text[m.start():], encoding='utf-8')
        changed.append(str(rel))

    if skipped:
        print('No style.css link found in: ' + ', '.join(skipped), file=sys.stderr)
    if check:
        if changed:
            print(f'{len(changed)} page(s) missing the theme.js tag: '
                  + ', '.join(changed[:5]) + ('...' if len(changed) > 5 else ''),
                  file=sys.stderr)
            return 1
        print(f'✓ theme.js tag present on all {already} pages')
        return 0

    print(f'inserted={len(changed)} already-present={already} skipped={len(skipped)}')
    if changed:
        print('Now run: python3 update_sri.py')
    return 1 if skipped else 0


if __name__ == '__main__':
    sys.exit(main())
