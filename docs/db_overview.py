import io
import sqlite3
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = r"C:\Users\abini\OneDrive\Desktop\LineSight\data\linesight.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = con.cursor()

tables = [r[0] for r in cur.execute(
    "select name from sqlite_master where type='table' order by name")]
print("TABLES:", tables)
for t in tables:
    n = cur.execute(f"select count(*) from {t}").fetchone()[0]
    cols = [c[1] for c in cur.execute(f"pragma table_info({t})")]
    print(f"  {t:22s} rows={n:8d}  cols={cols}")
