#!/usr/bin/env python3
"""Carry each session's recording onto its meeting recap page.

A talk lives on `presentations.html` as a card: date, title, blurb, YouTube
link. This carries it back to `meetings/YYYY-MM-DD.html`, so a reader who
lands on the recap of a recorded session has a route to the recording. It
writes both, from the one source:

- a visible `<p class="meeting-recording">` link under the quick-recap callout;
- a `VideoObject` JSON-LD block in `<head>`, same shape and same serializer as
  the one `update_presentations_schema.py` emits on the presentations page.

Both come from the same parsed card, in the same pass. Neither is hand-edited.
That pairing is the point rather than a convenience: Google's structured-data
policy asks that markup describe content the page actually shows, so a
`VideoObject` on a page with no visible video reference is not merely
redundant, it is the kind of mismatch that earns a manual action. The link and
the schema are written together so the page can never carry one without the
other.

Source of truth
---------------
`presentations.html`'s **cards**, parsed by importing
`update_presentations_schema`. Not its generated schema block - the two tools
are siblings reading the same markup, not a chain, so neither has to run before
the other and a stale schema block on that page cannot propagate here.

Matching is by date: a card titled "September 18, 2026: ..." belongs to
`meetings/2026-09-18.html`. A card whose date has no recap page (not a
Friday session) is reported, not an error.

The owned region
----------------
On the recap side this tool owns two spans and nothing else:

1. Everything between the quick-recap `</p>` and the
   `<div class="resource-tags meeting-tags">` that follows it. That region is
   whitespace on every recap that has no recording, which is what makes "own
   it outright" safe - re-running cannot accumulate duplicates, and a session
   whose card is removed from the presentations page loses its link again.
   Content there that this tool did not generate is replaced, with a warning
   naming the page, rather than silently discarded.
2. The marker-delimited JSON-LD block in `<head>`.

A recap missing either anchor raises rather than being skipped. A skipped page
and a page with nothing to do would otherwise look identical in the output.

Why `@graph` even for a single video
------------------------------------
Two dates could share a card one day, and a branch that has never executed is
a branch that does not work. `@graph` handles one video and N through the same
code, and `--check`'s self-test exercises the N case in memory so the path is
covered rather than merely present.

Usage
-----
    python3 tools/sync_recap_videos.py            # write
    python3 tools/sync_recap_videos.py --check    # CI gate; also self-tests
"""

from __future__ import annotations

import argparse
import html as html_mod
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from update_presentations_schema import (  # noqa: E402
    ExtractionError,
    build_items,
    extract_videos,
    inject,
    render_block,
)

ROOT = Path(__file__).resolve().parent.parent
PRESENTATIONS = ROOT / "presentations.html"
MEETINGS_DIR = ROOT / "meetings"

MARKER = "<!-- Structured Data - Session Recording (VideoObject) -->"

# The quick-recap callout is `.meeting-page > h2 + p`; the tags div always
# follows it. Both ends are captured in one match so the span between them is
# never assembled from two independent searches.
#
# The owned group absorbs *all* whitespace up to the div, and the div's own
# indentation is read back off the end of it and re-emitted. Letting the
# closing group take a leading `\s*` instead looks equivalent and is not: on
# the first pass that group matches only the indent, on the second it also
# takes the newline the inserted paragraph ended with, so the region would grow
# a blank line per run. The self-test's second pass guards this.
REGION_RE = re.compile(
    r'(<h2><time datetime="(\d{4}-\d{2}-\d{2})">.*?</h2>\s*<p>.*?</p>\n)'
    r"(.*?)"
    r'(<div class="resource-tags meeting-tags">)',
    re.DOTALL,
)
OWNED_P_RE = re.compile(r'<p class="meeting-recording">.*?</p>\s*', re.DOTALL)
INDENT = " " * 12


def recording_paragraph(video: dict) -> str:
    """The visible link for one recording.

    `quote=False`: the name is element text, where a literal `"` is legal and
    is what the source card carries (`Andreae "Dr Dre" Pohlman`). Escaping it
    would render `&quot;` as visible punctuation.
    """
    name = html_mod.escape(video["name"], quote=False)
    url = html_mod.escape(video["url"], quote=True)
    return (
        f'{INDENT}<p class="meeting-recording">'
        f'<a class="card-action" href="{url}" '
        f'target="_blank" rel="noopener noreferrer">'
        f"▶ Watch the presentation: {name}</a></p>\n"
    )


def videos_by_date(videos: list[dict]) -> dict[str, list[dict]]:
    by_date: dict[str, list[dict]] = {}
    for v in videos:
        if v["upload_date"]:
            by_date.setdefault(v["upload_date"], []).append(v)
    return by_date


def apply_to_page(text: str, page: str, videos: list[dict]) -> tuple[str, list[str]]:
    """Return (new text, warnings) for one recap page.

    `videos` is that date's recordings, possibly empty - an empty list removes
    both spans, so a card withdrawn from the presentations page is undone here
    too.
    """
    warnings: list[str] = []

    m = REGION_RE.search(text)
    if not m:
        raise ExtractionError(
            f"{page}: no quick-recap paragraph followed by a "
            f'"resource-tags meeting-tags" div; refusing to skip it silently'
        )

    owned = m.group(3)
    leftover = OWNED_P_RE.sub("", owned)
    if leftover.strip():
        warnings.append(
            f"{page}: replacing unrecognized markup between the quick recap "
            f"and the tag row: {leftover.strip()[:80]}"
        )

    # Whatever indented the tags div before still has to indent it after.
    indent = owned[owned.rfind("\n") + 1 :] if "\n" in owned else owned
    if indent.strip():
        indent = INDENT

    block = "".join(recording_paragraph(v) for v in videos)
    text = text[: m.start(3)] + block + indent + text[m.end(3) :]

    if videos:
        schema = render_block(build_items(videos), marker=MARKER)
        text = inject(text, schema, marker=MARKER)
    else:
        text = inject(text, "", marker=MARKER)

    return text, warnings


