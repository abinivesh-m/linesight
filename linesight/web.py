"""The LineSight console: live floor, downtime, OEE, shifts, report, settings, how.

    python -m linesight.web --port 8000

Charts are inline SVG built on the server: no CDN, no build step, no internet.
"""

from __future__ import annotations

import argparse
import csv
import html
import io
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs

from fastapi import FastAPI, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response

from . import analytics, db, settings as settings_mod
from .config import ALARM_CODES

app = FastAPI(title="LineSight", docs_url=None, redoc_url=None)

ROOT = Path(__file__).resolve().parents[1]
SHOTS = ROOT / "docs" / "shots"

STATE_COLOURS = {
    "running": "#1b7f3b",
    "fault": "#ff3300",
    "planned": "#b07a1a",
    "stopped": "#6b6b6b",
}
STATE_WORDS = {
    "running": "Running",
    "fault": "Fault",
    "planned": "Planned",
    "stopped": "Stopped",
}
NAV = [
    ("/", "Live floor", "M3 12h4l3-7 4 14 3-7h4"),
    ("/alerts", "Alerts", "M12 9v4m0 4h.01M10.3 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"),
    ("/downtime", "Downtime", "M12 7v5l3 2M21 12a9 9 0 11-18 0 9 9 0 0118 0z"),
    ("/oee", "OEE & losses", "M12 3v9l7 4M21 12a9 9 0 11-9-9"),
    ("/machines", "Machines", "M2 7h20M2 12h20M2 17h20"),
    ("/trends", "Trends", "M3 17l6-6 4 4 8-8"),
    ("/shifts", "Shift history", "M4 5h16M4 12h16M4 19h10"),
    ("/report", "Shift report", "M7 3h10l3 3v15H7zM9 12h6M9 16h6"),
    ("/settings", "Settings", "M12 9a3 3 0 100 6 3 3 0 000-6zM4 12h2m12 0h2M12 4v2m0 12v2"),
    ("/how", "How it works", "M12 6v.01M11 10h1v7h1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"),
]


# --------------------------------------------------------------------- utils
def esc(value) -> str:
    return html.escape(str(value))


