# Editorial standards

What "correct" means for prose on csoh.org, so that a review can reach the same
verdict twice.

These rules were already being applied - they lived in `code-of-conduct.html`,
`README.md`, `CLAUDE.md`, and in review habit. Scattered like that, a weekly
consistency review has nothing stable to check against, and "consistent" ends up
meaning whatever the reviewer inferred that week. This file is the source of
truth. `tools/check_docs_consistency.py` enforces the mechanical half; the
weekly review in `.github/workflows/weekly-docs-review.yml` judges the rest.

Scope is every word we ship: page prose, resource-card descriptions and
tooltips, glossary definitions, meeting recaps, breach reconstructions, JSON-LD
values a human wrote, `README.md` and the other root Markdown, and the docstrings
and comments in `tools/`.

## 1. Audience

Members run from **first-week learner to twenty-year practitioner**
(`code-of-conduct.html`). Both ends read the same page.

- Lead with the plain-language answer, then add the depth.
- Expand an acronym on first use per page, then link it to the glossary.
- Do not assume a reader has AWS, Kubernetes, or SOC experience unless the page
  says up front that it assumes it.
- Do not pad for beginners either. A twenty-year practitioner should not have to
  scroll past three paragraphs of preamble to reach the technique.

A page that only serves one end of that range is a finding, in either direction.

## 2. Accuracy

- Every factual claim is checkable against a primary source: a vendor's own
  documentation, a CVE record, a post-mortem, a paper.
- Prefer the primary source over coverage of it. Link the advisory, not the news
  article about the advisory.
- Product, company, and service names are spelled the way the vendor spells them
  (`GreyNoise`, not `GrayNoise`).
- If a company was acquired or a product renamed, the page uses the current name
  and the link resolves to the current owner.
- Dates, versions, and exam codes are the things that rot fastest. Anything of
  the form "as of", "currently", "the latest", or a bare year is a claim with an
  expiry date, and the review re-checks it.
- Credit your sources (`code-of-conduct.html`). A technique, tool, or diagram
  that came from someone else names them and links to them.

Where a claim cannot be verified, it gets softened or cut - not shipped with
confidence it has not earned.

## 3. Neutrality

CSOH is vendor-neutral, free, and volunteer-run. That is the headline promise on
`index.html` and in `README.md`, and prose is what keeps or breaks it.

- **No sales pitch.** Describe what a tool does and what it is good at. No
  marketing superlatives, no "leading" or "best-in-class".
- **No putting down competitors** (`code-of-conduct.html`). Comparisons state
  tradeoffs, not winners. `cloud-comparison.html` and `vendor-landscape.html`
  carry no rankings by design.
- **Disclose affiliation.** Shawn works at Wiz. Any page touching Wiz or its
  competitors says so. This is already done on `vendor-landscape.html`; it is a
  standard, not a one-off.
- **No sponsored content**, on the site or in the mailing list.
- **Apolitical.** CSOH is a technical community. Party politics, elections, and
  culture-war material are off-topic regardless of the author's view, including
  when they arrive indirectly through an auto-surfaced session recap. A session
  recap that wandered off-topic does not get echoed onto a technical reference
  page.
- **Attacker technique, not attacker capability.** Public CVEs, post-mortems,
  CTF write-ups, lab environments, ATT&CK mappings: in scope. Working exploits
  against systems the reader does not own, weaponized payloads, or real leaked
  credentials: never (`code-of-conduct.html`).

## 4. Temperature: does this match what members are actually discussing

The weekly Friday session is the signal. `meetings/` holds the recap archive, and
the recent ones say what the community currently cares about.

- A page that presents a superseded concern as current is stale, even when every
  sentence in it is still technically true.
- A topic raised repeatedly in recent sessions with thin or no coverage on the
  site is a gap worth naming.
- "Emerging", "new", and "increasingly" age badly. If the recaps show a topic has
  been routine for a year, the framing is wrong.

This is a judgment call and it is reported for a human, never auto-applied.

## 5. Mechanics

- **No em-dashes.** Use a spaced hyphen ( - ), a colon, or parentheses. This is
  consistent across the site and the review enforces it.
- **No hand-typed counts.** Every number describing site inventory lives inside a
  `<!--count:name-->N<!--/count-->` marker owned by `tools/sync_counts.py`. A bare
  "310+ glossary terms" in prose will drift the day content lands. See
  `CLAUDE.md`.
- **Dates agree with themselves.** A page's visible "Last updated" and its JSON-LD
  `dateModified` are the same date. `datePublished` is when the write-up was
  authored, not when the incident happened, and is never a January 1 placeholder.
- **One voice.** Second person for instructions ("you"), present tense for how
  things work, past tense for what happened in an incident.
- **Links say where they go.** No "click here". Link text names the destination.

## 6. External references

- The link resolves, and resolves to the thing the text promises.
- It points at the current edition. A card linking to a 2021 threat report when
  the 2026 one exists is stale even though the URL still works.
- Prefer a stable landing page over a dated artifact when the publisher issues
  the report annually.
- Official sources first: vendor documentation, GitHub orgs, `.gov` / `.edu`.
- No affiliate links, ever.

## 7. Deletion

Nothing in the automated pipeline deletes anything. `check_docs_consistency.py`
only rewrites values in place, and the weekly review runs with no edit tool at
all.

Removing a page, a resource card, a glossary entry, or a section is a human
decision every time. Candidates are collected in the weekly tracking issue with
the reason, and stay there until a human acts. An entry that looks dead is often
deliberate: `check_glossary_coverage.py` has an `UNREACHABLE` list of headwords
that intentionally never auto-link, and dropping one because it looked orphaned
would be wrong.

## 8. What the weekly review may change on its own

Only what `tools/check_docs_consistency.py` decides mechanically, where the
correct value is derivable from something already in the repo:

- a visible date resynced to the page's own JSON-LD `dateModified`
- a count resynced to the real number of cards or files
- an em-dash replaced with a spaced hyphen

Everything else - accuracy, neutrality, temperature, reading level, external
reference currency, and every deletion - is reported to the tracking issue and
waits for you.
