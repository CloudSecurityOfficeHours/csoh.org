#!/usr/bin/env python3
"""Render the public CSOH Google Calendar into calendar.html as static HTML.

The site has no server and ships no third-party scripts, so a Google Calendar
embed is out: its iframe is blocked by the CSP (`frame-src` falls under
`default-src 'self'`) and it would hand every visitor to Google. Instead this
tool reads the calendar's public iCalendar feed in CI, expands it into the next
dozen occurrences, and writes them into calendar.html as ordinary cards, the
same way update_news.py writes news.html. The reader gets HTML; the maintainer
edits the calendar in Google and nothing else.

What it reads
-------------
The calendar's public ICS (`ICS_URL`). It is a plain RFC 5545 file: one VEVENT
per series or one-off, `RRULE` for the weekly cadence, `EXDATE` for skipped
weeks, and a second VEVENT carrying `RECURRENCE-ID` for any instance that was
moved or cancelled. Everything a maintainer does in the Google UI shows up as
one of those four shapes, and all four are handled here with the standard
library only, so the CI job needs no pip install.

What it writes
--------------
The block between `<!-- calendar:events:start -->` and
`<!-- calendar:events:end -->` in calendar.html, and nothing outside it: the
page's title, description and prose stay hand-written, following the same rule
as the other generators (DEVELOPMENT.md, "page-level SEO metadata").

Times are shown in Pacific first, because every other page says "7am PT", with
Eastern alongside. Subscribers get their own timezone from the feed itself.

What it refuses to publish
--------------------------
The Zoom link is deliberately behind the mailing list (sessions.html says so,
and check_private_invites.py gates the same promise for chat invites). A
calendar description is where a Zoom join URL, meeting ID or passcode is most
likely to be pasted, so every description and location is scrubbed: join URLs
on the meeting hosts in `PRIVATE_HOSTS` become "(Zoom link via the CSOH mailing
list)", lines that read like dial-in details are dropped, and email addresses
outside csoh.org are removed. Other URLs are kept and made clickable.

Usage
-----
    python3 tools/sync_calendar.py                 # fetch, render, write if changed
    python3 tools/sync_calendar.py --check         # exit 1 if the page is stale
    python3 tools/sync_calendar.py --ics FILE      # render from a saved feed
    python3 tools/sync_calendar.py --self-test     # prove the parser and scrubber

--check is not wired into CI on purpose, for the same reason as
sync_next_session.py: the page goes stale every Friday on its own, with no
commit to blame. Freshness comes from update-calendar.yml running this on a
schedule and opening a PR when the output moved.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

REPO = Path(__file__).resolve().parent.parent
PAGE = REPO / "calendar.html"

# The CSOH community calendar. The id is public by design: it is what a reader
# pastes into their own calendar app to subscribe.
CALENDAR_ID = "14386e48ea9f9cd57a6d2edf3689ef25d9c2cd0bdf4edeeb63bcd501e60dcb1e@group.calendar.google.com"
ICS_URL = f"https://calendar.google.com/calendar/ical/{quote(CALENDAR_ID)}/public/basic.ics"

# The site's clock is Pacific ("Friday 7am PT" on every page). The calendar is
# kept in Eastern by its maintainer, so Eastern is shown second.
SITE_TZ = ZoneInfo("America/Los_Angeles")
SECOND_TZ = ZoneInfo("America/New_York")
UTC = timezone.utc

# How much of the future to render. Twelve occurrences is about a quarter of
# Fridays; the horizon stops a long-dated one-off from being padded with half a
# year of identical weekly cards.
LIMIT = 12
HORIZON_DAYS = 180

START_MARK = "<!-- calendar:events:start -->"
END_MARK = "<!-- calendar:events:end -->"

# Meeting hosts whose URLs are join links. Anything on these hosts is replaced
# rather than published, whatever the path looks like, because a join URL with
# the passcode embedded (`?pwd=`) is the common case in Google Calendar.
PRIVATE_HOSTS = (
    "zoom.us", "zoom.com", "zoomgov.com",
    "meet.google.com", "teams.microsoft.com", "teams.live.com",
    "webex.com", "whereby.com", "meet.jit.si", "gotomeeting.com",
)
PRIVATE_LINE_RE = re.compile(
    r"(meeting id|passcode|password|dial by|dial-in|one tap mobile|find your local number|join by phone)",
    re.I,
)
URL_RE = re.compile(r"https?://[^\s<>\"']+")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PRIVATE_LINK_TEXT = "(Zoom link via the CSOH mailing list)"
# Links back to this site are dropped from event text: the reader is already
# here, and the calendar's own boilerplate ends every entry with the homepage.
OWN_HOSTS = ("csoh.org",)
PRIVATE_LOCATION_TEXT = "Zoom (link via the CSOH mailing list)"
# Where a reader gets the Zoom link: the mailing-list sign-up, the same
# address as the page's "Get the Zoom link" button.
ZOOM_SIGNUP_URL = "https://csoh.kit.com/39feb4f397"

WEEKDAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
MAX_INSTANCES = 5000   # a runaway RRULE stops here rather than never


# --- iCalendar parsing -------------------------------------------------------

Props = dict[str, list[tuple[dict[str, str], str]]]


def unfold(raw: str) -> str:
    """Join RFC 5545 continuation lines (a line break followed by a space or tab)."""
    return re.sub(r"\r?\n[ \t]", "", raw).replace("\r\n", "\n").replace("\r", "\n")


def split_content_line(line: str) -> tuple[str, str]:
    """Split NAME;PARAM="a:b":VALUE at the first colon outside double quotes."""
    in_quotes = False
    for i, ch in enumerate(line):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ":" and not in_quotes:
            return line[:i], line[i + 1:]
    return line, ""


def parse_params(head: str) -> tuple[str, dict[str, str]]:
    parts = head.split(";")
    params: dict[str, str] = {}
    for part in parts[1:]:
        key, _, value = part.partition("=")
        params[key.upper()] = value.strip('"')
    return parts[0].upper(), params


def parse_calendar(raw: str) -> tuple[list[Props], dict[str, str]]:
    """Return the VEVENTs and the top-level VCALENDAR properties."""
    if "BEGIN:VCALENDAR" not in raw:
        raise SystemExit("not an iCalendar feed: no BEGIN:VCALENDAR (did the fetch return an error page?)")
    events: list[Props] = []
    top: dict[str, str] = {}
    stack: list[tuple[str, Props]] = []
    for line in unfold(raw).split("\n"):
        if not line:
            continue
        if line.startswith("BEGIN:"):
            stack.append((line[6:].upper(), {}))
            continue
        if line.startswith("END:"):
            if stack:
                name, props = stack.pop()
                if name == "VEVENT":
                    events.append(props)
            continue
        head, value = split_content_line(line)
        name, params = parse_params(head)
        if len(stack) == 1 and stack[0][0] == "VCALENDAR":
            top[name] = value
        elif stack and stack[-1][0] == "VEVENT":
            stack[-1][1].setdefault(name, []).append((params, value))
    return events, top


def first(props: Props, name: str) -> tuple[dict[str, str], str] | None:
    values = props.get(name)
    return values[0] if values else None


def tz_for(tzid: str | None, default: ZoneInfo) -> ZoneInfo:
    if not tzid:
        return default
    try:
        return ZoneInfo(tzid)
    except ZoneInfoNotFoundError:
        print(f"warning: unknown TZID {tzid!r}, using {default.key}", file=sys.stderr)
        return default


def parse_dt(value: str, params: dict[str, str], default_tz: ZoneInfo) -> tuple[datetime, bool]:
    """(aware datetime, is_all_day).

    An all-day value is a calendar date, not an instant, so it is anchored to
    midnight in the site's zone rather than the feed's: anchored to Eastern it
    would render as the previous evening in Pacific.
    """
    if params.get("VALUE") == "DATE" or re.fullmatch(r"\d{8}", value):
        d = date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        return datetime(d.year, d.month, d.day, tzinfo=SITE_TZ), True
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})(Z?)", value)
    if not m:
        raise ValueError(f"unreadable date-time {value!r}")
    y, mo, d, hh, mm, ss, zulu = m.groups()
    naive = datetime(int(y), int(mo), int(d), int(hh), int(mm), int(ss))
    if zulu:
        return naive.replace(tzinfo=UTC), False
    return naive.replace(tzinfo=tz_for(params.get("TZID"), default_tz)), False


DURATION_RE = re.compile(
    r"^(?P<sign>[+-])?P(?:(?P<w>\d+)W)?(?:(?P<d>\d+)D)?"
    r"(?:T(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?)?$"
)


def parse_duration(value: str) -> timedelta:
    m = DURATION_RE.match(value.strip())
    if not m:
        raise ValueError(f"unreadable duration {value!r}")
    g = {k: int(v or 0) for k, v in m.groupdict().items() if k != "sign"}
    td = timedelta(weeks=g["w"], days=g["d"], hours=g["h"], minutes=g["m"], seconds=g["s"])
    return -td if m.group("sign") == "-" else td


def ics_unescape(value: str) -> str:
    out = []
    i = 0
    while i < len(value):
        ch = value[i]
        if ch == "\\" and i + 1 < len(value):
            nxt = value[i + 1]
            if nxt in "nN":
                out.append("\n")
            elif nxt in ",;\\":
                out.append(nxt)
            else:
                out.append(ch + nxt)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# --- Recurrence expansion ----------------------------------------------------

def parse_rrule(value: str) -> dict[str, str]:
    rule: dict[str, str] = {}
    for part in value.split(";"):
        key, _, val = part.partition("=")
        if key:
            rule[key.upper()] = val
    return rule


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date | None:
    """The n-th (1-based; negative counts from the end) given weekday of a month."""
    if n == 0:
        return None
    if n > 0:
        d = date(year, month, 1)
        d += timedelta(days=(weekday - d.weekday()) % 7)
        d += timedelta(weeks=n - 1)
    else:
        nxt = date(year + (month == 12), month % 12 + 1, 1)
        d = nxt - timedelta(days=1)
        d -= timedelta(days=(d.weekday() - weekday) % 7)
        d += timedelta(weeks=n + 1)
    return d if d.month == month else None


def expand(start: datetime, rule: dict[str, str], horizon: datetime) -> list[datetime]:
    """Occurrences of a recurrence rule from DTSTART up to the horizon.

    Supports the shapes a Google Calendar can produce for a community calendar:
    DAILY, WEEKLY (BYDAY, WKST), MONTHLY (BYMONTHDAY or ordinal BYDAY such as
    2FR or -1FR, else the DTSTART day) and YEARLY, each with INTERVAL, COUNT
    and UNTIL. COUNT bounds the rule's own set, before EXDATE is applied, as
    RFC 5545 says. Anything else falls back to the first instance alone, with a
    warning, rather than guessing.

    Instances are built as the same wall-clock time in DTSTART's zone, which is
    what a recurring 7am means across a DST change.
    """
    freq = rule.get("FREQ", "").upper()
    interval = max(1, int(rule.get("INTERVAL", "1") or 1))
    count = int(rule["COUNT"]) if rule.get("COUNT") else None
    until: datetime | None = None
    if rule.get("UNTIL"):
        until_dt, until_all_day = parse_dt(rule["UNTIL"], {}, start.tzinfo)  # type: ignore[arg-type]
        until = until_dt + timedelta(days=1) if until_all_day else until_dt

    def wall(d: date) -> datetime:
        return start.replace(year=d.year, month=d.month, day=d.day)

    candidates: list[datetime] = []

    def accept(dt: datetime) -> bool:
        """Append dt if it belongs to the set; False once the set is finished."""
        if dt < start:
            return True
        if until is not None and dt > until:
            return False
        if dt > horizon:
            return False
        candidates.append(dt)
        return count is None or len(candidates) < count

    if freq == "DAILY":
        d = start.date()
        for _ in range(MAX_INSTANCES):
            if not accept(wall(d)):
                break
            d += timedelta(days=interval)

    elif freq == "WEEKLY":
        wkst = WEEKDAYS.get(rule.get("WKST", "MO").upper(), 0)
        bydays = [WEEKDAYS[x.strip()[-2:]] for x in rule.get("BYDAY", "").split(",") if x.strip()]
        if not bydays:
            bydays = [start.weekday()]
        week_start = start.date() - timedelta(days=(start.weekday() - wkst) % 7)
        done = False
        for _ in range(MAX_INSTANCES):
            for wd in sorted(bydays, key=lambda w: (w - wkst) % 7):
                if not accept(wall(week_start + timedelta(days=(wd - wkst) % 7))):
                    done = True
                    break
            if done:
                break
            week_start += timedelta(weeks=interval)

    elif freq == "MONTHLY":
        y, m = start.year, start.month
        monthdays = [int(x) for x in rule.get("BYMONTHDAY", "").split(",") if x.strip()]
        ordinal_days = []
        for token in rule.get("BYDAY", "").split(","):
            token = token.strip()
            if token:
                ordinal_days.append((int(token[:-2] or 0), WEEKDAYS[token[-2:]]))
        done = False
        for _ in range(MAX_INSTANCES):
            days: list[date] = []
            if monthdays:
                for md in monthdays:
                    try:
                        days.append(date(y, m, md))
                    except ValueError:
                        pass
            elif ordinal_days:
                for n, wd in ordinal_days:
                    d = nth_weekday(y, m, wd, n)
                    if d:
                        days.append(d)
            else:
                try:
                    days.append(date(y, m, start.day))
                except ValueError:
                    pass
            for d in sorted(days):
                if not accept(wall(d)):
                    done = True
                    break
            if done:
                break
            m += interval
            y, m = y + (m - 1) // 12, (m - 1) % 12 + 1

    elif freq == "YEARLY":
        y = start.year
        for _ in range(MAX_INSTANCES):
            try:
                d = date(y, start.month, start.day)
            except ValueError:
                d = None
            if d and not accept(wall(d)):
                break
            y += interval

    else:
        print(f"warning: unsupported RRULE {rule!r}; rendering the first instance only", file=sys.stderr)
        candidates.append(start)

    return candidates


# --- Occurrences --------------------------------------------------------------

@dataclass(frozen=True)
class Occurrence:
    uid: str
    start: datetime
    end: datetime
    summary: str
    description: str   # raw ICS text; scrubbed at render time
    location: str
    url: str
    all_day: bool
    kind: str          # "weekly", "recurring", "moved" or "single"
    named: bool = True     # False when the name is the weekly series' own
    series: bool = False   # an instance of the weekly series (the Friday Zoom)


def event_times(props: Props, default_tz: ZoneInfo) -> tuple[datetime, datetime, bool]:
    dtstart = first(props, "DTSTART")
    if not dtstart:
        raise ValueError("VEVENT without DTSTART")
    start, all_day = parse_dt(dtstart[1], dtstart[0], default_tz)
    dtend = first(props, "DTEND")
    duration = first(props, "DURATION")
    if dtend:
        end, _ = parse_dt(dtend[1], dtend[0], default_tz)
    elif duration:
        end = start + parse_duration(duration[1])
    else:
        end = start + (timedelta(days=1) if all_day else timedelta(hours=1))
    return start, end, all_day


def text(props: Props, name: str) -> str:
    item = first(props, name)
    return ics_unescape(item[1]).strip() if item else ""


def occurrences(events: list[Props], top: dict[str, str], now: datetime,
                limit: int = LIMIT, horizon_days: int = HORIZON_DAYS) -> list[Occurrence]:
    """The upcoming instances, in order: under way or still to start, soonest first."""
    default_tz = tz_for(top.get("X-WR-TIMEZONE"), SITE_TZ)
    horizon = now + timedelta(days=horizon_days)

    # Overrides first, so the series they belong to can skip those instances.
    overrides: dict[tuple[str, datetime], Props] = {}
    masters: list[Props] = []
    for ev in events:
        uid = text(ev, "UID")
        rid = first(ev, "RECURRENCE-ID")
        if rid:
            when, _ = parse_dt(rid[1], rid[0], default_tz)
            overrides[(uid, when)] = ev
        else:
            masters.append(ev)

    found: list[Occurrence] = []
    master_kind: dict[str, str] = {}

    def add(ev: Props, start: datetime, end: datetime, all_day: bool, kind: str) -> None:
        if text(ev, "STATUS").upper() == "CANCELLED":
            return
        if end <= now or start > horizon:
            return
        found.append(Occurrence(
            uid=text(ev, "UID"), start=start, end=end, all_day=all_day, kind=kind,
            summary=text(ev, "SUMMARY") or "Cloud Security Office Hours",
            description=text(ev, "DESCRIPTION"), location=text(ev, "LOCATION"),
            url=text(ev, "URL"),
        ))

    for ev in masters:
        uid = text(ev, "UID")
        start, end, all_day = event_times(ev, default_tz)
        rrule = first(ev, "RRULE")
        if not rrule:
            add(ev, start, end, all_day, "single")
            continue
        rule = parse_rrule(rrule[1])
        exdates: set[datetime] = set()
        for params, value in ev.get("EXDATE", []):
            for one in value.split(","):
                when, _ = parse_dt(one.strip(), params, default_tz)
                exdates.add(when)
        kind = "weekly" if rule.get("FREQ", "").upper() == "WEEKLY" and rule.get("INTERVAL", "1") == "1" else "recurring"
        master_kind[uid] = kind
        length = end - start
        for inst in expand(start, rule, horizon):
            if inst in exdates or (uid, inst) in overrides:
                continue
            add(ev, inst, inst + length, all_day, kind)

    # An override is "Rescheduled" only when its time moved. One whose text was
    # edited (a guest named, say) is still that week's regular session.
    for (uid, when), ev in overrides.items():
        start, end, all_day = event_times(ev, default_tz)
        add(ev, start, end, all_day, "moved" if start != when else master_kind.get(uid, "single"))

    # The weekly series is the Friday Zoom session. Its cards leave its name
    # off, because it would repeat on nearly every card, and link to the
    # sign-up that sends the Zoom link. A card names its event only when it is
    # something else: a one-off, another series, or a week whose title was
    # edited. The series is matched by name, not UID, because editing "this and
    # following events" in Google splits it into two masters with new UIDs.
    # Two weekly series with different names can't be told apart, so then every
    # card keeps its name and none gets the Zoom link.
    weekly = {text(ev, "UID"): text(ev, "SUMMARY") or "Cloud Security Office Hours"
              for ev in masters if master_kind.get(text(ev, "UID")) == "weekly"}
    names = set(weekly.values())
    if len(names) == 1:
        series_name = names.pop()
        found = [replace(o, named=o.summary != series_name, series=o.uid in weekly) for o in found]
    elif names:
        print(f"warning: {len(names)} differently named weekly series in the feed; "
              "every card keeps its name and none links to the Zoom sign-up", file=sys.stderr)

    found.sort(key=lambda o: (o.start, o.summary))
    return found[:limit]


# --- Scrubbing and rendering -------------------------------------------------

def host_matches(url: str, hosts: tuple[str, ...]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in hosts)


def is_private_url(url: str) -> bool:
    return host_matches(url, PRIVATE_HOSTS)


def scrub_line(line: str) -> str:
    """One line of description as safe HTML: escaped, URLs linked, join links withheld."""
    line = EMAIL_RE.sub(lambda m: "" if not m.group(0).lower().endswith("@csoh.org") else m.group(0), line)
    out: list[str] = []
    pos = 0
    for m in URL_RE.finditer(line):
        url = m.group(0)
        trail = ""
        while url and url[-1] in ".,;:)!?":
            trail = url[-1] + trail
            url = url[:-1]
        out.append(html.escape(line[pos:m.start()]))
        if host_matches(url, OWN_HOSTS):
            trail = ""
        elif is_private_url(url):
            out.append(PRIVATE_LINK_TEXT)
        else:
            shown = url if len(url) <= 60 else url[:57] + "..."
            out.append(f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(shown)}</a>')
        out.append(html.escape(trail))
        pos = m.end()
    out.append(html.escape(line[pos:]))
    return re.sub(r"\s{2,}", " ", "".join(out)).strip()


def scrub_description(raw: str, max_chars: int = 1200) -> str:
    """Google exports descriptions as HTML fragments or plain text; accept both."""
    textual = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</li>", "\n", raw)
    textual = re.sub(r"<[^>]+>", "", textual)
    textual = html.unescape(textual)
    lines: list[str] = []
    total = 0
    for line in textual.splitlines():
        line = line.strip()
        if not line or PRIVATE_LINE_RE.search(line):
            continue
        rendered = scrub_line(line)
        if not rendered:
            continue
        total += len(line)
        if total > max_chars:
            lines.append("&hellip;")
            break
        lines.append(rendered)
    return "<br>\n                            ".join(lines)


def scrub_location(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    if URL_RE.search(raw) and all(is_private_url(u) for u in URL_RE.findall(raw)):
        return PRIVATE_LOCATION_TEXT
    if re.search(r"(?i)\bzoom\b", raw) and not URL_RE.search(raw):
        return html.escape(raw)
    return scrub_line(raw)


def clock(dt: datetime) -> str:
    return f"{dt.hour % 12 or 12}:{dt.minute:02d}"


def meridiem(dt: datetime) -> str:
    return "AM" if dt.hour < 12 else "PM"


def time_range(start: datetime, end: datetime, tz: ZoneInfo, label: str) -> str:
    s, e = start.astimezone(tz), end.astimezone(tz)
    if s.date() == e.date() and meridiem(s) == meridiem(e):
        return f"{clock(s)} to {clock(e)} {meridiem(e)} {label}"
    return f"{clock(s)} {meridiem(s)} to {clock(e)} {meridiem(e)} {label}"


def day_title(dt: datetime) -> str:
    # No year: the month heading above the card carries it.
    return f"{dt:%A}, {dt:%B} {dt.day}"


def slug(value: str) -> str:
    return re.sub(r"-{2,}", "-", re.sub(r"[^a-z0-9]+", "-", value.lower())).strip("-") or "event"


KIND_TAGS = {"weekly": "Weekly", "recurring": "Recurring", "moved": "Rescheduled", "single": "One-off"}


def render_card(occ: Occurrence, used_ids: set[str]) -> str:
    local = occ.start.astimezone(SITE_TZ)
    card_id = f"event-{local:%Y%m%d}-{slug(occ.summary)}"
    n = 2
    while card_id in used_ids:
        card_id = f"event-{local:%Y%m%d}-{slug(occ.summary)}-{n}"
        n += 1
    used_ids.add(card_id)

    if occ.all_day:
        stamp_attr, when = f"{local:%Y-%m-%d}", "All day"
    else:
        stamp_attr = local.isoformat()
        when = (f"{time_range(occ.start, occ.end, SITE_TZ, 'PT')} "
                f"({time_range(occ.start, occ.end, SECOND_TZ, 'ET')})")

    parts = [
        # The date is the title because it is what tells one card from the
        # next; the time sits directly under it. Still an <h3>, because main.js
        # reads every .resource-card's h3 for its icon pass and throws on a card
        # without one.
        #
        # The icon tile is written here rather than left to main.js, so it can
        # show the day of the month (main.js skips a card that already has
        # one). It works with scripts off, and aria-hidden keeps a screen
        # reader from saying the day twice, since the title already says it.
        f'                    <div class="resource-card" id="{card_id}" data-no-preview>',
        f'                        <div class="resource-card-icon resource-card-icon--date" aria-hidden="true">{local.day}</div>',
        f'                        <h3><time datetime="{stamp_attr}">{day_title(local)}</time></h3>',
        f'                        <p class="article-date">{when}</p>',
    ]
    if occ.named:
        parts.append(f"                        <p><strong>{html.escape(occ.summary)}</strong></p>")
    description = scrub_description(occ.description)
    if description:
        parts.append(f"                        <p>{description}</p>")
    location = scrub_location(occ.location)
    if location:
        parts.append(f"                        <p>Where: {location}</p>")
    if occ.url and not is_private_url(occ.url):
        parts.append(f'                        <p><a href="{html.escape(occ.url, quote=True)}" target="_blank" rel="noopener noreferrer">Event details</a></p>')
    if occ.series:
        parts.append(f'                        <a href="{ZOOM_SIGNUP_URL}" class="card-action" target="_blank" rel="noopener noreferrer">Get the Zoom link &rarr;</a>')
    tags = [KIND_TAGS[occ.kind]] + (["All day"] if occ.all_day else [])
    parts.append('                        <div class="resource-tags">')
    parts.extend(f'                            <span class="tag">{t}</span>' for t in tags)
    parts.append("                        </div>")
    parts.append("                    </div>")
    return "\n".join(parts)


def render(occs: list[Occurrence]) -> str:
    if not occs:
        return ("                <p>Nothing is on the calendar for the next six months. The Friday session "
                "still runs every week at 7am PT; see <a href=\"sessions.html\">how to join</a>.</p>")
    out: list[str] = []
    used: set[str] = set()
    current: tuple[int, int] | None = None
    for occ in occs:
        local = occ.start.astimezone(SITE_TZ)
        key = (local.year, local.month)
        if key != current:
            if current is not None:
                out.append("                </div>")
            out.append(f'                <h3 id="month-{local:%Y-%m}">{local:%B} {local.year}</h3>')
            out.append('                <div class="resource-grid">')
            current = key
        out.append(render_card(occ, used))
    out.append("                </div>")
    return "\n".join(out)


def stamp(page: str, block: str) -> str:
    try:
        head, rest = page.split(START_MARK, 1)
        _old, tail = rest.split(END_MARK, 1)
    except ValueError:
        raise SystemExit(f"{PAGE.name}: the calendar markers are missing; refusing to write") from None
    return f"{head}{START_MARK}\n{block}\n                {END_MARK}{tail}"


# --- Entry points -------------------------------------------------------------

def fetch(source: str) -> str:
    if "://" not in source:
        return Path(source).read_text(encoding="utf-8")
    req = urllib.request.Request(source, headers={"User-Agent": "csoh.org sync_calendar (+https://csoh.org/calendar.html)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"could not fetch {source}: {exc}") from None


def run(source: str, now: datetime, check: bool, page_path: Path = PAGE, limit: int = LIMIT) -> int:
    events, top = parse_calendar(fetch(source))
    occs = occurrences(events, top, now, limit=limit)
    block = render(occs)
    original = page_path.read_text(encoding="utf-8")
    updated = stamp(original, block)
    print(f"calendar: {len(events)} VEVENT(s) in the feed, {len(occs)} upcoming rendered"
          + (f", next {occs[0].start.astimezone(SITE_TZ).isoformat()}" if occs else ""))
    if updated == original:
        print(f"  {page_path.name}: already current")
        return 0
    if check:
        print(f"  {page_path.name}: STALE")
        return 1
    page_path.write_text(updated, encoding="utf-8")
    print(f"  {page_path.name}: updated")
    return 0


FIXTURE = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//self-test//EN
X-WR-TIMEZONE:America/New_York
BEGIN:VEVENT
UID:weekly@test
DTSTART;TZID=America/New_York:20261106T100000
DTEND;TZID=America/New_York:20261106T110000
RRULE:FREQ=WEEKLY;BYDAY=FR
EXDATE;TZID=America/New_York:20261127T100000
SUMMARY:Cloud Security Office Hours Friday
DESCRIPTION:Open Office Hours<br><br><a href="https://csoh.org/">https://cs
 oh.org/</a>
STATUS:CONFIRMED
END:VEVENT
BEGIN:VEVENT
UID:weekly@test
RECURRENCE-ID;TZID=America/New_York:20261113T100000
DTSTART;TZID=America/New_York:20261114T110000
DTEND;TZID=America/New_York:20261114T120000
SUMMARY:Saturday special
DESCRIPTION:Moved a day\\, same room.
END:VEVENT
BEGIN:VEVENT
UID:weekly@test
RECURRENCE-ID;TZID=America/New_York:20261120T100000
DTSTART;TZID=America/New_York:20261120T100000
DTEND;TZID=America/New_York:20261120T110000
SUMMARY:Friday with a guest
DESCRIPTION:Same slot\\, edited text.
END:VEVENT
BEGIN:VEVENT
UID:weekly@test
RECURRENCE-ID;TZID=America/New_York:20261204T100000
DTSTART;TZID=America/New_York:20261204T100000
DTEND;TZID=America/New_York:20261204T110000
SUMMARY:Cloud Security Office Hours Friday
STATUS:CANCELLED
END:VEVENT
BEGIN:VEVENT
UID:oneoff@test
DTSTART:20261120T180000Z
DTEND:20261120T190000Z
SUMMARY:Guest talk
LOCATION:https://us02web.zoom.us/j/123456789?pwd=secret
DESCRIPTION:Join: https://us02web.zoom.us/j/123456789?pwd=secret\\nMeeting ID: 123 456 789\\nPasscode: 4242\\nSlides at https://example.com/deck?a=1&b=2. Contact host@example.com or admin@csoh.org.
END:VEVENT
BEGIN:VEVENT
UID:allday@test
DTSTART;VALUE=DATE:20261210
DTEND;VALUE=DATE:20261211
SUMMARY:Community day
END:VEVENT
BEGIN:VEVENT
UID:monthly@test
DTSTART;TZID=America/New_York:20261103T120000
DTEND;TZID=America/New_York:20261103T130000
RRULE:FREQ=MONTHLY;BYDAY=1TU;COUNT=3
SUMMARY:First Tuesday
END:VEVENT
BEGIN:VEVENT
UID:past@test
DTSTART;TZID=America/New_York:20260101T100000
DTEND;TZID=America/New_York:20260101T110000
SUMMARY:Long gone
END:VEVENT
END:VCALENDAR
"""

