# How-to slide decks

Each guide in `howto/` can have a slide deck, written as a plain-text outline
in `tools/decks/`, built into a .pptx, published to Google Slides, and linked
from the guide's info box. Outlines, the mapping file and build output live
under `tools/`, which never ships. The only published change is the one line
of links on the guide page.

```bash
python3 tools/build_howto_decks.py --self-test    # run the built-in cases
python3 tools/build_howto_decks.py --check        # CI gate
python3 tools/build_howto_decks.py --build SLUG [SLUG ...]   # render outlines to tools/decks/build/
python3 tools/build_howto_decks.py --self-test-render        # run the renderer cases
python3 tools/build_howto_decks.py --stale [--published-only]  # decks changed since publish
python3 tools/build_howto_decks.py --status       # outline and publish state
python3 tools/build_howto_decks.py --stamp        # rewrite guide links from the mapping
python3 tools/build_howto_decks.py --record SLUG PRES_ID
```

`--build` and `--self-test-render` need python-pptx (`pip install
python-pptx`); every other mode uses the standard library only, so CI runs
`--self-test` and `--check` without it. Paths resolve from the repository
root, so the tool reads the same tree from any working directory. A mode that
finds no outlines or no guide pages exits 1 rather than report on nothing.

## Outline format

An outline is `tools/decks/<slug>.deck`, where `<slug>` is the guide's file
name without `.html`. Files starting with `_` are fragments, not decks.

```text
title: <deck title>
guide: howto/<slug>.html
promise: <one sentence>

== <slide heading>
section: <guide heading text>
Prose lines join into one paragraph; a blank line ends it.
- A bullet
```lang
code, kept verbatim
```
credit: <source and licence>

== include: _fragment.deck
```

- The header holds exactly `title`, `guide` and `promise`, each once.
- `== include:` splices a fragment's slides in place. It names the fragment
  by its bare file name (`_name.deck`, no directory part), so it can only
  read a file in `tools/decks/`. A fragment has no header and cannot include
  another.
- `section:` must match an h2 or h3 on the guide.
- A code excerpt must be a contiguous run of whole lines from one `<pre>`
  block on the guide.
- An empty code block, `section:`, `credit:` or bullet is a parse error.
- Write a slide's prose before its bullets. The renderer draws every
  paragraph above every bullet, so `--check` reports prose that follows a
  bullet rather than let it move on the slide.
- Limits: 12 to 22 slides counting the generated cover and closing slides, at
  most 40 words of prose and 12 code rows per slide, at most 12 words in a
  heading, no U+2013 or U+2014, and no spaced hyphen used as a dash.
- Code rows are visual rows: a line longer than 84 columns wraps at spaces
  inside the code box and counts as the rows it wraps to (a single word longer
  than 84 columns is split across rows). Copying a wrapped line from the slide
  gives the original line, because the wrap is display only.
- The renderer prints the guide's own language label (the code block's
  `data-lang`, uppercased as the site shows it) as a tab on each code box, so
  the how-to-follow slide's "paste BASH blocks" applies; a block the guide
  leaves unlabelled gets no tab. That includes `data-lang="text"` blocks,
  which the site also draws without a label. An excerpt from inside a heredoc
  shows the file it writes on its tab, as written, in place of the label.

The limits keep slides readable but do not guarantee that a slide fits.
`--build` is the layout check. It refuses an outline with any style or guide
finding. The renderer estimates every element's height and refuses a slide
whose content would end below the bottom limit, then reopens the saved file
and verifies the slide count and size, font sizes, footers and speaker notes,
that no shape ends below the limit, and that no slide holds an en or em dash.
A deck that fails either step has no .pptx left in `tools/decks/build/`.

## What the flags do

- `--check` parses every outline, applies the style limits, and compares each
  slide's code and section with its guide. It validates
  `tools/decks/published.json`: every key names an outline and a guide page,
  and every entry has exactly `id` (a Google Drive file id), `published` (a
  `YYYY-MM-DD` date) and `outline_sha256`. It compares every `howto/*.html`
  page with the mapping: a mapped page must hold exactly one deck line, the
  one `--stamp` writes, last in its first info box; an unmapped page must hold
  no deck markup; and no page may link a Google Slides deck anywhere else. It
  exits 1 on any finding. CI runs it after `--self-test`.
