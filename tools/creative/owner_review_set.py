"""Produce one compact owner-review set (5 artifacts) + a review sheet.

Runs complete jobs through the shared pipeline and copies the outputs into
generated_images/creative/review_set/ with review-friendly names.
"""
from __future__ import annotations

import json
import shutil
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REVIEW = REPO / "generated_images" / "creative" / "review_set"
SHEET = REPO / "reports" / "creative_owner_review"
REVIEW.mkdir(parents=True, exist_ok=True)
SHEET.mkdir(parents=True, exist_ok=True)
BASE = "http://127.0.0.1:8000"
SRC = str(REPO / "generated_images" / "mogra_mockups" / "live_scene_turmeric.png")


def _req(path, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.loads(resp.read())


def run(task, payload, timeout=1800):
    jid = _req("/api/creative/pipeline", "POST", {"task": task, "payload": payload})["job_id"]
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(2)
        j = _req(f"/api/creative/jobs/{jid}")
        if j["status"] in ("done", "error", "cancelled"):
            j["elapsed_s"] = round(time.time() - t0, 2)
            return j
    return {"status": "timeout"}


def keep(src, name):
    if src and Path(src).exists():
        dst = REVIEW / name
        shutil.copyfile(src, dst)
        return str(dst)
    return None


def main():
    presets = _req("/api/creative/presets")
    spec = {"brand": "Mogra Organics", "tagline": "Fuel Your Focus.",
            "product_name": "Organic Turmeric Powder",
            "descriptor": "Ground · 100% Pure", "net_weight": "5 lb (80 oz)"}
    made = {}

    # 1) faithful product-photo ad
    j = run("product_ad", {"source": SRC, "cutout": True,
                           "compose": {"spec": spec,
                                       "surface": presets["surfaces"]["front_label_panel"]}})
    made["1_faithful_product_ad.png"] = keep(j.get("output"), "1_faithful_product_ad.png")

    # 2) packaging concept with exact text
    j = run("packaging_concept", {"prompt": "premium glass jar of turmeric powder on a neutral "
                                            "studio background, blank label panel, no text",
                                  "mode": "draft", "seed": 21,
                                  "compose": {"spec": spec,
                                              "surface": presets["surfaces"]["front_label_panel"]}})
    made["2_packaging_concept_exact_text.png"] = keep(
        (j.get("result") or {}).get("composited"), "2_packaging_concept_exact_text.png")

    # 3) finished branded ad layout
    j = run("ad_layout", {"product": SRC, "spec": spec, "export": [1080, 1080]})
    made["3_finished_branded_ad.png"] = keep(j.get("output"), "3_finished_branded_ad.png")

    # 4) masked edit before/after
    from PIL import Image, ImageDraw
    with Image.open(SRC) as im:
        w, h = im.size
    mask = REPO / "generated_images" / "creative" / "review_mask.png"
    m = Image.new("RGB", (w, h), (0, 0, 0))
    ImageDraw.Draw(m).rectangle([0, int(h * 0.55), w, h], fill=(255, 255, 255))
    m.save(mask)
    before = keep(SRC, "4a_masked_edit_before.png")
    j = run("inpaint", {"source": SRC, "mask": str(mask),
                        "prompt": "warm walnut wood table surface, soft studio light",
                        "denoise": 0.75, "seed": 11, "steps": 20})
    after = keep(j.get("output"), "4b_masked_edit_after.png")
    made["4a_masked_edit_before.png"] = before
    made["4b_masked_edit_after.png"] = after

    # 5) standard vs high resolution
    j = run("generate", {"prompt": "studio product photograph of a glass jar of turmeric "
                                   "powder on a neutral background, soft light, photorealistic",
                         "mode": "standard", "seed": 77, "width": 1024, "height": 1024})
    made["5a_sdxl_standard_1024.png"] = keep(j.get("output"), "5a_sdxl_standard_1024.png")
    std_meta = {"lane": (j.get("result") or {}).get("lane"),
                "execution_s": j.get("execution_s"), "interval_s": j.get("interval_s")}
    j = run("generate", {"prompt": "studio product photograph of a glass jar of turmeric "
                                   "powder on a neutral background, soft light, photorealistic",
                         "mode": "high", "seed": 77, "width": 1280, "height": 1280})
    made["5b_sdxl_high_1280.png"] = keep(j.get("output"), "5b_sdxl_high_1280.png")
    high_meta = {"lane": (j.get("result") or {}).get("lane"),
                 "execution_s": j.get("execution_s"), "interval_s": j.get("interval_s")}

    sheet = f"""# Owner Review Sheet — Shared Image Services

Generated: {time.strftime('%Y-%m-%dT%H:%M:%S')}
Folder: `generated_images/creative/review_set/`

These are **representative samples for owner visual approval**. Quality-based
defaults remain **provisional** until reviewed. "High resolution" does **not**
automatically mean higher quality — judge each sample on its own merits.

## What to inspect

| # | File | Inspect for |
|---|---|---|
| 1 | `1_faithful_product_ad.png` | Product identity preserved (source jar); label text exact & correctly spelled; contact/edges clean |
| 2 | `2_packaging_concept_exact_text.png` | It is labelled a **concept** (not a real SKU); exact text correct; label zone clean |
| 3 | `3_finished_branded_ad.png` | Text band does not cover the product; brand lockup correct; export 1080×1080 |
| 4a/4b | `4a_masked_edit_before.png` / `4b_masked_edit_after.png` | Only the masked (lower) region changed; product/label above the mask is pixel-identical |
| 5a/5b | `5a_sdxl_standard_1024.png` / `5b_sdxl_high_1280.png` | Compare detail, artifact level, and whether 1280 is actually better |

## Execution paths (this set)

- Standard run: `{std_meta}`
- High run: `{high_meta}`
- Inputs: samples 1 and 3 **reuse** the source product photo; samples 2 and 5 are
  **freshly generated**; sample 4 **reuses** the source and a generated mask.
- ComfyUI models are unloaded between jobs; execution time **includes model loading**.

## Decisions requested

1. Approve / reject each sample.
2. Confirm or change the provisional defaults (draft = Z-Image-Turbo,
   standard = SDXL 1024, high = SDXL 1280).
3. Confirm whether 1280² is worth the extra time/VRAM vs 1024².
"""
    (SHEET / "review_sheet.md").write_text(sheet, encoding="utf-8")
    (SHEET / "review_set.json").write_text(json.dumps(made, indent=2), encoding="utf-8")
    print(json.dumps(made, indent=2))
    print("sheet ->", SHEET / "review_sheet.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
