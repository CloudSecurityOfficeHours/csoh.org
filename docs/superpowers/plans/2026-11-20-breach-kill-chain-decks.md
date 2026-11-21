# Breach Kill Chain Slide Decks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the outline format, page gate, link writer and rich-slide renderer for breach kill chain decks, and take the VAPOR PANDA / ARTEX pilot through to Shawn's approval and publication.

**Architecture:** Each breach page's deck is a hand-written outline in `tools/decks/breaches/`. `tools/build_breach_decks.py` (standard library only, so CI runs it) parses outlines, checks them against their breach page, keeps `tools/decks/breaches/published.json`, and writes the deck line into breach pages. `tools/breach_deck_render.py` (python-pptx, local only) draws each slide type from native shapes and verifies the saved file. Publishing reuses the how-to path through the Google Drive connector.

**Tech Stack:** Python 3.10+ standard library; python-pptx 1.0.2 (local only, in `/Users/shawn/.pyenv/versions/3.10.0/bin/python3`); Google Drive and Slides connectors; the PowerPoint connector for a local PDF preview; GitHub Actions (`validate-html.yml`); lychee.

**Spec:** `docs/superpowers/specs/2026-11-20-breach-kill-chain-decks-design.md`

## Global Constraints

- Decks are CC BY-NC 4.0; breach pages stay CC BY-NC-ND 4.0. The cover and closing carry "Cloud Security Office Hours, csoh.org" and the licence.
- 16:9 slides. Palette and fonts from `tools/howto_deck_render.py` `STYLE` (import it, never copy values). Text meets 4.5:1 contrast against its own fill, including text on phase bands, chips and diagram boxes.
- Body text at least 18 pt; small labels (footer, credit, source line, chip, slide-type label) at least 14 pt.
- 18 to 36 slides per deck, counting the three generated slides (cover, how to use this deck, closing).
- Every slide's footer shows `csoh.org/<page>` and `n / total`; every slide has speaker notes.
- No U+2013 or U+2014 and no spaced hyphen used as a dash in any slide text or note. No AI tells from `docs/agent-lessons.md` section 2, no ranking of third parties, ATT&CK v19 names, the Wiz disclosure where the page carries it.
- A non-background slide says nothing the page does not; hedges and attributions ("per CrowdStrike", "likely", "about") survive; victims the page anonymizes stay anonymous.
- A background slide is labelled "Background", names its source on the slide, and its `source:` URL is on an allowed host.
- `--check` and `--self-test` must not import python-pptx.
- Breach outlines and their mapping live only under `tools/decks/breaches/`, so `build_howto_decks.py` (which globs `tools/decks/*.deck` without recursing) never reads them.
- Uploading, sharing publicly and deleting Drive files each need Shawn's explicit go. Never write the deck owner's email address into the repo.
- Commit locally with explicit paths (never `git add -A`); push only when Shawn says so. No CI-skip token in any commit message.

## Review Focus

1. **Page hash stability.** Stamping the deck line, glossary cross-linking (`crosslink_pages.py` wraps words in `<a>`), and `sync_chrome.py` nav or footer edits must not flag a deck stale; a changed sentence in the page's `<main>` must. Pinned by `page_hash_stable` in Task 2.
2. **Numbers in their many spellings.** `1,500+` must match the page's `1,500`; `1.4 billion` must match `1.4`; `70%` must match `70`; digits inside a word (`IMDSv2`, `T1606`, `artx5v`) are not numbers. Pinned by `numbers_normalized` in Task 2.
3. **Relative and absolute links.** A related link written `breaches/storm-0940-connectwise.html` must match the page's `href="storm-0940-connectwise.html"`; a source URL that differs from the page's only by a trailing slash must match. Pinned by `links_resolve` in Task 2.
4. **Speaker notes are content.** A dash, an unsupported number or a technique ID in the notes is a finding exactly as on the slide, except on background slides. Pinned by `notes_checked` in Task 2 and `notes_dash` in Task 1.
5. **Malformed typed lines.** An empty field (`stat: 200+ | | x`), a wrong field count, or a typed line the slide's layout does not take must fail with `file:line`, not render a hole. Pinned by `typed_line_empty_field` and `typed_line_wrong_layout` in Task 1.

---

## File Structure

