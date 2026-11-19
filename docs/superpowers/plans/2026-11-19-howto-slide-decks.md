# How-to Guide Slide Decks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the outline format, gate, link writer and .pptx renderer for how-to guide slide decks, and take the Splunk SPL pilot deck through to Shawn's approval and publication.

**Architecture:** Each guide's deck is a plain-text outline in `tools/decks/`. `tools/build_howto_decks.py` (standard library only, so CI can run it) parses outlines, checks them against their guide page, keeps `tools/decks/published.json`, and writes the deck links into guide pages. `tools/howto_deck_render.py` (python-pptx, local only) turns an outline into a 16:9 .pptx, which is uploaded through the Google Drive connector and converted to Google Slides.

**Tech Stack:** Python 3.10+ standard library (`html`, `re`, `json`, `hashlib`, `dataclasses`, `argparse`); python-pptx (local only); Google Drive and Google Slides connector tools; GitHub Actions (`validate-html.yml`).

**Spec:** `docs/superpowers/specs/2026-11-19-howto-slide-decks-design.md`

## Global Constraints

- Decks are CC BY-NC 4.0; guides stay CC BY-NC-ND 4.0.
- Attribution "Cloud Security Office Hours, csoh.org" and the license on the first and last slides.
- 16:9 slides. Palette: `#0f172a` primary, `#0369a1` secondary, `#f59e0b` accent, `#f8fafc` light background, `#1f2937` text, `#5b6573` muted. Fonts: Space Grotesk (headings), Source Sans 3 (body), Source Code Pro (code). Text meets 4.5:1 contrast.
- Body text at least 18 pt, code at least 14 pt, at most 12 code lines and 40 words of prose per slide.
- 12 to 20 slides per deck, counting the generated cover and closing slides.
- Every slide's footer shows the guide's csoh.org address and the slide number.
- No U+2013 or U+2014, and no spaced hyphen used as a dash, in any slide text. No AI tells from `docs/agent-lessons.md` section 2, no ranking of third parties, ATT&CK v19 names, the Wiz disclosure where the guide carries it.
- A deck claims no more testing than its guide's "How this page was checked" line, and none if the guide has no such line.
- Every code excerpt is a contiguous run of whole lines from one `<pre>` block on its guide.
- Outlines, tools, the mapping file and build output live under `tools/`, which never ships.
- `--check` and `--self-test` must not import python-pptx.
- Uploading, sharing publicly and deleting Drive files each need Shawn's explicit go. Never write the deck owner's email address into the repo.
- Commit locally with explicit paths (never `git add -A`); push only when Shawn says so. No CI-skip token in any commit message.

## Review Focus

1. **Code that differs only by escaping or whitespace.** Guide `<pre>` text is HTML-escaped (`&gt;`, `&amp;`, `&lt;`) and may carry trailing spaces; an outline excerpt is plain text. A reader expects an excerpt that matches what the page displays to pass. Covered by self-test cases `excerpt_entities` and `excerpt_trailing_space` (Task 2).
2. **A broken outline.** An unterminated code fence or a slide with no body must fail with `file:line`, not swallow the slides after it. Covered by `unterminated_fence` and `empty_slide` (Task 1).
3. **Guides without a "How this page was checked" line** (jq and JMESPath, OVAL and SCAP, regex). Stamping must still land the deck line at the end of the info box. Covered by `stamp_no_checked_line` (Task 3).
4. **Re-stamping.** Running `--stamp` twice, or after a deck's ID changes, must leave exactly one deck line holding the current ID. Covered by `stamp_idempotent` and `stamp_new_id` (Task 3).
5. **Section headings with markup.** Guide headings can contain `<code>` or entities; a `section:` line names the text a reader sees. Covered by `section_with_markup` (Task 2).

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/build_howto_decks.py` (create) | Outline parser, style limits, guide checks, mapping, link stamping, CLI, self-test. Standard library only. |
| `tools/howto_deck_render.py` (create) | python-pptx renderer and its output verifier. Imported only by `--build` and `--self-test-render`. |
| `tools/decks/_cloudtrail-lab.deck` (create) | Shared slides for the guides that use the 24-event CloudTrail lab. |
| `tools/decks/splunk-spl.deck` (create) | Pilot outline. |
| `tools/decks/published.json` (create) | Slug to `{id, published, outline_sha256}`. |
| `tools/DECKS_README.md` (create) | How to write, build, publish and re-publish a deck. |
| `.github/workflows/validate-html.yml` (modify) | New gate step. |
| `.gitignore` (modify) | `/tools/decks/build/`. |
| `LICENSE` (modify) | Third clause for the decks. |
| `CLAUDE.md` (modify) | One row in the "Generated content" table. |
| `howto/splunk-spl.html` (modify, Task 8 only) | Deck line stamped into the info box. |

## Outline format (used by Tasks 1, 5)

```text
title: Splunk SPL for cloud security
guide: howto/splunk-spl.html
promise: Five searches that find one leaked AWS key in CloudTrail.

