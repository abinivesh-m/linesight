import io
import sys

from pptx import Presentation
from pptx.util import Emu

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def dump(path):
    prs = Presentation(path)
    print("=" * 80)
    print(path)
    print("slide size:", prs.slide_width, "x", prs.slide_height,
          f"({Emu(prs.slide_width).inches:.2f} x {Emu(prs.slide_height).inches:.2f} in)")
    for i, layout in enumerate(prs.slide_layouts):
        print(f"  layout[{i}] {layout.name}")
    for i, slide in enumerate(prs.slides, 1):
        print(f"\n--- slide {i}  (layout: {slide.slide_layout.name}) ---")
        for sh in slide.shapes:
            t = ""
            if sh.has_text_frame:
                t = " | ".join(p.text for p in sh.text_frame.paragraphs if p.text.strip())
            print(f"  {sh.shape_type}, name={sh.name!r}, "
                  f"pos=({Emu(sh.left).inches:.2f},{Emu(sh.top).inches:.2f}) "
                  f"size=({Emu(sh.width).inches:.2f}x{Emu(sh.height).inches:.2f})"
                  + (f"  TEXT: {t[:120]}" if t else ""))


for p in sys.argv[1:]:
    dump(p)
