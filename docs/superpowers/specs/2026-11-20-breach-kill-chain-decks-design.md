# Breach kill chain slide decks: design

## Intent

Every breach kill chain in `breaches/` gets a public slide deck. The pilot
is `breaches/vapor-panda-artex.html` (VAPOR PANDA / ARTEX); the other pages
follow once Shawn approves it.

A deck has to stand on its own two ways, both named by Shawn:

- **As a teaching artifact.** Someone reads the PDF with no presenter and
  no speaker notes, so every slide must explain itself. A Google Slides PDF
  export does not include speaker notes, so anything a reader must know
  goes on a slide, never only in the notes.
- **As a presentation.** Someone presents it, to a team or at a session,
  with the speaker notes as their script. The notes add the narration and
  the detail the slide leaves out; they never carry a fact the slides
  contradict.

Shawn asked for the pilot to be "as rich as possible". The designer reads
that as diagrams, stat tiles, a kill-chain flow, ATT&CK mapping, defenses
set against the steps they break, and teaching material (discussion
questions, a check of your own environment), not text slides alone.

## Decisions Shawn made

- **Pilot: VAPOR PANDA / ARTEX** (`breaches/vapor-panda-artex.html`), not
  the ARTEX exposed-secrets page.
- **Audience and use:** stands alone as a teaching artifact or as a
  presentation (above).
- **Build approach: hand-written outlines, one per breach** (approach B
  below), with the renderer extended for diagrams. Shawn chose this over
  generating decks from the page markup, for editorial control per deck.
- **Background explainer slides are in**, for concepts the page names but
  does not explain (see Background explainer slides).
- **Licence: CC BY-NC 4.0**, as for the how-to decks, so teachers can adapt
  a deck. Shawn chose it over CC BY-NC-ND knowing an edited copy could drop
  the page's hedges while still crediting csoh.org; CC BY's requirement to
  indicate changes is the mitigation. The "make your own copy" link stays.

Everything below that is not in this list is the designer's proposal, and
the items marked *builder's call* are left to the builder.

## Goals

