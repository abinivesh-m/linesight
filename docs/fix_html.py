p = r"C:\Users\abini\OneDrive\Desktop\LineSight\brag-output-2026-11-20\composition\index.html"
s = open(p, encoding='utf-8').read()

s = s.replace(".donut-wrap { display: flex; flex-direction: column; align-items: center; }",
              ".donut-wrap { display: flex; flex-direction: column; align-items: center; position: relative; }")
s = s.replace("--muted: #6b6560;", "--muted: #5a5450;")
audio_tag = '<audio id="bgm" src="assets/music/happy-beats-business-moves-vol-9-by-ende-dot-app.mp3" data-start="0" data-duration="20" data-track-index="1" data-volume="0.35"></audio>\n    '
s = s.replace("    </div>\n\n    <script>", "    </div>\n    " + audio_tag + "<script>", 1)
s = s.replace('<div id="h1" class="line accent" style="opacity:0">', '<div id="h1" class="line accent">')
s = s.replace('<div id="h2" class="line" style="opacity:0;margin-top:12px;">', '<div id="h2" class="line" style="margin-top:12px;">')
s = s.replace('      tl.to("#h1", { opacity: 1, duration: 0.18, ease: "power4.out" }, 0.3);',
              '      tl.fromTo("#h1", { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.4, ease: "power4.out" }, 0.1);')
s = s.replace('      tl.to("#h2", { opacity: 1, duration: 0.18, ease: "power4.out" }, 1.0);',
              '      tl.fromTo("#h2", { opacity: 0, y: 8 }, { opacity: 1, y: 0, duration: 0.4, ease: "power4.out" }, 0.9);')
s = s.replace(".mstate { font-size: 10.5px;", ".mstate { font-size: 11.5px;")
s = s.replace(".kv { display: flex; justify-content: space-between; font-size: 12px;", ".kv { display: flex; justify-content: space-between; font-size: 12.5px;")

open(p, 'w', encoding='utf-8').write(s)
print("done")