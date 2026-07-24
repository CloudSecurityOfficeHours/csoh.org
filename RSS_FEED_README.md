# How to Use the CSOH Cloud Security News RSS Feed

## What Is RSS?

RSS (Really Simple Syndication) is a way to get updates from websites delivered straight to you - no need to keep checking the site manually. Think of it like subscribing to a newsletter, but instead of email, the updates go to a feed reader app of your choice.

## Our Feed URLs

CSOH publishes two feeds. Subscribe to either or both.

**Cloud security news:**

```
https://csoh.org/feed.xml
```

The latest cloud security news curated by Cloud Security Office Hours, covering AWS, Azure, GCP, Kubernetes vulnerabilities, breaches, and more. It updates automatically whenever new articles are added to our [news page](https://csoh.org/news.html).

**Weekly meeting recaps:**

```
https://csoh.org/recaps.xml
```

One item per Friday session: a topic-by-topic summary of what the community actually discussed, linking to the full recap on the site. Each item carries the session's topic tags (AI, Vulnerabilities, Supply Chain, and so on) as RSS categories, so you can filter in your reader. This is the lower-volume feed: roughly one item a week, versus several a day on the news feed.

Everything below applies to both feeds; substitute whichever URL you want.

## Getting Started (3 Steps)

### Step 1: Pick a Feed Reader

A feed reader is an app that collects and displays RSS feeds for you. Here are some popular free options:

| Reader | Platform | Link |
|--------|----------|------|
| **Feedly** | Web, iOS, Android | [feedly.com](https://feedly.com) |
| **Inoreader** | Web, iOS, Android | [inoreader.com](https://www.inoreader.com) |
| **NetNewsWire** | macOS, iOS | [netnewswire.com](https://netnewswire.com) |
| **Thunderbird** | Windows, macOS, Linux | [thunderbird.net](https://www.thunderbird.net) |
| **Newsblur** | Web, iOS, Android | [newsblur.com](https://newsblur.com) |

Don't overthink it - any of these will work. Feedly is the most beginner-friendly.

### Step 2: Add Our Feed

1. Open your feed reader.
2. Look for an **"Add Feed"**, **"Subscribe"**, or **"+"** button.
3. Paste in our feed URL:
   ```
   https://csoh.org/feed.xml
   ```
4. Confirm / click Subscribe.

That's it. New cloud security articles will now show up in your reader automatically.

### Step 3: Read Your Feed

Open your feed reader whenever you want to catch up. New articles appear in a simple list with the title, source, and a short summary. Click any article to read the full story on the original site.

## Quick-Start Examples by Platform

### macOS

**Option A - NetNewsWire (GUI, free & open-source):**

1. Install from the App Store or [netnewswire.com](https://netnewswire.com).
2. Open NetNewsWire → **File → New Web Feed** (or press ⌘N).
3. Paste the URL and click **Add**:
   ```
   https://csoh.org/feed.xml
   ```

**Option B - Terminal (curl + xmllint):**

```bash
# Fetch and preview the 5 latest headlines
curl -s https://csoh.org/feed.xml | xmllint --xpath '//item/title/text()' - 2>/dev/null | head -5
```

**Option C - Homebrew + newsboat (terminal reader):**

```bash
brew install newsboat
echo "https://csoh.org/feed.xml" >> ~/.newsboat/urls
newsboat
```

---

### Linux

**Option A - Newsboat (terminal reader, most distros):**

```bash
# Debian / Ubuntu
sudo apt install newsboat

# Fedora
sudo dnf install newsboat

# Arch
sudo pacman -S newsboat
```

Then add the feed and launch:

```bash
mkdir -p ~/.newsboat
echo "https://csoh.org/feed.xml" >> ~/.newsboat/urls
newsboat
```

Use arrow keys to navigate, Enter to open an article, and `q` to quit.

**Option B - Liferea (GUI reader):**

```bash
sudo apt install liferea   # Debian / Ubuntu
```

Open Liferea → **Subscriptions → New Subscription** → paste `https://csoh.org/feed.xml`.

**Option C - Terminal one-liner (curl + xmlstarlet):**

```bash
# Print the 5 latest headlines
curl -s https://csoh.org/feed.xml | xmlstarlet sel -t -v '//item/title' -n | head -5
```

---

### Windows

**Option A - Thunderbird (GUI, free):**

1. Download from [thunderbird.net](https://www.thunderbird.net) and install.
2. Open Thunderbird → **File → Subscribe** (or right-click **Feeds** → **Subscribe**).
3. Paste the feed URL and click **Add**:
   ```
   https://csoh.org/feed.xml
   ```

**Option B - PowerShell (built-in, no install needed):**

```powershell
# Fetch and display the 5 latest headlines
[xml]$feed = (Invoke-WebRequest -Uri "https://csoh.org/feed.xml").Content
$feed.rss.channel.item | Select-Object -First 5 title, link | Format-Table -AutoSize
```

**Option C - Windows Terminal + newsboat (via WSL):**

```powershell
# First, install WSL if you haven't (run as Administrator):
wsl --install

# Then inside WSL (Ubuntu):
sudo apt install newsboat
mkdir -p ~/.newsboat
echo "https://csoh.org/feed.xml" >> ~/.newsboat/urls
newsboat
```

---

## FAQ

### How often does the feed update?
The feed updates whenever new articles are added to the CSOH news page. This is typically daily on weekdays.

### Is the feed free?
Yes, completely free. You don't need an account on our site.

### Can I use RSS in Slack or Teams?
Yes! Both Slack and Microsoft Teams support RSS:

- **Slack**: Use the `/feed subscribe https://csoh.org/feed.xml` command in any channel (requires the RSS app to be installed in your workspace).
- **Microsoft Teams**: Add the "RSS" connector to a channel and paste the feed URL.

### Can I use RSS with email?
Services like [Blogtrottr](https://blogtrottr.com) or [IFTTT](https://ifttt.com) can send RSS updates to your inbox if you prefer email over a dedicated reader.

### What if my browser opens the feed as raw XML?
That's normal - feed URLs are meant to be opened in a feed reader, not a browser. Just copy the URL and paste it into your reader app instead.

## About Cloud Security Office Hours

[Cloud Security Office Hours](https://csoh.org) is a vendor-neutral community of 2000+ cloud security professionals. We meet weekly on Zoom and maintain a curated collection of 240+ security resources, 120+ news articles, and 554+ community-shared URLs. Join us at [csoh.org](https://csoh.org).
