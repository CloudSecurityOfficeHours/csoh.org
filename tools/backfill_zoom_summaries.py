#!/usr/bin/env python3
"""Backfill meetings.html from Zoom AI Companion meeting summaries.

Scans the Zoom account for all Friday ~7am-PT CSOH meeting summaries,
cross-references with what's already on meetings.html, and for every NEW
date fetches the summary content, infers tags, and injects a new article
via tools/add_meeting.py.

Notes on de-duplication within a single Friday: Zoom AI Companion often
produces multiple summary records per meeting when the host stopped and
restarted the session. This script picks the EARLIEST summary on each
Friday (typically the main morning block), which in practice also has
the most complete recap.

Required Zoom S2S OAuth scopes beyond the fetcher:
    meeting:read:list_summaries:admin
    meeting:read:list_meetings:admin
    meeting:read:summary:admin

Usage:
    # Dry run — list what would be added, make no changes
    python3 tools/backfill_zoom_summaries.py --dry-run

    # Full backfill (default: skip dates already on page)
    python3 tools/backfill_zoom_summaries.py

    # Limit to N new meetings (useful to preview format on a small sample)
    python3 tools/backfill_zoom_summaries.py --limit 3

    # Replace existing dates too (will clobber Apple-Notes-sourced content)
    python3 tools/backfill_zoom_summaries.py --replace-existing
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fetch_zoom_transcript as z  # noqa: E402


REPO_ROOT = Path(__file__).resolve().parent.parent
MEETINGS_HTML = REPO_ROOT / "meetings.html"
PACIFIC = ZoneInfo("America/Los_Angeles")

# Keyword → tag. First-match wins for a given tag, multiple tags can attach.
# Keywords are matched case-insensitively against overview + topic headings.
TAG_RULES: list[tuple[str, list[str]]] = [
    ("AI", ["ai", "llm", "genai", "claude", "chatgpt", "gemini", "copilot", "mythos", "generative ai"]),
    ("Supply Chain", ["supply chain", "dependency", "npm", "pypi", "dependabot", "package", "trivy", "chainguard", "maintainer"]),
    ("Vulnerabilities", ["vulnerability", "vulnerabilities", "cve", "zero-day", "zero day", "exploit", "rce", "xss", "injection", "patch"]),
    ("Conferences", ["rsa", "black hat", "def con", "defcon", "sector", "keynote", "conference"]),
    ("Governance", ["policy as code", "compliance", "grc", "fedramp", "audit", "sbom", "policy", "governance"]),
    ("Guest Speaker", ["presented", "presentation", "talk on", "guest speaker", "spoke on", "demo"]),
    ("Passwords", ["password", "mfa", "multi-factor", "multifactor", "authentication"]),
    ("Insider Threats", ["insider threat", "malicious insider"]),
    ("SBOM", ["sbom", "software bill of materials"]),
    ("GitHub Actions", ["github actions", "workflow"]),
    ("Education", ["certification", "degree", "omscs", "homeschool", "teach"]),
    ("Community", ["welcome", "introduction", "new participant", "new member", "anniversary"]),
    ("Industry News", ["news", "acquisition", "acquired", "merger", "layoff"]),
    ("Anniversary", ["anniversary"]),
]


def pacific_info(iso_utc: str):
    if not iso_utc:
        return None
    if iso_utc.endswith("Z"):
        iso_utc = iso_utc[:-1] + "+00:00"
    try:
        d = dt.datetime.fromisoformat(iso_utc).astimezone(PACIFIC)
    except ValueError:
        return None
    return d


def is_csoh_friday_summary(s: dict, target_hour: int = 7, slack_min: int = 90) -> bool:
    topic = s.get("meeting_topic") or ""
    if "cloud security office hours" not in topic.lower():
        return False
    d = pacific_info(s.get("meeting_start_time", ""))
    if d is None or d.strftime("%a") != "Fri":
        return False
    mins = d.hour * 60 + d.minute
    return abs(mins - target_hour * 60) <= slack_min


def list_all_summaries(token: str, start_date: dt.date, end_date: dt.date) -> list[dict]:
    """Paginate monthly windows (Zoom caps each request at ~1 month)."""
    all_s: list[dict] = []
    seen: set[str] = set()
    window_start = start_date
    while window_start <= end_date:
        window_end = min(end_date, window_start + dt.timedelta(days=30))
        next_page_token = ""
        while True:
            params = {
                "from": window_start.isoformat() + "T00:00:00Z",
                "to": window_end.isoformat() + "T23:59:59Z",
                "page_size": 50,
            }
            if next_page_token:
                params["next_page_token"] = next_page_token
            try:
                data = z.api_get("/meetings/meeting_summaries", token, params)
            except urllib.error.HTTPError as exc:
                print(
                    f"[warn] {window_start}..{window_end}: HTTP {exc.code} {exc.reason}",
                    file=sys.stderr,
                )
                break
            for s in data.get("summaries", []):
                key = s.get("meeting_uuid") or ""
                if not key or key in seen:
                    continue
                seen.add(key)
                all_s.append(s)
            next_page_token = data.get("next_page_token", "")
            if not next_page_token:
                break
        window_start = window_end + dt.timedelta(days=1)
    return all_s


def fetch_summary_detail(token: str, uuid: str) -> dict:
    enc = urllib.parse.quote(urllib.parse.quote(uuid, safe=""), safe="")
    return z.api_get(f"/meetings/{enc}/meeting_summary", token)


def infer_tags(text: str, max_tags: int = 4) -> list[str]:
    low = text.lower()
    picked: list[str] = []
    for tag, keywords in TAG_RULES:
        if any(k in low for k in keywords):
            picked.append(tag)
        if len(picked) >= max_tags:
            break
    if not picked:
        picked = ["Community"]
    return picked


NOISE_TITLE_RE = re.compile(
    r'\b('
    r'music sharing'
    r'|audio clip[s]?'
    r'|sharing audio'
    r'|sharing music'
    r'|audio sharing session'
    r'|audio (?:and|&) chat'
    r'|audio reflections'
    r'|nonsensical (?:transcript|discussion|content|meeting)'
    r'|incoherent (?:rambling|monologue|discussion|transcript|meeting|song|conversation|lyric)'
    r'|rambling (?:without|with no) (?:clear|decisions|focus|topic)'
    r"|shawn(?:&#x27;|\u2019|')s disjointed"
    r'|disjointed (?:and (?:fragmented|unclear) )?'
    r'(?:discussion|conversation|monologue|meeting|transcript|thought)'
    r'|(?:provocative|song|incoherent|disjointed) lyrics?'
    r'|song lyric (?:and|discussion)'
    r'|lively discussion with music and camaraderie'
    r'|informal greeting and weather'
    r'|music discussion(?! at)'
    r'|opening greetings? (?:and|&) (?:music|chat)'
    r'|shawn listens to music'
    r'|listens to music quietly'
    r'|stream of consciousness'
    r'|indecipherable (?:meeting|discussion|transcript)'
    r'|bilingual text display'
    r'|(?:multilingual |)song medley'
    r'|warm-?up session'
    r'|philosophical (?:and )?poetic|poetic musings'
    r'|emotional connection (?:and|&)'
    r'|cybersecurity music video'
    r')\b',
    re.IGNORECASE,
)

NOISE_BODY_RE = re.compile(
    r'\b('
    r'no significant decisions or action items'
    r'|(?:no|lacks) clear decisions[,]? action items[,]? or substantial'
    r'|no clear decisions[,]? alignments[,]? (?:or )?action items'
    r'|without a coherent topic'
    r'|without more context or a clearer (?:discussion topic|structure)'
    r'|lacks a clear discussion'
    r'|lacks a clear focus'
    r'|doesn[\u2019\']t contain any substantive discussion'
    r'|do(?:es)?n[\u2019\']t (?:have|seem to have) a clear (?:focus|topic|discussion)'
    r'|no clear discussion topic'
    r"|it[\u2019\']s (?:not possible|difficult) to provide a meaningful summary"
    r'|disjointed (?:collection|sequence|conversation|set|series|and fragmented conversation|monologue) '
    r'(?:of (?:phrases|sentences|words|greetings|comments|messages)|with )'
    r'|series of greetings and pleasantries'
    r'|series of audio clips'
    r'|mix of audio (?:clips|and chat)'
    r'|recording of [Ss]hawn [Nn]unley (?:performing|sharing)'
    r'|playing various tracks'
    r'|largely incoherent and lacked clear discussion'
    r'|recites lyrics from various songs'
    r'|stream of consciousness'
    r'|monologue or song lyrics'
    r"|no decisions[,]? action items[,]? or meaningful content can be summarized"
    r'|nonsensical (?:phrases|lyrics|content)'
    r'|mostly nonsensical'
    r'|not possible to provide a meaningful summary'
    r"|isn[\u2019\']t possible to provide a meaningful summary"
    r'|rather than a (?:real|meaningful|coherent) (?:meeting|discussion|conversation)'
    r'|without a (?:real|coherent) (?:topic|focus|discussion|conversation)'
    r'|rambling incoherently'
    r'|no meaningful conversation captured'
    r'|there does not seem to be any substantive content'
    r'|lyrics do not seem to convey any clear'
    r'|before any substantial business was addressed'
    r'|enjoy(?:ing|ed)? the music and camaraderie'
    r'|joining in the chorus'
    r'|audio clips and messages, including music'
    r'|listening to music and occasionally'
    r'|no substantive discussion or decisions seem to have taken place'
    r'|screen-?share (?:appears to )?display(?:s|ing)? (?:a (?:mix|series) of |what appears to be )?(?:song lyrics|disconnected|a poem)'
    r'|performs a medley (?:of |)'
    r'|reciting song lyrics'
    r'|warming up for (?:a |the )meeting (?:or |)(?:presentation )?by singing'
    r'|philosophical and poetic (?:statements|musings)'
    r'|feelings of loneliness (?:and longing|)'
    r'|expressed (?:his |her |)feelings about a past relationship'
    r'|random with recurring phrases'
    r'|song lyrics, greetings, and disconnected phrases'
    r'|lively discussion, filled with music'
    r')',
    re.IGNORECASE,
)


def _strip_noise_sections(markdown: str) -> str:
    """Remove ### subsections that look like AI-gave-up or music-chitchat
    summaries (the ones the Zoom transcript pulls from intro music or
    quiet meetings). Each subsection runs from `### Heading\\n` up to the
    next `### ` or end of file."""
    section_re = re.compile(
        r'(?P<full>^### (?P<heading>[^\n]+)\n(?P<body>(?:(?!^### ).*\n?)+))',
        re.MULTILINE,
    )

    def maybe_strip(m: re.Match) -> str:
        heading = m.group("heading").strip()
        body = m.group("body").strip()
        if NOISE_TITLE_RE.search(heading) or NOISE_BODY_RE.search(body):
            return ""
        return m.group("full")

    return section_re.sub(maybe_strip, markdown)


def build_markdown(summary: dict, pacific_date: str) -> str:
    content = summary.get("summary_content", "").strip()
    if not content:
        raise ValueError("empty summary_content")
    # Strip Zoom's "Next steps" section first — those entries reference private
    # tasks.zoom.us action-item URLs and are mostly noise on a public page.
    # Stop at the next heading (## or ###).
    content = re.sub(
        r"^## Next steps\s*\n(?:(?!^#{2,3} ).*\n)*",
        "",
        content,
        flags=re.MULTILINE,
    )
    # Normalize: the content has "## Summary" preceding "### Topic" subheadings.
    # add_meeting.py's markdown parser treats h1/h2/h3 equally, so that works out
    # (the empty "## Summary" body is skipped by the parser), but we prepend the
    # required H1 and strip the redundant "## Summary" divider.
    content = re.sub(r"^## Summary\s*\n", "", content, flags=re.MULTILINE)
    # Strip music chitchat / AI-gave-up subsections (intro music, etc.).
    content = _strip_noise_sections(content)
    return f"# CSOH {pacific_date}\n\n{content.strip()}\n"


def already_on_page() -> set[str]:
    txt = MEETINGS_HTML.read_text(encoding="utf-8")
    return set(re.findall(r'id="meeting-(\d{4}-\d{2}-\d{2})"', txt))


def run_add_meeting(md_path: Path, tags: list[str]) -> int:
    cmd = [sys.executable, str(Path(__file__).parent / "add_meeting.py"), str(md_path)]
    for t in tags:
        cmd += ["--tag", t]
    return subprocess.call(cmd)


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill meetings.html from Zoom AI Companion summaries.")
    parser.add_argument("--dry-run", action="store_true", help="List what would be added; make no changes.")
    parser.add_argument("--limit", type=int, default=0, help="Process at most N new meetings (0 = unlimited).")
    parser.add_argument("--replace-existing", action="store_true", help="Also replace meetings already on the page.")
    parser.add_argument("--months-back", type=int, default=60, help="How far back to scan (default 60).")
    parser.add_argument("--target-hour", type=int, default=7, help="Pacific hour for CSOH filter (default 7).")
    parser.add_argument("--hour-slack", type=int, default=90, help="Minutes either side of --target-hour (default 90).")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env")
    args = parser.parse_args()

    z.load_dotenv(args.env_file)
    missing = [k for k in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET") if not os.environ.get(k)]
    if missing:
        print(f"Missing env vars: {', '.join(missing)}", file=sys.stderr)
        return 1

    token = z.get_access_token(
        os.environ["ZOOM_ACCOUNT_ID"],
        os.environ["ZOOM_CLIENT_ID"],
        os.environ["ZOOM_CLIENT_SECRET"],
    )

    today = dt.date.today()
    start = today - dt.timedelta(days=31 * args.months_back)
    print(f"Scanning summaries from {start} to {today}…", file=sys.stderr)
    all_summaries = list_all_summaries(token, start, today)
    print(f"  found {len(all_summaries)} total summaries.", file=sys.stderr)

    # Filter to Friday ~7am PT CSOH topic.
    friday_summaries = [
        s for s in all_summaries
        if is_csoh_friday_summary(s, args.target_hour, args.hour_slack)
    ]
    print(f"  {len(friday_summaries)} match CSOH Friday {args.target_hour}:00 PT ±{args.hour_slack}m.", file=sys.stderr)

    # Group by Pacific date; keep all candidates sorted by duration desc so we
    # can try the longest one first and fall back if it has empty content.
    def summary_duration_sec(s: dict) -> int:
        start = pacific_info(s.get("meeting_start_time", ""))
        end = pacific_info(s.get("meeting_end_time", ""))
        if start is None or end is None:
            return 0
        return int((end - start).total_seconds())

    candidates_by_date: dict[str, list[dict]] = {}
    for s in friday_summaries:
        d = pacific_info(s.get("meeting_start_time", ""))
        if d is None:
            continue
        key = d.date().isoformat()
        candidates_by_date.setdefault(key, []).append(s)
    for key, lst in candidates_by_date.items():
        lst.sort(key=summary_duration_sec, reverse=True)
    print(f"  {len(candidates_by_date)} unique Fridays.", file=sys.stderr)

    existing = already_on_page()
    if args.replace_existing:
        candidate_dates = sorted(candidates_by_date.keys(), reverse=True)
    else:
        candidate_dates = sorted([d for d in candidates_by_date if d not in existing], reverse=True)
    print(f"  {len(candidate_dates)} to publish (skip={'no' if args.replace_existing else 'yes'}).", file=sys.stderr)

    if args.limit and args.limit < len(candidate_dates):
        candidate_dates = candidate_dates[:args.limit]
        print(f"  limited to first {len(candidate_dates)}.", file=sys.stderr)

    # add_meeting.py inserts each new article at the TOP of the list, so to end
    # up with newest-first order we need to publish OLDEST first — the newest
    # date lands on top last.
    todo_dates = list(reversed(candidate_dates))

    if not todo_dates:
        print("Nothing to do.", file=sys.stderr)
        return 0

    staging = Path("/tmp/csoh-backfill")
    staging.mkdir(parents=True, exist_ok=True)

    successes = 0
    failures: list[tuple[str, str]] = []

    for date in todo_dates:
        # Try each candidate on this date (longest duration first) until one has
        # non-empty content — Zoom often produces short fragment summaries when
        # a recording was stopped/restarted.
        detail = None
        tried = 0
        last_err = ""
        for meta in candidates_by_date[date]:
            uuid = meta["meeting_uuid"]
            tried += 1
            try:
                d = fetch_summary_detail(token, uuid)
            except urllib.error.HTTPError as exc:
                last_err = f"HTTP {exc.code}"
                continue
            if (d.get("summary_content") or "").strip():
                detail = d
                break
            last_err = "empty summary_content"

        if detail is None:
            print(f"  [skip {date}] no usable summary after {tried} candidate(s): {last_err}", file=sys.stderr)
            failures.append((date, last_err or "no summary"))
            continue

        overview = detail.get("summary_overview", "") or ""
        topic_labels = " ".join(
            (d.get("label") or "") for d in detail.get("summary_details", [])
        )
        tags = infer_tags(f"{overview} {topic_labels}")

        try:
            md = build_markdown(detail, date)
        except ValueError as exc:
            print(f"  [skip {date}] {exc}", file=sys.stderr)
            failures.append((date, str(exc)))
            continue

        md_path = staging / f"csoh-{date}.md"
        md_path.write_text(md, encoding="utf-8")

        if args.dry_run:
            print(f"  [dry] {date}  tags={tags}  md={md_path.name}")
            continue

        rc = run_add_meeting(md_path, tags)
        if rc == 0:
            successes += 1
            print(f"  [ok ] {date}  tags={tags}")
        else:
            failures.append((date, f"add_meeting rc={rc}"))
            print(f"  [fail] {date}  add_meeting exited {rc}", file=sys.stderr)

    print(
        f"\nDone. published={successes}  failures={len(failures)}  dry_run={args.dry_run}",
        file=sys.stderr,
    )
    for date, reason in failures:
        print(f"  failure {date}: {reason}", file=sys.stderr)
    return 0 if not failures else 2


if __name__ == "__main__":
    sys.exit(main())