# Probe instant for the self-test: a Saturday afternoon Pacific, the day after
# the first Friday in the fixture, so that Friday is already over.
PROBE = datetime(2026, 11, 7, 12, 0, tzinfo=SITE_TZ)

EXPECTED = [
    ("2026-11-14T08:00:00-08:00", "Saturday special", "moved"),
    # Edited in place, same time: still the weekly session, not "Rescheduled".
    ("2026-11-20T07:00:00-08:00", "Friday with a guest", "weekly"),
    ("2026-11-20T10:00:00-08:00", "Guest talk", "single"),
    # 2026-11-27 is EXDATEd and 2026-12-04 is a cancelled override.
    ("2026-12-01T09:00:00-08:00", "First Tuesday", "recurring"),
    ("2026-12-10T00:00:00-08:00", "Community day", "single"),
    ("2026-12-11T07:00:00-08:00", "Cloud Security Office Hours Friday", "weekly"),
    ("2026-12-18T07:00:00-08:00", "Cloud Security Office Hours Friday", "weekly"),
    ("2026-12-25T07:00:00-08:00", "Cloud Security Office Hours Friday", "weekly"),
    ("2027-01-01T07:00:00-08:00", "Cloud Security Office Hours Friday", "weekly"),
    ("2027-01-05T09:00:00-08:00", "First Tuesday", "recurring"),
    ("2027-01-08T07:00:00-08:00", "Cloud Security Office Hours Friday", "weekly"),
    ("2027-01-15T07:00:00-08:00", "Cloud Security Office Hours Friday", "weekly"),
]


