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
clamp would have prevented. That argument is about the wall clock main()
uses. The self-test keeps no clock of its own; it runs at the newest date the
files carry, for the reason given in self_test().

Every date on every surface has to be read before either clock is consulted,
or the run fails. A regex that stops matching some of the markup, or all of
it, reports no finding for what it skipped, which is also what a clean page
reports: see unread_surfaces().

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
from typing import List, Optional, Tuple

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


# Each surface has two regexes. The strict one reads a date's value, in exactly
# the shape update_news.py writes it. The loose one only finds where a date is
# marked up, whatever has become of the value: any element carrying the card
# date class, any datePublished or dateModified key, any pubDate or
# lastBuildDate element. unread_surfaces() requires the strict regex to read
# everything the loose one finds. A surface added here needs both, a row in
# unread_surfaces() and a rewrite in self_test(), or a markup change can leave
# some of its dates unread while every check stays green.
CARD_DATE_RE = re.compile(r'<p class="article-date">([^<]+)</p>')
JSONLD_DATE_RE = re.compile(r'"(datePublished|dateModified)": "([^"]+)"')
FEED_DATE_RE = re.compile(r"<(pubDate|lastBuildDate)>([^<]+)</\1>")
CARD_DATE_LOOSE_RE = re.compile(r'''(?<![\w-])class\s*=\s*["'][^"']*(?<![\w-])article-date(?![\w-])''')
JSONLD_DATE_LOOSE_RE = re.compile(r'"(?:datePublished|dateModified)"\s*:')
FEED_DATE_LOOSE_RE = re.compile(r"<(?:pubDate|lastBuildDate)\b")

# Finding = (surface, offending value, why)
Finding = Tuple[str, str, str]


def unread_surfaces(news_text: str, feed_text: str) -> List[Finding]:
    """Return a finding for each surface carrying a date its strict regex did not read.

    The checkers judge only what their regex matches, so markup that stops
    matching yields no finding, and no finding is also what a clean surface
    yields. On 2026-09-12, with every card date rewritten as
    <p class="article-date"><time>September 12, 2026</time></p> and the first
    set to September 30, --check exited 0 and printed "0 news cards" as though
    that were a count. The self-test passed too. Its plants insert well-formed
    elements of their own, so they fire as long as the anchor string they are
    inserted beside survives, whatever the real dates around them have become.
    With feed.xml's dates wrapped in CDATA instead, it passed the same way.

    Failing on zero was not enough: rewriting only the first card that way
    still passed, reading 119 of 120. So every date the loose regex finds has
    to fall inside a strict match. Over the last 400 committed versions of
    each file (news.html back to 2026-08-13, feed.xml to 2026-07-17), 112,800
    dates in all, the two regexes agreed on every one. Feed text cannot forge
    a loose match: card text is HTML-escaped, JSON-LD strings escape their
    quotes, and feed.xml escapes its angle brackets.

    A surface with nothing for either regex fails as well. update_news.py
    writes a date on every card, a datePublished and dateModified on every
    JSON-LD article plus a dateModified on the ItemList, and a lastBuildDate in
    every feed, and its main() exits before writing anything when it has no
    entries. So an empty surface means its markup was renamed or removed.
    """
    surfaces = (
        ("news.html card dates", "CARD_DATE_RE", CARD_DATE_RE, CARD_DATE_LOOSE_RE, news_text),
        ("news.html JSON-LD dates", "JSONLD_DATE_RE", JSONLD_DATE_RE, JSONLD_DATE_LOOSE_RE, news_text),
        ("feed.xml dates", "FEED_DATE_RE", FEED_DATE_RE, FEED_DATE_LOOSE_RE, feed_text),
    )
    findings: List[Finding] = []
    for surface, name, regex, loose, text in surfaces:
        spans = [m.span() for m in regex.finditer(text)]
        seen = [m.start() for m in loose.finditer(text)]
        missed = [pos for pos in seen if not any(start <= pos < end for start, end in spans)]
        if missed:
            why = (f"{name} read {len(seen) - len(missed)} of the {len(seen)} dates marked up here, "
                   f"so {len(missed)} went unchecked; the first is at {_line_at(text, missed[0])}")
        elif not spans:
            why = f"{name} matched no date and none is marked up here, so nothing on this surface was checked"
        else:
            continue
        findings.append((surface, regex.pattern, why))
    return findings


