# Breach Industry Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Readers can find breach kill chains by the industries they hit, by typing an industry (or a synonym) into the existing search box, or by pressing an industry button, on `breach-timeline.html` and `breach-kill-chain-decks.html`.

**Architecture:** Each hand-written timeline card carries a canonical "Industries hit" line. One vocabulary module (`tools/breach_industries.py`) owns the labels, their synonyms, the line's markup and its parser. The two existing sync tools read the lines, validate them, and render industry buttons plus a synonym map into the generated card finder; the deck tool also copies each line onto its deck card. `card-finder.js` stays page-agnostic: buttons fill the box, and a typed synonym matches its industry.

**Tech Stack:** Python 3 standard library (tools, `--self-test` planted controls), vanilla JS (`card-finder.js`), `style.css`, Playwright for browser verification.

**Spec:** `docs/superpowers/specs/2026-11-23-breach-industry-search-design.md`

## Global Constraints

- No em dashes, en dashes, or spaced hyphens used as dashes, in code comments, copy, or commit messages.
- No inline `<style>`, `<script>`, `style="..."` or `element.style`: production CSP is `style-src 'self'; script-src 'self'`.
- No CI-skip token in any commit message.
- Stage explicit paths only; never `git add -A`, `git add .` or `commit -a`. Never push.
- Don't commit `?v=`/`integrity=` stamps from `update_sri.py`, or `search-index.json`. Deploy regenerates both.
- Comments state the current rule and its reason, with no incident history.
- Every tag traces to a sentence on that chain's breach page; a page that names no victim industry gets no line.
- A button is rendered only for an industry at least one card on that page carries.
- Placeholders: `Search by company, actor, technique or industry` (timeline), `Search by company, actor, platform or industry` (decks).
- Run every generator twice; the second run must change nothing.

## Review Focus

1. A reader presses Finance, then Healthcare: the box reads "Healthcare" (it replaces, it does not add) and only Healthcare is pressed. Pinned in Task 6's browser check.
2. The browser restores the box on back/forward: the matching button comes back pressed. Pinned in Task 6 (reload with a value typed).
3. Escape, or "Clear the search", while a button is pressed: no button stays pressed. Pinned in Task 6.
4. A cross-linker run over the pages must not edit the buttons or the industries lines, or `--check` goes red after the next glossary refresh. Pinned in Tasks 3 and 4 (the probe region includes buttons and lines).
5. A card edited by hand with industries out of order, a typo, or a stray separator: `--check` names the card and prints the canonical line to paste. Pinned in Task 1 and Task 3.

---

### Task 1: The industry vocabulary module

**Files:**
- Create: `tools/breach_industries.py`

**Interfaces:**
- Produces:
  - `INDUSTRIES: dict[str, tuple[str, ...]]`: label to single-word synonyms (values below).
  - `fold(s: str) -> str`: the same folding as `card-finder.js` (NFKD, drop combining marks, lower-case, every run of non-`[a-z0-9]` to one space, strip).
  - `synonym_map() -> dict[str, str]`: folded synonym to folded label, for every industry.
  - `render_line(labels: Iterable[str]) -> str`: the canonical one-line markup, labels sorted.
  - `read_line(card_html: str) -> tuple[list[str], list[str]]`: the labels on a card's industries line (empty when it has none) and findings (strings, no card name; callers prefix it).
  - `vocabulary_findings() -> list[str]`: problems with `INDUSTRIES` itself.
  - CLI: `python3 tools/breach_industries.py --self-test`.

The canonical line, exactly:

```html
<p class="industries-hit"><span class="industries-hit-label" data-finder-skip>Industries hit:</span> <span class="no-glossary">Finance, Healthcare</span></p>
```

Starting vocabulary (labels and synonyms are my calls; a label may be added only when an evidence quote needs it, with synonyms):

| Label | Synonyms |
|---|---|
| Crypto | cryptocurrency bitcoin blockchain defi web3 ethereum stablecoin |
| Education | university universities school schools college academic |
| Energy | utility utilities oil electricity |
| Finance | bank banks banking financial fintech insurance insurer payments brokerage lender |
| Government | federal agency agencies military defense gov govt |
| Healthcare | health hospital hospitals medical pharmacy pharma clinic patients |
| Hospitality | hotel hotels casino casinos resort resorts travel restaurant |
| Legal | law lawyer lawyers attorney attorneys |
| Manufacturing | manufacturer industrial factory automotive semiconductor |
| Media | entertainment streaming news publishing publisher |
| Retail | ecommerce commerce store stores shopping retailer retailers |
| Technology | tech software saas developer developers hosting |
| Telecom | telecommunications telco carrier carriers wireless isp |
| Transportation | airline airlines logistics aviation transit rideshare |

