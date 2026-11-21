"""Machines, register map and thresholds - the only file a plant edits."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Machine:
    id: str
    name: str
    host: str
    port: int
    unit: int
    ideal_cycle_ms: int


# Three machines, three endpoints, one register map. A real PLC on the same
# protocol needs its IP and its port here, nothing else.
MACHINES: tuple[Machine, ...] = (
    Machine("CNC-01", "CNC Lathe 1", "127.0.0.1", 5020, 1, 42_000),
    Machine("CNC-02", "CNC Lathe 2", "127.0.0.1", 5021, 2, 55_000),
    Machine("PRESS-01", "Hydraulic Press", "127.0.0.1", 5022, 3, 30_000),
)

BY_ID = {m.id: m for m in MACHINES}

# ---- register map (9 points per machine) ---------------------------------
COIL_RUNNING = 0
COIL_FAULT = 1
COIL_PLANNED = 2

REG_PARTS = 0
REG_GOOD = 1
REG_LAST_CYCLE = 2
REG_IDEAL_CYCLE = 3
REG_ALARM = 4

COIL_COUNT = 8
REG_COUNT = 8

# ---- classification ------------------------------------------------------
ALARM_CODES: dict[int, str] = {
    0: "",
    11: "Hydraulic pressure low",
    12: "Coolant flow lost",
    21: "Spindle overload",
    22: "Door interlock open",
    31: "Feed servo alarm",
    41: "Lubrication pressure low",
}

MICRO_STOP_FACTOR = 2.0     # no cycle pulse for 2x ideal cycle while running
IDLE_SPLIT_S = 300          # under 5 min -> idle, longer -> unknown
ALERT_STOP_S = 600          # a stop this long raises an andon alert

# Loss buckets the signals can actually support. Startup rejects need a
# first-off signal we do not read, so they are reported as "not instrumented"
# rather than guessed.
LOSS_LABELS = {
    "breakdown": "Breakdown",
    "changeover": "Changeover",
    "micro": "Micro-stop",
    "slow": "Slow cycle",
    "defect": "Defect",
}
