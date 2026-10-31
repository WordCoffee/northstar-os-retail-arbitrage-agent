#!/usr/bin/env python3
"""Blank-plate architecture, end to end.

The rule: the image model renders a PRISTINE UNPRINTED PLATE. Every word on the
package is composited deterministically by `pouch_label.compose`. Then OCR is
used in the opposite direction from before - not to prove the absence of garbage,
but to prove the INTENDED COPY is actually readable.

    python tools/e2e_labelled.py [--seed 4242]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

os.environ.setdefault("MEDIA_GEN_LIVE", "1")

import asset_handoff  # noqa: E402
import hardware_guard  # noqa: E402
import listing_image  # noqa: E402
import pouch_label  # noqa: E402
import render_bind  # noqa: E402
import studio_generation as sg  # noqa: E402
import text_fidelity  # noqa: E402

OUT = ROOT / "exports" / "e2e_labelled_20261030"
PRODUCT = {"id": "lions-mane-6oz", "target_price": 34.0, "unit_cost": 11.5}
KEYWORDS = ["lion's mane powder", "fruiting body mushroom", "6 oz pouch"]
COPY = {
    "title": "LION'S MANE",
    "subtitle": "Organic Mushroom Powder",
    "weight": "6 oz (170 g)",
    "bullets": ["Fruiting body only", "Third-party tested", "60 servings"],
}
EXPECTED = ["lion", "mane", "mushroom", "powder"]

PLATE_PROMPT = (
    "A completely blank unprinted matte kraft stand-up pouch, no printing, no label, "
    "no text, no lettering, no logo, no graphics, plain uncoated surface, centred on a "
    "warm grey seamless backdrop, soft studio lighting, 85mm lens, shallow depth of field"
)


def ocr_words(png: bytes) -> dict:
    res = text_fidelity.check_text_in_image(png)
    return {"status": res.get("status"), "contains_text": res.get("contains_text"),
            "boxes": res.get("boxes"), "words": res.get("words") or []}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=4242)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "out_dir": str(OUT)}

    hw = hardware_guard.snapshot()
    batch, reason, _ = hardware_guard.plan(1)
    report["hardware_before"] = {"ratio": hw.ratio, "temp_c": hw.temp_c,
                                 "allowed_batch": batch, "reason": reason}
    if batch == 0:
        report["status"] = "refused_by_hardware_guard"
        (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 2

    # 1. blank plate
    t0 = time.time()
    render = sg.generate_image(PLATE_PROMPT, 1024, 1024, tier="draft", seed=args.seed)
    plate = render["bytes"]
    (OUT / "01_plate.png").write_bytes(plate)
    report["plate"] = {"bytes": len(plate), "seconds": round(time.time() - t0, 1),
                       "model": render.get("model"), "seed": args.seed,
                       "ocr": ocr_words(plate)}

    # 2. the model still prints. Scrub, then verify the scrub, then let the label
    #    cover the panel anyway - the scrub exists so no garbage survives outside
    #    the label area.
    if report["plate"]["ocr"]["contains_text"]:
        scrub = text_fidelity.clean_text_regions(plate)
        if scrub.get("image"):
            plate = scrub["image"]
            (OUT / "01b_plate_cleaned.png").write_bytes(plate)
        report["plate_scrub"] = {"cleared": scrub.get("cleared"),
                                 "status": scrub.get("status"),
                                 "ocr_after": ocr_words(plate)}

    # 3. deterministic typography
    t1 = time.time()
    plate_path = OUT / "01c_plate_for_label.png"
    plate_path.write_bytes(plate)
    composed = pouch_label.compose(
        plate_path,
        title=COPY["title"], subtitle=COPY["subtitle"], weight=COPY["weight"],
        bullets=COPY["bullets"],
    )
    labelled = composed["bytes"]
    (OUT / "02_labelled.png").write_bytes(labelled)
    report["label"] = {
        "seconds": round(time.time() - t1, 1), "bytes": len(labelled),
        "size": composed.get("size"), "geom_residual_px": composed.get("geom_residual_px"),
        "quad": composed.get("quad"),
    }

    # 4. the inversion: OCR must now find the REAL copy, not garbage
    words = ocr_words(labelled)
    found = " ".join(words["words"]).lower()
    hits = [w for w in EXPECTED if w in found]
    report["label_text_check"] = {"ocr": words, "expected": EXPECTED, "hits": hits,
                                  "passed": len(hits) >= 2}

    # 5. cutout -> pure white hero
    cut = sg.generate_cutout(labelled)
    (OUT / "03_cutout.png").write_bytes(cut["bytes"])
    hero = listing_image.hero_on_white(cut["bytes"], size=2000, fill=0.85, shadow=True)
    (OUT / "04_hero.png").write_bytes(hero)
    audit = listing_image.audit_white(hero)
    report["hero"] = {"path": str(OUT / "04_hero.png"), **audit}

    # 6. Phase 3 binding + hand-off
    brief = render_bind.bind(PRODUCT, pricing=PRODUCT, keywords=KEYWORDS)
    payload = asset_handoff.handoff(brief, [
        {"url": "04_hero.png", "width": 2000, "height": 2000, "role": "hero",
         "pure_white": audit["corners_pure_white"]},
        {"url": "02_labelled.png", "width": composed["size"][0], "height": composed["size"][1],
         "role": "detail"},
    ])
    report["brief"] = brief.to_dict()
    report["listing_payload"] = payload

    hw2 = hardware_guard.snapshot()
    report["hardware_after"] = {"ratio": hw2.ratio, "temp_c": hw2.temp_c}

    ok = (audit["corners_pure_white"] and payload["ready"]
          and report["label_text_check"]["passed"])
    report["status"] = "ok" if ok else "incomplete"
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("status", "plate", "label", "label_text_check", "hero",
                       "hardware_before", "hardware_after")}, indent=2)[:3000])
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
