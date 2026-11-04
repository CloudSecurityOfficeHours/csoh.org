#!/usr/bin/env python3
"""
Point the "Latest recap" sentence on sessions.html at the newest recap.

The sentence's link is the one <a> on sessions.html carrying
`data-latest-recap`. This tool rewrites that link's href and text to name the
newest meetings/YYYY-MM-DD.html on disk. The attribute is the hook, so the
prose around the link can be reworded freely.

add_meeting.py runs this after every recap it writes, which covers the weekly
publish PR and any recap published by hand. The newest date is read from the
meetings/ directory, never from the recap being written: re-running
add_meeting.py for an older date to fix its text must not move the link
backwards.

Usage:
    python3 tools/sync_latest_recap.py              # stamp (default)
    python3 tools/sync_latest_recap.py --check      # report drift, exit 1
    python3 tools/sync_latest_recap.py --self-test  # prove the machinery works

--check runs in validate-html.yml. Unlike the next-session date, this link
goes stale only when a recap is added, so a failure always has a cause in the
diff: a recap page written without add_meeting.py, or the hook removed from
sessions.html.
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSIONS_HTML = REPO_ROOT / "sessions.html"
MEETINGS_DIR = REPO_ROOT / "meetings"

RECAP_GLOB = "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html"
# Attributes in any order: the data attribute is the hook, wherever it sits.
HOOK_RE = re.compile(r"(<a\b[^>]*\sdata-latest-recap\b[^>]*>)(.*?)(</a>)", re.DOTALL)
# The lookbehind keeps a `data-href` attribute from matching.
HREF_RE = re.compile(r'(?<![\w-])href="([^"]*)"')


def newest_recap(meetings_dir: Path) -> str:
    """The newest recap date on disk. A name that fits the glob but is not a
    real date (2026-13-40) raises rather than sorting to the top."""
    dates = sorted(p.stem for p in meetings_dir.glob(RECAP_GLOB))
    if not dates:
        raise ValueError(f"no recap pages in {meetings_dir}")
    dt.date.fromisoformat(dates[-1])
    return dates[-1]


def human_date(iso: str) -> str:
    # Same format as the cards add_meeting.py writes on meetings.html.
    return dt.date.fromisoformat(iso).strftime("%A, %B %-d, %Y")


def stamp(text: str, iso: str) -> str:
    hooks = list(HOOK_RE.finditer(text))
    if len(hooks) != 1:
        raise ValueError(f"expected exactly one data-latest-recap link, found {len(hooks)}")
    m = hooks[0]
    if not HREF_RE.search(m.group(1)):
        raise ValueError("the data-latest-recap link has no href")
    open_tag = HREF_RE.sub(f'href="meetings/{iso}.html"', m.group(1), count=1)
    return text[: m.start()] + open_tag + human_date(iso) + m.group(3) + text[m.end():]


def linked_recap(text: str) -> str:
    """What the hook points at now, for the drift message."""
    m = HOOK_RE.search(text)
    href = HREF_RE.search(m.group(1)) if m else None
    return href.group(1) if href else "(nothing)"


def run(check: bool, sessions: Path = SESSIONS_HTML, meetings: Path = MEETINGS_DIR) -> int:
    name = sessions.name
    try:
        iso = newest_recap(meetings)
        text = sessions.read_text(encoding="utf-8")
        new = stamp(text, iso)
    except (OSError, ValueError) as exc:
        print(f"✗ {name}: {exc}", file=sys.stderr)
        return 1
    if new == text:
        print(f"✓ {name} links the newest recap ({iso})")
        return 0
    if check:
        print(
            f"✗ {name} links {linked_recap(text)} as the latest recap, but the newest is "
            f"meetings/{iso}.html. Run: python3 tools/sync_latest_recap.py",
            file=sys.stderr,
        )
        return 1
    sessions.write_text(new, encoding="utf-8")
    print(f"  pointed {name}'s latest-recap link at meetings/{iso}.html")
    return 0


# A sessions.html stand-in for the self-test. The second link names the same
# page without the hook and must never be touched.
_PLANT = (
    '<p>The most recent written recap is <a class="x" data-latest-recap '
    'href="meetings/2026-10-16.html">Friday, October 16, 2026</a>. See also '
    '<a href="meetings/2026-10-16.html">that week</a>.</p>\n'
)


def self_test() -> int:
    failures: list[str] = []

    def expect(label: str, ok: bool) -> None:
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
        if not ok:
            failures.append(label)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        meetings = root / "meetings"
        meetings.mkdir()
        # Written out of order, with names the glob must ignore.
        for n in ("2026-10-23", "2026-10-30", "2026-10-16", "index", "2026-11-06-draft"):
            (meetings / f"{n}.html").write_text("", encoding="utf-8")
        sessions = root / "sessions.html"
        sessions.write_text(_PLANT, encoding="utf-8")

        expect("--check fails on a stale link", run(True, sessions, meetings) == 1)
        expect("--check writes nothing", sessions.read_text(encoding="utf-8") == _PLANT)
        expect("stamp exits 0", run(False, sessions, meetings) == 0)
        once = sessions.read_text(encoding="utf-8")
        expect("href moves to the newest recap on disk",
               'data-latest-recap href="meetings/2026-10-30.html">' in once)
        expect("link text names that date", ">Friday, October 30, 2026</a>" in once)
        expect("other attributes on the hook survive", '<a class="x" data-latest-recap ' in once)
        expect("a link without the hook is untouched",
               '<a href="meetings/2026-10-16.html">that week</a>' in once)
        expect("decoy filenames are ignored", "2026-11-06" not in once and "index" not in once)
        expect("--check passes after stamping", run(True, sessions, meetings) == 0)
        run(False, sessions, meetings)
        expect("a second run changes nothing", sessions.read_text(encoding="utf-8") == once)

        # An older recap re-published later (newer mtime) must not win.
        (meetings / "2026-10-16.html").write_text("rewritten", encoding="utf-8")
        run(False, sessions, meetings)
        expect("re-writing an older recap does not move the link back",
               sessions.read_text(encoding="utf-8") == once)

        # A recap newer than the link appears: the link follows it.
        (meetings / "2026-11-13.html").write_text("", encoding="utf-8")
        expect("--check fails once a newer recap exists", run(True, sessions, meetings) == 1)
        run(False, sessions, meetings)
        expect("stamp follows the newer recap",
               'href="meetings/2026-11-13.html">Friday, November 13, 2026</a>'
               in sessions.read_text(encoding="utf-8"))

        bad = meetings / "2026-13-40.html"
        bad.write_text("", encoding="utf-8")
        expect("an impossible date fails rather than sorting first",
               run(True, sessions, meetings) == 1)
        bad.unlink()

        for label, text in (
            ("no hook fails", _PLANT.replace(" data-latest-recap", "")),
            ("two hooks fail", _PLANT.replace('<a href=', '<a data-latest-recap href=')),
            ("a hook with no href fails",
             _PLANT.replace(' href="meetings/2026-10-16.html">Friday', '>Friday')),
            ("data-latest-recapped is not the hook",
             _PLANT.replace("data-latest-recap", "data-latest-recapped")),
        ):
            sessions.write_text(text, encoding="utf-8")
            expect(label, run(True, sessions, meetings) == 1)

    print()
    if failures:
        print(f"✗ self-test: {len(failures)} check(s) failed", file=sys.stderr)
        return 1
    print("✓ self-test: every planted case behaved")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--check", action="store_true", help="report drift without writing; exit 1 if stale")
    ap.add_argument("--self-test", action="store_true", help="plant known defects and confirm each is caught")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return run(args.check)


if __name__ == "__main__":
    sys.exit(main())
