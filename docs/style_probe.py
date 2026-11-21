import io
import re
import sys
import zipfile
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PATH = r"C:\Users\abini\Downloads\NexussAI_LineSight_R2_Deck.pptx"
z = zipfile.ZipFile(PATH)

for n in (7, 8, 9):
    xml = z.read(f"ppt/slides/slide{n}.xml").decode("utf-8")
    print("=" * 70)
    print("slide", n)

    fills = Counter(re.findall(r"<a:solidFill>\s*<a:srgbClr val=\"([0-9A-Fa-f]{6})\"", xml))
    print("  solid fills:", fills.most_common(12))

    lines = Counter(re.findall(
        r"<a:ln[^>]*>.*?<a:solidFill>\s*<a:srgbClr val=\"([0-9A-Fa-f]{6})\"", xml, re.S))
    print("  line colours:", lines.most_common(8))

    print("  fonts:", Counter(re.findall(r'<a:latin typeface=\"([^\"]+)\"', xml)).most_common(6))
    print("  sizes:", Counter(re.findall(r'<a:rPr[^>]*sz=\"(\d+)\"', xml)).most_common(8))
    print("  bold runs:", len(re.findall(r'<a:rPr[^>]*b=\"1\"', xml)))

    # title placeholder styling
    for m in re.finditer(r'<p:sp>.*?</p:sp>', xml, re.S):
        blk = m.group(0)
        if "ph type=\"title\"" in blk or "ph type=\"ctrTitle\"" in blk:
            name = re.search(r'name=\"([^\"]*)\"', blk)
            col = re.findall(r'<a:srgbClr val=\"([0-9A-Fa-f]{6})\"', blk)
            sz = re.findall(r'sz=\"(\d+)\"', blk)
            face = re.findall(r'typeface=\"([^\"]+)\"', blk)
            print(f"  TITLE ph name={name.group(1) if name else '?'} colours={col[:4]} "
                  f"sizes={sz[:3]} faces={face[:3]}")
