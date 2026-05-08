# 📚 How to Add a Cloud Security Resource to CSOH

Welcome! This guide will walk you through **adding a new resource** to our community hub. Even if you've never used GitHub or written code before, you can follow these steps. We've broken it down into simple, bite-sized pieces.

**You don't need to be a programmer.** You just need to:
- Find a cool cloud security resource worth sharing
- Copy and paste some text
- Follow a few simple steps

---

## 🎯 What This Guide Covers

1. **Understanding what you're doing** - We'll explain the basics
2. **Finding and preparing your resource** - What info you need to gather
3. **Adding it to the website** - Step-by-step instructions
4. **Creating a pull request** - How to share your contribution with the community
5. **Getting your resource published** - What happens next

**Time needed:** ~10-15 minutes for your first contribution

### 🚀 Quick Option: Interactive Submission Tool

We have an **automated Python script** that handles everything for you:

```bash
python3 tools/submit_resource.py
```

This interactive tool:
- ✅ Prompts you for all required information (including hover tooltip)
- ✅ Validates URLs automatically
- ✅ Generates proper HTML
- ✅ Creates git branch and commits
- ✅ Provides PR creation instructions

### 🧭 Beginner Walkthrough (Interactive Tool)

If you are new to GitHub or the command line, this is the easiest path. Follow these steps:

1. **Install Python** (if you do not already have it)
  - Mac: Python 3 is usually installed. If not, install from python.org.
  - Windows: Install from python.org and check the box "Add to PATH".

2. **Open a terminal**
  - Mac: Spotlight → Terminal
  - Windows: Start → Command Prompt or PowerShell

3. **Clone the repository** (one time only)
  ```bash
  git clone https://github.com/CloudSecurityOfficeHours/csoh.org.git
  cd csoh.org
  ```

4. **Run the script**
  ```bash
  python3 tools/submit_resource.py
  ```

5. **Answer the prompts**
  - Resource name
  - URL
  - Description
  - Tooltip (extended hover description — optional)
  - Category
  - Tags
  - Confirmation

6. **When it finishes**, it will tell you exactly how to push and open a PR


### 🔒 URL Safety, SRI, and Preview Images

The script checks URL safety and can optionally generate a preview image for you.
If you skip the preview, the unified workflow will capture a screenshot and update SRI hashes after you open a PR. You do not need to run any extra scripts—just open a pull request and the automation will handle it.

### 🧰 Common Errors and Fixes

- **`python3` not found**
  - Install Python from python.org and reopen your terminal.
  - On Windows, make sure "Add to PATH" is checked.

- **`git` not found**
  - Install Git from git-scm.com and reopen your terminal.

- **Not in a git repo**
  - Run `cd csoh.org` before running the script.

- **Working directory has uncommitted changes**
  - Commit or stash changes, then re-run the script.

- **Permission denied**
  - Run `chmod +x tools/submit_resource.py` or use `python3 tools/submit_resource.py`.

- **URL flagged as unsafe**
  - Use the official site or GitHub repo URL and try again.

### 🧪 Copy/Paste Commands

**Mac or Linux (Terminal):**
```bash
git clone https://github.com/CloudSecurityOfficeHours/csoh.org.git
cd csoh.org
python3 tools/submit_resource.py
```

**Windows (PowerShell):**
```powershell
git clone https://github.com/CloudSecurityOfficeHours/csoh.org.git
cd csoh.org
python3 tools/submit_resource.py
```

**[See full documentation →](tools/SUBMIT_RESOURCE_README.md)**

If you prefer the manual web-based method, continue reading below!

---

## 📖 What is a Resource?

A **resource** is anything that helps cloud security professionals learn, practice, or advance their careers. Examples:

- 🎯 **CTF Challenges** - Intentionally broken cloud setups you practice hacking
- 🛠️ **Security Tools** - Software that scans or protects cloud infrastructure
- 🎓 **Certifications** - Official courses that teach cloud security skills
- 🧪 **Hands-On Labs** - Interactive exercises where you learn by doing
- 💼 **Job Boards** - Places to find cloud security careers
- 🤖 **AI Security Resources** - Tools and training for AI/ML security

---

## 🚀 Quick Start: Add a Resource in 5 Steps

### Step 1: Gather Your Resource Info

Before you do anything technical, write down these details about your resource:

