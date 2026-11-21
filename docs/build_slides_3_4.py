# -*- coding: utf-8 -*-
"""Build slides 3 (Technical Approach) and 4 (Working Prototype) for NexussAI.

Edits the team deck in place (copy of "7,8,9 Edited ppt.pptx"), keeping the
official template placeholders, footers and slide numbers untouched, and every
headline exactly as briefed.

Numbers are read from the frozen prototype run in data/linesight.db:
523,869 samples, 808 downtime events, 3 machines, 65.1% line OEE.

Run:  python docs/build_slides_3_4.py
"""

from pathlib import Path

from PIL import Image
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

SRC = Path(r"C:\Users\abini\Downloads\7,8,9 Edited ppt.pptx")
OUT = Path(r"C:\Users\abini\Downloads\NexussAI_LineSight_R2_Deck.pptx")
SHOTS = Path(r"C:\Users\abini\OneDrive\Desktop\LineSight\docs\shots")

ACCENT = RGBColor(0xFF, 0x33, 0x00)
ACCENT_SOFT = RGBColor(0xFF, 0xEE, 0xE8)
INK = RGBColor(0x11, 0x11, 0x11)
BODY = RGBColor(0x33, 0x33, 0x33)
MUTED = RGBColor(0x6B, 0x6B, 0x6B)
LINE = RGBColor(0xE2, 0xE2, 0xE2)
PANEL = RGBColor(0xF7, 0xF7, 0xF7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOOD = RGBColor(0x1B, 0x7F, 0x3B)

FONT = "Arial"


# ------------------------------------------------------------------ primitives
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
         align=PP_ALIGN.LEFT, italic=False, before=0, line=None, space=None):
    p = tf.paragraphs[0] if first else tf.add_paragraph()
    p.alignment = align
    p.space_after = Pt(after)
    p.space_before = Pt(before)
    if line:
        p.line_spacing = line
    run = p.add_run()
    run.text = text
    f = run.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = color
    if space is not None:
        run.font._rPr.set("spc", str(int(space * 100)))
    return p


