# Sync Recap Recordings

Carry each recorded session's YouTube link and `VideoObject` JSON-LD from its
card on `presentations.html` onto its meeting recap in `meetings/`.

```bash
python3 tools/sync_recap_videos.py            # write
python3 tools/sync_recap_videos.py --check    # CI gate; self-tests first
```

## Why

A recorded talk is described on a card on `presentations.html`. Without this
tool a reader who lands on that session's recap has no route to the recording,
and the recap's JSON-LD describes an `Article` with no video in it.

## It writes two things, always together

1. A visible link under the quick-recap callout:

   ```html
   <p class="meeting-recording"><a class="card-action" href="https://www.youtube.com/watch?v=..."
      target="_blank" rel="noopener noreferrer">▶ Watch the presentation: <name></a></p>
   ```

2. A `VideoObject` JSON-LD block in `<head>`, under the marker
   `<!-- Structured Data - Session Recording (VideoObject) -->`.

**The pairing is the point, not a convenience.** Google's structured-data
policy asks that markup describe content the page actually shows, so a
`VideoObject` on a page with no visible video reference is not merely
redundant - it is the kind of mismatch that earns a manual action. Both are
written from the same parsed card in the same pass, so a page cannot carry one
without the other. That is also what `--check` asserts.

`.meeting-recording` carries **no CSS of its own**, deliberately. The styling
is all on the inner `.card-action`, which already has `[data-theme="dark"]`
rules, so this needed no stylesheet change and therefore no SRI re-stamp and no
`sync_dark_branch.py` run. The class is a generator hook: it is what the tool
matches on to replace its own output, and it is there if anyone later wants to
style the row.

## Source of truth

`presentations.html`'s **cards**, parsed by importing
`update_presentations_schema.py` - the same extractor that builds that page's
own schema, so there is one answer to "what talks exist" and one serializer for
the JSON. The two tools are *siblings reading the same markup, not a chain*:
this one never reads the block the other writes, so neither has to run first,
and a stale schema block on the presentations page cannot propagate into the
recaps.

Matching is by date. A card titled `September 18, 2026: ...` belongs to
`meetings/2026-09-18.html`. Cards whose date has no recap page (three today,
all non-Friday sessions) are **reported on every run**, not skipped silently.

## The owned region

On each recap the tool owns exactly two spans:

1. Everything between the quick-recap `</p>` and the
   `<div class="resource-tags meeting-tags">` that follows. That span is
   whitespace on every recap without a recording, which is what makes owning it
   outright safe: re-running cannot accumulate duplicates, and a card withdrawn
   from the presentations page loses its link here again. Markup in that span
   that the tool did not generate is replaced, with a **warning naming the
   page** - not discarded in silence.
2. The marker-delimited `<script type="application/ld+json">` block.

A recap missing either anchor **raises** rather than being skipped. A skipped
page and a page with nothing to do are indistinguishable in the output
otherwise.

## `@graph` even for a single video

Every block is a `@graph`, including pages with exactly one recording. Two talks could share a date one day, and a branch that has never
executed is a branch that does not work; one code path handles 1 and N. The
self-test exercises the N case in memory, so the path is covered rather than
merely present.

## The self-test is load-bearing

`--check` plants four known-bad states in memory and refuses to report a result
unless every detector fires:

| planted | must be |
|---|---|
| a page that should have a link, with the link stripped | restored |
| the same page with a corrupted video id in its schema | corrected |
| a page with no recording, given a link and schema | both removed |
| two recordings on one date | two links, two `VideoObject`s, and reversible |

The idempotency cases matter most: a regex bug that only shows on the second
run (for example a leading `\s*` in `REGION_RE`'s closing group, which would
make the region grow a blank line every run) passes a hand read and a single
run. If you add a detector, add its planted case, or the next silent breakage
looks exactly like a healthy repo.

## Where it runs

| where | as | why |
|---|---|---|
| `deploy.yml`, "Regenerate derived files" | fixer | the published artifact is self-consistent whatever the repo holds |
| `site-update-deploy.yml` | fixer, commits | before the meetings search index, which reads the recap bodies this edits |
| `validate-html.yml` | `--check` gate | a PR that forgets to run it fails |

Both `tools/sync_recap_videos.py` and `tools/update_presentations_schema.py`
are in `deploy.yml`'s and `validate-html.yml`'s `paths:` filters. Editing either
alone changes the published output with no `.html` in the commit, and without
those entries the change would not deploy on its own (see "Path filters must cover
everything `stage_site.sh` publishes" in [CLAUDE.md](../CLAUDE.md)).

## Adding a recording

Add the card to `presentations.html` as usual, then:

```bash
python3 tools/update_presentations_schema.py
python3 tools/sync_recap_videos.py
python3 tools/build_meetings_search_index.py
python3 tools/build_search_index.py
```

If the session has no recap page yet, the tool reports the date and does
nothing else; publish the recap with [`add_meeting.py`](ADD_MEETING_README.md)
and re-run.
