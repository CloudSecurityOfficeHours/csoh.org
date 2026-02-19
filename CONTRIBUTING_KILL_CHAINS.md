# Contributing a Breach Kill Chain

Thank you for helping grow the CSOH Breach Kill Chain resource! This guide explains exactly what makes a good kill chain entry and how to submit one.

---

## What is a kill chain entry?

A kill chain is a **step-by-step reconstruction of a real cloud security breach** — from the attacker's first move to the moment of discovery. It's not a news summary. It's a structured breakdown of *exactly how* the attack progressed, mapped to MITRE ATT&CK Cloud techniques, so security professionals can learn from it and defend against it.

Each entry has:
- A numbered sequence of attack steps (typically 4–8 steps)
- Each step mapped to a real MITRE ATT&CK technique with a link
- Technical detail in each step (what command, what API, what misconfiguration)
- A "Key Lessons / How to Defend" section at the bottom
- Links to primary sources (official post-mortems, vendor blogs, court documents, CISA advisories)

---

## The bar for a good submission

Before you start, check these boxes:

- [ ] **There is a real post-mortem or official disclosure.** The attack chain must be sourced — not reconstructed from speculation. Good sources: vendor security blogs (MSRC, AWS Security Blog, Wiz, CrowdStrike, Mandiant), CISA advisories, court documents/indictments, academic papers. News articles alone are not sufficient.
- [ ] **It involves cloud infrastructure.** AWS, Azure, GCP, GitHub Actions, cloud identity (Azure AD / Okta / Duo), or cloud-adjacent supply chain attacks that pivot into cloud environments.
- [ ] **There is enough technical detail** to write meaningful steps. If the only public information is "company X was breached and data was stolen," there isn't enough to work with yet. Wait for a post-mortem.
- [ ] **It adds something new.** Check the existing entries first — don't duplicate an incident already covered.

---

## Good candidate breaches (as of early 2026)

These incidents have solid post-mortems and haven't been added yet. Pick one up!

