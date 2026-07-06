# Deep Site Analysis & Roadmap - 2026-07-04

Multi-agent qualitative analysis (15 agents: 10 site-slice readers + 3 external researchers + synthesis + adversarial critic). Complements the weekly automated audit, which scores 98-100 but only checks *presence* of SEO elements, not *validity* or content substance. 143 raw findings deduped and prioritized here.

**Framing:** technical SEO is solved. The gap is one layer down: the site's most valuable asset - the 94-meeting archive (two years of dated first-hand practitioner discussion) - is neutralized by fixable defects, and several verified bugs are invisible to the weekly audit.

## Verified bugs the weekly audit cannot see

| Bug | Scope | Verification |
|---|---|---|
| Invalid JSON-LD on meeting pages (single-quoted strings; strict parsers reject the whole block, so the archive ships no structured data) | 82/94 Article, 91/94 BreadcrumbList | Confirmed with `json.loads` |
| Meta descriptions ending in a literal ellipsis mid-list ("...KMS, WAF, Macie…") | 134 pages (30 root, 94 meetings, 10 breaches) | grep-verified |
| Site search excludes all meetings/ and breaches/ pages while claiming full coverage (`build_search_index.py` globs only root `*.html`) | 104 pages invisible | verified against index |
| Crosslinker bug: plain word "cloud" links to `#term-air-gap` 60x inside glossary.html; glossary anchors injected inside contribute.html code blocks | glossary + 2 contribute pages | verified |
| `"sameAs": []` on Organization schema despite existing GitHub/YouTube/Kit; ~70 pages inline a duplicate publisher blob instead of `@id` | sitewide entity graph | verified |
| FAQPage schema with no visible FAQ (careers hub cites "the careers FAQ above" which does not exist) | 7 pages | verified |
| Content freeze: newest recap 2026-05-08 (8 missed Fridays) vs faq "we don't skip holidays"; presentations.html has no 2026 section | freshness | verified |

## Week 1 - mechanical, high yield (SCRIPTABLE) - DONE 2026-07-05

