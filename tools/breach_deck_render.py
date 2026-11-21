#!/usr/bin/env python3
"""
Render a breach kill chain deck (a BDeck from build_breach_decks.py) to a
16:9 .pptx, and reopen the saved file to verify it.

The file is uploaded to Google Drive and converted to Google Slides, and the
converter drops images, connectors, SmartArt, embedded fonts and autofit. So
only text boxes and these native shapes are drawn: rectangles, rounded
rectangles, ovals, chevrons, right arrows and down arrows. verify_pptx
reports anything else it finds in the saved file.

Every height is estimated before a shape is placed, the way the how-to
renderer does it, and an element that would end below the content limit
raises LayoutError naming the outline slide, before anything is saved.

The palette, fonts, slide size, attribution and licence lines come from
howto_deck_render, so the two deck families share one look. Of the breach
deck tools, only this module imports python-pptx (howto_deck_render, which
it reads STYLE from, does too). build_breach_decks.py imports it only on its
--build and --self-test-render paths, and its render cases reach python-pptx
through it (reopen, and the names imported below), so the CI checks run
without python-pptx installed.
"""

from __future__ import annotations

import colorsys
import math
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_FILL
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Emu, Inches, Pt

from howto_deck_render import (
    ATTRIBUTION,
    CLOSING_LICENSE,
    LICENSE_LINE,
    SLIDE_H_EMU,
    SLIDE_W_EMU,
    STYLE,
)

SITE = "https://csoh.org/"
HOW_TO_HEADING = "How to use this deck"
CLOSING_HEADING = "Read the full kill chain"
# The slides render_deck adds around the outline's own: the cover, "how to
# use this deck" and the closing.
GENERATED = 3

# Sizes and spacing for the breach layouts, in inches and points. Colours and
# fonts are STYLE's.
LOOK = {
    "min_contrast": 4.5,
    "body_floor_pt": 18,
    "small_floor_pt": 14,
    "section_gap": 0.3,
    # Content, pinned boxes included, stops this far above the footer.
    "footer_gap": 0.15,
    "para_gap": 0.14,
    "list_pt": 22,
    "credit_pt": 16,
    "type_pt": 14,
    "type_pad_x": 0.16,
    "type_pad_y": 0.06,
    "type_spacing_pt": 1.2,
    "band_pt": 18,
    "band_pad": 0.16,
    "band_spacing_pt": 1.5,
    "after_band": 0.3,
    "tile": 1.05,
    "tile_pt": 44,
    "stage_heading_pt": 32,
    "chip_pt": 16,
    "chip_pad_x": 0.14,
    "chip_pad_y": 0.07,
    "chip_gap": 0.15,
    "fact_label_w": 2.9,
    "fact_label_pt": 20,
    "fact_value_pt": 20,
    "fact_col_gap": 0.3,
    "fact_row_gap": 0.16,
    "why_label_pt": 14,
    "why_pt": 20,
    "why_pad": 0.16,
    "why_accent_w": 0.08,
    "stat_value_pt": {2: 72, 3: 60, 4: 48},
    "stat_label_pt": 22,
    "stat_detail_pt": 18,
    "stat_pad": 0.25,
    "stat_gap": 0.3,
    "stat_para_gap": 0.06,
    "question_heading_pt": 40,
    "question_pt": 26,
    "check_box": 0.3,
    "check_indent": 0.55,
    "check_gap": 0.18,
    "link_name_pt": 20,
    "link_url_pt": 18,
    "link_col_gap": 0.4,
    "link_gap": 0.22,
}

# Width estimates. STYLE's chars-per-line values are calibrated for mixed
# text. Bold body text runs a little wider and capitals much wider, so those
# count fewer characters a line; a label's letter spacing is added on top.
BOLD_WIDTH = 0.92
CAPS_EM = 0.68

# ---------------------------------------------------------------------------
# Phase colours. The site's phase hues (breach-timeline.css), keyed by ATT&CK
# v19 tactic. A tactic with its own .ph-* rule takes it; the rest take the
# .mt-* rule the pages use for that tactic's technique chips. The pages label
# Resource Development with .ph-recon and Command and Control with
# .ph-exfil, so those two follow the pages. Stealth and Defense Impairment,
# v19's two halves of Defense Evasion, both take .mt-de.
# ---------------------------------------------------------------------------

SITE_PHASE_HUES = {
    "Reconnaissance": "b45309",  # .ph-recon
    "Resource Development": "b45309",  # .ph-recon
    "Initial Access": "dc2626",  # .ph-init
    "Execution": "ea580c",  # .ph-exec
    "Persistence": "4338ca",  # .ph-persist
    "Privilege Escalation": "7e22ce",  # .ph-priv
    "Stealth": "4338ca",  # .mt-de
    "Defense Impairment": "4338ca",  # .mt-de
    "Credential Access": "a16207",  # .ph-cred
    "Discovery": "64748b",  # .ph-disco
    "Lateral Movement": "2563eb",  # .mt-lm
    "Collection": "059669",  # .mt-co
    "Command and Control": "0891b2",  # .ph-exfil
    "Exfiltration": "0891b2",  # .ph-exfil
    "Impact": "059669",  # .ph-impact
}
# A phase that names no tactic: slate-600, which carries white text at 7.6:1.
FALLBACK_PHASE = "475569"