| File | Responsibility |
|---|---|
| `tools/build_breach_decks.py` (create) | Outline parser, style limits, page model and gate, mapping, stale report, stamping, CLI, self-test. Standard library only. Imports `EM_DASH`, `EN_DASH`, `SPACED_HYPHEN_RE`, `PRES_ID_RE`, `SLUG_RE`, `SHA256_RE`, `DATE_RE`, `_is_iso_date` and `OutlineError` from `build_howto_decks`. |
| `tools/breach_deck_render.py` (create) | python-pptx renderer for every layout, phase palette, contrast check, output verifier. Imports `STYLE`, `SLIDE_W_EMU`, `SLIDE_H_EMU`, `ATTRIBUTION`, `LICENSE_LINE` from `howto_deck_render`. |
| `tools/decks/breaches/vapor-panda-artex.deck` (create) | Pilot outline. |
| `tools/decks/breaches/published.json` (create, Task 9) | Slug to `{id, published, outline_sha256, page_sha256}`. |
| `tools/DECKS_README.md` (modify) | A "Breach kill chain decks" section: format, layouts, gate, publishing. |
| `.github/workflows/validate-html.yml` (modify) | Gate and stale steps; path filter. |
| `.gitignore` (modify) | `/tools/decks/breaches/build/`. |
| `LICENSE` (modify) | Clause 3 covers breach decks and their outlines. |
| `CLAUDE.md` (modify) | A row in the "Generated content" table. |
| `breaches/vapor-panda-artex.html` (modify, Task 9 only) | Deck line stamped in. |

## Outline format (used by Tasks 1, 4, 5, 6)

```text
title: VAPOR PANDA / ARTEX
page: breaches/vapor-panda-artex.html
as-of: 2026-11-20
promise: One operator, a graph of AI agents, and 200+ organizations in 11 days.

== The metadata service handed over a fleet
layout: stage
stage: 04
phase: Credential Access
technique: T1552.005 | Cloud Instance Metadata API
fact: Queried | the cloud Instance Metadata Service
fact: Obtained | a role able to command thousands of instances
A role that can command a fleet turns one compromised host into all of them.
notes:
At a US pharmaceutical organization the agent asked the metadata service
for credentials and got a role that could administer thousands of instances.

== What IMDSv2 changes
layout: background
source: AWS documentation | https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html
IMDSv2 requires a session token...
notes:
...
```

- Header: exactly `title`, `page`, `as-of`, `promise`, each once. `page` must be `breaches/<slug>.html`; `as-of` is `YYYY-MM-DD`.
- A slide starts with `== heading`. Its first line is `layout: <name>` (default `text` when absent).
- Control lines: `layout:`, `stage:`, `phase:`, `source: name | url`, `credit:`. Each at most once per slide.
- Typed lines: `key: field | field ...`, split on ` | `; every field non-empty after strip.
- Prose lines join into a paragraph; a blank line ends it. `- ` lines are bullets. Prose after a bullet is a finding, as in the how-to format.
- `notes:` on its own line starts the notes; everything to the next `== ` is notes (paragraphs split on blank lines). Notes are required on every slide.
- No includes and no code fences in breach outlines.

### Layouts

| Layout | Typed lines (count, fields) | Prose and bullets | Other requirements |
|---|---|---|---|
| `text` | none | prose and bullets, at least one | |
| `stats` | `stat` 2 to 4, fields `value | label | detail` | optional prose | |
| `stage` | `technique` 1 to 3, fields `id | name`; `fact` 1 to 5, fields `label | value` | optional prose (the "why it matters" line) | `stage:` and `phase:` required |
| `background` | none | prose and bullets, at least one | `source:` required |
| `question` | none | prose only, at least one paragraph | |
| `answer` | none | prose and bullets, at least one | |
| `checklist` | `check` 2 to 7, field `text` | optional prose | |
| `links` | `link` 1 to 8, fields `name | url` | optional prose | |
| `flow` | `step` 3 to 8, fields `NN | tactic | short title | technique id` | optional prose | |
| `layers` | `layer` 2 to 5, fields `tier label | box | box ...` (1 to 3 boxes) | optional prose | |
| `timeline` | `event` 2 to 6, fields `when | what` | optional prose | |
| `compare` | `col` 2 or 3, fields `heading | line | line ...` (1 to 4 lines) | optional prose | |
| `table` | `row` 2 to 7, 2 to 4 fields, every row the same width; the first row is the header | optional prose | |
| `bars` | `bar` 2 to 4, fields `number | label`; number parses after removing `,` and a trailing `+` | optional prose | |
| `matrix` | `columns` exactly 1, 2 to 8 fields; `row` 2 to 8, fields `label | mark ...` where `-` alone means no marks | optional prose | every mark is one of the column labels |

Limits on every slide: heading at most 12 words; prose and bullets at most 40 words together; each typed field at most 14 words; notes at most 220 words.

---

### Task 1: Outline parser and style limits

