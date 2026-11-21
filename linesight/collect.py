"""Poll every machine once a second, store the sample, classify the stops.

    python -m linesight.collect

Writes to data/linesight.db. Re-reads the machine list and the KPI settings every
few seconds, so a change on the Settings page applies without a restart.
"""

from __future__ import annotations

import argparse
import time

from pymodbus.client import ModbusTcpClient

from . import analytics, db, settings
from .config import ALERT_STOP_S


def read_machine(client: ModbusTcpClient, unit: int) -> tuple[list[int], list[int]] | None:
    coils = client.read_coils(0, count=3, device_id=unit)
    if coils.isError():
        return None
    registers = client.read_holding_registers(0, count=5, device_id=unit)
    if registers.isError():
        return None
    bits = [1 if b else 0 for b in coils.bits[:3]]
    return bits, [int(v) for v in registers.registers[:5]]


def raise_alerts(conn, start: float, stop_s: float = ALERT_STOP_S) -> int:
    rows = conn.execute(
        "SELECT machine, start_ts, seconds, category, cause FROM events "
        "WHERE start_ts >= ? AND seconds >= ? AND category IN ('fault', 'unknown')",
        (start, stop_s),
    ).fetchall()
    added = 0
    for row in rows:
        exists = conn.execute(
            "SELECT 1 FROM alerts WHERE machine = ? AND ts = ?", (row["machine"], row["start_ts"])
        ).fetchone()
        if exists:
            continue
        minutes = int(row["seconds"] // 60)
        conn.execute(
            "INSERT INTO alerts (ts, machine, kind, message) VALUES (?, ?, ?, ?)",
            (row["start_ts"], row["machine"], row["category"],
             f"{row['machine']} stopped {minutes} min - {row['cause']}"),
        )
        added += 1
    conn.commit()
    return added


class Rig:
    """Live machine list plus the KPI settings the classifier should use."""

    def __init__(self, conn) -> None:
        self.clients: dict[str, ModbusTcpClient] = {}
        self.connected: dict[str, bool] = {}
        self.machines: list[dict] = []
        self.cfg: dict = {}
        self.reload(conn)

    def reload(self, conn) -> None:
        self.machines = db.machines_enabled(conn)
        self.cfg = settings.load(conn)
        wanted = {m["id"] for m in self.machines}
        for machine in self.machines:
            if machine["id"] not in self.clients:
                self.clients[machine["id"]] = ModbusTcpClient(
                    machine["host"], port=int(machine["port"]), timeout=2, retries=1
                )
                self.connected[machine["id"]] = False
        for machine_id in list(self.clients):
            if machine_id not in wanted:
                self.clients[machine_id].close()
                del self.clients[machine_id]
                self.connected.pop(machine_id, None)


def main() -> None:
    parser = argparse.ArgumentParser(description="LineSight collector")
    parser.add_argument("--db", default=str(db.DB_PATH))
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--reclassify-every", type=float, default=15.0)
    parser.add_argument("--reload-every", type=float, default=10.0)
    parser.add_argument("--minutes", type=float, default=0, help="stop after N minutes (0 = forever)")
    parser.add_argument("--demo", action="store_true", help="auto-inject a fault every 90s for live demo")
    args = parser.parse_args()

    conn = db.init(args.db)
    rig = Rig(conn)
    started = time.time()
    deadline = started + args.minutes * 60 if args.minutes else None
    next_reclassify = started + args.reclassify_every
    next_demo = started + 30
    next_reload = started + args.reload_every
    samples = 0

    print(f"collector up: {len(rig.machines)} machines, {args.interval}s interval -> {args.db}")
    try:
        while True:
            now = time.time()

            if now >= next_reload:
                rig.reload(conn)
                next_reload = now + args.reload_every

            rows = []
            for machine in rig.machines:
                machine_id = machine["id"]
                client = rig.clients[machine_id]
                if not rig.connected.get(machine_id):
                    rig.connected[machine_id] = client.connect()
                if not rig.connected.get(machine_id):
                    continue
                reading = read_machine(client, int(machine["unit"]))
                if reading is None:
                    rig.connected[machine_id] = False
                    client.close()
                    continue
                (running, fault, planned), registers = reading
                rows.append((
                    round(now, 3), machine_id, running, fault, planned,
                    registers[0], registers[1], registers[2], registers[3], registers[4],
                ))

            if rows:
                db.insert_samples(conn, rows)
                conn.commit()
                samples += len(rows)

            if args.demo and now >= next_demo:
                import random
                m = random.choice([mm["id"] for mm in rig.machines])
                kind = random.choice(["fault", "micro", "idle"])
                secs = {"fault": 120, "micro": 60, "idle": 90}[kind]
                db.queue_command(conn, m, kind, secs, now)
                conn.commit()
                print(f"  DEMO: injected {kind} on {m} for {secs}s")
                next_demo = now + 90

            if now >= next_reclassify:
                analytics.recompute_events(conn, now - 6 * 3600, now, rig.cfg)
                raise_alerts(conn, now - 6 * 3600, float(rig.cfg.get("alert_stop_s", ALERT_STOP_S)))
                conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
                conn.commit()
                next_reclassify = now + args.reclassify_every
                print(f"  {int(now - started):5d}s  samples {samples:6d}  "
                      f"up {sum(rig.connected.values())}/{len(rig.machines)}")

            if deadline and now >= deadline:
                break
            time.sleep(max(0.0, args.interval - (time.time() - now)))
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        for client in rig.clients.values():
            client.close()
        conn.close()


if __name__ == "__main__":
    main()
