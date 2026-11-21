import io
import json
import sys
import urllib.request
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

TREE = Path(r"C:\Users\abini\AppData\Local\Temp\opencode\gh.json")
DEST = Path(r"C:\Users\abini\.config\opencode\skills")
RAW = "https://raw.githubusercontent.com/latent-spaces/brag/main/"

tree = json.loads(TREE.read_text(encoding="utf-8"))["tree"]
files = [
    t for t in tree
    if t["type"] == "blob"
    and (t["path"].startswith("skills/brag/") or t["path"].startswith("skills/brag-slim/"))
]

total = sum(t.get("size", 0) for t in files)
print(f"{len(files)} files, {total / 1024 / 1024:.1f} MB")

ok = 0
fail = []
for t in files:
    rel = t["path"][len("skills/"):]          # brag/SKILL.md
    out = DEST / rel
    if out.exists() and out.stat().st_size == t.get("size", 0):
        ok += 1
        continue
    out.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(RAW + t["path"], headers={"User-Agent": "opencode"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            out.write_bytes(r.read())
        ok += 1
    except Exception as e:                    # noqa: BLE001
        fail.append((t["path"], str(e)[:80]))

print(f"downloaded {ok}/{len(files)}")
for p, e in fail[:10]:
    print("  FAIL", p, e)
