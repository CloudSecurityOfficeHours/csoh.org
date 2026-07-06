# Awesome-list backlink submissions for CSOH

A ready-to-paste kit for submitting CSOH to the major "awesome cloud security"
GitHub lists. Backlinks from these repos are durable, security-credible, and
increase Google's trust in csoh.org for cloud-security queries.

These have to be submitted from your GitHub identity. The list below gives
you the target repo, the right section to add into, the exact entry text to
paste, and a copy-pasteable PR title + body.

---

## Submission workflow (do this once per repo)

```bash
# 1. Fork the repo on GitHub (click the Fork button)

# 2. Clone YOUR fork locally (replace YOUR-USERNAME)
git clone https://github.com/YOUR-USERNAME/awesome-cloud-security.git
cd awesome-cloud-security

# 3. Create a topic branch
git checkout -b add-cloud-security-office-hours

# 4. Edit README.md - paste the entry text from below into the right section,
#    keeping the list's existing format (numbered list, dash list, etc.)

# 5. Commit
git add README.md
git commit -m "Add Cloud Security Office Hours community resource"

# 6. Push to your fork
git push -u origin add-cloud-security-office-hours

# 7. Open a PR from your fork to the upstream repo via the GitHub UI
#    (a "Compare & pull request" banner will appear after your push)
```

**Tone for PR descriptions:** brief, factual, alphabetical-position request
if the list expects ordered entries. Avoid superlatives. Maintainers reject
self-promotional language.

---

## Target 1 - `4ndersonLin/awesome-cloud-security` (high priority)

**Default branch:** `master`
**Where to add:** under `## Others` in the **Reading Materials** section
(the existing entries there are general-cloud, multi-cloud, or community
resources - the right home for CSOH).

**Format:** ordered list (`1.`, `2.`, `3.` ...), continue numbering from the
last existing entry.

**Entry text (paste at the end of "Others"):**

```markdown
5. [Cloud Security Office Hours (CSOH)](https://csoh.org/): Vendor-neutral community with weekly Zoom sessions, a 230+ term [glossary](https://csoh.org/glossary.html), pillar guides ([What is Cloud Security?](https://csoh.org/what-is-cloud-security.html), [Best Practices](https://csoh.org/cloud-security-best-practices.html), [Shared Responsibility](https://csoh.org/shared-responsibility-model.html), [CSPM vs CNAPP](https://csoh.org/cspm-vs-cnapp.html)), [breach kill chains](https://csoh.org/breach-timeline.html) mapped to MITRE ATT&CK, and a [37+ CTF directory](https://csoh.org/ctfs.html).
```

**PR title:** `Add Cloud Security Office Hours under Reading Materials → Others`

**PR body:**

```
This adds Cloud Security Office Hours (https://csoh.org) under
Reading Materials → Others. It's a vendor-neutral community resource
hub with weekly Zoom sessions, pillar guides, a 230+ term glossary,
breach kill chains mapped to MITRE ATT&CK Cloud, and a curated
CTF directory. Free, open, no trackers, no on-site ads.

Slotted at position 5 in Others, alphabetically after the existing
Cloud Risk Encyclopedia entry.
```

---

## Target 2 - `iknowjason/Awesome-CloudSec-Labs`

This list is focused on hands-on labs and CTFs. CSOH's CTF directory and
Friday Zoom community are what fit.

**Where to add:** Look for sections named something like `Communities`,
`Resources`, `Conferences`, or `Other`. If there's a `Communities` or
`Discord/Slack` section, that's the natural home. Otherwise paste under the
most general "Resources" / "Other" section near the end.

