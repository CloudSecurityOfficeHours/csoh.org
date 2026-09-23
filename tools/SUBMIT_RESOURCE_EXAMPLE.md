## Example Interactive Session

Here's what a complete session looks like:

```
$ python3 tools/submit_resource.py

======================================================================
  🚀 CSOH Resource Submission Tool
======================================================================

This tool will help you add a new resource to CSOH.org
It will:
  ✅ Validate your URL for security
  ✅ Generate the proper HTML
  ✅ Create a git branch and commit
  ✅ Provide instructions for creating a PR

======================================================================

🔍 Checking git repository status...
✅ Git repository is clean

──────────────────────────────────────────────────────────────────────
  Step 1: Resource Information
──────────────────────────────────────────────────────────────────────

Resource name (e.g., 'CloudGoat', 'OWASP EKS Goat'): Prowler

──────────────────────────────────────────────────────────────────────
  Step 2: Resource URL
──────────────────────────────────────────────────────────────────────

Enter the full URL for this resource
URL (must start with http:// or https://): https://github.com/prowler-cloud/prowler

🔒 Validating URL security...
✅ URL is safe!

──────────────────────────────────────────────────────────────────────
  Step 3: Description
──────────────────────────────────────────────────────────────────────

Write a brief description (1-2 sentences)
Explain what it is and why it's useful for cloud security professionals
Description: Multi-cloud security assessment tool that performs CIS benchmarks and compliance checks across AWS, Azure, and GCP with 400+ security controls.

──────────────────────────────────────────────────────────────────────
  Step 4: Category
──────────────────────────────────────────────────────────────────────

Select the main category for this resource:
  1. CTF Challenges & Vulnerable Environments
  2. Hands-On Labs & Training Platforms
  3. Security Tools & Platforms
  4. Certifications & Professional Development
  5. AI Security & LLM Protection
  6. Job Search & Career Development
  7. Cloud Security Newsletters
  Your selection: 3

──────────────────────────────────────────────────────────────────────
  Step 5: Tags
──────────────────────────────────────────────────────────────────────

📋 Available Tags (select relevant ones):

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
    9. Certification
    10. Job Search

  Security Focus Tags:
    11. Vulnerability Testing
    12. Penetration Testing
    13. Cloud Scanning
    14. Secrets Management
    15. Compliance
    16. AI Security
    17. IAM
    18. DevSecOps

  Other Tags:
    19. NEW 2025
    20. Free
    21. Paid
    22. Open Source

  Enter tag numbers separated by commas (e.g., 1,6,10)
  Recommended: 2-5 tags
  Your selection: 1,2,3,5,8,13,15,22

──────────────────────────────────────────────────────────────────────
  📋 Review Your Submission
──────────────────────────────────────────────────────────────────────

Name:        Prowler
URL:         https://github.com/prowler-cloud/prowler
Category:    Security Tools & Platforms
Tags:        AWS, Azure, GCP, Multi-Cloud, Tool, Cloud Scanning, Compliance, Open Source
Description: Multi-cloud security assessment tool that performs CIS benchmarks and compliance checks across AWS, Azure, and GCP with 400+ security controls.

✅ Does this look correct? (y/n): y

──────────────────────────────────────────────────────────────────────
  Step 6: Generating and Inserting HTML
──────────────────────────────────────────────────────────────────────

Generated HTML:
    <a href="https://github.com/prowler-cloud/prowler" target="_blank" class="card-link" rel="noopener noreferrer">
        <div class="resource-card">
            <h3>Prowler</h3>
            <p>Multi-cloud security assessment tool that performs CIS benchmarks and compliance checks across AWS, Azure, and GCP with 400+ security controls.</p>
            <div class="resource-tags">
                <span class="tag">AWS</span>
                <span class="tag">Azure</span>
                <span class="tag">GCP</span>
                <span class="tag">Multi-Cloud</span>
                <span class="tag">Tool</span>
                <span class="tag">Cloud Scanning</span>
                <span class="tag">Compliance</span>
                <span class="tag">Open Source</span>
            </div>
        </div>
    </a>

📝 Reading resources-security-tools.html...
💾 Writing updated resources-security-tools.html...
🔧 Stamping the card id and refreshing counts...
✅ Successfully updated resources-security-tools.html!

──────────────────────────────────────────────────────────────────────
  Step 7: Creating Git Branch and Commit
──────────────────────────────────────────────────────────────────────

📝 Creating git branch: add-prowler
✅ Created branch: add-prowler
✅ Committed changes

──────────────────────────────────────────────────────────────────────
  Step 8: Next Steps - Create Pull Request
──────────────────────────────────────────────────────────────────────

Your changes are ready! Here's what to do next:

1. Push your branch to GitHub:
   git push origin add-prowler

2. Go to GitHub and create a Pull Request:
   https://github.com/CloudSecurityOfficeHours/csoh.org/pulls

3. In your PR description, include:
   Resource: Prowler
   URL: https://github.com/prowler-cloud/prowler
   Category: Security Tools & Platforms
   
   Multi-cloud security assessment tool that performs CIS benchmarks and compliance checks across AWS, Azure, and GCP with 400+ security controls.

4. Wait for the automated URL safety check to complete ✅
5. A maintainer will review and merge your PR!

Would you like to push now? (y/n): y

🚀 Pushing to origin/add-prowler...
✅ Successfully pushed!

🌐 Create your PR here:
   https://github.com/CloudSecurityOfficeHours/csoh.org/compare/add-prowler?expand=1

======================================================================
  ✨ Submission Complete!
======================================================================

Thank you for contributing to CSOH! 🙏
Your submission will help cloud security professionals worldwide.
```

## Key Features Demonstrated

- ✅ **Clean UI** with formatted sections and emoji
- ✅ **URL validation** integrated seamlessly
- ✅ **Smart defaults** - multi-select tags, category selection
- ✅ **Review before commit** - see everything before it's saved
- ✅ **Generated HTML preview** - verify the output
- ✅ **Git automation** - branch creation, commit, and push
- ✅ **Direct PR link** - one-click to create the pull request