== A search is a pipeline
section: A search is a pipeline
Each command works on the events the one before it produced.
- Filter first, then shape the results.
```spl
index=cloudtrail readOnly=false
```
credit: Splunk security_content, Apache-2.0

== include: _cloudtrail-lab.deck
```

- Header: `key: value` lines before the first `== ` line. `title`, `guide`, `promise` are required; anything else is an error.
- `== <heading>` starts a slide. `== include: <file>` splices that file's slides in place. An included file has no header and may not include others.
- In a slide, outside a fence: `section: <guide heading text>` and `credit: <text>` are fields; `- ` lines are bullets; other non-blank lines are prose, and consecutive prose lines join into one paragraph with a space; a blank line ends a paragraph.
- At most one fence per slide: a line starting ```` ``` ```` (optional language word) opens it, a line that is exactly ```` ``` ```` closes it. Fence lines are kept verbatim.
- The slug is the outline's filename without `.deck`. Files starting `_` are fragments, never decks.

---

### Task 1: Outline parser and style limits

**Files:**
- Create: `tools/build_howto_decks.py`

**Interfaces:**
- Produces:
  - `class OutlineError(Exception)`, message always starts `"<file>:<line>: "`.
  - `@dataclass Slide: heading: str; section: str | None; paragraphs: list[str]; bullets: list[str]; code: list[str] | None; code_lang: str | None; credit: str | None; where: str` (`where` is `"file:line"` of its `==` line).
  - `@dataclass Deck: slug: str; title: str; guide: str; promise: str; slides: list[Slide]; resolved_text: str` (`resolved_text` is the outline with includes spliced, used for the sha256).
  - `parse_outline_text(text: str, name: str, include_dir: Path) -> Deck`
  - `parse_outline(path: Path) -> Deck`
  - `style_findings(deck: Deck) -> list[str]`, each finding prefixed with the slide's `where`.
  - Constants: `MAX_PROSE_WORDS = 40`, `MAX_CODE_LINES = 12`, `MAX_CODE_COLS = 90`, `MAX_HEADING_WORDS = 12`, `MIN_SLIDES = 12`, `MAX_SLIDES = 20`, `GENERATED_SLIDES = 2`, `DECKS_DIR = Path("tools/decks")`.
  - `self_test() -> int` and a `CASES` list the later tasks append to; prints `self-test: <n> cases passed` and returns 0, or names each failing case and returns 1.

- [ ] **Step 1: Write the self-test cases**

Each case builds outline text in memory and asserts on the result:

```python
# parse_ok: the format example above (with a stub fragment) parses
d = parse_outline_text(SAMPLE, "sample.deck", tmp)
assert d.slug == "sample" and d.slides[0].heading == "A search is a pipeline"
assert d.slides[0].paragraphs == ["Each command works on the events the one before it produced."]
assert d.slides[0].bullets == ["Filter first, then shape the results."]
assert d.slides[0].code == ["index=cloudtrail readOnly=false"] and d.slides[0].code_lang == "spl"
assert d.slides[0].credit == "Splunk security_content, Apache-2.0"
# include_spliced: slides from the fragment appear where the include line was
# nested_include: a fragment that includes another raises OutlineError
# missing_header: no `guide:` raises OutlineError naming line 1
# unknown_header_key: `author: x` raises
# unterminated_fence: raises OutlineError whose message contains ":<fence line>:"
# two_fences: a second fence in one slide raises
# empty_slide: a slide with only a heading raises
# too_many_words: 41 prose words -> one finding containing "40"
# too_many_code_lines: 13 code lines -> finding containing "12"
# code_too_wide: a 91-character code line -> finding containing "90"
# heading_too_long: 13 words -> finding
# slide_count: 9 authored slides (11 with generated) -> finding; 18 authored (20) -> none
# em_dash / en_dash: U+2014 or U+2013 in prose, heading or credit -> finding
# spaced_hyphen: "word - word" in prose -> finding; the same inside code -> none
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `python3 tools/build_howto_decks.py --self-test`
Expected: non-zero exit; the cases fail because the parser does not exist yet.

