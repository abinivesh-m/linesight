from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor

SRC = r"C:\Users\abini\Downloads\linesight final ppt (1).pptx"
OUT = r"C:\Users\abini\Downloads\NexussAI_LineSight_R2_Deck.pptx"
OUT2 = r"C:\Users\abini\Downloads\linesight final ppt (1).pptx"

prs = Presentation(SRC)
assert len(prs.slides) == 10

# Slide 4 (index 3): append links to subtitle textbox
s4 = prs.slides[3]
sub = None
for sh in s4.shapes:
    if sh.has_text_frame and "mock-up" in sh.text_frame.text:
        sub = sh
        break
if sub is not None:
    p = sub.text_frame.paragraphs[0]
    r = p.add_run()
    r.text = "   ·   live: linesight-olive.vercel.app   ·   github: github.com/abinivesh-m/linesight"
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(0x6B, 0x6B, 0x6B)

# Slide 10 (index 9): add links below Thank You
s10 = prs.slides[9]
thanks = None
for sh in s10.shapes:
    if sh.has_text_frame and "Thank" in sh.text_frame.text:
        thanks = sh
        break
if thanks is not None:
    x = thanks.left.inches
    y = thanks.top.inches + thanks.height.inches + 0.3
    w = thanks.width.inches
else:
    x, y, w = 1.42, 3.6, 6.68
box = s10.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(0.9))
tf = box.text_frame
tf.word_wrap = True
p1 = tf.paragraphs[0]
p1.alignment = PP_ALIGN.CENTER
r1 = p1.add_run()
r1.text = "Live demo:   linesight-olive.vercel.app"
r1.font.size = Pt(12)
r1.font.bold = True
r1.font.color.rgb = RGBColor(0xC5, 0x5A, 0x11)
p2 = tf.add_paragraph()
p2.alignment = PP_ALIGN.CENTER
r2 = p2.add_run()
r2.text = "GitHub:   github.com/abinivesh-m/linesight"
r2.font.size = Pt(11)
r2.font.color.rgb = RGBColor(0x6B, 0x6B, 0x6B)

prs.save(OUT)
prs.save(OUT2)
print("saved both:", OUT, "and", OUT2)