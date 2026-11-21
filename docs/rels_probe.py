import io
import re
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

z = zipfile.ZipFile(r"C:\Users\abini\Downloads\NexussAI_LineSight_R2_Deck.pptx")
for n in (7, 8, 9):
    rels = z.read(f"ppt/slides/_rels/slide{n}.xml.rels").decode("utf-8")
    targets = re.findall(r'Target="([^"]+)"', rels)
    print(f"slide {n}:")
    for t in targets:
        if "media" in t:
            info = z.getinfo("ppt/" + t.replace("../", ""))
            print(f"   {t:34s} {info.file_size:8d} bytes")