- `--stale` lists each published deck whose outline, with includes spliced
  in, no longer matches the hash recorded at publish (or is missing, or no
  longer parses), and each outline never published. `--published-only` leaves out the never-published ones. The last
  line is a `stale check:` summary. It exits 0 whether or not decks are
  stale, because re-publishing needs the owner's go and a failure would block
  work nobody else can unblock; it exits 1 only when it cannot read the
  outlines, the guide pages or the mapping. CI runs it with
  `--published-only` as a step that never fails and reports each stale deck
  as a warning and in the job summary.
- `--status` lists each guide with whether it has an outline and a published
  deck. A guide without a deck is never blocked.
- `--stamp` rewrites every guide page from the mapping: it removes every deck
  line, then writes one deck line last in the first info box of each mapped
  page. It plans every page before writing any. When a page holds deck markup
  that is not a whole line (a `<p data-howto-deck>` missing its `</p>`, or
  written inline after other markup), the info box is not in the shape it can
  edit, or the mapping has a finding, it lists every problem and writes
  nothing.
- `--record` checks that the slug has an outline that parses and the id is a
  Drive file id, writes today's date and the outline's current sha256 into the mapping,
  then stamps every page as `--stamp` does. If any of that fails it writes
  neither the mapping nor any page.

`published.json` maps each slug to `{"id", "published", "outline_sha256"}`.
The hash covers the outline with includes spliced in, so a change to a shared
fragment flags every deck that uses it.

Editing the outline of a published deck, or a fragment it includes, makes
that deck stale: the public slides and their PDF keep the old text until the
owner re-publishes it, so tell the owner the deck needs re-publishing.

## Publishing a deck

1. Build the .pptx locally.
2. Upload it privately to the "CSOH how-to decks" folder in the owning
   account's Drive, and confirm the file's owner is the expected account.
3. Export the PDF, render its pages, and inspect them for overflow, font
   substitution and broken code boxes. Fix the outline or template and repeat.
4. Fact review: compare every slide with the guide and report anything the
   guide does not say. Fix and repeat until clean.
5. The owner reviews the private deck and approves it.
6. On the owner's go, share it publicly (anyone with the link), then run
   `--record SLUG PRES_ID`, run `--check`, and commit.

Uploading, sharing publicly and deleting superseded copies each need the
owner's explicit go.

## Re-publishing gives a new ID

Updating a Drive file's metadata cannot replace a deck's contents, so a
changed deck is uploaded as a new file with a new ID. Run `--record` with the
new ID; the guide page is the stable address, and its links are rewritten from
the mapping. Delete the superseded copy only on the owner's OK. PDFs already
passed around cannot be recalled.

## Licence

Decks are CC BY-NC 4.0; the guides stay CC BY-NC-ND 4.0. The first and last
slides carry the attribution "Cloud Security Office Hours, csoh.org" and the
licence.

# Breach kill chain decks

Each breach kill chain page in `breaches/` can have a slide deck, written as a
plain-text outline in `tools/decks/breaches/`, built into a .pptx, published to
Google Slides and linked from the page's header. Outlines, the mapping file and
build output live under `tools/`, which never ships. The only published change
is one line of links on the breach page.

```bash
python3 tools/build_breach_decks.py --self-test    # run the built-in cases
python3 tools/build_breach_decks.py --check        # CI gate
python3 tools/build_breach_decks.py --build SLUG [SLUG ...]   # render outlines to tools/decks/breaches/build/
python3 tools/build_breach_decks.py --self-test-render        # run the renderer cases
python3 tools/build_breach_decks.py --stale [--published-only]  # decks changed since publish
python3 tools/build_breach_decks.py --status       # outline and publish state
python3 tools/build_breach_decks.py --stamp        # rewrite breach page links from the mapping
python3 tools/build_breach_decks.py --record SLUG PRES_ID
```

