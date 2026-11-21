"""OEE, the loss tree, the downtime pareto and the shift history.

Everything is computed from the two tables that actually exist: samples (one row
per machine per second) and events (written by the classifier). No number on the
dashboard is typed in by hand.
"""

from __future__ import annotations

from collections import defaultdict

from . import db
from .classify import classify
from .config import ALARM_CODES

CATEGORY_LABELS = {
    "planned": "Planned stop",
    "fault": "Breakdown",
    "micro": "Micro-stop",
    "idle": "Idle",
    "unknown": "Unknown",
}

EXPLAINED = ("fault", "planned", "micro")


# ------------------------------------------------------------------ helpers
def scan(conn, start: float, end: float) -> dict[str, dict]:
    """One pass over the window: run time, planned time, reset-tolerant parts.

    A single ordered scan is roughly twice as fast as the two aggregate queries
    this replaces, and it also yields the per-minute part deltas the live chart
    needs. On a plant PC that difference is the difference between a dashboard
    that feels instant and one that does not.
    """
    totals: dict[str, dict] = {}
    rows = conn.execute(
        "SELECT ts, machine, running, fault, planned, parts, good, last_cycle, ideal_cycle, alarm "
        "FROM samples WHERE ts >= ? AND ts <= ? ORDER BY machine, ts",
        (start, end),
    )
    for row in rows:
        entry = totals.get(row["machine"])
        if entry is None:
            entry = totals[row["machine"]] = {
                "n": 0, "run_s": 0, "planned_s": 0, "parts": 0, "good": 0,
                "per_minute": {}, "last": row, "_parts": None, "_good": None,
            }
        entry["n"] += 1
        entry["run_s"] += int(row["running"])
        entry["planned_s"] += int(row["planned"])
        if entry["_parts"] is not None:
            dp = int(row["parts"]) - entry["_parts"]
            dg = int(row["good"]) - entry["_good"]
            if dp >= 0:
                entry["parts"] += dp
                if dg >= 0:
                    entry["good"] += min(dg, dp)
                minute = int(row["ts"] // 60)
                entry["per_minute"][minute] = entry["per_minute"].get(minute, 0) + dp
        entry["_parts"] = int(row["parts"])
        entry["_good"] = int(row["good"])
        entry["last"] = row
    for entry in totals.values():
        entry.pop("_parts", None)
        entry.pop("_good", None)
    return totals


def _machine_totals(conn, start: float, end: float) -> dict[str, dict]:
    totals = {}
    for machine_id, entry in scan(conn, start, end).items():
        totals[machine_id] = {
            "machine": machine_id,
            "n": entry["n"],
            "run_s": entry["run_s"],
            "planned_s": entry["planned_s"],
            "parts": entry["parts"],
            "good": entry["good"],
            "ideal_cycle": int(entry["last"]["ideal_cycle"]),
            "last_ts": float(entry["last"]["ts"]),
            "alarm": int(entry["last"]["alarm"]),
        }
    return totals


def _latest(conn, start: float, end: float) -> dict[str, dict]:
    """Last stored sample per machine inside the window."""
    return {machine_id: dict(entry["last"]) for machine_id, entry in scan(conn, start, end).items()}


def events_window(conn, start: float, end: float) -> list[dict]:
    return [
        dict(r)
        for r in conn.execute(
            "SELECT * FROM events WHERE start_ts >= ? AND start_ts <= ? ORDER BY start_ts DESC",
            (start, end),
        )
    ]


def open_stops(conn, latest: dict[str, dict], cfg: dict | None = None) -> list[dict]:
    """A stop that is still running, so the screen is honest before it ends."""
    cfg = cfg or {}
    idle_split = float(cfg.get("idle_split_s", 300))
    out: list[dict] = []
    for machine_id, last in latest.items():
        running, fault, planned = int(last["running"]), int(last["fault"]), int(last["planned"])
        if running and not fault and not planned:
            continue

        signature = (running, fault, planned)
        start = float(last["ts"])
        rows = conn.execute(
            "SELECT ts, running, fault, planned FROM samples WHERE machine = ? AND ts <= ? "
            "ORDER BY ts DESC LIMIT 7200",
            (machine_id, float(last["ts"])),
        ).fetchall()
        for row in rows:
            if (int(row["running"]), int(row["fault"]), int(row["planned"])) != signature:
                break
            start = float(row["ts"])

        seconds = max(0.0, float(last["ts"]) - start)
        if seconds < 2:
            continue

        alarm = int(last["alarm"] or 0)
        if fault:
            category, cause, confidence = "fault", ALARM_CODES.get(alarm) or "Fault, no alarm code published", 0.98
        elif planned:
            category, cause, confidence = "planned", "Changeover / planned maintenance (coil 00003)", 0.97
        elif seconds < idle_split:
            category, cause, confidence = "idle", "Short stop, no fault and no planned signal", 0.8
        else:
            category, cause, confidence = "unknown", "Stopped with no fault, no planned signal, no alarm", 0.35

        out.append({
            "id": None,
            "machine": machine_id,
            "category": category,
            "cause": cause,
            "seconds": round(seconds, 1),
            "confidence": confidence,
            "start_ts": start,
            "open": True,
        })
    return out


# ------------------------------------------------------------------ summary
def summarize(conn, start: float, end: float, cfg: dict | None = None,
              scanned: dict[str, dict] | None = None) -> dict:
    cfg = cfg or {}
    total_s = max(end - start, 1.0)
    machines: list[dict] = []
    totals = scanned if scanned is not None else scan(conn, start, end)
    events = events_window(conn, start, end)

    by_machine_events: dict[str, list[dict]] = defaultdict(list)
    for event in events:
        by_machine_events[event["machine"]].append(event)

    for machine_id, agg in totals.items():
        machine_events = by_machine_events.get(machine_id, [])
        last = agg["last"]
        run_s = int(agg["run_s"])
        planned_s = int(agg["planned_s"])
        parts = int(agg["parts"])
        good = int(agg["good"])
        ideal_ms = int(last["ideal_cycle"] or 1000)
        ideal_s = ideal_ms / 1000.0

        planned_time = max(total_s - planned_s, 1.0)
        availability = min(run_s / planned_time, 1.0)
        performance = min((parts * ideal_s) / run_s, 1.0) if run_s else 0.0
        quality = (good / parts) if parts else 0.0
        oee = availability * performance * quality

        by_cat: dict[str, float] = defaultdict(float)
        for event in machine_events:
            by_cat[event["category"]] += float(event["seconds"])

        age = round(max(0.0, end - float(last["ts"] or end)), 1)
        if last["fault"]:
            state = "fault"
        elif last["planned"]:
            state = "planned"
        elif last["running"]:
            state = "running"
        else:
            state = "stopped"

        machines.append({
            "machine": machine_id,
            "state": state,
            "parts": parts,
            "good": good,
            "rejects": max(parts - good, 0),
            "ideal_cycle_ms": ideal_ms,
            "last_cycle_ms": int(last["last_cycle"] or 0),
            "alarm": int(last["alarm"] or 0),
            "run_s": run_s,
            "planned_s": planned_s,
            "coverage": round(min(100.0, (int(agg["n"]) / total_s) * 100), 0),
            "availability": round(availability * 100, 1),
            "performance": round(performance * 100, 1),
            "quality": round(quality * 100, 1),
            "oee": round(oee * 100, 1),
            "downtime": {k: round(v) for k, v in by_cat.items()},
            "last_signal_age": age,
        })

    latest = {machine_id: dict(agg["last"]) for machine_id, agg in totals.items()}
    return {
        "window": {"start": start, "end": end, "seconds": round(total_s)},
        "machines": machines,
        "line": _rollup(machines),
        "events": events,
        "active": open_stops(conn, latest, cfg),
    }


def _rollup(machines: list[dict]) -> dict:
    if not machines:
        return {"oee": 0, "availability": 0, "performance": 0, "quality": 0, "parts": 0, "good": 0}
    n = len(machines)
    return {
        "oee": round(sum(m["oee"] for m in machines) / n, 1),
        "availability": round(sum(m["availability"] for m in machines) / n, 1),
        "performance": round(sum(m["performance"] for m in machines) / n, 1),
        "quality": round(sum(m["quality"] for m in machines) / n, 1),
        "parts": sum(m["parts"] for m in machines),
        "good": sum(m["good"] for m in machines),
    }


def loss_tree(summary: dict) -> list[tuple[str, float]]:
    """Minutes lost per bucket the signals can actually support."""
    buckets = {"breakdown": 0.0, "changeover": 0.0, "micro": 0.0, "slow": 0.0, "defect": 0.0}
    for m in summary["machines"]:
        buckets["breakdown"] += m["downtime"].get("fault", 0)
        buckets["changeover"] += m["downtime"].get("planned", 0)
        buckets["micro"] += m["downtime"].get("micro", 0)
        buckets["slow"] += m["run_s"] * (1 - m["performance"] / 100)
        # rejects become time at the ideal cycle, so every bucket is seconds
        buckets["defect"] += m["rejects"] * m["ideal_cycle_ms"] / 1000.0
    return sorted(buckets.items(), key=lambda kv: kv[1], reverse=True)


def pareto(summary: dict) -> list[tuple[str, float]]:
    totals: dict[str, float] = defaultdict(float)
    for m in summary["machines"]:
        for cat, seconds in m["downtime"].items():
            totals[cat] += seconds
    return sorted(
        ((CATEGORY_LABELS.get(k, k), round(v / 60, 1)) for k, v in totals.items() if v > 0),
        key=lambda kv: kv[1], reverse=True,
    )


def coverage(summary: dict) -> float:
    """Share of classified stop time that has a signal-derived reason."""
    explained = total = 0.0
    for m in summary["machines"]:
        for category, seconds in m["downtime"].items():
            total += seconds
            if category in EXPLAINED:
                explained += seconds
    return round(explained / total * 100, 1) if total else 0.0


# ------------------------------------------------------------------ history
def shift_windows(conn, hours: float = 8, limit: int = 6) -> list[tuple[float, float]]:
    row = conn.execute("SELECT MIN(ts) AS a, MAX(ts) AS b FROM samples").fetchone()
    if not row or row["a"] is None:
        return []
    block = hours * 3600
    end = float(row["b"])
    first = float(row["a"])
    out: list[tuple[float, float]] = []
    while len(out) < limit and end - block >= first - 1:
        out.append((end - block, end))
        end -= block
    return out


def quick_rollup(conn, start: float, end: float) -> dict:
    """Cheap per-shift numbers for the history table."""
    total_s = max(end - start, 1.0)
    totals = _machine_totals(conn, start, end)
    machines = []
    for agg in totals.values():
        run_s = int(agg["run_s"] or 0)
        planned_s = int(agg["planned_s"] or 0)
        parts = int(agg["parts"] or 0)
        good = int(agg["good"] or 0)
        ideal_s = int(agg["ideal_cycle"] or 1000) / 1000.0
        planned_time = max(total_s - planned_s, 1.0)
        availability = min(run_s / planned_time, 1.0)
        performance = min((parts * ideal_s) / run_s, 1.0) if run_s else 0.0
        quality = (good / parts) if parts else 0.0
        machines.append({
            "oee": availability * performance * quality * 100,
            "availability": availability * 100,
            "performance": performance * 100,
            "quality": quality * 100,
            "parts": parts,
            "good": good,
        })
    line = _rollup([
        {**m, "oee": round(m["oee"], 1), "availability": round(m["availability"], 1),
         "performance": round(m["performance"], 1), "quality": round(m["quality"], 1)}
        for m in machines
    ])
    top = conn.execute(
        "SELECT category, SUM(seconds) AS s FROM events WHERE start_ts >= ? AND start_ts <= ? "
        "GROUP BY category ORDER BY s DESC LIMIT 1",
        (start, end),
    ).fetchone()
    return {
        "line": line,
        "top": (CATEGORY_LABELS.get(top["category"], top["category"]), round(top["s"] / 60, 1))
        if top else ("—", 0.0),
    }


def shift_table(conn, blocks: list[tuple[float, float]]) -> list[dict]:
    """Roll up every stored shift without re-reading six shifts of raw samples.

    The parts counter resets when a machine is restarted, so a shift's output is
    the sum of the positive counter steps, not last minus first. That is
    computed per minute here, and a minute that contains a reset is re-read
    exactly. Run time and planned time are summed by SQLite in one pass.
    """
    if not blocks:
        return []
    block = blocks[0][1] - blocks[0][0]
    low = min(b[0] for b in blocks)
    high = max(b[1] for b in blocks)

    minutes = conn.execute(
        "SELECT CAST(ts / 60 AS INTEGER) AS minute, machine, "
        "       MAX(parts) AS pmax, MIN(parts) AS pmin, MAX(good) AS gmax, MIN(good) AS gmin, "
        "       COUNT(*) AS n, SUM(running) AS run_s, SUM(planned) AS planned_s, "
        "       MAX(ideal_cycle) AS ideal_cycle "
        "FROM samples WHERE ts >= ? AND ts <= ? "
        "GROUP BY minute, machine ORDER BY machine, minute",
        (low, high),
    ).fetchall()

    buckets: dict[tuple[int, str], dict] = {}
    previous: dict[str, tuple[int, int]] = {}
    suspect: list[tuple[str, int, int]] = []

    for row in minutes:
        machine = row["machine"]
        minute = int(row["minute"])
        pmax, pmin = int(row["pmax"] or 0), int(row["pmin"] or 0)
        gmax, gmin = int(row["gmax"] or 0), int(row["gmin"] or 0)
        prior = previous.get(machine)
        if prior is None:
            # first minute of the whole range: the counter starts where it was
            last_parts, last_good, exact = pmin, gmin, False
        else:
            last_parts, last_good = prior
            exact = (pmin < last_parts <= pmax) or (gmin < last_good <= gmax)

        if pmax >= last_parts:
            parts = pmax - last_parts
        else:
            parts = pmax  # counter reset between minutes
        if gmax >= last_good:
            good = gmax - last_good
        else:
            good = gmax
        if exact:
            suspect.append((machine, minute))
            parts = good = 0

        previous[machine] = (pmax, gmax)

        slot = int((minute * 60 - low) / block)
        if slot < 0 or slot >= len(blocks):
            continue
        shift = len(blocks) - 1 - slot  # blocks are newest first
        bucket = buckets.setdefault((shift, machine), {
            "n": 0, "run_s": 0, "planned_s": 0, "parts": 0, "good": 0,
            "ideal_cycle": int(row["ideal_cycle"] or 1000),
        })
        bucket["n"] += int(row["n"] or 0)
        bucket["run_s"] += int(row["run_s"] or 0)
        bucket["planned_s"] += int(row["planned_s"] or 0)
        bucket["parts"] += parts
        bucket["good"] += good

    for machine, minute in suspect:
        rows = conn.execute(
            "SELECT parts, good FROM samples WHERE machine = ? AND ts >= ? AND ts < ? ORDER BY ts",
            (machine, minute * 60, (minute + 1) * 60),
        ).fetchall()
        last_parts = last_good = None
        parts = good = 0
        for row in rows:
            if last_parts is not None:
                step = int(row["parts"]) - last_parts
                parts += step if step >= 0 else int(row["parts"])
                step = int(row["good"]) - last_good
                good += step if step >= 0 else int(row["good"])
            last_parts, last_good = int(row["parts"]), int(row["good"])
        slot = int((minute * 60 - low) / block)
        shift = len(blocks) - 1 - slot
        bucket = buckets.get((shift, machine))
        if bucket is not None:
            bucket["parts"] += parts
            bucket["good"] += good

    top_rows = conn.execute(
        "SELECT CAST((start_ts - ?) / ? AS INTEGER) AS shift, category, SUM(seconds) AS s "
        "FROM events WHERE start_ts >= ? AND start_ts <= ? "
        "GROUP BY shift, category ORDER BY s DESC",
        (low, block, low, high),
    ).fetchall()
    top: dict[int, tuple[str, float]] = {}
    for row in top_rows:
        top.setdefault(int(row["shift"]), (CATEGORY_LABELS.get(row["category"], row["category"]),
                                           round(float(row["s"]) / 60, 1)))

    per_shift: dict[int, list[dict]] = defaultdict(list)
    for (shift, _), agg in buckets.items():
        run_s, planned_s = agg["run_s"], agg["planned_s"]
        parts = max(0, agg["parts"])
        good = min(max(0, agg["good"]), parts)
        ideal_s = agg["ideal_cycle"] / 1000.0
        planned_time = max(block - planned_s, 1.0)
        availability = min(run_s / planned_time, 1.0)
        performance = min((parts * ideal_s) / run_s, 1.0) if run_s else 0.0
        quality = (good / parts) if parts else 0.0
        per_shift[shift].append({
            "oee": round(availability * performance * quality * 100, 1),
            "availability": round(availability * 100, 1),
            "performance": round(performance * 100, 1),
            "quality": round(quality * 100, 1),
            "parts": parts,
            "good": good,
        })

    out = []
    for index, (start, end) in enumerate(blocks):
        out.append({
            "start": start,
            "end": end,
            "line": _rollup(per_shift.get(index, [])),
            "top": top.get(index, ("—", 0.0)),
        })
    return out


# ------------------------------------------------------------------ rebuild
def recompute_events(conn, start: float, end: float, cfg: dict | None = None) -> int:
    """Bring signal events for a window up to date without losing their identity.

    The collector re-runs this every few seconds. Deleting and re-inserting rows
    would hand every stop a new id, so a link a supervisor just opened would go
    stale. Events are matched on (machine, start) and updated in place; only a
    stop that no longer exists in the signals is removed. A row a person
    confirmed is never touched.
    """
    cfg = cfg or {}
    written = 0
    machines = [r["machine"] for r in conn.execute(
        "SELECT DISTINCT machine FROM samples WHERE ts >= ? AND ts <= ?", (start, end))]
    for machine in machines:
        rows = db.window(conn, start, end, machine)
        confirmed = conn.execute(
            "SELECT start_ts, end_ts FROM events WHERE machine = ? AND confirmed_by IS NOT NULL",
            (machine,),
        ).fetchall()
        fresh = [
            event for event in classify(machine, rows, cfg)
            if not any(event.start_ts < c["end_ts"] and event.end_ts > c["start_ts"] for c in confirmed)
        ]
        existing = {
            round(float(r["start_ts"]), 3): r
            for r in conn.execute(
                "SELECT * FROM events WHERE machine = ? AND start_ts >= ? AND start_ts <= ? "
                "AND confirmed_by IS NULL", (machine, start, end))
        }
        keep = set()
        for event in fresh:
            key = round(event.start_ts, 3)
            keep.add(key)
            old = existing.get(key)
            if old is None:
                conn.execute(
                    "INSERT INTO events (machine, start_ts, end_ts, seconds, category, alarm, cause, "
                    "confidence, source, confirmed_by, confirmed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    event.as_row(),
                )
                written += 1
                continue
            new = (round(float(event.end_ts), 3), round(float(event.seconds), 1),
                   event.category, int(event.alarm or 0), event.cause,
                   round(float(event.confidence), 2))
            current = (round(float(old["end_ts"]), 3), round(float(old["seconds"]), 1),
                       old["category"], int(old["alarm"] or 0), old["cause"],
                       round(float(old["confidence"]), 2))
            if new != current:
                conn.execute(
                    "UPDATE events SET end_ts = ?, seconds = ?, category = ?, alarm = ?, cause = ?, "
                    "confidence = ?, source = 'signal' WHERE id = ?",
                    (event.end_ts, event.seconds, event.category, int(event.alarm or 0),
                     event.cause, event.confidence, old["id"]),
                )
                written += 1
        for key, old in existing.items():
            if key not in keep:
                conn.execute("DELETE FROM events WHERE id = ?", (old["id"],))
    conn.commit()
    return written
