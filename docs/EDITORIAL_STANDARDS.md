# Editorial standards

What "correct" means for prose on csoh.org, so that a review can reach the same
verdict twice.

A weekly consistency review needs one stable standard to check against, or
"consistent" ends up meaning whatever the reviewer inferred that week. This file
is the source of truth. `tools/check_docs_consistency.py` enforces the mechanical half; the
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

Where a claim cannot be verified, soften it or cut it. A claim ships only
with confidence it has earned.

## 3. Neutrality

CSOH is free, independent, and volunteer-run. Say that once where it matters
(the Code of Conduct, the About ethos, a cert that is genuinely cross-vendor).
Do not stamp "vendor-neutral" on every meta description, footer, page-meta
line, or guide intro. Readers already get it from the content.

- **No sales pitch.** Describe what a tool does and what it is good at. No
  marketing superlatives, no "leading" or "best-in-class".
- **No putting down competitors** (`code-of-conduct.html`). Comparisons state
  tradeoffs, not winners. `cloud-security-comparison.html` and
  `vendor-landscape.html` carry no rankings by design.
- **Disclose affiliation.** Shawn works at Wiz. Any page touching Wiz or its
  competitors says so. This is already done on `vendor-landscape.html`; it is a
  standard, not a one-off. Two exceptions need no disclosure:
  `chat-resources.html`, a dated record of links members shared in the
  session chat, credited to whoever shared them; and the resource directory
  (`resources.html` and every `resources-<category>.html` page), which lists
  third-party tools, courses and links one card each, saying what each is
  without comparing or ranking them. A Wiz card there is one entry among
  many, not prose the site wrote weighing Wiz against its competitors.
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

- **No em-dashes, en-dashes, or spaced hyphens used as dashes.** An em-dash
  (U+2014), an en-dash (U+2013), and their HTML entities do not belong in
  prose. A spaced hyphen (` - `) used in their place is a dash substitute and
  an AI tell, so it is not the replacement. Rewrite the sentence with a comma,
  a period, a colon, or parentheses. `tools/check_docs_consistency.py` reports
  em-dashes for that rewrite and does not insert a spaced hyphen. It does not
  flag every ` - `, because the same characters appear in commands, flags, and
  titles. En-dashes already in numeric ranges are the same ban; rewrite them
  when you touch the sentence.
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

An em-dash is not on that list. The script reports it. The rewrite (a comma,
a period, a colon, or parentheses) is a human edit. A spaced hyphen is not a
mechanical substitute.

Everything else (accuracy, neutrality, temperature, reading level, voice,
external reference currency, and every deletion) is reported to the tracking
issue and waits for you.

## 9. Voice: prose that reads as generated

Readers recognise machine-written prose by its structure more than its
vocabulary. The patterns below are what give a page away here. They are a style
problem, not an accuracy one, and fixing them must not change what any sentence
claims.

### Patterns to rewrite

- **Dash asides.** An aside set off by a dash in the middle or at the end of a
  sentence interrupts the flow. Give it its own sentence, make it a clause, or
  use "rather than", "which means", or a colon before a list.
- **Reversals.** "X, not Y", "It is not X. It is Y.", "not just X but Y". State
  the claim directly. Keep the contrast only where the reader would otherwise
  assume X.
- **A list, then its summary.** A list followed by a sentence that merely
  summarizes it, such as "Public buckets, open security groups, weak password
  policies. These are the day-to-day failure modes." Lead with the claim and
  follow it with the list.
- **Stacked fragments.** Three or more verbless sentences in a row: "CloudTrail
  feeding a SIEM. Provider-native services like GuardDuty. A response
  runbook." Write one sentence that carries the list. Cards and tiles are terse
  by design and are exempt.
- **Question strings.** A definition written as rhetorical questions: "Who can
  assume what role? Which permissions are unused?" Write the statement the
  questions stand for. FAQ headings are questions by design and are exempt.
- **Restating tag lines.** A short closer that repeats the sentence before it:
  "The provider's job, full stop." Fold the point into the sentence.
- **Tacked-on slogans.** A triad that restates the list before it: "VPCs,
  private endpoints, traffic monitoring: segment, restrict, observe."
- **Reveal labels.** "The catch:", "The honest lesson is", "Here's why", "This is
  where", "The bottom line". Say the thing.
- **Empty intensifiers.** "Actually", "genuinely", "truly", "single most",
  "highest-leverage". Cut one only when removing it changes nothing. In "the
  breaches that actually happen" it contrasts real incidents with hypothetical
  ones, so it stays.
- **Bold-lead bullets.** `<li><strong>Label:</strong> ...` is right when the
  label is a term being defined or a step being named. Prose cut into bullets
  with a bold phrase on each is not a list. Write the paragraph.

### The rewrite must not change the claim

A rewrite can keep every name, number, and link identical and still change what
a sentence says. Check each changed sentence for all of these:

- **Hedges and quantifiers stay as written.** "Most", "almost", "primarily",
  "often", "usually". "Primarily" is not "mostly".
- **Trend words stay.** "Increasingly" does not become "now". Whether a trend
  claim has gone stale is a temperature question (§4), not a style fix.
- **Intensity stays.** "Explodes" is not "grows". "Wildly different" is not
  "very different".
- **Scope stays.** An open example list stays open ("like", "such as",
  "including"). A complete enumeration stays complete ("which means", or a
  colon). Adding "and" before the last item of an example list closes it.
- **No new order.** Joining parallel items with "starts with", "on top of that",
  or "then" asserts a sequence or a dependency the original did not.
- **No new claim in place of a flourish.** "The acronym soup is real" cannot
  become "Most tool categories go by acronyms". The second is a countable claim
  nobody checked.
- **A flourish that carries a claim stays.** "Forget 'advanced persistent
  threats' for a minute" tells the reader that framing is misplaced. Deleting it
  deletes that.
- **Facts are out of scope.** A style pass that finds an inaccuracy reports it,
  and the fix goes in its own change, so a reviewer can tell a correction from a
  rewording.

### Doing a pass

- Edit only sentences that show a pattern above. Leave plain sentences alone,
  even ones you would have written differently.
- Skip generated and recorded text. `news.html` is regenerated weekly. Meeting
  recaps come from the session summaries through `tools/add_meeting.py`.
  `chat-resources.html` is a dated record of what members shared. Text a tool
  writes is changed in the tool.
- Text that appears twice changes in both places. A FAQ answer is duplicated in
  the page's `FAQPage` JSON-LD: run `python3 tools/check_faq_jsonld_parity.py
  --fix`, then `--check`. A pull quote repeats a sentence from its section.
- Rebuild `search-index.json` with `python3 tools/build_search_index.py`, twice.
  The second run must change nothing.
- For a pass across many pages, `tools/deai_segments.py` extracts the flagged
  blocks, lets a rewriter return replacements without editing pages, and
  applies only those that pass the mechanical check below. See
  [tools/DEAI_SEGMENTS_README.md](../tools/DEAI_SEGMENTS_README.md).

### Checking a pass

Both checks are required.

1. **Mechanical.** Every `<a>` keeps its `href` and the term it wraps. Every
   number, code span, tag, and attribute is unchanged, so only text moves. This
   catches broken links and renamed things, and very little of the drift above.
2. **Meaning.** A reviewer who sees both versions, and not the editor's summary
   of them, goes through every changed sentence and marks it same meaning,
   changed, or unsure against the list above. Ask the reviewer to assume
   something changed. Anything not marked same meaning is reverted or reworded,
   and the reviewer goes again from scratch, not only over the lines it flagged.
