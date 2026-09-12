#!/usr/bin/env python3
"""Fail if news.html or feed.xml carries a publish date in the future.

Publishers leak scheduled-publish dates into RSS. ReversingLabs served
2026-09-30 for a post its own feed later dated 2026-08-26; Huntress served
2026-09-15 for a post that was already live. update_news.py took pubDate
verbatim, and a future date taken verbatim is permanent:

  - parse_existing_cards() reads the date back out of news.html on the next
    run, so the page re-stamps its own bad value every three hours.
  - An already-published URL is skipped before its feed item is looked at
    again, so the publisher's later correction never reaches us.
  - Entries sort newest-first before the max_articles cut, so the card is
    pinned to slot 1 and cannot be evicted until real time passes it.

clamp_future_date() in update_news.py now stops these at ingest. This gate is
the assertion that it worked, and it covers the paths the clamp does not: a
hand edit, a restored backup, or a future date arriving through some route
nobody has thought of yet. Both cards sat at the top of the page for weeks,
and in the JSON-LD ItemList crawlers read, with every existing gate green -
no link checker or HTML validator has an opinion about a date.

The ceiling tracks the clamp rather than being chosen independently:
FUTURE_DATE_GRACE is imported from update_news.py, so the two cannot drift
apart and legitimately-accepted near-future dates are never reported. Card
dates are date-only, so they are compared against (now + grace).date();
timestamps in the JSON-LD and the feed are compared against now + grace
directly. This gate always runs later than the clamp did, so its `now` is
larger and its ceiling only ever wider - it cannot invent a finding the
clamp would have prevented.

Usage:
    python3 tools/check_news_dates.py            # report findings
    python3 tools/check_news_dates.py --check    # self-test, then report; exit 1 on any finding
    python3 tools/check_news_dates.py --self-test
"""
import argparse
import datetime as dt
import importlib.util
import os
import re
import sys
from email.utils import parsedate_to_datetime
from typing import List, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEWS_HTML = os.path.join(REPO_ROOT, "news.html")
FEED_XML = os.path.join(REPO_ROOT, "feed.xml")


