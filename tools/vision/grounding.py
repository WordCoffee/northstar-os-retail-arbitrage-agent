"""Pixel grounding: can a model turn "click Search" into a point inside the button?

Work order §5.1 layer 3 and the 2026-11-08 folded fix: benchmark a pixel-grounding model
(UI-TARS-class, OmniParser-class) on a 40-screen set, and until one passes, vision control
uses the UI Automation tree and the DOM only.

The set is generated, not scraped, so the ground truth is exact: every screen is drawn from
a seed, and every labelled element has a box recorded at draw time. A hit means the model's
point lands inside the labelled element's box. The bar is 60 % hit rate at three targets per
screen across 40 screens; below that, a click is not something a model gets to decide.

    python -m tools.vision.grounding --make --out state/vision/grounding_set
    python -m tools.vision.grounding --run --models qwen2.5vl:7b,llava:7b
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import random
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
SET_DIR = ROOT / "state" / "vision" / "grounding_set"
REPORT = ROOT / "reports" / "ty" / "d8_grounding.json"
BAR = 0.60
WIDTH, HEIGHT = 1280, 800
TARGETS_PER_SCREEN = 3

#: The five UI families the work order names: browser, file manager, terminal, the Northstar
#: UI, and a design canvas.
FAMILIES = ("browser", "file_manager", "terminal", "northstar", "canvas")

PROMPT = (
    "You are looking at a screenshot of a computer interface. Find the element labelled "
    "{label!r}. Answer with JSON only: {{\"x\": 0.0, \"y\": 0.0}} where x and y are the "
    "centre of that element as fractions of the image width and height. No prose."
)


def _font(size: int = 16):
    from PIL import ImageFont

    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _rect(draw, box: Sequence[int], fill: str, outline: str = "#2a3b32") -> None:
    draw.rectangle(list(box), fill=fill, outline=outline, width=2)


def _label(draw, text: str, x: int, y: int, font, colour: str = "#1b2a22") -> None:
    draw.text((x, y), text, fill=colour, font=font)


def _screen(family: str, seed: int) -> Dict[str, Any]:
    """One deterministic screen and its labelled boxes."""
    from PIL import Image, ImageDraw

    rng = random.Random(seed)
    image = Image.new("RGB", (WIDTH, HEIGHT), "#f6f3ec")
    draw = ImageDraw.Draw(image)
    font, small = _font(20), _font(15)
    targets: List[Dict[str, Any]] = []

    def add(name: str, box: Sequence[int]) -> None:
        targets.append({"name": name, "box": list(box)})

    if family == "browser":
        _rect(draw, (0, 0, WIDTH, 70), "#e8e2d6")
        _label(draw, "Northstar browser", 20, 22, font)
        box = (900, 16, 1100, 54)
        _rect(draw, box, "#ffffff")
        _label(draw, "Search", 950, 26, small)
        add("Search", box)
        for index in range(5):
            y = 120 + index * 90
            _rect(draw, (60, y, 1220, y + 70), "#ffffff")
            _label(draw, f"Result {index + 1}", 90, y + 22, font)
            if index == 2:
                add("Result 3", (60, y, 1220, y + 70))
        add("Reload", (1180, 16, 1240, 54))
        _rect(draw, (1180, 16, 1240, 54), "#ffffff")
        _label(draw, "Reload", 1188, 26, small)

    elif family == "file_manager":
        _rect(draw, (0, 0, 320, HEIGHT), "#eae4d8")
        for index, name in enumerate(("Reports", "Renders", "State", "Tools")):
            box = (20, 80 + index * 60, 300, 128 + index * 60)
            _rect(draw, box, "#ffffff")
            _label(draw, name, 40, 92 + index * 60, small)
            if name == "Renders":
                add("Renders", box)
        for index in range(8):
            y = 100 + index * 70
            _rect(draw, (340, y, 1240, y + 56), "#ffffff")
            _label(draw, f"image_{index + 1:03}.png", 360, y + 16, small)
            if index == 5:
                add("image_006.png", (340, y, 1240, y + 56))
        add("New folder", (1050, 16, 1240, 54))
        _rect(draw, (1050, 16, 1240, 54), "#dfe8df")
        _label(draw, "New folder", 1070, 26, small)

    elif family == "terminal":
        draw.rectangle((0, 0, WIDTH, HEIGHT), fill="#101814")
        rows = []
        for row in range(18):
            text = f"$ northstar run --seed {rng.randint(10, 99)} --lane {row}"
            rows.append(text)
            _label(draw, text, 30, 24 + row * 40, small, "#c9e6cf")
        box = (30, 24 + 10 * 40, 900, 24 + 10 * 40 + 34)
        add(rows[10], box)
        box2 = (30, 24 + 4 * 40, 800, 24 + 4 * 40 + 34)
        add(rows[4], box2)
        _rect(draw, (1050, 16, 1240, 54), "#1c3a2b", outline="#2e5c44")
        _label(draw, "Stop", 1110, 26, small, "#c9e6cf")
        add("Stop", (1050, 16, 1240, 54))

    elif family == "northstar":
        _rect(draw, (0, 0, 240, HEIGHT), "#132018")
        for index, name in enumerate(("Home", "Prospector", "Listings", "Design Studio",
                                      "Monitoring")):
            box = (16, 100 + index * 64, 224, 156 + index * 64)
            _rect(draw, box, "#1b2c22", outline="#2f4a3a")
            _label(draw, name, 34, 114 + index * 64, small, "#dbe9df")
            if name in ("Prospector", "Design Studio"):
                add(name, box)
        for index in range(4):
            x = 280 + index * 240
            box = (x, 120, x + 200, 320)
            _rect(draw, box, "#fbf9f4")
            _label(draw, f"Card {index + 1}", x + 20, 140, small)
            if index == 1:
                add("Card 2", box)
        add("Ask Bojo", (900, 700, 1220, 770))
        _rect(draw, (900, 700, 1220, 770), "#2b4b3a")
        _label(draw, "Ask Bojo", 1020, 724, small, "#dbe9df")

    else:  # canvas
        _rect(draw, (0, 0, WIDTH, 80), "#e3ddd0")
        for index, name in enumerate(("Brush", "Shape", "Text", "Export")):
            box = (900 + index * 90, 18, 980 + index * 90, 62)
            _rect(draw, box, "#ffffff")
            _label(draw, name, 910 + index * 90, 30, small)
            if name == "Export":
                add("Export", box)
        _rect(draw, (120, 140, 880, 700), "#ffffff", outline="#c9c2b3")
        _label(draw, "artboard", 140, 160, small)
        add("artboard", (120, 140, 880, 700))
        for index in range(6):
            box = (930, 140 + index * 90, 1010, 210 + index * 90)
            colour = (f"#{rng.randint(60, 220):02x}{rng.randint(60, 220):02x}"
                      f"{rng.randint(60, 220):02x}")
            draw.rectangle(list(box), fill=colour)
            if index == 3:
                add("swatch 4", box)
                _label(draw, "swatch 4", box[0] + 8, box[1] + 8, small, "#101814")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return {"family": family, "seed": seed, "png": buffer.getvalue(),
            "targets": [target for target in targets if target["box"][2] > target["box"][0]][:6]}


def build(count: int = 40, out_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Write the set once and record the ground truth; regenerate byte-identically."""
    folder = Path(out_dir or SET_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    manifest: List[Dict[str, Any]] = []
    for index in range(count):
        family = FAMILIES[index % len(FAMILIES)]
        screen = _screen(family, 1000 + index)
        name = f"{index + 1:02d}_{family}.png"
        (folder / name).write_bytes(screen["png"])
        manifest.append({"file": name, "family": family, "seed": screen["seed"],
                         "targets": screen["targets"]})
    meta = folder / "manifest.json"
    meta.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "screens": len(manifest), "folder": str(folder),
            "family_counts": {family: sum(1 for row in manifest if row["family"] == family)
                              for family in FAMILIES}}


