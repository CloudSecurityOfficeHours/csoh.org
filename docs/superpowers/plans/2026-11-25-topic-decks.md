# Topic slide decks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each teaching topic on `topics.html` a fact-checked slide deck, illustrated with its page's own diagrams, published to Google Slides and linked from its page, for well under the per-deck token cost of the breach rollout.

**Architecture:** Reuse the breach deck machinery instead of writing a third builder. `tools/build_breach_decks.py` gains a `DeckKind` seam, and a thin `tools/build_topic_decks.py` supplies the topic kind: outline directory, page set (read from `topics.html`), slide limits, layouts, deck-line anchor and mapping file. A new `figure` layout places a page diagram, rendered to PNG by Playwright, and the cover carries the page's hero illustration. Agents read a compact text extract of each page, never its HTML or images. A Sonnet drafter writes each outline against a section-scoped gate, then one Opus reviewer per deck checks it against only the sections it cites. Decks publish in batches of up to five, one fresh session (or Workflow run) per batch.

**Tech Stack:** Python 3 standard library (gate, extract), python-pptx (build), Playwright (figure rendering), PIL (contact sheets), Google Slides and Drive connectors plus Claude in Chrome (upload).

**Spec:** `docs/superpowers/specs/2026-11-20-breach-kill-chain-decks-design.md` for deck shape, licence and publishing, and the topic format in Task 0 below for what differs. `tools/DECKS_README.md` documents the outline format.

## Where the tokens go, and the levers

| What cost tokens in the breach rollout | What this plan does instead |
|---|---|
| Agents read each page's HTML | `--extract SLUG` prints `<main>` as text with section ids and one line per figure. On kubernetes, zero-trust and data-security it is 2.0 to 2.8 times smaller than the page file. The 41 pages hold about 263,000 words, and every page is read at least twice (draft, review). |
| Background slides needed web research, and the review checked each outside source (239 background slides across the breach outlines) | No background slides. A topic page already is the explainer, so no deck fetches anything from the web. |
| The fact review read the whole page | The gate holds every number, link and figure to the slide's cited sections, so the reviewer reads only those sections plus the heading list. |
| Every slide checked in Google's render, one image each | One contact-sheet image per deck (thumbnails fetched with curl, tiled locally); open a single slide only when its tile looks wrong. The text layouts already render in the 68 published breach decks; the image spike and the pilot check `figure` slides and cover art slide by slide. |
| Fix loop and re-review through the controller | The reviewer fixes its own findings, reruns `--check` and `--build`, and reports one line per Important finding. No third agent; the controller never reads an outline. |
| Long controller sessions | One fresh session (or Workflow run) per batch, briefed with one line pointing at this file. Agents return at most five lines. |
| Any page edit flags the whole deck stale | Per-section hashes, covering each section's text and its figures' SVG markup: `--stale` names the changed sections and the re-review reads only those. Topic pages change far more often than breach pages (weekly docs review, style passes), so this saving recurs for as long as the decks exist. |
| A stop per batch to approve private uploads | Approving this plan approves private uploads. Public sharing stays per batch. |
| Drafting model | Drafter on Sonnet 5.5, with the gate catching format. Review stays on Opus 5.5, where the breach pilot showed the value is (five Important findings on an outline that passed every gate). The pilot measures whether Sonnet drafts hold up; Task 1 Step 6 switches drafting to Opus if they do not. |
| (new) Pictures | Drafters choose diagrams from the extract's figure lines (title, description, caption) and never open an image. The builder renders them; the contact sheet already shows every slide. Pictures add almost no tokens. |

Deck size is not a lever here: 15 to 30 slides with notes up to 300 words is close to the breach decks' output per deck, so the savings come from the rows above. Two agents per deck, so a batch of five decks is ten agents.

## Decisions (Shawn, 2026-11-25)

