import io
import sys
from collections import Counter

from PIL import Image

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

for name, box in [("s7", None), ("s8", None), ("s9", None)]:
    im = Image.open(rf"C:\Users\abini\AppData\Local\Temp\opencode\ref789\{name}.png").convert("RGB")
    w, h = im.size
    print("=" * 60)
    print(name, im.size)
    px = im.load()
    c = Counter()
    for y in range(0, h, 3):
        for x in range(0, w, 3):
            c[px[x, y]] += 1
    for col, n in c.most_common(14):
        print(f"   #{col[0]:02X}{col[1]:02X}{col[2]:02X}  {n}")