Ambiguous words stay out: "exchange" (Microsoft Exchange), "cloud" (every card), "gaming", "mobile", "pipeline", "shipping", "power", "public", "state".

- [ ] **Step 1: Write the self-test first.** `self_test() -> int` with `expect(cond, what)` in the style of `tools/sync_breach_timeline_index.py`. Assertions:
  - `vocabulary_findings() == []`.
  - `render_line(["Healthcare", "Finance"]) == '<p class="industries-hit"><span class="industries-hit-label" data-finder-skip>Industries hit:</span> <span class="no-glossary">Finance, Healthcare</span></p>'`.
  - `read_line("<li>" + render_line(["Retail", "Finance"]) + "</li>") == (["Finance", "Retail"], [])`.
  - `read_line("<li>no line</li>") == ([], [])`.
  - A line naming `Fintech` gives a finding containing `"Fintech" is not an industry`.
  - A line naming `Finance, Finance` gives a finding containing `more than once`.
  - A line with `Retail, Finance` (out of order) gives a finding containing `should read` and the canonical `render_line(["Finance", "Retail"])` text.
  - A line using ` · ` as the separator gives the same `should read` finding.
  - Two lines in one card give a finding containing `more than one`.
  - A line with an extra attribute (`<p data-x="1" class="industries-hit">`) is still read, and reported as non-canonical.
  - `synonym_map()["bank"] == "finance"` and `synonym_map()["hospital"] == "healthcare"`.
  - Planted vocabulary controls, by passing a dict into a helper `vocabulary_findings(vocab)`: a two-word label, a synonym equal to another label, a synonym shared by two industries, and a synonym that `fold` changes (`"E-commerce"`) each produce a finding.
  - `fold("Shai-Hulud Café") == "shai hulud cafe"`.
- [ ] **Step 2: Run it and see it fail.** `python3 tools/breach_industries.py --self-test`. Expected: import or name errors, exit 1.
- [ ] **Step 3: Implement the module.** `vocabulary_findings(vocab=INDUSTRIES)` takes the dict as a parameter so the planted controls can pass their own. `read_line` matches `<p\b[^>]*\bclass="industries-hit"[^>]*>(.*?)</p>` (attributes allowed, per CLAUDE.md), reads the labels from the text after the `Industries hit:` label span with tags stripped and entities unescaped, splits on commas or middle dots, and reports non-canonical markup by comparing the match against `render_line` of the sorted labels.
- [ ] **Step 4: Run it and see it pass.** Same command. Expected: every line `ok`, `self-test: 0 failure(s)`, exit 0. Then `ruff check tools/breach_industries.py`.
- [ ] **Step 5: Commit.** `git add tools/breach_industries.py`; message `Breach industries: add the vocabulary and the card line it validates`.

### Task 2: Buttons and synonyms in the shared card finder

**Files:**
- Modify: `tools/card_finder.py` (`render_finder`, module docstring)
- Modify: `card-finder.js`
- Modify: `style.css` (card finder block near `.card-finder`; dark `.filter-btn` rules in the `[data-theme="dark"]` branch)

**Interfaces:**
- Consumes: nothing from Task 1 (callers pass plain values).
- Produces: `render_finder(..., filters: Sequence[str] = (), filter_label: str = "", synonyms: Mapping[str, str] | None = None) -> list[str]`.
  - With `filters`, inside `.card-finder-filter` after `.search-wrapper` and before the status line: `<div class="card-finder-buttons" role="group" aria-labelledby="{id_prefix}-filter-label">`, a `<span class="card-finder-buttons-label" id="{id_prefix}-filter-label"><span class="no-glossary">{filter_label}</span></span>`, then per filter `<button type="button" class="filter-btn card-finder-btn" data-finder-query="{label}" aria-pressed="false"><span class="no-glossary">{label}</span></button>`, in the order given.
  - With `synonyms`, the `.card-finder` div gains `data-finder-synonyms="bank=finance banking=finance ..."`: space-separated `word=label` pairs, sorted by word.
  - With neither, the output is byte-identical to today's.

