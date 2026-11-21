import sqlite3, time, os, shutil
root = r"C:\Users\abini\OneDrive\Desktop\LineSight"
dbp = os.path.join(root, "data", "linesight.db")
backup = dbp + ".bak"
shutil.copyfile(dbp, backup)
print("backup:", backup)

c = sqlite3.connect(dbp)
# max ts across all timestamped tables
mx = 0
for name, col in [("samples","ts"),("events","start_ts"),("alerts","ts"),("commands","ts")]:
    v = c.execute("select max(" + col + ") from " + name).fetchone()[0]
    print(name, col, v)
    mx = max(mx, v)
now = time.time()
offset = now - mx + 7200  # latest data ~2h ago, inside any 8h window
print("now", now, "max", mx, "offset", offset, "days", round(offset/86400,2))

c.execute("update samples set ts = ts + ?", (offset,))
c.execute("update events set start_ts = start_ts + ?, end_ts = end_ts + ?", (offset, offset))
c.execute("update alerts set ts = ts + ?", (offset,))
c.execute("update commands set ts = ts + ?", (offset,))
c.commit()

# verify
print("after shift:")
for name, col in [("samples","ts"),("events","start_ts"),("alerts","ts"),("commands","ts")]:
    mn, mx2 = c.execute("select min(" + col + "), max(" + col + ") from " + name).fetchone()
    print(" ", name, mn, "..", mx2)
c.close()
print("done")