**Files:**
- Create: `tools/build_breach_decks.py`

**Interfaces:**
- Consumes: `OutlineError`, `EM_DASH`, `EN_DASH`, `SPACED_HYPHEN_RE`, `DATE_RE` from `tools/build_howto_decks.py` (add `tools/` to `sys.path` as the how-to renderer import does).
- Produces:
  - `@dataclass BSlide(heading: str, layout: str, paragraphs: list[str], bullets: list[str], items: dict[str, list[list[str]]], notes: list[str], stage: str | None, phase: str | None, source: tuple[str, str] | None, credit: str | None, where: str)`
  - `@dataclass BDeck(slug: str, title: str, page: str, as_of: str, promise: str, slides: list[BSlide], text: str)`
  - `@dataclass(frozen=True) LayoutSpec(typed: dict[str, tuple[int, int, int, int | None]], prose: str, requires: tuple[str, ...])`: `typed` maps each typed key to (min lines, max lines, min fields, max fields or None); `prose` is one of `"none"`, `"optional"`, `"required"`, `"prose-only"`; `requires` names the control lines that must be present.
  - `LAYOUTS: dict[str, LayoutSpec]` holding the table above; `GENERATED_SLIDES = 3`, `MIN_SLIDES = 18`, `MAX_SLIDES = 36`
  - `parse_outline_text(text: str, name: str) -> BDeck`, `parse_outline(path: Path) -> BDeck`
  - `style_findings(deck: BDeck) -> list[str]`, each finding prefixed with the slide's `where` (`<file>:<line>`)
  - `outline_sha256(deck: BDeck) -> str` over `deck.text`
  - CLI `--self-test` running every `_case_*` in the module and printing `self-test: N cases passed`

- [ ] **Step 1: Write the failing self-test cases** in `tools/build_breach_decks.py`, following the `_case_*` pattern of `build_howto_decks.py` (a module with `main()`, `--self-test`, and cases that raise `AssertionError` with a message). Cases:
  - `parse_ok`: a sample outline with one `stage`, one `stats`, one `background` slide parses; `slides[0].items["fact"][0] == ["Queried", "the cloud Instance Metadata Service"]`, `slides[0].stage == "04"`, `slides[2].source[1].startswith("https://")`, notes are a non-empty list on each.
  - `missing_header` (each of the four keys), `unknown_header_key`, `bad_as_of` (`2026-11-31x`), `page_not_breaches` (`howto/x.html`).
  - `unknown_layout`, `control_line_twice` (`stage:` given twice).
  - `typed_line_empty_field`: `stat: 200+ | | x` raises `OutlineError` whose message starts with `<name>:<line>:`.
  - `typed_line_wrong_layout`: a `fact:` line on a `stats` slide raises with `file:line`.
  - `wrong_field_count` (a `stat` with two fields), `count_out_of_range` (one `stat`, five `fact`s).
  - `stage_requires_stage_and_phase`, `background_requires_source`, `question_rejects_bullets`.
  - `matrix_unknown_mark`: a `row` mark `09` not in `columns` is a finding.
  - `table_ragged`: rows of different widths is a finding.
  - `bars_non_number`: `bar: many | x` is a finding.
  - `missing_notes`: a slide with no `notes:` block raises.
  - `slide_count`: 14 outline slides (17 with generated) and 34 (37) are findings; 15 and 33 are not.
  - `too_many_words` (41 words of prose), `field_too_long` (15-word field), `notes_too_long` (221 words), `heading_too_long` (13 words).
  - `dashes`: an en dash in a fact value, an em dash in a field, and a spaced hyphen in the promise are each findings.
  - `notes_dash`: an em dash in notes is a finding.
  - `prose_after_bullet` is a finding.

- [ ] **Step 2: Run** `python3 tools/build_breach_decks.py --self-test`. Expected: fails (functions not defined).

- [ ] **Step 3: Implement** the dataclasses, `LAYOUTS`, the parser and `style_findings`. Parse errors (structure) raise `OutlineError("<file>:<line>: ...")`; limit breaches (counts, words, dashes, marks, ragged tables, numbers in bars) are findings, so `--check` can report all of them at once. `where` is `<file>:<line of the == line>`.

- [ ] **Step 4: Run** `python3 tools/build_breach_decks.py --self-test`. Expected: `self-test: N cases passed`, exit 0.

- [ ] **Step 5: Commit**

```bash
git add tools/build_breach_decks.py
git commit -m "decks: breach outline parser and style limits"
```

### Task 2: Page model and page gate

**Files:**
- Modify: `tools/build_breach_decks.py`

