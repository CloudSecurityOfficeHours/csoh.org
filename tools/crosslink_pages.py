#!/usr/bin/env python3
"""Cross-link glossary terms across content pages.

For each content page, finds the first occurrence of each glossary term
and wraps it in <a class="glossary-link" href="glossary.html#term-...">.

Skip zones (no linking inside any of these):
  - existing <a>...</a> elements
  - <code>, <pre>, <script>, <style>
  - <h1>-<h6>
  - <header>, <footer>, <nav>
  - HTML comments
  - HTML attribute values
  - JSON-LD blocks

Idempotent: existing <a class="glossary-link" href="glossary.html#..."> links
are stripped and rebuilt on every run, so changing the rules or adding
glossary terms is safe.

Per-page rules:
  - Only the first occurrence per page (across the whole body) is linked,
    to keep prose readable.
  - Terms in DENYLIST (overlap with ordinary English) are skipped, just as
    in crosslink_glossary.py.
  - The glossary page itself is not processed (it has its own script).
"""

from __future__ import annotations

import re
import sys
from html import unescape
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GLOSSARY_FILE = REPO_ROOT / "glossary.html"

# Pages we cross-link. The glossary is excluded (its own script handles it),
# and pages with no useful prose (404, sitemap, login forms) are excluded too.
TARGET_PAGES = [
    "index.html",
    "resources.html",
    "ctfs.html",
    "threat-research.html",
    "breach-timeline.html",
    "conferences.html",
    "meetings.html",
    "presentations.html",
    "sessions.html",
    "faq.html",
    "rss.html",
    "chat-resources.html",
    "what-is-cloud-security.html",
    "learning-path.html",
    "cloud-security-best-practices.html",
    "shared-responsibility-model.html",
    "cspm-vs-cnapp.html",
    "cloud-security-certifications.html",
    "github-actions.html",
    "terraform.html",
    "version-control.html",
    "kevin-mitnick.html",
    "contribute.html",
    "contribute-resources.html",
    "code-of-conduct.html",
    "privacy.html",
    "security-policy.html",
    "about-shawn-nunley.html",
    # May 2026 build-out: discipline & topic reference pages
    "iam.html",
    "zero-trust.html",
    "network-security.html",
    "data-security.html",
    "vulnerability-management.html",
    "api-security.html",
    "saas-security.html",
    "backup-dr.html",
    "threat-modeling.html",
    "service-mesh-security.html",
    "detection-engineering.html",
    "incident-response.html",
    "cloud-pentesting.html",
    "grc.html",
    "compliance-frameworks.html",
    "ai-ml-security.html",
    "ai-learning.html",
    "landing-zones.html",
    "containers.html",
    "kubernetes.html",
    "serverless.html",
    "ci-cd.html",
    "cloud-soc.html",
    # Per-cloud SEO hubs
    "aws-security.html",
    "azure-security.html",
    "gcp-security.html",
    "cloud-security-comparison.html",
    # Vendor directory
    "vendor-landscape.html",
    # Behind-the-scenes
    "cloud-deployment.html",
    # May 2026: cloud-security career & role deep-dive pages
    "cloud-security-careers.html",
    "cloud-security-engineer.html",
    "cloud-security-architect.html",
    "cloud-security-appsec-engineer.html",
    "cloud-security-cnapp-analyst.html",
    "cloud-security-detection-engineer.html",
    "cloud-security-grc-engineer.html",
    "cloud-security-iam-architect.html",
    "cloud-security-incident-responder.html",
    "cloud-security-penetration-tester.html",
    "cloud-security-platform-engineer.html",
    "cloud-security-sales-engineer.html",
    "cloud-security-customer-success-engineer.html",
    # Registered August 2026. These shipped without being added here, so they
    # carried zero glossary cross-links while every comparable page carried
    # 45+. Nothing errors when a page is missing from this list - it is simply
    # never visited - so check this file whenever a top-level page is added.
    "mcp-security.html",
    "non-human-identity.html",
    "what-practitioners-think.html",
    "what-practitioners-think-about-ai-security.html",
    "what-practitioners-think-about-security-conferences.html",
    "what-practitioners-think-about-security-regulation.html",
    "what-practitioners-think-about-supply-chain-security.html",
    "what-practitioners-think-about-vulnerability-management.html",
    # Also registered August 2026, same oversight as the block above. These 23
    # had accumulated since the list was last reconciled; breach-lessons.html
    # alone is ~9,500 words and carried a single glossary link.
    "about.html",
    "breach-lessons.html",
    "breaking-into-cloud-security.html",
    "what-breaking-into-cloud-security-really-takes.html",
    "cloud-breach-year-in-review.html",
    "cloud-breach-year-in-review-2021-2022.html",
    "cloud-breach-year-in-review-2023.html",
    "cloud-breach-year-in-review-2024.html",
    "cloud-breach-year-in-review-2025.html",
    "cloud-breach-year-in-review-2026-h1.html",
    "cloud-security-degree-programs.html",
    "cloud-security-home-lab.html",
    "cloud-security-interview-questions.html",
    "cloud-security-portfolio-projects.html",
    "cloud-security-reading-list.html",
    "cloud-security-resume-guide.html",
    "cnapp-vs-xdr.html",
    "cspm-vs-cwpp.html",
    "community.html",
    "how-csoh-org-is-secured.html",
    "mentorship.html",
    "present.html",
    "speakers.html",
]