def _line_at(text: str, pos: int) -> str:
    """Name the line holding pos, with a bounded excerpt of it to search for."""
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    end = len(text) if end == -1 else end
    line_no = text.count("\n", 0, pos) + 1
    return f"line {line_no}: {text[max(start, pos - 40):min(end, pos + 120)].strip()}"


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


def _newest_date(news_text: str, feed_text: str) -> Optional[dt.datetime]:
    """Return the latest date on any surface, in UTC, or None if none parses.

    Parses exactly as the checkers do, and skips what does not parse because
    the control reports it. UTC is load-bearing: the feed plants are written
    with a literal +0000, so a clock carrying a feed item's +0530 would plant
    a time five and a half hours away from the one intended.
    """
    stamps: List[dt.datetime] = []
    for m in CARD_DATE_RE.finditer(news_text):
        try:
            day = dt.datetime.strptime(m.group(1).strip(), "%B %d, %Y")
        except ValueError:
            continue
        stamps.append(day.replace(tzinfo=dt.timezone.utc))
    for m in JSONLD_DATE_RE.finditer(news_text):
        parsed = _parse_iso(m.group(2).strip())
        if parsed is not None:
            stamps.append(parsed)
    for m in FEED_DATE_RE.finditer(feed_text):
        try:
            parsed = parsedate_to_datetime(m.group(2).strip())
        except (TypeError, ValueError):
            continue
        stamps.append(parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc))
    return max(stamps).astimezone(dt.timezone.utc) if stamps else None


