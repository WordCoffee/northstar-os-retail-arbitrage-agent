"""E2: preserve the seller's product by compositing it, not by conditioning on it.

The identity experiment (E1) is blocked - the Qwen-Image-Edit weights are not on
disk and the box has ~9.7 GB free. This path needs no download:

  1. FLUX 3 renders an empty *scene* (a surface, a light, a shadow direction).
  2. BiRefNet cuts the real product out of the seller's own photo.
  3. product_composite places the cutout on the scene at a measured scale.
  4. The identity check proves the placed pixels ARE the seller's pixels, and
     the scorecard's product_fidelity measures the same thing independently.

    python tools/experiment_composite.py --scene lifestyle_linen --scale 0.7

Evidence: state/evidence/composite_experiment_<ts>.json and the PNGs under
renders/autonomy_probe/composite/.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

OUT = ROOT / "renders" / "autonomy_probe" / "composite"

SCENES = {
    "lifestyle_linen": ("an empty pale linen surface beside a window, soft morning light "
                        "from the left, a plain warm wall behind, no objects, no text, "
                        "photographic, shallow depth of field"),
    "lifestyle_counter": ("an empty wooden cafe counter with a blurred espresso machine and "
                          "a dark wall behind, warm tungsten light, no objects, no text, "
                          "photographic"),
    "studio_white": ("an empty seamless pure white studio background with a soft gradient "
                     "floor and one soft shadow area, no objects, no text, product "
                     "photography backdrop"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run(reference: Path, scene_name: str, *, scale: float, seed: int) -> dict:
    import picture_scorecard as ps
    import product_composite as pc
    import studio_generation as sg

    OUT.mkdir(parents=True, exist_ok=True)
    photo = reference.read_bytes()
    record: dict = {"experiment": "E2_composite_identity", "at": _now(),
                    "reference": str(reference.relative_to(ROOT)).replace("\\", "/"),
                    "scene": scene_name, "scale": scale, "steps": {}}

    # 1. the empty scene
    t0 = time.time()
    try:
        scene = sg.generate_image(SCENES[scene_name], width=1024, height=1024,
                                  tier="draft", seed=seed)
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"scene_render_failed: {type(exc).__name__}: {exc}"
        return record
    record["steps"]["scene"] = {"seconds": round(time.time() - t0, 1),
                                "bytes": len(scene["bytes"])}
    (OUT / f"{scene_name}_scene.png").write_bytes(scene["bytes"])

    # 2. the seller's product, cut out
    t0 = time.time()
    try:
        cut = sg.generate_cutout(photo, filename=f"e2-cutout-{seed}.png")
    except Exception as exc:  # noqa: BLE001
        record["error"] = f"cutout_failed: {type(exc).__name__}: {exc}"
        return record
    cutout_bytes = cut["bytes"]
    (OUT / f"{scene_name}_cutout.png").write_bytes(cutout_bytes)
    opaque = cut.get("opaque_pixels") or cut.get("opaque")
    record["steps"]["cutout"] = {"seconds": round(time.time() - t0, 1),
                                 "bytes": len(cutout_bytes), "opaque_pixels": opaque}

    # 3. place it
    placed = pc.place_product(scene["bytes"], cutout_bytes, scale=scale,
                              anchor=(0.5, 0.72), shadow=True)
    (OUT / f"{scene_name}_composite.png").write_bytes(placed["bytes"])
    record["steps"]["composite"] = {"product_scale": placed["product_scale"],
                                    "product_box": placed["product_box"],
                                    "scale_clamped": placed["scale_clamped"]}

    # 4. prove identity two ways
    ident = pc.identity_check(placed["bytes"], cutout_bytes,
                              tuple(placed["product_box"]))
    scored = ps.score_case(
        image_bytes=placed["bytes"],
        case={"id": f"e2_{scene_name}", "surface": "lifestyle",
              "scenario": scene_name, "brief": SCENES[scene_name]},
        reference_bytes=photo, seconds=record["steps"]["scene"]["seconds"] + 1, scoring=False)
    record["identity_check"] = ident
    record["product_fidelity"] = scored["dimensions"]["product_fidelity"]
    record["output"] = str((OUT / f"{scene_name}_composite.png").relative_to(ROOT)).replace("\\", "/")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = ROOT / "state" / "evidence" / f"composite_experiment_{stamp}.json"
    path.write_text(json.dumps(record, indent=2, default=str), encoding="utf-8")
    record["evidence"] = str(path.relative_to(ROOT)).replace("\\", "/")

    # Leave the text lane available for the next job.
    try:
        sg.release_models()
    except Exception:  # noqa: BLE001
        pass
    return record


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="E2 composite identity experiment.")
    parser.add_argument("--reference", default="renders/mogra_lions_mane/product_front.png")
    parser.add_argument("--scene", default="lifestyle_linen", choices=tuple(SCENES))
    parser.add_argument("--scale", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=5150)
    ns = parser.parse_args(argv)

    reference = ROOT / ns.reference
    if not reference.is_file():
        print(json.dumps({"ok": False, "error": f"reference not found: {ns.reference}"}))
        return 2
    try:
        import studio_generation as sg

        if not sg.engine_status().get("reachable"):
            print(json.dumps({"ok": False, "error": "comfyui_unreachable"}))
            return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 2

    result = run(reference, ns.scene, scale=ns.scale, seed=ns.seed)
    print(json.dumps(result, indent=2, default=str))
    return 0 if not result.get("error") else 1


if __name__ == "__main__":
    raise SystemExit(main())
