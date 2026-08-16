# `check_docs_consistency.py`

The mechanical half of the weekly documentation review. The judgment half lives
in `.github/workflows/weekly-docs-review.yml`; the standard both check against is
[`docs/EDITORIAL_STANDARDS.md`](../docs/EDITORIAL_STANDARDS.md).

```bash
python3 tools/check_docs_consistency.py            # list findings
python3 tools/check_docs_consistency.py --check    # CI gate, exit 1 on fixable drift
python3 tools/check_docs_consistency.py --fix      # apply
python3 tools/check_docs_consistency.py --report r.md
```

## Why it exists

The review used to be one model pass over the whole site. PR #1483 is the worked
example: most of what it found needed no judgment at all, it touched ~80 files,
it took two days to review, and it was closed unmerged against a `main` that
merges news PRs several times a day. Every fix in it was lost - including the
`breach-lessons.html` date mismatch it reported, which was still live months
later.

Paying a model to rediscover that class of defect every week costs tokens,
phrases the same problem differently each time, and buries the findings that
actually need a person. So anything decidable moved here, and the weekly model
pass was left with accuracy, neutrality, member temperature, and reading level.

## Fixable vs reported

The distinction drives the exit code, and it is the whole design.

**Fixable** means wrong *and* the correct value is derivable from something
already in the repo. `--fix` applies it; `--check` fails CI so it cannot
accumulate.

**Reported** means wrong or suspicious, but the right answer is not in the repo:
a real authoring date, a missing image, whether a glossary term earns its place.
These never auto-apply and never fail CI - a gate that failed on something CI
cannot fix would block every push until a human intervened, which is how a gate
gets disabled rather than satisfied.

**Nothing here deletes.** The script rewrites values in place and does nothing
else. Removal is a human decision every time, and the weekly workflow asserts
this from the outside as well.

## The checks

| Check | Class | What it catches |
|---|---|---|
| `date-visible-vs-jsonld` | fixable | `Last updated <date>` disagreeing with the page's own JSON-LD `dateModified` |
| `date-attr-text` | fixable | `<time datetime>` disagreeing with the date printed beside it |
| `em-dash` | fixable | Em-dashes where the standard calls for a spaced hyphen |
| `date-incoherent` | reported | `datePublished` after `dateModified` |
| `date-placeholder` | reported | January 1 `datePublished` - the unfilled template |
| `og-asset-missing` | reported | `og:image` / `twitter:image` naming a file that does not exist |
| `count-drift` | reported | A prose inventory number that is false |
| `glossary-orphan` | reported | A term in linkable prose that carries no glossary link |
| `dead-tool-ref` | reported | A doc naming a `tools/*.py` that no longer exists |

## Things that look like bugs and are not

Four narrowings, each of which the first version got wrong. They are the reason
the output is worth reading.

**Body `<time>` elements are not page dates.** Only the `<p class="page-meta">`
byline makes a claim about the page itself. Matching any `<time>` flagged
`conferences.html` and `threat-research.html`, whose `<time>` elements are
session and conference dates.

**`Published X` with a later `dateModified` is not a defect.** An article
published in July and edited in August is exactly that. PR #1483 rewrote
`breach-lessons.html`'s label on this basis; that was an editorial choice
presented as a correction.

**The breach series dates by incident, not by authorship.** 0ktapus is
2022-08-26, Log4Shell 2021-12-14, Codecov 2021-04-15 - each its incident date.
That is not what schema.org means by `datePublished`, but it is applied
consistently, so it is a convention rather than drift, and changing it is a
decision about the whole series. Only January 1 is flagged, because a real
incident has a real date.

**`N+` is a floor, and count claims are reported rather than fixed.** "300+
glossary terms" with 317 live is true. An earlier version resynced every count
toward the canonical value and produced three wrong edits out of four - the
worst being `README.md`'s "102 meeting recaps in `img/og/meetings/`", where the
sentence counts image *files* (104) and not recaps (107), so the "fix" would
have written a confident falsehood and hidden the three missing cards that
`og-asset-missing` reports separately. A number in prose carries context a regex
cannot read.

## Known exceptions

`COUNT_EXCEPTIONS` records numbers that look like inventory claims and are not -
RSA's ~600 exhibitors on `conferences.html`, the README's per-section subtotal.
Same idea as `UNREACHABLE` in `check_glossary_coverage.py`: a silently skipped
false positive gets rediscovered by the next reader, while one listed with a
reason is an argument you can disagree with. Add to it rather than widening a
regex.

## Notes

- Imports `canonical_counts()` and `display_values()` from `sync_counts.py`
  rather than recomputing. If you add a count there, this picks it up.
- Skips `<script>`, `<style>`, and fenced code blocks for prose checks. An
  em-dash in vendored JS or a code sample is not prose.
- **Git cannot tell you when a page's content last changed.** Site-wide SRI and
  chrome sweeps touch every file at once, so all 272 pages share a last-commit
  date. That is why `dateModified` is treated as authoritative and why the
  weekly workflow filters sweep commits out of its review slice.
- Vendor counts *are* derivable now. `vendor-landscape.html` has no card markup,
  so the number was hand-typed and drifted: about.html said 350+, README.md and
  CONTRIBUTING.md said 360+, and the truth was 308 distinct vendors across 32
  categories. `sync_counts.vendor_landscape()` counts the
  `<li><strong>Name</strong>` entries inside the category sections, skipping the
  sentence-shaped caveats and deduplicating the 24 vendors that appear under
  more than one category.
