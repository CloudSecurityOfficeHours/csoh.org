# Cloud Security Office Hours (CSOH)

A modern, community-driven cloud security resource hub built as a fast, responsive static community-driven website. Home to **2000+ security professionals**, **260+ curated resources**, **120+ news articles**, **554+ community-shared URLs**, and weekly expert-led Zoom sessions.

[![GitHub](https://img.shields.io/badge/GitHub-CloudSecurityOfficeHours/csoh.org-blue)](https://github.com/CloudSecurityOfficeHours/csoh.org)
[![Discord](https://img.shields.io/badge/Discord-2000%2B%20Members-5865F2)](https://discord.gg/AVzAY97D8E)
[![License](https://img.shields.io/badge/License-Open%20Content-green)](LICENSE)

---

## 🎯 About CSOH

Cloud Security Office Hours is a **vendor-neutral, free community** dedicated to advancing cloud security education and collaboration. Founded in February 2023, CSOH has grown to 2000+ members worldwide, providing:

- **Weekly Expert Zoom Sessions** - Every Friday at 7:00 AM PT with industry experts
- **260+ Curated Resources** - CTF challenges, hands-on labs, security tools, certifications
- **120+ News Articles** - Daily cloud security news from reputable sources
- **RSS Feed** - Subscribe at [csoh.org/feed.xml](https://csoh.org/feed.xml) for automatic news updates
- **554+ Community-Shared URLs** - Secure, validated links from Zoom chat sessions
- **Active Discord Community** - Real-time discussions, peer learning, mentorship
- **Dark Mode** - Toggle between light and dark themes, with automatic OS preference detection
- **Automated Security Validation** - All URLs checked for malicious patterns before publication
- **Vendor Neutral** - Completely free, open, community-run initiative

---

## 📄 Website Pages

### 🏠 Homepage (`index.html`)
Central hub featuring:
- Community overview and value proposition
- Featured resource categories with quick navigation
- Call-to-action buttons for Zoom registration and Discord
- Enhanced schema markup for improved SERP visibility
- Testimonials and member count (2000+)

### 📚 Resources (`resources.html`)
Comprehensive catalog of **260+ cloud security resources** organized by 6 categories:

#### 🎯 CTF Challenges & Vulnerable Environments
- **CloudGoat** - Open-source, AWS vulnerable environments by Ermetic
- **AWSGoat** - Vulnerable AWS stack from Appthreat
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

#### 🛡️ Security Tools & Platforms (60+ Tools)
- **CNAPP (Cloud Native Application Protection)** - Runtime protection tools
- **CSPM (Cloud Security Posture Management)** - Configuration & compliance scanning
- **KSPM (Kubernetes Security Posture Management)** - K8s-specific security
- **SIEM & Threat Detection** - Splunk, ELK Stack, AWS Security Hub, etc.
- **Compliance & Config Management** - Terraform, Ansible, CloudFormation
- **Vulnerability Management** - Snyk, Qualys, Tenable, etc.

#### 🎓 Certifications & Professional Development (40+ Certs)
- **AWS** - Security Specialty, Solutions Architect, Database Specialty
- **Azure** - Security Engineer Associate, Administrator Associate
- **Google Cloud** - Professional Cloud Security Engineer
- **Cloud Security Alliance** - CCSK Certification
- **Kubernetes** - CKA, CKAD, CKS
- **General Security** - CISSP, CEH, SC-300, AZ-305
- **Bootcamps & Prep Courses** - Pwned Labs, AWSome Day, etc.

#### 🤖 AI Security (15+ Resources)
- **AI Security Tools** - Trend Micro Workload Security, etc.
- **AI Vulnerable Environments** - AIGoat, AI Security CTFs
- **AI Security Research** - Papers, whitepapers, research resources

#### 💼 Job Search Resources (20+ Listings)
- **Job Boards** - LinkedIn, Dice, CyberSecJobs, CloudSecurityJobs
- **Resume Services** - Resume optimization platforms
- **Interview Prep** - Technical interview guides
- **Career Development** - Mentorship, networking resources

#### 📰 Cloud Security News (120+ Articles)
- **Latest articles** sorted by publication date (newest first)
- **Multi-source aggregation** - Ars Technica, TechCrunch, SecurityWeek, KrebsOnSecurity, Mandiant, CrowdStrike, AWS Security Blog, Microsoft MSRC, SANS ISC, The Register, BleepingComputer, Dark Reading, and more
- **Searchable & filterable** by source, topic, date
- **Auto-updated daily** via Python news aggregation script
- **Rich snippet optimization** for featured search results

### 💬 Chat Resources (`chat-resources.html`)
Community-shared resources from weekly Zoom sessions:
- **554+ URLs** shared by community members during live sessions
- **Security validated** - All URLs automatically checked for malicious patterns
- **Filterable by date, person, category** - Find resources from specific sessions
- **Descriptive titles** - Auto-generated from page content
- **Continuous protection** - GitHub Actions workflow validates new URLs before merge

### 📅 Zoom Sessions (`sessions.html`)
Information about weekly community gatherings:
- **When:** Every Friday at 7:00 AM Pacific Time
- **Format:** Expert presentations + open discussion + Q&A
- **Cost:** Completely free
- **Registration Link:** https://sendfox.com/CSOH
- Format details and speaker information

### 🎬 Presentations (`presentations.html`)
Archive of past Zoom session presentations:
- Recorded sessions from industry experts
- Topic tags (AWS, Azure, GCP, Kubernetes, CSPM, CNAPP, etc.)
- Dates and presentation descriptions
- Direct video links

---

## 🔗 Breach Kill Chains (`breach-timeline.html`)

A community-maintained library of **step-by-step cloud breach reconstructions**, mapped to MITRE ATT&CK Cloud techniques and sourced from official post-mortems.

### Current incidents covered

| Incident | Year | Provider | Key Techniques |
|---|---|---|---|
| Capital One | 2019 | AWS | T1190, T1552.005, T1619, T1530 |
| Uber | 2022 | AWS / GCP | T1078, T1621, T1552.001, T1078.004 |
| Storm-0558 | 2023 | Azure | T1078, T1552, T1606.001, T1114.002 |
| SolarWinds | 2020 | Azure AD / AWS | T1195.002, T1071.004, T1606.002, T1114.002 |
| Microsoft SAS Leak | 2023 | Azure | T1552.004, T1530 |

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
- Step-by-step technical detail — not just a summary
- Every step mapped to a MITRE ATT&CK Cloud technique
- Actionable defender recommendations tied to specific controls

This is intentionally high-bar. A small number of deeply researched entries is more valuable than many shallow ones.

---


## 🚀 Features

### ⚡ Performance & Security
- **Pure Static HTML** - No database, server-side code, or backend dependencies
- **Instant Load Times** - Optimized CSS/JS, no external frameworks
- **Zero Vulnerabilities** - No SQL injection, XSS, or code execution risks
- **Automated URL Safety Checks** - All URLs validated for phishing, malware, and suspicious patterns
- **CI/CD Security Validation** - GitHub Actions workflow blocks unsafe URLs before merge
- **1,000+ URLs Validated** - Comprehensive site-wide security scanning
- **Automated Preview Images** - Screenshots generated when new resources are added
- **CDN Ready** - Deploy anywhere (GitHub Pages, Vercel, AWS S3, etc.)
- **100% Uptime** - Simple file hosting = maximum reliability

### 🌙 Dark Mode
- **One-Click Toggle** - 🌙/☀️ button in the header on every page
- **OS Auto-Detection** - Respects `prefers-color-scheme` system setting
- **Persistent Preference** - Choice saved in `localStorage` across sessions
- **Full Coverage** - All pages, cards, tags, forms, and navigation styled for dark mode

### 📡 RSS Feed
- **Auto-Generated Feed** - `feed.xml` updated automatically alongside news articles
- **Standards Compliant** - Valid RSS 2.0 feed for any reader app
- **Reader Guide** - See [RSS_FEED_README.md](RSS_FEED_README.md) for setup instructions

### 🔍 SEO & Discoverability
- **Rich Schema Markup** - NewsArticle, FAQPage, Organization, Event, CollectionPage
- **Featured Snippet Optimization** - FAQ schema for voice search
- **Google News Carousel** - Article collection markup
- **Mobile Responsive** - Perfect Google Lighthouse scores
- **Sitemap.xml & robots.txt** - Full crawlability configuration
- **Open Graph & Twitter Cards** - Social media optimization

### ♿ Accessibility
- **Semantic HTML5** - Proper heading hierarchy (H1→H2→H3)
- **ARIA Labels** - Screen reader support (including dark mode toggle)
- **Keyboard Navigation** - Full keyboard access
- **Color Contrast** - WCAG AA compliant in both light and dark modes
- **Alt Text** - Descriptive image labels

### 🔎 Search & Filter
- **Full-text Search** - Find resources by keyword
- **Category Filtering** - Filter by resource type
- **Tag-based Navigation** - AWS, Azure, GCP, Kubernetes, Certifications, Labs, CTF, Tools, etc.
- **Date Sorting** - News articles sorted newest first

---

## 📁 Project Structure

```
csoh.org/
├── index.html                  # Homepage with hero section & category overview
├── resources.html              # Main resource directory (260+ resources in 6 categories)
├── news.html                   # Cloud security news (120+ articles)
├── chat-resources.html         # Community-shared URLs from Zoom sessions (554+ URLs)
├── sessions.html               # Weekly Zoom session information
├── presentations.html          # Archive of recorded presentations
├── kevin-mitnick.html          # Special resource page
│
├── style.css                   # Main stylesheet (responsive design + dark mode)
├── main.js                     # Interactive features (search, filter, sorting, dark mode toggle)
├── feed.xml                    # RSS feed (auto-generated by update_news.py)
│
├── sitemap.xml                 # XML sitemap for search engines
├── robots.txt                  # Search engine crawling rules
├── security-policy.html        # Security disclosure policy
├── security.txt                # Security.txt (root copy)
├── .well-known/                # Well-known endpoints
│   └── security.txt            # Security.txt (RFC 9116 location)
│
├── img/                        # Images and preview thumbnails
│   └── previews/               # Resource preview images
│
├── tools/                      # Automation and maintenance scripts
│   ├── submit_resource.py            # Interactive tool for submitting new resources
│   ├── submit_news_source.py         # Interactive tool for submitting news sources
│   ├── generate_preview.py           # Generate preview screenshots for resources
│   ├── check_url_safety.py           # Core URL safety validator with pattern matching
│   ├── check_existing_urls.py        # Batch scanner for chat-resources.html URLs
│   ├── check_all_site_urls.py        # Comprehensive site-wide URL scanner
│   ├── update_chat_titles.py         # Generate descriptive titles for chat URLs
│   ├── SUBMIT_RESOURCE_README.md     # Interactive submission tool documentation
│   ├── SUBMIT_NEWS_SOURCE_README.md  # News source submission tool documentation
│   ├── GENERATE_PREVIEW_README.md    # Preview image generation documentation
│   ├── CHECK_URL_SAFETY_README.md    # URL safety checker documentation
│   └── CHECK_URL_SAFETY_WORKFLOW.md  # GitHub Actions workflow documentation
│
├── update_news.py              # Python script to auto-update news articles + RSS feed
├── update_sri.py               # Python script to update SRI hashes & cache-bust params
├── calculate-sri.sh            # Shell script for manual SRI hash calculation
├── UPDATE_NEWS_README.md       # News automation documentation
├── UPDATE_SRI_README.md        # SRI & cache-busting documentation
├── RSS_FEED_README.md          # RSS feed usage guide for subscribers
│
├── .github/workflows/
│   ├── update-news.yml              # Automated news + RSS feed updates (every 12 hours)
│   └── site-update-deploy.yml       # Unified workflow: SRI, preview, URL safety, deploy
│
├── resources-data.json         # Data export of all resources (for integrations)
├── preview-mapping.json        # Metadata for resource previews
│
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
    <div class="resource-card">
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

News articles are **updated automatically** — you don't need to add them by hand. A GitHub Actions workflow runs every 12 hours, pulls articles from 22 cloud security RSS feeds, and creates a pull request with the new content. See the [How Automation Works](#-how-automation-works) section below for details, or read the full docs in [UPDATE_NEWS_README.md](UPDATE_NEWS_README.md).

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

### Customizing the Homepage

Edit the "Resource Categories" section in `index.html` to:
- Change category descriptions
- Modify call-to-action buttons
- Adjust hero section messaging

---

## 🤖 How Automation Works


This site uses **GitHub Actions workflows** to automate all major site updates. Most automation is now handled by a **unified workflow** that runs all key steps in sequence, only when needed.

### Unified Site Update & Deploy Workflow

**Workflow file:** `.github/workflows/site-update-deploy.yml`

**Triggers on pushes to `main` when these files change:**
- `style.css`, `main.js`, `chat-resources.js`, `update_sri.py`
- `resources.html`, `chat-resources.html`
- `chat-screenshots/**` (new chat resource screenshots)
- Manual trigger via the GitHub Actions tab

**What it does:**
- Updates SRI hashes and cache-busting tags if CSS/JS changed (using `update_sri.py`)
- Generates preview images for new resources in `resources.html` (using `generate_preview.py`)
- Deploys the site to the web server via FTP in smart passes:
  - **Pass 1:** Always deploys all HTML/CSS/JS and other site files (excludes images)
  - **Pass 2:** Only uploads `img/previews/` when new preview images were generated
  - **Pass 3:** Only uploads `chat-screenshots/` when new screenshots were added

**How it works:**
1. Checks for any changes that require SRI updates, new previews, or new chat screenshots
2. Runs each step in order, skipping steps if not needed
3. Only deploys after all updates succeed

**News updates** are still handled by a separate scheduled workflow (`update-news.yml`) that runs every 12 hours and creates a PR with new articles. Once merged, the unified workflow deploys the site.

**Full docs:** See [UPDATE_SRI_README.md](UPDATE_SRI_README.md), [tools/GENERATE_PREVIEW_README.md](tools/GENERATE_PREVIEW_README.md), [UPDATE_NEWS_README.md](UPDATE_NEWS_README.md), and [tools/CHECK_URL_SAFETY_README.md](tools/CHECK_URL_SAFETY_README.md)

### Setup Note

Workflows use a **Personal Access Token (PAT)** stored as a GitHub repo secret called `PAT_TOKEN`. If workflows start failing with permission errors, the PAT may need to be rotated — see setup instructions in [UPDATE_NEWS_README.md](UPDATE_NEWS_README.md#setup-requirements).

---

## 🔍 SEO & Search Optimization

### Rich Snippets Enabled
- ✅ **NewsArticle Schema** - 120+ articles eligible for Google News carousel
- ✅ **FAQPage Schema** - 5 high-relevance Q&A pairs for featured snippets
- ✅ **Organization Schema** - Domain authority signals (4.8★ rating, 2000+ members)
- ✅ **CollectionPage Schema** - Resource pages eligible for rich results
- ✅ **Event Schema** - Weekly Zoom session marked up for search visibility
- ✅ **BreadcrumbList** - Navigation hierarchy for SERP display

## 🤝 Contributing

Want to help improve CSOH? We have **beginner-friendly guides** for contributing—no coding experience needed!

### 📚 Contribution Guides

- **[Interactive Resource Submission Tool](tools/SUBMIT_RESOURCE_README.md)** - Automated Python script with URL validation and PR creation
- **[Interactive News Source Submission Tool](tools/SUBMIT_NEWS_SOURCE_README.md)** - Add RSS/Atom feeds with the interactive script
- **[How to Add a Resource](contribute-resources.html)** - Step-by-step guide for adding cloud security resources (tools, labs, certifications, etc.)
- **[General Contributions](contribute.html)** - Guide for all other contributions:
  - Adding news sources for our daily news automation
  - Improving descriptions and content
  - Suggesting resource reorganization
  - Reporting bugs or broken links
  - Feature requests and ideas

### Quick Start

**Easy options (no coding required):**
1. [Report an issue](https://github.com/CloudSecurityOfficeHours/csoh.org/issues) - Found a bug? Have a suggestion?
2. [Join Discord](https://discord.gg/AVzAY97D8E) - Discuss ideas with the community
3. [Add a resource](contribute-resources.html) - Use our web-based guide (copy/paste method)
4. [Use the submission tool](tools/SUBMIT_RESOURCE_README.md) - Interactive Python script (automated)
5. [Add a news source](tools/SUBMIT_NEWS_SOURCE_README.md) - Interactive Python script

**For developers:**
1. Fork the repository
2. Create a feature branch: `git checkout -b add-resource`
3. Make changes and test locally
4. Commit with clear messages: `git commit -m "Add AWS security labs resource"`
5. Push to your fork: `git push origin add-resource`
6. Create a Pull Request

### Contribution Guidelines

- All resources must be **free or freemium** (or worth including as premium option)
- Ensure **working links** before submitting
- Add **descriptive tags** (AWS, Azure, GCP, Kubernetes, CTF, Tools, Labs)
- Maintain **vendor neutrality** - no paid sponsorships without disclosure
- Follow existing **HTML/CSS conventions**

---

## 📞 Community & Support

### Join the Community
- **Discord**: https://discord.gg/AVzAY97D8E - 2000+ members, real-time discussions
- **Zoom Sessions**: https://sendfox.com/CSOH - Fridays at 7:00 AM PT
- **GitHub**: https://github.com/CloudSecurityOfficeHours/csoh.org

### Need Help?
- **Discord**: Ask in #general or #resources channel
- **Issues**: Create a [GitHub issue](https://github.com/CloudSecurityOfficeHours/csoh.org/issues)
- **Contact**: Reach out via Discord to community admins

### Support CSOH
- ❤️ **Star** this repository
- 🔗 **Share** CSOH with your network
- 💬 **Contribute** resources or improvements
- 💰 **Donate** via [PayPal](https://www.paypal.com/paypalme/cloudsec) (optional, fully community-run)

---

## 📋 Stats & Impact

- **2000+** Community members
- **260+** Curated resources
- **554+** Community-shared URLs (from Zoom chat sessions)
- **120+** News articles (auto-updated daily)
- **1,000+** URLs validated for security
- **6** Resource categories
- **50+** Training platforms
- **60+** Security tools catalogued
- **~100+** Published presentations
- **Weekly** Expert Zoom sessions
- **2** Automated workflows (news, unified site update/deploy)

---

## 📜 License

- **Website Code**: MIT License - Feel free to fork and customize
- **Resource Descriptions**: Creative Commons Attribution
- **Linked Resources**: Property of their respective creators/owners
- **News Articles**: Linked to original sources with proper attribution

Copyright © 2023-2026 Cloud Security Office Hours

---

## 🙏 Acknowledgments

Special thanks to:
- **2000+ Community Members** - Your engagement drives everything
- **Guest Speakers** - Industry experts sharing knowledge
- **Contributors** - Those adding resources and improvements
- **Open Source Community** - Tools and platforms we catalog

---

## 🎓 Getting Started

**New to cloud security?** Here's our recommended learning path:

1. **Start with Resources**: Browse [CTF Challenges](resources.html#ctf-challenges) and [Labs](resources.html#labs-training)
2. **Get Certified**: Explore [Certifications](resources.html#certifications) path for your cloud platform
3. **Join Community**: Register for [Weekly Zoom Sessions](sessions.html) (Fridays 7 AM PT)
4. **Stay Updated**: Check [News](news.html) daily for latest threats and updates
5. **Subscribe to RSS**: Add our [RSS feed](https://csoh.org/feed.xml) to your reader — see [RSS_FEED_README.md](RSS_FEED_README.md) for setup
6. **Network**: Join [Discord](https://discord.gg/AVzAY97D8E) for real-time discussions

---

**Last Updated**: February 16, 2026

For the latest updates and announcements, follow us on Discord!