# Every other root-level page is out on purpose, so that a page missing from
# TARGET_PAGES is a decision rather than an oversight. To keep it that way,
# tools/check_crosslink_coverage.py fails if a root page is in neither list.
#
#   glossary.html                 crosslink_glossary.py owns it (intra-page links)
#   news.html                     rebuilt by update_news.py every 3h; links would be wiped
#   search.html                   a JS search UI, ~40 words of prose
#   403.html / 404.html           error pages, no prose worth linking
#   google66d489593949bd4c.html   Search Console verification stub
DELIBERATELY_UNLINKED = {
    "glossary.html",
    "news.html",
    "search.html",
    "403.html",
    "404.html",
    "google66d489593949bd4c.html",
}

# Subdirectory pages (per-breach, per-meeting) are auto-discovered rather
# than listed individually - there are ~100 meeting pages and the set
# grows as new sessions get added. Subdir pages need a "../" prefix to reach
# glossary.html; the GLOSSARY_LINK_HREF_PREFIX is computed per-file based
# on each path's depth (see crosslink_page below).
SUBDIR_PATTERNS = [
    "breaches/*.html",
    "meetings/*.html",
]

# Single-word terms common enough in English that linking them is more
# distracting than helpful. This is a superset of crosslink_glossary.py's
# denylist - it adds words (cloud, data, policy, ...) that recur constantly in
# page prose where crosslink_glossary.py only runs over the glossary itself.
DENYLIST = {
    # The standards body, not a concept. Every headword of the form
    # "ISO/IEC <number>" yields a bare "ISO" key, so without this the word
    # linked to whichever ISO entry sits earliest in the glossary (27001) even
    # when the sentence was about 27017 or 42001. The full designations are
    # indexed as their own keys and match longest-first, so "ISO/IEC 42001"
    # still links correctly - it is only the bare word that is suppressed.
    "iso",
    "public",
    "private",
    "hybrid",
    "image",
    "baseline",
    "registry",
    "principal",
    "first",
    # Extras for content pages where these words appear constantly:
    "cloud",
    "data",
    "policy",
    "policies",
    "control",
    "controls",
    "secret",
    "secrets",
    "key",
    "keys",
    "log",
    "logs",
    "audit",
    "scope",
    "session",
    "sessions",
    "tag",
    "tags",
    "role",
    "roles",
    "user",
    "users",
    "account",
    "accounts",
    # False-positive single-word remnants extracted from compound entries
    # like "Blue / Red Team" or "Kev / Kevin" - link the full phrase only.
    "blue",
    "red",
    "purple",
    "kev",
    "agent",      # too generic in prose; Agent (LLM) usually rendered with caps
    "container",  # generic English usage
    "drift",      # configuration drift only meaningful with context
    "subnet",     # plain networking term, common
    "functions",  # also common English
    "vault",      # ambiguous: HashiCorp/Azure Key Vault depending on context
    "blast",      # only useful in "blast radius"
    "ad",         # shell `ad`, ambiguous
    "csp",        # cloud prose: usually Cloud Service Provider, not Content Security Policy
    "sp",         # "NIST SP" (Special Publication) collides with SP - Service Provider
    "soc",        # ambiguous: Security Operations Center vs the SOC 1/2/3 report family
}

