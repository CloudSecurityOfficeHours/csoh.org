# Contributing a Breach Kill Chain

Thank you for helping grow the CSOH Breach Kill Chain resource! This guide explains exactly what makes a good kill chain entry and how to submit one.

---

## What is a kill chain entry?

A kill chain is a **step-by-step reconstruction of a real cloud security breach** - from the attacker's first move to the moment of discovery. It's not a news summary. It's a structured breakdown of *exactly how* the attack progressed, mapped to MITRE ATT&CK Cloud techniques, so security professionals can learn from it and defend against it.

Each entry has:
- A numbered sequence of attack steps (typically 4-8 steps)
- Each step mapped to a real MITRE ATT&CK technique with a link
- Technical detail in each step (what command, what API, what misconfiguration)
- A "Key Lessons / How to Defend" section at the bottom
- Links to primary sources (official post-mortems, vendor blogs, court documents, CISA advisories)

---

## The bar for a good submission

Before you start, check these boxes:

- [ ] **There is a real post-mortem or official disclosure.** The attack chain must be sourced - not reconstructed from speculation. Good sources: vendor security blogs (MSRC, AWS Security Blog, Wiz, CrowdStrike, Mandiant), CISA advisories, court documents/indictments, academic papers. News articles alone are not sufficient.
- [ ] **It involves cloud infrastructure.** AWS, Azure, GCP, GitHub Actions, cloud identity (Azure AD / Okta / Duo), or cloud-adjacent supply chain attacks that pivot into cloud environments.
- [ ] **There is enough technical detail** to write meaningful steps. If the only public information is "company X was breached and data was stolen," there isn't enough to work with yet. Wait for a post-mortem.
- [ ] **It adds something new.** Check the existing entries first - don't duplicate an incident already covered.

---

## Good candidate breaches (as of mid-2026)

These incidents have solid post-mortems and haven't been added yet. Pick one up!

| Incident | Year | Provider | Where to find the source |
|---|---|---|---|
| Midnight Blizzard (APT29) Microsoft corporate | 2024 | Azure / Entra | Microsoft MSRC blog - password-spray into a legacy tenant, then OAuth app abuse |
| Sisense customer credential compromise | 2024 | Cloud BI | CISA advisory - cascading cloud-BI supply-chain exposure |

---

## How to write the steps

Each step should answer three questions:

1. **What did the attacker do?** (the action)
2. **How did they do it technically?** (the mechanism - command, API endpoint, exploit, technique)
3. **Why did it work?** (the security failure that enabled it)

**Good step example:**
> **EC2 IAM role credentials retrieved from IMDS - no authentication required**
> Thompson used the SSRF to GET `/latest/meta-data/iam/security-credentials/ISRM-WAF-Role`, which returned temporary AWS credentials (AccessKeyId, SecretAccessKey, SessionToken). IMDSv1 served these to any request made from the instance - no token required. The role had been granted far broader S3 permissions than a WAF function ever needs.
> `MITRE: T1552.005 - Cloud Instance Metadata API`

**Bad step example (too vague):**
> The attacker got AWS credentials and used them to access data.

---

## How to find the MITRE ATT&CK technique

