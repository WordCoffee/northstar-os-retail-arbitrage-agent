"""Test run: the FULL MOGRA pouch packaging brief through the studio's own
text-safe generation lane (klein 9B-KV default) -> clean base plate + OCR check.

The pipeline's entire point: the brief goes in VERBATIM; text_fidelity strips
every typographic demand before the model sees it (brand names, weights,
barcode/QR asks, ALL-CAPS runs) and appends the blank-surface suppression
phrase; the render is OCR-verified letter-free. Real type is composited later
by scripts/compose_mogra_canister_line.py.

Output: renders/mogra-canister-line-base.png (+ .json sidecar with the verdict)
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
os.environ.setdefault("MEDIA_GEN_LIVE", "1")
os.environ.setdefault("COMFYUI_URL", "http://127.0.0.1:8199")
# defaults now = Flux-2-Klein-9B-KV-Q8_0.gguf + qwen_3_8b_fp8mixed (engine)

BRIEF = """# MOGRA ORGANICS - POUCH PACKAGING DESIGN BRIEF
## OBJECTIVE
Design 1:1-scale, print-ready packaging artwork for two Mogra Organics mushroom powder
stand-up zipper pouches. Mat manufacturing artwork, not concept mood boards.
## BAG SPECIFICATIONS
- Bag type: matte stand-up pouch (doypack) with resealable zipper and bottom gusset
- SKU 1: 130mm W x 210mm H + 40mm gusset. SKU 2: 150mm W x 210mm H + 40mm gusset.
- Front printed usable zone: pouch width from about 25mm below the zipper line to the gusset fold
- Finish: full-coverage matte print. No windows.
## BRAND ASSETS
- Design language carries over from the approved canister concepts "Botanical Modern".
- Palette: black #171717, kraft #D5A77A, olive #9DBA8B, ivory #F5EEE2, sage #9FA9A4,
  forest green #253628, cream #D0C5AC
- Typography: high-contrast serif for the wordmark and product names, clean sans serif
  for information text
- Illustration: engraved line-art botanical mushroom illustration (lion's mane mushroom
  form for the left pouch, shiitake mushroom cluster for the right pouch), drawn in the
  style of the canister art - no cartoon characters, no stock mushroom photographs
- Ornaments: thin botanical sprigs and laurel accents, minimal divider rules
## FRONT PANEL LAYOUT (each pouch)
1. Logo lockup centered top third
2. Product name large, subline beneath
3. Botanical mushroom line illustration, single-color print
4. Icon row near bottom
5. Bottom weight line and footer text
## BACK PANEL LAYOUT
1. Short product description block
2. RESERVED ZONE - Supplement Facts panel with black rules on a white block
3. RESERVED ZONE - QR code and UPC barcode
4. Suggested use, storage note, country of origin line, distributed-by line
5. Zipper icon and reseal note
## SKU DIFFERENTIATION
Both pouches share one master layout. Differentiate by:
- Background colorway: the left pouch is in the kraft and olive family (kraft #D5A77A
  matte pouch with olive accents), the right pouch is ivory with forest green accents
  (ivory #F5EEE2 matte pouch, forest green #253628 accents) - both must sit side by side
  cohesively on a shelf
- Mushroom illustration species
- Product name and weight only; no other layout changes
## DESIGN BAR
Premium organic apothecary feel: calm, botanical, confident. No gradients, no photo
realism of powder piles, no generic wellness stock iconography.
## SCENE
Both pouches standing side by side on a warm oak surface against a softly blurred
botanical greenhouse backdrop, late-afternoon light, product photography lighting,
both pouches fully in frame, sharp focus."""


def main() -> int:
    import studio_generation as sg
    from text_fidelity import render_with_text_guard

    st = sg.engine_status()
    if not st.get("armed"):
        print(json.dumps({"ok": False, "error": "engine_not_armed", "engine": st}))
        return 2

    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 4242

    def _render(prompt: str):
        return sg.generate_image(prompt=prompt, width=1216, height=832,
                                 tier="final", seed=seed)

    t0 = time.time()
    guarded = render_with_text_guard(render_fn=_render, brief=BRIEF, text_safe=True)
    out = guarded["out"]
    tf = guarded.get("text_fidelity") or {}

    png = ROOT / "renders" / "mogra-canister-line-base.png"
    png.write_bytes(out["bytes"])
    (ROOT / "renders" / "mogra-canister-line-base.json").write_text(json.dumps({
        "file": png.name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "model": out.get("model"), "provider": out.get("provider"),
        "seed": out.get("seed"), "width": out.get("width"), "height": out.get("height"),
        "seconds": round(time.time() - t0, 1),
        "text_safe": True,
        "verdict": tf.get("verdict"),
        "ocr": tf.get("check"),
        "attempts": tf.get("attempts"),
        "retried": tf.get("retried"),
        "suppressed_count": tf.get("suppressed_count"),
        "kept_count": tf.get("kept_count"),
    }, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "png": str(png), "verdict": tf.get("verdict"),
                      "seconds": round(time.time() - t0, 1)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
