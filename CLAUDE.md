# CLAUDE.md

Notes for anyone (human or agent) working in this repo: the rules that are not
obvious from the code, why they hold, and how to check them.

Two habits run through all of it:

- **Run a control before believing a clean result.** A check that cannot see
  the thing it looks for reports zero, and zero looks like health. Plant a known
  defect, confirm it is reported, then restore.
- **Numbers and machine state in this file are not facts.** Counts, dates and
  "is currently applied" statements drift. Re-derive them with the command
  given rather than citing them.

---

## Commits and deploys

### Never put a CI-skip token in a commit message

GitHub skips **every** workflow on a push when the head commit's message
contains any of these:

```
[skip ci]  [ci skip]  [no ci]  [skip actions]  [actions skip]
```

It scans the whole message, subject and body, and ignores backticks and quotes,
so describing a token is enough to trigger it. Nothing fails and no run
appears; the change just sits in `main` unpublished. To write about them, say
"a CI-skip marker" or "the skip-ci token". The strings are harmless in files.

The housekeeping workflow (`site-update-deploy.yml`) uses these tokens on
purpose so its own commits don't loop. Anything it fixes lands in `main` but
does not reach production until the next real deploy, so never rely on it to
repair a live problem.

### Path filters must cover everything `stage_site.sh` publishes

`deploy.yml` and `site-update-deploy.yml` deploy only when a push touches a
file matched by their `paths:` filters. A published file no pattern matches
cannot deploy on its own, and the push looks fine.

- GitHub's `*` does not match `/`. Use `'**.html'`, never `'*.html'`.
- Root-level assets need their own entries: `favicon.png`, `banner.png`,
  `banner.webp`, `apple-touch-icon*.png` are not under `img/**`.
- The filters are explicit allow-lists of filenames. A new CSS/JS asset must be
  added to both.

Diff the published set against the patterns rather than reading them:

```sh
./tools/stage_site.sh /tmp/dist
python3 - /tmp/dist <<'PY'
import re, pathlib, sys, yaml
wf = yaml.safe_load(pathlib.Path('.github/workflows/deploy.yml').read_text())
pats = wf[True]['push']['paths']    # YAML parses a bare `on:` key as True
rx = [re.compile('^' + p.replace('**', '\x00').replace('*', '[^/]*')
                 .replace('\x00', '.*') + '$') for p in pats]
dist = pathlib.Path(sys.argv[1])
missed = sorted(str(f.relative_to(dist)) for f in dist.rglob('*')
                if f.is_file() and not any(r.match(str(f.relative_to(dist))) for r in rx))
print(f"{len(pats)} patterns; {len(missed)} uncovered: {missed}")
PY
```

Expect exactly one: `search-index.json`, which the build regenerates every run.
Control: `touch /tmp/dist/planted.woff2` and re-run; it must appear. Keep
`wf[True]` (`wf['on']` is a `KeyError`, and `.get('on', {})` silently reads
nothing), and don't swap the YAML parse for a regex over the file, which picks
up unrelated list items.

Widening a filter is the safe direction: an extra pattern costs one redundant
deploy.

### Registering a new asset

| Asset | Register in |
|---|---|
| CSS / JS | `ASSETS` in `update_sri.py`; `paths:` of `deploy.yml` **and** `site-update-deploy.yml` |
| JSON | all of the above, plus `tools/site-publish.filter` and `nginx.conf` |
| Anything under `/.well-known/` | nothing extra, but verify against production (see below) |

`site-publish.filter` and `nginx.conf` both block `*.json` except five named
files (`manifest`, `preview-mapping`, `meetings-search-index`, `search-index`,
`resources-index`).
Neither exists on localhost, so a missing entry passes every local check and
every CI gate, and fails only in production. The tell is mixed status codes:
404 from S3/Azure (never staged) and 403 from GCP (in the image, refused by
nginx). A mixed 404/403 means more than one thing is saying no.

```sh
for i in $(seq 1 12); do
  printf '%s ' "$(curl -s -o /dev/null -w '%{http_code}' \
    "https://csoh.org/<file>.json?cb=$RANDOM")"
done; echo                                        # want twelve 200s
curl -s -o /dev/null -w 'control %{http_code}\n' \
  "https://csoh.org/search-index.json?cb=$RANDOM"  # want 200
```

Before deploying, prove the allow-list was extended rather than opened:

```sh
./tools/stage_site.sh /tmp/dist && ls /tmp/dist/<file>.json
echo '{}' > zz-plant.json && ./tools/stage_site.sh /tmp/dist2
ls /tmp/dist2/zz-plant.json 2>/dev/null && echo "ALLOW-LIST IS OPEN"
rm -f zz-plant.json
```

`nginx -t` needs a running Docker daemon. An exact `location =` beats the regex
deny regardless of order, so copying one of the existing blocks is safe;
say so rather than implying nginx checked it.

### A new page subdirectory has to be registered in several places

`tools/sync_chrome.py` (glob + parent page) · `tools/run_seo_audit.py`
(`AUDITED_SUBDIRS`) · `tools/check_all_site_urls.py` · `.lychee.toml` ·
`tools/build_search_index.py` (`SUBDIR_TYPES`) · `tools/crosslink_pages.py`
(`SUBDIR_PATTERNS`) · `sitemap.xml`. The last three are judgement calls:
`homelab/` is deliberately excluded from search and cross-linking. The SEO
audit averages over what it audits, so an unregistered directory never lowers
the score.

---

## The three origins

Cloudflare load-balances across AWS (S3 + CloudFront), Azure (Blob static
website) and GCP (Cloud Run). A fix to what gets published has to be verified
against production, with enough requests to land on every origin:

```sh
for i in $(seq 1 12); do
  curl -so /dev/null -w '%{http_code} ' "https://csoh.org/<path>?cb=$RANDOM"
done; echo   # want twelve 200s, not eight
```

### How each origin gets its files

- **S3 and Azure** serve exactly what `stage_site.sh` stages, governed by
  `tools/site-publish.filter`. `build` uploads `dist/` as an artifact and
  `publish-aws` / `publish-azure` download it.
