#!/usr/bin/env python3
"""
Render a topic deck (a BDeck parsed with build_topic_decks.TOPIC) to a 16:9
.pptx, and reopen the saved file to verify it.

Every layout but two is breach_deck_render.py's, drawn by its render_deck
with a topic page class and topic generated slides. This module adds:

- the figure layout: one of the page's diagrams, rendered to PNG, scaled to
  fit with its aspect ratio kept and never past 1.5 image pixels per point
  of placed width, on a white panel, with the page's own <figcaption> (or
  the sentences of it the slide's caption: line selects) under it and the
  SVG's <title> as its alt text;
- the code layout: the slide's excerpt of one of the page's <pre> blocks in
  howto_deck_render.code_box, the how-to decks' code box, with the tab the
  how-to build would print for the same excerpt (the page's language
  label, or the file a heredoc writes);
- cover art: the page's hero illustration, or its tile from topics.html
  when it has none;
- the words of the generated how-to and closing slides, set on its page
  class; the slides themselves are breach_deck_render.py's.

Diagrams render with Playwright: the page loads from the working tree
through a routed origin, with integrity attributes stripped (a stale SRI
hash would otherwise drop style.css and render the art unstyled), a light
colour scheme and device scale 2. The render stops when style.css did not
load, and a PNG of a single colour is refused as blank. The hero's art is
hidden on article pages, so it is revealed on a solid panel the colour of
the cover. PNGs are cached in tools/decks/topics/build/figures/<slug>/
<target>-<hash>.png, keyed by the SVG markup's hash (for the hero, also by
style.css and the CSS that reveals it), so an unchanged figure is never
rendered again; delete the directory to render everything afresh.

build_topic_decks.py imports this module only on its --build and
--self-test-render paths, so its --self-test and --check need neither
python-pptx nor Playwright.
"""

from __future__ import annotations

import functools
import hashlib
import io
import mimetypes
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import breach_deck_render as r  # noqa: E402
import build_breach_decks as bbd  # noqa: E402
import build_topic_decks as btd  # noqa: E402
import howto_deck_render as hdr  # noqa: E402
from build_howto_decks import excerpt_file, excerpt_label  # noqa: E402
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE  # noqa: E402
from pptx.enum.text import PP_ALIGN  # noqa: E402
from pptx.util import Inches  # noqa: E402

LayoutError = r.LayoutError
STYLE = r.STYLE
EMU_PER_PT = 12700
# A placed picture keeps at least this many image pixels per point of its
# width, so it stays sharp when projected.
MIN_PX_PER_PT = 1.5
# How far a placed picture's aspect ratio may stray from its image's.
RATIO_TOLERANCE = 0.01
DEVICE_SCALE = 2
ORIGIN = "http://csoh.test"

LOOK = {
    # The page's caption under a figure; the slide's own prose above it is
    # the breach diagrams' caption size.
    "caption_pt": 18,
    "lead_pt": r.LOOK["caption_pt"],
    "panel": "ffffff",
    "panel_line": "cbd5e1",
    "panel_line_pt": 0.75,
    "panel_pad": 0.15,
    "caption_gap": 0.12,
    "min_picture_h": 1.5,
    # The cover: text on the left, the art in a box on the right.
    "cover_x": 0.9,
    "cover_y": 0.9,
    "cover_text_w": 7.0,
    "cover_title_pt": 44,
    "cover_promise_pt": 26,
    "art_x": 8.3,
    "art_y": 0.9,
    "art_w": 4.4,
    "art_h": 5.6,
}

INTEGRITY_RE = re.compile(rb'\sintegrity="[^"]*"')
# Article pages hide the hero art; show it at its own size on the cover's
# colour, without the hero's fade along its bottom edge. The padding keeps
# the screenshot's clip, which rounds out to whole CSS pixels, on that colour
# rather than on the hero section's background.
HERO_CSS = (
    ".hero-illustration { display: block !important; box-sizing: content-box !important; "
    "width: 600px !important; max-width: 600px !important; padding: 8px !important; "
    f"background: #{STYLE['dark']} !important; }} "
    ".hero::after, .hero::before { display: none !important; }"
)
STYLESHEET_JS = """() => [...document.styleSheets].some(s => {
  try { return (s.href || '').split('?')[0].endsWith('/style.css') && s.cssRules.length > 0; }
  catch (e) { return false; } })"""
MARK_JS = """(key) => {
  for (const el of document.querySelectorAll('[data-deck-target]')) el.removeAttribute('data-deck-target');
  let svg = null;
  if (key === 'hero') { svg = document.querySelector('.hero-illustration svg'); }
  else {
    const el = document.getElementById(key);
    if (el) svg = el.tagName.toLowerCase() === 'figure' ? el.querySelector('svg') : el.closest('svg');
  }
  if (!svg) return false;
  svg.setAttribute('data-deck-target', '');
  return true; }"""


class FigureError(LayoutError):
    """A picture could not be rendered, or is blank. A LayoutError, so
    --build reports it like any slide that does not fit."""


# ---------------------------------------------------------------------------
# Rendering the page's SVGs to PNG.
# ---------------------------------------------------------------------------


def check_png(path: Path) -> tuple[int, int]:
    """The image's pixel size. Raises FigureError when it is one colour all
    over: a figure whose stylesheet or fonts failed renders blank."""
    from PIL import Image

    with Image.open(path) as im:
        size = im.size
        one_colour = im.convert("RGBA").getcolors(1) is not None
    if one_colour:
        raise FigureError(f"{path.name} is one colour all over, so the picture is blank")
    return size


def figure_cache() -> Path:
    return bbd.outline_dir(btd.TOPIC) / "build" / "figures"


