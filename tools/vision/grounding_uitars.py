"""UI-TARS on the 40-screen grounding set, measured the same way as the baseline.

The baseline is qwen2.5vl at **61.7 %** hit rate on this set (21.7 % abstentions, 78.7 % when it
answers). The owner's bar: adopt a pixel-grounding model only if it beats that by **10 points**;
otherwise UIA and DOM stay primary.

UI-TARS is a GUI-agent model, so it answers in its own action dialect as well as plain JSON. Both
are parsed; anything else is an abstention, which is a miss, never a pass.

This runs on the **ComfyUI venv** interpreter (CUDA torch), not the repo one (CPU-only):

    & "$env:USERPROFILE\\ComfyUI\\venv\\Scripts\\python.exe" -m tools.vision.grounding_uitars --run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

from vision import grounding  # noqa: E402

MODEL = "ByteDance-Seed/UI-TARS-2B-SFT"
OUT = ROOT / "reports" / "ty" / "d8_grounding_uitars.json"
SET = ROOT / "state" / "vision" / "grounding_set"
BAR = grounding.BAR            # 0.60, the same bar the baseline had to clear
ADOPT_MARGIN = 0.10            # the owner's margin over 61.7 %
BASELINE = 0.617

PROMPT = (
    "You are a GUI grounding model. In the screenshot, locate the element labelled {label!r}. "
    "Answer with the centre point as JSON: {{\"x\": <0-1000>, \"y\": <0-1000>}}. "
    "If it is not visible, answer {{\"x\": 0, \"y\": 0}}."
)

_ACTION = re.compile(r"start_box\s*=\s*'?\(?\s*([0-9.]+)\s*,\s*([0-9.]+)", re.I)
_JSON = re.compile(r"\{[^{}]*\}")


def parse(text: str) -> Optional[Dict[str, float]]:
    """A point in 0..1 from JSON or UI-TARS's own `click(start_box='(x,y)')` dialect."""
    raw = str(text or "")
    for match in _JSON.finditer(raw):
        try:
            payload = json.loads(match.group(0))
            x, y = float(payload["x"]), float(payload["y"])
        except (ValueError, KeyError, TypeError):
            continue
        if x == 0 and y == 0:
            return None
        return {"x": x / 1000.0 if x > 1 else x, "y": y / 1000.0 if y > 1 else y}
    match = _ACTION.search(raw)
    if match:
        x, y = float(match.group(1)), float(match.group(2))
        return {"x": x / 1000.0 if x > 1 else x, "y": y / 1000.0 if y > 1 else y}
    return None


def load(model: str = MODEL):
    import torch
    from transformers import AutoProcessor, Qwen2VLForConditionalGeneration

    processor = AutoProcessor.from_pretrained(model)
    net = Qwen2VLForConditionalGeneration.from_pretrained(
        model, torch_dtype=torch.float16, device_map="cuda", low_cpu_mem_usage=True)
    net.eval()
    return net, processor


def ask(net, processor, png: bytes, label: str) -> str:
    import io

    import torch
    from PIL import Image

    with Image.open(io.BytesIO(png)) as opened:
        image = opened.convert("RGB")
    messages = [{"role": "user", "content": [
        {"type": "image"}, {"type": "text", "text": PROMPT.format(label=label)}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(text=[prompt], images=[image], return_tensors="pt").to("cuda")
    with torch.inference_mode():
        out = net.generate(**inputs, max_new_tokens=64, do_sample=False)
    trimmed = [row[len(inp):] for row, inp in zip(out, inputs["input_ids"])]
    return processor.batch_decode(trimmed, skip_special_tokens=True)[0]


def run(limit: int = 0, targets: int = 3) -> Dict[str, Any]:
    manifest = json.loads((SET / "manifest.json").read_text(encoding="utf-8"))
    screens = manifest[:limit] if limit else manifest
    net, processor = load()
    trials = hits = abstained = 0
    latency: List[float] = []
    failures: List[Dict[str, Any]] = []
    for row in screens:
        png = (SET / row["file"]).read_bytes()
        for target in row["targets"][:targets]:
            started = time.time()
            try:
                raw = ask(net, processor, png, target["name"])
            except Exception as exc:  # noqa: BLE001
                raw = ""
                failures.append({"file": row["file"], "target": target["name"],
                                 "error": f"{type(exc).__name__}: {exc}"})
            latency.append(time.time() - started)
            point = parse(raw)
            trials += 1
            if point is None:
                abstained += 1
            elif grounding.hit(target["box"], point):
                hits += 1
            else:
                failures.append({"file": row["file"], "target": target["name"],
                                 "raw": str(raw)[:140], "point": point})
    rate = hits / trials if trials else 0.0
    answered = trials - abstained
    payload = {
        "model": MODEL,
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "screens": len(screens), "targets_per_screen": targets,
        "trials": trials, "hits": hits, "hit_rate": round(rate, 3),
        "abstained": abstained,
        "hit_rate_when_answered": round(hits / answered, 3) if answered else 0.0,
        "median_seconds": round(sorted(latency)[len(latency) // 2], 2) if latency else None,
        "baseline": BASELINE, "bar": BAR, "adopt_margin": ADOPT_MARGIN,
        "passed_bar": rate >= BAR,
        "beats_baseline_by_margin": rate >= BASELINE + ADOPT_MARGIN,
        "decision": ("adopt UI-TARS: it clears the baseline by the required margin"
                     if rate >= BASELINE + ADOPT_MARGIN else
                     "keep UIA and DOM primary: UI-TARS does not clear the bar by 10 points"),
        "failures": failures[:12],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="UI-TARS grounding benchmark")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--targets", type=int, default=3)
    parser.add_argument("--probe", action="store_true", help="load the model and answer one call")
    ns = parser.parse_args(argv)
    if ns.probe:
        net, processor = load()
        png = (SET / "01_browser.png").read_bytes()
        print(json.dumps({"answer": ask(net, processor, png, "Search")}, indent=2))
        return 0
    payload = run(limit=ns.limit, targets=ns.targets)
    print(json.dumps({k: payload[k] for k in ("model", "trials", "hits", "hit_rate",
                                              "abstained", "median_seconds", "decision")},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