def self_test() -> int:
    """Prove the expansion, the scrubber and the stamping, each on a planted case."""
    failed = 0

    def check(ok: bool, what: str) -> None:
        nonlocal failed
        failed += not ok
        print(f"  {'ok  ' if ok else 'FAIL'} {what}")

    events, top = parse_calendar(FIXTURE)
    occs = occurrences(events, top, PROBE)
    got = [(o.start.astimezone(SITE_TZ).isoformat(), o.summary, o.kind) for o in occs]
    check(got == EXPECTED, "recurrence set (weekly + EXDATE + moved + edited + cancelled + monthly 1TU + all-day + one-off)")
    for g, e in zip(got, EXPECTED):
        if g != e:
            print(f"       got  {g}\n       want {e}")

    # The horizon is respected and COUNT bounds the monthly series: with a wide
    # limit, no fourth "First Tuesday" appears.
    many = occurrences(events, top, PROBE, limit=100)
    tuesdays = [o for o in many if o.summary == "First Tuesday"]
    check(len(tuesdays) == 2, "COUNT=3 monthly series yields two future instances, not more")
    check(all(o.start <= PROBE + timedelta(days=HORIZON_DAYS) for o in many), "nothing rendered past the horizon")

    block = render(occs)
    check("zoom.us" not in block and "pwd=" not in block, "Zoom join URL withheld from description and location")
    check("Meeting ID" not in block and "Passcode" not in block, "dial-in lines dropped")
    check("host@example.com" not in block and "admin@csoh.org" in block, "outside email removed, csoh.org address kept")
    check('href="https://example.com/deck?a=1&amp;b=2"' in block, "ordinary URL linked, with the ampersand escaped")
    check("csoh.org" not in scrub_description("Open Office Hours<br><a href=\"https://csoh.org/\">https://csoh.org/</a>"),
          "link back to this site dropped from event text")
    check(scrub_description("See https://csoh.org/sessions.html for details") == "See for details",
          "control: a csoh.org deep link is dropped and the sentence closes up")
    check(PRIVATE_LOCATION_TEXT in block, "Zoom location replaced with the mailing-list wording")
    check("10:00 to 11:00 AM PT (1:00 to 2:00 PM ET)" in block, "Pacific first, Eastern second, across a meridiem change")
    check(">All day<" in block, "all-day event labelled")
    check(block.count('<h3 id="month-') == 3, "grouped by month (Nov, Dec, Jan)")
    check(block.count('class="resource-card"') == len(occs), "one card per occurrence")
    check('<h3><time datetime="2026-12-11T07:00:00-08:00">Friday, December 11</time></h3>' in block,
          "card titled by its date")
    check('<h3><time datetime="2026-12-10">Thursday, December 10</time></h3>' in block,
          "all-day card titled by its date")
    icons = re.findall(r'<div class="resource-card-icon resource-card-icon--date" aria-hidden="true">(\d+)</div>', block)
    check(icons == [str(o.start.astimezone(SITE_TZ).day) for o in occs],
          "every card's icon tile shows its own day of the month")
    check("Cloud Security Office Hours Friday" not in block, "weekly series name not repeated on its cards")
    check(all(f"<strong>{n}</strong>" in block for n in
              ("Saturday special", "Friday with a guest", "Guest talk", "First Tuesday", "Community day")),
          "one-offs, the other series and renamed weeks keep their names")
    zoom_link = f'<a href="{ZOOM_SIGNUP_URL}" class="card-action"'
    cards = re.findall(r'<div class="resource-card".*?\n                    </div>', block, re.S)
    linked = {re.search(r'datetime="([^"]+)"', c).group(1)[:10] for c in cards if zoom_link in c}
    check(linked == {"2026-11-14", "2026-11-20", "2026-12-11", "2026-12-18", "2026-12-25",
                     "2027-01-01", "2027-01-08", "2027-01-15"},
          "weekly cards (moved and edited weeks too) link to the Zoom sign-up; one-offs and other series don't")
    # A "this and following" edit splits the series into a second master with
    # a new UID and the same name: both halves are still the weekly Zoom.
    split = FIXTURE.replace("END:VCALENDAR", "BEGIN:VEVENT\nUID:weekly-split@test\n"
                            "DTSTART;TZID=America/New_York:20261112T100000\n"
                            "DTEND;TZID=America/New_York:20261112T110000\n"
                            "RRULE:FREQ=WEEKLY;BYDAY=TH\nSUMMARY:Cloud Security Office Hours Friday\n"
                            "END:VEVENT\nEND:VCALENDAR")
    assert split != FIXTURE, "plant did nothing"
    split_occs = occurrences(*parse_calendar(split), PROBE, limit=100)
    halves = render(split_occs)
    split_instances = sum(o.uid in ("weekly@test", "weekly-split@test") for o in split_occs)
    check("Cloud Security Office Hours Friday" not in halves and 'datetime="2026-11-12T07:00:00-08:00"' in halves
          and halves.count(zoom_link) == split_instances,
          "a split series is still one series: names left off, every instance linked")
    # Control: a second weekly series leaves no single name to drop, so every
    # card is named again and none claims to be the Zoom session.
    two = FIXTURE.replace("END:VCALENDAR", "BEGIN:VEVENT\nUID:weekly2@test\n"
                          "DTSTART;TZID=America/New_York:20261109T100000\n"
                          "DTEND;TZID=America/New_York:20261109T110000\n"
                          "RRULE:FREQ=WEEKLY;BYDAY=MO\nSUMMARY:Monday lab\nEND:VEVENT\nEND:VCALENDAR")
    assert two != FIXTURE, "plant did nothing"
    both = render(occurrences(*parse_calendar(two), PROBE))
    check("<strong>Cloud Security Office Hours Friday</strong>" in both and "<strong>Monday lab</strong>" in both,
          "control: two weekly series both keep their names")
    check(zoom_link not in both, "control: with two weekly series no card links to the Zoom sign-up")

    # Control: a planted join link in a brand-new shape is still caught.
    planted = scrub_description("Backup room: https://csoh.zoom.us/my/room?pwd=x and https://meet.google.com/abc-defg-hij")
    check("zoom.us" not in planted and "meet.google.com" not in planted, "control: planted join links on two hosts withheld")
    kept = scrub_description("Reading: https://github.com/CloudSecurityOfficeHours/csoh.org")
    check("github.com/CloudSecurityOfficeHours" in kept, "control: a non-meeting link is kept")

    # Stamping: writes once, is a no-op the second time, and --check sees a plant.
    with tempfile.TemporaryDirectory(prefix="sync_calendar-") as tmp:
        fixture_path = Path(tmp) / "feed.ics"
        fixture_path.write_text(FIXTURE, encoding="utf-8")
        page = Path(tmp) / "calendar.html"
        page.write_text(f"<main>\n                {START_MARK}\n                <p>old</p>\n                {END_MARK}\n</main>\n", encoding="utf-8")
        run(str(fixture_path), PROBE, check=False, page_path=page)
        first_pass = page.read_text(encoding="utf-8")
        check("<p>old</p>" not in first_pass and "Saturday special" in first_pass, "stamped between the markers")
        check(run(str(fixture_path), PROBE, check=True, page_path=page) == 0, "second pass is a no-op")
        page.write_text(first_pass.replace("Saturday special", "Sunday special"), encoding="utf-8")
        check(run(str(fixture_path), PROBE, check=True, page_path=page) == 1, "--check detects a planted stale card")
        check(page.read_text(encoding="utf-8") != first_pass, "--check did not write")
        try:
            stamp("<main>no markers</main>", block)
            check(False, "missing markers refused")
        except SystemExit:
            check(True, "missing markers refused")

    print("self-test:", "FAILED" if failed else "all detectors fired")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ics", default=ICS_URL, help="feed URL or a local .ics file (default: the public CSOH calendar)")
    ap.add_argument("--now", help="ISO-8601 instant to render from, for reproducing a run (default: now)")
    ap.add_argument("--limit", type=int, default=LIMIT, help=f"occurrences to render (default {LIMIT})")
    ap.add_argument("--check", action="store_true", help="report whether calendar.html is stale; exit 1 if so, write nothing")
    ap.add_argument("--self-test", action="store_true", help="plant known cases and confirm each is handled")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now(SITE_TZ)
    if now.tzinfo is None:
        now = now.replace(tzinfo=SITE_TZ)
    return run(args.ics, now, check=args.check, limit=args.limit)


if __name__ == "__main__":
    sys.exit(main())
