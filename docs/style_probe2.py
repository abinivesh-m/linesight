import io
import re
import sys
import zipfile
from collections import Counter

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PATH = r"C:\Users\abini\Downloads\NexussAI_LineSight_R2_Deck.pptx"
z = zipfile.ZipFile(PATH)

for n in (3, 7, 8, 9):
    xml = z.read(f"ppt/slides/slide{n}.xml").decode("utf-8")
    print("=" * 70)
    print("slide", n)
    print("  schemeClr:", Counter(re.findall(r'schemeClr val="(\w+)"', xml)).most_common())
    print("  gradFill:", xml.count("<a:gradFill"), " preset:", Counter(
        re.findall(r'prst="(\w+)"', xml)).most_common(4))
    print("  shapes:", xml.count("<p:sp>"), "pics:", xml.count("<p:pic>"),
          "grpSp:", xml.count("<p:grpSp>"))
