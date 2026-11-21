# -*- coding: utf-8 -*-
"""Build slides 3 (Technical Approach) and 4 (Working Prototype).

Slide 3: the Figma architecture graphic (8 stages, snake flow, what each stage
does) plus a summary banner.
Slide 4: the same composition as before -- hero screen, two stacked screens,
numbered callouts, KPI strip -- recoloured to the orange/peach language of the
team's slides 7, 8 and 9. Geometry is unchanged from the previous revision.

Run:  python docs/build_slides_warm.py
"""

from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

SRC = Path(r"C:\Users\abini\Downloads\7,8,9 Edited ppt.pptx")
OUT = Path(r"C:\Users\abini\Downloads\NexussAI_LineSight_R2_Deck.pptx")
FALLBACK = Path(r"C:\Users\abini\Downloads\NexussAI_LineSight_R2_Deck_warm.pptx")
SHOTS = Path(r"C:\Users\abini\OneDrive\Desktop\LineSight\docs\shots")
ARCH = Path(r"C:\Users\abini\OneDrive\Desktop\LineSight\docs\figma\architecture.png")

ORANGE = RGBColor(0xF7, 0x96, 0x46)
ORANGE_DEEP = RGBColor(0xC5, 0x5A, 0x11)
PEACH = RGBColor(0xFC, 0xD5, 0xB5)
PEACH_LIGHT = RGBColor(0xFD, 0xE8, 0xD8)
PEACH_DIV = RGBColor(0xE9, 0xB5, 0x8C)
INK = RGBColor(0x11, 0x11, 0x11)
BODY = RGBColor(0x33, 0x33, 0x33)
MUTED = RGBColor(0x6B, 0x6B, 0x6B)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

FONT = "Arial"


# ----------------------------------------------------------------- primitives
def tb(slide, x, y, w, h, anchor=MSO_ANCHOR.TOP):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    return box


def para(tf, text, size=9, bold=False, color=BODY, after=2, first=False,
         align=PP_ALIGN.LEFT, line=None, space=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(after)
    if line:
        p.line_spacing = line
    run = p.add_run()
    run.text = text
    f = run.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    if space is not None:
        run.font._rPr.set("spc", str(int(space * 100)))
    return p


def soft_shadow(shape, blur=0.06, dist=0.02, alpha=0.14):
    shape.shadow.inherit = False
    effect = shape._element.spPr.find(qn("a:effectLst"))
    shd = etree.SubElement(effect, qn("a:outerShdw"))
    shd.set("blurRad", str(int(Inches(blur))))
    shd.set("dist", str(int(Inches(dist))))
    shd.set("dir", "5400000")
    shd.set("algn", "ctr")
    shd.set("rotWithShape", "0")
    clr = etree.SubElement(shd, qn("a:srgbClr"))
    clr.set("val", "000000")
    a = etree.SubElement(clr, qn("a:alpha"))
    a.set("val", str(int(alpha * 100000)))


def circle(slide, x, y, d, fill=ORANGE):
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y),
                                 Inches(d), Inches(d))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    tf = shp.text_frame
    tf.word_wrap = False
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    soft_shadow(shp, blur=0.03, dist=0.012, alpha=0.15)
    return shp


def badge(slide, x, y, d, text, size=7.5):
    shp = circle(slide, x, y, d)
    para(shp.text_frame, text, size=size, bold=True, color=WHITE, first=True,
         after=0, align=PP_ALIGN.CENTER)
    return shp


def banner(slide, x, y, w, h, text, size=11):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                 Inches(x), Inches(y), Inches(w), Inches(h))
    shp.adjustments[0] = 0.30
    fill = shp.fill
    fill.gradient()
    stops = fill.gradient_stops
    stops[0].color.rgb = PEACH_LIGHT
    stops[0].position = 0.0
    stops[1].color.rgb = PEACH
    stops[1].position = 1.0
    shp.line.color.rgb = ORANGE_DEEP
    shp.line.width = Pt(1.25)
    tf = shp.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = Inches(0.2)
    tf.margin_right = Inches(0.2)
    tf.margin_top = 0
    tf.margin_bottom = 0
    soft_shadow(shp, blur=0.04, dist=0.015, alpha=0.12)
    para(tf, text, size=size, bold=True, color=INK, first=True, after=0,
         align=PP_ALIGN.CENTER, space=0.4)
    return shp