**Interfaces:**
- Consumes: `BDeck`, `BSlide` (Task 1).
- Produces:
  - `@dataclass PageStage(num: str, title: str, techniques: set[str])`: `num` as the page shows it (`"04"`); `techniques` holds the stage's `mt` link ID and every `stag` that matches `T\d{4}(\.\d{3})?`.
  - `@dataclass BreachPage(path: str, stages: dict[str, PageStage], numbers: set[str], techniques: set[str], links: set[str], text: str)`
  - `parse_breach_page(html: str, path: str) -> BreachPage`, reading only `<main>`; `links` are absolute URLs, relative hrefs resolved against `https://csoh.org/<path>`, with a trailing `/` stripped and the fragment kept.
  - `number_tokens(text: str) -> set[str]`: matches `(?<![A-Za-z0-9.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![A-Za-z0-9.])\d+(?:\.\d+)?` not followed by a letter, returning each with commas and leading zeros removed (`"04"` becomes `"4"`).
  - `technique_ids(text: str) -> set[str]`: `T\d{4}(?:\.\d{3})?`.
  - `main_text(html: str) -> str`: `<main>` with every deck line removed, tags stripped, entities unescaped, whitespace collapsed.
  - `page_sha256(html: str) -> str` over `main_text(html)`.
  - `BACKGROUND_HOSTS = ("csoh.org", "attack.mitre.org", "owasp.org", "cheatsheetseries.owasp.org", "learn.microsoft.com", "docs.aws.amazon.com", "cloud.google.com", "kubernetes.io", "www.rfc-editor.org", "datatracker.ietf.org", "docs.oasis-open.org")`; a URL is allowed when its host equals one of these or ends with `.` plus one.
  - `page_findings(deck: BDeck, page: BreachPage) -> list[str]`

- [ ] **Step 1: Write the failing cases**, each on a small synthetic page built by a `_breach_page(stages=..., body=..., links=...)` helper in the page's real markup (`kc-step`, `step-num`, `step-title`, `mt` link, `stag` spans, `pm-link`), plus one case on the real pilot page:
  - `page_parse_real`: `parse_breach_page` on `breaches/vapor-panda-artex.html` returns stages `01` to `07`; stage `04` techniques equal `{"T1552.005", "T1651"}`; `"1465"` and `"1.4"` are in `numbers`; `https://csoh.org/breaches/storm-0940-connectwise.html` is in `links`.
  - `numbers_normalized`: `number_tokens("1,500+ an hour, 1.4 billion, 70%, IMDSv2, T1606, artx5v, 04")` equals `{"1500", "1.4", "70", "4"}`.
  - `page_hash_stable`: wrapping a word in `<a class="glossary-link">`, inserting a deck line, and changing the nav outside `<main>` leave `page_sha256` unchanged; changing one word in a `step-desc` changes it.
  - `stage_unknown`: `stage: 09` is a finding. `stage_technique_not_on_stage`: `technique: T1606` on stage `04` is a finding even though T1606 is on the page.
  - `flow_step_checked`: a `flow` `step` whose number or technique does not match that page stage is a finding. `matrix_columns_checked`: a column label of two digits that names no stage is a finding.
  - `number_not_on_page`: `140` on a slide passes when the page has it; `141` is a finding naming the slide.
  - `technique_not_on_page`: `T1059` in a bullet is a finding.
  - `notes_checked`: `141` or `T1059` in a non-background slide's notes is a finding; the same in a background slide's notes is not.
  - `links_resolve`: `link: Related | breaches/storm-0940-connectwise.html` matches the page's `href="storm-0940-connectwise.html"`; `https://example.com/report/` matches `href="https://example.com/report"`; `https://example.com/other` is a finding.
  - `background_exempt`: a background slide with numbers and a T-ID not on the page passes; its `source:` on `medium.com` is a finding; on `docs.aws.amazon.com` it is not.
  - `as_of_not_future`: an `as-of` later than today is a finding.

- [ ] **Step 2: Run** `--self-test`. Expected: the new cases fail.

- [ ] **Step 3: Implement** the page model and `page_findings`. On a non-background slide, the gate reads the heading, prose, bullets, every typed field, `credit`, and the notes. Each finding names the slide's `where` and the offending token.

- [ ] **Step 4: Run** `--self-test`. Expected: all cases pass.

- [ ] **Step 5: Commit**

```bash
git add tools/build_breach_decks.py
git commit -m "decks: breach page model and page gate"
```

### Task 3: Mapping, stale report, stamping and CI

