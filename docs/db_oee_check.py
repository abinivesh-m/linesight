import io
import sys

sys.path.insert(0, r"C:\Users\abini\OneDrive\Desktop\LineSight")

from linesight import analytics, db  # noqa: E402

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

conn = db.connect(r"C:\Users\abini\OneDrive\Desktop\LineSight\data\linesight.db")
mx = conn.execute("select max(ts) from samples").fetchone()[0]

for hours in (1, 8, 24):
    start = mx - hours * 3600
    s = analytics.summarize(conn, start, mx)
    line = s["line"]
    print(f"\n=== last {hours} h ===")
    print("line:", {k: line[k] for k in ("oee", "availability", "performance", "quality",
                                         "parts", "good", "run_s") if k in line})
    for m in s["machines"]:
        print(f"  {m['machine']:9s} A={m['availability']:5.1f} P={m['performance']:5.1f} "
              f"Q={m['quality']:5.1f} OEE={m['oee']:5.1f} parts={m['parts']} good={m['good']}")