- **GCP** builds its container from a fresh checkout: `COPY .` minus
  `.dockerignore`, minus the Dockerfile's strip list, minus nginx's
  request-time denies.

Those four definitions must agree; nothing in CI compares them. Both sides
should resolve to the same file count. Remember that nginx's denies are part of
the GCP definition: some files are in the image and 403 at request time.

`.dockerignore` is a security boundary, not just a build-speed one. It excludes
Terraform state and provider binaries, which `.gitignore` also covers, so a
local `docker compose up` after `terraform init` would otherwise bake them into
image layers while the repo looks clean.

### `upload-artifact` drops dotfiles unless told otherwise

`actions/upload-artifact` defaults to `include-hidden-files: false` and omits
dot-paths without warning. `deploy.yml` sets it to `true`. That is safe because
`site-publish.filter` excludes every dot-path except `/.well-known/`. **If you
widen that filter, recheck this**: the flag would then ship every dotfile you
staged.

A silent count is a failure mode. Prefer a check that asserts (files staged ==
files in the artifact) over one that prints a number.

### `/.well-known/` is carved out of the dotfile deny

Three places, kept in step:

- `nginx.conf`: `location ^~ /.well-known/` before `location ~ /\.`. The `^~`
  stops nginx evaluating the regex denies.
- `tools/site-publish.filter`: `+ /.well-known/` before the `- .*` catch-all.
- `deploy.yml`: `include-hidden-files: true` on the artifact upload.

`/security.txt` names `/.well-known/security.txt` as `Canonical:`, and MTA-STS
lives there too. If you harden the dotfile rules:

```sh
curl -sI https://csoh.org/.well-known/security.txt | head -1   # want 200
curl -sI https://csoh.org/.git/config                | head -1   # want 403
```

### The published Terraform is content

`site-publish.filter` is a deny-list and does not name `infra/`, so the `.tf`
files are published. They are about two-thirds teaching comments, so
`check-broken-links.yml` crawls `./infra/terraform/*/*.tf` and triggers on
`'**.tf'`.

HCL is full of URL-shaped identifiers (CSP hosts, the OIDC issuer,
`principal://` members, placeholder hostnames). Exclude them in `.lychee.toml`
anchored to the bare host root (`/?$`), so the same host with a path is still
checked. A bare `"img\\.youtube\\.com"` would stop checking every video
thumbnail. Adding a CSP host or issuer to a `.tf` file will surface as a 404 on
its bare root; anchor it and add it.

Nothing on the site links to the served copies, `infra/` is not in the sitemap,
and the content-type differs by origin. Adding `- /infra/` to the filter would
break no links; keep the link gate either way.

---

## CSP, styling and SRI

The CSP is `default-src 'self'; style-src 'self'; script-src 'self'`: no
`'unsafe-inline'`, nonce or hash. **localhost sends no CSP at all**, so anything
the policy blocks works in every local check and fails only in production.

### The site looks unstyled: check SRI first

The browser refuses `style.css` when its hash doesn't match the page's
`integrity=`, and drops every rule. Compare what's served against what the page
demands, extracting both values from the same tag (the first `integrity=` in
the document belongs to `theme.js`, and the `<link>` wraps across lines):

```sh
python3 - <<'PY'
import re, urllib.request, hashlib, base64
h = urllib.request.urlopen("https://csoh.org/").read().decode()
tag = next(t for t in re.findall(r'<link[^>]*>', h, re.S)
           if 'style.css' in t and 'stylesheet' in t)
href = re.search(r'href="([^"]+)"', tag).group(1)
demanded = re.search(r'integrity="sha384-([^"]+)"', tag).group(1)
served = base64.b64encode(hashlib.sha384(
    urllib.request.urlopen("https://csoh.org" + href).read()).digest()).decode()
print(href, "\ndemanded:", demanded, "\nserved:  ", served,
      "\n", "MATCH" if served == demanded else "MISMATCH")
PY
```

Second opinion with no hashing: `document.styleSheets.length` is 0 and an
`Integrity` console error appears when SRI genuinely fails.

```sh
python3 -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b=p.chromium.launch(); pg=b.new_page()
    pg.goto('https://csoh.org/', wait_until='networkidle')
    print('sheets:', pg.evaluate('document.styleSheets.length'),
          '| header bg:', pg.evaluate(\"getComputedStyle(document.querySelector('header')).backgroundColor\"))
    b.close()"
```

The pipeline guards against both known causes:

- **Stale hashes.** `deploy.yml` runs `update_sri.py` in the build, so the
  published artifact is self-consistent. Run it locally anyway so local preview
  loads.
- **A poisoned edge cache** (old bytes cached under a new `?v=` key, pinned by
  `immutable`). Publish jobs upload assets before HTML, and `purge-cloudflare`
  clears the edge after all three origins update, then re-derives every
  versioned asset's hash from the edge and fails the deploy on a mismatch.
  `cf-cache-status: HIT` with the wrong bytes is the tell.

### No inline `<style>` blocks

