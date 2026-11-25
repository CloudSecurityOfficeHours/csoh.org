# Topic slide decks: pilot notes

Notes for `docs/superpowers/plans/2026-11-25-topic-decks.md`. Task 1 Step 6 adds the pilot's token figures and findings.

## Image spike (Task 0 Step 1)

- **Pictures survive the Google Slides import.** A two-slide .pptx built with python-pptx `add_picture`, uploaded through the Chrome picker, converts to Slides with both pictures as image elements at their placed size and aspect ratio, and with each picture's alt text (`cNvPr descr`) as the element's description. Google's own thumbnail render shows both sharp. So the .pptx carries the pictures; the placeholder and `createImage` fallback is not needed.
- **Rendering.** Playwright loads the page from the working tree through a routed fake origin (`page.route`), with `integrity` attributes stripped from the HTML, a light colour scheme and device scale 2. `document.styleSheets.length` was 1. The figure PNG (`cluster-supply-chain`) came out 1280 by 526 with a white background; the hero 1200 by 962.
- **Topic pages hide their hero art.** `style.css` sets `display: none` on `.hero--illustrated .hero-illustration` when the body has `main.contribute-article`, which every topic page does, so readers never see it. The renderer has to override that rule (an injected style) before it screenshots the hero.
- **The hero screenshot carries the hero section's background** (navy, `#0b1729`) and a lighter strip along its bottom edge from what sits behind it. Clip the hero to its own box on a solid navy panel, or crop the bottom strip, and check the edges in the pilot's render.
- The spike file is `topic-deck-image-spike` (Drive id `14Tk9mBKR32mqqBrg29KXGErtcXyqBM1xJFoO2_0dCmc`) in My Drive root, private. Trash it with the pilot's go.
