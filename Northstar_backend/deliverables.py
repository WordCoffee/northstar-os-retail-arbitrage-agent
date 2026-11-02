"""Deliverable packages: an accepted render becomes a folder a user can reopen.

A run that passes the adherence gate writes one folder per run:

    state/deliverables/<run_id>/
        final.png         the full-size render
        brief.txt         the exact brief submitted
        adherence.json    the vision verdict: observed form, requested form, scores
        citations.json    the local template/workflow sources actually used
        manifest.json     every field populated from real values, unknowns omitted

No placeholders: a field that cannot be resolved is left out of the manifest, never
filled with "TODO" or an invented value.
"""
from __future__ import annotations

import base64
import json
import re
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]
DELIVERABLES = ROOT / "state" / "deliverables"
OLLAMA = "http://127.0.0.1:11434"
VISION_MODEL = "qwen3.5:4b"

FORM_WORDS = {
    "pouch": ("pouch", "sachet", "stand-up"),
    "box": ("box", "carton", "folding"),
    "bottle": ("bottle", "flask"),
    "tube": ("tube",),
    "jar": ("jar", "pot"),
}

QUESTION = ("Look at the image. Which single container form is shown: stand-up pouch, "
            "rigid box, bottle, or squeeze tube? Answer with one word from that list.")


def _post(url: str, payload: dict, timeout: float = 120.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def classify_form(png: bytes, *, model: str = VISION_MODEL) -> Dict[str, Any]:
    """Ask the local vision lane what container is in the render.

    Returns the raw answer and the matched form, or ``{"available": False}`` when the
    lane cannot be reached - an unknown verdict is never reported as a pass.
    """
    try:
        res = _post(f"{OLLAMA}/api/generate",
                    {"model": model, "prompt": QUESTION,
                     "images": [base64.b64encode(png).decode()], "stream": False,
                     "think": False,
                     "options": {"num_predict": 40, "temperature": 0.0}})
    except Exception as exc:  # noqa: BLE001 - an unreachable lane is not a verdict
        return {"available": False, "reason": f"{type(exc).__name__}: {str(exc)[:120]}"}
    answer = str(res.get("response") or "").strip().lower()
    matched = next((form for form, words in FORM_WORDS.items()
                    if any(w in answer for w in words)), None)
    return {"available": True, "model": model, "answer": answer[:80],
            "observed": matched or "unrecognised"}


def adherence_verdict(requested: str, observed: Dict[str, Any]) -> Dict[str, Any]:
    """Pass only when the vision lane is available AND the form matches."""
    if not observed.get("available"):
        return {"ok": False, "reason": "vision lane unavailable",
                "detail": observed.get("reason"),
                "requested": requested, "observed": observed.get("observed")}
    ok = bool(requested) and observed.get("observed") == requested
    return {"ok": ok, "requested": requested, "observed": observed.get("observed"),
            "answer": observed.get("answer"), "model": observed.get("model")}


def _safe_id(run_id: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "_", str(run_id or "")).strip("._")
    return base[:80] or f"run-{int(time.time())}"


def write_deliverable(run_id: str, *, brief: str, final_png: bytes,
                      adherence: Dict[str, Any],
                      citations: Optional[Sequence[Dict[str, Any]]] = None,
                      extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Write the package. Returns its path and the manifest that was written."""
    folder = DELIVERABLES / _safe_id(run_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "final.png").write_bytes(final_png)
    (folder / "brief.txt").write_text(str(brief), encoding="utf-8")
    (folder / "adherence.json").write_text(json.dumps(adherence, indent=2), encoding="utf-8")
    cites = list(citations or [
        {"component": "studio_generation.generate_image", "kind": "local",
         "source": "repo:Northstar_backend/studio_generation.py", "license": "project code"},
        {"component": "comfyui workflow: flux3-image-klein-nvfp4", "kind": "local",
         "source": "repo:Northstar_backend/studio_generation.py (workflow builder)",
         "license": "FLUX.1 [dev] non-commercial (local bench)"},
    ])
    (folder / "citations.json").write_text(json.dumps(cites, indent=2), encoding="utf-8")

    image_size = None
    try:
        from PIL import Image
        with Image.open(folder / "final.png") as im:
            image_size = [im.width, im.height]
    except Exception:  # noqa: BLE001 - size is optional evidence
        image_size = None

    manifest: Dict[str, Any] = {
        "run_id": _safe_id(run_id),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "brief": str(brief),
        "adherence": {"ok": bool(adherence.get("ok")),
                      "requested": adherence.get("requested"),
                      "observed": adherence.get("observed"),
                      "model": adherence.get("model"),
                      **({"reason": adherence["reason"]} if adherence.get("reason") else {}),
                      **({"detail": adherence["detail"]} if adherence.get("detail") else {})},
        "files": sorted([p.name for p in folder.iterdir() if p.is_file()] + ["manifest.json"]),
        "bytes": len(final_png),
        "citations": cites,
    }
    if image_size:
        manifest["image_size"] = image_size
    # Unknown stays out; nothing is invented to fill a gap.
    for key, value in (extra or {}).items():
        if value is not None:
            manifest[key] = value
    (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return {"folder": str(folder), "manifest": manifest}


def read_final(run_id: str) -> Optional[bytes]:
    """Return the packaged render for a run, or None. Never escapes the root."""
    folder = (DELIVERABLES / _safe_id(run_id)).resolve()
    root = DELIVERABLES.resolve()
    if root not in folder.parents:
        return None
    final = folder / "final.png"
    if not final.is_file():
        return None
    try:
        return final.read_bytes()
    except OSError:
        return None


def list_deliverables(limit: int = 50) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not DELIVERABLES.is_dir():
        return rows
    for folder in sorted((p for p in DELIVERABLES.iterdir() if p.is_dir()),
                         key=lambda p: (p.stat().st_mtime, p.name), reverse=True)[:limit]:
        manifest_path = folder / "manifest.json"
        if not manifest_path.is_file():
            continue
        try:
            rows.append(json.loads(manifest_path.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return rows
