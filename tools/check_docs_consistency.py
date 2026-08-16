#!/usr/bin/env python3
"""Documentation consistency: the half of the weekly review a script can decide.

The weekly documentation review used to be one model pass over the whole site,
and most of what it found was mechanical - a visible date disagreeing with the
page's own JSON-LD, a social card pointing at a file that does not exist, a
count in prose that content drift left behind. PR #1483 is the worked example:
a majority of its findings needed no judgment at all, it took two days to
review, and it was closed unmerged against a fast-moving `main`. Every fix in
it was lost, including a date mismatch on `breach-lessons.html` that is still
live today.

Rediscovering that class of finding with a model every week costs tokens,
phrases the same defect differently each time, and buries the findings that
genuinely need a human. So this script owns everything decidable, and the
weekly model pass (`.github/workflows/weekly-docs-review.yml`) is left with
accuracy, neutrality, member temperature, and reading level - the things no
regex can settle. `docs/EDITORIAL_STANDARDS.md` is the standard both halves
check against.

Two classes of finding, and the distinction drives the exit code:

  FIXABLE   - wrong, and the correct value is derivable from something already
              in the repo. `--fix` rewrites it; `--check` fails CI so drift
              cannot accumulate.
  REPORT    - wrong or suspicious, but the correct value is not in the repo (a
              real authoring date, a missing image asset, whether a term earns
              its place). Never auto-applied, never fails CI. These flow into
              the weekly tracking issue and wait for a human.

`--check` deliberately ignores REPORT findings. A gate that fails on something
CI cannot fix would block every push forever.

**This script never deletes.** It rewrites values in place and nothing else -
no file, section, card, or glossary entry is ever removed. Removal is a human
decision every time (`docs/EDITORIAL_STANDARDS.md` §7).

Usage:
    python3 tools/check_docs_consistency.py --check          # CI gate
    python3 tools/check_docs_consistency.py --fix            # apply
    python3 tools/check_docs_consistency.py --report r.md    # markdown report

Exit code: 0 when no FIXABLE finding remains; 1 from --check when any does.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sync_counts import canonical_counts, display_values  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# Same exclusion set as check_jsonld.py: build output, vendored code, and any
# dot-directory (.git, .claude worktrees) which holds stale copies of pages.
EXCLUDE_DIRS = {"dist", "vendor", "node_modules", "__pycache__", "seo-audits"}

# Markdown that is authored prose rather than generated output.
DOC_GLOBS = ("*.md", "tools/*.md", "docs/*.md")

# The breach series sets datePublished to the date of the INCIDENT rather than
# the date the write-up was authored - 0ktapus is 2022-08-26, Log4Shell is
# 2021-12-14, Codecov is 2021-04-15, each matching its incident. That is not
# what schema.org means by datePublished on an Article, but it is applied
# consistently across the series, so it is a convention and not drift. Changing
# it is an editorial decision about the whole series, not a per-page defect.
#
# What that convention makes visible is January 1. A real incident has a real
# date, so a January 1 datePublished is a page where nobody filled the template
# in, and it breaks the series' own rule.

# ---------------------------------------------------------------- known exceptions
#
# Recorded decisions, in the style of check_glossary_coverage.py's UNREACHABLE:
# a false positive that is silently skipped will be rediscovered by the next
# person to read the code, but one listed with a reason is an argument you can
# disagree with.

# Count phrases that look like a site inventory claim but are not.
COUNT_EXCEPTIONS = {
    # RSA Conference's exhibitor hall, not our vendor landscape.
    ("conferences.html", "600"): "RSA exhibitor count, not a CSOH inventory number",
    # A per-section subtotal inside the README's own resource breakdown.
    ("README.md", "50"): "AI Security section subtotal, not the site-wide total",
    # An instruction to contributors about section size, not a claim.
    ("CONTRIBUTING.md", "30"): "guidance on section size, not an inventory count",
    # This tool's own README quotes README.md's false count as the worked
    # example of why counts are reported and not auto-fixed. Documenting a
    # defect reproduces it, and the checker cannot tell a quotation from a
    # claim - the same trap CLAUDE.md records for writing a CI-skip token
    # while explaining one.
    ("tools/DOCS_CONSISTENCY_README.md", "102"): "quotes the defect it documents",
}

# Glossary entries nothing links to are usually a signal, but these are the
# deliberately-unlinkable headwords check_glossary_coverage.py already records.
# Kept in step with that file's UNREACHABLE by check 9 itself.
GLOSSARY_UNREACHABLE_SOURCE = REPO / "tools" / "check_glossary_coverage.py"


@dataclass
class Finding:
    kind: str
    path: str
    message: str
    fixable: bool
    detail: str = ""


@dataclass
class FileEdit:
    """One in-place rewrite. `old` and `new` are whole-file text."""
    path: Path
    new: str
    notes: list[str] = field(default_factory=list)


# ------------------------------------------------------------------------ helpers

def _excluded(rel: Path) -> bool:
    return any(p in EXCLUDE_DIRS or p.startswith(".") for p in rel.parts)


def html_pages() -> list[Path]:
    out = []
    for p in REPO.rglob("*.html"):
        rel = p.relative_to(REPO)
        if not _excluded(rel):
            out.append(p)
    return sorted(out)


def doc_files() -> list[Path]:
    out: list[Path] = []
    for g in DOC_GLOBS:
        for p in REPO.glob(g):
            rel = p.relative_to(REPO)
            if not _excluded(rel):
                out.append(p)
    return sorted(set(out))


def rel(p: Path) -> str:
    return str(p.relative_to(REPO))


def strip_code(text: str) -> str:
    """Blank out <script>/<style> and fenced code so prose checks skip them.

    Replaced with same-length filler rather than deleted, so offsets computed
    against the result still point at the right place in the original.
    """
    def blank(m: re.Match) -> str:
        return "\x00" * len(m.group(0))
    text = re.sub(r"(?is)<(script|style)\b.*?</\1>", blank, text)
    text = re.sub(r"(?s)```.*?```", blank, text)
    return text


# JSON-LD dates
DATE_MODIFIED = re.compile(r'"dateModified"\s*:\s*"(\d{4}-\d{2}-\d{2})')
DATE_PUBLISHED = re.compile(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})')

# The page-meta byline is the ONLY visible date that makes a claim about the
# page itself. Body <time> elements are session and conference dates; matching
# those was the first version's bug and it produced confident false positives
# on conferences.html and threat-research.html.
PAGE_META = re.compile(r'<p class="page-meta">(.*?)</p>', re.DOTALL)
META_TIME = re.compile(
    r'(<time datetime=")(\d{4}-\d{2}-\d{2})("[^>]*>\s*)'
    r'(Published|Last updated)(\s*<strong>)(\d{4}-\d{2}-\d{2})(</strong>)',
    re.IGNORECASE,
)


# ------------------------------------------------------------------- checks 1 - 3

def check_dates(path: Path, text: str) -> tuple[list[Finding], str]:
    """Date coherence within a single page.

    Three distinct defects, only two of them mechanical:

    1. `Last updated <date>` disagreeing with the page's own JSON-LD
       `dateModified`. One claim, two values, so one is wrong. dateModified is
       authoritative: on all five live instances the visible date is simply a
       stale copy of datePublished, and on
       what-practitioners-think-about-security-conferences.html it is EARLIER
       than datePublished, i.e. the page claimed it was updated before it
       existed. FIXABLE.

    2. The `datetime` attribute disagreeing with the human-readable date beside
       it. Machines read one, people read the other. FIXABLE.

    3. `datePublished` after `dateModified`, which cannot be true. REPORT,
       because which of the two is wrong is not derivable.

    A page-meta reading `Published <date>` with a LATER dateModified is not a
    defect and is deliberately not flagged - an article published in July and
    edited in August is exactly that. PR #1483 treated this as an error on
    breach-lessons.html and rewrote the label; that was an editorial choice
    dressed as a correction.
    """
    findings: list[Finding] = []
    meta = PAGE_META.search(text)
    if not meta:
        return findings, text

    dm = DATE_MODIFIED.search(text)
    dp = DATE_PUBLISHED.search(text)
    block = meta.group(1)
    m = META_TIME.search(block)
    if not m:
        return findings, text

    attr, label, shown = m.group(2), m.group(4), m.group(6)
    new_block = block

    # 2. attribute vs visible text, resolved toward the attribute.
    if attr != shown:
        findings.append(Finding(
            "date-attr-text", rel(path),
            f"<time datetime=\"{attr}\"> but the visible text reads {shown}",
            fixable=True,
        ))
        new_block = new_block.replace(m.group(0), m.group(0)[: m.start(6) - m.start(0)]
                                      + attr + m.group(7), 1)
        m = META_TIME.search(new_block) or m
        attr = shown = attr

    # 1. "Last updated" vs dateModified.
    if label.lower() == "last updated" and dm and attr != dm.group(1):
        findings.append(Finding(
            "date-visible-vs-jsonld", rel(path),
            f"visible \"Last updated {attr}\" but JSON-LD dateModified is {dm.group(1)}",
            fixable=True,
            detail="dateModified is authoritative; the visible date is stale.",
        ))
        fixed = META_TIME.sub(
            lambda mm: (mm.group(1) + dm.group(1) + mm.group(3) + mm.group(4)
                        + mm.group(5) + dm.group(1) + mm.group(7)),
            new_block, count=1,
        )
        new_block = fixed

    # 3. published after modified.
    if dp and dm and dp.group(1) > dm.group(1):
        findings.append(Finding(
            "date-incoherent", rel(path),
            f"datePublished {dp.group(1)} is after dateModified {dm.group(1)}",
            fixable=False,
        ))

    if new_block != block:
        text = text.replace(meta.group(0), meta.group(0).replace(block, new_block, 1), 1)
    return findings, text


def check_placeholder_dates(path: Path, text: str) -> list[Finding]:
    """January 1 datePublished: the template nobody filled in.

    Judged against the series' own convention (see the note above), not against
    schema.org. Every other breach page carries the incident's real date, so
    January 1 is the tell - Capital One reads 2019-01-01 where the breach was
    July 2019, and Mitnick/Novell reads 1994-01-01.

    REPORT only. The right value is not recoverable from the repo, and git
    cannot supply it either: site-wide SRI and chrome sweeps touch every file,
    so all 272 pages share the same last-commit date.
    """
    dp = DATE_PUBLISHED.search(text)
    if not dp or not dp.group(1).endswith("-01-01"):
        return []
    return [Finding(
        "date-placeholder", rel(path),
        f"datePublished {dp.group(1)} is a January 1 placeholder",
        fixable=False,
        detail="Every other page in the series carries the incident's real date.",
    )]


# ----------------------------------------------------------------------- check 4

OG_IMAGE = re.compile(r'<meta\s+(?:property|name)="(og:image|twitter:image)"\s+content="([^"]+)"')


def check_social_cards(path: Path, text: str) -> list[Finding]:
    """og:image / twitter:image must resolve to a file that exists.

    Three meeting pages (2026-07-10, -17, -24) point at cards that were never
    generated: img/og/meetings/ holds 104 images for 107 pages. Their unfurls
    are broken right now, silently, because nothing fetches the URL a meta tag
    advertises.

    REPORT, not fixable: the correct action is to run
    `tools/generate_meeting_og_images.py`, which needs Playwright. Inventing a
    substitute image would hide the gap.
    """
    # og:image and twitter:image almost always name the same asset, so report
    # per missing FILE rather than per meta tag - otherwise every broken card
    # is counted twice and the total overstates the problem.
    missing: dict[str, set[str]] = {}
    for m in OG_IMAGE.finditer(text):
        prop, url = m.group(1), m.group(2)
        local = url.split("csoh.org/", 1)[-1].lstrip("/")
        if not local or local.startswith(("http://", "https://", "data:")):
            continue
        if not (REPO / local).exists():
            missing.setdefault(local, set()).add(prop)
    return [
        Finding(
            "og-asset-missing", rel(path),
            f"{' and '.join(sorted(props))} point at {local}, which does not exist"
            if len(props) > 1 else
            f"{next(iter(props))} points at {local}, which does not exist",
            fixable=False,
            detail="Regenerate the card (tools/generate_meeting_og_images.py "
                   "or tools/generate_og_images.py).",
        )
        for local, props in sorted(missing.items())
    ]


# ----------------------------------------------------------------------- check 5

# Prose inventory claims. Only subjects whose true value is derivable from the
# repo are listed; "vendors" is deliberately absent - vendor-landscape.html is
# prose in lists with no countable card structure, so there is no truth to
# check against and guessing one would be worse than reporting the conflict.
COUNT_SUBJECTS = {
    "curated resources": "resources_floor",
    "curated cloud security resources": "resources_floor",
    "resources": "resources_floor",
    "meeting recaps": "meetings",
    "recaps": "meetings",
    "glossary terms": "glossary_terms_floor",
    "breach kill chains": "breaches",
    "conferences": "conferences",
}

COUNT_RE = re.compile(
    r"(\d{2,4})(\+?)\s+(?:curated\s+)?"
    r"(curated cloud security resources|curated resources|meeting recaps|glossary terms|"
    r"breach kill chains|conferences|resources|recaps)\b",
    re.IGNORECASE,
)


def check_counts(path: Path, text: str, disp: dict) -> list[Finding]:
    """Inventory numbers in prose that are FALSE, reported for a human.

    Two deliberate narrowings, both learned by getting it wrong first.

    **Only disagreement, never "correct but unmarked."** 24 pages carry "browse
    all 107 recaps" and every one is generated by inject_session_blocks.py from
    the real total. Flagging them as unwrapped would fight a generator that is
    already keeping them right.

    **Only claims that are false.** "N+" is a floor, so "300+ glossary terms"
    with 317 live is true, and so are "100+ recaps" and "200+ resources". An
    earlier version rewrote all three toward the canonical floor and produced
    three wrong edits out of four.

    Report-only, deliberately. The one genuinely false claim here is README.md's
    "102 meeting recaps in img/og/meetings/", and the right value is 104 - the
    number of image FILES - not 107, the number of recaps the subject phrase
    matches. Auto-fixing would have written a confident falsehood and hidden
    the three missing cards that check_social_cards reports separately. A
    number in prose carries context a regex cannot read, so a human decides.
    """
    findings: list[Finding] = []
    for m in COUNT_RE.finditer(strip_code(text)):
        num, plus, subject = m.group(1), m.group(2), m.group(3).lower()
        if (rel(path), num) in COUNT_EXCEPTIONS:
            continue
        key = COUNT_SUBJECTS.get(subject)
        truth = disp.get(key) if key else None
        if not truth:
            continue
        real = int(truth.rstrip("+"))
        claimed = int(num)
        false_claim = (claimed > real) if plus else (claimed != real)
        if not false_claim:
            continue
        findings.append(Finding(
            "count-drift", rel(path),
            f"prose says \"{num}{plus} {subject}\" but the real count is {truth}",
            fixable=False,
            detail="Check what the sentence is actually counting before changing it, "
                   f"then consider a <!--count:{key}--> marker so sync_counts.py "
                   "owns it.",
        ))
    return findings


def check_count_conflicts(texts: dict[str, str]) -> list[Finding]:
    """Inventory claims that disagree across documents with no derivable truth.

    "vendors" is the live case: about.html says 350+ twice, README.md and
    CONTRIBUTING.md say 360+. One is stale, but vendor-landscape.html has no
    countable structure, so the script cannot say which. REPORT.
    """
    seen: dict[str, set[tuple[str, str]]] = {}
    pat = re.compile(r"(\d{2,4})\+?\s+vendors\b", re.IGNORECASE)
    for name, text in texts.items():
        for m in pat.finditer(strip_code(text)):
            if (name, m.group(1)) in COUNT_EXCEPTIONS:
                continue
            seen.setdefault("vendors", set()).add((name, m.group(1)))
    out = []
    for subject, pairs in seen.items():
        values = {v for _, v in pairs}
        if len(values) > 1:
            where = ", ".join(f"{n} says {v}" for n, v in sorted(pairs))
            out.append(Finding(
                "count-conflict", "(multiple)",
                f"{subject}: {where}",
                fixable=False,
                detail="vendor-landscape.html has no countable card structure, so "
                       "no value can be derived. Pick one and consider giving "
                       "sync_counts.py something to count.",
            ))
    return out


# ----------------------------------------------------------------------- check 6

def check_em_dashes(path: Path, text: str) -> tuple[list[Finding], str]:
    """Em-dashes, per docs/EDITORIAL_STANDARDS.md §5.

    The site is already almost clean, so this is a regression guard rather than
    a cleanup. Script, style, and fenced code blocks are skipped: an em-dash in
    vendored JS or a code sample is not prose.
    """
    scan = strip_code(text)
    n = scan.count("—")
    if not n:
        return [], text
    out = [Finding(
        "em-dash", rel(path),
        f"{n} em-dash{'es' if n > 1 else ''} in prose; the standard is a spaced hyphen",
        fixable=True,
    )]
    # Rebuild with replacements applied only at offsets that survived stripping.
    chars = list(text)
    for i, ch in enumerate(scan):
        if ch == "—":
            chars[i] = "\x01"
    rebuilt = "".join(chars)
    # An em-dash ending a line must not leave a trailing space behind it - the
    # sentence continues on the next line, and trailing whitespace is its own
    # lint failure. Handle that case before the general one.
    rebuilt = re.sub(r"[ \t]*\x01[ \t]*(?=\n)", " -", rebuilt)
    rebuilt = re.sub(r"[ \t]*\x01[ \t]*", " - ", rebuilt)
    return out, rebuilt


# ----------------------------------------------------------------------- check 7

TOOL_REF = re.compile(r"\btools/([a-z0-9_]+\.py)\b")


def check_repo_doc_refs(path: Path, text: str) -> list[Finding]:
    """A tool README naming a script that no longer exists.

    Cheap, and it catches the documentation half of a rename - the half that
    does not break CI and so survives for months.
    """
    out = []
    for m in sorted(set(TOOL_REF.findall(text))):
        if not (REPO / "tools" / m).exists():
            out.append(Finding(
                "dead-tool-ref", rel(path),
                f"references tools/{m}, which does not exist",
                fixable=False,
            ))
    return out


# ----------------------------------------------------------------------- check 8

def check_glossary_orphans(pages: list[Path]) -> list[Finding]:
    """Glossary entries that no page links to.

    crosslink_pages.py links glossary terms from every page automatically, so an
    entry with zero inbound links is one whose headword never appears in site
    prose. That is worth a look - it may be a term that has fallen out of use,
    or one whose headword is phrased differently from how anyone writes it.

    REPORT, firmly. An orphan is NOT evidence a term should be cut:
    check_glossary_coverage.py maintains an UNREACHABLE list of headwords that
    are deliberately unlinkable, and those are correct entries. Deletion is a
    human call (docs/EDITORIAL_STANDARDS.md §7).
    """
    glossary = REPO / "glossary.html"
    if not glossary.exists():
        return []
    html = glossary.read_text(encoding="utf-8")
    entries = {
        m.group(1)
        for m in re.finditer(r'<dt[^>]*\bid\s*=\s*["\'](term-[^"\']+)["\']', html)
    }
    # Headwords check_glossary_coverage.py already records as unlinkable.
    unreachable: set[str] = set()
    if GLOSSARY_UNREACHABLE_SOURCE.exists():
        src = GLOSSARY_UNREACHABLE_SOURCE.read_text(encoding="utf-8")
        block = re.search(r"UNREACHABLE\s*=\s*\{(.*?)\n\}", src, re.DOTALL)
        if block:
            unreachable = set(re.findall(r'"(term-[^"]+)"', block.group(1)))

    linked: set[str] = set()
    for p in pages:
        if p.name == "glossary.html":
            continue
        for m in re.finditer(r'href="[^"]*glossary\.html#(term-[^"#]+)"',
                             p.read_text(encoding="utf-8", errors="replace")):
            linked.add(m.group(1))

    orphans = sorted(entries - linked - unreachable)
    if not orphans:
        return []
    shown = ", ".join(o.replace("term-", "") for o in orphans[:12])
    more = f" (+{len(orphans) - 12} more)" if len(orphans) > 12 else ""
    return [Finding(
        "glossary-orphan", "glossary.html",
        f"{len(orphans)} entries no page links to: {shown}{more}",
        fixable=False,
        detail="Not a deletion list. A headword may simply be phrased "
               "differently from how the site writes it.",
    )]


# --------------------------------------------------------------------------- main

def collect(apply: bool) -> tuple[list[Finding], list[FileEdit]]:
    disp = display_values(canonical_counts())
    findings: list[Finding] = []
    edits: list[FileEdit] = []

    pages = html_pages()
    docs = doc_files()

    conflict_texts: dict[str, str] = {}

    for p in pages + docs:
        original = p.read_text(encoding="utf-8", errors="replace")
        text = original
        is_html = p.suffix == ".html"

        if is_html:
            f, text = check_dates(p, text)
            findings += f
            findings += check_placeholder_dates(p, text)
            findings += check_social_cards(p, text)
        else:
            findings += check_repo_doc_refs(p, text)

        findings += check_counts(p, text, disp)
        f, text = check_em_dashes(p, text)
        findings += f

        conflict_texts[rel(p)] = original
        if text != original:
            edits.append(FileEdit(p, text))

    findings += check_count_conflicts(conflict_texts)
    findings += check_glossary_orphans(pages)

    if apply:
        for e in edits:
            e.path.write_text(e.new, encoding="utf-8")

    return findings, edits


def render_report(findings: list[Finding]) -> str:
    fixable = [f for f in findings if f.fixable]
    report = [f for f in findings if not f.fixable]
    out = ["# Documentation consistency report", ""]
    out.append(f"{len(fixable)} mechanical, {len(report)} needing a human.")
    out.append("")
    if fixable:
        out += ["## Mechanical - applied by `--fix`", ""]
        for f in sorted(fixable, key=lambda x: (x.kind, x.path)):
            out.append(f"- **{f.path}** - {f.message}")
            if f.detail:
                out.append(f"  - {f.detail}")
        out.append("")
    if report:
        out += ["## Needs a human", "",
                "Not auto-applied. Nothing here is deleted by any tool.", ""]
        for f in sorted(report, key=lambda x: (x.kind, x.path)):
            out.append(f"- [ ] **{f.path}** - {f.message}")
            if f.detail:
                out.append(f"  - {f.detail}")
        out.append("")
    if not findings:
        out.append("No findings.")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Mechanical documentation consistency checks. Never deletes.")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true",
                      help="report and exit 1 if any FIXABLE finding remains (CI gate)")
    mode.add_argument("--fix", action="store_true",
                      help="apply every mechanical fix in place")
    ap.add_argument("--report", metavar="FILE",
                    help="write a markdown report (use - for stdout)")
    args = ap.parse_args()

    findings, edits = collect(apply=args.fix)
    fixable = [f for f in findings if f.fixable]
    human = [f for f in findings if not f.fixable]

    if args.report:
        text = render_report(findings)
        if args.report == "-":
            print(text)
        else:
            Path(args.report).write_text(text, encoding="utf-8")
            print(f"Wrote {args.report}")

    if args.fix:
        print(f"Applied {len(fixable)} mechanical fix(es) across {len(edits)} file(s).")
        for e in edits:
            print(f"  {rel(e.path)}")
    elif not args.report:
        for f in sorted(findings, key=lambda x: (not x.fixable, x.kind, x.path)):
            tag = "FIX " if f.fixable else "HUMAN"
            print(f"  [{tag}] {f.path}: {f.message}")

    print(f"\n{len(fixable)} mechanical, {len(human)} needing a human.")

    if args.check and fixable:
        print("\nRun `python3 tools/check_docs_consistency.py --fix` to apply the "
              "mechanical fixes. The rest are reported, never auto-applied.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
