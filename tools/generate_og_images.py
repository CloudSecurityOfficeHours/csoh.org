#!/usr/bin/env python3
"""Generate per-page Open Graph (social-share) images.

Renders a CSOH-branded 1200×630 image for each page in PAGES, saves them
under ../img/og/<slug>.jpg, and rewrites each page's <meta property="og:image">
+ <meta name="twitter:image"> to point at the new file.

Idempotent - re-running regenerates images for any page whose content
might have changed; pages whose OG image is already set to the per-page
version won't get a redundant URL update.

Usage:
    python3 tools/generate_og_images.py
    python3 tools/generate_og_images.py --pages index.html ctfs.html
    python3 tools/generate_og_images.py --skip-html       # only regenerate jpgs
"""

from __future__ import annotations

import argparse
import http.server
import re
import socket
import socketserver
import sys
import threading
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = REPO_ROOT / "tools" / "og" / "template.html"
OUT_DIR = REPO_ROOT / "img" / "og"
OG_VIEWPORT = {"width": 1200, "height": 630}

# (filename, title, subtitle, badge) - keep titles ≤ ~60 chars and subtitles
# ≤ ~140 chars so the template doesn't have to clamp aggressively. The
# subtitle prints under the headline; choose a one-line value prop, not
# the page meta description.
#
# To add a page: append a (filename, title, subtitle, badge) tuple in the
# matching section below. For a subdirectory page use the relative path
# (e.g. "breaches/foo.html"); the JPG is written alongside at
# img/og/breaches/foo.jpg. Then run: python3 tools/generate_og_images.py
# --pages breaches/foo.html   (regenerates just that one image).
PAGES = [
    ("index.html",
     "Cloud Security, Vendor-Neutral",
     "2,000+ practitioners. 500+ resources. Free weekly Zoom. No trackers.",
     "Community"),
    ("what-is-cloud-security.html",
     "What is Cloud Security?",
     "Shared responsibility, the threats that matter, the tool landscape - explained by practitioners.",
     "Pillar Guide"),
    ("topics.html",
     "Every Cloud Security Topic",
     "Foundations, the three clouds, workloads, identity, detection, governance, AI - one index.",
     "Topic Index"),
    ("learning-path.html",
     "Cloud Security Learning Path",
     "Beginner → working practitioner. Roadmap, milestones, and the labs that actually teach.",
     "Roadmap"),
    ("cloud-security-best-practices.html",
     "Cloud Security Best Practices",
     "The controls that actually prevent breaches - ranked by what shows up as root cause in real incident reports.",
     "Practitioner Guide"),
    ("shared-responsibility-model.html",
     "The Shared Responsibility Model",
     "What the cloud provider secures vs. what you secure. Across IaaS, PaaS, SaaS, and serverless.",
     "Pillar Guide"),
    ("cspm-vs-cnapp.html",
     "CSPM vs CNAPP vs CWPP vs CIEM vs DSPM",
     "The acronym soup decoded. When you need each tool, where they overlap, and the open-source alternatives.",
     "Tool Comparison"),
    ("cloud-security-certifications.html",
     "Cloud Security Certifications Compared",
     "CCSK, CCSP, AWS, Azure, GCP, CKS - side by side, with recommended paths by role.",
     "Comparison"),
    ("github-actions.html",
     "How We Use GitHub Actions",
     "Learn CI/CD by reading our heavily commented production workflows. Triggers, secrets, gotchas, all real.",
     "Tutorial"),
    ("terraform.html",
     "How We Use Terraform",
     "Learn infrastructure-as-code by reading our real multi-cloud Terraform. State, providers, keyless OIDC - all real.",
     "Tutorial"),
    ("version-control.html",
     "Git & Version Control",
     "Version control from first principles, then our real git workflow - branches, pull requests, secrets out of history.",
     "Tutorial"),
    ("resources.html",
     "500+ Cloud Security Resources",
     "CTFs, labs, tools, certifications, and AI-security resources - curated by the CSOH community.",
     "Directory"),
    ("ctfs.html",
     "Cloud Security CTF Challenges",
     "Hands-on practice for AWS, Azure, GCP, Kubernetes and AI security. Free and open-source.",
     "Hands-On"),
    ("conferences.html",
     "Security & Hacker Conferences",
     "RSA, DEF CON, Black Hat, fwd:cloudsec, CCC, OffensiveCon, BSides - and which ones are worth attending.",
     "Directory"),
    ("glossary.html",
     "The Cloud Security Glossary",
     "300+ terms - IAM, CNAPP, CSPM, MITRE ATT&CK, AI security and more - in plain English.",
     "Reference"),
    ("breach-timeline.html",
     "Cloud Breach Kill Chains",
     "Step-by-step attack reconstructions mapped to MITRE ATT&CK Cloud. Capital One, SolarWinds, MGM, and more.",
     "Threat Library"),
    ("threat-research.html",
     "Cloud Threat Research Directory",
     "Vendor research teams, IOC feeds, MITRE ATT&CK Cloud mappings, government advisories - curated.",
     "Defender Resource"),
    ("meetings.html",
     "109 Weekly Cloud Security Recaps",
     "Topic-by-topic notes from every CSOH Friday session - 109 meetings searchable by speaker and topic.",
     "Archive"),
    ("faq.html",
     "Cloud Security Office Hours FAQ",
     "What CSOH is, how to join, what to expect at the Friday Zoom, and how to contribute.",
     "FAQ"),
    ("news.html",
     "Cloud Security News",
     "AWS, Azure, GCP, Kubernetes news - curated daily from 39 vendor-neutral sources.",
     "Daily News"),
    ("sessions.html",
     "Free Weekly Cloud Security Zoom",
     "Friday 7am PT. Expert talks, open discussion, Q&A. 2,000+ members. No vendor pitches.",
     "Community"),
    ("presentations.html",
     "Cloud Security Talks Archive",
     "Recordings of past CSOH Zoom sessions - speakers, talks, and walkthroughs.",
     "Archive"),
    ("about-shawn-nunley.html",
     "About Shawn Nunley",
     "Founder of Cloud Security Office Hours. 25+ years across cloud, identity, infrastructure, and security.",
     "About"),
    ("contribute.html",
     "Contribute to CSOH",
     "Add resources, propose talks, fix typos, build tools. Open-source, by the community, for the community.",
     "Open Source"),
    ("contribute-resources.html",
     "How to Add a Resource",
     "Step-by-step guide for submitting CTFs, tools, certifications, and labs to CSOH. Beginner-friendly, no coding required.",
     "How-To"),
    ("privacy.html",
     "Privacy Policy",
     "No cookies, no trackers, no marketing pixels. CSOH's plain-English privacy policy in one short read.",
     "Policy"),
    ("security-policy.html",
     "Security Vulnerability Disclosure",
     "How to responsibly report security issues to CSOH - scope, response timeline, and recognition.",
     "Policy"),
    ("code-of-conduct.html",
     "Code of Conduct",
     "Community standards for CSOH Friday Zoom sessions, the mailing list, and the GitHub repo.",
     "Policy"),
    ("rss.html",
     "Subscribe to Cloud Security News",
     "RSS feed of curated cloud security news from 39 vendor-neutral sources - updated daily.",
     "Subscribe"),
    ("kevin-mitnick.html",
     "Kevin Mitnick - In Memoriam",
     "A personal tribute by Shawn Nunley. From adversaries to brothers - a story of justice, redemption, and friendship.",
     "Memorial"),

    # ── Topic pages (cloud-security disciplines & technologies) ─────────────
    ("iam.html",
     "IAM & Cloud Identity",
     "Roles, policies, federation, workload identity, and the priv-esc paths attackers actually use. Practitioner-grade.",
     "Topic Guide"),
    ("zero-trust.html",
     "Zero Trust Architecture",
     "NIST SP 800-207, BeyondCorp, CISA Maturity Model - what Zero Trust actually means for cloud workloads.",
     "Topic Guide"),
    ("network-security.html",
     "Cloud Network Security",
     "VPCs, private endpoints, egress controls, WAF/DDoS, SASE/ZTNA. Defaults that prevent the common breaches.",
     "Topic Guide"),
    ("data-security.html",
     "Cloud Data Security",
     "KMS, envelope encryption, BYOK/HSM, secrets, key rotation, classification, DLP. End-to-end coverage.",
     "Topic Guide"),
    ("api-security.html",
     "API Security",
     "OWASP API Top 10, BOLA, JWT pitfalls, GraphQL/gRPC, gateways. The attack surface most breaches actually use.",
     "Topic Guide"),
    ("saas-security.html",
     "SaaS Security",
     "SSPM, OAuth-app risk, M365 / Workspace / Salesforce / GitHub posture. Securing the SaaS layer that ate everything.",
     "Topic Guide"),
    ("ai-ml-security.html",
     "AI / ML Security",
     "OWASP LLM Top 10, MITRE ATLAS, prompt injection, agent sandboxing. Securing AI workloads in production.",
     "Topic Guide"),
    ("what-practitioners-think-about-security-conferences.html",
     "What Practitioners Think About Security Conferences",
     "Five Friday sessions on whether RSA is still worth it, Black Hat versus DEF CON, and how people get an employer to pay.",
     "From the Sessions"),
    ("what-practitioners-think.html",
     "What Practitioners Actually Think",
     "Five digests built from a live weekly call. What cloud security practitioners said to peers, disagreements included.",
     "From the Sessions"),
    ("what-practitioners-think-about-security-regulation.html",
     "What Practitioners Actually Think About Security Regulation",
     "Six Friday sessions on fines, executive liability, and frameworks written for somebody else. The unvarnished version.",
     "From the Sessions"),
    ("what-practitioners-think-about-supply-chain-security.html",
     "What Practitioners Actually Think About Supply Chain Security",
     "Seven Friday sessions on SBOMs, GitHub Actions, and dependency risk. What defenders said while the compromises were still landing.",
     "From the Sessions"),
    ("what-practitioners-think-about-vulnerability-management.html",
     "What Practitioners Actually Think About Vulnerability Management",
     "Eight Friday sessions on CVSS, prioritization, and why patching stalls. What people running these programs actually said.",
     "From the Sessions"),
    ("what-practitioners-think-about-ai-security.html",
     "What Practitioners Actually Think About AI Security",
     "Twenty-two Friday sessions of working cloud security practitioners arguing about AI security and governance, disagreements included.",
     "From the Sessions"),
    ("what-breaking-into-cloud-security-really-takes.html",
     "What Breaking Into Cloud Security Really Takes",
     "Twenty-seven Friday sessions on certifications, the experience paradox, referrals, and the job market, from people already doing the job.",
     "From the Sessions"),
    ("breaking-into-cloud-security.html",
     "How to Break Into Cloud Security",
     "The honest guide to the transition from IT support: the paths in, what to learn first, and how people actually get hired.",
     "Career Guide"),
    ("service-mesh-security.html",
     "Service Mesh Security",
     "Istio, Linkerd, Cilium, Consul; mTLS; SPIFFE/SPIRE. Identity, encryption and policy across micro-services.",
     "Topic Guide"),
    ("vulnerability-management.html",
     "Vulnerability Management",
     "CVSS / EPSS / KEV, reachability, SAST/SCA/DAST, SBOM, ASPM. Prioritization that survives reality.",
     "Topic Guide"),
    ("threat-modeling.html",
     "Cloud Threat Modeling",
     "STRIDE, PASTA, LINDDUN, attack trees, MITRE ATT&CK Cloud. Threat-model the system before it ships.",
     "Topic Guide"),
    ("detection-engineering.html",
     "Cloud Detection Engineering",
     "Sigma, detection-as-code, ATT&CK Cloud Matrix. Build the alerts that actually catch real attacker behavior.",
     "Topic Guide"),
    ("incident-response.html",
     "Cloud Incident Response",
     "IR lifecycle, cloud forensics, evidence preservation, runbooks. What to do when the SIEM lights up.",
     "Topic Guide"),
    ("cloud-soc.html",
     "Cloud SOC & Threat Monitoring",
     "Log-driven detection, SIEM/data-lake architecture, SOC operations for cloud-first orgs.",
     "Topic Guide"),
    ("cloud-pentesting.html",
     "Cloud Pentesting",
     "AWS / Azure / GCP attack paths. Pacu, ROADtools, BloodHound. The offensive playbook defenders need to know.",
     "Topic Guide"),
    ("ci-cd.html",
     "CI/CD Security",
     "Pipeline hardening, OIDC federation, secret scanning, signed artifacts, runtime gates. Stop supply-chain breaches.",
     "Topic Guide"),
    ("landing-zones.html",
     "Cloud Landing Zones",
     "Control Tower / CAF / GCP blueprint. Multi-account org structure, baseline guardrails, centralized logging.",
     "Topic Guide"),
    ("backup-dr.html",
     "Backup & Disaster Recovery",
     "3-2-1-1-0 backups, immutability, RTO/RPO targets, the ransomware kill chain and how to break it.",
     "Topic Guide"),
    ("grc.html",
     "GRC for Cloud",
     "Governance, risk and compliance translated for cloud-native teams. Frameworks, controls, evidence, audits.",
     "Topic Guide"),
    ("compliance-frameworks.html",
     "Compliance Frameworks",
     "SOC 2, ISO 27001, PCI DSS, HIPAA, FedRAMP, CMMC, GDPR - what each one actually requires in the cloud.",
     "Topic Guide"),
    ("ai-learning.html",
     "Learn Cloud Security with AI",
     "Using LLMs and AI tutors to accelerate your cloud security learning curve. Prompts, workflows, gotchas.",
     "Learning"),

    # ── Provider-specific hubs ──────────────────────────────────────────────
    ("aws-security.html",
     "AWS Security - The Complete Guide",
     "IAM, GuardDuty, Security Hub, KMS, Organizations, SCPs. Vendor-neutral take on securing AWS at scale.",
     "Provider Hub"),
    ("azure-security.html",
     "Azure Security",
     "Entra ID, Defender for Cloud, Sentinel, Conditional Access. Practitioner guide to securing Azure tenants.",
     "Provider Hub"),
    ("gcp-security.html",
     "GCP Security",
     "Security Command Center, IAM, VPC Service Controls, Org Policy. Vendor-neutral guide to securing Google Cloud.",
     "Provider Hub"),
    ("containers.html",
     "Container Security",
     "Image hardening, runtime defense, IMDS exposure, the supply chain - boundary security for containerized workloads.",
     "Topic Guide"),
    ("kubernetes.html",
     "Kubernetes & Managed K8s",
     "EKS, AKS, GKE security: RBAC, admission control, network policy, pod security, attack paths and defenses.",
     "Topic Guide"),
    ("serverless.html",
     "Serverless Security",
     "Lambda / Azure Functions / Cloud Functions: IAM, secrets, runtime, dependency, and event-injection risks.",
     "Topic Guide"),
    ("cloud-deployment.html",
     "Cloud Deployment Patterns",
     "How CSOH deploys to GCP: Cloud Run + Workload Identity Federation + Cloud CDN + Cloud Armor. Learn by reading.",
     "Reference"),
    ("how-csoh-org-is-secured.html",
     "How csoh.org Is Secured",
     "Strict CSP, SRI on every asset, HSTS and Cross-Origin isolation, keyless OIDC deploys, a Trivy-scanned pipeline - and how to verify each claim yourself.",
     "Security"),
    ("breach-lessons.html",
     "Lessons From 13 Cloud Breaches",
     "Thirteen real cloud breach kill chains, boiled down to the recurring root causes. Learn the initial-access patterns that keep working and the controls...",
     "Analysis"),
    ("cloud-breach-year-in-review.html",
     "Cloud Breach Year in Review",
     "Five years of cloud and SaaS breaches, one review per year - and what changed between them.",
     "Threat Library"),
    ("cloud-breach-year-in-review-2026-h1.html",
     "2026 Cloud Breaches: The First Half",
     "The year AI stopped being a topic and became a participant. A mid-year review, January to July.",
     "Year in Review"),
    ("cloud-breach-year-in-review-2024.html",
     "2024 Cloud Breach Year in Review",
     "The year consequences got physical - and a supply-chain attacker spent two years earning trust.",
     "Year in Review"),
    ("cloud-breach-year-in-review-2023.html",
     "2023 Cloud Breach Year in Review",
     "The year trust infrastructure became the target: identity providers, file transfer, CI platforms.",
     "Year in Review"),
    ("cloud-breach-year-in-review-2021-2022.html",
     "2021-2022 Cloud Breach Review",
     "Where it started: Log4Shell, the build pipeline, the management plane, and MFA as battleground.",
     "Year in Review"),
    ("cloud-breach-year-in-review-2025.html",
     "2025 Cloud Breach Year in Review",
     "The cloud, SaaS, and supply-chain breaches that defined 2025 - stolen keys, hijacked OAuth tokens, poisoned dependencies - and what they mean for 2026.",
     "Analysis"),
    ("cloud-security-interview-questions.html",
     "Cloud Security Interview Questions",
     "50+ real cloud security interview questions by domain, with what each one tests and the bones of a strong answer, plus paste-in IAM and CloudTrail...",
     "Careers"),
    ("cloud-security-resume-guide.html",
     "The Cloud Security Resume Guide",
     "A practical, opinionated guide to writing a cloud security resume: structure, impact bullets, projects, certs, ATS keywords, and mistakes to avoid.",
     "Careers"),
    ("cnapp-vs-xdr.html",
     "CNAPP vs XDR (and CDR)",
     "CNAPP, XDR, and CDR explained side by side: what each one actually does, when you need which, where they overlap, and how they are converging.",
     "Comparison"),
    ("cspm-vs-cwpp.html",
     "CSPM vs CWPP",
     "CSPM watches your cloud control plane for misconfigurations; CWPP protects the workloads themselves. Here is the difference, the overlap, and...",
     "Comparison"),
    ("get-into-cloud-security-no-experience.html",
     "How to Get Into Cloud Security With No Experience",
     "A concrete, honest guide to breaking into cloud security from zero: realistic on-ramps, what to learn first, building proof, and a 3-6-12 month plan.",
     "Careers"),
    ("is-cloud-security-a-good-career.html",
     "Is Cloud Security a Good Career in 2026?",
     "An honest look at whether cloud security is a good career in 2026: demand, pay, day-to-day reality, the downsides, who it suits, and how to start.",
     "Careers"),
    ("mcp-security.html",
     "MCP Security",
     "A practitioner guide to Model Context Protocol security: how MCP works, its attack surface, and concrete defenses for AI agents that call tools.",
     "Guide"),
    ("non-human-identity.html",
     "Non-Human Identity (NHI) Security",
     "A practitioner's guide to non-human identity security: service accounts, API keys, tokens, workload identities, and AI agents, plus discovery,...",
     "Guide"),
    ("present.html",
     "Present at Cloud Security Office Hours",
     "A practical guide to giving a talk at Cloud Security Office Hours: what we look for, how to pitch, formats, logistics, and speaker tips.",
     "Community"),
    ("speakers.html",
     "CSOH Guest Speakers",
     "How the Cloud Security Office Hours guest-speaker program works, what makes a good talk, and how to pitch a vendor-neutral session.",
     "Community"),
    ("cloud-security-comparison.html",
     "AWS vs Azure vs GCP - Security",
     "10 comparison tables and a scorecard across IAM, logging, posture, detection, encryption, network and pricing.",
     "Comparison"),
    ("vendor-landscape.html",
     "Cloud Security Vendor Landscape",
     "350+ vendors across 28 categories. CNAPP, CSPM, SIEM, EDR, DSPM and the rest - mapped, not ranked.",
     "Reference"),

    # ── Career & community pages ────────────────────────────────────────────
    ("cloud-security-careers.html",
     "Cloud Security Careers",
     "Roles, salary bands, interview formats, and portfolio projects that actually move the needle.",
     "Career"),
    ("cloud-security-degree-programs.html",
     "Cloud Security Degree Programs",
     "Universities and academic paths with strong cloud-security credentials. Honest take on cost vs. outcome.",
     "Career"),
    ("cloud-security-home-lab.html",
     "Cloud Security Home Lab",
     "Free-tier setups, budget guardrails, and kill-switches so you learn without a surprise bill.",
     "Hands-On"),
    ("cloud-security-portfolio-projects.html",
     "Cloud Security Portfolio Projects",
     "Seven hands-on walkthroughs to build a cloud security portfolio that gets you hired.",
     "Hands-On"),
    ("cloud-security-reading-list.html",
     "Cloud Security Reading List",
     "Curated books, blogs, newsletters, podcasts, papers and people-to-follow across cloud security.",
     "Reference"),
    ("community.html",
     "Join the CSOH Community",
     "Mailing list, Signal chat, and the Friday Zoom. How to plug in and what to expect.",
     "Community"),

    # ── Breach kill chains ──────────────────────────────────────────────────
    ("breaches/capital-one.html",
     "Capital One 2019 Breach Kill Chain",
     "SSRF → IMDSv1 → over-privileged IAM role → 106M-record S3 exfiltration. Step-by-step kill chain with defenses.",
     "Breach Kill Chain"),
    ("breaches/solarwinds.html",
     "SolarWinds 2020 Breach Kill Chain",
     "Build-system compromise → SUNBURST → on-prem to cloud pivot → Golden SAML → US-government espionage.",
     "Breach Kill Chain"),
    ("breaches/lastpass.html",
     "LastPass 2022-23 Breach Kill Chain",
     "DevOps engineer endpoint compromise → cloud backups exfiltrated → customer vaults at risk. Full chain and defenses.",
     "Breach Kill Chain"),
    ("breaches/uber.html",
     "Uber 2022 Breach Kill Chain",
     "MFA fatigue → Slack-discovered PAM secrets → AWS, GCP, Duo, OneLogin and HackerOne access. Full chain and defenses.",
     "Breach Kill Chain"),
    ("breaches/scattered-spider-mgm.html",
     "Scattered Spider / MGM 2023 Breach Kill Chain",
     "Vishing the help desk → Okta MFA reset → Azure AD → ESXi ransomware. Full kill chain and identity defenses.",
     "Breach Kill Chain"),
    ("breaches/storm-0558.html",
     "Storm-0558 2023 Breach Kill Chain",
     "Stolen Microsoft MSA signing key → forged Azure AD tokens → 25 government and Outlook tenant compromises.",
     "Breach Kill Chain"),
    ("breaches/snowflake-unc5537.html",
     "Snowflake / UNC5537 2024 Breach Kill Chain",
     "Info-stealer credentials + no-MFA SaaS accounts → 165+ Snowflake customers breached. Full chain and SaaS defenses.",
     "Breach Kill Chain"),
    ("breaches/microsoft-sas-leak.html",
     "Microsoft SAS Leak 2023 Breach Kill Chain",
     "Over-permissive Azure storage SAS token in an open-source repo → 38 TB of internal data exposed. Full chain.",
     "Breach Kill Chain"),
    ("breaches/promptware.html",
     "Promptware 2024-26 Breach Kill Chain",
     "Prompt-injection kill chain across LLM-powered apps and AI agents. Defenses for builders and defenders.",
     "Breach Kill Chain"),
    ("breaches/mitnick-novell.html",
     "Mitnick / Novell 1994 Breach Kill Chain",
     "War dialing → pretexting → the voicemail trap that named the hacker → the watched honeypot. Personal post-mortem.",
     "Breach Kill Chain"),
    ("breaches/codefinger-s3.html",
     "Codefinger S3 Ransomware 2025 Kill Chain",
     "Stolen AWS keys + SSE-C → encrypted S3 buckets with attacker-held keys and 7-day delete timers. Full chain and defenses.",
     "Breach Kill Chain"),
    ("breaches/tj-actions-changed-files.html",
     "tj-actions/changed-files 2025 Kill Chain",
     "CVE-2025-30066: a retagged GitHub Action dumped CI runner memory and leaked secrets into public build logs. Full chain.",
     "Breach Kill Chain"),
    ("breaches/salesloft-drift-unc6395.html",
     "Salesloft Drift / UNC6395 2025 Kill Chain",
     "Stolen Drift OAuth tokens → bulk SOQL exfil across 700+ Salesforce tenants → secret mining. Full chain and SaaS defenses.",
     "Breach Kill Chain"),
    ("breaches/ultralytics-cache-poisoning.html",
     "Ultralytics / PyPI 2024 Kill Chain",
     "A fork branch name poisoned the Actions cache - and the malicious release carried entirely correct provenance.",
     "Breach Kill Chain"),
    ("breaches/polyfill-io.html",
     "Polyfill.io 2024 Kill Chain",
     "Nothing was hacked. The domain was sold, and 490,000+ sites kept loading the script into their users' browsers.",
     "Breach Kill Chain"),
    ("breaches/kaseya-vsa-revil.html",
     "Kaseya VSA / REvil 2021 Kill Chain",
     "One RMM server reaches every client an MSP administers - ~1,500 businesses encrypted via a trusted update.",
     "Breach Kill Chain"),
    ("breaches/event-stream-npm.html",
     "event-stream npm 2018 Kill Chain",
     "Publish rights handed over on request, and two million weekly downloads used to rob one Bitcoin wallet app.",
     "Breach Kill Chain"),
    ("breaches/0ktapus-twilio.html",
     "0ktapus / Twilio 2022 Kill Chain",
     "130+ orgs phished by SMS - and the one where FIDO2 hardware keys made the human failure irrelevant.",
     "Breach Kill Chain"),
    ("breaches/moveit-cl0p.html",
     "MOVEit / Cl0p 2023 Kill Chain",
     "An unauthenticated SQLi zero-day in file transfer software: ~2,600 organizations harvested in days.",
     "Breach Kill Chain"),
    ("breaches/okta-lapsus-sitel.html",
     "Okta / LAPSUS$ 2022 Kill Chain",
     "Five days inside a subcontractor - and two months before Okta's customers were told.",
     "Breach Kill Chain"),
    ("breaches/chaosdb-cosmos.html",
     "ChaosDB / Cosmos DB 2021 Kill Chain",
     "Tenant isolation broke: full admin on other customers' databases, and no customer control would have helped.",
     "Breach Kill Chain"),
    ("breaches/midnight-blizzard-microsoft.html",
     "Midnight Blizzard / Microsoft 2024 Kill Chain",
     "A forgotten test tenant with no MFA, a legacy OAuth app with production rights, then executive email.",
     "Breach Kill Chain"),
    ("breaches/circleci-session-theft.html",
     "CircleCI 2023 Kill Chain",
     "A live 2FA-backed session cookie stolen from a laptop - then 'rotate every secret you gave us'.",
     "Breach Kill Chain"),
    ("breaches/change-healthcare-alphv.html",
     "Change Healthcare 2024 Kill Chain",
     "No MFA on a Citrix portal, nine quiet days, then a third of US patient records and weeks of outage.",
     "Breach Kill Chain"),
    ("breaches/log4shell.html",
     "Log4Shell 2021 Kill Chain",
     "Not a breach - the moment nobody could answer whether they were affected, and SBOM stopped being optional.",
     "Breach Kill Chain"),
    ("breaches/codecov-bash-uploader.html",
     "Codecov Bash Uploader 2021 Kill Chain",
     "One line added to a script thousands of pipelines curl and execute - two months of CI secrets exfiltrated.",
     "Breach Kill Chain"),
    ("breaches/3cx-x-trader.html",
     "3CX / X_TRADER 2023 Kill Chain",
     "The first documented cascading supply chain compromise: one supply chain attack delivering another.",
     "Breach Kill Chain"),
    ("breaches/okta-support-har.html",
     "Okta Support System 2023 Kill Chain",
     "A password synced to a personal Google profile, and a support system full of customers' live session tokens.",
     "Breach Kill Chain"),
    ("breaches/xz-utils-backdoor.html",
     "XZ Utils Backdoor 2024 Kill Chain",
     "CVE-2024-3094: two years of legitimate contributions, a backdoor only in the tarballs, caught by 500ms of latency.",
     "Breach Kill Chain"),
    ("breaches/unc6040-salesforce-vishing.html",
     "UNC6040 Salesforce Vishing 2025 Kill Chain",
     "A phone call and a genuine OAuth consent screen emptied Salesforce tenants - no product vulnerability involved.",
     "Breach Kill Chain"),
    ("breaches/sharepoint-toolshell.html",
     "SharePoint ToolShell 2025 Kill Chain",
     "CVE-2025-53770: unauthenticated RCE, then stolen machine keys that let attackers forge trusted requests after the patch.",
     "Breach Kill Chain"),
    ("breaches/npm-debug-chalk-phishing.html",
     "npm debug / chalk 2025 Kill Chain",
     "MFA was on and did not help: a real-time TOTP relay reached 18 packages carrying 2.6 billion weekly downloads.",
     "Breach Kill Chain"),
    ("breaches/anthropic-gtg-1002.html",
     "GTG-1002 AI-Orchestrated Espionage 2025 Kill Chain",
     "Task decomposition and a role-play persona turned an AI coding agent into the operator of an espionage campaign.",
     "Breach Kill Chain"),
    ("breaches/huggingface-agent-intrusion-timeline.html",
     "Hugging Face Agent Intrusion 2026 Kill Chain",
     "A self-built agent message board, Artifactory zero-days, and 17,600 reconstructed actions inside production.",
     "Breach Kill Chain"),
    ("breaches/huggingface-openai-agent.html",
     "Hugging Face / OpenAI Agent 2026 Kill Chain",
     "An AI model under evaluation escaped its sandbox and breached Hugging Face production to retrieve benchmark answers.",
     "Breach Kill Chain"),
    ("breaches/entra-id-actor-token.html",
     "Entra ID Actor Token 2025 Kill Chain",
     "CVE-2025-55241: an undocumented S2S token + a legacy Graph API that never checked the tenant → Global Admin anywhere.",
     "Breach Kill Chain"),
    ("breaches/nx-s1ngularity.html",
     "Nx / s1ngularity 2025 Kill Chain",
     "PR title injection → stolen npm token → the developer's own AI CLIs weaponized to hunt secrets → credentials in public repos.",
     "Breach Kill Chain"),
    ("breaches/shai-hulud-npm-worm.html",
     "Shai-Hulud npm Worm 2025 Kill Chain",
     "Phished maintainer tokens → TruffleHog turned on the developer → self-replication across 500+ packages, no attacker in the loop.",
     "Breach Kill Chain"),
    ("breaches/oracle-ebs-cl0p.html",
     "Oracle EBS / Cl0p 2025 Kill Chain",
     "CVE-2025-61882: unauthenticated XSLT injection → RCE → two months of silent zero-day → executive email extortion.",
     "Breach Kill Chain"),
    ("breaches/litellm-pypi-teampcp.html",
     "LiteLLM / PyPI 2026 Kill Chain",
     "A poisoned Trivy scanner in CI leaked the PyPI publishing token → two malicious releases → cloud credential sweep from every Python process.",
     "Breach Kill Chain"),
    ("breaches/vercel-context-ai-oauth.html",
     "Vercel / Context.ai 2026 Kill Chain",
     "Infostealer at an AI vendor → OAuth app compromise → Google Workspace takeover → plaintext customer environment variables.",
     "Breach Kill Chain"),
    ("breaches/vimeo-anodot-shinyhunters.html",
     "Vimeo / Anodot 2026 Kill Chain",
     "Stolen analytics-vendor tokens → direct Snowflake and BigQuery access → 119,000 records exfiltrated → extortion deadline.",
     "Breach Kill Chain"),
    ("breaches/megalodon-github-actions.html",
     "Megalodon / GitHub Actions 2026 Kill Chain",
     "Infostealer-bought GitHub credentials → 5,718 commits into 5,561 repos in six hours → CI secret and OIDC theft.",
     "Breach Kill Chain"),
    ("breaches/mini-shai-hulud-tanstack.html",
     "Mini Shai-Hulud / TanStack 2026 Kill Chain",
     "Fork PR poisons the Actions cache → OIDC scraped from runner memory → npm packages published with valid SLSA provenance.",
     "Breach Kill Chain"),
    ("breaches/storm-2949-entra-sspr.html",
     "Storm-2949 2026 Breach Kill Chain",
     "Entra ID self-service password reset + a fake IT call → MFA takeover → Azure RBAC abuse → Key Vault, SQL and storage theft.",
     "Breach Kill Chain"),
    ("breaches/ai-assisted-aws-72-hours.html",
     "Suspected AI-Assisted AWS Compromise 2026 Kill Chain",
     "App weakness → machine-speed secrets sweep → multi-account persistence → CI/CD abuse → infrastructure extortion in 72 hours.",
     "Breach Kill Chain"),

    # ── Portfolio projects ──────────────────────────────────────────────────
    ("portfolio/aws-org-scps.html",
     "Build a multi-account AWS Org with SCPs",
     "Portfolio project: IAM Identity Center, baseline guardrail SCPs, and centralized CloudTrail across 3 accounts.",
     "Portfolio Project"),
    ("portfolio/cloudgoat.html",
     "Walk every CloudGoat scenario",
     "Portfolio project: complete and write up Rhino Security Labs' CloudGoat - the canonical AWS-attack lab.",
     "Portfolio Project"),
    ("portfolio/cnapp-comparison.html",
     "Write a CNAPP comparison",
     "Portfolio project: trial 3 CNAPP platforms against the same vulnerable AWS account and compare findings.",
     "Portfolio Project"),
    ("portfolio/detection-lab.html",
     "Build 5 detections in a lab SIEM",
     "Portfolio project: ship CloudTrail to a free SIEM, write Sigma rules for 5 MITRE ATT&CK Cloud techniques.",
     "Portfolio Project"),
    ("portfolio/open-source-contribution.html",
     "Contribute to OSS cloud security",
     "Portfolio project: ship your first PR to Prowler, Cloud Custodian, Pacu, ROADtools, KICS, or Steampipe.",
     "Portfolio Project"),
    ("portfolio/prowler-audit.html",
     "Prowler audit + remediation",
     "Portfolio project: run Prowler against your AWS account, document every finding, and Terraform the fix.",
     "Portfolio Project"),
    ("portfolio/recreate-capital-one.html",
     "Recreate the Capital One breach",
     "Portfolio project: build the vulnerable WAF + SSRF + IMDSv1 + over-privileged role stack, exploit, then defend.",
     "Portfolio Project"),
    ("cloud-security-how-to.html",
     "Cloud Security How-To Guides",
     "OPA, regex, OVAL, jq, CEL, Sigma, YARA, IAM - explained, walked through, and exercised.",
     "How-To Index"),
    ("howto/regex-for-security.html",
     "Regex for Security Work",
     "Anchors and allowlist bypasses, credential scanning, RE2 vs backtracking, and ReDoS you can time.",
     "How-To Guide"),
    ("howto/jq-and-jmespath.html",
     "jq and JMESPath",
     "The two JSON query languages cloud work runs on, and the traps that return empty instead of an error.",
     "How-To Guide"),
    ("howto/iam-policy-languages.html",
     "IAM Policy Languages and Cedar",
     "Why a policy that says Allow may grant nothing, and the schema that catches what IAM ignores.",
     "How-To Guide"),
    ("howto/opa-rego.html",
     "OPA and Rego",
     "Undefined vs false, deny sets, gating a real Terraform plan with Conftest, and testing both directions.",
     "How-To Guide"),
    ("howto/cel-policy-expressions.html",
     "CEL Policy Expressions",
     "The language inside the Kubernetes API server and GCP IAM, and the check that decides fail open or closed.",
     "How-To Guide"),
    ("howto/sigma-and-yara.html",
     "Sigma and YARA",
     "Detection as code: log events compiled to your SIEM's dialect, and byte patterns in files and memory.",
     "How-To Guide"),
    ("howto/oval-and-scap.html",
     "OVAL and SCAP",
     "Read the machine-readable substrate under compliance scanning, and why backports break version checks.",
     "How-To Guide"),
]


