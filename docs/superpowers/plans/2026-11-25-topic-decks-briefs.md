# Topic slide decks: agent briefs

The drafter and reviewer briefs for `docs/superpowers/plans/2026-11-25-topic-decks.md`. Every deck's agents get the same text; only `SLUG` changes. The controller passes this file's path and the slug; it never pastes page text or outlines into a prompt.

## Shared rules (both agents)

- Work from the repository root. Touch only `tools/decks/topics/SLUG.deck`. Never edit an HTML page, and never run `tools/crosslink_pages.py` (it rewrites every page it reaches, and has no argument parsing).
- Read the page only through `python3 tools/build_topic_decks.py --extract SLUG` (add `--sections ID,ID` to narrow it). Never open the page's HTML and never open an image: a figure is chosen and described from its `[figure #id]` line, which carries its title, description and caption.
- The outline format, layouts and gate are in `tools/DECKS_README.md`: the "Topic decks" section, and the layout table under "Breach outline format" for each layout's typed lines.
- A slide and its notes say nothing their cited sections do not say. Keep every hedge, quantifier and attribution as the page writes it. Notes on a `figure` slide say only what the figure's title, description, caption and section say.
- On a page that carries "(disclosure: the site's author works at Wiz)", the first slide that shows Wiz carries it on the slide. No Wiz superlatives, and no ranking of third parties ("the best", "the leading").
- 15 to 30 slides counting the three generated slides; at most 40 words of prose per slide (25 on a `figure` slide), 14 per typed field, 12 per heading and 300 in the notes; notes on every slide.
- No U+2013 or U+2014 and no spaced hyphen used as a dash, anywhere in the outline. Rewrite with a comma, a period, a colon or parentheses.
- Plain voice. No "actually", "genuinely" or "highest-leverage"; no "not X. It is Y."; no stacks of verbless fragments.
- Gates, both to 0 findings: `python3 tools/build_topic_decks.py --check`, then `/Users/shawn/.pyenv/versions/3.10.0/bin/python3 tools/build_topic_decks.py --build SLUG`. A `LayoutError` names the slide to trim.
- Commit only the outline, by explicit path, never `git add -A`. No CI-skip token in the message. End it with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Never push. Never send the repository owner's email address anywhere.
- Do not spawn subagents.

## Drafter brief

You write the slide deck outline for the topic page `SLUG.html`.

1. Read the two README sections above and `python3 tools/build_topic_decks.py --extract SLUG`. Example outline: `tools/decks/topics/kubernetes.deck` once it exists. Until then, `tools/decks/breaches/vapor-panda-artex.deck` shows the syntax only (its stage layouts are not available to topic decks).
2. Write `tools/decks/topics/SLUG.deck`. The deck stands alone as a PDF without notes, and as a talk whose notes are the script. Follow the page's order. Cover what the page teaches, giving its central sections a slide or two and leaving out "Further reading", "Where next" and session cross-links. Pick the layout that fits the content: `compare` or `table` for comparisons, `checklist` for things to do, `list` for pitfalls and anti-patterns (dots, not tick boxes), `stats` for figures the page states, `layers` for stacked responsibilities, `figure` for the page's diagrams. Use at least one `figure` slide when the page has a figure, each figure at most once. Close with two `question` and `answer` pairs drawn from the page; a `question` slide's prose sets up the question and never repeats its heading. The `promise` restates the page's own summary in one sentence, hedged as the page hedges it.
3. Notes are what a presenter says: they expand the slide from the same sections, in full sentences. 300 words is a ceiling; most slides need far fewer.
4. Loop both gates to 0 findings. Commit with the message `decks: <topic name> outline`.
5. Reply with at most five lines: slug, slide count (with the generated three), figures used, gate status, and up to three doubts.

## Reviewer brief

You are a fresh fact reviewer for `tools/decks/topics/SLUG.deck`. You did not write it.

1. Read the outline, then only the sections it cites:

   ```bash
   python3 tools/build_topic_decks.py --extract SLUG --sections "$(sed -n 's/^section: //p' tools/decks/topics/SLUG.deck | tr '|' '\n' | tr -d ' ' | sort -u | paste -sd, -)"
   ```

   The output starts with the page's heading list, so you can also judge what the deck leaves out.
2. Check slide by slide and note by note, in this order:
   - A claim the cited sections do not make: a dropped hedge or quantifier, two claims merged into one, a number from the page used for a different claim, an attribution lost, notes that read more into a diagram than its caption and description say, advice stated without the caveat the page attaches to it.
   - The shared rules above.
   - Teaching: a slide that would mislead someone who never reads the page.
3. Fix every finding in place, minors included: the decks are public. Make all edits first, then rerun both gates to 0 findings. Do not plant test defects: the gate has its own tests. Commit with the message `decks: review <topic name> outline`.
4. Write your findings to `tools/decks/topics/build/SLUG-review.md` (ignored scratch): one line each, with severity (Important or Minor), the outline line, what was wrong and what you changed.
5. Reply with at most five lines: counts by severity, one line per Important finding, and anything you could not settle that Shawn must decide.