- [ ] **Step 1: Pin today's output.** Before editing, capture `render_region` output from both sync tools on the real pages (`python3 -c` importing each tool) into the scratchpad; after Step 3, assert the default call (no filters, no synonyms) still produces it exactly.
- [ ] **Step 2: Implement `render_finder`'s new parameters.** Escape the label text with `_text` and attribute values with `_attr`.
- [ ] **Step 3: Implement the script.** In `card-finder.js`:
  - Leave out `[data-finder-skip]` elements nested inside a searched node, not only searched nodes that sit inside one. Today a node's whole `textContent` is taken, so the "Industries hit:" label inside `p.industries-hit` would be searched and "industries" would match every card. Take each node's text from a clone with its `[data-finder-skip]` descendants removed. The deck page's skipped `.tag` spans keep working, because they are selected nodes inside a skip (themselves).
  - Read `finder.dataset.finderSynonyms` into a map once.
  - A term matches an entry when `e.text.includes(t)`, or when `syn[t]` exists and `e.text.includes(' ' + syn[t] + ' ')`.
  - Buttons are `finder.querySelectorAll('[data-finder-query]')`. Click: if the button is pressed, call `clear()`; otherwise set `input.value` to its query and call `refresh()`. Focus stays on the button.
  - In `refresh()`, set each button's `aria-pressed` to `fold(input.value) === fold(button.dataset.finderQuery)` (as the strings `"true"`/`"false"`).
  - Update the header comment to describe buttons and synonyms.
- [ ] **Step 4: Style it.**
  - In `style.css`: `.card-finder .card-finder-buttons` (flex, wrap, gap 0.4rem, margin 0.75rem 0 0, align-items center) and `.card-finder-buttons-label` (`var(--fs-14)`, weight 600, `var(--text-muted)`, margin-right 0.25rem).
  - Add `.filter-btn[aria-pressed="true"]` beside every `.filter-btn.active` selector in the light rules and the `[data-theme="dark"]` branch.
  - `.industries-hit` (margin 0.5rem 0 0, `var(--fs-14)`, `var(--text-muted)`) and `.industries-hit-label` (weight 600).
  - Run `python3 tools/sync_dark_branch.py && python3 tools/sync_dark_branch.py --check`.
- [ ] **Step 5: Verify.** Both sync tools' `--self-test` still pass (they don't pass the new parameters yet), the default-call output equals the Step 1 capture, and `ruff check tools/card_finder.py`.
- [ ] **Step 6: Commit.** `git add tools/card_finder.py card-finder.js style.css`; message `Card finder: optional filter buttons and synonyms`.

### Task 3: Timeline tool reads, validates and offers industries

**Files:**
- Modify: `tools/sync_breach_timeline_index.py`

**Interfaces:**
- Consumes: `read_line`, `synonym_map`, `render_line` (Task 1); `render_finder(filters=, filter_label=, synonyms=)` (Task 2).
- Produces: `collect(page_html) -> tuple[list[Entry], list[str], list[str]]`, now also returning the sorted union of industries across cards. `render_region(entries, industries)`. Placeholder `Search by company, actor, technique or industry`, `filter_label="Industries"`, `text_selector=".breach-card-meta, .breach-card-title, .breach-card-summary, .industries-hit"`.

- [ ] **Step 1: Write the failing self-test assertions.** Extend `_card` with an optional `industries` argument that inserts `render_line(...)` after the summary. Assertions:
  - The rewritten region contains one button per industry in the union, alphabetical (a fixture with Finance on one card and Crypto, Finance on another gives Crypto then Finance).
  - It contains no button for a vocabulary industry no card carries (assert `data-finder-query="Legal"` is absent).
  - It contains `data-finder-synonyms=` with `bank=finance`.
  - The placeholder is the new one, and `.industries-hit` is in `data-finder-text`.
  - A card with an unknown industry, and a card with an out-of-order line, each make `sync(root, check=False) == 1`, and the printed finding names the card id.
  - Changing one card's industries makes `--check` fail until the tool runs (the buttons are stale).
  - A card with no line is not a finding.
  - The cross-linker probe: `render_region` with entries whose names are every glossary key, and `industries` set to every vocabulary label, links nothing, and the existing plain-paragraph control still links.