def _hero_key(html: str, page: Path) -> str:
    """The hero PNG's cache key. The hero's look comes from style.css and
    HERO_CSS as well as its SVG, so a change to any of the three renders it
    afresh."""
    try:
        css = (page.parent / "style.css").read_bytes()
    except OSError:
        css = b""
    parts = (btd.hero_sha256(html), hashlib.sha256(css).hexdigest(), HERO_CSS)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def _target_sha(html: str, target: str, page: Path) -> str:
    """A target's cache key: a figure's SVG hash, or the hero's _hero_key."""
    if target == "hero":
        if not btd.has_hero(html):
            raise FigureError(f"{page.name} has no hero illustration")
        return _hero_key(html, page)
    figs = btd.figures(html)
    if target not in figs:
        raise FigureError(f"{target!r} is not a figure on {page.name}; its figures are: {', '.join(figs) or 'none'}")
    return figs[target].svg_sha256


def _route(root: Path):
    """Serve the working tree at ORIGIN, with integrity attributes stripped
    from HTML; refuse everything else, so a render never reaches the web."""
    def handle(route) -> None:
        url = route.request.url
        if not url.startswith(ORIGIN + "/"):
            route.abort()
            return
        rel = url[len(ORIGIN) + 1:].split("?")[0].split("#")[0] or "index.html"
        f = (root / rel).resolve()
        if not f.is_relative_to(root.resolve()) or not f.is_file():
            route.fulfill(status=404, body="")
            return
        body = f.read_bytes()
        if f.suffix == ".html":
            body = INTEGRITY_RE.sub(b"", body)
        route.fulfill(status=200, body=body,
                      content_type=mimetypes.guess_type(f.name)[0] or "application/octet-stream")
    return handle


def _render_pngs(page: Path, wanted: dict[str, Path]) -> None:
    """Screenshot each target's <svg> on page into its path."""
    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise FigureError(f"rendering {page.name}'s pictures needs Playwright: {e}") from None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                pg = browser.new_page(device_scale_factor=DEVICE_SCALE, color_scheme="light",
                                      viewport={"width": 1280, "height": 900})
                pg.route("**/*", _route(page.parent))
                pg.goto(f"{ORIGIN}/{page.name}", wait_until="networkidle")
                if not pg.evaluate(STYLESHEET_JS):
                    raise FigureError(f"{page.name}: its stylesheet (style.css) did not load, so its "
                                      "pictures would render unstyled")
                pg.evaluate("document.fonts.ready.then(() => true)")
                for target, path in wanted.items():
                    if target == "hero":
                        pg.add_style_tag(content=HERO_CSS)
                    if not pg.evaluate(MARK_JS, target):
                        raise FigureError(f"{page.name}: no <svg> found for {target!r} in the browser")
                    svg = pg.locator("[data-deck-target]")
                    if not svg.is_visible():
                        raise FigureError(f"{page.name}: the <svg> for {target!r} is hidden on the page")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    tmp = path.with_suffix(".tmp.png")
                    svg.screenshot(path=str(tmp), timeout=10000)
                    try:
                        check_png(tmp)
                    except FigureError as e:
                        tmp.unlink(missing_ok=True)
                        raise FigureError(f"{page.name}: {target}: {e}") from None
                    tmp.replace(path)
            finally:
                browser.close()
    except PlaywrightError as e:
        raise FigureError(f"{page.name}: Playwright could not render it: {e}") from None


def render_figure_pngs(page: Path, targets: list[str], out: Path) -> dict[str, Path]:
    """PNGs of the targets on page (figure ids, or "hero"), at
    out/<page stem>/<target>-<first 12 of its SVG hash>.png. One browser
    renders every target not already there; a cached PNG is never rendered
    again."""
    html = page.read_text(encoding="utf-8")
    paths = {
        t: out / page.stem / f"{t}-{_target_sha(html, t, page)[:12]}.png" for t in dict.fromkeys(targets)
    }
    todo = {t: p for t, p in paths.items() if not p.is_file()}
    if todo:
        _render_pngs(page, todo)
    return paths


def render_figure_png(page: Path, target: str, out: Path) -> Path:
    """One figure's (or the hero's) PNG; see render_figure_pngs."""
    return render_figure_pngs(page, [target], out)[target]


# ---------------------------------------------------------------------------
# Placing pictures.
# ---------------------------------------------------------------------------


def _fit(px_w: int, px_h: int, max_w: float, max_h: float) -> tuple[float, float]:
    """Inches for an image of px_w by px_h inside max_w by max_h, its
    aspect ratio kept and no wider than MIN_PX_PER_PT allows."""
    ratio = px_w / px_h
    w = min(max_w, max_h * ratio, px_w / (MIN_PX_PER_PT * 72))
    return w, w / ratio


@dataclass
class _Context:
    page: btd.TopicPage
    art: dict[str, Path]
    cover: tuple[Path, str]
    # Each code slide's tab text (or None), by the slide's where.
    tabs: dict[str, str | None]


class _TopicPage(r._Page):
    """A topic slide: the breach page with the generated slides worded for a
    topic page, and pictures."""

    NOTES_LINK = "Full page"
    PAGE_NOUN = "page"
    HOW_TO_INTRO = (
        "Read it on your own or present it. Every slide draws on the csoh.org page.",
        "The diagrams are the page's own, with the page's captions. The speaker notes are a "
        "presenter's script.",
    )
    CLOSING_HEADING = "Read the full page"
    CLOSING_LEAD = "Every section, source and diagram in detail: "

    def __init__(self, prs, deck, where: str, dark: bool = False, *, ctx: _Context):
        super().__init__(prs, deck, where, dark)
        self.ctx = ctx

    def picture(self, name: str, path: Path, x: float, y: float, w: float, h: float, alt: str):
        self.reserve(y + h)
        pic = self.slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
        pic.name = name
        pic._element.nvPicPr.cNvPr.set("descr", alt)
        return pic


def _checked(where: str, path: Path) -> tuple[int, int]:
    try:
        return check_png(path)
    except FigureError as e:
        raise FigureError(f"{where}: {e}") from None