`--build` and `--self-test-render` need python-pptx (`pip install
python-pptx`); every other mode uses the standard library only, so CI runs
`--self-test` and `--check` without it. Outlines live in a subdirectory so
`build_howto_decks.py`, which does not recurse into `tools/decks/`, never reads
them.

## Breach outline format

An outline is `tools/decks/breaches/<slug>.deck`, where `<slug>` is the breach
page's file name without `.html`.

```text
title: VAPOR PANDA / ARTEX
page: breaches/<slug>.html
as-of: YYYY-MM-DD
promise: <one sentence>

== <slide heading>
layout: stage
stage: 04
phase: Credential Access
technique: T1552.005 | Cloud Instance Metadata API
fact: Queried | the cloud Instance Metadata Service
Prose lines join into one paragraph; a blank line ends it.
notes:
Speaker notes run to the next "== " line. Every slide has them.
```

- The header holds exactly `title`, `page`, `as-of` and `promise`, each once.
- A slide's first line is `layout: <name>`; `text` when absent. `stage:`,
  `stages:`, `phase:`, `source: name | url` and `credit:` are control lines,
  each at most once per slide. Typed lines are `key: field | field`, and every
  field is non-empty.
- Notes are required on every slide. There are no includes and no code fences.
- A non-background slide says nothing its page does not: every number,
  technique ID, stage and link must appear on the page. A version, IPv4
  address or CIDR (`8.4.28`, `10.0.0.0/8`) is one number, compared whole.
- A `stage` slide's techniques must be on that stage of the page, which
  counts every ATT&CK link in the stage header and every technique tag. Its
  `phase:` must name the stage's phase label. The name in a `phase-lbl`, and
  in a `phase:` line, is the text before its first colon or its first spaced
  hyphen (`" - "`), whichever comes first, with markup and emoji removed and
  every leading character that is not a letter or digit dropped:
  `🔀 Execution and Privilege Escalation: Containers` gives `Execution and
  Privilege Escalation`, `₿ Impact: Coins taken` gives `Impact`, and
  `Reconnaissance - Open Source Intelligence` gives `Reconnaissance`. A hyphen
  inside a word stays (`Cross-Site Scripting`). Some pages write a label as a
  name, a spaced hyphen and a subtitle, and the gate reads that form so those
  pages stay as written. A `phase:` line is held to the dash rule, so for such
  a label it gives the name alone or the name, a colon and the subtitle. A
  `flow` step's tactic follows the same rule.
- A chain too long for a slide per stage groups its stages by phase on
  `stage-group` slides. `stages:` lists 2 to 6 two-digit stage numbers in
  ascending order and `phase:` names the phase they share; both are required.
  A `stage-group` slide takes no `stage:` line, and no other layout takes
  `stages:`. Each `row: NN | what happened` is one listed stage, one row per
  stage in the listed order; up to three `technique:` lines give the chips;
  the prose is the "why it matters" line, and it has to be true of every
  stage in the group. The gate requires every listed stage to be on the page
  under the slide's phase label, every technique to be on one of the listed
  stages, and the rows to name exactly the listed stages. The band reads
  `<PHASE> · STAGES 03, 04 AND 05`, and each row shows its stage number on a
  tile in the phase colour. When the rows do not fit, `--build` raises a
  `LayoutError` naming the slide; split the group into two slides of the same
  phase.
- A stage the page maps to no technique (a detection or response stage)
  still gets a `stage` slide, with no `technique:` line and no chip row; in a
  `flow` step its technique is `-`, and the box shows no ID.
- A `flow` slide holds 3 to 8 steps, so a chain of more than eight stages
  takes two or more flow slides, each a run of consecutive stages.
- A `background` slide names its source on the slide, and its `source:` URL
  is on an allowed host or a subdomain of one: `csoh.org`,
  `attack.mitre.org`, `owasp.org`, `cheatsheetseries.owasp.org`,
  `learn.microsoft.com`, `docs.aws.amazon.com`, `cloud.google.com`,
  `kubernetes.io`, `www.rfc-editor.org`, `datatracker.ietf.org` and
  `docs.oasis-open.org` (`BACKGROUND_HOSTS` in the tool). Its slide text and
  notes are not held to the page, so its notes can give the URL of any second
  source its `credit:` line names.