- [x] **Meetings metadata rescue** - fixed JSON-LD quoting (91 files, 173 broken blocks now parse; Meeple double-quote escaped); rewrote all 94 date-only titles to `[headline] - CSOH Recap, [Mon D, YYYY]` from the Article headline; sentence-aware description truncation applied to the 29 recaps where it yields a clean complete sentence (removes the trailing ellipsis). Generator (`tools/add_meeting.py`) fixed so new recaps come out right: `truncate()` prefers sentence boundaries, `<title>` uses the headline.
- [x] **Ran `tools/inject_meeting_topic_links.py`** - 42 link-less recaps got 59 contextual topic links; no nested anchors.
- [x] **Search index fix** - `build_search_index.py` now emits one page-level doc per breaches/ (10) and meetings/ (94) page; added "Breaches" + "Recaps" filter chips and typeLabel cases to search-init.js (loaded plain, no SRI). Browser-verified: "storm-0558" and "LiteLLM" now surface the right pages with correct badges; the page's "search across every page" claim is finally true.
- [~] **Entity graph** - populated the canonical homepage Organization `sameAs` with the GitHub org. DEFERRED (needs design/URLs): the 175-page publisher `@id` swap would dangle (those pages don't define `#org`; valid inline blocks are safer than a broken reference); YouTube footer link + richer sameAs need a channel/org-LinkedIn/X URL from Shawn (none exist on the site today).
- [x] **Air-gap link cleanup** - stripped all 60 spurious `#term-air-gap` anchors in glossary.html; guarded `crosslink_glossary.py` so parenthetical qualifiers ("Air Gap (Cloud)", "Ambient Mode (Service Mesh)") never become aliases (acronym/expansion pairs still do) + added "cloud" to DENYLIST; unwrapped 11 glossary anchors inside `.code-block`/`.tag-example` on the two contribute pages and taught `crosslink_pages.py` to mask those class-based regions.
- [x] **Stats true-up** - resources "240+"/"280+" -> "370+" (actual 374) across index.html (incl. FAQPage JSON-LD), llms.txt, resources.html, README.md, faq.html; chat-resources "570 links" -> "580+" (actual 581).
- [x] **CI lints** - `tools/check_jsonld.py` (blocking gate wired into validate-html.yml; all 427 blocks pass, catches regressions); `tools/check_meeting_staleness.py` + `check-meeting-staleness.yml` (weekly, opens/updates/auto-closes a sticky issue; currently reports 58 days / ~8 missed sessions). Ellipsis-ending meta lint DEFERRED to accompany the Week-2 root/breach/long-recap description rewrite (would fail now on ~100 not-yet-rewritten pages).

### Follow-ups surfaced during Week 1
- meetings/2026-02-20 and 2026-02-27 ship byte-identical recap *body* text (not just descriptions) - a source-content dup needing the real notes; titles now differ. (spawned as a task)
- Search index is 2.48 MB (loaded on search.html only). Fine for now; revisit if search.html CWV suffers.

## Week 2-3 - editorial passes

- [x] **Breach citations** - 10 "Real-world example" links from topic pages to breaches/ (aws->capital-one, azure->microsoft-sas-leak, ci-cd->solarwinds, iam->uber + snowflake, ai-ml->promptware, data-security->lastpass, detection->storm-0558, incident-response->scattered-spider-mgm, kevin-mitnick->mitnick-novell). All verified to resolve; no nested anchors. Facts checked against each breach page.
- [x] **Homepage pillar cards** - added a "Learn the fundamentals" grid to index.html linking 8 pillar guides (what-is, shared-responsibility, aws/azure/gcp, iam, zero-trust, cspm-vs-cnapp). Browser-verified: cards render, all OG images 200.
- [x] **Glossary deep-dive links** - 34 "Deep dive: <guide>" trailing links added to glossary terms with a matching guide (surgical, per the glossary workflow). Also fixed a bug in `check_jsonld.py` (was descending into `.claude` worktrees). No nested anchors; all targets exist.
- [x] **Trust pass** - added "How CSOH is funded" section (id=funding) to about.html; fixed the faq.html contradiction (visible answer + the "Does CSOH cost anything?" JSON-LD both no longer overclaim "no sponsorships"); added a Wiz affiliation-disclosure paragraph to cspm-vs-cnapp.html modeled on vendor-landscape.
- [~] **Orphan rescue / sibling asymmetries** - added 6 contextual links: kevin-mitnick->mitnick-novell (breach pass), grc->compliance-frameworks, ctfs->cloud-pentesting, incident-response->backup-dr, ci-cd->version-control, cloud-pentesting->api-security. REMAINING orphans: ai-learning, degree-programs, terraform, service-mesh-security, threat-modeling still thin; more sibling pairs (aws->iam return, version-control->github-actions return) to reciprocate.
- [x] **Surface GitHub issue forms** - "Fastest path: use a form" callout on contribute.html; reframed contribute-resources.html "Fastest option" to lead with the no-install Resource Suggestion form (was pushing `python3`); linked the resource + kill-chain forms in two faq.html answers and aligned the "add a resource" JSON-LD.
- [x] **CONTRIBUTING_KILL_CHAINS.md rewrite** - replaced the dead single-page tab layout (incident-tabs/kc-main/incident-panel) with the current one-page-per-breach workflow (copy a breaches/ page -> fill inc-header/kill-chain body -> register: breach-card + ItemList numberOfItems bump + pager + sitemap + sync_chrome). Refreshed the stale 2022-23 candidate table to 2025-26 incidents (Salesloft/Drift, Codefinger, tj-actions, Midnight Blizzard, Sisense). Updated the Claude-assist and PR-submit steps.
- [x] **FAQ schema compliance** - added visible "Quick answers" (details/summary) blocks rendering the exact schema Q&A on the 4 schema-only career pages (careers 4, sales-engineer 10, customer-success 6, help-desk 6) + index.html (5); rebuilt the FAQPage schema from the visible content on the 3 mismatched pages (engineer 5, architect 8, detection 7). All 8 now match visible==schema 1:1 (verified). Fixed the careers "FAQ above" phantom citation. Browser-verified rendering.
- [x] **Recap backlog (CLEARED)** - Shawn provided the Zoom summaries; added all 8 missing recaps via add_meeting.py: 2026-05-15, 05-22, 05-29, 06-05, 06-12, 06-19, 06-26, 07-03 (cleaned: dropped the todos and off-topic chatter; 07-03 vendor-controversy framed as unnamed vendor + "allegations"). 05-15/05-22 were mid-chain inserts, so the append-only tool's pager + hub order were corrected by recomputing the full 102-page pager chain and re-sorting the hub cards (verified: chain fully consistent, no dangling links). Staleness check now healthy. STILL TODO: refresh chat-resources export; add 2026 presentations section; fix stale Cloud Next 25 link.

## Month 2 - larger editorial

- [x] **sessions.html rebuild** - 760 -> 1,946 words. Rewrote About (format, vendor-neutrality, psychological-safety-by-design, the since-Feb-2023 consistency), added "Who these sessions are for" (4 personas with cross-links to learning-path/careers/interview/portfolio), expanded What to Expect, added a "What we've been talking about" evergreen teaser (links breach-timeline/meetings/presentations), expanded How to Join to 4 steps (added explicit calendar-subscribe step), and added a 6-Q FAQ + matching FAQPage JSON-LD (visible==schema 1:1, browser-verified). All links resolve, no em-dashes, reindexed. NOTE: the "Submit a question for Friday" Google Form still needs a URL from Shawn - covered for now via email + ask-live + present.html.
- [x] **2026 currency pass** - vendor-landscape: fixed 4 stale entries (QRadar->Palo Alto, Secureworks->Sophos, Skyhigh un-Trellixed, Banyan->SonicWall) + added NHI and ASM/CTEM categories (ItemList 28->30). cspm-vs-cnapp: dropped Lacework->FortiCNAPP (3 spots), noted the ~$32B Google/Wiz acquisition, added an AI-SPM/CDR section. compliance-frameworks: added an "AI governance: EU AI Act & ISO 42001" section + decision-tree branch. All anchors + TOC + JSON-LD verified.
- [x] **Quick wins (partial)** - fixed the stale Cloud Next link (->canonical /next/); shipped a static /csoh.ics (weekly Friday 7am PT with VTIMEZONE) linked from faq.html + sessions.html. DEFERRED: local-time Intl.DateTimeFormat snippet (doable but rebumps main.js SRI across ~190 pages - warrants its own commit). NEEDS INPUT: "Submit a question" Google Form URL; presentations.html 2026 talk data; chat-resources export data.
- [x] **cloud-security-engineer.html expansion** - deepened 14 of 16 sections in place (5-agent workflow, each given the current section HTML to expand, not rewrite): 4,794 -> 9,120 words, now at sibling parity. Added ~30 h3 subsections (prevention>detection>response framing, the reactive-vs-proactive week rhythm, tools-by-category depth, per-stage career mechanics, break-in pivots, AI-era impact). Preserved all salary figures and existing links; left the rich cloud-twists section and the schema-coupled FAQ untouched (FAQPage 1:1 intact). Danglers/self-links stripped, TOC anchors all resolve, JSON-LD valid, browser-checked, reindexed.
- [x] **"How csoh.org is secured" page** - new how-csoh-org-is-secured.html: 10 evidenced sections (static-site, strict CSP + no-inline, security headers, SRI, cookieless analytics, supply chain, keyless OIDC deploys, CI gates, RFC 9116 disclosure, and a "verify it yourself" section with securityheaders.com/Observatory/hstspreload/curl). Wired fully: OG image generated, sitemap + llms.txt + search index, linked from about.html + security-policy.html. Browser-verified. (Follow-up: add glossary terms SRI + Trivy - unlinked for now.)
- [x] **AI-era sections** - added a substantive section to each pillar (drafted via 3-agent workflow, fact-grounded): zero-trust #ai-agents "Zero trust for AI agents and non-human identities" (agent = NHI, model output != authz, human-in-the-loop, MCP as PEP, continuous verification; cites NIST 800-207 + CISA agentic-AI guide + OWASP LLM01); api-security #ai-apis "Securing AI, LLM, and agent APIs" (OWASP LLM Top 10 alongside API Top 10, prompt injection as input-trust, tool-call authz = BOLA root cause, token budgets, output validation); saas-security #ai-saas "AI features, OAuth sprawl, and third-party integration risk" (copilots inherit broad access, OAuth sprawl -> the Salesloft Drift lesson, SSPM inventories AI apps). Each: 5 h3s, TOC entry, cross-links to nhi/mcp/ai-ml/detection pages + relevant breach; danglers + self-links stripped; JSON-LD/anchors verified; browser-checked; reindexed.
- [ ] Static /csoh.ics + "Submit a question for Friday" Google Form.
- [x] **Local-time snippet** - main.js computes the viewer's local equivalent of the next Friday 07:00 PT (DST-correct via Intl offset math) and appends it to `[data-session-localtime]` spans on index.html + sessions.html; skips silently for Pacific viewers. Verified: algorithm (LA 07:00 / NY 10:00 / London 15:00) + DOM fill in-browser. Rebumped main.js SRI across 205 pages (own commit).
- [ ] Consent/PII policy for named community members (gates the amplification work).

## Quarter - new content (ranked by SERP winnability)

- [x] **non-human-identity.html + mcp-security.html** - two new pillar-grade topic guides (drafted via workflow, wired + verified).
- [x] **Interview-questions hub + resume guide** - cloud-security-interview-questions.html (45+ Qs by domain, with model-answer guidance + paste-in artifacts) and cloud-security-resume-guide.html (before/after bullets).
- [x] **Career-question pages** - get-into-cloud-security-no-experience.html and is-cloud-security-a-good-career.html.
- [x] **3 new kill chains** - breaches/codefinger-s3.html (S3 SSE-C ransomware, Jan 2025), breaches/tj-actions-changed-files.html (CVE-2025-30066 CI/CD supply-chain, Mar 2025), breaches/salesloft-drift-unc6395.html (OAuth token theft -> bulk SOQL exfil, Aug 2025). Each: 5-step MITRE-mapped chain, def-box, primary sources, defense-topics. Registered: cards + ItemList (10->13) + pager chain (snowflake now has a next) + sitemap + llms.txt + OG images + search index. Fact-verified via WebSearch; drafted with a 3-agent workflow. Shipped 9be06d2f.
- [x] **breach-lessons.html** - synthesis of recurring root causes across the 10 breach kill chains + a MITRE ATT&CK technique section; links each breach page.
- [x] **Comparison pages** - cnapp-vs-xdr.html and cspm-vs-cwpp.html (category comparisons with tables; no vendor head-to-heads).
- [ ] First-party data: quarterly community-pulse report, annual Cloud Breach Year in Review.
- [x] **speakers.html + present.html** - guest-speaker index + speaker pitch guide (evergreen, no fabricated roster).

## Killed by adversarial critic (do NOT do)

- DiscussionForumPosting schema on recaps - they're owner-authored summaries, not UGC; spam-action risk.
- Occupation/HowTo schema - Google deprecated both enrichments.
- Guided CloudGoat/flAWS labs - rot fast, support burden a solo maintainer can't absorb.
- Bot-injected "recent news" blocks into topic pages - conflicts with churn discipline, fake-freshness signal.
- Regenerating all 94 recaps - add_meeting.py is publish-once; would clobber years of hand edits.
- Inline Kit email form - CSP `form-action 'self'` (nginx + rules.tf with ignore_changes gotcha) blocks it; 4-surface change, not "low effort."

## Sequencing note

Extend `check_pagespeed.py` beyond the homepage to a representative heavy-page set (resources 548KB/376 imgs, glossary 272KB, a recap, a breach) before layering curation UI onto those pages. Stand up a monthly 20-30-prompt AI-citation baseline (repo CSV) before the content investments land, so impact is attributable. Sequence new-page work by Search Console impression/CTR data.
