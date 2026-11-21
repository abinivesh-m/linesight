import os, sys, shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("LINESIGHT_DB_PATH", "/tmp/linesight.db")
try:
    src_db = os.path.join(ROOT, "data", "linesight.db")
    dst_db = os.environ["LINESIGHT_DB_PATH"]
    if os.path.exists(src_db) and not os.path.exists(dst_db):
        shutil.copyfile(src_db, dst_db)
except Exception:
    pass

from linesight.web import app  # noqa: E402

__all__ = ["app"]