**Files:**
- Modify: `tools/build_breach_decks.py`, `.github/workflows/validate-html.yml`, `.gitignore`, `LICENSE`, `CLAUDE.md`, `tools/DECKS_README.md`

**Interfaces:**
- Consumes: Tasks 1 and 2; `PRES_ID_RE`, `SLUG_RE`, `SHA256_RE`, `_is_iso_date` from `build_howto_decks`.
- Produces:
  - Paths: `DECKS_DIR = ROOT/tools/decks/breaches`, `MAPPING = DECKS_DIR/published.json`, `PAGES_DIR = ROOT/breaches`, `BUILD_DIR = DECKS_DIR/build`; a `_set_root(root)` like the how-to tool's, for self-test trees.
  - `ENTRY_KEYS = ("id", "outline_sha256", "page_sha256", "published")`
  - `DECK_ATTR = "data-breach-deck"`; `deck_line_html(pres_id: str) -> str`: the how-to deck line's wording and attributes with `data-breach-deck`, class `u-mt-075`, at the indentation of the page's `pm-link` lines.
  - `stamp_page(html: str, pres_id: str | None) -> str`: removes every deck line, then inserts one after the last `<a class="pm-link"` line inside `inc-header`. Raises `ValueError` on loose deck markup or when there is no `pm-link` line.
  - `link_findings(slug, html, mapping) -> list[str]`, `mapping_findings(mapping, outlines, pages) -> list[str]`
  - CLI modes: `--check`, `--stale [--published-only]`, `--status`, `--stamp`, `--record SLUG PRES_ID`, with the how-to tool's semantics, plus: `--stale` also reports `page changed since it was published on <date>; review the deck against the page` when `page_sha256` differs, and `--record` writes both hashes.

- [ ] **Step 1: Write the failing cases:** `stamp_insert` (line lands after the last `pm-link`), `stamp_idempotent`, `stamp_new_id`, `stamp_remove`, `stamp_no_pm_link` (refused), `stamp_refuses_loose_markup`, `links_unmapped_line`, `links_missing_line`, `links_wrong_id`, `links_slides_link_elsewhere` (a `docs.google.com/presentation` link outside the deck line is a finding), `mapping_findings` (missing key, extra key, bad id, bad date, slug with no outline, slug with no page), `stale_outline_changed`, `stale_page_changed` (both in a temp tree via `_set_root`), `stale_exit_zero`, `check_empty_tree` (no outlines: exit 1, "nothing was checked"), and `record_writes_both_hashes`.

- [ ] **Step 2: Run** `--self-test`. Expected: the new cases fail.

- [ ] **Step 3: Implement** the mapping, stale, status, stamp and record modes, then `check_all()`: parse and style-check every outline, run `page_findings` against `breaches/<slug>.html`, validate the mapping, and run `link_findings` over every `breaches/*.html`. Summary line: `breach decks: N outlines checked, M breach pages checked, K findings`.

- [ ] **Step 4: Run** `--self-test` and `--check`. Expected: self-test passes; `--check` exits 1 with "no outlines found" until Task 6 (that is the empty-tree guard working).

- [ ] **Step 5: Registrations.**
  - `validate-html.yml`: add `tools/build_breach_decks.py` to the path filter beside `tools/build_howto_decks.py` (`tools/decks/**` already covers the outlines). Add steps `Assert breach deck outlines and links` (id `breach-decks`) and `Report published breach decks that need review`, copying the how-to steps' structure and comments with "breach" wording. Add the gate to the summary table beside `OUTCOME_HOWTO_DECKS`.
  - `.gitignore`: `/tools/decks/breaches/build/`.
  - `LICENSE` clause 3: "Slide decks made from the how-to guides and the breach kill chains, and the outlines in tools/decks/ they are built from, ...".
  - `CLAUDE.md`: a row in "Generated content": `Breach deck links (data-breach-deck) on breaches/ pages | tools/build_breach_decks.py --stamp | --check in validate-html.yml; --stale --published-only there warns`.
  - `tools/DECKS_README.md`: a "Breach kill chain decks" section with the outline format, the layout table, the gate, the stale rule (outline or page changed) and the publishing steps.

- [ ] **Step 6: Run** `python3 tools/check_readme_coverage.py --check` and `python3 tools/build_howto_decks.py --self-test && python3 tools/build_howto_decks.py --check`. Expected: both exit 0 (the how-to gate does not see breach outlines).

- [ ] **Step 7: Commit**

```bash
git add tools/build_breach_decks.py .github/workflows/validate-html.yml .gitignore LICENSE CLAUDE.md tools/DECKS_README.md
git commit -m "decks: breach deck mapping, stamping, stale report and CI gate"
```

