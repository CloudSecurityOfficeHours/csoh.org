#!/usr/bin/env python3
"""
Render a how-to slide deck (a Deck from build_howto_decks.py) to a 16:9 .pptx,
and reopen the saved file to verify it.

Only plain text boxes and solid-filled rectangles are used. The file is
uploaded to Google Drive and converted to Google Slides, and the converter
drops SmartArt, embedded fonts and autofit-shrink, so none are used.

python-pptx is imported here and nowhere else; build_howto_decks.py imports
this module only on its --build and --self-test-render paths, so the CI checks
run without python-pptx installed.
"""

from __future__ import annotations

import math
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Emu, Inches, Pt

# Every layout value lives here so the pilot deck can tune it in one place.
STYLE = {
    "slide_w": 13.333,
    "slide_h": 7.5,
    "bg": "f8fafc",
    "bar": "0369a1",
    "bar_w": 0.12,
    "dark": "0f172a",
    "heading": "0f172a",
    "text": "1f2937",
    "muted": "5b6573",
    "code_text": "e2e8f0",
    "accent": "f59e0b",
    "light": "e2e8f0",
    "muted_light": "94a3b8",
    "white": "ffffff",
    "heading_font": "Space Grotesk",
    "body_font": "Source Sans 3",
    "code_font": "Source Code Pro",
    "x": 0.6,
    "y": 0.45,
    "w": 12.1,
    "heading_pt": 36,
    "body_pt": 24,
    "code_pt": 16,
    "small_pt": 14,
    "guide_pt": 16,
    "guide_h": 0.35,
    "guide_advance": 0.4,
    "cover_title_pt": 48,
    "cover_promise_pt": 28,
    "cover_line_pt": 20,
    "code_pad": 0.15,
    "footer_from_bottom": 0.3,
    "footer_h": 0.3,
    "bottom_limit": 6.9,
    "body_chars_per_line": 72,
    "heading_chars_per_line": 48,
    "cover_title_chars_per_line": 34,
    "cover_promise_chars_per_line": 64,
    "line_body": 1.25,
    "line_code": 1.25,
    "line_heading": 1.2,
    "para_gap": 0.08,
    "block_gap": 0.15,
    "label_pt": 12,
    "label_above": 0.17,
    "label_below": 0.07,
    "label_pad": 0.12,
    "label_spacing_pt": 0.84,
}

# 16:9 at the standard widescreen size; 13.333 in is not an exact EMU count.
SLIDE_W_EMU = 12192000
SLIDE_H_EMU = 6858000

LICENSE_LINE = "Slides licensed CC BY-NC 4.0"
ATTRIBUTION = "Cloud Security Office Hours, csoh.org"
CLOSING_HEADING = "Work through the full guide"
CLOSING_LICENSE = (
    f"{ATTRIBUTION}. Slides licensed CC BY-NC 4.0 "
    "(creativecommons.org/licenses/by-nc/4.0). "
    "Third-party excerpts keep their own licenses."
)

# Runs the 18 pt body floor does not apply to, by shape name. Code runs are
# held to exactly the code size instead.
SMALL_SHAPES = ("footer-left", "footer-right", "guide-line", "credit", "code-label")
CODE_SHAPE = "code"
LABEL_SHAPE = "code-label"
BAR_SHAPE = "bar"
FORBIDDEN_DASHES = (chr(0x2014), chr(0x2013))


class LayoutError(Exception):
    """An element would end below the bottom limit. Names the slide's where."""


def _rgb(hexstr: str) -> RGBColor:
    return RGBColor.from_string(hexstr.upper())


def _lines(text: str, per_line: int) -> int:
    return max(1, math.ceil(len(text) / per_line))


def _body_height(paras: list[str]) -> float:
    """Inches for prose or bullets: wrapped lines at the body size, a gap
    between paragraphs, and the box's own breathing room."""
    n = sum(_lines(p, STYLE["body_chars_per_line"]) for p in paras)
    return n * STYLE["body_pt"] * STYLE["line_body"] / 72 + STYLE["para_gap"] * len(paras) + 0.1