def _render_figure(page: _TopicPage, s) -> None:
    """The heading, the slide's prose, then the figure on its panel with its
    caption under it (the page's, or the sentences the slide's caption: line
    selects, or none for caption: none), the two centred in the room left."""
    fig = page.ctx.page.figures.get(s.figure)
    path = page.ctx.art.get(s.figure)
    if fig is None or path is None:
        raise FigureError(f"{s.where}: no picture of figure {s.figure!r} from {page.deck.page}")
    caption = btd.slide_caption(fig, s)
    px_w, px_h = _checked(s.where, path)
    y = r._heading(page, s.heading, r.Y)
    if s.paragraphs or s.bullets:
        y = r._body(page, s.paragraphs, s.bullets, y + STYLE["block_gap"], pt=LOOK["lead_pt"])
    top = y + r.LOOK["section_gap"]
    pad, cpt = LOOK["panel_pad"], LOOK["caption_pt"]
    cap_h = r._block_h([caption], r.W, cpt) + LOOK["caption_gap"] if caption else 0.0
    room = page.floor - top - cap_h - 2 * pad
    if room < LOOK["min_picture_h"]:
        raise LayoutError(f"{s.where}: the figure has {room:.2f} in of height left, under "
                          f"{LOOK['min_picture_h']} in; shorten the heading or the prose")
    w, h = _fit(px_w, px_h, r.W - 2 * pad, room)
    top += (room - h) / 2
    x = r.X + (r.W - w) / 2
    page.box("figure-panel", x - pad, top, w + 2 * pad, h + 2 * pad, fill=LOOK["panel"],
             line=(LOOK["panel_line"], LOOK["panel_line_pt"]))
    page.picture("figure", path, x, top + pad, w, h, fig.title)
    if caption:
        page.box("figure-caption", r.X, top + h + 2 * pad + LOOK["caption_gap"], r.W, cap_h - LOOK["caption_gap"],
                 [r._p(caption, cpt, page.muted)], align=PP_ALIGN.CENTER)


def page_code_tab(page_html: str, lines: list[str]) -> str | None:
    """The tab on a code slide's box: what the how-to build prints for the
    same excerpt of its page, the page's language label uppercased (none
    for an unlabelled or text block), or the file a heredoc writes."""
    return hdr.code_tab(excerpt_label(page_html, lines), excerpt_file(page_html, lines))


def _render_code(page: _TopicPage, s) -> None:
    """The heading, the slide's prose, then the how-to renderer's code box
    with its tab, spaced as a how-to code slide is."""
    y = r._heading(page, s.heading, r.Y) + STYLE["block_gap"]
    if s.paragraphs or s.bullets:
        y = r._body(page, s.paragraphs, s.bullets, y) + STYLE["block_gap"]
    hdr.code_box(page, r.X, y, r.W, s.code, page.ctx.tabs.get(s.where))


def _render_cover(page: _TopicPage) -> None:
    """The art in a box on the right, and the breach cover's lines in the
    narrower column beside it."""
    path, alt = page.ctx.cover
    px_w, px_h = _checked(page.where, path)
    w, h = _fit(px_w, px_h, LOOK["art_w"], LOOK["art_h"])
    page.picture("cover-art", path, LOOK["art_x"] + (LOOK["art_w"] - w) / 2,
                 LOOK["art_y"] + (LOOK["art_h"] - h) / 2, w, h, alt)
    r.cover_text(page, LOOK["cover_x"], LOOK["cover_y"], LOOK["cover_text_w"],
                 LOOK["cover_title_pt"], LOOK["cover_promise_pt"])


RENDERERS = {**r.RENDERERS, "figure": _render_figure, "code": _render_code, "list": r._render_list}


def _cover_art(deck, html: str, art: dict[str, Path]) -> tuple[Path, str]:
    """The cover's picture and alt text, from build_topic_decks.cover_source
    (which verify_pptx reads too): the rendered hero, else the page's
    topics.html tile. Raises FigureError when there is nothing to show."""
    where = f"{deck.slug}.deck (cover)"
    source = btd.cover_source(deck.slug, html)
    if source is None:
        raise FigureError(f"{where}: {deck.page} has no hero illustration, and its topics.html card "
                          "has no tile image to show instead")
    kind, path, alt = source
    if kind == "hero":
        path = art.get("hero")
        if path is None:
            raise FigureError(f"{where}: {deck.page} has a hero illustration, but no rendered picture of its hero")
    elif not path.is_file():
        raise FigureError(f"{where}: the topics.html tile {bbd._rel(path)} is missing")
    return path, alt


def render_deck(deck, out: Path, page_html: str | None = None, art: dict[str, Path] | None = None) -> Path:
    """Write the topic deck as a .pptx at out. page_html is the page's HTML
    (read from the tree when None); art maps "hero" and each figure id to
    its PNG (rendered and cached with Playwright when None). Raises
    LayoutError, or FigureError for a picture, before writing anything."""
    if page_html is None:
        page_html = (bbd.ROOT / deck.page).read_text(encoding="utf-8")
    page = btd.parse_topic_page(page_html, deck.page)
    if art is None:
        wanted = (["hero"] if btd.has_hero(page_html) else [])
        wanted += [s.figure for s in deck.slides if s.layout == "figure" and s.figure in page.figures]
        art = render_figure_pngs(bbd.ROOT / deck.page, wanted, figure_cache()) if wanted else {}
    cover = _cover_art(deck, page_html, art)
    tabs = {s.where: page_code_tab(page_html, s.code) for s in deck.slides if s.layout == "code" and s.code}
    ctx = _Context(page, art, cover, tabs)
    return r.render_deck(deck, out, page_cls=functools.partial(_TopicPage, ctx=ctx), renderers=RENDERERS,
                         cover=_render_cover)


# ---------------------------------------------------------------------------
# Verification of the saved file.
# ---------------------------------------------------------------------------