### Task 4: Renderer foundation and text layouts

**Files:**
- Create: `tools/breach_deck_render.py`
- Modify: `tools/build_breach_decks.py` (add `--build` and `--self-test-render`, importing the renderer only on those paths)

**Interfaces:**
- Consumes: `BDeck`, `BSlide`, `LAYOUTS`.
- Produces:
  - `PHASE_COLORS: dict[str, str]` keyed by ATT&CK v19 tactic name (Reconnaissance, Resource Development, Initial Access, Execution, Persistence, Privilege Escalation, Stealth, Defense Impairment, Credential Access, Discovery, Lateral Movement, Collection, Command and Control, Exfiltration, Impact), each a darkened tone of the site's `breach-timeline.css` phase hue; `phase_color(phase: str) -> str` matches the tactic name at the start of the `phase:` text (the part before `:`), falling back to slate `#475569`.
  - `contrast(fg: str, bg: str) -> float` (WCAG relative luminance).
  - `class LayoutError(Exception)`.
  - `render_deck(deck: BDeck, out: Path) -> Path`; `verify_pptx(path: Path, deck: BDeck) -> list[str]`.
  - One `_render_<layout>(page, slide)` per layout; this task covers `text`, `stats`, `stage`, `background`, `question`, `answer`, `checklist`, `links`, and the generated `cover`, `how-to-use` and `closing`.
- Generated slide copy (exact):
  - How to use this deck, heading "How to use this deck"; paragraphs: "Read it on your own or present it. Every fact about the incident comes from the csoh.org kill chain and the sources it cites." / "Slides marked Background explain a general idea and name their own source. The speaker notes are a presenter's script." / "Full kill chain: csoh.org/<page>. These slides reflect it as of <as-of>."
  - Closing heading "Read the full kill chain"; paragraphs: "Every step, source and defense in detail: https://csoh.org/<page>" and the how-to `CLOSING_LICENSE` text.
  - Cover: title, promise, "Reflects the csoh.org kill chain as of <as-of>", `ATTRIBUTION`, `LICENSE_LINE`.

- [ ] **Step 1: Write the failing render cases** (run by `--self-test-render`): `render_sample` builds a deck using every layout this task covers and asserts `verify_pptx` returns `[]`; `phase_contrast` asserts `contrast("ffffff", c) >= 4.5` for every `PHASE_COLORS` value and the fallback; `overflow_refused` asserts a `stage` slide with five long facts and a 40-word paragraph raises `LayoutError` naming the slide's `where`; `verify_catches_dash` plants an en dash in a saved file's text box and asserts a finding; `verify_catches_small_font` plants a 12 pt body run and asserts a finding.

- [ ] **Step 2: Run** `/Users/shawn/.pyenv/versions/3.10.0/bin/python3 tools/build_breach_decks.py --self-test-render`. Expected: fails (module missing).

- [ ] **Step 3: Implement** the renderer. Shapes allowed: rectangle, rounded rectangle, oval, chevron, right arrow, down arrow, and text boxes; no connectors, SmartArt, images, embedded fonts or autofit. Every content slide carries a slide-type label for `background` ("BACKGROUND", plus the source name and host as a credit line at the bottom), `question` ("DISCUSSION"), `answer` ("DISCUSSION: ANSWER"). Stage slides draw a phase band (`<PHASE> · STAGE NN`, white on `phase_color`), the heading as the headline, technique chips (`ID  Name`), facts as label and value rows, and the prose as a "Why it matters" line. Stat tiles show the value large in the accent-on-dark style. Height estimates follow the how-to renderer's approach (`_lines`, per-line heights) and raise `LayoutError` before saving. `verify_pptx` extends the how-to checks: shape bottoms within the limit, body runs at least 18 pt except named small shapes at least 14 pt, footer text, notes on every slide, no en or em dash in any text frame or note, and the slide count.

- [ ] **Step 4: Run** `--self-test-render`, then `--self-test` with python-pptx blocked. Expected: both pass. The blocked run:

```bash
python3 -c "import sys, runpy; sys.modules['pptx'] = None; sys.argv = ['build_breach_decks.py', '--self-test']; runpy.run_path('tools/build_breach_decks.py', run_name='__main__')"
```

- [ ] **Step 5: Commit**

```bash
git add tools/breach_deck_render.py tools/build_breach_decks.py
git commit -m "decks: breach deck renderer with text, stat, stage and teaching layouts"
```

### Task 5: Diagram layouts

**Files:**
- Modify: `tools/breach_deck_render.py`

