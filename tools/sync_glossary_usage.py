#!/usr/bin/env python3
"""
List, under each glossary entry, every page on the site that uses the term.

crosslink_pages.py links the first mention of each glossary term on every
content page. This tool reads those links back and writes the reverse view
into glossary.html: a second <dd class="term-usage"> after each definition,
holding a collapsed "Used on N pages" list grouped by section. A term no page
links to gets no list.

It reads the links rather than matching term text itself, so "uses the term"
has one definition on the site: the linker's, with its denylist, case rules
and skip zones. The lists therefore see only what the linker sees. A page the
linker skips (DELIBERATELY_UNLINKED in crosslink_pages.py, homelab/,
portfolio/) does not appear, and neither does a term mentioned only in a
heading or a code block. A hand-written link to a glossary entry counts the
same as a generated one.

Each list item is labelled with the page's <h1>, or for a session recap with
its date and the session title from its first <h2>. Leading emoji are dropped
and a spaced hyphen becomes a colon, so "❓ Frequently Asked Questions" is
listed as "Frequently Asked Questions" and "AWS Security - The Complete Guide"
as "AWS Security: The Complete Guide".

Everything inside <dd class="term-usage"> is owned by this tool: edit the
pages or the glossary, then re-run it. The definition stays the first <dd>
after its <dt>, which is all check_faq_jsonld_parity.py and
build_search_index.py read. glossary.js keeps the lists out of the page's
filter text, and crosslink_glossary.py leaves them unlinked.

Usage:
    python3 tools/sync_glossary_usage.py              # write (default)
    python3 tools/sync_glossary_usage.py --check      # report drift, exit 1
    python3 tools/sync_glossary_usage.py --self-test  # prove the machinery works

Run it after crosslink_pages.py, after adding, removing or renaming a glossary
entry, and after changing the heading of a page that links to the glossary.
--check runs in validate-html.yml.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GLOSSARY = "glossary.html"

# Directories holding pages that are never published as site content.
SKIP_DIRS = {"tools"}

# List heading for each directory, in display order. A page in a directory
# not named here is listed under OTHER_GROUP.
GROUPS = {
    "": "Guides and pages",
    "howto": "How-to guides",
    "breaches": "Breaches",
    "meetings": "Session recaps",
}
OTHER_GROUP = "Other pages"
GROUP_ORDER = [*GROUPS.values(), OTHER_GROUP]
NEWEST_FIRST = {GROUPS["meetings"]}

# A link to a glossary entry: attributes in any order, relative from any depth
# or absolute. The lookbehind keeps a data-href attribute from matching.
TERM_LINK_RE = re.compile(
    r'<a\b[^>]*?(?<![\w-])href="(?:https://csoh\.org)?/?(?:\.\./)*'
    r'glossary\.html#(term-[a-z0-9-]+)"',
    re.IGNORECASE,
)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.DOTALL)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
# A recap's session title follows the <time> in its first <h2>.
RECAP_H2_RE = re.compile(
    r'<h2\b[^>]*>\s*<time\b[^>]*\bdatetime="(\d{4}-\d{2}-\d{2})"[^>]*>.*?</time>(.*?)</h2>',
    re.DOTALL,
)
# add_meeting.py's fallback when a session had no distinct topic. It names
# nothing, so such a recap is labelled by its date alone.
GENERIC_RECAP_TITLE = "Cloud Security Office Hours Meeting"

# A glossary entry: its <dt> and the definition <dd> right after it. The
# tempered dots stop a <dt> with no <dd> from swallowing the next entry.
ENTRY_RE = re.compile(
    r'^([ \t]*)(<dt\b[^>]*\bid="(term-[a-z0-9-]+)"[^>]*>(?:(?!</dt>).)*</dt>'
    r"\s*<dd\b[^>]*>(?:(?!</dd>).)*</dd>)",
    re.DOTALL | re.MULTILINE,
)
USAGE_RE = re.compile(r'\n[ \t]*<dd class="term-usage">.*?</dd>', re.DOTALL)


def clean(fragment: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    return re.sub(r"\s+", " ", text).strip()


def tidy_label(text: str) -> str:
    # Leading emoji decorate a heading; in a list they are noise.
    text = re.sub(r"^[^\w\"'(]+", "", text)
    # A spaced hyphen standing in for a dash reads as a colon in a label.
    return re.sub(r"\s+-\s+", ": ", text).strip()


def label_for(rel: str, page: str) -> str:
    if rel.startswith("meetings/"):
        m = RECAP_H2_RE.search(page)
        if m:
            day = dt.date.fromisoformat(m.group(1))
            date = f"{day:%B} {day.day}, {day.year}"
            title = tidy_label(clean(m.group(2)).lstrip(" -:"))
            return date if title in ("", GENERIC_RECAP_TITLE) else f"{date}: {title}"
    m = H1_RE.search(page) or TITLE_RE.search(page)
    return (tidy_label(clean(m.group(1))) if m else "") or rel


def site_pages(root: Path) -> list[Path]:
    nested = (
        p for p in root.glob("*/*.html")
        if p.parent.name not in SKIP_DIRS and not p.parent.name.startswith(".")
    )
    return [p for p in sorted(root.glob("*.html")) if p.name != GLOSSARY] + sorted(nested)


def collect(root: Path) -> tuple[dict[str, set[str]], dict[str, str]]:
    """({term id: pages linking to it}, {page: list label})."""
    uses: dict[str, set[str]] = defaultdict(set)
    labels: dict[str, str] = {}
    for path in site_pages(root):
        page = path.read_text(encoding="utf-8", errors="replace")
        terms = set(TERM_LINK_RE.findall(COMMENT_RE.sub("", page)))
        if not terms:
            continue
        rel = path.relative_to(root).as_posix()
        labels[rel] = label_for(rel, page)
        for term in terms:
            uses[term].add(rel)
    return uses, labels


def render(pages: set[str], labels: dict[str, str], indent: str) -> str:
    groups: dict[str, list[str]] = defaultdict(list)
    for rel in pages:
        top = rel.split("/", 1)[0] if "/" in rel else ""
        groups[GROUPS.get(top, OTHER_GROUP)].append(rel)
    n = len(pages)
    lines = [
        f'{indent}<dd class="term-usage">',
        f"{indent}    <details>",
        f'{indent}        <summary>Used on {n} page{"" if n == 1 else "s"}</summary>',
    ]
    for group in GROUP_ORDER:
        rels = groups.get(group)
        if not rels:
            continue
        if group in NEWEST_FIRST:
            rels.sort(reverse=True)
        else:
            rels.sort(key=lambda r: (labels[r].casefold(), r))
        lines.append(f'{indent}        <p class="term-usage-group">{group} ({len(rels)})</p>')
        lines.append(f"{indent}        <ul>")
        lines += [
            f'{indent}            <li><a href="{r}">{html.escape(labels[r], quote=False)}</a></li>'
            for r in rels
        ]
        lines.append(f"{indent}        </ul>")
    lines += [f"{indent}    </details>", f"{indent}</dd>"]
    return "\n".join(lines)


def stamp(glossary: str, uses: dict[str, set[str]], labels: dict[str, str]) -> tuple[str, set[str]]:
    """(glossary with fresh lists, term ids present in the glossary)."""
    known: set[str] = set()

    def add(m: re.Match) -> str:
        indent, term = m.group(1), m.group(3)
        known.add(term)
        pages = uses.get(term)
        return m.group(0) + ("\n" + render(pages, labels, indent) if pages else "")

    return ENTRY_RE.sub(add, USAGE_RE.sub("", glossary)), known


def lists_by_term(glossary: str) -> dict[str, int]:
    """{term id: pages its list names}, 0 for a term with no list."""
    out = {}
    for m in ENTRY_RE.finditer(glossary):
        usage = USAGE_RE.match(glossary, m.end())
        out[m.group(3)] = usage.group(0).count("<li>") if usage else 0
    return out


def run(check: bool, root: Path = REPO_ROOT) -> int:
    path = root / GLOSSARY
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"✗ {GLOSSARY}: {exc}", file=sys.stderr)
        return 1
    if not ENTRY_RE.search(text):
        print(f"✗ {GLOSSARY}: no <dt id=\"term-...\"> entries found", file=sys.stderr)
        return 1

    uses, labels = collect(root)
    new, known = stamp(text, uses, labels)
    for term in sorted(set(uses) - known):
        print(
            f"  warning: {term} is not a glossary entry but is linked from "
            f"{', '.join(sorted(uses[term]))}",
            file=sys.stderr,
        )
    listed = {t: p for t, p in uses.items() if t in known}
    summary = (
        f"{len(listed)} of {len(known)} terms used, "
        f"{sum(len(p) for p in listed.values())} term-page pairs, {len(labels)} pages"
    )

    if new == text:
        print(f"✓ {GLOSSARY} usage lists are current ({summary})")
        return 0
    if check:
        before, after = lists_by_term(text), lists_by_term(new)
        stale = [t for t in after if before.get(t) != after[t]]
        detail = ", ".join(f"{t} lists {before.get(t, 0)}, expected {after[t]}" for t in stale[:8])
        more = f" and {len(stale) - 8} more" if len(stale) > 8 else ""
        print(
            f"✗ {GLOSSARY} usage lists are stale"
            + (f": {detail}{more}" if stale else " (labels or markup differ)")
            + ". Run: python3 tools/sync_glossary_usage.py",
            file=sys.stderr,
        )
        return 1
    path.write_text(new, encoding="utf-8")
    print(f"  rewrote {GLOSSARY} usage lists ({summary})")
    return 0


# Self-test fixtures. Each page exercises one rule; see the expectations below.
_GLOSSARY = """<dl class="glossary-list">
                <dt id="term-alpha">Alpha</dt>
                <dd>First term, see <a class="glossary-link" href="#term-gamma">Gamma</a>.</dd>
                <dt id="term-beta">Beta</dt>
                <dd>Used nowhere that counts.</dd>
                <dt id="term-gamma">Gamma / G</dt>
                <dd>Third term.</dd>
                <dt id="term-delta">Delta</dt>
                <dd>Fourth term.</dd>
