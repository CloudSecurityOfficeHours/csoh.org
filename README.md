# Cloud Security Office Hours (CSOH)

A modern, community-driven cloud security resource hub built as a fast, responsive static website. Home to **2000+ security professionals**, **260+ curated resources**, **120+ news articles**, **554+ community-shared URLs**, and weekly expert-led Zoom sessions.

[![GitHub](https://img.shields.io/badge/GitHub-CloudSecurityOfficeHours/csoh.org-blue)](https://github.com/CloudSecurityOfficeHours/csoh.org)
[![Discord](https://img.shields.io/badge/Discord-2000%2B%20Members-5865F2)](https://discord.gg/AVzAY97D8E)
[![License](https://img.shields.io/badge/License-Open%20Content-green)](LICENSE)

---

## 🎯 About CSOH

Cloud Security Office Hours is a **vendor-neutral, free community** dedicated to advancing cloud security education and collaboration. Founded in February 2023, CSOH has grown to 2000+ members worldwide, providing:

- **Weekly Expert Zoom Sessions** - Every Friday at 7:00 AM PT with industry experts
- **260+ Curated Resources** - CTF challenges, hands-on labs, security tools, certifications
- **120+ News Articles** - Daily cloud security news from reputable sources
- **554+ Community-Shared URLs** - Secure, validated links from Zoom chat sessions
- **Active Discord Community** - Real-time discussions, peer learning, mentorship
- **Automated Security Validation** - All URLs checked for malicious patterns before publication
- **Vender Neutral** - Completely free, open, community-run initiative

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

## 🚀 Features

### ⚡ Performance & Security
- **Pure Static HTML** - No database, server-side code, or backend dependencies
- **Instant Load Times** - Optimized CSS/JS, no external frameworks
- **Zero Vulnerabilities** - No SQL injection, XSS, or code execution risks
- **Automated URL Safety Checks** - All URLs validated for phishing, malware, and suspicious patterns
- **CI/CD Security Validation** - GitHub Actions workflow blocks unsafe URLs before merge
- **1,000+ URLs Validated** - Comprehensive site-wide security scanning
- **CDN Ready** - Deploy anywhere (GitHub Pages, Vercel, AWS S3, etc.)
- **100% Uptime** - Simple file hosting = maximum reliability

### 🔍 SEO & Discoverability
- **Rich Schema Markup** - NewsArticle, FAQPage, Organization, Event, CollectionPage
- **Featured Snippet Optimization** - FAQ schema for voice search
- **Google News Carousel** - Article collection markup
- **Mobile Responsive** - Perfect Google Lighthouse scores
- **Sitemap.xml & robots.txt** - Full crawlability configuration
- **Open Graph & Twitter Cards** - Social media optimization

### ♿ Accessibility
- **Semantic HTML5** - Proper heading hierarchy (H1→H2→H3)
- **ARIA Labels** - Screen reader support
- **Keyboard Navigation** - Full keyboard access
- **Color Contrast** - WCAG AA compliant
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
├── style.css                   # Main stylesheet (responsive design)
├── main.js                     # Interactive features (search, filter, sorting)
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
│   ├── check_url_safety.py           # Core URL safety validator with pattern matching
│   ├── check_existing_urls.py        # Batch scanner for chat-resources.html URLs
│   ├── check_all_site_urls.py        # Comprehensive site-wide URL scanner
│   ├── update_chat_titles.py         # Generate descriptive titles for chat URLs
│   ├── CHECK_URL_SAFETY_README.md    # URL safety checker documentation
│   └── CHECK_URL_SAFETY_WORKFLOW.md  # GitHub Actions workflow documentation
│
├── update_news.py              # Python script to auto-update news articles
├── update_sri.py               # Python script to update SRI hashes & cache-bust params
├── calculate-sri.sh            # Shell script for manual SRI hash calculation
├── UPDATE_NEWS_README.md       # News automation documentation
├── UPDATE_SRI_README.md        # SRI & cache-busting documentation
│
├── .github/workflows/
│   ├── update-news.yml         # Automated news updates (every 12 hours)
│   ├── update-sri.yml          # Automated SRI hash updates (on CSS/JS changes)
│   ├── check-url-safety.yml    # Automated URL safety validation (on HTML changes)
│   └── deploy to csoh.org.yml  # Automated FTP deployment (on push to main)
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

4. **Commit and push** to update the live site

### Adding a New Article to News

News articles are **updated automatically** — you don't need to add them by hand. A GitHub Actions workflow runs every 12 hours, pulls articles from 22 cloud security RSS feeds, and creates a pull request with the new content. See the [How Automation Works](#-how-automation-works) section below for details, or read the full docs in [UPDATE_NEWS_README.md](UPDATE_NEWS_README.md).

To **add a new news source**, edit the `FEEDS` list at the top of `update_news.py` and submit a pull request.

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

This site uses four **GitHub Actions workflows** that handle routine tasks automatically. GitHub Actions is a free automation service built into GitHub — think of it as a robot that runs scripts for you whenever certain things happen in the repo.

### 1. News Auto-Updates (every 12 hours)

**What it does:** Keeps the [News page](https://csoh.org/news.html) fresh without anyone manually adding articles.

**How it works:** Twice a day, a Python script (`update_news.py`) checks 22 cloud security news sources for new articles. It filters for relevant topics, removes duplicates, and updates `news.html`. The workflow creates a Pull Request with the changes — if only `news.html` changed, it auto-merges. Once merged, the site is automatically deployed.

**Full docs:** [UPDATE_NEWS_README.md](UPDATE_NEWS_README.md)

### 2. SRI Hash & Cache-Bust Updates (on CSS/JS changes)

**What it does:** Keeps the site secure and prevents visitors from seeing stale styles after updates.

**How it works:** Whenever `style.css` or `main.js` is changed and pushed to `main`, a Python script (`update_sri.py`) automatically:
- Recalculates **SRI fingerprints** — cryptographic hashes that let the browser verify the file hasn't been tampered with
- Updates **cache-busting version tags** (`?v=abc123` in the URL) — so browsers download the fresh file instead of serving an old cached copy
- Commits the updated HTML files and pushes them

**Full docs:** [UPDATE_SRI_README.md](UPDATE_SRI_README.md)

### 3. URL Safety Validation (on any HTML file change)

**What it does:** Protects the site from malicious URLs by validating all links before they go live.

**How it works:** Whenever any HTML file is modified in a pull request or push, a Python script (`check_all_site_urls.py`) scans **all URLs across the entire site** (1,000+ URLs) and checks them against:
- **Suspicious patterns** - URL shorteners, raw IP addresses, executable files, phishing indicators
- **Blocklist** - Known malicious domains
- **Whitelist** - Trusted domains (GitHub, AWS, Microsoft, etc.)
- **Security best practices** - HTTPS usage, domain length, subdomain depth

If any **unsafe URLs** are detected, the workflow **fails and blocks the merge**, posting a detailed report as a comment on the PR. The full safety report is uploaded as an artifact for 30 days.

**Full docs:** [tools/CHECK_URL_SAFETY_README.md](tools/CHECK_URL_SAFETY_README.md) and [.github/workflows/CHECK_URL_SAFETY_WORKFLOW.md](.github/workflows/CHECK_URL_SAFETY_WORKFLOW.md)

### 4. Auto-Deploy to Web Server (on push to main)

**What it does:** Uploads the latest site files to the web server whenever changes land on the `main` branch.

**How it works:** After any push to `main` (including auto-merged news PRs and SRI hash commits), the deploy workflow checks out the code, recalculates SRI hashes as a safety net, and uploads everything to the web server via FTP.

### Setup Note

All three workflows use a **Personal Access Token (PAT)** stored as a GitHub repo secret called `PAT_TOKEN` (because the GitHub organization restricts the default token). If workflows start failing with permission errors, the PAT may need to be rotated — see the setup instructions in [UPDATE_NEWS_README.md](UPDATE_NEWS_README.md#setup-requirements).

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
- **4** Automated workflows (news, SRI, URL safety, deployment)

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
5. **Network**: Join [Discord](https://discord.gg/AVzAY97D8E) for real-time discussions

---

**Last Updated**: February 15, 2026

For the latest updates and announcements, follow us on Discord!
