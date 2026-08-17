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
| 🗺️ [Vendor Landscape](https://csoh.org/vendor-landscape.html) | <!--count:vendors_floor-->300+<!--/count--> cloud-security vendors across <!--count:vendor_categories-->32<!--/count--> categories. No rankings, just orientation |
| 📖 [Glossary](https://csoh.org/glossary.html) | 310 cloud-security terms, plain-English, every cross-reference hyperlinked |
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
| 📰 [Cloud Security News](https://csoh.org/news.html) | 120+ articles, refreshed every 3 hours from 62 sources |
| 🔬 [Threat Research Sources](https://csoh.org/threat-research.html) | Curated directory of vendor research, IOC feeds, advisories - includes a Supply Chain Attacks section |
| 🔗 [Breach Kill Chains](https://csoh.org/breach-timeline.html) | <!--count:breaches-->45<!--/count--> real cloud breaches mapped to MITRE ATT&CK |
| 🛰️ [Cloud SOC & Threat Monitoring](https://csoh.org/cloud-soc.html) | Log-driven detection, native services, SIEM, detection engineering, IR |
| 🕵️ [Detection Engineering](https://csoh.org/detection-engineering.html) | Sigma, ATT&CK Cloud Matrix, detection-as-code, SIEM/lake/XDR |
| 🚨 [Incident Response & Forensics](https://csoh.org/incident-response.html) | IR lifecycle, EC2/EKS/Lambda evidence, memory forensics, runbooks |
| 🎯 [Cloud Pentesting & Red Teaming](https://csoh.org/cloud-pentesting.html) | AWS/Azure/GCP attack paths, Pacu/ROADtools/BloodHound, MITRE ATT&CK Cloud |
| 🚩 [CTF Challenges](https://csoh.org/ctfs.html) | 52+ hands-on cloud CTFs across AWS / Azure / GCP / Kubernetes / AI |

### Careers

#### Getting Started
| Guide | What it covers |
|---|---|
| 🧭 [Cloud Security Careers](https://csoh.org/cloud-security-careers.html) | Roles, salary bands, interview formats, portfolio projects |
| 🛣️ [Cloud Security Learning Path](https://csoh.org/learning-path.html) | Beginner → working practitioner roadmap with milestones |
| 🪜 [Help Desk → Cloud Security](https://csoh.org/breaking-into-cloud-security.html) | The realistic transition from IT support |
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
| 🏟️ [Conferences](https://csoh.org/conferences.html) | 26 security & hacker conferences, with pros & cons |

#### Archive
| Resource | What it covers |
|---|---|
| 📝 [Meeting Recaps](https://csoh.org/meetings.html) | <!--count:meetings-->107<!--/count--> weekly session recaps, searchable |
| 🎬 [Presentations](https://csoh.org/presentations.html) | Archive of recorded talks with topic tags and direct video links |
| 💬 [Chat Resources](https://csoh.org/chat-resources.html) | 580+ community-shared URLs from live sessions, security-validated |

## 📚 Reference & Practice

Cross-cutting entry points that sit outside the topic menus (everything else now lives under its nav section above):

| Resource | What it is |
|---|---|
| 🛡️ [Resources Directory](https://csoh.org/resources.html) | <!--count:resources_floor-->480+<!--/count--> tools, labs, CTFs, certifications - top-level nav link, auto-refreshed weekly |
| 🔍 [Site-wide Search](https://csoh.org/search.html) | MiniSearch full-text index across every page, with section-anchor results and synonym expansion |

---

## 🌐 About

Cloud Security Office Hours is a vendor-neutral, free community founded in February 2023. We meet on Zoom every Friday at 7am PT, share what we're learning, and maintain this resource hub. Everything on the site is free, no cookies, no cross-site trackers, no on-site advertising (the only analytics is GoatCounter, a cookieless page-view counter). (No sponsored content on the site or in the mailing list; hosting is offset by optional donations.)

Sign up for the weekly Zoom link at **[csoh.kit.com](https://csoh.kit.com/39feb4f397)**. Subscribe to our cloud-security news at **[csoh.org/feed.xml](https://csoh.org/feed.xml)** (or visit the [RSS subscribe page](https://csoh.org/rss.html) for setup help).

---

## 🎓 Getting Started

**New to cloud security?** It's the practice of protecting data, applications, and infrastructure hosted in cloud environments like AWS, Azure, and Google Cloud - one of the fastest-growing areas in cybersecurity.

Our recommended learning sequence:

1. **Get the Lay of the Land**: [What is Cloud Security?](https://csoh.org/what-is-cloud-security.html) - vendor-neutral pillar overview of the field
2. **Follow the Roadmap**: [Cloud Security Learning Path](https://csoh.org/learning-path.html) - beginner → advanced with milestones, free labs, study targets
3. **Master the Fundamentals**: [Best Practices](https://csoh.org/cloud-security-best-practices.html) and the [Shared Responsibility Model](https://csoh.org/shared-responsibility-model.html)
4. **Decode the Acronyms**: [Glossary](https://csoh.org/glossary.html) - 310 terms, every cross-reference hyperlinked
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
A series of one-page-per-role deep dives covering day-to-day work, the skills that actually matter, salary signals, and how to break in: Cloud Security Engineer, Cloud Security Architect (Staff+ IC), IAM / Identity Architect, Cloud AppSec / IaC Security Engineer, CSPM / CNAPP Analyst, Cloud Detection Engineer, Cloud Incident Responder (DFIR), Cloud Penetration Tester / Red Team, Security SRE / Platform Security Engineer, Cloud GRC / Compliance Engineer, Cloud Security Sales Engineer, and Cloud Security Customer Success Engineer. Each role page carries FAQ schema.

### 🛠️ Cloud Security Portfolio Projects (`cloud-security-portfolio-projects.html` + `portfolio/`)
A hub of build-it-yourself projects that demonstrate real cloud-security skill to hiring managers, each with a full step-by-step walkthrough under `portfolio/`: build a multi-account AWS Org with SCPs, walk every CloudGoat scenario, write a CNAPP comparison, build 5 detections in a lab SIEM, run a Prowler audit and Terraform the fixes, recreate the Capital One breach end to end, and ship a first OSS contribution to a cloud-security project.

### 🪜 Breaking Into Cloud Security (`breaking-into-cloud-security.html`)
The realistic transition from IT support / help desk into cloud security: what actually transfers, what you have to build from scratch, and the sequence that works. This page absorbed three earlier entry-path pages (`is-cloud-security-a-good-career.html`, `get-into-cloud-security-no-experience.html`, `help-desk-to-cloud-security.html`); the old URLs 301 in `.htaccess` and `retire_merged_career_pages.py` repointed every in-site link so there is no redirect hop.

### 🧪 Cloud Security Home Lab Walk-throughs (`homelab/`)
Deep, command-line-level lab walkthroughs that go further than the home-lab overview page: break-and-detect on AWS, a CloudTrail → SIEM detection pipeline, a Kubernetes security lab, and a LocalStack AWS lab. Registered like `portfolio/` in `sync_chrome.py`, the validators, and lychee; deliberately **not** in the site search index.

### 🎤 Interview Prep (`cloud-security-interview-questions.html`, `cloud-security-resume-guide.html`)
Two companion pages to the careers hub: interview questions with model answers (what a good answer sounds like, not just the question list), and a resume guide covering structure, phrasing, and what hiring managers actually scan for.

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

### 🔍 Focused Category Comparisons (`cspm-vs-cwpp.html`, `cnapp-vs-xdr.html`)
Two narrower head-to-heads for the questions the big comparison page gets asked repeatedly: posture vs. workload protection (CSPM vs CWPP), and where CNAPP ends and XDR/CDR begins.

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

### 🤖 Non-Human Identity (`non-human-identity.html`)
The identity class that now outnumbers humans by an order of magnitude: service accounts, workload identities, API keys, tokens, and increasingly AI agents. Discovery, ownership, lifecycle, rotation, and why the usual IAM playbook doesn't transfer cleanly.

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

### 🔌 MCP Security (`mcp-security.html`)
Securing the Model Context Protocol - the tool-calling layer AI assistants now use to reach real systems. Trust boundaries between model, client, and server; prompt-injection reaching a tool call; credential and scope handling; and what to check before you connect an MCP server to anything that matters.

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
A directory of **<!--count:vendors_floor-->300+<!--/count--> cloud-security vendors** across <!--count:vendor_categories-->32<!--/count--> categories - CNAPP, CSPM, KSPM, CIEM, SSPM, DSPM, SIEM, EDR/XDR, MDR, SOAR, ASPM, SAST/SCA, IaC scanning, secrets, PAM, IdP, WAF/DDoS, API security, CASB, SASE, ZTNA, DevSecOps, image hardening, supply chain, AI security, vuln mgmt, forensics, MSSPs, GRC platforms. Vendor-neutral one-liners, no rankings. Wiz affiliation disclosed.

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

### 🔐 How csoh.org Is Secured (`how-csoh-org-is-secured.html`)
The site's own security model as a worked example: the strict CSP and the rest of the security-header set, SRI on every shared asset, keyless OIDC deploys with no long-lived cloud credentials, the GitHub App / PAT split in CI, the URL-safety and broken-link gates, and the WAF and edge controls in front of all three origins. The fourth "Behind the Scenes" page - it is the security counterpart to the deploy, Actions, and Terraform explainers.

### 📚 Resources (`resources.html`)
Comprehensive catalog of **<!--count:resources_floor-->480+<!--/count--> cloud security resources** organized by 6 categories:

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

### 🎤 Speakers & Pitching a Talk (`speakers.html`, `present.html`)
`speakers.html` is the archive of guest speakers who have presented at a Friday session. `present.html` is the other side of it: what a CSOH talk looks like, what we're looking for, and how to pitch one (no vendor pitches).

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
- **<!--count:meetings-->107<!--/count--> meeting recaps** with per-topic summaries and speaker notes
- Searchable, filterable by tag (AWS, Azure, AI, supply chain, conferences, etc.)
- **Speaker filter** - auto-detects recurring community members across recaps and surfaces a one-click filter row (Shawn, Neil, Jay, Matt, etc.) with appearance counts
- Auto-ingested from Zoom AI Companion summaries or VTT transcripts via `tools/add_meeting.py`

### 🗣️ What Practitioners Think (`what-practitioners-think.html` + digests)
A hub for the session-digest series: what the room actually said about a topic across many Fridays, synthesized from the recaps rather than written top-down. Current digests cover [AI security](what-practitioners-think-about-ai-security.html), [security regulation](what-practitioners-think-about-security-regulation.html), [supply-chain security](what-practitioners-think-about-supply-chain-security.html), [vulnerability management](what-practitioners-think-about-vulnerability-management.html), and [what breaking into cloud security really takes](what-breaking-into-cloud-security-really-takes.html).

### 🚩 Cloud CTFs (`ctfs.html`)
Dedicated directory for hands-on cloud CTF challenges:
- **52+ challenges** across AWS, Azure, GCP, Kubernetes, and AI security
- Includes the full Wiz Cloud Security Championship calendar
- Submit a new CTF with `python3 tools/submit_ctf.py` - see [CONTRIBUTING_CTFS.md](CONTRIBUTING_CTFS.md)

### 📡 RSS Subscribe (`rss.html`)
Plain-English landing page for both feeds - `feed.xml` (cloud-security news, refreshed every 3 hours) and `recaps.xml` (one item per Friday-session recap). Explains what RSS is, recommends readers (Feedly, Inoreader, NetNewsWire, Thunderbird), and gives one-click subscribe instructions. See [RSS_FEED_README.md](RSS_FEED_README.md).

### 📖 Glossary (`glossary.html`)
A plain-English glossary of cloud-security acronyms and concepts:
- **310 terms** across 13 sections - cloud models, IAM, network, data, detection, the *PM family, supply-chain, ATT&CK, AI/LLM, DevOps, standards bodies
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
Plain-English privacy policy. Short version: no cookies, no marketing or cross-site trackers, only cookieless page-view analytics (GoatCounter), never sell or share data. The only personal data we hold is your mailing-list email. External links are scrubbed of tracking parameters before publication.

### 🔒 Security Policy (`security-policy.html`)
RFC 9116-compliant vulnerability disclosure policy. The machine-readable copy is served from both `/.well-known/security.txt` (the RFC canonical location) and `/security.txt`.

### 🔬 Threat Research (`threat-research.html`)
Curated directory of primary sources for cloud-focused threat intel - vendor research teams, annual threat reports, IOC feeds, attack frameworks, and government advisories. Companion to `breach-timeline.html`: kill chains cover specific historical incidents, threat-research is the living index of where defenders go for ongoing intel. See the full section below.

---

## 🔗 Breach Kill Chains (`breach-timeline.html`)

A community-maintained library of **step-by-step cloud breach reconstructions**, mapped to MITRE ATT&CK Cloud techniques and sourced from official post-mortems.

### Current incidents covered

| Incident | Year | Provider | Key Techniques |
|---|---|---|---|
| Mitnick / Novell | 1994 | On-Prem | War dialing, pretexting, voicemail trap, watched honeypot |
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
| Storm-2949 / Entra ID SSPR | 2026 | Azure / Entra ID | T1621, T1098.005, T1556.006, T1530 |
| Mini Shai-Hulud / TanStack npm | 2026 | npm / GitHub Actions | T1195.002, T1552.001, T1550.001, T1567.001 |
| Suspected AI-Assisted AWS Compromise | 2026 | AWS | T1078.004, T1580, T1619, T1648 |
| LiteLLM / PyPI (TeamPCP) | 2026 | PyPI / CI | T1195.001, T1552, T1546, T1613 |
| Vercel / Context.ai OAuth | 2026 | Google Workspace / SaaS | T1528, T1199, T1078, T1580 |
| Vimeo / Anodot (ShinyHunters) | 2026 | Snowflake / BigQuery | T1199, T1078.004, T1213, T1657 |
| Megalodon / GitHub Actions | 2026 | GitHub Actions | T1552.005, T1078, T1053, T1041 |

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
│
│  ── Entry points ──
├── index.html                  # Homepage with hero section & category overview
├── search.html                 # Site-wide MiniSearch full-text search
├── 403.html                    # Custom 403 (Forbidden) error page
├── 404.html                    # Custom 404 (Not Found) error page
│
│  ── Foundations ──
├── what-is-cloud-security.html # Pillar: vendor-neutral cloud-security overview (FAQ schema)
├── shared-responsibility-model.html # Provider vs. customer security split
├── cloud-security-best-practices.html # Practitioner's controls checklist
├── vendor-landscape.html       # <!--count:vendors_floor-->300+<!--/count--> cloud-security vendors across <!--count:vendor_categories-->32<!--/count--> categories
├── glossary.html               # 310 cloud security terms with live search & cross-links
├── faq.html                    # Frequently asked questions (FAQPage schema)
│
│  ── Tool-category comparisons ──
├── cspm-vs-cnapp.html          # CSPM vs CNAPP vs CWPP vs CIEM vs DSPM
├── cspm-vs-cwpp.html           # Posture vs workload protection, head to head
├── cnapp-vs-xdr.html           # CNAPP vs XDR (and CDR)
│
│  ── Platform topics ──
├── containers.html             # Container security: boundary, escapes, IMDS, supply chain
├── kubernetes.html             # Kubernetes & managed K8s (EKS / AKS / GKE) security
├── serverless.html             # Lambda / Functions security - event injection, IAM, denial of wallet
├── service-mesh-security.html  # Istio / Linkerd / Cilium / Consul, mTLS, SPIFFE/SPIRE
├── ci-cd.html                  # CI/CD pipelines for cloud, OIDC federation, deploy strategies
├── landing-zones.html          # Cloud foundations (AWS / Azure / GCP reference designs)
│
│  ── Security domains ──
├── iam.html                    # IAM & cloud identity, RBAC/ABAC, workload identity, priv-esc
├── non-human-identity.html     # Non-human identity (NHI): service accounts, keys, agents
├── zero-trust.html             # NIST SP 800-207, BeyondCorp, CISA Maturity Model, ZTNA
├── network-security.html       # VPC design, private endpoints, egress, WAF, DDoS, SASE/ZTNA
├── data-security.html          # Envelope encryption, BYOK/HSM, secrets management, rotation
├── vulnerability-management.html # CVSS/EPSS/KEV, reachability, SAST/SCA/DAST, SBOM/VEX, ASPM
├── api-security.html           # OWASP API Top 10, BOLA, JWT pitfalls, GraphQL/gRPC
├── saas-security.html          # SSPM, OAuth app risk, M365 / Workspace / Salesforce / GitHub
├── backup-dr.html              # 3-2-1-1-0, immutability per cloud, ransomware kill chain
├── threat-modeling.html        # STRIDE/PASTA/LINDDUN, attack trees, ATT&CK Cloud
│
│  ── Detection / response / offense ──
├── cloud-soc.html              # Cloud threat monitoring, SIEM, detection engineering, IR
├── detection-engineering.html  # Sigma, ATT&CK Cloud Matrix, detection-as-code, SIEM/lake/XDR
├── incident-response.html      # IR lifecycle, EC2/EKS/Lambda evidence, memory forensics
├── cloud-pentesting.html       # AWS/Azure/GCP attack paths, Pacu/ROADtools/BloodHound
├── threat-research.html        # Curated cloud threat research directory
├── ctfs.html                   # Dedicated cloud CTF directory (52+ challenges)
│
│  ── Breach kill chains ──
├── breach-timeline.html        # Index of breach kill chains (per-breach pages in breaches/)
├── breach-lessons.html         # Cross-incident synthesis: recurring root causes across the 20 chains
├── cloud-breach-year-in-review-2025.html  # The cloud/SaaS/supply-chain breaches that defined 2025
├── kevin-mitnick.html          # Special resource page
│
│  ── Governance + AI ──
├── grc.html                    # Governance, Risk, Compliance - frameworks, policy-as-code
├── compliance-frameworks.html  # SOC 2, ISO 27001, PCI DSS, HIPAA, FedRAMP, CMMC, NIST CSF, GDPR
├── ai-learning.html            # Using AI assistants to LEARN cloud security faster
├── ai-ml-security.html         # Securing AI workloads - OWASP LLM Top 10, agentic AI, ATLAS
├── mcp-security.html           # Securing the Model Context Protocol
│
│  ── Per-cloud hubs ──
├── aws-security.html           # AWS security hub
├── azure-security.html         # Azure security hub
├── gcp-security.html           # GCP security hub
├── cloud-security-comparison.html # AWS vs Azure vs GCP - 10 tables + a 20-row scorecard
│
│  ── Careers ──
├── cloud-security-careers.html # Roles, salaries, interviews, portfolio (FAQ schema)
├── learning-path.html          # Beginner→advanced roadmap (HowTo schema)
├── breaking-into-cloud-security.html # The realistic transition from IT support
├── what-breaking-into-cloud-security-really-takes.html # Session digest: the unvarnished version
├── cloud-security-degree-programs.html # Academic paths and university programs (FAQ schema)
├── cloud-security-certifications.html # CCSK / CCSP / AWS / Azure / GCP / CKS comparison
├── cloud-security-home-lab.html # Free-tier setups, budget guardrails, kill-switches
├── cloud-security-interview-questions.html # Interview questions with model answers
├── cloud-security-resume-guide.html # Resume structure, phrasing, and what hiring managers scan for
├── cloud-security-reading-list.html # Curated reading list (staleness-checked monthly)
├── cloud-security-portfolio-projects.html # Portfolio projects hub (walkthroughs in portfolio/)
├── cloud-security-<role>.html  # Career role-in-depth series: engineer, architect,
│                               #   iam-architect, appsec-engineer, cnapp-analyst,
│                               #   detection-engineer, incident-responder, penetration-tester,
│                               #   platform-engineer, grc-engineer, sales-engineer,
│                               #   customer-success-engineer (FAQ schema)
│
│  ── Community ──
├── sessions.html               # Weekly Zoom session information
├── speakers.html               # Guest speaker archive
├── present.html                # How to pitch a talk for a Friday session
├── community.html              # Community & Signal chat
├── mentorship.html             # Community mentorship program
├── conferences.html            # Security & hacker conferences directory with pros/cons
├── presentations.html          # Archive of recorded presentations
├── meetings.html               # Weekly meeting recaps (<!--count:meetings-->107<!--/count--> entries, topic-by-topic)
├── chat-resources.html         # Community-shared URLs from Zoom sessions (580+ URLs)
├── what-practitioners-think.html # Hub for the session-digest series below
├── what-practitioners-think-about-ai-security.html
├── what-practitioners-think-about-security-regulation.html
├── what-practitioners-think-about-supply-chain-security.html
├── what-practitioners-think-about-vulnerability-management.html
│
│  ── Catalogs & feeds ──
├── resources.html              # Main resource directory (410+ resources in 6 categories)
├── news.html                   # Cloud security news (120+ articles)
├── rss.html                    # Landing page explaining the RSS feeds to subscribers
│
│  ── Behind the scenes (the dogfooded stack) ──
├── cloud-deployment.html       # Multi-cloud deploy architecture
├── github-actions.html         # Learn GitHub Actions via our heavily-commented workflows
├── terraform.html              # Learn Terraform via our own multi-cloud IaC
├── version-control.html        # Git & version-control fundamentals via this repo
├── how-csoh-org-is-secured.html # The site's own security model, end to end
├── contribute.html             # General contributions guide
├── contribute-resources.html   # Resource submission web form / guide
│
│  ── About & policy ──
├── about.html                  # About CSOH: mission and ethos
├── about-shawn-nunley.html     # Founder bio (Person / ProfilePage schema, E-E-A-T)
├── code-of-conduct.html        # Community Code of Conduct
├── privacy.html                # Privacy Policy (no cookies, no cross-site trackers, no on-site ads)
├── security-policy.html        # Security disclosure policy page
├── google66d489593949bd4c.html # Google Search Console verification token
│
│  ── Subdirectory page sets ──
├── breaches/                   # <!--count:breaches-->45<!--/count--> per-breach kill chain pages (Capital One, SolarWinds, etc.)
├── meetings/                   # <!--count:meetings-->107<!--/count--> per-meeting recap pages (split from meetings.html)
├── portfolio/                  # 7 hands-on portfolio-project walkthroughs (see hub page above)
├── homelab/                    # 4 deep command-line home-lab walkthroughs
│
│  ── Shared assets ──
├── style.css                   # Main stylesheet (responsive design + dark mode)
├── main.js                     # Shared interactive features (search, filter, sort, dark mode)
├── chat-resources.js           # chat-resources.html-specific filtering/search
├── meetings.js                 # meetings.html-specific index + filters + speaker filter
├── glossary.js                 # glossary.html-specific search/filter
├── breach-timeline.css         # breach-timeline.html-specific styles
├── breach-timeline.js          # breach-timeline.html-specific tab/panel logic
├── 404.js                      # 404-page "did you mean" suggestions
├── search.css                  # search.html styles (external, for the strict CSP)
├── search-init.js              # search.html: index load, MiniSearch wiring, result render
├── search-index.json           # Site-wide search index (auto-generated at deploy time)
├── search-synonyms.json        # Acronym ↔ expansion map fed into the search index
├── meetings-search-index.json  # Search index for meeting recaps (auto-generated)
├── vendor/                     # Self-hosted third-party JS (SRI-pinned, first-party origin)
│   ├── README.md               # What each file is, and the local patches applied to it
│   ├── minisearch-7.1.2.min.js # Search library used by search-init.js
│   └── goatcounter-count.js    # Cookieless page-view counter loader
│
│  ── Feeds & machine-readable files ──
├── feed.xml                    # News RSS feed (auto-generated by update_news.py)
├── recaps.xml                  # Meeting-recap RSS feed (tools/generate_recaps_rss.py)
├── sitemap.xml                 # XML sitemap for search engines
├── robots.txt                  # Crawling rules (all major crawlers + 21 AI/LLM bots)
├── llms.txt                    # Site summary for LLM crawlers
├── humans.txt                  # Human-readable credits, linked via <link rel="author">
├── manifest.json               # PWA manifest (Add to Home Screen)
├── csoh.ics                    # Calendar file for the recurring Friday session
├── security.txt                # Security contact (root mirror)
├── .well-known/                # Well-known endpoints (carved out of the dotfile deny)
│   ├── security.txt            # Security.txt at the RFC 9116 canonical location
│   └── mta-sts.txt             # MTA-STS policy (served via mta-sts.csoh.org)
│
│  ── Images ──
├── img/                        # Images and preview thumbnails
│   ├── og/                     # 1200×630 social cards (+ breaches/, portfolio/, meetings/)
│   ├── previews/               # Resource preview screenshots
│   ├── news-banners/           # Per-source banner images for news.html
│   ├── authors/                # Author / speaker photos
│   ├── icons/                  # Favicons and PWA icons
│   └── photos/                 # Miscellaneous site photography
├── chat-screenshots/           # Per-URL screenshots shown in chat-resources.html
├── email-screenshots/          # Newsletter screenshots referenced from community pages
│
├── tools/                      # Automation and maintenance scripts (see table below)
│
├── update_news.py              # News aggregation script (62 RSS feeds, runs every 3 hours)
├── update_sri.py               # Updates SRI hashes & cache-bust params across HTML files
├── retire_merged_career_pages.py # One-off: repoint links to the merged "breaking in" page
│
├── .github/workflows/          # 15 CI/CD workflows (see "How Automation Works" below)
│
├── seo-audits/                 # SEO audit reports + SCORECARD.md (excluded from deploy filters)
├── preview-mapping.json        # Metadata for resource previews
├── dist/                       # Build output from tools/stage_site.sh (gitignored)
│
│  ── Server & container config ──
├── .htaccess                   # Apache server config (security headers, caching, compression)
├── nginx.conf                  # Nginx server config (Docker / Cloud Run deployments)
├── nginx-security-headers.conf # Security-header snippet included by nginx.conf
├── Dockerfile                  # Container build for the GCP Cloud Run origin
├── docker-compose.yml          # Compose config for running the site locally in Docker
├── .dockerignore               # Files excluded from the Docker build context
│
│  ── Tooling config ──
├── .lychee.toml                # Config for the broken-link-checker workflow
├── .yamllint.yml               # Config for the yamllint job in lint.yml
├── pyproject.toml              # Config for the ruff job in lint.yml (Python lint)
├── .trivyignore.yaml           # Time-boxed Trivy CVE suppressions for the Cloud Run image
├── .editorconfig               # Editor consistency rules
│
├── infra/                      # Infrastructure-as-code for the multi-cloud deploy
│   ├── README.md               # Architecture, cost, and cutover runbook
│   ├── MANUAL_SECURITY_STEPS.md   # Steps needing a dashboard/registrar login
│   ├── AWS_IDENTITY_MIGRATION.md  # Root-account → Identity Center runbook
│   └── terraform/              # Terraform for AWS, GCP, Azure & Cloudflare - every .tf file
│       │                       #   commented line by line so a newcomer can read it
│       ├── aws/                # S3 + CloudFront origin, OIDC deploy role
│       ├── gcp/                # Cloud Run origin, Workload Identity Federation, Artifact Registry
│       ├── azure/              # Blob static-website origin, federated identity
│       └── cloudflare/         # Edge: zone, rules, active/active load balancer + health checks
│
├── CLAUDE.md                   # Repo gotchas for humans and agents working here
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

### The `tools/` directory

Every script is stdlib-first, idempotent, and only writes when content actually changes (see [DEVELOPMENT.md → Scripts must only write when content actually changes](DEVELOPMENT.md#scripts-must-only-write-when-content-actually-changes)). Scripts with a `_README.md` beside them have long-form docs; the rest are documented by their module docstring.

**Content ingest (interactive or credentialed)**

| Script | What it does | Docs |
|---|---|---|
| `submit_resource.py` | Interactive resource submission with URL validation + PR creation | [README](tools/SUBMIT_RESOURCE_README.md) · [example](tools/SUBMIT_RESOURCE_EXAMPLE.md) |
| `submit_news_source.py` | Interactive news-source (RSS/Atom feed) submission | [README](tools/SUBMIT_NEWS_SOURCE_README.md) |
| `submit_ctf.py` | Interactive cloud-CTF submission for `ctfs.html` | [README](tools/SUBMIT_CTF_README.md) |
| `add_meeting.py` | Publish a new meeting recap (page + `meetings.html` entry + feeds) | [README](tools/ADD_MEETING_README.md) |
| `fetch_zoom_transcript.py` | Pull a VTT transcript from a Zoom cloud recording (Server-to-Server OAuth) | [README](tools/FETCH_ZOOM_TRANSCRIPT_README.md) |
| `backfill_zoom_summaries.py` | Bulk-import every Zoom AI Companion summary on the account | [README](tools/BACKFILL_ZOOM_SUMMARIES_README.md) |

**Site-wide stamping (run after content changes)**

| Script | What it does | Docs |
|---|---|---|
| `sync_chrome.py` | Stamps ONE canonical nav, header buttons, and footer onto every page | [README](tools/SYNC_CHROME_README.md) |
| `sync_counts.py` | Recomputes every count on the site (JSON-LD `numberOfItems`, `<!--count:-->` markers, OG subtitles) from the real cards | [README](tools/SYNC_COUNTS_README.md) |
| `crosslink_glossary.py` | Adds `id="term-…"` to glossary `<dt>`s and links every term mention inside `<dd>`s | [README](tools/CROSSLINK_GLOSSARY_README.md) |
| `crosslink_pages.py` | Links the first occurrence of each glossary term across the rest of the site | [README](tools/CROSSLINK_PAGES_README.md) |
| `inject_meeting_topic_links.py` | Injects contextual topic-page links into recap bodies | [README](tools/INJECT_MEETING_TOPIC_LINKS_README.md) |
| `inject_session_blocks.py` | Stamps a "From the Friday sessions" block onto topic pages | [README](tools/INJECT_SESSION_BLOCKS_README.md) |
| `inject_goatcounter.py` | Stamps the GoatCounter analytics tag onto every page | docstring |
| `update_presentations_schema.py` | Regenerates the `VideoObject` JSON-LD on `presentations.html` | [README](tools/UPDATE_PRESENTATIONS_SCHEMA_README.md) |
| `update_sitemap.py` | Refreshes `<lastmod>` in `sitemap.xml` (does **not** discover new pages) | [README](tools/UPDATE_SITEMAP_README.md) |
| `normalize_urls.py` | Strips tracking params, upgrades http→https, resolves redirects | docstring |
| `../update_sri.py` | Recomputes SRI hashes + `?v=` cache-bust keys for every shared asset | [README](tools/UPDATE_SRI_README.md) |
| `../update_news.py` | Pulls 62 RSS feeds → `news.html`, `feed.xml`, sitemap lastmod | [README](tools/UPDATE_NEWS_README.md) |

**Generated artifacts (indexes, feeds, images)**

| Script | What it does | Docs |
|---|---|---|
| `build_search_index.py` | Builds `search-index.json` (one entry per `<section id>` + glossary term) | docstring |
| `build_meetings_search_index.py` | Builds `meetings-search-index.json` over full recap text | docstring |
| `generate_rss.py` | Rebuilds `feed.xml` from `news.html` | docstring |
| `generate_recaps_rss.py` | Builds `recaps.xml`, the meeting-recap RSS feed | docstring |
| `generate_og_images.py` | 1200×630 social cards for top-level pages | docstring |
| `generate_meeting_og_images.py` | 1200×630 social cards for meeting recaps | [README](tools/GENERATE_MEETING_OG_IMAGES_README.md) |
| `generate_thumbnails.py` | 3:2 glyph tiles for the compact card grids (`img/thumbs/`) | docstring |
| `generate_news_banners.py` | Banner images for news sources | docstring |
| `generate_preview.py` | Screenshot previews for resource cards | [README](tools/GENERATE_PREVIEW_README.md) |
| `generate_webp.py` | `.webp` siblings for every raster image | docstring |
| `wrap_img_webp.py` | Wraps `<img>` in `<picture>` with a WebP `<source>` | docstring |

**CI gates and audits (report or fail, never edit content)**

| Script | What it does | Docs |
|---|---|---|
| `check_all_site_urls.py` | Site-wide URL safety scan (phishing patterns, suspicious TLDs, shorteners) | [README](tools/CHECK_URL_SAFETY_README.md) |
| `check_url_safety.py` | The single-URL validator `check_all_site_urls.py` is built on | [README](tools/CHECK_URL_SAFETY_README.md) |
| `check_jsonld.py` | Every JSON-LD block on the site must be valid JSON | docstring |
| `check_no_inline_scripts.py` | No inline `<script>` blocks (the CSP forbids them) | docstring |
| `check_svg_dimensions.py` | `width`/`height` on every `<svg>` that has a `viewBox` | docstring |
| `check_crosslink_coverage.py` | Every root page is either cross-linked or explicitly opted out - `crosslink_pages.py` skips unlisted pages silently, so omissions never surfaced | docstring |
| `check_glossary_coverage.py` | Glossary invariants: unique `<dt>` ids, no alias claimed by two entries, anchors resolve, no unreachable entry added by accident | docstring |
| `check_docs_consistency.py` | The mechanical half of the weekly documentation review: visible dates vs JSON-LD, social-card assets, false count claims, glossary orphans. Fixes what is derivable, reports the rest, deletes nothing | [README](tools/DOCS_CONSISTENCY_README.md) |
| `check_news_banners.py` | Every news source has an on-disk banner image | docstring |
| `check_mobile_layout.py` | Mobile layout regression check | docstring |
| `run_seo_audit.py` | Deterministic structural SEO audit → `seo-audits/` + SCORECARD | [README](tools/RUN_SEO_AUDIT_README.md) |
| `check_pagespeed.py` | Google PageSpeed Insights (mobile + desktop) → SCORECARD | [README](tools/CHECK_PAGESPEED_README.md) |
| `check_lighthouse.py` | Lighthouse SEO / a11y / perf threshold check | [README](tools/CHECK_LIGHTHOUSE_README.md) |
| `check_edge_headers.py` | Asserts the live security headers match `rules.tf` - the Cloudflare ruleset is inert after creation, so Terraform cannot catch drift | [README](tools/CHECK_EDGE_HEADERS_README.md) |
| `check_robots_parity.py` | Asserts the live `robots.txt` matches the repo, catching an edge-injected managed `robots.txt` | [README](tools/CHECK_ROBOTS_PARITY_README.md) |
| `check_reading_list_staleness.py` | Flags reading-list sources that stopped publishing | [README](tools/CHECK_READING_LIST_STALENESS_README.md) |
| `check_meeting_staleness.py` | Flags a stalled meeting-recap cadence | docstring |
| `check_conference_staleness.py` | Flags conference "Next:" dates that have gone stale | docstring |

**Build / packaging**

| File | What it does |
|---|---|
| `stage_site.sh` | Produces `dist/` - the exact public file set every origin serves |
| `site-publish.filter` | rsync filter listing what `stage_site.sh` includes and excludes |
| `url_resolution_cache.json` | CI-seeded redirect cache for `normalize_urls.py` (never commit a local copy) |
| `awesome-list-submissions.md` | Tracking notes for awesome-list outreach |

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

News articles are **updated automatically** - you don't need to add them by hand. A GitHub Actions workflow runs every 3 hours, pulls articles from 62 cloud security RSS feeds, and creates a pull request with the new content. See the [How Automation Works](#-how-automation-works) section below for details, or read the full docs in [tools/UPDATE_NEWS_README.md](tools/UPDATE_NEWS_README.md).

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

This site uses **GitHub Actions workflows** to automate all major site updates. Every workflow file is commented line by line - they double as the teaching material behind [github-actions.html](https://csoh.org/github-actions.html), so read them if you want the full story.

All 15 workflows, grouped by what they do. Times are UTC.

**Content automation (writes to the site)**

| Workflow | When | What it does |
|---|---|---|
| [`update-news.yml`](.github/workflows/update-news.yml) | every 3h | Pulls 62 RSS/Atom feeds, rewrites `news.html`, `feed.xml`, sitemap lastmod; opens a PR that auto-merges if the diff is news files only |
| [`update-resources.yml`](.github/workflows/update-resources.yml) | Mon 14:00 | `claude-code-action` adds 2-3 fresh entries per `resources.html` section; auto-merges only if the diff is `resources.html` alone |
| [`update-counts.yml`](.github/workflows/update-counts.yml) | Mon 07:30 | Recomputes every count on the site from the real cards and refreshes the count share-cards |
| [`normalize-urls.yml`](.github/workflows/normalize-urls.yml) | 1st of month, 08:00 | Deep URL-normalization pass; opens an auto-approved PR for a human to merge |
| [`site-update-deploy.yml`](.github/workflows/site-update-deploy.yml) | push to `main` on site files | Chained housekeeping commits: SRI, URL safety, normalization, schema, sitemap, previews |

**Deploy**

| Workflow | When | What it does |
|---|---|---|
| [`deploy.yml`](.github/workflows/deploy.yml) | push to `main` on site files | Builds once, publishes active/active to AWS + GCP + Azure behind Cloudflare, keyless OIDC per cloud |

**PR quality gates**

| Workflow | When | Blocks the PR? |
|---|---|---|
| [`lint.yml`](.github/workflows/lint.yml) | every push + PR | Yes - `actionlint` + `ruff` + `yamllint` |
| [`validate-html.yml`](.github/workflows/validate-html.yml) | push/PR on `*.html` + Mon 07:00 | Yes, with a PR comment - W3C HTML5 validator |
| [`check-url-safety.yml`](.github/workflows/check-url-safety.yml) | PRs on `*.html` + Mon 06:30 | Yes - phishing patterns, suspicious TLDs, shortener domains |
| [`check-broken-links.yml`](.github/workflows/check-broken-links.yml) | PRs on `*.html` + Mon 06:00 | No - lychee crawl, PR comment only (link rot is everywhere) |

**Periodic audits (report-only, never edit the site)**

| Workflow | When | Where the report lands |
|---|---|---|
| [`check-pagespeed.yml`](.github/workflows/check-pagespeed.yml) | Mon 14:00 | Row in `seo-audits/SCORECARD.md`; issue on regression |
| [`run-seo-audit.yml`](.github/workflows/run-seo-audit.yml) | Mon 14:15 | Row in `seo-audits/SCORECARD.md` + `seo-audits/YYYY-MM-DD.md`; issue on regression |
| [`check-meeting-staleness.yml`](.github/workflows/check-meeting-staleness.yml) | Mon 15:00 | Sticky issue labeled `meeting-staleness` |
| [`check-reading-list-staleness.yml`](.github/workflows/check-reading-list-staleness.yml) | 1st of month, 07:00 | Sticky issue labeled `reading-list-staleness` |
| [`check-conference-staleness.yml`](.github/workflows/check-conference-staleness.yml) | 1st of month, 14:00 | Sticky issue labeled `conference-staleness` for stale "Next:" dates on `conferences.html` |

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

### The other two staleness checks

Same shape, different content, and neither one edits the site either - each opens or refreshes exactly one sticky issue:

- **`check-meeting-staleness.yml`** (Mondays 15:00 UTC) runs `tools/check_meeting_staleness.py` and files an issue labeled `meeting-staleness` when the newest recap on `meetings.html` is older than the expected weekly cadence. It catches an ingest that quietly stopped working, which no other check would notice.
- **`check-conference-staleness.yml`** (1st of the month, 14:00 UTC) runs `tools/check_conference_staleness.py` over the "Next:" dates on `conferences.html` and files an issue labeled `conference-staleness` for any that have passed. Conference dates rot in place: the link still resolves, so lychee stays quiet, but the page is advertising an event that already happened. It also scans the *visible text* of cards marked `ongoing` or `TBA`, whose `data-next-date` is deliberately never compared against today - the BSides card advertised a date four days past while the check reported OK, because only the attribute was ever examined.

Both are deliberately `paths:`-filtered so that editing the content they watch does *not* re-trigger them - only the script and the workflow file do.

---

## 🔍 SEO & Search Optimization

CSOH is engineered for organic discovery across traditional search (Google, Bing), AI search/answer engines (ChatGPT, Perplexity, Claude, Gemini), and social previews (LinkedIn, Twitter/X, Slack). The site uses no third-party scripts and no cross-site tracking - just clean semantic HTML, structured data, disciplined metadata, and a self-hosted cookieless page-view counter (GoatCounter).

### Schema.org structured data (25+ types)

**Page-level schema** - each page declares what kind of thing it is:
- ✅ **Article** / **NewsArticle** - pillar pages and the news index, with `datePublished`, `dateModified`, `author`, `publisher`
- ✅ **HowTo** + **HowToStep** - step-by-step content (e.g. learning path, GitHub Actions guide)
- ✅ **Course** + **CourseInstance** - learning-path roadmap and certifications comparison (Google Course rich result eligible)
- ✅ **FAQPage** + **Question** / **Answer** - 63 pages with structured Q&A for featured snippets
- ✅ **CollectionPage** - resource hub pages eligible for sitelinks rich results
- ✅ **Event** + **VirtualLocation** + **Schedule** - weekly Friday Zoom session
- ✅ **VideoObject** - each YouTube talk on `presentations.html` and meeting recaps
- ✅ **DefinedTermSet** - the glossary, with 310 individual terms

**Entity schema** - who/what is responsible for the content:
- ✅ **Organization** - CSOH itself, with founding date, contact point, sameAs links, search action
- ✅ **Person** + **ProfilePage** - founder bio with `jobTitle`, `worksFor`, `founder`, `knowsAbout`, `sameAs`
- ✅ **Author attribution** - pillar articles credit the Person via `@id` reference (E-E-A-T signal)
- ✅ **ItemList** - certifications comparison, news listings, and resource directories
- ✅ **BreadcrumbList** - full navigation hierarchy on every content page

### Author authority (E-E-A-T)

- ✅ Dedicated bio page at `/about-shawn-nunley.html` with full Person schema
- ✅ Visible "About the author" card at the bottom of all pillar articles (85 pages and counting)
- ✅ Visible byline + footer "Founded by" link site-wide
- ✅ `rel="author"` on every author link
- ✅ `sameAs` external profile links (LinkedIn, GitHub, csoh.org)

### Discoverability

- ✅ **`sitemap.xml`** - 228 URLs, `<lastmod>` refreshed from git commit dates on every deploy ([tools/update_sitemap.py](tools/update_sitemap.py))
- ✅ **`robots.txt`** - Allow: / for all major crawlers, plus explicit allow-rules for 21 AI/LLM bots (GPTBot, ClaudeBot, PerplexityBot, Google-Extended, Applebot-Extended, CCBot, MistralAI-User, Cohere, etc.)
- ✅ **RSS feed** (`feed.xml`) for the news aggregator
- ✅ **`humans.txt`** for human-readable credits, linked via `<link rel="author">`
- ✅ **`security.txt`** (RFC 9116) for vulnerability disclosure, at both `/.well-known/security.txt` and `/security.txt`
- ✅ Site-wide **canonical URLs** to consolidate ranking signals
- ✅ **Glossary cross-linking** - first occurrence of each of 310 terms auto-linked to the glossary on every content page ([tools/crosslink_pages.py](tools/crosslink_pages.py))

### Social previews

- ✅ **Open Graph** + **Twitter Card** meta on every indexable page (title, description, type, url, image)
- ✅ **Per-article social images** - <!--count:og_images-->249<!--/count--> unique 1200×630 JPG previews under `img/og/` (top-level pages via [tools/generate_og_images.py](tools/generate_og_images.py), plus `img/og/breaches/`, `img/og/portfolio/`, and <!--count:meetings-->107<!--/count--> meeting recaps in `img/og/meetings/` via [tools/generate_meeting_og_images.py](tools/generate_meeting_og_images.py)) so each page has its own LinkedIn/Slack/Twitter preview, not a generic site banner
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

- ✅ Zero cookies, zero cross-site trackers, zero third-party scripts (analytics is cookieless, self-hosted GoatCounter)
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
- ☕ **Donate** via [Buy Me a Coffee](https://buymeacoffee.com/csoh) (optional, fully community-run)

### Policies
- 🤝 **[Code of Conduct](code-of-conduct.html)** - community standards across Friday Zoom, mailing list, and GitHub
- 🔐 **[Privacy Policy](privacy.html)** - no cookies, no cross-site trackers, no on-site ads
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
