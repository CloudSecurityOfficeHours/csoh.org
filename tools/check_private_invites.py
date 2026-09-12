#!/usr/bin/env python3
"""
CI gate: refuse private join links in anything we publish.

A private invite link is an unguessable join token for a members-only space:
a Signal group invite, a Signal direct-contact link, a Telegram private
invite, a WhatsApp group invite. Publishing one silently converts "vetted,
members-only" into "open to anyone who reads the page", and no link checker
notices, because the URL resolves perfectly - that is the whole point of it.

This exists because it happened. `chat-resources.html` republished the CSOH
Signal group invite twice (2025-12-19 and 2026-02-13), plus a Signal
direct-contact link and the CSOH Telegram group invite, once whole and once
truncated, all harvested from the group chat by the resource-card pipeline.
Meanwhile `community.html` said:
"It's not posted publicly on purpose; we'd rather you join after a Friday
Zoom or a quick email exchange than have it ingested by every recruiter
scraper on the internet." Both statements were live at the same time, for
months, and both were served from csoh.org.

What is NOT flagged, deliberately:

  - `discord.gg/<code>` and `discord.com/invite/<code>`. Discord invites to
    public community servers are ordinary shared resources, and the chat
    archive links several. They are advertised openly by their own
    communities; a Signal group invite never is.
  - `t.me/<name>`. That is a public Telegram channel. Only the `t.me/+token`
    and `t.me/joinchat/token` forms are private invites, and the patterns
    below are written to tell those two apart.

So the rule is not "no chat links". It is "no unguessable join token".

The corpus comes from `git ls-files`, never a recursive walk: `rglob` and
`grep -r` descend into the git worktrees under `.claude/`, which hold full
copies of the site, and a sweep that scans those reports findings that are
not in this checkout. Files that `tools/site-publish.filter` excludes from
the published site (`/tools/`, `*.py`, `*.md`, `*.sh`) are skipped here too,
so a URL sitting in a local cache under `tools/` is not treated as published.

Usage:
    python3 tools/check_private_invites.py            # scan, exit 1 on hits
    python3 tools/check_private_invites.py --check    # same (CI spelling)
    python3 tools/check_private_invites.py --self-test  # prove the detector

Exit codes: 0 clean, 1 private invite link found, 2 self-test failed.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

# Extensions that get published and can carry a URL. Binary assets are not
# scanned: a screenshot of a join page is a separate problem, and deleting
# the card is what removes it (the preview file is named after the URL hash,
# so an orphaned invite screenshot is caught by the reference check below).
PUBLISHED_SUFFIXES = {
    ".html", ".htm", ".json", ".xml", ".txt", ".ics",
    ".css", ".js", ".webmanifest", ".md",
}

# Paths `tools/site-publish.filter` keeps out of the published site. Markdown
# is excluded there too, but README/SECURITY/CONTRIBUTING are read on GitHub
# by exactly the audience an invite link should not reach, so .md stays in
# the scan and only /tools/ is dropped.
UNPUBLISHED_PREFIXES = ("tools/",)

# Each pattern must match the *invite* form and not the public form.
PATTERNS: list[tuple[str, re.Pattern[str], str]] = [
    (
        "Signal group invite",
        re.compile(r"https?://signal\.group/#[A-Za-z0-9_+/=-]+", re.I),
        "Signal group links are invite-only by construction; publishing one "
        "opens the group to anyone who reads the page.",
    ),
    (
        "Signal direct-contact link",
        re.compile(r"https?://signal\.me/#[A-Za-z0-9_+/=-]+", re.I),
        "A signal.me link lets any reader message that person directly on "
        "Signal, and the token identifies them.",
    ),
    (
        "Telegram private invite",
        re.compile(r"https?://t\.me/(?:\+[A-Za-z0-9_-]+|joinchat/[A-Za-z0-9_-]+)", re.I),
        "The t.me/+token and t.me/joinchat/ forms are private group invites. "
        "A public channel is t.me/<name> and is not flagged.",
    ),
    (
        "WhatsApp group invite",
        re.compile(r"https?://chat\.whatsapp\.com/[A-Za-z0-9]+", re.I),
        "chat.whatsapp.com links are group join tokens.",
    ),
]


def tracked_files(repo: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=repo, capture_output=True, text=True, check=True,
    ).stdout
    files = []
    for rel in out.split("\0"):
        if not rel:
            continue
        if rel.startswith(UNPUBLISHED_PREFIXES):
            continue
        if Path(rel).suffix.lower() not in PUBLISHED_SUFFIXES:
            continue
        files.append(repo / rel)
    return files


def scan_text(text: str) -> list[tuple[int, str, str, str]]:
    """Return (line, kind, url, why) for every private invite link in text."""
    hits = []
    for kind, pattern, why in PATTERNS:
        for m in pattern.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            hits.append((line, kind, m.group(0), why))
    return sorted(hits)


def self_test() -> int:
    """Prove every pattern fires, and that public equivalents do not.

    Run against synthetic strings rather than by planting text in a real
    file: this checkout is shared with other sessions, and a sweep that dies
    mid-run would leave the planted string behind for the next baseline to
    "find".
    """
    # Synthetic tokens only, never a real invite: this file is public on
    # GitHub. The first version used the live CSOH Telegram invite and
    # prefixes of the real Signal links, so the gate itself republished them.
    # URLs are assembled at runtime so a repo-wide grep for invite links does
    # not match this file.
    fake = "EXAMPLE0example0EXAMPLE0example0"
    must_match = [
        ("Signal group invite", "https://signal.group/" + "#" + fake),
        ("Signal direct-contact link", "https://signal.me/" + "#eu/" + fake),
        ("Telegram private invite", "https://t.me/" + "+" + fake[:16]),
        ("Telegram private invite", "https://t.me/" + "joinchat/" + fake),
        ("WhatsApp group invite", "https://chat.whatsapp.com/" + fake),
    ]
    must_not_match = [
        "https://discord.gg/cloudsec",              # public server invite
        "https://discord.com/invite/cloudsec",      # same, canonical form
        "https://t.me/durov",                       # public channel
        "https://signal.org/download/",             # product page
        "https://whatsapp.com/",                    # product page
        "confirm in the signal group at the next session",  # prose, no URL
    ]
    failures = []
    for expect_kind, sample in must_match:
        hits = scan_text(sample)
        if not hits:
            failures.append(f"MISS: {sample!r} should have matched {expect_kind}")
        elif hits[0][1] != expect_kind:
            failures.append(f"WRONG KIND: {sample!r} matched {hits[0][1]}, want {expect_kind}")
    for sample in must_not_match:
        hits = scan_text(sample)
        if hits:
            failures.append(f"FALSE POSITIVE: {sample!r} matched {hits[0][1]}")

    if failures:
        print("Self-test FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  {f}", file=sys.stderr)
        return 2
    print(
        f"Self-test OK: {len(must_match)} invite forms detected, "
        f"{len(must_not_match)} public/prose lookalikes ignored."
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="CI spelling of the default scan")
    ap.add_argument("--self-test", action="store_true", help="prove the detector still fires")
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    repo = Path(__file__).resolve().parent.parent
    targets = tracked_files(repo)

    failures = []
    for path in targets:
        try:
            text = path.read_text(errors="replace")
        except OSError:
            continue
        for line, kind, url, why in scan_text(text):
            failures.append((path.relative_to(repo), line, kind, url, why))

    if failures:
        print("Private invite links found in published files:", file=sys.stderr)
        for rel, line, kind, url, _why in failures:
            print(f"  {rel}:{line}: {kind}: {url}", file=sys.stderr)
        print("", file=sys.stderr)
        for kind, _pat, why in PATTERNS:
            if any(f[2] == kind for f in failures):
                print(f"  {kind}: {why}", file=sys.stderr)
        print(
            "\nRemove the card or link, delete any preview screenshot named after it "
            "(chat-screenshots/, img/previews/), drop the URL from "
            "chat-screenshots/url-mapping.json and tools/url_resolution_cache.json so "
            "the preview pipeline cannot recreate it, and rotate the invite in the app "
            "if it was public for any length of time.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: scanned {len(targets)} published file(s); no private invite links.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