**Interfaces:**
- Consumes: Task 4's page helpers, `phase_color`, `LayoutError`.
- Produces: `_render_flow`, `_render_layers`, `_render_timeline`, `_render_compare`, `_render_table`, `_render_bars`, `_render_matrix`.

Drawing rules the outline author relies on:

- `flow`: one numbered box per step, coloured by `phase_color(tactic)`, holding the number, short title and technique ID; right arrows between boxes; up to 4 per row, two rows for 5 to 8 steps, reading left to right on each row.
- `layers`: one row per `layer`, top to bottom; the tier label at left; 1 to 3 boxes per row; a down arrow between consecutive rows only. No other connections are drawn.
- `timeline`: a horizontal rule with one marker per event, evenly spaced (never scaled to dates, so no time scale is implied); `when` above, `what` below.
- `compare`: 2 or 3 equal columns, heading band then lines.
- `table`: header row on dark fill; body rows alternating light fills.
- `bars`: horizontal bars on one shared scale from zero, length proportional to the parsed number, the written value (as in the outline) at the bar's end. A bar under 2% of the largest is drawn at a minimum visible width and its value is still printed.
- `matrix`: column headers across, row labels down, a filled marker where marked, an empty cell otherwise; a row whose marks are `-` gets its label in italics with "(no stage named)".

- [ ] **Step 1: Write the failing render cases:** `render_diagrams` (a deck using every diagram layout at its maximum counts verifies clean); `bars_to_scale` (for bars 40 and 1,500, the saved bar widths are in ratio 1500:40 within 1%, apart from the minimum width rule, which this pair triggers, so assert the larger is the full track and the smaller is at the minimum); `flow_two_rows` (7 steps give two rows of 4 and 3); `timeline_even` (marker x positions are evenly spaced).

- [ ] **Step 2: Run** `--self-test-render`. Expected: the new cases fail.

- [ ] **Step 3: Implement** the seven layouts within the rules above and the Global Constraints.

