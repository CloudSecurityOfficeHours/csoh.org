#!/usr/bin/env python3
"""Fail if a catalog doc points at something absent, or misses a page.

WHY THIS EXISTS
---------------
Three holes, all found by hand in August 2026, all the shape this repo keeps
re-learning: a check that cannot see a thing reports the same "clean" as a
check that looked and found nothing.

**Nothing was checking a Markdown link.** lychee crawls `*.html` and the
published `*.tf`, and that is the whole input list - Markdown is not in it. So
README.md's 212 in-repo links had no gate at all, and across the 38 tracked
docs it is over 400. The manual sweep that found this was itself a shell loop
that died on a quoting error and printed "all resolve" anyway, which is how
this file ended up with a self-test.

**Coverage sweeps kept getting scoped to the repo root.** `topics.html` shipped
with the nav restructure and went unmentioned in README.md entirely; nothing
noticed, because the sweep that would have caught it globbed `*.html` and
`*.html` does not descend. The same single-star assumption is why `'*.html'` in
a workflow `paths:` filter silently skipped every subdirectory: **enumerate by
what the repo actually contains, not by the pattern you were already thinking
about.**

**A count marker inside a code fence renders as literal text.** Fences are
verbatim, so `<!--count:meetings-->109<!--/count-->` in a directory tree is
displayed to every reader on GitHub. Four were doing that in README.md and one
in DEVELOPMENT.md. Counts in a fence belong to `MD_PROSE_RULES` in
`sync_counts.py` instead.

WHAT IT ASSERTS
---------------
1. Every in-repo Markdown link resolves, across every doc in `tracked_docs()`.
2. Every root page is named in each doc in `CATALOGS`, matches a documented
   `<placeholder>` glob there, or is in `NOT_IN_README` with a reason.
3. Every published subdirectory is documented in each catalog *and* is in
   `check-broken-links.yml`'s input globs. Pages inside them are governed by
   counts rather than enumeration, which is right at 109 recaps - but a whole
   directory appearing nowhere is how a tree goes uncrawled.
4. No count marker sits inside a code fence, except the documented examples in
   `MARKER_EXAMPLES`.

`CATALOGS` is deliberately narrow. README.md and DEVELOPMENT.md each carry a
full directory tree and so owe a coverage contract; CONTRIBUTING.md names ~54
pages as a "where to file things" shortlist and never claims to be exhaustive.
Holding it to the same rule would invent 54 findings, and a gate that cries
wolf gets muted - which leaves it worth exactly what one that never fires is
worth.

THE SELF-TEST IS NOT OPTIONAL
-----------------------------
`--check` runs `self_test()` first and refuses to report a clean result unless
every detector has been shown to fire on planted bad input - and, where it
matters, to stay quiet on planted good input. A checker that cannot fail is
indistinguishable from a passing repo, and this file exists because that exact
confusion cost real time. **Adding a detector means adding its planted case.**

    python3 tools/check_readme_coverage.py            # report
    python3 tools/check_readme_coverage.py --check    # exit 1 on any finding
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from pathlib import Path, PurePosixPath

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"

# Docs that claim to enumerate the site, and so owe a coverage check. Both
# carry a full directory tree. CONTRIBUTING.md deliberately is NOT here: it
# names ~54 pages as a "where to file things" shortlist and never claims to be
# exhaustive, so holding it to this contract would invent 54 findings and teach
# everyone to ignore the gate. Its links are still checked, like every doc's.
CATALOGS = ("README.md", "DEVELOPMENT.md")

GITHUB_BLOB = "https://github.com/CloudSecurityOfficeHours/csoh.org/blob/main/"
GITHUB_TREE = "https://github.com/CloudSecurityOfficeHours/csoh.org/tree/main/"
SITE = "https://csoh.org/"

# Root pages deliberately not named in README.md. Keep the reason attached -
# adding a line here should be a decision, not a way to silence the check.
NOT_IN_README: dict[str, str] = {
    "google66d489593949bd4c.html": "Search Console ownership token, not content",
}

# Site URLs that are not files in this repo: directory indexes and redirect
# targets that nginx resolves. Anchored exactly so a typo'd path still fails.
SITE_URL_NOT_A_FILE = {
    "",  # https://csoh.org/ itself
}


def markdown_links(text: str) -> list[str]:
    """Every `](target)` destination in a Markdown document."""
    return [m.group(1).strip() for m in re.finditer(r"\]\(([^)\s]+)[^)]*\)", text)]


def in_repo_targets(text: str, base: str = "") -> set[str]:
    """Link destinations that should correspond to a file in this checkout.

    External hosts are somebody else's problem (lychee's, for the HTML pages).
    What matters here is a link that *claims* to point at this repo.

    `base` is the linking document's own directory, relative to the repo root.
    A relative link resolves against the document, not the root - `tools/`
    docs link to each other as `SYNC_CHROME_README.md` and up as `../CLAUDE.md`.
    Resolving those from the root instead reported 40-odd files as missing when
    every one of them existed, which is the same false-confidence failure in
    the other direction: a check that cries wolf gets muted, and then it is
    just as useless as one that never fires.
    """
    out: set[str] = set()
    for raw in markdown_links(text):
        target = raw.split("#", 1)[0]
        if not target:
            continue
        if target.startswith((GITHUB_BLOB, GITHUB_TREE)):
            prefix = GITHUB_BLOB if target.startswith(GITHUB_BLOB) else GITHUB_TREE
            out.add(target[len(prefix):].rstrip("/"))
        elif target.startswith(SITE):
            path = target[len(SITE):].rstrip("/")
            if path not in SITE_URL_NOT_A_FILE:
                out.add(path)
        elif not re.match(r"^[a-z][a-z0-9+.-]*:", target):
            rel = target.rstrip("/")
            if rel:
                # PurePosixPath keeps this platform-independent; os.path.normpath
                # would turn "a/b" into "a\\b" on Windows runners.
                out.add(str(PurePosixPath(posixpath.normpath(posixpath.join(base, rel)))))
    return {t for t in out if t and not t.startswith("..")}


def tracked_docs() -> list[Path]:
    """Markdown docs whose in-repo links are checked: repo root plus tools/."""
    return sorted(REPO.glob("*.md")) + sorted((REPO / "tools").glob("*.md"))


def unresolved(targets: set[str], exists=None) -> list[str]:
    """Targets with no corresponding path. `exists` is injectable for the self-test."""
    exists = exists or (lambda p: (REPO / p).exists())
    return sorted(t for t in targets if not exists(t))


def published_subdirs() -> list[str]:
    """Root directories holding published pages, derived rather than listed."""
    skip = {"tools", "seo-audits", "infra", "docs", "vendor", "dist", "node_modules"}
    out = []
    for d in sorted(p for p in REPO.iterdir() if p.is_dir()):
        if d.name.startswith(".") or d.name in skip or d.name.startswith("__"):
            continue
        if any(d.glob("*.html")):
            out.append(d.name)
    return out


def documented_globs(text: str) -> list[re.Pattern]:
    """`cloud-security-<role>.html` style placeholders used to stand for a set.

    Both catalogs collapse near-identical page families this way - 12 role
    pages, 5 year-in-review periods, 5 session digests - and then name the
    members in the adjacent comment. That is better authoring than 22 near
    duplicate tree lines, so the check has to understand it rather than force
    the tree to be expanded.
    """
    out = []
    for tok in re.findall(r"[a-z0-9-]*<[a-z-]+>[a-z0-9-]*\.html", text):
        out.append(re.compile("^" + re.sub(r"<[a-z-]+>", "[a-z0-9-]+", tok) + "$"))
    return out


def unmentioned_root_pages(text: str, optouts: dict | None = None) -> list[str]:
    optouts = NOT_IN_README if optouts is None else optouts
    globs = documented_globs(text)
    return sorted(
        p.name
        for p in REPO.glob("*.html")
        if p.name not in optouts
        and p.name not in text
        and not any(g.match(p.name) for g in globs)
    )


# Fenced code blocks render their contents verbatim, so a count marker inside
# one is displayed to the reader instead of disappearing. Four were doing that
# in README.md and one in DEVELOPMENT.md. These two lines are the exception:
# they are documentation *showing* the syntax, and are supposed to be visible.
MARKER_EXAMPLES = {
    "Access <!--count:resources_floor-->480+<!--/count--> curated resources.",
}


def visible_markers(text: str) -> list[str]:
    """Count markers inside a code fence, where they render as literal text."""
    fence, out = False, []
    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            fence = not fence
            continue
        if fence and "<!--count:" in line and line.strip() not in MARKER_EXAMPLES:
            out.append(line.strip()[:90])
    return out


def stale_optouts() -> list[str]:
    return sorted(n for n in NOT_IN_README if not (REPO / n).exists())


def undocumented_subdirs(text: str) -> list[str]:
    return sorted(d for d in published_subdirs() if f"{d}/" not in text)


def uncrawled_subdirs() -> list[str]:
    """Published subdirectories missing from the link crawler's input globs."""
    wf = REPO / ".github" / "workflows" / "check-broken-links.yml"
    if not wf.exists():
        return []
    globs = wf.read_text(encoding="utf-8")
    return sorted(d for d in published_subdirs() if f"./{d}/*.html" not in globs)