FORBIDDEN_DASHES = (chr(0x2014), chr(0x2013))
BAR_SHAPE = "bar"
# Runs in these shapes are labels, held to the 14 pt floor; every other run
# is body text, held to 18 pt.
SMALL_SHAPES = ("footer-left", "footer-right", "type-label", "credit", "chip", "why-label")
# Shapes outside the content area by design: the full-height bar and the
# footer below the content limit.
UNTRACKED = (BAR_SHAPE, "footer-left", "footer-right")
TYPE_LABELS = {
    "background": "BACKGROUND",
    "question": "DISCUSSION",
    "answer": "DISCUSSION: ANSWER",
}
DARK_LAYOUTS = ("question",)
ALLOWED_AUTOSHAPES = (
    MSO_SHAPE.RECTANGLE,
    MSO_SHAPE.ROUNDED_RECTANGLE,
    MSO_SHAPE.OVAL,
    MSO_SHAPE.CHEVRON,
    MSO_SHAPE.RIGHT_ARROW,
    MSO_SHAPE.DOWN_ARROW,
)
# Shape positions are whole EMUs, so a sum can land a few EMUs past an exact
# limit; 100 EMU is under a thousandth of an inch.
EMU_SLACK = 100


class LayoutError(Exception):
    """An element would end below the room it has. Names the slide's where."""


def _rgb(hexstr: str) -> RGBColor:
    return RGBColor.from_string(hexstr.upper())


def _luminance(hexstr: str) -> float:
    hexstr = hexstr.lstrip("#")

    def channel(i: int) -> float:
        c = int(hexstr[i : i + 2], 16) / 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4)


def contrast(fg: str, bg: str) -> float:
    """WCAG contrast ratio of two hex colours, from 1 to 21."""
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _hls_hex(h: float, lum: float, s: float) -> str:
    return "".join(f"{round(c * 255):02x}" for c in colorsys.hls_to_rgb(h, lum, s))


def _darken_for_white(hexstr: str) -> str:
    """hexstr with its lightness lowered, hue and saturation kept, until
    white text on it clears the contrast floor. A colour that already
    clears it is returned unchanged."""
    h, lum, s = colorsys.rgb_to_hls(*(int(hexstr[i : i + 2], 16) / 255 for i in (0, 2, 4)))
    out = hexstr
    while contrast("ffffff", out) < LOOK["min_contrast"]:
        lum -= 0.005
        out = _hls_hex(h, lum, s)
    return out


PHASE_COLORS: dict[str, str] = {t: _darken_for_white(c) for t, c in SITE_PHASE_HUES.items()}


def phase_color(phase: str) -> str:
    """The colour for a phase: line. The tactic is the start of the text
    before any colon ("Persistence and Collection: Mail" is Persistence),
    matched as whole words in any case; anything else gets the fallback."""
    head = phase.split(":", 1)[0].strip().lower()
    for tactic in sorted(PHASE_COLORS, key=len, reverse=True):
        t = tactic.lower()
        if head == t or (head.startswith(t) and not head[len(t)].isalnum()):
            return PHASE_COLORS[tactic]
    return FALLBACK_PHASE


# ---------------------------------------------------------------------------
# Height estimates.
# ---------------------------------------------------------------------------


def _per_line(width: float, pt: float, heading: bool = False, bold: bool = False) -> int:
    """Characters that fit across width inches at pt, scaled from the how-to
    renderer's calibration (body_chars_per_line at body_pt and
    heading_chars_per_line at heading_pt, both across STYLE's w)."""
    if heading:
        n = STYLE["heading_chars_per_line"] * STYLE["heading_pt"] / pt
    else:
        n = STYLE["body_chars_per_line"] * STYLE["body_pt"] / pt * (BOLD_WIDTH if bold else 1)
    return max(1, int(n * width / STYLE["w"]))


def _caps_per_line(width: float, pt: float, spacing: float) -> int:
    return max(1, int(width * 72 / (CAPS_EM * pt + spacing)))


def _caps_width(text: str, pt: float, spacing: float) -> float:
    return len(text) * (CAPS_EM * pt + spacing) / 72


def _char_width(pt: float) -> float:
    """Inches per character of body text at pt."""
    return STYLE["w"] / (STYLE["body_chars_per_line"] * STYLE["body_pt"] / pt)


def _rows(text: str, per_line: int) -> int:
    """Lines text wraps to, filling each line with whole words; a word
    longer than a line breaks across lines."""
    rows, cur = 1, 0
    for word in text.split():
        if cur == 0:
            cur = len(word)
        elif cur + 1 + len(word) <= per_line:
            cur += 1 + len(word)
        else:
            rows += 1
            cur = len(word)
        while cur > per_line:
            rows += 1
            cur -= per_line
    return rows


