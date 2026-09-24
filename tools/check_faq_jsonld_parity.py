#!/usr/bin/env python3
"""Keep FAQ and glossary JSON-LD identical to the text each page shows.

WHY THIS EXISTS
---------------
The site repeats visible prose inside structured data. Most guide pages carry
an FAQPage block whose answers restate the visible FAQ, and glossary.html
repeats every definition as a DefinedTerm description. Kept by hand, the two
copies drift: a correction lands in the visible prose and never reaches its
JSON-LD copy.

The JSON-LD copy matters more than it looks: it is the text a search engine
lifts into a snippet, so the stale version is the one a reader is most likely
to see without ever opening the page.

THE CONVENTION: THE PAGE IS THE SOURCE, THE JSON-LD IS GENERATED
-----------------------------------------------------------------
Rather than verify JSON-LD-only claims, each copy is regenerated from the
visible text, word for word:

- FAQPage mainEntity is the visible FAQ, in page order. A question's name is
  its <summary> or <h3> text and its answer is everything up to the next
  question. Questions that exist only in JSON-LD are dropped.
- A DefinedTerm description is its visible <dd>, minus a trailing
  "Deep dive:" link, which is navigation to a guide page rather than part of
  the definition.

Text is taken the way a reader sees it: tags removed (inline ones such as <a>
and <strong> without leaving a gap, so a link before a full stop does not
become "link ."), entities decoded, whitespace collapsed.

So edit the visible FAQ or <dd>, then run --fix. Never edit the JSON-LD copy by
hand: --check, which validate-html.yml runs, fails on any difference.

WHERE THE VISIBLE FAQ IS
------------------------
The first of: <section id="faq">; the range under an <h2> titled FAQ,
Frequently asked..., Quick answers or Common questions, up to the next <h2>,
</section>, </main> or </article>; or, on a page whose <h1> carries such a
title (faq.html), all of <main>. Inside it, <details>/<summary> pairs if there
are any, otherwise each <h3> and the content that follows it.

--fix deletes structured data only when the case is unambiguous. It removes a
FAQPage block when the page has no FAQ section AND none of the block's
questions appear anywhere on the page, which Google's FAQ guidelines do not
allow. An FAQ section with no readable question, questions visible outside any
FAQ section, or a FAQPage sharing its block with other entities is reported
and left alone. Each of those is the extractor failing, and a fix that
"handled" it would delete real content.

THE SELF-TEST IS NOT OPTIONAL
-----------------------------
Every run starts with self_test(), which plants pages and refuses to report
anything unless each detector fires and each rewrite produces the expected
page, leaves the rest of the JSON-LD alone, and changes nothing on a second
run. Two plants matter most. A question that exists only inside <head> or the
JSON-LD itself must not count as visible: if the extractor ever stopped
stripping those, every block would "match" its own copy and the removal rule
would never fire. And an FAQ the extractor cannot read must change nothing.
Adding a detector or a rewrite means adding its planted case.

    python3 tools/check_faq_jsonld_parity.py              # report, naming the claims --fix would drop
    python3 tools/check_faq_jsonld_parity.py --fix        # regenerate the JSON-LD copies
    python3 tools/check_faq_jsonld_parity.py --check      # exit 1 on any difference (CI)
    python3 tools/check_faq_jsonld_parity.py --json out.json
    python3 tools/check_faq_jsonld_parity.py --self-test  # self-test only
"""

from __future__ import annotations

import argparse
import difflib
import html as html_lib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# Pages whose JSON-LD is not a mirror of authored prose: chat-resources.html is
# an archive of shared links, news.html is regenerated from feeds, and tools/
# holds render templates that are never served.
EXCLUDE = {"chat-resources.html", "news.html"}
EXCLUDE_PREFIXES = ("tools/",)

LDJSON_RE = re.compile(r"(<script[^>]+application/ld\+json[^>]*>)(.*?)</script>", re.S | re.I)
NON_VISIBLE_RE = re.compile(
    r"<head\b.*?</head>|<script\b.*?</script>|<style\b.*?</style>|<noscript\b.*?</noscript>|<!--.*?-->",
    re.S | re.I,
)
TAG_RE = re.compile(r"<[^>]+>")
TAG_NAME_RE = re.compile(r"<\s*/?\s*([a-zA-Z][a-zA-Z0-9-]*)")
# Phrasing elements render inline, so removing one must not add a gap:
# '<a href="#cui">CUI</a>.' reads "CUI.", not "CUI .". Every other tag
# (p, li, br, div, td...) separates the words on either side of it.
INLINE_TAGS = frozenset(
    "a abbr b bdi bdo cite code data dfn em i kbd mark q s samp small span strong sub sup time u var wbr".split()
)
TOKEN_RE = re.compile(r"[a-z0-9]+")
ANSWER_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
PAGE_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n\s*\n")
DT_DD_RE = re.compile(r'<dt\b[^>]*\bid="([^"]+)"[^>]*>.*?</dt>\s*<dd\b[^>]*>(.*?)</dd>', re.S)

