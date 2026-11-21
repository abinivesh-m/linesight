"""Check the classifier against ground truth and sanity-check the store.

    python -m linesight.selftest

The simulator knows what it did. The classifier does not. This replays a shift,
classifies it from the signals only, and scores the result second by second.
"""

from __future__ import annotations

import sys
import time

from . import analytics, db, settings as settings_mod
from .classify import classify
from .config import MACHINES
from .model import MachineModel

CODES = {"running": 0, "fault": 1, "planned": 2, "micro": 3, "other": 4}
NAMES = {v: k for k, v in CODES.items()}


def shift_samples(model: MachineModel, start: float, end: float) -> list[dict]:
    rows = []
    t = start
    while t < end:
        coils, registers = model.at(t)
        rows.append({
            "ts": t, "machine": model.machine.id, "running": coils[0], "fault": coils[1],
            "planned": coils[2], "parts": registers[0], "good": registers[1],
            "last_cycle": registers[2], "ideal_cycle": registers[3], "alarm": registers[4],
        })
        t += 1.0
    return rows


def truth_codes(model: MachineModel, start: float, end: float) -> list[int]:
    codes = [0] * int(end - start)
    mapping = {"fault": 1, "planned": 2, "micro": 3, "idle": 4}
    for segment in model.segments:
        lo = max(int(segment.start), 0)
        hi = min(int(segment.end), len(codes))
        for i in range(lo, hi):
            codes[i] = mapping.get(segment.kind, 4)
    return codes


def inferred_codes(events, start: float, end: float) -> list[int]:
    codes = [0] * int(end - start)
    mapping = {"fault": 1, "planned": 2, "micro": 3, "idle": 4, "unknown": 4}
    for event in events:
        lo = max(int(event.start_ts - start), 0)
        hi = min(int(event.end_ts - start), len(codes))
        code = mapping.get(event.category, 4)
        for i in range(lo, hi):
            codes[i] = code
    return codes


def main() -> int:
    hours = 8
    end = time.time()
    start = end - hours * 3600
    cfg = settings_mod.defaults()

    truth_all: list[int] = []
    guess_all: list[int] = []
    per_machine: list[tuple[str, float]] = []

    print("LineSight selftest")
    print(f"  replayed {hours}h of simulated signals, 3 machines, 1 Hz")

    for index, machine in enumerate(MACHINES):
        model = MachineModel(machine, 101 + index, start, hours * 3600)
        rows = shift_samples(model, start, end)
        truth = truth_codes(model, start, end)
        events = classify(machine.id, rows, cfg)
        guess = inferred_codes(events, start, end)

        stop_seconds = sum(1 for code in truth if code != 0)
        agreed = sum(1 for t, g in zip(truth, guess) if t != 0 and t == g)
        per_machine.append((machine.id, agreed / max(stop_seconds, 1) * 100))
        print(f"  {machine.id:9} {stop_seconds:6d} stop seconds   {agreed:6d} agreed   "
              f"{agreed / max(stop_seconds, 1) * 100:5.1f}%")
        truth_all.extend(truth)
        guess_all.extend(guess)

    total = sum(1 for code in truth_all if code != 0)
    correct = sum(1 for t, g in zip(truth_all, guess_all) if t != 0 and t == g)
    accuracy = correct / max(total, 1) * 100

    print("\n  second-by-second agreement with the simulator's ground truth")
    print("  truth \\ guess   running   fault  planned    micro    other")
    for code, name in NAMES.items():
        row = [0] * 5
        for t, g in zip(truth_all, guess_all):
            if t == code:
                row[g] += 1
        cells = "".join(f"{v:9d}" for v in row)
        print(f"  {name:14}{cells}")

    print(f"\n  stop-second accuracy  {accuracy:.1f}%")

    # false micro-stops: running in truth, micro-stop in the guess
    false_micro = sum(1 for t, g in zip(truth_all, guess_all) if t == 0 and g == 3)
    missed_fault = sum(1 for t, g in zip(truth_all, guess_all) if t == 1 and g != 1)
    print(f"  false micro-stops     {false_micro} s")
    print(f"  fault seconds missed  {missed_fault} s")

    conn = db.init()
    try:
        samples = conn.execute("SELECT COUNT(*) c FROM samples").fetchone()["c"]
        events = conn.execute("SELECT COUNT(*) c FROM events").fetchone()["c"]
        bad = conn.execute("SELECT COUNT(*) c FROM events WHERE seconds <= 0").fetchone()["c"]
        settings = settings_mod.load(conn)
        print(f"\n  stored samples        {samples}")
        print(f"  stored events         {events}")
        print(f"  non-positive events   {bad}")
        print(f"  OEE target            {settings['oee_target']}%")
    finally:
        conn.close()

    ok = accuracy >= 90 and bad == 0
    print(f"\n  {'PASS' if ok else 'FAIL'}  (threshold: 90% agreement, no invalid events)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