- [ ] **Step 4: Run** `--self-test-render`. Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add tools/breach_deck_render.py
git commit -m "decks: breach deck diagram layouts"
```

### Task 6: The VAPOR PANDA / ARTEX outline

**Files:**
- Create: `tools/decks/breaches/vapor-panda-artex.deck`

- [ ] **Step 1: Read** `breaches/vapor-panda-artex.html` in full, the spec's "The pilot's content" table, and the cited background sources for the four background slides.

- [ ] **Step 2: Write the outline** to the spec's slide table, about 32 outline slides plus the 3 generated:
  - At a glance (`stats`): 200+, 9, 1,500+ against 40, with the page's qualifiers.
  - Timeline (`timeline`): only dates the page gives: October 17 start; 11 days; October 30, reported active (CyberScoop); early November, Censys's console count.
  - Nine against about 140 (`compare`): what each figure measures, with "moderate-confidence" kept.
  - ARTEX's structure (`layers`): operator; main agent; planner agents and worker agents; shared graph of facts, findings and goals.
  - How much humans steer (`compare`): CrowdStrike's operator against Check Point's 10 cybercrime instances.
  - Exposed consoles by method (`table`): Censys 1,465 hosts and about 815 distinct-looking deployments; Check Point 1,608 live, 2,557 ever, and the 1,800+ in its summary; Censys's caution about authorized testers.
  - The kill chain on one slide (`flow`): stages 01 to 07 with the page's phases and primary techniques.
  - Stages 01 to 07 (`stage`), each followed where listed by a `background` slide: 02 (XXE and unsigned SAML assertions), 04 (IMDSv1 against IMDSv2), 05 (LAPS and resource-based constrained delegation), 07 (DLL side-loading).
  - Machine tempo (`bars`): 40 against 1,500+ commands an hour, then a `text` slide: nothing new in technique, the rate changed, requests every 10 seconds, parallel paths.
  - Defenses (`matrix`): seven defenses against stages 01 to 07, marking only the ties the page states (keys to 03, IMDSv2 to 04, SAML to 02, sensor gaps to 06, orchestration to 05); markers and decoys as `-` rows. Then two or three `checklist` or `text` slides on the defenses.
  - Hunting (`text`): artx and artex command lines, artx-prefixed cloud roles, `C:\ProgramData\artx5v\`, default user agents, tempo, and the page's caveat that indicators change and blocking them will not stop an agent.
  - Check your own environment (`checklist`), from the page's defenses.
  - Discussion: three `question` slides each followed by an `answer` slide; one asks what the reader would add for stages 01 and 07, which the page's defenses leave open, and its answer says the page offers none and frames any suggestion as the reader's own.
  - Sources (`links`): the page's eight primary sources. Related (`links`): Storm-0940 / ConnectWise and the ARTEX exposed-secrets kill chain.
  - Notes on every slide: a presenter's script for that slide (what to say, in the page's hedged terms), at most 220 words.

- [ ] **Step 3: Run** `python3 tools/build_breach_decks.py --check`. Expected: `0 findings`. Fix the outline until it is.

- [ ] **Step 4: Run** `/Users/shawn/.pyenv/versions/3.10.0/bin/python3 tools/build_breach_decks.py --build vapor-panda-artex`. Expected: `tools/decks/breaches/build/vapor-panda-artex.pptx` written and 0 verify findings. A `LayoutError` means trimming that slide.

- [ ] **Step 5: Control.** Change `1,465` to `1,466` in the outline: `--check` reports it; restore and confirm 0 findings.

- [ ] **Step 6: Commit**

```bash
git add tools/decks/breaches/vapor-panda-artex.deck
git commit -m "decks: VAPOR PANDA / ARTEX pilot outline"
```

### Task 7: Local preview and fact review

**Files:**
- Modify: `tools/decks/breaches/vapor-panda-artex.deck` (fixes only)

- [ ] **Step 1: Local preview.** Open the .pptx with the PowerPoint connector and export a PDF to the scratchpad; read every page. Fonts substitute locally (Space Grotesk and Source Sans 3 are not installed), so judge layout, diagram geometry, arrow placement and density, not typography. Fix the outline or renderer and rebuild.

- [ ] **Step 2: Fact review.** A fresh reviewer on the most capable model, given the page, the outline and the spec's anti-goals (not this session's reasoning), checks every slide and every note: each non-background statement against the page, hedges and attributions intact, no victim named beyond the page, numbers and dates as the page gives them, diagrams showing only connections the page describes, the matrix marking only stated ties, ATT&CK v19 names, writing rules. Each background slide is checked against its named source. The reviewer reports findings; it does not edit.

- [ ] **Step 3: Fix** every confirmed finding, re-run `--check` and `--build` (0 findings each), and repeat Step 2 on the changed slides until clean.

- [ ] **Step 4: Commit**

```bash
git add tools/decks/breaches/vapor-panda-artex.deck tools/breach_deck_render.py
git commit -m "decks: VAPOR PANDA / ARTEX fact review fixes"
```

### Task 8: Private upload and Google render check (needs Shawn's go)

- [ ] **Step 1: Ask Shawn** to approve a private upload to a "CSOH breach decks" folder in his Drive. Wait for an explicit yes.
- [ ] **Step 2: Upload** the .pptx with the Drive connector (converted to Google Slides), private. Confirm the file's owner is the expected account from its metadata.
- [ ] **Step 3: Inspect Google's render.** Export the PDF (`exportMimeType: application/pdf`) and pull large slide thumbnails; check every slide for fonts, overflow, diagram shapes and arrows after conversion, chip and band contrast, footers and notes. A defect goes back to the outline or renderer; the re-upload is a new file, and the superseded one goes on a list for Shawn.
- [ ] **Step 4: Hand the private deck to Shawn** for review with its link, and wait for his approval or changes.

### Task 9: Publish (needs Shawn's go)

**Files:**
- Create: `tools/decks/breaches/published.json`
- Modify: `breaches/vapor-panda-artex.html`

- [ ] **Step 1: On Shawn's go**, share the deck `anyoneWithLink` as reader. Signed out, `/export/pdf` returns `200 application/pdf` starting `%PDF-` with one page per slide, and `/copy` redirects to `accounts.google.com`.
- [ ] **Step 2: Run** `python3 tools/build_breach_decks.py --record vapor-panda-artex <PRES_ID>`. Expected: the mapping entry has all four keys and the page holds one deck line after its `pm-link` lines.
- [ ] **Step 3: Check the page** in the preview server with production's CSP applied, light and dark, scripts on and off: the deck line renders under the source links, links underlined, no layout shift.
- [ ] **Step 4: Gates,** each exit 0: `build_breach_decks.py --self-test`, `--check`, `--stale --published-only` (prints no deck), `build_howto_decks.py --check`, `check_readme_coverage.py --check`, `check_no_inline_scripts.py`. `lychee --config .lychee.toml breaches/vapor-panda-artex.html` reports both deck links OK.
- [ ] **Step 5: Commit**

```bash
git add tools/decks/breaches/published.json breaches/vapor-panda-artex.html
git commit -m "decks: publish the VAPOR PANDA / ARTEX deck"
```

- [ ] **Step 6: Report** "committed, ready to push" and wait for Shawn's push instruction.