**Entry text (adapt bullet style to match the list's conventions):**

```markdown
- [Cloud Security Office Hours](https://csoh.org/) - Vendor-neutral community with weekly Friday Zoom sessions, a [37+ cloud CTF directory](https://csoh.org/ctfs.html), [breach kill chains](https://csoh.org/breach-timeline.html) mapped to MITRE ATT&CK, and pillar guides on cloud security fundamentals. Free and open.
```

**PR title:** `Add Cloud Security Office Hours community + CTF directory`

**PR body:**

```
Adds Cloud Security Office Hours (https://csoh.org) - a vendor-neutral
cloud-security community founded in 2023.

Relevant for this list:
- 37+ curated cloud CTFs at https://csoh.org/ctfs.html (covers AWS, Azure,
  GCP, Kubernetes, AI security)
- Breach kill chains mapped to MITRE ATT&CK Cloud at
  https://csoh.org/breach-timeline.html
- Free weekly Friday Zoom community for practitioners

Happy to move it to a different section if there's a better fit.
```

---

## Target 3 - `The-Art-of-Hacking/h4cker`

Maintained by Omar Santos (Cisco PSIRT). Massive list of cybersecurity
GitHub repos. They accept community resource submissions.

**Where to add:** Look for sections like `Cloud Security`, `Cybersecurity
Communities`, `Learning Resources`, or similar. The repo has many sub-files;
the `cybersecurity_books_and_videos` and `cloud_security` files are the
most likely targets. Read the README for current structure.

**Entry text:**

```markdown
- [Cloud Security Office Hours (CSOH)](https://csoh.org/) - Vendor-neutral community resource hub for cloud security: weekly Friday Zoom sessions, [pillar guides](https://csoh.org/) (What is Cloud Security?, Best Practices, Shared Responsibility, CSPM vs CNAPP), a [230+ term glossary](https://csoh.org/glossary.html), [breach kill chains](https://csoh.org/breach-timeline.html), and a [37+ CTF directory](https://csoh.org/ctfs.html). Free and open, vendor-neutral, no trackers, no on-site ads.
```

**PR title:** `Add Cloud Security Office Hours to Cloud Security resources`

**PR body:**

```
Adds Cloud Security Office Hours (https://csoh.org) as a cloud security
community + reference resource. Vendor-neutral, free, no trackers, no on-site ads.
Includes pillar guides, glossary, breach kill chains, CTF directory,
and weekly Zoom sessions.

Let me know if there's a more specific section you'd prefer it in.
```

---

## Target 4 - `sbilly/awesome-security`

Long-running, broad infosec list. Cloud security is a sub-section.

**Where to add:** Look for `Cloud Security` or sub-sections like
`Cloud-Security` or `Cloud-Native Security`. If there's an `Online
Resources` or `Communities` sub-section, prefer that.

**Entry text:**

```markdown
- [Cloud Security Office Hours](https://csoh.org/) - Vendor-neutral cloud-security community with weekly Zoom sessions, pillar guides, glossary, breach kill chains mapped to MITRE ATT&CK, and a curated CTF directory.
```

**PR title:** `Add Cloud Security Office Hours under Cloud Security`

---

## Target 5 - `paragonie/awesome-appsec`

App-sec focused. CSOH's coverage of cloud-native app security and AI/LLM
security is the relevant angle.

**Where to add:** `Online Resources` → `Online Tutorials` or `Books and
Reading Material`, depending on current structure.

**Entry text:**

```markdown
- [Cloud Security Office Hours](https://csoh.org/) - Free vendor-neutral cloud-security community covering AppSec topics including [supply-chain security](https://csoh.org/cloud-security-best-practices.html#supply-chain), [Kubernetes hardening](https://csoh.org/cloud-security-best-practices.html#workloads), and [AI/LLM workload security](https://csoh.org/cloud-security-best-practices.html#ai). Pillar guides + glossary + breach kill chains.
```

---

## Target 6 - `rmusser01/Infosec_Reference`

Comprehensive reference repo by Robert Musser. Has dedicated cloud security
sections.

**Where to add:** Cloud Security section, likely under `Resources` or
`Communities`. The README is large - grep for "Cloud Security" or look at
existing `cloud-security.md` if there's a dedicated file.

**Entry text:**

```markdown
- [Cloud Security Office Hours](https://csoh.org/) - Community-run vendor-neutral cloud-security hub. Weekly Friday Zoom (7am PT), pillar guides, [230+ term glossary](https://csoh.org/glossary.html), [13 breach kill chains](https://csoh.org/breach-timeline.html) mapped to MITRE ATT&CK Cloud, [91 weekly meeting recaps](https://csoh.org/meetings.html), [37+ CTFs](https://csoh.org/ctfs.html).
```

---

## Bonus: smaller / niche lists worth submitting to

These have less reach individually but together add up to a credible
backlink profile. Same workflow.

| Repo | Section to target |
|---|---|
| `0voice/cloud_native_security_study` | Resources / Communities |
| `forter/security-101-for-saas-startups` | Learning Resources (has a "communities" list) |
| `wtsxDev/Penetration-Testing` | Cloud Security |
| `jpiechowka/free-cybersec-resources` | Cloud Security |
| `hslatman/awesome-threat-intelligence` | only relevant if the list has a "communities" or "blog" section - skip if not a clean fit |
| `Hack-with-Github/Awesome-Hacking` | Cloud Security |

---

## After submitting

- **Don't comment "any update?" on the PR for at least 2 weeks.** Most
  awesome-list maintainers batch-merge. Aggressive nudging gets PRs closed.
- **If a PR is rejected**, ask politely what would make it accept-worthy,
  or move on. Don't argue.
- **Keep a tracker** so you don't accidentally submit twice. A CSV or a
  pinned note works:

```
repo                               | pr_url                | submitted   | status
4ndersonLin/awesome-cloud-security | https://github.com/.. | 2026-04-30  | open
iknowjason/Awesome-CloudSec-Labs   | https://github.com/.. | 2026-04-30  | merged
```

- **Once accepted**, the backlink takes 1-4 weeks to influence Google
  rankings. Don't expect overnight.

---

## Why not submit to more?

Diminishing returns kick in fast. A backlink from a well-maintained
list with 5,000+ stars and 500+ forks is worth ~10x one from a list
with 50 stars. Focus the effort on the top 3-4 in this document.

The rest of the search-visibility lift comes from on-page SEO (which
we've handled) and original linkable content (which the pillars and
breach kill chains are designed to be).
