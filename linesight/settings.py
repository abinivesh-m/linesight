"""Configurable KPIs and thresholds, stored in SQLite so one PC needs no config file.

Every value the brief calls "configurable" is here: the targets, the shift
definition, the thresholds that turn signals into events, and the alert rule.
The Settings page writes these; the classifier, collector and dashboard read
them on every pass.
"""

from __future__ import annotations

from . import db

FIELDS: list[dict] = [
    # key, label, type, default, min, max, unit, help
    {"key": "line_name", "label": "Line name", "type": "text", "default": "Line 2",
     "help": "Shown in the header and on the shift report."},
    {"key": "site", "label": "Plant / site", "type": "text", "default": "Coimbatore",
     "help": "Shown in the header and on the shift report."},
    {"key": "shift_hours", "label": "Shift length", "type": "number", "default": 8, "min": 1, "max": 24,
     "unit": "h", "help": "Planned production time per shift."},
    {"key": "shift_start", "label": "Shift start", "type": "text", "default": "06:00",
     "help": "24-hour clock. Used for shift labels."},
    {"key": "oee_target", "label": "OEE target", "type": "number", "default": 65, "min": 1, "max": 100,
     "unit": "%", "help": "The line turns amber below target and red below half of it."},
    {"key": "micro_stop_factor", "label": "Micro-stop threshold", "type": "number", "default": 2.0,
     "min": 1.1, "max": 10, "unit": "x cycle",
     "help": "Running with no cycle pulse for this multiple of the ideal cycle is a micro-stop."},
    {"key": "idle_split_s", "label": "Idle vs unknown split", "type": "number", "default": 300,
     "min": 30, "max": 3600, "unit": "s",
     "help": "A stop shorter than this is reported as idle, longer as unknown."},
    {"key": "alert_stop_s", "label": "Alert after a stop of", "type": "number", "default": 600,
     "min": 60, "max": 7200, "unit": "s",
     "help": "Faults and unexplained stops longer than this raise an andon alert."},
    {"key": "demo_mode", "label": "Simulator controls", "type": "select", "default": "on",
     "options": ["on", "off"],
     "help": "Shows the fault-injection buttons. Turn off on a real plant."},
]

BY_KEY = {f["key"]: f for f in FIELDS}
NUMERIC = {"number", "text"}


def defaults() -> dict:
    return {f["key"]: f["default"] for f in FIELDS}


def load(conn) -> dict:
    stored = db.settings_all(conn)
    values = defaults()
    for key, raw in stored.items():
        field = BY_KEY.get(key)
        if field is None:
            continue
        try:
            values[key] = float(raw) if field["type"] == "number" else str(raw)
        except ValueError:
            continue
    return values


def save(conn, updates: dict) -> tuple[dict, list[str]]:
    """Validate then persist. Returns (values, errors)."""
    errors: list[str] = []
    clean: dict[str, str] = {}
    for key, raw in updates.items():
        field = BY_KEY.get(key)
        if field is None:
            continue
        text = str(raw).strip()
        if field["type"] == "number":
            try:
                number = float(text)
            except ValueError:
                errors.append(f"{field['label']} must be a number")
                continue
            if not field["min"] <= number <= field["max"]:
                errors.append(f"{field['label']} must be between {field['min']} and {field['max']}")
                continue
            clean[key] = str(number)
        elif field["type"] == "select":
            if text not in field.get("options", []):
                errors.append(f"{field['label']} is not a valid choice")
                continue
            clean[key] = text
        else:
            if not text or len(text) > 60:
                errors.append(f"{field['label']} must be 1-60 characters")
                continue
            clean[key] = text

    if not errors:
        for key, value in clean.items():
            db.set_setting(conn, key, value)
        conn.commit()
    return load(conn), errors
