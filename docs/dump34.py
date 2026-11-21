import io
import sys

from pptx import Presentation
from pptx.util import Emu

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

prs = Presentation(r"C:\Users\abini\Downloads\7,8,9 Edited ppt.pptx")
for idx in (2, 3):
    slide = prs.slides[idx]
    print(f"--- slide {idx + 1} ---")
    for sh in slide.shapes:
        txt = ""
        if sh.has_text_frame:
            txt = " | ".join(p.text for p in sh.text_frame.paragraphs if p.text.strip())
        print(f"  {sh.shape_type} name={sh.name!r} "
              f"pos=({Emu(sh.left).inches:.2f},{Emu(sh.top).inches:.2f}) "
              f"size=({Emu(sh.width).inches:.2f}x{Emu(sh.height).inches:.2f})"
              + (f" TEXT={txt[:90]}" if txt else ""))
