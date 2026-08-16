#!/usr/bin/env python3
"""Refresh <lastmod> values in sitemap.xml from real file dates.

For each <url> entry, the <loc> is mapped to a local file (the path after
https://csoh.org/, defaulting to index.html for the bare origin). The lastmod
is set to:

  1. today's date, if the file has uncommitted changes (working tree or index),
  2. the last commit date (%cs) from `git log`, otherwise,
  3. the file mtime as a final fallback.

Exit code is 0 whether or not the sitemap changed. Prints a one-line summary.

Usage:
    python3 tools/update_sitemap.py
"""

from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo


ORIGIN = "https://csoh.org/"
SITEMAP = "sitemap.xml"


def url_to_path(loc: str, repo_root: Path) -> Path | None:
    parsed = urlparse(loc)
    path = parsed.path.lstrip("/")
    if not path:
        path = "index.html"
    candidate = repo_root / path
    if candidate.exists():
        return candidate
    return None


def has_uncommitted_changes(path: Path, repo_root: Path) -> bool:
    rel = str(path.relative_to(repo_root))
    # Working tree vs index
    r1 = subprocess.run(
        ["git", "diff", "--quiet", "--", rel],
        cwd=repo_root,
    )
    if r1.returncode != 0:
        return True
    # Index vs HEAD
    r2 = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", rel],
        cwd=repo_root,
    )
    return r2.returncode != 0


# Every date in the sitemap is rendered in this one timezone.
#
# `%cs` renders a committer date in the *commit's own* timezone, so the value
# depended on where the commit was made. Laptop commits landed in Pacific and
# CI commits in UTC, and a news-bot commit at 2026-08-16T01:13Z was therefore
# stamped 2026-08-16 while every neighbouring entry - same evening, same
# work - said 2026-08-15. That is a lastmod dated in the future for anyone
# west of Greenwich, and Google stops trusting lastmod on a site that reports
# values it can tell are unreliable.
#
# Pacific rather than UTC because it is the timeline the site already runs on
# ("Friday at 7am PT") and because it is behind UTC: a date correct in Pacific
# is never in the future in UTC, so the values stay conservative in the
# direction that matters. It also leaves the existing, already-correct laptop
# dates untouched.
SITEMAP_TZ = "America/Los_Angeles"


def _today() -> dt.date:
    return dt.datetime.now(ZoneInfo(SITEMAP_TZ)).date()


def git_last_commit_date(path: Path, repo_root: Path) -> str | None:
    """Committer date as YYYY-MM-DD, rendered in SITEMAP_TZ."""
    rel = str(path.relative_to(repo_root))
    r = subprocess.run(
        ["git", "log", "-1", "--format=%cd", "--date=format-local:%Y-%m-%d", "--", rel],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env={**os.environ, "TZ": SITEMAP_TZ},
    )
    if r.returncode != 0:
        return None
    date = r.stdout.strip()
    return date or None


def last_modified(path: Path, repo_root: Path) -> str:
    """Best-known modification date, never later than today in SITEMAP_TZ."""
    today = _today()

    if has_uncommitted_changes(path, repo_root):
        return today.isoformat()

    commit_date = git_last_commit_date(path, repo_root)
    if commit_date is None:
        commit_date = dt.date.fromtimestamp(os.path.getmtime(path)).isoformat()

    try:
        parsed = dt.date.fromisoformat(commit_date)
    except ValueError:
        return today.isoformat()
    return min(parsed, today).isoformat()


def update_sitemap(repo_root: Path) -> int:
    sitemap_path = repo_root / SITEMAP
    text = sitemap_path.read_text(encoding="utf-8")

    url_block = re.compile(
        r"<url>(?P<body>.*?)</url>", re.DOTALL
    )
    loc_re = re.compile(r"<loc>([^<]+)</loc>")
    lastmod_re = re.compile(r"<lastmod>[^<]*</lastmod>")

    changed_urls: list[tuple[str, str]] = []

    def replace_url(match: re.Match[str]) -> str:
        body = match.group("body")
        loc_match = loc_re.search(body)
        if not loc_match:
            return match.group(0)
        loc = loc_match.group(1).strip()
        path = url_to_path(loc, repo_root)
        if path is None:
            return match.group(0)
        new_date = last_modified(path, repo_root)
        new_body, n = lastmod_re.subn(
            f"<lastmod>{new_date}</lastmod>", body, count=1
        )
        if n == 0:
            # Insert after <loc>
            insert_at = loc_match.end()
            indent = "\n    "
            new_body = (
                body[:insert_at]
                + f"{indent}<lastmod>{new_date}</lastmod>"
                + body[insert_at:]
            )
        if new_body != body:
            changed_urls.append((loc, new_date))
        return f"<url>{new_body}</url>"

    new_text = url_block.sub(replace_url, text)

    if new_text != text:
        sitemap_path.write_text(new_text, encoding="utf-8")
        print(f"Updated {len(changed_urls)} lastmod entries in {SITEMAP}:")
        for loc, date in changed_urls:
            print(f"  {date}  {loc}")
    else:
        print(f"{SITEMAP} already up to date")

    return 0


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    return update_sitemap(repo_root)


if __name__ == "__main__":
    sys.exit(main())