- [ ] **Step 3: Implement the parser, `style_findings`, `self_test`, and a `main()` with `--self-test`**

Word count is `len(text.split())` over paragraphs and bullets. The spaced-hyphen test is the regex `(?<=\S) - (?=\S)` on prose, headings and credits only.

- [ ] **Step 4: Run it and confirm it passes**

Run: `python3 tools/build_howto_decks.py --self-test`
Expected: `self-test: <n> cases passed`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add tools/build_howto_decks.py
git commit -m "decks: outline parser and style limits for how-to slide decks"
```

### Task 2: Checks against the guide page

**Files:**
- Modify: `tools/build_howto_decks.py`

**Interfaces:**
- Consumes: `Deck`, `Slide`, `CASES` from Task 1.
- Produces:
  - `guide_code_blocks(html: str) -> list[list[str]]`: each `<pre[^>]*>(.*?)</pre>` (DOTALL), `html.unescape`d, split on `\n`, each line `rstrip()`ped.
  - `guide_headings(html: str) -> dict[str, str | None]`: visible text of every `<h2>`/`<h3>` (tags stripped, unescaped, whitespace collapsed) to its `id`, or `None` if it has none.
  - `is_contiguous_run(excerpt: list[str], block: list[str]) -> bool`: excerpt lines (each `rstrip()`ped) equal some consecutive slice of block.
  - `guide_findings(deck: Deck, html: str) -> list[str]`: an excerpt that is not a contiguous run of any block; a `section:` that is not a heading.

- [ ] **Step 1: Add the self-test cases**

```python
# excerpt_ok: excerpt = lines 2-3 of a planted <pre> -> no finding
# excerpt_gap: lines 1 and 3 (skipping 2) -> finding
# excerpt_across_blocks: last line of block A + first of block B -> finding
# excerpt_entities: <pre>a &gt; b &amp;&amp; c</pre> matches excerpt "a > b && c"
# excerpt_trailing_space: block line "x  " matches excerpt "x"
# excerpt_one_char_changed: control; flipping one character -> finding
# section_ok: <h3 id="step-load">2. Load the lab data</h3> -> heading maps to "step-load"
# section_with_markup: <h3>Use <code>stats</code> &amp; count</h3> matches "Use stats & count"
# section_missing: a section: line naming no heading -> finding
```

- [ ] **Step 2: Run it and confirm the new cases fail**

Run: `python3 tools/build_howto_decks.py --self-test`
Expected: exit 1, naming the cases above.

- [ ] **Step 3: Implement the four functions**

- [ ] **Step 4: Run it and confirm it passes**

Run: `python3 tools/build_howto_decks.py --self-test`
Expected: exit 0.

- [ ] **Step 5: Commit**

```bash
git add tools/build_howto_decks.py
git commit -m "decks: check slide code and sections against the guide page"
```

### Task 3: Mapping, guide-page links, CLI and CI gate

**Files:**
- Modify: `tools/build_howto_decks.py`
- Create: `tools/decks/published.json` (contents `{}`), `tools/DECKS_README.md`
- Modify: `.github/workflows/validate-html.yml`, `.gitignore`, `CLAUDE.md`

**Interfaces:**
- Consumes: Tasks 1 and 2.
- Produces:
  - `MAPPING = DECKS_DIR / "published.json"`, shape `{"<slug>": {"id": str, "published": "YYYY-MM-DD", "outline_sha256": str}}`, keys sorted, 2-space indent, trailing newline.
  - `outline_sha256(deck: Deck) -> str` (sha256 hex of `resolved_text` encoded UTF-8).
  - `deck_line_html(pres_id: str) -> str`, exactly (one line, 12-space indent as in the info box):

```html
            <p class="u-mt-075" data-howto-deck><strong>Slides:</strong> <a href="https://docs.google.com/presentation/d/{id}/export/pdf" target="_blank" rel="noopener noreferrer">download the PDF</a> or <a href="https://docs.google.com/presentation/d/{id}/copy" target="_blank" rel="noopener noreferrer">make your own editable copy</a> (copying needs a Google account). The slides are licensed <a href="https://creativecommons.org/licenses/by-nc/4.0/" target="_blank" rel="noopener noreferrer">CC BY-NC 4.0</a>.</p>