def _code_height(lines: list[str]) -> float:
    from build_howto_decks import code_visual_rows

    return code_visual_rows(lines) * STYLE["code_pt"] * STYLE["line_code"] / 72 + 2 * STYLE["code_pad"]


def _heading_height(text: str) -> float:
    n = _lines(text, STYLE["heading_chars_per_line"])
    return n * STYLE["heading_pt"] * STYLE["line_heading"] / 72 + 0.1


class _Page:
    """One slide under construction. Tracks the lowest edge of every element
    so an overflow is reported before the file is written."""

    def __init__(self, prs, where: str, dark: bool):
        self.slide = prs.slides.add_slide(prs.slide_layouts[6])
        self.where = where
        self.bottom = 0.0
        fill = self.slide.background.fill
        fill.solid()
        fill.fore_color.rgb = _rgb(STYLE["dark"] if dark else STYLE["bg"])
        if not dark:
            self._rect(BAR_SHAPE, 0, 0, STYLE["bar_w"], STYLE["slide_h"], STYLE["bar"])

    def _rect(self, name, x, y, w, h, color):
        shape = self.slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
        shape.name = name
        shape.fill.solid()
        shape.fill.fore_color.rgb = _rgb(color)
        shape.line.fill.background()
        shape.shadow.inherit = False
        return shape

    def _frame(self, shape, margin: float, anchor=MSO_ANCHOR.TOP):
        tf = shape.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.vertical_anchor = anchor
        for side in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
            setattr(tf, side, Inches(margin))
        return tf

    def _fill(self, tf, paras, font, size, color, bold=False, align=PP_ALIGN.LEFT, gap=0.0):
        for i, text in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            if gap and i < len(paras) - 1:
                p.space_after = Pt(gap)
            run = p.add_run()
            run.text = text
            run.font.name = font
            run.font.size = Pt(size)
            run.font.bold = bold
            run.font.color.rgb = _rgb(color)

    def text(
        self, name, x, y, w, h, paras, font, size, color, bold=False, align=PP_ALIGN.LEFT, gap=0.0,
        track=True,
    ):
        # The footer sits below the content limit by design, so it is not tracked.
        if track:
            self.reserve(y + h)
        box = self.slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        box.name = name
        tf = self._frame(box, 0.0)
        self._fill(tf, paras, font, size, color, bold, align, gap)
        return box

    def code(self, x, y, w, lines, label=None):
        h = _code_height(lines)
        self.reserve(y + h)
        shape = self._rect(CODE_SHAPE, x, y, w, h, STYLE["dark"])
        tf = self._frame(shape, STYLE["code_pad"])
        self._fill(tf, lines, STYLE["code_font"], STYLE["code_pt"], STYLE["code_text"])
        if label:
            self._label(x, y, label)
        return y + h

    def _label(self, x, y, label):
        """The tab text, as given, on the box's top edge. It spans
        the block gap above the box and the box's top padding, so it adds no
        height and stays clear of the first code row."""
        text = label
        char_w = (0.6 * STYLE["label_pt"] + STYLE["label_spacing_pt"]) / 72
        w = len(text) * char_w + 2 * STYLE["label_pad"]
        top = y - STYLE["label_above"]
        h = STYLE["label_above"] + STYLE["label_below"]
        tab = self._rect(LABEL_SHAPE, x, top, w, h, STYLE["dark"])
        tf = self._frame(tab, 0.0, anchor=MSO_ANCHOR.MIDDLE)
        tf.word_wrap = False
        tf.margin_left = tf.margin_right = Inches(STYLE["label_pad"])
        self._fill(tf, [text], STYLE["code_font"], STYLE["label_pt"], STYLE["muted_light"], bold=True)
        tab.text_frame.paragraphs[0].runs[0]._r.get_or_add_rPr().set("spc", str(round(STYLE["label_spacing_pt"] * 100)))

    def reserve(self, bottom: float) -> None:
        if bottom > STYLE["bottom_limit"] + 1e-9:
            raise LayoutError(
                f"{self.where}: content would end at {bottom:.2f} in, "
                f"below the {STYLE['bottom_limit']} in limit"
            )
        self.bottom = max(self.bottom, bottom)

    def footer(self, guide: str, n: int, total: int, color: str) -> None:
        top = STYLE["slide_h"] - STYLE["footer_from_bottom"] - STYLE["footer_h"]
        half = STYLE["w"] / 2
        args = (STYLE["body_font"], STYLE["small_pt"], color)
        self.text("footer-left", STYLE["x"], top, half, STYLE["footer_h"], [f"csoh.org/{guide}"], *args, track=False)
        self.text(
            "footer-right", STYLE["x"] + half, top, half, STYLE["footer_h"], [f"{n} / {total}"], *args,
            align=PP_ALIGN.RIGHT, track=False,
        )

    def notes(self, text: str) -> None:
        self.slide.notes_slide.notes_text_frame.text = text


