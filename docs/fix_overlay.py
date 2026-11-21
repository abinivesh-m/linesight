p = r"C:\Users\abini\OneDrive\Desktop\LineSight\brag-output-2026-11-20\composition\index.html"
s = open(p, encoding='utf-8').read()

# CSS: update donut-wrap and add donut-overlay
s = s.replace(
  ".donut-wrap { display: flex; flex-direction: column; align-items: center; position: relative; }",
  ".donut-wrap { display: flex; flex-direction: column; align-items: center; position: relative; width: 180px; margin: 0 auto; }\n      .donut-overlay { position: absolute; top: 0; left: 0; width: 180px; height: 180px; display: flex; flex-direction: column; align-items: center; justify-content: center; }"
)

# HTML: replace the absolutely-positioned overlay div
old_overlay = '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);text-align:center;">\n                <div class="donut-num" id="oeeNum">0.0%</div>\n                <div style="font-size:11px;color:var(--muted);">line OEE</div>\n              </div>'
new_overlay = '<div class="donut-overlay">\n                <div class="donut-num" id="oeeNum">0.0%</div>\n                <div style="font-size:11px;color:var(--muted);">line OEE</div>\n              </div>'
assert old_overlay in s, "overlay block not found"
s = s.replace(old_overlay, new_overlay)

open(p, 'w', encoding='utf-8').write(s)
print("done")