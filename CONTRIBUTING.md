# 🤝 Contributing to CSOH.org

Welcome! This guide covers **any change you want to suggest** to the CSOH website — whether it's adding news sources, improving descriptions, fixing typos, or redesigning the homepage. You don't need to be a developer.

**Common contributions:**
- 📰 **News Sources** - Add feeds so we get better articles
- 📝 **Content Changes** - Improve descriptions, fix typos, update information
- 🏷️ **Categorization** - Suggest better tags or organization
- 🎨 **Homepage Ideas** - Suggest content or layout improvements
- 🐛 **Bug Reports** - Report broken links or display issues
- ✨ **Feature Suggestions** - Ideas for new pages or functionality

---

## 📖 What You'll Learn

1. **Types of contributions** - What can be changed
2. **How to prepare your change** - Gathering details
3. **How to find what to edit** - Locating files
4. **Making the edit** - Step-by-step walkthrough
5. **Creating a pull request** - Getting your change reviewed
6. **What happens next** - The publishing process

**Time needed:** 5-20 minutes depending on complexity

---

## 🎯 Types of Contributions

### 1️⃣ Adding News Sources

**What this means:** Suggest RSS feeds or websites we should pull news articles from

**Examples:**
- A security blog that publishes cloud security news
- A vendor blog with good security research
- A news aggregator with cloud articles

**Why it matters:** More sources = better, more diverse news for our readers

**Have an idea?** Gather:
- Name of the source (e.g., "ThoughtWorks Technology Radar")
- RSS feed URL (e.g., `https://example.com/feed.xml`)
- Why you think it's good (e.g., "Excellent Kubernetes security content")

