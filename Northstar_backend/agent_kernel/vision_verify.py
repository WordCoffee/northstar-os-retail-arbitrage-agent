"""Ty's Vision — local visual verification of a render or a screenshot.

A design constraint is only met if it can be seen. This module asks the local
vision model a single yes/no question about the image and returns a structured
verdict. It never claims a pass when the model is unavailable: `available: false`
is a failed verification, not a silent success.

The default model is the 2026-11-04 bake-off winner, `gemma3:4b` (18/20,
JSON parse rate 1.0). The two misses were a small barcode and a square-canvas
judgement; use OCR for barcode/text and geometry for canvas, not this model.

The caller is injectable so the graduation gate and tests run without a GPU.
"""
from __future__ import annotations

import base64
import json
import os
import re
from typing import Any, Callable, Dict, Optional

MODEL = os.environ.get("NORTHSTAR_VISION_MODEL", "gemma3:4b")
URL = os.environ.get("NORTHSTAR_VISION_URL", "http://127.0.0.1:11434/api/chat")
TIMEOUT_S = float(os.environ.get("NORTHSTAR_VISION_TIMEOUT", "180"))
MAX_EDGE = 640
NUM_CTX = 2048

PROMPT = (
    "You are a strict visual verifier for an e-commerce product asset. "
    "Look only at the image. Decide whether it satisfies this constraint:\n"
    "{constraint}\n"
    "Judge what is visible, not what was intended. If the constraint is not "
    "clearly satisfied, or the image is ambiguous, pass=false. "
    'Reply with exactly one JSON object: {{"pass": true|false, '
    '"reasons": ["..."], "confidence": 0.0-1.0}}'
)


def _parse(raw: str) -> Dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the vision answer")
    payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict) or "pass" not in payload:
        raise ValueError("vision answer has no pass field")
    reasons = payload.get("reasons")
    if isinstance(reasons, str):
        reasons = [reasons]
    confidence = payload.get("confidence")
    try:
        confidence = float(confidence) if confidence is not None else None
    except (TypeError, ValueError):
        confidence = None
    return {"pass": bool(payload.get("pass")),
            "reasons": [str(r)[:300] for r in (reasons or [])][:8],
            "confidence": confidence}


def _prepare_image(image_bytes: bytes, max_edge: int = MAX_EDGE) -> bytes:
    """Bound the vision tokens: 640px is the bake-off setting."""
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(image_bytes)) as image:
        img = image.convert("RGB")
        img.thumbnail((int(max_edge), int(max_edge)), Image.LANCZOS)
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return buf.getvalue()


def _call_model(image_bytes: bytes, constraint: str) -> str:
    import urllib.request

    prepared = _prepare_image(image_bytes)
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(constraint=constraint),
                      "images": [base64.b64encode(prepared).decode("ascii")]}],
        "stream": False,
        "keep_alive": "2m",
        # `format: json` returns HTTP 500 with images on the qwen runner
        # (measured 2026-11-04); gemma3 answers JSON from the prompt, and the
        # parser enforces it. 2K ctx keeps the model inside the box's RAM.
        "options": {"temperature": 0.0, "num_ctx": NUM_CTX},
    }
    req = urllib.request.Request(URL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as response:
        data = json.loads(response.read().decode("utf-8"))
    return str((data.get("message") or {}).get("content") or "")


def verify(image_bytes: bytes, constraint: str, *,
           caller: Optional[Callable[[bytes, str], str]] = None) -> Dict[str, Any]:
    """Ask the local vision model whether the image meets the constraint."""
    if not image_bytes:
        return {"ok": False, "pass": None, "available": False,
                "reason": "no_image", "reasons": [], "model": MODEL}
    if not str(constraint or "").strip():
        return {"ok": False, "pass": None, "available": False,
                "reason": "no_constraint", "reasons": [], "model": MODEL}
    try:
        raw = (caller or _call_model)(image_bytes, str(constraint))
        verdict = _parse(raw)
    except Exception as exc:  # noqa: BLE001 - unavailable is a failed check
        return {"ok": False, "pass": None, "available": False,
                "reason": f"{type(exc).__name__}: {exc}"[:300],
                "reasons": [], "model": MODEL}
    return {"ok": verdict["pass"], "pass": verdict["pass"], "available": True,
            "reason": "" if verdict["pass"] else "constraint_not_met",
            "reasons": verdict["reasons"], "confidence": verdict["confidence"],
            "model": MODEL, "constraint": str(constraint)[:400]}


__all__ = ["verify", "MODEL", "PROMPT"]
