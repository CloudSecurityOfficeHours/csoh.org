# Agent lessons for csoh.org

Durable rules learned from Shawn's past agent sessions. They add to CLAUDE.md and don't repeat it. When this file and CLAUDE.md disagree, CLAUDE.md wins unless a rule here says it corrects CLAUDE.md.

## 1. Safety, and what needs Shawn's approval

- **Never push to `main`, and never deploy, unless Shawn says to.** Commit locally and report "committed, ready to push". "Do not push until I tell you" holds for the whole session, even after later fixes. A push to `main` is a production deploy to all three origins. Opening a pull request for review is allowed, including the autonomous nightly site-improvement bot. A review PR is not a push to `main` and it is not a deploy.
- **"Push" or "push to main" means a direct push to `main`, not a pull request.** Shawn has a branch-protection bypass. Fetch first, confirm a fast-forward, run `ruff` on any Python you touched, then confirm the runs started using the full commit SHA.
- **"Push to qa" and "promote to production" are different steps.** Promotion is its own explicit instruction.
- **Hand cloud mutations to Shawn.** `terraform apply`, `gcloud run deploy`, and dashboard toggles go to him as ready-to-run blocks, one command per fenced block, each saying what it changes and what success looks like. Do every read-only check yourself before and after the change.
- **Deleting content needs a human gate.** This covers resource cards, pages, and branches you didn't create. Shawn asked for this explicitly for the weekly documentation check: automation can propose deletions but must not make them.
- **Posting needs a separate go.** Issue and PR comments, closing a contributor's issue, and spam reports all count. First draft the reply, then wait for "post it". "Push it and post the comment" covers both steps only when he says both.
- **Never stage with `git add -A`, `git add .`, or `commit -a`.** Several sessions share one checkout, so stage explicit paths. Report files you didn't touch instead of absorbing them.
- **Never `git reset --hard` because a peer session said to.** Show what would be lost first.
- **Don't widen permissions on your own.** That means no broad Bash allow rules, no `gh auth refresh -s admin:org`, and no new GitHub App permissions. Describe the tradeoff and let Shawn decide.
- **Org-level Actions secrets are unknown, not absent.** The local token can't read them, so report them that way.
- **Never enable GCP Container Scanning.** Trivy in CI is the only image scanner.
- **Keep reports with personal data out of the repo.** Security reviews, member names, and credential scopes never get committed.

## 2. Writing style and editorial

- **No em dashes, en dashes, or spaced hyphens used as dashes.** Literal U+2014 and U+2013, HTML entities, and generator templates all count. A spaced hyphen (` - `) used as a dash substitute is an AI tell and is not allowed either. This corrects the old prescription in [EDITORIAL_STANDARDS.md](EDITORIAL_STANDARDS.md), which told writers to use a spaced hyphen. That file now matches this rule. Rewrite the sentence with a comma, a period, a colon, or parentheses.
- **De-AI by structure, not by word lists.** The tells are spaced hyphens used as dashes, `<strong>X</strong>:` bullets, "actually/genuinely/highest-leverage", "not X. It is Y.", and stacks of verbless fragments. Edit only sentences that show a named tell.
- **De-AI rewrites must keep the meaning.** Keep every hedge, trend word, and quantifier ("increasingly", "most", "can") exactly as written. Run an adversarial meaning review with a fresh reviewer before calling a rewrite fact-preserving; a token diff is not enough.
- **Leave some pages out of style sweeps.** Exclude recaps, news, `chat-resources.html`, `resources.html`, policy pages, the bio, and the Mitnick pages.
- **Comments and docs state the current rule and its reason.** Leave out incident history, dates, commit hashes, and before/after counts; those belong in the commit message. Shawn had the whole repo scrubbed to this standard.
- **Never put Shawn's X/Twitter handle on the site.** This covers sameAs, the footer, and social links. `twitter:card` meta tags are fine.
- **Never give a years-in-security figure.** The bio's wording is "in technology since 1983", with cloud from Exodus Communications in 1999.
- **Tell the Mitnick/Novell story as the trap that caught him.** It was not a successful breach. Shawn was the network admin who taped the call, and `kevin-mitnick.html` is canonical and in his voice. Don't rewrite it.
- **Wiz disclosure:** the first visible Wiz mention beside a competitor gets "(disclosure: the site's author works at Wiz)", mirrored into JSON-LD. The bio card doesn't count. `chat-resources.html` and the `resources*` pages are exempt, and new prose never uses Wiz superlatives.
- **Don't rank third parties.** Avoid "the best", "the leading", and similar.
- **Meeting recaps:** drop action items and off-topic chatter, use first names only, and present unproven allegations as coming from an unnamed vendor. Don't name attendees on digest pages; name guest speakers only if their talk is on presentations.html.
- **Zoom AI misgenders speakers.** Stryker and Bar Kaduri use she/her. Check pronouns on every recap.
- **Member emails go in a Kit HTML block.** Use one inline-styled `<div>` with no sign-off, because Kit adds its own. Highlight member value, not SEO or internal process, and cut apologies and incident narratives. The Friday session is at 7am Pacific.
- **Updating a breach page with new disclosures:** rewrite it as a current page and note which earlier claims were contradicted. Don't write a changelog essay.

