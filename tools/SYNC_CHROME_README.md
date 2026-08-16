# Site Chrome Sync

Stamps **one canonical** nav, header button pair, and footer onto every HTML page in the repo.

There is no templating layer here - the site is ~233 standalone `.html` files, each carrying its own copy of the chrome. This script is what keeps those copies from diverging.

## Quick Start

```bash
python3 tools/sync_chrome.py
```

Run it from the repo root. It is idempotent: running it twice changes nothing the second time.

## Never hand-edit the nav or footer

This is the rule the script exists to enforce. Edit the `CANON_*` constants in [`sync_chrome.py`](sync_chrome.py) and re-run it:

| Constant | What it controls |
|---|---|
| `CANON_LOGO` | The logo block - the first child of `.header-content` |
| `CANON_HAMBURGER` | The mobile menu button |
| `CANON_THEME_TOGGLE` | The light/dark toggle |
| `CANON_NAV` | The entire `<nav>`: top-level items, dropdowns, and mega-menu columns |
| `CANON_FOOTER` | The entire `<footer>` |

Hand-editing is how the site got into the state that motivated this script: the `breaches/` and `meetings/` pages carried an older, smaller nav; a few root pages had stray extra items; the footer's "About CSOH" link existed on some pages and not others; and the logo had drifted into **four** different shapes, with 126 pages having silently lost the cloud mark entirely. Two of those shapes also put the SVG beside the tagline, widening the block from 185px to 231px - which is what decided whether the theme toggle fit on the header's single line, so the header wrapped on some pages and not others.

## What it preserves per page

Everything is byte-identical everywhere except two legitimate differences, both applied automatically:

1. **`../` path prefixes** on pages inside `breaches/`, `meetings/`, `portfolio/`, and `homelab/`.
2. **Current-page markers** - `aria-current="page"` on the active link, plus the `active` class on its enclosing dropdown toggle. The mapping from page to dropdown is derived by scanning `CANON_NAV`, so adding a link to a menu column automatically makes that page highlight the right menu.

   The marker is the class and nothing else. `aria-expanded` stays `"false"` in the stamped HTML on every page, including the active one: it reports whether the menu is open *right now*, and on load it is closed. `main.js` (`initDropdownNav`) owns it from there. Setting it to `"true"` to mean "current section" is the accessibility bug fixed in this script's `mark_active()` - it announced all 254 nav menus as already open.

## Pages covered

```
*.html            (repo root)
breaches/*.html
meetings/*.html
portfolio/*.html
homelab/*.html
```

`google66d489593949bd4c.html` is skipped - it is Google's site-verification stub and must stay exactly as Google issued it.

**Adding a new subdirectory of pages?** It will not be touched until you add its glob to the `paths` list in `main()` and teach `parent_page_for()` which hub page it belongs under. Registering a new subdirectory means touching several places (this script, the validators, `.lychee.toml`); see [DEVELOPMENT.md → Adding a new page](../DEVELOPMENT.md#adding-a-new-page).

## Output

```
updated=0 unchanged=236 skipped=1
skipped files: google66d489593949bd4c.html
```

`updated=0` on a second run is the check that it did its job. If a run reports `updated=N` when you did not change any `CANON_*` constant, something hand-edited the chrome - inspect the diff before committing.

## Do not run these

Three older scripts encoded an earlier nav design and were **removed**: `sync_navs.py`, `redesign_nav.py`, `unify_footer.py`. If you find a copy in a stale branch or worktree, do not run it - it will clobber the current nav with the 2025 one.

## See also

- [DEVELOPMENT.md → Adding a new page](../DEVELOPMENT.md#adding-a-new-page) - the full checklist; nav registration is step 8
- [`SYNC_COUNTS_README.md`](SYNC_COUNTS_README.md) - the other site-wide stamper, for numbers rather than chrome
- [CLAUDE.md](../CLAUDE.md) - repo gotchas, including this one