def _line_h(pt: float, heading: bool = False) -> float:
    return pt * STYLE["line_heading" if heading else "line_body"] / 72


def _block_h(texts: list[str], width: float, pt: float, heading: bool = False,
             bold: bool = False, gap: float = LOOK["para_gap"]) -> float:
    """Inches for paragraphs: wrapped lines, a gap between paragraphs, and
    the box's own breathing room."""
    per = _per_line(width, pt, heading, bold)
    rows = sum(_rows(t, per) for t in texts)
    return rows * _line_h(pt, heading) + gap * (len(texts) - 1) + 0.1


# ---------------------------------------------------------------------------
# The page: one slide under construction.
# ---------------------------------------------------------------------------


@dataclass
class _Run:
    text: str
    pt: float
    color: str
    font: str = "body_font"
    bold: bool = False
    spacing: float = 0.0
    link: str | None = None


def _p(text: str, pt: float, color: str, **kw) -> list[_Run]:
    """A paragraph of one run."""
    return [_Run(text, pt, color, **kw)]


class _Page:
    """One slide under construction. Tracks the lowest edge of the content
    above, and the floor that elements pinned to the bottom leave, so an
    overflow is reported before the file is written."""

    def __init__(self, prs, deck, where: str, dark: bool = False):
        self.slide = prs.slides.add_slide(prs.slide_layouts[6])
        self.deck = deck
        self.where = where
        self.dark = dark
        self.bottom = 0.0
        self.floor = STYLE["bottom_limit"] - LOOK["footer_gap"]
        fill = self.slide.background.fill
        fill.solid()
        fill.fore_color.rgb = _rgb(STYLE["dark"] if dark else STYLE["bg"])
        if not dark:
            self.box(BAR_SHAPE, 0, 0, STYLE["bar_w"], STYLE["slide_h"], fill=STYLE["bar"],
                     track=False)

    @property
    def muted(self) -> str:
        return STYLE["muted_light"] if self.dark else STYLE["muted"]

    def reserve(self, bottom: float) -> None:
        if bottom > self.floor + 1e-9:
            raise LayoutError(
                f"{self.where}: content would end at {bottom:.2f} in; "
                f"this slide has room to {self.floor:.2f} in"
            )
        self.bottom = max(self.bottom, bottom)

    def claim_bottom(self, h: float, gap: float) -> float:
        """Room for an element pinned to the bottom of the content area,
        with gap above it. Returns its top and lowers the floor the rest of
        the slide must stay above."""
        top = self.floor - h
        if top - gap < self.bottom - 1e-9:
            raise LayoutError(
                f"{self.where}: content above ends at {self.bottom:.2f} in, but the "
                f"{h:.2f} in pinned to the bottom needs it to end by {top - gap:.2f} in"
            )
        self.floor = top - gap
        return top

    def box(self, name, x, y, w, h, paras=(), *, fill=None, kind=None, line=None,
            radius=None, margins=0.0, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
            gap=0.0, wrap=True, track=True):
        """A text box, or a filled shape (with text when paras are given).
        A shape pinned to the bottom, or outside the content area by
        design, passes track=False; everything else is checked against the
        floor."""
        if track:
            self.reserve(y + h)
        at = (Inches(x), Inches(y), Inches(w), Inches(h))
        if fill is None and line is None and kind is None:
            sh = self.slide.shapes.add_textbox(*at)
        else:
            sh = self.slide.shapes.add_shape(kind or MSO_SHAPE.RECTANGLE, *at)
            if fill:
                sh.fill.solid()
                sh.fill.fore_color.rgb = _rgb(fill)
            else:
                sh.fill.background()
            if line:
                sh.line.color.rgb = _rgb(line[0])
                sh.line.width = Pt(line[1])
            else:
                sh.line.fill.background()
            sh.shadow.inherit = False
            if radius is not None:
                sh.adjustments[0] = radius
        sh.name = name
        if paras:
            self._write(sh.text_frame, paras, margins, align, anchor, gap, wrap)
        return sh

    def _write(self, tf, paras, margins, align, anchor, gap, wrap) -> None:
        tf.word_wrap = wrap
        tf.auto_size = MSO_AUTO_SIZE.NONE
        tf.vertical_anchor = anchor
        left, top, right, bottom = margins if isinstance(margins, tuple) else (margins,) * 4
        tf.margin_left, tf.margin_top = Inches(left), Inches(top)
        tf.margin_right, tf.margin_bottom = Inches(right), Inches(bottom)
        for i, runs in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            if gap and i < len(paras) - 1:
                p.space_after = Pt(gap * 72)
            for r in runs:
                run = p.add_run()
                run.text = r.text
                font = run.font
                font.name = STYLE[r.font]
                font.size = Pt(r.pt)
                font.bold = r.bold
                font.color.rgb = _rgb(r.color)
                if r.spacing:
                    run._r.get_or_add_rPr().set("spc", str(round(r.spacing * 100)))
                if r.link:
                    run.hyperlink.address = r.link

    def footer(self, n: int, total: int) -> None:
        top = STYLE["slide_h"] - STYLE["footer_from_bottom"] - STYLE["footer_h"]
        half = STYLE["w"] / 2
        args = (STYLE["small_pt"], self.muted)
        self.box("footer-left", STYLE["x"], top, half, STYLE["footer_h"],
                 [_p(f"csoh.org/{self.deck.page}", *args)], track=False)
        self.box("footer-right", STYLE["x"] + half, top, half, STYLE["footer_h"],
                 [_p(f"{n} / {total}", *args)], align=PP_ALIGN.RIGHT, track=False)

    def notes(self, paras: list[str]) -> None:
        url = f"Full kill chain: {SITE}{self.deck.page}"
        self.slide.notes_slide.notes_text_frame.text = "\n\n".join([*paras, url])