# Sections of the file to skip wholesale (no links anywhere inside).
SKIP_BLOCK_TAGS = (
    # Skip the entire <head> - <title>, <meta>, JSON-LD <script>, OG tags etc.
    # never contain user-visible prose and must not have <a> tags inserted.
    # (Without this, text inside <title> and <meta description> gets linked.)
    "head",
    "header",
    "footer",
    "nav",
    "script",
    "style",
    "code",
    "pre",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    # An <a> inside a <button> is invalid HTML; skip button content entirely.
    "button",
    # <title> belongs to <head>, but defensive - in case <head> is malformed
    # or the linker is run on a fragment without <head>, still skip <title>.
    "title",
)

# Default href prefix for glossary cross-links (root-level pages).
# For pages in subdirectories (e.g. breaches/), we compute "../glossary.html#..."
# instead - see _glossary_prefix_for() below.
GLOSSARY_LINK_HREF_PREFIX = "glossary.html#"


def _glossary_prefix_for(rel_path: str) -> str:
    """Return the right href prefix for glossary cross-links, given the page's
    path relative to the repo root. A page at root uses 'glossary.html#...';
    a page in a one-level subdir like 'breaches/foo.html' needs
    '../glossary.html#...' so the link works from there."""
    depth = rel_path.count("/")
    return ("../" * depth) + "glossary.html#"


def _existing_link_pattern_for(prefix: str) -> re.Pattern[str]:
    """Strip-existing pattern needs to know which prefix to look for so we
    can re-link with a possibly different one. Used by unwrap_existing_links
    when called per-page."""
    return re.compile(
        rf'<a\s+class="glossary-link"\s+href="{re.escape(prefix)}[^"]+">([^<]+)</a>',
        re.IGNORECASE,
    )


