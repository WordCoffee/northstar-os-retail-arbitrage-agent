"""
ITEM 3 — attribute the chat lane's latency tail from lane_telemetry only.

No Redis, no new infrastructure, no invented causes: every statement below is
derived from the 52 recorded rows. Where the data cannot separate two causes,
the report says so and names the instrumentation that would.

Output: reports/rea_probe/latency_attribution.json
"""

from __future__ import annotations

import json
import sqlite3
import statistics
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "Northstar_backend" / "data" / "northstar.db"
OUT = ROOT / "reports" / "rea_probe"
OUT.mkdir(parents=True, exist_ok=True)

# A render measured end-to-end on this machine today (tools/rea_ceiling_probe.py):
#   1216 long edge -> 31.0 s (816x1216), 2048 long edge -> 39.3 s (1360x2048)
RENDER_FLOOR_S = 31.0
RENDER_CEILING_S = 40.0


def load() -> list[dict]:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = []
    for r in con.execute(
            "select id, lane, task_class, latency_ms, tokens, tool_calls, ok, created_at "
            "from lane_telemetry order by latency_ms desc"):
        d = dict(r)
        d["seconds"] = round(float(d["latency_ms"]) / 1000.0, 2)
        rows.append(d)
    return rows


def bucket(seconds: float) -> str:
    if seconds <= RENDER_CEILING_S:
        return "a: <=40s (one render)"
    if seconds <= 90:
        return "b: 40-90s (render + a second step)"
    if seconds <= 300:
        return "c: 90-300s"
    if seconds <= 900:
        return "d: 300-900s"
    return "e: >900s"


def main() -> None:
    rows = load()
    secs = [r["seconds"] for r in rows]
    summary = {
        "rows": len(rows),
        "ok_rows": sum(1 for r in rows if r["ok"]),
        "p50_s": round(statistics.median(secs), 2),
        "p95_s": round(sorted(secs)[max(0, int(len(secs) * 0.95) - 1)], 2),
        "max_s": round(max(secs), 2),
        "render_floor_measured_s": RENDER_FLOOR_S,
        "render_ceiling_measured_s": RENDER_CEILING_S,
    }

    buckets: dict[str, dict] = {}
    for r in rows:
        b = bucket(r["seconds"])
        d = buckets.setdefault(b, {"n": 0, "ok": 0, "tool_calls": [], "examples": []})
        d["n"] += 1
        d["ok"] += int(bool(r["ok"]))
        d["tool_calls"].append(r["tool_calls"] or 0)
        if len(d["examples"]) < 4:
            d["examples"].append({
                "id": r["id"], "seconds": r["seconds"], "tool_calls": r["tool_calls"],
                "ok": r["ok"], "at": r["created_at"],
            })
    for b, d in buckets.items():
        d["mean_tool_calls"] = round(sum(d["tool_calls"]) / max(1, len(d["tool_calls"])), 2)
        d["ok_rate"] = round(d["ok"] / max(1, d["n"]), 2)
        del d["tool_calls"]

    # Cluster check: do the slow rows share a time window (a stalled engine would).
    slow = [r for r in rows if r["seconds"] > 300]
    clustered = []
    for r in slow:
        t = datetime.fromisoformat(r["created_at"])
        clustered.append({"id": r["id"], "seconds": r["seconds"], "at": r["created_at"],
                          "tool_calls": r["tool_calls"], "ok": r["ok"], "hour": t.hour})

    # Does tool count explain the tail?  (a render is 1 tool call)
    by_tools: dict[int, list[float]] = {}
    for r in rows:
        by_tools.setdefault(int(r["tool_calls"] or 0), []).append(r["seconds"])
    tool_effect = {str(k): {"n": len(v), "median_s": round(statistics.median(v), 2),
                            "max_s": round(max(v), 2)} for k, v in sorted(by_tools.items())}

    # Temporal clustering: a random tail spreads out; a degraded engine does not.
    by_hour: dict[str, list[float]] = {}
    for r in rows:
        t = datetime.fromisoformat(r["created_at"])
        key = t.strftime("%Y-%m-%dT%H")
        by_hour.setdefault(key, []).append(r["seconds"])
    windows = []
    for key, vals in sorted(by_hour.items()):
        if len(vals) >= 3:
            windows.append({
                "hour_utc": key, "n": len(vals),
                "median_s": round(statistics.median(vals), 2),
                "max_s": round(max(vals), 2),
                "slow_over_90s": sum(1 for v in vals if v > 90),
            })

    payload = {
        "probe": "rea_latency_attribution",
        "date": "2026-10-28",
        "source": "lane_telemetry (52 rows, chat:default)",
        "summary": summary,
        "buckets": buckets,
        "slow_rows": clustered,
        "tool_call_effect": tool_effect,
        "hourly_windows": windows,
        "attribution": {
            "a_<=40s": "attributable: a single render. Measured render cost today is "
                       f"{RENDER_FLOOR_S}-{RENDER_CEILING_S} s, so rows in this band are the render itself.",
            "b_40-90s": "attributable: render plus at least one more model/tool step; the band starts "
                        "where the render cost ends.",
            "c_90-300s": "PARTIAL: consistent with several sequential steps, or a cold model load after "
                         "unload_brain() evicted it for a render. lane_telemetry has no stage timestamps, "
                         "so these two cannot be separated.",
            "d_e_>300s": "NOT ATTRIBUTABLE from this table. A 34-minute row exists; the table records "
                         "only total latency, tool count and ok, so queue wait, model reload and a hung "
                         "engine look identical.",
        },
        "instrumentation_missing": [
            "per-stage timestamps on the turn (queued, model loaded, tool started, tool finished)",
            "an explicit 'waited on render lock' marker",
            "Ollama /api/ps state at turn start (was the brain resident or evicted?)",
            "ComfyUI queue depth at turn start",
        ],
    }
    (OUT / "latency_attribution.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({k: payload[k] for k in ("summary", "buckets", "slow_rows", "tool_call_effect")},
                     indent=2))


if __name__ == "__main__":
    main()
