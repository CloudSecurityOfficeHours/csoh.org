# How-to guide slide decks: design

## Intent

Every guide in `howto/` gets a public slide deck. The decks have two jobs,
both chosen by Shawn:

- **Passed around as a PDF.** People share the deck on LinkedIn or download
  it, and read it away from csoh.org with no presenter. Every slide has to
  explain itself, and every copy has to lead back to the guide.
- **Reused to teach.** Other people make an editable copy and teach their own
  sessions from it.

A deck is a condensed companion to its guide, not a replacement. The guide
keeps the full lab; the deck gets a reader to the one idea, shows the key
steps, and sends them to the guide to do the work.

## Decisions Shawn made

- Audience: the public, reading on their own (not decks for Shawn to present).
- Both uses above: shareable PDF and editable copy.
- Build approach: outlines written in the repo, turned into decks by a
  script, published to Google Slides (approach 1 below).
- Owner: the decks are meant to belong to a **CSOH Google account**
  (csoh.org runs on Google Workspace), because anyone who opens a deck can
  see its owner's name and address. **For now** they live in Shawn's
  personal Google Drive, the account the Drive connector is signed in to,
  as the existing decks on `presentations.html` do.
- Every deck opens by explaining how to set up the environment and how to
  follow the guide (deck shape items 3 and 4).
- License: the decks are **CC BY-NC 4.0**. The guides stay CC BY-NC-ND 4.0.
  The no-derivatives term would forbid a teacher from editing a deck and
  presenting it, which is the reuse the decks exist for.

## Goals

- One deck per guide, generated from an outline in the repo.
- Each deck published as Google Slides, viewable by anyone with the link.
- Each guide page links to its deck twice: a PDF download and "make your own
  copy", both Google's own links, so csoh.org hosts no new file types.
- Every code sample on a slide is a contiguous run of lines from one of the
  guide's code blocks, and a CI gate fails if it is not.
- Every slide carries the guide's csoh.org address, so a forwarded PDF leads
  back to the site.
- A pilot deck (Splunk SPL) is built, checked and approved before the rest.

## Non-goals

- No embedded deck viewer on the guide pages. Links only, so guide pages load
  nothing from Google and the CSP needs no change.
- No PDF or .pptx files hosted on csoh.org.
- No deck index page and no structured data for decks in this round.
- No presenter-only material. Speaker notes exist only to help teachers find
  the matching guide section.

## Anti-goals (failure even if everything else works)

- A slide that says something its guide does not, or claims more testing than
  the guide's "How this page was checked" line. A guide checked against
  documentation only, or one with parts marked "not run", says exactly that
  on its deck. A guide with no such line gets no testing claim on its deck.
- Slides that do not read on a phone. A LinkedIn document post is read on a
  small screen, so walls of text or tiny code fail.
- Breaking the site's writing rules (`docs/agent-lessons.md` section 2): no
  em or en dashes and no spaced hyphens used as dashes, none of the listed AI
  tells, no ranking of third parties, ATT&CK v19 names, and the Wiz disclosure
  where the guide carries it (the YARA-L guide).
- A link on a guide page that crawlers or `tools/normalize_urls.py` turn into
  a Google sign-in URL.

## Approaches considered

1. **Outline in the repo, generated .pptx, uploaded to Google Slides
   (chosen).** The repo is the source of truth and the gate can tie code to
   the guide. Costs: the most machinery; the .pptx to Slides conversion may
   shift layout; re-publishing creates a new file (see Constraints).
2. **Built directly in Google Slides through the Slides API.** Least
   machinery and hand-editable, but the deck lives outside git, code is
   retyped instead of copied from the checked guide, and nothing notices when
   a guide changes. Every API request also passes inline through the
   connector, which is costly per deck. Rejected.
3. **PDF and .pptx files hosted on csoh.org.** No Google dependency, but each
   edit commits new binaries, the new file types need registering in the
   deploy path filters, and teachers get no one-click copy. Rejected.

## Constraints

- **Publishing scope.** Outlines, the generator and the deck-to-file mapping
  live under `tools/`, which `tools/site-publish.filter` excludes from every
  origin. The only published change is the links on guide pages.
