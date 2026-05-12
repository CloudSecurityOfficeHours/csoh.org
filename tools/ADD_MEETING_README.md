# Add Meeting Recap Tool

Publish a new CSOH meeting recap from a saved Apple Notes note.

## Quick Start

```bash
python3 tools/add_meeting.py path/to/note.html
```

The script:

1. Parses the note (HTML export from Apple Notes, or markdown/plain text).
2. Finds the meeting date in the `CSOH YYYY-MM-DD` title.
3. Writes a standalone `meetings/YYYY-MM-DD.html` page using the previously-newest meeting page as the template (so CSS/JS hash bumps and other cross-cutting tweaks carry through automatically).
4. Inserts a card at the top of `meetings.html`, renumbers the ItemList JSON-LD, and refreshes count copy.
5. Patches the previously-newest meeting page's pager to add a "Newer meeting →" link to the new page.
6. Adds a `<url>` entry to `sitemap.xml` and a record to `meetings-search-index.json`.
7. Fixes broken entities common in Apple Notes exports (`&quot` → `"`, `&amp` → `&`).

Re-running with the same date is idempotent — the existing page is replaced in place.

## Workflow from an Apple Notes note

1. **In Claude Code**, ask me to dump the note:
   ```
   Fetch the Apple Notes note "CSOH 2026-04-24" and save the raw HTML to /tmp/csoh-2026-04-24.html
   ```
   I'll use the Apple Notes MCP and write the result to a file.
2. **Run the tool**:
   ```bash
   python3 tools/add_meeting.py /tmp/csoh-2026-04-24.html
   ```
3. **Review the diff**, commit, push. The deploy workflow will refresh `sitemap.xml` for `meetings.html` automatically.

If you don't have the MCP set up locally, you can also copy/paste the note contents into a plain text file and feed that to the script — see "Input formats" below.

## Input formats

The script accepts two formats and auto-detects:

### Apple Notes HTML export

Looks like this (raw output from the Apple Notes MCP `get_note_content` tool):

```html
<div><h1>CSOH 2026-04-24</h1></div>
<div><b><h2>Quick recap</h2></b></div>
<div>Meeting focused on X. Participants discussed Y and Z. …</div>
<div><b><h2>Topic heading one</h2></b></div>
<div>Body paragraph.</div>
<div><b><h2>Topic heading two</h2></b></div>
<div>Body paragraph.</div>
```

### Markdown / plain text

```markdown
# CSOH 2026-04-24

## Quick recap

Meeting focused on X. Participants discussed Y and Z. …

## Topic heading one

Body paragraph.

## Topic heading two

Body paragraph.
```

## Flags

- `--headline "Short headline"` — override the TOC entry's short headline. Default is the first topic heading.
- `--tag "Foo"` — topical tag for the filter bar (repeatable). Example: `--tag AI --tag Conferences --tag "Supply Chain"`. A month tag (`YYYY-MM`) is always added automatically from the meeting date.
- `--meetings-file path/to/meetings.html` — operate on a different file (useful for testing).

### Tag conventions

Tags appear as filter buttons on `meetings.html`. Keep them short, Title Case, and reuse existing ones when possible so the filter bar stays tidy. Tags currently in use:

`AI`, `Anniversary`, `Community`, `Conferences`, `Education`, `GitHub Actions`, `Governance`, `Guest Speaker`, `Industry News`, `Insider Threats`, `Passwords`, `SBOM`, `Supply Chain`, `Vulnerabilities`.

Add new ones sparingly — each one creates a new filter button.

## Expected structure

The note must contain:

- An `<h1>` (or `# ...`) with the exact pattern `CSOH YYYY-MM-DD` somewhere.
- An `<h2>` (or `## ...`) titled **Quick recap** followed by the recap paragraph.
- One or more `<h2>` subsections, each followed by a paragraph.

An empty `<h2>Summary</h2>` placeholder (as produced by some Apple Notes transcription tools) is ignored.

## What doesn't happen automatically

- **Commits and pushes.** Stage and commit the changes yourself — the script never touches git. Affected files: `meetings/YYYY-MM-DD.html` (new), `meetings.html`, `meetings-search-index.json`, `sitemap.xml`, and the previously-newest meeting page (its pager is patched).
- **Removing meetings.** To remove a stale meeting, delete `meetings/YYYY-MM-DD.html`, the matching card in `meetings.html`, the search-index record, and the sitemap entry. Fix the pager on neighboring meeting pages by hand.
- **Renaming/redating.** If you got the date wrong, delete the old page and re-run the tool with the corrected note.

## Requirements

- Python 3.9+ (standard library only)
- Run from the repo root or anywhere — the script resolves `meetings.html` relative to its own location.