# A trailing "Deep dive: <link>." in a glossary <dd> is navigation to the guide
# page, not part of the definition, and DefinedTerm descriptions leave it out on
# purpose. Recorded here so it is a decision you can
# disagree with rather than a silent skip.
DD_NAVIGATION_SUFFIX_RE = re.compile(r"\s*<em>\s*Deep dive:\s*</em>.*$", re.S)

FAQ_TITLE_RE = re.compile(r"\bFAQs?\b|\bFrequently asked\b|\bQuick answers\b|\bCommon questions\b", re.I)
FAQ_SECTION_RE = re.compile(r'<section\b[^>]*\bid="faq"[^>]*>(.*?)</section>', re.S | re.I)
H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.S | re.I)
H2_RE = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.S | re.I)
MAIN_RE = re.compile(r"<main\b[^>]*>(.*?)</main>", re.S | re.I)
H2_RANGE_END_RE = re.compile(r"<h2\b|</section>|</main>|</article>", re.I)
DETAILS_RE = re.compile(r"<details\b[^>]*>\s*<summary\b[^>]*>(.*?)</summary>(.*?)</details>", re.S | re.I)
H3_PAIR_RE = re.compile(r"<h3\b[^>]*>(.*?)</h3>(.*?)(?=<h3\b|\Z)", re.S | re.I)
MAIN_ENTITY_KEY_RE = re.compile(r'"mainEntity"\s*:\s*(?=\[)')
DESCRIPTION_KEY_RE = re.compile(r'"description"\s*:\s*')
DECODER = json.JSONDecoder()

# Findings --fix resolves. Everything else needs a person.
FIXABLE = frozenset({"faq-out-of-sync", "faq-no-visible-faq", "term-out-of-sync"})


@dataclass
class Finding:
    page: str
    kind: str   # a LABELS key
    key: str    # a one-line summary, or the term id
    line: int
    detail: dict = field(default_factory=dict)


def html_pages() -> list[str]:
    """Tracked pages, from git rather than a filesystem glob.

    rglob would descend into the git worktrees under .claude/, which hold full,
    stale copies of the site and would double every finding.
    """
    out = subprocess.run(
        ["git", "ls-files", "*.html"], cwd=REPO, capture_output=True, text=True, check=True
    ).stdout.split()
    return sorted(p for p in out if p not in EXCLUDE and not p.startswith(EXCLUDE_PREFIXES))


def read_page(rel: str) -> str:
    # Bytes, not read_text(): text mode turns \r\n into \n, so writing a fix
    # back would silently rewrite every line ending of a CRLF file.
    return (REPO / rel).read_bytes().decode("utf-8")


def _tag_gap(m: re.Match) -> str:
    name = TAG_NAME_RE.match(m.group(0))
    return "" if name and name.group(1).lower() in INLINE_TAGS else " "


def rendered(fragment: str) -> str:
    """An HTML fragment's text as a reader sees it, on one line."""
    return re.sub(r"\s+", " ", html_lib.unescape(TAG_RE.sub(_tag_gap, fragment))).strip()


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(rendered(text).lower())


def visible_text(raw: str) -> str:
    """What a reader sees: no <head>, scripts (JSON-LD included), styles, or comments.

    Line breaks are kept, because sentence splitting uses blank lines.
    """
    return html_lib.unescape(TAG_RE.sub(_tag_gap, NON_VISIBLE_RE.sub(" ", raw)))


def answer_sentences(text: str) -> list[str]:
    return [s for s in ANSWER_SENTENCE_RE.split(rendered(text)) if s.strip()]


def line_of(raw: str, needle: str) -> int:
    for probe in (json.dumps(needle, ensure_ascii=False)[1:-1], needle, needle[:60]):
        i = raw.find(probe) if probe else -1
        if i >= 0:
            return raw.count("\n", 0, i) + 1
    return 0


def line_at(raw: str, offset: int) -> int:
    return raw.count("\n", 0, offset) + 1


def clip(text: str, n: int = 220) -> str:
    return text if len(text) <= n else text[: n - 3] + "..."


