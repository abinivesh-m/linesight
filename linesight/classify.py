"""Turn raw signal samples into downtime events.

This is the part of the product that is not a dashboard: the reason for a stop
is inferred from the coil pattern, the cycle pulse and the alarm code, with a
confidence attached. A dropdown that asks an operator to remember yesterday is
what makes downtime data fiction.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import ALARM_CODES, IDLE_SPLIT_S, MICRO_STOP_FACTOR

RUNNING = "running"
PLANNED = "planned"
FAULT = "fault"
STOPPED = "stopped"
MICRO = "micro"
CONTRADICTION = "contradiction"


@dataclass
class Event:
    machine: str
    start_ts: float
    end_ts: float
    category: str
    cause: str
    confidence: float
    alarm: int = 0
    source: str = "signal"
    confirmed_by: str | None = None
    confirmed_at: float | None = None
    tags: list[str] = field(default_factory=list)

    @property
    def seconds(self) -> float:
        return round(self.end_ts - self.start_ts, 1)

    def as_row(self) -> tuple:
        return (
            self.machine, self.start_ts, self.end_ts, self.seconds, self.category,
            self.alarm, self.cause, self.confidence, self.source,
            self.confirmed_by, self.confirmed_at,
        )


def _label(row, last_change_ts: float, micro_threshold: float) -> str:
    running = int(row["running"])
    fault = int(row["fault"])
    planned = int(row["planned"])
    if running and (fault or planned):
        return CONTRADICTION
    if planned:
        return PLANNED
    if fault:
        return FAULT
    if running:
        if row["ts"] - last_change_ts >= micro_threshold:
            return MICRO
        return RUNNING
    return STOPPED


def classify(machine: str, rows, cfg: dict | None = None) -> list[Event]:
    """Classify one machine's samples (must be sorted by ts)."""
    cfg = cfg or {}
    events: list[Event] = []
    if not rows:
        return events

    idle_split = float(cfg.get("idle_split_s", IDLE_SPLIT_S))
    factor = float(cfg.get("micro_stop_factor", MICRO_STOP_FACTOR))
    ideal_s = max(int(rows[0]["ideal_cycle"]) / 1000.0, 1.0)
    micro_threshold = factor * ideal_s

    last_parts = int(rows[0]["parts"])
    last_change_ts = float(rows[0]["ts"])
    current: str | None = None
    start_ts = 0.0
    alarm = 0

    def close(label: str, start: float, end: float, code: int) -> None:
        seconds = end - start
        if seconds < 2:
            return
        if label == PLANNED:
            events.append(Event(machine, start, end, "planned",
                                "Changeover / planned maintenance (coil 00003)", 0.97))
        elif label == FAULT:
            cause = ALARM_CODES.get(code) or "Fault, no alarm code published"
            events.append(Event(machine, start, end, "fault", cause, 0.98, alarm=code))
        elif label == MICRO:
            # the counter moves one cycle after production restarts; the stop
            # ends when the machine could have produced again
            stop_end = max(start + 1.0, end - ideal_s)
            events.append(Event(machine, start, stop_end, "micro",
                                f"No cycle pulse for {seconds / ideal_s:.1f}x the ideal cycle", 0.75))
        elif label == CONTRADICTION:
            events.append(Event(machine, start, end, "unknown",
                                "Signals contradict (running and fault set together)", 0.2))
        elif label == STOPPED:
            if seconds < idle_split:
                events.append(Event(machine, start, end, "idle",
                                    "Short stop, no fault and no planned signal", 0.8))
            else:
                events.append(Event(machine, start, end, "unknown",
                                    "Stopped with no fault, no planned signal, no alarm", 0.35))

    for row in rows:
        ts = float(row["ts"])
        parts = int(row["parts"])
        if parts != last_parts:
            last_parts = parts
            last_change_ts = ts
        elif not int(row["running"]):
            # a stop breaks the cycle pulse; give the machine a full cycle to
            # restart before calling it a micro-stop
            last_change_ts = ts

        label = _label(row, last_change_ts, micro_threshold)
        if label != current:
            if current is not None:
                close(current, start_ts, ts, alarm)
            current = label
            # a micro-stop starts at the last cycle pulse, not at the moment the
            # threshold was crossed - otherwise every stop is reported as 1 cycle
            start_ts = last_change_ts if label == MICRO else ts
            alarm = int(row["alarm"])

    if current is not None:
        close(current, start_ts, float(rows[-1]["ts"]), alarm)

    return [e for e in events if e.category != RUNNING]
