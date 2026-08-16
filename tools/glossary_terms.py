#!/usr/bin/env python3
"""Shared glossary-term parsing for the two cross-linkers.

`crosslink_glossary.py` links terms *inside* glossary.html; `crosslink_pages.py`
links them from every other page. Both need the same answer to one question:
given a `<dt>` headword, what strings should link to it?

They used to answer it with two copies of `derive_keys`, and the copies drifted
until each carried a bug the other had already fixed:

  * crosslink_glossary gated parenthetical aliases behind an "acronymish" test,
    which crosslink_pages lacked entirely, so "Ambient Mode (Service Mesh)"
    hijacked "Service Mesh" on every page but not inside the glossary.
  * crosslink_pages learned that an unspaced slash is part of a name rather than
    a separator, so "ISO/IEC 42001" is one key. crosslink_glossary still split
    it, making bare "ISO" an alias of whichever ISO entry came first.

One module, imported by both, is the fix for that class of bug rather than for
either instance of it. (Reconciling them also retired the acronymish gate; see
the note above derive_keys for why the denylist does that job better.) The
denylists stay separate on purpose - see below.
"""

from __future__ import annotations

import re
from html import unescape

# Single-word keys that overlap with ordinary English often enough that linking
# them is noise. This is the baseline both tools share.
BASE_DENYLIST = {
    "public",
    "private",
    "hybrid",
    "image",
    "baseline",
    "registry",
    "principal",
    "first",
    "csp",
    "sp",
    "soc",
    "cloud",
    # The standards body, not a concept. Every "ISO/IEC <number>" headword
    # yields a bare "ISO" key, so without this the word links to whichever ISO
    # entry sits earliest in the glossary even when the sentence is about a
    # different standard. The full designations are keys in their own right and
    # match longest-first, so "ISO/IEC 42001" still links correctly.
    "iso",
}

# crosslink_pages.py runs over page prose rather than terse glossary
# definitions, where these recur constantly in senses that have nothing to do
# with the glossary entry ("the data", "a policy", "which account"). Kept
# separate rather than merged because inside a glossary definition these words
# are usually being used in their defined sense and are worth linking.
PAGE_EXTRA_DENYLIST = {
    "account", "accounts", "ad", "agent", "audit", "blast", "blue",
    "container", "control", "controls", "data", "drift", "functions",
    "kev", "key", "keys", "log", "logs", "policies", "policy", "purple",
    "red", "role", "roles", "scope", "secret", "secrets", "session",
    "sessions", "subnet", "tag", "tags", "user", "users", "vault",
}

PAGE_DENYLIST = BASE_DENYLIST | PAGE_EXTRA_DENYLIST


def slugify(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return "term-" + text if text else "term-unknown"


# Parenthetical aliases are accepted unconditionally, and deliberately so.
#
# crosslink_glossary.py used to gate them behind an "acronymish" test - accept
# "(CNAPP)", reject "(Cloud)" - written after registering "Cloud" from
# "Air Gap (Cloud)" wrapped the bare word 60 times across the glossary, all
# pointing at term-air-gap. The gate works for that case but is far too blunt:
# it requires the parenthetical to be short and all-caps, so it also threw away
# "Kubernetes (K8s)" and every tool name in
# "IaC Scanners (Checkov / Trivy / tfsec / KICS / Terrascan)" - 8 legitimate
# aliases, and 29 real links across the site.
#
# The case it was defending against is already covered twice over: "cloud" is
# in BASE_DENYLIST, so it cannot become an alias regardless; and any headword
# that does claim a term belonging to another entry now trips the duplicate-key
# check in CROSSLINK_PAGES_README.md, which names both entries instead of
# silently preferring whichever appears first. A precise check plus a denylist
# entry beats a heuristic that cannot tell "K8s" from "Cloud".


def derive_keys(dt_inner_html: str, denylist: set[str] | None = None) -> list[str]:
    """Return the lookup keys for a <dt>, primary first.

    `denylist` defaults to BASE_DENYLIST; pass PAGE_DENYLIST for page prose.
    """
    if denylist is None:
        denylist = BASE_DENYLIST

    text = re.sub(r"<[^>]+>", "", dt_inner_html)
    text = unescape(text).strip()

    # Split off the long-form expansion after a dash.
    parts = re.split(r"\s+-\s+|\s*[—–]\s*", text, maxsplit=1)
    lhs = parts[0]
    rhs = parts[1] if len(parts) > 1 else ""

    keys: list[str] = []

    def add_alternatives(s: str) -> None:
        """Index a slash-separated fragment.

        A *spaced* slash separates alternatives ("SASE / SSE"); an *unspaced*
        one is part of one designation ("ISO/IEC 42001", "CI/CD"). Both the
        whole designation and its parts are indexed, and since callers match
        alternatives longest-first, prose containing "ISO/IEC 42001" links as a
        single correct anchor rather than as an "ISO" link pointing at the
        27001 entry followed by a separate "IEC 42001" link.
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
        if not kl or kl in seen or kl in denylist:
            continue
        seen.add(kl)
        unique.append(k)
    return unique
