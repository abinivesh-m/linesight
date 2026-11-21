p = r"C:\Users\abini\OneDrive\Desktop\LineSight\brag-output-2026-11-20\composition\index.html"
s = open(p, encoding='utf-8').read()

old = '''              <svg class="donut" viewBox="0 0 180 180" width="180" height="180">
                <circle cx="90" cy="90" r="72" fill="none" stroke="#e6e0d4" stroke-width="16"/>
                <circle id="oeeRing" cx="90" cy="90" r="72" fill="none" stroke="#e63946" stroke-width="16" stroke-dasharray="0 452" stroke-linecap="round" transform="rotate(-90 90 90)"/>
                <text id="oeeNum" x="90" y="88" text-anchor="middle" font-family="Georgia, serif" font-size="30" font-weight="700" fill="#141414">0.0%</text>
                <text x="90" y="110" text-anchor="middle" font-size="11" fill="#5a5450">line OEE</text>
              </svg>
              <div style="font-size:11px;color:var(--muted);margin-top:8px;">target 65% ?? A 94.2 ?? P 78.3 ?? Q 98.9</div>'''

new = '''              <svg class="donut" viewBox="0 0 180 180" width="180" height="180">
                <circle cx="90" cy="90" r="72" fill="none" stroke="#e6e0d4" stroke-width="16"/>
                <circle id="oeeRing" cx="90" cy="90" r="72" fill="none" stroke="#e63946" stroke-width="16" stroke-dasharray="0 452" stroke-linecap="round" transform="rotate(-90 90 90)"/>
              </svg>
              <div id="oeeNum" style="font-family:Georgia,serif;font-size:30px;font-weight:700;color:var(--ink);margin-top:-118px;height:30px;line-height:30px;">0.0%</div>
              <div style="font-size:11px;color:var(--muted);margin-top:88px;">line OEE</div>
              <div style="font-size:11px;color:var(--muted);margin-top:4px;">target 65% ?? A 94.2 ?? P 78.3 ?? Q 98.9</div>'''

assert old in s, "old not found"
s = s.replace(old, new)
# update the GSAP tween selector still works (#oeeNum is now a div)
open(p, 'w', encoding='utf-8').write(s)
print("done")