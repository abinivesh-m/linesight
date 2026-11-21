import io
import sqlite3
import sys
from datetime import datetime, timedelta

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DB = r"C:\Users\abini\OneDrive\Desktop\LineSight\data\linesight.db"
con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
cur = con.cursor()

mn, mx = cur.execute("select min(ts), max(ts) from samples").fetchone()
print("samples span:", datetime.fromtimestamp(mn), "->", datetime.fromtimestamp(mx))
print("total samples:", cur.execute("select count(*) from samples").fetchone()[0])

start = mx - 8 * 3600
print("last 8h window:", datetime.fromtimestamp(start), "->", datetime.fromtimestamp(mx))

rows = cur.execute(
    "select machine, sum(running), sum(fault), sum(planned), max(parts), max(good),"
    " count(*), avg(last_cycle), avg(ideal_cycle) from samples"
    " where ts >= ? group by machine", (start,)).fetchall()
print("\nmachine  run_s  fault_s  plan_s  parts  good  n     avg_cyc  ideal")
for r in rows:
    print("  ", r)

print("\ntotal run/fault/planned/rows:",
      cur.execute("select sum(running), sum(fault), sum(planned), count(*) from samples"
                  " where ts >= ?", (start,)).fetchone())

print("\ndowntime by category in window:")
for r in cur.execute(
        "select category, count(*), round(sum(seconds)/60.0,1) from events"
        " where start_ts >= ? group by category order by 3 desc", (start,)):
    print("  ", r)

print("\nall-time downtime by category:")
for r in cur.execute(
        "select category, count(*), round(sum(seconds)/60.0,1) from events"
        " group by category order by 3 desc"):
    print("  ", r)

print("\nalerts:", cur.execute("select count(*), sum(ack) from alerts").fetchone())
print("commands:", cur.execute("select count(*), sum(done) from commands").fetchone())

print("\nlast 5 events:")
for r in cur.execute(
        "select machine, category, seconds, cause, confidence from events"
        " order by start_ts desc limit 5"):
    print("  ", r)

print("\nmachines:")
for r in cur.execute("select id, name, ideal_cycle_ms, enabled from machines"):
    print("  ", r)
