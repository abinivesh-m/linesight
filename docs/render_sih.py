import io
import sys
from pathlib import Path

import pymupdf

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SRC = Path(r"C:\Users\abini\Downloads\NexussAI_SIH26127.pdf")
OUT = Path(r"C:\Users\abini\AppData\Local\Temp\opencode\sih")
OUT.mkdir(parents=True, exist_ok=True)

doc = pymupdf.open(SRC)
print("pages:", doc.page_count)
for i, page in enumerate(doc):
    if i > 5:
        break
    pix = page.get_pixmap(dpi=170)
    p = OUT / f"p{i + 1}.png"
    pix.save(p)
    print(f"p{i + 1}: {pix.width}x{pix.height}  {p}")
