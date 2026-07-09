#!/usr/bin/env python3
"""Stamp the GoatCounter analytics tag onto every HTML page.

Why this exists
---------------
The site has no templating - the footer scripts are hand-copied into each of
~220 static pages (root + meetings/ + breaches/ + portfolio/ + homelab/). This script inserts ONE
canonical GoatCounter `<script>` tag, byte-identical, right before the closing
`</body>` on every page, the same way tools/sync_chrome.py keeps the nav and
footer uniform.

How GoatCounter fits the site's strict CSP
------------------------------------------
The loader is vendored at /vendor/goatcounter-count.js and served first-party,
so `script-src 'self'` needs no remote script origin and the tag carries no
inline JavaScript (so tools/check_no_inline_scripts.py stays green). The hit is
sent to https://csoh.goatcounter.com/count (allow-listed in img-src + connect-src
in the CSP). The `integrity=` and `?v=` attributes are added afterwards by
update_sri.py - do NOT hand-add them here.

Run from the repo root:

    python3 tools/inject_goatcounter.py
    python3 update_sri.py        # then stamp SRI + cache-bust

It is idempotent: a page that already carries the tag is left untouched.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# The canonical tag. Root-relative src + absolute data-goatcounter URL, so it is
# identical on every page regardless of directory depth. update_sri.py rewrites
# the src to add `?v=<hash>` and appends the matching `integrity=`.
TAG = (
    '  <script data-goatcounter="https://csoh.goatcounter.com/count" '
    'src="/vendor/goatcounter-count.js" defer></script>'
)

# Presence of this attribute means the page is already instrumented.
MARKER = "data-goatcounter"

CLOSING_BODY = re.compile(r"</body\s*>", re.IGNORECASE)


def inject(path: Path) -> str:
    """Insert TAG before the final </body>.

    Returns "added", "present" (already instrumented), or "nobody" (no </body>,
    e.g. a Search Console verification token - left untouched).
    """
    html = path.read_text(encoding="utf-8")
    if MARKER in html:
        return "present"

    # Use the LAST </body> in case a page shows a literal </body> inside a code
    # sample - the real document close is always last.
    last = None
    for last in CLOSING_BODY.finditer(html):
        pass
    if last is None:
        return "nobody"

    # Insert on its own line, preserving the indentation of the </body> line.
    line_start = html.rfind("\n", 0, last.start()) + 1
    new = html[:line_start] + TAG + "\n" + html[line_start:]
    path.write_text(new, encoding="utf-8")
    return "added"


def main() -> int:
    targets = sorted(
        list(REPO.glob("*.html"))
        + list(REPO.glob("meetings/*.html"))
        + list(REPO.glob("breaches/*.html"))
        + list(REPO.glob("portfolio/*.html"))
        + list(REPO.glob("homelab/*.html"))
    )

    added = present = skipped = 0
    for path in targets:
        result = inject(path)
        added += result == "added"
        present += result == "present"
        if result == "nobody":
            skipped += 1
            print(f"  - skipped (no <body>): {path.relative_to(REPO)}")

    print(f"GoatCounter tag: {added} added, {present} already present, "
          f"{skipped} skipped ({len(targets)} scanned).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
