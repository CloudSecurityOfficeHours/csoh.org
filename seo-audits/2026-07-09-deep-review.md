# Deep Site Review - 2026-07-09

Six-agent qualitative review (freshness, career/guidance quality, technical topic quality, docs accuracy, IA/navigation, metadata/plumbing) plus a pre-pass against the 2026-07-04 deep-analysis roadmap. Follow-up to that roadmap: ~90% of it has shipped and verified; this review focuses on what broke since, what drifted, and net-new findings.

## Update log (2026-07-11)

**P1 - all fixed:** regenerated the 8 missing meeting OG images (img/og/meetings now 1:1 with 102 recaps); corrected 7 "zero analytics" claims across README/SECURITY/CONTRIBUTING to match privacy.html; fixed 3 wrong glossary anchors (terraform Cloud Run, serverless Fargate, help-desk Defender for Cloud); reattributed the phantom "careers FAQ" pull-quote.

**P2 - mostly shipped:**
- #5/#9 nav de-orphaning: added the 4 career pages (Is It a Good Career?, Start With No Experience, Interview Questions, Resume Guide) to Careers > Getting Started; Non-Human Identity + MCP Security to Learn; Present at CSOH + Guest Speakers to Community; Search to footer Explore. Propagated via sync_chrome.py to 222 pages; browser-verified desktop mega-menus (no overflow) + mobile accordion.
- #5 internal links: contextual interview-bank link added to all 11 role pages' interview-loop sections; resume-guide linked from help-desk resume section; learning-path "Ready to start?" list extended with no-experience + interview bank.
- #8 Lacework: replaced as a live vendor on all career/role pages (careers, learning-path, engineer, architect, cnapp-analyst) with Sysdig / SentinelOne + a FortiCNAPP acquisition note. REMAINING (P3 currency): unannotated Lacework still on pure technical-topic pages (aws-security, azure-security, grc, vulnerability-management, incident-responder) - separate sweep.
- #9 vs-page triangle: cnapp-vs-xdr and cspm-vs-cwpp now cross-link each other (was a broken triangle through cspm-vs-cnapp only).
- #7 hero CTA: FIXED per Shawn's call - hero primary button now points to sessions.html (session info + calendar + signup); nav CTA kept as the direct Kit email signup. Browser-verified.
- #6 breach 2026 gap: per Shawn's call, added a coverage note to breach-timeline (newest full kill chain = Salesloft Drift Aug 2025; 2026 incidents tracked in the news feed) rather than authoring new kill chains now. Full 2026 kill chains deferred to a dedicated session.

Validators after edits: check_jsonld OK, check_no_inline_scripts OK (223 files), 0 nested anchors, search index rebuilt (1617 docs).

## Update log 2 (2026-07-11) - P3

- **Bio drift RESOLVED**: standardized the author-card bio across 133 files to Shawn's chosen wording ("In technology since 1983 and in cloud since the early colocation era at Exodus Communications (1999)..."). about-shawn-nunley.html meta/OG/JSON-LD aligned to that page's own authoritative narrative (42 years, 1984 Read-Rite start, last 30 in security) rather than the generic card. NOTE: the card says "since 1983", the detailed bio page says "42 years / started 1984" - a 1-year framing gap left for Shawn to reconcile (1983 pre-Read-Rite vs 1984 first job).
- **Wiz-Google**: verified the deal CLOSED March 11, 2026 (US Nov 2025, EU Feb 2026). Updated vendor-landscape + cspm-vs-cnapp from "agreed to acquire / operationally independent" to past tense.
- **AWS SCS-C03**: web-verified the site's claim is CORRECT (released Dec 2, 2025). No change.
- **Lacework currency (technical pages)**: swept aws-security, azure-security, grc, vulnerability-management, cloud-security-incident-responder -> FortiCNAPP; also fixed cloud-security-comparison + sales-engineer. Left correctly-annotated instances (vendor-landscape "acquired by Fortinet", resources "formerly Lacework", cspm-vs-cnapp "FortiCNAPP (formerly Lacework)").
- **Post-quantum crypto (top technical gap)**: new "Post-quantum cryptography & crypto-agility" section on data-security.html (ML-KEM/ML-DSA/SLH-DSA, harvest-now-decrypt-later, hybrid PQC TLS on AWS/GCP/Cloudflare, crypto-agility playbook, CNSA 2.0 timeline) + a PQC-TLS note on network-security.html.
- **DSPM**: new DSPM section on data-security.html (vs classification/CSPM/DLP, shadow-data problem, tool landscape). SSPM was already fully covered on saas-security (3 sections) - review's "SSPM under-developed" was inaccurate; skipped.
- **Thin comparison page**: added a "Representative tooling (2026)" section to cnapp-vs-xdr.html (CNAPP/XDR/CDR vendor map) + TOC entry; "Through 2025" -> "and into 2026".
- **faq.html FAQPage**: expanded mainEntity 6 -> 34 (now matches all visible questions 1:1), regenerated from the visible Q&A so schema==visible.
- **Smaller**: "at least seven" -> "at least a dozen" (careers, help-desk); no-experience pay section now links careers#salary with the entry-band caveat.
- **Stamps**: bumped Last-updated + article:modified_time on the 3 pages with major new sections (data-security, network-security, cnapp-vs-xdr); left published dates intact.

