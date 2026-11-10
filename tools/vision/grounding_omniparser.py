"""OmniParser-class grounding: detect icons, caption them, match the label.

OmniParser's recipe is a detector plus a captioner: YOLO-style icon boxes, then a vision-language
model names each crop, then the label is matched to the best caption. This is that recipe, with
the pieces this machine has:

* **ultralytics YOLOv8** for boxes — **AGPL-3.0**, allowed here only by the logged dev-only GRANT
  (`reports/ty/grants.md`, 2026-11-09); it is never served and never shipped;
* **Florence-2-base** for captions — MIT weights, `transformers` with `trust_remote_code` because
  the model ships its own modelling file. That is a supply-chain decision, so it is stated in the
  report rather than hidden: the code is fetched at load time from the Microsoft repo.

The measured bar is the same one UI-TARS faced: beat qwen2.5vl's **61.7 %** on the 40-screen set by
**10 points**, or UIA and DOM stay primary.

    & "$env:USERPROFILE\\ComfyUI\\venv\\Scripts\\python.exe" -m tools.vision.grounding_omniparser --probe
    & "$env:USERPROFILE\\ComfyUI\\venv\\Scripts\\python.exe" -m tools.vision.grounding_omniparser --run
"""
from __future__ import annotations

import argparse
import difflib
import io
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from vision import grounding  # noqa: E402

OUT = ROOT / "reports" / "ty" / "d8_grounding_omniparser.json"
SET = ROOT / "state" / "vision" / "grounding_set"
BASELINE = 0.617
ADOPT_MARGIN = 0.10
BAR = grounding.BAR
CAPTION_MODEL = "microsoft/Florence-2-base"
YOLO_WEIGHTS = "yolov8n.pt"


def load() -> Dict[str, Any]:
    """Detector and captioner, each reported as unavailable rather than assumed."""
    state: Dict[str, Any] = {}
    try:
        from ultralytics import YOLO

        state["detector"] = YOLO(YOLO_WEIGHTS)
        state["detector_ok"] = True
    except Exception as exc:  # noqa: BLE001
        state["detector_ok"] = False
        state["detector_error"] = f"{type(exc).__name__}: {exc}"
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoProcessor

        processor = AutoProcessor.from_pretrained(CAPTION_MODEL, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            CAPTION_MODEL, trust_remote_code=True, torch_dtype=torch.float16,
            device_map="cuda")
        model.eval()
        state.update({"captioner": model, "processor": processor, "captioner_ok": True})
    except Exception as exc:  # noqa: BLE001
        state["captioner_ok"] = False
        state["captioner_error"] = f"{type(exc).__name__}: {exc}"
    return state


def detect(detector: Any, image: Any, limit: int = 20) -> List[Tuple[int, int, int, int]]:
    """Icon-ish boxes, largest first, as (x, y, w, h) in image pixels."""
    results = detector.predict(image, verbose=False, conf=0.15)
    boxes: List[Tuple[int, int, int, int]] = []
    for result in results:
        for box in getattr(result, "boxes", []) or []:
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            if x2 - x1 < 8 or y2 - y1 < 8:
                continue
            boxes.append((x1, y1, x2 - x1, y2 - y1))
    boxes.sort(key=lambda b: -(b[2] * b[3]))
    return boxes[:limit]