def plan(by_date: dict[str, list[dict]]) -> tuple[list[tuple[Path, str]], list[str]]:
    """Compute every recap's desired text. Returns (changes, warnings)."""
    changes: list[tuple[Path, str]] = []
    warnings: list[str] = []
    for path in sorted(MEETINGS_DIR.glob("[0-9]" * 4 + "-[0-9][0-9]-[0-9][0-9].html")):
        date = path.stem
        original = path.read_text(encoding="utf-8")
        updated, warns = apply_to_page(original, path.name, by_date.get(date, []))
        warnings.extend(warns)
        if updated != original:
            changes.append((path, updated))
    return changes, warnings


def self_test(by_date: dict[str, list[dict]]) -> list[str]:
    """Plant known-bad states in memory and confirm each detector fires.

    A clean `--check` is only worth believing if the machinery that would
    report a dirty one has been shown to work on this run. Nothing is written;
    every case operates on a string.
    """
    failures: list[str] = []

    dated = sorted(d for d in by_date if (MEETINGS_DIR / f"{d}.html").exists())
    if not dated:
        return ["self-test: no recap page has a recording to exercise"]
    with_video = MEETINGS_DIR / f"{dated[0]}.html"
    vids = by_date[dated[0]]

    without = next(
        (
            p
            for p in sorted(MEETINGS_DIR.glob("2*.html"))
            if p.stem not in by_date
        ),
        None,
    )

    # 1. A page that should carry a link, with the link stripped out.
    good, _ = apply_to_page(with_video.read_text(encoding="utf-8"), with_video.name, vids)
    stripped = OWNED_P_RE.sub("", good)
    fixed, _ = apply_to_page(stripped, with_video.name, vids)
    if stripped == good:
        failures.append("self-test: stripping the link changed nothing to detect")
    elif fixed != good:
        failures.append("self-test: a missing recording link was not restored")

    # 2. The same page with a corrupted video id in its schema block.
    corrupt = good.replace(vids[0]["video_id"], "zzzzzzzzzzz")
    repaired, _ = apply_to_page(corrupt, with_video.name, vids)
    if corrupt == good:
        failures.append("self-test: corrupting the video id changed nothing to detect")
    elif repaired != good:
        failures.append("self-test: a wrong video id in the schema was not corrected")

    # 3. A page with no recording, carrying a link and schema it should not.
    if without is not None:
        clean = without.read_text(encoding="utf-8")
        planted, _ = apply_to_page(clean, without.name, vids)
        removed, _ = apply_to_page(planted, without.name, [])
        if planted == clean:
            failures.append("self-test: planting a recording changed nothing to detect")
        elif removed != clean:
            failures.append("self-test: a withdrawn recording was not removed")

    # 4. Two recordings on one date - the branch no real date exercises yet.
    if len(vids) == 1:
        second = dict(vids[0], video_id="secondvid1", name="Second talk")
        second["url"] = "https://www.youtube.com/watch?v=secondvid1"
        pair, _ = apply_to_page(with_video.read_text(encoding="utf-8"), with_video.name, [vids[0], second])
        if pair.count('<p class="meeting-recording">') != 2:
            failures.append("self-test: a second recording on one date lost its link")
        if pair.count('"@type": "VideoObject"') != 2:
            failures.append("self-test: a second recording on one date lost its VideoObject")
        back, _ = apply_to_page(pair, with_video.name, vids)
        if back != good:
            failures.append("self-test: dropping back to one recording is not idempotent")

    return failures


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--check",
        action="store_true",
        help="report what would change and exit 1 if anything would; writes nothing",
    )
    args = ap.parse_args()

    try:
        videos = extract_videos(PRESENTATIONS.read_text(encoding="utf-8"))
    except ExtractionError as exc:
        print(f"sync_recap_videos: presentations.html: {exc}", file=sys.stderr)
        return 1

    by_date = videos_by_date(videos)
    undated = [v for v in videos if not v["upload_date"]]
    orphans = sorted(d for d in by_date if not (MEETINGS_DIR / f"{d}.html").exists())

    try:
        changes, warnings = plan(by_date)
        failures = self_test(by_date) if args.check else []
    except ExtractionError as exc:
        print(f"sync_recap_videos: {exc}", file=sys.stderr)
        return 1

    matched = sum(len(v) for d, v in by_date.items() if (MEETINGS_DIR / f"{d}.html").exists())
    print(
        f"{len(videos)} recordings on presentations.html: "
        f"{matched} on a recap page, {len(orphans)} with no recap, "
        f"{len(undated)} with no date in the card title"
    )
    for d in orphans:
        print(f"  no recap for {d}: {by_date[d][0]['name']}")
    for v in undated:
        print(f"  no date parsed from card title: {v['name']}")
    for w in warnings:
        print(f"  warning: {w}", file=sys.stderr)

    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        print("Refusing to report a result from machinery that failed its own test.",
              file=sys.stderr)
        return 1
    if args.check:
        print("Self-test passed (4 planted cases, all detected)")

    if args.check:
        if changes:
            print(f"\n{len(changes)} recap page(s) out of step with presentations.html:")
            for path, _ in changes:
                print(f"  {path.relative_to(ROOT)}")
            print("\nRun: python3 tools/sync_recap_videos.py")
            return 1
        print("All recap pages already carry their recording link and schema.")
        return 0

    for path, updated in changes:
        path.write_text(updated, encoding="utf-8")
    print(f"Updated {len(changes)} recap page(s)" if changes else "Already up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
