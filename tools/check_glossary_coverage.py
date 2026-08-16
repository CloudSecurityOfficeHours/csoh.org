#!/usr/bin/env python3
"""Assert the glossary's structural invariants, and that every entry is reachable.

`crosslink_glossary.py` and `crosslink_pages.py` both fail quietly. A `<dt>` that
yields no lookup keys is skipped with no message; an alias claimed by two entries
resolves to whichever `<dt>` sits earlier in the file; a `<dt>` whose id collides
with another's silently steals its links. None of these raise, so the glossary
can degrade for months while every run reports success.

This is the glossary-side counterpart to `check_crosslink_coverage.py`. Hard
failures are things that are always wrong:

  1. every `<dt>` carries an id
  2. no two `<dt>`s share an id
  3. no alias is claimed by two entries, under either tool's denylist
  4. every `<dt>` is followed by a `<dd>`
  5. every intra-glossary `href="#term-..."` resolves
  6. no entry links to itself inside its own definition

Unreachable entries are handled the way the page list is: an entry that yields
no keys can never be linked to by either tool, which is a legitimate choice for a
headword too generic to auto-link - but it should be a recorded decision rather
than a surprise. Known ones are listed in UNREACHABLE below with a reason; a new
one fails until it is either fixed or added.

    python3 tools/check_glossary_coverage.py

Exits non-zero and names what broke.
"""

from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from glossary_terms import BASE_DENYLIST, PAGE_DENYLIST, derive_keys  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
GLOSSARY = REPO / "glossary.html"

# Entries that intentionally yield no lookup keys, and so are reachable only by
# browsing or searching the glossary - never by an auto-generated link.
#
# All four are single-word headwords whose key is in BASE_DENYLIST. For three of
# them that is the right call: "Image", "Registry" and "Principal" are ordinary
# English words that would auto-link constantly in senses unrelated to the entry.
#
# "FIRST" is a different case and worth understanding before copying the
# pattern. It is the Forum of Incident Response and Security Teams, and as an
# all-caps key crosslink_pages.py would match it case-sensitively, hitting the 8
# real "FIRST" mentions and none of the ~980 ordinary "first"s.
# crosslink_glossary.py has no such rule - it matches every key with
# re.IGNORECASE - so the word has to be denied globally to stop it linking
# "first" throughout the glossary. The denylist entry is therefore working
# around a gap in one tool at the other's expense. Teaching
# crosslink_glossary.py the same acronym rule would let "first" leave the
# denylist and make this entry linkable again.
UNREACHABLE = {
    "term-image": "'Image' is an ordinary English word; denylisted",
    "term-registry": "'Registry' is an ordinary English word; denylisted",
    "term-principal": "'Principal' is an ordinary English word; denylisted",
    "term-first": "'FIRST' collides with the word 'first'; see note above",
}

DT_RE = re.compile(r"<dt(\s[^>]*)?>(.*?)</dt>", re.DOTALL)
ID_RE = re.compile(r'\bid\s*=\s*["\']([^"\']+)["\']')


def main() -> int:
    html = GLOSSARY.read_text(encoding="utf-8")
    problems: list[str] = []

    entries = []
    for m in DT_RE.finditer(html):
        attrs = m.group(1) or ""
        inner = m.group(2)
        id_m = ID_RE.search(attrs)
        entries.append((id_m.group(1) if id_m else None, inner))

    if not entries:
        print("No <dt> entries found in glossary.html.", file=sys.stderr)
        return 1

    # 1 + 2 - ids present and unique.
    missing_id = [re.sub(r"<[^>]+>", "", i).strip() for s, i in entries if s is None]
    for headword in missing_id:
        problems.append(f"<dt> without an id: {headword[:60]!r}")

    ids = [s for s, _ in entries if s]
    for slug, count in collections.Counter(ids).items():
        if count > 1:
            problems.append(f"duplicate <dt> id: {slug} appears {count} times")

    # 3 - one alias, one entry. Checked under both denylists, since a collision
    # under either is a collision for the tool that uses it.
    for label, denylist in (("glossary", BASE_DENYLIST), ("pages", PAGE_DENYLIST)):
        claims: dict[str, list[str]] = collections.defaultdict(list)
        for slug, inner in entries:
            for key in derive_keys(inner, denylist):
                claims[key.lower()].append(slug or "?")
        for key, owners in claims.items():
            if len(owners) > 1:
                problems.append(
                    f"alias {key!r} claimed by {len(owners)} entries "
                    f"({label} denylist): {owners}"
                )

    # 4 - every <dt> is followed by a <dd>.
    seq = [(m.group(1), m.start()) for m in re.finditer(r"<(dt|dd)\b", html)]
    for i, (tag, pos) in enumerate(seq):
        if tag != "dt":
            continue
        if i + 1 >= len(seq) or seq[i + 1][0] != "dd":
            line = html.count("\n", 0, pos) + 1
            problems.append(f"<dt> at line {line} is not followed by a <dd>")

    # 5 - intra-glossary anchors resolve.
    present = set(re.findall(r'id="([^"]+)"', html))
    for target in sorted(set(re.findall(r'href="#(term-[a-z0-9-]+)"', html))):
        if target not in present:
            problems.append(f"intra-glossary link to missing anchor: #{target}")

    # 6 - no entry links to itself in its own <dd>.
    current: str | None = None
    for m in re.finditer(r"<(dt|dd)(\s[^>]*)?>(.*?)</\1>", html, re.DOTALL):
        tag, attrs, inner = m.group(1), m.group(2) or "", m.group(3)
        if tag == "dt":
            id_m = ID_RE.search(attrs)
            current = id_m.group(1) if id_m else None
            continue
        for link in re.finditer(r'href="#(term-[a-z0-9-]+)"', inner):
            if link.group(1) == current:
                problems.append(f"{current} links to itself in its own definition")

    # Reachability - a decision, not a surprise.
    unreachable = {
        slug for slug, inner in entries if slug and not derive_keys(inner, BASE_DENYLIST)
    }
    for slug in sorted(unreachable - set(UNREACHABLE)):
        problems.append(
            f"{slug} yields no lookup keys, so nothing can ever link to it. "
            f"Rename the headword, drop the denylist entry, or add it to "
            f"UNREACHABLE in {Path(__file__).name} with a reason."
        )
    for slug in sorted(set(UNREACHABLE) - unreachable):
        problems.append(
            f"{slug} is listed in UNREACHABLE but now yields keys - remove the entry"
        )

    if problems:
        print(f"{len(problems)} glossary problem(s):", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    print(
        f"OK: {len(entries)} glossary entries - ids unique, aliases unambiguous, "
        f"anchors resolve, {len(UNREACHABLE)} intentionally unlinkable."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