def caption(state: Dict[str, Any], image: Any, box: Tuple[int, int, int, int]) -> str:
    import torch

    x, y, w, h = box
    crop = image.crop((x, y, x + w, y + h))
    prompt = "<MORE_DETAILED_CAPTION>"
    inputs = state["processor"](text=prompt, images=crop, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        ids = state["captioner"].generate(**inputs, max_new_tokens=40, num_beams=2)
    text = state["processor"].batch_decode(ids, skip_special_tokens=False)[0]
    return str(state["processor"].post_process_generation(
        text, task=prompt, image_size=crop.size).get(prompt) or text)


def pick(captions: List[Tuple[Tuple[int, int, int, int], str]], label: str
         ) -> Optional[Tuple[int, int, int, int]]:
    best, best_score = None, 0.0
    low = str(label).casefold()
    for box, text in captions:
        score = difflib.SequenceMatcher(None, low, str(text).casefold()).ratio()
        if low and low in str(text).casefold():
            score = max(score, 0.95)
        if score > best_score:
            best, best_score = box, score
    return best if best_score >= 0.35 else None


def point_of(box: Tuple[int, int, int, int], size: Tuple[int, int]) -> Dict[str, float]:
    x, y, w, h = box
    return {"x": (x + w / 2) / size[0], "y": (y + h / 2) / size[1]}


def run(limit: int = 0, targets: int = 3) -> Dict[str, Any]:
    from PIL import Image

    manifest = json.loads((SET / "manifest.json").read_text(encoding="utf-8"))
    screens = manifest[:limit] if limit else manifest
    state = load()
    if not state.get("detector_ok") or not state.get("captioner_ok"):
        payload = {"ok": False, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "reason": "detector or captioner unavailable",
                   "detector_error": state.get("detector_error"),
                   "captioner_error": state.get("captioner_error"),
                   "decision": "keep UIA and DOM primary"}
        OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return payload

    trials = hits = abstained = 0
    latency: List[float] = []
    failures: List[Dict[str, Any]] = []
    for row in screens:
        with Image.open(SET / row["file"]) as opened:
            image = opened.convert("RGB")
        started = time.time()
        boxes = detect(state["detector"], image)
        caps = [(box, caption(state, image, box)) for box in boxes]
        latency.append(time.time() - started)
        for target in row["targets"][:targets]:
            trials += 1
            biggest = max(caps, key=lambda item: item[0][2] * item[0][3], default=None)
            chosen = pick(caps, target["name"])
            if chosen is None:
                abstained += 1
                failures.append({"file": row["file"], "target": target["name"],
                                 "reason": "no caption matched"})
            elif grounding.hit(target["box"], point_of(chosen, image.size)):
                hits += 1
            else:
                failures.append({"file": row["file"], "target": target["name"],
                                 "point": point_of(chosen, image.size)})
        state.pop("detector", None)  # keep the payload small; reloaded per run
        state["detector"] = state.get("detector") or None
    rate = hits / trials if trials else 0.0
    payload = {"ok": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "model": "omniparser-class (yolov8n + florence-2-base)",
               "licences": {"detector": "AGPL-3.0 (dev-only GRANT)",
                            "captioner": "MIT (trust_remote_code)"},
               "screens": len(screens), "targets_per_screen": targets,
               "trials": trials, "hits": hits, "hit_rate": round(rate, 3),
               "abstained": abstained,
               "median_seconds": round(sorted(latency)[len(latency) // 2], 2) if latency else None,
               "baseline": BASELINE, "bar": BAR, "adopt_margin": ADOPT_MARGIN,
               "beats_baseline_by_margin": rate >= BASELINE + ADOPT_MARGIN,
               "decision": ("adopt: it clears the baseline by the required margin"
                            if rate >= BASELINE + ADOPT_MARGIN
                            else "keep UIA and DOM primary: it does not clear the bar by 10 points"),
               "failures": failures[:12]}
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="OmniParser-class grounding benchmark")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--targets", type=int, default=3)
    ns = parser.parse_args(argv)
    if ns.probe:
        state = load()
        print(json.dumps({k: state.get(k) for k in
                          ("detector_ok", "captioner_ok", "detector_error",
                           "captioner_error")}, indent=2))
        return 0
    payload = run(limit=ns.limit, targets=ns.targets)
    print(json.dumps({k: payload.get(k) for k in
                      ("ok", "reason", "trials", "hits", "hit_rate", "abstained",
                       "median_seconds", "decision")}, indent=2))
    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
