"""Six prompt-only outputs, next to the brief that asked for them.

A prompt-only brief has no source image, so the usual "source next to output" pairing is impossible.
What the reviewer needs instead is the **brief** next to the output: what was asked for, and what came
back. The brief is rendered as a text card at the same size as the picture so the two can be read
side by side.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
BRIEFS = ROOT / "ty" / "seller_briefs_heldout_modes.json"
PROOF = ROOT / "state" / "seller" / "heldout_prompt_only_proof4.json"
OUT = ROOT / "reports" / "ty" / "prompt_only_source_next_to_output.png"


def rows() -> List[dict]:
    payload = json.loads(BRIEFS.read_text(encoding="utf-8")) if BRIEFS.exists() else {"briefs": []}
    proof = json.loads(PROOF.read_text(encoding="utf-8")) if PROOF.exists() else {"results": []}
    briefs = {row["id"]: row for row in payload.get("briefs") or []
              if row.get("source_mode") == "prompt_only"}
    out = []
    for result in proof.get("results") or []:
        brief = briefs.get(str(result.get("brief_id")))
        if not brief:
            continue
        artefact = str(result.get("artefact_path") or "")
        out.append({"brief": brief, "result": result, "artefact": artefact,
                    "ok": bool(artefact) and (ROOT / artefact).is_file()})
    return out


def _card(text: str, size: int):
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

    card = Image.new("RGB", (size, size), (250, 248, 243))
    draw = ImageDraw.Draw(card)
    try:
        title = ImageFont.truetype("georgiab.ttf", max(20, size // 24))
        body = ImageFont.truetype("segoeui.ttf", max(16, size // 34))
        small = ImageFont.truetype("segoeui.ttf", max(13, size // 46))
    except OSError:
        title = body = small = ImageFont.load_default()
    y = int(size * 0.05)
    draw.text((int(size * 0.05), y), "THE BRIEF", font=title, fill=(26, 42, 34))
    y += int(size * 0.06)
    draw.line((int(size * 0.05), y, int(size * 0.95), y), fill=(196, 204, 197), width=2)
    y += int(size * 0.03)
    words = str(text).split()
    line = ""
    for word in words:
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=body) <= size * 0.88:
            line = trial
        else:
            draw.text((int(size * 0.05), y), line, font=body, fill=(26, 42, 34))
            y += int(size * 0.042)
            line = word
            if y > size * 0.86:
                break
    if line and y <= size * 0.86:
        draw.text((int(size * 0.05), y), line, font=body, fill=(26, 42, 34))
    draw.text((int(size * 0.05), int(size * 0.93)), "no reference image: generated from this text",
              font=small, fill=(90, 104, 96))
    return card


def sheet(target: Optional[Path] = None, *, limit: int = 6, tile: int = 560) -> Optional[Path]:
    from PIL import Image, ImageDraw, ImageFont  # noqa: PLC0415

    picked = [row for row in rows() if row["ok"]][:limit]
    if not picked:
        return None
    try:
        caption_font = ImageFont.truetype("segoeui.ttf", 15)
        head = ImageFont.truetype("georgiab.ttf", 18)
    except OSError:
        caption_font = head = ImageFont.load_default()
    header = 34
    canvas = Image.new("RGB", (tile * 2 + 24, (tile + header + 26) * len(picked)), (246, 243, 236))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 6), "brief (text only)", fill=(27, 42, 34), font=head)
    draw.text((tile + 20, 6), "output", fill=(27, 42, 34), font=head)
    for index, row in enumerate(picked):
        top = header + index * (tile + header + 26)
        card = _card(str(row["brief"].get("prompt") or ""), tile - 10)
        canvas.paste(card, (8, top + 4))
        with Image.open(ROOT / row["artefact"]) as image:
            thumb = image.convert("RGB")
            thumb.thumbnail((tile - 10, tile - 10))
        canvas.paste(thumb, (tile + 12, top + 4))
        result = row["result"]
        caption = (f"{row['brief']['id']}  {row['brief'].get('situation')}  "
                   f"score {result.get('score')}  {'pass' if result.get('passed') else 'fail'}")
        draw.text((8, top + tile - 8), caption, fill=(27, 42, 34), font=caption_font)
    destination = Path(target or OUT)
    canvas.save(destination)
    return destination


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Prompt-only: brief next to output")
    parser.add_argument("--out", type=Path, default=None)
    ns = parser.parse_args(argv)
    path = sheet(ns.out)
    print(json.dumps({"sheet": str(path) if path else None,
                      "rows": len([r for r in rows() if r["ok"]])}, indent=2))
    return 0 if path else 1


if __name__ == "__main__":
    raise SystemExit(main())
