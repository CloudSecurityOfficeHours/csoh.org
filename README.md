# Cloud Security Office Hours

**Vendor-neutral cloud-security community. 2,000+ practitioners. Free weekly Zoom on Fridays. No marketing.**

🌐 **[csoh.org](https://csoh.org)** · 📅 **[Friday Zoom 7am PT](https://csoh.kit.com/39feb4f397)** · 📡 **[RSS](https://csoh.org/feed.xml)**

[![GitHub](https://img.shields.io/badge/GitHub-CloudSecurityOfficeHours/csoh.org-blue)](https://github.com/CloudSecurityOfficeHours/csoh.org)
[![Mailing List](https://img.shields.io/badge/Mailing%20List-2000%2B%20Members-orange)](https://csoh.kit.com/39feb4f397)
[![License](https://img.shields.io/badge/License-Open%20Content-green)](LICENSE)

---

## ⭐ Featured Guides

The vendor-neutral curriculum, written by practitioners. This catalog mirrors the site navigation - **Learn**, **By Cloud**, **Threat Intel**, **Careers**, and **Community** - so the README and the nav stay in step. (The nav itself is canonical in [`tools/sync_chrome.py`](tools/sync_chrome.py).)

### Learn

#### Foundations
| Guide | What it covers |
|---|---|
| 📚 [What is Cloud Security?](https://csoh.org/what-is-cloud-security.html) | Plain-English foundation - shared responsibility, threats, tool landscape |
| ⚖️ [Shared Responsibility Model](https://csoh.org/shared-responsibility-model.html) | What the cloud provider secures vs. what you secure (AWS / Azure / GCP) |
| 🛠️ [CSPM vs CNAPP vs CWPP vs CIEM vs DSPM](https://csoh.org/cspm-vs-cnapp.html) | The acronym soup decoded - when you need each tool |
| ✅ [Cloud Security Best Practices](https://csoh.org/cloud-security-best-practices.html) | The controls that actually prevent breaches, ranked by real incidents |
| 🗺️ [Vendor Landscape](https://csoh.org/vendor-landscape.html) | 350+ cloud-security vendors across 30 categories. No rankings, just orientation |
| 📖 [Glossary](https://csoh.org/glossary.html) | 300+ cloud-security terms, plain-English, every cross-reference hyperlinked |
| ❓ [FAQ](https://csoh.org/faq.html) | Format, mailing list, recording policy, contributing, presenter pitches (FAQ schema) |

#### Workloads & Platform
| Guide | What it covers |
|---|---|
| 📦 [Containers & Cloud Security](https://csoh.org/containers.html) | Trust boundary, escape paths, identity chaining via IMDS, supply chain |
| ☸️ [Kubernetes & Managed Kubernetes](https://csoh.org/kubernetes.html) | EKS / AKS / GKE - shared responsibility, workload identity, RBAC, admission |
| ⚡ [Serverless Functions](https://csoh.org/serverless.html) | Lambda / Azure Functions / Cloud Functions - event injection, IAM, denial of wallet |
| 🕸️ [Service Mesh Security](https://csoh.org/service-mesh-security.html) | Istio / Linkerd / Cilium / Consul, mTLS, SPIFFE/SPIRE, ambient mode |
| 🔄 [CI/CD for Cloud Deployments](https://csoh.org/ci-cd.html) | Pipeline anatomy, OIDC federation, AWS/Azure/GCP toolchains |
| 📐 [Landing Zones](https://csoh.org/landing-zones.html) | Cloud foundations - Control Tower / Azure CAF / GCP blueprint |

#### Security Domains
| Guide | What it covers |
|---|---|
| 🔐 [IAM & Cloud Identity](https://csoh.org/iam.html) | Federation, RBAC/ABAC, JIT, workload identity, privilege-escalation paths |
| 🛡️ [Zero Trust Architecture](https://csoh.org/zero-trust.html) | NIST SP 800-207, BeyondCorp, CISA Maturity Model, ZTNA, microsegmentation |
| 🌐 [Cloud Network Security](https://csoh.org/network-security.html) | VPC design, private endpoints, egress controls, WAF, DDoS, SASE/ZTNA |
| 🗝️ [Data Security, KMS & Secrets](https://csoh.org/data-security.html) | Envelope encryption, BYOK/HSM, secrets management, key rotation |
| 🐛 [Vulnerability Management](https://csoh.org/vulnerability-management.html) | CVSS/EPSS/KEV prioritization, reachability, SAST/SCA/DAST, SBOM/VEX, ASPM |
| 🔌 [API Security](https://csoh.org/api-security.html) | OWASP API Top 10, BOLA, JWT pitfalls, GraphQL/gRPC, runtime defense |
| 📡 [SaaS Security (SSPM)](https://csoh.org/saas-security.html) | M365 / Workspace / Salesforce / GitHub / Slack, OAuth app risk, ITDR |

#### Governance & AI
| Guide | What it covers |
|---|---|
| 💾 [Backup, DR & Ransomware](https://csoh.org/backup-dr.html) | 3-2-1-1-0, immutability per cloud, ransomware kill chain, key custody |
| 🧠 [Threat Modeling](https://csoh.org/threat-modeling.html) | STRIDE/PASTA/LINDDUN, attack trees, ATT&CK Cloud, three worked examples |
| 📜 [GRC for Cloud](https://csoh.org/grc.html) | Governance, Risk, Compliance - frameworks, policy-as-code, audit evidence |
| 📋 [Compliance Frameworks](https://csoh.org/compliance-frameworks.html) | SOC 2, ISO 27001, PCI DSS, HIPAA, FedRAMP, CMMC, NIST CSF, GDPR |
| 💡 [AI Learning](https://csoh.org/ai-learning.html) | Using AI assistants to learn cloud security faster - prompts, workflows, study tactics |
| 🤖 [AI/ML & LLM Security](https://csoh.org/ai-ml-security.html) | OWASP LLM Top 10, prompt injection, agentic AI, model supply chain, ATLAS |

#### Build It
| Guide | What it covers |
|---|---|
| ☁️ [Multi-Cloud Secure Deploy](https://csoh.org/cloud-deployment.html) | One static site, three active/active cloud origins behind Cloudflare, keyless OIDC deploys - the full dogfooded stack |
| ⚙️ [How We Use GitHub Actions](https://csoh.org/github-actions.html) | Learn CI/CD by reading our heavily-commented workflows |
| 🧱 [How We Use Terraform](https://csoh.org/terraform.html) | Learn IaC by reading the line-by-line-commented Terraform that provisions our own multi-cloud infra |
| 🔀 [Git & Version Control](https://csoh.org/version-control.html) | Version-control fundamentals taught through this repo's own history |

### By Cloud
| Hub | Focus |
|---|---|
| 🟧 [AWS Security](https://csoh.org/aws-security.html) | Well-Architected, service catalog, top-10 misconfigs, AWS attack paths |
| 🟦 [Azure Security](https://csoh.org/azure-security.html) | CAF Secure, Entra/Defender/Sentinel, Entra-vs-AD, Azure attack paths |
| 🟩 [GCP Security](https://csoh.org/gcp-security.html) | Encryption-by-default, SCC Enterprise, VPC Service Controls deep-dive |
| ⚖️ [AWS vs Azure vs GCP](https://csoh.org/cloud-security-comparison.html) | Definitive side-by-side - 10 comparison tables and a 20-row scorecard |

### Threat Intel
| Guide | What it covers |
|---|---|
| 📰 [Cloud Security News](https://csoh.org/news.html) | 120+ articles, refreshed every 3 hours from 39 sources |
| 🔬 [Threat Research Sources](https://csoh.org/threat-research.html) | Curated directory of vendor research, IOC feeds, advisories - includes a Supply Chain Attacks section |
| 🔗 [Breach Kill Chains](https://csoh.org/breach-timeline.html) | <!--count:breaches-->13<!--/count--> real cloud breaches mapped to MITRE ATT&CK |
| 🛰️ [Cloud SOC & Threat Monitoring](https://csoh.org/cloud-soc.html) | Log-driven detection, native services, SIEM, detection engineering, IR |
| 🕵️ [Detection Engineering](https://csoh.org/detection-engineering.html) | Sigma, ATT&CK Cloud Matrix, detection-as-code, SIEM/lake/XDR |
| 🚨 [Incident Response & Forensics](https://csoh.org/incident-response.html) | IR lifecycle, EC2/EKS/Lambda evidence, memory forensics, runbooks |
| 🎯 [Cloud Pentesting & Red Teaming](https://csoh.org/cloud-pentesting.html) | AWS/Azure/GCP attack paths, Pacu/ROADtools/BloodHound, MITRE ATT&CK Cloud |
| 🚩 [CTF Challenges](https://csoh.org/ctfs.html) | 39+ hands-on cloud CTFs across AWS / Azure / GCP / Kubernetes / AI |

### Careers

#### Getting Started
| Guide | What it covers |
|---|---|
| 🧭 [Cloud Security Careers](https://csoh.org/cloud-security-careers.html) | Roles, salary bands, interview formats, portfolio projects |
| 🛣️ [Cloud Security Learning Path](https://csoh.org/learning-path.html) | Beginner → working practitioner roadmap with milestones |
| 🪜 [Help Desk → Cloud Security](https://csoh.org/help-desk-to-cloud-security.html) | The realistic transition from IT support |
| 🎓 [Cloud Security Certifications](https://csoh.org/cloud-security-certifications.html) | CCSK, CCSP, AWS, Azure, GCP, CKS compared side by side |
| 🎓 [Cloud Security Degree Programs](https://csoh.org/cloud-security-degree-programs.html) | Academic paths, what to look for, named US/international universities |
| 🧰 [Cloud Security Home Lab](https://csoh.org/cloud-security-home-lab.html) | Free-tier setups, budget guardrails, kill-switches |
| 🛠️ [Portfolio Projects](https://csoh.org/cloud-security-portfolio-projects.html) | Build-it-yourself projects that prove skills to hiring managers (walkthroughs below) |
| 📖 [Cloud Security Reading List](https://csoh.org/cloud-security-reading-list.html) | Books, blogs, podcasts, newsletters & people to follow - staleness-checked monthly |
| 🤝 [Mentorship](https://csoh.org/mentorship.html) | How CSOH connects mentors and mentees in the community |

#### Engineering Roles
| Role | Track |
|---|---|
| [Cloud Security Engineer](https://csoh.org/cloud-security-engineer.html) | The generalist core role |
| [Cloud Security Architect](https://csoh.org/cloud-security-architect.html) | Staff+ IC design track |
| [Security SRE / Platform Security Engineer](https://csoh.org/cloud-security-platform-engineer.html) | Security platform & reliability |
| [Cloud AppSec / IaC Security Engineer](https://csoh.org/cloud-security-appsec-engineer.html) | Shift-left, pipeline & IaC |
| [CSPM / CNAPP Analyst](https://csoh.org/cloud-security-cnapp-analyst.html) | Posture & findings triage |
| [IAM / Identity Architect](https://csoh.org/cloud-security-iam-architect.html) | Identity-first specialization |

#### Specialist & Field Roles
| Role | Track |
|---|---|
| [Cloud Detection Engineer](https://csoh.org/cloud-security-detection-engineer.html) | Detection-as-code |
| [Cloud Incident Responder (DFIR)](https://csoh.org/cloud-security-incident-responder.html) | Cloud forensics & IR |
| [Cloud Penetration Tester / Red Team](https://csoh.org/cloud-security-penetration-tester.html) | Offensive cloud |
| [Cloud GRC / Compliance Engineer](https://csoh.org/cloud-security-grc-engineer.html) | Governance, risk, audit |
| [Cloud Security Sales Engineer](https://csoh.org/cloud-security-sales-engineer.html) | Pre-sales / SE track |
| [Cloud Security Customer Success Engineer](https://csoh.org/cloud-security-customer-success-engineer.html) | Post-sales / CSE track |

#### Hands-on portfolio projects

[Cloud Security Portfolio Projects](https://csoh.org/cloud-security-portfolio-projects.html) is a hub of build-it-yourself projects that prove cloud-security skills to hiring managers. Each has a full step-by-step walkthrough under `portfolio/`:

| Project | What you build |
|---|---|
| [Build a multi-account AWS Org with SCPs](https://csoh.org/portfolio/aws-org-scps.html) | 3-account AWS Org, Identity Center, guardrail SCPs, centralized CloudTrail |
| [Walk every CloudGoat scenario](https://csoh.org/portfolio/cloudgoat.html) | Complete and write up Rhino's CloudGoat AWS-attack labs |
| [Write a CNAPP comparison](https://csoh.org/portfolio/cnapp-comparison.html) | Trial 3 CNAPPs against one vulnerable account, compare findings |
| [Build 5 detections in a lab SIEM](https://csoh.org/portfolio/detection-lab.html) | Free SIEM + CloudTrail + Sigma rules, validated with Stratus Red Team |
| [Prowler audit + remediation](https://csoh.org/portfolio/prowler-audit.html) | Audit your own AWS account, Terraform a fix for every finding |
| [Recreate the Capital One breach](https://csoh.org/portfolio/recreate-capital-one.html) | Build the vulnerable SSRF/IMDSv1 stack, exploit it, then detect it |
| [Contribute to OSS cloud security](https://csoh.org/portfolio/open-source-contribution.html) | Ship your first PR to Prowler / Cloud Custodian / Pacu / etc. |

### Community

#### Live
| Resource | What it covers |
|---|---|
| 📅 [Friday Zoom Sessions](https://csoh.org/sessions.html) | Every Friday 7am PT - format, speakers, and how to join |
| 💬 [Community & Signal](https://csoh.org/community.html) | The Signal chat and how to join the conversation between Fridays |
| 🤝 [Mentorship](https://csoh.org/mentorship.html) | How CSOH connects mentors and mentees in the community |
| 🏟️ [Conferences](https://csoh.org/conferences.html) | 27 security & hacker conferences, with pros & cons |

#### Archive
| Resource | What it covers |
|---|---|
| 📝 [Meeting Recaps](https://csoh.org/meetings.html) | <!--count:meetings-->102<!--/count--> weekly session recaps, searchable |
| 🎬 [Presentations](https://csoh.org/presentations.html) | Archive of recorded talks with topic tags and direct video links |
| 💬 [Chat Resources](https://csoh.org/chat-resources.html) | 580+ community-shared URLs from live sessions, security-validated |

## 📚 Reference & Practice

Cross-cutting entry points that sit outside the topic menus (everything else now lives under its nav section above):

| Resource | What it is |
|---|---|
| 🛡️ [Resources Directory](https://csoh.org/resources.html) | 370+ tools, labs, CTFs, certifications - top-level nav link, auto-refreshed weekly |
| 🔍 [Site-wide Search](https://csoh.org/search.html) | MiniSearch full-text index across every page, with section-anchor results and synonym expansion |

---

## 🌐 About

Cloud Security Office Hours is a vendor-neutral, free community founded in February 2023. We meet on Zoom every Friday at 7am PT, share what we're learning, and maintain this resource hub. Everything on the site is free, no marketing trackers, no on-site advertising. (The site uses GoatCounter, a cookieless, privacy-friendly page-view counter - no cookies, no cross-site tracking, no IP storage.) (The mailing list occasionally includes a clearly-labeled sponsored link from a community-aligned partner - never a separate promotional email.)

Sign up for the weekly Zoom link at **[csoh.kit.com](https://csoh.kit.com/39feb4f397)**. Subscribe to our cloud-security news at **[csoh.org/feed.xml](https://csoh.org/feed.xml)** (or visit the [RSS subscribe page](https://csoh.org/rss.html) for setup help).

---

## 🎓 Getting Started

**New to cloud security?** It's the practice of protecting data, applications, and infrastructure hosted in cloud environments like AWS, Azure, and Google Cloud - one of the fastest-growing areas in cybersecurity.

Our recommended learning sequence:

1. **Get the Lay of the Land**: [What is Cloud Security?](https://csoh.org/what-is-cloud-security.html) - vendor-neutral pillar overview of the field
2. **Follow the Roadmap**: [Cloud Security Learning Path](https://csoh.org/learning-path.html) - beginner → advanced with milestones, free labs, study targets
3. **Master the Fundamentals**: [Best Practices](https://csoh.org/cloud-security-best-practices.html) and the [Shared Responsibility Model](https://csoh.org/shared-responsibility-model.html)
4. **Decode the Acronyms**: [Glossary](https://csoh.org/glossary.html) - 300+ terms, every cross-reference hyperlinked
5. **Get Hands-On**: [CTF Challenges](https://csoh.org/ctfs.html) and [Resources](https://csoh.org/resources.html) for practice
6. **Choose a Certification**: [Cloud Security Certifications guide](https://csoh.org/cloud-security-certifications.html) - CCSK, CCSP, AWS, Azure, GCP, CKS
7. **Read Real Breaches**: [Breach Kill Chains](https://csoh.org/breach-timeline.html) - see how attacks actually happen
8. **Join the Community**: [csoh.kit.com](https://csoh.kit.com/39feb4f397) for the Friday Zoom link
9. **Stay Updated**: [News](https://csoh.org/news.html), [RSS feed](https://csoh.org/feed.xml), or any [Friday Zoom recap](https://csoh.org/meetings.html)

---

## 📄 Website Pages

### 🏠 Homepage (`index.html`)
Central hub featuring:
- Community overview and value proposition
- Featured resource categories with quick navigation
- Call-to-action buttons for mailing list signup (which delivers the Zoom link)
- Enhanced schema markup for improved SERP visibility
- Testimonials and member count (2000+)

### ☁️ What is Cloud Security? (`what-is-cloud-security.html`)
Vendor-neutral pillar page introducing the field - shared responsibility model, core pillars, top threats, the CSPM/CNAPP/CWPP/CIEM tool landscape, and a pointer-rich getting-started roadmap. Targets the high-volume "what is cloud security" search query and serves as the hub that links into the rest of the site. FAQ schema for rich snippets.

### 🛣️ Learning Path (`learning-path.html`)
Step-by-step roadmap from "no cloud experience" to working practitioner: prerequisites, beginner / intermediate / advanced stages with milestones, specialization tracks, and a "stay current" rhythm. Marked up with `HowTo` schema. Built from what actually works for the 2000+ members of the community.

### 🎓 Cloud Security Degree Programs (`cloud-security-degree-programs.html`)
Academic paths for cloud security: when a degree pays off, degree types and what they fit, what to look for in a program, NSA/CISA CAE and equivalent designations, named US universities (research, federal-track, applied), online and professional master's, and international programs (UK, EU, Canada, Australia, Israel, Asia). FAQ schema.

### 🧭 Cloud Security Careers (`cloud-security-careers.html`)
Roles and salary bands, what hiring managers actually look for, interview formats, portfolio projects, and how to translate from adjacent roles. FAQ schema. The careers hub fans out to a **role-in-depth series** and a **portfolio-projects hub** (below).

### 🧑‍💼 Career Roles, In Depth (`cloud-security-*.html`)
A series of one-page-per-role deep dives covering day-to-day work, the skills that actually matter, salary signals, and how to break in: Cloud Security Engineer, Cloud Security Architect (Staff+ IC), IAM / Identity Architect, Cloud AppSec / IaC Security Engineer, CSPM / CNAPP Analyst, Cloud Detection Engineer, Cloud Incident Responder (DFIR), Cloud Penetration Tester / Red Team, Security SRE / Platform Security Engineer, Cloud GRC / Compliance Engineer, Cloud Security Sales Engineer, and Cloud Security Customer Success Engineer. `help-desk-to-cloud-security.html` is the companion transition guide for people coming from IT support. Each role page carries FAQ schema.

### 🛠️ Cloud Security Portfolio Projects (`cloud-security-portfolio-projects.html` + `portfolio/`)
A hub of build-it-yourself projects that demonstrate real cloud-security skill to hiring managers, each with a full step-by-step walkthrough under `portfolio/`: build a multi-account AWS Org with SCPs, walk every CloudGoat scenario, write a CNAPP comparison, build 5 detections in a lab SIEM, run a Prowler audit and Terraform the fixes, recreate the Capital One breach end to end, and ship a first OSS contribution to a cloud-security project.

### 📖 Cloud Security Reading List (`cloud-security-reading-list.html`)
A hand-curated, opinionated list of books, blogs, podcasts, newsletters, and people to follow. A monthly GitHub Actions workflow (`check-reading-list-staleness.yml`) discovers each source's feed and flags anything that has gone quiet - it never edits the page, only files a tracking issue for a human to review.

### 🤝 Mentorship (`mentorship.html`)
How CSOH connects mentors and mentees within the community, what to expect, and how to take part.

### 💬 Community & Signal (`community.html`)
The community Signal chat and how to join the conversation between Friday sessions.

### 🧰 Cloud Security Home Lab (`cloud-security-home-lab.html`)
Free-tier setups across AWS / Azure / GCP, budget guardrails, kill-switches, and the lab progression that builds a real portfolio without a surprise bill.

### 🎓 Cloud Security Certifications (`cloud-security-certifications.html`)
Side-by-side comparison of the major cloud security certifications - CCSK, CCSP, AWS Security Specialty, Microsoft AZ-500/SC-100, Google PCSE, and CKS. Includes a comparison table, recommended paths by role (career switcher / established engineer / senior architect / detection specialist), and an FAQ.

### ✅ Cloud Security Best Practices (`cloud-security-best-practices.html`)
Practitioner's checklist of the controls that actually prevent breaches, ordered by what shows up as root cause in our breach kill chains. Covers identity, configuration, network, data, detection, supply chain, workloads, AI, governance - plus an explicit "anti-patterns" section.

### ⚖️ Shared Responsibility Model (`shared-responsibility-model.html`)
What the cloud provider secures vs. what you secure across IaaS, PaaS, SaaS, and FaaS. Includes the AWS / Azure / GCP differences (and Google's "shared fate" extension), a per-service-tier table, the contractual layer, and the gotchas behind every "who's responsible for X?" argument.

### 🛠️ CSPM vs CNAPP vs CWPP vs CIEM vs DSPM (`cspm-vs-cnapp.html`)
The acronym soup decoded. Side-by-side comparison of cloud-security tool categories with explicit "when do I need each" guidance, an open-source-only reference stack, and an FAQ on whether CNAPP is "just marketing" (mostly: no).

### 📦 Containers & Cloud Security (`containers.html`)
Vendor-neutral guide to containers in the cloud - what they actually are, why the boundary is process-isolation rather than tenant-isolation, the real escape paths (privileged flags, kernel CVEs, hostPath, docker.sock), identity chaining via the instance metadata service, flat networking, supply chain, minimal/hardened base images (Chainguard, Minimus, Wiz, Distroless), runtime detection, and an AWS/Azure/GCP service comparison.

### ☸️ Kubernetes & Managed Kubernetes (`kubernetes.html`)
Practitioner's guide to EKS / AKS / GKE - what's managed vs. what you still own, the pod-to-node-to-cloud threat arc, workload identity (IRSA / WIF / AKS Workload Identity), RBAC sprawl, Pod Security Standards, default-flat pod networking, admission control (Kyverno / OPA Gatekeeper), and a side-by-side comparison of the three managed offerings.

### ⚡ Serverless Functions & Cloud Security (`serverless.html`)
Practitioner's guide to AWS Lambda, Azure Functions, and Google Cloud Functions - what they are, when to use them, the good/bad tradeoffs, and the seven security risk categories: event injection from S3/SQS/HTTP triggers, identity sprawl across per-function roles, supply-chain risk, secrets handling, network egress, denial of wallet, and the observability gap.

### 🔄 CI/CD for Cloud Deployments (`ci-cd.html`)
Vendor-neutral CI/CD reference focused on cloud - pipeline anatomy, OIDC federation (replacing long-lived cloud keys), AWS / Azure / GCP per-cloud deep dives, deployment strategies (blue/green, canary, rolling), securing the pipeline itself, IaC in the pipeline, and the DORA-aligned bootstrapping path.

### 🛰️ Cloud SOC & Threat Monitoring (`cloud-soc.html`)
Cloud-side detection and response - how cloud SOC differs from packet-driven traditional SOC, the log sources that matter (CloudTrail / Activity Log / Cloud Audit Logs, identity events, VPC flow, DNS, data plane), native cloud detection (GuardDuty / Defender for Cloud / SCC), the modern SIEM landscape (Splunk, Sentinel, Chronicle, Elastic, CrowdStrike, Datadog), detection engineering as a practice, MITRE-mapped detection categories, threat intel, IR specifics, and a 4-stage SOC maturity model.

### 🔐 IAM & Cloud Identity (`iam.html`)
Cloud identity is the #1 root-cause category in breach reports. This page covers federation (SAML/OIDC/SCIM), RBAC vs ABAC vs ReBAC, JIT access and PAM, workload identity (IRSA / Workload Identity Federation / Managed Identities), and the per-cloud privilege-escalation paths (`iam:PassRole`, AssumeRole chains, GCP service-account impersonation, Azure managed-identity abuse). FAQ schema.

### 🛡️ Zero Trust Architecture (`zero-trust.html`)
NIST SP 800-207 explained, the BeyondCorp origin story, the seven tenets, PDP/PEP/Policy Engine, ZTNA vs VPN, microsegmentation (host-based vs network-based vs service-mesh), continuous verification, CISA Zero Trust Maturity Model, and per-cloud patterns for AWS / Azure / GCP. Explicitly debunks "Zero Trust as a product."

### 🌐 Cloud Network Security (`network-security.html`)
VPC/VNet design, private endpoints (PrivateLink / Private Link / Private Service Connect), egress controls, DNS security, WAF / DDoS / bot management, service mesh east-west, SASE/SSE landscape, ZTNA, microsegmentation, eBPF (Cilium/Tetragon), and a flow-logs + observability section. "Egress is the new ingress" through-line.

### 🗝️ Data Security, KMS & Secrets (`data-security.html`)
Data classification, encryption at rest / in transit, envelope encryption with DEK/KEK, BYOK vs HYOK vs CMK, HSMs (FIPS 140-2/140-3), secrets managers (AWS Secrets Manager / Azure Key Vault / GCP Secret Manager / HashiCorp Vault), Kubernetes secrets patterns (sealed-secrets, ESO, SOPS), tokenization vs encryption, DLP, confidential computing, and database encryption nuances.

### 🐛 Cloud Vulnerability Management (`vulnerability-management.html`)
CVSS is not a priority score. The prioritization stack: CVSS → EPSS → KEV → reachability → asset criticality. SCA, SAST, DAST, container image scanning, IaC scanning, agentless vs agent-based cloud scanners, SBOM (CycloneDX/SPDX), VEX, runtime detection (eBPF), patch management in cloud, ASPM, and SLAs by severity.

### 🔌 API Security (`api-security.html`)
OWASP API Security Top 10 (2023) walked end to end - BOLA, broken auth, BOPLA, unrestricted resource consumption, BFLA, business-flow abuse, SSRF, misconfig, inventory drift, unsafe consumption. Plus auth patterns (OAuth/OIDC/JWT pitfalls/mTLS), rate limiting, gateway landscape, schema validation, GraphQL/gRPC specifics, runtime API platforms, and testing.

### 📡 SaaS Security & SSPM (`saas-security.html`)
The third leg of the *PM stool. Four pillars (identity / config / data / detection), the OAuth-app problem, shadow IT discovery, SSPM vs CASB, ITDR, and per-app guides for Microsoft 365, Google Workspace, Salesforce, GitHub, Slack/Teams. SSPM and CASB landscape, plus a SaaS security program model.

### 💾 Backup, DR & Ransomware Resilience (`backup-dr.html`)
Why backup became a security control. 3-2-1-1-0, RTO/RPO, immutability (S3 Object Lock Compliance, Azure Immutable Storage, GCS Bucket Lock), virtual air gap, KMS key custody (the killer detail), the cloud-ransomware kill chain (encrypt backups FIRST), per-cloud landscape, restoration drills, cyber insurance reality, and tabletop scenarios.

### 🧠 Cloud Threat Modeling (`threat-modeling.html`)
Shostack's four questions, STRIDE / PASTA / LINDDUN compared, attack trees, MITRE ATT&CK Cloud as a threat library, OWASP Threat Dragon and Microsoft TMT, commercial platforms (IriusRisk, ThreatModeler), and three worked examples - a 3-tier AWS app, an LLM RAG app, and a multi-account landing zone.

### 🕵️ Detection Engineering & Cloud Logging (`detection-engineering.html`)
The build side of cloud SOC. Detection-engineering lifecycle (research → develop → tune → deploy → validate), cloud logging fundamentals per cloud, Sigma + vendor detection languages, MITRE ATT&CK Cloud Matrix, detection-as-code workflow, SIEM vs Data Lake vs XDR, log retention economics, and validation tooling (Atomic / Stratus Red Team / CALDERA).

### 🚨 Incident Response & Cloud Forensics (`incident-response.html`)
The IR lifecycle adapted for cloud. Forensic readiness before the incident (immutable log archive, dedicated forensics account, snapshot pipelines, SCPs to block evidence destruction). Evidence collection by workload type (EC2 / EKS / Lambda / S3 / IAM), memory forensics, container forensics, isolation patterns, credential rotation under incident, six standard cloud IR runbooks, retainers, and breach-notification timing.

### 🎯 Cloud Pentesting & Red Teaming (`cloud-pentesting.html`)
The offensive complement to detection-engineering. Provider testing policies, RoE, methodology (PTES / ATT&CK / Hacking the Cloud), per-cloud attack paths (AWS / Azure / GCP / Kubernetes), the open-source toolkit catalog (Pacu, ROADtools, BloodHound, Cloudfox, MicroBurst, Stratus Red Team, CloudGoat, AzureHound). Explicit authorized-testing-only banner.

### 📜 GRC for Cloud (`grc.html`)
Governance, Risk, Compliance - the discipline that makes cloud security legible to auditors and regulators. Three pillars, framework landscape (SOC 2, ISO 27001, PCI DSS, HIPAA, FedRAMP, NIST CSF, CIS, GDPR), policy-as-code, compliance-as-code, continuous compliance with CSPM/CNAPP, audit evidence in cloud, AWS Audit Manager vs Azure Policy vs GCP Assured Workloads.

### 📋 Compliance Frameworks in Cloud (`compliance-frameworks.html`)
The deep-dive companion to GRC: framework-by-framework breakdowns (SOC 2 Type I/II, ISO 27001/27017/27018, PCI DSS v4, HIPAA, FedRAMP Low/Mod/High + 20x, CMMC 2.0, NIST CSF 2.0, NIST SP 800-53/171, CIS Benchmarks, GDPR, SOX, NIS2, DORA, plus industry-specific). Control crosswalks, GRC platform landscape, and AWS / Azure / GCP compliance program comparison.

### 🤖 AI/ML & LLM Security (`ai-ml-security.html`)
Securing AI workloads (distinct from `ai-learning.html`, which is about using AI to learn cloud security). OWASP LLM Top 10 walked item by item, OWASP ML Top 10, prompt-injection defenses, agentic AI risks, model supply chain, training-data security, vector DB and RAG security, AI governance frameworks (NIST AI RMF, EU AI Act, ISO/IEC 42001, MITRE ATLAS), and per-cloud AI service controls.

### 🕸️ Service Mesh Security (`service-mesh-security.html`)
Securing east-west traffic. Istio / Linkerd / Cilium / Consul Connect, mTLS, authentication (SPIFFE/SPIRE workload identity), authorization policy, observability (Hubble, Kiali), sidecar vs sidecarless (ambient mode, eBPF), multi-cluster meshes, mesh attack surface, AWS App Mesh / Anthos Service Mesh / AKS Istio add-on.

### 📐 Landing Zones & Cloud Foundations (`landing-zones.html`)
The foundation layer - AWS Control Tower + Organizations + SCPs, Azure CAF Enterprise-scale + Management Groups + Azure Policy, GCP Org → Folders → Projects + Org Policies + VPC Service Controls. Account-vault patterns, identity layer placement, tagging strategy.

### 🟧 AWS Security Hub (`aws-security.html`)
SEO-targeted hub page for the "AWS security" search intent (~10× the volume of "cloud security"). Well-Architected Security pillar, the full AWS service catalog (detection / identity / data / network / compliance / IR), reference landing-zone architecture, top-10 AWS misconfigurations, AWS attack paths, and discipline cross-links with `#aws` anchors.

### 🟦 Azure Security Hub (`azure-security.html`)
Same SEO play for Azure. CAF Secure methodology, the Microsoft service catalog (Defender for Cloud / Sentinel / Entra ID / Purview / Key Vault / Front Door / NSGs), Entra-ID-vs-traditional-AD, Azure attack paths (managed identity abuse, illicit consent grants, Conditional Access bypass), and the Microsoft Defender licensing maze.

### 🟩 GCP Security Hub (`gcp-security.html`)
Same SEO play for Google Cloud. Encryption-by-default story, Security Command Center Standard/Premium/Enterprise, BeyondCorp Enterprise, VPC Service Controls deep-dive, GCP attack paths (service-account impersonation, deployment-manager privesc, metadata SSH-key injection), and Assured Workloads.

### ⚖️ AWS vs Azure vs GCP Security Services (`cloud-security-comparison.html`)
The definitive vendor-neutral comparison. Ten side-by-side `.comparison-table` blocks (identity, detection, data, network, compliance, pricing, customer identity, compute, container, serverless), conceptual differences that bite you (IAM-policy languages, org-boundary models, log pricing, VPC SC), a "which cloud for which job" guidance section, and a 20-row score-card summary.

### 🗺️ Vendor Landscape (`vendor-landscape.html`)
A directory of **350+ cloud-security vendors** across 30 categories - CNAPP, CSPM, KSPM, CIEM, SSPM, DSPM, SIEM, EDR/XDR, MDR, SOAR, ASPM, SAST/SCA, IaC scanning, secrets, PAM, IdP, WAF/DDoS, API security, CASB, SASE, ZTNA, DevSecOps, image hardening, supply chain, AI security, vuln mgmt, forensics, MSSPs, GRC platforms. Vendor-neutral one-liners, no rankings. Wiz affiliation disclosed.

### 🔍 Site Search (`search.html`)
[MiniSearch](https://lucaong.github.io/minisearch/)-powered full-text search across every page, with **section-anchor results** and **synonym expansion**. `tools/build_search_index.py` builds `search-index.json` at deploy time (one entry per `<section id>` + one per glossary term), `search-init.js` lazy-loads it on first keystroke, and `search-synonyms.json` maps acronyms to expansions so `NHI` finds every "non-human identity" mention site-wide. CSP stays strict - `script-src 'self'`, no `unsafe-eval`, no `wasm-unsafe-eval`.

### ⚙️ How We Use GitHub Actions (`github-actions.html`)
Learn-by-example explainer for GitHub Actions, using CSOH's workflow files as the teaching material. Covers triggers, concurrency, secrets, the GITHUB_TOKEN vs PAT distinction, the `workflow` scope gotcha, OIDC trust to GCP, and a recommended reading order through the workflow files - every one of which is commented line by line (roughly half of each file is explanatory comments) specifically so a newcomer can read it top to bottom and understand it.

### ☁️ How We Deploy Across AWS, GCP & Azure (`cloud-deployment.html`)
The dogfooded multi-cloud architecture: one static site served active/active from AWS (S3 + CloudFront), GCP (Cloud Run), and Azure (Blob static website) behind a single Cloudflare edge (TLS, WAF, security headers, redirects, Load Balancer with health-check failover), deployed to each cloud with keyless OIDC. Security controls called out at every layer. Pairs with the GitHub Actions explainer to give a complete CI/CD-to-cloud reference.

### 🧱 How We Use Terraform (`terraform.html`)
Learn-by-example IaC explainer, using the Terraform that provisions CSOH's own multi-cloud infrastructure (AWS, GCP, Azure, Cloudflare) as the teaching material. Every `.tf` file under `infra/terraform/` is exhaustively commented inline - roughly two of every three lines is a comment, and even core Terraform vocabulary ("resource" vs "data", providers, state, dependencies) is explained in place - specifically so a complete newcomer can read the multi-cloud build end to end and understand it. The third leg of the "Behind the Scenes" developer-docs set alongside GitHub Actions and the multi-cloud deploy page.

### 🔀 Git & Version Control (`version-control.html`)
Version-control fundamentals - branching, commits, pull requests, and history hygiene - taught through this repository's own workflow.

### 📚 Resources (`resources.html`)
Comprehensive catalog of **<!--count:resources_floor-->380+<!--/count--> cloud security resources** organized by 6 categories:

#### 🎯 CTF Challenges & Vulnerable Environments
- **CloudGoat** - Open-source, AWS vulnerable environments by Rhino Security Labs
- **AWSGoat** - Vulnerable AWS stack from INE (formerly AppSecEngineer)
- **Kubernetes Goat** - K8s containerized application with intentional vulnerabilities
- **AIGoat** - AI/ML vulnerable applications
- **Blue Team Labs** - Hands-on security scenarios
- Plus 15+ additional CTF platforms (OWASP, HackTheBox, TryHackMe, etc.)

#### 🧪 Hands-On Labs & Training Platforms
- **Cybr** - Free AWS security labs
- **Digital Cloud Training** - Comprehensive challenge labs
- **AWS Well-Architected Labs** - Official AWS security training
- **Immersive Labs** - Interactive cybersecurity training
- **SecureFlag** - GCP security labs
- **Pwned Labs** - Realistic penetration testing scenarios
- Plus 20+ additional training platforms

#### 🛡️ Security Tools & Platforms (25+ Tools)
- **CNAPP (Cloud Native Application Protection)** - Runtime protection tools
- **CSPM (Cloud Security Posture Management)** - Configuration & compliance scanning
- **KSPM (Kubernetes Security Posture Management)** - K8s-specific security
- **SIEM & Threat Detection** - Splunk, ELK Stack, AWS Security Hub, etc.
- **Compliance & Config Management** - Terraform, Ansible, CloudFormation
- **Vulnerability Management** - Snyk, Qualys, Tenable, etc.

#### 🎓 Certifications & Professional Development (25+ Certs)
- **AWS** - Security Specialty, Solutions Architect, Database Specialty
- **Azure** - Security Engineer Associate, Administrator Associate
- **Google Cloud** - Professional Cloud Security Engineer
- **Cloud Security Alliance** - CCSK Certification
- **Kubernetes** - CKA, CKAD, CKS
- **General Security** - CISSP, CEH, SC-300, AZ-305
- **Bootcamps & Prep Courses** - Pwned Labs, AWSome Day, etc.

#### 🤖 AI Security (50+ Resources)
- **AI Security Tools** - Trend Micro Workload Security, etc.
- **AI Vulnerable Environments** - AIGoat, AI Security CTFs
- **AI Security Research** - Papers, whitepapers, research resources

#### 💼 Job Search Resources (50+ Listings)
- **Job Boards** - LinkedIn, Dice, CyberSecJobs, CloudSecurityJobs
- **Resume Services** - Resume optimization platforms
- **Interview Prep** - Technical interview guides
- **Career Development** - Mentorship, networking resources

#### 📰 Cloud Security News (120+ Articles)
- **Latest articles** sorted by publication date (newest first)
- **Multi-source aggregation** - SecurityWeek, KrebsOnSecurity, CrowdStrike, AWS Security Blog, Microsoft MSRC, SANS ISC, The Register, BleepingComputer, Dark Reading, Palo Alto Unit 42, CISA, and more
- **Searchable & filterable** by source, topic, date
- **Auto-updated every 3 hours** via Python news aggregation script
- **Rich snippet optimization** for featured search results

### 💬 Chat Resources (`chat-resources.html`)
Community-shared resources from weekly Zoom sessions:
- **580+ URLs** shared by community members during live sessions
- **Security validated** - All URLs automatically checked for malicious patterns
- **Filterable by date, person, category** - Find resources from specific sessions
- **Descriptive titles** - Auto-generated from page content
- **Continuous protection** - GitHub Actions workflow validates new URLs before merge

### 📅 Zoom Sessions (`sessions.html`)
Information about weekly community gatherings:
- **When:** Every Friday at 7am PT
- **Format:** Expert presentations + open discussion + Q&A
- **Cost:** Completely free
- **Registration Link:** https://csoh.kit.com/39feb4f397
- Format details and speaker information

### 🏟️ Conferences (`conferences.html`)
A practitioner's directory of security and hacker conferences worldwide - RSA, DEF CON, Black Hat, fwd:cloudsec, KubeCon, CCC, Troopers, OffensiveCon, HITB, NULLCON, BSides, ShmooCon, Pwn2Own, and the rest. Each entry covers what makes the event unique plus its honest pros and cons.

### 🎬 Presentations (`presentations.html`)
Archive of past Zoom session presentations:
- Recorded sessions from industry experts
- Topic tags (AWS, Azure, GCP, Kubernetes, CSPM, CNAPP, etc.)
- Dates and presentation descriptions
- Direct video links

### 📝 Meeting Recaps (`meetings.html`)
Topic-by-topic recaps of every weekly session:
- **<!--count:meetings-->102<!--/count--> meeting recaps** with per-topic summaries and speaker notes
- Searchable, filterable by tag (AWS, Azure, AI, supply chain, conferences, etc.)
- **Speaker filter** - auto-detects recurring community members across recaps and surfaces a one-click filter row (Shawn, Neil, Jay, Matt, etc.) with appearance counts
- Auto-ingested from Zoom AI Companion summaries or VTT transcripts via `tools/add_meeting.py`

### 🚩 Cloud CTFs (`ctfs.html`)
Dedicated directory for hands-on cloud CTF challenges:
- **39+ challenges** across AWS, Azure, GCP, Kubernetes, and AI security
- Includes the full Wiz Cloud Security Championship calendar
- Submit a new CTF with `python3 tools/submit_ctf.py` - see [CONTRIBUTING_CTFS.md](CONTRIBUTING_CTFS.md)

### 📡 RSS Subscribe (`rss.html`)
Plain-English landing page for the `feed.xml` feed: explains what RSS is, recommends readers (Feedly, Inoreader, NetNewsWire, Thunderbird), and gives one-click subscribe instructions.

### 📖 Glossary (`glossary.html`)
A plain-English glossary of cloud-security acronyms and concepts:
- **300+ terms** across 13 sections - cloud models, IAM, network, data, detection, the *PM family, supply-chain, ATT&CK, AI/LLM, DevOps, standards bodies
- **Live search** filters terms and definitions as you type, hiding sections with no matches
- **Cross-linked**: every glossary term mentioned in any other definition is automatically hyperlinked to its entry - see `tools/crosslink_glossary.py`
- Targeted terms (arrived via `#term-...` anchor) get a yellow highlight so the reader can immediately spot them

### ❓ FAQ (`faq.html`)
Frequently asked questions covering CSOH's format, mailing list, recording policy, contributing, and presenter pitches. Backed by `FAQPage` schema for rich-snippet eligibility.

### 🌐 About CSOH (`about.html`)
The mission-and-ethos page: who we are, why CSOH is vendor-neutral and free, and how the community operates. The founder bio with full `Person` / `ProfilePage` schema lives separately at `about-shawn-nunley.html` (see [Author authority](#author-authority-e-e-a-t)).

### 🤝 Code of Conduct (`code-of-conduct.html`)
Community standards for every CSOH-organized space - Friday Zoom session, mailing list, GitHub repo. Covers expected and unacceptable behavior, reporting, and enforcement. Adapted from the Contributor Covenant.

### 🔐 Privacy Policy (`privacy.html`)
Plain-English privacy policy. Short version: no cookies, no analytics, no marketing trackers, never sell or share data. The only personal data we hold is your mailing-list email. External links are scrubbed of tracking parameters before publication.

### 🔒 Security Policy (`security-policy.html`)
RFC 9116-compliant vulnerability disclosure policy. Mirrored at `/.well-known/security.txt`.

### 🔬 Threat Research (`threat-research.html`)
Curated directory of primary sources for cloud-focused threat intel - vendor research teams, annual threat reports, IOC feeds, attack frameworks, and government advisories. Companion to `breach-timeline.html`: kill chains cover specific historical incidents, threat-research is the living index of where defenders go for ongoing intel. See the full section below.

---

## 🔗 Breach Kill Chains (`breach-timeline.html`)

A community-maintained library of **step-by-step cloud breach reconstructions**, mapped to MITRE ATT&CK Cloud techniques and sourced from official post-mortems.

### Current incidents covered

| Incident | Year | Provider | Key Techniques |
|---|---|---|---|
| Mitnick / Novell | 1994 | On-Prem | Social engineering, pretexting, credential theft |
| Capital One | 2019 | AWS | T1190, T1552.005, T1619, T1530 |
| SolarWinds | 2020 | Azure AD / AWS | T1195.002, T1071.004, T1606.002, T1114.002 |
| Uber | 2022 | AWS / GCP | T1078, T1621, T1552.001, T1078.004 |
| LastPass | 2022-2023 | LastPass / AWS S3 | T1195.002, T1203, T1555, T1530 |
| Storm-0558 | 2023 | Azure | T1078, T1552, T1606.001, T1114.002 |
| Microsoft SAS Leak | 2023 | Azure | T1552.004, T1530 |
| Scattered Spider / MGM | 2023 | Okta / Azure | T1598, T1078, T1484, T1486 |
| Snowflake / UNC5537 | 2024 | Snowflake | T1078.004, T1555.003, T1530, T1657 |
| Promptware | 2024-2026 | AI / LLM (Gemini, Copilot) | T1566, T1071.001, T1534, T1530 |
| Codefinger / S3 | 2025 | AWS S3 | T1552, T1078.004, T1486, T1657 |
| tj-actions/changed-files | 2025 | GitHub Actions | T1195.001, T1552.001, T1078 |
| Salesloft Drift / UNC6395 | 2025 | Salesforce / SaaS | T1528, T1078.004, T1213, T1530 |

The recurring root causes across all of these are synthesized in **[breach-lessons.html](https://csoh.org/breach-lessons.html)**, and the incidents that defined this past year are collected in the **[2025 Cloud Breach Year in Review](https://csoh.org/cloud-breach-year-in-review-2025.html)**.

### How to contribute a kill chain

See **[CONTRIBUTING_KILL_CHAINS.md](CONTRIBUTING_KILL_CHAINS.md)** for the full guide including:
- What qualifies as a good kill chain entry
- A list of candidate incidents with good post-mortems
- The HTML template to copy for a new entry
- The quality checklist before submitting

To **nominate an incident** without writing it yourself, open an issue using the **"🔗 New Kill Chain Request"** template.

### The standard

Kill chain entries require:
- A real post-mortem or official technical disclosure (vendor blog, CISA advisory, court documents)
- Step-by-step technical detail - not just a summary
- Every step mapped to a MITRE ATT&CK Cloud technique
- Actionable defender recommendations tied to specific controls

This is intentionally high-bar. A small number of deeply researched entries is more valuable than many shallow ones.

---

## 🔬 Threat Research (`threat-research.html`)

A curated directory of primary sources for cloud-focused threat research. Unlike Breach Kill Chains (which documents specific historical incidents), this page is a living index of where cloud defenders go for ongoing intel.

### Sections

- **Vendor Research Teams** - Wiz Research, Unit 42, Mandiant, Microsoft Threat Intelligence, Google TAG, CrowdStrike Counter Adversary Ops, SentinelLabs, Datadog Security Labs, Sysdig TRT, Aqua Nautilus, Permiso, Cado Security, AWS Security Bulletins, MSRC, IBM X-Force, Trellix, Proofpoint
- **Annual Threat Reports** - Mandiant M-Trends, CrowdStrike Global Threat Report, Unit 42 Cloud Threat Report, Verizon DBIR, IBM X-Force Index, Datadog State of Cloud Security, CSA Top Threats, ENISA, Sophos State of Ransomware
- **Notable Incidents & Post-Mortems** - cross-links to `breach-timeline.html` plus primary sources for Capital One, Storm-0558, SolarWinds, LastPass, Scattered Spider/MGM, Snowflake/UNC5537, Uber, Microsoft SAS Token Leak, Codecov, Okta HAR
- **IOC Feeds & Threat Intel Platforms** - AlienVault OTX, abuse.ch, VirusTotal, MISP, Shodan, GreyNoise, Censys, CIRCL, Feodo Tracker, Spamhaus, IBM X-Force Exchange, OSINT Framework
- **Attack Frameworks & Matrices** - MITRE ATT&CK Cloud / Containers, D3FEND, Microsoft Kubernetes Threat Matrix, OWASP Cloud-Native Top 10, TheHive, Sigma, Elastic Detection Rules
- **Government & Regulatory Advisories** - CISA (+KEV), FBI IC3, NSA, UK NCSC, ACSC, NIST NVD, CVE.org

### How to contribute a source

Edit `threat-research.html` directly - each link is a standard `.resource-card` in the same format as `resources.html` and `presentations.html`. Open a PR with:

- A link to the primary research output (blog index, report landing page, or feed URL - not a marketing page)
- A one-sentence description of what's unique about the source
- 2-3 tags (use existing tag classes where possible: `ctf`, `tool`, `lab`, `certification`, `job`, `ai-security`, `new`)

---


## Features

- Static HTML - no database, no server-side code. Published active/active to AWS, GCP & Azure behind a single Cloudflare edge via keyless OIDC (see [How Automation Works](#-how-automation-works)).
- URL-safety gate - every PR is scanned for unsafe URLs before merge (`check_all_site_urls.py`).
- RSS feed - `feed.xml` regenerated with each news update. See [RSS_FEED_README.md](RSS_FEED_README.md).
- Dark mode - toggle plus `prefers-color-scheme` detection, persisted in `localStorage`.
- Schema markup - NewsArticle, FAQPage, Organization, Event, CollectionPage.
- Accessibility - semantic HTML5, ARIA labels, WCAG AA contrast in both themes.
- Search + tag filtering on news and resources pages.

---

## 📁 Project Structure

```
csoh.org/
├── index.html                  # Homepage with hero section & category overview
├── what-is-cloud-security.html # Pillar: vendor-neutral cloud-security overview (FAQ schema)
├── learning-path.html          # Beginner→advanced roadmap (HowTo schema)
├── cloud-security-degree-programs.html # Academic paths and university programs (FAQ schema)
├── cloud-security-careers.html        # Roles, salaries, interviews, portfolio (FAQ schema)
├── cloud-security-home-lab.html       # Free-tier setups, budget guardrails, kill-switches
├── cloud-security-certifications.html # CCSK / CCSP / AWS / Azure / GCP / CKS comparison
├── cloud-security-reading-list.html   # Curated reading list (staleness-checked monthly)
├── cloud-security-portfolio-projects.html # Portfolio projects hub (walkthroughs in portfolio/)
├── cloud-security-<role>.html         # Career role-in-depth series: engineer, architect,
│                                      #   iam-architect, appsec-engineer, cnapp-analyst,
│                                      #   detection-engineer, incident-responder, penetration-tester,
│                                      #   platform-engineer, grc-engineer, sales-engineer,
│                                      #   customer-success-engineer (FAQ schema)
├── help-desk-to-cloud-security.html   # Transition guide: IT help desk -> cloud security
├── github-actions.html         # Learn GitHub Actions via our heavily-commented workflows
├── cloud-deployment.html       # Multi-cloud deploy architecture (the dogfooded stack)
├── terraform.html              # Learn Terraform via our own multi-cloud IaC
├── version-control.html        # Git & version-control fundamentals via this repo
├── resources.html              # Main resource directory (380+ resources in 6 categories)
├── news.html                   # Cloud security news (120+ articles)
├── chat-resources.html         # Community-shared URLs from Zoom sessions (580+ URLs)
├── sessions.html               # Weekly Zoom session information
├── community.html              # Community & Signal chat
├── mentorship.html             # Community mentorship program
├── presentations.html          # Archive of recorded presentations
├── meetings.html               # Weekly meeting recaps (102 entries, topic-by-topic)
├── ctfs.html                   # Dedicated cloud CTF directory (39+ challenges)
├── conferences.html            # Security & hacker conferences directory with pros/cons
├── rss.html                    # Landing page explaining the RSS feed to subscribers
├── glossary.html               # 300+ cloud security terms with live search & cross-links
├── faq.html                    # Frequently asked questions (FAQPage schema)
├── code-of-conduct.html        # Community Code of Conduct
├── privacy.html                # Privacy Policy (no cookies, no trackers, no on-site ads)
├── about.html                  # About CSOH: mission and ethos
├── about-shawn-nunley.html     # Founder bio (Person / ProfilePage schema, E-E-A-T)
├── breach-timeline.html        # Index of breach kill chains (per-breach pages live in /breaches/)
├── breach-lessons.html         # Cross-incident synthesis: recurring root causes across the 13 chains
├── cloud-breach-year-in-review-2025.html  # The cloud/SaaS/supply-chain breaches that defined 2025
├── breaches/                   # 13 per-breach kill chain pages (Capital One, SolarWinds, etc.)
├── meetings/                   # 102 per-meeting recap pages (split from meetings.html)
├── portfolio/                  # 7 hands-on portfolio-project walkthroughs (see hub page above)
├── cloud-security-best-practices.html  # Practitioner's controls checklist
├── shared-responsibility-model.html    # Provider vs. customer security split
├── cspm-vs-cnapp.html                  # Tool-category comparison
├── landing-zones.html                  # Cloud foundations (AWS / Azure / GCP reference designs)
├── containers.html                     # Container security: boundary, escapes, IMDS, supply chain
├── kubernetes.html                     # Kubernetes & managed K8s (EKS / AKS / GKE) security
├── serverless.html                     # Lambda / Functions security - event injection, IAM, denial of wallet
├── ci-cd.html                          # CI/CD pipelines for cloud, OIDC federation, deploy strategies
├── cloud-soc.html                      # Cloud threat monitoring, SIEM, detection engineering, IR
├── threat-research.html        # Curated cloud threat research directory
├── contribute.html             # General contributions guide
├── contribute-resources.html   # Resource submission web form / guide
├── security-policy.html        # Security disclosure policy page
├── kevin-mitnick.html          # Special resource page
├── 403.html                    # Custom 403 (Forbidden) error page
├── 404.html                    # Custom 404 (Not Found) error page
│
├── style.css                   # Main stylesheet (responsive design + dark mode)
├── main.js                     # Shared interactive features (search, filter, sort, dark mode)
├── chat-resources.js           # chat-resources.html-specific filtering/search
├── meetings.js                 # meetings.html-specific index + filters + speaker filter
├── glossary.js                 # glossary.html-specific search/filter
├── breach-timeline.css         # breach-timeline.html-specific styles
├── breach-timeline.js          # breach-timeline.html-specific tab/panel logic
├── feed.xml                    # RSS feed (auto-generated by update_news.py)
├── meetings-search-index.json  # Search index for meeting recaps (auto-generated)
│
├── sitemap.xml                 # XML sitemap for search engines
├── robots.txt                  # Search engine crawling rules
├── security.txt                # Security.txt (root copy)
├── .well-known/                # Well-known endpoints
│   └── security.txt            # Security.txt (RFC 9116 location)
│
├── img/                        # Images and preview thumbnails
│   └── previews/               # Resource preview images
├── chat-screenshots/           # Per-URL screenshots shown in chat-resources.html
│
├── tools/                      # Automation and maintenance scripts
│   ├── submit_resource.py                  # Interactive tool for submitting new resources
│   ├── submit_news_source.py               # Interactive tool for submitting news sources
│   ├── submit_ctf.py                       # Interactive tool for submitting cloud CTFs
│   ├── add_meeting.py                      # Append a new meeting recap from an Apple Notes HTML export
│   ├── fetch_zoom_transcript.py            # Pull a VTT transcript from a Zoom cloud recording (OAuth)
│   ├── backfill_zoom_summaries.py          # Bulk-import Zoom AI Companion meeting summaries
│   ├── generate_preview.py                 # Generate preview screenshots for resources
│   ├── generate_rss.py                     # Regenerate feed.xml from news.html
│   ├── normalize_urls.py                   # URL normalizer (tracking params, HTTPS, redirects)
│   ├── check_url_safety.py                 # Core URL safety validator with pattern matching
│   ├── check_all_site_urls.py              # Comprehensive site-wide URL scanner
│   ├── update_sitemap.py                   # Refresh sitemap.xml <lastmod> dates from git history
│   ├── update_presentations_schema.py      # Regenerate VideoObject JSON-LD on presentations.html
│   ├── crosslink_glossary.py               # Auto-link every glossary term mention to its <dt> entry
│   ├── crosslink_pages.py                  # Auto-link glossary terms across the rest of the site
│   ├── build_meetings_search_index.py      # Build meetings-search-index.json from meetings.html
│   ├── build_search_index.py               # Build site-wide search-index.json (sections + glossary)
│   ├── sync_chrome.py                      # Stamp ONE canonical nav + footer onto every page
│   ├── inject_meeting_topic_links.py       # Inject contextual topic-page links into recaps
│   ├── generate_og_images.py               # Generate 1200x630 OG social images (top-level pages)
│   ├── generate_meeting_og_images.py       # Generate OG images for meeting recaps
│   ├── generate_news_banners.py            # Generate banner images for news sources
│   ├── generate_webp.py                    # Generate .webp siblings for raster images
│   ├── wrap_img_webp.py                    # Wrap <img> in <picture> with a WebP <source>
│   ├── run_seo_audit.py                    # Deterministic structural SEO audit -> SCORECARD
│   ├── check_pagespeed.py                  # Google PageSpeed Insights run -> SCORECARD
│   ├── check_lighthouse.py                 # Lighthouse SEO / a11y / perf threshold check
│   ├── check_mobile_layout.py              # Mobile layout regression check
│   ├── check_news_banners.py               # Verify every news source has a banner image
│   ├── check_no_inline_scripts.py          # CI gate: no inline <script> blocks in HTML
│   ├── check_svg_dimensions.py             # CI gate: width/height on every <svg> with viewBox
│   ├── check_reading_list_staleness.py     # Flag stale reading-list sources (monthly)
│   ├── SUBMIT_RESOURCE_README.md           # Interactive resource submission docs
│   ├── SUBMIT_RESOURCE_EXAMPLE.md          # Walkthrough example for the resource tool
│   ├── SUBMIT_NEWS_SOURCE_README.md        # News source submission docs
│   ├── SUBMIT_CTF_README.md                # CTF submission docs
│   ├── ADD_MEETING_README.md               # Meeting recap ingest docs
│   ├── FETCH_ZOOM_TRANSCRIPT_README.md     # Zoom transcript fetch docs (OAuth setup)
│   ├── BACKFILL_ZOOM_SUMMARIES_README.md   # Bulk Zoom AI Companion backfill docs
│   ├── GENERATE_PREVIEW_README.md          # Preview image generation docs
│   ├── CHECK_URL_SAFETY_README.md          # URL safety checker docs
│   ├── UPDATE_NEWS_README.md               # News aggregation pipeline docs
│   ├── UPDATE_SRI_README.md                # SRI hash generator docs
│   ├── UPDATE_SITEMAP_README.md            # Sitemap refresher docs
│   ├── UPDATE_PRESENTATIONS_SCHEMA_README.md # Presentations VideoObject schema docs
│   ├── CROSSLINK_GLOSSARY_README.md        # Glossary cross-linking docs
│   └── CROSSLINK_PAGES_README.md          # Cross-page glossary term linking docs
│
├── update_news.py              # News aggregation script (39 RSS feeds, runs every 3 hours)
├── update_sri.py               # Updates SRI hashes & cache-bust params across HTML files
│
├── .github/workflows/
│   ├── update-news.yml              # Automated news + RSS feed updates (every 3 hours)
│   ├── update-resources.yml         # Weekly auto-generation of resource previews
│   ├── site-update-deploy.yml       # Unified workflow: SRI, URL normalization, previews, presentations schema, sitemap, deploy
│   ├── check-url-safety.yml         # URL safety validation on PRs + weekly
│   ├── normalize-urls.yml           # Monthly URL normalization (tracking params, redirects)
│   ├── validate-html.yml            # HTML5 validation on PRs + weekly
│   ├── lint.yml                     # actionlint + ruff + yamllint on every push/PR
│   ├── check-broken-links.yml       # Broken link checker (PRs + weekly)
│   ├── check-reading-list-staleness.yml # Monthly reading-list feed staleness -> tracking issue
│   ├── check-meeting-staleness.yml   # Weekly check that the newest recap isn't stale -> sticky issue
│   ├── update-counts.yml            # Weekly: recompute site counts + refresh count share-cards
│   ├── check-pagespeed.yml          # Weekly Google PageSpeed Insights run → SCORECARD row + regression issue (Mon 14:00 UTC)
│   ├── run-seo-audit.yml            # Weekly deterministic structural SEO audit → SCORECARD row + regression issue (Mon 14:15 UTC)
│   ├── deploy.yml                   # Build once, publish to AWS + GCP + Azure (keyless OIDC)
│   └── CHECK_URL_SAFETY_WORKFLOW.md # Workflow configuration notes
│
├── preview-mapping.json        # Metadata for resource previews
│
├── .htaccess                   # Apache server config (security headers, caching, compression)
├── nginx.conf                  # Nginx server config (Docker deployments)
├── Dockerfile                  # Container build for local/Docker deployments
├── docker-compose.yml          # Compose config for the Dockerized site
├── .env.example                # Template for Zoom OAuth + other secrets (.env is gitignored)
├── .lychee.toml                # Config for the broken-link-checker workflow
├── .yamllint.yml               # Config for the yamllint job in lint.yml
├── pyproject.toml              # Config for the ruff job in lint.yml (Python lint)
├── .editorconfig               # Editor consistency rules
├── .dockerignore               # Files excluded from the Docker build context
│
├── infra/                      # Infrastructure-as-code for the multi-cloud deploy
│   ├── README.md               # Architecture, cost, and cutover runbook
│   └── terraform/              # Terraform for AWS, GCP, Azure & Cloudflare - every .tf file
│       │                       #   commented line by line so a newcomer can read it
│       ├── aws/                # S3 + CloudFront origin, OIDC deploy role
│       ├── gcp/                # Cloud Run origin, Workload Identity Federation, Artifact Registry
│       ├── azure/              # Blob static-website origin, federated identity
│       └── cloudflare/         # Edge: zone, rules, active/active load balancer + health checks
│
├── CONTRIBUTING.md             # Umbrella contributing guide
├── CONTRIBUTING_RESOURCES.md   # Contributing resources specifically
├── CONTRIBUTING_CTFS.md        # Contributing CTFs specifically
├── CONTRIBUTING_KILL_CHAINS.md # Contributing breach kill chains specifically
├── DEVELOPMENT.md              # Local development setup & architecture
├── SECURITY.md                 # Security reporting policy
├── RSS_FEED_README.md          # RSS feed usage guide for subscribers
├── .gitignore                  # Git exclusion rules
├── README.md                   # This file
└── LICENSE                     # Open content license
```

---

## 🛠️ Managing Content

### Adding a New Resource

**Fastest option:** Run `python3 tools/submit_resource.py` to add a resource interactively.
**Script guide:** [tools/SUBMIT_RESOURCE_README.md](tools/SUBMIT_RESOURCE_README.md)

1. **Open `resources.html`** in your editor
2. **Locate the appropriate section** (CTF, Labs, Tools, etc.)
3. **Add a new resource card** before the closing `</div>` of the section:

```html
<a href="https://resource-url.com" target="_blank" class="card-link" rel="noopener noreferrer">
    <div class="resource-card" data-tooltip="Extended 2-3 sentence description shown on hover. Cover what makes it unique, who benefits most, and prerequisites or cost.">
        <img src="img/previews/resource-url.com.jpg" alt="Preview" class="resource-preview">
        <h3>Resource Name</h3>
        <p>Brief description of what this resource offers and why it's valuable for cloud security professionals.</p>
        <div class="resource-tags">
            <span class="tag">AWS</span>
            <span class="tag">Security</span>
            <span class="tag new">NEW</span>
        </div>
    </div>
</a>
```

**Preview images:** If you do not have a preview image, the workflow will automatically capture a screenshot and update `preview-mapping.json` after you open a PR.

4. **Commit and push** to update the live site

### Adding a New Article to News

News articles are **updated automatically** - you don't need to add them by hand. A GitHub Actions workflow runs every 3 hours, pulls articles from 39 cloud security RSS feeds, and creates a pull request with the new content. See the [How Automation Works](#-how-automation-works) section below for details, or read the full docs in [tools/UPDATE_NEWS_README.md](tools/UPDATE_NEWS_README.md).

To **add a new news source**, either:

1. Run `python3 tools/submit_news_source.py` (interactive, recommended)
2. Or edit the `FEEDS` list at the top of `update_news.py` manually

**Script guide:** [tools/SUBMIT_NEWS_SOURCE_README.md](tools/SUBMIT_NEWS_SOURCE_README.md)

### Adding a New Zoom Session or Presentation

1. **For Sessions:** Edit `sessions.html` to add session details

2. **For Presentations:** Edit `presentations.html` and add a new card with:
   - Date and title
   - Speaker name
   - Description
   - Topic tags
   - Video/presentation link

### Adding a New Meeting Recap

Meeting recaps live on `meetings.html` and are ingested from Zoom, not written by hand. Two automation paths:

- **Single meeting from a VTT transcript:** `python3 tools/fetch_zoom_transcript.py` pulls the transcript from your Zoom cloud recording, then `python3 tools/add_meeting.py <note>` appends a new `<article>` block to `meetings.html`. See [tools/FETCH_ZOOM_TRANSCRIPT_README.md](tools/FETCH_ZOOM_TRANSCRIPT_README.md) and [tools/ADD_MEETING_README.md](tools/ADD_MEETING_README.md).
- **Bulk backfill from Zoom AI Companion summaries:** `python3 tools/backfill_zoom_summaries.py` imports every AI Companion summary on the account in one pass. See [tools/BACKFILL_ZOOM_SUMMARIES_README.md](tools/BACKFILL_ZOOM_SUMMARIES_README.md).

Both require Zoom Server-to-Server OAuth credentials in a local `.env` (see `.env.example`).

### Adding a New CTF

Run `python3 tools/submit_ctf.py` to add a challenge to `ctfs.html` interactively. See [tools/SUBMIT_CTF_README.md](tools/SUBMIT_CTF_README.md) for the script, or [CONTRIBUTING_CTFS.md](CONTRIBUTING_CTFS.md) for the full contribution guide.

### Adding a Glossary Term

1. Open `glossary.html` and locate the right `<h2 id="...">` section (cloud models, compute/containers, IAM, network, data, detection, posture, vuln, compliance, attack, AI, ops, standards bodies).
2. Add a new `<dt>...</dt>` + `<dd>...</dd>` pair anywhere inside that section's `<dl class="glossary-list">`. Format the headword as `ABBR - Long Form` or just `Term Name`; aliases can be separated by `/`.
3. Run `python3 tools/crosslink_glossary.py` - it will:
   - Add an `id="term-..."` to your new `<dt>`.
   - Hyperlink your new term wherever it appears in other definitions.
   - Hyperlink any existing terms that appear in your new definition.
4. Update the search-bar count and OG description if the total moved past a round number.

The script is idempotent and safe to re-run. See [tools/CROSSLINK_GLOSSARY_README.md](tools/CROSSLINK_GLOSSARY_README.md) for details.

### Customizing the Homepage

Edit the "Resource Categories" section in `index.html` to:
- Change category descriptions
- Modify call-to-action buttons
- Adjust hero section messaging

---

## 🤖 How Automation Works


This site uses **GitHub Actions workflows** to automate all major site updates. Most automation is now handled by a **unified workflow** that runs all key steps in sequence, only when needed.

### Site Housekeeping Workflow

**Workflow file:** `.github/workflows/site-update-deploy.yml`

**Triggers on pushes to `main` when these files change:**
- `*.html`
- `style.css`, `main.js`, `chat-resources.js`, `breach-timeline.css`, `breach-timeline.js`
- `chat-screenshots/**`, `img/**`
- `update_sri.py`
- Manual trigger via the GitHub Actions tab

**What it does (housekeeping only - actual deploy is `deploy.yml`):**
- Updates SRI hashes and cache-busting tags if CSS/JS changed (using `update_sri.py`)
- Checks URL safety - blocks normalization if unsafe URLs are detected (using `check_all_site_urls.py`)
- Normalizes URLs - strips tracking parameters, upgrades HTTP to HTTPS, resolves redirects (using `normalize_urls.py`)
- Regenerates the `VideoObject` JSON-LD on `presentations.html` (using `update_presentations_schema.py`)
- Rebuilds the meetings.html search index
- Refreshes `<lastmod>` dates in `sitemap.xml` from git history (using `update_sitemap.py`)
- Generates preview images for new resources in `resources.html` (using `generate_preview.py`)
- Optimizes generated images
- Each step that mutates files commits the change back to `main` (with `[skip ci]` markers) so the next workflow run sees fresh state

**Why this is separate from the deploy:** these housekeeping commits carry `[skip ci]`, so they do NOT trigger `deploy.yml` (that would loop). `deploy.yml` runs independently from the original content push that started this workflow; the housekeeping commits land in `main` and ship with the next deploy. Splitting them keeps each workflow's responsibility narrow.

**News updates** are still handled by a separate scheduled workflow (`update-news.yml`) that runs every 3 hours and creates a PR with new articles. Once merged, the housekeeping workflow runs against the new content, then `deploy.yml` ships it.

### Standalone URL Normalization Workflow

**Workflow file:** `.github/workflows/normalize-urls.yml`

In addition to the URL normalization that runs as part of every deploy, a **standalone monthly workflow** performs a deeper pass across all HTML files:

- **Schedule:** Monthly on the 1st at 08:00 UTC (also available via manual trigger)
- **What it does:**
  - Checks URL safety first - blocks normalization if unsafe URLs are found
  - Strips tracking parameters (`utm_*`, `fbclid`, `gclid`, `msclkid`, etc.)
  - Upgrades HTTP links to HTTPS
  - Resolves redirecting URLs to their final destinations
- **Output:** Creates a PR with a detailed report of all changes, auto-approved for review

**Full docs:** See [tools/UPDATE_SRI_README.md](tools/UPDATE_SRI_README.md), [tools/GENERATE_PREVIEW_README.md](tools/GENERATE_PREVIEW_README.md), [tools/UPDATE_NEWS_README.md](tools/UPDATE_NEWS_README.md), and [tools/CHECK_URL_SAFETY_README.md](tools/CHECK_URL_SAFETY_README.md)

### Multi-Cloud Deploy Workflow

**Workflow file:** `.github/workflows/deploy.yml`

Builds the site once, then publishes it active/active to three cloud origins behind Cloudflare. This is the workflow that actually publishes csoh.org to production.

**Triggers on pushes to `main` when these files change:**
- The same path filters as `site-update-deploy.yml` (HTML, CSS, JS, screenshots, images)
- `Dockerfile`, `nginx.conf`, `tools/stage_site.sh`, `tools/site-publish.filter`, `.github/workflows/deploy.yml`
- Manual trigger via the GitHub Actions tab

**What it does - build once, fan out:**
- **build:** regenerates the search index and runs `tools/stage_site.sh` to produce `dist/` (the public file set - mirrors nginx block rules + the Dockerfile strip list), uploaded as an artifact so all origins serve byte-identical content.
- **publish-aws:** assumes an IAM role via OIDC, `aws s3 sync --delete` to the private bucket, invalidates CloudFront.
- **publish-azure:** logs in via an Entra federated credential (OIDC), `az storage blob sync` into the `$web` static-website container.
- **publish-gcp:** builds the `Dockerfile` (digest-pinned `nginx:1.27-alpine` + `apk upgrade`), Trivy-scans (fails on fixable HIGH/CRITICAL), pushes an immutable SHA tag to Artifact Registry, deploys a Cloud Run revision. Auth is Workload Identity Federation - no stored key.

Every cloud uses **keyless OIDC** - no long-lived cloud credentials in the repo. Non-secret resource IDs come from repo Variables (see [infra/README.md](infra/README.md)).

**Edge in front of all three origins:** Cloudflare (Free plan + Load Balancing add-on) terminates TLS, caches, runs the WAF (free managed ruleset), sets security headers, applies legacy redirects, and load-balances active/active across the origins with health-check failover. (This replaced the old GCP Global HTTPS load balancer + Cloud Armor + Cloud CDN, which were redundant with Cloudflare and cost ~$100/mo.)

**Full architecture, cost, and cutover runbook:** [infra/README.md](infra/README.md). The full security walkthrough is the public teaching page [cloud-deployment.html](cloud-deployment.html). Security model and rotation: [SECURITY.md → Deployment Security](SECURITY.md#deployment-security).

### Setup Note

Workflows authenticate to GitHub via a **GitHub App** (`csoh-ci`) that mints short-lived (~1h) installation tokens at job start, plus a small fine-grained PAT (`CSOH_PAT`) used only to approve App-opened PRs (GitHub blocks self-approval). The full model - App config, ruleset bypass, why one PAT remains - is documented in [SECURITY.md → CI/CD Authentication](SECURITY.md#cicd-authentication). Setup / rotation steps for the PAT are in [tools/UPDATE_NEWS_README.md](tools/UPDATE_NEWS_README.md#setup-requirements).

`deploy.yml` does *not* use the GitHub App - it authenticates to each cloud via keyless OIDC (GCP Workload Identity Federation, an AWS IAM role, an Azure Entra federated credential) and only needs the auto-injected `GITHUB_TOKEN` (with `id-token: write` for the OIDC exchanges). There is no cloud-side credential to set up or rotate for any of the three.

### Weekly SEO Monitoring Workflows

Two complementary workflows run every Monday around 14:00 UTC to keep `seo-audits/SCORECARD.md` current without manual cadence. Both follow the same csoh-ci App + `CSOH_PAT` pattern as `update-news.yml`: PR-based update, auto-approved, auto-merged. The deploy and site-housekeeping workflows have path filters that exclude `seo-audits/`, so SCORECARD-only changes naturally don't trigger a redeploy. Both file a tracking issue (label `regression`) if the overall score dropped vs the previous row.

**`check-pagespeed.yml` - Mondays 14:00 UTC**

Runs `tools/check_pagespeed.py` against `https://csoh.org/` - mobile + desktop in parallel - using Google's PageSpeed Insights v5 API. Captures the four Lighthouse category scores (Performance / Accessibility / Best Practices / SEO), lab Core Web Vitals (LCP, CLS, TBT, FCP, Speed Index), and for any category < 100 the specific failing audit IDs plus the failing DOM nodes' CSS selectors. Appends a row to the PageSpeed Insights table in SCORECARD.md. Requires `PSI_API_KEY` repo secret (free key from [console.cloud.google.com/apis/credentials](https://console.cloud.google.com/apis/credentials), restricted to "PageSpeed Insights API").

**`run-seo-audit.yml` - Mondays 14:15 UTC**

Runs `tools/run_seo_audit.py` - a deterministic structural SEO audit across every indexable HTML page (top-level + breaches + portfolio + meetings; the script counts them at runtime). Mirrors the mechanical checks the `/seo-audit` skill does: canonical, title 30-65 chars, meta description 100-165 chars, og:image ≠ banner.png, full Twitter Card, single H1, robots meta, JSON-LD presence, image alt coverage, `<html lang>`. Writes a per-day report under `seo-audits/YYYY-MM-DD.md` and appends a row to the Internal SEO audit table. Stdlib-only, no API costs, no LLM calls.

For qualitative depth (internal-linking strategy, content depth, AI visibility, topical authority) that the deterministic script can't reason about, invoke `/seo-audit` from Claude Code manually and add a row off-cycle.

**Full docs:** [tools/CHECK_PAGESPEED_README.md](tools/CHECK_PAGESPEED_README.md), [tools/RUN_SEO_AUDIT_README.md](tools/RUN_SEO_AUDIT_README.md).

### Monthly Reading-List Staleness Check

**Workflow file:** `.github/workflows/check-reading-list-staleness.yml`

Once a month, `tools/check_reading_list_staleness.py` walks every podcast / blog / newsletter / YouTube channel on `cloud-security-reading-list.html`, discovers its RSS/Atom feed, and flags anything whose newest post is older than the threshold. The reading list is hand-curated and opinionated, so this workflow **never edits the page** - it only opens (or updates) a single tracking issue with the report for a human to act on.

**Full docs:** [tools/CHECK_READING_LIST_STALENESS_README.md](tools/CHECK_READING_LIST_STALENESS_README.md).

---

## 🔍 SEO & Search Optimization

CSOH is engineered for organic discovery across traditional search (Google, Bing), AI search/answer engines (ChatGPT, Perplexity, Claude, Gemini), and social previews (LinkedIn, Twitter/X, Slack). The site uses no marketing trackers and no third-party-origin scripts - just clean semantic HTML, structured data, and disciplined metadata. Cookieless page-view analytics via GoatCounter (self-hosted script, no cookies, no cross-site tracking).

### Schema.org structured data (25+ types)

**Page-level schema** - each page declares what kind of thing it is:
- ✅ **Article** / **NewsArticle** - pillar pages and the news index, with `datePublished`, `dateModified`, `author`, `publisher`
- ✅ **HowTo** + **HowToStep** - step-by-step content (e.g. learning path, GitHub Actions guide)
- ✅ **Course** + **CourseInstance** - learning-path roadmap and certifications comparison (Google Course rich result eligible)
- ✅ **FAQPage** + **Question** / **Answer** - 60 pages with structured Q&A for featured snippets
- ✅ **CollectionPage** - resource hub pages eligible for sitelinks rich results
- ✅ **Event** + **VirtualLocation** + **Schedule** - weekly Friday Zoom session
- ✅ **VideoObject** - each YouTube talk on `presentations.html` and meeting recaps
- ✅ **DefinedTermSet** - the glossary, with 300+ individual terms

**Entity schema** - who/what is responsible for the content:
- ✅ **Organization** - CSOH itself, with founding date, contact point, sameAs links, search action
- ✅ **Person** + **ProfilePage** - founder bio with `jobTitle`, `worksFor`, `founder`, `knowsAbout`, `sameAs`
- ✅ **Author attribution** - pillar articles credit the Person via `@id` reference (E-E-A-T signal)
- ✅ **ItemList** - certifications comparison, news listings, and resource directories
- ✅ **BreadcrumbList** - full navigation hierarchy on every content page

### Author authority (E-E-A-T)

- ✅ Dedicated bio page at `/about-shawn-nunley.html` with full Person schema
- ✅ Visible "About the author" card at the bottom of all pillar articles (65 pages and counting)
- ✅ Visible byline + footer "Founded by" link site-wide
- ✅ `rel="author"` on every author link
- ✅ `sameAs` external profile links (LinkedIn, GitHub, csoh.org)

### Discoverability

- ✅ **`sitemap.xml`** - 218 URLs, `<lastmod>` refreshed from git commit dates on every deploy ([tools/update_sitemap.py](tools/update_sitemap.py))
- ✅ **`robots.txt`** - Allow: / for all major crawlers, plus explicit allow-rules for 21 AI/LLM bots (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended, CCBot, MistralAI-User, Cohere, etc.)
- ✅ **RSS feed** (`feed.xml`) for the news aggregator
- ✅ **`humans.txt`** for human-readable credits, linked via `<link rel="author">`
- ✅ **`security.txt`** at the well-known location for vulnerability disclosure
- ✅ Site-wide **canonical URLs** to consolidate ranking signals
- ✅ **Glossary cross-linking** - first occurrence of each of 300+ terms auto-linked to the glossary on every content page ([tools/crosslink_pages.py](tools/crosslink_pages.py))

### Social previews

- ✅ **Open Graph** + **Twitter Card** meta on every indexable page (title, description, type, url, image)
- ✅ **Per-article social images** - 170+ unique 1200×630 JPG previews under `img/og/` (top-level pages via [tools/generate_og_images.py](tools/generate_og_images.py), 102 meeting recaps via [tools/generate_meeting_og_images.py](tools/generate_meeting_og_images.py)) so each page has its own LinkedIn/Slack/Twitter preview, not a generic site banner
- ✅ **`og:type`: profile** on the bio page with `profile:first_name` / `profile:last_name`

### Performance signals (Core Web Vitals)

- ✅ **WebP everywhere** - homepage banner, all 36 news-source banners, and the author photo all serve WebP via `<picture>` with JPG/PNG fallback (≈40-60% smaller payloads)
- ✅ **`<link rel="preload">`** for critical CSS, with **SRI integrity hashes** auto-updated on every deploy
- ✅ **`loading="lazy"`** on below-the-fold images
- ✅ **`width` / `height`** attributes on every `<img>` to prevent CLS
- ✅ **`decoding="async"`** on hero images
- ✅ **PWA manifest** (`manifest.json`) + 192/512 maskable icons → "Add to Home Screen" eligible

### Content optimization discipline

- ✅ Title tags 45-60 chars, meta descriptions 120-160 chars on every indexable page
- ✅ One `<h1>` per page, semantic heading hierarchy
- ✅ `alt` text on every content image
- ✅ Skip links + ARIA labels for accessibility (which Google increasingly weighs)
- ✅ `lang="en"` on `<html>` for international targeting

### Privacy as an SEO signal

- ✅ Zero cookies, zero marketing trackers; cookieless page-view analytics only (GoatCounter, self-hosted script)
- ✅ Strict Content-Security-Policy
- ✅ HSTS preload-eligible
- ✅ All external scripts blocked at the CSP layer

The result: rich-snippet eligibility across Google's full catalog of result types, full author entity wiring for E-E-A-T, AI-search citation eligibility, and Core Web Vitals headroom from a static-HTML stack with no JS frameworks.

## 🤝 Contributing

Want to help improve CSOH? We have **beginner-friendly guides** for contributing - no coding experience needed!

### 📚 Contribution Guides

- **[Interactive Resource Submission Tool](tools/SUBMIT_RESOURCE_README.md)** - Automated Python script with URL validation and PR creation
- **[Interactive News Source Submission Tool](tools/SUBMIT_NEWS_SOURCE_README.md)** - Add RSS/Atom feeds with the interactive script
- **[How to Add a Resource](contribute-resources.html)** - Step-by-step guide for adding cloud security resources (tools, labs, certifications, etc.)
- **[General Contributions](contribute.html)** - Guide for all other contributions:
  - Adding news sources for our automated news aggregation
  - Improving descriptions and content
  - Suggesting resource reorganization
  - Reporting bugs or broken links
  - Feature requests and ideas

### Quick Start

**Easy options (no coding required):**
1. [Report an issue](https://github.com/CloudSecurityOfficeHours/csoh.org/issues) - Found a bug? Have a suggestion?
2. [Join the mailing list](https://csoh.kit.com/39feb4f397) - Get the weekly Zoom link and meeting info
3. [Add a resource](contribute-resources.html) - Use our web-based guide (copy/paste method)
4. [Use the submission tool](tools/SUBMIT_RESOURCE_README.md) - Interactive Python script (automated)
5. [Add a news source](tools/SUBMIT_NEWS_SOURCE_README.md) - Interactive Python script

**For developers:**
See **[DEVELOPMENT.md](DEVELOPMENT.md)** for the full local setup guide, project architecture, and testing instructions.

1. Fork the repository
2. Create a feature branch: `git checkout -b add-resource`
3. Run `python3 -m http.server 8091` and preview at `http://localhost:8091`
4. Make changes and test locally (check light mode, dark mode, and mobile layout)
5. Commit with clear messages: `git commit -m "Add AWS security labs resource"`
6. Push to your fork: `git push origin add-resource`
7. Create a Pull Request

### Contribution Guidelines

- All resources must be **free or freemium** (or worth including as premium option)
- Ensure **working links** before submitting
- Add **descriptive tags** (AWS, Azure, GCP, Kubernetes, CTF, Tools, Labs)
- Maintain **vendor neutrality** - no paid sponsorships without disclosure
- Follow existing **HTML/CSS conventions**

---

## 📞 Community & Support

### Join the Community
- **Mailing List**: https://csoh.kit.com/39feb4f397 - 2000+ subscribers; sign up to receive the weekly Friday Zoom link (7am PT)
- **GitHub**: https://github.com/CloudSecurityOfficeHours/csoh.org

### Need Help?
- **Email**: admin@csoh.org for general questions or to reach community admins
- **Issues**: Create a [GitHub issue](https://github.com/CloudSecurityOfficeHours/csoh.org/issues)
- **Friday Zoom**: Bring questions live - sign up at [csoh.kit.com](https://csoh.kit.com/39feb4f397) for the link

### Support CSOH
- ❤️ **Star** this repository
- 🔗 **Share** CSOH with your network
- 💬 **Contribute** resources or improvements
- 💰 **Donate** via [PayPal](https://www.paypal.com/paypalme/cloudsec) (optional, fully community-run)

### Policies
- 🤝 **[Code of Conduct](code-of-conduct.html)** - community standards across Friday Zoom, mailing list, and GitHub
- 🔐 **[Privacy Policy](privacy.html)** - no cookies, no trackers, no on-site ads
- 🔒 **[Security Policy](security-policy.html)** / [SECURITY.md](SECURITY.md) - coordinated disclosure

---

## 📜 License

This project is dual-licensed:

- **Website Code** (HTML markup, CSS, JS, Python, config): [MIT License](LICENSE) - fork, modify, and reuse freely with attribution.
- **Editorial Content** (articles, guides, glossary entries, breach reconstructions, resource descriptions): [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) - you may share with attribution, but no commercial use and no derivative works without permission.
- **Linked Resources**: Property of their respective creators/owners.
- **News Articles**: Linked to original sources with proper attribution.

For commercial licensing, republication, or permission to create derivatives, contact the site owner via [about-shawn-nunley.html](https://csoh.org/about-shawn-nunley.html).

Copyright © 2023-2026 Cloud Security Office Hours / Shawn Nunley

---

For the latest updates and announcements, sign up for the [mailing list](https://csoh.kit.com/39feb4f397).
