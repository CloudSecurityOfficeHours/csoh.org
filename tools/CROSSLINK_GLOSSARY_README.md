# `crosslink_glossary.py`

Adds anchor IDs to every `<dt>` in `glossary.html` and hyperlinks every glossary-term mention found in any `<dd>` to its corresponding entry. Run it after adding or editing glossary terms.

## What it does

1. **Assigns IDs.** Every `<dt>` gets `id="term-..."`, derived from the headword (e.g. `IAM - Identity & Access Management` → `id="term-iam"`).
2. **Builds a key→slug lookup.** Pulls every alias from each `<dt>`:
   - The primary headword and any `/`-separated aliases on the left of an em-dash.
   - The long form on the right of the em-dash (when ≤6 words).
   - Parenthetical aliases like `(K8s)` or `(AD)`.
3. **Hyperlinks every occurrence.** Walks every `<dd>` and wraps each glossary-term mention in `<a class="glossary-link" href="#term-...">`. Skips:
   - Text already inside an existing `<a>` tag (no nesting).
   - Self-references (a term won't link to itself in its own definition).
   - A small denylist of generic single-word keys that overlap with everyday English (`public`, `private`, `hybrid`, `image`, `baseline`, `registry`, `principal`, `first`, `csp`, `sp`, `soc`, `cloud`).

## Usage

```bash
python3 tools/crosslink_glossary.py
```

Output:

```
Linked 180 term mentions across 197 unique terms.   # illustrative - the live glossary has ~300 terms
```

The script is **rebuild-idempotent, not preservation-idempotent**: every run first STRIPS all existing `<a class="glossary-link">` wrappers (it prints `Stripped N existing link(s) for fresh relinking.`), then relinks from scratch under the current rules. So any hand-added or specially-scoped glossary link inside `glossary.html` is discarded on the next run - add glossary entries via the script's rules, not by hand-wrapping. Removed terms lose their lookup entry, and pre-existing links to a removed slug will 404 and should be cleaned up by hand.

## When to run

- **After adding a `<dt>` / `<dd>` pair** to `glossary.html`.
- **After renaming a term**: re-run, then update the old slug in any pages outside the glossary that linked to it (none currently link to glossary anchors from outside).
- **As part of CI** if you want automated enforcement (not currently wired in - runs are manual).

## Adding a new glossary term

1. Edit `glossary.html`. Locate the right `<h2 id="...">` section (cloud models, IAM, network, data, detection, posture, vuln, compliance, attack, AI, ops, standards bodies). Add a new pair inside that section's `<dl class="glossary-list">`:

   ```html
   <dt>FOO - Fancy Other Object</dt>
   <dd>One- or two-sentence definition. Keep it short - long bodies break the dt/dd visual rhythm.</dd>
   ```

2. Run the cross-linker:

   ```bash
   python3 tools/crosslink_glossary.py
   ```

3. If the total term count crosses a round number, update the search-bar placeholder text and the `<span id="visibleTerms">` initial count in `glossary.html`. Both currently read `301` (the placeholder is `Search 300+ terms`).

## Adjusting the denylist

If a generic word ends up auto-linking from an unrelated dt (for example, the dt `Public / Private / Hybrid / Multi-Cloud` was previously linking every "public" or "private" in unrelated definitions), add the lowercased word to the `DENYLIST` set near the top of `crosslink_glossary.py` and re-run.

Conversely, if you want a previously-denylisted word to link, remove it from the set. Be careful - common adjectives like "public" generate many false positives.

## Implementation notes

- **No external dependencies.** Pure Python 3 stdlib (regex + html).
- **Match boundaries** use `(?<![A-Za-z0-9])` and `(?![A-Za-z0-9])` rather than `\b` so that hyphenated keys like `Pass-the-Hash` and ampersand keys like `MITRE ATT&CK` match correctly.
- **Tag-safe.** Existing `<a>...</a>` blocks are masked with placeholders before substitution and restored after, so the script never wraps text inside an existing link or rewrites an `href` attribute by mistake.
- **Whole-key matching only.** No prefix matching, no word-stem matching. "Tokenization" won't match the key "Token".

## See also

- [glossary.html](../glossary.html) - the cross-linked output.
- [glossary.js](../glossary.js) - the live-search behavior on the rendered page.
- [README.md](../README.md#adding-a-glossary-term) - the higher-level "Adding a Glossary Term" recipe.