Validation: check_jsonld OK, check_no_inline_scripts OK (223 files), 0 nested anchors + 0 em-dashes on all new-content pages, FAQPage 34 items valid, search index rebuilt (1620 docs). PQC/DSPM sections browser-verified rendering (display:block, correct headings, TOC anchors + cross-links resolve).

## Overall verdict

The site is in the best shape it has ever been. Technical plumbing is near-perfect (sitemap 1:1, canonicals clean site-wide, feeds fresh to the hour, CI 100% green over the last 25+ runs, update-news token issue fixed and verified). Content is current within days on all automated surfaces and the career + technical sections are genuinely best-in-class for a free community site. The findings below are concentrated in four themes: (1) a handful of real defects introduced by recent workflow gaps, (2) the newest, highest-value pages being invisible from the nav, (3) an 11-month editorial dead zone in the breach franchise, and (4) repo-doc claims that lag the code by one feature cycle - including a falsified "zero analytics" privacy claim.

## P1 - Real defects (fix first)

1. **8 meeting recaps ship broken og:image references.** Every recap since 2026-05-15 (05-15, 05-22, 05-29, 06-05, 06-12, 06-19, 06-26, 07-03) points og:image at `img/og/meetings/<date>.jpg`, but images stop at 2026-05-08.jpg (94 images vs 102 pages). Social previews for two months of recaps render imageless. Root cause: `tools/generate_meeting_og_images.py` is not wired into add_meeting.py or any workflow, so the manual step silently fell out during the May recap backfill. Fix: generate the 8 images; wire the step into the add_meeting flow or housekeeping CI.

2. **README/SECURITY/CONTRIBUTING still claim "zero analytics / no trackers" while GoatCounter is live on every page.** README.md lines ~168/454/583/924/988/1060, SECURITY.md line 119 ("no analytics, no tracking pixels" - contradicting its own line 55 documenting the GoatCounter CSP allowance), CONTRIBUTING.md line 5. privacy.html was correctly updated to "cookieless page-view analytics"; the repo docs were not. On a security community's repo this is a trust claim that is now false. Fix: align all ~7 claims with privacy.html's wording.

3. **Three wrong glossary anchors.** terraform.html:428 links "Cloud Run" to `glossary.html#term-lambda`; serverless.html:896 links "Fargate" to `#term-ecs`; help-desk-to-cloud-security.html links "Defender for Cloud" to `#term-guardduty`. Surgical fixes (per glossary workflow - do not rerun the crosslinker).

4. **Phantom-source pull quote (again).** cloud-security-careers.html has a pull quote attributed "from the CSOH careers FAQ" - faq.html has no careers section. (The July 4 pass fixed one instance of this pattern; this is a second.) Reattribute to "the Quick answers below" or drop the attribution.

## P2 - Highest-value improvements

