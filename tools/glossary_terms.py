#!/usr/bin/env python3
"""Shared glossary-term parsing for the two cross-linkers.

`crosslink_glossary.py` links terms *inside* glossary.html; `crosslink_pages.py`
links them from every other page. Both need the same answer to one question:
given a `<dt>` headword, what strings should link to it?

One module, imported by both, so the two linkers can never disagree about
which strings a headword owns (two copies of `derive_keys` would drift apart,
each fixing bugs the other still has). The denylists stay separate on
purpose - see below.
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
    # "first" is deliberately NOT here. The glossary defines FIRST (the Forum
    # of Incident Response and Security Teams), and both linkers match
    # acronym-shaped keys case-sensitively, so "FIRST" links and the ordinary
    # word "first" never does. Denying it would cost the entry every link.
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
    # Two unrelated meanings, both all-caps and both live on this site: the
    # glossary defines Common Platform Enumeration, while conferences.html and
    # resources.html use CPE for the Continuing Professional Education credits
    # that trainings award. Case-sensitive acronym matching cannot separate
    # them. The long form "Common Platform Enumeration" is a key in its own
    # right and is unambiguous, so the entry is still reachable from page prose.
    "cpe",
}

PAGE_DENYLIST = BASE_DENYLIST | PAGE_EXTRA_DENYLIST


def slugify(text: str) -> str:
    text = unescape(text)
    text = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return "term-" + text if text else "term-unknown"


# A headword key is unescaped text; the pages it is matched against are HTML.
# So a key containing "&", "<" or ">" can only ever match a page that spelled
# the character WRONG. "MITRE ATT&CK" is the standing example: a naive key
# matches only a page that wrote a bare "&" instead of "&amp;", and is blind
# to every correctly escaped mention (as are "Identity & Access Management",
# "Command & Control" and the other "&" headwords).
#
# So build the pattern from the key rather than from re.escape() alone, and let
# each character match either spelling. The matched span is written back into
# the link verbatim, so a page keeps its "&amp;" and stays well-formed.
_ENTITY_ALTERNATIVES = {
    "&": r"(?:&amp;|&)",
    "<": r"(?:&lt;|<)",
    ">": r"(?:&gt;|>)",
}


def key_regex(key: str) -> str:
    """Regex source matching `key` in HTML, either escaped or literal.

    Use this instead of re.escape() anywhere a glossary key is matched against
    page markup. For a key with no entity-worthy character it is exactly
    re.escape(key), so nothing else changes.
    """
    return "".join(_ENTITY_ALTERNATIVES.get(c, re.escape(c)) for c in key)


def match_key(word: str) -> str:
    """Normalise a span matched by key_regex() back to key form for lookup.

    key_to_slug is built from unescaped headwords, so a span captured as
    "MITRE ATT&amp;CK" has to be unescaped before it will find its slug.
    """
    return unescape(word)


def is_acronym(key: str) -> bool:
    """All-uppercase, 2-8 chars, no spaces - match these case-sensitively.

    Lets "AI" the acronym link while "ai" inside "aim" or "rain" does not, and
    "KEV" link while the name "Kev" does not. Both cross-linkers consult this;
    a key that satisfies it is only ever matched against text of the same case.
    """
    return (
        2 <= len(key) <= 8
        and " " not in key
        and key == key.upper()
        and any(c.isalpha() for c in key)
    )


# Parenthetical aliases are accepted unconditionally, and deliberately so.
#
# An "acronymish" gate (accept "(CNAPP)", reject "(Cloud)") is far too blunt:
# it would throw away "Kubernetes (K8s)" and every tool name in
# "IaC Scanners (Checkov / Trivy / tfsec / KICS / Terrascan)".
#
# The case such a gate defends against ("Air Gap (Cloud)" claiming the bare
# word "Cloud") is covered twice over: "cloud" is in BASE_DENYLIST, so it
# cannot become an alias regardless; and any headword that does claim a term
# belonging to another entry trips the duplicate-key
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