```

  - `stamp_page(html: str, pres_id: str | None) -> str`: replaces the existing `<p[^>]*data-howto-deck[^>]*>.*?</p>` line, or inserts the line before the `</div>` that closes the first `<div class="info-box--blue">`; removes the line when `pres_id` is None. Raises `ValueError` if the page has no such info box.
  - `link_findings(slug: str, html: str, mapping: dict) -> list[str]`: page has a deck line but no mapping entry, or the reverse, or the line differs from `deck_line_html(mapping[slug]["id"])`.
  - CLI flags: `--check` (all decks: parse, `style_findings`, `guide_findings`, `link_findings` for every `howto/*.html`; exit 1 on any finding), `--self-test`, `--stale` (report decks whose `outline_sha256` differs from the mapping; exit 0), `--status` (per guide: outline yes/no, published yes/no; exit 0), `--stamp` (rewrite every guide page from the mapping), `--record SLUG PRES_ID` (write today's date and the current sha256 into the mapping, then stamp that page), `--build SLUG [SLUG ...]` (Task 4).

- [ ] **Step 1: Add the self-test cases**

```python
# stamp_insert: page with info box + checked line -> deck line is the last child of the box
# stamp_no_checked_line: info box with only the Time paragraph -> deck line still last in the box
# stamp_idempotent: stamp(stamp(page, "A"), "A") == stamp(page, "A")
# stamp_new_id: stamp(stamp(page, "A"), "B") has exactly one data-howto-deck line, holding B
# stamp_remove: stamp(stamp(page, "A"), None) == page
# stamp_no_info_box: raises ValueError
# links_unmapped_line: deck line on a page whose slug is not in the mapping -> finding
# links_missing_line: mapping entry, page without line -> finding
# links_wrong_id: line with id A, mapping says B -> finding
# sha_changes: editing one prose word changes outline_sha256
```

- [ ] **Step 2: Run it and confirm the new cases fail**

Run: `python3 tools/build_howto_decks.py --self-test`
Expected: exit 1.

- [ ] **Step 3: Implement the functions and CLI flags above (not `--build`)**

`--check` must pass with no outlines yet and an empty mapping, and print a one-line summary: `decks: <n> outlines checked, <m> guide pages checked, <k> findings`.

- [ ] **Step 4: Run both modes and confirm they pass**

Run: `python3 tools/build_howto_decks.py --self-test && python3 tools/build_howto_decks.py --check`
Expected: both exit 0; `--check` reports 0 outlines, every guide page checked, 0 findings.

- [ ] **Step 5: Control on the real tree**

With `howto/regex-for-security.html` committed and unmodified, insert `deck_line_html("planted")` at the end of its info box, run `python3 tools/build_howto_decks.py --check`, confirm exit 1 with one finding naming that page, then restore with `git checkout -- howto/regex-for-security.html` and confirm `--check` exits 0 again.

- [ ] **Step 6: Add the CI step, ignore rule and docs**

`validate-html.yml`, after the glossary-usage step, a step named `Assert how-to deck outlines and links`, id `howto-decks`, running `python3 tools/build_howto_decks.py --self-test` then `--check`, each through `2>&1 | tee -a check-howto-decks.log` under `set -o pipefail`, with a comment above it stating what it guards and that the self-test is the control. `.gitignore`: `/tools/decks/build/`. `CLAUDE.md` "Generated content" table: `| How-to deck links (`data-howto-deck`) on howto/ pages | tools/build_howto_decks.py --stamp | --check in validate-html.yml |`. `tools/DECKS_README.md`: the outline format, the CLI flags, the publish steps from the spec, and the rule that re-publishing gives a new ID.

- [ ] **Step 7: Run the doc gates**

Run: `python3 tools/check_readme_coverage.py --check && python3 tools/check_docs_consistency.py --check`
Expected: both exit 0.

- [ ] **Step 8: Commit**

```bash
git add tools/build_howto_decks.py tools/decks/published.json tools/DECKS_README.md .github/workflows/validate-html.yml .gitignore CLAUDE.md
git commit -m "decks: deck links on guide pages, mapping, and a CI gate"
```

### Task 4: The .pptx renderer and the license clause

**Files:**
- Create: `tools/howto_deck_render.py`
- Modify: `tools/build_howto_decks.py` (`--build`, `--self-test-render`), `LICENSE`

**Interfaces:**
- Consumes: `Deck`, `Slide`, `DECKS_DIR`.
- Produces:
  - `class LayoutError(Exception)`.
  - `render_deck(deck: Deck, out: Path) -> Path`: writes the .pptx, raising `LayoutError` naming the slide's `where` if any element would end below 6.9 in.
  - `verify_pptx(path: Path, deck: Deck) -> list[str]`: reopens the file and returns findings.
  - Build output: `DECKS_DIR / "build" / f"{slug}.pptx"`.

Layout values (pin these; the pilot may tune them in one place, a `STYLE` dict at the top of the file):
- Slide 13.333 x 7.5 in; background `#f8fafc`; a full-height bar 0.12 in wide in `#0369a1` at the left edge.
- Heading: Space Grotesk bold 32 pt `#0f172a`, box at (0.6, 0.45) in, 12.1 in wide.
- "In the guide: <section>" line under the heading when `section` is set: Source Sans 3 14 pt `#5b6573`.
- Prose and bullets: Source Sans 3 20 pt `#1f2937`.
- Code: Source Code Pro 14 pt `#e2e8f0` in a box filled `#0f172a`, 0.15 in inner padding.
- Credit under the code: Source Sans 3 12 pt `#5b6573`.
- Footer, 0.3 in from the bottom: `csoh.org/<guide path>` left, `<n> / <total>` right, Source Sans 3 12 pt `#5b6573`.
- Height estimate: prose lines = sum of `ceil(len(paragraph) / 85)`, 20 pt x 1.25 per line; code = lines x 14 pt x 1.3 + padding.
- Cover (slide 1): background `#0f172a`; title Space Grotesk bold 44 pt `#ffffff`; promise 24 pt `#e2e8f0`; then `Cloud Security Office Hours, csoh.org` in `#f59e0b` and `Slides licensed CC BY-NC 4.0` in `#e2e8f0`, both 18 pt.
- Closing (last slide), heading `Do the full lab`, body: `The guide has every step, the lab data and the answers: https://csoh.org/<guide path>`, then `Cloud Security Office Hours, csoh.org. Slides licensed CC BY-NC 4.0 (creativecommons.org/licenses/by-nc/4.0). Third-party excerpts keep their own licenses.`
- Speaker notes: `Guide section: https://csoh.org/<guide>#<id>` when the section heading has an id; `Guide section: "<section>" at https://csoh.org/<guide>` when it has none; `Full guide: https://csoh.org/<guide>` when the slide has no section.

- [ ] **Step 1: Install python-pptx locally**

Run: `python3 -m pip install python-pptx && python3 -c "import pptx; print(pptx.__version__)"`
Expected: a version number. (Local interpreter only; CI never installs it.)

- [ ] **Step 2: Write `--self-test-render` cases**

```python
# render_ok: a 10-slide in-memory deck renders; verify_pptx returns []
#   and the reopened file has 12 slides, width 12192000 EMU, height 6858000 EMU,
#   every slide's text contains "csoh.org/howto/", every slide has notes text
# render_overflow: a slide with 12 code lines plus 40 words of prose raises LayoutError naming its where
# render_fonts: every run on non-footer, non-credit, non-guide-line text is >= 18 pt, code runs are 14 pt
```

- [ ] **Step 3: Run it and confirm it fails**

Run: `python3 tools/build_howto_decks.py --self-test-render`
Expected: exit 1 (renderer missing).

- [ ] **Step 4: Implement `render_deck`, `verify_pptx`, and the `--build` / `--self-test-render` flags**

`--build` imports `howto_deck_render` inside the function, refuses a deck with any `--check` finding, writes the file, runs `verify_pptx`, and exits 1 on any finding.

- [ ] **Step 5: Run it and confirm it passes, and that CI mode still has no pptx import**

Run: `python3 tools/build_howto_decks.py --self-test-render && python3 -X importtime tools/build_howto_decks.py --check 2>&1 | grep -c pptx`
Expected: render self-test exits 0; the grep prints `0`.

- [ ] **Step 6: Add the license clause**

In `LICENSE`, change "This project uses a dual license model:" to "This project uses three licenses:" and add after item 2:

```text
3) Slide decks made from the how-to guides, and the outlines in tools/decks/
   they are built from, are licensed under Creative Commons
   Attribution-NonCommercial 4.0 International (CC BY-NC 4.0). Third-party
   material quoted on a slide keeps its own license, as described below.
```

- [ ] **Step 7: Lint and commit**

```bash
ruff check tools/build_howto_decks.py tools/howto_deck_render.py
git add tools/howto_deck_render.py tools/build_howto_decks.py LICENSE
git commit -m "decks: pptx renderer and CC BY-NC 4.0 clause for the decks"
```

### Task 5: The pilot outline (Splunk SPL)

**Files:**
- Create: `tools/decks/_cloudtrail-lab.deck`, `tools/decks/splunk-spl.deck`

**Interfaces:**
- Consumes: the outline format; `--check`; `--build`.

- [ ] **Step 1: Read `howto/splunk-spl.html` in full**

- [ ] **Step 2: Write `_cloudtrail-lab.deck`**

One or two slides: the 24-event CloudTrail lab and the D1 to D5 detections, worded from the text the guides share (identical across the guides that use the lab). No `section:` lines, because each including guide names those sections differently.

- [ ] **Step 3: Write `splunk-spl.deck` in the spec's deck shape**

Who it is for and what you need (from the info box, with a testing claim no stronger than its "How this page was checked" line); what SPL is and where you meet it; the one idea ("A search is a pipeline"); the shared lab; walk-through slides for the steps that teach the most (each with `section:` set to the step's exact heading and an excerpt copied from that step's code); two or three exercises as question then answer slides; common mistakes. Step 9's public rule excerpt, if used, carries `credit:` naming Splunk's security_content and its license as the guide states them. 12 to 20 slides with the generated two.

- [ ] **Step 4: Run the gate until clean**

Run: `python3 tools/build_howto_decks.py --check`
Expected: exit 0, `1 outlines checked`, 0 findings.

- [ ] **Step 5: Build it**

Run: `python3 tools/build_howto_decks.py --build splunk-spl`
Expected: `tools/decks/build/splunk-spl.pptx` written, 0 verify findings.

- [ ] **Step 6: Commit**

```bash
git add tools/decks/_cloudtrail-lab.deck tools/decks/splunk-spl.deck
git commit -m "decks: Splunk SPL pilot outline"
```

### Task 6: Fact and style review of the pilot

**Files:**
- Modify: `tools/decks/splunk-spl.deck`, `tools/decks/_cloudtrail-lab.deck`

- [ ] **Step 1: Dispatch a fresh reviewer**

Give it the two outline files and `howto/splunk-spl.html`, not this plan's conclusions. Ask for every statement on a slide that the guide does not support or that overstates it (testing claims especially), every ATT&CK name older than v19, any ranking of third parties, and any sentence showing the tells in `docs/agent-lessons.md` section 2. Each finding quotes the slide line and the guide text it conflicts with, or says the guide has none.

- [ ] **Step 2: Verify each finding against the guide before changing anything**

Grep the guide for the quoted text; drop findings whose quote is not there.

- [ ] **Step 3: Fix, then rerun the gate and the build**

Run: `python3 tools/build_howto_decks.py --check && python3 tools/build_howto_decks.py --build splunk-spl`
Expected: both exit 0.

- [ ] **Step 4: Commit**

```bash
git add tools/decks/splunk-spl.deck tools/decks/_cloudtrail-lab.deck
git commit -m "decks: fact-review fixes to the Splunk SPL pilot"
```

### Task 7: Private upload and Google rendering check

Connector calls; nothing in the repo changes unless the render needs a fix. The approved design covers a private, unshared upload; sharing is Task 8 and needs its own go.

- [ ] **Step 1: Create the folder and upload**

`create_file` with `title: "CSOH how-to decks"`, `contentMimeType: "application/vnd.google-apps.folder"`. Then `create_file` with `title: "CSOH how-to: Splunk SPL"`, `parentId: <folder>`, `contentMimeType: "application/vnd.openxmlformats-officedocument.presentationml.presentation"`, `base64Content: "sha256:<hex>:<absolute path to splunk-spl.pptx>"` (hex from `shasum -a 256`).

- [ ] **Step 2: Check ownership and visibility**

`get_file_metadata` with `includeRichMetadata: true`. Expected: `mimeType` is `application/vnd.google-apps.presentation`, owner is the connector's account, `visibility` is private. Stop if the owner is anything else.

- [ ] **Step 3: Inspect every slide as Google renders it**

`read_presentation` with `fields: ["slides.objectId"]`, then `read_slide_page_thumbnail` for each slide. Look for font substitution, text overflowing a box, code wrapping, and footer collisions. For any defect, fix `STYLE` in `howto_deck_render.py` or the outline, rebuild, re-run `--self-test-render`, upload a new copy, and add the superseded file's ID to a list for Shawn to delete. Commit any renderer change with explicit paths.

- [ ] **Step 4: Hand the private deck to Shawn**

Give him its Drive link and the list of superseded uploads to delete, and wait for his approval of the deck and his separate go to share it publicly.

### Task 8: Publish the pilot

Only after Shawn's explicit go to share.

**Files:**
- Modify: `tools/decks/published.json`, `howto/splunk-spl.html`

- [ ] **Step 1: Share it**

`share_file` with `fileId: <deck id>`, `permissionId: "anyoneWithLink"`, `role: "reader"`.

- [ ] **Step 2: Check it as a signed-out reader**

Run: `curl -sL -o <scratchpad>/pilot.pdf -w '%{http_code} %{content_type}\n' "https://docs.google.com/presentation/d/<id>/export/pdf" && head -c 5 <scratchpad>/pilot.pdf`
Expected: `200 application/pdf` and `%PDF-`. Open the PDF with the Read tool and confirm the page count equals the deck's slide count.
Run: `curl -sI "https://docs.google.com/presentation/d/<id>/copy" | grep -i '^location'`
Expected: a redirect toward Google sign-in (the copy page needs an account), which is what the deck line says.

- [ ] **Step 3: Record and stamp**

Run: `python3 tools/build_howto_decks.py --record splunk-spl <id>`
Expected: mapping entry written; `howto/splunk-spl.html` gains exactly one `data-howto-deck` line at the end of its info box.

- [ ] **Step 4: Run the gates**

Run: `python3 tools/build_howto_decks.py --self-test && python3 tools/build_howto_decks.py --check && python3 tools/stamp_code_langs.py --check`
Expected: all exit 0.
Run: `lychee --config .lychee.toml howto/splunk-spl.html`
Expected: both deck links reported OK; if either is not, add an anchored exclude to `.lychee.toml` and say so in the commit message.

- [ ] **Step 5: Check the page renders**

Open `howto/splunk-spl.html` in the preview, confirm the line sits at the end of the info box, its links are underlined, and it reads correctly in dark mode.

- [ ] **Step 6: Commit; do not push**

```bash
git add tools/decks/published.json howto/splunk-spl.html
git commit -m "decks: publish the Splunk SPL pilot deck and link it from the guide"
```

Report "committed, ready to push". The remaining guides follow in a separate plan once Shawn approves the pilot.