- [ ] **Step 2: Run and see the new assertions fail.** `python3 tools/sync_breach_timeline_index.py --self-test`. Expected: `FAIL` lines for the new assertions, exit 1.
- [ ] **Step 3: Implement.** Findings from `read_line` are prefixed with the card's `where` string. After the run, print a `note:` line naming the cards that have no industries line; this is not a finding. Update the module docstring to describe the industries line, the buttons and the new findings.
- [ ] **Step 4: Run and see it pass.** Self-test exit 0, then `ruff check tools/sync_breach_timeline_index.py`. Don't run the tool on the real page yet: until Task 5, no card carries a line and the page would get no buttons. Between this commit and Task 5's, `--check` on the real page is red (new placeholder, page not regenerated). The commits stay local, and Task 5 brings it back to green.
- [ ] **Step 5: Commit.** `git add tools/sync_breach_timeline_index.py`; message `Kill chain index: read industries from the cards and offer them as buttons`.

### Task 4: Deck tool copies industries onto deck cards

**Files:**
- Modify: `tools/sync_breach_deck_index.py`
- Modify: `breach-kill-chain-decks.html` (FAQ answer near line 1660: "company, actor or platform" becomes "company, actor, platform or industry"; then `python3 tools/check_faq_jsonld_parity.py --fix` updates the JSON-LD copy)

**Interfaces:**
- Consumes: `read_line`, `render_line`, `synonym_map` (Task 1); `render_finder` (Task 2).
- Produces: `timeline_order(...) -> dict[str, tuple[int, str, str, tuple[str, ...]]]` (adds industries); `Deck.industries: tuple[str, ...]`; `render_card` emits `render_line(d.industries)` after the promise paragraph when non-empty; `render_index` passes `filters` = sorted union over listed decks, `filter_label="Industries"`, `synonyms=synonym_map()`, the new placeholder.

- [ ] **Step 1: Write the failing self-test assertions.** Extend `_fixture` so a timeline entry can carry industries, rendered into its card with `render_line`. Assertions:
  - The deck card for a chain tagged Finance, Retail contains `render_line(["Finance", "Retail"])`, after its `<p><span class="no-glossary">` promise and before `<div class="resource-tags">`.
  - A deck whose chain has no line gets no `industries-hit` paragraph.
  - The buttons are the union over listed decks only: an industry carried only by a timeline chain with no deck gets no button.
  - The placeholder is the new one, and `data-finder-synonyms=` is present.
  - The existing `timeline_order` attribute-order test is updated to the four-tuple.
  - The cross-linker probe `Deck` carries every vocabulary label as `industries`, and still links nothing.
- [ ] **Step 2: Run and see them fail.** `python3 tools/sync_breach_deck_index.py --self-test`. Expected: new `FAIL` lines, exit 1.
- [ ] **Step 3: Implement.** Invalid lines are the timeline tool's to report: the deck tool copies whatever `read_line` parses and ignores its findings. Update the module docstring.
- [ ] **Step 4: Run and see it pass.** Self-test exit 0; `ruff check tools/sync_breach_deck_index.py`.
- [ ] **Step 5: Update the FAQ.** Edit the visible answer, run `python3 tools/check_faq_jsonld_parity.py --fix`, then `--check` (exit 0).
- [ ] **Step 6: Commit.** `git add tools/sync_breach_deck_index.py breach-kill-chain-decks.html`; message `Deck list: carry each chain's industries onto its deck card`.

### Task 5: Tag the 60 chains

**Files:**
- Create: `docs/superpowers/plans/2026-11-23-breach-industry-evidence.md`
- Modify: `breach-timeline.html` (one line per tagged card), `breach-kill-chain-decks.html` (regenerated region)

**Interfaces:**
- Consumes: the reader agents' JSON in the scratchpad (`evidence/batch-1.json` to `batch-6.json`, keyed by slug: `industries[{industry, org, quote}]`, `none_reason`, `proposed`, `outside_knowledge`, `judgement_calls`); `render_line` (Task 1).

