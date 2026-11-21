"""Generate deterministic shifts, so charts and reports have history.

    python -m linesight.seed --shifts 6 --hours 8 --fresh

This is the same machine model the live simulator uses, sampled at 1 Hz and run
through the same classifier. It is a simulated history and every surface that
shows it says so.
"""

from __future__ import annotations

import argparse
import time

from . import analytics, db, settings as settings_mod
from .config import MACHINES
from .model import MachineModel


def main() -> None:
    parser = argparse.ArgumentParser(description="seed simulated shifts")
    parser.add_argument("--hours", type=float, default=8.0)
    parser.add_argument("--shifts", type=int, default=6)
    parser.add_argument("--db", default=str(db.DB_PATH))
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--fresh", action="store_true", help="clear samples and events first")
    args = parser.parse_args()

    conn = db.init(args.db)
    cfg = settings_mod.load(conn)
    if args.fresh:
        conn.execute("DELETE FROM samples")
        conn.execute("DELETE FROM events")
        conn.execute("DELETE FROM alerts")
        conn.commit()

    hours = args.hours
    end = time.time()
    total_events = 0

    for shift in range(args.shifts):
        block_end = end - shift * hours * 3600
        block_start = block_end - hours * 3600

        for index, machine in enumerate(MACHINES):
            model = MachineModel(machine, args.seed + index + shift * 10, block_start, hours * 3600)
            rows = []
            t = block_start
            written = 0
            while t < block_end:
                coils, registers = model.at(t)
                rows.append((
                    round(t, 3), machine.id, coils[0], coils[1], coils[2],
                    registers[0], registers[1], registers[2], registers[3], registers[4],
                ))
                t += 1.0
                if len(rows) >= 5000:
                    db.insert_samples(conn, rows)
                    conn.commit()
                    written += len(rows)
                    rows.clear()
            if rows:
                db.insert_samples(conn, rows)
                conn.commit()
                written += len(rows)
            if shift == 0:
                print(f"  {machine.id:9} {written:6d} samples  parts {model.parts:5d}  good {model.good:5d}")

        events = analytics.recompute_events(conn, block_start, block_end, cfg)
        total_events += events
        print(f"  shift -{shift}  {time.strftime('%d %b %H:%M', time.localtime(block_start))}"
              f" -> {time.strftime('%H:%M', time.localtime(block_end))}  {events:3d} events")

    print(f"\n{total_events} events classified from the signals")
    print(f"database {args.db}")
    conn.close()


if __name__ == "__main__":
    main()