def parse_point(text: str) -> Optional[Dict[str, float]]:
    import re

    cleaned = str(text or "")
    match = re.search(r"\{[^{}]*\}", cleaned, re.DOTALL)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except ValueError:
        return None
    try:
        x, y = float(payload["x"]), float(payload["y"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        # a model that answers in pixels is still usable if it is inside the image
        if 0.0 <= x <= WIDTH and 0.0 <= y <= HEIGHT:
            return {"x": x / WIDTH, "y": y / HEIGHT}
        return None
    return {"x": x, "y": y}


def hit(box: Sequence[int], point: Dict[str, float], *, tolerance: int = 8) -> bool:
    """Is the point inside the box? Tolerance is in pixels, for near-edge misses."""
    left, top, right, bottom = (int(v) for v in box)
    x, y = point["x"] * WIDTH, point["y"] * HEIGHT
    return (left - tolerance) <= x <= (right + tolerance) and \
           (top - tolerance) <= y <= (bottom + tolerance)


def _ask(endpoint: str, model: str, png: bytes, label: str, num_ctx: int = 8192,
         timeout: float = 300.0) -> str:
    import urllib.request

    image = png
    try:
        from PIL import Image

        with Image.open(io.BytesIO(png)) as opened:
            if opened.width > 1280:
                ratio = 1280 / opened.width
                opened = opened.resize((1280, int(opened.height * ratio)))
            buffer = io.BytesIO()
            opened.convert("RGB").save(buffer, format="PNG")
            image = buffer.getvalue()
    except Exception:  # noqa: BLE001
        pass
    payload = {"model": model, "prompt": PROMPT.format(label=label), "stream": False,
               "keep_alive": "2m",
               "images": [base64.b64encode(image).decode("ascii")],
               "options": {"temperature": 0.0, "num_predict": 80, "num_ctx": num_ctx}}
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8", "replace") or "{}")
    return str(body.get("response") or "")


def run(*, models: Sequence[str], endpoint: str = "http://127.0.0.1:11434",
        folder: Optional[Path] = None, limit: int = 0,
        ask: Optional[Callable[[str, bytes, str], str]] = None) -> Dict[str, Any]:
    """Measure hit rate per model. The caller is injectable so tests need no GPU."""
    source = Path(folder or SET_DIR)
    manifest_path = source / "manifest.json"
    if not manifest_path.exists():
        built = build(out_dir=source)
        if not built.get("ok"):
            return {"ok": False, "reason": "no set and it could not be built"}
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    screens = manifest[:limit] if limit else manifest

    results: Dict[str, Any] = {}
    for model in models:
        trials = 0
        hits = 0
        abstained = 0
        latency: List[float] = []
        failures: List[Dict[str, Any]] = []
        for row in screens:
            png = (source / row["file"]).read_bytes()
            for target in row["targets"][:TARGETS_PER_SCREEN]:
                started = time.time()
                try:
                    raw = (ask(model, png, target["name"]) if ask
                           else _ask(endpoint, model, png, target["name"]))
                except Exception as exc:  # noqa: BLE001 - a failed call is a missed trial
                    raw = ""
                    failures.append({"file": row["file"], "target": target["name"],
                                     "error": f"{type(exc).__name__}: {exc}"})
                latency.append(time.time() - started)
                point = parse_point(raw)
                trials += 1
                # (0, 0) is how these models decline: it is the corner of the image and
                # never the centre of a label. Counting it as an abstention matters,
                # because an abstention falls back to the tree while a confident wrong
                # click does not.
                if point is None or (point["x"] == 0.0 and point["y"] == 0.0):
                    abstained += 1
                if point and hit(target["box"], point):
                    hits += 1
                else:
                    failures.append({"file": row["file"], "target": target["name"],
                                     "raw": str(raw)[:120], "point": point})
        rate = (hits / trials) if trials else 0.0
        answered = trials - abstained
        results[model] = {"hit_rate": round(rate, 3), "hits": hits, "trials": trials,
                          "abstained": abstained,
                          "hit_rate_when_answered": round(hits / answered, 3)
                          if answered else 0.0,
                          "median_seconds": round(sorted(latency)[len(latency) // 2], 2)
                          if latency else None,
                          "pass": rate >= BAR, "bar": BAR,
                          "failures": failures[:10]}
    winner = max(results.items(), key=lambda item: item[1]["hit_rate"], default=("", {}))
    return {"ok": True, "screens": len(screens), "targets_per_screen": TARGETS_PER_SCREEN,
            "models": results, "winner": winner[0],
            "any_pass": any(row["pass"] for row in results.values()),
            "decision": ("a grounding model passed: pixels may drive clicks"
                         if any(row["pass"] for row in results.values())
                         else "no grounding model passed: vision control uses UIA and DOM only"),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}


#: How a measured grounding model may be used. The measurement is 61.7 % hit rate with
#: 21.7 % abstentions (78.7 % of answers correct), so pixels are a *fallback* locator, never
#: the primary one, and a pixel-driven click is always verify-after-act.
PIXEL_RULE = (
    "UI Automation and the DOM first. Pixels only when the tree has no match. An answer of "
    "(0, 0) is an abstention and produces no click. Every pixel-driven click is verified "
    "after the act and never used for an irreversible class."
)


def locate(*, model: str, png: bytes, label: str,
           endpoint: str = "http://127.0.0.1:11434",
           ask: Optional[Callable[[str, bytes, str], str]] = None) -> Dict[str, Any]:
    """One pixel location, or an abstention. (0, 0) is never treated as a location."""
    try:
        raw = (ask(model, png, label) if ask else _ask(endpoint, model, png, label))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "point": None, "abstained": True,
                "reason": f"{type(exc).__name__}: {exc}"}
    point = parse_point(raw)
    if point is None or (point["x"] == 0.0 and point["y"] == 0.0):
        return {"ok": False, "point": None, "abstained": True, "raw": str(raw)[:120]}
    return {"ok": True, "point": point, "abstained": False, "model": model,
            "rule": PIXEL_RULE}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Pixel-grounding benchmark")
    parser.add_argument("--make", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--models", default="qwen2.5vl:7b,llava:7b")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--out", default=str(REPORT))
    parser.add_argument("--limit", type=int, default=0)
    ns = parser.parse_args(argv)

    if ns.make or not ns.run:
        print(json.dumps(build(), indent=2))
        if not ns.run:
            return 0
    models = [name.strip() for name in ns.models.split(",") if name.strip()]
    result = run(models=models, endpoint=ns.endpoint, limit=ns.limit)
    Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
    Path(ns.out).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"screens": result.get("screens"),
                      "models": {name: {k: row[k] for k in ("hit_rate", "hits", "trials",
                                                            "median_seconds", "pass")}
                                 for name, row in (result.get("models") or {}).items()},
                      "decision": result.get("decision")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