The browser discards every inline `<style>` and `<script>`. Page-specific CSS
goes in a file served from the origin and registered like any asset (see
[Registering a new asset](#registering-a-new-asset)). Inside SVG, use
presentation attributes.

`<body>` carries `js-enabled` statically, and `style.css` hides `header nav`
below 1023px behind that class. So the `<noscript>` rule that reveals the nav
must live in the stylesheet too, or the nav is unreachable with JS off.

Check (must print `clean`) and see what production sends:

```sh
python3 - <<'PY'
import re, subprocess, pathlib
files = subprocess.run(['git','ls-files','*.html'], capture_output=True, text=True).stdout.split()
hits = [f for f in files if not f.startswith('tools/')
        and '<style>' in re.sub(r'<!--.*?-->', '', pathlib.Path(f).read_text(errors='ignore'), flags=re.S)]
print('\n'.join(hits) if hits else 'clean')
PY
curl -sI https://csoh.org/ | grep -i '^content-security-policy'
```

`tools/og/*template.html` legitimately contain `<style>`; they are rendered
locally by Playwright and never served. Use `git ls-files` rather than `grep -r`
or `rglob`, which descend into the git worktrees under `.claude/`.

Control: plant `<style>` in a page, confirm it is named, then `git checkout --`
the file.

To verify a layout honestly, render it with production's CSP applied
(Playwright `route.fulfill` adding a `content-security-policy` header), **with
scripts both enabled and disabled**. Enumerate sections by what the page
contains, not by the class you suspect, or the broken one is simply absent from
the output.

Cloudflare does not currently inject its bot-detection script into our HTML. If
it starts again, `script-src 'self'` will block it. Check across several
requests:

```sh
for i in 1 2 3 4 5 6; do
  curl -s "https://csoh.org/?cb=$RANDOM" | grep -c 'cdn-cgi/challenge-platform'
done   # want six zeros
```

### No `style="..."` attributes either

Inline attributes fall under `style-src-attr`, governed by the same
`style-src 'self'`, and are dropped the same way. So is
`element.style.cssText = '...'`. Use classes.

```sh
grep -rlE '\sstyle="[^"]*:' --include='*.html' .   # want: no output
```

When moving a style out of an attribute:

- **`display:none` inverts.** A dropped `display:none` makes the element
  render. Put it in a class.
- **`el.style.display = ''` does not reveal a class-hidden element.** Set an
  explicit value.
- **`.is-hidden` is `display: none !important`**, which no inline style can
  override. Anything that must be revealable at runtime needs a different
  mechanism (`#redirect-hint` uses an id selector).
- **A class is weaker than the attribute it replaces.** A bare class at
  `(0,1,0)` loses to `.hero p` at `(0,1,1)`. Scope the class under its
  container, qualify it with the element, or use `!important` with a comment
  saying why.

Verify by measurement: capture computed properties on every affected element
on localhost (attributes applied, the intended rendering) and again under the
production CSP, and diff. Eyeballing pages finds only the pages you open.

---

## Colour and contrast

### Tokens

- `--secondary-color` is sky-700 `#0369a1`. It is the lightest sky shade that
  clears 4.5:1 on both `--white` and `--light-bg`, as text and as a surface
  under white text. Don't lighten it. If a component needs an exception to a
  token, fix the token.
- `--text-muted` is `#5b6573` in `:root` (6.2:1 on `--light-bg`) and `#94a3b8`
  in dark mode. The dark value is written in **both** the
  `prefers-color-scheme` block and the `[data-theme="dark"]` branch by hand;
  `sync_dark_branch.py` mirrors rules, not `:root` custom properties, so
  `--check` won't catch one copy drifting.
- `.news-date-count` looks like it could use `var(--text-muted)` but its dark
  override is deliberately translucent white. Read its comment first.

### Prose links are underlined, and must stay so

`color-contrast` wants a link at >= 4.5:1 against its background;
`link-in-text-block` wants >= 3:1 against the surrounding text unless something
other than colour distinguishes it. On this palette no colour satisfies both
(the luminance ranges don't overlap), so the underline is required. Revealing
it only on hover does not satisfy WCAG 1.4.1: hover reaches neither keyboard
nor touch users.

### Dark mode is not covered by PageSpeed

PSI scores light mode on the home page only. Dark mode and every other page
need their own measurement. A known specificity trap: `[data-theme="dark"] body
a` at (0,1,2) outranks single-class button rules like `.share-btn` at (0,1,0).

The share buttons use the platforms' brand hues darkened in lightness only
(hue unchanged) until white text clears 4.5:1: X `#0b7abf`, Bluesky `#0074de`,
Reddit `#d83b00`; LinkedIn's own `#0a66c2` already passes. They carry text, so
the bar is 4.5:1, not the 3:1 for non-text UI.

### Measuring without inventing failures

- Load each page **fresh** under browser-level `prefers-color-scheme`
  emulation. Never load once and flip `data-theme` on `<html>`: the computed
  tree ends up inconsistent and reports hundreds of phantom failures.
- Walk backgrounds up to and including `documentElement`, and skip any element
  with a `background-image` on itself or an ancestor.
- Blend translucent fills rather than skipping to the first opaque ancestor
  (`.ctf-month-badge` sits on `rgba(44, 62, 80, 0.92)`).
- Text over a sibling `<img>` layer, or over a gradient, cannot be measured
  from computed style (kevin-mitnick.html's memorial hero). axe and Lighthouse
  share this limitation.

Control, which must make the scan fail again:

```js
document.head.appendChild(Object.assign(document.createElement('style'),
  { textContent: ':root{--secondary-color:#0284c7}' }))
```

Fixing one audit can reveal the next. Re-run the gate after a fix rather than
reasoning that it worked.

### The dark mirror block is generated

`tools/sync_dark_branch.py` owns the `@media (prefers-color-scheme: dark)`
block and Lint gates on `--check`. Write dark rules in the
`[data-theme="dark"]` branch only. It flattens each rule onto one line, so put
comments above the selector, never inside a rule.

```sh
python3 tools/sync_dark_branch.py && python3 update_sri.py
python3 tools/sync_dark_branch.py --check
```

---

## Generated content

Several things on the site are owned by a tool. Edit the source and re-run it;
never hand-edit the output.

| What | Tool | Gate |
|---|---|---|
| Nav, footer, logo, hamburger/theme buttons | `tools/sync_chrome.py` (edit its `CANON_*` constants) | |
| Every count (`<!--count:...-->` markers) | `tools/sync_counts.py` | `--check` in CI |
| FAQ and glossary JSON-LD | `tools/check_faq_jsonld_parity.py --fix` | `--check` in `validate-html.yml` |
| Resource card ids | `tools/stamp_card_ids.py` | `--check` in `validate-html.yml` |
| Next-session date and `Event` markup | `tools/sync_next_session.py` | none, runs as a fixer |
| Recap recording links + `VideoObject` | `tools/sync_recap_videos.py` | `--check` in `validate-html.yml` |
| Dark-mode mirror block | `tools/sync_dark_branch.py` | `--check` in Lint |

All are idempotent. **Run any generator twice before trusting it.** The second
run is the only one that parses the first run's output; a regex that consumes
one character too many is perfect on run one and grows the file on every run
after.

Counts written into prose or docs go inside a marker so `sync_counts.py` owns
them. The comment is invisible in rendered HTML and in GitHub Markdown:

```html
Access <!--count:resources_floor-->730+<!--/count--> curated resources.
```

Docs: `tools/SYNC_CHROME_README.md`, `tools/SYNC_COUNTS_README.md`,
`tools/SYNC_RECAP_VIDEOS_README.md`.

### Regexes over card markup must allow attributes

Write `<div class="resource-card"[^>]*>`, never the bare tag. A pattern pinned
to an exact tag doesn't fail when markup gains an attribute; it matches fewer
things, which looks like there being fewer things.

### Card icons

`addIconsToCards()` in `main.js` picks a glyph from keywords in a card's tags
and title, falling back to a padlock. The keywords suit third-party resource
cards; on our own prose cards they rarely match. So:

- A card on our own pages states its glyph: `<div class="resource-card"
  data-icon="📝">`. That wins over the classifier.
- `news.html` is regenerated weekly by `update-news.yml`, so hand-placed
  attributes would be lost. Its cards map `data-category` to an icon, after the
  keyword classifier and before the padlock. Anything regenerated needs a rule
  keyed to what the generator emits.
- `topics.html` opts out with `data-no-card-icons` on `<main>`.

Icons are injected at runtime, so check by rendering and counting:

```js
const c = {};
document.querySelectorAll('.resource-card-icon')
  .forEach(e => { const k = e.textContent.trim(); c[k] = (c[k] || 0) + 1; });
console.log(document.querySelectorAll('.resource-card').length, c);
```

Control: plant a card that matches nothing (must get the padlock) and one with
`data-icon` (must win). Confirm the page is running the deployed `main.js?v=`
before believing it. `frame-src` blocks same-origin iframes in production, so
run sweeps on localhost and confirm one page against production.

### Search results deep-link to their own card

Every resource card carries `id="card-<slug-of-its-h3>"`, stamped by
`tools/stamp_card_ids.py`. `card_slug()` lives in `build_search_index.py` and
both sides use it. The indexer **reads** the id from the HTML rather than
recomputing it, so an unstamped card falls back to its category anchor instead
of pointing at an id that doesn't exist.

Browsers auto-open a `<details>` when the fragment points inside it, but not
universally, so `openSectionFromHash()` opens the ancestor section and
re-scrolls. When verifying the `:target` highlight, assert on `outline-style`:
`outline-width` computes to `3px` even with no outline.

Check (want 0), then control by removing one card's `id`, rebuilding, and
confirming the number moves:

```sh
python3 -c "
import json
docs = json.load(open('search-index.json'))['docs']
bad = [d['url'] for d in docs if d['type'] == 'resource' and '#card-' not in d['url']]
print(len(bad), 'card results not deep-linked to their own card')
"
```

### `normalize_urls.py` must not follow redirects onto a login page

A login URL carries the crawling session's short-lived tokens, so writing it
back into the HTML produces a link that is dead for every reader.
`is_auth_wall()` skips these, and sits above the shortener rule. It errs toward
flagging: a false positive leaves a working redirect; a false negative leaves a
permanently broken link. Skips print under their own heading in the PR. Add
hosts to `AUTH_WALL_HOSTS` in `tools/normalize_urls.py` rather than matching
paths.

### Weekly session `Event` markup

`tools/sync_next_session.py` stamps the next occurrence from `csoh.ics` into the
`[data-next-session]` banners on index.html and sessions.html and into the
`Event` `startDate`/`endDate` on sessions.html. One tool writes both because
the markup must restate the visible date.

- `startDate` is required by Google; `eventSchedule` does not substitute.
- The `Event` lives on **sessions.html only**. Google wants one URL per event.
- Google does not support purely virtual events for the rich result. The markup
  keeps `VirtualLocation` and `OnlineEventAttendanceMode` because they are the
  honest schema.org description. **Do not invent a physical venue** to fill
  `location.address`; markup that contradicts the page risks a manual action.
- validator.schema.org checks syntax only. Google's Rich Results Test requires
  sign-in.

There is no `--check` gate: the committed date expires every Friday, so a gate
would fail weekly for nothing anyone did. It runs as a fixer in
`site-update-deploy.yml` and twice in `deploy.yml` (the `build` job and the GCP
image job, which builds from the raw checkout). `promote-qa.yml` ships the date
from its QA build; the next ordinary deploy corrects it. `--self-test` covers
stale values and DST offsets.

### Recap recording links and `VideoObject`

`tools/sync_recap_videos.py` reads each talk's card on `presentations.html` and
stamps onto that session's recap both a visible "Watch the presentation" link
and a `VideoObject` in `<head>`, always as a pair: markup must describe content
the page shows.

- It reads the **cards**, not the presentations page's schema block. It shares
  an extractor with `update_presentations_schema.py` but never reads that
  tool's output, so neither must run first. Keep it that way.
- `.meeting-recording` has no CSS; styling is on the inner `.card-action`,
  which already has dark rules. The class is the replace hook.
- It owns the whole span between the quick-recap `</p>` and the tags `<div>`.
  Foreign markup there is replaced with a warning naming the page; a recap
  missing either anchor raises. Cards whose date has no recap are reported.

```sh
python3 tools/sync_recap_videos.py --check; echo "want 0: $?"
python3 - <<'PY'
import re, pathlib
p = pathlib.Path('meetings/2025-05-23.html'); s = p.read_text()
p.write_text(re.sub(r'<p class="meeting-recording">.*?</p>\n\s*', '            ', s, count=1))
PY
python3 tools/sync_recap_videos.py --check; echo "want 1: $?"
git checkout -- meetings/2025-05-23.html
```

---

## Meeting recaps

### Discussion topics render open

The topics on each recap sit in a plain `<div class="meeting-topics">`, not a
`<details>`. The wrapper stays because `.meeting-topics > p` styles topic
paragraphs apart from the quick recap. Every rule is scoped under
`.meeting-page` because `faq.html` uses the same class for its accordion, where
`<details>` is correct.

After editing recap prose, rebuild both `build_search_index.py` and
`build_meetings_search_index.py`.

### Zoom attendee rosters are stripped in `add_meeting.py`

Zoom AI Companion ends summaries with `---` and an `**Attendees:**` list of
participant names. The guard sits in `add_meeting.py` beside `scrub_emails`,
where every input path passes through; don't add a second copy elsewhere. It
warns rather than failing.

It matches `Attendees:` / `Participants:` **with the colon**, because
"Attendees" appears in a real session title (`meetings/2024-11-22.html`) and in
prose. `Present:` is deliberately excluded. A false positive here deletes the
tail of a paragraph, so the bias is toward missing a roster, which is visible
and fixable.

Test by where text enters and what must survive: roster spellings must drop,
benign controls must stay. When applying it to existing HTML, run it per `<p>`
body (its `.*$` runs to end of string under `DOTALL`) and assert the result is
a prefix of the input. When checking an index file, count substrings over the
whole file rather than walking one structured entry.

### Verifying hidden or collapsed content

- `el.offsetHeight > 0` is true for a child of a **closed** `<details>`. Use
  `checkVisibility()` or the wrapper's `innerText.length`.
- Swapping a stylesheet under Playwright `route.fulfill` breaks SRI, and the
  browser silently drops the sheet. Strip `integrity="..."` from the HTML in
  the same handler, and assert `document.styleSheets.length` in both runs.

### Planting and restoring test cases

Restore a planted defect with `git checkout --` when your baseline is committed:
a `cp` backup gets left behind when a sweep dies midway. While you have
**uncommitted** changes to the file, `git checkout --` discards them, so copy
the file to the scratchpad and restore from that instead.

Make the plant assert it changed something, so a no-op plant can't pass:

    a = s.replace('<div class="meeting-topics">', '<details ...>', 1)
    assert a != s, "plant did nothing - the fix is not on disk"

---

## Link checking and doc gates

### `.lychee.toml` regexes need doubled backslashes

Excludes are TOML basic strings, so a literal dot is `\\.`. A single `\.` is an
invalid escape, which fails the whole file, and lychee exits without crawling.

`check-broken-links.yml` asserts the crawl ran: the job fails unless the report
exists and its Summary shows a non-zero `Total`. A broken link never fails that
job; a crawl that didn't happen always does. Preserve that asymmetry.

Note that `grep -q` inside an `if` treats "marker absent" and "file absent" the
same way.

```sh
lychee --dump --config .lychee.toml './*.html' | head -1   # validate before trusting a green run
```

### `check_readme_coverage.py` covers what lychee doesn't

lychee crawls published HTML and `.tf`, not Markdown. `python3
tools/check_readme_coverage.py --check` (in `validate-html.yml`) asserts:

- every in-repo Markdown link in every tracked doc resolves, relative to the
  linking document;
- every root page is named in each doc in `CATALOGS` (README.md and
  DEVELOPMENT.md, which carry full directory trees; CONTRIBUTING.md is a
  shortlist and deliberately excluded);
- every published subdirectory (derived by globbing for `*.html`) is
  documented and is in `check-broken-links.yml`'s inputs;
- no count marker sits inside a code fence, where it would render literally.

Page families collapsed behind `<placeholder>` tokens are expanded from the
adjacent comment. Counts inside a fence belong to `MD_PROSE_RULES` in
`sync_counts.py`; match the wording both docs share and capture differences
with a backreference. `--check` self-tests against planted cases and refuses a
verdict if a detector stays silent; add a planted case with any new detector.

### Treat the weekly docs review as unverified

`weekly-docs-review.yml` can produce findings that are specific, well-sourced
in appearance, and wrong. Its prompt requires a `Source:` line on every
accuracy item, naming the publishing body, or `Source: UNVERIFIED - <why>`.
**Read the `Source:` line first.** A wrong correction costs more than a missed
one: it makes the page less accurate than before review.

Settle enumerated standards from the canonical source. For the OWASP LLM Top
10, the directory listing encodes IDs and titles:

```sh
curl -s https://api.github.com/repos/GenAI-Security-Project/GenAI-LLM-Top10/contents/2026/final \
  | grep -o '"name": "LLM[^"]*"'
```

---

## Workflow security

### A workflow that needs cloud credentials must declare an `environment:`

Every cloud pins OIDC trust to an exact `sub` claim naming a GitHub
Environment:

| Job needs                       | `environment:` | Reaches                       |
|---------------------------------|----------------|-------------------------------|
| Production deploy (3 origins)   | `production`   | AWS + Azure + GCP deployer    |
| QA deploy (Cloud Run only)      | `qa`           | `csoh-deployer-qa`, GCP only  |
| Anything else                   | *(none)*       | no cloud credential at all    |

AWS (`infra/terraform/aws/oidc.tf`) and Azure (`infra/terraform/azure/identity.tf`)
accept only `environment:production`. GCP (`infra/terraform/gcp/wif.tf`)
accepts `production` or `qa`, mapped to separate service accounts;
`csoh-deployer-qa` holds `run.admin` on the QA service only, plus `run.viewer`
and Artifact Registry write. `production` is restricted to `main` and `qa` to
`qa` by each environment's branch policy. `var.github_branch` documents intent
but is not referenced by the trust.

Without an `environment:`, `google-github-actions/auth` and
`aws-actions/configure-aws-credentials` fail with an error that doesn't explain
why; `id-token: write` alone is not enough.

`weekly-docs-review.yml`, `security-impact-review.yml` and
`update-resources.yml` hold `id-token: write` for `claude-code-action` and read
untrusted input. They are safe **only** because they declare no
`environment:`. Do not add any value there.

### Never allowlist a bare interpreter in a job that reads the web

In a `claude-code-action` job that reads untrusted pages, `Bash(python3:*)` (or
any interpreter) matches arbitrary code and voids the rest of
`--allowedTools`. If a prompt needs Python, check in a script and allowlist
that exact path. Also set `persist-credentials: false` on `actions/checkout` in
such jobs, so the token isn't left in `.git/config`, and pass tokens explicitly
to the steps that need them.

### PR triage scans the title, body and diff

`tools/pr_security_triage.py` is the deterministic half of
`security-impact-review.yml` and sets the verdict. `check_prompt_injection`
must read the PR title and body as well as the added diff lines, because those
are exactly what the model step is handed. Patterns must catch plain phrasings
("ignore your instructions") as well as elaborate ones.

Test a detector by **every place** hostile input can enter, with benign
controls ("docs: explain how we approve pull requests", "Update the
instructions in CONTRIBUTING.md") that must stay CLEAR.

### `vendor/` files carry local patches

`vendor/goatcounter-count.js` is patched so the beacon never sends the query
string (`q: ''`, and `get_path()` returns `loc.pathname`), because
`/search.html?q=` would otherwise report visitors' search terms, and
`privacy.html` and `llms.txt` promise it isn't collected. Edits are marked
`CSOH LOCAL MODIFICATION` and listed in `vendor/README.md`. Re-apply them after
any re-vendor, then run `python3 update_sri.py`.

---

## Cloudflare

### Two tokens

- **Cache-purge token**: Zone → Cache Purge on `csoh.org` only. Lives only in
  the Actions secret `CLOUDFLARE_API_TOKEN`, used by `purge-cloudflare`.
  Actions secrets are write-only; to purge by hand, create a new token rather
  than rolling this one. Rotation is in `SECURITY.md`.
- **Terraform token**: broad; never in CI. In `.env` as
  `CLOUDFLARE_TF_API_TOKEN`. The provider reads `CLOUDFLARE_API_TOKEN`, so map
  it per run:

```sh
set -a; . ./.env; set +a
export CLOUDFLARE_API_TOKEN="$CLOUDFLARE_TF_API_TOKEN"
```

`.env` also carries `TF_VAR_account_id`, `TF_VAR_zone_id` and the three
`TF_VAR_*_origin_host` values.

- `Invalid API Token`: check the value before the permissions. Length is not a
  validity signal.
- `/user/tokens/verify` reports `active` regardless of scope. Each ruleset
  phase has its own permission group, so an under-scoped token fails only some
  resources (`10000`, `9109`). The full list is in `infra/README.md`.
- A plan always shows `cloudflare_record.dmarc`, `.mta_sts_id` and
  `.smtp_tls_reporting` changing (quote-stripping drift in state). Scope applies
  with `-target=` so you don't rewrite production DMARC and MTA-STS as a side
  effect.

### The security-header ruleset ignores changes to its rules

`cloudflare_ruleset.security_headers` in `infra/terraform/cloudflare/rules.tf`
has `lifecycle { ignore_changes = [rules] }` to work around a v4-provider
ordering bug. So `terraform apply` never changes live headers. Apply header
edits in the dashboard, or drop the `lifecycle` block for one apply.

`tools/check_edge_headers.py` compares the header pairs in `rules.tf` with what
the site serves, and `purge-cloudflare` fails the deploy on drift. Run
`python3 tools/check_edge_headers.py` (or `--url <origin>`). Delete it after the
v5 provider upgrade removes `ignore_changes`.

Header values live in three places that must agree: `rules.tf` (edge),
`infra/terraform/aws/cloudfront.tf` (`aws_cloudfront_response_headers_policy.security`,
covering the public `*.cloudfront.net` hostname), and
`nginx-security-headers.conf` (GCP). Azure Blob static websites can't set
response headers, so that origin depends on the edge.

### Cache rules: extension matching, last match wins

`cloudflare_ruleset.cache` keys off `http.request.uri.path.extension`, which is
empty for `/` and clean URLs. The HTML rule therefore also matches the empty
extension and `ends_with(path, "/")`, plus `json` and `txt`. This zone has no
regex support in rule expressions.

Cache rules apply the **last** matching rule. The general HTML rule carries
`and http.request.uri.path ne "/search.html"` so `/search.html`'s 60-second
rule holds regardless of order. Prefer explicit exclusions to careful ordering.

Caching `json`/`txt` for an hour relies on `purge-cloudflare` clearing the edge
every deploy.

```sh
for u in / /about /search-index.json /search.html; do
  printf '%-22s ' "$u"
  curl -sI "https://csoh.org$u" | grep -i '^cf-cache-status' | tr -d '\r'
done   # none should say DYNAMIC on a second request
```

### Load balancer health checks

Anything on a timer against an origin is a unit cost multiplied by the probe
fan-out. The monitor in `infra/terraform/cloudflare/load_balancer.tf`:

- **`check_regions` is on the pool**, not the monitor (the v4 monitor has no
  such attribute and accepts it silently). This plan allows **one** region;
  more returns `1002`. It is `["ENAM"]`. Unset means every data center.
- **`interval = 300`.** Worst-case failure detection is
  `interval * (1 + retries)`. Don't cut it further.
- **`method = "HEAD"`**, because Azure Blob can't gzip and GET shipped the full
  page per probe. If you ever set `expected_body`, it must go back to `GET`.
- A rejected pool apply still writes the value into state. Use
  `terraform plan -refresh-only` after a failed apply.

Read the live values, not the file:

```sh
curl -s -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$TF_VAR_account_id/load_balancers/pools" \
  | python3 -c 'import json,sys; [print(p["name"], p.get("check_regions"), p["modified_on"]) for p in json.load(sys.stdin)["result"]]'
curl -s -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  "https://api.cloudflare.com/client/v4/accounts/$TF_VAR_account_id/load_balancers/monitors" \
  | python3 -c 'import json,sys; [print(m["method"], m["interval"], m["retries"]) for m in json.load(sys.stdin)["result"]]'
```

Who is hitting the origins:

```sh
gcloud logging read 'resource.type="cloud_run_revision"' \
  --limit=1000 --freshness=30m --project=csoh-org-495800 \
  --format='value(httpRequest.userAgent)' | sort | uniq -c | sort -rn | head
```

A flat request curve with no weekday variation is a machine, not readers.

---

## GCP

### Artifact Registry retention

`artifact_registry.tf` sets `immutable_tags = false` because with immutable tags
**no** delete rule can run ("tagged artifacts can't be deleted"), and CI's
unique tags mean nothing ever becomes untagged either. Digest pinning in
`deploy.yml` and `deploy-qa.yml` (`path@sha256:...`) provides the guarantee
immutability used to. The two settings are a package: re-enabling immutability
silently stops cleanup.

Policies: `keep-recent-10`, `delete-old-tagged` (1d), `delete-old-untagged`
(1d). Cloud Run keeps images used by serving revisions. If QA's image has aged
out when it's promoted, `deploy.yml` rebuilds the commit from source; what's
lost is the exact bytes QA tested. Retention has to account for promotion.

Policies take effect within about a day. Past that, a policy that isn't
deleting is a defect. A hand-run delete of one image is the fastest way to make
a silent failure speak. Audit logs won't help: DATA_WRITE logging is off.

```sh
gcloud artifacts repositories describe csoh-containers \
  --project csoh-org-495800 --location us-central1 --format=json \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d["updateTime"]); print(list(d["cleanupPolicies"]))'
gcloud artifacts docker images list \
  us-central1-docker.pkg.dev/csoh-org-495800/csoh-containers \
  --include-tags --format='value(createTime)' | cut -c1-10 | sort | uniq -c | tail
```

### Binary Authorization is enforcing

Cloud Run only starts images from
`us-central1-docker.pkg.dev/csoh-org-495800/csoh-containers/`. The policy is
`infra/terraform/gcp/binary_authorization.tf`: project-level, an allowlist plus
default `ALWAYS_DENY`. Both `csoh-site` and `csoh-site-qa` opt in with
`binary_authorization { use_default = true }`.

It checks provenance, not attestations, because:

- Cloud Run accepts only the project's single default policy, so one rule
  governs production and QA, and QA images are born before anything could
  attest them.
- Signing would be gated on the same GitHub Environment boundary as registry
  write, adding no independent lock while the builder and deployer are the same
  job.

Both deployer identities can push to the registry, so this doesn't stop a
compromised deployer; it stops running images from anywhere else.

**A denied deploy fails quietly.** The revision is created and fails, traffic
stays on the previous revision, and the service `spec` now names the rejected
image, leaving it `Ready: False` until the next deploy that passes `--image`.
Terraform won't fix it (`ignore_changes` on the image). "The site is up" says
nothing about service health here.

Test both directions, the second restoring the first:

```sh
# must be DENIED
gcloud run deploy csoh-site-qa --project csoh-org-495800 --region us-central1 \
  --image us-docker.pkg.dev/cloudrun/container/hello --quiet

# must SUCCEED, and restores the spec the denied one overwrote
gcloud run deploy csoh-site-qa --project csoh-org-495800 --region us-central1 \
  --image us-central1-docker.pkg.dev/csoh-org-495800/csoh-containers/csoh-site:<tag> \
  --platform managed --ingress all \
  --service-account csoh-run-runtime@csoh-org-495800.iam.gserviceaccount.com --quiet
```

`gcloud run services describe` returns the Knative v1 shape. Read
`metadata.annotations."run.googleapis.com/binary-authorization"` (value
`default`) and `spec.template.spec.containers[0].image`; the v2 paths come back
empty. Cloud Run evaluates the digest-resolved reference.

```sh
gcloud container binauthz policy export --project csoh-org-495800
gcloud run services describe csoh-site --project csoh-org-495800 \
  --region us-central1 \
  --format='value(metadata.annotations."run.googleapis.com/binary-authorization")'
```

Config traps:

- In an allowlist pattern `*` doesn't cross `/`; `csoh-containers/**` is the
  whole repository.
- Both services are declared with the placeholder `hello` image, which the
  policy denies. The policy `depends_on` both services so a from-scratch apply
  creates them first. If either is ever force-replaced while enforcing, comment
  out its `binary_authorization` block for that apply, or deploy through CI
  before re-enforcing.

---

## AWS

### The S3 origin bucket keeps only the current copy

`infra/terraform/aws/s3.tf`: versioning `"Suspended"`, plus a lifecycle rule
that expires noncurrent versions after 1 day, removes orphaned delete markers,
and aborts incomplete multipart uploads. Every deploy rebuilds the bucket from
git, so reverting the commit is the rollback. Don't re-enable versioning here.
Elsewhere, versioning without a `noncurrent_version_expiration` is unbounded
growth.

- A console change to a Terraform-managed resource is drift that the next apply
  reverts. Change `s3.tf`.
- `"Disabled"` is not available once a bucket has been versioned; `"Suspended"`
  is the only off.
- Never prune versions with a delete script. Deleting a delete marker while
  versions sit under it resurrects the removed page on the AWS origin. Let the
  lifecycle rule do it.
- `aws s3 sync` re-uploads every file each deploy (fresh checkout mtimes).
  `--size-only` is not a fix: re-stamping `?v=` and `integrity=` changes pages
  without changing their size, so AWS would serve stale HTML against new assets.
- `days = 0` beside `expired_object_delete_marker = true` is correct: the
  provider sends zero as null.

```sh
aws s3api get-bucket-lifecycle-configuration --bucket csoh-org-site-origin
aws s3api list-object-versions --bucket csoh-org-site-origin --prefix favicon.png \
  --query '{noncurrent: length(Versions[?!IsLatest] || `[]`), deleteMarkers: length(DeleteMarkers || `[]`)}'
aws s3 ls s3://csoh-org-site-origin --recursive --summarize | tail -2
aws cloudwatch get-metric-statistics --namespace AWS/S3 --metric-name BucketSizeBytes \
  --dimensions Name=BucketName,Value=csoh-org-site-origin Name=StorageType,Value=StandardStorage \
  --start-time "$(date -u -v-3d +%FT%TZ)" --end-time "$(date -u +%FT%TZ)" \
  --period 86400 --statistics Average --region us-east-1
```

---

## Cost

The cost tables in `cloud-deployment.html` and `infra/README.md` are re-derived
from billing data, never edited by hand; `infra/README.md` carries the queries.
Sources: the GCP BigQuery billing export (dataset `csoh_cost`, about a day
behind), the Azure Cost Management API, and AWS Cost Explorer (needs
`aws login`). Cloudflare billing can't be read with the Terraform token; that
line is a dashboard figure. The table on `cloud-deployment.html` marks each
line `measured` or `estimated`; an estimate is a to-do, not a rounding.

- **Scale gross cost, then subtract the monthly free allowance once.** Cloud
  Run's allowances arrive as credits consumed early in the month.
- **Cost Explorer's recent days are provisional.** Leave a margin before
  querying.
- **Read inventory next to dollars** (image count, `BucketSizeBytes`). A flat
  or zero line can hide growth, especially under AWS credits.
- **Azure cost is mostly transactions**, not storage: probe reads and deploy
  writes. A `HEAD` is still a billable operation.
- `az consumption usage list` returns rows with null costs. Use Cost
  Management, and retry on 429s:

```sh
az rest --method post \
  --url "https://management.azure.com/subscriptions/<sub-id>/providers/Microsoft.CostManagement/query?api-version=2023-11-01" \
  --body '{"type":"ActualCost","timeframe":"MonthToDate","dataset":{"granularity":"Daily","aggregation":{"totalCost":{"name":"PreTaxCost","function":"Sum"}},"grouping":[{"type":"Dimension","name":"Meter"}]}}'
```

### Budgets

Each cloud stack has a `budget.tf`: $10/month, alerting
`var.budget_alert_emails` on actual and forecast spend.

- The AWS budget counts cost after credits, so it reads $0 while credits last
  and its first alert means they're gone. Its forecast ignores credits, so a
  forecast email can arrive while nothing is billed.
- The GCP budget needs `cloudbilling.googleapis.com` and
  `billingbudgets.googleapis.com` enabled first, and a billing role on the
  billing account; project Owner isn't enough.
- Changing the Azure budget's `start_date` replaces it and discards history.

```sh
aws budgets describe-budgets --account-id 038416307420 --query 'Budgets[].BudgetName'
az consumption budget list --query '[].name' -o tsv
curl -s -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  -H "x-goog-user-project: csoh-org-495800" \
  "https://billingbudgets.googleapis.com/v1/billingAccounts/$(gcloud billing projects describe csoh-org-495800 --format='value(billingAccountName)' | cut -d/ -f2)/budgets" \
  | python3 -c 'import json,sys; [print(b["displayName"]) for b in json.load(sys.stdin).get("budgets", [])]'
```

---

## QA

`qa.csoh.org` is deployed from the `qa` branch to a second Cloud Run service.
`main` is production and deploys on every push. Promotion is **Actions →
Promote QA to production**, which fast-forwards `main`.

Work on QA in `../csoh-qa`, a worktree permanently on `qa`. Don't `git switch
qa` in the main checkout; other sessions share it.

- `deploy-qa.yml` has **no `paths:` filter** on purpose: `promote-qa.yml`
  only promotes commits that have a QA run.
- The QA container config must match production's, because promotion reuses
  QA's image. QA-specific behaviour belongs at the Cloudflare edge.
- QA is outside the load balancer pool, so it isn't probed and can scale to
  zero.
- The Host rewrite is a Worker, because Host Header Override needs a paid plan
  (checked at apply, not plan).

`qa.csoh.org` is behind Cloudflare Access, but its `*.run.app` hostname is
public. Don't stage anything that would harm you if read early.

Full docs: `.github/workflows/QA_PIPELINE_README.md`.

---

## This machine

### Local `dig` is unreliable: verify DNS over DoH

Local `dig` strips the DNSSEC AD bit and can serve stale answers straight after
a change, even from the authoritative server. Use two DoH resolvers:

```sh
curl -s "https://dns.google/resolve?name=csoh.org&type=A" | grep -o '"AD":[a-z]*'
curl -s -H 'accept: application/dns-json' \
  "https://cloudflare-dns.com/dns-query?name=_dmarc.csoh.org&type=TXT"
```

Run a control before believing a negative: ask about a domain known to be
signed (`cloudflare.com`), or a record you didn't just change. The zone is
signed and its DS record is delegated; never submit another DS record.

### Terraform must be a native arm64 build

Check `file "$(which terraform)"`. An x86_64 Terraform (Intel Homebrew under
`/usr/local`) downloads x86_64 providers, and the AWS provider times out
starting under Rosetta: a provider at 100% CPU with no network connections and
`timeout while waiting for plugin to start`. After switching, `terraform init`
in all four stack directories, including `azure/`.

Keep `AWS_EC2_METADATA_DISABLED=true` exported. Local AWS auth is `aws login`,
which the provider doesn't implement; use `aws configure export-credentials
--format env`. When the session expires the provider falls through to EC2
metadata and hangs before failing with `no EC2 IMDS role found`. `aws sts
get-caller-identity` gives the real answer.

Never use `-lock=false`; it starts a second concurrent apply. Confirm no
terraform process is alive (an orphan plugin has `PPID 1`), then
`force-unlock` with the ID from the error.

### Playwright and the image generators

Probe which interpreter has Playwright rather than trusting a note:

```sh
python3 -c "import playwright, PIL; print(playwright.__file__, PIL.__version__)"
```

If bare `python3` lacks it, try `/Users/shawn/.pyenv/versions/3.10.0/bin/python3`
(which has Chromium downloaded) or `/usr/bin/python3`. Don't build a venv.

Beyond the image generators, Playwright is how to render under production's
CSP (`route.fulfill` with the header) and with scripts off
(`browser.new_context(java_script_enabled=False)`). Run the same script against
an unchanged, already-shipped page as a control; a measurement you can't
reproduce on a known-good page is not a finding. The in-app browser pane can
misreport layout (e.g. `clientWidth` of 0).

### `img/og/` and `img/thumbs/`

- **`img/og/`**: 1200x630 social cards from `tools/generate_og_images.py`, for
  unfurls and the four featured "start here" cards on `index.html`.
- **`img/thumbs/`**: 3:2 glyph tiles from `tools/generate_thumbnails.py`, for
  compact card grids, where an OG card's text is illegible.

`.resource-card .resource-preview` crops to a fixed box with `object-fit:
cover` for third-party screenshots; the `--og` and `--thumb` modifiers pin the
box to each asset's own ratio.

After adding a tile, run `generate_webp.py img/thumbs` and then
`update_sri.py`. For `img/og/`, always use `generate_webp.py --only-existing`:
only the four featured cards render through `<picture>`, and every other OG
image is an `og:image` target that can't use a `.webp` sibling.
`update-counts.yml` relies on `--only-existing` to keep `meetings.webp` in step
with its `.jpg`.
