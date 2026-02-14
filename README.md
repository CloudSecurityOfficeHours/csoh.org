# Cloud Security Office Hours (CSOH)

A modern, community-driven cloud security resource hub built as a fast, responsive static website. Home to **2000+ security professionals**, **260+ curated resources**, **120+ news articles**, and weekly expert-led Zoom sessions.

[![GitHub](https://img.shields.io/badge/GitHub-CloudSecurityOfficeHours/csoh.org-blue)](https://github.com/CloudSecurityOfficeHours/csoh.org)
[![Discord](https://img.shields.io/badge/Discord-2000%2B%20Members-5865F2)](https://discord.gg/AVzAY97D8E)
[![License](https://img.shields.io/badge/License-Open%20Content-green)](LICENSE)

---

## 🎯 About CSOH

Cloud Security Office Hours is a **vendor-neutral, free community** dedicated to advancing cloud security education and collaboration. Founded in February 2023, CSOH has grown to 2000+ members worldwide, providing:

- **Weekly Expert Zoom Sessions** - Every Friday at 7:00 AM PT with industry experts
- **260+ Curated Resources** - CTF challenges, hands-on labs, security tools, certifications
- **120+ News Articles** - Daily cloud security news from reputable sources
- **Discord Community** - Real-time discussions, peer learning, mentorship
- **Vendor Neutral** - Completely free, open, community-run initiative

---

## 📄 Website Pages

### 🏠 Homepage (`index.html`)
Central hub featuring:
- Community overview and value proposition
- Featured resource categories with quick navigation
- Call-to-action buttons for Zoom registration and Discord
- Enhanced schema markup for improved SERP visibility

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
├── update_news.py              # Python script to auto-update news articles
├── setup_autoupdate.sh         # Setup script for dependencies
├── UPDATE_NEWS_README.md        # News automation documentation
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

1. Open `news.html`
2. Add new article card in the article grid (maintain date-sorted order):

```html
<a href="https://article-url.com" target="_blank" class="card-link" rel="noopener noreferrer">
    <div class="resource-card" data-category="report">
        <h3>Article Title</h3>
        <p class="article-date">February 10, 2026</p>
        <p>Brief description of the article content... <span class="source">(Source Name)</span></p>
        <div class="resource-tags">
            <span class="tag">Cloud Security</span>
            <span class="tag">AWS</span>
        </div>
    </div>
</a>
```

**Option 2: Automated Updates (Recommended)**
1. Run the news updater:
   ```bash
   python3 update_news.py
   ```

2. Set up automatic daily updates via cron (macOS/Linux):
   ```bash
   crontab -e
   # Add this line (updates every day at 2 AM):
   0 2 * * * cd /path/to/csoh.org && python3 update_news.py
   ```

3. Optional: review the feed list and settings in `update_news.py`.

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
- **120+** News articles (auto-updated daily)
- **6** Resource categories
- **50+** Training platforms
- **60+** Security tools catalogued
- **~100+** Published presentations
- **Weekly** Expert Zoom sessions

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

**Last Updated**: February 10, 2026

For the latest updates and announcements, follow us on Discord!