def find_free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *_args, **_kwargs):
        pass


def serve_repo(port: int) -> socketserver.ThreadingTCPServer:
    def handler(*args, **kwargs):
        return Handler(*args, directory=str(REPO_ROOT), **kwargs)
    server = socketserver.ThreadingTCPServer(("127.0.0.1", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def slug_for(filename: str) -> str:
    """index.html -> index, breach-timeline.html -> breach-timeline.

    Subdir pages keep their folder: breaches/capital-one.html ->
    breaches/capital-one, so the JPG lands at img/og/breaches/capital-one.jpg.
    """
    return filename[:-5] if filename.endswith(".html") else filename


def update_html_meta(filename: str, og_path: str) -> bool:
    """Rewrite og:image and twitter:image meta tags to point at the new
    per-page asset. Returns True if the file was modified."""
    full_path = REPO_ROOT / filename
    if not full_path.exists():
        return False
    s = full_path.read_text(encoding="utf-8")
    original = s

    # Absolute URL because OG/Twitter scrapers fetch by URL, not path.
    abs_url = f"https://csoh.org/{og_path}"

    s = re.sub(
        r'(<meta\s+property="og:image"\s+content=")[^"]+(")',
        rf'\1{abs_url}\2',
        s,
        count=1,
    )
    s = re.sub(
        r'(<meta\s+name="twitter:image"\s+content=")[^"]+(")',
        rf'\1{abs_url}\2',
        s,
        count=1,
    )

    if s != original:
        full_path.write_text(s, encoding="utf-8")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate per-page OG images.")
    parser.add_argument("--pages", nargs="*",
                        help="Subset of filenames to regenerate (default: all)")
    parser.add_argument("--skip-html", action="store_true",
                        help="Only regenerate JPGs, don't rewrite the meta tags")
    args = parser.parse_args()

    if not TEMPLATE_PATH.exists():
        print(f"missing template: {TEMPLATE_PATH}", file=sys.stderr)
        return 1

    targets = PAGES
    if args.pages:
        targets = [p for p in PAGES if p[0] in args.pages]
        if not targets:
            print("No matching pages in PAGES list", file=sys.stderr)
            return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Install playwright: pip install playwright && playwright install chromium",
              file=sys.stderr)
        return 2

    port = find_free_port()
    server = serve_repo(port)
    template_url = f"http://127.0.0.1:{port}/tools/og/template.html"
    print(f"🎨 Generating {len(targets)} OG images at {OG_VIEWPORT['width']}x{OG_VIEWPORT['height']}...\n")

    generated = 0
    html_updated = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport=OG_VIEWPORT,
                device_scale_factor=2,    # crisp on retina
            )
            page = context.new_page()

            for filename, title, subtitle, badge in targets:
                slug = slug_for(filename)
                params = urllib.parse.urlencode({
                    "title": title,
                    "subtitle": subtitle,
                    "badge": badge,
                })
                url = f"{template_url}?{params}"
                page.goto(url, wait_until="networkidle")
                page.wait_for_timeout(120)

                out_path = OUT_DIR / f"{slug}.jpg"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(out_path),
                    type="jpeg",
                    quality=88,
                    full_page=False,
                    clip={"x": 0, "y": 0, "width": OG_VIEWPORT["width"], "height": OG_VIEWPORT["height"]},
                )
                generated += 1

                rel = out_path.relative_to(REPO_ROOT).as_posix()
                if not args.skip_html:
                    if update_html_meta(filename, rel):
                        html_updated += 1
                        print(f"  ✓ {filename} → {rel} (meta updated)")
                    else:
                        print(f"    {filename} → {rel} (meta already set)")
                else:
                    print(f"  ✓ {rel}")
        finally:
            browser.close()

    server.shutdown()
    print(f"\nGenerated {generated} images. Updated {html_updated} HTML files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
