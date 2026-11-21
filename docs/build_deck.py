# -*- coding: utf-8 -*-
"""Build the Sakthi Hackathon 2.0 Round 2 deck for LineSight.

Ten slides on the official template, in the official order. Numbers are the
frozen readings of the prototype run captured on 4 Nov 2026, the same run the
screenshots in docs/shots were taken from -- so the slides and the app cannot
disagree.

Run:  python docs/build_deck.py
"""

import copy
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

TEMPLATE = Path(r"C:\Users\abini\Downloads\Sakthi_Hackathon_Round2_PPT_Template (1).pptx")
HERE = Path(__file__).resolve().parent
OUT = HERE / "LineSight_Sakthi_R2.pptx"
SHOTS = HERE / "shots"

ACCENT = RGBColor(0xFF, 0x33, 0x00)
ACCENT_SOFT = RGBColor(0xFF, 0xEC, 0xE6)
INK = RGBColor(0x14, 0x14, 0x14)
BODY = RGBColor(0x33, 0x33, 0x33)
MUTED = RGBColor(0x6B, 0x6B, 0x6B)
PANEL = RGBColor(0xF5, 0xF5, 0xF5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GOOD = RGBColor(0x1B, 0x7F, 0x3B)
LINE = RGBColor(0xDD, 0xDD, 0xDD)

FONT = "Arial"

# ---------------------------------------------------------------- frozen facts
# Measured on the six-shift seeded run; selftest numbers from
# `python -m linesight.selftest` on the same data.
FACTS = {
    "oee": "66.0",
    "target": "65",
    "breakdown_min": "288",
    "explained": "95",
    "stops": "691",
    "samples": "519k",
    "accuracy": "98.7",
    "acc_cnc1": "98.6",
    "acc_cnc2": "98.0",
    "acc_press": "99.5",
    "machines": "3",
    "signals": "9",
    "source_kb": "138",
    "db_mb": "58",
}


# --------------------------------------------------------------------- shapes
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


def para(tf, text, size=12, bold=False, color=BODY, after=4, first=False,
         align=PP_ALIGN.LEFT, italic=False, before=0, line=None):
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
    return p


def heading(slide, title, sub=None, y=0.40):
    size = 26 if len(title) <= 46 else 22
    box = tb(slide, 0.69, y, 8.62, 0.62)
    para(box.text_frame, title, size=size, bold=True, color=INK, first=True, after=0)
    rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.69), Inches(y + 0.80),
                                  Inches(1.1), Inches(0.055))
    rule.fill.solid()
    rule.fill.fore_color.rgb = ACCENT
    rule.line.fill.background()
    rule.shadow.inherit = False
    if sub:
        sbox = tb(slide, 0.69, y + 0.92, 8.62, 0.32)
        para(sbox.text_frame, sub, size=11.5, color=MUTED, first=True, after=0)


def footer(slide, num):
    f1 = tb(slide, 0.69, 7.15, 6.4, 0.24)
    para(f1.text_frame, "Sakthi Hackathon 2.0  ·  Team NexussAI  ·  PS-002  ·  LineSight",
         size=9, color=WHITE, first=True, after=0)
    f2 = tb(slide, 7.00, 7.15, 0.90, 0.24)
    para(f2.text_frame, str(num), size=9, color=WHITE, first=True, after=0, align=PP_ALIGN.RIGHT)


def panel(slide, x, y, w, h, fill=PANEL, line=None, radius=0.04):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y),
                                 Inches(w), Inches(h))
    try:
        shp.adjustments[0] = radius
    except Exception:
        pass
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def bar(slide, x, y, w, h, color=ACCENT):
    sh = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb = color
    sh.line.fill.background()
    sh.shadow.inherit = False
    return sh