| Incident | Year | Provider | Good Source |
|---|---|---|---|
| Okta Support System Breach | 2023 | Okta / AWS | [Okta security advisory](https://sec.okta.com/harfiles) |
| Snowflake Credential Stuffing Campaign | 2024 | Snowflake | [Mandiant report](https://cloud.google.com/blog/topics/threat-intelligence/unc5537-snowflake-data-theft-extortion) |
| 3CX Supply Chain (Lazarus) | 2023 | AWS CloudFront | [Mandiant analysis](https://www.mandiant.com/resources/blog/3cx-software-supply-chain-compromise) |
| CircleCI Secrets Breach | 2023 | CI/CD | [CircleCI post-mortem](https://circleci.com/blog/january-4-2023-security-alert/) |
| Toyota Connected Car Data Exposure | 2023 | GCP | [Toyota statement](https://global.toyota/en/newsroom/corporate/39174380.html) |
| Twilio / Authy SMS Phishing | 2022 | AWS | [Twilio post-mortem](https://www.twilio.com/blog/august-2022-social-engineering-attack) |
| LastPass Breach (DevOps Engineer) | 2022–2023 | AWS S3 | [LastPass disclosure](https://blog.lastpass.com/posts/2023/03/security-incident-update-recommended-actions) |

---

## How to write the steps

Each step should answer three questions:

1. **What did the attacker do?** (the action)
2. **How did they do it technically?** (the mechanism — command, API endpoint, exploit, technique)
3. **Why did it work?** (the security failure that enabled it)

**Good step example:**
> **EC2 IAM role credentials retrieved from IMDS — no authentication required**
> Thompson used the SSRF to GET `/latest/meta-data/iam/security-credentials/ISRM-WAF-Role`, which returned temporary AWS credentials (AccessKeyId, SecretAccessKey, SessionToken). IMDSv1 served these to any request made from the instance — no token required. The role had been granted far broader S3 permissions than a WAF function ever needs.
> `MITRE: T1552.005 – Cloud Instance Metadata API`

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
| SSRF to metadata service | T1552.005 – Cloud Instance Metadata API |
| Misconfigured S3 / storage bucket | T1530 – Data from Cloud Storage |
| Stolen/reused credentials | T1078 – Valid Accounts |
| MFA push fatigue / bombing | T1621 – MFA Request Generation |
| Secret in source code / file | T1552.001 – Credentials in Files |
| Public repository secret exposure | T1552.004 – Private Keys |
| SAML token forgery (Golden SAML) | T1606.002 – SAML Tokens |
| OAuth token forgery | T1606.001 – Web Cookies / Tokens |
| Supply chain software compromise | T1195.002 – Compromise Software Supply Chain |
| Cloud storage enumeration | T1619 – Cloud Storage Object Discovery |
| Exfiltration from cloud storage | T1530 – Data from Cloud Storage |
| Email collection (Exchange/M365) | T1114.002 – Remote Email Collection |
| DNS-based C2 | T1071.004 – DNS |
| Adding persistent OAuth app | T1098.001 – Additional Cloud Credentials |

---

## HTML structure for a new panel

Copy this template and fill it in. Add it inside the `<main class="kc-main">` element in `breach-timeline.html`, before the `<!-- Contribute CTA -->` comment.

Also add a tab button to the `<nav class="incident-tabs">` section at the top.

### Tab button (add to nav)

```html
<button class="itab" data-panel="YOUR-PANEL-ID" data-year="YYYY" role="tab">
  Incident Name YEAR
  <span class="itab-prov prov-aws">AWS</span>
  <!-- Use prov-azure for Azure incidents -->
</button>
```

> **Important:** The `data-year="YYYY"` attribute is required — it's what the page uses to automatically sort tabs into chronological order. Replace `YYYY` with the 4-digit year the incident occurred. If you forget it, your tab will sort to the beginning.

### Full panel template

```html
<!-- ═══════════════ YOUR INCIDENT NAME ═══════════════ -->
<div id="YOUR-PANEL-ID" class="incident-panel" role="tabpanel">
  <div class="inc-header">
    <div class="inc-meta">
      <span class="inc-year">Month YYYY</span>
      <span class="sev-badge sev-critical">Critical</span>
      <!-- Severity options: sev-critical, sev-high, sev-medium -->
      <span class="prov-tag prov-aws">AWS</span>
      <!-- Provider options: prov-aws (yellow), prov-azure (blue) -->
      <!-- For GCP: style="background:rgba(34,197,94,.15);color:#4ade80;" -->
    </div>
    <h2 class="inc-title">Short Name – Step1 → Step2 → Step3 → Impact</h2>
    <p class="inc-summary">
      2–4 sentence plain English summary of what happened, who did it,
      what went wrong, and what the impact was.
    </p>
    <div class="inc-stats">
      <div class="inc-stat"><strong>X</strong> records/orgs/impact metric</div>
      <div class="inc-stat"><strong>X days</strong> dwell time</div>
      <div class="inc-stat"><strong>Threat actor:</strong> Name / type</div>
    </div>
    <a class="pm-link" href="POST_MORTEM_URL" target="_blank" rel="noopener">📄 Source name ↗</a>
  </div>

  <div class="kill-chain">

    <!-- Repeat this block for each step. Change phase-lbl text and class as appropriate. -->
    <!-- Phase label classes: ph-recon ph-init ph-exec ph-cred ph-priv ph-persist ph-exfil ph-disco -->
    <!-- Step colour classes: step-r (red) step-o (orange) step-y (yellow) step-p (purple) step-b (blue) step-c (cyan) step-g (green) -->

    <div class="phase-lbl ph-init">⚡ Initial Access</div>
    <div class="kc-step step-r">
      <div class="step-num">01</div>
      <div class="step-body">
        <div class="step-hdr">
          <div class="step-title">One sentence describing what the attacker did</div>
          <a class="mt mt-ta" href="https://attack.mitre.org/techniques/TXXXX/" target="_blank" rel="noopener">TXXXX – Technique Name</a>
          <!-- MITRE tag classes: mt-ta mt-ex mt-pe mt-de mt-ca mt-di mt-lm mt-co mt-ef mt-p2 -->
        </div>
        <p class="step-desc">
          2–4 sentences explaining what happened, how it worked technically,
          and why the security control failed.
        </p>
        <div class="step-code">
          <span class="hl">Key detail label:</span> Value or command<br>
          <span class="hl">Why it worked:</span> The specific failure that enabled this step<br>
          <span class="hl">Defence gap:</span> What was missing
        </div>
        <div class="step-tags">
          <span class="stag">Tag1</span>
          <span class="stag">Tag2</span>
          <span class="stag">TXXXX</span>
        </div>
      </div>
    </div>

    <!-- Add more phase labels and steps following the same pattern -->

    <div class="def-box">
      <h3>🛡 How to Defend Against This Chain</h3>
      <div class="def-items">
        <div class="def-item"><strong>Specific control 1.</strong> Explanation of what to do and why it would have stopped this attack.</div>
        <div class="def-item"><strong>Specific control 2.</strong> Be concrete — name the AWS service, Azure policy, or tool. Not "improve monitoring" but "enable GuardDuty finding X."</div>
        <!-- Add 3–5 defender items -->
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
</div>
```

---

## Don't want to write the HTML yourself? Use Claude

If you've found a good post-mortem but don't want to write the HTML, you can use Claude (claude.ai) to do the heavy lifting. Here's how:

1. **Download `breach-timeline.html`** from the repo (go to the file on GitHub, click the download icon)
2. **Open a new conversation** at [claude.ai](https://claude.ai)
3. **Upload the file** using the attachment button
4. **Send a message** like:

   > *"Please add a kill chain for the Snowflake 2024 credential stuffing campaign to this file. Here's the post-mortem: [paste URL]"*

5. Claude will research the incident, write the new panel in the exact same style as the existing entries, map each step to MITRE ATT&CK techniques, and return the updated file
6. **Review the output** — check the sources, verify the MITRE mappings, and make any corrections
7. **Submit the updated file as a PR** following the steps below

> **Important:** Always review what Claude produces before submitting. Check that every source link works, every MITRE technique ID is correct, and the technical details match what the post-mortem actually says. Claude can make mistakes, especially on specific command syntax or dates — you're the human reviewer.

This approach is particularly useful if you attended a Friday Zoom session where a breach was discussed — you have the context, Claude can handle the formatting.

---

## Submitting your PR

1. **Fork** the [CSOH GitHub repository](https://github.com/CloudSecurityOfficeHours/csoh.org)
2. **Create a branch** named `kill-chain/incident-name-year` (e.g., `kill-chain/okta-2023`)
3. **Edit `breach-timeline.html`** — add your tab button and panel following the template above
4. **Open a pull request** with the title format: `Add kill chain: [Incident Name] [Year]`
5. In the PR description, include:
   - A one-paragraph summary of the incident
   - Links to your primary sources
   - The MITRE techniques you mapped to each step
   - Whether you attended a Friday Zoom session where this was discussed (so we can link the recording)

---

## Quality checklist before submitting

- [ ] Every step has a MITRE ATT&CK technique ID that links to attack.mitre.org
- [ ] Every claim is sourced — no speculation or unverified assertions
- [ ] The `step-code` block contains technical specifics (commands, API paths, tool names) not just narrative
- [ ] The defender section names specific controls, tools, or cloud service features — not generic advice
- [ ] At least 2 primary sources are linked (post-mortem, vendor blog, official advisory, or academic paper)
- [ ] The incident involves cloud infrastructure (not purely on-premises)
- [ ] HTML validates — test by opening the file locally in a browser before submitting

---

## Questions?

Join the **#kill-chains** channel on [Discord](https://discord.gg/AVzAY97D8E) or bring your incident to a [Friday Zoom session](https://sendfox.com/CSOH) — community discussion often surfaces the best technical detail for a step.
