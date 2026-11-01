"""Measure what a resident generation actually costs, in RAM and VRAM.

The autonomy gate used to decide from PRE-LOAD free RAM plus a disk-size guess,
which is how a 2.09 GB post-load headroom was reported while the gate still said
GO. This tool answers the only question that matters for a long unattended run:

    while the model is resident and generating, what is the LOWEST free RAM?

It samples `psutil.virtual_memory().available` continuously and Ollama's `/api/ps`
(size, size_vram) once a second for the whole generation, then unloads the model.

    python tools/measure_model_resident.py --model bojo:gpu-orig
    python tools/measure_model_resident.py --model bojo:gpu-orig --floor 3.0 --json

Exit codes: 0 measured and floor met, 1 measured and floor MISSED, 2 could not
measure (no Ollama, model missing, empty generation).
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

OLLAMA = "http://127.0.0.1:11434"

PROMPT = (
    "Write six short numbered sentences describing how a person makes pour-over "
    "coffee, one per line. No preamble."
)


def _post(path: str, payload: Dict[str, Any], timeout: float = 600.0):
    req = urllib.request.Request(
        OLLAMA + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    return urllib.request.urlopen(req, timeout=timeout)


def _get(path: str, timeout: float = 15.0) -> Dict[str, Any]:
    with urllib.request.urlopen(OLLAMA + path, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _available_gb() -> Optional[float]:
    try:
        import psutil  # type: ignore
        return round(psutil.virtual_memory().available / (1024 ** 3), 3)
    except Exception:  # noqa: BLE001
        return None


def _resident(model: str) -> List[Dict[str, Any]]:
    try:
        rows = _get("/api/ps").get("models") or []
    except (urllib.error.URLError, OSError, ValueError):
        return []
    out = []
    for row in rows:
        name = str(row.get("name") or row.get("model") or "")
        if model and not (name == model or name.startswith(model.split(":")[0])):
            continue
        out.append({"name": name,
                    "size_gb": round(float(row.get("size") or 0) / 1024 ** 3, 3),
                    "vram_gb": round(float(row.get("size_vram") or 0) / 1024 ** 3, 3)})
    return out


class Sampler(threading.Thread):
    def __init__(self, model: str, interval: float = 0.2) -> None:
        super().__init__(daemon=True)
        self.model = model
        self.interval = interval
        self.stop = threading.Event()
        self.ram: List[float] = []
        self.resident: List[Dict[str, Any]] = []

    def run(self) -> None:
        last_ps = 0.0
        while not self.stop.is_set():
            gb = _available_gb()
            if gb is not None:
                self.ram.append(gb)
            now = time.monotonic()
            if now - last_ps >= 1.0:
                last_ps = now
                rows = _resident(self.model)
                if rows:
                    self.resident = rows
            time.sleep(self.interval)


def measure(model: str, *, prompt: str = PROMPT, num_ctx: Optional[int] = None,
            num_gpu: Optional[int] = None,
            keep_alive: str = "2m", unload: bool = True) -> Dict[str, Any]:
    baseline = _available_gb()
    sampler = Sampler(model, interval=0.2)
    sampler.start()
    started = time.monotonic()
    tokens = 0
    text_parts: List[str] = []
    error = ""
    payload: Dict[str, Any] = {"model": model, "prompt": prompt, "stream": True,
                              "keep_alive": keep_alive}
    opts: Dict[str, Any] = {"num_predict": 160}
    if num_ctx:
        opts["num_ctx"] = int(num_ctx)
    if num_gpu is not None:
        opts["num_gpu"] = int(num_gpu)
    if opts:
        payload["options"] = opts
    try:
        with _post("/api/generate", payload) as resp:
            for raw in resp:
                line = raw.decode("utf-8").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("response"):
                    text_parts.append(str(event["response"]))
                if event.get("done"):
                    tokens = int(event.get("eval_count") or 0)
    except urllib.error.URLError as exc:
        error = f"ollama unreachable: {exc}"
    except Exception as exc:  # noqa: BLE001 - a measurement failure is reported
        error = f"{type(exc).__name__}: {exc}"
    elapsed = round(time.monotonic() - started, 2)
    sampler.stop.set()
    sampler.join(timeout=3.0)

    resident_during = sampler.resident
    # The model stays loaded for `keep_alive` after the stream ends, so one
    # sample taken now is the most reliable evidence that it was resident at all.
    after = _resident(model)
    if after:
        resident_during = after
    if unload:
        try:
            _post("/api/generate", {"model": model, "keep_alive": 0, "prompt": ""})
        except Exception:  # noqa: BLE001 - unloading is best-effort and recorded
            pass

    min_ram = min(sampler.ram) if sampler.ram else None
    return {
        "model": model,
        "num_ctx": int(num_ctx) if num_ctx else None,
        "baseline_available_gb": baseline,
        "min_available_gb": min_ram,
        "drop_gb": (round(baseline - min_ram, 3)
                    if baseline is not None and min_ram is not None else None),
        "samples": len(sampler.ram),
        "resident_during": resident_during,
        "resident_total_gb": max([r["size_gb"] for r in resident_during], default=0.0),
        "resident_vram_gb": max([r["vram_gb"] for r in resident_during], default=0.0),
        "resident_system_gb": round(
            max([r["size_gb"] for r in resident_during], default=0.0)
            - max([r["vram_gb"] for r in resident_during], default=0.0), 3),
        "tokens": tokens,
        "elapsed_s": elapsed,
        "tok_per_s": round(tokens / elapsed, 2) if elapsed else None,
        "reply_head": ("".join(text_parts).strip()[:120] or ""),
        "error": error,
    }


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="bojo:gpu-orig")
    ap.add_argument("--prompt", default=PROMPT)
    ap.add_argument("--num-ctx", type=int, default=None)
    ap.add_argument("--num-gpu", type=int, default=None)
    ap.add_argument("--floor", type=float, default=3.0)
    ap.add_argument("--json", action="store_true", help="print only the JSON record")
    ap.add_argument("--out", default="")
    args = ap.parse_args(argv)

    rec = measure(args.model, prompt=args.prompt, num_ctx=args.num_ctx,
                  num_gpu=args.num_gpu)
    # A verdict needs a resident sample AND a real cost. A model that answers
    # before the /api/ps poll ever sees it is NOT measured - that is how a
    # "FLOOR-MET" can be reported from an empty sample.
    if rec["error"] or not rec["tokens"]:
        rec["verdict"] = "UNMEASURED"
        code = 2
    elif rec["min_available_gb"] is None or not rec["resident_during"]:
        rec["verdict"] = "UNMEASURED"
        code = 2
    elif rec["min_available_gb"] >= args.floor:
        rec["verdict"] = "FLOOR-MET"
        code = 0
    else:
        rec["verdict"] = "FLOOR-MISSED"
        code = 1
    rec["floor_gb"] = args.floor

    payload = json.dumps(rec, indent=2)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(payload, encoding="utf-8")
    print(payload if args.json or not args.out else payload)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