```
Name:           [e.g., "CloudGoat"]
URL:            [e.g., "https://github.com/RhinoSecurityLabs/cloudgoat"]
Description:    [1-2 sentences explaining what it is and why it's useful]
Tags:           [Select from the list below]
Category:       [Pick one main category]
```

**Example:**
```
Name:           OWASP EKS Goat
URL:            https://github.com/OWASP/www-project-eks-goat
Description:    Intentionally vulnerable AWS EKS environment with 20+ attack-defense 
                labs simulating real-world misconfigurations and IAM flaws.
Tags:           CTF, Labs & Training, AWS, Kubernetes
Category:       CTF Challenges
```

### Step 2: Pick Your Tags

Tags help people find resources. Pick 2-5 tags from this list:

**Resource Types:** `CTF` • `Labs & Training` • `Tool` • `Certification` • `Job Search`

**Cloud Platforms:** `AWS` • `Azure` • `GCP` • `Kubernetes` • `Multi-Cloud`

**Security Focus:** `Vulnerability Testing` • `Penetration Testing` • `Cloud Scanning` • `Secrets Management` • `Compliance` • `AI Security` • `IAM` • `DevSecOps`

**Other:** `NEW 2026` • `Free` • `Paid` • `Open Source`

### Step 3: Preview Image (Skip This)

Preview images auto-generate after you open a PR. You can skip to Step 4.

If you want to provide your own, save a JPG under ~150 KB with a clear name (e.g. `cloudgoat-preview.jpg`) and come back to Step 5.

### Step 4: Edit the Resources HTML File

**Don't be scared!** HTML is just text with special labels. Here's what you need to do:

