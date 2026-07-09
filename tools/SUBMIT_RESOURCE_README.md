# 🚀 Interactive Resource Submission Tool

An interactive Python script that makes it easy to submit new resources to CSOH.org with automatic URL validation and PR creation.

## What It Does

This tool guides you through the entire process of adding a resource:

1. ✅ **Collects all required information** - Interactive prompts for name, URL, description, tooltip, category, tags
2. 🔒 **Validates URL safety** - Automatic security checks using our URL safety validator
3. 🖼️ **Generates preview image (optional)** - Captures a screenshot if you choose (needs `generate_preview.py` plus Pillow/Playwright locally; if those aren't installed, the preview is deferred to GitHub Actions)
4. 📝 **Generates proper HTML** - Creates correctly formatted resource card
5. 🔧 **Inserts into correct section** - Automatically finds and updates the right category
6. 🌿 **Creates git branch** - Sets up a new branch for your changes
7. 💾 **Commits changes** - Commits with a descriptive message
8. 🚀 **Push and PR instructions** - Provides next steps for GitHub PR creation

## Requirements

- Python 3.6+
- Git repository (clean working directory)
- Write access to the repository

## Usage

### Basic Usage

```bash
python3 tools/submit_resource.py
```

Or if executable:

```bash
./tools/submit_resource.py
```

### Interactive Workflow

The script will guide you through these steps:

#### Step 1: Resource Information
```
Resource name: CloudGoat
```

#### Step 2: Resource URL
```
URL: https://github.com/RhinoSecurityLabs/cloudgoat

🔒 Validating URL security...
✅ URL is safe!
```

#### Step 3: Description
```
Description: Open-source AWS vulnerable-by-design environment for practicing
cloud security penetration testing and incident response.
```

#### Step 4: Extended Tooltip Description
```
Tooltip description (press Enter to skip):
CloudGoat deploys real AWS resources with intentional misconfigurations you
exploit using the AWS CLI and console. Scenarios cover IAM privilege
escalation, Lambda abuse, and S3 data exfiltration. Requires an AWS account
with admin access - all resources are cleaned up with a single destroy command.
```

#### Step 5: Category
```
Select the main category:
  1. CTF Challenges & Vulnerable Environments
  2. Hands-On Labs & Training Platforms
  3. Security Tools & Platforms
  4. Certifications & Professional Development
  5. AI Security Resources
  6. Job Search Resources

Your selection: 1
```

#### Step 6: Tags
```
Available Tags (select relevant ones):

  Platform Tags:
    1. AWS
    2. Azure
    3. GCP
    4. Kubernetes
    5. Multi-Cloud

  Resource Type Tags:
    6. CTF
    7. Labs & Training
    8. Tool
    ...

  Enter tag numbers separated by commas (e.g., 1,6,10)
  Recommended: 2-5 tags
  
  Your selection: 1,6,7
```

#### Step 7: Review
```
📋 Review Your Submission

Name:        CloudGoat
URL:         https://github.com/RhinoSecurityLabs/cloudgoat
Category:    CTF Challenges & Vulnerable Environments
Tags:        AWS, CTF, Labs & Training
Description: Open-source AWS vulnerable-by-design environment...

✅ Does this look correct? (y/n): y
```

#### Step 7.5: Preview Image (Optional)
```
🖼️  Generate preview image automatically? (y/n, default=y): y

🖼️  Generating Preview Image
This may take 10-30 seconds...
✅ Preview generated successfully
  Preview: img/previews/github.com-rhinosecuritylabs-cloudgoat.jpg
```

Note: For forked PRs, preview images are generated but may not be pushed back automatically.

#### Step 8: Generation and Insertion
```
📝 Generating and Inserting HTML
✅ Successfully updated resources.html!
```

#### Step 9: Git Operations
```
📝 Creating git branch: add-cloudgoat
✅ Created branch: add-cloudgoat
✅ Committed changes
```

#### Step 10: Push and PR
```
Your changes are ready! Here's what to do next:

1. Push your branch to GitHub:
   git push origin add-cloudgoat

2. Go to GitHub and create a Pull Request
3. Wait for automated URL safety check ✅
4. Maintainer will review and merge!

Would you like to push now? (y/n):
```


## Features

### 🔒 Automatic URL Safety Validation & Unified Workflow

Every URL is checked against:
- **Suspicious patterns** - Phishing indicators, URL shorteners, malware signatures
- **Security best practices** - HTTPS usage, domain legitimacy
- **Blocklists** - Known malicious domains
- **Whitelists** - Trusted sources (GitHub, AWS, Microsoft, etc.)

If a URL fails validation:
- ❌ **Errors** - Blocks submission (unsafe URL detected)
- ⚠️ **Warnings** - Prompts for confirmation (suspicious but not blocked)

After you open a pull request, the **unified workflow** will automatically:
- Validate all URLs for safety
- Generate preview images for new/changed resources
- Update SRI hashes and cache-busting tags if CSS/JS changed
- Deploy the site after merge

You do not need to run any SRI or preview scripts manually - just submit your resource and the workflow will handle the rest.

### 📋 Smart Category Selection

Choose from 6 main categories:
1. CTF Challenges & Vulnerable Environments
2. Hands-On Labs & Training Platforms
3. Security Tools & Platforms
4. Certifications & Professional Development
5. AI Security Resources
6. Job Search Resources

The script automatically inserts your resource in the correct HTML section.

### 🏷️ Comprehensive Tag System

Select from 20+ tags organized by:
- **Platform Tags** - AWS, Azure, GCP, Kubernetes, Multi-Cloud
- **Resource Type** - the script's exact tags are `CTF`, `Labs & Training`, `Tool`, `Certification`, `Job Search`
- **Security Focus** - Penetration Testing, DevSecOps, IAM, Compliance, AI Security
- **Other** - NEW 2026, Free, Paid, Open Source

### 🌿 Git Integration

Automatically:
- Checks for clean working directory
- Creates descriptive branch names (e.g., `add-cloudgoat`)
- Commits with clear messages
- Optionally pushes to remote
- Provides PR creation link

## Error Handling

### Git Repository Issues
```
❌ Not in a git repository
❌ Working directory has uncommitted changes
```
**Solution:** Navigate to the repo root and commit/stash changes first.

### URL Validation Failures
```
❌ URL validation failed:
   • Domain 'malicious-site.com' is on blocklist
```
**Solution:** Use a different, legitimate URL.

### Category Section Not Found
```
❌ Could not find section for category: CTF Challenges
```
**Solution:** The HTML structure may have changed. Add the resource manually or report the issue.

## Examples

### Example 1: Adding a CTF Challenge
```bash
$ python3 tools/submit_resource.py

Resource name: OWASP EKS Goat
URL: https://github.com/OWASP/www-project-eks-goat
Description: Intentionally vulnerable AWS EKS environment with 20+ 
             attack-defense labs for Kubernetes security training.
Category: 1 (CTF Challenges)
Tags: 1,4,6,7 (AWS, Kubernetes, CTF, Labs & Training)

✅ Created branch: add-owasp-eks-goat
✅ Committed changes
🚀 Pushed to GitHub
```

### Example 2: Adding a Security Tool
```bash
$ python3 tools/submit_resource.py

Resource name: Prowler
URL: https://github.com/prowler-cloud/prowler
Description: Multi-cloud security assessment tool for AWS, Azure, and GCP 
             with CIS benchmarks and compliance frameworks.
Category: 3 (Security Tools)
Tags: 1,2,3,8,15 (AWS, Azure, GCP, Tool, Compliance)

✅ Created branch: add-prowler
✅ Committed changes
```

## Contributing Features

Want to improve this tool? Consider adding:
- **GitHub API integration** - Automatically create PRs via API
- **Preview image handling** - Upload or generate preview images
- **Batch submission** - Add multiple resources at once
- **Template validation** - Check HTML structure before insertion
- **Duplicate detection** - Warn if similar resource exists


## Troubleshooting

### ImportError: No module named 'check_url_safety'
**Solution:** Run from repository root or ensure `tools/check_url_safety.py` exists.

### Permission Denied
**Solution:** Make script executable: `chmod +x tools/submit_resource.py`

### Git Push Fails
**Solution:** Ensure you have push access to the repository. You may need to fork first.

### URL Keeps Getting Flagged
**Solution:** 
- Ensure you're using HTTPS
- Use official documentation/GitHub URLs when possible
- Avoid URL shorteners
- Contact maintainers if you believe it's a false positive

### Preview or SRI not updated after PR
**Solution:**
- Check the Actions tab for the `site-update-deploy.yml` workflow run and resolve any errors.
- The workflow will handle preview and SRI updates automatically after your PR is opened or merged.

## See Also

- [How to Add a Resource (Manual)](../CONTRIBUTING_RESOURCES.md) - Web-based method
- [URL Safety Checker](CHECK_URL_SAFETY_README.md) - Details on URL validation
- [General Contributions](../CONTRIBUTING.md) - Other ways to contribute

---

**Made with ❤️ by the Cloud Security Office Hours Community**
