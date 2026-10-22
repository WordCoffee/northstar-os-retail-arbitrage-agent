"""Local vision QC lane — asks "does this render match the brief?" without eating the GPU.

Design rules, because this box has ONE 16 GB card and the render lanes need it:

1. **CPU by default when the GPU is busy.** The lane reads free VRAM first. It
   only asks Ollama for GPU layers when there is real headroom; otherwise it
   pins `num_gpu: 0` and runs on the CPU. Vision QC is a check, not a render -
   it must never be the reason a render fails.
2. **It never lingers.** Every call sets `keep_alive: 0`, so the QC model is
   unloaded the moment the answer comes back. Nothing sits in VRAM between checks.
3. **Small images.** The frame is downscaled before it is sent (default 768 px on
   the long side), which cuts vision tokens roughly quadratically.
4. **A verdict, not a paragraph.** The model is asked for strict JSON; if the
   reply will not parse, the lane says `unparsed` and returns the raw text -
   it never invents a verdict.

    python Northstar_backend/local_vision.py --engines
    python Northstar_backend/local_vision.py --image plate.png --brief "a kraft pouch"
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from typing import Any, Callable, Dict, Optional

DEFAULT_MODEL = os.environ.get("VISION_QC_MODEL", "qwen2.5vl:7b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
#: GPU is only used when at least this much VRAM is free (the 7B VL model needs ~6 GB).
GPU_HEADROOM_MB = int(os.environ.get("VISION_QC_GPU_HEADROOM_MB", "7000"))
#: Long side of the frame sent to the model. Smaller = fewer tokens = less work.
DEFAULT_MAX_SIDE = int(os.environ.get("VISION_QC_MAX_SIDE", "768"))

Verdict = Dict[str, Any]
#: Injectable transport: (url, payload, timeout) -> parsed JSON. Tests replace it.
Poster = Callable[[str, Dict[str, Any], float], Dict[str, Any]]
#: Injectable VRAM reader: () -> free MiB or None. Tests replace it.
VramReader = Callable[[], Optional[int]]

_PROMPT = (
    "You are a packaging-artwork QA reviewer. Look at the image and answer ONLY "
    "with JSON, no prose, in exactly this shape:\n"
    '{"matches_brief": true|false, "issues": ["..."], "confidence": 0.0-1.0, '
    '"description": "one short sentence"}\n'
    "Judge only what is visible. If the image is blank, unreadable, or does not "
    "show a product, say so in issues and set matches_brief to false."
)


def _http_post(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace") or "{}")


def vram_free_mb() -> Optional[int]:
    """Free VRAM in MiB, or None when it cannot be read (never guessed)."""
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return None
        return int(out.stdout.strip().splitlines()[0])
    except Exception:  # noqa: BLE001
        return None


def choose_mode(free_mb: Optional[int], allow_gpu: Optional[bool]) -> str:
    """'gpu' or 'cpu'. Unknown VRAM means cpu - the safe direction."""
    if allow_gpu is False:
        return "cpu"
    if allow_gpu is True:
        return "gpu"
    if free_mb is None:
        return "cpu"
    return "gpu" if free_mb >= GPU_HEADROOM_MB else "cpu"


def _downscale(image_bytes: bytes, max_side: int) -> bytes:
    """Shrink the frame before it becomes vision tokens. Best effort."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(image_bytes)) as im:
            im = im.convert("RGB")
            w, h = im.size
            scale = max_side / float(max(w, h))
            if scale < 1.0:
                im = im.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                               Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, format="PNG", optimize=True)
            return buf.getvalue()
    except Exception:  # noqa: BLE001 - a QC check must not die on an odd PNG
        return image_bytes


def _parse_verdict(raw: str) -> Dict[str, Any]:
    """Pull the JSON object out of the reply. Unparsed is reported, not hidden."""
    text = (raw or "").strip()
    if not text:
        return {"verdict": "unparsed", "raw": ""}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {"verdict": "unparsed", "raw": text[:400]}
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"verdict": "unparsed", "raw": text[:400]}
    if not isinstance(data, dict):
        return {"verdict": "unparsed", "raw": text[:400]}
    issues = data.get("issues") or []
    if isinstance(issues, str):
        issues = [issues]
    return {
        "verdict": "ok",
        "matches_brief": bool(data.get("matches_brief")),
        "issues": [str(i)[:200] for i in issues][:8],
        "confidence": data.get("confidence"),
        "description": str(data.get("description") or "")[:300],
    }


