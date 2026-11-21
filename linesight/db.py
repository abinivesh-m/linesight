"""SQLite storage: samples, events, alerts, settings, machines, demo commands.

One row per machine per second, WAL so a power cut is survivable. Everything the
UI can change lives in here too, so a plant PC needs no config files.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import os
DB_PATH = Path(os.environ.get("LINESIGHT_DB_PATH", str(Path(__file__).resolve().parents[1] / "data" / "linesight.db")))

SCHEMA = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS samples (
    ts           REAL NOT NULL,
    machine      TEXT NOT NULL,
    running      INTEGER NOT NULL,
    fault        INTEGER NOT NULL,
    planned      INTEGER NOT NULL,
    parts        INTEGER NOT NULL,
    good         INTEGER NOT NULL,
    last_cycle   INTEGER NOT NULL,
    ideal_cycle  INTEGER NOT NULL,
    alarm        INTEGER NOT NULL,
    PRIMARY KEY (ts, machine)
);

CREATE INDEX IF NOT EXISTS idx_samples_machine_ts ON samples (machine, ts);
CREATE INDEX IF NOT EXISTS idx_samples_ts ON samples (ts);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    machine      TEXT NOT NULL,
    start_ts     REAL NOT NULL,
    end_ts       REAL NOT NULL,
    seconds      REAL NOT NULL,
    category     TEXT NOT NULL,
    alarm        INTEGER NOT NULL DEFAULT 0,
    cause        TEXT NOT NULL DEFAULT '',
    confidence   REAL NOT NULL DEFAULT 0,
    source       TEXT NOT NULL DEFAULT 'signal',
    confirmed_by TEXT,
    confirmed_at REAL
);

CREATE INDEX IF NOT EXISTS idx_events_start ON events (start_ts);
CREATE INDEX IF NOT EXISTS idx_events_machine ON events (machine, start_ts);

CREATE TABLE IF NOT EXISTS alerts (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    ts       REAL NOT NULL,
    machine  TEXT NOT NULL,
    kind     TEXT NOT NULL,
    message  TEXT NOT NULL,
    ack      INTEGER NOT NULL DEFAULT 0,
    ack_at   REAL
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS machines (
    id             TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    host           TEXT NOT NULL,
    port           INTEGER NOT NULL,
    unit           INTEGER NOT NULL,
    ideal_cycle_ms INTEGER NOT NULL,
    enabled        INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS commands (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    ts      REAL NOT NULL,
    machine TEXT NOT NULL,
    kind    TEXT NOT NULL,
    seconds REAL NOT NULL,
    done    INTEGER NOT NULL DEFAULT 0
);
"""


def connect(path: Path | str = DB_PATH) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


_READY: set[str] = set()


def ready(path: Path | str = DB_PATH) -> sqlite3.Connection:
    """Open a connection, creating the schema once per process.

    Running the schema script (and switching journal mode) on every request
    takes a write lock, which makes the dashboard wait on the collector.
    """
    key = str(Path(path).resolve())
    if key not in _READY:
        conn = init(path)
        _READY.add(key)
        return conn
    return connect(path)


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, decl: str) -> None:
    names = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in names:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def init(path: Path | str = DB_PATH) -> sqlite3.Connection:
    from .config import MACHINES

    conn = connect(path)
    conn.executescript(SCHEMA)
    _ensure_column(conn, "alerts", "ack_at", "REAL")

    if not conn.execute("SELECT 1 FROM machines LIMIT 1").fetchone():
        conn.executemany(
            "INSERT INTO machines (id, name, host, port, unit, ideal_cycle_ms, enabled) "
            "VALUES (?, ?, ?, ?, ?, ?, 1)",
            [(m.id, m.name, m.host, m.port, m.unit, m.ideal_cycle_ms) for m in MACHINES],
        )
    conn.commit()
    return conn


def insert_samples(conn: sqlite3.Connection, rows: list[tuple]) -> None:
    conn.executemany(
        "INSERT OR REPLACE INTO samples "
        "(ts, machine, running, fault, planned, parts, good, last_cycle, ideal_cycle, alarm) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )


def window(conn: sqlite3.Connection, start: float, end: float, machine: str | None = None):
    sql = ("SELECT ts, machine, running, fault, planned, parts, good, last_cycle, ideal_cycle, alarm "
           "FROM samples WHERE ts >= ? AND ts <= ?")
    args: list = [start, end]
    if machine:
        sql += " AND machine = ?"
        args.append(machine)
    sql += " ORDER BY machine, ts"
    return conn.execute(sql, args).fetchall()


# ------------------------------------------------------------------ settings
def settings_all(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute("INSERT INTO settings (key, value) VALUES (?, ?) "
                 "ON CONFLICT(key) DO UPDATE SET value = excluded.value", (key, value))


# ------------------------------------------------------------------ machines
def machines_all(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM machines ORDER BY id")]


def machines_enabled(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM machines WHERE enabled = 1 ORDER BY id")]


def save_machine(conn: sqlite3.Connection, machine: dict) -> None:
    conn.execute(
        "INSERT INTO machines (id, name, host, port, unit, ideal_cycle_ms, enabled) "
        "VALUES (:id, :name, :host, :port, :unit, :ideal_cycle_ms, :enabled) "
        "ON CONFLICT(id) DO UPDATE SET name=excluded.name, host=excluded.host, port=excluded.port, "
        "unit=excluded.unit, ideal_cycle_ms=excluded.ideal_cycle_ms, enabled=excluded.enabled",
        machine,
    )


# ------------------------------------------------------------------ commands
def queue_command(conn: sqlite3.Connection, machine: str, kind: str, seconds: float, now: float) -> None:
    conn.execute("INSERT INTO commands (ts, machine, kind, seconds, done) VALUES (?, ?, ?, ?, 0)",
                 (now, machine, kind, seconds))


def pending_commands(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM commands WHERE done = 0 ORDER BY id").fetchall()


def complete_command(conn: sqlite3.Connection, command_id: int) -> None:
    conn.execute("UPDATE commands SET done = 1 WHERE id = ?", (command_id,))