1. Go to [resources.html](resources.html) on GitHub (or use your code editor)
2. Find the section for your resource's category
3. Copy an **existing resource card** (we'll show you how)
4. Paste it and change the details

**Here's what a resource card looks like:**

```html
<a href="PASTE_YOUR_URL_HERE" class="card-link" target="_blank" rel="noopener noreferrer">
    <div class="resource-card" data-tooltip="Extended 2-3 sentence description that appears on hover. Cover what makes it unique, who benefits most, and any prerequisites or cost info.">
        <h3>Your Resource Name</h3>
        <p>Your resource description goes here. Keep it to 1-2 sentences explaining what it does and why it's useful.</p>
        <div class="resource-tags">
            <span class="tag ctf">CTF</span>
            <span class="tag">AWS</span>
            <span class="tag">Kubernetes</span>
        </div>
    </div>
</a>
```

**What to change:**
- `PASTE_YOUR_URL_HERE` → Your resource's URL
- `data-tooltip="..."` → A richer 2-3 sentence description shown on hover (what makes it unique, who benefits, prerequisites). Use `&quot;` for quotes and `&amp;` for ampersands inside the attribute. Optional — you can remove the attribute if you don't have one.
- `Your Resource Name` → The actual name
- `Your resource description...` → What you wrote in Step 1
- The `<span class="tag">` lines → Your tags

**Tag styling:** Some tags have special colors:
- `<span class="tag ctf">` = CTF (teal)
- `<span class="tag tool">` = Tool (purple)
- `<span class="tag lab">` = Lab/Training (green)
- `<span class="tag ai-security">` = AI Security (orange)
- `<span class="tag certification">` = Certification (blue)
- `<span class="tag job">` = Job Search (pink)
- `<span class="tag">` = Regular tag (gray)

> **Note:** All tag colors automatically adapt to dark mode — you don't need to add any dark mode–specific styles.

**Don't worry about images or SRI hashes!** The site will handle those automatically after you open a pull request. If you want to add a custom preview image, [see Step 5](#step-5-add-a-preview-image-optional).

### Step 5: Add a Preview Image (Optional)

If you took a screenshot in Step 3, follow these sub-steps:

#### 5a. Upload Your Image

1. Go to the [img/previews/](img/previews/) folder on GitHub
2. Click "Add file" → "Upload files"
3. Drag/drop your screenshot
4. Write a commit message: "Add preview image for [Resource Name]"
5. Click "Commit changes"

#### 5b. Edit preview-mapping.json

1. Open [preview-mapping.json](preview-mapping.json)
2. Click the pencil icon to edit
3. Find this section and add a new line:

```json
{
  "https://example.com/": "img/previews/your-preview-image.jpg",
  "https://example.org/": "img/previews/another-preview.jpg"
}
```

For example:
```json
{
  "https://github.com/RhinoSecurityLabs/cloudgoat": "img/previews/cloudgoat-preview.jpg",
  "https://github.com/madhuakula/kubernetes-goat": "img/previews/kubernetes-goat-preview.jpg"
}
```

3. Scroll down and click "Commit changes"

---

## 🍴 Creating a Pull Request (GitHub)

**What's a pull request?** It's how you ask a project to accept your changes. Think of it as raising your hand in class to share something.

### Beginner-Friendly Method: GitHub's Web Interface

You don't need to install anything or learn command-line. Here's the easiest way:

#### Step A: Fork the Repository

1. Go to [github.com/CloudSecurityOfficeHours/csoh.org](https://github.com/CloudSecurityOfficeHours/csoh.org)
2. Click the **"Fork"** button (top-right corner)

   ![Fork button location](https://docs.github.com/assets/cb-25158/images/help/repository/fork_button.jpg)

3. This creates your own copy of the project

#### Step B: Edit the Files

1. In **your fork**, click on `resources.html`
2. Click the pencil icon ✏️ to edit
3. Find where you want to add your resource (scroll to the right category section)
4. Paste your resource card (see Step 4 above)
5. Scroll down and click **"Commit changes"**
6. Add a message like: "Add [Resource Name] to resources"
7. Click **"Commit changes"** again

**Repeat for `preview-mapping.json`** if you have a custom preview image.

#### Step C: Create the Pull Request

1. Go back to **your fork** homepage
2. You'll see a yellow banner saying **"This branch is ahead of CloudSecurityOfficeHours:main"**
3. Click the **"Contribute"** button → **"Open pull request"**
4. Add a title: "Add [Resource Name]"
5. Add a description:
   ```
   **Resource:** [Name]
   **URL:** [Link]
   **Category:** [Category]
   
   This resource teaches [what it teaches]. It would be great 
   for people learning about [what topic].
   ```
6. Click **"Create pull request"**

**That's it!** The maintainers will review your contribution.

---

## 🛡️ Automated URL Safety Check

When you submit your pull request, our automated security system will validate all URLs in your contribution. Here's what happens:

### ✅ What Gets Checked

Every URL is automatically scanned for:
- **Suspicious patterns** - URL shorteners, raw IP addresses, phishing indicators
- **Security best practices** - HTTPS usage, domain legitimacy
- **Blocklisted domains** - Known malicious or spam sites
- **Whitelisted domains** - Trusted sources (GitHub, AWS, Microsoft, etc.)

### 🤖 The Validation Process

1. **GitHub Actions workflow runs** - Automatically triggered when any HTML file changes
2. **All 1,000+ site URLs are scanned** - Your new URL plus all existing ones
3. **Results posted as a check** - You'll see ✅ or ❌ in the PR
4. **Report generated** - Full details available as a workflow artifact

### 🚨 If a URL Fails Validation

**Don't worry!** The workflow blocks unsafe URLs but provides clear guidance:

- **⚠️ Suspicious** (warning) - URL might have minor issues but isn't blocked
  - Example: Using HTTP instead of HTTPS
  - Example: Very long domain names
  - **Action:** The PR can still merge, but consider updating the URL

- **❌ Unsafe** (blocked) - URL matches malicious patterns or is blocklisted
  - Example: Known phishing domain
  - Example: Executable files in URL
  - **Action:** PR will be blocked. Update the URL or remove it, then re-submit

### 📋 Sample Report

```
Total URLs checked: 1,018
  ✅ Safe:        1,017 (99.9%)
  ⚠️  Suspicious:  1 (0.1%)
  ❌ Unsafe:      0 (0%)

⚠️  SUSPICIOUS URL:
📄 resources.html
   http://example.com/resource
   - Uses HTTP (not HTTPS) - may be insecure
```

### 💡 Pro Tips for URL Safety

- **Always use HTTPS** when available
- **Use official sources** - Link to official documentation or GitHub repos
- **Avoid URL shorteners** - Use the full destination URL
- **Test the link** - Make sure it actually works before submitting

This automated check protects our 2,000+ community members from malicious links while keeping the contribution process smooth and transparent!

---

## 🤔 Need Help? Links to External Resources

Don't understand something? Here are links to helpful guides:

### GitHub Basics
- **What is GitHub?** → [GitHub's Getting Started Guide](https://docs.github.com/en/get-started)
- **How to fork a repo:** → [GitHub Fork Documentation](https://docs.github.com/en/get-started/quickstart/fork-a-repo)
- **How to make changes in GitHub's web editor:** → [GitHub Editing Files](https://docs.github.com/en/repositories/working-with-files/managing-files/editing-files)
- **What are pull requests?** → [GitHub Pull Request Guide](https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests)

### HTML Basics (If You're Curious)
- **What is HTML?** → [MDN: What is HTML?](https://developer.mozilla.org/en-US/docs/Web/HTML)
- **HTML Elements Explained:** → [W3Schools HTML Tutorial](https://www.w3schools.com/html/)

### Cloud Security Learning
- **New to cloud security?** → [Cloud Security Alliance Certification](https://cloudsecurityalliance.org/education/ccsk/)
- **AWS Security Fundamentals:** → [AWS Security Training](https://aws.amazon.com/training/security-training/)
- **Azure Security Learning Path:** → [Microsoft Azure Security Engineer](https://docs.microsoft.com/en-us/learn/certifications/azure-security-engineer)

---

## ✍️ Resource Categories & Examples

### 🎯 CTF Challenges & Vulnerable Environments
Intentionally broken cloud setups where you practice hacking.

**Examples:** CloudGoat, FLAWS, Kubernetes Goat, AWSGoat

**When to use this:** You found a vulnerable environment for learning hands-on

### 🧪 Hands-On Labs & Training Platforms
Interactive courses where you build and break things.

**Examples:** TryHackMe, HackTheBox, Cybr, Immersive Labs

**When to use this:** You found a training platform with interactive exercises

### 🛡️ Security Tools & Platforms
Software for scanning, protecting, or analyzing cloud infrastructure.

**Examples:** CloudMapper, Prowler, Wiz, Snyk

**When to use this:** You found a tool security teams actually use

### 🎓 Certifications & Professional Development
Official credentials that show you know cloud security.

**Examples:** AWS Security Specialty, Azure Security Engineer, CCSK

**When to use this:** You found a certification or bootcamp

### 🤖 AI Security Resources
Tools and training for securing AI/ML systems.

**Examples:** AI Security research papers, prompt injection testing tools

**When to use this:** You found something specifically about AI/ML security

### 💼 Job Search Resources
Places to find cloud security careers.

**Examples:** LinkedIn, CloudSecurityJobs.com, Indeed

**When to use this:** You found a job board or career resource

---

## 💡 Pro Tips

1. **Check if it already exists:** Search `resources.html` to make sure your resource isn't already there
2. **Write clear descriptions:** Pretend you're explaining this to a friend who's new to cloud security
3. **Tag appropriately:** Pick tags that help people find it (be specific!)
4. **Test your link:** Make sure the URL you're adding actually works
5. **Welcome feedback:** Maintainers might suggest improvements—that's normal!
6. **Start with one:** Add 1-2 resources first. You'll get the hang of it

---

## ❓ FAQ

**Q: Do I need to be a developer to contribute?**  
A: No! This guide is specifically designed for non-technical people. You just need to copy/paste and follow instructions.

**Q: What if I make a mistake?**  
A: No problem! That's why pull requests exist. You can edit your PR before it's merged, and maintainers can help fix issues.

**Q: How long until my resource is published?**  
A: Usually within a few days. Maintainers review every contribution.

**Q: Can I add multiple resources at once?**  
A: Yes! But start with one to get comfortable with the process.

**Q: What if the preview image doesn't show?**  
A: That's okay! The website will auto-generate a thumbnail. You can always improve it later.

**Q: Do I need to know YAML or JSON?**  
A: You don't need to understand them deeply. Just follow the copy/paste pattern. The syntax is pretty forgiving for our use case.

**Q: Can I use my own preview image?**  
A: Absolutely! Just follow Step 5. Custom images make resources look professional.

**Q: What makes a "good" resource?**  
A: Anything that helps cloud security professionals learn, practice, or advance their careers. Our community votes with their clicks!

---

## 🎉 You Did It!

Congratulations! By adding a resource, you're helping grow the cloud security community. Every contribution matters, no matter how small.

**Questions?** 
- Email us at admin@csoh.org or join a [Friday Zoom session](https://csoh.kit.com/39feb4f397)
- Open an issue on [GitHub](https://github.com/CloudSecurityOfficeHours/csoh.org)

**Ready to add your first resource?** Start with [Step 1](#step-1-gather-your-resource-info) above!

---

**Made with ❤️ by the Cloud Security Office Hours Community**
