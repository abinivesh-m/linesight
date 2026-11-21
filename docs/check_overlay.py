p = r"C:\Users\abini\OneDrive\Desktop\LineSight\brag-output-2026-11-20\composition\index.html"
s = open(p, encoding='utf-8').read()
print("donut-overlay count:", s.count("donut-overlay"))
print("old overlay count:", s.count("position:absolute;top:50%"))
# find the donut-wrap block
i = s.find("donut-wrap")
print(s[i-30:i+260])