- Limits: 18 to 36 slides counting the generated cover, how-to-use and
  closing slides, at most 40 words of prose per slide, 14 words per typed
  field, 12 in a heading and 220 in the notes, no U+2013 or U+2014, and no
  spaced hyphen used as a dash.

| Layout | Typed lines |
|---|---|
| `text`, `background`, `question`, `answer` | none; prose and bullets (`question` takes prose only, `background` needs `source:`) |
| `stats` | `stat` 2 to 4: `value \| label \| detail` |
| `stage` | `technique` 0 to 3: `id \| name`; `fact` 1 to 5: `label \| value`; needs `stage:` and `phase:` |
| `stage-group` | `technique` 0 to 3: `id \| name`; `row` 2 to 6: `NN \| what happened`, one per listed stage; needs `stages:` and `phase:` |
| `checklist` | `check` 2 to 7 |
| `links` | `link` 1 to 8: `name \| url` |
| `flow` | `step` 3 to 8: `NN \| tactic \| short title \| technique id or -` |
| `layers` | `layer` 2 to 5: `tier label \| box ...` (1 to 3 boxes) |
| `timeline` | `event` 2 to 6: `when \| what` |
| `compare` | `col` 2 or 3: `heading \| line ...` (1 to 4 lines) |
| `table` | `row` 2 to 7, 2 to 4 fields each, the first row the header |
| `bars` | `bar` 2 to 4: `number \| label` |
| `matrix` | `columns` once, 2 to 8 fields; `row` 2 to 8: `label \| mark ...` |

## Breach deck gate and publishing

- `--check` parses every outline, applies the style limits and compares each
  slide with its breach page. It validates `tools/decks/breaches/published.json`:
  every key names an outline and a breach page, and every entry has exactly
  `id` (a Google Drive file id), `outline_sha256`, `page_sha256` and
  `published` (a `YYYY-MM-DD` date). It compares every `breaches/*.html` page
  with the mapping: a mapped page must hold exactly one deck line
  (`data-breach-deck`), the one `--stamp` writes, right after the last
  `pm-link` line in `inc-header`; an unmapped page must hold no deck markup;
  and no page may link a Google Slides deck anywhere else. It exits 1 on any
  finding, and when it finds no outlines it says nothing was checked and exits 1.
- A deck is stale when its outline or its page changed since `--record`. The
  page hash covers the text of the page's `<main>` with deck lines and the
  prev/next pager removed, so stamping a deck line, glossary cross-linking,
  nav or footer edits, and a new chain changing its neighbours' pagers do not
  flag a deck; a changed sentence does. `--stale` prints one line per
  reason: the outline changed (the public deck needs re-publishing) or the
  page changed (review the deck against the page). It exits 0 whether or not
  decks are stale, and CI reports each as a warning.
- `--build SLUG` writes `tools/decks/breaches/build/<slug>.pptx`. It first
  removes that deck's old build, refuses an outline with any finding
  `--check` reports for it, then reopens the saved file and verifies it: the
  slide count and size, shape kinds, font sizes, the contrast of every run,
  footers, speaker notes, type labels and background credits, no autofit, no
  en or em dash, and no shape below the bottom limit or off the side of the
  slide. A deck that fails any step leaves no
  .pptx. A `LayoutError` names the slide (`<slug>.deck:<line>`) whose content
  would end below the room it has; trim that slide's text. It also names a
  stat value too wide to fit its tile on one line, measured glyph by glyph in
  the wider of Space Grotesk Bold and Arial Bold with a margin, since Google
  Slides wraps whatever does not fit; shorten the value and move the rest
  into its label or detail, keeping any hedge ("~$2.85B" becomes "$2.85B"
  with "approximately" in the label or detail). It names any word (text
  with no space in it) wider than the box it sits in, because Google Slides
  breaks such a word mid-word rather than at a hyphen: move a long name,
  address or hash to a wider box such as the caption, or say it in words.
  A table column is first widened to hold its widest word. And it names a
  timeline label that wraps past three lines (the when) or eight (the
  what); timeline lines are counted from measured glyph widths, so a label
  that wraps in Google Slides has its lines reserved.