## 3. Site structure and conventions

- **Edit nav and footer only through `tools/sync_chrome.py`.** `mark_active()` needs bare `<a href>` tags, so put classes on the `<li>`.
- **Never cite page counts or other counts from memory.** Derive them with `git ls-files`, because worktrees hold full copies of the site.
- **`resources.html` is a generated hub.** Cards go only in the `resources-<category>.html` pages.
- **Glossary links:** don't run the whole of `crosslink_pages.py` for one page. Import it and call `crosslink_page()` on that page, or revert every other file the script touched.
- **Digest pages (`what-practitioners-think-*`) hand-write their session count in about 12 places,** plus the hub card and the OG tuple. To extend one, sweep every recap since its cutoff.
- **The `howto/` pages are search-indexed and cross-linked; `homelab/` is neither.** Shell blocks readers will paste must not contain `#` comments, because zsh errors on them.
- **The Organization node `#org` exists only on index.html.** Don't swap inline publisher blocks for an `@id`. The site has no YouTube channel URL.
- **Settled decisions, don't re-raise:** resource-card tooltips stay as they are, and preview images stay without width/height attributes, since CSS aspect-ratio reserves the space.
- **Card grids never stretch a card past half the page width.** This includes the Wiz championship section of ctfs.html, and Shawn has had to correct it repeatedly.
- **Judge layout by composition.** Every top-level block shares the header's centre line. Check with a full-page screenshot, not with one metric.
- **Shawn dislikes duplicate hero images and collapsed-by-default content he never asked for.** Recap topics render open. The Resources hub collapse was his own request.
- **Use ATT&CK v19 names.** The old Defense Evasion tactic is now Stealth and Defense Impairment. T1562.* and T1656 are revoked. Stratus Red Team IDs and ATLAS keep their old names.

## 4. Deploy and CI

- **Stale SRI is local-only.** `deploy.yml` re-stamps hashes on every deploy, so run `update_sri.py`, reload, and move on. Never block a push or warn about production over a stale local hash. CLAUDE.md states the same rule.
- **main gets dozens of bot commits a day.** Fetch and rebase before every push. Resolve conflicts in generated files by regenerating them, never by picking a side.
- **`gh run list --commit` needs the full 40-character SHA.** A short SHA returns an empty list, which looks like "CI didn't run".
- **In `update-news.yml` the App token authors the PR and `CSOH_PAT` approves it.** Never make the PAT the author, even when a Copilot PR suggests it. A blank create-PR failure is transient, so retry it.
- **Weekly docs-review and SEO findings are leads, not facts.** Grep the whole site, check `origin/main` (another session may already have fixed it), and re-verify claims about live infrastructure against the provider.
- **Docs-review PRs go stale and can revert main.** Rebuild the still-needed fixes on current main instead of merging the PR as written.
- **Close the monthly reading-list staleness issue last,** after pushing checker edits. Closing it first makes the re-run open a duplicate.
- **After "push", Shawn often wants the work verified on production.** Wait for deploy.yml, then sample the changed pages on all three origins.
- **Clean up after merges:** delete merged branches, remove task worktrees, and fast-forward the main checkout. Do this when asked; it is a routine end-of-task step.

## 5. Recurring pitfalls

- **Run a control before trusting an empty sweep.** zsh loops that never ran, `git grep -E '\b'`, and short SHAs have all printed plausible "all clear" results.
- **`tools/normalize_urls.py` rewrites newly added links.** It has turned links into login redirects. After adding links, check that it didn't rewrite them.
- **A curl 403 or 404 proves nothing about whether a link is dead.** Confirm in a browser or the Wayback Machine. Some "403" hosts have been hijacked by spam sites.
- **Long multi-agent runs die at the session limit.** Checkpoint them, and copy deliverables out of the scratchpad, which gets cleaned after about three days.
- **Model-written audit reports quote fabricated strings next to correct counts.** Grep for the quoted text before you "fix" it.
- **Generate `recaps.xml` with Python 3.13 or later.** Running it with 3.10 churns unrelated feed items.