def rect(slide, x, y, w, h, fill=PANEL, line=None, radius=0.06, shape=None):
    shp = slide.shapes.add_shape(
        shape or MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    if shape is None:
        try:
            shp.adjustments[0] = radius
        except Exception:
            pass
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(1)
    shp.shadow.inherit = False
    shp.text_frame.word_wrap = True
    return shp


def rule(slide, x, y, w, h=0.045, color=ACCENT):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = color
    shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def badge(slide, x, y, d, text, size=8, fill=ACCENT):
    shp = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background()
    shp.shadow.inherit = False
    tf = shp.text_frame
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    para(tf, text, size=size, bold=True, color=WHITE, first=True, after=0,
         align=PP_ALIGN.CENTER)
    return shp


def fit(path, x, y, w, h):
    """Fit an image inside a box, preserving aspect ratio, centred."""
    iw, ih = Image.open(path).size
    ar = iw / ih
    if w / h > ar:
        nh, nw = h, h * ar
    else:
        nw, nh = w, w / ar
    return x + (w - nw) / 2, y + (h - nh) / 2, nw, nh


def shot(slide, name, x, y, w, h, border=True):
    path = SHOTS / name
    if border:
        rect(slide, x, y, w, h, fill=WHITE, line=LINE, radius=0.02)
    l, t, iw, ih = fit(path, x + 0.02, y + 0.02, w - 0.04, h - 0.04)
    slide.shapes.add_picture(str(path), Inches(l), Inches(t), Inches(iw), Inches(ih))


def drop_shape(shape):
    shape._element.getparent().remove(shape._element)


def find(slide, name):
    for sh in slide.shapes:
        if sh.name == name:
            return sh
    return None


# --------------------------------------------------------------------- slide 3
def build_technical(slide):
    # template hint box removed, title placeholder left exactly as printed
    hint = find(slide, "Rectangle 4")
    if hint is not None:
        drop_shape(hint)

    stack = tb(slide, 0.55, 1.24, 8.92, 0.26)
    para(stack.text_frame,
         "Python  ·  FastAPI + uvicorn  ·  SQLite (WAL)  ·  pymodbus  ·  "
         "server-rendered HTML + inline SVG        —  every layer on one plant PC",
         size=9, color=MUTED, first=True, after=0)

    cards = [
        ("01", "CAPTURE", "Modbus TCP in,\none row per second",
         ["3 machines · 9 register tags at 1 Hz",
          "No vendor driver, no gateway licence",
          "Simulator speaks the same register map"]),
        ("02", "CLASSIFY", "Every stop\ngets a cause",
         ["Coils + cycle pulse, not guesswork",
          "5 categories, each with a confidence",
          "No evidence → UNKNOWN, never invented"]),
        ("03", "STORE", "One file holds\nthe whole history",
         ["SQLite WAL · 523,869 samples",
          "808 stop events, 5 causes",
          "No database server, no cloud"]),
        ("04", "SERVE", "OEE and loss tree,\nserved live",
         ["ISO 22400-2: A × P × Q",
          "Configurable KPIs, 1 h / 8 h / 24 h",
          "PDF + CSV export, zero build step"]),
    ]

    cw, gap, ch, cy = 1.93, 0.40, 2.28, 1.60
    for i, (num, kicker, title, bullets) in enumerate(cards):
        x = 0.55 + i * (cw + gap)
        rect(slide, x, cy, cw, ch, fill=WHITE, line=LINE, radius=0.05)
        rect(slide, x, cy + 0.14, 0.05, ch - 0.28, fill=ACCENT, shape=MSO_SHAPE.RECTANGLE)

        k = tb(slide, x + 0.20, cy + 0.16, cw - 0.32, 0.20)
        para(k.text_frame, f"{num} · {kicker}", size=7.5, bold=True, color=ACCENT,
             first=True, after=0, space=1.2)

        t = tb(slide, x + 0.20, cy + 0.40, cw - 0.32, 0.62)
        tf = t.text_frame
        for j, line in enumerate(title.split("\n")):
            para(tf, line, size=11.5, bold=True, color=INK, first=(j == 0), after=0, line=0.92)

        rule(slide, x + 0.20, cy + 1.06, 0.42, 0.035, ACCENT)

        b = tb(slide, x + 0.20, cy + 1.18, cw - 0.34, ch - 1.28)
        for j, line in enumerate(bullets):
            para(b.text_frame, "•  " + line, size=8, color=BODY, first=(j == 0),
                 after=5, line=1.02)

        if i < 3:
            ch_x = x + cw + 0.07
            ch_y = cy + ch / 2 - 0.13
            arrow = slide.shapes.add_shape(MSO_SHAPE.CHEVRON, Inches(ch_x), Inches(ch_y),
                                           Inches(0.26), Inches(0.26))
            arrow.fill.solid()
            arrow.fill.fore_color.rgb = ACCENT
            arrow.line.fill.background()
            arrow.shadow.inherit = False

    # trace band
    by = 4.06
    rect(slide, 0.55, by, 8.92, 0.92, fill=PANEL, line=None, radius=0.04)
    lab = tb(slide, 0.72, by + 0.10, 3.9, 0.18)
    para(lab.text_frame, "READ FROM THE LINE · 9 TAGS", size=7, bold=True, color=MUTED,
         first=True, after=0, space=1.0)
    sig = tb(slide, 0.72, by + 0.30, 4.1, 0.50)
    para(sig.text_frame,
         "run · fault · planned · alarm · parts · good · last cycle · ideal cycle · clock",
         size=8, color=INK, first=True, after=0, line=1.15)

    vline = rect(slide, 4.95, by + 0.14, 0.012, 0.64, fill=LINE, shape=MSO_SHAPE.RECTANGLE)

    lab2 = tb(slide, 5.16, by + 0.10, 4.0, 0.18)
    para(lab2.text_frame, "WHAT IT BECOMES", size=7, bold=True, color=MUTED,
         first=True, after=0, space=1.0)
    der = tb(slide, 5.16, by + 0.30, 4.15, 0.52)
    para(der.text_frame,
         "machine state → stop cause + confidence → A, P, Q → OEE → loss tree → "
         "alert → shift report",
         size=8, color=INK, first=True, after=0, line=1.15)

    # why it holds
    why = [
        ("OFFLINE-FIRST", "0 cloud calls",
         "Collector, database and dashboard all run on the plant PC. An air-gapped line keeps reporting."),
        ("PLC-AGNOSTIC", "any Modbus TCP source",
         "Register map, units and ideal cycle live in config — a new machine is a config change, not code."),
        ("DEPLOYABLE IN A SHIFT", "2 commands",
         "python -m linesight.collect, then linesight.web, on a ₹4,000 mini-PC. "
         "No licence, no per-seat fee, first KPI in minutes."),
    ]
    cy2, ch2 = 5.14, 1.62
    for i, (kicker, metric, body) in enumerate(why):
        x = 0.55 + i * (2.87 + 0.16)
        rect(slide, x, cy2, 2.87, ch2, fill=WHITE, line=LINE, radius=0.05)
        k = tb(slide, x + 0.18, cy2 + 0.14, 2.55, 0.18)
        para(k.text_frame, kicker, size=7.5, bold=True, color=ACCENT, first=True,
             after=0, space=1.2)
        m = tb(slide, x + 0.18, cy2 + 0.36, 2.55, 0.26)
        para(m.text_frame, metric, size=13, bold=True, color=INK, first=True, after=0)
        bd = tb(slide, x + 0.18, cy2 + 0.72, 2.52, 0.80)
        para(bd.text_frame, body, size=8, color=MUTED, first=True, after=0, line=1.1)


# --------------------------------------------------------------------- slide 4
def build_prototype(slide, template_slide):
    blank = find(slide, "Text Placeholder 2")
    if blank is not None:
        drop_shape(blank)

    title = find(slide, "Title 1")
    ref = find(template_slide, "Title 1")
    if title is not None and not title.text_frame.text.strip():
        # inherit the template title's type, colour and alignment: only set the words
        if ref is not None:
            title.left, title.top = ref.left, ref.top
            title.width, title.height = ref.width, ref.height
        title.text_frame.text = "Working Prototype"

    sub = tb(slide, 0.55, 1.22, 8.92, 0.24)
    para(sub.text_frame,
         "Not a mock-up: these are screens from the running build — 3 machines, one shift, "
         "captured 04 Nov 2026.",
         size=9, color=MUTED, first=True, after=0)

    # hero
    hx, hy, hw, hh = 0.55, 1.56, 5.32, 3.33
    shot(slide, "live.png", hx, hy, hw, hh)
    badge(slide, 0.20, hy + hh / 2 - 0.12, 0.24, "1", size=9)

    # right column
    shot(slide, "oee.png", 6.12, 1.56, 3.34, 2.09)
    badge(slide, 9.50, 1.56 + 2.09 / 2 - 0.12, 0.24, "2", size=9)
    shot(slide, "report.png", 6.12, 3.78, 3.34, 2.09)
    badge(slide, 9.50, 3.78 + 2.09 / 2 - 0.12, 0.24, "3", size=9)

    # callouts under hero
    notes = [
        ("1", "Live fault banner names the machine, the alarm and how long it has been down — "
              "the same sentence the supervisor needs."),
        ("2", "Signal age shows 1 s. If a tag stops arriving the card says so instead of freezing a stale delta."),
        ("3", "Three OEE factors per machine, five loss buckets, then the one-page shift report with PDF + CSV export."),
    ]
    ny = 5.00
    for num, text in notes:
        badge(slide, 0.57, ny + 0.02, 0.20, num, size=7.5, fill=ACCENT)
        t = tb(slide, 0.86, ny, 4.98, 0.26)
        para(t.text_frame, text, size=7.5, color=BODY, first=True, after=0, line=1.05)
        ny += 0.28

    # KPI strip
    sy, sh = 5.94, 0.84
    rect(slide, 0.55, sy, 8.92, sh, fill=INK, line=None, radius=0.03)
    stats = [
        ("3", "machines\npolled at 1 Hz"),
        ("523,869", "signal samples\nstored (SQLite WAL)"),
        ("808", "stops auto-classified\nwith confidence"),
        ("65.1%", "line OEE, last 8 h\n(65% target)"),
    ]
    for i, (big, small) in enumerate(stats):
        x = 0.55 + i * 2.23
        b = tb(slide, x + 0.18, sy + 0.13, 2.0, 0.34)
        para(b.text_frame, big, size=17, bold=True, color=WHITE, first=True, after=0)
        s = tb(slide, x + 0.18, sy + 0.47, 2.02, 0.30)
        for j, line in enumerate(small.split("\n")):
            para(s.text_frame, line, size=7, color=RGBColor(0xC9, 0xC9, 0xC9),
                 first=(j == 0), after=0, line=0.95)
        if i < 3:
            rect(slide, x + 2.10, sy + 0.16, 0.008, sh - 0.32, fill=RGBColor(0x44, 0x44, 0x44),
                 shape=MSO_SHAPE.RECTANGLE)


def notes(slide, text):
    frame = slide.notes_slide.notes_text_frame
    frame.text = text


NOTES_3 = (
    "Architecture in one breath. Three Modbus TCP machines are polled at 1 Hz by one "
    "collector, which writes raw samples straight into a single SQLite file. A classifier "
    "turns coil and cycle-pulse transitions into stop events, each with a category and a "
    "confidence. FastAPI reads that file and renders every page server-side, so there is no "
    "build step and no internet dependency. Every number on the dashboard traces back to a "
    "row in that file.")

NOTES_4 = (
    "Everything on this slide is the running build, captured on 4 November. Left, the live "
    "floor: the fault banner names the machine, the alarm and the elapsed time. Right, the OEE "
    "page with the ISO 22400-2 three-factor split and the loss tree, and the shift report that "
    "exports to PDF and CSV. The numbers in the strip are the last eight-hour window: 3 "
    "machines, 523,869 samples, 808 stops classified, 65.1 percent line OEE against a 65 "
    "percent target. The 45.3 percent in the one-hour box on the live screen is that same "
    "line while CNC-02 is down on a hydraulic pressure fault, which is exactly the visibility "
    "the plant does not have today.")


def main():
    prs = Presentation(str(SRC))
    assert len(prs.slides) == 10, len(prs.slides)
    build_technical(prs.slides[2])
    build_prototype(prs.slides[3], prs.slides[2])
    notes(prs.slides[2], NOTES_3)
    notes(prs.slides[3], NOTES_4)
    prs.save(str(OUT))
    print("wrote:", OUT)


if __name__ == "__main__":
    main()
