"""Retest a local vision model on a clean server, and decide by measurement.

The D7 verdict on `qwen2.5vl:7b` was "degenerate on every temperature and context tested",
but that test ran against a server whose User environment pinned `OLLAMA_LLM_LIBRARY=cpu`,
`OLLAMA_NUM_GPU=0` and `OLLAMA_KV_CACHE_TYPE=q4_0`. A model that was never given the GPU or
a full-precision KV cache has not been fairly judged.

So this runs the same V1 screen-awareness prompt against a server started for the purpose:
GPU allowed, no KV-cache quantisation, `num_ctx` 8192. The old verdict is overwritten only
if the measurement changes.

    python -m tools.vision.retest --model qwen2.5vl:7b --endpoint http://127.0.0.1:11435
"""
from __future__ import annotations

import argparse
import base64
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import capture, understand

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "ty" / "d8_vision_retest.json"

#: The same prompt D7 used, so the comparison is a comparison and not a new test.
PROMPT = understand.SCREEN_PROMPT


def _post(endpoint: str, payload: Dict[str, Any], timeout: float = 300.0) -> Dict[str, Any]:
    import urllib.request

    request = urllib.request.Request(
        endpoint.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace") or "{}")


def run(*, model: str, endpoint: str, num_ctx: int = 8192, runs: int = 3,
        png: Optional[bytes] = None, temperature: float = 0.0,
        json_format: bool = False) -> Dict[str, Any]:
    """One model, one frame, several attempts. Every attempt's raw text is kept."""
    shot = {"ok": True, "png": png}
    if png is None:
        shot = capture.frame()
        if shot.get("blocked"):
            return {"ok": False, "blocked": True, "reason": shot.get("reason")}
        if not shot.get("ok"):
            return {"ok": False, "reason": shot.get("reason")}
    image = base64.b64encode(understand._downscale(shot["png"])).decode("ascii")

    attempts: List[Dict[str, Any]] = []
    for index in range(max(1, runs)):
        payload = {"model": model, "prompt": PROMPT, "stream": False,
                   "keep_alive": "2m",
                   "images": [image],
                   "options": {"temperature": temperature, "num_ctx": int(num_ctx),
                               "num_predict": 300}}
        if json_format:
            payload["format"] = "json"
        started = time.time()
        try:
            body = _post(endpoint, payload)
        except Exception as exc:  # noqa: BLE001 - a failure is a result
            attempts.append({"run": index + 1, "ok": False,
                             "error": f"{type(exc).__name__}: {exc}"})
            continue
        raw = str(body.get("response") or "")
        parsed = understand.parse_json(raw)
        apps = [str(entry.get("name") or "") for entry in parsed.get("apps") or []
                if isinstance(entry, dict)]
        attempts.append({
            "run": index + 1, "ok": bool(apps), "raw": raw[:600],
            "parsed": bool(parsed), "apps": apps,
            "seconds": round(time.time() - started, 2),
            "eval_count": body.get("eval_count"), "model": body.get("model")})
    usable = [row for row in attempts if row.get("ok")]
    return {"ok": bool(usable), "model": model, "endpoint": endpoint,
            "num_ctx": num_ctx, "json_format": json_format,
            "temperature": temperature, "usable_runs": len(usable),
            "attempts": attempts}


def verdict(result: Dict[str, Any]) -> str:
    """A model that answers valid JSON naming apps on a clean server is not degenerate."""
    if not result.get("ok"):
        return "degenerate"
    names = {name for row in result["attempts"] for name in row.get("apps") or []}
    return "coherent" if len(names) >= 2 else "partial"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Clean-server vision retest")
    parser.add_argument("--model", default="qwen2.5vl:7b")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11435")
    parser.add_argument("--num-ctx", type=int, default=8192)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--json", action="store_true", dest="json_format")
    parser.add_argument("--out", default="")
    ns = parser.parse_args(argv)

    result = run(model=ns.model, endpoint=ns.endpoint, num_ctx=ns.num_ctx,
                 runs=ns.runs, json_format=ns.json_format)
    result["verdict"] = verdict(result)
    target = Path(ns.out) if ns.out else OUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("ok", "model", "num_ctx", "json_format",
                                             "usable_runs", "verdict")}, indent=2))
    for row in result.get("attempts") or []:
        print(json.dumps({"run": row.get("run"), "ok": row.get("ok"),
                          "apps": row.get("apps"), "raw": (row.get("raw") or "")[:120]}))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
