#!/usr/bin/env python3
"""Fail if README.md points at something that is not there, or misses a page.

WHY THIS EXISTS
---------------
Two holes, both found by hand in August 2026, both the shape this repo keeps
re-learning: a check that cannot see a thing reports the same "clean" as a
check that looked and found nothing.

**Nothing was checking README.md's links.** lychee crawls `*.html` and the
published `*.tf`, and that is the whole input list - Markdown is not in it. So
the 200-plus links in README.md, most of them pointing at files in this repo,
had no gate at all. The manual sweep that found this was itself a shell loop
that died on a quoting error and printed "all resolve" anyway, which is how
this file ended up with a self-test.

**Coverage sweeps kept getting scoped to the repo root.** `topics.html` shipped
with the nav restructure and went unmentioned in README.md entirely; nothing
noticed, because the sweep that would have caught it globbed `*.html` and
`*.html` does not descend. The same single-star assumption is why `'*.html'` in
a workflow `paths:` filter silently skipped every subdirectory, and it is worth
stating plainly: **enumerate by what the repo actually contains, not by the
pattern you were already thinking about.**

WHAT IT ASSERTS
---------------
1. Every link in README.md that points inside this repo resolves to a real
   file - GitHub blob URLs, `https://csoh.org/` page URLs, and relative paths
   alike.
2. Every root-level page is named in README.md, or is listed in
   `NOT_IN_README` with a reason.
3. Every published subdirectory is documented in README.md *and* crawled by
   `check-broken-links.yml`. Individual pages inside them are governed by
   counts rather than enumeration, which is the right call at 109 recaps - but
   the directory itself appearing nowhere is how a whole tree goes unchecked.

THE SELF-TEST IS NOT OPTIONAL
-----------------------------
`--check` runs `self_test()` first and refuses to report a clean result unless
every detector has been shown to fire on planted bad input. A checker that
cannot fail is indistinguishable from a passing repo, and this file exists
because that exact confusion cost real time twice.

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


def unmentioned_root_pages(text: str) -> list[str]:
    return sorted(
        p.name
        for p in REPO.glob("*.html")
        if p.name not in NOT_IN_README and p.name not in text
    )


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

    text = README.read_text(encoding="utf-8")
    broken_links = []
    link_total = 0
    for doc in tracked_docs():
        rel = doc.relative_to(REPO)
        targets = in_repo_targets(doc.read_text(encoding="utf-8"), base=str(rel.parent) if str(rel.parent) != "." else "")
        link_total += len(targets)
        broken_links += [f"{rel}: {t}" for t in unresolved(targets)]
    findings: list[tuple[str, list[str]]] = [
        ("Markdown links pointing at files that do not exist", broken_links),
        ("Root pages named nowhere in README.md", unmentioned_root_pages(text)),
        ("Entries in NOT_IN_README that no longer exist", stale_optouts()),
        ("Published subdirectories not documented in README.md", undocumented_subdirs(text)),
        ("Published subdirectories not crawled by check-broken-links.yml", uncrawled_subdirs()),
    ]

    total = sum(len(v) for _, v in findings)
    print(f"Self-test passed ({len(published_subdirs())} published subdirectories: "
          f"{', '.join(published_subdirs())})")
    print(f"Checked {link_total} in-repo links across {len(tracked_docs())} Markdown "
          f"docs, and {len(list(REPO.glob('*.html')))} root pages against README.md.")

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