- `--stamp` removes every deck line and writes one after the last `pm-link`
  line of each mapped page, planning every page before writing any.
  `--record` refuses an outline with any finding `--check` reports, and
  otherwise writes the id, both hashes and today's date, then stamps. A
  refused record writes neither the mapping nor any page.
- The glossary cross-linker (`tools/crosslink_pages.py`) never links inside a
  deck line: a `<p>` carrying `data-breach-deck` or `data-howto-deck` is one
  of its skip zones, because each tool's `--check` requires a deck line to be
  exactly the text its `--stamp` writes.

Publishing follows the how-to steps: build, upload privately, export and
inspect the PDF, fact-review against the page, get the owner's approval, then
on the owner's go share it publicly, run `--record SLUG PRES_ID`, run
`--check` and commit. Uploading, sharing publicly and deleting superseded
copies each need the owner's explicit go. A changed deck is uploaded as a new
file with a new ID, and the breach page's link is rewritten from the mapping.

Breach decks are CC BY-NC 4.0 and the pages stay CC BY-NC-ND 4.0. The first
and last slides carry "Cloud Security Office Hours, csoh.org" and the licence.

## The deck list page

`breach-kill-chain-decks.html` lists every published breach deck, one card
each, between its `<!--breach-decks:start-->` and `<!--breach-decks:end-->`
markers. Above the cards sits a card finder (`tools/card_finder.py`,
`card-finder.js`, shared with `breach-timeline.html`): a search field and an
index of the decks grouped by incident year, each entry linking its card. The
field ships hidden and the script reveals it and filters the index and the
cards together, so without scripts the index still works and no dead search
box shows. `tools/sync_breach_deck_index.py` renders all of it from
`published.json`, each deck's outline (title, promise, as-of date, and the
slide count with the three generated slides added) and the order, incident
year and platform tag of the deck's card on `breach-timeline.html`. Run it
after every `--record`, in the same commit:

```bash
python3 tools/sync_breach_deck_index.py              # rewrite the list
python3 tools/sync_breach_deck_index.py --check      # CI gate
python3 tools/sync_breach_deck_index.py --self-test  # planted controls
```

`--check` fails when the list is out of step, and when a mapped deck has no
outline, no breach page or no card on the timeline. The generated text sits in
headings, links and `no-glossary` spans, so `crosslink_pages.py` never edits
it; the self-test asserts that against the real glossary.

# Topic decks

Each teaching page carded on `topics.html` can have a slide deck, written as a
plain-text outline in `tools/decks/topics/`, built into a .pptx, published to
Google Slides and linked from one line under the page's `page-meta` line. The
page set is every root-level card on `topics.html` less `EXCLUDED` in
`tools/build_topic_decks.py` (`glossary.html`, `faq.html` and
`vendor-landscape.html`), so a new topic card shows up in `--status` without a
code change.

The topic tool is the breach tool's machinery run with a different
`DeckKind`: the parser, style limits, mapping, stamping, staleness and build
loop live once in `tools/build_breach_decks.py`, and every function that reads
a kind-specific value takes a `kind`. `tools/topic_deck_render.py` draws every
layout but `figure` through `tools/breach_deck_render.py`, and adds the
`figure` layout, the cover art and the topic wording of the generated slides.

```bash
python3 tools/build_topic_decks.py --self-test    # run the built-in cases
python3 tools/build_topic_decks.py --check        # CI gate
python3 tools/build_topic_decks.py --extract SLUG [--sections ID,ID]   # the page as text, for drafting and review
python3 tools/build_topic_decks.py --build SLUG [SLUG ...]   # render outlines to tools/decks/topics/build/
python3 tools/build_topic_decks.py --self-test-render        # run the renderer cases
python3 tools/build_topic_decks.py --stale [--published-only]  # decks whose outline or cited sections changed
python3 tools/build_topic_decks.py --status       # outline and publish state, and the pages with no deck by design
python3 tools/build_topic_decks.py --stamp        # rewrite topic page deck lines from the mapping
python3 tools/build_topic_decks.py --record SLUG PRES_ID
```