- One deck per breach page, from a hand-written outline in the repo.
- Rich slide types: stat tiles, a kill-chain flow diagram, a layered
  diagram (for things like ARTEX's agent structure), a timeline, a
  comparison table, a to-scale bar comparison, a defense-to-stage matrix,
  stage slides, question and answer slides, a checklist and a sources
  slide.
- Every slide readable alone; every slide has speaker notes written as a
  presenter's script.
- Published as Google Slides, viewable by anyone with the link, with a PDF
  download and a "make your own copy" link written onto the breach page.
- A CI gate that ties each outline to its page, so a deck cannot quote a
  stage, number, technique or source the page does not have.
- A way to see which published decks need review because their page
  changed. Breach pages are rewritten when new disclosures land
  (`docs/agent-lessons.md` section 2), which the how-to pipeline never had
  to handle.

## Non-goals

- No embedded deck viewer on breach pages, no files hosted on csoh.org, no
  CSP change (same as the how-to decks).
- No deck index page and no structured data for decks in this round.
- No new detection queries. A deck shows hunting markers only where its
  page gives them. (A page that carries a query may have it quoted as a
  code excerpt, under the same contiguous-lines rule as the how-to decks.)
- No vendor logos, screenshots or long quotations from third-party reports.

## Anti-goals (failure even if everything else works)

- **A slide that says more than the page**, other than a marked background
  slide (below). This includes dropping a hedge
  or an attribution. The pilot page is careful: "about 140 compromised"
  comes from an interview and includes moderate-confidence cases, while
  nine is the confirmed figure; facts are "per CrowdStrike" or "per Check
  Point". A deck that states 140 as compromised, or turns a vendor's claim
  into the site's own, fails.
- **A visual that implies precision the page lacks.** A timeline with dates
  the page does not give, a bar chart not drawn to scale, or a diagram
  showing connections the source does not describe.
- **Naming victims the page keeps anonymous** ("a Greek government entity",
  "a US pharmaceutical organization").
- **Breaking the site's writing rules** (`docs/agent-lessons.md` section 2):
  no em or en dashes, no spaced hyphen used as a dash (the breach pages'
  own titles join the name to the chain with one, so slides reword them),
  none of the listed
  AI tells, no ranking of third parties, ATT&CK v19 names, and the Wiz
  disclosure where the page carries it.
- **Slides that do not read on a phone.** A LinkedIn document post is read
  on a small screen.
- **A breach page link that crawlers or `tools/normalize_urls.py` turn into
  a Google sign-in URL.** `normalize_urls.py` reads root-level pages only,
  so it never touches `breaches/`, but check this rather than trust it.

## Approaches considered

- **A. Generate each deck from the page markup, plus a short hand-written
  layer.** Every breach page shares one structure (stages with a title,
  technique, prose, facts box and tags; headline stats; defense items;
  sources), so a builder could turn a page into most of a deck. Cheap to
  roll out to every page and unable to drift, but each deck reads like its
  page in slide form and gives little editorial control. Not chosen.
- **B. Hand-write every deck, as the how-to decks are (chosen by Shawn).**
  Full editorial control over what each deck emphasizes and how it
  teaches. Costs: one outline per breach page, each needing its own fact
  review, and a gate to catch an outline drifting from its page.
- **C. HTML slides hosted on csoh.org.** No Google dependency, but the
  site's CSP and asset registration get in the way, and teachers lose the
  one-click copy and the PDF. Rejected, as it was for the how-to decks.

## Constraints

- **Reuse the how-to pipeline where it fits.** Palette, fonts, 16:9 size,
  readability floor, the Drive connector path, the publish steps, the
  approval gates and the `export/pdf` and `/copy` link pattern are already
  settled by the how-to pilot (`tools/DECKS_README.md`,
  `docs/superpowers/specs/2026-11-19-howto-slide-decks-design.md`).
- **Publishing scope.** Outlines, tools, the mapping file and build output
  live under `tools/`, which never ships. The only published change is the
  deck line on each breach page.
- **Keep the how-to gate green.** `build_howto_decks.py` globs
  `tools/decks/*.deck` without recursing and validates every key in
  `tools/decks/published.json` against a how-to guide. Breach outlines and
  their mapping must not land where that tool reads them.
- **The gate runs without python-pptx**, in `validate-html.yml`, like the
  how-to gate.
- **Google Slides conversion.** The how-to renderer uses only text boxes and
  solid rectangles because the converter drops SmartArt, embedded fonts and
  autofit-shrink. Diagrams therefore use native shapes (rectangles, rounded
  rectangles, lines with arrowheads, chevrons) and text boxes only. Whether
  lines and arrowheads survive conversion is unproven; the pilot settles it.
- **Licence.** Breach reconstructions stay CC BY-NC-ND 4.0 as editorial
  content; their decks are CC BY-NC 4.0 (Shawn's decision, above).
  `LICENSE` clause 3 currently names only decks made from the how-to
  guides and must be widened to breach decks and their outlines.
- **Readability floor.** Body text at least 18 pt; small labels (footer,
  source credits, chip text) at least 14 pt. About 40 words of prose per
  slide. Text meets 4.5:1 contrast against its own fill, including text on
  phase-coloured bands and chips.
- **Owning account.** Same as the how-to decks: Shawn's personal Drive for
  now, in a separate "CSOH breach decks" folder. Check each upload's owner;
  never write the owner's address into the repo.
- **Approvals.** Uploading, sharing publicly and deleting Drive files each
  need Shawn's explicit go. Commit locally; push only when he says so.

## Design

### Files (names are the builder's call; the separation is not)

- `tools/decks/breaches/<page-slug>.deck`: one outline per breach page.
- `tools/decks/breaches/published.json`: slug to `{id, published,
  outline_sha256, page_sha256}`.
- `tools/build_breach_decks.py`: parser, style limits, page checks,
  mapping, link stamping, CLI and self-test. Standard library only. It may
  import shared helpers from `build_howto_decks.py` (dash and spaced-hyphen
  checks, the mapping and stamping logic) rather than copy them.
- `tools/breach_deck_render.py`: python-pptx renderer and output verifier,
  sharing the how-to renderer's palette and fonts.
- `tools/BREACH_DECKS_README.md`, or a section in `tools/DECKS_README.md`.

### Deck shape

Every breach deck follows this order so a reader can move between decks.
Sections marked *if the page has it* are left out when the page has
nothing to put there. 18 to 36 slides, counting the generated cover and
closing.

1. **Cover** (generated): a short title (the breach name, not the page's
   arrow chain), a one-sentence promise, "Reflects the csoh.org kill chain
   as of <date>", attribution and licence.
2. **How to use this deck**: read alone or present it; every fact about
   the incident comes from the page and the sources it cites; slides
   marked Background explain a general concept and name their own source;
   the notes are a presenter's script; the full kill chain is at the page
   URL.
3. **At a glance**: stat tiles from the page's headline stats.
4. **What happened**: the page summary in about 40 words, with a timeline
   (*if the page has dates*).
5. **Who reported what, and how sure they are** (*if the page discusses
   it*): which vendor measured what, and the figures that disagree.
6. **The kill chain on one slide**: a flow diagram of every stage, with its
   phase and ATT&CK technique.
7. **One slide per stage**, two where a stage carries a concept worth
   drawing, each followed by a background slide where the stage names a
   concept the page does not explain. Each stage slide shows the phase band and number, the
   technique chips, a one-sentence headline, the stage's key facts as
   label and value rows, and one "why it matters" line.
8. **The pattern** (*if the page draws one*): what changed and what did not
   (for the pilot, machine tempo against old techniques).
9. **Defenses**: a matrix of each defense against the stages it breaks,
   then one or two slides per defense group. The matrix marks a cell only
   where the page ties that defense to that stage, and shows the gaps
   openly: a stage no defense addresses gets an empty column, and a
   defense that names no stage gets its own row marked as such. The gaps
   feed a discussion question ("the page offers no defense for stage 07;
   what would you add?"). *Designer's call*: drawing a tie the page does
   not state breaks the anti-goal on connections, and adding ties to the
   page is outside this project's scope.
10. **Hunting** (*if the page gives markers*): the markers as the page
    states them, with the page's own caveats about how fast they change.
11. **Check your own environment**: a checklist built from the page's
    defenses, phrased as questions a reader answers about their own
    estate.
12. **Discussion**: two or three questions, each followed by an answer
    slide, because a PDF reader never sees the notes.
13. **Sources**: the page's primary sources.
14. **Related kill chains** (*if the page links any*).
15. **Closing** (generated): the page URL, attribution, licence.

Every slide's footer shows the page's csoh.org address and the slide
number. Speaker notes on every slide: a presenter's script for that slide,
then the page URL.

### The pilot's content

What `vapor-panda-artex.deck` covers, slide by slide, so the shape above is
concrete. The builder writes the words.

| # | Slide | Type |
|---|---|---|
| 1 | VAPOR PANDA / ARTEX, with the promise | cover |
| 2 | How to use this deck | text |
| 3 | 200+ organizations, 14+ countries, 11 days, 9 confirmed | stat tiles |
| 4 | October 17 start, 11 days, active on October 30 (CyberScoop), console counts in early November | timeline |
| 5 | Nine confirmed against about 140: what each figure measures | comparison |
| 6 | Operator, main agent, planner and worker agents, shared graph | layered diagram |
| 7 | How much humans steer: CrowdStrike's operator against Check Point's cybercrime operators | comparison |
| 8 | Exposed consoles by method: Censys 1,465 / about 815; Check Point 1,608 / 2,557 / 1,800+ | table |
| 9 | Seven stages on one slide | flow diagram |
| 10 to 16 | Stages 01 to 07 | stage slides |
| beside them | Background: XXE and unsigned SAML assertions (stage 02), IMDSv1 against IMDSv2 (04), LAPS and resource-based constrained delegation (05), DLL side-loading (07) | background |
| 17 | 40 against 1,500+ commands an hour, drawn to scale; requests every 10 seconds | bar comparison |
| 18 | Nothing new in technique; what changed is the rate | text |
| 19 | Seven defenses against seven stages, gaps shown (no defense on the page addresses 01 or 07; markers and decoys name no stage) | matrix |
| 20 to 22 | The defenses, grouped | checklist or text |
| 23 | ARTEX markers and machine tempo, with the page's caveats | text |
| 24 | Check your own environment | checklist |
| 25 to 28 | Two discussion questions, each with an answer slide | question / answer |
| 29 | Sources | sources |
| 30 | Related: Storm-0940 / ConnectWise, ARTEX exposed secrets | text |
| 31 | Closing | closing |

The page carries no Wiz mention, so this deck needs no disclosure; the
builder confirms that against the page at build time.

### Outline format

The how-to format (`title:`, a header, `== heading` slides, prose, bullets,
`credit:`, `== include:`) extended with:

- header lines `page:` (the breach page) and `as-of:` (the date the deck
  reflects) in place of `guide:`;
- a `layout:` line choosing the slide type, with typed lines for its
  content (for example `stat: 200+ | organizations targeted | in at least
  14 countries over 11 days`), whose exact syntax is the builder's call;
- `stage: NN` on a stage slide, naming the page's stage number;
- a `notes:` block holding the presenter's script.

The format must keep slide text and notes readable in a diff, because the
fact review reads outlines as well as renders.

### The gate (`--check`, in CI)

It fails on:

- a parse error or a style limit, as for the how-to decks, plus the deck
  length range above;
- a `stage:` that names no stage on the page, or a technique on a stage
  slide that the page does not list for that stage (as its primary
  technique or a tag);
- an ATT&CK technique ID anywhere in the outline that the page does not
  carry;
- a number written in digits on a slide or in the notes that does not
  appear on the page, after normalizing thousands separators. Structural
  digits the renderer generates (slide numbers) are not in the outline and
  so never checked. Numbers written as words are left to the fact review;
- a source URL that is not a link on the page, or a related-page link to a
  breach page that does not exist;
- a mapping or stamping problem, as for the how-to decks.

A planted control for each detector goes in the self-test, as in the
how-to tool.

### Keeping decks in step with pages

- **Outline drift fails CI** (the gate above). An edit to a breach page
  that removes a number, stage or source a deck quotes turns `--check` red
  until the outline is fixed in the same change.
- **Page change since publish is reported, not failed.** The mapping
  records a hash of the page's main content at publish. `--stale` lists
  decks whose outline or page changed since, so Shawn knows to review and
  re-publish. It never fails CI, for the reason the how-to `--stale` never
  does: re-publishing needs Shawn's go.

### Publishing

The how-to steps, unchanged: build locally; upload privately; export the
PDF and inspect every page in Google's own render (fonts, overflow,
diagrams, arrowheads, chip contrast); a fresh fact review compares every
slide and every speaker note with the page and reports anything the page
does not say; Shawn reviews and approves; on his go, share publicly,
record the ID, stamp the link onto the page, run the gates and commit.

### The link on the breach page

One line, written by the stamping tool, in the page's header after the
`pm-link` source links: the PDF link and the copy link, that copying needs
a Google account, and the CC BY-NC 4.0 licence, matching the how-to deck
line's wording and attributes. Exact markup and class are the builder's
call; no inline style (CSP), and any new class goes in `style.css` with a
dark-mode rule if it needs one.

### Other registrations

- `LICENSE` clause 3 widened to breach decks and their outlines.
- `CLAUDE.md` "Generated content" table: a row for the breach deck links,
  like the how-to row.
- `.gitignore`: the breach build directory.
- `validate-html.yml`: the new `--check` step and a non-failing
  `--stale --published-only` step.
- Confirm lychee reports both deck links OK on the pilot page, as the
  how-to pilot did.

### Rollout

The pilot goes through to Shawn's approval and publication first. The
remaining pages follow in batches, each deck with its own fact review,
newest pages first. A rollout plan is written after the pilot, carrying
what the pilot learned, as the how-to rollout was.

### Background explainer slides

**Shawn decided decks carry background slides** for concepts the page
names but does not explain. For the pilot: XML external entity (XXE)
flaws, unsigned SAML assertions, LAPS, resource-based constrained
delegation, DLL side-loading, and IMDSv1 against IMDSv2.

How they stay honest (designer's proposal):

- A background slide is marked as such on the slide itself (a
  "Background" label), so a reader can tell the page's facts from general
  explanation.
- Each one names its source on the slide and carries a `source:` URL in
  the outline. Sources in order of preference: the site's own glossary
  (which defines IMDS, SAML 2.0, blast radius, guardrails, kill chain and
  EDR, but not XXE, LAPS, delegation or side-loading), MITRE ATT&CK, OWASP,
  then the vendor's or standard's own documentation. No blogs or news.
- It explains the concept in general and says nothing about the incident
  beyond what the page says. It sits next to the stage slide that names
  the concept.
- The gate exempts a background slide from the page checks (numbers,
  techniques, sources) and instead requires its `source:` line, whose URL
  must be on an allowed host the tool lists. The fact review checks each
  background slide against its named source rather than the page.
- At most one background slide per stage, and the deck length range
  still holds.
- A background slide's speaker notes may carry background too, under the
  same source. Every other slide's notes stay with the page, and the
  number check covers them.

## Left to the builder

- File names, the outline syntax for each slide type, and the generator's
  internals, within the separation above.
- The visual template for each slide type, within the look, contrast and
  readability constraints.
- Exact deck-line markup on breach pages.
- Which facts, defenses and questions each slide carries, within the deck
  shape and the anti-goals.
- Tests beyond one planted control per gate detector.