def self_test(news_text: str, feed_text: str, grace: dt.timedelta) -> bool:
    """Plant a known-bad date on every surface and require each detector to fire.

    A gate that reports clean because it stopped matching is indistinguishable
    from a clean site, which is the failure this repo keeps recording. The
    boundary cases are as load-bearing as the positives: a value just inside
    the grace must NOT be reported, or the gate starts failing news runs for
    dates the clamp is designed to accept, and a gate that cries wolf gets
    muted. If you add a detector, add its planted case here.
    """
    # The clock is the newest date the files already carry, never a literal.
    # It was hardcoded to 2026-09-12 12:00, the morning this gate landed, so
    # the control asserted that nothing on the page was dated after 18:00 that
    # day. The page is re-rendered every three hours and its dates only move
    # forward: the first run to ingest a later article (PR #1696, 21:05) failed
    # here with nothing wrong on the page, as would every run after it. The
    # card plant below carried the same flaw a year out, as a literal
    # September 30, 2027.
    #
    # Judging real dates against real time is main()'s job, and it names the
    # offending value and the remedy. A control that did it too would fail
    # first and blame the checker for the content. Deriving the clock also
    # keeps every positive plant later than any real date, so a planted
    # finding can never equal a real one and be subtracted out with `base`.
    now = _newest_date(news_text, feed_text) or dt.datetime.now(dt.timezone.utc)
    inside = now + grace - dt.timedelta(minutes=5)
    outside = now + grace + dt.timedelta(hours=2)
    far = now + dt.timedelta(days=365)
    ok = True

    def report(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= passed
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}{(': ' + detail) if detail and not passed else ''}")

    # Control: at that clock nothing can be in the future, so what this proves
    # is that every date the files really carry parses - the formats
    # update_news.py actually writes, such as a feed item's non-UTC offset,
    # and not only the ones the plants below are built from.
    base = check_news_html(news_text, now, grace) + check_feed_xml(feed_text, now, grace)
    report("control: committed news.html and feed.xml are clean",
           not base, f"{len(base)} unexpected finding(s): {base[:3]}")

    cases = [
        ("card date far in the future",
         lambda t: t.replace('<p class="article-date">',
                             f'<p class="article-date">{far.strftime("%B %d, %Y")}</p><p class="article-date">', 1),
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

    # The plants above fire whenever their anchor string survives, so all of
    # them passed on 2026-09-12 against a page where CARD_DATE_RE read no real
    # card. These rewrite the real markup instead, the way a change to
    # update_news.py could, and require unread_surfaces() to name exactly the
    # surfaces listed. The first three rewrite a single date, because a surface
    # still almost entirely readable is the case a zero check missed. The
    # rename leaves the loose regex nothing to find. The last three are the
    # boundary: feed text quoting date markup arrives escaped and must not be
    # counted, or an article about RSS or schema.org would fail a news run.
    rewrites = [
        ("one card date wrapped in <time> is named unread", ["news.html card dates"],
         CARD_DATE_RE.sub(r'<p class="article-date"><time>\1</time></p>', news_text, count=1), feed_text),
        ("one JSON-LD date written without spaces is named unread", ["news.html JSON-LD dates"],
         JSONLD_DATE_RE.sub(r'"\1":"\2"', news_text, count=1), feed_text),
        ("one feed date wrapped in CDATA is named unread", ["feed.xml dates"],
         news_text, FEED_DATE_RE.sub(r"<\1><![CDATA[\2]]></\1>", feed_text, count=1)),
        ("card date class renamed on every card is named unread", ["news.html card dates"],
         news_text.replace('class="article-date"', 'class="card-date"'), feed_text),
        ("card text quoting the date class is not counted", [],
         news_text.replace('<span class="source">', 'class=&quot;article-date&quot; <span class="source">', 1),
         feed_text),
        ("JSON-LD text quoting a date key is not counted", [],
         news_text.replace('"inLanguage": "en-US"', '"inLanguage": "en-US", "abstract": "\\"datePublished\\": \\"x\\""', 1),
         feed_text),
        ("feed text quoting a date element is not counted", [],
         news_text, feed_text.replace("<description>", "<description>&lt;pubDate&gt;x&lt;/pubDate&gt; ", 1)),
    ]
    for name, expected, news, feed in rewrites:
        if (news, feed) == (news_text, feed_text):
            report(name, False, "rewrote nothing - the markup it rewrites is gone, so this case is untested")
            continue
        named = [s for s, _, _ in unread_surfaces(news, feed)]
        report(name, named == expected, f"expected {expected}, got {named}")

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

    # Before the self-test and the report, in every mode, because neither means
    # anything for a date nothing read: the plants fire regardless and the
    # report counts only what matched. See unread_surfaces().
    unread = unread_surfaces(news_text, feed_text)
    if unread:
        print(f"{len(unread)} surface(s) carry dates this gate did not read, so they went unchecked:",
              file=sys.stderr)
        for surface, pattern, why in unread:
            # Unquoted: a repr doubles every backslash, which misstates the regex.
            print(f"  {surface}: {why}\n    pattern: {pattern}", file=sys.stderr)
        print("\nThe markup changed shape under the regex, or the file is damaged. If "
              "update_news.py now writes these dates differently, update the regex here to "
              "match, and its _LOOSE_RE partner too if the element or key itself was renamed. "
              "For card dates, change ARTICLE_DATE_RE in update_news.py with it: "
              "parse_existing_cards() reads that markup back on every run and silently "
              "drops every card it cannot read.", file=sys.stderr)
        return 1

    if args.check or args.self_test:
        print(f"Self-test (grace = {grace}, imported from update_news.py):")
        if not self_test(news_text, feed_text, grace):
            print("Self-test FAILED: a detector did not fire, so a clean report "
                  "would mean nothing. Fix the checker before trusting it.",
                  file=sys.stderr)
            return 1
        print("Self-test passed: every detector fires and every boundary case is allowed.\n")
        if args.self_test:
            return 0

    now = dt.datetime.now(dt.timezone.utc)
    findings = (check_news_html(news_text, now, grace)
                + check_feed_xml(feed_text, now, grace))
    cards = len(CARD_DATE_RE.findall(news_text))
    stamps = len(JSONLD_DATE_RE.findall(news_text))
    items = len(FEED_DATE_RE.findall(feed_text))

    if not findings:
        print(f"OK: no future publish date in {cards} news cards, {stamps} JSON-LD dates "
              f"or {items} feed dates (ceiling {(now + grace).isoformat(timespec='seconds')}).")
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