`--self-test` and `--check` use the standard library only, so CI runs them
without python-pptx, Pillow or Playwright. `--build` needs python-pptx and
Pillow, plus Playwright with Chromium to render the page's diagrams;
`--self-test-render` needs the same. `--check` exits 1 when there are no
outlines.

## Reading a page: `--extract`

`--extract SLUG` prints the page's `<main>` as text: the page title as
`# <h1> {#top}`, then each h2 as `## <text> {#id}` and each h3 as `### <text>`,
paragraphs as single lines, list items as `- ` lines, table rows as
`| a | b |`, a link's URL in parentheses after its text except for glossary
links, and each diagram where it sits as
`[figure #id] <title>: <description> (caption: <caption>)`. The table of
contents, the page finder, the `page-meta` line and the deck line are left
out, and so are the labels inside an SVG. With `--sections a,b` it prints the
heading list and then only those sections. Drafters and reviewers read this,
never the page's HTML or images.

## Topic outline format

What differs from the breach format:

```text
title: <deck title>
page: <slug>.html
as-of: YYYY-MM-DD
promise: <one sentence>

== <slide heading>
layout: figure
section: supply-chain
figure: cluster-supply-chain
At most 25 words of prose on a figure slide.
notes:
Speaker notes, on every slide.
```

- `page:` names a page from the topic page set.
- Every slide carries `section: <id>` or `section: <id> | <id>`: one or two
  ids, so the gate and the review stay scoped to the part of the page the
  slide draws on. Three or more is a parse error naming the line. An id is
  the `id` of the `<section>` that wraps an h2 in `<main>`. An h2 with no such
  section gets a slug of its text (`Where next` is `where-next`). The text
  above the first h2 is section `top`. The ids are the `{#id}` marks in the
  extract.
- Control lines are `layout`, `section`, `figure`, `source` and `credit`;
  there is no `stage`, `stages` or `phase`.
- Layouts: `text`, `stats`, `checklist`, `list`, `links`, `layers`,
  `timeline`, `compare`, `table`, `bars`, `matrix`, `question`, `answer` and
  `figure`, with the breach layouts' typed lines. There is no `stage`,
  `stage-group`, `flow` or `background`.
- A `list` slide takes 2 to 7 `item:` lines and draws each with a dot where a
  `checklist` draws a tick box, so pitfalls and anti-patterns do not read as
  things to do. Like `check:` lines, items are typed fields, not prose.
