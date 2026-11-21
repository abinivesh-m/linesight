"""Deterministic machine behaviour, used by both the live simulator and the seed.

The model only writes coils and holding registers. It never tells the classifier
what happened - the collector has to infer that from the signals, which is the
whole point of the project.
"""

from __future__ import annotations

import bisect
import random
from dataclasses import dataclass, field

from .config import ALARM_CODES, Machine


@dataclass
class Segment:
    start: float          # seconds from shift start
    end: float
    kind: str             # fault | planned | idle | micro
    alarm: int = 0


@dataclass
class MachineModel:
    machine: Machine
    seed: int
    start_ts: float
    horizon_s: float
    rng: random.Random = field(init=False)
    segments: list[Segment] = field(default_factory=list, init=False)
    forced: list[Segment] = field(default_factory=list, init=False)
    _starts: list[float] = field(default_factory=list, init=False)
    parts: int = 0
    good: int = 0
    last_cycle_ms: int = 0
    _next_part: float = 0.0
    _alarm: int = 0

    def __post_init__(self) -> None:
        self.rng = random.Random(self.seed)
        self.last_cycle_ms = self.machine.ideal_cycle_ms
        self._next_part = self.start_ts + self.machine.ideal_cycle_ms / 1000.0
        self._build_schedule()
        self.segments.sort(key=lambda s: s.start)
        self._starts = [s.start for s in self.segments]

    # ------------------------------------------------------------ schedule
    def _free(self, start: float, end: float) -> bool:
        return not any(s.start < end and s.end > start for s in self.segments)

    def _build_schedule(self) -> None:
        rng = self.rng
        horizon = self.horizon_s

        # planned maintenance / changeover, once per shift
        planned_at = rng.uniform(5400, 9000)
        self.segments.append(Segment(planned_at, planned_at + rng.uniform(720, 1500), "planned"))

        # breakdowns: first one early, so a live demo sees a cause inside minutes
        t = rng.uniform(75, 150)
        while t < horizon:
            duration = rng.uniform(180, 900)
            if self._free(t, t + duration):
                self.segments.append(Segment(t, t + duration, "fault", rng.choice([11, 12, 21, 22, 31, 41])))
            t += duration + rng.uniform(1200, 3000)

        # a short stop and a long unexplained stop, to exercise IDLE vs UNKNOWN
        for window, low, high in (((2100, 3600), 90, 240), ((9000, 12000), 360, 720)):
            at = rng.uniform(*window)
            end = at + rng.uniform(low, high)
            if self._free(at, end):
                self.segments.append(Segment(at, end, "idle"))

        # micro-stops: running stays true, the cycle pulse disappears
        t = rng.uniform(300, 900)
        while t < horizon:
            duration = rng.uniform(20, 90)
            if self._free(t, t + duration):
                self.segments.append(Segment(t, t + duration, "micro"))
            t += duration + rng.uniform(420, 900)

    # -------------------------------------------------------------- control
    def force(self, kind: str, seconds: float, now: float, alarm: int = 0) -> None:
        """Inject a stop at wall-clock time. Demo control, not part of the product."""
        if kind == "fault" and not alarm:
            alarm = self.rng.choice([11, 12, 21, 22, 31, 41])
        self.forced.append(Segment(now, now + seconds, kind, alarm))

    # -------------------------------------------------------------- sample
    def at(self, ts: float) -> tuple[list[int], list[int]]:
        """Return (coils, holding registers) at a wall-clock timestamp."""
        self.forced = [s for s in self.forced if s.end > ts]
        forced = next((s for s in self.forced if s.start <= ts < s.end), None)

        if forced is not None:
            segment: Segment | None = forced
        else:
            offset = ts - self.start_ts
            index = bisect.bisect_right(self._starts, offset) - 1
            segment = self.segments[index] if index >= 0 else None
            if segment is not None and offset >= segment.end:
                segment = None

        running = fault = planned = 0
        alarm = 0
        producing = True

        if segment is not None:
            if segment.kind == "fault":
                fault, producing = 1, False
                alarm = segment.alarm
            elif segment.kind == "planned":
                planned, producing = 1, False
            elif segment.kind == "idle":
                producing = False
            elif segment.kind == "micro":
                running, producing = 1, False
            else:  # pragma: no cover - defensive
                producing = False

        if producing:
            running = 1
            cycle_s = self.machine.ideal_cycle_ms / 1000.0
            guard = 0
            while self._next_part <= ts and guard < 10_000:
                self.parts += 1
                if self.rng.random() > 0.035:
                    self.good += 1
                self.last_cycle_ms = int(self.machine.ideal_cycle_ms * self.rng.uniform(0.92, 1.18))
                self._next_part += cycle_s
                guard += 1
        else:
            self._next_part = max(self._next_part, ts + self.machine.ideal_cycle_ms / 1000.0)

        self._alarm = alarm
        coils = [running, fault, planned, 0, 0, 0, 0, 0]
        regs = [self.parts, self.good, self.last_cycle_ms, self.machine.ideal_cycle_ms, alarm, 0, 0, 0]
        return coils, regs

    @property
    def alarm_text(self) -> str:
        return ALARM_CODES.get(self._alarm, "")
