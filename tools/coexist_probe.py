"""One measurement per step of the coexistence test: VRAM, RAM, capture latency.

The coexistence test asks one question at several points in time, so the answer must be
measured the same way at each point. `capture_ms` is the UI-responsiveness proxy: a
screen grab that suddenly takes four times as long is the visible sign of a starved
desktop, and it is measured with the same code the vision layer uses.

    python tools/coexist_probe.py --label "step 2: bojo+embeddings"
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import gpu_budget  # noqa: E402


def capture_ms(repeats: int = 3) -> dict:
    """Median desktop-capture latency, through the real vision capture path."""
    try:
        from vision import capture  # noqa: PLC0415

        times = []
        size = None
        for _ in range(max(1, repeats)):
            started = time.time()
            shot = capture.frame()
            times.append(round((time.time() - started) * 1000, 1))
            size = shot.get("size") or size
        times.sort()
        return {"median_ms": times[len(times) // 2], "samples_ms": times, "size": size}
    except Exception as exc:  # noqa: BLE001 - a failed grab is data, not a crash
        return {"error": f"{type(exc).__name__}: {exc}"}


def measure(label: str = "") -> dict:
    vram = gpu_budget.snapshot()
    mem = gpu_budget.ram()
    served = gpu_budget.ps()
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "label": label,
        "vram_used_gb": round((vram.get("used_mb") or 0) / 1024, 2),
        "vram_free_gb": vram.get("free_gb"),
        "vram_used_frac": vram.get("used_frac"),
        "ram_free_gb": mem.get("free_gb"),
        "ram_total_gb": mem.get("total_gb"),
        "served": served,
        "capture": capture_ms(),
        "budget_ok": gpu_budget.verdict(vram, mem)["ok"],
        "budget_problems": gpu_budget.verdict(vram, mem)["problems"],
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Coexistence step probe")
    parser.add_argument("--label", default="")
    parser.add_argument("--out", default="")
    ns = parser.parse_args(argv)
    row = measure(ns.label)
    if ns.out:
        path = Path(ns.out)
        path.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if path.is_file():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                existing = []
        existing.append(row)
        path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(row, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
