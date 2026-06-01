#!/usr/bin/env python3
"""
Build a static search index over the full text of every per-meeting page.

Output: /meetings-search-index.json - a JSON array, one entry per meeting:
  {"id": "meeting-2026-04-17", "text": "lowercased plain-text body…"}

The meetings.html search reads this file lazily (on first keystroke) and
intersects matches against the card list. Without this, search only
matches against card summaries - which miss most speaker mentions and
topical detail buried in the full recap.

Idempotent: re-running with no meeting changes leaves the file untouched.
Safe to wire into the deploy workflow.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Pull <main>...</main> body if present; else fall back to <body>...</body>.
MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.DOTALL | re.IGNORECASE)
BODY_RE = re.compile(r"<body\b[^>]*>(.*?)</body>", re.DOTALL | re.IGNORECASE)

# Strip these blocks entirely before extracting text. They contain noise
# (script bodies, JSON-LD, navigation, footer) that would pollute the index.
DROP_BLOCKS = [
    re.compile(r"<script\b[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<style\b[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<nav\b[^>]*>.*?</nav>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<header\b[^>]*>.*?</header>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<footer\b[^>]*>.*?</footer>", re.DOTALL | re.IGNORECASE),
]
TAG_RE = re.compile(r"<[^>]+>")
WS_RE = re.compile(r"\s+")
ENTITY_RE = re.compile(r"&([a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);")

ENTITIES = {
    "amp": "&", "lt": "<", "gt": ">", "quot": '"', "apos": "'",
    "nbsp": " ", "mdash": "-", "ndash": "-", "hellip": "…",
    "ldquo": "“", "rdquo": "”", "lsquo": "‘", "rsquo": "’",
}


def decode_entities(s: str) -> str:
    def repl(m: re.Match) -> str:
        e = m.group(1)
        if e.startswith("#x") or e.startswith("#X"):
            try:
                return chr(int(e[2:], 16))
            except ValueError:
                return m.group(0)
        if e.startswith("#"):
            try:
                return chr(int(e[1:]))
            except ValueError:
                return m.group(0)
        return ENTITIES.get(e, m.group(0))
    return ENTITY_RE.sub(repl, s)


def extract_text(html: str) -> str:
    m = MAIN_RE.search(html) or BODY_RE.search(html)
    body = m.group(1) if m else html
    for pat in DROP_BLOCKS:
        body = pat.sub(" ", body)
    body = TAG_RE.sub(" ", body)
    body = decode_entities(body)
    body = WS_RE.sub(" ", body).strip().lower()
    return body


def main() -> int:
    repo = Path(__file__).resolve().parent.parent
    meetings_dir = repo / "meetings"
    out_path = repo / "meetings-search-index.json"

    entries = []
    for path in sorted(meetings_dir.glob("*.html")):
        # Filename is YYYY-MM-DD.html → id "meeting-YYYY-MM-DD" (matches the
        # corresponding article id on meetings.html).
        date = path.stem
        text = extract_text(path.read_text(errors="replace"))
        entries.append({"id": f"meeting-{date}", "text": text})

    # Pretty-print with sorted keys for stable diffs, but keep on one line
    # per entry to avoid bloating with whitespace.
    payload = "[\n" + ",\n".join(
        json.dumps(e, ensure_ascii=False) for e in entries
    ) + "\n]\n"

    if out_path.exists() and out_path.read_text() == payload:
        print(f"unchanged: {out_path.relative_to(repo)} ({len(entries)} entries)")
        return 0

    out_path.write_text(payload)
    size_kb = len(payload.encode("utf-8")) / 1024
    print(f"wrote: {out_path.relative_to(repo)} - {len(entries)} entries, {size_kb:.1f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