def _notes_for(deck, slide, headings: dict[str, str | None] | None) -> str:
    base = f"https://csoh.org/{deck.guide}"
    if not slide.section:
        return f"Full guide: {base}"
    sid = (headings or {}).get(slide.section)
    if sid:
        return f"Guide section: {base}#{sid}"
    return f'Guide section: "{slide.section}" at {base}'


def _cover(prs, deck, total: int) -> None:
    pg = _Page(prs, f"{deck.slug}.deck (cover)", dark=True)
    x, w = 0.9, 11.5
    y = 1.9
    title_h = _lines(deck.title, STYLE["cover_title_chars_per_line"]) * STYLE["cover_title_pt"] * STYLE["line_heading"] / 72 + 0.1
    pg.text("title", x, y, w, title_h, [deck.title], STYLE["heading_font"], STYLE["cover_title_pt"], STYLE["white"], bold=True)
    y += title_h + 0.3
    promise_h = _lines(deck.promise, STYLE["cover_promise_chars_per_line"]) * STYLE["cover_promise_pt"] * STYLE["line_body"] / 72 + 0.1
    pg.text("promise", x, y, w, promise_h, [deck.promise], STYLE["body_font"], STYLE["cover_promise_pt"], STYLE["light"])
    y += promise_h + 0.5
    line_h = STYLE["cover_line_pt"] * STYLE["line_body"] / 72 + 0.1
    pg.text("attribution", x, y, w, line_h, [ATTRIBUTION], STYLE["body_font"], STYLE["cover_line_pt"], STYLE["accent"])
    y += line_h + 0.05
    pg.text("license", x, y, w, line_h, [LICENSE_LINE], STYLE["body_font"], STYLE["cover_line_pt"], STYLE["light"])
    pg.footer(deck.guide, 1, total, STYLE["light"])
    pg.notes(f"Full guide: https://csoh.org/{deck.guide}")


def _content(prs, deck, slide, n: int, total: int, headings) -> None:
    pg = _Page(prs, slide.where, dark=False)
    x, w = STYLE["x"], STYLE["w"]
    y = STYLE["y"]
    h = _heading_height(slide.heading)
    pg.text("heading", x, y, w, h, [slide.heading], STYLE["heading_font"], STYLE["heading_pt"], STYLE["heading"], bold=True)
    y += h
    if slide.section:
        pg.text("guide-line", x, y, w, STYLE["guide_h"], [f"In the guide: {slide.section}"], STYLE["body_font"], STYLE["guide_pt"], STYLE["muted"])
        y += STYLE["guide_advance"]
    y += STYLE["block_gap"]
    items = list(slide.paragraphs) + [f"• {b}" for b in slide.bullets]
    if items:
        h = _body_height(items)
        pg.text("body", x, y, w, h, items, STYLE["body_font"], STYLE["body_pt"], STYLE["text"], gap=STYLE["para_gap"] * 72)
        y += h + STYLE["block_gap"]
    if slide.code:
        tab = slide.code_file or (slide.code_label.upper() if slide.code_label else None)
        y = pg.code(x, y, w, slide.code, tab)
        if slide.credit:
            y += 0.05
            pg.text("credit", x, y, w, 0.3, [slide.credit], STYLE["body_font"], STYLE["small_pt"], STYLE["muted"])
    elif slide.credit:
        pg.text("credit", x, y, w, 0.3, [slide.credit], STYLE["body_font"], STYLE["small_pt"], STYLE["muted"])
    pg.footer(deck.guide, n, total, STYLE["muted"])
    pg.notes(_notes_for(deck, slide, headings))


