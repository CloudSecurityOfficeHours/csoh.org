# How-to slide decks: rollout to the remaining guides

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give each of the other 23 guides in `howto/` a reviewed slide deck, uploaded privately for Shawn, then shared and linked from its guide one batch at a time on his go.

**Architecture:** The pilot's tooling is reused unchanged: one outline per guide in `tools/decks/<slug>.deck`, checked by `tools/build_howto_decks.py --check`, built by `--build`, published through the Drive connector by the controller (pilot ruling R4), and linked by `--record`. The guides that use the 24-event CloudTrail lab share `_cloudtrail-lab.deck` once Task 1 has confirmed every sentence in it is true of each of them. Work runs in three batches: the lab guides, the other guides with a "How this page was checked" line, and the three guides without one.

**Tech Stack:** Python 3 standard library (checker), python-pptx 1.0.2 (local build only), Google Drive and Slides connectors, lychee.

**Spec:** `docs/superpowers/specs/2026-11-19-howto-slide-decks-design.md` (Rollout section). The approved pilot is `tools/decks/splunk-spl.deck`; its plan is `docs/superpowers/plans/2026-11-19-howto-slide-decks.md`.

## Global Constraints

- Decks are CC BY-NC 4.0; guides stay CC BY-NC-ND 4.0. The renderer adds attribution and license to the first and last slides.
- 12 to 20 slides per deck, counting the generated cover and closing slides.
- At most 40 words of prose and 12 visual code rows per slide (a code line longer than 84 columns wraps and counts as the rows it wraps to). The limits do not guarantee fit: `--build` is the layout check, and every deck must build with 0 verify findings.
- Every code excerpt is a contiguous run of whole lines from one `<pre>` block on its own guide, and is shortened only from its ends.
- A slide says nothing its guide does not say. A deck claims no more testing than its guide's "How this page was checked" line, keeps that line's "Not run" items, and makes no testing claim at all when the guide has no such line.
- Every acronym and every term a beginner would not know is defined on the slide where it first appears, in the guide's own words. Nothing is referred to before the deck has introduced it.
- An excerpt the guide attributes to a third party carries a `credit:` line naming the source the guide names.
- No U+2013 or U+2014 and no spaced hyphen used as a dash. No AI tells from `docs/agent-lessons.md` section 2: whole sentences, not verbless fragments; command, function and field names in prose read as names ("the where command"), not English words. No ranking of third parties. ATT&CK v19 names. The Wiz disclosure where the guide carries it.
- Uploading privately is approved. Sharing publicly, and deleting or trashing any Drive file, each need Shawn's explicit go for that batch or file. Never write the deck owner's email address into the repo.
- Commit locally with explicit paths (never `git add -A`); push only when Shawn says so. No CI-skip token in any commit message. End messages with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. A testing claim that outgrows the guide: a "checked" slide that drops "Not run" items or turns "checked against documentation" into "tested". Every outline task's fact review compares that slide with the guide's line clause by clause.
2. A shared lab sentence one including guide does not support (a definition, an address, a detection's wording). Task 1 audits the fragment against all eleven lab guides; each lab deck's fact review reads the included slides too.
3. An exercise answer that disagrees with the guide's own answer block (inverted condition, a different field name). Each fact review reads every answer slide against the guide's answer.
4. A third-party excerpt with no credit, or credited to the wrong source. Each fact review lists every excerpt and the guide sentence that names its origin.
5. A deck that builds but reads badly in Google: a slide at the bottom limit, a heading the estimate puts on the wrong number of lines, or a substitute font. Each batch's render check (Tasks 12, 23 and 27) looks at every slide in Google's own render before Shawn sees it.

---

## Outline procedure (every outline task)

Each outline task names one guide. Its implementer writes `tools/decks/<slug>.deck`; nothing else changes.

- [ ] **Step 1: Read the guide and the pilot.** Read `howto/<slug>.html`, the pilot outline `tools/decks/splunk-spl.deck`, the outline format in `tools/DECKS_README.md`, and the list of problems the pilot's review caught, `.superpowers/sdd/2026-11-19-howto-slide-decks/task-5-6-findings.md`.
- [ ] **Step 2: Write the outline** in the deck shape from the spec: who it is for and what you need; how the guide was checked (only if the guide says); what the language is and where you meet it; the one idea that makes it click; one slide per key step, each with a code excerpt and its `section:`; two or three exercises, each with its question and answer on consecutive slides; common mistakes. The promise line restates the guide's own promise. Lab guides include `_cloudtrail-lab.deck` where the guide introduces the lab, as the pilot does, once Task 1 is complete.
- [ ] **Step 3: Run the gate.** `python3 tools/build_howto_decks.py --check` reports 0 findings.
- [ ] **Step 4: Build.** `python3 tools/build_howto_decks.py --build <slug>` exits 0 with 0 verify findings. Report every slide's content bottom against the 6.9 in limit (a throwaway script outside the repo, as in `task-7b-report.md`).
- [ ] **Step 5: Control.** Change one character in one code line, confirm `--check` names it, restore from a scratch copy.
- [ ] **Step 6: Commit** `tools/decks/<slug>.deck` alone, message `decks: <guide title> outline`.

**Review (controller):** one combined spec, quality and fact review on the most capable model, as pilot ruling R9 set up: every slide sentence against the guide, the Review Focus items above, and the Global Constraints. Fix rounds and re-reviews follow the SDD fix loop.

## Publish procedure (Tasks 12, 23, 27 and 28 to 30)

Run by the controller, because it uses the Drive and Slides connectors (pilot ruling R4).

**Upload and render check (Tasks 12, 23, 27):**

- [ ] Build each deck in the batch, upload it privately as Google Slides into the "CSOH how-to decks" folder (`1NlWcekhB2ZqJmXDfrIHGjfVnZLu17ccd`), and confirm from its metadata that the owner is the connector account and visibility is PRIVATE. Log each ID in the ledger.
- [ ] Pull a LARGE thumbnail of every slide and check fonts, code wrapping, overflow, footers, credits and heading spacing. A defect goes back to that outline's implementer and reviewer; the re-upload gets a new ID and the old one joins the list of superseded files for Shawn.
- [ ] Hand the batch to Shawn: the private links, what the render check found, and the superseded files. Stop for his go on this batch; carry on with the next batch's outlines meanwhile.

**Publish (Tasks 28 to 30, each only after Shawn's go for that batch):**

- [ ] Rebase the branch onto `origin/main` (nothing is pushed), regenerating any generated file that conflicts, and confirm `--check` still reports 0 findings. A guide whose quoted code changed on main sends its outline back through the outline procedure.
- [ ] Share each deck `anyoneWithLink` as reader. Signed out, its `/export/pdf` returns `200 application/pdf` starting `%PDF-` with one page per slide, and its `/copy` redirects to `accounts.google.com`.
- [ ] `python3 tools/build_howto_decks.py --record <slug> <id>` for each deck, then `--stamp` twice and confirm the second run changes nothing.
- [ ] Gates, each exit 0: `--self-test`, `--check`, `--stale` (prints nothing), `python3 tools/stamp_code_langs.py --check`, `python3 tools/check_readme_coverage.py --check`, `python3 tools/check_no_inline_scripts.py`. `lychee --config .lychee.toml` on the batch's guide pages reports both deck links OK on every page; any other failure is named as pre-existing or fixed.
- [ ] Preview two of the batch's guide pages in light and dark mode: the deck line is the last line of the info box and its links are underlined.
- [ ] Commit `tools/decks/published.json` and the batch's `howto/<slug>.html` pages with the message `decks: publish <batch name> decks and link them from their guides`. Do not push.

---

### Task 1: Audit the shared CloudTrail lab fragment

**Files:**
- Modify: `tools/decks/_cloudtrail-lab.deck`, `tools/decks/splunk-spl.deck`

**Interfaces:**
- Produces: a `_cloudtrail-lab.deck` every one of the eleven lab guides supports sentence by sentence, which Tasks 2 to 11 include.

The eleven lab guides: `splunk-spl` (the published pilot), `kusto-kql`, `sql-for-security-data-lakes`, `panther-python-detections`, `cloud-native-log-queries`, `elastic-esql-eql`, `sumo-logic-queries`, `crowdstrike-logscale`, `datadog-cloud-siem`, `falco-rules`, `yara-l`. Only four of them (`splunk-spl`, `kusto-kql`, `sql-for-security-data-lakes`, `panther-python-detections`) define CloudTrail as the record of calls made to an AWS account and an access key as the credential a program signs its AWS requests with.

- [ ] **Step 1: Rebase onto `origin/main`** (nothing is pushed), regenerating any generated file that conflicts, and confirm `--check` reports 0 findings.
- [ ] **Step 2: Audit.** Write a table, one row per fragment sentence and one column per lab guide, marking whether the guide states it (quote the guide's words).
- [ ] **Step 3: Split.** A slide stays in the fragment only if every lab guide supports every sentence on it. Any other slide moves, word for word and in the same position, into `splunk-spl.deck`, and each later lab deck writes its own version from its own guide.
- [ ] **Step 4: Confirm the published pilot is unchanged.** `--check` reports 0 findings, `--stale` prints nothing (the resolved outline text, which the published hash covers, is identical), and `--build splunk-spl` exits 0 with 0 verify findings.
- [ ] **Step 5: Commit** both files, message `decks: keep only what every lab guide says in the shared lab slides`.

### Batch A: the lab guides

Each task follows the outline procedure for its guide.

### Task 2: `kusto-kql`
Defines CloudTrail and access keys itself; its deck can keep those definitions.

### Task 3: `sql-for-security-data-lakes`
Defines CloudTrail and access keys itself.

### Task 4: `panther-python-detections`
Defines CloudTrail and access keys itself.

### Task 5: `cloud-native-log-queries`
Two query languages (CloudWatch Logs Insights and Google Cloud Logging). Each code slide says which one it shows.

### Task 6: `elastic-esql-eql`
Two languages (ES|QL and EQL). Each code slide says which one it shows.

### Task 7: `sumo-logic-queries`

### Task 8: `crowdstrike-logscale`

### Task 9: `datadog-cloud-siem`

### Task 10: `falco-rules`

### Task 11: `yara-l`
The guide carries the Wiz disclosure in its info box. The deck states it, in the guide's words, on the first slide that names Google or Google SecOps.

### Task 12: Batch A upload and render check
The publish procedure's upload and render check for Tasks 2 to 11.

### Batch B: the other guides with a "How this page was checked" line

### Task 13: `azure-policy`

### Task 14: `cel-policy-expressions`

### Task 15: `cloud-custodian`

### Task 16: `iam-policy-languages`
Two languages (IAM policy JSON and Cedar). Each code slide says which one it shows.

### Task 17: `kyverno`

### Task 18: `opa-rego`

### Task 19: `osquery-and-velociraptor`
Two tools (osquery SQL and Velociraptor VQL). Each code slide says which one it shows.

### Task 20: `python-cloud-sdks`
The guide mentions build-bot but is not one of the lab guides; it does not include the fragment.

### Task 21: `semgrep-rules`

### Task 22: `sigma-and-yara`
Two languages (Sigma and YARA). Each code slide says which one it shows.

### Task 23: Batch B upload and render check
The publish procedure's upload and render check for Tasks 13 to 22.

### Batch C: the guides with no "How this page was checked" line

Before Task 24, grep each of the three guides for "How this page was checked". A guide that has gained the line gets a checked slide like the others; one that has not gets no testing claim.

### Task 24: `jq-and-jmespath`
Two languages (jq and JMESPath). Each code slide says which one it shows.

### Task 25: `oval-and-scap`

### Task 26: `regex-for-security`

### Task 27: Batch C upload and render check
The publish procedure's upload and render check for Tasks 24 to 26.

### Tasks 28 to 30: Publish batches A, B and C
The publish procedure, one task per batch, each only after Shawn's go for that batch.

### After the last batch

The SDD final whole-branch review, carrying the deferred minors from the pilot's ledger (including the slide 19 wording on the published Splunk deck, which needs a re-publish if fixed), then superpowers:finishing-a-development-branch.
