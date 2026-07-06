# Update News Automation

## How Does the News Page Stay Up to Date?

The [News page](https://csoh.org/news.html) is updated **automatically every 3 hours** - no one has to manually add articles. The script also generates an **RSS feed** (`feed.xml`) so subscribers get updates automatically. Here's how it works in plain English:

1. **GitHub Actions** (a free automation service built into GitHub) runs a Python script on a schedule - every 3 hours.
2. The script visits **39 cloud security news sources** and checks for new articles using something called **RSS feeds**. An RSS feed is like a news wire - it's a machine-readable list of recent articles that a website publishes so other tools can easily pull in headlines, dates, and summaries.
3. The script filters those articles for **cloud security topics** (looking for keywords like "AWS", "Azure", "Kubernetes", "vulnerability", "breach", etc.) and throws out duplicates.
4. **Existing cards on `news.html` are preserved across runs.** RSS feeds are rolling windows, so today-dated articles from earlier runs would otherwise get dropped when feeds rotate. The script parses the current `news.html`, then merges in whatever new items this run's feeds surfaced, sorted by date and capped at 120 articles.
5. If after that merge fewer than **10 today-dated articles** are on the page, the script tops up from a **relaxed-filter pool** - today-dated items from the same security feeds that didn't hit the strict keyword filter. The target is tunable with `--today-target`.
6. It then writes fresh article cards to `news.html` (title, date, summary, source, link), regenerates `feed.xml` (the RSS feed), rebuilds the `NewsArticle` JSON-LD block on `news.html` from the top 20 articles, and refreshes `<lastmod>` dates in `sitemap.xml`.
7. Instead of pushing changes directly, it **creates a Pull Request** (a proposed change) so a maintainer can review it before it goes live.
8. If the only files changed are `news.html`, `feed.xml`, and `sitemap.xml`, the PR is **automatically merged** - no human review needed for routine news updates.
9. Once merged, the **unified site-update-deploy.yml workflow** automatically uploads the updated site to the web server via FTP.

**The end result:** the News page always has fresh, relevant cloud security articles without anyone lifting a finger.

---

## News Sources (39 feeds)

The script pulls from these trusted, non-paywalled sources:

### General Security News

| Source | What It Covers |
|--------|---------------|
| AWS Security Blog | Official AWS security announcements |
| Google Cloud Blog | Google Cloud identity & security updates |
| Google Online Security Blog | Google-wide security research |
| Microsoft MSRC | Microsoft Security Response Center advisories |
| Cloudflare Blog | Web security, DDoS, zero trust |
| SANS ISC | Internet Storm Center threat intelligence |
| BleepingComputer | Malware, vulnerabilities, data breaches |
| The Hacker News | Cybersecurity news and analysis |
| SecurityWeek | Enterprise security news |
| KrebsOnSecurity | Investigative cybersecurity journalism |
| Dark Reading | Enterprise security research |
| Help Net Security | Security news and expert insights |
| Infosecurity Magazine | Industry news and analysis |
| Security Affairs | Cyber crime and hacking news |
| Schneier on Security | Security commentary by Bruce Schneier |
| The Register - Security | IT security news |
| The Register - Cloud | Cloud infrastructure news |
| CISA Alerts | US government cybersecurity alerts |
| CISA Current Activity | Active threats and exploits |
| CISA Bulletins | Weekly vulnerability summaries |

### Cloud Security Research

| Source | What It Covers |
|--------|---------------|
| Wiz Blog | Cloud vulnerability research and misconfiguration deep-dives |
| Orca Security Blog | Cloud vulnerabilities, lateral movement, secret exposure |
| Aqua Security Blog | Container and Kubernetes security, cloud-native threats |
| Sysdig Blog | Runtime threat detection, Kubernetes security |
| Datadog Security Labs | Cloud infrastructure threats, supply chain attacks |

### Threat Intelligence / Research

| Source | What It Covers |
|--------|---------------|
| CrowdStrike Blog | Threat intelligence and research |
| Palo Alto Networks Unit 42 | Threat research and analysis |
| Google Threat Intelligence | APT campaigns, nation-state actors (Mandiant) |
| Cisco Talos | Malware analysis, vulnerability disclosures |
| SentinelLabs | Malware reversing, APT tracking |
| Elastic Security Labs | Detection engineering, rootkit analysis |
| FortiGuard Labs | Zero-day disclosures, active exploitation alerts |

Want to **add a new source**? You have two options:

1. Run `python3 tools/submit_news_source.py` (interactive, recommended)
2. Or edit the `FEEDS` list at the top of `update_news.py` manually (this script lives at the repo ROOT, not in `tools/`; helper scripts like `submit_news_source.py` are in `tools/`). See the `FEEDS` list for the full current set of sources.

**Script guide:** [SUBMIT_NEWS_SOURCE_README.md](SUBMIT_NEWS_SOURCE_README.md)

### Common Errors (Submit Script)

- **`python3` not found**: Install Python from python.org and reopen your terminal
- **`git` not found**: Install Git from git-scm.com
- **Not in a git repo**: Run `cd csoh.org` before the script
- **Feed URL rejected**: Use the RSS/Atom feed URL (not the homepage)
- **Working directory not clean**: Commit or stash changes, then retry

---

## How the GitHub Actions Workflow Works

The workflow is defined in `.github/workflows/update-news.yml`. Here's what happens step by step:

```
Schedule (every 3 hours) or manual trigger
        |
        v
  Check out the latest code from the repo
        |
        v
  Run update_news.py (fetch feeds, filter, update news.html + feed.xml)
        |
        v
  Any changes?
   /         \
  No          Yes
  |            |
  Done    Create a Pull Request
              |
              v
         Only news.html + feed.xml + sitemap.xml changed?
          /         \
        Yes          No
         |            |
     Auto-merge    Wait for
     (squash)      human review
         |
         v
      Unified workflow uploads to web server
```

### Triggers

- **Scheduled:** Runs automatically every 3 hours (`0 */3 * * *` in cron syntax)
- **Manual:** You can trigger it anytime from the GitHub Actions tab (click "Run workflow")
- **On push:** Runs when `update_news.py` itself is modified and pushed to main

---

## Running Manually (for developers)

You don't need GitHub Actions to run the script. If you have Python 3.9+ installed:

```bash
python3 update_news.py
```

Optional arguments:

```bash
python3 update_news.py \
  --news-file news.html \
  --resources-file resources.html \
  --max-articles 120 \
  --min-sources 10 \
  --today-target 10
```

`--today-target` sets the minimum number of today-dated entries the page should hold. If the strict keyword filter plus preserved cards don't hit this number, the script tops up from today-dated items on the same security feeds that narrowly missed the strict filter. Set to `0` to disable the top-up.

### Requirements

- Python 3.9+ (standard library only - no `pip install` needed)
- Internet access (to fetch RSS feeds)

---

## Duplicate Handling & Card Preservation

The script avoids posting the same article twice by comparing normalized URLs against:

- Existing entries already in `news.html` (these are also preserved, see below)
- Any URLs in `resources.html` (so news doesn't duplicate a curated resource)

**Preservation logic.** Each run parses the cards already on `news.html` and carries them forward. New feed items are layered on top, the combined set is sorted by date (newest first), and the result is capped at `--max-articles`. This means:

- Today-dated articles surfaced in a morning run are still on the page after an afternoon run, even if the source feeds have since rotated them off.
- Over a typical day, the today count grows as each run adds the freshest items and preserves the earlier ones.
- The strict keyword filter only applies to new items. Preserved cards stay regardless - they were accepted when first added.

## Today-Target Top-Up

If preservation + new strict-filter items still leave fewer than `--today-target` today-dated entries (default 10), the script fills the gap from a **relaxed-filter pool**: today-dated items pulled from our security-focused feeds that didn't happen to contain a strict keyword. This trades a little precision for freshness on quiet publishing days (weekends, holidays).

When this runs, workflow logs show a line like:

```
Selected 120 entries (10 from today, 120 preserved, 3 new from feeds, 2 relaxed-filter today top-ups).
```

If the page still falls short of the target after the top-up, the script prints a warning but does not fabricate entries.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| Workflow fails at "Mint installation token" | App private key revoked / expired / `CSOH_CI_PRIVATE_KEY` secret missing | Generate a new private key in the `csoh-ci` GitHub App settings and replace the `CSOH_CI_PRIVATE_KEY` org secret |
| Workflow fails at "Auto approve" with HTTP 401 | `CSOH_PAT` expired or revoked | Regenerate the fine-grained PAT (see Setup Requirements below) and replace the `CSOH_PAT` org secret |
| Script exits with "fewer than 10 sources" | Too many feeds are down or unreachable | Usually temporary - wait for the next scheduled run |
| No PR created | No new articles found since last run | Normal - means news is already up to date |
| PR not auto-merging | Files other than `news.html` and `feed.xml` changed | Review the PR manually - the script may have been updated |
| Site not deployed after merge | Unified workflow failed or was skipped | Check Actions tab for site-update-deploy.yml run and resolve any errors |

---

## Setup Requirements

The workflow authenticates to GitHub via two credentials, both stored as **organization-level** Actions secrets (under https://github.com/organizations/CloudSecurityOfficeHours/settings/secrets/actions):

1. **`csoh-ci` GitHub App** - used for opening the PR, pushing commits, and enabling auto-merge. Stored as two secrets:
   - `CSOH_CI_CLIENT_ID` - the App's Client ID (`Iv23.*`)
   - `CSOH_CI_PRIVATE_KEY` - the App's RSA private key (PEM, multi-line)

   The App is on the main-branch ruleset bypass list so its direct pushes (from `site-update-deploy.yml`) are accepted, and it has `contents: read+write` and `pull-requests: read+write` permissions scoped to this repo only. Tokens minted from the App are short-lived (~1h) and rotate automatically.

2. **`CSOH_PAT` fine-grained Personal Access Token** - used only to approve PRs the App opened. GitHub blocks self-approval, and empirically GitHub's auto-merge feature does not consult the App's ruleset bypass when checking the approval requirement, so a second-identity PAT is required to drive auto-merge to completion.

   To rotate `CSOH_PAT`:

   1. Go to https://github.com/settings/personal-access-tokens/new (signed in as a maintainer).
   2. **Resource owner:** `CloudSecurityOfficeHours` (the org, not your personal account).
   3. **Expiration:** 1 year max; shorter is fine.
   4. **Repository access:** Only select repositories → `csoh.org`.
   5. **Repository permissions:** **Pull requests: Read and write**. Leave everything else at "No access."
   6. Generate, approve via the org PAT-approval flow if prompted, copy the `github_pat_*` value.
   7. Replace the `CSOH_PAT` org-level Actions secret with the new value.

For the full authentication model and rationale, see [SECURITY.md → CI/CD Authentication](../SECURITY.md#cicd-authentication).
