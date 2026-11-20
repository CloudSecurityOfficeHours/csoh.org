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