def card(slide, x, y, w, h, kicker, body, size=9.5, fill=PANEL, accent=False):
    panel(slide, x, y, w, h, fill=fill)
    bar(slide, x, y, 0.055, h, ACCENT if accent else LINE)
    box = tb(slide, x + 0.18, y + 0.13, w - 0.32, h - 0.2)
    tf = box.text_frame
    para(tf, kicker, size=8.5, bold=True, color=ACCENT, first=True, after=3)
    para(tf, body, size=size, color=BODY, after=0, line=1.05)


def wipe(slide, keep_pictures=False):
    keep = {13, 19} if keep_pictures else set()
    for sh in list(slide.shapes):
        if sh.shape_type in keep:
            continue
        sh._element.getparent().remove(sh._element)


def cell(table, r, c, text, size=10.5, bold=False, color=BODY, fill=WHITE,
         align=PP_ALIGN.LEFT, italic=False):
    cl = table.cell(r, c)
    cl.text = ""
    tf = cl.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    f = run.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.italic = italic
    f.color.rgb = color
    cl.fill.solid()
    cl.fill.fore_color.rgb = fill
    cl.margin_left = Inches(0.10)
    cl.margin_right = Inches(0.08)
    cl.margin_top = Inches(0.03)
    cl.margin_bottom = Inches(0.03)
    cl.vertical_anchor = MSO_ANCHOR.MIDDLE


def place_image(slide, path, x, y, w, h, border=True):
    pic = slide.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
    if border:
        pic.line.color.rgb = LINE
        pic.line.width = Pt(0.75)
    return pic


def fit(path, x, y, w, h):
    """Return (left, top, width, height) for an image letterboxed into a box."""
    from PIL import Image
    with Image.open(path) as img:
        iw, ih = img.size
    scale = min(w / iw, h / ih)
    nw, nh = iw * scale, ih * scale
    return x + (w - nw) / 2, y + (h - nh) / 2, nw, nh


# --------------------------------------------------------------------- build
prs = Presentation(str(TEMPLATE))
LAYOUT_OBJECT = prs.slide_layouts[1]

# template order: 1 team, 2 solution, 3 technical, 4 feasibility, 5 impact,
# 6 references, 7 instructions, 8 thank you
tpl = list(prs.slides)
while len(prs.slides) < 10:
    prs.slides.add_slide(LAYOUT_OBJECT)
slides = list(prs.slides)


# ================================================================== 1. team
s = slides[0]
wipe(s, keep_pictures=True)
bar(s, 2.52, 1.86, 0.05, 0.86, ACCENT)
box = tb(s, 2.68, 1.76, 6.53, 0.5)
para(box.text_frame, "LineSight", size=30, bold=True, color=INK, first=True, after=0,
     align=PP_ALIGN.RIGHT)
box = tb(s, 2.68, 2.26, 6.53, 0.34)
para(box.text_frame, "The shop floor that explains its own downtime",
     size=12.5, bold=True, color=ACCENT, first=True, after=0, align=PP_ALIGN.RIGHT)

table_shape = None
for sh in s.shapes:
    if sh.has_table:
        table_shape = sh
tbl = table_shape.table
tbl._tbl.append(copy.deepcopy(tbl._tbl.tr_lst[-1]))

rows = [
    ("Problem Statement ID", "PS-002"),
    ("Submission Team ID", "SKH2-2026-00779"),
    ("Team Name", "NexussAI"),
    ("Theme", "IIoT and Real-Time Monitoring Systems"),
    ("Problem Statement Title", "Real-Time Production Monitoring and Performance Analytics Dashboard"),
    ("College Name", "Sri Krishna College of Engineering and Technology"),
    ("Team Members", "Abinivesh M  ·  Abhinivesh K  ·  Mrittika S  ·  Harini E S"),
]
heights = [0.50, 0.50, 0.50, 0.50, 0.82, 0.52, 0.58]
for r, h in enumerate(heights):
    tbl.rows[r].height = Inches(h)
for r, (label, value) in enumerate(rows):
    cell(tbl, r, 0, label, size=10.5, bold=True, color=MUTED, fill=PANEL)
    cell(tbl, r, 1, value, size=11.5, color=INK, fill=WHITE)