- [ ] **Step 1: Verify every quote mechanically.** A scratchpad script checks each quote is a substring of that slug's extracted page text (`scratchpad/text/<slug>.txt`, built from the page's `<main>` with tags stripped and entities decoded), and that each industry is in the vocabulary. Expected: a count of quotes found and a list of misses. Control: plant one altered quote and confirm it is reported missing.
- [ ] **Step 2: Review the tags.** Re-read each `judgement_calls` and `proposed` entry against the spec's "hit" rule. Drop tags whose quote shows targeting only. Resolve proposed labels: map onto the vocabulary, or add a label (with synonyms) to Task 1's module and re-run its self-test.
- [ ] **Step 3: Write the evidence table.** One row per slug: card title, industries, and per industry the organization and the quote. List untagged chains with the reason, and the outside-knowledge leads as a separate section (leads for page updates, not tags).
- [ ] **Step 4: Stop for Shawn's review of the evidence table.** No card changes until he approves the tags.
- [ ] **Step 5: Insert the lines.** A scratchpad script inserts `render_line(labels)` into each tagged card, on its own line after the `breach-card-summary` paragraph, at the summary's indent. It asserts the page changed in exactly as many places as there are tagged cards.
- [ ] **Step 6: Regenerate, twice.** `python3 tools/sync_breach_timeline_index.py` twice, then `python3 tools/sync_breach_deck_index.py` twice: the second run of each prints "up to date". Then both `--check` exit 0, and both `--self-test` exit 0.
- [ ] **Step 7: Commit.** `git add breach-timeline.html breach-kill-chain-decks.html docs/superpowers/plans/2026-11-23-breach-industry-evidence.md`; message `Breach pages: tag each kill chain with the industries it hit`.

### Task 6: Verify in the browser, run the gates

**Files:** none (scratchpad scripts only), unless a check finds a defect.

- [ ] **Step 1: Stamp for local preview.** `python3 update_sri.py`. The stamps stay uncommitted: everything else is committed by now, so `git restore .` later discards only stamps.
- [ ] **Step 2: Playwright under production's CSP.** A scratchpad script serves the worktree locally and loads both pages with `route.fulfill` adding `content-security-policy: default-src 'self'; style-src 'self'; script-src 'self'; frame-src https://docs.google.com`. Assert `document.styleSheets.length > 0`, then:
  - pressing each button shows exactly the cards whose line names that industry (counts compared with a count from the HTML);
  - pressing Finance then Healthcare leaves the box reading "Healthcare", with only Healthcare pressed;
  - pressing the pressed button clears the box;
  - typing `bank` gives the same set as Finance; typing `finance` presses Finance;
  - typing `industries` matches no card on either page (the label is not searched), and typing `slides` still matches none on the decks page;
  - Escape and "Clear the search" leave no button pressed;
  - reloading after typing `healthcare` (browser form restore) comes back with Healthcare pressed. If Chromium doesn't restore the field, say so in the report rather than claiming it.
- [ ] **Step 3: Scripts off.** `java_script_enabled=False`: no button is visible (`checkVisibility()` false), and the industries lines are visible on the cards.
- [ ] **Step 4: Contrast, light and dark.** Load each page fresh under `prefers-color-scheme` emulation and measure `.industries-hit` text and pressed and unpressed `.card-finder-btn` against their backgrounds, blending translucent fills (`.breach-card` sits on its own background). Want 4.5:1 or better. Control: inject `:root{--text-muted:#cbd5e1}` and confirm the light run fails.
- [ ] **Step 5: Composition.** Full-page screenshots of both pages at desktop and 375px. The button row sits inside the finder box, sharing its centre line; the cards are not stretched. Send them to Shawn.
- [ ] **Step 6: Gates.** Expected output for each:
  - `python3 tools/check_no_inline_scripts.py`: exit 0.
  - The CLAUDE.md inline-`<style>` check prints `clean`.
  - `grep -rlE '\sstyle="[^"]*:' --include='*.html' .` prints nothing.
  - `python3 tools/sync_dark_branch.py --check`: exit 0.
  - `python3 tools/check_faq_jsonld_parity.py --check`: exit 0.
  - `python3 tools/check_readme_coverage.py --check`: exit 0.
  - A dash scan of every changed line prints nothing: `git diff origin/main...HEAD | grep -nP '^\+.*(\x{2014}|\x{2013}|&mdash;|&ndash;| - )'`. Card titles' existing ` - ` separators are not on added lines.
  - The lessons' pre-PR commands print nothing for stamps and indexes.
- [ ] **Step 7: Discard the stamps.** `git restore .`, then `git status --short` shows a clean tree.
- [ ] **Step 8: Report.** Report as committed and ready to push; don't push. If the change is to land as a PR rather than a direct push, the branch already holds no generated files.