**How to contribute:** [See "Adding News Sources" below](#adding-news-sources)

---

### 2️⃣ Improving Descriptions & Content

**What this means:** Fix grammar, make descriptions clearer, update outdated info

**Examples:**
- A resource description isn't clear
- You found a typo in homepage text
- A certification became available for a new cloud platform
- A tool's description is outdated

**Why it matters:** Clear, accurate content helps people learn and find what they need

**Have an idea?** Note:
- What page or section needs fixing
- What's wrong with it
- What the better version should say

**How to contribute:** [See "Editing Content" below](#editing-content--descriptions)

---

### 3️⃣ Suggesting Better Categorization

**What this means:** Propose new tags, reorganize sections, or change how things are grouped

**Examples:**
- A resource has the wrong tags
- Two categories should be combined
- A new tag would help people find things better
- A resource is in the wrong section

**Why it matters:** Good organization helps people discover resources they need

**Have an idea?** Suggest:
- What should be changed
- What tags or categories are better
- Why the change helps users

**How to contribute:** [See "Suggesting Reorganization" below](#suggesting-reorganization)

---

### 4️⃣ Homepage & Main Page Improvements

**What this means:** Changes to [index.html](index.html), any page's header/footer, navigation

**Examples:**
- Homepage content is outdated
- Navigation is confusing
- A section needs updating
- New content should be featured

**Why it matters:** The homepage is people's first impression of CSOH

**Have an idea?** Describe:
- What you want to change
- Why it's important
- What the new version should say/look like

**How to contribute:** [See "Editing Content" below](#editing-content--descriptions)

---

### 5️⃣ Bug Reports & Technical Issues

**What this means:** Report broken links, display problems, or errors

**Examples:**
- A link doesn't work
- A page looks wrong on mobile
- A button doesn't do anything
- Text is hard to read

**Why it matters:** We want the site to work perfectly for everyone

**Have an idea?** Tell us:
- What's broken
- When it happens (what page, device, browser)
- What it should do instead

**How to contribute:** [See "Reporting Issues" below](#reporting-issues)

---

### 6️⃣ Feature Suggestions

**What this means:** Ideas for new pages, tools, or functionality

**Examples:**
- "We should have a page for interview prep resources"
- "Can we add a 'recently added' section?"
- "Community members should be able to rate resources"

**Why it matters:** Great ideas help CSOH grow and stay useful

**Have an idea?** Explain:
- What feature you'd like
- Why it would help the community
- How you imagine it working

**How to contribute:** [See "Feature Requests" below](#feature-requests)

---

## 🔧 How to Make Your Contribution

### Adding News Sources

News articles come from RSS feeds. Adding a new source means adding its feed to our script.

#### Step 1: Find the News Script

1. Go to [update_news.py](update_news.py) on GitHub
2. Click the pencil ✏️ icon to edit

#### Step 2: Add Your Feed

Look for this section:

```python
FEEDS = [
    'https://feeds.arstechnica.com/arstechnica/index',
    'https://feeds.engadget.com/engadget',
    # ... more feeds
]
```

Add your new feed to the list:

```python
FEEDS = [
    'https://feeds.arstechnica.com/arstechnica/index',
    'https://feeds.engadget.com/engadget',
    'https://your-new-source.com/feed.xml',  # ← Add here
]
```

#### Step 3: Commit and Create a Pull Request

1. Scroll down and click **"Commit changes"**
2. Write a message: `"Add [Source Name] to news feeds"`
3. Create a pull request (see [Creating a Pull Request](#creating-a-pull-request) below)

**Tips:**
- Many websites have **RSS feeds** (look for an RSS icon 🔘)
- If the site doesn't list a feed URL, try `/feed`, `/feed.xml`, or `/rss`
- Check the feed actually contains cloud security articles before suggesting
- Add feeds from **reputable sources** (established news sites, vendor blogs, research orgs)

**How to find RSS feeds:**
- Look for an RSS icon on the website
- Try common URLs: `yoursite.com/feed` or `yoursite.com/feed.xml`
- Use a [Feed Finder tool](https://www.feedly.com/) to discover feeds

---

### Editing Content & Descriptions

Whether you're fixing a typo or rewriting a section, the process is the same.

#### Step 1: Find the File to Edit

**For resource descriptions:**
- File: [resources.html](resources.html)

**For homepage content:**
- File: [index.html](index.html)

**For news page:**
- File: [news.html](news.html)

**For other pages:**
- [sessions.html](sessions.html) - Zoom sessions info
- [presentations.html](presentations.html) - Past presentations

#### Step 2: Open the File for Editing

1. Click on the file name above
2. Click the pencil ✏️ icon to edit

#### Step 3: Find What You're Changing

Use `Ctrl+F` (or `Cmd+F` on Mac) to search for the text you're changing.

For example, if you're fixing a resource description:
- Search for the resource name
- Find the `<p>` tag with the description
- Click after the text to position your cursor

#### Step 4: Make Your Edit

Just type! You're editing text, it works like a document:
- **Fix typos:** Select the wrong word, delete it, type the right one
- **Improve descriptions:** Select the old text, replace with better wording
- **Update info:** Change dates, numbers, or outdated content
- **Add links:** Add `<a href="url">text</a>` around text you want to link

**Example - Fixing a typo:**
```html
<!-- BEFORE -->
<p>Learn cloud security with hands-on laps.</p>

<!-- AFTER -->
<p>Learn cloud security with hands-on labs.</p>
```

**Example - Improving a description:**
```html
<!-- BEFORE -->
<p>AWS training tool.</p>

<!-- AFTER -->
<p>Comprehensive AWS security training with hands-on labs for IAM, 
networking, and data protection.</p>
```

#### Step 5: Commit and Create a Pull Request

1. Scroll down and click **"Commit changes"**
2. Write a helpful message explaining what you changed
3. Create a pull request (see below)

---

### Suggesting Reorganization

Want to suggest moving a resource, adding new tags, or reorganizing sections?

#### Option A: Edit the File Directly

If it's a simple change (moving a resource, fixing a tag):

1. Open [resources.html](resources.html)
2. Find the resource card
3. Change the `<span class="tag">` lines to add/remove/fix tags
4. Move the entire `<a class="card-link">...</a>` block to a different section if needed
5. Commit with a message like: "Move [Resource] to correct category and fix tags"

#### Option B: Suggest It in a Pull Request

If you're not sure exactly how to do it:

1. Fork the repo (see [Creating a Pull Request](#creating-a-pull-request))
2. Make the changes as described above
3. In your pull request description, explain your reasoning:

```
**Suggestion:** Move Redis Labs to "Security Tools" instead of "Labs"
**Reason:** Redis Labs is a vendor tool, not a training lab
**Benefit:** Better organization helps users find what they're looking for
```

---

### Editing the Homepage

The homepage is at [index.html](index.html). It contains:
- Hero section (big banner at top)
- About text
- Featured resources
- Call-to-action buttons
- Footer

To edit:

1. Click [index.html](index.html)
2. Click pencil ✏️ to edit
3. Use `Ctrl+F` to find what you want to change
4. Edit the text or HTML
5. Commit and create pull request

**Common changes:**
- Update member count or statistics
- Change featured sections
- Add new content
- Fix broken links
- Improve descriptions

---

### Reporting Issues

Found a bug or broken link? You can create an **Issue** (no coding required):

#### Step 1: Go to Issues

1. Visit [github.com/CloudSecurityOfficeHours/csoh.org](https://github.com/CloudSecurityOfficeHours/csoh.org)
2. Click the **"Issues"** tab

#### Step 2: Create a New Issue

1. Click **"New Issue"**
2. Give it a title: "Broken link in Resources page" or "Mobile display issue"
3. Describe the problem:
   ```
   **What's broken:**
   The link to CloudGoat doesn't work
   
   **Where it is:**
   Resources page, CTF section
   
   **What should happen:**
   The link should go to https://github.com/RhinoSecurityLabs/cloudgoat
   
   **What's happening instead:**
   404 error / page doesn't load
   ```

4. Click **"Submit new issue"**

Maintainers will fix it! You don't need to know how to code.

---

### Feature Requests

Have a big idea? Create an issue:

#### Step 1: Go to Issues

1. Visit [github.com/CloudSecurityOfficeHours/csoh.org](https://github.com/CloudSecurityOfficeHours/csoh.org)
2. Click the **"Issues"** tab

#### Step 2: Create a New Issue

1. Click **"New Issue"**
2. Title: "Feature: Interview prep resources section"
3. Describe your idea:
   ```
   **The idea:**
   Create a new "Interview Prep" category with resources for cloud 
   security job interviews
   
   **Why it would help:**
   Many community members ask interview questions. A dedicated section 
   would help them prepare.
   
   **Example content:**
   - Behavioral interview guides
   - Technical interview prep
   - Mock interview platforms
   - Salary research resources
   
   **How it could work:**
   New "Interview Prep & Career" section on resources page with 20-30 resources
   ```

4. Click **"Submit new issue"**

---

## 📝 Creating a Pull Request

A **pull request (PR)** is how you submit your changes for review. Think of it like:
- Writing a memo with your suggested changes
- Waiting for feedback
- Getting approval before the change goes live

### Quick Method: Edit Directly on GitHub

This is easiest for small changes:

#### Step 1: Fork the Repository

1. Go to [github.com/CloudSecurityOfficeHours/csoh.org](https://github.com/CloudSecurityOfficeHours/csoh.org)
2. Click **"Fork"** button (top-right)
3. This creates your own copy

#### Step 2: Make Your Changes

In your fork:
1. Click on the file you want to edit
2. Click the pencil ✏️ icon
3. Make your changes
4. Click **"Commit changes"**
5. Write a commit message (e.g., "Fix typo in CloudGoat description")
6. Click **"Commit changes"** again

Repeat for any other files you're changing.

#### Step 3: Create the Pull Request

1. Go back to your fork's main page
2. You'll see a message like **"This branch is ahead of CloudSecurityOfficeHours:main"**
3. Click **"Contribute"** → **"Open pull request"**
4. Check the changes look right
5. Add a **Title**: What did you change?
   - "Add Snyk to Security Tools"
   - "Fix HomeLab description"
   - "Add 5 new news sources"

6. Add a **Description**: Why did you change it?
   ```
   **What I changed:**
   - Added Snyk to Security Tools section
   - Tagged with: Tool, CSPM, Vulnerability Management
   
   **Why:**
   Snyk is a popular cloud security tool that wasn't listed. 
   Many community members use it.
   ```

7. Click **"Create pull request"**

**That's it!** A maintainer will review your contribution.

### More Advanced: Using Git (Optional)

If you're comfortable with the command line, you can use Git:

```bash
# Clone the repository
git clone https://github.com/CloudSecurityOfficeHours/csoh.org.git
cd csoh.org

# Create a new branch
git checkout -b add-news-sources

# Edit files
nano update_news.py  # or use your editor

# Stage changes
git add .

# Commit
git commit -m "Add TechCrunch security feed"

# Push to your fork
git push origin add-news-sources

# Go to GitHub and create a pull request
```

**Learning resources:**
- [Git Basics](https://git-scm.com/book/en/v2/Getting-Started-Git-Basics)
- [GitHub Git Cheat Sheet](https://github.github.com/training-kit/downloads/github-git-cheat-sheet.pdf)

---

## 📋 Pull Request Checklist

Before you submit, make sure:

- ✅ **Changes are clear** - Someone can understand what you did
- ✅ **Spelling/grammar is correct** - Your PR text is well-written
- ✅ **Links work** - Test any URLs you're adding
- ✅ **Formatting looks right** - Check HTML looks correct
- ✅ **Commit message is helpful** - Clearly describe what you did
- ✅ **You're not changing too much** - Keep each PR focused on one thing

### 🛡️ Automated URL Safety Check

When you submit a PR that modifies any HTML file, our automated workflow will:

- ✅ **Scan all URLs** across the entire site (1,000+ URLs)
- ⚠️ **Flag suspicious patterns** (URL shorteners, HTTP-only, etc.)
- ❌ **Block unsafe URLs** (phishing, malware, blocklisted domains)
- 📋 **Generate a report** available as a workflow artifact

**What this means for you:**
- If your PR adds or modifies URLs, they'll be automatically validated
- ✅ **Safe URLs** - PR can merge immediately
- ⚠️ **Suspicious warnings** - PR can still merge, but review the warnings
- ❌ **Unsafe URLs** - PR will be blocked until the issue is fixed

**Pro tips:**
- Always use HTTPS when available
- Link to official sources (GitHub, AWS docs, etc.)
- Avoid URL shorteners - use full destination URLs
- Test links before submitting

See [tools/CHECK_URL_SAFETY_README.md](tools/CHECK_URL_SAFETY_README.md) for full details.

---

## 🔗 Helpful External Resources

### GitHub Learning
- **What is GitHub?** → [GitHub's Getting Started](https://docs.github.com/en/get-started)
- **Forking a repo** → [GitHub Fork Documentation](https://docs.github.com/en/get-started/quickstart/fork-a-repo)
- **Making changes on GitHub** → [Editing Files in GitHub](https://docs.github.com/en/repositories/working-with-files/managing-files/editing-files)
- **Pull requests explained** → [GitHub PR Guide](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests)
- **Git command line tutorial** → [Git Tutorial](https://git-scm.com/docs/gittutorial)

### RSS Feeds
- **What is RSS?** → [RSS Explained](https://www.makeuseof.com/tag/what-is-an-rss-feed/)
- **Finding RSS feeds** → [Feedly Feed Directory](https://feedly.com/)
- **Feed URL patterns** → [Common RSS Feed URLs](https://www.makeuseof.com/tag/how-to-find-a-website-rss-feed/)

### HTML Basics (If Curious)
- **HTML elements** → [W3Schools HTML Tutorial](https://www.w3schools.com/html/)
- **Common HTML tags** → [MDN HTML Reference](https://developer.mozilla.org/en-US/docs/Web/HTML/Element)

### Markdown (For PR Descriptions)
- **Writing good PR descriptions** → [GitHub Markdown Guide](https://guides.github.com/features/mastering-markdown/)
- **Markdown syntax** → [Markdown Cheatsheet](https://github.com/adam-p/markdown-here/wiki/Markdown-Cheatsheet)

---

## ❓ FAQ

**Q: Do I need to be a developer?**  
A: No! All the examples above use GitHub's web interface. No coding experience needed.

**Q: What if I make a mistake?**  
A: You can edit your PR before it's merged. Or maintainers can suggest fixes. Mistakes are learning opportunities!

**Q: How long until my change is published?**  
A: Usually 1-3 days. Maintainers review each PR to maintain quality.

**Q: Can I suggest changes I don't know how to make?**  
A: Yes! Open an issue with your suggestion. You don't have to code it.

**Q: What if my pull request gets rejected?**  
A: That's okay! You'll get feedback on why. You can discuss it or try again.

**Q: Can I suggest multiple changes at once?**  
A: It's better to do one thing per PR. But you can have multiple PRs open.

**Q: Do you accept all suggestions?**  
A: We review for quality and fit with CSOH's mission. We'll explain if something doesn't fit.

**Q: What qualifies as a good news source?**  
A: Reputable sources with regular cloud security content. Not spam, not paywalled (usually).

**Q: Can I suggest a resource for myself/my company?**  
A: Sure! Disclose that it's yours. We value transparency. If it's genuinely useful to the community, it'll be accepted.

**Q: How do I know if something is "good enough" to suggest?**  
A: If it would help a cloud security professional learn or advance, it's worth suggesting. The community decides!

---

## 🎁 Recognition

Contributors get:
- Your name and link in our contributor credits
- Recognition in community posts
- Gratitude from 2000+ cloud security professionals
- The satisfaction of helping people learn

---

## 🚀 Ready to Contribute?

1. **Found a bug?** → [Report it here](https://github.com/CloudSecurityOfficeHours/csoh.org/issues/new)
2. **Have a suggestion?** → [Create an issue](https://github.com/CloudSecurityOfficeHours/csoh.org/issues/new)
3. **Want to make a change?** → Follow the steps above
4. **Questions?** → Join our [Discord](https://discord.gg/AVzAY97D8E)

---

## 📞 Need Help?

- **GitHub questions** → Ask in [GitHub Discussions](https://github.com/CloudSecurityOfficeHours/csoh.org/discussions)
- **Community support** → [Discord server](https://discord.gg/AVzAY97D8E)
- **Security issues** → Email security@csoh.org
- **Want to contribute resources?** → Check [CONTRIBUTING_RESOURCES.md](CONTRIBUTING_RESOURCES.md)

---

**Thank you for helping make CSOH better! 🙏**

Every contribution—from fixing a typo to suggesting a whole new section—helps our community grow.

*Made with ❤️ by the Cloud Security Office Hours Team*