class VisibleIndex:
    """The page's visible text as one token stream plus sentence-level lookups."""

    def __init__(self, text: str):
        self.stream = " " + " ".join(TOKEN_RE.findall(text.lower())) + " "
        self.sentences = []
        for s in PAGE_SENTENCE_RE.split(text):
            s = re.sub(r"\s+", " ", s).strip()
            if len(TOKEN_RE.findall(s.lower())) >= 3:
                self.sentences.append(s)
        self.sentence_tokens = [TOKEN_RE.findall(s.lower()) for s in self.sentences]
        self.by_word: dict[str, set[int]] = defaultdict(set)
        for i, toks in enumerate(self.sentence_tokens):
            for w in set(toks):
                self.by_word[w].add(i)

    def contains(self, toks: list[str]) -> bool:
        return bool(toks) and (" " + " ".join(toks) + " ") in self.stream

    def closest(self, toks: list[str]) -> tuple[float, str]:
        overlap: Counter = Counter()
        for w in set(toks):
            for i in self.by_word.get(w, ()):
                overlap[i] += 1
        best = (0.0, "")
        for i, _ in overlap.most_common(8):
            r = difflib.SequenceMatcher(None, toks, self.sentence_tokens[i], autojunk=False).ratio()
            if r > best[0]:
                best = (r, self.sentences[i])
        return best


def claims_not_on_page(text: str, index: VisibleIndex) -> list[dict]:
    """Sentences of a JSON-LD answer that appear nowhere on the page, with the nearest visible one."""
    out = []
    for sentence in answer_sentences(text):
        toks = tokens(sentence)
        if toks and not index.contains(toks):
            ratio, near = index.closest(toks)
            out.append({"sentence": sentence, "ratio": round(ratio, 2), "closest": near})
    return out


def _types(obj: dict) -> set:
    t = obj.get("@type")
    return set(t) if isinstance(t, list) else {t}


def _walk(obj):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _script_safe(json_source: str) -> str:
    # The JSON sits inside a <script> element, where "</" can end it early and
    # "<!--" can change how the rest is parsed. Both escapes are valid JSON.
    return json_source.replace("</", "<\\/").replace("<!--", "\\u003c!--")


def json_text(value, text: str, pos: int) -> str:
    """`value` as JSON, written to sit at `pos` in `text`.

    Two-space steps under the indentation of that line, which is how every
    FAQPage array on the site was written, so an unchanged array round-trips
    byte for byte. Line endings follow the block's own.
    """
    line_start = text.rfind("\n", 0, pos) + 1
    base = re.match(r"[ \t]*", text[line_start:]).group(0)
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = json.dumps(value, indent=2, ensure_ascii=False).split("\n")
    return _script_safe(lines[0] + "".join(newline + base + line for line in lines[1:]))