- **License text.** `LICENSE` gains a third clause: the slide decks of the
  how-to guides, and their outlines, are CC BY-NC 4.0. Each deck states its
  license and the attribution "Cloud Security Office Hours, csoh.org" on its
  first and last slides.
- **Third-party excerpts.** Some guides quote vendor rules (Splunk's public
  detections, Falco stock rules, Elastic, Sigma and Panther content). Any such
  excerpt on a slide is credited on that slide, and the license slide says
  third-party excerpts keep their own licenses. This matches the third-party
  paragraph already in `LICENSE`, and the new clause repeats the carve-out.
  (Builder's call, consistent with `LICENSE`.)
- **Google Drive connector.** `create_file` uploads a .pptx (passed as a file
  reference) and converts it to Google Slides by default. `share_file` with
  `permissionId: "anyoneWithLink"` makes it public. `download_file_content`
  with `exportMimeType: application/pdf` returns the PDF for checking.
  `update_file` changes metadata only, so it cannot replace a deck's
  contents: re-publishing a changed deck means a new file with a new ID.
- **Owning account.** Decks upload to the account the Drive connector is
  signed in to, which for now is Shawn's personal Google account. Check
  each upload's owner in its metadata and stop if it is not the expected
  account. Never write the owner's email address into the repo.
- **Moving to a CSOH account later.** Moving means re-uploading every deck
  from the CSOH account, which gives each a new ID. The mapping file and
  the link-writing tool already handle a changed ID, so the move is a
  re-publish of every deck plus one commit of new links. A csoh.org
  Workspace must allow "anyone with the link" sharing outside the domain
  and must not block download or copy for viewers.
- **Stable entry point.** Because deck IDs change on re-publish, the guide
  page is the stable address. The tool that writes the links reads the
  current ID from the mapping file, and every slide points to the guide, not
  to the deck.
- **Approvals.** Uploading, sharing publicly and deleting old copies are
  outward-facing. Upload a deck privately for review; share it publicly only
  on Shawn's explicit go; delete superseded copies only on his OK. Commit
  locally; push only when he says so.
- **Generator dependencies.** `python-pptx` is not installed in any local
  interpreter. The build step may need it locally; the CI gate must run with
  what `validate-html.yml` already provides and must not import it.
- **Link checks.** lychee crawls guide pages. A signed-out request to a
  `/copy` link is sent to Google sign-in, so the pilot has to confirm what
  lychee reports for both links. Any lychee exclude is anchored narrowly.
  `normalize_urls.py` reads only root-level pages, so it never touches links
  in `howto/`.
- **Look.** 16:9 slides. Site palette: `--primary-color` `#0f172a`,
  `--secondary-color` `#0369a1`, `--accent-color` `#f59e0b`, `--light-bg`
  `#f8fafc`. Site fonts Space Grotesk (headings) and Source Sans 3 (body) are
  Google Fonts, so Google Slides renders them; code uses a monospace Google
  Font. Text meets 4.5:1 contrast against its background.
- **Readability floor.** Body text at least 18 pt, code at least 14 pt, about
  12 code lines and about 40 words of prose per slide at most. The pilot may
  tune these after looking at a phone-sized render.

## Design

### Files

- `tools/decks/<guide-slug>.<ext>`: one outline per guide, holding slide
  text, speaker notes and code excerpts. The format must keep prose and
  multi-line code readable in review.
- A shared outline fragment for the guides that use the 24-event CloudTrail
  lab (the lab and its D1 to D5 detections), included by reference so those
  decks state the lab identically.
- `tools/build_howto_decks.py`: validates outlines, writes
  `tools/decks/build/<slug>.pptx` (git-ignored, and under the `/tools/`
  publish exclusion; not `dist/`, which `stage_site.sh` wipes), writes the
  deck links into guide pages, and has `--check` (CI), `--stale` and
  `--status` modes.
- A mapping file in `tools/decks/`: guide slug to Google presentation ID,
  the publish date, and the sha256 of the outline that was published.
- `tools/DECKS_README.md`: how to write an outline, build, publish and
  re-publish.

### Deck shape

Follows the guide's own sections, so a reader can match slides to the page:

1. Title: guide title, a one-line promise, attribution, license.
2. Who it is for and what you need (the guide's info box), plus a short form
   of "How this page was checked" that claims no more than the guide.
3. How to follow the guide: the guide's "How to use this guide" section in
   short (read in order, what the walk-through covers, which code blocks you
   paste and which show what you should see).
4. Set up your environment: the guide's setup step, with its commands as a
   code excerpt and what you should see when it worked (one slide, two if
   setup has two distinct stages).
5. What the language is and where you meet it.
6. The one idea that makes it click.
7. Walk-through highlights: one slide per key step, each with a code excerpt,
   one sentence on what it shows, and the step's name in the guide.
8. Two or three exercises: the question on one slide, the answer on the next.
9. Common mistakes.
10. Where next: the guide's full URL, attribution and license.

Twelve to twenty-two slides. Every slide's footer shows the guide's csoh.org
address and the slide number. Speaker notes give the matching guide section's
URL with its anchor.

### Code gate

Each code excerpt in an outline must equal a contiguous run of whole lines
from one `<pre>` block on its guide page, after HTML unescaping. `--check`
fails on any excerpt that does not match, and also fails if a guide page's
deck links disagree with the mapping file. It joins the other `--check`
gates in `validate-html.yml`. Control: change one character of a planted
excerpt, confirm `--check` fails, restore.

The gate cannot judge prose. That is the fact review's job.

### Keeping decks in step with guides (builder's call)

- **Code drift fails CI.** An edit that changes guide code a deck quotes
  turns `--check` red until the outline is fixed in the same change. The fix
  is a text edit under `tools/decks/`, so any session or review PR can make
  it, including docs-review PRs.
- **Publish lag is reported, not failed.** `--stale` lists decks whose
  outline no longer matches the sha256 recorded at publish. Re-publishing
  needs Shawn's go, so a CI failure here would block work nobody else can
  unblock. The public deck lags until he re-publishes; PDFs already passed
  around cannot be recalled in any design.
- **Coverage is not enforced.** `--status` lists guides with no deck. A new
  guide can ship without one, so it is never blocked on a public-deck
  approval.

### Publishing a deck

1. Build the .pptx locally.
2. Upload it privately to a "CSOH how-to decks" folder in the owning
   account's Drive.
3. Export the PDF, render its pages, and inspect them for overflow, font
   substitution and broken code boxes. Fix the outline or template and
   repeat.
4. Fact review: a fresh reviewer compares every slide with the guide and
   reports anything the guide does not say. Fix and repeat until clean.
5. Shawn reviews the private deck and approves it.
6. On his go, share it publicly, record its ID in the mapping file, write the
   links into the guide page, run the gates, and commit.

### Links on the guide page

One line at the end of the guide's info box (after "How this page was
checked" where the guide has it): the
deck's PDF link (`https://docs.google.com/presentation/d/<id>/export/pdf`)
and its copy link (`.../d/<id>/copy`), noting that copying needs a Google
account and that the slides are CC BY-NC 4.0. Links open in a new tab with
`rel="noopener noreferrer"`, like other external links on the site, and stay
underlined like every prose link.

### Rollout

The pilot is `howto/splunk-spl.html`. It is part of the detection series, so
its template and the shared CloudTrail lab slides carry straight to the other
guides that use that lab. After Shawn approves the pilot, the remaining
guides follow in batches, each deck with its own fact review. The three
guides with no "How this page was checked" line (jq and JMESPath, OVAL and
SCAP, regex) go last, in case they gain that line first.

## Left to the builder

- The outline file format and the generator's internals.
- The visual template, within the look and readability constraints.
- Slide count per guide, within the range above.
- Which exercises and steps make the cut for each deck.
- Exact wording and position of the info-box line.
- Tests for the generator beyond the gate's control.

## What the pilot has to settle

- How cleanly the .pptx converts to Google Slides (fonts, code boxes, text
  fitting).
- Whether the PDF export link downloads for a signed-out reader.
- What lychee reports for the export and copy links.