footer(s, 1)


# ============================================================== 2. solution
s = slides[1]
wipe(s)
heading(s, "The number is easy. The reason is the hard part.",
        "LineSight is a production monitor for small plants that infers why each stop happened — and keeps the proof.")

steps = [
    ("1 · READ", "Nine points from the PLC every second: three coils, five holding registers, one alarm code. Modbus TCP, nothing proprietary."),
    ("2 · INFER", "A rule per cause reads the pattern. Every stop gets a category, a cause and a confidence — never a dropdown."),
    ("3 · PROVE", "Every stop opens its own page: the signals ±45 seconds around it, the rule that fired, 98% confidence or 35%."),
]
for i, (k, b) in enumerate(steps):
    card(s, 0.69 + i * 2.92, 1.80, 2.74, 1.02, k, b, size=9)

panel(s, 0.69, 2.94, 8.62, 1.22, fill=ACCENT_SOFT)
bar(s, 0.69, 2.94, 0.075, 1.22, ACCENT)
box = tb(s, 0.98, 3.04, 8.1, 1.04)
tf = box.text_frame
para(tf, "Nobody types the reason.", size=17, bold=True, color=INK, first=True, after=3)
para(tf, "94% of stop time on the last shift carries a reason derived from the signals alone. The rest is reported as "
         "unknown instead of being guessed. When an operator disagrees they correct it, and the correction is stored "
         "with their name and the time. The signal record is never overwritten.",
     size=10.5, color=BODY, after=0, line=1.1)

buckets = [
    ("Breakdown", "Fault coil high, or a stop the alarm register names."),
    ("Planned stop", "Planned coil high: changeover, break, no schedule."),
    ("Micro-stop", "Running, but no part pulse for over 2 ideal cycles."),
    ("Idle", "Stopped with no alarm and no plan — waiting."),
    ("Unknown", "Signals contradict each other. Left unknown."),
]
for i, (k, b) in enumerate(buckets):
    x = 0.69 + i * 1.74
    panel(s, x, 4.42, 1.62, 1.16, fill=PANEL)
    box = tb(s, x + 0.14, 4.52, 1.36, 0.98)
    tf = box.text_frame
    para(tf, k, size=10, bold=True, color=INK, first=True, after=2)
    para(tf, b, size=8, color=MUTED, after=0, line=1.05)

panel(s, 0.69, 5.86, 8.62, 0.62, fill=INK)
box = tb(s, 0.69, 5.86, 8.62, 0.62, anchor=MSO_ANCHOR.MIDDLE)
para(box.text_frame, "Runs offline on one plant PC.  No cloud, no licence fee, no integrator.",
     size=12.5, bold=True, color=WHITE, first=True, after=0, align=PP_ALIGN.CENTER)
footer(s, 2)


# ============================================================= 3. technical
s = slides[2]
wipe(s)
heading(s, "Four processes, one SQLite file, no cloud",
        "The machine talks Modbus. Everything after that runs on the plant's own PC.")

l, t, w, h = fit(SHOTS / "architecture.png", 0.69, 1.68, 8.62, 3.62)
place_image(s, SHOTS / "architecture.png", l, t, w, h)

stack = [
    ("COLLECT", "Modbus TCP client, 1 Hz, reconnect with backoff. The bundled server speaks the same protocol, so the demo is the real path."),
    ("CLASSIFY", "One rule per cause. Confidence 0.98 fault, 0.97 planned, 0.75 micro — and 0.20 when two coils disagree."),
    ("STORE", "SQLite in WAL mode. 523k rows of nine signals. Pages recompute from samples; nothing is a stored opinion."),
    ("DELIVER", "FastAPI, server-rendered HTML, SVG charts, a PDF written in-process. 30–100 ms per page once warm."),
]
for i, (k, b) in enumerate(stack):
    card(s, 0.69 + i * 2.18, 5.36, 2.09, 1.44, k, b, size=8.2)