1. Go to [attack.mitre.org/matrices/enterprise/cloud/](https://attack.mitre.org/matrices/enterprise/cloud/)
2. Browse the tactic columns (Initial Access, Credential Access, Exfiltration, etc.)
3. Find the technique that best describes what happened
4. Use the full technique ID including sub-technique if applicable (e.g., T1552.005 not just T1552)
5. Link directly to the technique page

Common cloud techniques:

| What happened | MITRE Technique |
|---|---|
| SSRF to metadata service | T1552.005 - Cloud Instance Metadata API |
| Misconfigured S3 / storage bucket | T1530 - Data from Cloud Storage |
| Stolen/reused credentials | T1078 - Valid Accounts |
| MFA push fatigue / bombing | T1621 - MFA Request Generation |
| Secret in source code / file | T1552.001 - Credentials in Files |
| Public repository secret exposure | T1552.004 - Private Keys |
| SAML token forgery (Golden SAML) | T1606.002 - SAML Tokens |
| OAuth token forgery | T1606.001 - Web Cookies / Tokens |
| Supply chain software compromise | T1195.002 - Compromise Software Supply Chain |
| Cloud storage enumeration | T1619 - Cloud Storage Object Discovery |
| Exfiltration from cloud storage | T1530 - Data from Cloud Storage |
| Email collection (Exchange/M365) | T1114.002 - Remote Email Collection |
| DNS-based C2 | T1071.004 - DNS |
| Adding persistent OAuth app | T1098.001 - Additional Account Credentials |

---

## How the breach library is structured

Each kill chain is its **own page** at `breaches/<incident-slug>.html` (e.g. `breaches/capital-one.html`). The single-page tabbed layout (`kc-main`, `incident-tabs`, `incident-panel`) described in older versions of this guide is gone. `breach-timeline.html` is now an **index**: a grid of cards, one per breach, each linking to its page.

Adding a kill chain therefore has two parts: **(1) create the breach page**, then **(2) register it** on the timeline, in the sitemap, and in the prev/next pager.

### 1. Create `breaches/<slug>.html`

The reliable way is to **copy the newest existing page in `breaches/`** and edit it in place - that inherits the correct `<head>`, nav, footer, shared-asset integrity hashes, and the `incident-pager` markup, so you only touch the content. In the copy, update:

- `<title>`, `<meta name="description">`, `<link rel="canonical">`, the Open Graph / Twitter tags, and the OG image path.
- The two JSON-LD blocks (`Article` and `BreadcrumbList`) - change the name, description, URL, and dates. **Every JSON-LD string must use double quotes**; `tools/check_jsonld.py` (a build gate) fails on single quotes.
- The `<h1>` (e.g. `Capital One 2019`).
- The `<main class="kc-main kc-page">` body (below).

### Page body: header + kill chain

Everything below goes inside `<main class="kc-main kc-page" id="main-content">`. Note glossary links use `../glossary.html#term-...` (the `../` is required - the page is one level down).

```html
<div class="inc-header">
  <div class="inc-meta">
    <span class="inc-year">Month YYYY</span>
    <span class="sev-badge sev-critical">Critical</span>   <!-- sev-critical | sev-high | sev-medium -->
    <span class="prov-tag prov-aws">AWS</span>             <!-- prov-aws | prov-azure | prov-gcp | prov-purple (on-prem) -->
  </div>
  <h2 class="inc-title">Short Name - Step1 &rarr; Step2 &rarr; Step3 &rarr; Impact</h2>
  <p class="inc-summary">2-4 sentence plain-English summary: who did it, what went wrong, the impact.</p>
  <div class="inc-stats">
    <div class="inc-stat"><strong>X</strong> records / orgs impacted</div>
    <div class="inc-stat"><strong>X days</strong> dwell time</div>
    <div class="inc-stat"><strong>Threat actor:</strong> Name / type</div>
  </div>
  <a class="pm-link" href="POST_MORTEM_URL" target="_blank" rel="noopener">Source name</a>
</div>

<div class="kill-chain">

  <!-- Repeat phase-lbl + kc-step for each step. -->
  <!-- Phase label classes: ph-recon ph-init ph-exec ph-cred ph-priv ph-persist ph-exfil ph-disco -->
  <!-- Step colour classes: step-r step-o step-y step-p step-b step-c step-g -->

  <div class="phase-lbl ph-init">Initial Access</div>
  <div class="kc-step step-r">
    <div class="step-num">01</div>
    <div class="step-body">
      <div class="step-hdr">
        <div class="step-title">One sentence describing what the attacker did</div>
        <a class="mt mt-ta" href="https://attack.mitre.org/techniques/TXXXX/" target="_blank" rel="noopener">TXXXX - Technique Name</a>
        <!-- MITRE tag classes: mt-ta mt-ex mt-pe mt-de mt-ca mt-di mt-lm mt-co mt-ef mt-p2 -->
      </div>
      <p class="step-desc">2-4 sentences: what happened, how it worked technically, why the control failed.</p>
      <div class="step-code">
        <span class="hl">Key detail:</span> value or command<br>
        <span class="hl">Why it worked:</span> the specific failure that enabled this step<br>
        <span class="hl">Defence gap:</span> what was missing
      </div>
      <div class="step-tags">
        <span class="stag">Tag</span>
        <span class="stag">TXXXX</span>
      </div>
    </div>
  </div>

  <!-- Add more phase labels and steps following the same pattern -->

  <div class="def-box">
    <h3>How to Defend Against This Chain</h3>
    <div class="def-items">
      <div class="def-item"><strong>Specific control.</strong> Name the AWS service, Azure policy, or tool - not "improve monitoring" but "enable GuardDuty finding X." Add 3-5 items.</div>
    </div>
  </div>

  <div class="src-box">
    <h4>Primary Sources</h4>
    <div class="src-links">
      <a class="src-link" href="URL" target="_blank" rel="noopener">Source Name</a>
      <!-- Add all sources used -->
    </div>
  </div>

</div>
```

Leave the `<nav class="incident-pager">` block that the copied page already has - you fix its links in step 2.

### 2. Register the page

- **Timeline card.** In `breach-timeline.html`, add a `<li class="breach-card" id="<slug>">` in date order, matching the existing cards exactly (meta row with `inc-year` / `sev-badge` / `prov-tag`, then `breach-card-title`, `breach-card-summary`, and the `breach-card-cta`), linking to `breaches/<slug>.html`.
- **ItemList schema.** In the same file's `ItemList` JSON-LD, add a `ListItem` for the new page and **increment `numberOfItems`** by 1. The count must equal the number of cards.
- **Pager.** Fix the `incident-pager` prev/next links on the new page and on the two pages it now sits between, so the chain stays in order.
- **Sitemap.** Add `https://csoh.org/breaches/<slug>.html` to `sitemap.xml`.
- **Nav/footer.** Run `python3 tools/sync_chrome.py` so the shared header/footer stay identical site-wide.

---

## Don't want to write the HTML yourself? Use Claude

If you've found a good post-mortem but don't want to write the HTML, you can use Claude (claude.ai) to do the heavy lifting. Here's how:

1. **Download the newest page in `breaches/`** from the repo (open the file on GitHub, click the download icon) to use as the style template
2. **Open a new conversation** at [claude.ai](https://claude.ai)
3. **Upload the file** using the attachment button
4. **Send a message** like:

   > *"Using this breach page as the template, write a new `breaches/salesloft-drift.html` for the Salesloft/Drift 2025 OAuth token theft campaign, keeping the exact same page structure, classes, and JSON-LD. Here's the post-mortem: [paste URL]"*

5. Claude will research the incident, write a new breach page in the exact same style as the template, map each step to MITRE ATT&CK techniques, and return the file (remind it to also give you the `breach-card` and `ItemList` entries for `breach-timeline.html`)
6. **Review the output** - check the sources, verify the MITRE mappings, and make any corrections
7. **Submit the updated file as a PR** following the steps below

> **Important:** Always review what Claude produces before submitting. Check that every source link works, every MITRE technique ID is correct, and the technical details match what the post-mortem actually says. Claude can make mistakes, especially on specific command syntax or dates - you're the human reviewer.

This approach is particularly useful if you attended a Friday Zoom session where a breach was discussed - you have the context, Claude can handle the formatting.

---

## Submitting your PR

1. **Fork** the [CSOH GitHub repository](https://github.com/CloudSecurityOfficeHours/csoh.org)
2. **Create a branch** named `kill-chain/incident-name-year` (e.g., `kill-chain/okta-2023`)
3. **Create `breaches/<slug>.html`** and register it (timeline card, ItemList + `numberOfItems`, pager, sitemap, `sync_chrome.py`) following the two-step structure above
4. **Open a pull request** with the title format: `Add kill chain: [Incident Name] [Year]`
5. In the PR description, include:
   - A one-paragraph summary of the incident
   - Links to your primary sources
   - The MITRE techniques you mapped to each step
   - Whether you attended a Friday Zoom session where this was discussed (so we can link the recording)

---

## Quality checklist before submitting

- [ ] Every step has a MITRE ATT&CK technique ID that links to attack.mitre.org
- [ ] Every claim is sourced - no speculation or unverified assertions
- [ ] The `step-code` block contains technical specifics (commands, API paths, tool names) not just narrative
- [ ] The defender section names specific controls, tools, or cloud service features - not generic advice
- [ ] At least 2 primary sources are linked (post-mortem, vendor blog, official advisory, or academic paper)
- [ ] The incident involves cloud infrastructure (not purely on-premises)
- [ ] HTML validates - test by opening the file locally in a browser before submitting

---

## Questions?

Bring your incident to a [Friday Zoom session](https://csoh.kit.com/39feb4f397) - community discussion often surfaces the best technical detail for a step.