def _picture_problems(tag: str, pic, want_alt: str | None) -> list[str]:
    from PIL import Image

    out = []
    alt = pic._element.nvPicPr.cNvPr.get("descr") or ""
    if not alt.strip():
        out.append(f"{tag}: {pic.name} has no alt text")
    elif want_alt is not None and alt != want_alt:
        out.append(f"{tag}: {pic.name} alt text is {alt!r}, expected {want_alt!r}")
    px_w, px_h = pic.image.size
    placed = pic.width / pic.height
    if abs(placed / (px_w / px_h) - 1) > RATIO_TOLERANCE:
        out.append(f"{tag}: {pic.name} is placed at aspect ratio {placed:.3f}, its image's is {px_w / px_h:.3f}")
    density = px_w / (pic.width / EMU_PER_PT)
    if density < MIN_PX_PER_PT - 1e-6:
        out.append(f"{tag}: {pic.name} has {density:.2f} image pixels per point of width; "
                   f"it needs {MIN_PX_PER_PT}")
    if any((pic.crop_left, pic.crop_right, pic.crop_top, pic.crop_bottom)):
        out.append(f"{tag}: {pic.name} is cropped")
    with Image.open(io.BytesIO(pic.image.blob)) as im:
        if im.convert("RGBA").getcolors(1) is not None:
            out.append(f"{tag}: {pic.name} is one colour all over, so it shows nothing")
    return out


def _code_problems(tag: str, slide, s, page_html: str) -> list[str]:
    """A code slide carries one code box holding its excerpt line for line,
    and the tab page_code_tab gives (or none); no other slide carries
    either. The run sizes are breach verify's, which holds a code slide's
    box to the how-to code sizes."""
    boxes = [sh for sh in slide.shapes if sh.name == hdr.CODE_SHAPE]
    tabs = [sh.text_frame.text for sh in slide.shapes if sh.name == hdr.LABEL_SHAPE]
    if s is None or s.layout != "code":
        if boxes or tabs:
            return [f"{tag}: a {s.layout if s else 'generated'} slide carries a code box or tab"]
        return []
    if len(boxes) != 1:
        return [f"{tag}: {len(boxes)} code boxes, expected 1"]
    out = []
    if [p.text for p in boxes[0].text_frame.paragraphs] != s.code:
        out.append(f"{tag}: the code box does not hold the slide's excerpt line for line")
    want = page_code_tab(page_html, s.code)
    if tabs != ([want] if want else []):
        out.append(f"{tag}: code tab is {tabs!r}, expected {[want] if want else []!r}")
    return out


def verify_pptx(path: Path, deck, pictures: bool = True, page_html: str | None = None) -> list[str]:
    """Every breach verify finding (pictures allowed when pictures is True),
    plus the pictures: the cover carries the art, each figure slide its one
    figure with the caption it prints, and no other slide a picture; every
    picture has the expected alt text, its image's aspect ratio, at least
    MIN_PX_PER_PT pixels per point, no crop, and more than one colour. And
    the code: each code slide's box holds its excerpt with the page's tab,
    and no other slide has a code box."""
    findings = r.verify_pptx(path, deck, pictures=pictures)
    if page_html is None:
        page_html = (bbd.ROOT / deck.page).read_text(encoding="utf-8")
    page = btd.parse_topic_page(page_html, deck.page)
    source = btd.cover_source(deck.slug, page_html)
    cover_alt = source[2] if source else None
    outline = {i + 3: s for i, s in enumerate(deck.slides)}
    for n, slide in enumerate(r.reopen(path).slides, start=1):
        tag = f"{path.name} slide {n}"
        s = outline.get(n)
        want: list[tuple[str, str | None]] = []
        if n == 1:
            want = [("cover-art", cover_alt)]
        elif s is not None and s.layout == "figure":
            fig = page.figures.get(s.figure)
            want = [("figure", fig.title if fig else None)]
            got = [sh.text_frame.text for sh in slide.shapes if sh.name == "figure-caption"]
            cap = btd.slide_caption(fig, s) if fig is not None else ""
            if fig is not None and got != ([cap] if cap else []):
                whose = "its caption: line selects" if s.caption else "the page's is"
                findings.append(f"{tag}: figure caption is {got!r}; {whose} {cap!r}")
        pics = [sh for sh in slide.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE]
        if [p.name for p in pics] != [name for name, _ in want]:
            findings.append(f"{tag}: pictures {[p.name for p in pics]}, expected {[name for name, _ in want]}")
        for pic, (_name, alt) in zip(pics, want):
            findings += _picture_problems(tag, pic, alt)
        findings += _code_problems(tag, slide, s, page_html)
    return findings


# ---------------------------------------------------------------------------
# Render cases. They need python-pptx and PIL; the last needs Playwright.
# build_topic_decks.py --self-test-render runs them.
# ---------------------------------------------------------------------------


