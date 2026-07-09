# 📰 Interactive News Source Submission Tool

An interactive Python script that helps contributors add new RSS/Atom feeds to CSOH's news automation.

## What It Does

This tool guides you through:

1. ✅ Collecting the source name and feed URL
2. 🔒 Validating URL safety
3. 🔍 Checking that the URL looks like an RSS/Atom feed
4. 📝 Updating `update_news.py` safely
5. 🌿 Creating a git branch and commit
6. 🚀 Providing push and PR instructions

## Requirements

- Python 3.6+
- Git repository (clean working directory)
- Internet access (to validate the feed)

## Usage

```bash
python3 tools/submit_news_source.py
```

## Example Session

```
$ python3 tools/submit_news_source.py

Source name (e.g., AWS Security Blog): Example Security Blog
Feed URL (RSS or Atom): https://example.com/feed.xml

Checking that the feed looks valid...
Updated update_news.py with the new feed.
Created branch: add-news-source-example-security-blog
Committed changes.

Next steps:
1. Push your branch: git push origin add-news-source-example-security-blog
2. Create a PR: https://github.com/CloudSecurityOfficeHours/csoh.org/pulls
3. Include source name and feed URL in the PR description
4. After your PR is merged, the unified workflow will automatically deploy the updated site.
```

Before adding the feed, the script refuses duplicates (a source name or feed URL already in `FEEDS`) and runs a URL-safety check, prompting you to proceed if it only raises warnings.

## Common Errors

- **`python3` not found**: Install Python from python.org and reopen your terminal
- **`git` not found**: Install Git from git-scm.com
- **Not in a git repo**: Run `cd csoh.org` before the script
- **Feed URL rejected**: Use the RSS/Atom feed URL (not the homepage)
- **Working directory not clean**: Commit or stash changes, then retry

## Notes

- The script does a lightweight RSS/Atom check. Some feeds are valid but may not be detected.
  If that happens, you can choose to proceed anyway.
- If you prefer manual edits, update the `FEEDS` list in `update_news.py` directly.

## See Also

- [Update News Automation](UPDATE_NEWS_README.md)
- [General Contributions](../CONTRIBUTING.md)
- [Contribute Page](../contribute.html)
