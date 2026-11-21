p = r"C:\Users\abini\OneDrive\Desktop\LineSight\brag-output-2026-11-20\composition\index.html"
s = open(p, encoding='utf-8').read()
print("oeeNum occurrences:", s.count("oeeNum"))
print("donut-overlay occurrences:", s.count("donut-overlay"))
i = s.find('<svg class="donut"')
print(repr(s[i:i+320]))