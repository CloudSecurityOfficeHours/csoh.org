# 🔗 Meeting → Topic Page Link Injector

Wraps the first occurrence of cloud-security topic keywords in each meeting recap with a link to the matching topic page (e.g. `disaster recovery` → `../backup-dr.html`).

Used to give each meeting recap 2-3 contextual internal links to topic pages - improves both reader navigation and internal-link equity flowing into the pillar/topic pages.

## How it works

For each `meetings/YYYY-MM-DD.html`:

1. Find the `<article class="section meeting-page">` … `</article>` body (skips nav, footer, etc.).
2. Iterate the `TOPIC_KEYWORDS` mapping (≈80 phrases → 30 topic pages, ordered by specificity).
3. For each topic, find the first occurrence of any of its keywords that is **not** already inside an `<a>` tag and **not** inside any HTML tag.
4. Wrap that span in `<a href="../<topic>.html">…</a>`.
5. Stop at 3 inserts per meeting (avoids over-linking).
6. One link per topic page per meeting (no duplicates).

Generic single-token terms (`AWS`, `IAM`, `S3`, etc.) are denylisted to avoid weak / spammy matches.

## Usage

```bash
# Dry-run across all 94 meetings - prints what would change, writes nothing
python3 tools/inject_meeting_topic_links.py --dry-run

# Apply across all 94 meetings
python3 tools/inject_meeting_topic_links.py

# Apply to specific meetings
python3 tools/inject_meeting_topic_links.py --pages meetings/2026-05-08.html
```

Idempotent in practice - re-running finds the same first-occurrences already inside `<a>` tags and skips them.

## Tuning

Edit the `TOPIC_KEYWORDS` list in the script to add new phrases or new topic pages. Earlier rows win when multiple topics match the same keyword. `MAX_LINKS_PER_MEETING` caps inserts per file. `DENYLIST` blocks specific tokens entirely.

## When to run

- After a batch of new meetings is added.
- After topic-page reorganization (e.g. you split or renamed a topic page).
- After updating `TOPIC_KEYWORDS` if you want previously-skipped meetings to get a second pass.