# ---------------------------------------------------------------------------
# Pieces several layouts share.
# ---------------------------------------------------------------------------

X, W, Y = STYLE["x"], STYLE["w"], STYLE["y"]


def _heading(page, text, y, x=X, w=W, pt=None, min_h=0.0) -> float:
    """The slide heading at y; returns its bottom. With min_h, the box is at
    least that tall and its text centred in it."""
    pt = pt or STYLE["heading_pt"]
    color = STYLE["white"] if page.dark else STYLE["heading"]
    h = _block_h([text], w, pt, heading=True)
    anchor = MSO_ANCHOR.MIDDLE if min_h > h else MSO_ANCHOR.TOP
    h = max(h, min_h)
    page.box("heading", x, y, w, h, [_p(text, pt, color, font="heading_font", bold=True)],
             anchor=anchor)
    return y + h


def _body(page, paras, bullets, y, pt=None) -> float:
    """Paragraphs, then bullets, at y; returns the bottom (y when empty)."""
    items = list(paras) + [f"• {b}" for b in bullets]
    if not items:
        return y
    pt = pt or STYLE["body_pt"]
    color = STYLE["light"] if page.dark else STYLE["text"]
    h = _block_h(items, W, pt)
    page.box("body", X, y, W, h, [_p(t, pt, color) for t in items], gap=LOOK["para_gap"])
    return y + h


def _type_label(page, layout: str, y: float) -> float:
    """The pill that says what kind of slide this is; returns its bottom.
    Background slides take the sky fill; discussion slides take amber."""
    text = TYPE_LABELS[layout]
    if layout == "background":
        fill, color = STYLE["bar"], STYLE["white"]
    else:
        fill, color = STYLE["accent"], STYLE["dark"]
    pt, sp = LOOK["type_pt"], LOOK["type_spacing_pt"]
    px, py = LOOK["type_pad_x"], LOOK["type_pad_y"]
    w = _caps_width(text, pt, sp) + 2 * px
    h = _line_h(pt) + 2 * py
    page.box("type-label", X, y, w, h,
             [_p(text, pt, color, font="heading_font", bold=True, spacing=sp)],
             fill=fill, kind=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.5,
             margins=(px, 0, px, 0), align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, wrap=False)
    return y + h


