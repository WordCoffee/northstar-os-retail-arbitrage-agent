#!/usr/bin/env python3
"""End-to-end hero pipeline: FLUX 3 -> cutout -> pure-white hero -> listing payload.

Proof, not a demo: every stage writes its artefact and its measurement into
exports/e2e_hero_20261030/report.json, and the hardware guardrail is consulted
before the first render.

    python tools/e2e_hero.py [--prompt "..."] [--seed 4242]
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

os.environ.setdefault("MEDIA_GEN_LIVE", "1")   # local render, no provider, no spend

import asset_handoff  # noqa: E402
import hardware_guard  # noqa: E402
import listing_image  # noqa: E402
import render_bind  # noqa: E402
import studio_generation as sg  # noqa: E402
import text_fidelity  # noqa: E402

OUT = ROOT / "exports" / "e2e_hero_20261030"
PRODUCT = {"id": "e2e-lions-mane-6oz", "target_price": 34.0, "unit_cost": 11.5}
KEYWORDS = ["lion's mane powder", "fruiting body mushroom", "6 oz pouch"]
BUYER = {"room": "kitchen", "segment": "home cook"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default=(
        "A matte kraft stand-up pouch of organic lion's mane mushroom powder, "
        "centred, soft studio lighting, 85mm lens, plain warm grey seamless backdrop, "
        "no text, no lettering, no logo, no watermark"
    ))
    ap.add_argument("--seed", type=int, default=4242)
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    report = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "out_dir": str(OUT)}

    # 1. guardrail BEFORE anything touches the GPU
    hw = hardware_guard.snapshot()
    batch, reason, _ = hardware_guard.plan(1)
    report["hardware_before"] = {
        "ok": hw.ok, "used_mb": hw.used_mb, "total_mb": hw.total_mb,
        "ratio": hw.ratio, "temp_c": hw.temp_c, "allowed_batch": batch, "reason": reason,
    }
    if batch == 0:
        report["status"] = "refused_by_hardware_guard"
        (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(report, indent=2))
        return 2

    # 2. FLUX 3 render
    t0 = time.time()
    render = sg.generate_image(args.prompt, 1024, 1024, tier="draft", seed=args.seed)
    png = render.get("bytes")
    if not png:
        raise RuntimeError(f"generate_image returned no bytes: {sorted(render)}")
    (OUT / "01_render.png").write_bytes(png)
    report["render"] = {
        "bytes": len(png), "seconds": round(time.time() - t0, 1),
        "model": render.get("model"), "seed": args.seed, "path": str(OUT / "01_render.png"),
    }

    # 2b. TEXT GATE. FLUX 3 paints lettering even when told not to; the measured
    # run produced 8 OCR boxes of garbled copy. Detect, scrub deterministically,
    # re-check. A hero that still carries lettering must not ship.
    first = text_fidelity.check_text_in_image(png)
    gate = {"first": {k: first.get(k) for k in ("status", "contains_text", "boxes", "engine")}}
    if first.get("contains_text"):
        scrub = text_fidelity.clean_text_regions(png)
        cleaned = scrub.get("image")
        if cleaned:
            again = text_fidelity.check_text_in_image(cleaned)
            gate["after_clean"] = {k: again.get(k) for k in ("status", "contains_text", "boxes")}
            gate["cleared"] = scrub.get("cleared")
            gate["cleaned_bytes"] = len(cleaned)
            png = cleaned
            (OUT / "01b_render_cleaned.png").write_bytes(cleaned)
            gate["passed"] = not again.get("contains_text")
        else:
            gate["after_clean"] = {"status": scrub.get("status"), "error": scrub.get("error")}
            gate["passed"] = False
    else:
        gate["passed"] = True
    report["text_gate"] = gate
    if not gate["passed"]:
        report["status"] = "rejected_text_in_render"
        report["blocked"] = ["text_in_render"]
        (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({k: report[k] for k in ("status", "text_gate", "render")}, indent=2))
        return 3

    # 3. cutout (BiRefNet, local)
    t1 = time.time()
    cut = sg.generate_cutout(png)
    (OUT / "02_cutout.png").write_bytes(cut["bytes"])
    report["cutout"] = {
        "bytes": len(cut["bytes"]), "seconds": round(time.time() - t1, 1),
        "model": cut.get("model"), "path": str(OUT / "02_cutout.png"),
    }

    # 4. pure-white hero + contact shadow
    t2 = time.time()
    hero = listing_image.hero_on_white(cut["bytes"], size=2000, fill=0.85, shadow=True)
    (OUT / "03_hero.png").write_bytes(hero)
    audit = listing_image.audit_white(hero)
    report["hero"] = {
        "bytes": len(hero), "seconds": round(time.time() - t2, 1),
        "path": str(OUT / "03_hero.png"), **audit,
    }

    # 5. Phase 3 binding: margin -> material, then the Listing Forge payload
    brief = render_bind.bind(PRODUCT, pricing=PRODUCT, keywords=KEYWORDS,
                             buyer=BUYER, lifestyle=False)
    payload = asset_handoff.handoff(brief, [
        {"url": "03_hero.png", "width": 2000, "height": 2000, "role": "hero",
         "pure_white": audit["corners_pure_white"]},
        {"url": "01_render.png", "width": 1024, "height": 1024, "role": "detail"},
    ])
    report["brief"] = brief.to_dict()
    report["listing_payload"] = payload

    # 6. guardrail AFTER
    hw2 = hardware_guard.snapshot()
    report["hardware_after"] = {"used_mb": hw2.used_mb, "ratio": hw2.ratio, "temp_c": hw2.temp_c}

    report["status"] = "ok" if (
        audit["corners_pure_white"] and payload["ready"] and brief.material_tier != "unknown"
    ) else "incomplete"
    (OUT / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("status", "hardware_before", "render", "cutout", "hero", "brief")}, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
