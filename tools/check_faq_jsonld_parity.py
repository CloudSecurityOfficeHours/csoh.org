#!/usr/bin/env python3
"""Report FAQ and glossary JSON-LD copies that say something the page does not.

WHY THIS EXISTS
---------------
The site mirrors visible prose into structured data by hand. Most guide pages
carry an FAQPage block whose answers repeat the visible FAQ, and glossary.html
repeats each definition as a DefinedTerm description. Nothing kept the two
copies in step. While fixing weekly docs-review issue #1624 on 2026-09-12,
three separate findings turned out to be this one defect: a correction landed
in the visible prose and never reached its JSON-LD copy.

- faq.html's privacy answer still said "no analytics" in its FAQPage copy.
- compliance-frameworks.html's CMMC answer still said Level 2 "requires a
  C3PAO assessment" after the body described the Phase II suspension.
- glossary.html's AI-APP DefinedTerm still called the term an "Emerging
  category" after the visible definition had been rewritten.

The JSON-LD copy matters more than it looks: it is the text a search engine
lifts into a snippet, so the stale version is the one a reader is most likely
to see without ever opening the page.

WHAT IT REPORTS
---------------
1. FAQ answers with sentences that appear nowhere in the page's visible text.
   The comparison is on lowercase word tokens, so quotes, entities, markup and
   punctuation never count as a difference; wording does.
2. FAQPage blocks where none of the questions appear on the page at all.
   Google's FAQ structured-data guidelines require the content to be visible.
3. DefinedTerm descriptions that differ from the visible <dd>, and DefinedTerm
   @ids with no matching <dt>.

Every unmatched sentence carries its closest visible sentence and a similarity
ratio. The ratio is a triage hint, not a verdict: 0.95 can still flip a number,
and 0.3 can be a faithful one-line summary of a whole section.

Report-only by default and deliberately not wired into CI yet. A gate that
fails on its first day gets muted; triage the backlog, then add --check to
validate-html.yml.

THE SELF-TEST IS NOT OPTIONAL
-----------------------------
Every run starts with self_test(), which plants mismatched copies and refuses
to report anything unless each detector fires, and stays quiet on planted
copies that differ only in punctuation, entities or markup. The plant that
matters most is an answer that exists only inside <head> or the JSON-LD itself:
if the visible-text extractor ever stopped stripping those, every answer would
"match" its own copy and the report would be clean for the wrong reason.
Adding a detector means adding its planted case.

    python3 tools/check_faq_jsonld_parity.py                  # report
    python3 tools/check_faq_jsonld_parity.py --json out.json  # also write JSON
    python3 tools/check_faq_jsonld_parity.py --check          # exit 1 on any finding
    python3 tools/check_faq_jsonld_parity.py --self-test      # detectors only
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

LDJSON_RE = re.compile(r"<script[^>]+application/ld\+json[^>]*>(.*?)</script>", re.S | re.I)
NON_VISIBLE_RE = re.compile(
    r"<head\b.*?</head>|<script\b.*?</script>|<style\b.*?</style>|<noscript\b.*?</noscript>|<!--.*?-->",
    re.S | re.I,
)
TAG_RE = re.compile(r"<[^>]+>")
TOKEN_RE = re.compile(r"[a-z0-9]+")
ANSWER_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(\[])")
PAGE_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n\s*\n")
DT_DD_RE = re.compile(r'<dt\b[^>]*\bid="([^"]+)"[^>]*>.*?</dt>\s*<dd\b[^>]*>(.*?)</dd>', re.S)
FAQ_SECTION_RE = re.compile(r'id="faq"|<h2[^>]*>[^<]*(?:FAQ|Frequently|Quick answers|Common questions)', re.I)

# A trailing "Deep dive: <link>." in a glossary <dd> is navigation to the guide
# page, not part of the definition, and DefinedTerm descriptions leave it out on
# purpose (36 terms on 2026-09-12). Recorded here so it is a decision you can
# disagree with rather than a silent skip.
DD_NAVIGATION_SUFFIX_RE = re.compile(r"\s*<em>\s*Deep dive:\s*</em>.*$", re.S)

# Similarity bands for unmatched sentences. Hints for triage only.
COSMETIC, EDITED = 0.9, 0.6


@dataclass
class Finding:
    page: str
    kind: str   # faq-answer | faq-not-visible | term-differs | term-missing-dt | jsonld-parse
    key: str    # question text, term id, or a short description
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


def plain(text: str) -> str:
    """Tag-stripped, entity-decoded, whitespace-collapsed text."""
    return re.sub(r"\s+", " ", html_lib.unescape(TAG_RE.sub(" ", text))).strip()


def tokens(text: str) -> list[str]:
    return TOKEN_RE.findall(plain(text).lower())


def visible_text(raw: str) -> str:
    """What a reader sees: no <head>, scripts (JSON-LD included), styles, or comments."""
    return html_lib.unescape(TAG_RE.sub(" ", NON_VISIBLE_RE.sub(" ", raw)))


def answer_sentences(text: str) -> list[str]:
    return [s for s in ANSWER_SENTENCE_RE.split(plain(text)) if s.strip()]


def line_of(raw: str, needle: str) -> int:
    for probe in (json.dumps(needle, ensure_ascii=False)[1:-1], needle, needle[:60]):
        i = raw.find(probe) if probe else -1
        if i >= 0:
            return raw.count("\n", 0, i) + 1
    return 0


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


def _types(obj: dict) -> set:
    t = obj.get("@type")
    return set(t) if isinstance(t, list) else {t}


def jsonld_entities(raw: str) -> tuple[list[dict], list[str]]:
    """Every Question and DefinedTerm in the page's JSON-LD, plus parse errors.

    Walks the whole tree, so @graph wrappers and list-valued @type both work.
    """
    found: list[dict] = []
    errors: list[str] = []

    def walk(obj) -> None:
        if isinstance(obj, dict):
            types = _types(obj)
            if "Question" in types:
                answer = obj.get("acceptedAnswer")
                if isinstance(answer, list):
                    answer = answer[0] if answer else {}
                text = answer.get("text", "") if isinstance(answer, dict) else ""
                found.append({"kind": "question", "name": str(obj.get("name", "")), "text": str(text)})
            if "DefinedTerm" in types and obj.get("description"):
                found.append({"kind": "term", "id": str(obj.get("@id", "")),
                              "name": str(obj.get("name", "")), "text": str(obj["description"])})
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    for n, block in enumerate(LDJSON_RE.findall(raw), 1):
        try:
            walk(json.loads(block))
        except json.JSONDecodeError as e:
            errors.append(f"JSON-LD block {n} does not parse: {e}")
    return found, errors


def analyze_page(page: str, raw: str) -> tuple[list[Finding], Counter]:
    entities, errors = jsonld_entities(raw)
    stats: Counter = Counter()
    findings = [Finding(page, "jsonld-parse", e, 0) for e in errors]
    questions = [e for e in entities if e["kind"] == "question"]
    terms = [e for e in entities if e["kind"] == "term"]
    if not questions and not terms:
        return findings, stats
    index = VisibleIndex(visible_text(raw))

    if questions:
        stats["faq_pages"] += 1
        stats["questions"] += len(questions)
        per_question = []
        visible_questions = 0
        for q in questions:
            q_visible = index.contains(tokens(q["name"]))
            visible_questions += q_visible
            unmatched = []
            for sentence in answer_sentences(q["text"]):
                toks = tokens(sentence)
                if not toks:
                    continue
                stats["sentences"] += 1
                if index.contains(toks):
                    stats["exact"] += 1
                    continue
                ratio, near = index.closest(toks)
                stats["cosmetic" if ratio >= COSMETIC else "edited" if ratio >= EDITED else "absent"] += 1
                unmatched.append({"sentence": sentence, "ratio": round(ratio, 2), "closest": near})
            if unmatched:
                per_question.append(Finding(page, "faq-answer", q["name"], line_of(raw, q["name"]),
                                            {"question_visible": q_visible, "answer": plain(q["text"]),
                                             "unmatched": unmatched}))
        if visible_questions == 0:
            findings.append(Finding(
                page, "faq-not-visible", f"{len(questions)} questions, none visible", line_of(raw, "FAQPage"),
                {"faq_section_markup": bool(FAQ_SECTION_RE.search(NON_VISIBLE_RE.sub(" ", raw))),
                 "questions": [q["name"] for q in questions]}))
        else:
            findings += per_question

    if terms:
        stats["term_pages"] += 1
        stats["terms"] += len(terms)
        dd_by_id = dict(DT_DD_RE.findall(raw))
        for t in terms:
            frag = t["id"].rsplit("#", 1)[-1] if "#" in t["id"] else ""
            line = line_of(raw, t["id"]) if t["id"] else line_of(raw, t["name"])
            if frag not in dd_by_id:
                findings.append(Finding(page, "term-missing-dt", t["id"] or t["name"], line,
                                        {"jsonld": plain(t["text"])}))
                continue
            dd_html = DD_NAVIGATION_SUFFIX_RE.sub("", dd_by_id[frag])
            ld_toks, dd_toks = tokens(t["text"]), tokens(dd_html)
            if ld_toks == dd_toks:
                stats["terms_exact"] += 1
                continue
            sm = difflib.SequenceMatcher(None, ld_toks, dd_toks, autojunk=False)
            diff = [{"op": op, "jsonld": " ".join(ld_toks[a1:a2]), "page": " ".join(dd_toks[b1:b2])}
                    for op, a1, a2, b1, b2 in sm.get_opcodes() if op != "equal"]
            findings.append(Finding(page, "term-differs", frag, line,
                                    {"ratio": round(sm.ratio(), 2), "jsonld": plain(t["text"]),
                                     "page": plain(dd_html), "diff": diff}))
    return findings, stats


def self_test() -> list[str]:
    """Prove every detector fires on planted input, and stays quiet on harmless variation."""
    bad: list[str] = []

    def page(ld: dict, body: str, head: str = "", ld_in_body: bool = False) -> str:
        script = '<script type="application/ld+json">' + json.dumps(ld) + "</script>"
        return ("<!DOCTYPE html><html><head><title>planted</title>" + head + ("" if ld_in_body else script)
                + "</head><body>" + (script if ld_in_body else "") + body + "</body></html>")

    def faq(*pairs):
        return {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": [
            {"@type": "Question", "name": q, "acceptedAnswer": {"@type": "Answer", "text": a}} for q, a in pairs]}

    def kinds(raw: str) -> list[str]:
        return [f.kind for f in analyze_page("planted.html", raw)[0]]

    q = "What does Level 2 require?"
    shown = "<h2>FAQ</h2><h3>What does Level 2 require?</h3><p>Level 2 covers CUI. Most contracts still use self-assessment.</p>"

    if kinds(page(faq((q, "Level 2 covers CUI. Most contracts still use self-assessment.")), shown)):
        bad.append("an answer mirrored word for word was reported")

    shown2 = ('<h3>Is it private?</h3><p>Short version: no <strong>cookies</strong>, it&#x27;s &quot;fine&quot; '
              'for M&amp;A. Long version: <a href="privacy.html">privacy.html</a>.</p>')
    if kinds(page(faq(("Is it private?", "Short version: no cookies, it's 'fine' for M&A. Long version: privacy.html .")), shown2)):
        bad.append("a copy differing only in quotes, entities, markup or spacing was reported")

    stale = analyze_page("planted.html", page(faq((q, "Level 2 covers CUI. It requires a C3PAO assessment.")), shown))[0]
    answers = [f for f in stale if f.kind == "faq-answer"]
    if not answers:
        bad.append("a JSON-LD answer that contradicts the visible answer was not reported")
    elif [u["sentence"] for u in answers[0].detail["unmatched"]] != ["It requires a C3PAO assessment."]:
        bad.append("the stale-answer finding flagged the wrong sentences")

    head = '<meta name="description" content="It requires a C3PAO assessment.">'
    stale_ld = faq((q, "Level 2 covers CUI. It requires a C3PAO assessment."))
    if "faq-answer" not in kinds(page(stale_ld, shown, head=head)):
        bad.append("an answer present only in <head> counted as visible - the extractor is not stripping <head>")
    if "faq-answer" not in kinds(page(stale_ld, shown, ld_in_body=True)):
        bad.append("an answer present only in a JSON-LD block in <body> counted as visible - scripts are not stripped")

    if "faq-not-visible" not in kinds(page(faq((q, "Level 2 covers CUI.")), "<p>Nothing about that here.</p>")):
        bad.append("an FAQPage whose questions appear nowhere on the page was not reported")

    graphed = {"@context": "https://schema.org", "@graph": [{"@type": ["FAQPage"], "mainEntity": [
        {"@type": ["Question"], "name": q, "acceptedAnswer": {"@type": "Answer", "text": "It requires a C3PAO assessment."}}]}]}
    if "faq-answer" not in kinds(page(graphed, shown)):
        bad.append("a Question inside @graph with a list-valued @type was not read")

    def term(desc: str) -> dict:
        return {"@context": "https://schema.org", "@type": "DefinedTermSet", "hasDefinedTerm": [
            {"@type": "DefinedTerm", "@id": "https://csoh.org/glossary.html#term-x", "name": "X", "description": desc}]}

    dl = '<dl><dt id="term-x">X</dt><dd>A <a href="#term-y">vendor</a> coinage. <em>Deep dive:</em> <a href="x.html">X</a>.</dd></dl>'
    if kinds(page(term("A vendor coinage."), dl)):
        bad.append("a DefinedTerm matching its <dd> apart from the Deep dive link was reported")
    if "term-differs" not in kinds(page(term("An emerging category."), dl)):
        bad.append("a DefinedTerm description that differs from its <dd> was not reported")
    if "term-missing-dt" not in kinds(page(term("A vendor coinage."), "<p>No list here.</p>")):
        bad.append("a DefinedTerm with no matching <dt> was not reported")

    broken = '<script type="application/ld+json">{"@type": "FAQPage",</script>'
    if "jsonld-parse" not in kinds("<html><head>" + broken + "</head><body></body></html>"):
        bad.append("a JSON-LD block that does not parse was not reported")

    return bad


LABELS = {
    "jsonld-parse": "JSON-LD blocks that do not parse",
    "faq-not-visible": "FAQPage blocks with no visible FAQ (none of the questions appear on the page)",
    "faq-answer": "FAQ answers with sentences that appear nowhere on the page",
    "term-missing-dt": "DefinedTerms with no matching <dt>",
    "term-differs": "DefinedTerm descriptions that differ from the visible <dd>",
}


def clip(text: str, n: int = 220) -> str:
    return text if len(text) <= n else text[: n - 3] + "..."


def report(findings: list[Finding], totals: Counter) -> None:
    unmatched = totals["cosmetic"] + totals["edited"] + totals["absent"]
    print(f"Self-test passed. Checked {totals['questions']} FAQ questions on {totals['faq_pages']} pages "
          f"({totals['sentences']} answer sentences) and {totals['terms']} DefinedTerms on {totals['term_pages']} page(s).")
    print(f"Answer sentences: {totals['exact']} found on the page, {unmatched} not "
          f"({totals['cosmetic']} close >= {COSMETIC}, {totals['edited']} edited >= {EDITED}, {totals['absent']} no close match). "
          f"DefinedTerms identical to their <dd>: {totals['terms_exact']} of {totals['terms']}.")
    for kind, label in LABELS.items():
        items = [f for f in findings if f.kind == kind]
        if not items:
            continue
        pages = len({f.page for f in items})
        print(f"\n{label}: {len(items)} on {pages} page(s)")
        for f in items:
            where = f"{f.page}:{f.line}" if f.line else f.page
            if kind == "faq-answer":
                flag = "" if f.detail["question_visible"] else "  [question not on page]"
                print(f"  {where}  {clip(f.key, 120)}{flag}")
                for u in f.detail["unmatched"]:
                    print(f"      [{u['ratio']:.2f}] {clip(u['sentence'])}")
                    if u["closest"]:
                        print(f"             closest on page: {clip(u['closest'])}")
            elif kind == "faq-not-visible":
                section = "has an FAQ-shaped section" if f.detail["faq_section_markup"] else "no FAQ section at all"
                print(f"  {where}  {f.key}; {section}")
            elif kind == "term-differs":
                print(f"  {where}  {f.key}  [{f.detail['ratio']:.2f}]")
                for d in f.detail["diff"][:4]:
                    print(f"      JSON-LD: {clip(d['jsonld'] or '(nothing)', 150)}")
                    print(f"      page:    {clip(d['page'] or '(nothing)', 150)}")
            else:
                print(f"  {where}  {f.key}")
    print(f"\n{len(findings)} finding(s)." if findings else "\nNo findings.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 on any finding")
    ap.add_argument("--json", metavar="PATH", help="also write the findings as JSON")
    ap.add_argument("--self-test", action="store_true", help="run the detector self-test and nothing else")
    args = ap.parse_args()

    broken = self_test()
    if broken:
        print("SELF-TEST FAILED - this checker cannot be trusted:", file=sys.stderr)
        for b in broken:
            print(f"  {b}", file=sys.stderr)
        print("\nFix the checker before believing any result from it.", file=sys.stderr)
        return 1
    if args.self_test:
        print("Self-test passed: every detector fired on its planted case and stayed quiet on harmless variation.")
        return 0

    findings: list[Finding] = []
    totals: Counter = Counter()
    for rel in html_pages():
        page_findings, stats = analyze_page(rel, (REPO / rel).read_text(encoding="utf-8", errors="replace"))
        findings += page_findings
        totals.update(stats)

    # An enumeration or parsing failure would also produce zero findings.
    if not totals["questions"] or not totals["terms"]:
        print("No FAQ questions or DefinedTerms were found anywhere, so page enumeration or JSON-LD "
              "parsing is broken and a clean result would mean nothing.", file=sys.stderr)
        return 1

    report(findings, totals)
    if args.json:
        Path(args.json).write_text(json.dumps([asdict(f) for f in findings], indent=2, ensure_ascii=False),
                                   encoding="utf-8")
    return 1 if (args.check and findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