def _closing(prs, deck, n: int, total: int) -> None:
    pg = _Page(prs, f"{deck.slug}.deck (closing)", dark=False)
    x, w = STYLE["x"], STYLE["w"]
    y = STYLE["y"]
    h = _heading_height(CLOSING_HEADING)
    pg.text("heading", x, y, w, h, [CLOSING_HEADING], STYLE["heading_font"], STYLE["heading_pt"], STYLE["heading"], bold=True)
    y += h + STYLE["block_gap"]
    paras = [
        f"The guide has every step, all the code and the exercise answers: https://csoh.org/{deck.guide}",
        CLOSING_LICENSE,
    ]
    pg.text("body", x, y, w, _body_height(paras), paras, STYLE["body_font"], STYLE["body_pt"], STYLE["text"], gap=STYLE["para_gap"] * 72)
    pg.footer(deck.guide, n, total, STYLE["muted"])
    pg.notes(f"Full guide: https://csoh.org/{deck.guide}")


def render_deck(deck, out: Path, headings: dict[str, str | None] | None = None) -> Path:
    """Write deck as a .pptx at out: a generated cover, the outline's slides,
    a generated closing. Raises LayoutError before writing if any element
    would end below the bottom limit."""
    prs = Presentation()
    prs.slide_width = Emu(SLIDE_W_EMU)
    prs.slide_height = Emu(SLIDE_H_EMU)
    total = len(deck.slides) + 2
    _cover(prs, deck, total)
    for i, slide in enumerate(deck.slides, start=2):
        _content(prs, deck, slide, i, total, headings)
    _closing(prs, deck, total, total)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


def verify_pptx(path: Path, deck) -> list[str]:
    """Reopen the saved file and return every finding."""
    prs = Presentation(str(path))
    findings: list[str] = []
    want = len(deck.slides) + 2
    if len(prs.slides) != want:
        findings.append(f"{path.name}: {len(prs.slides)} slides, expected {want}")
    if (prs.slide_width, prs.slide_height) != (SLIDE_W_EMU, SLIDE_H_EMU):
        findings.append(f"{path.name}: slide size is not 13.333 x 7.5 in")
    limit = Inches(STYLE["bottom_limit"])
    for n, slide in enumerate(prs.slides, start=1):
        tag = f"{path.name} slide {n}"
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text_frame.text)
                findings += _font_findings(tag, shape)
            if shape.name not in (BAR_SHAPE, *SMALL_SHAPES[:2]) and shape.top + shape.height > limit:
                findings.append(f"{tag}: {shape.name} ends below {STYLE['bottom_limit']} in")
        text = "\n".join(texts)
        if f"csoh.org/{deck.guide}" not in text:
            findings.append(f"{tag}: footer lacks csoh.org/{deck.guide}")
        if f"{n} / {want}" not in text:
            findings.append(f"{tag}: footer lacks {n} / {want}")
        if any(d in text for d in FORBIDDEN_DASHES):
            findings.append(f"{tag}: contains an en or em dash")
        if not slide.has_notes_slide or not slide.notes_slide.notes_text_frame.text.strip():
            findings.append(f"{tag}: no speaker notes")
    return findings


def _font_findings(tag: str, shape) -> list[str]:
    out = []
    for p in shape.text_frame.paragraphs:
        for run in p.runs:
            size = run.font.size.pt if run.font.size else None
            if shape.name == CODE_SHAPE:
                if size != STYLE["code_pt"]:
                    out.append(f"{tag}: code run is {size} pt, expected {STYLE['code_pt']}")
            elif shape.name == LABEL_SHAPE:
                if size != STYLE["label_pt"]:
                    out.append(f"{tag}: code label is {size} pt, expected {STYLE['label_pt']}")
            elif shape.name not in SMALL_SHAPES:
                if size is None or size < 18:
                    out.append(f"{tag}: {shape.name} run is {size} pt, below 18")
    return out
