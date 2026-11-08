"""The VLM layer: pixels in, structured text out, and never the other way round.

Work order §5.1 layer 3. Only a local model sees pixels; what leaves this module is JSON
and text, after the privacy filter. That is why `describe_screen` returns a dict rather
than a blob: the caller can enforce a schema, and the report can show what the model was
asked and what it answered.

    python -m tools.vision.understand --v1
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

import gpu_budget  # noqa: E402
from . import capture, privacy  # noqa: E402

#: Chosen by measurement, and the verdict was corrected on 2026-11-08 (D8).
#:
#: The D7 conclusion -- "qwen2.5vl:7b degenerate, llava:7b correct" -- was measured against
#: a server whose User environment pinned `OLLAMA_KV_CACHE_TYPE=q4_0` with a 65536 context.
#: On a clean server (f16 KV cache, num_ctx 8192) the result reverses:
#:
#:   qwen2.5vl:7b  0.47-0.75 s warm, valid JSON, read the foreground window's real title
#:   llava:7b      1.89-1.91 s warm, valid JSON, but invented apps that were not open
#:
#: llava listed "Windows Start Menu", "Control Panel" and "Visual Studio Code"; the window
#: list at the same moment held a Windows Terminal, Settings and Chrome. qwen2.5vl named
#: "OC | Ty director finish order", which is the exact terminal title. That is a clear
#: margin on correctness, so the incumbent moves. Evidence:
#: `reports/ty/d8_qwen25vl_clean11434.json`, `reports/ty/d8_vision_retest_llava.json`.
MODEL = "qwen2.5vl:7b"
MODEL_FALLBACK = "llava:7b"
NUM_CTX = 8192
MAX_WIDTH = 1280


def _downscale(png: bytes, max_width: int = MAX_WIDTH) -> bytes:
    """Shrink a frame before the encoder sees it.

    Measured 2026-11-07: a 2560x1600 frame made qwen2.5vl's multimodal encoder fail with
    `mtmd_batch_encode: std::bad_alloc` while Bojo and embeddings were resident. App
    identification does not need native resolution, and the encoder cost scales with
    pixels, so the frame is downscaled before it leaves the machine.
    """
    try:
        import io

        from PIL import Image  # noqa: PLC0415

        image = Image.open(io.BytesIO(png))
        if image.width <= max_width:
            return png
        ratio = max_width / float(image.width)
        resized = image.resize((max_width, max(1, int(image.height * ratio))),
                               Image.LANCZOS)
        buffer = io.BytesIO()
        resized.save(buffer, format="PNG")
        return buffer.getvalue()
    except Exception:  # noqa: BLE001 - a downscale failure must not lose the frame
        return png

SCREEN_PROMPT = (
    "You are looking at a screenshot of a Windows desktop. Answer with JSON only: "
    '{"apps":[{"name":"","purpose":""}],"foreground":""}. '
    "List each visible application window once, give its purpose in eight words or fewer, "
    "and name the window that has focus. No prose, no markdown."
)


def _post(payload: Dict[str, Any], timeout: float = 300.0) -> Dict[str, Any]:
    import urllib.request

    req = urllib.request.Request(
        gpu_budget.base_url() + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace") or "{}")


def parse_json(text: str) -> Dict[str, Any]:
    """The model's answer as JSON, or an empty dict. Never raises on prose."""
    if not text:
        return {}
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?|```$", "", cleaned, flags=re.MULTILINE).strip()
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except ValueError:
        pass
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}
    return {}


def describe_screen(*, png: Optional[bytes] = None, model: str = MODEL,
                    window: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Describe the visible desktop. A blocked window yields no pixels and no answer."""
    started = time.time()
    shot = {"ok": True, "png": png, "size": None}
    if png is None:
        shot = capture.frame(window)
        if shot.get("blocked"):
            return {"ok": False, "blocked": True, "reason": shot.get("reason"),
                    "apps": [], "seconds": round(time.time() - started, 1)}
        if not shot.get("ok"):
            return {"ok": False, "reason": shot.get("reason"), "apps": [],
                    "seconds": round(time.time() - started, 1)}

    payload = {
        "model": model, "prompt": SCREEN_PROMPT, "stream": False,
        "keep_alive": "5m", "format": "json",
        "images": [base64.b64encode(_downscale(shot["png"])).decode("ascii")],
        "options": {"temperature": 0.0, "num_predict": 300, "num_ctx": NUM_CTX},
    }
    try:
        body = _post(payload)
    except Exception as exc:  # noqa: BLE001 - a model failure is reported, not hidden
        return {"ok": False, "reason": f"{type(exc).__name__}: {exc}", "apps": [],
                "seconds": round(time.time() - started, 1)}

    raw = str(body.get("response") or "")
    parsed = parse_json(raw)
    apps: List[Dict[str, str]] = []
    for entry in parsed.get("apps") or []:
        if isinstance(entry, dict) and entry.get("name"):
            apps.append({"name": privacy.redact(str(entry.get("name"))),
                         "purpose": privacy.redact(str(entry.get("purpose") or ""))})
    return {
        "ok": bool(apps),
        "blocked": False,
        "apps": apps,
        "foreground": privacy.redact(str(parsed.get("foreground") or "")),
        "raw_is_json": bool(parsed),
        "seconds": round(time.time() - started, 1),
        "model": model,
        "device": (gpu_budget.ps() or [{}])[0].get("processor", "unknown"),
        "size": shot.get("size"),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Vision understanding (VLM)")
    parser.add_argument("--v1", action="store_true", help="run the V1 screen-awareness test")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)

    result = describe_screen()
    print(json.dumps(result, indent=2))
    if ns.v1:
        # V1: no browser required, valid JSON, names real applications.
        ok = bool(result.get("ok") and result.get("raw_is_json") and result.get("apps"))
        print(json.dumps({"v1": {"pass": ok, "apps": len(result.get("apps") or [])}}))
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
