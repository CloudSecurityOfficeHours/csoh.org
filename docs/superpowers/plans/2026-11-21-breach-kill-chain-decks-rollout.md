# Breach kill chain decks: rollout to the remaining pages

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each of the other 59 breach pages a fact-reviewed slide deck, uploaded privately for Shawn, then shared and linked from its page one batch at a time on his go.

**Architecture:** The pilot's tooling is reused: one hand-written outline per page in `tools/decks/breaches/<slug>.deck`, checked by `tools/build_breach_decks.py --check`, built by `--build`, uploaded and checked in Google's render by the controller, and linked by `--record`. Task 1 adds what the remaining pages need and the pilot did not: a phase-group slide for the two very long chains, phase-label parsing for two pages' label styles, and a crosslinker skip zone for deck lines. Outlines run newest first in seven batches; the two long chains and the Mitnick/Novell page go last.

**Tech Stack:** Python 3 standard library (checker), python-pptx 1.0.2 (local build only, `/Users/shawn/.pyenv/versions/3.10.0/bin/python3`), Google Drive and Slides connectors, lychee.

**Spec:** `docs/superpowers/specs/2026-11-20-breach-kill-chain-decks-design.md` (Rollout section). The approved pilot is `tools/decks/breaches/vapor-panda-artex.deck`; its plan is `docs/superpowers/plans/2026-11-20-breach-kill-chain-decks.md` and its lessons are in `docs/superpowers/plans/2026-11-20-breach-kill-chain-decks-pilot-notes.md`.

## Global Constraints

- Decks are CC BY-NC 4.0; breach pages stay CC BY-NC-ND 4.0. The renderer adds attribution and licence to the cover and closing slides.
- 18 to 36 slides per deck, counting the three generated slides. `--build` is the layout check: every deck builds with 0 verify findings.
- A non-background slide, and its notes, say nothing the page does not. Hedges and attributions survive ("per CrowdStrike", "likely", "about", "moderate-confidence"); a vendor's claim never becomes the site's own voice; victims the page anonymizes stay anonymous; diagrams and the defense matrix show only connections the page states.
- A background slide is labelled, names its source on the slide, cites an allowed host, and says nothing about the incident beyond the page.
- Stage `phase:` lines and flow tactics mirror the page's phase labels exactly (the gate enforces it).
- Every deck carries the Wiz disclosure wherever its page does ("(disclosure: the site's author works at Wiz)" at the first visible Wiz mention beside a competitor). Thirteen pages mention Wiz.
- No U+2013 or U+2014 and no spaced hyphen used as a dash in any slide text or note. No AI tells from `docs/agent-lessons.md` section 2. No ranking of third parties. ATT&CK v19 names.
- Uploading privately to the "CSOH breach decks" folder (`1F9D5b8yeJfOJQhSvf2_HTG0zhcJeafTh`) is approved only if Shawn says so when approving this plan; otherwise each batch's upload waits for his go. Sharing publicly, and deleting or trashing any Drive file, each need his explicit go for that batch or file. Never write the deck owner's email address into the repo.
- Commit locally with explicit paths (never `git add -A`); push only when Shawn says so. No CI-skip token in any commit message. End messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A deck that says more than its page.** The pilot passed every gate and its fact review still found five Important findings (dropped hedges, a lost attribution, a diagram implying a connection). Every outline task's review is a fresh fact review on the most capable model, slide by slide and note by note against the page, with background slides checked against their named sources.
2. **A missing or misplaced Wiz disclosure.** Thirteen pages mention Wiz; twelve carry the disclosure. `shai-hulud-npm-worm` mentions Wiz with no disclosure on the page: its outline task checks whether the mention sits beside a competitor and, if it does, reports it to Shawn as a page fix rather than adding a disclosure the page lacks.
3. **A phase-group slide that merges stages the page keeps apart.** The gate requires every grouped stage to share one phase label; the fact review also checks that a group's single "why it matters" line is true of every stage in it.
4. **The Mitnick/Novell deck's framing.** It is Shawn's own story: the trap that caught Mitnick, not a successful breach, told as `breaches/mitnick-novell.html` tells it. Its page is never edited. Shawn reviews that deck himself before it is uploaded.
5. **Google render defects at new extremes.** Long technique names, three chips, two or more flow slides and phase-group slides are new to Google's render. Every batch's render check looks at every slide in Google's own render, not the local preview.

---

## Outline procedure (every outline task)

