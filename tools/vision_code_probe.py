"""Probe: can Ty's Vision read code?

Answers one question with measurements instead of opinion: when a source file is
turned into a screenshot, can the local vision lane extract anything usable?

Three measurements, all local and free:

1. ``verdict``  -- ``agent_kernel.vision_verify.verify()`` on a code screenshot,
   with ground-truthed constraints. This is the shipped contract: image +
   constraint -> {pass, reasons, confidence}.
2. ``read``     -- the same model, free-form, asked to transcribe the code it
   sees and name the function it defines. This is NOT a shipped interface; it
   measures whether the pixels actually carry the code.
3. ``ocr``      -- RapidOCR (the text-fidelity gate) on the same pixels, for
   character-level fidelity with no model in the loop.

Usage:
    python tools/vision_code_probe.py
    python tools/vision_code_probe.py --lines 39 60 --json out.json
"""
from __future__ import annotations

import argparse
import base64
import difflib
import io
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel import vision_verify as vv  # noqa: E402

SAMPLE = ROOT / "Northstar_backend" / "agent_kernel" / "vision_verify.py"
FONT_CANDIDATES = [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\lucon.ttf"]


def render(lines, *, width=1280, font_size=15, pad=16) -> bytes:
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            font = ImageFont.truetype(path, font_size)
            break
    if font is None:  # pragma: no cover - only on a box without Consolas
        font = ImageFont.load_default()

    dummy = Image.new("RGB", (10, 10), "white")
    measure = ImageDraw.Draw(dummy)
    step = int(font_size * 1.45)
    height = pad * 2 + step * max(1, len(lines))
    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)
    for i, text in enumerate(lines):
        draw.text((pad, pad + i * step), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def read_freeform(image_bytes: bytes, question: str) -> str:
    """Same model + transport as vision_verify, no JSON constraint."""
    import urllib.request

    prepared = vv._prepare_image(image_bytes)  # noqa: SLF001 - probe only
    body = {
        "model": vv.MODEL,
        "messages": [{"role": "user", "content": question,
                      "images": [base64.b64encode(prepared).decode("ascii")]}],
        "stream": False,
        "keep_alive": "2m",
        "options": {"temperature": 0.0, "num_ctx": vv.NUM_CTX},
    }
    req = urllib.request.Request(vv.URL, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=vv.TIMEOUT_S) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return str((data.get("message") or {}).get("content") or "")


def ocr(image_bytes: bytes) -> str:
    try:
        import numpy as np
        from PIL import Image
        from rapidocr_onnxruntime import RapidOCR
    except Exception as exc:  # noqa: BLE001
        return f"UNAVAILABLE: {type(exc).__name__}: {exc}"
    with Image.open(io.BytesIO(image_bytes)) as im:
        arr = np.array(im.convert("RGB"))
    engine = RapidOCR()
    result, _ = engine(arr)
    if not result:
        return ""
    return "\n".join(str(row[1]) for row in result)


def ratio(a: str, b: str) -> float:
    return round(difflib.SequenceMatcher(None, a, b).ratio(), 3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default=str(SAMPLE))
    ap.add_argument("--lines", nargs=2, type=int, default=[39, 60])
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    path = Path(args.file)
    source = path.read_text(encoding="utf-8").splitlines()
    lo, hi = args.lines
    snippet = source[lo - 1:hi]
    text = "\n".join(snippet)
    print(f"[probe] {path.name} lines {lo}-{hi} ({len(snippet)} lines, "
          f"{len(text)} chars)")
    print(f"[probe] model={vv.MODEL} url={vv.URL} max_edge={vv.MAX_EDGE}")

    image = render(snippet)
    render_path = ROOT / "state" / "evidence" / "vision_code_probe" / "code.png"
    render_path.parent.mkdir(parents=True, exist_ok=True)
    render_path.write_bytes(image)
    print(f"[probe] rendered {len(image)} bytes -> {render_path.relative_to(ROOT)}")

    cases = [
        ("the code defines a function named _parse", True),
        ("the code imports the subprocess module", False),
        ("the code removes a markdown code fence with a regular expression", True),
        ("the code contains a return statement that yields a dictionary", True),
        ("the code writes a file to disk", False),
    ]
    rows = []
    for constraint, expected in cases:
        t0 = time.time()
        out = vv.verify(image, constraint)
        secs = round(time.time() - t0, 1)
        rows.append({"constraint": constraint, "expected": expected,
                     "pass": out.get("pass"), "available": out.get("available"),
                     "correct": (out.get("pass") is expected) if out.get("available") else None,
                     "reasons": out.get("reasons"), "seconds": secs})
        print(f"  verdict {secs:>5}s expected={expected!s:<5} "
              f"got={out.get('pass')!s:<5} {constraint[:60]}")

    t0 = time.time()
    try:
        answer = read_freeform(
            image,
            "Transcribe the code in this image exactly, line by line. Do not "
            "explain. Then, on a final line starting with NAME=, give the name "
            "of the function it defines.")
        read_error = ""
    except Exception as exc:  # noqa: BLE001
        answer, read_error = "", f"{type(exc).__name__}: {exc}"
    read_secs = round(time.time() - t0, 1)

    t0 = time.time()
    ocr_text = ocr(image)
    ocr_secs = round(time.time() - t0, 1)

    payload = {
        "file": str(path.relative_to(ROOT)),
        "lines": [lo, hi],
        "model": vv.MODEL,
        "verdicts": rows,
        "verdict_accuracy": round(
            sum(1 for r in rows if r["correct"]) / max(1, len(rows)), 3),
        "freeform": {"answer": answer, "error": read_error,
                     "char_ratio_vs_source": ratio(answer, text) if answer else None,
                     "seconds": read_secs},
        "ocr": {"text": ocr_text,
                "char_ratio_vs_source": ratio(ocr_text, text) if not ocr_text.startswith("UNAVAILABLE") else None,
                "seconds": ocr_secs},
        "source_chars": len(text),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    print(f"[probe] verdict accuracy {payload['verdict_accuracy']}")
    print(f"[probe] free-form {read_secs}s ratio={payload['freeform']['char_ratio_vs_source']}")
    print(f"[probe] ocr        {ocr_secs}s ratio={payload['ocr']['char_ratio_vs_source']}")
    print("---- free-form answer ----")
    print(answer or read_error)
    print("---- ocr text ----")
    print(ocr_text)
    print("---- source ----")
    print(text)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[probe] wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