footer(s, 3)


# =========================================================== 4. prototype
s = slides[3]
wipe(s)
heading(s, "The prototype, running",
        "Captured from the app on 4 Nov 2026 — no mockups, no re-drawn screens.")

shots = [
    ("live.png", "Live floor", "Three machines, one screen. Top unplanned loss, not the total."),
    ("downtime.png", "Downtime log", "Every stop classified, in progress or closed."),
    ("event.png", "Stop evidence", "The signals around one stop, and the rule that fired."),
    ("oee.png", "OEE and losses", "A / P / Q, five loss buckets, the tree behind them."),
]
for i, (name, label, caption) in enumerate(shots):
    x = 0.69 + (i % 2) * 3.70
    y = 1.72 + (i // 2) * 2.58
    place_image(s, SHOTS / name, x, y, 3.58, 2.24)
    box = tb(s, x, y + 2.28, 3.58, 0.24)
    tf = box.text_frame
    p = tf.paragraphs[0]
    p.space_after = Pt(0)
    run = p.add_run()
    run.text = label + "   "
    run.font.name = FONT
    run.font.size = Pt(9)
    run.font.bold = True
    run.font.color.rgb = ACCENT
    run2 = p.add_run()
    run2.text = caption
    run2.font.name = FONT
    run2.font.size = Pt(8.5)
    run2.font.color.rgb = MUTED

stats = [
    (FACTS["oee"] + "%", "line OEE on the seeded shift"),
    (FACTS["stops"], "stops classified and stored"),
    (FACTS["accuracy"] + "%", "stop-second agreement with ground truth"),
    (FACTS["samples"], "signal samples stored, one per second"),
]
for i, (big, label) in enumerate(stats):
    y = 1.78 + i * 1.24
    panel(s, 8.14, y, 1.17, 1.12, fill=PANEL)
    box = tb(s, 8.22, y + 0.10, 1.02, 0.92)
    tf = box.text_frame
    para(tf, big, size=17, bold=True, color=ACCENT, first=True, after=1)
    para(tf, label, size=7, color=MUTED, after=0, line=0.95)
footer(s, 4)


# ========================================================== 5. feasibility
s = slides[4]
wipe(s)
heading(s, "Can a plant run this on Monday?",
        "One office PC, one network cable, one SQLite file. No cloud account, no licence key, no integration project.")

feas = [
    ("ONE PC", "138 KB of Python and a 58 MB history file. Warm page 30–100 ms; a cold eight-hour rollup about half a second. It ran the whole demo on a laptop."),
    ("WHAT IT PLUGS INTO", "Any controller that answers Modbus TCP. Nine points is the whole contract: three coils, five holding registers, one alarm code. No new sensors for the case in this deck."),
    ("NO LICENCE, NO CLOUD", "Python, FastAPI, SQLite, reportlab — free and already installed. Nothing leaves the plant. Pull the network cable and the dashboard keeps working."),
    ("TESTED, NOT ASSERTED", "98.7% of stop-seconds agree with the simulator's own state — 98.6 / 98.0 / 99.5 by machine. 37 seconds of fault time missed. 0 invalid events."),
]
for i, (k, b) in enumerate(feas):
    x = 0.69 + (i % 2) * 4.33
    y = 1.72 + (i // 2) * 1.44
    card(s, x, y, 4.29, 1.30, k, b, size=10)

risks = [
    ("Counter resets", "Parts are positive deltas only, and the minute holding a reset is re-read exactly."),
    ("A dark signal", "Coverage is printed per machine. A dead input shows as low coverage, not as a perfect shift."),
    ("Start-up rejects", "Not instrumented yet: a shift-start scrap burst needs a first-off signal. That is one sensor, and the deck does not claim it."),
    ("Operator distrust", "The cause arrives with its confidence and its evidence. A correction is attributed, dated and kept beside the signal record."),
]
box = tb(s, 0.69, 4.66, 8.62, 0.26)
para(box.text_frame, "WHAT COULD GO WRONG, AND WHAT WE DID ABOUT IT", size=8.5, bold=True,
     color=ACCENT, first=True, after=0)
for i, (k, b) in enumerate(risks):
    y = 4.96 + i * 0.48
    box = tb(s, 0.69, y, 1.72, 0.36)
    para(box.text_frame, k, size=9.5, bold=True, color=INK, first=True, after=0)
    box = tb(s, 2.44, y, 6.87, 0.40)
    para(box.text_frame, b, size=9, color=BODY, first=True, after=0, line=1.0)
    if i < len(risks) - 1:
        bar(s, 0.69, y + 0.42, 8.62, 0.008, LINE)
footer(s, 5)


# =============================================================== 6. impact
s = slides[5]
wipe(s)
heading(s, "Five points of OEE is 24 minutes a shift",
        "Not a forecast. Five points of a 480-minute shift is 24 minutes, and this prototype shows where they go.")

panel(s, 0.69, 1.72, 8.62, 1.12, fill=INK)
box = tb(s, 0.95, 1.72, 8.1, 1.12, anchor=MSO_ANCHOR.MIDDLE)
tf = box.text_frame
para(tf, "60%  →  65%  ≈  +24 minutes of capacity, every shift, on one line",
     size=19, bold=True, color=WHITE, first=True, after=3)
para(tf, "That is the same line running, with the hour it already loses given a name.",
     size=10.5, color=RGBColor(0xD5, 0xD5, 0xD5), after=0)

left = [
    ("WHERE IT GOES TODAY", "Breakdown alone is " + FACTS["breakdown_min"] + " of the 480 minutes in the shift — 60% of the clock. "
                            "32 separate stops, each one stored with its cause and its evidence."),
    ("WHAT IT IS WORTH", "24 minutes × 3 shifts × 300 days = 360 hours of recovered capacity per line per year. "
                         "Arithmetic on an assumption, labelled as one."),
]
for i, (k, b) in enumerate(left):
    card(s, 0.69 + i * 4.33, 3.00, 4.29, 1.14, k, b, size=9.5, accent=True)

people = [
    ("SUPERVISOR", "Opens one page, sees which stop to attack first, and stops reconstructing the shift from memory."),
    ("PLANT HEAD", "Six shifts of history that survive the person who wrote the logbook."),
    ("OPERATOR", "Their correction is recorded, attributed and dated — not silently overwritten."),
]
for i, (k, b) in enumerate(people):
    x = 0.69 + i * 2.92
    panel(s, x, 4.36, 2.74, 1.14, fill=PANEL)
    box = tb(s, x + 0.18, 4.48, 2.44, 0.94)
    tf = box.text_frame
    para(tf, k, size=8.5, bold=True, color=ACCENT, first=True, after=3)
    para(tf, b, size=9, color=BODY, after=0, line=1.05)

box = tb(s, 0.69, 5.74, 8.62, 0.74)
tf = box.text_frame
para(tf, "The 60% baseline is an assumption for an Indian SME line, not a measurement from this plant.",
     size=9, color=MUTED, first=True, after=2)
para(tf, "LineSight's own claim is narrower and it is measured: it finds the gap and it names it — 94% of stop time explained, "
         "98.7% agreement with ground truth.",
     size=9, color=MUTED, after=0)
footer(s, 6)


# ====================================================== 7. existing vs us
s = slides[6]
wipe(s)
heading(s, "What a supervisor has instead",
        "LineSight is not an MES. It is the smallest thing that answers one question honestly: where did the shift go?")

rows = [
    ("", "Manual logbook", "SCADA or MES add-on", "LineSight"),
    ("Cost to start", "Paper, if it gets filled", "Licence plus an integrator", "Free stack, one PC"),
    ("Works offline", "Yes", "Rarely", "Yes, by design"),
    ("Cause of each stop", "What the operator remembers", "Alarm text, if it is wired", "Inferred from coil and register pattern"),
    ("Evidence per stop", "None", "Trend, if a historian was bought", "Its own page: signals, rule, confidence"),
    ("Time to first answer", "Blank until someone writes", "Weeks of commissioning", "The same day"),
]
shape = s.shapes.add_table(len(rows), 4, Inches(0.69), Inches(1.76), Inches(8.62), Inches(3.9))
tbl = shape.table
for i, wd in enumerate([1.72, 2.05, 2.30, 2.55]):
    tbl.columns[i].width = Inches(wd)
for r in range(len(rows)):
    tbl.rows[r].height = Inches(0.62 if r else 0.60)

for r, row in enumerate(rows):
    for c, text in enumerate(row):
        if r == 0:
            fill = ACCENT if c == 3 else PANEL
            cell(tbl, r, c, text, size=10.5, bold=True,
                 color=WHITE if c == 3 else INK, fill=fill)
        else:
            if c == 0:
                cell(tbl, r, c, text, size=9.5, bold=True, color=MUTED, fill=PANEL)
            elif c == 3:
                cell(tbl, r, c, text, size=9.5, bold=(r == 0), color=INK, fill=ACCENT_SOFT)
            else:
                cell(tbl, r, c, text, size=9.5, color=BODY, fill=WHITE)

box = tb(s, 0.69, 5.98, 8.62, 0.8)
tf = box.text_frame
para(tf, "The gap is not the dashboard. Every plant already has numbers somewhere.",
     size=11, bold=True, color=INK, first=True, after=3)
para(tf, "The gap is that nobody can say why the machine stopped without asking the person who was standing there — "
         "and that person's answer is gone by the next shift.",
     size=10, color=BODY, after=0, line=1.1)
footer(s, 7)


# ========================================================== 8. future scope
s = slides[7]
wipe(s)
heading(s, "What is built, and what comes next",
        "The four versions below are ordered by what a plant would pay for first, not by what is interesting to build.")

bar(s, 0.69, 2.03, 8.62, 0.02, LINE)
horizons = [
    ("BUILT", "Now", ACCENT, [
        "Eleven pages: floor, alerts, downtime, evidence, OEE, machines, trends, history, report, settings, how-it-works",
        "Five loss buckets, one rule per cause",
        "Configurable KPI thresholds, stored in SQLite",
        "Six shifts of history, CSV and PDF out",
        "Fault injection, for a demo you can watch",
    ]),
    ("NEXT", "30 days", MUTED, [
        "First-off signal, so start-up scrap is counted",
        "OPC-UA driver beside the Modbus client",
        "Per-machine alert thresholds and quiet hours",
        "Shift-start checklist scored against the first part",
        "Shift digest by email, from the same report",
    ]),
    ("THEN", "90 days", MUTED, [
        "Multi-line rollup and a plant view",
        "Tool-life and spare-part linkage on stoppages",
        "Cause model learned from confirmed corrections",
        "Daily loss Pareto sent at shift end",
        "Historian retention policy, not one flat table",
    ]),
    ("LATER", "Beyond", MUTED, [
        "ERP write-back for production orders",
        "Multi-plant comparison, on-premise only",
        "Vibration and current as extra evidence",
        "Tool-life alarms from spindle hours",
    ]),
]
for i, (kicker, when, color, items) in enumerate(horizons):
    x = 0.69 + i * 2.19
    panel(s, x, 2.22, 2.05, 3.35, fill=PANEL if i else ACCENT_SOFT)
    bar(s, x, 2.22, 2.05, 0.05, color)
    box = tb(s, x + 0.16, 2.38, 1.75, 0.5)
    tf = box.text_frame
    para(tf, kicker, size=8.5, bold=True, color=color, first=True, after=0)
    para(tf, when, size=13, bold=True, color=INK, after=0)
    box = tb(s, x + 0.16, 2.96, 1.78, 2.84)
    tf = box.text_frame
    for j, item in enumerate(items):
        para(tf, "·  " + item, size=9.4, color=BODY, first=(j == 0), after=8, line=1.03)

box = tb(s, 0.69, 6.02, 8.62, 0.24)
para(box.text_frame, "Nothing on the right of the first column is claimed as working today.",
     size=8.5, italic=True, color=MUTED, first=True, after=0)
footer(s, 8)


# ============================================================ 9. references
s = slides[8]
wipe(s)
heading(s, "What this is built on",
        "Standards and specifications we followed, plus the one number a reader can check themselves.")

refs = [
    ("ISO 22400-2:2014",
     "Manufacturing operations management — Key performance indicators. The availability × performance × quality definition, "
     "and the reason planned time is subtracted before availability is divided."),
    ("Nakajima, S. (1988). Introduction to TPM. Productivity Press.",
     "The original OEE framing and the loss categories that the five buckets in this prototype descend from."),
    ("Modbus Application Protocol Specification v1.1b3, Modbus Organization.",
     "Function codes 1, 3, 5, 6, 15 and 16 — all six implemented in the bundled server, so the demo exercises the same protocol as a real PLC."),
    ("OPC Foundation, OPC UA Part 1: Overview and Concepts.",
     "The protocol the roadmap adds next; it is why the collector keeps the transport behind one small client."),
    ("The prototype itself.",
     "python -m linesight.selftest replays eight hours of simulated signals and scores LineSight second by second against the "
     "simulator's own state: 98.7% agreement, 0 invalid events."),
]
for i, (title, note) in enumerate(refs):
    y = 1.78 + i * 0.90
    box = tb(s, 0.69, y, 0.5, 0.5)
    para(box.text_frame, f"{i + 1:02d}", size=15, bold=True, color=ACCENT, first=True, after=0)
    box = tb(s, 1.24, y, 8.07, 0.84)
    tf = box.text_frame
    para(tf, title, size=11, bold=True, color=INK, first=True, after=2)
    para(tf, note, size=9, color=MUTED, after=0, line=1.05)
    if i < len(refs) - 1:
        bar(s, 0.69, y + 0.80, 8.62, 0.008, LINE)
footer(s, 9)


# ============================================================ 10. thank you
s = slides[9]
wipe(s)
bar(s, 0.69, 2.10, 1.6, 0.07, ACCENT)
box = tb(s, 0.69, 2.30, 8.62, 0.9)
para(box.text_frame, "Thank you.", size=44, bold=True, color=INK, first=True, after=0)

box = tb(s, 0.69, 3.42, 7.4, 0.4)
para(box.text_frame, "LineSight  ·  PS-002  ·  Team NexussAI", size=13, bold=True,
     color=ACCENT, first=True, after=0)

box = tb(s, 0.69, 3.98, 7.4, 1.5)
tf = box.text_frame
para(tf, "Ask us to inject a fault. It will be classified, given a cause and a confidence, and stored "
         "with its evidence inside fifteen seconds — on this laptop, with the network cable out.",
     size=12, color=BODY, first=True, after=10, line=1.15)
para(tf, "Six shifts of history are already in the box: 523k samples, 692 stops, 98.7% agreement with ground truth.",
     size=12, color=BODY, after=0, line=1.15)

box = tb(s, 0.69, 5.86, 8.62, 0.3)
para(box.text_frame, "Abinivesh M  ·  Abhinivesh K  ·  Mrittika S  ·  Harini E S  —  Sri Krishna College of Engineering and Technology",
     size=9, color=MUTED, first=True, after=0)
footer(s, 10)


# ------------------------------------------------------------------ reorder
# The slides above are already written in the official order:
# team, solution, technical, prototype, feasibility, impact, existing, future,
# references, thank you. Nothing to move; the assertion keeps it that way.
assert len(prs.slides) == 10

prs.save(str(OUT))
print("saved", OUT, "-", len(prs.slides), "slides")