Each outline task names one page. Its implementer writes `tools/decks/breaches/<slug>.deck`; nothing else changes.

- [ ] **Step 1: Read.** The page in full, the pilot outline, the pilot notes, the breach section of `tools/DECKS_README.md`, and the spec's Deck shape, Anti-goals and Background explainer slides sections.
- [ ] **Step 2: Write the outline** in the spec's deck shape. One `stage` slide per stage (a `stage-group` slide per phase only on the two long-chain pages, Tasks 64 and 65); one or more `flow` slides covering every stage, at most eight steps each; a stage with no ATT&CK technique carries no `technique:` line and its flow step's technique field is `-`; background slides for concepts the page names but does not explain, at most one per stage, each from an allowed host. Two discussion question and answer pairs. The promise restates the page's own summary in one hedged sentence.
- [ ] **Step 3: Gate.** `python3 tools/build_breach_decks.py --check` reports 0 findings.
- [ ] **Step 4: Build.** `/Users/shawn/.pyenv/versions/3.10.0/bin/python3 tools/build_breach_decks.py --build <slug>` exits 0 with 0 verify findings. Trim any slide that raises LayoutError.
- [ ] **Step 5: Control.** Change one figure in the outline to a value the page does not have; `--check` names it; restore from a scratch copy.
- [ ] **Step 6: Commit** `tools/decks/breaches/<slug>.deck` alone, message `decks: <breach name> outline`.

**Review (controller):** one fresh fact review on the most capable model per deck (Review Focus 1 to 3 and the Global Constraints), then the SDD fix loop. Fix every finding, minors included: the decks are public.

## Publish procedure (one upload task and one publish task per batch)

Run by the controller: it uses the Drive and Slides connectors.

**Upload and render check:**

- [ ] Build each deck in the batch, upload it privately as Google Slides into the "CSOH breach decks" folder, and confirm from its metadata and permissions that the owner is the connector account and only the owner has access. Log each ID in the ledger.
- [ ] Pull a LARGE thumbnail of every slide (`read_slide_page_thumbnail`), download the image URLs, build contact sheets, and check fonts, wrapping, overflow, arrows, chips, bands, footers and link styling. A defect goes back to the outline or renderer; the re-upload gets a new ID and the old one joins the list of superseded files for Shawn.
- [ ] Hand the batch to Shawn: the private links, what the render check found, and the superseded files. Stop for his go on this batch; carry on with the next batch's outlines meanwhile.