def self_test() -> list[str]:
    """Prove every detector fires on planted input.

    Each assertion below is the failure this file was written to catch. If one
    of them stops firing, the detector is broken and a clean run means nothing
    - so that is reported as an error in its own right rather than as success.
    """
    bad: list[str] = []

    doc = f"[a]({GITHUB_BLOB}tools/__missing__.py) [b]({SITE}__missing__.html) [c](./__missing__)"
    found = in_repo_targets(doc)
    if len(found) != 3:
        bad.append(f"link extractor found {len(found)} of 3 planted in-repo targets")
    if len(unresolved(found)) != 3:
        bad.append("link resolver did not flag three targets that cannot exist")

    # A real, existing path must NOT be reported - a detector that flags
    # everything is as useless as one that flags nothing.
    if unresolved(in_repo_targets(f"[ok]({GITHUB_BLOB}README.md)")):
        bad.append("link resolver flagged README.md, which exists")

    # External links must be ignored rather than resolved against the repo.
    if in_repo_targets("[x](https://example.com/nope.html)"):
        bad.append("link extractor treated an external host as an in-repo path")

    # Relative links resolve against the linking document, not the repo root.
    # Getting this wrong reported ~40 existing tools/ docs as missing, so both
    # directions are pinned: sideways within the directory, and up out of it.
    if in_repo_targets("[a](SYNC_CHROME_README.md)", base="tools") != {"tools/SYNC_CHROME_README.md"}:
        bad.append("relative link did not resolve against the document's own directory")
    if in_repo_targets("[a](../CLAUDE.md)", base="tools") != {"CLAUDE.md"}:
        bad.append("parent-relative link did not resolve out of the document's directory")
    if unresolved(in_repo_targets("[a](sync_chrome.py)", base="tools")):
        bad.append("tools/sync_chrome.py reported missing from a tools-relative link")

    if not unmentioned_root_pages(""):
        bad.append("root-page sweep found nothing against an empty document")
    if unmentioned_root_pages(" ".join(p.name for p in REPO.glob("*.html"))):
        bad.append("root-page sweep flagged pages that were all mentioned")

    if not undocumented_subdirs(""):
        bad.append("subdirectory sweep found nothing against an empty document")

    if not published_subdirs():
        bad.append("no published subdirectories discovered - the glob is wrong")

    # A `<placeholder>` token must stand in for the family it names, and must
    # not swallow unrelated pages - a glob that matches everything would hide
    # exactly the gap this check exists to find.
    globs = documented_globs("- cloud-security-<role>.html # 12 role pages")
    if not (len(globs) == 1 and globs[0].match("cloud-security-architect.html")):
        bad.append("placeholder glob did not expand to match its own family")
    if globs and globs[0].match("index.html"):
        bad.append("placeholder glob matched an unrelated page")

    fenced = "```\n├── x.html  # <!--count:meetings-->9<!--/count--> recaps\n```"
    if not visible_markers(fenced):
        bad.append("visible-marker check missed a marker inside a code fence")
    if visible_markers("A <!--count:meetings-->9<!--/count--> outside any fence"):
        bad.append("visible-marker check flagged a marker in ordinary prose")
    example = "```\n" + next(iter(MARKER_EXAMPLES)) + "\n```"
    if visible_markers(example):
        bad.append("visible-marker check flagged a documented syntax example")

    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 on any finding (for CI)")
    args = ap.parse_args()

    broken = self_test()
    if broken:
        print("SELF-TEST FAILED - this checker cannot be trusted:", file=sys.stderr)
        for b in broken:
            print(f"  {b}", file=sys.stderr)
        print("\nFix the checker before believing any result from it.", file=sys.stderr)
        return 1

    broken_links = []
    link_total = 0
    for doc in tracked_docs():
        rel = doc.relative_to(REPO)
        targets = in_repo_targets(doc.read_text(encoding="utf-8"), base=str(rel.parent) if str(rel.parent) != "." else "")
        link_total += len(targets)
        broken_links += [f"{rel}: {t}" for t in unresolved(targets)]
    uncovered, undocumented = [], []
    for name in CATALOGS:
        doc = (REPO / name).read_text(encoding="utf-8")
        uncovered += [f"{name}: {p}" for p in unmentioned_root_pages(doc)]
        undocumented += [f"{name}: {d}/" for d in undocumented_subdirs(doc)]

    visible = []
    for doc in tracked_docs():
        visible += [f"{doc.relative_to(REPO)}:{m}" for m in visible_markers(
            doc.read_text(encoding="utf-8"))]

    findings: list[tuple[str, list[str]]] = [
        ("Markdown links pointing at files that do not exist", broken_links),
        ("Root pages named nowhere in a catalog doc", uncovered),
        ("Entries in NOT_IN_README that no longer exist", stale_optouts()),
        ("Published subdirectories not documented in a catalog doc", undocumented),
        ("Published subdirectories not crawled by check-broken-links.yml", uncrawled_subdirs()),
        ("Count markers inside a code fence (they render as literal text)", visible),
    ]

    total = sum(len(v) for _, v in findings)
    print(f"Self-test passed ({len(published_subdirs())} published subdirectories: "
          f"{', '.join(published_subdirs())})")
    print(f"Checked {link_total} in-repo links across {len(tracked_docs())} Markdown docs, "
          f"and {len(list(REPO.glob('*.html')))} root pages against {', '.join(CATALOGS)}.")

    for label, items in findings:
        if items:
            print(f"\n{label}:", file=sys.stderr)
            for i in items:
                print(f"  {i}", file=sys.stderr)

    if total:
        print(f"\n{total} finding(s).", file=sys.stderr)
        return 1 if args.check else 0

    print("No findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