def _load_grace() -> dt.timedelta:
    """Import FUTURE_DATE_GRACE from update_news.py.

    Imported rather than restated: a gate carrying its own copy of the
    threshold is a second source of truth that drifts silently. If the symbol
    is ever renamed or removed, this raises instead of quietly falling back to
    a guess that would report findings the clamp deliberately allows.
    """
    path = os.path.join(REPO_ROOT, "update_news.py")
    spec = importlib.util.spec_from_file_location("_update_news_for_grace", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.FUTURE_DATE_GRACE


CARD_DATE_RE = re.compile(r'<p class="article-date">([^<]+)</p>')
JSONLD_DATE_RE = re.compile(r'"(datePublished|dateModified)": "([^"]+)"')
FEED_DATE_RE = re.compile(r"<(pubDate|lastBuildDate)>([^<]+)</\1>")

# Finding = (surface, offending value, why)
Finding = Tuple[str, str, str]


def check_news_html(text: str, now: dt.datetime, grace: dt.timedelta) -> List[Finding]:
    findings: List[Finding] = []
    date_ceiling = (now + grace).date()

    for m in CARD_DATE_RE.finditer(text):
        raw = m.group(1).strip()
        try:
            d = dt.datetime.strptime(raw, "%B %d, %Y").date()
        except ValueError:
            findings.append(("news.html card", raw, "not a parseable 'Month DD, YYYY' date"))
            continue
        if d > date_ceiling:
            findings.append(
                ("news.html card", raw, f"dated after {date_ceiling.isoformat()}")
            )

    stamp_ceiling = now + grace
    for m in JSONLD_DATE_RE.finditer(text):
        field, raw = m.group(1), m.group(2).strip()
        parsed = _parse_iso(raw)
        if parsed is None:
            findings.append((f"news.html JSON-LD {field}", raw, "not a parseable ISO 8601 timestamp"))
            continue
        if parsed > stamp_ceiling:
            findings.append(
                (f"news.html JSON-LD {field}", raw, f"after {stamp_ceiling.isoformat()}")
            )
    return findings


def check_feed_xml(text: str, now: dt.datetime, grace: dt.timedelta) -> List[Finding]:
    findings: List[Finding] = []
    stamp_ceiling = now + grace
    for m in FEED_DATE_RE.finditer(text):
        field, raw = m.group(1), m.group(2).strip()
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            findings.append((f"feed.xml {field}", raw, "not a parseable RFC 2822 date"))
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        if parsed > stamp_ceiling:
            findings.append((f"feed.xml {field}", raw, f"after {stamp_ceiling.isoformat()}"))
    return findings


def _parse_iso(value: str):
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            parsed = dt.datetime.strptime(value, fmt)
        except ValueError:
            continue
        return parsed.replace(tzinfo=dt.timezone.utc) if parsed.tzinfo is None else parsed
    return None


def self_test(news_text: str, feed_text: str, grace: dt.timedelta) -> bool:
    """Plant a known-bad date on every surface and require each detector to fire.

    A gate that reports clean because it stopped matching is indistinguishable
    from a clean site, which is the failure this repo keeps recording. The
    boundary cases are as load-bearing as the positives: a value just inside
    the grace must NOT be reported, or the gate starts failing news runs for
    dates the clamp is designed to accept, and a gate that cries wolf gets
    muted. If you add a detector, add its planted case here.
    """
    now = dt.datetime(2026, 9, 12, 12, 0, tzinfo=dt.timezone.utc)
    inside = now + grace - dt.timedelta(minutes=5)
    outside = now + grace + dt.timedelta(hours=2)
    ok = True

    def report(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}{(': ' + detail) if detail and not passed else ''}")

    # Control: the real files, as committed, must be clean at a `now` that is
    # at or past their newest date. Without this the positives below prove
    # only that the regexes match something, not that the site is healthy.
    base = check_news_html(news_text, now, grace) + check_feed_xml(feed_text, now, grace)
    report("control: committed news.html and feed.xml are clean",
           not base, f"{len(base)} unexpected finding(s): {base[:3]}")

    cases = [
        ("card date far in the future",
         lambda t: t.replace('<p class="article-date">',
                             '<p class="article-date">September 30, 2027</p><p class="article-date">', 1),
         check_news_html, news_text, True),
        ("card date unparseable",
         lambda t: t.replace('<p class="article-date">',
                             '<p class="article-date">Septembruary 40, 2026</p><p class="article-date">', 1),
         check_news_html, news_text, True),
        ("JSON-LD datePublished in the future",
         lambda t: t.replace('"datePublished": "', f'"datePublished": "{outside.strftime("%Y-%m-%dT%H:%M:%SZ")}", "x": "', 1),
         check_news_html, news_text, True),
        ("feed pubDate in the future",
         lambda t: t.replace("<pubDate>", f"<pubDate>{outside.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate><pubDate>", 1),
         check_feed_xml, feed_text, True),
        ("card date just inside the grace is allowed",
         lambda t: t.replace('<p class="article-date">',
                             f'<p class="article-date">{(now + grace).strftime("%B %d, %Y")}</p><p class="article-date">', 1),
         check_news_html, news_text, False),
        ("feed pubDate just inside the grace is allowed",
         lambda t: t.replace("<pubDate>", f"<pubDate>{inside.strftime('%a, %d %b %Y %H:%M:%S +0000')}</pubDate><pubDate>", 1),
         check_feed_xml, feed_text, False),
    ]

    for name, mutate, checker, text, should_fire in cases:
        mutated = mutate(text)
        if mutated == text:
            report(name, False, "planted nothing - the anchor string is gone, so this detector is untested")
            continue
        found = [f for f in checker(mutated, now, grace) if f not in base]
        report(name, bool(found) == should_fire,
               f"expected {'a finding' if should_fire else 'no finding'}, got {found[:2]}")

    return ok


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="run the self-test first, then report; exit 1 on any finding")
    ap.add_argument("--self-test", action="store_true",
                    help="only prove every detector fires, then exit")
    args = ap.parse_args(argv)

    grace = _load_grace()
    with open(NEWS_HTML, encoding="utf-8") as f:
        news_text = f.read()
    with open(FEED_XML, encoding="utf-8") as f:
        feed_text = f.read()

    if args.check or args.self_test:
        print(f"Self-test (grace = {grace}, imported from update_news.py):")
        if not self_test(news_text, feed_text, grace):
            print("Self-test FAILED: a detector did not fire, so a clean report "
                  "would mean nothing. Fix the checker before trusting it.",
                  file=sys.stderr)
            return 1
        print("Self-test passed: every detector fires and both boundary cases are allowed.\n")
        if args.self_test:
            return 0

    now = dt.datetime.now(dt.timezone.utc)
    findings = (check_news_html(news_text, now, grace)
                + check_feed_xml(feed_text, now, grace))
    cards = len(CARD_DATE_RE.findall(news_text))
    items = len(FEED_DATE_RE.findall(feed_text))

    if not findings:
        print(f"OK: no future publish date in {cards} news cards or {items} feed dates "
              f"(ceiling {(now + grace).isoformat(timespec='seconds')}).")
        return 0

    print(f"{len(findings)} future or malformed publish date(s):", file=sys.stderr)
    for surface, value, why in findings:
        print(f"  {surface}: {value!r} - {why}", file=sys.stderr)
    print("\nA future date pins its card to the top of news.html and cannot be "
          "evicted until real time passes it. If a feed is the source, extend "
          "clamp_future_date() in update_news.py; if the page is already wrong, "
          "correct the date and re-render so the date-group headings, counts, "
          "JSON-LD ItemList and feed.xml stay consistent.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
