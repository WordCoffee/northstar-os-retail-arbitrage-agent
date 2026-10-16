"""One-off: MOGRA "Forest Dusk" pouch mockup through the studio's own
text-safe lane — the same code path as POST /api/design-studio/generate:

  text_fidelity.render_with_text_guard(render_fn=sg.generate_image, brief, text_safe=True)

Renders on the operator's local ComfyUI (FLUX.2 klein 4B, :8199), OCR-verifies
lettering is absent, and writes the PNG + a scrub-sidecar JSON to renders/.
No secrets are read; no paid provider is touched.
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

OUT_PNG = ROOT / "renders" / "mogra-forest-dusk-mockup.png"
OUT_SIDE = ROOT / "renders" / "mogra-forest-dusk-mockup.json"

BRIEF = """Product mockup, photorealistic, product photography lighting.
Two cosmetic-grade matte stand-up zipper pouches (doypack, bottom gusset,
resealable zip) standing side by side on a warm oak surface against a softly
blurred botanical-greenhouse backdrop, late-afternoon light.
Bag 1 (left): deep forest green matte pouch, 130x210mm proportions.
Bag 2 (right): identical layout and proportions, slightly wider (150x210mm),
in warm charcoal-black matte instead of green.
Style rules: premium natural-foods apothecary feel; matte uncoated print
finish with soft specular highlights along pouch edges and gusset crease;
no gradients on the pouch faces; no plastic sheen; no cartoon characters;
no piles of loose powder; no hands, no people; restrained, confident, lots of
typography breathing room. Both pouches fully in frame, sharp focus, 4K detail.
Engraved-style botanical line illustrations in muted gold: a lion's mane
mushroom on the left pouch, a shiitake cluster on the right; a cream circular
badge emblem with a mortar-and-pestle icon and two small green leaves on each
pouch's upper third; a row of four tiny circular cream icons low on each face.
Palette: deep forest green #2e4632, warm charcoal #23201d, warm cream #f3ead6,
muted gold #b99a5c, warmer gold #cfa055."""


def main() -> int:
    import studio_generation as sg
    from text_fidelity import render_with_text_guard

    st = sg.engine_status()
    if not st.get("armed"):
        print(json.dumps({"ok": False, "error": "engine_not_armed", "engine": st}))
        return 2

    def _render(prompt: str):
        return sg.generate_image(prompt=prompt, width=1216, height=832,
                                 tier="final", seed=20261016)

    t0 = time.time()
    guarded = render_with_text_guard(render_fn=_render, brief=BRIEF, text_safe=True)
    out = guarded["out"]
    tf = guarded.get("text_fidelity") or {}

    OUT_PNG.parent.mkdir(parents=True, exist_ok=True)
    OUT_PNG.write_bytes(out["bytes"])
    OUT_SIDE.write_text(json.dumps({
        "file": OUT_PNG.name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "provider": out.get("provider"),
        "model": out.get("model"),
        "seed": out.get("seed"),
        "width": out.get("width"),
        "height": out.get("height"),
        "seconds": round(time.time() - t0, 1),
        "text_safe": True,
        "verdict": tf.get("verdict"),
        "matched_terms": tf.get("matched_terms"),
        "ocr": tf.get("check"),
        "attempts": tf.get("attempts"),
        "retried": tf.get("retried"),
        "suppressed_count": tf.get("suppressed_count"),
        "kept_count": tf.get("kept_count"),
        "expected_terms": tf.get("expected_terms"),
    }, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "png": str(OUT_PNG), "verdict": tf.get("verdict")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