def _host(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _credits(page, slide) -> None:
    """The source line ("Source: <name> (<host>)") and any credit: line,
    pinned to the bottom of the content area."""
    lines = []
    if slide.source:
        lines.append(f"Source: {slide.source[0]} ({_host(slide.source[1])})")
    if slide.credit:
        lines.append(slide.credit)
    if not lines:
        return
    pt = LOOK["credit_pt"]
    h = _block_h(lines, W, pt, gap=0.0)
    top = page.claim_bottom(h, STYLE["block_gap"])
    page.box("credit", X, top, W, h, [_p(t, pt, page.muted) for t in lines], track=False)


# ---------------------------------------------------------------------------
# One renderer per layout. Each draws the slide's content; the caller adds
# the source line, footer and notes.
# ---------------------------------------------------------------------------


def _render_text(page, s) -> None:
    y = _heading(page, s.heading, Y)
    _body(page, s.paragraphs, s.bullets, y + STYLE["block_gap"])


def _render_stats(page, s) -> None:
    y = _heading(page, s.heading, Y) + LOOK["section_gap"]
    stats = s.items.get("stat", [])
    n = max(1, len(stats))
    gap, pad = LOOK["stat_gap"], LOOK["stat_pad"]
    tw = (W - gap * (n - 1)) / n
    inner = tw - 2 * pad
    vpt = LOOK["stat_value_pt"][min(max(n, 2), 4)]
    lpt, dpt, pgap = LOOK["stat_label_pt"], LOOK["stat_detail_pt"], LOOK["stat_para_gap"]

    def height(value: str, label: str, detail: str) -> float:
        return (
            2 * pad + 2 * pgap + 0.1
            + _rows(value, _per_line(inner, vpt, heading=True)) * _line_h(vpt, heading=True)
            + _rows(label, _per_line(inner, lpt, bold=True)) * _line_h(lpt)
            + _rows(detail, _per_line(inner, dpt)) * _line_h(dpt)
        )

    # Every tile in the row takes the tallest tile's height.
    th = max((height(*row) for row in stats), default=0.0)
    for i, (value, label, detail) in enumerate(stats):
        paras = [
            _p(value, vpt, STYLE["accent"], font="heading_font", bold=True),
            _p(label, lpt, STYLE["white"], bold=True),
            _p(detail, dpt, STYLE["light"]),
        ]
        page.box("stat-tile", X + i * (tw + gap), y, tw, th, paras, fill=STYLE["dark"],
                 kind=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06, margins=pad, gap=pgap)
    _body(page, s.paragraphs, s.bullets, y + th + LOOK["section_gap"])


def _chips(page, techniques, y: float) -> float:
    """One chip per technique, "ID  Name", flowing left to right and onto a
    new row when the next would not fit. Returns the bottom of the last row.
    The width estimate runs wide of the real text, and the text is centred,
    so the spare room falls evenly on both sides."""
    pt, px, py, gap = LOOK["chip_pt"], LOOK["chip_pad_x"], LOOK["chip_pad_y"], LOOK["chip_gap"]
    cx, row_top, row_h = X, y, 0.0
    for tid, name in techniques:
        text = f"{tid}  {name}"
        cw = min(len(text) * _char_width(pt) + 2 * px, W)
        lines = _rows(text, _per_line(cw - 2 * px, pt)) if cw >= W else 1
        ch = lines * _line_h(pt) + 2 * py
        if cx > X and cx + cw > X + W + 1e-9:
            cx, row_top, row_h = X, row_top + row_h + gap, 0.0
        runs = [_Run(tid, pt, STYLE["accent"], bold=True), _Run(f"  {name}", pt, STYLE["light"])]
        page.box("chip", cx, row_top, cw, ch, [runs], fill=STYLE["dark"],
                 kind=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.2, margins=(px, py, px, py),
                 align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
        cx += cw + gap
        row_h = max(row_h, ch)
    return row_top + row_h


def _why(page, s, color: str) -> None:
    """The "why it matters" box, pinned to the bottom: a white panel with a
    phase-coloured edge, a small label, then the slide's prose."""
    prose = list(s.paragraphs) + [f"• {b}" for b in s.bullets]
    if not prose:
        return
    aw, pad = LOOK["why_accent_w"], LOOK["why_pad"]
    lpt, pt = LOOK["why_label_pt"], LOOK["why_pt"]
    ix, iw = X + aw + pad, W - aw - 2 * pad
    label_h = _line_h(lpt) + 0.04
    text_h = _block_h(prose, iw, pt)
    h = 2 * pad + label_h + text_h
    top = page.claim_bottom(h, LOOK["section_gap"])
    page.box("why", X, top, W, h, fill=STYLE["white"], line=(STYLE["light"], 1), track=False)
    page.box("why-accent", X, top, aw, h, fill=color, track=False)
    page.box("why-label", ix, top + pad, iw, label_h,
             [_p("WHY IT MATTERS", lpt, color, font="heading_font", bold=True,
                 spacing=LOOK["type_spacing_pt"])], track=False)
    page.box("why-text", ix, top + pad + label_h, iw, text_h,
             [_p(t, pt, STYLE["text"]) for t in prose], gap=LOOK["para_gap"], track=False)


def _render_stage(page, s) -> None:
    phase, stage = s.phase or "", s.stage or ""
    color = phase_color(phase)
    # The phase band runs the full slide width; its text lines up with the
    # content column.
    band_text = f"{phase.upper()} · STAGE {stage}"
    bpt, bsp, bpad = LOOK["band_pt"], LOOK["band_spacing_pt"], LOOK["band_pad"]
    band_h = _rows(band_text, _caps_per_line(W, bpt, bsp)) * _line_h(bpt) + 2 * bpad
    right = STYLE["slide_w"] - X - W
    page.box("phase-band", 0, 0, STYLE["slide_w"], band_h,
             [_p(band_text, bpt, STYLE["white"], font="heading_font", bold=True, spacing=bsp)],
             fill=color, margins=(X, 0, right, 0), anchor=MSO_ANCHOR.MIDDLE)

    y = band_h + LOOK["after_band"]
    tile = LOOK["tile"]
    page.box("stage-number", X, y, tile, tile,
             [_p(stage, LOOK["tile_pt"], STYLE["white"], font="heading_font", bold=True)],
             fill=color, kind=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.12,
             align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE, wrap=False)
    hx = X + tile + LOOK["section_gap"]
    y = _heading(page, s.heading, y, x=hx, w=X + W - hx, pt=LOOK["stage_heading_pt"], min_h=tile)

    y = _chips(page, s.items.get("technique", []), y + 0.25)
    _why(page, s, color)

    # Facts: a label column and a value column, a hairline above each row.
    lw, gap = LOOK["fact_label_w"], LOOK["fact_row_gap"]
    lpt, vpt = LOOK["fact_label_pt"], LOOK["fact_value_pt"]
    vx = X + lw + LOOK["fact_col_gap"]
    vw = X + W - vx
    y += LOOK["section_gap"]
    for label, value in s.items.get("fact", []):
        h = max(
            _rows(label, _per_line(lw, lpt, bold=True)) * _line_h(lpt),
            _rows(value, _per_line(vw, vpt)) * _line_h(vpt),
        ) + 0.05
        page.box("fact-rule", X, y - gap / 2, W, 0.012, fill=STYLE["light"])
        page.box("fact-label", X, y, lw, h, [_p(label, lpt, STYLE["muted"], bold=True)])
        page.box("fact-value", vx, y, vw, h, [_p(value, vpt, STYLE["text"])])
        y += h + gap


def _render_background(page, s) -> None:
    y = _type_label(page, "background", Y) + STYLE["block_gap"]
    y = _heading(page, s.heading, y)
    _body(page, s.paragraphs, s.bullets, y + STYLE["block_gap"])


def _render_question(page, s) -> None:
    y = _type_label(page, "question", Y) + 0.25
    y = _heading(page, s.heading, y, pt=LOOK["question_heading_pt"])
    _body(page, s.paragraphs, s.bullets, y + LOOK["section_gap"], pt=LOOK["question_pt"])


def _render_answer(page, s) -> None:
    y = _type_label(page, "answer", Y) + STYLE["block_gap"]
    y = _heading(page, s.heading, y)
    _body(page, s.paragraphs, s.bullets, y + STYLE["block_gap"])


def _render_checklist(page, s) -> None:
    y = _heading(page, s.heading, Y) + STYLE["block_gap"]
    y = _body(page, s.paragraphs, s.bullets, y)
    pt, box, indent = LOOK["list_pt"], LOOK["check_box"], LOOK["check_indent"]
    line = _line_h(pt)
    y += STYLE["block_gap"]
    for (text,) in s.items.get("check", []):
        h = _rows(text, _per_line(W - indent, pt)) * line + 0.05
        page.box("check-box", X, y + (line - box) / 2, box, box, fill=STYLE["white"],
                 line=(STYLE["bar"], 2), kind=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.15)
        page.box("check-text", X + indent, y, W - indent, h, [_p(text, pt, STYLE["text"])])
        y += h + LOOK["check_gap"]


def _display_url(href: str, per_line: int) -> str:
    """The address as shown: host and path when they fit on one line, else
    the host alone. The run links to the full address either way."""
    parts = urlsplit(href)
    full = _host(href) + parts.path.rstrip("/")
    if parts.query:
        full += f"?{parts.query}"
    if parts.fragment:
        full += f"#{parts.fragment}"
    return full if len(full) <= per_line else _host(href)


def _render_links(page, s) -> None:
    y = _heading(page, s.heading, Y) + STYLE["block_gap"]
    y = _body(page, s.paragraphs, s.bullets, y)
    if s.paragraphs or s.bullets:
        y += STYLE["block_gap"]
    links = s.items.get("link", [])
    # Up to four links take one column; more fill a left column first, then
    # a right one, so the list still reads top to bottom.
    cols = 1 if len(links) <= 4 else 2
    per_col = math.ceil(len(links) / cols)
    gap = LOOK["link_col_gap"]
    cw = (W - gap * (cols - 1)) / cols
    npt, upt = LOOK["link_name_pt"], LOOK["link_url_pt"]
    # Each link is one box, its name and then its address, so the address
    # follows the name's last line however the name actually wraps. Boxes in
    # one row share the row's tallest height, so the columns line up.
    cells = []
    for name, url in links:
        href = urljoin(SITE, url)
        h = (_rows(name, _per_line(cw, npt, bold=True)) * _line_h(npt)
             + _line_h(upt) + 0.1)
        cells.append((name, href, _display_url(href, _per_line(cw, upt)), h))
    row_hs = [max(c[3] for c in cells[row::per_col]) for row in range(per_col)]
    for i, (name, href, shown, _h) in enumerate(cells):
        col, row = divmod(i, per_col)
        top = y + sum(row_hs[:row]) + LOOK["link_gap"] * row
        page.box("link", X + col * (cw + gap), top, cw, row_hs[row], [
            [_Run(name, npt, STYLE["heading"], bold=True, link=href)],
            [_Run(shown, upt, STYLE["bar"], link=href)],
        ])


def _not_implemented(page, s) -> None:
    raise LayoutError(f"{s.where}: layout {s.layout} is not implemented yet")


RENDERERS = {
    "text": _render_text,
    "stats": _render_stats,
    "stage": _render_stage,
    "background": _render_background,
    "question": _render_question,
    "answer": _render_answer,
    "checklist": _render_checklist,
    "links": _render_links,
    "flow": _not_implemented,
    "layers": _not_implemented,
    "timeline": _not_implemented,
    "compare": _not_implemented,
    "table": _not_implemented,
    "bars": _not_implemented,
    "matrix": _not_implemented,
}


# ---------------------------------------------------------------------------
# The generated slides. Each takes its page alone: the deck it describes is
# page.deck.
# ---------------------------------------------------------------------------


def _render_cover(page) -> None:
    deck = page.deck
    x, w, y = 0.9, 11.5, 1.2
    tpt, ppt, lpt = STYLE["cover_title_pt"], STYLE["cover_promise_pt"], STYLE["cover_line_pt"]
    th = _rows(deck.title, STYLE["cover_title_chars_per_line"]) * _line_h(tpt, heading=True) + 0.1
    page.box("title", x, y, w, th,
             [_p(deck.title, tpt, STYLE["white"], font="heading_font", bold=True)])
    y += th + 0.3
    ph = _rows(deck.promise, STYLE["cover_promise_chars_per_line"]) * _line_h(ppt) + 0.1
    page.box("promise", x, y, w, ph, [_p(deck.promise, ppt, STYLE["light"])])
    y += ph + 0.4
    line_h = _line_h(lpt) + 0.1
    for name, text, color in (
        ("as-of", f"Reflects the csoh.org kill chain as of {deck.as_of}", STYLE["light"]),
        ("attribution", ATTRIBUTION, STYLE["accent"]),
        ("license", LICENSE_LINE, STYLE["light"]),
    ):
        page.box(name, x, y, w, line_h, [_p(text, lpt, color)])
        y += line_h + 0.05


def _render_how_to_use(page) -> None:
    deck = page.deck
    y = _heading(page, HOW_TO_HEADING, Y)
    paras = [
        "Read it on your own or present it. Every fact about the incident comes from "
        "the csoh.org kill chain and the sources it cites.",
        "Slides marked Background explain a general idea and name their own source. "
        "The speaker notes are a presenter's script.",
        f"Full kill chain: csoh.org/{deck.page}. These slides reflect it as of {deck.as_of}.",
    ]
    _body(page, paras, [], y + STYLE["block_gap"])


def _render_closing(page) -> None:
    url = f"{SITE}{page.deck.page}"
    y = _heading(page, CLOSING_HEADING, Y) + STYLE["block_gap"]
    lead = "Every step, source and defense in detail: "
    pt, color = STYLE["body_pt"], STYLE["text"]
    h = _block_h([lead + url, CLOSING_LICENSE], W, pt)
    paras = [
        [_Run(lead, pt, color), _Run(url, pt, STYLE["bar"], link=url)],
        _p(CLOSING_LICENSE, pt, color),
    ]
    page.box("body", X, y, W, h, paras, gap=LOOK["para_gap"])


def _generated(prs, deck, which: str, draw, n: int, total: int, dark: bool = False) -> None:
    page = _Page(prs, deck, f"{deck.slug}.deck ({which})", dark=dark)
    draw(page)
    page.footer(n, total)
    page.notes([])


def _content(prs, deck, s, n: int, total: int) -> None:
    page = _Page(prs, deck, s.where, dark=s.layout in DARK_LAYOUTS)
    _credits(page, s)
    RENDERERS[s.layout](page, s)
    page.footer(n, total)
    page.notes(s.notes)


def render_deck(deck, out: Path) -> Path:
    """Write deck as a .pptx at out: a generated cover and "how to use this
    deck", the outline's slides, a generated closing. Raises LayoutError
    before writing if any element would end below the room it has."""
    prs = Presentation()
    prs.slide_width = Emu(SLIDE_W_EMU)
    prs.slide_height = Emu(SLIDE_H_EMU)
    total = len(deck.slides) + GENERATED
    _generated(prs, deck, "cover", _render_cover, 1, total, dark=True)
    _generated(prs, deck, "how to use", _render_how_to_use, 2, total)
    for n, s in enumerate(deck.slides, start=3):
        _content(prs, deck, s, n, total)
    _generated(prs, deck, "closing", _render_closing, total, total)
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    return out


# ---------------------------------------------------------------------------
# Verification of the saved file.
# ---------------------------------------------------------------------------


def _solid(shape) -> str | None:
    fill = getattr(shape, "fill", None)
    if fill is None or fill.type != MSO_FILL.SOLID:
        return None
    return str(fill.fore_color.rgb).lower()


def _fill_behind(shapes: list, i: int, bg: str) -> str:
    """The colour text in shapes[i] sits on: the shape's own fill, else the
    fill of the nearest shape below it in z-order that covers its centre,
    else the slide background."""
    own = _solid(shapes[i])
    if own:
        return own
    sh = shapes[i]
    cx, cy = sh.left + sh.width // 2, sh.top + sh.height // 2
    for under in reversed(shapes[:i]):
        fill = _solid(under)
        covers = (under.left <= cx <= under.left + under.width
                  and under.top <= cy <= under.top + under.height)
        if fill and covers:
            return fill
    return bg


def _kind_problem(shape) -> str | None:
    kind = shape.shape_type
    if kind == MSO_SHAPE_TYPE.TEXT_BOX:
        return None
    if kind == MSO_SHAPE_TYPE.AUTO_SHAPE:
        auto = shape.auto_shape_type
        return None if auto in ALLOWED_AUTOSHAPES else f"a {auto} shape"
    return f"a {kind}"


def _run_findings(tag: str, shape, behind: str) -> list[str]:
    out = []
    floor = LOOK["small_floor_pt"] if shape.name in SMALL_SHAPES else LOOK["body_floor_pt"]
    for p in shape.text_frame.paragraphs:
        for run in p.runs:
            if not run.text.strip():
                continue
            size = run.font.size.pt if run.font.size is not None else None
            if size is None or size < floor:
                out.append(f"{tag}: {shape.name} run is {size} pt, below {floor}")
            color = run.font.color
            if color.type != MSO_COLOR_TYPE.RGB:
                out.append(f"{tag}: {shape.name} run has no colour of its own")
                continue
            ratio = contrast(str(color.rgb), behind)
            if ratio < LOOK["min_contrast"]:
                out.append(
                    f"{tag}: {shape.name} run contrast {ratio:.2f}:1 against {behind}, "
                    f"below {LOOK['min_contrast']}"
                )
    return out


def _slide_findings(tag: str, slide, n: int, total: int, page: str, outline) -> list[str]:
    findings: list[str] = []
    limit = Inches(STYLE["bottom_limit"]) + EMU_SLACK
    bg = _solid(slide.background) or STYLE["bg"]
    shapes = list(slide.shapes)
    named: dict[str, list] = {}
    for i, sh in enumerate(shapes):
        named.setdefault(sh.name, []).append(sh)
        kind = _kind_problem(sh)
        if kind:
            findings.append(
                f"{tag}: shape {sh.name!r} is {kind}; only text boxes, rectangles, rounded "
                "rectangles, ovals, chevrons and right and down arrows survive conversion"
            )
        if sh.name not in UNTRACKED and sh.top + sh.height > limit:
            findings.append(f"{tag}: {sh.name} ends below {STYLE['bottom_limit']} in")
        if sh.left < 0 or sh.left + sh.width > SLIDE_W_EMU + EMU_SLACK:
            findings.append(f"{tag}: {sh.name} runs off the side of the slide")
        if not sh.has_text_frame:
            continue
        tf = sh.text_frame
        if tf.auto_size not in (None, MSO_AUTO_SIZE.NONE):
            findings.append(f"{tag}: {sh.name} uses autofit, which the converter drops")
        if any(d in tf.text for d in FORBIDDEN_DASHES):
            findings.append(f"{tag}: en or em dash in {sh.name}")
        findings += _run_findings(tag, sh, _fill_behind(shapes, i, bg))

    for name, want in (("footer-left", f"csoh.org/{page}"), ("footer-right", f"{n} / {total}")):
        got = [sh.text_frame.text for sh in named.get(name, [])]
        if got != [want]:
            shown = repr(got[0]) if len(got) == 1 else f"on {len(got)} shapes"
            findings.append(f"{tag}: {name} is {shown}, expected {want!r}")

    notes = slide.notes_slide.notes_text_frame.text if slide.has_notes_slide else ""
    if not notes.strip():
        findings.append(f"{tag}: no speaker notes")
    elif any(d in notes for d in FORBIDDEN_DASHES):
        findings.append(f"{tag}: en or em dash in the speaker notes")

    if outline is not None:
        want = TYPE_LABELS.get(outline.layout)
        got = [sh.text_frame.text for sh in named.get("type-label", [])]
        if want and got != [want]:
            shown = repr(got[0]) if len(got) == 1 else f"on {len(got)} shapes"
            findings.append(f"{tag}: type label is {shown}, expected {want!r}")
        elif not want and got:
            findings.append(f"{tag}: a {outline.layout} slide carries a type label {got!r}")
        if outline.layout == "background" and outline.source:
            credit = " ".join(sh.text_frame.text for sh in named.get("credit", []))
            if outline.source[0] not in credit:
                findings.append(f"{tag}: credit does not name its source {outline.source[0]!r}")
    return findings


def reopen(path: Path):
    """The saved presentation, read back."""
    return Presentation(str(path))


def verify_pptx(path: Path, deck) -> list[str]:
    """Reopen the saved file and return every finding: the slide count and
    size; per slide, shape kinds, bottoms and sides, autofit, run sizes
    (18 pt body, 14 pt labels), contrast of every run against what it sits
    on, dashes, the footer, the notes, and the type label and source line
    that background and discussion slides carry."""
    prs = reopen(path)
    findings: list[str] = []
    want = len(deck.slides) + GENERATED
    if len(prs.slides) != want:
        findings.append(f"{path.name}: {len(prs.slides)} slides, expected {want}")
    if (prs.slide_width, prs.slide_height) != (SLIDE_W_EMU, SLIDE_H_EMU):
        findings.append(f"{path.name}: slide size is not 13.333 x 7.5 in")
    # Outline slide i (counting from 0) is file slide i + 3 (counting from 1):
    # the cover and "how to use" come first.
    outline = {i + 3: s for i, s in enumerate(deck.slides)}
    for n, slide in enumerate(prs.slides, start=1):
        findings += _slide_findings(
            f"{path.name} slide {n}", slide, n, want, deck.page, outline.get(n)
        )
    return findings
