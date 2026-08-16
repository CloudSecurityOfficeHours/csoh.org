#!/usr/bin/env python3
"""Cross-link glossary.html.

Reads glossary.html (at the repo root, one level up from tools/) and:
  1. Adds an `id="term-..."` to every <dt> element (idempotent).
  2. For every <dd>, wraps the first occurrence of any glossary term it
     mentions in an <a class="glossary-link" href="#term-...">.

Skips text that is already inside an <a> tag (so we don't double-link
external references like "see <a href=...>Breach Kill Chains</a>").
Also skips self-references (a term doesn't link to its own dt) and only
links the first occurrence of each term per dd group to keep things
readable.

Re-runnable, but rebuild-idempotent rather than preservation-idempotent:
main() STRIPS every existing <a class="glossary-link"> wrapper and relinks
from scratch, so the current rules apply to the whole file consistently. A
hand-added or hand-retargeted link inside glossary.html does not survive the
next run. Fix the headword or the rules instead.

(This docstring used to claim the opposite - that existing wrappers were
"preserved and treated as already-linked". They never were. Anyone who trusted
it and hand-fixed a link here would have watched the fix vanish silently.)

Term parsing lives in glossary_terms.py, shared with crosslink_pages.py so the
two cannot drift apart again.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from glossary_terms import (  # noqa: E402
    BASE_DENYLIST as DENYLIST,
    derive_keys,
    is_acronym,
    slugify,
)

__all__ = ["DENYLIST", "derive_keys", "slugify", "main"]

GLOSSARY = Path(__file__).resolve().parent.parent / "glossary.html"


def add_dt_ids(content: str) -> tuple[str, dict[str, str], dict[str, str]]:
    """Add id="..." to each <dt> (if not already present).

    Returns the updated content, a map of lowercased-key -> slug, and a map of
    lowercased-key -> the key's original-case spelling. The second map exists so
    _link_text can apply the acronym rule: the match regex is case-insensitive,
    but a key that `is_acronym` must still match text of the same case.
    """
    key_to_slug: dict[str, str] = {}
    key_to_original: dict[str, str] = {}

    def replace(m: re.Match) -> str:
        attrs = m.group(1) or ""
        inner = m.group(2)
        keys = derive_keys(inner)
        if not keys:
            return m.group(0)

        # If the dt already has an id, reuse it.
        existing_id = re.search(r"\bid\s*=\s*[\"']([^\"']+)[\"']", attrs)
        slug = existing_id.group(1) if existing_id else slugify(keys[0])

        for k in keys:
            kl = k.lower()
            if kl and kl not in key_to_slug:
                key_to_slug[kl] = slug
                key_to_original[kl] = k

        if existing_id:
            return m.group(0)
        # Insert id after the opening <dt
        new_attrs = f' id="{slug}"' + attrs
        return f"<dt{new_attrs}>{inner}</dt>"

    pattern = re.compile(r"<dt(\s[^>]*)?>(.*?)</dt>", re.DOTALL)
    return pattern.sub(replace, content), key_to_slug, key_to_original


def build_term_regex(keys: list[str]) -> re.Pattern[str]:
    """Build one big alternation regex that matches any key, longest first."""
    sorted_keys = sorted(keys, key=lambda k: -len(k))
    pieces = [re.escape(k) for k in sorted_keys]
    # Use a non-word lookbehind/ahead for boundaries that work with hyphens
    # and ampersands in keys (e.g. "Pass-the-Hash", "MITRE ATT&CK").
    return re.compile(
        r"(?<![A-Za-z0-9])(" + "|".join(pieces) + r")(?![A-Za-z0-9])",
        flags=re.IGNORECASE,
    )


def link_dd(
    inner: str,
    term_re: re.Pattern[str],
    key_to_slug: dict[str, str],
    key_to_original: dict[str, str],
    self_slug: str,
) -> str:
    """Return inner with every term mention wrapped in <a>.

    Protects existing <a>...</a> regions (and any tag content) so we don't
    nest anchors or rewrite attribute strings. Skips self-links (a term
    doesn't link to its own dt inside its own definition).
    """
    # Mask existing <a>...</a> regions with placeholders.
    a_re = re.compile(r"<a\b[^>]*>.*?</a>", re.DOTALL | re.IGNORECASE)
    placeholders: list[str] = []

    def stash(m: re.Match) -> str:
        placeholders.append(m.group(0))
        return f"\x00A{len(placeholders) - 1}\x00"

    masked = a_re.sub(stash, inner)

    # Walk segments: tags vs text. Only modify text segments.
    out: list[str] = []
    cursor = 0
    tag_re = re.compile(r"<[^>]+>")
    for tm in tag_re.finditer(masked):
        if tm.start() > cursor:
            out.append(
                _link_text(
                    masked[cursor : tm.start()],
                    term_re,
                    key_to_slug,
                    key_to_original,
                    self_slug,
                )
            )
        out.append(tm.group(0))
        cursor = tm.end()
    if cursor < len(masked):
        out.append(
            _link_text(masked[cursor:], term_re, key_to_slug, key_to_original, self_slug)
        )
    result = "".join(out)

    # Restore placeholders.
    def unstash(m: re.Match) -> str:
        return placeholders[int(m.group(1))]

    return re.sub(r"\x00A(\d+)\x00", unstash, result)


_SENTENCE_END = re.compile(r"[.!?]")


def _link_text(
    text: str,
    term_re: re.Pattern[str],
    key_to_slug: dict[str, str],
    key_to_original: dict[str, str],
    self_slug: str,
) -> str:
    """Wrap glossary-term occurrences in text with <a>. Within a sentence,
    each target slug is linked only once - repeating the same word (or
    another alias of the same term) inside one sentence does not get a
    second link. Sentence boundaries are `.`, `!`, `?`. Self-links are
    always skipped."""
    if not text:
        return text
    out: list[str] = []
    cursor = 0
    seen_in_sentence: set[str] = set()
    for m in term_re.finditer(text):
        # If a sentence boundary appears between the previous match (or
        # start of text) and this one, reset the per-sentence seen set.
        if _SENTENCE_END.search(text, cursor, m.start()):
            seen_in_sentence = set()

        word = m.group(1)
        slug = key_to_slug.get(word.lower())
        if not slug or slug == self_slug:
            continue
        # The alternation is case-insensitive so ordinary multi-word terms match
        # however they are capitalised, but an acronym key must match exactly.
        # Without this, "FIRST" (Forum of Incident Response and Security Teams)
        # linked every ordinary "first" in the glossary, which is why the word
        # had to sit in the denylist and why that entry was unreachable.
        original = key_to_original.get(word.lower())
        if original and is_acronym(original) and word != original:
            continue
        if slug in seen_in_sentence:
            continue
        seen_in_sentence.add(slug)
        out.append(text[cursor : m.start()])
        out.append(f'<a class="glossary-link" href="#{slug}">{word}</a>')
        cursor = m.end()
    out.append(text[cursor:])
    return "".join(out)


def link_dds(
    content: str,
    term_re: re.Pattern[str],
    key_to_slug: dict[str, str],
    key_to_original: dict[str, str],
) -> str:
    """Walk the file and link each <dd> based on the most recent preceding <dt>'s id."""
    # We track the "self" slug: the id of the most recent <dt>.
    pos_re = re.compile(r"<(dt|dd)(\s[^>]*)?>(.*?)</\1>", re.DOTALL | re.IGNORECASE)

    out: list[str] = []
    last_end = 0
    self_slug: str = ""

    for m in pos_re.finditer(content):
        out.append(content[last_end : m.start()])
        tag = m.group(1).lower()
        attrs = m.group(2) or ""
        inner = m.group(3)
        if tag == "dt":
            id_m = re.search(r"\bid\s*=\s*[\"']([^\"']+)[\"']", attrs)
            self_slug = id_m.group(1) if id_m else ""
            out.append(m.group(0))
        else:  # dd
            new_inner = link_dd(inner, term_re, key_to_slug, key_to_original, self_slug)
            out.append(f"<dd{attrs}>{new_inner}</dd>")
        last_end = m.end()
    out.append(content[last_end:])
    return "".join(out)


def unwrap_all_glossary_links(content: str) -> tuple[str, int]:
    """Strip every existing <a class="glossary-link">WORD</a>, replacing it
    with WORD. Done before relinking so the current rules (denylist,
    first-per-sentence, etc.) apply to the whole file consistently."""
    pattern = re.compile(
        r'<a\s+class="glossary-link"\s+href="#[^"]+">([^<]+)</a>',
        re.IGNORECASE,
    )
    removed = 0

    def replace(m: re.Match) -> str:
        nonlocal removed
        removed += 1
        return m.group(1)

    return pattern.sub(replace, content), removed


def main() -> int:
    if not GLOSSARY.exists():
        print(f"glossary not found: {GLOSSARY}", file=sys.stderr)
        return 1

    content = GLOSSARY.read_text(encoding="utf-8")

    # Pass 0: strip all existing glossary-links so we can relink fresh
    # under the current rules (denylist, first-per-sentence, etc.).
    content, n_unwrapped = unwrap_all_glossary_links(content)
    if n_unwrapped:
        print(f"Stripped {n_unwrapped} existing link(s) for fresh relinking.")

    # Pass 1: assign IDs and collect terms.
    content, key_to_slug, key_to_original = add_dt_ids(content)
    if not key_to_slug:
        print("No <dt> entries found; nothing to do.", file=sys.stderr)
        return 1

    # Pass 2: link <dd>s.
    term_re = build_term_regex(list(key_to_slug.keys()))
    content = link_dds(content, term_re, key_to_slug, key_to_original)

    GLOSSARY.write_text(content, encoding="utf-8")
    n_terms = len({v for v in key_to_slug.values()})
    n_links = content.count('class="glossary-link"')
    print(f"Linked {n_links} term mentions across {n_terms} unique terms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
