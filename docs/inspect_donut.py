p = r"C:\Users\abini\OneDrive\Desktop\LineSight\brag-output-2026-11-20\composition\index.html"
s = open(p, encoding='utf-8').read()
needle = '<div class="donut-wrap">'
i = s.find(needle)
print("idx:", i)
print(repr(s[i:i+400]))