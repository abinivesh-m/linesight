import os, sqlite3, glob
root = r"C:\Users\abini\OneDrive\Desktop\LineSight"
print("git status:")
os.system('cd "' + root + '" && git status --short')
print("--- top-level ---")
for f in sorted(os.listdir(root)):
    print(" ", f)
print("--- deploy-ish files ---")
for pat in ['vercel.json','requirements.txt','runtime.txt','Procfile','pyproject.toml','package.json']:
    p = os.path.join(root, pat)
    print(" ", pat, os.path.exists(p))
print("--- db ---")
dbp = os.path.join(root, 'data', 'linesight.db')
print("  exists:", os.path.exists(dbp), "size MB:", round(os.path.getsize(dbp)/1048576,2) if os.path.exists(dbp) else None)
if os.path.exists(dbp):
    c = sqlite3.connect(dbp)
    print("  tables:", [r[0] for r in c.execute("select name from sqlite_master where type='table'")])
    for t in ['signals','machines','events','stops','alerts']:
        try:
            print("   ", t, c.execute(f'select count(*) from {t}').fetchone()[0])
        except Exception as e:
            print("   ", t, "ERR", e)