def main_entity(pairs: list[tuple[str, str]]) -> list[dict]:
    return [{"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in pairs]


def faq_container(visible_html: str) -> tuple[str, str] | None:
    """(how it was found, the HTML holding the FAQ), or None when the page has no FAQ."""
    m = FAQ_SECTION_RE.search(visible_html)
    if m:
        return 'section id="faq"', m.group(1)
    for h in H2_RE.finditer(visible_html):
        if FAQ_TITLE_RE.search(rendered(h.group(1))):
            rest = visible_html[h.end():]
            stop = H2_RANGE_END_RE.search(rest)
            return "FAQ-titled h2", rest[: stop.start() if stop else len(rest)]
    h1 = H1_RE.search(visible_html)
    if h1 and FAQ_TITLE_RE.search(rendered(h1.group(1))):
        main = MAIN_RE.search(visible_html)
        return "FAQ page", main.group(1) if main else visible_html
    return None


def visible_faq(raw: str) -> tuple[str | None, list[tuple[str, str]]]:
    visible_html = NON_VISIBLE_RE.sub(" ", raw)
    found = faq_container(visible_html)
    if found is None:
        return None, []
    kind, region = found
    pattern = DETAILS_RE if re.search(r"<details\b", region, re.I) else H3_PAIR_RE
    return kind, [(rendered(q), rendered(a)) for q, a in pattern.findall(region)]


def _faq_nodes(data) -> list[tuple[str, dict]]:
    """FAQPage nodes in one parsed block, labelled by where they sit."""
    if isinstance(data, dict) and "FAQPage" in _types(data):
        return [("top", data)]
    if isinstance(data, dict) and isinstance(data.get("@graph"), list):
        return [("@graph", n) for n in data["@graph"] if isinstance(n, dict) and "FAQPage" in _types(n)]
    if isinstance(data, list):
        return [("list", n) for n in data if isinstance(n, dict) and "FAQPage" in _types(n)]
    return []


def _qa(question: dict) -> tuple[str, str]:
    answer = question.get("acceptedAnswer")
    if isinstance(answer, list):
        answer = answer[0] if answer else {}
    text = answer.get("text", "") if isinstance(answer, dict) else ""
    return str(question.get("name", "")), str(text)


def _whole_lines(raw: str, start: int, end: int) -> tuple[int, int]:
    """Widen [start, end) to whole lines nothing else shares, so a removal leaves no blank line."""
    line_start = raw.rfind("\n", 0, start) + 1
    if not raw[line_start:start].strip():
        start = line_start
    line_end = raw.find("\n", end)
    if line_end != -1 and not raw[end:line_end].strip():
        end = line_end + 1
    return start, end


def _sync_faq(page: str, raw: str, blocks: list, stats: Counter, findings: list, edits: list) -> None:
    nodes = [(m, where, node) for m, data in blocks if data is not None for where, node in _faq_nodes(data)]
    if not nodes:
        return
    stats["faq_pages"] += 1
    line = line_at(raw, nodes[0][0].start())
    if len(nodes) > 1:
        findings.append(Finding(page, "faq-unreadable", f"{len(nodes)} FAQPage nodes on one page; expected one", line))
        return
    m, where, node = nodes[0]
    entities = node.get("mainEntity")
    entities = [entities] if isinstance(entities, dict) else entities if isinstance(entities, list) else []
    current = [_qa(q) for q in entities if isinstance(q, dict)]
    stats["questions"] += len(current)
    container, pairs = visible_faq(raw)
    stats["visible_questions"] += len(pairs)

    if container is None:
        shown = [q for q, _ in current if VisibleIndex(visible_text(raw)).contains(tokens(q))]
        names = [q for q, _ in current]
        if shown:
            findings.append(Finding(page, "faq-unreadable",
                                    "questions appear on the page, but in no FAQ section this tool recognises",
                                    line, {"visible_questions": shown}))
        elif where != "top" or _types(node) != {"FAQPage"}:
            findings.append(Finding(page, "faq-unreadable",
                                    "no visible FAQ, but the FAQPage shares its JSON-LD with other entities, "
                                    "so it is not removed automatically", line, {"questions": names}))
        else:
            findings.append(Finding(page, "faq-no-visible-faq", f"{len(current)} questions, no visible FAQ",
                                    line, {"questions": names}))
            edits.append((*_whole_lines(raw, m.start(), m.end()), ""))
        return

    if not pairs:
        findings.append(Finding(page, "faq-unreadable",
                                f"found the FAQ ({container}) but could not read a question in it", line))
        return
    blank = [q or "(blank question)" for q, a in pairs if not q or not a]
    if blank:
        findings.append(Finding(page, "faq-unreadable", "visible FAQ entries with a blank question or answer",
                                line, {"entries": blank}))
        return
    expected = main_entity(pairs)
    if entities == expected:
        stats["faq_in_sync"] += 1
        return

    body, body_start = m.group(2), m.start(2)
    keys = list(MAIN_ENTITY_KEY_RE.finditer(body))
    try:
        if len(keys) != 1:
            raise ValueError("mainEntity is not unique")
        _, end = DECODER.raw_decode(body, keys[0].end())
    except ValueError:
        findings.append(Finding(page, "faq-unreadable",
                                "differs from the visible FAQ, but its mainEntity array could not be located",
                                line))
        return
    start = keys[0].end()
    edits.append((body_start + start, body_start + end, json_text(expected, body, start)))

    index = VisibleIndex(visible_text(raw))
    shown_names = [q for q, _ in pairs]
    now, then = dict(pairs), dict(current)
    dropped = [{"question": q, "claims_not_on_page": claims_not_on_page(a, index)} for q, a in current if q not in now]
    added = [q for q in shown_names if q not in then]
    changed = [{"question": q, "claims_not_on_page": claims_not_on_page(then[q], index)}
               for q in shown_names if q in then and then[q] != now[q]]
    reordered = not dropped and not added and [q for q, _ in current] != shown_names
    summary = ", ".join(part for part in (
        f"{len(changed)} answer(s) differ" if changed else "",
        f"{len(added)} visible question(s) missing" if added else "",
        f"{len(dropped)} JSON-LD-only question(s)" if dropped else "",
        "questions out of order" if reordered else "",
    ) if part) or "same text, different JSON shape"
    findings.append(Finding(page, "faq-out-of-sync", summary, line,
                            {"dropped": dropped, "added": added, "changed": changed, "reordered": reordered}))


def _description_span(body: str, term_id: str, old: str) -> tuple[int, int] | None:
    """Where this term's description literal sits in the block, confirmed by decoding it."""
    at = re.search(r'"@id"\s*:\s*' + re.escape(json.dumps(term_id, ensure_ascii=False)), body)
    key = DESCRIPTION_KEY_RE.search(body, at.end()) if at else None
    if not key:
        return None
    try:
        value, end = DECODER.raw_decode(body, key.end())
    except ValueError:
        return None
    return (key.end(), end) if value == old else None


def _sync_terms(page: str, raw: str, blocks: list, stats: Counter, findings: list, edits: list) -> None:
    dd_by_id = None
    for m, data in blocks:
        if data is None:
            continue
        terms = [t for t in _walk(data) if "DefinedTerm" in _types(t) and isinstance(t.get("description"), str)]
        if not terms:
            continue
        if dd_by_id is None:
            dd_by_id = dict(DT_DD_RE.findall(raw))
            stats["term_pages"] += 1
        body, body_start = m.group(2), m.start(2)
        for t in terms:
            stats["terms"] += 1
            term_id = str(t.get("@id", ""))
            name = str(t.get("name", ""))
            frag = term_id.rsplit("#", 1)[-1] if "#" in term_id else ""
            line = line_of(raw, term_id) if term_id else line_of(raw, name)
            if frag not in dd_by_id:
                findings.append(Finding(page, "term-missing-dt", term_id or name, line, {"jsonld": t["description"]}))
                continue
            expected = rendered(DD_NAVIGATION_SUFFIX_RE.sub("", dd_by_id[frag]))
            if t["description"] == expected:
                stats["terms_in_sync"] += 1
                continue
            span = _description_span(body, term_id, t["description"]) if expected else None
            if span is None:
                findings.append(Finding(page, "term-unreadable", frag, line,
                                        {"jsonld": t["description"], "page": expected or "(empty <dd>)"}))
                continue
            edits.append((body_start + span[0], body_start + span[1],
                          _script_safe(json.dumps(expected, ensure_ascii=False))))
            findings.append(Finding(page, "term-out-of-sync", frag, line, {"jsonld": t["description"], "page": expected}))


def sync_page(page: str, raw: str) -> tuple[list[Finding], Counter, str]:
    """A page's findings, plus the text --fix would write (identical to raw when nothing needs fixing)."""
    findings: list[Finding] = []
    stats: Counter = Counter()
    blocks = []
    for m in LDJSON_RE.finditer(raw):
        try:
            blocks.append((m, json.loads(m.group(2))))
        except json.JSONDecodeError as e:
            blocks.append((m, None))
            findings.append(Finding(page, "jsonld-parse", f"JSON-LD block does not parse: {e}", line_at(raw, m.start())))
    edits: list[tuple[int, int, str]] = []
    _sync_faq(page, raw, blocks, stats, findings, edits)
    _sync_terms(page, raw, blocks, stats, findings, edits)
    edits.sort()
    if any(a[1] > b[0] for a, b in zip(edits, edits[1:])):
        findings.append(Finding(page, "faq-unreadable", "rewrites on this page would overlap, so none were made", 0))
        return findings, stats, raw
    fixed = raw
    for start, end, text in reversed(edits):
        fixed = fixed[:start] + text + fixed[end:]
    return findings, stats, fixed


def self_test() -> list[str]:
    """Plant pages, and prove each detector fires and each rewrite writes exactly what it should."""
    bad: list[str] = []

    def page(blocks: list, body: str, head: str = "", ld_in_body: bool = False) -> str:
        scripts = "".join('<script type="application/ld+json">\n' + json.dumps(b, indent=2) + "\n</script>\n"
                          for b in blocks)
        return ("<!DOCTYPE html>\n<html>\n<head>\n<title>planted</title>\n" + head + ("" if ld_in_body else scripts)
                + "</head>\n<body>\n<main>\n" + (scripts if ld_in_body else "") + body + "\n</main>\n</body>\n</html>\n")

    def faq(*pairs) -> dict:
        return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": main_entity(list(pairs))}

    def run(raw: str) -> tuple[list[Finding], Counter, str]:
        return sync_page("planted.html", raw)

    def kinds(raw: str) -> list[str]:
        return sorted(f.kind for f in run(raw)[0])

    def faq_in(raw: str):
        try:
            for m in LDJSON_RE.finditer(raw):
                for _, node in _faq_nodes(json.loads(m.group(2))):
                    return [_qa(q) for q in node["mainEntity"]]
        except ValueError:
            return "unparseable"
        return None

    def converges(raw: str, label: str) -> str:
        fixed = run(raw)[2]
        again = run(fixed)
        if again[2] != fixed or any(f.kind in FIXABLE for f in again[0]):
            bad.append(f"--fix did not converge on the planted {label} page")
        return fixed

    q1, a1 = "What does Level 2 require?", "Level 2 covers CUI. Most contracts still use self-assessment."
    q2, a2 = "Is it free?", "Yes, it's \"free\" for M&A teams."
    h3_faq = ('<section id="faq"><h2>Quick answers</h2>'
              '<h3>What does Level 2 require?</h3><p>Level 2 covers <a href="#cui">CUI</a>.\n  '
              'Most contracts still use self-assessment.</p>'
              '<h3>Is it free?</h3><p>Yes, it&#x27;s &quot;free&quot; for M&amp;A teams.</p></section>')

    synced = page([faq((q1, a1), (q2, a2))], h3_faq)
    if run(synced)[0] or run(synced)[2] != synced:
        bad.append("a FAQPage identical to the visible FAQ was reported or rewritten "
                   "(tags must not leave a gap before punctuation, and entities must decode)")

    stale = page([faq((q1, "Level 2 covers CUI. It requires a C3PAO assessment."), ("Is it cheap?", "Very."))], h3_faq)
    found = [f for f in run(stale)[0] if f.kind == "faq-out-of-sync"]
    if not found:
        bad.append("a FAQPage with a stale answer and a JSON-LD-only question was not reported")
    else:
        d = found[0].detail
        if [c["sentence"] for item in d["changed"] for c in item["claims_not_on_page"]] != ["It requires a C3PAO assessment."]:
            bad.append("the stale answer's unsupported sentence was not the one named")
        if [item["question"] for item in d["dropped"]] != ["Is it cheap?"] or d["added"] != [q2]:
            bad.append("the dropped and added questions were not reported correctly")
    if faq_in(converges(stale, "stale-answer")) != [(q1, a1), (q2, a2)]:
        bad.append("--fix did not rebuild the FAQPage from the visible questions and answers, in page order")
    crlf = converges(stale.replace("\n", "\r\n"), "CRLF")
    if re.search(r"(?<!\r)\n", crlf) or faq_in(crlf) != [(q1, a1), (q2, a2)]:
        bad.append("--fix on a CRLF page wrote a bare newline or the wrong FAQ")

    details = ('<section id="faq"><details><summary><strong>Is CWPP the same as <a class="glossary-link" '
               'href="glossary.html#term-edr">EDR</a>?</strong></summary><p>No. Never paste &lt;/script&gt; here.</p>'
               '</details></section>')
    fixed = converges(page([faq(("Old question?", "Old answer."))], details), "details")
    if faq_in(fixed) != [("Is CWPP the same as EDR?", "No. Never paste </script> here.")]:
        bad.append("a <details>/<summary> FAQ was not mirrored word for word, or its </script> broke the block")
    if "<\\/script>" not in fixed:
        bad.append("an answer containing </script> was written into the JSON-LD unescaped")

    ranged = ('<h2>Frequently asked questions</h2><details><summary>Q one?</summary><p>A one.</p></details>'
              '<h2>Pricing</h2><details><summary>Not part of the FAQ</summary><p>Nope.</p></details>')
    if faq_in(converges(page([faq(("Q one?", "Stale."))], ranged), "h2-range")) != [("Q one?", "A one.")]:
        bad.append("the FAQ under an FAQ-titled <h2> was not bounded by the next <h2>")

    whole = ('<h1>Frequently Asked Questions</h1><h2>Sessions</h2><details><summary>When?</summary>'
             '<p>Fridays.</p></details><h2>Site</h2><details><summary>Who runs it?</summary><p>Volunteers.</p></details>')
    if faq_in(converges(page([faq(("When?", "Fridays."))], whole), "FAQ-page")) != [("When?", "Fridays."), ("Who runs it?", "Volunteers.")]:
        bad.append("an FAQ page's questions under several topic <h2>s were not all mirrored")

    org = {"@context": "https://schema.org", "@type": "Organization", "name": "Planted"}
    head = '<meta name="description" content="What does Level 2 require?">\n'
    nothing = "<p>Nothing like that here.</p>"
    for label, raw in (("<head>", page([faq((q1, a1)), org], nothing, head=head)),
                       ("<body>", page([faq((q1, a1)), org], nothing, ld_in_body=True))):
        if kinds(raw) != ["faq-no-visible-faq"]:
            bad.append(f"a FAQPage with no visible FAQ (JSON-LD in {label}) was not flagged for removal; "
                       "is text inside <head> or <script> being counted as visible?")
            continue
        remaining = [json.loads(m.group(2)) for m in LDJSON_RE.finditer(converges(raw, "no-FAQ"))]
        if remaining != [org]:
            bad.append("removing a FAQPage block did not leave exactly the other JSON-LD blocks behind")

    ambiguous = {
        "an FAQ section with no readable question":
            page([faq((q1, a1))], '<section id="faq"><h2>FAQ</h2><p>Coming soon.</p></section>'),
        "questions visible outside any FAQ section":
            page([faq((q1, a1))], "<h2>Details</h2><h3>What does Level 2 require?</h3><p>Level 2 covers CUI.</p>"),
        "a FAQPage inside @graph on a page with no FAQ":
            page([{"@context": "https://schema.org", "@graph": [org, faq((q1, a1))]}], nothing),
    }
    for label, raw in ambiguous.items():
        findings, _, fixed = run(raw)
        if "faq-unreadable" not in [f.kind for f in findings] or fixed != raw:
            bad.append(f"{label} was not reported as unreadable, or --fix changed the page")

    def around_array(text: str) -> tuple[str, str]:
        key = MAIN_ENTITY_KEY_RE.search(text)
        _, end = DECODER.raw_decode(text, key.end())
        return text[: key.end()], text[end:]

    graphed = page([{"@context": "https://schema.org", "@graph": [
        org, {"@type": "FAQPage", "mainEntity": main_entity([(q1, "Stale."), (q2, a2)])}]}], h3_faq)
    fixed = converges(graphed, "@graph")
    if faq_in(fixed) != [(q1, a1), (q2, a2)] or around_array(fixed) != around_array(graphed):
        bad.append("a FAQPage inside @graph was not rewritten in place, or text outside its mainEntity array changed")

    def term_set(*terms) -> dict:
        return {"@context": "https://schema.org", "@type": "DefinedTermSet", "hasDefinedTerm": [
            {"@type": "DefinedTerm", "@id": f"https://csoh.org/glossary.html#{i}", "name": i, "description": d}
            for i, d in terms]}

    dl = ('<dl><dt id="term-x">X</dt><dd>A <a href="#term-y">vendor</a> coinage. <em>Deep dive:</em> '
          '<a href="x.html">X</a>.</dd><dt id="term-y">Y</dt><dd>Why not.</dd></dl>')
    if run(page([term_set(("term-x", "A vendor coinage."), ("term-y", "Why not."))], dl))[0]:
        bad.append("DefinedTerms matching their <dd> apart from the Deep dive link were reported")
    drifted = page([term_set(("term-x", "An emerging category."), ("term-y", "Why not."))], dl)
    if kinds(drifted) != ["term-out-of-sync"]:
        bad.append("a DefinedTerm description that differs from its <dd> was not reported")
    fixed = converges(drifted, "glossary")
    described = [t["description"] for m in LDJSON_RE.finditer(fixed) for t in json.loads(m.group(2))["hasDefinedTerm"]]
    if described != ["A vendor coinage.", "Why not."]:
        bad.append("--fix did not rewrite exactly the one differing DefinedTerm description")
    if "term-missing-dt" not in kinds(page([term_set(("term-z", "Zed."))], dl)):
        bad.append("a DefinedTerm with no matching <dt> was not reported")

    broken = '<html><head><script type="application/ld+json">{"@type": "FAQPage",</script></head><body></body></html>'
    findings, _, fixed = run(broken)
    if [f.kind for f in findings] != ["jsonld-parse"] or fixed != broken:
        bad.append("a JSON-LD block that does not parse was not reported, or was rewritten")

    return bad


LABELS = {
    "jsonld-parse": "JSON-LD blocks that do not parse (fix by hand)",
    "faq-unreadable": "FAQs this tool could not read, so it changed nothing (fix the markup or the extractor)",
    "term-missing-dt": "DefinedTerms with no matching <dt> (fix by hand)",
    "term-unreadable": "DefinedTerms this tool could not rewrite (fix by hand)",
    "faq-no-visible-faq": "FAQPage blocks with no visible FAQ anywhere on the page (--fix removes them)",
    "faq-out-of-sync": "FAQPage blocks that differ from the visible FAQ (--fix rewrites them)",
    "term-out-of-sync": "DefinedTerm descriptions that differ from the visible <dd> (--fix rewrites them)",
}


def report(findings: list[Finding], totals: Counter, verbose: bool) -> None:
    print(f"Self-test passed. {totals['faq_pages']} FAQPage blocks: {totals['questions']} questions in JSON-LD, "
          f"{totals['visible_questions']} in the visible FAQs, {totals['faq_in_sync']} blocks already identical. "
          f"{totals['terms']} DefinedTerms, {totals['terms_in_sync']} identical to their <dd>.")
    for kind, label in LABELS.items():
        items = [f for f in findings if f.kind == kind]
        if not items:
            continue
        print(f"\n{label}: {len(items)} on {len({f.page for f in items})} page(s)")
        for f in items:
            where = f"{f.page}:{f.line}" if f.line else f.page
            print(f"  {where}  {clip(f.key, 140)}")
            if kind in FIXABLE and not verbose:
                continue
            if kind == "faq-out-of-sync":
                for item in f.detail["dropped"]:
                    print(f"      drops JSON-LD-only question: {clip(item['question'], 120)}")
                    for c in item["claims_not_on_page"]:
                        print(f"          [{c['ratio']:.2f}] {clip(c['sentence'])}")
                for item in f.detail["changed"]:
                    if item["claims_not_on_page"]:
                        print(f"      rewrites answer to: {clip(item['question'], 120)}")
                        for c in item["claims_not_on_page"]:
                            print(f"          [{c['ratio']:.2f}] {clip(c['sentence'])}")
                            if c["closest"]:
                                print(f"                 closest on page: {clip(c['closest'])}")
                for q in f.detail["added"]:
                    print(f"      adds visible question: {clip(q, 120)}")
            elif kind in ("term-out-of-sync", "term-unreadable"):
                print(f"      JSON-LD: {clip(f.detail['jsonld'])}")
                print(f"      page:    {clip(f.detail['page'])}")
            else:
                for key, value in f.detail.items():
                    print(f"      {key}: {clip(str(value))}")
    if not findings:
        print("\nNo findings: every FAQPage and DefinedTerm copy matches its page.")
        return
    fixable = sum(1 for f in findings if f.kind in FIXABLE)
    print(f"\n{len(findings)} finding(s): {fixable} resolved by --fix, {len(findings) - fixable} need a person.")
    if fixable:
        print("Regenerate the copies with: python3 tools/check_faq_jsonld_parity.py --fix")


def analyze_all() -> tuple[dict[str, tuple[str, list[Finding], str]], Counter]:
    results: dict[str, tuple[str, list[Finding], str]] = {}
    totals: Counter = Counter()
    for rel in html_pages():
        raw = read_page(rel)
        findings, stats, fixed = sync_page(rel, raw)
        results[rel] = (raw, findings, fixed)
        totals.update(stats)
    return results, totals


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="exit 1 if any copy differs from its page or anything needs a person")
    mode.add_argument("--fix", action="store_true",
                      help="regenerate the JSON-LD copies from the visible text, then report what is left")
    mode.add_argument("--self-test", action="store_true", help="run the self-test and nothing else")
    ap.add_argument("--json", metavar="PATH", help="also write the findings as JSON")
    args = ap.parse_args()

    broken = self_test()
    if broken:
        print("SELF-TEST FAILED - this checker cannot be trusted:", file=sys.stderr)
        for b in broken:
            print(f"  {b}", file=sys.stderr)
        print("\nFix the checker before believing any result from it.", file=sys.stderr)
        return 1
    if args.self_test:
        print("Self-test passed: every detector fired on its planted case, every rewrite wrote exactly "
              "the expected page, and a second --fix changed nothing.")
        return 0

    results, totals = analyze_all()
    # An enumeration or extraction failure would also look like a clean site.
    if not totals["questions"] or not totals["visible_questions"] or not totals["terms"]:
        print("No FAQ questions, visible FAQ entries or DefinedTerms were found anywhere, so page enumeration "
              "or extraction is broken and a clean result would mean nothing.", file=sys.stderr)
        return 1

    if args.fix:
        written = []
        for rel, (raw, _, fixed) in results.items():
            if fixed != raw:
                (REPO / rel).write_bytes(fixed.encode("utf-8"))
                written.append(rel)
        print(f"--fix rewrote {len(written)} page(s)" + (": " + ", ".join(written) if written else "."))
        results, totals = analyze_all()
        stuck = [rel for rel, (raw, _, fixed) in results.items() if fixed != raw]
        if stuck:
            print("--fix did not converge; a second run would change: " + ", ".join(stuck), file=sys.stderr)
            return 1

    findings = [f for _, found, _ in results.values() for f in found]
    report(findings, totals, verbose=not (args.check or args.fix))
    if args.json:
        Path(args.json).write_text(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    return 1 if (args.check or args.fix) and findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
