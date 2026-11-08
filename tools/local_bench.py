"""Local-model benchmark: throughput and time-to-first-token, per role, on whatever
device the model actually runs on.

The earlier benchmarks in this repository were all measured while Ollama was pinned to
the CPU (`OLLAMA_LLM_LIBRARY=cpu`, `OLLAMA_NUM_GPU=0`). Their numbers are real but they
describe a different machine. This harness reports the device alongside the number so the
two can never be confused again.

    python tools/local_bench.py                    # all mapped roles
    python tools/local_bench.py --roles bojo,coder
    python tools/local_bench.py --json
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "tools"))
import gpu_budget  # noqa: E402

OUT = ROOT / "reports" / "ty" / "local_bench_gpu_20261107.json"

PROMPT = ("Name three things a marketplace seller must check before listing a product. "
          "Answer in three short lines.")

EMBED_TEXTS = ["northstar seller listing", "profit margin per sku",
               "competitor price watch", "a+ content module", "buy box ownership"]


def _post(path: str, payload: Dict[str, Any], timeout: float = 300.0) -> Dict[str, Any]:
    req = urllib.request.Request(
        gpu_budget.base_url() + path, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace") or "{}")


def _device() -> str:
    served = gpu_budget.ps()
    return served[0]["processor"] if served else "unknown"


def bench_chat(model: str, role: str, repeats: int = 3) -> Dict[str, Any]:
    ttft: List[float] = []
    tps: List[float] = []
    total: List[float] = []
    for _ in range(repeats):
        started = time.time()
        body = _post("/api/generate", {"model": model, "prompt": PROMPT,
                                       "stream": False, "keep_alive": "5m",
                                       "options": {"num_predict": 128}})
        total.append(time.time() - started)
        eval_count = int(body.get("eval_count") or 0)
        eval_ns = int(body.get("eval_duration") or 0)
        prompt_ns = int(body.get("prompt_eval_duration") or 0)
        if eval_count and eval_ns:
            tps.append(eval_count / (eval_ns / 1e9))
        if prompt_ns:
            ttft.append(prompt_ns / 1e9)
    return {
        "role": role, "model": model, "device": _device(), "repeats": repeats,
        "ttft_s": round(statistics.median(ttft), 3) if ttft else None,
        "tokens_per_s": round(statistics.median(tps), 2) if tps else None,
        "wall_s": round(statistics.median(total), 2) if total else None,
    }


def bench_embeddings(model: str, role: str = "embeddings") -> Dict[str, Any]:
    started = time.time()
    dims = 0
    for text in EMBED_TEXTS:
        body = _post("/api/embeddings", {"model": model, "prompt": text})
        dims = len(body.get("embedding") or [])
    elapsed = time.time() - started
    return {"role": role, "model": model, "device": _device(),
            "texts": len(EMBED_TEXTS), "dims": dims,
            "per_text_ms": round(1000 * elapsed / len(EMBED_TEXTS), 1),
            "wall_s": round(elapsed, 2)}


def run(roles: Optional[List[str]] = None) -> Dict[str, Any]:
    wanted = roles or list(gpu_budget.ROLE_MODELS)
    rows: List[Dict[str, Any]] = []
    for role in wanted:
        model = gpu_budget.ROLE_MODELS.get(role)
        if not model:
            rows.append({"role": role, "skipped": "no model mapped"})
            continue
        if role == "embeddings":
            rows.append(bench_embeddings(model, role))
        else:
            rows.append(bench_chat(model, role))
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ollama": gpu_budget.base_url(),
            "vram": gpu_budget.snapshot(), "ram": gpu_budget.ram(),
            "rows": rows}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Local-model benchmark (device-aware)")
    parser.add_argument("--roles", default="")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    roles = [r.strip() for r in ns.roles.split(",") if r.strip()] or None
    result = run(roles)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if ns.json:
        print(json.dumps(result["rows"], indent=2))
    else:
        print(f"{'role':<12}{'model':<24}{'device':<12}{'tok/s':>7}{'ttft':>8}{'wall':>8}")
        for row in result["rows"]:
            if "skipped" in row:
                print(f"{row['role']:<12}{row['skipped']}")
                continue
            tps = row.get("tokens_per_s")
            if tps is None:
                print(f"{row['role']:<12}{row['model']:<24}{row['device']:<12}"
                      f"{'-':>7}{'-':>8}{row.get('per_text_ms', 0):>7}ms/text")
                continue
            print(f"{row['role']:<12}{row['model']:<24}{row['device']:<12}"
                  f"{tps:>7}{row.get('ttft_s') or 0:>8}{row.get('wall_s') or 0:>8}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
