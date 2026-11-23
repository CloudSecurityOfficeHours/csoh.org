# Search the breach kill chains by industry

## Intent

A reader who works in one industry (healthcare, finance, crypto, retail and
so on) wants the kill chains that hit organizations like theirs. They should
get them from the search box that is already on `breach-timeline.html` and
`breach-kill-chain-decks.html`, by typing the industry or by pressing a
button for it.

## Goals

- Typing an industry name, or a common synonym of one ("bank", "hospital",
  "casino"), narrows both pages to the chains that hit that industry.
- A row of industry buttons under each search box fills the box with one
  click, so readers don't have to guess the vocabulary.
- Every card shows which industries it was tagged with, so a match is never
  a mystery.
- A chain is tagged with **every industry its breach page names as hit**,
  not only the headline company's. Snowflake gets Retail (Ticketmaster),
  Finance (Santander) and Telecom (AT&T).

## Non-goals

- No new pages, no industry landing pages, no change to the site-wide search
  (`search.html`) or to the year-in-review and lessons pages.
- No change to the order or grouping of the index (still by incident year).

## Anti-goals

- A tag the breach page does not support. Every tag must trace to a sentence
  on that chain's page. If no page names a law firm, there is no Legal
  button.
- Buttons for industries no card carries (a button that returns nothing).
- Hidden search keywords. A card must show the words that made it match.
- Anything that works only with JavaScript and is visible without it. The
  buttons ship inside the search bar, which already ships hidden until
  `card-finder.js` reveals it.

## What "hit" means

An industry is tagged when the chain's breach page says an organization in
it was compromised, lost data, money or access, or took services offline
because of the attack. Being targeted, or being "potentially affected",
does not count. Package and workflow worms (npm, PyPI, GitHub Actions) get
Technology where the page names software companies or developers as
victims. A chain whose page names no victim industry (XZ Utils was caught
before it reached anyone) gets no tag.

## Approaches considered

- **Visible tags plus industry buttons (chosen by Shawn).** A labelled
  "Industries hit" line on each card, buttons under the search box, and
  synonyms handled by the search script. Readers see why a card matched and
  can browse the vocabulary.
- **Visible tags only.** Same tags and synonyms, no buttons. Less UI, but
  readers must guess the words.
- **Hidden keywords.** Cards unchanged, search reads invisible keywords.
  Rejected: a match with nothing on the card to explain it looks broken.

## Design

### The vocabulary

One module, `tools/breach_industries.py`, holds the fixed list: each
industry's label and its single-word synonyms. Starting list: Crypto,
Education, Energy, Finance, Government, Healthcare, Hospitality, Legal,
Manufacturing, Media, Retail, Technology, Telecom, Transportation. Tagging
may add an industry only when a page names one outside the list; each new
one comes with synonyms. Labels a page never needs simply never get a
button.

### Timeline cards (hand-written, the single source)

Each `<li class="breach-card">` on `breach-timeline.html` gains one line
between the summary and the "Read kill chain" link:

```
2024  CRITICAL  [Healthcare Infrastructure]
Change Healthcare / ALPHV - Citrix Without MFA → ...
A summary of the breach...
Industries hit: Finance, Healthcare
Read kill chain →
```

Industries are listed alphabetically and separated by commas, which a
screen reader reads as a list (a middle dot is read aloud as "dot").

The "Industries hit:" label is left out of the search (`data-finder-skip`),
so typing "industries" doesn't match every card. A chain with no tag has no
line.

### Deck cards (generated)

`tools/sync_breach_deck_index.py` already copies each deck's year and
platform from its timeline card. It copies the industries the same way and
renders the same labelled line on each deck card. Editing a timeline card
and re-running the tool updates both pages.

### Buttons and synonyms (generated, shared)

`tools/card_finder.py` renders, inside the search bar, a button per industry
that at least one card on that page carries, in alphabetical order, reusing
the site's existing `.filter-btn` style. It also renders the synonym map
onto the finder box as a data attribute. Both sync tools pass these in, so
the two pages can't drift.

`card-finder.js` stays page-agnostic:

- A button sets the search box to its industry and filters. Pressing the
  active button clears the search. The button whose industry matches the
  box is marked pressed (`aria-pressed`), so typing "finance" lights the
  Finance button.
- A typed word also matches a card when it is a synonym of an industry the
  card carries ("bank" finds Finance cards). Every word must still match,
  in any order, as now.

The placeholders become "Search by company, actor, technique or industry"
(timeline) and "Search by company, actor, platform or industry" (decks).

### Checks

- `sync_breach_timeline_index.py --check` fails on an industry not in the
  vocabulary, a repeated one, or a malformed line, and when the buttons are
  out of step with the cards.
- `sync_breach_deck_index.py --check` fails when deck cards or buttons are
  out of step with the timeline.
- Each tool's `--self-test` plants an unknown industry, a card with no line,
  and a button for an industry no card carries, and asserts each is caught.
- Both generators run twice to prove idempotence.

### Tagging the 60 chains

Read each breach page and record, per industry, the sentence that supports
it. The evidence table goes in the implementation plan's folder for Shawn
to check. Each quoted sentence is verified mechanically as text that
actually appears on the page, before any tag goes on a card.

### Verification

On localhost under production's CSP, scripts on and off: the buttons are
hidden without scripts; each button narrows both pages to the right count;
synonyms work; pressed state follows typing; Escape and "Clear the search"
reset the buttons. Contrast of the new line and the pressed button in light
and dark mode, each page loaded fresh. Then the usual gates
(`validate-html.yml` tools, inline-style checks, `update_sri.py`).

## Left to the builder

- The exact synonym list per industry, kept to single words that are not
  ambiguous ("exchange" is out: it is also Microsoft Exchange).
- The attribute format for the synonym map.
- Styling details of the "Industries hit" line, matched to each page's card
  styles and checked by composition in a full-page screenshot.