def qc_image(image_bytes: bytes, brief: str, *, model: Optional[str] = None,
             max_side: Optional[int] = None, allow_gpu: Optional[bool] = None,
             timeout: float = 600.0, poster: Optional[Poster] = None,
             vram_reader: Optional[VramReader] = None) -> Dict[str, Any]:
    """Ask the local VL model whether a render matches the brief.

    Returns a dict that always carries `mode` ('gpu'|'cpu'), `seconds`, and the
    VRAM reading before/after, so the cost of the check is visible.
    """
    if not image_bytes:
        raise ValueError("image is required")
    read_vram = vram_reader or vram_free_mb
    post = poster or _http_post
    mdl = model or DEFAULT_MODEL
    side = int(max_side or DEFAULT_MAX_SIDE)

    before = read_vram()
    mode = choose_mode(before, allow_gpu)

    payload: Dict[str, Any] = {
        "model": mdl,
        "prompt": f"{_PROMPT}\n\nBrief: {brief.strip()[:600] or '(no brief given)'}",
        "images": [base64.b64encode(_downscale(image_bytes, side)).decode("ascii")],
        "stream": False,
        "keep_alive": 0,  # never leave the QC model resident
        "options": {"temperature": 0.1, "num_predict": 220},
    }
    if mode == "cpu":
        payload["options"]["num_gpu"] = 0

    t0 = time.time()
    try:
        resp = post(f"{OLLAMA_HOST}/api/generate", payload, timeout)
    except Exception as exc:  # noqa: BLE001 - report, never fabricate a verdict
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:300],
                "mode": mode, "model": mdl, "seconds": round(time.time() - t0, 1),
                "vram_free_mb_before": before, "vram_free_mb_after": read_vram()}

    verdict = _parse_verdict(str(resp.get("response", "")))
    verdict.update({
        "ok": verdict.get("verdict") == "ok",
        "mode": mode,
        "model": mdl,
        "max_side": side,
        "seconds": round(time.time() - t0, 1),
        "vram_free_mb_before": before,
        "vram_free_mb_after": read_vram(),
        "eval_count": resp.get("eval_count"),
    })
    return verdict


def qc_file(path: str, brief: str, **kwargs) -> Dict[str, Any]:
    with open(path, "rb") as fh:
        return qc_image(fh.read(), brief, **kwargs)


def engines() -> Dict[str, Any]:
    """What this lane can do right now, and which device it would pick."""
    free = vram_free_mb()
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=4) as resp:
            models = [m.get("name", "") for m in
                      json.loads(resp.read().decode("utf-8", "replace")).get("models", [])]
    except Exception as exc:  # noqa: BLE001
        return {"available": False, "error": f"{type(exc).__name__}: {exc}"[:200],
                "model": DEFAULT_MODEL, "vram_free_mb": free}
    return {
        "available": any(m.startswith(DEFAULT_MODEL.split(":")[0]) for m in models),
        "model": DEFAULT_MODEL,
        "installed": [m for m in models if DEFAULT_MODEL.split(":")[0] in m],
        "vram_free_mb": free,
        "gpu_headroom_mb": GPU_HEADROOM_MB,
        "would_use": choose_mode(free, None),
        "keep_alive": 0,
        "max_side": DEFAULT_MAX_SIDE,
    }


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Local vision QC lane")
    ap.add_argument("--engines", action="store_true")
    ap.add_argument("--image", default=None)
    ap.add_argument("--brief", default="")
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-side", type=int, default=None)
    ap.add_argument("--gpu", choices=["auto", "yes", "no"], default="auto")
    args = ap.parse_args(argv)

    if args.engines:
        print(json.dumps(engines(), indent=2))
        return 0
    if args.image:
        allow = {"auto": None, "yes": True, "no": False}[args.gpu]
        out = qc_file(args.image, args.brief, model=args.model,
                      max_side=args.max_side, allow_gpu=allow)
        print(json.dumps(out, indent=2))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
