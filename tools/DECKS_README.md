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
python3 tools/build_howto_decks.py --stale        # decks changed since publish
python3 tools/build_howto_decks.py --status       # outline and publish state
python3 tools/build_howto_decks.py --stamp        # rewrite guide links from the mapping
python3 tools/build_howto_decks.py --record SLUG PRES_ID
```

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

- The header holds exactly `title`, `guide` and `promise`.
- `== include:` splices a fragment's slides in place. A fragment has no header
  and cannot include another.
- `section:` must match an h2 or h3 on the guide.
- A code excerpt must be a contiguous run of whole lines from one `<pre>`
  block on the guide.
- Limits: 12 to 22 slides counting the generated cover and closing slides, at
  most 40 words of prose and 12 code rows per slide, no U+2013 or U+2014, and
  no spaced hyphen used as a dash.
- Code rows are visual rows: a line longer than 84 columns wraps at spaces
  inside the code box and counts as the rows it wraps to (a single word longer
  than 84 columns is split across rows). Copying a wrapped line from the slide
  gives the original line, because the wrap is display only.
- The renderer prints the guide's own language label (the code block's
  `data-lang`, uppercased as the site shows it) as a tab on each code box, so
  the how-to-follow slide's "paste BASH blocks" applies; a block the guide
  leaves unlabelled gets no tab.

## What the flags do

- `--check` parses every outline, applies the style limits, compares each
  slide's code and section with its guide, and compares the deck line on every
  `howto/*.html` page with `tools/decks/published.json`. It exits 1 on any
  finding. CI runs it after `--self-test`.
- `--stale` lists decks whose outline hash differs from the one recorded at
  publish. It never fails: re-publishing needs the owner's go, so a CI failure
  would block work nobody else can unblock.
- `--status` lists each guide with whether it has an outline and a published
  deck. A guide without a deck is never blocked.
- `--stamp` rewrites every guide page's `data-howto-deck` line from the
  mapping, and removes the line from pages with no mapping entry.
- `--record` writes today's date and the outline's current sha256 into the
  mapping, then stamps that page.

`published.json` maps each slug to `{"id", "published", "outline_sha256"}`.
The hash covers the outline with includes spliced in, so a change to a shared
fragment flags every deck that uses it.

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