def _png(path: Path, w: int, h: int, fill=(255, 255, 255), mark=(3, 105, 161)) -> Path:
    from PIL import Image, ImageDraw

    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (w, h), fill)
    ImageDraw.Draw(im).rectangle([w // 4, h // 4, w // 2, h // 2], fill=mark)
    im.save(path)
    return path


def _blank(path: Path, w: int = 400, h: int = 300) -> Path:
    from PIL import Image

    Image.new("RGB", (w, h), (255, 255, 255)).save(path)
    return path


def _slide(heading: str, layout: str = "text", **kw) -> bbd.BSlide:
    kw.setdefault("notes", [f"Say why {heading.lower()} matters."])
    return bbd.BSlide(heading=heading, layout=layout, **kw)


FIG_A = ("cluster-supply-chain", "supply-chain")
FIG_B = ("cmp-title", "comparison")


def _deck(*figs: tuple[str, str]) -> bbd.BDeck:
    slides = [_slide("What a cluster is", section=["what-is"],
                     paragraphs=["A cluster has worker nodes and a control plane."])]
    for fig, sec in figs:
        slides.append(_slide(f"The {sec} figure", "figure", section=[sec], figure=fig,
                             paragraphs=["The page draws it this way."]))
    for i, s in enumerate(slides):
        s.where = f"t.deck:{10 * (i + 1)}"
    return bbd.BDeck("kube", "Kubernetes and Managed Kubernetes", "kube.html", "2026-11-20",
                     "What a managed cluster runs, and what you still own.", slides, "")


def _art(tmp: Path, fig: tuple[int, int] = (1280, 526)) -> dict[str, Path]:
    return {
        "hero": _png(tmp / "art" / "hero.png", 1200, 960, fill=(15, 23, 42)),
        "cluster-supply-chain": _png(tmp / "art" / f"fig-{fig[0]}x{fig[1]}.png", *fig),
        "cmp-title": _png(tmp / "art" / "cmp.png", 800, 400),
    }


def _render(tmp: Path, deck, art: dict[str, Path], html: str = btd.PAGE, name: str = "t.pptx") -> Path:
    return render_deck(deck, tmp / name, page_html=html, art=art)


def _pics(slide) -> list:
    return [sh for sh in slide.shapes if sh.shape_type == MSO_SHAPE_TYPE.PICTURE]


def _one(slide, name: str):
    found = [sh for sh in slide.shapes if sh.name == name]
    assert len(found) == 1, (name, [sh.name for sh in slide.shapes])
    return found[0]


def _alt(pic) -> str:
    return pic._element.nvPicPr.cNvPr.get("descr") or ""


def _layout_error(fn, needle: str) -> LayoutError:
    try:
        fn()
    except LayoutError as e:
        assert needle in str(e), (needle, str(e))
        return e
    raise AssertionError("LayoutError was not raised")


def _replant(src: Path, dst: Path, n: int, change) -> Path:
    """dst: src with change(picture, slide) applied to slide n's picture."""
    prs = r.reopen(src)
    slide = list(prs.slides)[n - 1]
    change(_pics(slide)[0], slide)
    prs.save(str(dst))
    return dst


def _case_figure_fits_and_keeps_ratio(tmp: Path) -> None:
    deck = _deck(FIG_A)
    limit = Inches(STYLE["bottom_limit"]) + r.EMU_SLACK
    left, right = Inches(STYLE["x"]) - r.EMU_SLACK, Inches(STYLE["x"] + STYLE["w"]) + r.EMU_SLACK
    for w, h in ((1280, 526), (600, 1000), (1600, 400), (800, 800), (1280, 1600)):
        out = _render(tmp, deck, _art(tmp, (w, h)))
        assert verify_pptx(out, deck, page_html=btd.PAGE) == [], verify_pptx(out, deck, page_html=btd.PAGE)
        slide = list(r.reopen(out).slides)[3]
        (pic,) = _pics(slide)
        assert abs((pic.width / pic.height) / (w / h) - 1) < 0.01, (w, h, pic.width, pic.height)
        cap = _one(slide, "figure-caption")
        assert pic.top + pic.height <= cap.top and cap.top + cap.height <= limit, (w, h)
        assert left <= pic.left and pic.left + pic.width <= right, (w, h)
    # Control: verify reports a picture stretched out of its ratio.

    def stretch(pic, _slide):
        pic.width = int(pic.width * 0.9)

    bad = _replant(out, tmp / "bad.pptx", 4, stretch)
    f = verify_pptx(bad, deck, page_html=btd.PAGE)
    assert any("aspect ratio" in x for x in f), f


def _case_figure_resolution(tmp: Path) -> None:
    deck = _deck(FIG_A)
    for w, h in ((2400, 900), (300, 200)):
        out = _render(tmp, deck, _art(tmp, (w, h)))
        (pic,) = _pics(list(r.reopen(out).slides)[3])
        assert pic.image.size == (w, h), pic.image.size
        assert w / (pic.width / EMU_PER_PT) >= 1.5 - 1e-6, (w, pic.width)
    # The small one is placed at its pixel limit, not stretched to fill.
    assert pic.width <= (300 / 1.5) * EMU_PER_PT + r.EMU_SLACK, pic.width

    def enlarge(pic, _slide):
        pic.width, pic.height = int(pic.width * 1.5), int(pic.height * 1.5)

    f = verify_pptx(_replant(out, tmp / "big.pptx", 4, enlarge), deck, page_html=btd.PAGE)
    assert any("pixels per point" in x for x in f), f


def _case_list_has_dots_not_boxes(tmp: Path) -> None:
    items = [["One giant cluster for every environment"], ["No NetworkPolicy"], ["Namespaces as boundaries"]]
    s = _slide("Common pitfalls", "list", section=["what-is"], items={"item": items})
    s.where = "t.deck:90"
    deck = _deck(FIG_A)
    deck.slides.append(s)
    out = _render(tmp, deck, _art(tmp), name="l.pptx")
    sl = next(x for x in r.reopen(out).slides if any(sh.name == "list-text" for sh in x.shapes))
    texts = [sh.text_frame.text for sh in sl.shapes if sh.name == "list-text"]
    dots = [sh for sh in sl.shapes if sh.name == "list-dot"]
    assert texts == [t for (t,) in items], texts
    assert len(dots) == 3 and all(d.auto_shape_type == MSO_SHAPE.OVAL for d in dots), dots
    # Control: a list draws no checklist boxes, and each dot sits beside its item.
    assert not any(sh.name == "check-box" for sh in sl.shapes)
    tops = [sh.top for sh in sl.shapes if sh.name == "list-text"]
    assert all(t <= d.top <= t + 400000 for t, d in zip(tops, dots)), (tops, [d.top for d in dots])


def _case_caption_from_page(tmp: Path) -> None:
    deck = _deck(FIG_A, FIG_B)
    out = _render(tmp, deck, _art(tmp))
    slides = list(r.reopen(out).slides)
    assert _one(slides[3], "figure-caption").text_frame.text == "The cluster runs more than your code."
    assert _one(slides[4], "figure-caption").text_frame.text == "Each provider runs the control plane for you."
    # The outline carries no caption, so an edited page caption is what renders.
    edited = bbd._plant(btd.PAGE, "more than your code.", "more than the code you wrote.")
    again = _render(tmp, deck, _art(tmp), html=edited, name="e.pptx")
    assert _one(list(r.reopen(again).slides)[3], "figure-caption").text_frame.text.endswith("the code you wrote.")
    # Control: verify against the edited page names the stale caption.
    f = verify_pptx(out, deck, page_html=edited)
    assert any("caption" in x and "slide 4" in x for x in f), f


def _case_caption_selected(tmp: Path) -> None:
    """A figure slide with a caption: line prints the sentences it selects,
    not the page's whole caption, and verify holds the slide to them."""
    html = btd.CAPTION_PAGE
    picked = "The cluster runs more than your code. Each check is numbered!"
    deck = _deck(FIG_A, FIG_B)
    deck.slides[1].caption = "The cluster runs  more than your code.\tEach check is numbered!"
    out = _render(tmp, deck, _art(tmp), html=html)
    slides = list(r.reopen(out).slides)
    assert _one(slides[3], "figure-caption").text_frame.text == picked
    # Control: the slide with no caption: line prints its page's caption.
    assert _one(slides[4], "figure-caption").text_frame.text == "Each provider runs the control plane for you."
    assert verify_pptx(out, deck, page_html=html) == [], verify_pptx(out, deck, page_html=html)
    # Control: the same deck without the line prints the whole caption, and
    # verify of the selected render against that deck names slide 4.
    whole = _deck(FIG_A, FIG_B)
    again = _render(tmp, whole, _art(tmp), html=html, name="w.pptx")
    full = btd.figures(html)["cluster-supply-chain"].caption
    assert full != picked and _one(list(r.reopen(again).slides)[3], "figure-caption").text_frame.text == full
    f = verify_pptx(out, whole, page_html=html)
    assert any("caption" in x and "slide 4" in x for x in f), f
    # caption: none draws the picture with no caption under it.
    bare = _deck(FIG_A, FIG_B)
    bare.slides[1].caption = btd.NO_CAPTION
    none = _render(tmp, bare, _art(tmp), html=html, name="n.pptx")
    sl = list(r.reopen(none).slides)[3]
    assert not any(sh.name == "figure-caption" for sh in sl.shapes)
    assert len(_pics(sl)) == 1
    assert verify_pptx(none, bare, page_html=html) == [], verify_pptx(none, bare, page_html=html)
    # Control: verify of a render that printed the caption, against the
    # caption: none deck, names slide 4.
    f = verify_pptx(again, bare, page_html=html)
    assert any("caption" in x and "slide 4" in x for x in f), f


def _case_picture_alt_text(tmp: Path) -> None:
    deck = _deck(FIG_A, FIG_B)
    out = _render(tmp, deck, _art(tmp))
    slides = list(r.reopen(out).slides)
    assert [_alt(p) for p in _pics(slides[0])] == ["Illustration of a cluster"]
    assert [_alt(p) for p in _pics(slides[3])] == ["What else runs in the cluster"]
    assert [_alt(p) for p in _pics(slides[4])] == ["Three managed control planes"]
    assert all(_pics(s) == [] for i, s in enumerate(slides) if i not in (0, 3, 4))

    def drop(pic, _slide):
        pic._element.nvPicPr.cNvPr.set("descr", "")

    f = verify_pptx(_replant(out, tmp / "noalt.pptx", 4, drop), deck, page_html=btd.PAGE)
    assert any("alt text" in x and "slide 4" in x for x in f), f


def _case_blank_png_refused(tmp: Path) -> None:
    blank = _blank(tmp / "blank.png")
    _layout_error(lambda: check_png(blank), "one colour")
    assert check_png(_png(tmp / "ok.png", 400, 300)) == (400, 300)
    deck = _deck(FIG_A)
    art = _art(tmp)
    e = _layout_error(lambda: _render(tmp, deck, {**art, "cluster-supply-chain": blank}), "one colour")
    assert "t.deck:20" in str(e), e
    _layout_error(lambda: _render(tmp, deck, {**art, "hero": blank}), "one colour")
    assert not (tmp / "t.pptx").exists(), "a refused render left a file"
    # Control: verify reports a blank picture planted into a saved file.
    out = _render(tmp, deck, art)

    def whiteout(pic, slide):
        slide.part.related_part(pic._element.blipFill.blip.rEmbed)._blob = blank.read_bytes()

    f = verify_pptx(_replant(out, tmp / "white.pptx", 4, whiteout), deck, page_html=btd.PAGE)
    assert any("one colour" in x and "slide 4" in x for x in f), f


def _case_cover_hero_or_tile(tmp: Path) -> None:
    deck = _deck(FIG_A)
    art = _art(tmp)
    out = _render(tmp, deck, art)
    (pic,) = _pics(list(r.reopen(out).slides)[0])
    assert pic.name == "cover-art" and _alt(pic) == "Illustration of a cluster", (pic.name, _alt(pic))
    assert hashlib.sha256(pic.image.blob).digest() == hashlib.sha256(art["hero"].read_bytes()).digest()
    # Without a hero, the cover shows the page's tile from its topics.html card.
    nohero = bbd._plant(btd.PAGE, btd.HERO, "")
    tile = _png(tmp / "img" / "thumbs" / "kube-tile.jpg", 1440, 960, fill=(224, 242, 254))
    (tmp / "topics.html").write_text(
        '<a href="kube.html" class="card-link"><div class="resource-card"><picture>'
        '<source srcset="img/thumbs/kube-tile.webp" type="image/webp">'
        '<img class="resource-preview resource-preview--thumb" src="img/thumbs/kube-tile.jpg" '
        'alt="Kube graphic" width="1440" height="960"></picture><h3>K</h3></div></a>\n', encoding="utf-8")
    figs = {k: v for k, v in art.items() if k != "hero"}
    with bbd._rooted(tmp):
        out = _render(tmp, deck, figs, html=nohero, name="tile.pptx")
        assert verify_pptx(out, deck, page_html=nohero) == [], verify_pptx(out, deck, page_html=nohero)
    (pic,) = _pics(list(r.reopen(out).slides)[0])
    assert _alt(pic) == "Kube graphic" and pic.image.blob == tile.read_bytes(), _alt(pic)
    # A page with a hero but no rendered picture of it says so, rather than
    # that the page has no hero.
    _layout_error(lambda: _render(tmp, deck, figs, name="nohero.pptx"), "no rendered picture of its hero")
    # Control: with no hero and no tile there is nothing to show, and it says so.
    (tmp / "topics.html").write_text("<main></main>\n", encoding="utf-8")
    with bbd._rooted(tmp):
        _layout_error(lambda: _render(tmp, deck, figs, html=nohero, name="none.pptx"), "tile")


def _case_breach_still_refuses_pictures(tmp: Path) -> None:
    assert bbd.BREACH.pictures is False and btd.TOPIC.pictures is True
    deck = bbd._render_sample()
    out = r.render_deck(deck, tmp / "b.pptx")
    assert r.verify_pptx(out, deck) == []
    prs = r.reopen(out)
    list(prs.slides)[2].shapes.add_picture(str(_png(tmp / "p.png", 200, 100)), Inches(1), Inches(2))
    prs.save(str(tmp / "b2.pptx"))

    def picture_findings(**kw) -> list[str]:
        return [x for x in r.verify_pptx(tmp / "b2.pptx", deck, **kw) if "PICTURE" in x]

    assert len(picture_findings()) == 1 and "survive conversion" in picture_findings()[0], picture_findings()
    assert picture_findings() == picture_findings(pictures=bbd.BREACH.pictures)
    # Control: the same file passes when the kind allows pictures.
    assert picture_findings(pictures=True) == []


def _case_render_png_cached_and_checked(tmp: Path) -> None:
    """Playwright end to end on a scratch site: the stylesheet loads despite
    a wrong integrity hash, the hero shows although the stylesheet hides it,
    both PNGs are at device scale 2 and cached by their SVG's hash, and a
    page with no stylesheet or a figure that renders blank is refused."""
    site = tmp / "site"
    site.mkdir()
    (site / "style.css").write_text(".hero-illustration { display: none; } body { margin: 0; }\n", encoding="utf-8")
    head = '<link rel="stylesheet" href="/style.css?v=1" integrity="sha384-planted">'
    body = (f'<section class="hero hero--illustrated"><h1>P</h1>{btd.HERO}</section>\n'
            f'<main class="container contribute-article">\n{btd.SUPPLY_FIGURE}</main>')
    page = site / "pg.html"
    page.write_text(f"<html><head>{head}</head><body>{body}</body></html>\n", encoding="utf-8")
    out = tmp / "figures"
    paths = render_figure_pngs(page, ["hero", "cluster-supply-chain"], out)
    sha = btd.figures(page.read_text(encoding="utf-8"))["cluster-supply-chain"].svg_sha256
    assert paths["cluster-supply-chain"] == out / "pg" / f"cluster-supply-chain-{sha[:12]}.png", paths
    assert paths["hero"].parent == out / "pg" and paths["hero"].name.startswith("hero-"), paths
    # Device scale 2: twice the SVG's CSS size. The element clip rounds out
    # to whole CSS pixels, so a height may gain one.
    for target, (w, h) in (("cluster-supply-chain", (640, 262)), ("hero", (600, 480))):
        got = check_png(paths[target])
        assert got[0] == 2 * w and 2 * h <= got[1] <= 2 * (h + 1), (target, got)
    for p in paths.values():
        os.utime(p, (1, 1))
    assert render_figure_png(page, "cluster-supply-chain", out) == paths["cluster-supply-chain"]
    assert all(p.stat().st_mtime == 1 for p in paths.values()), "a cached PNG was rendered again"
    # The hero is drawn by the stylesheet as well as its SVG, so a changed
    # style.css renders it afresh under a new name; a figure keeps its key,
    # the hash of its SVG markup alone.
    with (site / "style.css").open("a", encoding="utf-8") as f:
        f.write("/* restyled */\n")
    again = render_figure_pngs(page, ["hero", "cluster-supply-chain"], out)
    assert again["hero"] != paths["hero"] and check_png(again["hero"]), (again, paths)
    assert again["cluster-supply-chain"] == paths["cluster-supply-chain"]
    assert paths["cluster-supply-chain"].stat().st_mtime == 1, "a figure was rendered again"
    nocss = site / "nocss.html"
    nocss.write_text(f"<html><head></head><body>{body}</body></html>\n", encoding="utf-8")
    _layout_error(lambda: render_figure_pngs(nocss, ["cluster-supply-chain"], out), "stylesheet")
    empty = site / "empty.html"
    empty.write_text(page.read_text(encoding="utf-8").replace(
        '<rect x="0" y="0" width="120" height="40" fill="#0369a1"/>', "").replace(
        '<text x="10" y="20">Sign images</text>', ""), encoding="utf-8")
    _layout_error(lambda: render_figure_pngs(empty, ["cluster-supply-chain"], out), "one colour")
    _layout_error(lambda: render_figure_pngs(page, ["nope"], out), "nope")


def _code_deck() -> bbd.BDeck:
    """The figure deck plus two code slides on CODE_PAGE: the labelled HCL
    block under a line of prose (file slide 5), then the unlabelled shell
    block alone (file slide 6)."""
    deck = _deck(FIG_A)
    for n, (heading, code, prose) in enumerate((
        ("Pin the CLI and the state store", btd.HCL_LINES, ["Pin the CLI, then plan."]),
        ("Then plan", btd.SHELL_LINES, []),
    )):
        s = _slide(heading, "code", section=["build"], paragraphs=list(prose), code=list(code), code_lang="hcl")
        s.where, s.code_where = f"t.deck:{70 + 10 * n}", f"t.deck:{73 + 10 * n}"
        deck.slides.append(s)
    return deck


def _case_code_box_from_howto(tmp: Path) -> None:
    """A code slide carries the how-to renderer's code box: the shapes
    howto_deck_render.code_box draws for the same lines, the same size and
    text, with the page's language label on its tab and no tab for an
    unlabelled <pre>."""
    from lxml import etree

    deck = _code_deck()
    out = _render(tmp, deck, _art(tmp), html=btd.CODE_PAGE)
    assert verify_pptx(out, deck, page_html=btd.CODE_PAGE) == [], verify_pptx(out, deck, page_html=btd.CODE_PAGE)
    slides = list(r.reopen(out).slides)
    box, tab = _one(slides[4], "code"), _one(slides[4], "code-label")
    assert [p.text for p in box.text_frame.paragraphs] == list(btd.HCL_LINES)
    assert tab.text_frame.text == "HCL", tab.text_frame.text
    assert tab.left == box.left and tab.top < box.top < tab.top + tab.height, (tab.top, box.top)
    # Below the slide's heading and prose.
    assert _one(slides[4], "body").top < tab.top
    # The how-to renderer's own box for the same lines.
    hprs = hdr.Presentation()
    hp = hdr._Page(hprs, "h", dark=False)
    hdr.code_box(hp, r.X, 1.0, r.W, list(btd.HCL_LINES), "HCL")
    hprs.save(str(tmp / "h.pptx"))
    hslide = list(r.reopen(tmp / "h.pptx").slides)[0]
    for name in ("code", "code-label"):
        mine, theirs = _one(slides[4], name), _one(hslide, name)
        assert (mine.width, mine.height, mine.auto_shape_type) == (theirs.width, theirs.height, theirs.auto_shape_type), name
        assert etree.tostring(mine._element.txBody) == etree.tostring(theirs._element.txBody), name
        assert etree.tostring(mine._element.spPr.find(".//{*}solidFill")) == etree.tostring(
            theirs._element.spPr.find(".//{*}solidFill")), name
    assert [p.text for p in _one(slides[5], "code").text_frame.paragraphs] == list(btd.SHELL_LINES)
    assert not [sh for sh in slides[5].shapes if sh.name == "code-label"]


def _case_code_verified(tmp: Path) -> None:
    """verify_pptx holds a code slide to its excerpt, its tab and the
    how-to code sizes, and no other slide to a code box."""
    from pptx.util import Pt

    deck = _code_deck()
    out = _render(tmp, deck, _art(tmp), html=btd.CODE_PAGE)

    def planted(n: int, change) -> list[str]:
        prs = r.reopen(out)
        change(list(prs.slides)[n - 1])
        prs.save(str(tmp / "bad.pptx"))
        return verify_pptx(tmp / "bad.pptx", deck, page_html=btd.CODE_PAGE)

    def reline(sl):
        _one(sl, "code").text_frame.paragraphs[1].runs[0].text = '  required_version = ">= 1.5.0"'

    def shrink(sl):
        _one(sl, "code").text_frame.paragraphs[0].runs[0].font.size = Pt(12)

    def untab(sl):
        el = _one(sl, "code-label")._element
        el.getparent().remove(el)

    def rename(sl):
        _one(sl, "heading").name = "code"

    for n, change, needles in (
        (5, reline, ("slide 5", "excerpt")),
        (5, shrink, ("slide 5", "code run is 12.0 pt", "expected 16")),
        (5, untab, ("slide 5", "tab")),
        (3, rename, ("slide 3", "code box")),
    ):
        f = planted(n, change)
        assert any(all(x in g for x in needles) for g in f), (needles, f)
    # Control: the file as built is clean.
    assert verify_pptx(out, deck, page_html=btd.CODE_PAGE) == []


def _case_code_too_tall(tmp: Path) -> None:
    deck = _code_deck()
    s = deck.slides[-2]
    s.paragraphs = [" ".join(["Pin"] * 100)]
    s.code = [f"line {i}" for i in range(12)]
    _layout_error(lambda: _render(tmp, deck, _art(tmp), html=btd.CODE_PAGE), "t.deck:70")
    assert not (tmp / "t.pptx").exists(), "a refused render left a file"
    # Control: the same twelve rows under one line of prose fit.
    s.paragraphs = ["Pin the CLI, then plan."]
    out = _render(tmp, deck, _art(tmp), html=btd.CODE_PAGE)
    assert verify_pptx(out, deck, page_html=btd.CODE_PAGE) == []


def _case_heading_wrap_moves_content(tmp: Path) -> None:
    """A heading Google Slides wraps gets two lines' height on a topic text
    slide and a code slide, so the prose and the code box start below its
    second line rather than under it. The heading wrapped in Slides at 36
    pt across the 12.1 in box (build_breach_decks.py's
    heading_lines_measured case holds the measurements)."""
    wraps = "ignore_changes can quietly unmanage a resource"
    line = r._line_h(STYLE["heading_pt"], heading=True)

    def shapes(heading: str | None) -> list:
        deck = _code_deck()
        if heading:
            deck.slides[0].heading = deck.slides[-2].heading = heading
        out = _render(tmp, deck, _art(tmp), html=btd.CODE_PAGE)
        assert verify_pptx(out, deck, page_html=btd.CODE_PAGE) == []
        slides = list(r.reopen(out).slides)
        return [(_one(sl, "heading"), _one(sl, "body"),
                 [sh for sh in sl.shapes if sh.name in ("code", "code-label")])
                for sl in (slides[2], slides[4])]

    before, after = shapes(None), shapes(wraps)
    for (h0, b0, c0), (h1, b1, c1) in zip(before, after):
        assert abs((h0.height / 914400 - 0.1) / line - 1) < 0.01, h0.height
        assert abs((h1.height / 914400 - 0.1) / line - 2) < 0.01, h1.height
        assert b1.top >= h1.top + h1.height, (b1.top, h1.top + h1.height)
        assert abs((b1.top - b0.top) / 914400 - line) < 0.001, (b0.top, b1.top)
        for k0, k1 in zip(c0, c1):
            assert abs((k1.top - k0.top) / 914400 - line) < 0.001, (k0.top, k1.top)
    assert after[1][2], "the code slide drew no code box"


RENDER_CASES: list = [
    ("figure_fits_and_keeps_ratio", _case_figure_fits_and_keeps_ratio),
    ("figure_resolution", _case_figure_resolution),
    ("list_has_dots_not_boxes", _case_list_has_dots_not_boxes),
    ("caption_from_page", _case_caption_from_page),
    ("caption_selected", _case_caption_selected),
    ("picture_alt_text", _case_picture_alt_text),
    ("blank_png_refused", _case_blank_png_refused),
    ("cover_hero_or_tile", _case_cover_hero_or_tile),
    ("breach_still_refuses_pictures", _case_breach_still_refuses_pictures),
    ("render_png_cached_and_checked", _case_render_png_cached_and_checked),
    ("code_box_from_howto", _case_code_box_from_howto),
    ("code_verified", _case_code_verified),
    ("code_too_tall", _case_code_too_tall),
    ("heading_wrap_moves_content", _case_heading_wrap_moves_content),
]


if __name__ == "__main__":
    import sys

    sys.exit(bbd._run_cases(RENDER_CASES, "self-test-render"))
