p = r"C:\Users\abini\OneDrive\Desktop\LineSight\brag-output-2026-11-20\composition\index.html"
s = open(p, encoding='utf-8').read()
start = s.find('<div class="donut-wrap">')
end = s.find('</div>', start) + 6
# find the matching closing: the donut-wrap contains svg + overlay + target line; find the next '</div>' after target line
i = s.find('target 65%', start)
end = s.find('</div>', i) + 6
print("BLOCK:")
print(s[start:end])
print("LEN", end-start)