def shot(slide, name, x, y, w, h):
    p = slide.shapes.add_picture(str(SHOTS / name), Inches(x), Inches(y),
                                 Inches(w), Inches(h))
    p.line.color.rgb = ORANGE
    p.line.width = Pt(1.25)
    return p


def find(slide, name):
    for sh in slide.shapes:
        if sh.name == name:
            return sh
    return None


def drop(shape):
    shape._element.getparent().remove(shape._element)


def heading(slide, text):
    """Keep the placeholder's own type (same as slides 7-9), centre it."""
    title = find(slide, "Title 1")
    if title is None:
        return None
    tf = title.text_frame
    tf.text = text
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    return title


# --------------------------------------------------------------------- slide 3
def build_technical(slide):
    hint = find(slide, "Rectangle 4")
    if hint is not None:
        drop(hint)

    heading(slide, "Technical Approach")

    sub = tb(slide, 0.50, 1.17, 9.00, 0.24)
    para(sub.text_frame,
         "Eight stages, one process: PLC coil  →  stop cause  →  OEE  →  "
         "the sentence a supervisor acts on.",
         size=9.5, color=MUTED, first=True, after=0, align=PP_ALIGN.CENTER)

    # Figma sheet, 1800 x 1070 -> 9.00 x 5.35 at 2x
    slide.shapes.add_picture(str(ARCH), Inches(0.50), Inches(1.44),
                             Inches(9.00), Inches(5.35))


# --------------------------------------------------------------------- slide 4
def build_prototype(slide, template_slide):
    blank = find(slide, "Text Placeholder 2")
    if blank is not None:
        drop(blank)

    title = find(slide, "Title 1")
    ref = find(template_slide, "Title 1")
    if title is not None and ref is not None:
        title.left, title.top = ref.left, ref.top
        title.width, title.height = ref.width, ref.height
    heading(slide, "Working Prototype")

    sub = tb(slide, 0.55, 1.22, 8.92, 0.24)
    para(sub.text_frame,
         "Not a mock-up: these are screens from the running build — 3 machines, "
         "one shift, captured 04 Nov 2026.  ·  live demo: linesight-olive.vercel.app",
         size=9, color=MUTED, first=True, after=0)

    # geometry unchanged from the previous revision
    hx, hy, hw, hh = 0.55, 1.56, 5.32, 3.33
    shot(slide, "live.png", hx, hy, hw, hh)
    badge(slide, 0.20, hy + hh / 2 - 0.12, 0.24, "1", size=9)

    shot(slide, "oee.png", 6.12, 1.56, 3.34, 2.09)
    badge(slide, 9.50, 1.56 + 2.09 / 2 - 0.12, 0.24, "2", size=9)

    shot(slide, "report.png", 6.12, 3.78, 3.34, 2.09)
    badge(slide, 9.50, 3.78 + 2.09 / 2 - 0.12, 0.24, "3", size=9)

    notes = [
        ("1", "Live fault banner names the machine, the alarm and how long it has been down — "
              "the same sentence the supervisor needs."),
        ("2", "Signal age shows 1 s. If a tag stops arriving the card says so instead of freezing a stale delta."),
        ("3", "Three OEE factors per machine, five loss buckets, then the one-page shift report with PDF + CSV export."),
    ]
    ny = 5.00
    for num, text in notes:
        badge(slide, 0.57, ny + 0.02, 0.20, num, size=7.5)
        t = tb(slide, 0.86, ny, 4.98, 0.26)
        para(t.text_frame, text, size=7.5, color=BODY, first=True, after=0,
             line=1.05)
        ny += 0.28

    # KPI strip -- same box, recoloured to peach
    sx, sy, sw, sh = 0.55, 5.94, 8.92, 0.84
    strip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(sx),
                                   Inches(sy), Inches(sw), Inches(sh))
    strip.adjustments[0] = 0.12
    fill = strip.fill
    fill.gradient()
    stops = fill.gradient_stops
    stops[0].color.rgb = PEACH_LIGHT
    stops[0].position = 0.0
    stops[1].color.rgb = PEACH
    stops[1].position = 1.0
    strip.line.color.rgb = ORANGE_DEEP
    strip.line.width = Pt(1.25)
    soft_shadow(strip, blur=0.04, dist=0.015, alpha=0.12)

    stats = [
        ("3", "machines\npolled at 1 Hz"),
        ("523,869", "signal samples\nstored (SQLite WAL)"),
        ("808", "stops auto-classified\nwith confidence"),
        ("65.1%", "line OEE, last 8 h\n(65% target)"),
    ]
    for i, (big, small) in enumerate(stats):
        x = sx + i * 2.23
        b = tb(slide, x + 0.18, sy + 0.13, 2.0, 0.34)
        para(b.text_frame, big, size=17, bold=True, color=INK, first=True,
             after=0)
        s = tb(slide, x + 0.18, sy + 0.47, 2.02, 0.30)
        for j, line in enumerate(small.split("\n")):
            para(s.text_frame, line, size=7, color=BODY, first=(j == 0),
                 after=0, line=0.95)
        if i < 3:
            div = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE,
                                         Inches(x + 2.10), Inches(sy + 0.16),
                                         Inches(0.008), Inches(sh - 0.32))
            div.fill.solid()
            div.fill.fore_color.rgb = PEACH_DIV
            div.line.fill.background()