def hhmm(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def stamp(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d %b %H:%M")


def ago(ts: float) -> str:
    seconds = max(0, int(time.time() - ts))
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def dur(seconds: float) -> str:
    """Human duration: seconds under two minutes, minutes above."""
    if seconds < 120:
        return f"{seconds:.0f} s"
    if seconds < 7200:
        return f"{seconds / 60:.1f} min"
    return f"{seconds / 3600:.1f} h"


def window(minutes: int) -> tuple[float, float]:
    end = time.time()
    return end - minutes * 60, end


async def form(request: Request) -> dict[str, str]:
    body = (await request.body()).decode("utf-8", "replace")
    return {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}


def back(to: str) -> RedirectResponse:
    return RedirectResponse(to, status_code=303)


# --------------------------------------------------------------------- charts
def donut(percent: float, caption: str, size: int = 176, target: float = 65) -> str:
    radius = size / 2 - 14
    circumference = 2 * 3.141592653589793 * radius
    filled = max(0.0, min(percent, 100.0)) / 100 * circumference
    colour = "#1b7f3b" if percent >= target else ("#e08a00" if percent >= target * 0.7 else "#ff3300")
    tick = 2 * 3.141592653589793 * radius * min(max(target, 0), 100) / 100
    return f"""
<svg viewBox="0 0 {size} {size}" width="{size}" height="{size}" role="img" aria-label="OEE {percent}%">
  <circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="#eeeeec" stroke-width="14"/>
  <circle cx="{size/2}" cy="{size/2}" r="{radius}" fill="none" stroke="{colour}" stroke-width="14"
          stroke-dasharray="{filled:.1f} {circumference:.1f}" stroke-linecap="round"
          transform="rotate(-90 {size/2} {size/2})"/>
  <line x1="{size/2 + radius * 0.86:.1f}" y1="{size/2 - radius * 0.5:.1f}"
        x2="{size/2 + radius * 1.14:.1f}" y2="{size/2 - radius * 0.66:.1f}"
        stroke="{colour}" stroke-width="2" opacity="0.75"/>
  <text x="{size/2}" y="{size/2-4}" text-anchor="middle" font-size="32" font-weight="700" fill="#141414">{percent:.1f}%</text>
  <text x="{size/2}" y="{size/2+20}" text-anchor="middle" font-size="11" fill="#6b6b6b">{esc(caption)}</text>
</svg>"""


def hbars(items: list[tuple[str, float]], unit: str = "", width: int = 340, colour: str = "#ff3300") -> str:
    if not items:
        return '<p class="muted">no data in this window</p>'
    top = max(v for _, v in items) or 1
    row_h, label_w = 26, 110
    height = row_h * len(items) + 6
    parts = [f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">']
    for i, (label, value) in enumerate(items):
        y = i * row_h + 4
        bar_w = max(2.0, (width - label_w - 62) * value / top)
        parts.append(
            f'<text x="0" y="{y + 15}" font-size="11" fill="#333">{esc(label)}</text>'
            f'<rect x="{label_w}" y="{y + 4}" width="{bar_w:.1f}" height="14" rx="3" fill="{colour}" opacity="0.88"/>'
            f'<text x="{label_w + bar_w + 8:.1f}" y="{y + 15}" font-size="11" fill="#6b6b6b">{value:.1f}{unit}</text>'
        )
    parts.append("</svg>")
    return "".join(parts)


def spark(points: list[float], width: int = 640, height: int = 110) -> str:
    if len(points) < 2:
        return '<p class="muted">collecting…</p>'
    top = max(points) or 1
    step = width / (len(points) - 1)
    coords = " ".join(f"{i*step:.1f},{height - 10 - (v / top) * (height - 24):.1f}" for i, v in enumerate(points))
    area = f"0,{height} " + coords + f" {width},{height}"
    return f"""
<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" preserveAspectRatio="none" role="img">
  <polygon points="{area}" fill="#ff3300" opacity="0.07"/>
  <polyline points="{coords}" fill="none" stroke="#ff3300" stroke-width="2"/>
</svg>"""


def meter(label: str, percent: float, target: float = 85) -> str:
    colour = "#1b7f3b" if percent >= target else ("#e08a00" if percent >= target - 10 else "#ff3300")
    return f"""<div class="meter"><span>{esc(label)}</span>
  <div class="track"><div style="width:{max(0, min(percent, 100)):.1f}%;background:{colour}"></div></div>
  <b>{percent:.1f}%</b></div>"""


def timeline(rows, start: float, end: float) -> str:
    """Three coil tracks plus the part pulses around one event."""
    width, height = 860, 132
    span = max(end - start, 1.0)
    tracks = [("Running", "running", "#1b7f3b"), ("Fault", "fault", "#ff3300"), ("Planned", "planned", "#b07a1a")]
    parts = ['<svg viewBox="0 0 860 132" width="100%" height="132" role="img">']
    for index, (label, key, colour) in enumerate(tracks):
        y = 16 + index * 28
        parts.append(f'<text x="0" y="{y + 11}" font-size="10" fill="#6b6b6b">{label}</text>')
        parts.append(f'<rect x="86" y="{y}" width="{width-86}" height="14" rx="2" fill="#f1f1ee"/>')
        run_start = None
        previous = 0
        for row in rows:
            value = int(row[key])
            if value and run_start is None:
                run_start = float(row["ts"])
            if not value and run_start is not None:
                x1 = 86 + (run_start - start) / span * (width - 86)
                x2 = 86 + (float(row["ts"]) - start) / span * (width - 86)
                parts.append(f'<rect x="{x1:.1f}" y="{y}" width="{max(1.5, x2-x1):.1f}" height="14" rx="2" fill="{colour}" opacity="0.85"/>')
                run_start = None
            previous = value
        if run_start is not None:
            x1 = 86 + (run_start - start) / span * (width - 86)
            parts.append(f'<rect x="{x1:.1f}" y="{y}" width="{max(1.5, width-x1-2):.1f}" height="14" rx="2" fill="{colour}" opacity="0.85"/>')

    parts.append('<text x="0" y="112" font-size="10" fill="#6b6b6b">Part pulses</text>')
    parts.append(f'<rect x="86" y="101" width="{width-86}" height="14" rx="2" fill="#f1f1ee"/>')
    last = None
    for row in rows:
        value = int(row["parts"])
        if last is not None and value > last:
            x = 86 + (float(row["ts"]) - start) / span * (width - 86)
            parts.append(f'<rect x="{x:.1f}" y="101" width="2" height="14" fill="#141414" opacity="0.55"/>')
        last = value

    parts.append(f'<text x="86" y="128" font-size="10" fill="#9a9a96">{start and datetime.fromtimestamp(start).strftime("%H:%M:%S")}</text>')
    parts.append(f'<text x="{width}" y="128" text-anchor="end" font-size="10" fill="#9a9a96">{datetime.fromtimestamp(end).strftime("%H:%M:%S")}</text>')
    parts.append("</svg>")
    return "".join(parts)


def throughput(scanned: dict[str, dict], buckets: int = 60) -> list[float]:
    per_minute: dict[int, int] = {}
    for entry in scanned.values():
        for minute, produced in entry["per_minute"].items():
            per_minute[minute] = per_minute.get(minute, 0) + produced
    keys = sorted(per_minute)
    return [per_minute[k] for k in keys][-buckets:]


# -------------------------------------------------------------------- payload
def snapshot(conn, minutes: int, cfg: dict | None = None) -> dict:
    cfg = cfg or settings_mod.load(conn)
    start, end = window(minutes)
    scanned = analytics.scan(conn, start, end)
    summary = analytics.summarize(conn, start, end, cfg, scanned=scanned)

    machines = []
    names = {m["id"]: m["name"] for m in db.machines_all(conn)}
    for entry in summary["machines"]:
        machines.append({
            **entry,
            "name": names.get(entry["machine"], entry["machine"]),
            "alarm_text": ALARM_CODES.get(entry["alarm"], ""),
            "age_s": entry["last_signal_age"],
        })

    events = [
        {
            "id": e["id"],
            "machine": e["machine"],
            "category": e["category"],
            "cause": e["cause"],
            "seconds": e["seconds"],
            "confidence": e["confidence"],
            "source": e["source"],
            "at": hhmm(e["start_ts"]),
            "start_ts": e["start_ts"],
        }
        for e in summary["events"][:12]
    ]

    active = [
        {"machine": a["machine"], "category": a["category"], "cause": a["cause"],
         "seconds": a["seconds"], "confidence": a["confidence"], "since": hhmm(a["start_ts"])}
        for a in summary.get("active", [])
    ]

    alerts = [
        {"id": r["id"], "at": hhmm(r["ts"]), "machine": r["machine"], "kind": r["kind"],
         "message": r["message"], "ack": r["ack"]}
        for r in conn.execute("SELECT * FROM alerts ORDER BY ack, ts DESC LIMIT 6")
    ]

    pareto = analytics.pareto(summary)
    losses = analytics.loss_tree(summary)
    trend = throughput(scanned)
    unplanned = [item for item in pareto if item[0] != "Planned stop"] or pareto
    top_label, top_minutes = unplanned[0] if unplanned else ("—", 0.0)
    top_key = next((k for k, label in analytics.CATEGORY_LABELS.items() if label == top_label), None)

    return {
        "generated_at": datetime.now().strftime("%H:%M:%S"),
        "window_minutes": minutes,
        "line": summary["line"],
        "machines": machines,
        "events": events,
        "active": active,
        "alerts": alerts,
        "target": cfg.get("oee_target", 65),
        "line_name": cfg.get("line_name", "Line 2"),
        "site": cfg.get("site", "Coimbatore"),
        "headline": {
            "label": top_label,
            "minutes": top_minutes,
            "events": sum(1 for e in summary["events"] if e["category"] == top_key),
            "coverage": analytics.coverage(summary),
            "stop_events": len(summary["events"]),
        },
        "charts": {
            "oee": donut(summary["line"]["oee"], "line OEE", target=float(cfg.get("oee_target", 65))),
            "pareto": hbars(pareto, " min"),
            "loss": hbars([(k.title(), round(v / 60, 1)) for k, v in losses], " min"),
            "trend": spark(trend),
        },
    }


# ----------------------------------------------------------------------- shell
def nav_html(path: str, state: dict, alerts_open: int) -> str:
    items = []
    for href, label, icon in NAV:
        active = "active" if (path == href or (href != "/" and path.startswith(href))) else ""
        badge = ""
        if href in ("/downtime", "/alerts") and alerts_open:
            badge = f'<span class="badge">{alerts_open}</span>'
        items.append(
            f'<a class="nav {active}" href="{href}">'
            f'<svg viewBox="0 0 24 24" width="17" height="17" fill="none" stroke="currentColor" '
            f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="{icon}"/></svg>'
            f'<span>{label}</span>{badge}</a>'
        )

    dots = "".join(
        f'<div class="health"><span class="pdot" style="background:{STATE_COLOURS.get(m["state"], "#6b6b6b")}"></span>'
        f'<span>{esc(m["machine"])}</span><b>{m["oee"]:.0f}%</b></div>'
        for m in state["machines"]
    )
    return f"""
<aside class="side">
  <div class="brand">Line<span>Sight</span></div>
  <div class="site">{esc(state['line_name'])} · {esc(state['site'])}</div>
  <nav>{''.join(items)}</nav>
  <div class="health-block">
    <div class="kicker">Machines</div>{dots}
  </div>
  <div class="side-foot">Simulated shift · no plant data<br>Runs offline on one PC</div>
</aside>"""


def shell(path: str, state: dict, title: str, subtitle: str, body: str, minutes: int,
          actions: str = "", noscript: bool = False) -> str:
    alerts_open = sum(1 for a in state["alerts"] if not a["ack"])
    window_links = "".join(
        f'<a class="chip {"on" if minutes == m else ""}" href="{path}?minutes={m}">{label}</a>'
        for m, label in ((60, "1h"), (480, "8h"), (1440, "24h"))
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LineSight — {esc(title)}</title><style>{CSS}</style>
<link rel="preconnect" href="https://cdn.jsdelivr.net">
<script defer src="https://cdn.jsdelivr.net/npm/lenis@1.1.18/dist/lenis.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/gsap@3.12.5/dist/gsap.min.js"></script></head>
<body>
<div class="app">
  {nav_html(path, state, alerts_open)}
  <div class="main">
    <header class="topbar">
      <div>
        <h1>{esc(title)}</h1>
        <p class="sub">{subtitle}</p>
      </div>
      <div class="top-right">
        <div class="windows">{window_links}</div>
        <div class="live"><span class="dot" id="livedot"></span><span id="liveword">live</span>
          · <span id="clock">{state['generated_at']}</span></div>
      </div>
    </header>
    <main>{body}</main>
  </div>
</div>
<div id="toast" class="toast" role="status" aria-live="polite"></div>
<button class="theme-toggle" id="themeToggle" title="Toggle dark mode (d)" aria-label="Toggle dark mode">🌙</button>
<div id="cmdPalette" class="command-palette" hidden>
  <div>
    <input id="cmdInput" placeholder="Go to…" autocomplete="off">
    <div id="cmdResults" class="results"></div>
  </div>
</div>
<script>{JS if not noscript else ''}</script>
<script>
if (window.Lenis) {{ const lenis = new Lenis({{ lerp: 0.09, smoothWheel: true }}); function raf(t){{ lenis.raf(t); requestAnimationFrame(raf); }} requestAnimationFrame(raf); }}
if (window.gsap) {{ gsap.from('.card, .machine, .andon', {{ opacity: 0, y: 12, duration: 0.45, stagger: 0.04, ease: 'power2.out' }}); }}
</script>
</body></html>"""


# ------------------------------------------------------------------------ css
CSS = """
:root{--ink:#141414;--body:#2a2a2a;--muted:#6b6560;--line:#e6e0d4;--accent:#e63946;--panel:#ffffff;--bg:#f5f1e8;--side:#1f1a17}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--body);font:14px/1.45 Arial,Helvetica,sans-serif}
h1,.brand,.brief-big,.moee,.big,.stat .n,.paper h2{font-family:Georgia,'Times New Roman',serif;letter-spacing:-.4px;font-weight:700}
.app{display:flex;min-height:100vh}
.side{width:226px;flex:0 0 226px;background:var(--side);color:#f0ebe0;padding:22px 14px;position:sticky;top:0;height:100vh;display:flex;flex-direction:column}
.brand{font-size:22px;font-weight:700;color:#fff;letter-spacing:-.4px;padding:0 10px;font-family:Georgia,'Times New Roman',serif}
.brand span{color:var(--accent)}
.site{font-size:11px;color:#b8ad9a;padding:2px 10px 20px}
.nav{display:flex;align-items:center;gap:10px;padding:9px 10px;border-radius:7px;color:#e0d8c8;text-decoration:none;font-size:13px;position:relative;transition:background .15s ease}
.nav:hover{background:rgba(255,255,255,.06);color:#fff}
.nav.active{background:rgba(255,255,255,.08);color:#fff;box-shadow:inset 3px 0 0 var(--accent)}
.nav .badge{margin-left:auto;background:var(--accent);color:#fff;font-size:10px;font-weight:700;border-radius:9px;padding:1px 6px}
.health-block{margin-top:auto;padding:14px 10px 6px;border-top:1px solid rgba(255,255,255,.08)}
.kicker{font-size:10px;letter-spacing:.11em;text-transform:uppercase;color:#b8ad9a;margin-bottom:8px}
.health{display:flex;align-items:center;gap:7px;font-size:11.5px;color:#d8d0c0;padding:3px 0}
.health b{margin-left:auto;color:#fff;font-weight:600}
.pdot{width:7px;height:7px;border-radius:50%;display:inline-block}
.side-foot{font-size:10px;color:#8a8070;padding:12px 10px 0;line-height:1.5}
.main{flex:1;min-width:0}
.topbar{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;padding:22px 30px 16px;background:var(--bg)}
h1{margin:0;font-size:22px;letter-spacing:-.3px;color:var(--ink)}
.sub{margin:2px 0 0;font-size:12.5px;color:var(--muted)}
.top-right{display:flex;align-items:center;gap:16px}
.windows{display:flex;gap:2px;background:#eaeae6;padding:3px;border-radius:8px}
.chip{font-size:11.5px;padding:4px 10px;border-radius:6px;color:#555;text-decoration:none}
.chip.on{background:#fff;color:var(--ink);font-weight:700;box-shadow:0 1px 2px rgba(0,0,0,.08)}
.live{font-size:11.5px;color:var(--muted);display:flex;align-items:center;gap:7px}
.dot{width:8px;height:8px;border-radius:50%;background:#1b7f3b;box-shadow:0 0 0 3px rgba(27,127,59,.14)}
.dot.stale{background:#e08a00;box-shadow:0 0 0 3px rgba(224,138,0,.16)}
.andon{display:flex;align-items:center;gap:10px;background:#fff;border:1px solid #f3c9bb;border-left:4px solid var(--accent);border-radius:8px;padding:10px 14px;margin-bottom:12px;font-size:13px;color:#8a2a08}
.andon .adot{width:9px;height:9px;border-radius:50%;background:var(--accent);box-shadow:0 0 0 4px rgba(255,51,0,.14)}
.andon b{color:#7a2406}
.andon .atag{margin-left:auto;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:#b0502a}
tr.openrow td{background:#fff8f4;font-weight:600}
main{padding:0 30px 40px;max-width:1290px}
.grid{display:grid;gap:14px}
.machines{grid-template-columns:repeat(3,1fr);margin-bottom:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:18px 20px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 4px 14px rgba(0,0,0,.03);transition:box-shadow .2s ease,transform .2s ease}
.card h3{margin:0 0 12px;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
.machine{position:relative;overflow:hidden}
.machine:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--state,#999)}
.mhead{display:flex;align-items:baseline;justify-content:space-between;margin-bottom:10px}
.mstate{font-size:10.5px;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--state,#666)}
.machine h2{margin:0;font-size:15.5px;color:var(--ink)}
.moee{font-size:26px;font-weight:700;color:var(--ink);line-height:1}
.moee small{font-size:11px;color:var(--muted);font-weight:400;margin-left:4px}
.kv{display:flex;justify-content:space-between;font-size:12.5px;padding:2.5px 0;color:var(--muted)}
.kv b{color:var(--ink);font-weight:600}
.row-brief{display:flex;align-items:center;gap:26px;margin-bottom:14px;border-left:4px solid var(--accent)}
.brief-k{font-size:10px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.brief-big{font-size:22px;font-weight:700;color:var(--ink);letter-spacing:-.3px}
.brief-big i{font-style:normal;color:var(--accent)}
.brief-note{margin-left:auto;text-align:right;font-size:12px;color:var(--muted);max-width:50%}
.brief-note b{color:var(--ink);font-weight:600}
.row2{grid-template-columns:250px 1fr 1fr}
.row3{grid-template-columns:1.55fr 1fr;margin-top:14px}
.row4{grid-template-columns:1fr 1fr;margin-top:14px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);border-bottom:1px solid var(--line);padding:7px 6px}
td{padding:7px 6px;border-bottom:1px solid #f1f1ee;vertical-align:top}
tr:last-child td{border-bottom:0}
.pill{display:inline-block;padding:1px 8px;border-radius:20px;font-size:10.5px;font-weight:700;letter-spacing:.02em}
.pill.fault{background:#ffe6e0;color:#b82400}
.pill.planned{background:#f6edd9;color:#7a5c1f}
.pill.micro{background:#fff0d2;color:#8a5b00}
.pill.idle{background:#efefec;color:#555}
.pill.unknown{background:#e9e9f5;color:#4b4b8a}
.pill.operator{background:#e3f2e8;color:#1b7f3b}
.muted{color:var(--muted);font-size:12px}
.alert{border-left:3px solid var(--accent);padding:7px 10px;background:#fff;font-size:12px;margin-bottom:6px;display:flex;gap:8px;align-items:flex-start}
.alert.ack{border-left-color:#c9c9c4;opacity:.65}
.alert form{margin-left:auto}
.mini{border:0;background:#f0f0ec;color:#333;font-size:10.5px;padding:3px 8px;border-radius:5px;cursor:pointer}
.mini:hover{background:#e2e2dd}
.pager{display:flex;align-items:center;gap:10px;justify-content:flex-end;padding:10px 0 2px}
.btn{display:inline-block;border:0;background:var(--accent);color:#fff;font-size:12.5px;font-weight:700;padding:9px 14px;border-radius:7px;cursor:pointer;text-decoration:none}
.btn.ghost{background:#fff;color:var(--ink);border:1px solid var(--line);font-weight:600}
.btn.ghost:hover{border-color:#bbb}
.btn.dark{background:var(--ink)}
.meter{display:flex;align-items:center;gap:10px;margin:7px 0;font-size:12px;color:var(--muted)}
.meter span{width:96px}
.meter b{width:48px;text-align:right;color:var(--ink)}
.track{flex:1;height:8px;background:#eeeeeb;border-radius:4px;overflow:hidden}
.big{font-size:32px;font-weight:700;color:var(--ink);line-height:1;margin:4px 0}
.field{display:flex;flex-direction:column;gap:4px;margin-bottom:10px}
.field label{font-size:10.5px;font-weight:600;color:var(--muted);letter-spacing:.05em;text-transform:uppercase}
.field input,.settings input,.settings select{padding:8px 10px;border:1px solid var(--line);border-radius:7px;font-size:13px;background:var(--panel);color:var(--ink);transition:border-color .15s ease}
.field input:focus,.settings input:focus{border-color:var(--accent);outline:none}
.settings{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.result{padding:10px 18px;font-size:13px;cursor:pointer;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--line);transition:background .1s ease}
.result:hover,.result.active{background:var(--accent);color:#fff}
/* ---- professional polish ---- */
.toast{position:fixed;bottom:24px;right:24px;background:#161616;color:#fff;padding:12px 18px;border-radius:10px;font-size:13px;box-shadow:0 8px 24px rgba(0,0,0,.25);opacity:0;transform:translateY(12px);transition:opacity .25s ease,transform .25s ease;pointer-events:none;z-index:1000;max-width:360px}
.toast.show{opacity:1;transform:translateY(0)}
.toast.ok{background:#1b7f3b}
.toast.warn{background:#b82400}
.empty{padding:32px 16px;text-align:center;color:var(--muted);font-size:13px}
.empty b{display:block;font-size:15px;color:var(--ink);margin-bottom:6px}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
button:focus-visible,a:focus-visible{outline-offset:3px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{text-align:left;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);border-bottom:2px solid var(--line);padding:9px 6px;position:sticky;top:0;background:var(--bg)}
td{padding:9px 6px;border-bottom:1px solid #f1f1ee;vertical-align:top}
tr:hover td{background:#fafaf7}
tr:last-child td{border-bottom:0}
@media (max-width:900px){.side{width:64px;flex:0 0 64px;padding:14px 6px}.brand,.site,.nav span,.health-block,.side-foot{display:none}.nav{justify-content:center;padding:10px 0}.machines{grid-template-columns:1fr}.row2,.row3,.row4{grid-template-columns:1fr}.main{padding:0 14px 30px}.topbar{padding:16px 14px 10px;flex-direction:column;align-items:flex-start;gap:10px}}
@media (max-width:600px){h1{font-size:18px}.moee{font-size:20px}table{font-size:11.5px}th,td{padding:6px 4px}}
@keyframes pulse{0%,100%{box-shadow:0 0 0 0 rgba(255,51,0,.4)}50%{box-shadow:0 0 0 8px rgba(255,51,0,0)}}
.andon .adot{animation:pulse 1.6s ease-in-out infinite}
.skeleton{background:linear-gradient(90deg,#eee 25%,#f5f5f5 50%,#eee 75%);background-size:200% 100%;animation:shimmer 1.4s infinite;border-radius:6px;height:14px}
@keyframes shimmer{0%{background-position:200% 0}100%{background-position:-200% 0}}
.filters{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px}
.filters a{font-size:11.5px;padding:5px 10px;border-radius:20px;background:#fff;border:1px solid var(--line);color:#555;text-decoration:none}
.filters a.on{background:var(--ink);border-color:var(--ink);color:#fff}
.stat{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:14px}
.stat .card{padding:14px 16px}
.stat .n{font-size:26px;font-weight:700;color:var(--ink);line-height:1.1}
.stat .l{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.07em}
label.f{display:block;font-size:12px;color:var(--ink);font-weight:600;margin:0 0 4px}
label.f small{display:block;font-weight:400;color:var(--muted);font-size:11px;margin-top:2px}
input[type=text],input[type=number],select{width:100%;padding:8px 10px;border:1px solid var(--line);border-radius:7px;font:13px Arial;background:#fff;color:var(--ink)}
input:focus,select:focus{outline:2px solid #ffd9cf;border-color:var(--accent)}
.form-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px 18px}
.form-actions{display:flex;gap:10px;align-items:center;margin-top:18px}
.flash{padding:9px 12px;border-radius:7px;font-size:12.5px;margin-bottom:12px}
.flash.ok{background:#e6f5ec;color:#146b32}
.flash.err{background:#ffeae4;color:#a32a08}
.evidence{background:#fbfbf9;border:1px solid var(--line);border-radius:8px;padding:12px}
.rule{font-family:Consolas,monospace;font-size:11.5px;color:#444;background:#f4f4f0;padding:8px 10px;border-radius:6px;white-space:pre-wrap}
.paper{background:#fff;border:1px solid var(--line);border-radius:10px;padding:34px 38px;max-width:860px}
.paper h2{margin:0 0 4px;font-size:19px;color:var(--ink)}
.paper .meta{color:var(--muted);font-size:11.5px;margin-bottom:20px}
.paper h4{margin:22px 0 8px;font-size:11px;letter-spacing:.09em;text-transform:uppercase;color:var(--accent)}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.reg{font-family:Consolas,monospace;font-size:11.5px}
.note{font-size:11.5px;color:var(--muted);border-top:1px dashed var(--line);margin-top:18px;padding-top:12px;line-height:1.6}
.demo{display:flex;gap:8px;flex-wrap:wrap}
.demo form{margin:0}
footer{padding:0 30px 30px;color:#9a9a96;font-size:10.5px;max-width:1290px}
@media (max-width:1100px){.machines{grid-template-columns:1fr}.row2,.row3,.row4,.two,.form-grid{grid-template-columns:1fr}.stat{grid-template-columns:1fr 1fr}.side{display:none}}
/* ---- dark mode ---- */
body.dark{--ink:#e8e8e4;--body:#c8c8c2;--muted:#8b8b86;--line:#2a2a2a;--panel:#1e1e1e;--bg:#121212;--side:#0a0a0a}
body.dark .card{background:#1e1e1e;border-color:#2a2a2a;box-shadow:0 1px 2px rgba(0,0,0,.3),0 4px 14px rgba(0,0,0,.2)}
body.dark .card:hover{box-shadow:0 2px 6px rgba(0,0,0,.4),0 8px 24px rgba(0,0,0,.3)}
body.dark th{background:#121212;border-color:#2a2a2a}
body.dark td{border-color:#222}
body.dark tr:hover td{background:#1a1a1a}
body.dark .mini{background:#2a2a2a;color:#c8c8c2}
body.dark .mini:hover{background:#333}
body.dark .windows{background:#1a1a1a}
body.dark .chip.on{background:#2a2a2a;color:#e8e8e4}
body.dark .track{background:#2a2a2a}
body.dark .topbar{background:#121212}
body.dark .andon{background:#1e1e1e;border-color:#3a2a22}
body.dark .alert{background:#1e1e1e}
body.dark table{color:#c8c8c2}
body.dark .pill.fault{background:#3a1a14;color:#ff8a70}
body.dark .pill.planned{background:#2a2214;color:#d4a85a}
body.dark .pill.micro{background:#2a2210;color:#e0a840}
body.dark .pill.idle{background:#222;color:#999}
body.dark .pill.unknown{background:#1e1e2a;color:#8a8ab0}
body.dark .muted{color:#8b8b86}
body.dark .help-card{background:#1e1e1e;color:#c8c8c2}
body.dark .toast{background:#2a2a2a}
.theme-toggle{position:fixed;bottom:18px;right:18px;width:42px;height:42px;border-radius:50%;border:1px solid var(--line);background:var(--panel);color:var(--ink);font-size:18px;cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.12);z-index:999;display:flex;align-items:center;justify-content:center;transition:transform .2s ease,background .2s ease}
.theme-toggle:hover{transform:rotate(20deg)}
.command-palette{position:fixed;inset:0;background:rgba(0,0,0,.5);display:flex;align-items:flex-start;justify-content:center;padding-top:15vh;z-index:3000;backdrop-filter:blur(4px)}
.command-palette[hidden]{display:none}
.command-palette input{width:500px;max-width:90vw;padding:14px 18px;font-size:16px;border:0;border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.3);outline:none}
.command-palette .results{width:500px;max-width:90vw;margin-top:8px;background:var(--panel);border-radius:12px;box-shadow:0 20px 60px rgba(0,0,0,.3);overflow:hidden;max-height:320px;overflow-y:auto}
.command-palette .result{padding:10px 18px;font-size:13px;cursor:pointer;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--line)}
.command-palette .result:hover,.command-palette .result.active{background:var(--accent);color:#fff}
.command-palette .result small{margin-left:auto;opacity:.6;font-size:10px}"""

JS = """
const PILL = c => `<span class="pill ${c}">${c}</span>`;
const STATE = {running:'#1b7f3b',fault:'#ff3300',planned:'#b07a1a',stopped:'#6b6b6b'};
const WORD = {running:'Running',fault:'Fault',planned:'Planned',stopped:'Stopped'};
async function refresh(){
  try{
    const r = await fetch('/api/state');
    if(!r.ok) return;
    const s = await r.json();
    document.querySelector('#clock').textContent = s.generated_at;
    const fresh = Math.max(...s.machines.map(m => m.age_s === null ? 999 : m.age_s), 0);
    const live = fresh <= 20;
    const dot = document.querySelector('#livedot');
    if (dot) dot.className = live ? 'dot' : 'dot stale';
    const lw = document.querySelector('#liveword');
    if (lw) lw.textContent = live ? 'live' : `no signal ${fresh.toFixed(0)}s`;
    for (const m of s.machines){
      const el = document.querySelector(`[data-machine="${m.machine}"]`);
      if(!el) continue;
      el.style.setProperty('--state', STATE[m.state] || '#6b6b6b');
      el.querySelector('[data-f="state"]').textContent = WORD[m.state] || m.state;
      el.querySelector('[data-f="parts"]').textContent = m.parts;
      el.querySelector('[data-f="good"]').textContent = m.good;
      el.querySelector('[data-f="cycle"]').textContent = m.last_cycle_ms ? (m.last_cycle_ms/1000).toFixed(1)+'s' : '—';
      el.querySelector('[data-f="oee"]').textContent = m.oee.toFixed(1);
      el.querySelector('[data-f="age"]').textContent = m.age_s === null ? '—' : m.age_s.toFixed(0)+'s';
      if (m.alarm_text) el.querySelector('[data-f="alarm"]').textContent = m.alarm_text;
    }
    const set = (id, v) => { const n = document.querySelector(id); if (n) n.innerHTML = v; };
    set('#oeeChart', s.charts.oee); set('#paretoChart', s.charts.pareto);
    set('#lossChart', s.charts.loss); set('#trendChart', s.charts.trend);
    set('#headline', `${s.headline.label} <i>${s.headline.minutes.toFixed(0)} min</i>`);
    set('#headnote', `<b>${s.headline.events} × ${s.headline.label}</b> classified from coil and cycle signals<br>`+
      `<b>${s.headline.coverage.toFixed(0)}%</b> of stop time has a signal-derived reason · the rest stays unknown`);
    const rows = document.querySelector('#events');
    if (rows) {
      const act = s.active.map(a =>
        `<tr class="openrow"><td>${a.since}</td><td>${a.machine}</td><td>${PILL(a.category)}</td>`+
        `<td>${(a.seconds/60).toFixed(1)} min</td><td>${a.cause}</td><td>${(a.confidence*100).toFixed(0)}%</td></tr>`).join('');
      rows.innerHTML = act + s.events.map(e =>
        `<tr><td>${e.at}</td><td>${e.machine}</td><td>${PILL(e.category)}</td>`+
        `<td>${(e.seconds/60).toFixed(1)} min</td><td>${e.cause}</td><td>${(e.confidence*100).toFixed(0)}%</td></tr>`).join('');
    }
    set('#andon', s.active.map(a =>
      `<div class="andon"><span class="adot"></span><div><b>${a.machine} · ${a.category}</b> `+
      `for ${a.seconds < 120 ? a.seconds.toFixed(0) + ' s' : (a.seconds/60).toFixed(1) + ' min'} since ${a.since} — ${a.cause}</div>`+
      `<span class="atag">in progress</span></div>`).join(''));
  }catch(err){}
}
setInterval(refresh, 2000);
refresh();
// ---- professional UX helpers ----
window.toast = function(msg, kind) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className = 'toast show ' + (kind || '');
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
};
const qs = new URLSearchParams(location.search);
if (qs.has('saved')) window.toast('Settings saved', 'ok');
if (qs.has('error')) window.toast('Check the highlighted fields', 'warn');

// ---- dark mode toggle ----
(function() {
  const saved = localStorage.getItem('ls-theme');
  if (saved === 'dark') document.body.classList.add('dark');
  const btn = document.getElementById('themeToggle');
  if (btn) {
    btn.textContent = document.body.classList.contains('dark') ? '☀️' : '🌙';
    btn.addEventListener('click', () => {
      document.body.classList.toggle('dark');
      const isDark = document.body.classList.contains('dark');
      localStorage.setItem('ls-theme', isDark ? 'dark' : 'light');
      btn.textContent = isDark ? '☀️' : '🌙';
    });
  }
})();

// ---- command palette (Ctrl+K / Cmd+K) ----
const NAV_ITEMS = [
  {name:'Live floor', url:'/'}, {name:'Alerts', url:'/alerts'}, {name:'Downtime', url:'/downtime'},
  {name:'OEE & losses', url:'/oee'}, {name:'Machines', url:'/machines'}, {name:'Trends', url:'/trends'},
  {name:'Shift history', url:'/shifts'}, {name:'Shift report', url:'/report'},
  {name:'Settings', url:'/settings'}, {name:'How it works', url:'/how'}
];
(function() {
  const palette = document.getElementById('cmdPalette');
  const input = document.getElementById('cmdInput');
  const results = document.getElementById('cmdResults');
  if (!palette || !input) return;
  let active = 0;
  function render(q) {
    const filtered = NAV_ITEMS.filter(n => n.name.toLowerCase().includes(q.toLowerCase()));
    results.innerHTML = filtered.map((n,i) => '<div class="result'+(i===active?' active':'')+'" data-url="'+n.url+'"><span>'+n.name+'</span><small>'+n.url+'</small></div>').join('');
    active = 0;
  }
  function open() { palette.hidden = false; input.value = ''; render(''); input.focus(); }
  function close() { palette.hidden = true; }
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); palette.hidden ? open() : close(); }
    if (e.key === 'Escape' && !palette.hidden) close();
  });
  input.addEventListener('input', () => render(input.value));
  results.addEventListener('click', (e) => { const r = e.target.closest('.result'); if (r) location.href = r.dataset.url; });
  palette.addEventListener('click', (e) => { if (e.target === palette) close(); });
})();
"""


# ----------------------------------------------------------------------- pages
def page_live(conn, state, minutes: int) -> str:
    tiles = []
    for m in state["machines"]:
        colour = STATE_COLOURS.get(m["state"], "#6b6b6b")
        alert = f'<div class="kv"><span>Alarm</span><b data-f="alarm">{esc(m["alarm_text"] or "—")}</b></div>' if m["state"] == "fault" else ""
        tiles.append(f"""
    <article class="card machine" data-machine="{esc(m['machine'])}" style="--state:{colour}">
      <div class="mhead">
        <div><div class="mstate" data-f="state">{STATE_WORDS.get(m['state'], m['state'])}</div>
        <h2>{esc(m['name'])}</h2></div>
        <div class="moee"><span data-f="oee">{m['oee']:.1f}</span><small>OEE %</small></div>
      </div>
      <div class="kv"><span>Parts</span><b data-f="parts">{m['parts']}</b></div>
      <div class="kv"><span>Good</span><b data-f="good">{m['good']}</b></div>
      <div class="kv"><span>Last cycle</span><b><span data-f="cycle">{(m['last_cycle_ms'] or 0)/1000:.1f}s</span>
        <span class="muted">/ {m['ideal_cycle_ms']/1000:.1f}s</span></b></div>
      <div class="kv"><span>Signal age</span><b data-f="age">{m['age_s']:.0f}s</b></div>
      {alert}
    </article>""")

    active_rows = "".join(
        f'<tr class="openrow"><td>{a["since"]}</td><td>{esc(a["machine"])}</td>'
        f'<td><span class="pill {a["category"]}">{a["category"]}</span></td>'
        f'<td>{a["seconds"]/60:.1f} min</td><td>{esc(a["cause"])}</td>'
        f'<td>{a["confidence"]*100:.0f}%</td></tr>'
        for a in state.get("active", [])
    )
    rows = active_rows + "".join(
        f'<tr><td><a href="/downtime/event/{e["id"]}">{e["at"]}</a></td><td>{esc(e["machine"])}</td>'
        f'<td><span class="pill {e["category"]}">{e["category"]}</span></td>'
        f'<td>{e["seconds"]/60:.1f} min</td><td>{esc(e["cause"])}</td>'
        f'<td>{e["confidence"]*100:.0f}%</td></tr>'
        for e in state["events"]
    ) or '<tr><td colspan="6" class="muted">no stops in this window</td></tr>'

    banner = "".join(
        f'<div class="andon"><span class="adot"></span><div><b>{esc(a["machine"])} · {a["category"]}</b> '
        f'for {dur(a["seconds"])} since {a["since"]} — {esc(a["cause"])}</div>'
        f'<span class="atag">in progress</span></div>'
        for a in state.get("active", [])
    )

    alerts = "".join(
        f'<div class="alert {"ack" if a["ack"] else ""}"><div><b>{a["at"]} · {esc(a["machine"])}</b><br>{esc(a["message"])}</div>'
        + ("" if a["ack"] else f'<form method="post" action="/alerts/{a["id"]}/ack"><button class="mini" type="submit">Acknowledge</button></form>')
        + "</div>"
        for a in state["alerts"]
    ) or '<p class="muted">No alerts. A stop over the alert threshold raises one here.</p>'

    demo = ""
    if state.get("demo_mode", True):
        buttons = "".join(
            f'<form method="post" action="/demo/inject"><input type="hidden" name="kind" value="{k}">'
            f'<button class="mini" type="submit">{label}</button></form>'
            for k, label in (("fault", "Inject fault"), ("planned", "Inject planned stop"), ("micro", "Inject micro-stop"))
        )
        demo = f"""
  <section class="card" style="margin-top:14px">
    <h3>Demo control (simulator)</h3>
    <p class="muted" style="margin:0 0 10px">Writes to the PLC, not to the database. The classifier still has to work out what happened.</p>
    <div class="demo">{buttons}</div>
  </section>"""

    head = state["headline"]
    body = f"""
  <div id="andon">{banner}</div>
  <section class="grid machines">{''.join(tiles)}</section>

  <section class="card row-brief">
    <div><div class="brief-k">Top unplanned loss · last {minutes // 60}h {minutes % 60:02d}m</div>
      <div class="brief-big" id="headline">{esc(head['label'])} <i>{head['minutes']:.0f} min</i></div></div>
    <div class="brief-note" id="headnote"><b>{head['events']} × {esc(head['label'])}</b> classified from coil and cycle signals<br>
      <b>{head['coverage']:.0f}%</b> of stop time has a signal-derived reason · the rest stays unknown</div>
  </section>

  <section class="grid row2">
    <div class="card"><h3>Line OEE · target {state['target']:.0f}%</h3><div id="oeeChart">{state['charts']['oee']}</div></div>
    <div class="card"><h3>Downtime by cause</h3><div id="paretoChart">{state['charts']['pareto']}</div></div>
    <div class="card"><h3>Loss tree</h3><div id="lossChart">{state['charts']['loss']}</div></div>
  </section>

  <section class="card" style="margin-top:14px"><h3>Output per minute</h3><div id="trendChart">{state['charts']['trend']}</div></section>

  <section class="grid row3">
    <div class="card"><h3>Downtime log — inferred from signals</h3>
      <table><thead><tr><th>Start</th><th>Machine</th><th>Category</th><th>For</th><th>Cause</th><th>Conf.</th></tr></thead>
      <tbody id="events">{rows}</tbody></table>
    </div>
    <div class="card"><h3>Alerts</h3><div id="alerts">{alerts}</div></div>
  </section>{demo}"""

    words = [f"{m['machine']} {STATE_WORDS.get(m['state'], m['state']).lower()}" for m in state["machines"]]
    subtitle = f"{esc(state['line_name'])} · " + " · ".join(esc(w) for w in words) + f" · last {minutes // 60}h {minutes % 60:02d}m"
    return shell("/", state, "Live floor", subtitle, body, minutes)


def page_downtime(conn, state, minutes: int, machine: str, category: str, page: int = 1) -> str:
    start, end = window(minutes)
    events = analytics.events_window(conn, start, end)
    if machine != "all":
        events = [e for e in events if e["machine"] == machine]
    if category != "all":
        events = [e for e in events if e["category"] == category]

    total_stop = sum(e["seconds"] for e in events)
    explained = sum(e["seconds"] for e in events if e["category"] in analytics.EXPLAINED)
    confirmed = sum(1 for e in events if e["confirmed_by"])
    needs = sum(1 for e in events if e["category"] in ("unknown", "idle"))

    per_page = 40
    pages = max(1, (len(events) + per_page - 1) // per_page)
    page = min(max(page, 1), pages)
    shown = events[(page - 1) * per_page: page * per_page]

    filters_m = "".join(f'<a class="{"on" if machine == k else ""}" href="/downtime?minutes={minutes}&machine={k}&category={category}">{v}</a>'
                        for k, v in [("all", "All machines")] + [(m["machine"], m["machine"]) for m in state["machines"]])
    filters_c = "".join(f'<a class="{"on" if category == k else ""}" href="/downtime?minutes={minutes}&machine={machine}&category={k}">{v}</a>'
                        for k, v in [("all", "All causes"), ("fault", "Breakdown"), ("micro", "Micro-stop"),
                                     ("planned", "Planned"), ("idle", "Idle"), ("unknown", "Unknown")])

    rows = "".join(
        f'<tr><td><a href="/downtime/event/{e["id"]}">{stamp(e["start_ts"])}</a></td>'
        f'<td>{esc(e["machine"])}</td><td><span class="pill {e["category"]}">{e["category"]}</span></td>'
        f'<td>{e["seconds"]/60:.1f}</td><td>{esc(e["cause"])}</td><td>{e["confidence"]*100:.0f}%</td>'
        f'<td>{"operator" if e["confirmed_by"] else "signal"}</td>'
        f'<td><a class="mini" href="/downtime/event/{e["id"]}">Open</a></td></tr>'
        for e in shown
    ) or '<tr><td colspan="8" class="muted">no stops match this filter</td></tr>'

    pager = ""
    if pages > 1:
        base = f"/downtime?minutes={minutes}&machine={machine}&category={category}"
        pager = (
            f'<div class="pager"><span class="muted">{(page-1)*per_page+1}–{min(page*per_page, len(events))} '
            f'of {len(events)}</span>'
            + (f'<a class="mini" href="{base}&page={page-1}">&larr; Newer</a>' if page > 1 else "")
            + (f'<a class="mini" href="{base}&page={page+1}">Older &rarr;</a>' if page < pages else "")
            + "</div>"
        )

    body = f"""
  <section class="stat">
    <div class="card"><div class="n">{len(events)}</div><div class="l">Stops in window</div></div>
    <div class="card"><div class="n">{total_stop/60:.0f}<small style="font-size:13px;color:#71716d"> min</small></div><div class="l">Stop time</div></div>
    <div class="card"><div class="n">{(explained/total_stop*100 if total_stop else 0):.0f}%</div><div class="l">Has a signal reason</div></div>
    <div class="card"><div class="n">{needs}</div><div class="l">Waiting on an operator</div></div>
  </section>

  <div class="filters">{filters_m}</div>
  <div class="filters">{filters_c}</div>

  <section class="card">
    <h3>Every stop, with the reason and how sure the machine is</h3>
    <table><thead><tr><th>Start</th><th>Machine</th><th>Category</th><th>Min</th><th>Cause</th><th>Conf.</th><th>Source</th><th></th></tr></thead>
    <tbody>{rows}</tbody></table>
    {pager}
    <p class="note">A stop is never classified from a dropdown. The category comes from the coil pattern and the
    cycle pulse; the alarm register only names the cause once the machine has already flagged a fault.
    {confirmed} of these were confirmed or corrected by a person and keep that attribution.</p>
  </section>"""
    return shell("/downtime", state, "Downtime", "What stopped, for how long, and why — inferred from the signals", body, minutes)


def page_event(conn, state, event_id: int, minutes: int) -> str:
    event = conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()
    if event is None:
        return shell("/downtime", state, "Downtime", "Event not found", '<section class="card"><p>No such stop.</p></section>', minutes)

    start = float(event["start_ts"]) - 45
    end = float(event["end_ts"]) + 45
    rows = db.window(conn, start, end, event["machine"])
    trace = timeline(rows, start, end)

    span = float(event["seconds"])
    rule = {
        "fault": "fault coil is 1 while running is 0 → breakdown\ncause taken from the alarm register (4xxxx5)",
        "planned": "planned coil is 1 → changeover or planned maintenance\nno operator input required",
        "micro": f"running is 1 but the part counter did not move for {settings_factor(conn):.1f}x the ideal cycle",
        "idle": "running is 0, fault and planned are 0, stop shorter than the idle split",
        "unknown": "running is 0, no fault, no planned signal, no alarm — the signals do not explain it",
    }.get(event["category"], "")

    options = "".join(
        f'<option value="{k}" {"selected" if k == event["category"] else ""}>{v}</option>'
        for k, v in analytics.CATEGORY_LABELS.items()
    )
    confirmed = (
        f'<p class="flash ok">Confirmed by {esc(event["confirmed_by"])} at '
        f'{datetime.fromtimestamp(event["confirmed_at"]).strftime("%d %b %H:%M")}.</p>'
        if event["confirmed_by"] else ""
    )

    body = f"""
  <p><a class="mini" href="/downtime?minutes={minutes}">&larr; All downtime</a></p>
  <section class="grid two">
    <div class="card">
      <h3>What the machine says</h3>
      <table>
        <tr><td class="muted">Machine</td><td><b>{esc(event["machine"])}</b></td></tr>
        <tr><td class="muted">Started</td><td><b>{stamp(event["start_ts"])}</b></td></tr>
        <tr><td class="muted">Ended</td><td><b>{stamp(event["end_ts"])}</b></td></tr>
        <tr><td class="muted">Duration</td><td><b>{span/60:.1f} min</b></td></tr>
        <tr><td class="muted">Category</td><td><span class="pill {event["category"]}">{event["category"]}</span></td></tr>
        <tr><td class="muted">Cause</td><td><b>{esc(event["cause"])}</b></td></tr>
        <tr><td class="muted">Confidence</td><td><b>{event["confidence"]*100:.0f}%</b></td></tr>
        <tr><td class="muted">Source</td><td><b>{"operator" if event["confirmed_by"] else "signal"}</b></td></tr>
      </table>
      {confirmed}
    </div>
    <div class="card">
      <h3>The rule that fired</h3>
      <div class="rule">{esc(rule)}</div>
      <p class="note">Confidence is not a decoration. A contradiction between coils drops it to 20%; an alarm register
      behind a fault coil lifts it to 98%. Anything the signals cannot separate stays “unknown” at 35%.</p>
    </div>
  </section>

  <section class="card" style="margin-top:14px">
    <h3>Signals around the stop · 45 s either side</h3>
    <div class="evidence">{trace}</div>
    <p class="note">Generated from the stored samples for this machine. This is the whole evidence base:
    three coils, five holding registers, one row per second.</p>
  </section>

  <section class="card" style="margin-top:14px">
    <h3>Confirm or correct it</h3>
    <p class="muted" style="margin-top:0">The machine proposes. A person can confirm, and the correction is stored with
    a name and a timestamp instead of overwriting the signal record.</p>
    <form method="post" action="/events/{event["id"]}/confirm">
      <div class="form-grid">
        <div><label class="f">Category <select name="category">{options}</select></label></div>
        <div><label class="f">Cause <input type="text" name="cause" value="{esc(event["cause"])}"></label></div>
        <div><label class="f">Your name <input type="text" name="by" placeholder="e.g. R. Kumar"></label></div>
      </div>
      <div class="form-actions"><button class="btn" type="submit">Save confirmation</button>
        <a class="btn ghost" href="/downtime?minutes={minutes}">Cancel</a></div>
    </form>
  </section>"""
    return shell("/downtime", state, f"Stop at {hhmm(event['start_ts'])}", f"{esc(event['machine'])} · {event['category']} · {span/60:.1f} min", body, minutes)


def settings_factor(conn) -> float:
    return float(settings_mod.load(conn).get("micro_stop_factor", 2.0))


def page_oee(conn, state, minutes: int) -> str:
    cfg = settings_mod.load(conn)
    summary = {"machines": state["machines"], "line": state["line"]}
    losses = analytics.loss_tree(summary)
    total_loss = sum(v for _, v in losses) or 1
    pareto = analytics.pareto(summary)

    rows = "".join(
        f'<tr><td><b>{esc(m["machine"])}</b></td><td>{m["coverage"]:.0f}%</td>'
        f'<td>{m["availability"]}%</td><td>{m["performance"]}%</td><td>{m["quality"]}%</td>'
        f'<td><b>{m["oee"]}%</b></td><td>{m["parts"]}</td><td>{m["rejects"]}</td></tr>'
        for m in summary["machines"]
    )
    meters = "".join(
        f'<div style="margin-bottom:14px"><div class="kicker">{esc(m["machine"])}</div>'
        + meter("Availability", m["availability"]) + meter("Performance", m["performance"])
        + meter("Quality", m["quality"]) + "</div>"
        for m in summary["machines"]
    )
    loss_rows = "".join(
        f'<tr><td>{esc(k.title())}</td><td><b>{v/60:.1f} min</b></td>'
        f'<td>{v/total_loss*100:.0f}%</td></tr>'
        for k, v in losses
    )

    body = f"""
  <section class="grid row2" style="margin-bottom:14px">
    <div class="card"><h3>Line OEE · target {cfg.get("oee_target", 65):.0f}%</h3>
      {donut(summary["line"]["oee"], "line OEE", target=float(cfg.get("oee_target", 65)))}
      <p class="muted" style="margin:8px 0 0">Availability × Performance × Quality</p></div>
    <div class="card"><h3>Availability, performance, quality</h3>{meters}</div>
    <div class="card"><h3>Downtime by cause</h3>{hbars(pareto, " min")}</div>
  </section>

  <section class="grid two">
    <div class="card"><h3>Loss tree · every minute accounted for</h3>
      <table><thead><tr><th>Loss bucket</th><th>Time</th><th>Share</th></tr></thead><tbody>{loss_rows}</tbody></table>
      <p class="note">Startup rejects are not listed: they need a first-off signal this register map does not expose,
      so they are reported as not instrumented rather than guessed.</p></div>
    <div class="card"><h3>By machine</h3>
      <table><thead><tr><th>Machine</th><th>Data</th><th>A</th><th>P</th><th>Q</th><th>OEE</th><th>Parts</th><th>Rej.</th></tr></thead>
      <tbody>{rows}</tbody></table>
      <p class="note">Data is the share of the window with a stored sample. A machine that was switched off shows it
      instead of quietly scoring 0%.</p></div>
  </section>

  <section class="card" style="margin-top:14px"><h3>Definitions used (ISO 22400-2)</h3>
    <table>
      <tr><td style="width:220px"><b>Availability</b></td><td>Run time ÷ (planned time − planned stops)</td></tr>
      <tr><td><b>Performance</b></td><td>(Parts × ideal cycle) ÷ run time</td></tr>
      <tr><td><b>Quality</b></td><td>Good parts ÷ parts</td></tr>
      <tr><td><b>OEE</b></td><td>Availability × Performance × Quality</td></tr>
      <tr><td><b>Micro-stop</b></td><td>Running with no cycle pulse for {cfg.get("micro_stop_factor", 2):.1f}× the ideal cycle</td></tr>
      <tr><td><b>Idle vs unknown</b></td><td>Stops under {float(cfg.get("idle_split_s", 300))/60:.0f} min are idle; longer unexplained stops stay unknown</td></tr>
    </table>
  </section>"""
    return shell("/oee", state, "OEE & losses", "Where the shift went, in minutes you can act on", body, minutes)


_SHIFT_CACHE: tuple[float, tuple, list] | None = None


def _shift_rolls(conn, blocks: list[tuple[float, float]]) -> list[dict]:
    """Six shifts cost one pass, and the result is kept for a minute."""
    global _SHIFT_CACHE
    key = (len(blocks), int(max(e for _, e in blocks) // 60))
    now = time.time()
    if _SHIFT_CACHE and _SHIFT_CACHE[1] == key and now - _SHIFT_CACHE[0] < 120:
        return _SHIFT_CACHE[2]
    rolls = analytics.shift_table(conn, blocks)
    _SHIFT_CACHE = (now, key, rolls)
    return rolls


def page_shifts(conn, state, minutes: int, start: str | None) -> str:
    cfg = settings_mod.load(conn)
    if start:
        start_ts = float(start)
        end_ts = start_ts + float(cfg.get("shift_hours", 8)) * 3600
        summary = analytics.summarize(conn, start_ts, end_ts, cfg)
        events = analytics.events_window(conn, start_ts, end_ts)[:20]
        rows = "".join(
            f'<tr><td>{esc(e["machine"])}</td><td><span class="pill {e["category"]}">{e["category"]}</span></td>'
            f'<td>{hhmm(e["start_ts"])}</td><td>{e["seconds"]/60:.1f}</td><td>{esc(e["cause"])}</td></tr>'
            for e in events
        )
        body = f"""
  <p><a class="mini" href="/shifts">&larr; All shifts</a></p>
  <section class="stat">
    <div class="card"><div class="n">{summary["line"]["oee"]}%</div><div class="l">Line OEE</div></div>
    <div class="card"><div class="n">{summary["line"]["parts"]}</div><div class="l">Parts</div></div>
    <div class="card"><div class="n">{summary["line"]["availability"]}%</div><div class="l">Availability</div></div>
    <div class="card"><div class="n">{len(events)}</div><div class="l">Classified stops</div></div>
  </section>
  <section class="grid two">
    <div class="card"><h3>{stamp(start_ts)} → {hhmm(end_ts)}</h3>{hbars(analytics.pareto(summary), " min")}</div>
    <div class="card"><h3>Stops in this shift</h3>
      <table><thead><tr><th>Machine</th><th>Category</th><th>At</th><th>Min</th><th>Cause</th></tr></thead><tbody>{rows}</tbody></table></div>
  </section>"""
        return shell("/shifts", state, "Shift detail", f"{stamp(start_ts)} · {esc(state['site'])}", body, minutes)

    blocks = analytics.shift_windows(conn, float(cfg.get("shift_hours", 8)), 6)
    rolls = _shift_rolls(conn, blocks)
    rows = ""
    for index, roll in enumerate(rolls):
        start_ts, end_ts = roll["start"], roll["end"]
        rows += (
            f'<tr><td><a href="/shifts?start={start_ts:.0f}&minutes={minutes}">'
            f'{"Current shift" if index == 0 else stamp(start_ts)}</a></td>'
            f'<td>{hhmm(start_ts)}–{hhmm(end_ts)}</td><td>{roll["line"]["parts"]}</td>'
            f'<td>{roll["line"]["availability"]}%</td><td>{roll["line"]["performance"]}%</td>'
            f'<td>{roll["line"]["quality"]}%</td><td><b>{roll["line"]["oee"]}%</b></td>'
            f'<td>{esc(roll["top"][0])} · {roll["top"][1]:.0f} min</td></tr>'
        )
    body = f"""
  <section class="card">
    <h3>Stored shifts</h3>
    <table><thead><tr><th>Shift</th><th>Window</th><th>Parts</th><th>A</th><th>P</th><th>Q</th><th>OEE</th><th>Top loss</th></tr></thead>
    <tbody>{rows}</tbody></table>
    <p class="note">Every second is kept in SQLite, so any window can be recomputed later. Each row is calculated
    from the stored samples when the page is opened, not typed in.</p>
  </section>
  <section class="card" style="margin-top:14px">
    <h3>Export</h3>
    <div class="form-actions" style="margin-top:0">
      <a class="btn ghost" href="/export/events.csv?minutes={minutes}">Downtime events (CSV)</a>
      <a class="btn ghost" href="/export/shift.csv?minutes={minutes}">Shift summary (CSV)</a>
      <a class="btn ghost" href="/report.pdf?minutes={minutes}">Shift report (PDF)</a>
    </div>
  </section>"""
    return shell("/shifts", state, "Shift history", "Every stored second, rolled up into the shifts you worked", body, minutes)


def page_report(conn, state, minutes: int) -> str:
    start, end = window(minutes)
    summary = {"machines": state["machines"], "line": state["line"]}
    events = analytics.events_window(conn, start, end)
    pareto = analytics.pareto(summary)

    rows = "".join(
        f'<tr><td>{esc(m["machine"])}</td><td>{m["availability"]}%</td><td>{m["performance"]}%</td>'
        f'<td>{m["quality"]}%</td><td><b>{m["oee"]}%</b></td><td>{m["parts"]}</td><td>{m["good"]}</td></tr>'
        for m in summary["machines"]
    )
    top = "".join(f'<tr><td>{esc(k)}</td><td>{v:.1f} min</td></tr>' for k, v in pareto)
    worst = sorted(events, key=lambda e: e["seconds"], reverse=True)[:8]
    worst_rows = "".join(
        f'<tr><td>{hhmm(e["start_ts"])}</td><td>{esc(e["machine"])}</td>'
        f'<td><span class="pill {e["category"]}">{e["category"]}</span></td>'
        f'<td>{e["seconds"]/60:.1f}</td><td>{esc(e["cause"])}</td></tr>'
        for e in worst
    )

    body = f"""
  <div class="form-actions" style="margin:0 0 14px">
    <a class="btn" href="/report.pdf?minutes={minutes}">Download PDF</a>
    <a class="btn ghost" href="/export/events.csv?minutes={minutes}">Download events CSV</a>
    <a class="btn ghost" href="/export/shift.csv?minutes={minutes}">Download shift CSV</a>
  </div>
  <div class="paper">
    <h2>Shift report · {esc(state['line_name'])}</h2>
    <div class="meta">{esc(state['site'])} · {stamp(start)} → {hhmm(end)} · generated {datetime.now().strftime('%d %b %Y %H:%M')}</div>
    <h4>Line OEE</h4>
    <p style="font-size:15px;margin:0 0 10px"><b>{summary['line']['oee']}%</b> ·
      A {summary['line']['availability']}% · P {summary['line']['performance']}% · Q {summary['line']['quality']}% ·
      {summary['line']['parts']} parts, {summary['line']['good']} good</p>
    <h4>By machine</h4>
    <table><thead><tr><th>Machine</th><th>A</th><th>P</th><th>Q</th><th>OEE</th><th>Parts</th><th>Good</th></tr></thead>
    <tbody>{rows}</tbody></table>
    <h4>Downtime by cause</h4>
    <table><tbody>{top}</tbody></table>
    <h4>Longest stops</h4>
    <table><thead><tr><th>Start</th><th>Machine</th><th>Category</th><th>Min</th><th>Cause</th></tr></thead>
    <tbody>{worst_rows}</tbody></table>
    <h4>Sign-off</h4>
    <p class="note" style="border:0;margin:0;padding:0">Prepared by LineSight. Every category above was inferred from the
    machine signals and carries a confidence; stops a person confirmed say so. Simulated shift for this build.</p>
  </div>"""
    return shell("/report", state, "Shift report", "One page the supervisor can print, mail or file", body, minutes)


def page_settings(conn, state, minutes: int, saved: bool = False, errors: list[str] | None = None) -> str:
    cfg = settings_mod.load(conn)
    errors = errors or []
    fields = []
    for field in settings_mod.FIELDS:
        key = field["key"]
        value = cfg.get(key, field["default"])
        if field["type"] == "number":
            control = f'<input type="number" step="any" name="{key}" value="{value}">'
        elif field["type"] == "select":
            control = (f'<select name="{key}">' + "".join(
                f'<option value="{o}" {"selected" if o == value else ""}>{o}</option>' for o in field["options"]
            ) + "</select>")
        else:
            control = f'<input type="text" name="{key}" value="{esc(value)}">'
        fields.append(
            f'<div><label class="f">{esc(field["label"])}'
            f'{" (" + field["unit"] + ")" if field.get("unit") else ""}'
            f'<small>{esc(field["help"])}</small></label>{control}</div>'
        )

    machine_rows = "".join(
        f"""<tr>
        <td><input form="m{m['id']}" type="text" name="name" value="{esc(m['name'])}" style="min-width:130px"></td>
        <td><input form="m{m['id']}" type="text" name="host" value="{esc(m['host'])}" style="width:110px"></td>
        <td><input form="m{m['id']}" type="number" name="port" value="{m['port']}" style="width:80px"></td>
        <td><input form="m{m['id']}" type="number" name="unit" value="{m['unit']}" style="width:64px"></td>
        <td><input form="m{m['id']}" type="number" name="ideal_cycle_ms" value="{m['ideal_cycle_ms']}" style="width:100px"></td>
        <td><select form="m{m['id']}" name="enabled"><option value="1" {"selected" if m['enabled'] else ""}>on</option>
          <option value="0" {"selected" if not m['enabled'] else ""}>off</option></select></td>
        <td><button class="mini" form="m{m['id']}" type="submit">Save</button></td>
      </tr>"""
        for m in db.machines_all(conn)
    )
    forms = "".join(
        f'<form id="m{m["id"]}" method="post" action="/machines/{esc(m["id"])}"></form>'
        for m in db.machines_all(conn)
    )

    flash = ""
    if saved:
        flash = '<div class="flash ok">Settings saved. The collector picks them up within ten seconds.</div>'
    if errors:
        flash = '<div class="flash err">' + "<br>".join(esc(e) for e in errors) + "</div>"

    body = f"""
  {flash}
  <section class="card">
    <h3>KPIs and thresholds</h3>
    <form method="post" action="/settings">
      <div class="form-grid">{''.join(fields)}</div>
      <div class="form-actions"><button class="btn" type="submit">Save settings</button>
        <span class="muted">Stored in SQLite on this PC. No restart needed.</span></div>
    </form>
  </section>

  <section class="card" style="margin-top:14px">
    <h3>Machines and register endpoints</h3>
    <table><thead><tr><th>Name</th><th>Host</th><th>Port</th><th>Unit</th><th>Ideal cycle (ms)</th><th>Polled</th><th></th></tr></thead>
    <tbody>{machine_rows}</tbody></table>
    {forms}
    <form method="post" action="/machines" style="margin-top:14px">
      <div class="form-grid">
        <div><label class="f">Machine id<small>Short code, e.g. CNC-03</small></label><input type="text" name="id" required></div>
        <div><label class="f">Name</label><input type="text" name="name" required></div>
        <div><label class="f">Host</label><input type="text" name="host" value="127.0.0.1" required></div>
        <div><label class="f">Port</label><input type="number" name="port" value="502" required></div>
        <div><label class="f">Unit id</label><input type="number" name="unit" value="1" required></div>
        <div><label class="f">Ideal cycle (ms)</label><input type="number" name="ideal_cycle_ms" value="45000" required></div>
      </div>
      <div class="form-actions"><button class="btn dark" type="submit">Add machine</button></div>
    </form>
    <p class="note">Same nine points for every machine: coils 1 running, 2 fault, 3 planned; registers 1 parts,
    2 good, 3 last cycle ms, 4 ideal cycle ms, 5 alarm code. A real PLC needs its IP and port here, nothing else.</p>
  </section>"""
    return shell("/settings", state, "Settings", "The only screen a plant engineer needs to touch", body, minutes)


def page_how(conn, state, minutes: int) -> str:
    cfg = settings_mod.load(conn)
    image = ""
    if (SHOTS / "architecture.png").exists():
        image = f'<img src="/static/architecture.png" alt="LineSight architecture" style="width:100%;border-radius:8px">'
    else:
        image = '<p class="muted">Architecture image not exported yet.</p>'
    body = f"""
  <section class="card">
    <h3>The whole system, on one PC</h3>
    {image}
    <p class="note">Browser → FastAPI → collector, classifier and OEE → SQLite. The only network traffic is Modbus TCP
    to the machines on the plant LAN. Nothing leaves the building.</p>
  </section>

  <section class="grid two" style="margin-top:14px">
    <div class="card"><h3>Register map · nine points per machine</h3>
      <table class="reg">
        <tr><td>00001</td><td>Running</td><td class="muted">coil</td></tr>
        <tr><td>00002</td><td>Fault</td><td class="muted">coil</td></tr>
        <tr><td>00003</td><td>Planned stop</td><td class="muted">coil</td></tr>
        <tr><td>40001</td><td>Parts counter</td><td class="muted">register</td></tr>
        <tr><td>40002</td><td>Good counter</td><td class="muted">register</td></tr>
        <tr><td>40003</td><td>Last cycle time</td><td class="muted">ms</td></tr>
        <tr><td>40004</td><td>Ideal cycle time</td><td class="muted">ms</td></tr>
        <tr><td>40005</td><td>Alarm code</td><td class="muted">register</td></tr>
      </table>
    </div>
    <div class="card"><h3>How a stop becomes a cause</h3>
      <div class="rule">planned coil = 1        → planned stop        97%
fault coil = 1          → breakdown          98%
running = 1, no pulse   → micro-stop         75%
running = 0, under {float(cfg.get("idle_split_s", 300))/60:.0f} min → idle              80%
running = 0, longer     → unknown            35%
running + fault         → contradiction      20%</div>
      <p class="note">Thresholds are editable in Settings. A cause is never taken from a dropdown; an operator can only
      confirm or correct what the machine already proposed.</p>
    </div>
  </section>

  <section class="card" style="margin-top:14px"><h3>What this build is, honestly</h3>
    <table>
      <tr><td style="width:240px"><b>Machines</b></td><td>A Modbus TCP simulator publishing the same nine points a PLC would, on three units</td></tr>
      <tr><td><b>Collector</b></td><td>Polls once a second over Modbus TCP and stores every sample</td></tr>
      <tr><td><b>Classifier</b></td><td>Infers category, cause and confidence from coils and the cycle pulse</td></tr>
      <tr><td><b>Not claimed</b></td><td>Startup rejects (needs a first-off signal), vibration or power analytics, multi-line rollup</td></tr>
    </table>
  </section>"""
    return shell("/how", state, "How it works", "The architecture, the register map, and the rules in plain text", body, minutes)


# -*- coding: utf-8 -*-
"""New capability sections: alerts, machines, trends."""

def page_alerts(conn, state, minutes: int) -> str:
    alerts = [dict(r) for r in conn.execute(
        "SELECT * FROM alerts ORDER BY ts DESC LIMIT 200").fetchall()]
    open_count = sum(1 for a in alerts if not a["ack"])
    by_machine = {}
    for a in alerts:
        by_machine.setdefault(a["machine"], []).append(a)

    rows = ""
    for a in alerts:
        rows += (
            f'<tr class="{"ack" if a["ack"] else "openrow"}">'
            f'<td>{stamp(a["ts"])}</td><td>{esc(a["machine"])}</td>'
            f'<td>{esc(a["kind"])}</td><td>{esc(a["message"])}</td>'
            f'<td>{"acknowledged" if a["ack"] else "open"}</td>'
            f'<td>' + ("" if a["ack"] else
                       f'<form method="post" action="/alerts/{a["id"]}/ack" style="margin:0">'
                       f'<button class="mini" type="submit">Acknowledge</button></form>') + '</td></tr>'
        )
    if not rows:
        rows = '<tr><td colspan="6" class="muted">No alerts recorded yet. A stop over the configured threshold raises one here.</td></tr>'

    body = f"""
  <section class="grid two">
    <div class="card">
      <h3>Open alerts</h3>
      <div class="big">{open_count}</div>
      <p class="muted">of {len(alerts)} recorded · alerts fire when a stop crosses the configured threshold</p>
    </div>
    <div class="card">
      <h3>By machine</h3>
      <table><thead><tr><th>Machine</th><th>Open</th><th>Total</th></tr></thead><tbody>
      {''.join(f'<tr><td>{esc(m)}</td><td>{sum(1 for a in v if not a["ack"])}</td><td>{len(v)}</td></tr>' for m, v in by_machine.items()) or '<tr><td colspan="3" class="muted">none</td></tr>'}
      </tbody></table>
    </div>
  </section>
  <section class="card" style="margin-top:14px">
    <h3>All alerts — newest first</h3>
    <table><thead><tr><th>At</th><th>Machine</th><th>Kind</th><th>Message</th><th>State</th><th></th></tr></thead>
    <tbody>{rows}</tbody></table>
  </section>"""
    return shell("/alerts", state, "Alerts", "Every threshold crossing, acknowledged or not", body, minutes)


def page_machines(conn, state, minutes: int) -> str:
    live = {m["machine"]: m for m in state["machines"]}
    rows = ""
    for m in db.machines_all(conn):
        st = live.get(m["id"], {})
        rows += (
            f'<tr><td><b>{esc(m["id"])}</b></td><td>{esc(m["name"])}</td>'
            f'<td>{esc(m["host"])}:{m["port"]}/u{m["unit"]}</td>'
            f'<td>{m["ideal_cycle_ms"]} ms</td>'
            f'<td>{"on" if m["enabled"] else "off"}</td>'
            f'<td>{esc(st.get("state", "—"))}</td>'
            f'<td>{st.get("oee", 0):.1f}%</td>'
            f'<td><a class="mini" href="/settings">configure</a></td></tr>'
        )
    if not rows:
        rows = '<tr><td colspan="8" class="muted">No machines registered.</td></tr>'

    body = f"""
  <section class="card">
    <h3>Machine registry</h3>
    <p class="muted" style="margin:0 0 10px">The collector reads these every 10 seconds. Edits take effect without a restart.</p>
    <table><thead><tr><th>Id</th><th>Name</th><th>Endpoint</th><th>Ideal cycle</th><th>Enabled</th><th>State</th><th>OEE</th><th></th></tr></thead>
    <tbody>{rows}</tbody></table>
  </section>
  <section class="card" style="margin-top:14px">
    <h3>Add a machine</h3>
    <form method="post" action="/machines" class="settings">
      <div class="field"><label>Id</label><input name="id" placeholder="CNC-03"></div>
      <div class="field"><label>Name</label><input name="name" placeholder="CNC Lathe 3"></div>
      <div class="field"><label>Host</label><input name="host" value="127.0.0.1"></div>
      <div class="field"><label>Port</label><input name="port" type="number" value="5023"></div>
      <div class="field"><label>Unit</label><input name="unit" type="number" value="1"></div>
      <div class="field"><label>Ideal cycle ms</label><input name="ideal_cycle_ms" type="number" value="45000"></div>
      <div class="field"><label></label><button type="submit">Add machine</button></div>
    </form>
  </section>"""
    return shell("/machines", state, "Machines", "Registry, live status and endpoint configuration", body, minutes)


def page_trends(conn, state, minutes: int) -> str:
    cfg = settings_mod.load(conn)
    blocks = analytics.shift_windows(conn, float(cfg.get("shift_hours", 8)), 6)
    rolls = analytics.shift_table(conn, blocks)
    # oldest first for the chart
    rolls = list(reversed(rolls))
    points = [r["line"]["oee"] for r in rolls]
    labels = [hhmm(r["start"]) for r in rolls]
    max_oee = max(points) if points else 1
    width, height = 860, 160
    bars = ""
    for i, (r, v) in enumerate(zip(rolls, points)):
        bw = (width - 40) / len(points)
        x = 20 + i * bw
        bh = (v / max(max_oee, 1)) * (height - 30)
        colour = "#1b7f3b" if v >= 65 else ("#e08a00" if v >= 55 else "#ff3300")
        bars += (f'<rect x="{x+4:.1f}" y="{height-20-bh:.1f}" width="{bw-8:.1f}" height="{bh:.1f}" '
                 f'fill="{colour}" rx="2"/>'
                 f'<text x="{x+bw/2:.1f}" y="{height-4}" font-size="9" text-anchor="middle" fill="#6b6b6b">{labels[i]}</text>'
                 f'<text x="{x+bw/2:.1f}" y="{height-26-bh:.1f}" font-size="9" text-anchor="middle" fill="#333" font-weight="bold">{v:.0f}</text>')
    chart = f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" role="img">{bars}</svg>'

    rows = ""
    for r in reversed(rolls):
        L = r["line"]
        top = r["top"]
        rows += (
            f'<tr><td>{stamp(r["start"])}</td><td>{hhmm(r["start"])}–{hhmm(r["end"])}</td>'
            f'<td>{L["parts"]}</td><td>{L["availability"]}%</td><td>{L["performance"]}%</td>'
            f'<td>{L["quality"]}%</td><td><b>{L["oee"]}%</b></td>'
            f'<td>{esc(top[0])} · {top[1]:.0f} min</td></tr>'
        )

    body = f"""
  <section class="card">
    <h3>OEE per shift — last {len(rolls)} shifts</h3>
    <p class="muted" style="margin:0 0 8px">Each bar is recomputed from the stored samples, not from a cached value.</p>
    {chart}
  </section>
  <section class="card" style="margin-top:14px">
    <h3>Shift detail</h3>
    <table><thead><tr><th>Shift</th><th>Window</th><th>Parts</th><th>A</th><th>P</th><th>Q</th><th>OEE</th><th>Top loss</th></tr></thead>
    <tbody>{rows}</tbody></table>
  </section>"""
    return shell("/trends", state, "Trends", "OEE and losses across the stored shifts", body, minutes)


# ---------------------------------------------------------------------- routes

@app.exception_handler(404)
async def not_found(request, exc):
    body = """
  <section class="card" style="text-align:center;padding:60px 20px">
    <div style="font-size:64px;font-weight:700;color:var(--accent);line-height:1">404</div>
    <h2 style="margin:12px 0 6px">Page not found</h2>
    <p class="muted">That route does not exist. Pick a section from the left, or go back to the live floor.</p>
    <a class="btn" href="/" style="margin-top:16px">Live floor</a>
  </section>"""
    # build a minimal shell-less response
    return HTMLResponse(f"<!doctype html><html><head><meta charset='utf-8'><title>404 — LineSight</title>"
                       f"<style>{CSS}</style></head><body style='background:var(--bg);padding:60px 20px'>"
                       f"<div style='max-width:600px;margin:0 auto'>{body}</div></body></html>", status_code=404)
_STATE_CACHE: dict[int, tuple[float, dict]] = {}
_STATE_TTL = 15.0

_HTML_CACHE: dict[str, tuple[float, str]] = {}
_HTML_TTL = 8.0


def _html_cached(key: str) -> str | None:
    hit = _HTML_CACHE.get(key)
    if hit and time.time() - hit[0] < _HTML_TTL:
        return hit[1]
    return None


def _html_store(key: str, value: str) -> str:
    _HTML_CACHE[key] = (time.time(), value)
    return value


def _forget() -> None:
    _STATE_CACHE.clear()
    _HTML_CACHE.clear()


def _state(conn, minutes: int) -> dict:
    now = time.time()
    hit = _STATE_CACHE.get(minutes)
    if hit and now - hit[0] < _STATE_TTL:
        return hit[1]
    state = snapshot(conn, minutes)
    state["demo_mode"] = settings_mod.load(conn).get("demo_mode", "on") == "on"
    _STATE_CACHE[minutes] = (now, state)
    return state


@app.get("/", response_class=HTMLResponse)
def index(minutes: int = Query(480, ge=5, le=1440)) -> HTMLResponse:
    key = f"index:{minutes}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_live(conn, state, minutes)
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/downtime", response_class=HTMLResponse)
def downtime(minutes: int = Query(480, ge=5, le=1440), machine: str = "all", category: str = "all",
             page: int = 1) -> HTMLResponse:
    key = f"downtime:{minutes}:{machine}:{category}:{page}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_downtime(conn, state, minutes, machine, category, page)
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/downtime/event/{event_id}", response_class=HTMLResponse)
def event_page(event_id: int, minutes: int = Query(480, ge=5, le=1440)) -> HTMLResponse:
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        return HTMLResponse(page_event(conn, state, event_id, minutes))
    finally:
        conn.close()


@app.get("/oee", response_class=HTMLResponse)
def oee(minutes: int = Query(480, ge=5, le=1440)) -> HTMLResponse:
    key = f"oee:{minutes}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_oee(conn, state, minutes)
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/shifts", response_class=HTMLResponse)
def shifts(minutes: int = Query(480, ge=5, le=1440), start: str | None = None) -> HTMLResponse:
    key = f"shifts:{minutes}:{start}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_shifts(conn, state, minutes, start)
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/report", response_class=HTMLResponse)
def report(minutes: int = Query(480, ge=5, le=1440)) -> HTMLResponse:
    key = f"report:{minutes}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_report(conn, state, minutes)
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/settings", response_class=HTMLResponse)
def settings_page(minutes: int = Query(480, ge=5, le=1440), saved: int = 0) -> HTMLResponse:
    key = f"settings:{minutes}:{saved}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_settings(conn, state, minutes, saved=bool(saved))
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/how", response_class=HTMLResponse)
def how(minutes: int = Query(480, ge=5, le=1440)) -> HTMLResponse:
    key = f"how:{minutes}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_how(conn, state, minutes)
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/alerts", response_class=HTMLResponse)
def alerts(minutes: int = Query(480, ge=5, le=1440)) -> HTMLResponse:
    key = f"alerts:{minutes}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_alerts(conn, state, minutes)
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/machines", response_class=HTMLResponse)
def machines(minutes: int = Query(480, ge=5, le=1440)) -> HTMLResponse:
    key = f"machines:{minutes}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_machines(conn, state, minutes)
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/trends", response_class=HTMLResponse)
def trends(minutes: int = Query(480, ge=5, le=1440)) -> HTMLResponse:
    key = f"trends:{minutes}"
    cached = _html_cached(key)
    if cached is not None:
        return HTMLResponse(cached)
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        html = page_trends(conn, state, minutes)
    finally:
        conn.close()
    return HTMLResponse(_html_store(key, html))


@app.get("/api/state")
def api_state(minutes: int = Query(480, ge=5, le=1440)) -> JSONResponse:
    started = time.perf_counter()
    conn = db.ready()
    try:
        payload = _state(conn, minutes)
        payload["server_ms"] = round((time.perf_counter() - started) * 1000)
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})
    finally:
        conn.close()


@app.get("/static/architecture.png")
def architecture() -> Response:
    path = SHOTS / "architecture.png"
    if not path.exists():
        return Response(status_code=404)
    return FileResponse(path, media_type="image/png")


@app.post("/settings")
async def settings_save(request: Request) -> RedirectResponse:
    data = await form(request)
    conn = db.ready()
    try:
        _, errors = settings_mod.save(conn, data)
        if errors:
            state = _state(conn, 480)
            return HTMLResponse(page_settings(conn, state, 480, errors=errors), status_code=400)
    finally:
        conn.close()
    _forget()
    return back("/settings?saved=1")


@app.post("/machines/{machine_id}")
async def machine_save(machine_id: str, request: Request) -> RedirectResponse:
    data = await form(request)
    conn = db.ready()
    try:
        db.save_machine(conn, {
            "id": machine_id,
            "name": data.get("name", machine_id),
            "host": data.get("host", "127.0.0.1"),
            "port": int(data.get("port", 502) or 502),
            "unit": int(data.get("unit", 1) or 1),
            "ideal_cycle_ms": int(data.get("ideal_cycle_ms", 45000) or 45000),
            "enabled": 1 if data.get("enabled", "1") == "1" else 0,
        })
        conn.commit()
    finally:
        conn.close()
    _forget()
    return back("/settings")


@app.post("/machines")
async def machine_new(request: Request) -> RedirectResponse:
    data = await form(request)
    if data.get("id") and data.get("name"):
        conn = db.ready()
        try:
            db.save_machine(conn, {
                "id": data["id"].strip(),
                "name": data["name"].strip(),
                "host": data.get("host", "127.0.0.1").strip(),
                "port": int(data.get("port", 502) or 502),
                "unit": int(data.get("unit", 1) or 1),
                "ideal_cycle_ms": int(data.get("ideal_cycle_ms", 45000) or 45000),
                "enabled": 1,
            })
            conn.commit()
        finally:
            conn.close()
    _forget()
    return back("/settings")


@app.post("/alerts/{alert_id}/ack")
def alert_ack(alert_id: int) -> RedirectResponse:
    conn = db.ready()
    try:
        conn.execute("UPDATE alerts SET ack = 1, ack_at = ? WHERE id = ?", (time.time(), alert_id))
        conn.commit()
    finally:
        conn.close()
    _forget()
    return back("/alerts")


@app.post("/events/{event_id}/confirm")
async def event_confirm(event_id: int, request: Request) -> RedirectResponse:
    data = await form(request)
    conn = db.ready()
    try:
        conn.execute(
            "UPDATE events SET category = ?, cause = ?, confidence = 1.0, source = 'operator', "
            "confirmed_by = ?, confirmed_at = ? WHERE id = ?",
            (data.get("category", "unknown"), data.get("cause", "")[:120],
             data.get("by", "operator")[:40] or "operator", time.time(), event_id),
        )
        conn.commit()
    finally:
        conn.close()
    _forget()
    return back("/downtime")


@app.post("/demo/inject")
async def demo_inject(request: Request) -> RedirectResponse:
    data = await form(request)
    kind = data.get("kind", "fault")
    if kind not in ("fault", "planned", "micro", "idle"):
        kind = "fault"
    conn = db.ready()
    try:
        machine = data.get("machine") or (db.machines_enabled(conn)[0]["id"] if db.machines_enabled(conn) else "CNC-01")
        seconds = {"fault": 180, "planned": 300, "micro": 75, "idle": 150}[kind]
        db.queue_command(conn, machine, kind, seconds, time.time())
        conn.commit()
    finally:
        conn.close()
    _forget()
    return back("/")


@app.get("/export/events.csv")
def export_events(minutes: int = Query(480, ge=5, le=1440)) -> Response:
    conn = db.ready()
    try:
        start, end = window(minutes)
        events = analytics.events_window(conn, start, end)
    finally:
        conn.close()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["start", "end", "machine", "category", "seconds", "minutes", "cause", "confidence", "source", "confirmed_by"])
    for e in events:
        writer.writerow([
            datetime.fromtimestamp(e["start_ts"]).isoformat(timespec="seconds"),
            datetime.fromtimestamp(e["end_ts"]).isoformat(timespec="seconds"),
            e["machine"], e["category"], e["seconds"], round(e["seconds"] / 60, 1),
            e["cause"], e["confidence"], "operator" if e["confirmed_by"] else "signal", e["confirmed_by"] or "",
        ])
    return Response(buffer.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="linesight-events.csv"'})


@app.get("/export/shift.csv")
def export_shift(minutes: int = Query(480, ge=5, le=1440)) -> Response:
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        summary = {"machines": state["machines"], "line": state["line"]}
    finally:
        conn.close()
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["machine", "availability", "performance", "quality", "oee", "parts", "good", "rejects"])
    for m in summary["machines"]:
        writer.writerow([m["machine"], m["availability"], m["performance"], m["quality"],
                         m["oee"], m["parts"], m["good"], m["rejects"]])
    writer.writerow([])
    writer.writerow(["line", summary["line"]["availability"], summary["line"]["performance"],
                     summary["line"]["quality"], summary["line"]["oee"], summary["line"]["parts"],
                     summary["line"]["good"], ""])
    return Response(buffer.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="linesight-shift.csv"'})


@app.get("/report.pdf")
def report_pdf(minutes: int = Query(480, ge=5, le=1440)) -> Response:
    conn = db.ready()
    try:
        state = _state(conn, minutes)
        start, end = window(minutes)
        summary = {"machines": state["machines"], "line": state["line"]}
        events = analytics.events_window(conn, start, end)
    finally:
        conn.close()
    return Response(content=build_pdf(state, summary, events, start, end),
                    media_type="application/pdf",
                    headers={"Content-Disposition": 'inline; filename="linesight-shift.pdf"'})


def build_pdf(state: dict, summary: dict, events: list[dict], start: float, end: float) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm, title="LineSight shift report")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontSize=19, spaceAfter=2)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4)
    small = ParagraphStyle("small", parent=styles["Normal"], fontSize=8.5, textColor=colors.HexColor("#666666"))

    story = [
        Paragraph("LineSight shift report", h1),
        Paragraph(f"{state['line_name']} · {state['site']} · "
                  f"{datetime.fromtimestamp(start).strftime('%d %b %H:%M')} – "
                  f"{datetime.fromtimestamp(end).strftime('%H:%M')} · generated "
                  f"{datetime.now().strftime('%d %b %Y %H:%M')}", small),
        Spacer(1, 5 * mm),
    ]

    line = summary["line"]
    story.append(Paragraph(
        f"Line OEE <b>{line['oee']}%</b> · A {line['availability']}% · P {line['performance']}% · "
        f"Q {line['quality']}% · {line['parts']} parts, {line['good']} good", styles["Normal"]))
    story.append(Spacer(1, 3 * mm))

    data = [["Machine", "Availability", "Performance", "Quality", "OEE", "Parts", "Good"]]
    for m in summary["machines"]:
        data.append([m["machine"], f"{m['availability']}%", f"{m['performance']}%", f"{m['quality']}%",
                     f"{m['oee']}%", m["parts"], m["good"]])
    table = Table(data, colWidths=[32 * mm, 27 * mm, 27 * mm, 22 * mm, 20 * mm, 20 * mm, 20 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f1f1f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f6f6f4")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story += [table, Paragraph("Downtime by cause", h2)]

    pareto = analytics.pareto(summary)
    rows = [["Cause", "Minutes"]]
    for label, minutes in pareto:
        rows.append([label, f"{minutes:.1f}"])
    pt = Table(rows, colWidths=[70 * mm, 30 * mm])
    pt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e0e0e0")),
    ]))
    story += [pt, Paragraph("Downtime, classified from signals", h2)]

    rows = [["Start", "Machine", "Category", "Min", "Cause", "Conf.", "Source"]]
    for e in sorted(events, key=lambda x: x["seconds"], reverse=True)[:16]:
        rows.append([datetime.fromtimestamp(e["start_ts"]).strftime("%H:%M"), e["machine"], e["category"],
                     f"{e['seconds']/60:.1f}", Paragraph(esc(e["cause"]), styles["Normal"]),
                     f"{e['confidence']*100:.0f}%", "operator" if e["confirmed_by"] else "signal"])
    dt = Table(rows, colWidths=[14 * mm, 20 * mm, 17 * mm, 12 * mm, 74 * mm, 12 * mm, 15 * mm], repeatRows=1)
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e0e0e0")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story += [dt, Spacer(1, 6 * mm),
              Paragraph("Every category above was inferred from the machine signals and carries a confidence. "
                        "Stops confirmed by a person say so. Simulated shift for this build; no plant data.", small)]

    doc.build(story)
    return buffer.getvalue()


def main() -> None:
    import uvicorn

    parser = argparse.ArgumentParser(description="LineSight dashboard")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