5. **The July-5 career cluster is nav-orphaned.** cloud-security-interview-questions.html, cloud-security-resume-guide.html, get-into-cloud-security-no-experience.html, is-cloud-security-a-good-career.html have 1-3 inbound links each and are absent from the Careers menu (which finds room for Degree Programs). Compounding: 11 of 12 role pages have an "interview loop" section, and none but cloud-security-engineer link the 51-question interview bank; help-desk's resume section never links the resume guide; learning-path's closing list omits all four. These are the exact pages the career-changer audience arrives for. Fix: add interview-questions + resume-guide (at minimum) to CANON_NAV Careers > Getting Started; add the interview-bank link to each role page's interview-loop intro; link resume-guide from help-desk; extend learning-path's "Ready to start?" list. (Nav edits via CANON_NAV + tools/sync_chrome.py.)

6. **Breach franchise stops at August 2025.** Newest incident anywhere in breach-timeline/breach-lessons/breaches/ is Salesloft Drift (Aug 2025) - an 11-month dead zone that stands out precisely because everything else is current. Fix: add 1-3 notable 2026 kill chains (candidates already flow through the site's own news feed) and refresh timeline/lessons.

7. **Hero CTA label/destination mismatch.** index.html's primary "Join Zoom Sessions" button (and nav "Join Friday Zoom") opens the Kit email-signup form off-site in a new tab; a first-timer expecting session info gets an email-capture form with no framing. sessions.html (which explains everything and hosts the same signup) is buried in the Community dropdown. Fix: point the hero CTA at sessions.html, or relabel honestly.

8. **Lacework survives as a live vendor recommendation on career pages.** The July 4 currency pass fixed vendor-landscape and cspm-vs-cnapp, but cloud-security-careers, learning-path, cloud-security-engineer, and cloud-security-cnapp-analyst still present Lacework as hiring/publishing release notes (acquired by Fortinet 2024, folded into FortiCNAPP). Also worth a parenthetical: Prisma Cloud -> Cortex Cloud rebrand on the cnapp-analyst vendor profile.

9. **Current-topic pages missing from Learn nav.** mcp-security.html and non-human-identity.html (two of the strongest 2026 pages) have no nav presence; cnapp-vs-xdr.html and cspm-vs-cwpp.html dead-end off cspm-vs-cnapp only. Add MCP Security + NHI to Learn > Governance & AI; add a cross-link strip across the three "vs" pages. Community menu has room for speakers.html + present.html (1 and 3 inbound links today).

## P3 - Content freshness and editorial

10. **chat-resources.html is ~10 weeks behind** (newest entry 2026-05-01 vs recaps through 07-03). Needs the export data (known open item).
11. **presentations.html has no 2026 section** - newest deck 2025-10-10. Needs talk data from Shawn (known open item).
12. **Post-quantum crypto gap.** No PQC/crypto-agility coverage on any topic page (only glossary/news). NIST ML-KEM/ML-DSA finalized 2024; AWS/GCP/Cloudflare ship PQC TLS. Add a subsection to data-security.html + a line on network-security.html.
13. **Verify Wiz-Google acquisition tense** on vendor-landscape.html:1181 and cspm-vs-cnapp.html:729 ("agreed to acquire ~$32B in 2025") - whether the deal closed by mid-2026 decides the wording. Shawn will know.
14. **Cert sequencing conflicts across the three plans** (learning-path: specialty months 3-9; help-desk: month 12+; certifications: CCSK-first vs fundamentals-first flips). One reconciling sentence per page fixes it.
15. **Author-bio drift: "7+ years" vs "8+ years"** split roughly evenly across ~14 career pages. One sed pass.
16. **Two comparison pages are markedly thinner than siblings** (cnapp-vs-xdr, cspm-vs-cwpp: 2 external links each, no representative-tooling depth). Add a "representative tooling (2026)" list + one worked scenario each.
17. **Smaller editorial:** "at least seven" roles claim vs 12 role guides (careers + help-desk); no-experience pay section is number-free (link careers#salary; note entry-adjacent bands dip below the hub's junior floor); cnapp-vs-xdr "Through 2025..." framing; DSPM/SSPM deserve named sections on data-security/saas-security; ~30 pages' "Last updated" stamps frozen at 2026-05-15/17 (refresh only with real touches); verify AWS SCS-C03 claim on certifications page; 3 interview paste-in artifacts are all AWS-only (add one Entra/Azure); non-US comp gets one line site-wide.

## P4 - Docs drift (README.md / DEVELOPMENT.md / SECURITY.md)

18. **Workflow count and coverage:** DEVELOPMENT.md says "14 workflows"; there are 15 (check-conference-staleness.yml missing from every doc, table, and SECURITY.md's auth table). Four tools have zero doc coverage: check_conference_staleness.py, check_meeting_staleness.py, sync_counts.py, inject_goatcounter.py.
19. **normalize-urls approval story contradicts itself in 4 places.** Reality (workflow body): no auto-approve. Fix DEVELOPMENT.md:196, README.md:863, and the workflow's own header comment; SECURITY.md is correct.
20. **crosslink_glossary.py "idempotent and safe to re-run"** (README:809, DEVELOPMENT:426) omits the destructive strip behavior the tools README documents correctly. Copy the caveat into both.
21. **README's resource-card example uses alt="Preview"**, which DEVELOPMENT.md:464 explicitly forbids.
22. **homelab/ absent from all repo docs** and page counts stale ("~175 pages" vs actual ~223: 97 root + 13 breaches + 102 meetings + 7 portfolio + 4 homelab).
23. **Small drift batch:** README "94+ entries" (102), glossary "13 sections" (14), CONTRIBUTING "deploys to GCP" (multi-cloud), DEVELOPMENT update_sri file list omits 404.js + goatcounter-count.js, ADD_MEETING_README under-documents mid-chain back-fill, FETCH_ZOOM_TRANSCRIPT_README missing 4 newer flags, GENERATE_PREVIEW_README missing --fix-html, docker-compose preview option undocumented, robots.txt/humans.txt "updated" stamps say April 2026.

## P5 - Plumbing polish

24. **Weekly SEO scorer is inconsistent:** 2026-07-09 scored On-Page 30/100 (70 warnings) and 100/100 (0 warnings) in same-day runs. The warnings are real but cosmetic (~60 recap titles at 66-72 chars from the July 4 "- CSOH Recap, [date]" rewrite; 5 newer pages with 172-237-char meta descriptions). Make thresholds deterministic or SCORECARD.md trends are noise.
25. faq.html FAQPage JSON-LD covers 6 of 34 visible questions - extend mainEntity.
26. check_jsonld.py is parse-only; a cheap numberOfItems/position invariant check would catch ItemList drift.
27. update_sri.py has no --check flag (any arg, including --help, runs the real update). Add a read-only mode.
28. search.html has one crawlable static inbound link (JS-injected otherwise) - add a static footer link.
29. sitemap conferences lastmod stamped 2026-07-10 (future) - housekeeping runs at ~02:00 UTC; pin the stamp timezone.

## Carried over from the 2026-07-04 roadmap (still open, mostly need input from Shawn)

- Consent/PII policy for named community members (gates amplification work).
- presentations.html 2026 talk data; chat-resources export; "Submit a question for Friday" Google Form URL; quarterly community-pulse data.
- meetings/2026-02-20 and 2026-02-27 byte-identical recap bodies (needs the real notes).
- Remaining thin orphans: ai-learning, degree-programs, terraform (well-linked but orphan-adjacent), service-mesh-security, threat-modeling; sibling-link reciprocation (aws->iam return, version-control->github-actions return).
- Extend check_pagespeed.py beyond homepage; AI-citation baseline CSV.

## Confirmed healthy (no action)

- CI fully green 25+ runs; update-news token fix verified (App creates, PAT approves).
- Sitemap/canonicals/meta-OG/twitter:card/preview-mapping: 1:1 site-wide, zero mismatches. feed.xml fresh, 120 items. security.txt valid to 2027-02, manifest icons exist, llms.txt targets all resolve.
- All conference "Next:" dates current (18 dated 2026-07-28..2027-04-13; 7 honest TBAs). News current to the day. Recaps weekly and gap-free through 2026-07-03. Copyright current.
- Technical accuracy spot-checks clean across 10 pages (Entra ID naming, PSS/PSP, Kyverno, IMDSv2, OpenTofu/BSL, Capital One chain, tool liveness). Cert facts verified (CCSK/CCSP/AZ-500/PCSE/CKS pricing+format). Salary bands mutually consistent and OTE-correct.
- homelab labs: coherent progression, current commands, strong safety framing.
- Strongest pages: aws-security, iam, non-human-identity, terraform, zero-trust, break-and-detect-aws lab.
