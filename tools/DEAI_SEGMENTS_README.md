# deai_segments.py

Mechanical half of a section-9 style pass (see
[`docs/EDITORIAL_STANDARDS.md`](../docs/EDITORIAL_STANDARDS.md#9-voice-prose-that-reads-as-generated)).
It finds prose blocks that show a pattern, lets a rewriter replace them without
ever editing a page directly, and refuses any replacement it can prove changed
something other than style.

It cannot judge meaning. A rewrite that passes every check here can still drop
a hedge's force, imply an order, or close an open list. Each accepted rewrite
still needs the adversarial meaning review the standard describes.

## Commands

```sh
python3 tools/deai_segments.py extract pages.txt segs.json --skip-intensifier-only
python3 tools/deai_segments.py batch segs.json batches/ 5
python3 tools/deai_segments.py check batches/batch-01.json rewrites.json
python3 tools/deai_segments.py apply segs.json accepted.json report.json --dry-run
python3 tools/deai_segments.py apply segs.json accepted.json report.json
python3 tools/deai_segments.py verify --ref HEAD
python3 tools/deai_segments.py labels pages.txt report.json --dry-run
python3 tools/deai_segments.py runin pages.txt report.json --dry-run
python3 tools/deai_segments.py self-test
```

- `extract` takes one page path per line and writes every flagged segment with
  its byte offsets. A segment is the inner HTML of one innermost `<p>`, `<li>`,
  `<dd>`, `<td>`, `<th>` or `<figcaption>` inside `<main>`.
- `batch` splits segments into files of roughly equal size, never splitting a
  page, plus a `manifest.json`.
- `check` is for rewriters: it prints each rewrite the apply step would
  reject and exits 1 if there are any.
- `apply` re-runs the check, then writes accepted rewrites last-offset-first.
  It refuses a segment whose bytes changed since extraction.
- `verify` compares every page modified since a git ref and fails unless only
  prose text moved.
- `labels` is a mechanical label pass, separate from any rewrite. A list item
  that opens with a link and then ` - ` gets a colon in place of the dash. An
  acronym followed by ` - ` and its expansion gets the expansion in
  parentheses, but only when the expansion's initials spell the acronym. It
  never touches link text, code, headings, generated regions or
  `glossary.html`, whose headword separator the cross-link tooling parses. Bold
  term labels are left to `runin`: a colon there would only produce the
  `<strong>X</strong>:` bullet section 9 calls a tell.
- `runin` turns a bold term label followed by ` - ` into the site's run-in
  head: `<strong>Term</strong> - what it is` becomes `<strong>Term.</strong>
  What it is`. A trailing parenthetical stays outside the bold and takes the
  period. Labels ending in a decimal, a percentage, a dollar amount or an
  ATT&CK technique ID get a colon instead. The description keeps a lowercase
  first letter when it opens with an identifier (`eBPF`, `kubectl`). The
  docstring lists exactly which positions count as a label. A bold term in the
  middle of a sentence is never touched; those need a hand edit, usually a
  colon or parentheses. Same exclusions as `labels`.

## What the check rejects

- any change to tags, attributes, comments, or the text inside `<a>`, `<code>`,
  `<kbd>`, `<abbr>` or `<time>`;
- any added, removed or changed number;
- a changed count of a hedge or quantifier ("most", "almost", "primarily",
  "increasingly", "at least" and the rest of the list in the source);
- an em or en dash in any form, or a new spaced-hyphen aside;
- an edited, added or dropped quoted passage. Unbalanced straight quotes pin
  the whole segment;
- a changed count of mentions of any vendor named on `vendor-landscape.html`.

## What is never extracted

Headings, `<head>`, code, `<pre>`, SVG, scripts, blockquotes, the generated
`SESSION_BLOCK` and `QUOTES` regions, page chrome (byline, TOC, author card,
breadcrumbs, share bar, card markup), and any block containing the page's pull
quote. Generated and recorded pages belong in the exclusion list of the pass
itself; see the standard.

## After applying

Run `python3 tools/check_faq_jsonld_parity.py --fix` (FAQ answers and glossary
definitions are copied into JSON-LD), then rebuild `search-index.json` twice
with `python3 tools/build_search_index.py`. The second run must change
nothing. Finish with `verify`.