- A `figure` slide has one `figure: <id>` line naming one of the page's
  diagrams, which must sit in a section the slide cites; its id is the
  `[figure #id]` in the extract (the figure's own `id`, or its SVG
  `<title>`'s id where the figure has none). The drafter never types the
  caption: the builder places the page's `<figcaption>` under the picture.
  Each figure appears at most once per deck, and a deck whose page has a
  diagram has at least one `figure` slide.
- Every number, technique ID and link in a slide's text and notes appears in
  the sections it cites. The title and promise, which the cover shows, are
  held to the whole page.
- On a page that carries "(disclosure: the site's author works at Wiz)", the
  first slide that shows Wiz carries the disclosure on the slide, where the
  audience sees it. The notes never count for this: they are not shown, and
  the PDF leaves them out. A title or promise that names Wiz carries it in the
  title or the promise. Separately, notes that name Wiz before any slide shows
  it carry the disclosure too, for the presenter who reads them out.
- Limits: 15 to 30 slides counting the generated cover, how-to-use and
  closing slides; at most 40 words of prose per slide (25 on a `figure`
  slide), 14 per typed field, 12 in a heading and 300 in the notes; no U+2013
  or U+2014 and no spaced hyphen used as a dash.

## Topic gate, staleness and the deck line

- `--check` reports every finding above, naming the outline line, and
  validates `tools/decks/topics/published.json`: every entry has exactly
  `id`, `outline_sha256`, `page_sha256`, `cover_sha256` (the cover's art),
  `sections` (each cited section id mapped to its hash) and `published`.
- A section's hash covers its extract text, link URLs included, and the SVG
  markup of its figures, so a redrawn diagram changes it while the
  `page-meta` date, the deck line, the nav and a glossary link do not.
  `--stale` names the cited sections that changed or are no longer on the
  page; a change to a section no slide cites leaves the deck current, so a
  re-review reads only the named sections. The cover's art sits outside
  `<main>`, so it has its own hash: a redrawn hero, or on a page without one
  a changed tile image or alt text, makes the deck stale too.
- The deck line is `<p class="page-meta" data-topic-deck>` with the breach
  deck line's link text, alone on its line right after the page's
  `page-meta` line at the top of `<main>`. Under it, also alone on its line,
  `--stamp` writes the preview: `<details class="deck-preview"
  data-topic-deck>` holding the deck's `/embed` viewer in a `.deck-frame`.
  It starts closed, and a closed panel does not render its lazy iframe, so
  nothing loads from Google until a reader opens it. `--check` wants exactly
  those two lines, in that order, for the mapping's id, and any other Google
  Slides link or embed on the page is a finding. `--stamp` and `--record`
  write both and plan every page before writing any, as the breach tool
  does. The glossary cross-linker skips both lines.
- `topics.html` shows the same deck on the topic's card. A card with a deck
  is a `<div class="resource-card resource-card--topic-deck">` holding the
  card's link (its picture, h3 and p unchanged), then two lines carrying
  `data-topic-hub-deck`: a `.deck-actions` strip with the PDF and editable
  copy links, and a closed `.deck-preview`. A card whose topic has no deck
  stays a plain `<a class="card-link">` card. `--stamp` and `--record` write
  every card from the mapping, in the same plan as the topic pages, and
  `--check` fails a card that disagrees with it or any other Google Slides
  link on the page. The cross-linker skips both lines here too.

## Topic build

`--build SLUG` writes `tools/decks/topics/build/<slug>.pptx`, refusing an
outline with any `--check` finding, and verifies the saved file as the breach
build does, with pictures allowed. Diagrams render with Playwright: the page
loads from the working tree through a routed origin with `integrity`
attributes stripped, a light colour scheme and device scale 2, and each
figure's `<svg>` is screenshotted. The render stops when `style.css` did not
load, and a picture of one colour is refused as blank. The hero illustration,
which article pages hide, is shown for its screenshot on a panel the colour of
the cover. PNGs are cached in `tools/decks/topics/build/figures/<slug>/`
under the hash of their SVG markup, so an unchanged figure is never rendered
again. The hero's key also covers `style.css` and the CSS that reveals it,
because the stylesheet draws the hero as well. Delete that directory to render
everything afresh.

- A `figure` slide shows its heading, its prose, then the picture on a white
  panel, scaled to fit with its aspect ratio kept and never past 1.5 image
  pixels per point of its width, with the page's caption under it. When the
  room left is too small, a `LayoutError` names the slide; shorten the
  heading or the prose.
- The cover shows the page's hero illustration beside the title, or, on a
  page without one, the image on its `topics.html` card.
- Every picture carries alt text: the SVG's `<title>` for a figure, the
  hero's label, or the card image's `alt`.
- Verification also checks that the cover carries the art, each `figure`
  slide its one picture and the page's caption, and no other slide a
  picture, and that every picture has the expected alt text, its image's
  aspect ratio, enough pixels, no crop and more than one colour.

Publishing follows the breach steps, to the "CSOH topic decks" Drive folder:
build, upload privately, check every picture in Google's render, fact-review
the slides against the sections they cite, get the owner's approval, then on
the owner's go share it publicly, run `--record SLUG PRES_ID`, run `--check`
and commit. Topic decks are CC BY-NC 4.0 and the pages stay CC BY-NC-ND 4.0.