1. **Pages.** The 41 teaching pages. Glossary, FAQ and Vendor Landscape get no deck. The page list is `topics.html` minus `EXCLUDED` in the tool, so a new topic card shows up in `--status` without a code change.
2. **Size.** 15 to 30 slides counting the three generated slides. Speaker notes up to 300 words where a slide needs them; 300 is a ceiling, not a target.
3. **Models.** Sonnet 5.5 drafts, Opus 5.5 reviews, with the pilot's tiering check.
4. **Pictures.** Decks carry more than one picture, taken from the page itself; not every diagram on a page has to appear. The cover shows the page's hero illustration (34 pages) or, without one, its topic tile from `img/thumbs/`. A deck has at least one `figure` slide when its page has a diagram figure (60 across 39 pages), and may use each figure once. `gcp-security` and `zero-trust` have no diagram figures, so their decks carry cover art only; a diagram for those pages would be a page edit outside this plan.
5. **No background slides.**
6. **Build it pages** (`version-control`, `github-actions`, `terraform`, `cloud-deployment`) go last, in Batch 9, with a `code` layout reusing the how-to renderer's code box (an excerpt is whole lines from one `<pre>` on the page). The cloud-deployment deck leaves out the cost tables, which are re-derived from billing data and change.
7. **Deck link** is one line right after the `page-meta` line at the top of `<main>`. All 41 pages have exactly one.
8. **Licence** CC BY-NC 4.0, as the breach decks. **Drive folder** is a new "CSOH topic decks" folder.
9. **Uploads.** Approving this plan approves private uploads to that folder. Sharing publicly and trashing stay a per-batch go.
10. **Execution.** Each batch is one Workflow run of ten agents, started with "use a workflow" in that batch's session. The fallback is the same two agents per deck dispatched with the Agent tool.
11. **Deck list page.** None during the rollout. After Batch 9, decide whether to add one like `breach-kill-chain-decks.html`; it is a new page with the registration cost CLAUDE.md lists.

## Global Constraints

- No U+2013 or U+2014 and no spaced hyphen used as a dash, in outlines, notes, docs and commit messages.
- A slide and its notes say nothing their cited sections do not say. Keep every hedge, quantifier and attribution as the page writes it. Notes on a `figure` slide say only what the figure's title, description, caption and section say.
- On a page that carries "(disclosure: the site's author works at Wiz)", the first slide that mentions Wiz carries it too. No Wiz superlatives, and no ranking of third parties.
- 15 to 30 slides counting the three generated slides; at most 40 words of prose per slide (25 on a `figure` slide), 14 per typed field, 12 per heading and 300 in the notes; notes on every slide.
- Pictures come only from the deck's own page. Every picture carries alt text from its SVG's `<title>`.
- `--build` is the layout check: every deck builds with 0 verify findings.
- Builds need python-pptx and Playwright: probe `python3 -c "import pptx, playwright"`, else use `/Users/shawn/.pyenv/versions/3.10.0/bin/python3`.
- Every batch worktree is cut from, and rebased onto, `origin/main` before building.
- Commit locally with explicit paths, never `git add -A`; push only when Shawn says. No CI-skip token in any commit message. End messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Never write the deck owner's email address into the repo or into any agent brief. Trash a superseded deck only after the deploy that relinks its page.

## Review Focus

1. **A slide that says more than its section:** a dropped hedge, two claims merged into one, a number from the page reused for a different claim, notes that read more into a diagram than its caption and description say. No gate sees these; they lead the reviewer's rubric.
2. **A page edited between draft and upload.** The weekly docs review edits topic pages. The upload step rebases and runs `--stale`; a stale deck goes back to a reviewer with only the changed sections.
3. **A diagram redrawn on the page while the deck keeps the old picture.** A text-only hash misses a changed shape, so section hashes include each figure's SVG markup. Gate case in Task 0.
4. **A blank or clipped picture.** Rendering the page locally can drop `style.css` on an SRI mismatch, and a hero illustration styled by the stylesheet then renders blank. The renderer strips `integrity` attributes, asserts the stylesheet loaded, and refuses a PNG that is a single colour. Render case in Task 0.
5. **The Wiz disclosure** on the 21 pages that carry it, and **section ids renamed or removed**: `--check` names the slide in both cases. Gate cases in Task 0.

---

### Task 0: Topic deck tooling

Runs on Opus with one fresh reviewer (subagent-driven). This is the one place the plan spends freely: every later deck gets cheaper the more the gate catches.

