import sqlite3, os
root = r"C:\Users\abini\OneDrive\Desktop\LineSight"
dbp = os.path.join(root, "data", "linesight.db")
c = sqlite3.connect(dbp)
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
print("tables:", tables)
for name in tables:
    cols = [r[1] for r in c.execute("pragma table_info(" + name + ")")]
    print(name, cols)
    if "ts" in cols:
        mn, mx = c.execute("select min(ts), max(ts) from " + name).fetchone()
        print("   ts range:", mn, "..", mx, "span", round(mx-mn), "s")
    if "start_ts" in cols:
        mn, mx = c.execute("select min(start_ts), max(start_ts) from " + name).fetchone()
        print("   start_ts range:", mn, "..", mx)