</dl>
"""
_PAGES = {
    "guide.html": '<h1>📘 Alpha Guide - Basics</h1><p><a class="glossary-link" '
                  'href="glossary.html#term-alpha">Alpha</a></p>'
                  '<!-- <a href="glossary.html#term-beta">Beta</a> -->',
    "zeta.html": '<h1>Zeta &amp; Co</h1><a href="/glossary.html#term-alpha" class="x">Alpha</a>'
                 '<a class="glossary-link" href="glossary.html#term-delta">Delta</a>',
    "breaches/acme.html": '<h1>Acme 2024</h1><a data-x="1" href="../glossary.html#term-gamma" '
                          'class="glossary-link">G</a>',
    "meetings/2026-10-30.html": '<h1>Friday, October 30, 2026 - Meeting Recap</h1>'
                                '<h2><time datetime="2026-10-30">Friday, October 30, 2026</time>'
                                ' - Cloud Security Office Hours Meeting</h2>'
                                '<a class="glossary-link" href="../glossary.html#term-gamma">G</a>'
                                '<a class="glossary-link" href="../glossary.html#term-alpha">A</a>',
    "meetings/2026-11-06.html": '<h2><time datetime="2026-11-06">Friday, November 6, 2026</time>'
                                ' - Secrets - and Keys</h2>'
                                '<a class="glossary-link" href="../glossary.html#term-alpha">A</a>',
    "howto/h.html": '<h1>H</h1><a data-href="glossary.html#term-beta">not a link</a>'
                    '<a href="glossary.html#term-missing">dangling</a>',
    "tools/og/t.html": '<h1>Template</h1><a href="../../glossary.html#term-beta">B</a>',
    "tools/t.html": '<h1>Tool page</h1><a href="../glossary.html#term-beta">B</a>',
}


def self_test() -> int:
    failures: list[str] = []

    def expect(label: str, ok: bool) -> None:
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
        if not ok:
            failures.append(label)

    def block(text: str, term: str) -> str:
        m = next(m for m in ENTRY_RE.finditer(text) if m.group(3) == term)
        usage = USAGE_RE.match(text, m.end())
        return usage.group(0) if usage else ""

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, body in _PAGES.items():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(body, encoding="utf-8")
        g = root / GLOSSARY
        g.write_text(_GLOSSARY, encoding="utf-8")

        expect("--check fails when lists are missing", run(True, root) == 1)
        expect("--check writes nothing", g.read_text(encoding="utf-8") == _GLOSSARY)
        expect("write exits 0", run(False, root) == 0)
        once = g.read_text(encoding="utf-8")
        alpha, beta, gamma = (block(once, t) for t in ("term-alpha", "term-beta", "term-gamma"))

        expect("alpha lists its four pages", alpha.count("<li>") == 4 and "Used on 4 pages" in alpha)
        expect("links in comments, data-href, tools/ and dangling ids do not count", beta == "")
        expect("gamma lists the breach and the recap", gamma.count("<li>") == 2)
        expect("attribute order does not matter",
               '<a href="breaches/acme.html">Acme 2024</a>' in gamma)
        expect("absolute /glossary.html links count", '<a href="zeta.html">' in alpha)
        expect("leading emoji dropped, spaced hyphen becomes a colon",
               ">Alpha Guide: Basics</a>" in alpha)
        expect("entities in labels are re-escaped", ">Zeta &amp; Co</a>" in alpha)
        expect("a generic recap title is labelled by date alone", ">October 30, 2026</a>" in alpha)
        expect("a recap with a title gets date and title",
               ">November 6, 2026: Secrets: and Keys</a>" in alpha)
        expect("recaps are listed newest first",
               alpha.index("2026-11-06") < alpha.index("2026-10-30"))
        expect("groups follow GROUP_ORDER with counts",
               alpha.index("Guides and pages (2)") < alpha.index("Session recaps (2)"))
        expect("a single page reads 'Used on 1 page'",
               "<summary>Used on 1 page</summary>" in block(once, "term-delta"))
        expect("the definition is still the first <dd>",
               re.search(r'id="term-alpha">Alpha</dt>\s*<dd>First term', once) is not None)
        expect("the list sits right after the definition, at its indent",
               '</dd>\n                <dd class="term-usage">' in once)

        expect("--check passes after writing", run(True, root) == 0)
        run(False, root)
        expect("a second run changes nothing", g.read_text(encoding="utf-8") == once)

        g.write_text(once.replace(">Acme 2024</a>", ">Hand edit</a>"), encoding="utf-8")
        expect("--check fails on a hand-edited label", run(True, root) == 1)
        g.write_text(once.replace("Used on 4 pages", "Used on 9 pages"), encoding="utf-8")
        expect("--check fails on a hand-edited summary", run(True, root) == 1)
        run(False, root)
        expect("writing restores the hand edits", g.read_text(encoding="utf-8") == once)

        for rel in ("breaches/acme.html", "meetings/2026-10-30.html"):
            p = root / rel
            p.write_text(p.read_text(encoding="utf-8").replace("#term-gamma", "#term-other"),
                         encoding="utf-8")
        expect("--check fails once a term loses its pages", run(True, root) == 1)
        run(False, root)
        expect("a term with no remaining pages loses its list",
               block(g.read_text(encoding="utf-8"), "term-gamma") == "")

        g.write_text("<p>no entries</p>", encoding="utf-8")
        expect("a glossary with no entries fails", run(True, root) == 1)

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
