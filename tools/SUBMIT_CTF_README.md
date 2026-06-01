# 🎯 Interactive CTF Submission Tool

Interactive script for adding a new CTF challenge to [ctfs.html](../ctfs.html).

## What It Does

1. ✅ Collects CTF name, URL, description, tooltip, section, tags
2. 🔒 Validates URL safety (via `check_url_safety.py`)
3. 📝 Generates a card in the exact format used on `ctfs.html`
4. 🎯 Inserts it into the right section (`aws-ctfs`, `kubernetes-ctfs`, etc.)
5. 🖼️ Optionally generates a preview screenshot (via `generate_preview.py`)
6. 🌿 Creates a git branch and commits the change
7. 🚀 Offers to push and gives you the PR URL

## Requirements

- Python 3.6+
- Clean git working directory
- Optional: `playwright` + `Pillow` for local preview generation
  ```bash
  pip install playwright Pillow
  playwright install chromium
  ```

## Usage

```bash
python3 tools/submit_ctf.py
```

You'll be prompted through each step. Here's a minimal example session:

```
🎯 CSOH CTF Submission Tool
✅ Git repository is clean

Step 1: CTF Name
CTF name: EntraGoat

Step 2: URL
Challenge URL: https://github.com/Semperis/EntraGoat
🔒 Validating URL...
✅ URL is safe

Step 3: Short Description
Description: Six vulnerable Entra ID attack-path scenarios with solutions.

Step 4: Tooltip Description (Optional)
Tooltip: From Semperis. Deploys a vulnerable Entra ID environment via PowerShell + Node.js UI.

Step 5: Section Placement
  1. Wiz Standalone Challenges (always-available)
  2. AWS CTFs
  3. Azure CTFs
  4. GCP CTFs
  5. Kubernetes CTFs
  6. Multi-Cloud CTFs
  7. AI, Secrets, and CI/CD CTFs
Your selection: 3

Step 6: Tags
  1. AWS   2. Azure   3. GCP   4. Kubernetes   5. Multi-Cloud
  6. IAM   7. Containers   8. Serverless   ...
Your selection: 2,6

📋 Review
Name:        EntraGoat
URL:         https://github.com/Semperis/EntraGoat
Section:     Azure CTFs
Tags:        CTF, Azure, IAM
...

✅ Looks correct? (y/n): y
🖼️  Generate preview image locally? (y/n, default=y): y
...

✅ Updated ctfs.html
✅ Committed on branch: add-ctf-entragoat

Push now? (y/n): y
✅ Pushed.
   https://github.com/CloudSecurityOfficeHours/csoh.org/compare/add-ctf-entragoat?expand=1
```

## Sections

| # | Section | For |
|---|---|---|
| 1 | `wiz-standalone` | Always-available Wiz CTFs |
| 2 | `aws-ctfs` | AWS-focused (IAM, S3, Lambda, etc.) |
| 3 | `azure-ctfs` | Azure / Entra ID |
| 4 | `gcp-ctfs` | GCP |
| 5 | `kubernetes-ctfs` | Kubernetes (any cloud) |
| 6 | `multi-cloud-ctfs` | AWS + Azure + GCP in one |
| 7 | `specialty-ctfs` | AI/ML, Secrets, CI/CD |

The monthly `wiz-championship` section is intentionally excluded from the script - those are edited directly as part of the calendar.

## Tags

- `CTF` - always included automatically as the first tag
- Cloud tags: `AWS`, `Azure`, `GCP`, `Kubernetes`, `Multi-Cloud`
- Focus tags: `IAM`, `Containers`, `Serverless`, `Recon`, `Incident Response`, `Reverse Engineering`, `IaC`, `Secrets Management`, `CI/CD`, `AI/ML`, `Cloud Security`

Pick 1-3 tags beyond `CTF`.

## See Also

- [CONTRIBUTING_CTFS.md](../CONTRIBUTING_CTFS.md) - full contribution guide
- [SUBMIT_RESOURCE_README.md](SUBMIT_RESOURCE_README.md) - sibling tool for general resources
- [GENERATE_PREVIEW_README.md](GENERATE_PREVIEW_README.md) - how preview images are generated