NOTES_3 = (
    "Architecture in one breath. Three Modbus TCP machines are polled at 1 Hz by one "
    "collector, which writes raw samples straight into a single SQLite file. A classifier "
    "turns coil and cycle-pulse transitions into stop events, each with a category and a "
    "confidence. Analytics applies ISO 22400-2, FastAPI renders every page server-side, and "
    "the output is the fault banner, the shift report and the MCP tools. Every number on the "
    "dashboard traces back to a row in that file.")

NOTES_4 = (
    "Everything on this slide is the running build, captured on 4 November. Left, the live "
    "floor: the fault banner names the machine, the alarm and the elapsed time. Right, the OEE "
    "page with the ISO 22400-2 three-factor split and the loss tree, and the shift report that "
    "exports to PDF and CSV. The strip is the last eight-hour window: 3 machines, 523,869 "
    "samples, 808 stops classified, 65.1 percent line OEE against a 65 percent target.")


def set_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


def add_links(slide):
    thanks = None
    for sh in slide.shapes:
        if sh.has_text_frame and "Thank" in sh.text_frame.text:
            thanks = sh
            break
    if thanks is not None:
        x = thanks.left.inches
        y = thanks.top.inches + thanks.height.inches + 0.25
        w = thanks.width.inches
    else:
        x, y, w = 1.42, 3.6, 6.68
    box = tb(slide, x, y, w, 0.9)
    para(box.text_frame, "Live demo:   linesight-olive.vercel.app", size=12, bold=True,
         color=ORANGE_DEEP, first=True, after=2, align=PP_ALIGN.CENTER)
    para(box.text_frame, "GitHub:   <paste your repo URL here>", size=11, color=MUTED,
         after=0, align=PP_ALIGN.CENTER)


def main():
    prs = Presentation(str(SRC))
    assert len(prs.slides) == 10, len(prs.slides)
    build_technical(prs.slides[2])
    build_prototype(prs.slides[3], prs.slides[2])
    add_links(prs.slides[9])
    set_notes(prs.slides[2], NOTES_3)
    set_notes(prs.slides[3], NOTES_4)

    try:
        prs.save(str(OUT))
        print("wrote:", OUT)
    except PermissionError:
        prs.save(str(FALLBACK))
        print("deck open in PowerPoint, wrote:", FALLBACK)


if __name__ == "__main__":
    main()