**Files:**
- Modify: `tools/build_breach_decks.py` (add `DeckKind`; thread it through the functions that read kind-specific constants; breach behaviour unchanged)
- Modify: `tools/breach_deck_render.py` (correct the module docstring with the spike's result; allow picture shapes when the deck kind allows them)
- Create: `tools/build_topic_decks.py`, `tools/topic_deck_render.py` (cover art, the `figure` layout, figure rendering; every other layout delegates to `breach_deck_render.py`), `tools/decks/topics/published.json` (`{}`)
- Modify: `tools/crosslink_pages.py` (skip zone for a `<p>` carrying `data-topic-deck`), `tools/DECKS_README.md` (a topic section, written as current rules)

**Interfaces:**
- Produces, in `build_breach_decks.py`: `@dataclass(frozen=True) class DeckKind` with `name: str`, `outline_dir: Path`, `mapping_path: Path`, `deck_attr: str`, `header_keys: tuple[str, ...]`, `page_re: re.Pattern[str]`, `layouts: frozenset[str]`, `control_keys: frozenset[str]`, `min_slides: int`, `max_slides: int`, `max_notes_words: int`, `pictures: bool`, `insert_deck_line: Callable[[str, str], str]`, `page_findings: Callable[[BDeck, str], list[str]]`; and `BREACH: DeckKind` holding today's constants (`pictures=False`). Functions keep their names and take `kind: DeckKind = BREACH`.
- Produces, in `build_topic_decks.py`: `TOPIC: DeckKind` (15, 30, 300, `pictures=True`); `EXCLUDED = frozenset({"glossary.html", "faq.html", "vendor-landscape.html"})`; `topic_pages() -> list[str]` (card hrefs on `topics.html` minus `EXCLUDED`, in card order); `@dataclass(frozen=True) class Figure` with `id`, `section`, `title`, `desc`, `caption`, `svg_sha256`; `figures(page_html: str) -> dict[str, Figure]` (each `<figure>` in `<main>` holding an `<svg>`, keyed by the figure's `id`, or by its SVG `<title>`'s `id` where the figure has none, as 18 of the 60 do); `has_hero(page_html: str) -> bool`; `sections(page_html: str) -> dict[str, str]`; `section_hashes(page_html: str) -> dict[str, str]` (text plus the SVG markup of the section's figures); `extract(slug: str, only: list[str] | None = None) -> str`. CLI modes as the breach tool (`--self-test --check --build --stale [--published-only] --status --stamp --record`) plus `--extract SLUG [--sections ID,ID]`.
- Produces, in `topic_deck_render.py`: `render_figure_png(page: Path, target: str, out: Path) -> Path`, where `target` is a figure id or `"hero"`; PNGs are cached in `tools/decks/topics/build/figures/<slug>/<target>-<svg_sha256[:12]>.png`, so an unchanged figure is never re-rendered. `--self-test` and `--check` never import Playwright or python-pptx, so CI stays standard-library only.

**Topic outline format** (what differs from the breach format):
- Header: `title`, `page: <slug>.html` (a page from `topic_pages()`), `as-of`, `promise`.
- Every slide carries `section: <id>` or `section: <id> | <id>`. An id is the `id` of the `<section>` wrapping an h2 in `<main>`. An h2 outside such a section (30 of the 41 pages have one) gets a slug of its text.
- Layouts: `text`, `stats`, `checklist`, `links`, `layers`, `timeline`, `compare`, `table`, `bars`, `matrix`, `question`, `answer`, `figure`. No `stage`, `stage-group`, `flow` or `background`; `code` arrives in Batch 9.
- A `figure` slide has one `figure: <id>` control line naming a figure inside its cited section, a heading, and at most 25 words of prose. The builder places the PNG scaled to fit with its aspect ratio kept, on a white panel, with the page's own `<figcaption>` under it; the drafter never types the caption. Each figure appears at most once per deck.
- A deck whose page has a diagram figure has at least one `figure` slide.
- Every number and link in a slide's text and notes appears in its cited sections (the breach page check, scoped).
- The Wiz rule from Global Constraints.
- `published.json` entries hold `id`, `outline_sha256`, `page_sha256`, `sections` (cited id to hash) and `published`.
- The deck line is `<p class="page-meta" data-topic-deck>`, right after the page's `page-meta` paragraph, with the breach deck line's link text.

**Extract format:** `## <h2 text> {#id}` and `### <h3 text>` lines, paragraphs as single lines, `- ` list items, table rows as `| a | b |`, a link's URL in parentheses except glossary links, and each figure where it sits as `[figure #id] <title>: <desc> (caption: <caption>)`. The toc, page-finder, `page-meta` and deck line are dropped. With `--sections`, the output is the heading list followed by only those sections.

- [ ] **Step 1: Image spike, before any code.** Build a two-slide .pptx with python-pptx: one rendered PNG of `kubernetes.html`'s `cluster-supply-chain` figure, one of its hero. Upload it privately through the Chrome picker (the breach deck memory's method) and read one LARGE thumbnail of each slide. If both pictures survive the conversion, the `.pptx` carries them. If not, stop and rewrite this task with the fallback: the builder leaves a named placeholder shape, and after the import the PNGs, uploaded to the Drive folder and shared by link, replace it through the Slides connector's `createImage`. Record the result in the pilot notes; the spike file is trashed with the pilot's go.
- [ ] **Step 2: Record the breach baseline.** Save the output of `python3 tools/build_breach_decks.py --check` and `--stale --published-only` to the scratchpad, and confirm `--self-test` passes.
- [ ] **Step 3: Write the failing cases.** Gate, in `build_topic_decks.py`: `_case_figure_keyed_by_title_id` (a figure with no `id` is found by its `<title>` id), `_case_section_unknown` (a slide cites `nope`; the finding names the outline line and the id), `_case_number_outside_section`, `_case_wiz_disclosure` (page with the disclosure and a deck mentioning Wiz without it is a finding; the same deck against a page without it is clean), `_case_layout_not_allowed` (a `stage` slide), `_case_page_not_a_topic` (`glossary.html`, and a page absent from `topics.html`), `_case_figure_unknown`, `_case_figure_outside_section`, `_case_figure_twice`, `_case_figure_required` (page with a diagram, deck with no `figure` slide), `_case_figure_prose_limit` (26 words on a `figure` slide), `_case_extract_drops_glossary_links`, `_case_extract_lists_figures`, `_case_extract_sections_only`, `_case_section_hash_scoped` (editing section A changes A's hash only), `_case_section_hash_sees_svg` (changing one `<rect>` width in a figure changes its section's hash), `_case_stale_names_sections`, `_case_stamp_after_page_meta`, `_case_stamp_idempotent`, `_case_crosslink_skips_topic_deck_line`. Render, in `topic_deck_render.py`: `_case_figure_fits_and_keeps_ratio` (placed width over height within 1% of the PNG's), `_case_figure_resolution` (at least 1.5 image pixels per point of placed width), `_case_caption_from_page`, `_case_picture_alt_text`, `_case_blank_png_refused`, `_case_cover_hero_or_tile`, `_case_breach_still_refuses_pictures`.
- [ ] **Step 4:** both tools' `--self-test` (and `--self-test-render`) fail on each new case.
- [ ] **Step 5: Implement** `DeckKind`, the topic module and the topic renderer, importing from the breach modules rather than copying. Figures render by loading the page from the working tree in Playwright with a light colour scheme and device scale 2, stripping `integrity` attributes in the route handler, asserting `document.styleSheets.length` is above 0, and screenshotting the figure's `<svg>` (or the hero's).
- [ ] **Step 6: Breach unchanged.** Re-run Step 2's commands and `diff` against the baseline: no difference. `--build vapor-panda-artex` and one stage-group deck both exit 0 with 0 verify findings.
- [ ] **Step 7:** every self-test passes. Controls: `--extract kubernetes` lists one `## ` line per h2 in `<main>` other than "On this page" (18 on that page) and one `[figure` line, and its length is under half the page file's. Render every hero and figure on three pages into the scratchpad and confirm none is refused as blank.
- [ ] **Step 8:** `ruff check` the touched Python, then commit the files above: `decks: topic deck tooling, with page figures, on the shared breach deck builder`.

The CI gate is added in Task 1, with the first outline: `--check` exits 1 on a tree with no outlines.

### Task 1: Pilot, `kubernetes.html`, end to end

Chosen because it is mid-sized (5,258 words and 18 sections; the median topic page has 6,602 words), carries the Wiz disclosure, has a hero illustration and a diagram figure, and has EKS/AKS/GKE comparison content for the `compare` and `table` layouts. It runs the batch procedure exactly, so it also measures it.

- [ ] **Step 1:** Run the batch procedure's agent pair (below) for `kubernetes`, recording each agent's token use from its result.
- [ ] **Step 2:** Build, upload privately, and check every slide in Google's render this once, pictures included.
- [ ] **Step 3:** Stop for Shawn: the private link, the reviewer's findings, the token figures. He judges shape, density, the pictures and the notes' voice. Fold his changes into the topic section of `tools/DECKS_README.md` and the pilot outline, which later drafters use as their example.
- [ ] **Step 4:** On his go: share (anyone with the link, reader), `--record kubernetes <id>`, and add `--self-test`, `--check` and a `--stale --published-only` warning step for `build_topic_decks.py` to `.github/workflows/validate-html.yml`. Trash the spike file.
- [ ] **Step 5:** Gates exit 0: both tools' `--self-test` and `--check`, `python3 tools/check_readme_coverage.py --check`, `python3 tools/sync_glossary_usage.py --check`. Preview `kubernetes.html` under production's CSP, light and dark: the deck line sits under the page-meta line and its links are underlined. Commit the outline, `published.json`, `kubernetes.html` and the workflow file.
- [ ] **Step 6: Tiering check.** If the reviewer found more than three Important meaning errors in the Sonnet draft, drafting moves to Opus for the rollout; record the choice in `docs/superpowers/plans/2026-11-25-topic-decks-pilot-notes.md` (under 40 lines: the spike result, token use per agent, findings by kind, procedure changes).

### Batch procedure

Each batch runs in a new session whose whole brief is: "Run Batch N of `docs/superpowers/plans/2026-11-25-topic-decks.md`."

- [ ] **Worktree** `csoh/topic-decks-batch-N` from `origin/main`.
- [ ] **Agents**, one pair per deck, all pairs in parallel. Each prompt starts with the same text for every deck (the topic section of `tools/DECKS_README.md`, the pilot outline path, Global Constraints) and ends with the slug, so the shared part can be cached.
  - **Drafter** (Sonnet 5.5, or Opus after Task 1 Step 6): reads `--extract <slug>` and the pilot outline; chooses figures from the extract's figure lines without opening any image; writes `tools/decks/topics/<slug>.deck`; loops `--check` and `--build <slug>` to 0 findings; commits the outline alone (`decks: <topic> outline`). Returns slug, slide count, figures used, gate status and at most three lines of doubts.
  - **Reviewer** (Opus 5.5, fresh, after its drafter): reads the outline and `--extract <slug> --sections <the ids it cites>`; checks Review Focus 1, then Global Constraints, slide by slide and note by note; fixes every finding in place, minors included; reruns both gates; commits (`decks: review <topic> outline`). Returns counts by severity, one line per Important finding, and anything left for Shawn.
- [ ] **Upload:** rebase, `--check`, `--stale`; build each deck; upload every .pptx through the Chrome picker in one `browser_batch` (the method in the breach deck memory); set titles with `update_file`; move the batch with one Drive multi-select; confirm owner-only access with `get_file_permissions`.
- [ ] **Render check:** for each deck, fetch its slide thumbnail URLs with `read_slide_page_thumbnail`, download them with curl, tile them with PIL into one image in the scratchpad, and read that image. Every picture must show, uncropped. Open a single slide only when its tile looks wrong.
- [ ] **Stop for Shawn:** private links, reviewer leftovers, render findings.
- [ ] **On his go:** share each deck; `--record` each; the Task 1 Step 5 gates; preview one page of the batch under production's CSP; commit `published.json` and the batch's pages (`decks: publish batch N topic decks and link them from their pages`). Do not push.

### Batches

Grouped by `topics.html` section, at most five decks each.

| Batch | Pages |
|---|---|
| 1 Foundations | what-is-cloud-security, shared-responsibility-model, cspm-vs-cnapp, cnapp-to-ai-app, cloud-security-best-practices |
| 2 Cloud providers | aws-security, azure-security, gcp-security, cloud-security-comparison |
| 3 Workloads | containers, serverless, service-mesh-security, ci-cd, landing-zones |
| 4 Identity and governance | iam, non-human-identity, zero-trust, grc, compliance-frameworks |
| 5 Data, network and apps | data-security, network-security, api-security, saas-security |
| 6 Threats and resilience | threat-modeling, human-risk, vulnerability-management, backup-dr |
| 7 Detection and response | cloud-logging, working-a-finding, cloud-soc, detection-engineering, incident-response |
| 8 Offense and AI | cloud-pentesting, ai-learning, ai-ml-security, mcp-security |
| 9 Build it | version-control, github-actions, terraform, cloud-deployment (first adds the `code` layout, with its own failing cases) |

### After the last batch

- [ ] `python3 tools/build_topic_decks.py --status` shows a published deck for every page in `topic_pages()`, and names the excluded pages.
- [ ] Decide Decision 11 with Shawn.
- [ ] Save a memory note on the topic deck workflow, linked from the breach deck one.
