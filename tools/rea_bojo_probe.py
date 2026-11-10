"""
REA 1.5 probe — measure the substrate instead of guessing at it.

Three measurements, all local, all free, none of which touch the live GPU lane:

1. Real lane latency from `lane_telemetry` (the system's own recorded history).
2. SQLite concurrent-writer behaviour: does a second writer fail or wait?
   Tested on a disposable temp DB, not the live one.
3. Host headroom snapshot (RAM / VRAM) so any claim about the binding
   constraint is dated.

Deliberately NOT done: firing a render into the live ComfyUI lane while the
operator's stack is serving. The report says why.

Run: python tools/rea_bojo_probe.py
"""

from __future__ import annotations

import json
import os
import sqlite3
import statistics
import subprocess
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "Northstar_backend" / "data" / "northstar.db"
OUT = ROOT / "reports" / "rea_probe"
OUT.mkdir(parents=True, exist_ok=True)


def lane_stats() -> dict:
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute(
        "select lane, task_class, latency_ms, tool_calls, ok from lane_telemetry")]
    by_lane: dict[str, list[float]] = {}
    for r in rows:
        key = f"{r['lane']}|{r['task_class']}"
        by_lane.setdefault(key, []).append(float(r["latency_ms"]) / 1000.0)

    def summarise(v: list[float]) -> dict:
        v = sorted(v)
        return {
            "n": len(v),
            "p50_s": round(statistics.median(v), 2),
            "p95_s": round(v[max(0, int(len(v) * 0.95) - 1)], 2),
            "max_s": round(v[-1], 2),
            "mean_s": round(sum(v) / len(v), 2),
        }

    return {
        "rows": len(rows),
        "ok_rows": sum(1 for r in rows if r["ok"]),
        "by_lane": {k: summarise(v) for k, v in sorted(by_lane.items())},
    }


def sqlite_contention(busy_timeout_ms: int, writers: int = 4, rows_per_writer: int = 60) -> dict:
    """Two+ writers, BEGIN IMMEDIATE, on a disposable WAL database."""
    tmp = Path(tempfile.mkdtemp(prefix="rea_sqlite_"))
    path = tmp / "probe.db"
    con = sqlite3.connect(path)
    con.execute("pragma journal_mode=wal")
    con.execute("create table t (id integer primary key, w integer, v text)")
    con.commit()
    con.close()

    errors: list[str] = []
    committed = {"n": 0}
    lock = threading.Lock()

    def writer(w: int) -> None:
        c = sqlite3.connect(path, timeout=max(0.001, busy_timeout_ms / 1000))
        c.execute(f"pragma busy_timeout={busy_timeout_ms}")
        try:
            for i in range(rows_per_writer):
                try:
                    c.execute("begin immediate")
                    c.execute("insert into t (w, v) values (?, ?)", (w, f"{w}-{i}" * 20))
                    c.commit()
                    with lock:
                        committed["n"] += 1
                except sqlite3.OperationalError as exc:
                    errors.append(str(exc))
                    try:
                        c.rollback()
                    except sqlite3.Error:
                        pass
        finally:
            c.close()

    t0 = time.perf_counter()
    threads = [threading.Thread(target=writer, args=(i,)) for i in range(writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - t0

    check = sqlite3.connect(path)
    final = check.execute("select count(*) from t").fetchone()[0]
    check.close()

    return {
        "busy_timeout_ms": busy_timeout_ms,
        "writers": writers,
        "attempted": writers * rows_per_writer,
        "committed": committed["n"],
        "errors": len(errors),
        "first_error": errors[0] if errors else None,
        "elapsed_s": round(elapsed, 3),
        "rows_in_db": final,
    }


def host() -> dict:
    out: dict = {}
    try:
        import psutil  # type: ignore
        vm = psutil.virtual_memory()
        out["ram_total_gb"] = round(vm.total / 1e9, 2)
        out["ram_available_gb"] = round(vm.available / 1e9, 2)
        out["ram_used_pct"] = vm.percent
    except Exception as exc:
        out["ram_error"] = type(exc).__name__
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total,memory.used,memory.free,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=20)
        if r.returncode == 0:
            total, used, free, util = [x.strip() for x in r.stdout.strip().split(",")]
            out["vram_total_mb"] = int(total)
            out["vram_used_mb"] = int(used)
            out["vram_free_mb"] = int(free)
            out["gpu_util_pct"] = int(util)
    except Exception as exc:
        out["vram_error"] = type(exc).__name__
    return out


def main() -> None:
    data = {
        "probe": "rea_bojo_probe",
        "date": "2026-10-28",
        "host": host(),
        "lane_latency": lane_stats(),
        "sqlite": [sqlite_contention(0), sqlite_contention(5000)],
        "not_done": (
            "No render was fired into the live ComfyUI lane during this probe: the "
            "operator's stack was serving (backend :8000, ComfyUI :8188, Ollama :11434) "
            "and RAM headroom was the documented binding constraint. Lane latency comes "
            "from the system's own recorded telemetry instead."
        ),
    }
    (OUT / "bojo_probe.json").write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