**Publish (only after Shawn's go for that batch):**

- [ ] Rebase onto `origin/main` (nothing is pushed), regenerating any generated file that conflicts, and confirm `--check` still reports 0 findings. A page that changed on main since its outline was reviewed sends that outline back through the outline procedure and its review.
- [ ] Share each deck `anyoneWithLink` as reader. Signed out, its `/export/pdf` returns `200 application/pdf` starting `%PDF-` with one page per slide, and its `/copy` redirects to `accounts.google.com`.
- [ ] `python3 tools/build_breach_decks.py --record <slug> <id>` for each deck, then `--stamp` twice and confirm the second run changes nothing.
- [ ] `python3 tools/sync_breach_deck_index.py` twice (the second run reports the list up to date), so `breach-kill-chain-decks.html` lists every published deck. Shawn's rule: every batch publish runs it, in the same commit as the batch.
- [ ] Gates, each exit 0: `--self-test`, `--check`, `--stale --published-only` (no deck listed), `python3 tools/sync_breach_deck_index.py --self-test` and `--check`, `python3 tools/check_readme_coverage.py --check`, `python3 tools/check_no_inline_scripts.py`, `python3 tools/sync_glossary_usage.py --check`. `lychee --config .lychee.toml` on the batch's pages and `breach-kill-chain-decks.html` reports no errors.
- [ ] Preview two of the batch's pages and `breach-kill-chain-decks.html` under production's CSP, light and dark: the deck line sits after the source links and its links are underlined; the index shows one card per published deck.
- [ ] Commit `tools/decks/breaches/published.json`, the batch's `breaches/<slug>.html` pages and `breach-kill-chain-decks.html` with the message `decks: publish <batch name> breach decks and link them from their pages`. Do not push.

---

### Task 0: Housekeeping before the rollout

- [ ] **Step 1:** Ask Shawn to OK deleting the superseded pilot upload `1Aty73b-UmRXItQ-dC51cEAYf56ZvseqmrfUzMNpwP3c`; trash it only on his yes.
- [ ] **Step 2:** Rebase onto `origin/main`; `--self-test`, `--check` and `--stale --published-only` exit 0 and list no stale deck.

### Task 1: Tooling the remaining pages need

**Files:**
- Modify: `tools/build_breach_decks.py`, `tools/breach_deck_render.py`, `tools/crosslink_pages.py`, `tools/DECKS_README.md`

**Interfaces:**
- Consumes: `phase_name(text: str) -> str`, `LAYOUTS`, `page_findings`, the render dispatch, `crosslink_page()` in `tools/crosslink_pages.py`.
- Produces:
  - `phase_name` strips every leading character that is not a letter or digit (the "₿" on `breaches/event-stream-npm.html`'s Impact label, emoji, variation selectors) and ends the name at the first ":" or the first spaced hyphen " - ", whichever comes first (the labels on `breaches/mitnick-novell.html`). No page is edited.
  - Layout `stage-group`: control lines `stages: NN NN ...` (2 to 6 stage numbers, ascending) and `phase:` (both required); typed lines `technique` 0 to 3 (`id | name`) and `row` one per listed stage (`NN | what happened`, in the listed order); optional prose is the "why it matters" line. Gate: every listed stage exists on the page, all share the slide's phase name, every technique belongs to one of them, and the rows name exactly the listed stages. Renderer: the phase band reads `<PHASE> · STAGES 03, 04 AND 05`, each row shows its stage number and text, chips as on a stage slide, and LayoutError names the slide when the rows do not fit (the author splits the group).
  - `crosslink_pages.py` treats a `<p>` carrying `data-breach-deck` or `data-howto-deck` as a skip zone, beside the `no-glossary` zones.

- [ ] **Step 1: Write the failing cases.** `phase_name_symbols`: `phase_name("₿ Impact: Coins taken")` is `"Impact"`; `phase_name("Reconnaissance - Open Source Intelligence")` is `"Reconnaissance"`; `phase_name("Cross-Site Scripting: x")` is `"Cross-Site Scripting"` (an unspaced hyphen is kept). `phase_gate_real_labels`: on the real `breaches/mitnick-novell.html` and `breaches/event-stream-npm.html`, every stage's parsed phase name contains no ":" and no " - " and starts with a letter. `stage_group_parse` and `stage_group_gate`: a two-stage group passes; a group listing a stage from another phase, a row for an unlisted stage, a missing row, and a technique from an unlisted stage are each a finding. `stage_group_render` (render case): a group of six rows verifies clean, and one of seven long rows raises LayoutError naming the slide. `crosslink_skips_deck_line`: a temp page whose deck line contains a glossary key, passed through `crosslink_page()`, gains no link inside the deck line and still gains one in its prose (control).
- [ ] **Step 2: Run** `--self-test`, `--self-test-render` and the crosslink case; the new cases fail.
- [ ] **Step 3: Implement** the three changes, and document `stage-group`, the phase-label rule and the skip zone in the breach section of `tools/DECKS_README.md`.
- [ ] **Step 4: Run** `--self-test` (also with python-pptx blocked), `--self-test-render`, `--check` (the pilot still 0 findings), `python3 tools/check_readme_coverage.py --check`, and `crosslink_pages.py` twice on one breach page from a scratch copy, confirming the second run changes nothing. All pass.
- [ ] **Step 5: Commit** the four files, message `decks: phase-group slides, phase labels with symbols or spaced hyphens, deck lines skipped by the crosslinker`.

### Batch A: October 2026

Each task follows the outline procedure for its page.

- **Task 2:** `artex-github-secrets-azure`. Microsoft names no actor for the Azure follow-on; the deck must not either. Related: the pilot.
- **Task 3:** `binance-tradertraitor-signing-service`
- **Task 4:** `black-october-ai-platforms`. Nine stages: two flow slides. Carries the Wiz disclosure.
- **Task 5:** `litellm-1-107-release-hijack`. Carries the Wiz disclosure.
- **Task 6:** `ovhcloud-cli-release-swap`
- **Task 7:** `polymarket-debugbear-rum-drainer`
- **Task 8:** `storm-0940-connectwise`. Carries the Wiz disclosure. Related: the pilot.
- **Task 9:** `workos-escaped-research-agent`
- **Task 10:** `gmo-onamae-desktop-cloud`
- **Task 11:** `m365-token-spray-replay`
- **Task 12:** Batch A upload and render check.

### Batch B: March to August 2026

- **Task 13:** `chaindrop-keyv-npm`
- **Task 14:** `huggingface-openai-agent`
- **Task 15:** `ai-assisted-aws-72-hours`
- **Task 16:** `storm-3168-jadepuffer-azure`
- **Task 17:** `megalodon-github-actions`
- **Task 18:** `mini-shai-hulud-tanstack`. Carries the Wiz disclosure.
- **Task 19:** `storm-2949-entra-sspr`
- **Task 20:** `vercel-context-ai-oauth`
- **Task 21:** `vimeo-anodot-shinyhunters`
- **Task 22:** `litellm-pypi-teampcp`
- **Task 23:** Batch B upload and render check.

### Batch C: 2025 (and promptware, 2024 to 2026)

- **Task 24:** `promptware`
- **Task 25:** `anthropic-gtg-1002`
- **Task 26:** `npm-debug-chalk-phishing`. Carries the Wiz disclosure.
- **Task 27:** `shai-hulud-npm-worm`. Mentions Wiz with no disclosure on the page (Review Focus 2).
- **Task 28:** `oracle-ebs-cl0p`
- **Task 29:** `nx-s1ngularity`. Carries the Wiz disclosure.
- **Task 30:** `salesloft-drift-unc6395`
- **Task 31:** `entra-id-actor-token`
- **Task 32:** `sharepoint-toolshell`
- **Task 33:** `unc6040-salesforce-vishing`
- **Task 34:** Batch C upload and render check.

### Batch D: 2023 to early 2025

- **Task 35:** `tj-actions-changed-files`. Carries the Wiz disclosure.
- **Task 36:** `codefinger-s3`
- **Task 37:** `ultralytics-cache-poisoning`. Carries the Wiz disclosure.
- **Task 38:** `snowflake-unc5537`
- **Task 39:** `polyfill-io`
- **Task 40:** `change-healthcare-alphv`
- **Task 41:** `xz-utils-backdoor`
- **Task 42:** `midnight-blizzard-microsoft`
- **Task 43:** `okta-support-har`
- **Task 44:** `scattered-spider-mgm`
- **Task 45:** Batch D upload and render check.

### Batch E: 2021 to 2023

- **Task 46:** `microsoft-sas-leak`. Carries the Wiz disclosure.
- **Task 47:** `moveit-cl0p`
- **Task 48:** `storm-0558`. Carries the Wiz disclosure.
- **Task 49:** `3cx-x-trader`
- **Task 50:** `circleci-session-theft`
- **Task 51:** `lastpass`. Its phase labels are "Stage 1" style names; the deck mirrors them, and the renderer's fallback colour applies.
- **Task 52:** `uber`
- **Task 53:** `0ktapus-twilio`
- **Task 54:** `okta-lapsus-sitel`
- **Task 55:** `log4shell`
- **Task 56:** Batch E upload and render check.

### Batch F: 2021 and earlier

- **Task 57:** `chaosdb-cosmos`. Carries the Wiz disclosure.
- **Task 58:** `kaseya-vsa-revil`
- **Task 59:** `codecov-bash-uploader`
- **Task 60:** `solarwinds`. Some phase labels have no subtitle; the gate mirrors the whole label.
- **Task 61:** `capital-one`
- **Task 62:** `event-stream-npm`. Its Impact label carries "₿", which Task 1 strips.
- **Task 63:** Batch F upload and render check.

### Batch G: the long chains and Mitnick/Novell

The two long chains follow Shawn's choice: stages that share a phase share one `stage-group` slide; flow slides cover every stage, eight per slide; the deck stays within 36 slides, so optional sections (timeline, compare, extra defense slides) give way first. Each gets its own fact review.

- **Task 64:** `php2shell-pan-os` (18 stages, 51 sources). Carries the Wiz disclosure.
- **Task 65:** `huggingface-agent-intrusion-timeline` (28 stages, 43 sources).
- **Task 66:** `mitnick-novell`. Nine stages; its labels use spaced hyphens, which Task 1 parses; its page is never edited. The story is the trap that caught Mitnick, told as the page tells it (Review Focus 4). Shawn reviews the outline before it is built for upload.
- **Task 67:** Batch G upload and render check.

### Tasks 68 to 74: Publish batches A to G

The publish procedure, one task per batch, each only after Shawn's go for that batch.

### After the last batch

The SDD final whole-branch review, carrying the tooling minors listed in the pilot notes, then superpowers:finishing-a-development-branch.
