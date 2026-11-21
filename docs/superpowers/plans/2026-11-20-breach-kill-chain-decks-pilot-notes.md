# Breach kill chain decks: what the pilot settled, and what the rollout inherits

Companion to `docs/superpowers/plans/2026-11-20-breach-kill-chain-decks.md`. The pilot
(`tools/decks/breaches/vapor-panda-artex.deck`) was published on 2026-11-20. The rollout
plan for the other breach pages starts from this list.

## What the pilot settled

- **Google Slides conversion.** Rectangles, rounded rectangles, ovals, chevrons, block
  arrows and text boxes convert cleanly, and so do the fonts (Space Grotesk, Source Sans 3,
  Source Code Pro). Two behaviours needed renderer changes:
  - Google ignores a text frame's no-wrap setting, so a label must be wide enough on its
    own. Type-label pills are sized from measured glyph widths of the wider of Space
    Grotesk Bold and Arial Bold, plus a 10% margin.
  - Google draws every hyperlinked run in its own link blue with an underline, whatever
    colour the .pptx sets. Hyperlink only text that should look like a link.
- **Inspecting Google's render.** `read_slide_page_thumbnail` (LARGE) returns a short-lived
  image URL that downloads without auth; contact sheets of those images are the render
  check. The PowerPoint connector timed out for every implementer; the local preview was an
  HTML rebuild of each slide with the repo's fonts.
- **Public links.** Signed out, `/export/pdf` returns `200 application/pdf` (one page per
  slide) and `/copy` redirects to Google sign-in. lychee reports both as OK.
- **Re-uploading gives a new file id.** The superseded pilot upload is
  `1Aty73b-UmRXItQ-dC51cEAYf56ZvseqmrfUzMNpwP3c`, kept in the "CSOH breach decks" folder until
  the owner approves deleting it.
- **Fact review earns its cost.** The first outline passed every gate and still had five
  Important findings (dropped hedges, an attribution gap, a diagram implying a connection the
  page does not describe). Every deck needs its own fresh fact review against its page.

## Settle before the second outline

- **Long chains.** Four breach pages have 9 to 28 stages. The format allows several `flow`
  slides; decide how they read (by phase group, or in runs of eight) and say so in the
  rollout plan.
- **Page labels the phase gate cannot mirror.** `breaches/mitnick-novell.html` writes its
  phase labels with spaced hyphens; reword them to the site's `Phase: subtitle` form before
  its deck. `phase_name` keeps a leading "₿" on `breaches/event-stream-npm.html`'s Impact
  label; strip every leading symbol, not only emoji.
- **Shared code with the how-to tool.** Move the render cases next to the renderer, and
  extract the publishing helpers both deck tools copy (mapping, stamping, stale, record,
  `link_findings`) when a change next touches both.
- **Crosslinker skip zone.** `tools/crosslink_pages.py` does not skip a `p` carrying
  `data-breach-deck` or `data-howto-deck`; a future glossary term matching the deck line's
  words would be linked inside it and trip `link_findings`.

## Tooling minors, none blocking

- Bar values: `BAR_NUMBER_RE` accepts shapes like `1,,5`; a `+` value is drawn at its floor
  with no caption saying so; a two-bar slide is sparse.
- Parser: `A |x` (pipe without spaces) is one field with no finding; an unknown lowercase
  key with no space and no pipe becomes prose; deck-level findings hard-code `<slug>.deck`;
  CRLF outlines hash differently from LF.
- Gate: `HREF_RE` reads double-quoted hrefs only; `1.40` and `1.4` do not compare equal;
  the `phase:` text and a non-background `source:` name are not number-checked.
- Publishing: `--status` does not show stamp state; `--stale` warns once per reason while
  its summary counts decks; a dead newline guard in stamp insertion; the "Slides linked
  elsewhere" finding hides behind a loose-markup finding.
- Renderer and tests: an unnamed `+0.1` in the flow height; the diagram overflow test omits
  compare, timeline, bars and matrix; the layers test does not assert the absence of other
  connectors; the R12 hue check omits Initial Access against Stealth; the label-width test
  repeats the safety factor and uses a fixed slide index; a comment states as fact that
  Google substitutes Arial Bold.
