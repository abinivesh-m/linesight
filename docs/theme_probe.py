import io
import re
import sys
import zipfile

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PATH = r"C:\Users\abini\Downloads\7,8,9 Edited ppt.pptx"
z = zipfile.ZipFile(PATH)
theme = z.read("ppt/theme/theme1.xml").decode("utf-8")
block = re.search(r"<a:clrScheme.*?</a:clrScheme>", theme, re.S).group(0)
for name, val in re.findall(r'<a:(dk1|lt1|dk2|lt2|accent1|accent2|accent3|accent4|accent5|accent6)>.*?val="([0-9A-Fa-f]{6})"', block):
    print(f"{name:8s} #{val}")
print("fonts:", re.findall(r'<a:latin typeface="([^"]+)"', theme)[:4])

# footer / background check on slide 3
s3 = z.read("ppt/slides/slide3.xml").decode("utf-8")
print("\nslide3 shapes:", s3.count("<p:sp>"), "solid fills:", re.findall(r'<a:solidFill><a:srgbClr val="([0-9A-Fa-f]{6})"', s3)[:8])
s1 = z.read("ppt/slideMasters/slideMaster1.xml").decode("utf-8")
print("master fills:", re.findall(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', s1)[:10])
