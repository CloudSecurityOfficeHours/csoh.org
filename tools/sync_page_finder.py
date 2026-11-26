#!/usr/bin/env python3
"""
Stamp the "Find on this page" field (page-finder.js) into the On this page box
of every page in PAGES and at the top of every breach kill chain, and take it
out of every other page.

On a guide in PAGES the field goes right after the box's heading; on a kill
chain (every page in breaches/) it goes right before the chain's
<div class="kill-chain">, between the incident header and the first step. Either way it sits between the `page-finder` marker
comments, and the script tag goes right after main.js's. page-finder.js needs
nothing per page: it searches the page's <main> and narrows the box's own list
of links where there is a box. So the field's markup lives only in FINDER
below; to change it, edit FINDER and re-run.

    python3 tools/sync_page_finder.py              # write
    python3 tools/sync_page_finder.py --check      # exit 1 if any page differs
    python3 tools/sync_page_finder.py --self-test  # planted controls

Run update_sri.py after a write: it stamps ?v= and integrity= on the new
script tag. --check ignores those two attributes.

Which pages: guides with an On this page box that run long enough that a
reader would rather search for a passage than scan for it, which in practice
means a few thousand words of article text. Add or remove a page in PAGES and
re-run. A page that picks the field up by being copied from a listed sibling
fails --check until it is listed or the tool takes the field out.

Kill chains are not listed: every page in breaches/ gets the field, so a new
chain copied from an existing one arrives with it, and one written from
scratch fails --check until the tool is run. A page in breaches/ without
exactly one kill chain is refused. tools/build_breach_decks.py leaves the
field out of the page text it hashes, so stamping it never makes a published
deck look stale.

Every visible word in the field sits in a `no-glossary` span or an attribute,
so tools/crosslink_pages.py never links a glossary term inside it.
--self-test runs the real cross-linker over the field to prove it.

Standard library only.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PAGES = [
    "ai-learning.html",
    "ai-ml-security.html",
    "api-security.html",
    "aws-security.html",
    "azure-security.html",
    "backup-dr.html",
    "breach-lessons.html",
    "ci-cd.html",
    "cloud-breach-year-in-review-2025.html",
    "cloud-breach-year-in-review-2026-h1.html",
    "cloud-deployment.html",
    "cloud-pentesting.html",
    "cloud-security-appsec-engineer.html",
    "cloud-security-architect.html",
    "cloud-security-careers.html",
    "cloud-security-cnapp-analyst.html",
    "cloud-security-comparison.html",
    "cloud-security-customer-success-engineer.html",
    "cloud-security-degree-programs.html",
    "cloud-security-detection-engineer.html",
    "cloud-security-engineer.html",
    "cloud-security-grc-engineer.html",
    "cloud-security-iam-architect.html",
    "cloud-security-incident-responder.html",
    "cloud-security-interview-questions.html",
    "cloud-security-penetration-tester.html",
    "cloud-security-platform-engineer.html",
    "cloud-security-sales-engineer.html",
    "cloud-soc.html",
    "cnapp-to-ai-app.html",
    "compliance-frameworks.html",
    "containers.html",
    "data-security.html",
    "detection-engineering.html",
    "gcp-security.html",
    "github-actions.html",
    "grc.html",
    "howto/azure-policy.html",
    "howto/cel-policy-expressions.html",
    "howto/cloud-custodian.html",
    "howto/cloud-native-log-queries.html",
    "howto/crowdstrike-logscale.html",
    "howto/datadog-cloud-siem.html",
    "howto/elastic-esql-eql.html",
    "howto/falco-rules.html",
    "howto/iam-policy-languages.html",
    "howto/kusto-kql.html",
    "howto/kyverno.html",
    "howto/opa-rego.html",
    "howto/osquery-and-velociraptor.html",
    "howto/oval-and-scap.html",
    "howto/panther-python-detections.html",
    "howto/python-cloud-sdks.html",
    "howto/semgrep-rules.html",
    "howto/sigma-and-yara.html",
    "howto/splunk-spl.html",
    "howto/sql-for-security-data-lakes.html",
    "howto/sumo-logic-queries.html",
    "howto/yara-l.html",
    "iam.html",
    "incident-response.html",
    "kubernetes.html",
    "landing-zones.html",
    "network-security.html",
    "saas-security.html",
    "serverless.html",
    "service-mesh-security.html",
    "terraform.html",
    "threat-modeling.html",
    "threat-research.html",
    "vendor-landscape.html",
    "vulnerability-management.html",
    "what-practitioners-think-about-ai-security.html",
    "what-practitioners-think-about-vulnerability-management.html",
    "zero-trust.html",
]

KILL_CHAIN_DIR = "breaches/"

START = "<!-- page-finder -->"
END = "<!-- /page-finder -->"

# The field, before indentation. The status line is a live region that stays
# rendered (an empty one takes no space), because a live region inside a
# display:none parent is not announced when it changes.
FINDER = [
    START,
    '<div class="page-finder" role="search">',
    '    <label for="page-finder-input" class="visually-hidden"><span class="no-glossary">Find on this page</span></label>',
    '    <div class="search-wrapper">',
    '        <input type="search" class="page-finder-input" id="page-finder-input" placeholder="Find on this page"'
    ' autocomplete="off" spellcheck="false" enterkeyhint="search">',
    "    </div>",
    '    <p class="page-finder-status"><span class="page-finder-count" role="status"></span>'
    ' <button type="button" class="page-finder-step page-finder-prev is-hidden" aria-label="Previous match"'
    ' title="Previous match (Shift+Enter)"><span aria-hidden="true">&uarr;</span></button>'
    ' <button type="button" class="page-finder-step page-finder-next is-hidden" aria-label="Next match"'
    ' title="Next match (Enter)"><span aria-hidden="true">&darr;</span></button></p>',
    "</div>",
    END,
]

SCRIPT = '<script src="/page-finder.js" defer></script>'

BLOCK_RE = re.compile(r"\n[ \t]*" + re.escape(START) + r".*?" + re.escape(END), re.S)
# The tag as update_sri.py leaves it: ?v= on the URL and integrity= last.
SCRIPT_RE = re.compile(r'\n[ \t]*<script src="/page-finder\.js(?:\?v=[0-9a-f]+)?" defer(?: integrity="[^"]*")?></script>')
TOC_HEAD_RE = re.compile(r'<div class="toc"[^>]*>\s*<(h[23])\b[^>]*>.*?</\1>', re.S)
KILL_CHAIN_RE = re.compile(r'<div class="kill-chain"[^>]*>')
MAIN_JS_RE = re.compile(r'^([ \t]*)<script src="/main\.js[^>]*>\s*</script>', re.M)


def is_kill_chain(rel: str) -> bool:
    return rel.startswith(KILL_CHAIN_DIR) and rel.endswith(".html")


def listed(rel: str) -> bool:
    return rel in PAGES or is_kill_chain(rel)


def _indent_at(text: str, pos: int) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    return re.match(r"[ \t]*", text[line_start:]).group(0)


def render(page: str, rel: str) -> str:
    """page with the field and script in place when rel is listed, and with
    neither when it is not. Raises ValueError when a listed page has no single
    place to put them."""
    out = BLOCK_RE.sub("", page)
    if not listed(rel):
        return SCRIPT_RE.sub("", out)

    if is_kill_chain(rel):
        chains = list(KILL_CHAIN_RE.finditer(out))
        if len(chains) != 1:
            raise ValueError(f"{rel}: needs exactly one <div class=\"kill-chain\"> (found {len(chains)})")
        # On lines of its own above the chain's, at the chain's indent. A
        # chain that shares its line with other markup is refused rather than
        # split.
        at = out.rfind("\n", 0, chains[0].start()) + 1
        indent = _indent_at(out, chains[0].start())
        if out[at:chains[0].start()] != indent:
            raise ValueError(f"{rel}: <div class=\"kill-chain\"> must start its own line")
        block = "".join(f"{indent}{ln}\n" for ln in FINDER)
    else:
        heads = list(TOC_HEAD_RE.finditer(out))
        if len(heads) != 1:
            raise ValueError(f"{rel}: needs exactly one On this page box with a heading (found {len(heads)})")
        at = heads[0].end()
        indent = _indent_at(out, heads[0].start(1))
        block = "".join(f"\n{indent}{ln}" for ln in FINDER)
    out = out[:at] + block + out[at:]

    if not SCRIPT_RE.search(out):
        mains = list(MAIN_JS_RE.finditer(out))
        if len(mains) != 1:
            raise ValueError(f"{rel}: needs exactly one main.js script tag (found {len(mains)})")
        m = mains[0]
        out = out[: m.end()] + f"\n{m.group(1)}{SCRIPT}" + out[m.end():]
    return out


def html_files(root: Path) -> list[str]:
    """Every tracked .html file outside tools/, as repo-relative paths. Under
    git, ls-files keeps out the worktrees under .claude/; elsewhere (the
    self-test's temporary tree) every file counts."""
    try:
        out = subprocess.run(["git", "ls-files", "*.html"], cwd=root, capture_output=True,
                             text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        out = [str(p.relative_to(root)) for p in root.rglob("*.html")]
    return sorted(f for f in out if not f.startswith("tools/"))


def sync(root: Path, check: bool) -> int:
    rels = html_files(root)
    missing = [p for p in PAGES if p not in rels]
    if missing:
        print("listed pages that do not exist:", ", ".join(missing))
        return 1
    stale = []
    count = sum(1 for rel in rels if listed(rel))
    for rel in rels:
        path = root / rel
        page = path.read_text(encoding="utf-8")
        if not listed(rel) and START not in page and "/page-finder.js" not in page:
            continue
        try:
            new = render(page, rel)
        except ValueError as exc:
            print(exc)
            return 1
        if new != page:
            stale.append(rel)
            if not check:
                path.write_text(new, encoding="utf-8")
    if check:
        if stale:
            print("page finder out of step on:", ", ".join(stale))
            print("run: python3 tools/sync_page_finder.py && python3 update_sri.py")
            return 1
        print(f"page finder current on {count} pages ({len(PAGES)} guides, {count - len(PAGES)} kill chains)")
        return 0
    print(f"page finder: {len(stale)} page(s) updated, on {count} pages")
    return 0


def self_test() -> int:
    failures: list[str] = []

    def expect(cond: bool, what: str) -> None:
        print(("ok   " if cond else "FAIL ") + what)
        if not cond:
            failures.append(what)

    first_page = PAGES[0]
    page = ('<html><body><main class="container contribute-article">\n'
            '        <div class="toc">\n            <h2>On this page</h2>\n            <ol>\n'
            '                <li><a href="#a">A</a></li>\n            </ol>\n        </div>\n'
            '        <section id="a"><h2>A</h2><p>Text</p></section>\n    </main>\n'
            '    <script src="/main.js?v=1" integrity="sha384-x"\n        defer></script>\n</body></html>\n')
    one_line = page.replace('<div class="toc">\n            <h2>On this page</h2>\n            <ol>',
                            '<div class="toc"><h2>On this page</h2><ol>')
    assert one_line != page, "plant did nothing"
    chain = ('<html><body><main class="kc-main kc-page">\n'
             '  <div class="inc-header"><h2>T</h2>\n  </div>\n'
             '  <div class="kill-chain">\n\n'
             '    <div class="phase-lbl">Recon</div>\n'
             '    <div class="kc-step"><p>Text</p></div>\n  </div>\n    </main>\n'
             '    <script src="/main.js?v=1" integrity="sha384-x"\n        defer></script>\n</body></html>\n')
    kc = KILL_CHAIN_DIR + "zz-chain.html"

    with tempfile.TemporaryDirectory() as t:
        root = Path(t)
        for rel in PAGES:
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            (root / rel).write_text(page, encoding="utf-8")
        (root / "other.html").write_text(page, encoding="utf-8")
        (root / kc).parent.mkdir(parents=True, exist_ok=True)
        (root / kc).write_text(chain, encoding="utf-8")

        expect(sync(root, check=True) == 1, "a listed page without the field fails --check")
        expect(sync(root, check=False) == 0 and sync(root, check=True) == 0, "--check passes after a write")
        first = (root / first_page).read_text(encoding="utf-8")
        sync(root, check=False)
        expect((root / first_page).read_text(encoding="utf-8") == first, "a second write changes nothing")
        expect(first.count(START) == 1 and first.count('id="page-finder-input"') == 1, "one field per page")
        expect(first.index("<h2>On this page</h2>") < first.index(START) < first.index("<ol>"),
               "the field sits between the box's heading and its list")
        expect("\n            " + START in first, "the field takes the heading's indent")
        expect(first.count(SCRIPT) == 1 and first.index("/main.js") < first.index(SCRIPT),
               "one script tag, after main.js")
        expect((root / "other.html").read_text(encoding="utf-8") == page, "an unlisted page is left alone")

        got = (root / kc).read_text(encoding="utf-8")
        expect(got.count(START) == 1 and got.count(SCRIPT) == 1, "a kill chain, though unlisted, gets the field")
        expect(got.index("</div>\n") < got.index(START) < got.index('<div class="kill-chain">'),
               "the field sits between the incident header and the kill chain")
        expect("\n  " + START + "\n" in got and "\n  " + END + "\n  <div class=\"kill-chain\">" in got,
               "the field takes the chain's indent, on lines of its own")
        shared = chain.replace('  <div class="kill-chain">', '  <p>x</p><div class="kill-chain">')
        assert shared != chain, "plant did nothing"
        (root / kc).write_text(shared, encoding="utf-8")
        expect(sync(root, check=False) == 1 and (root / kc).read_text(encoding="utf-8") == shared,
               "a chain sharing its line is refused and left as it was")
        (root / kc).write_text(chain, encoding="utf-8")
        sync(root, check=False)

        stamped = first.replace(SCRIPT, '<script src="/page-finder.js?v=0a1b2c3d" defer integrity="sha384-q"></script>')
        (root / first_page).write_text(stamped, encoding="utf-8")
        expect(sync(root, check=True) == 0, "update_sri's ?v= and integrity= do not fail --check")

        (root / first_page).write_text(first.replace("Find on this page", "Find"), encoding="utf-8")
        expect(sync(root, check=True) == 1, "a hand-edited field fails --check")
        sync(root, check=False)

        (root / "other.html").write_text(stamped, encoding="utf-8")
        expect(sync(root, check=True) == 1, "an unlisted page carrying the field fails --check")
        sync(root, check=False)
        expect((root / "other.html").read_text(encoding="utf-8") == page,
               "the write takes the field and script out of an unlisted page")

        (root / first_page).write_text(one_line, encoding="utf-8")
        sync(root, check=False)
        squeezed = (root / first_page).read_text(encoding="utf-8")
        sync(root, check=False)
        expect((root / first_page).read_text(encoding="utf-8") == squeezed and squeezed.count(START) == 1,
               "a box written on one line takes the field, and a second write changes nothing")

        two = page.replace('<section id="a">', '<div class="toc"><h2>More</h2></div>\n<section id="a">')
        assert two != page, "plant did nothing"
        (root / first_page).write_text(two, encoding="utf-8")
        expect(sync(root, check=False) == 1, "a page with two boxes is refused")
        (root / first_page).write_text(page, encoding="utf-8")
        expect(sync(root, check=False) == 0, "control: the same tree with one box is accepted")

        chainless = chain.replace('<div class="kill-chain">', '<div class="chain">')
        assert chainless != chain, "plant did nothing"
        (root / kc).write_text(chainless, encoding="utf-8")
        expect(sync(root, check=False) == 1, "a page in breaches/ without a kill chain is refused")

    # The cross-linker must leave the field alone, judged with the real
    # glossary: every glossary key placed in the label would be linked
    # somewhere if the label were outside a skip zone.
    try:
        sys.path.insert(0, str(REPO / "tools"))
        import crosslink_pages as cl
        import html as htmllib
        keys_to_slug, keys = cl.load_glossary_terms()
        patterns = cl.build_term_regexes(keys)
        words = htmllib.escape(" ".join(keys), quote=False)
        region = "\n".join(FINDER).replace("Find on this page</span>", words + "</span>")
        assert region != "\n".join(FINDER), "plant did nothing"
        masked, _ = cl.mask_skip_zones(region)
        _, linked = cl.link_text_segments(masked, patterns, keys_to_slug, "")
        expect(not linked, "no glossary key is linked inside the field")
        masked, _ = cl.mask_skip_zones(f"<p>{words}</p>")
        _, control = cl.link_text_segments(masked, patterns, keys_to_slug, "")
        expect(bool(control), "control: the same words in a plain paragraph are linked")
    except Exception as exc:  # noqa: BLE001 - report, never pass silently
        expect(False, f"cross-linker check could not run: {exc!r}")

    print(f"\nself-test: {len(failures)} failure(s)")
    return 1 if failures else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[1].strip())
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="exit 1 if any page differs")
    mode.add_argument("--self-test", action="store_true", help="run the planted controls")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    return sync(REPO, check=args.check)


if __name__ == "__main__":
    sys.exit(main())