def slugify(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return "term-" + text if text else "term-unknown"


def derive_keys(dt_inner_html: str) -> list[str]:
    """Same logic as crosslink_glossary.derive_keys."""
    text = re.sub(r"<[^>]+>", "", dt_inner_html)
    text = unescape(text).strip()
    parts = re.split(r"\s+-\s+|\s*[\u2014\u2013]\s*", text, maxsplit=1)
    lhs = parts[0]
    rhs = parts[1] if len(parts) > 1 else ""
    keys: list[str] = []

    def add_alternatives(s: str) -> None:
        """Index a slash-separated headword fragment.

        A *spaced* slash separates alternatives ("SASE / SSE"); an *unspaced*
        one is part of a single designation ("ISO/IEC 42001", "CI/CD"). Both
        the whole designation and its parts are indexed, and because
        build_term_regexes sorts alternatives longest-first, prose containing
        "ISO/IEC 42001" matches that key as one link instead of rendering as
        an "ISO" link (pointing at the 27001 entry) followed by a separate
        "IEC 42001" link.
        """
        for alt in re.split(r"\s+/\s+", s):
            alt = alt.strip()
            if not alt:
                continue
            keys.append(alt)
            if "/" in alt:
                for piece in alt.split("/"):
                    piece = piece.strip()
                    if piece:
                        keys.append(piece)

    def add_with_parens(s: str) -> None:
        base = re.sub(r"\s*\([^)]*\)", "", s).strip()
        add_alternatives(base)
        for m in re.finditer(r"\(([^)]+)\)", s):
            for piece in re.split(r"\s*/\s*", m.group(1)):
                piece = piece.strip()
                if piece:
                    keys.append(piece)

    add_with_parens(lhs)
    if rhs:
        for piece in re.split(r"\s+/\s+", rhs):
            piece = re.sub(r"\s*\([^)]*\)", "", piece).strip()
            if piece and 1 <= len(piece.split()) <= 6:
                keys.append(piece)

    seen: set[str] = set()
    unique: list[str] = []
    for k in keys:
        kl = k.lower()
        if not kl or kl in seen or kl in DENYLIST:
            continue
        seen.add(kl)
        unique.append(k)
    return unique


def load_glossary_terms() -> tuple[dict[str, str], list[str]]:
    """Parse glossary.html and return:
      - key_to_slug:   lowercased-key -> slug
      - original_keys: original-case spellings (for is_acronym checks)
    """
    content = GLOSSARY_FILE.read_text(encoding="utf-8")
    key_to_slug: dict[str, str] = {}
    original_keys: list[str] = []
    pattern = re.compile(r"<dt(\s[^>]*)?>(.*?)</dt>", re.DOTALL)
    for m in pattern.finditer(content):
        attrs = m.group(1) or ""
        inner = m.group(2)
        keys = derive_keys(inner)
        if not keys:
            continue
        existing_id = re.search(r"\bid\s*=\s*[\"']([^\"']+)[\"']", attrs)
        slug = existing_id.group(1) if existing_id else slugify(keys[0])
        for k in keys:
            kl = k.lower()
            if kl and kl not in key_to_slug:
                key_to_slug[kl] = slug
                original_keys.append(k)
    return key_to_slug, original_keys


def is_acronym(key: str) -> bool:
    """All-uppercase, 2-8 chars, no spaces - require case-sensitive match
    so 'AI' (the acronym) matches but 'ai' (in 'aim', 'rain', etc.) doesn't."""
    return (
        2 <= len(key) <= 8
        and " " not in key
        and key == key.upper()
        and any(c.isalpha() for c in key)
    )


def build_term_regexes(keys: list[str]) -> list[tuple[re.Pattern[str], bool]]:
    """Returns (pattern, case_sensitive) pairs.

    Acronyms are matched case-sensitively to avoid linking 'cd' to CD or
    'Kev' to KEV. Everything else is case-insensitive.
    """
    case_sensitive_keys = [k for k in keys if is_acronym(k)]
    case_insensitive_keys = [k for k in keys if not is_acronym(k)]

    patterns: list[tuple[re.Pattern[str], bool]] = []
    if case_sensitive_keys:
        sorted_keys = sorted(case_sensitive_keys, key=lambda k: -len(k))
        pieces = [re.escape(k) for k in sorted_keys]
        patterns.append((
            re.compile(r"(?<![A-Za-z0-9])(" + "|".join(pieces) + r")(?![A-Za-z0-9])"),
            True,
        ))
    if case_insensitive_keys:
        sorted_keys = sorted(case_insensitive_keys, key=lambda k: -len(k))
        pieces = [re.escape(k) for k in sorted_keys]
        patterns.append((
            re.compile(
                r"(?<![A-Za-z0-9])(" + "|".join(pieces) + r")(?![A-Za-z0-9])",
                flags=re.IGNORECASE,
            ),
            False,
        ))
    return patterns


def unwrap_existing_links(content: str) -> tuple[str, int]:
    """Strip every existing <a class="glossary-link"> so we can rebuild fresh.
    Matches any href ending in glossary.html#... (root-relative OR ../-relative
    for pages in subdirectories)."""
    pattern = re.compile(
        r'<a\s+class="glossary-link"\s+href="(?:\.\./)*glossary\.html#[^"]+">([^<]+)</a>',
        re.IGNORECASE,
    )
    removed = 0

    def replace(m: re.Match) -> str:
        nonlocal removed
        removed += 1
        return m.group(1)

    return pattern.sub(replace, content), removed


def mask_skip_zones(content: str) -> tuple[str, list[str]]:
    """Replace every protected region with a placeholder so the linker
    never touches it. Returns (masked, placeholders)."""
    placeholders: list[str] = []

    def stash(m: re.Match) -> str:
        placeholders.append(m.group(0))
        return f"\x00P{len(placeholders) - 1}\x00"

    # 1. HTML comments
    content = re.sub(r"<!--.*?-->", stash, content, flags=re.DOTALL)

    # 2. Block-level skip tags (script, style, code, pre, headings,
    #    header, footer, nav). DOTALL across multiple lines.
    for tag in SKIP_BLOCK_TAGS:
        content = re.sub(
            rf"<{tag}(\s[^>]*)?>.*?</{tag}>",
            stash,
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # 2b. Class-based skip zones. Copy-paste examples and code samples that
    #     are marked up as <div>/<span> (not <code>/<pre>) must never receive
    #     injected <a> markup, or contributors paste anchor tags into PRs.
    for tag in ("div", "span"):
        content = re.sub(
            rf'<{tag}\b[^>]*\bclass="[^"]*\b(?:code-block|tag-example)\b[^"]*"[^>]*>.*?</{tag}>',
            stash,
            content,
            flags=re.DOTALL | re.IGNORECASE,
        )

    # 3. Existing anchors anywhere
    content = re.sub(
        r"<a\b[^>]*>.*?</a>",
        stash,
        content,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 4. Any remaining HTML tag (so we never touch attribute values).
    #    Tags don't get mutated; we only modify text between tags.

    return content, placeholders


def unmask(content: str, placeholders: list[str]) -> str:
    """Restore placeholders. Must loop because masked regions can nest:
    a `<h3>` stashed first, then the `<a>` that wraps it stashed second,
    means the inner placeholder lives inside the outer placeholder's text
    and only surfaces after the outer one is restored. `re.sub` does one
    pass, so loop until no more substitutions happen."""

    def restore(m: re.Match) -> str:
        return placeholders[int(m.group(1))]

    pattern = re.compile(r"\x00P(\d+)\x00")
    while True:
        new_content = pattern.sub(restore, content)
        if new_content == content:
            return new_content
        content = new_content


def link_text_segments(
    content: str,
    patterns: list[tuple[re.Pattern[str], bool]],
    key_to_slug: dict[str, str],
    href_prefix: str = "glossary.html#",
) -> tuple[str, list[str]]:
    """Walk masked content, only inserting links in text-between-tags.
    Records which slugs got linked (one per slug max - first per page)."""
    out: list[str] = []
    cursor = 0
    linked_slugs: set[str] = set()
    linked_words: list[str] = []

    tag_re = re.compile(r"<[^>]+>")
    for tm in tag_re.finditer(content):
        if tm.start() > cursor:
            text_chunk = content[cursor : tm.start()]
            new_chunk = _link_chunk(
                text_chunk, patterns, key_to_slug, linked_slugs, linked_words, href_prefix
            )
            out.append(new_chunk)
        out.append(tm.group(0))
        cursor = tm.end()
    if cursor < len(content):
        out.append(
            _link_chunk(
                content[cursor:], patterns, key_to_slug, linked_slugs, linked_words, href_prefix
            )
        )
    return "".join(out), linked_words


def _link_chunk(
    text: str,
    patterns: list[tuple[re.Pattern[str], bool]],
    key_to_slug: dict[str, str],
    linked_slugs: set[str],
    linked_words: list[str],
    href_prefix: str = "glossary.html#",
) -> str:
    """Walk left-to-right. At each step take the EARLIEST match across all
    patterns and, among matches starting there, the LONGEST. Link it when its
    slug is unlinked; otherwise emit the whole matched span unchanged and skip
    past it. Claiming the full longest span (even when its slug is already
    linked or denylisted) stops a shorter acronym from grabbing the leftover of
    a longer term - e.g. linking "SOC" out of an already-linked "SOC 2", or
    "IAM" out of "IAM Access Analyzer"."""
    if not text:
        return text
    out: list[str] = []
    cursor = 0
    while cursor < len(text):
        # 1) Earliest position any pattern matches at/after the cursor.
        earliest: int | None = None
        for pat, _case_sensitive in patterns:
            m = pat.search(text, cursor)
            if m and (earliest is None or m.start() < earliest):
                earliest = m.start()
        if earliest is None:
            out.append(text[cursor:])
            break

        # 2) Among matches anchored at `earliest`, take the longest.
        best: tuple[int, str] | None = None  # (end, word)
        for pat, _case_sensitive in patterns:
            m = pat.match(text, earliest)
            if m and (best is None or m.end() > best[0]):
                best = (m.end(), m.group(1))
        if best is None:
            out.append(text[cursor : earliest + 1])
            cursor = earliest + 1
            continue

        end, word = best
        slug = key_to_slug.get(word.lower())
        out.append(text[cursor:earliest])
        if slug and slug not in linked_slugs:
            out.append(
                f'<a class="glossary-link" href="{href_prefix}{slug}">{word}</a>'
            )
            linked_slugs.add(slug)
            linked_words.append(word)
        else:
            out.append(text[earliest:end])
        cursor = end
    return "".join(out)


def crosslink_page(
    path: Path,
    patterns: list[tuple[re.Pattern[str], bool]],
    key_to_slug: dict[str, str],
) -> dict:
    raw = path.read_text(encoding="utf-8")
    # Compute the right glossary href prefix for this page based on how many
    # directories deep it sits relative to the repo root. A subdir page like
    # breaches/capital-one.html needs "../glossary.html#..." so the link
    # actually resolves.
    rel_path = str(path.relative_to(REPO_ROOT))
    href_prefix = _glossary_prefix_for(rel_path)
    cleaned, removed = unwrap_existing_links(raw)
    masked, placeholders = mask_skip_zones(cleaned)
    linked, linked_words = link_text_segments(masked, patterns, key_to_slug, href_prefix)
    final = unmask(linked, placeholders)
    if final != raw:
        path.write_text(final, encoding="utf-8")
    return {
        "file": path.name,
        "stripped": removed,
        "linked": len(linked_words),
        "words": linked_words,
        "changed": final != raw,
    }


def main() -> int:
    if not GLOSSARY_FILE.exists():
        print(f"glossary not found: {GLOSSARY_FILE}", file=sys.stderr)
        return 1

    key_to_slug, original_keys = load_glossary_terms()
    if not key_to_slug:
        print("No glossary terms found.", file=sys.stderr)
        return 1
    print(
        f"Loaded {len({v for v in key_to_slug.values()})} unique glossary terms "
        f"({len(key_to_slug)} aliases)."
    )

    patterns = build_term_regexes(original_keys)

    # Combine the explicit TARGET_PAGES list with any auto-discovered
    # subdirectory pages (per-breach, per-meeting). Sort discovered pages
    # for stable ordering across runs.
    import glob as _glob
    all_targets = list(TARGET_PAGES)
    for pattern in SUBDIR_PATTERNS:
        for path in sorted(_glob.glob(str(REPO_ROOT / pattern))):
            rel = str(Path(path).relative_to(REPO_ROOT))
            all_targets.append(rel)

    total_linked = 0
    total_pages_changed = 0
    for name in all_targets:
        page = REPO_ROOT / name
        if not page.exists():
            print(f"  - skip (missing): {name}")
            continue
        result = crosslink_page(page, patterns, key_to_slug)
        marker = "✓" if result["changed"] else " "
        print(
            f"  {marker} {result['file']}: stripped {result['stripped']}, "
            f"linked {result['linked']}"
            + (f" ({', '.join(result['words'])})" if result["words"] else "")
        )
        total_linked += result["linked"]
        if result["changed"]:
            total_pages_changed += 1

    print(
        f"\nDone. Linked {total_linked} term mentions across "
        f"{total_pages_changed} pages."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
