# `crosslink_pages.py`

Cross-link glossary terms across the rest of the site.

## What it does

For each content page (everything except `glossary.html`), the script finds the **first occurrence** of each glossary term and wraps it in an anchor pointing to the glossary entry:

```html
<a class="glossary-link" href="glossary.html#term-cspm">CSPM</a>
```

This is the cross-page companion to [`crosslink_glossary.py`](CROSSLINK_GLOSSARY_README.md), which only links terms *within* `glossary.html`.

## Usage

```bash
python3 tools/crosslink_pages.py
```

The script is **idempotent** - every run strips existing cross-page glossary links and rebuilds them, so adding new glossary entries or tuning the denylist is safe to re-run.

## Where links go

The list of target pages is at the top of `crosslink_pages.py` in `TARGET_PAGES`. Add new top-level pages there as the site grows. Note: `breaches/*.html` and `meetings/*.html` are auto-discovered via `SUBDIR_PATTERNS` and rewritten too (with a computed `../glossary.html#` prefix), so you do NOT list those individually.

The glossary itself, error pages (`403.html`, `404.html`), and the Google site verification stub are deliberately excluded.

## Linking rules

- **First occurrence per page only.** Subsequent mentions of the same term on the same page are not linked, to keep prose readable.
- **Acronyms (all-caps, 2-8 chars) match case-sensitively.** This prevents `cd` (the shell command) from matching `CD` (Continuous Delivery), `Kev` (a person's name) from matching `KEV` (Known Exploited Vulnerabilities), etc. Multi-word and lowercase glossary entries continue to match case-insensitively.
- **A spaced slash separates alternatives; an unspaced one is part of the name.** `SASE / SSE` is two aliases. `ISO/IEC 42001` and `CI/CD` are single designations, indexed whole *and* split into parts, with the whole form winning because alternatives are matched longest-first. Get this wrong and `ISO/IEC 42001` in prose renders as an `ISO` link pointing at the 27001 entry followed by a separate `IEC 42001` link, which is what it used to do.
- **One alias, one entry.** An alias is claimed by the first `<dt>` in document order, so if two entries derive the same key the winner depends on glossary ordering rather than on intent. Keep headwords disjoint: when a dedicated entry exists (`SCC - Security Command Center`), do not also list that term in a broader entry's headword (`GuardDuty / Defender for Cloud / Security Command Center`), and do not use a parenthetical as a disambiguator (`Ambient Mode (Service Mesh)`) because the parenthetical is read as an alias. Put that context in the definition instead. The invariant is checked by the snippet in "Verifying" below.
- **Skip zones** - the linker never touches text inside any of these:
  - existing `<a>` tags (no double-linking)
  - `<code>`, `<pre>`, `<script>`, `<style>`
  - `<h1>` through `<h6>` (headings shouldn't get inline links)
  - `<header>`, `<footer>`, `<nav>` (chrome, not content)
  - `<title>`/`<head>` and `<button>` text
  - `.code-block` and `.tag-example` class blocks (example snippets)
  - HTML comments, attribute values, JSON-LD schema blocks
- **DENYLIST** filters single-word terms that overlap with ordinary English (`public`, `data`, `cloud`, `agent`, etc.) plus single-word remnants accidentally extracted from compound entries like `Blue / Red Team`. If a generic word starts auto-linking somewhere unhelpful, add it to the `DENYLIST` set near the top of the script.

## When to run it

- After adding or editing glossary terms (so new terms get cross-linked from existing pages).
- After adding a new content page (add the page name to `TARGET_PAGES` first).
- If you notice false-positive links and update the `DENYLIST`.

## Output

```
Loaded 201 unique glossary terms (338 aliases).   # illustrative - a live run currently loads ~300 terms / ~500 aliases
    index.html: stripped 0, linked 0
    resources.html: stripped 1, linked 1 (AI)
    ctfs.html: stripped 7, linked 7 (Kubernetes, AI, SSRF, IMDSv2, OIDC, LLM, CI)
  ✓ breach-timeline.html: stripped 56, linked 55 (...)
  ...
Done. Linked 228 term mentions across 5 pages.
```

The trailing parenthesized list shows which terms were linked on each page so you can spot any unwanted matches.

## Verifying

Two invariants are worth checking after editing glossary headwords. Neither is
enforced by the script, and both fail silently: a duplicate alias simply
resolves to whichever entry sits earlier in the file.

```sh
# 1. No alias is claimed by two entries. Expect "duplicate alias keys: 0".
python3 - <<'EOF'
import sys, re, collections; sys.path.insert(0, "tools")
import crosslink_pages as cp
raw = collections.defaultdict(list)
for m in re.finditer(r'<dt id="(term-[a-z0-9-]+)">(.*?)</dt>', open("glossary.html").read(), re.S):
    for k in cp.derive_keys(m.group(2)):
        raw[k.lower()].append(m.group(1))
d = {k: v for k, v in raw.items() if len(v) > 1}
print("duplicate alias keys:", len(d))
for k, v in d.items():
    print("  ", k, "->", v)
EOF

# 2. Every link's anchor text belongs to the entry it points at.
#    Expect "mismatched links: 0".
python3 - <<'EOF'
import sys, re, glob; sys.path.insert(0, "tools")
import crosslink_pages as cp
k2s, _ = cp.load_glossary_terms()
bad = 0
for f in glob.glob("*.html") + glob.glob("meetings/*.html") + glob.glob("breaches/*.html"):
    for m in re.finditer(r'<a class="glossary-link" href="[^"]*#(term-[a-z0-9-]+)">([^<]+)</a>', open(f).read()):
        want = k2s.get(m.group(2).lower())
        if want and want != m.group(1):
            print(f'  {f}: "{m.group(2)}" -> {m.group(1)}, expected {want}'); bad += 1
print("mismatched links:", bad)
EOF
```

## Relationship to `crosslink_glossary.py`

| Script | Operates on | Produces |
|---|---|---|
| `crosslink_glossary.py` | `glossary.html` only | `<a class="glossary-link" href="#term-...">` (anchor-only, intra-page) |
| `crosslink_pages.py` | All content pages | `<a class="glossary-link" href="glossary.html#term-...">` (cross-page) |

Both share the same `derive_keys` and slugification logic and use the same `glossary-link` class so they look identical in the DOM.
