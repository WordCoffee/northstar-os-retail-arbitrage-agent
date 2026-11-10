"""E1: is identity preserved by *editing* the real product instead of conditioning on it?

The measurement that motivated this: FLUX 3 reference conditioning (mi2i) renders
a different pouch — subject-crop ssim 0.010-0.323 and pHash 26-28 against the
reference photo. Every competitor that does product photography preserves the
product, so this is the gap that matters.

This experiment asks Qwen-Image-Edit-2511 (Apache-2.0, installed locally) to
re-place the *actual* product photo in a new scene, then scores identity with the
same instrument (`picture_scorecard`, subject crop). One command, one number:

    python tools/experiment_identity.py --reference renders/mogra_lions_mane/product_front.png

A result is printed and written to state/evidence/identity_experiment_<ts>.json.
Nothing is claimed unless the numbers are there.
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

OUT = ROOT / "renders" / "autonomy_probe" / "identity"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


SCENES = {
    "lifestyle_linen": ("Place this exact product on a pale linen surface beside a soft "
                        "window light. Keep the pouch shape, the kraft material and the "
                        "cream label exactly as they are, unchanged."),
    "lifestyle_counter": ("Place this exact product on a wooden cafe counter with a blurred "
                          "espresso machine behind it. Keep the pouch, its label and its "
                          "proportions exactly as they are."),
    "main_white": ("Place this exact product centred on a pure white seamless background with "
                   "a soft contact shadow. Keep the pouch, label and proportions unchanged."),
}


def run(reference: Path, scenes: list[str], *, tier: str) -> dict:
    import picture_scorecard as ps
    import studio_generation as sg

    data = reference.read_bytes()
    OUT.mkdir(parents=True, exist_ok=True)
    out: dict = {"experiment": "E1_identity_by_edit", "at": _now(),
                 "reference": str(reference.relative_to(ROOT)).replace("\\", "/"),
                 "model": "qwen-image-edit-2511 (Apache-2.0)", "tier": tier,
                 "rows": []}

    # The baseline for the same reference, measured with the same instrument.
    base = ps.score_case(image_bytes=data,
                         case={"id": "baseline", "surface": "lifestyle"},
                         reference_bytes=data, scoring=False)
    out["self_check"] = base["dimensions"]["product_fidelity"]

    for name in scenes:
        prompt = SCENES[name]
        started = time.time()
        try:
            result = sg.generate_edit(data, prompt, tier=tier)
        except Exception as exc:  # noqa: BLE001 - the failure is the measurement
            out["rows"].append({"scene": name, "ok": False,
                                "error": f"{type(exc).__name__}: {exc}",
                                "seconds": round(time.time() - started, 1)})
            continue
        seconds = round(time.time() - started, 1)
        target = OUT / f"e1_{name}.png"
        target.write_bytes(result["bytes"])
        scored = ps.score_case(
            image_bytes=result["bytes"],
            case={"id": name, "surface": "lifestyle", "scenario": name,
                  "brief": prompt},
            reference_bytes=data, seconds=seconds, scoring=False)
        out["rows"].append({
            "scene": name, "ok": True,
            "image": str(target.relative_to(ROOT)).replace("\\", "/"),
            "bytes": len(result["bytes"]), "seconds": seconds,
            "fidelity": scored["dimensions"]["product_fidelity"],
            "text": scored["dimensions"]["text_accuracy"],
            "mode": result.get("mode"),
            "copy_drift": result.get("copy_drift") or result.get("preserves_copy"),
        })
        # Free the edit model before the next scene: this box is RAM-bound.
        try:
            sg.release_models()
        except Exception:  # noqa: BLE001
            pass

    scores = [r["fidelity"]["score"] for r in out["rows"]
              if r.get("ok") and r.get("fidelity", {}).get("score") is not None]
    out["summary"] = {
        "scenes_run": len(out["rows"]),
        "scenes_ok": sum(1 for r in out["rows"] if r.get("ok")),
        "fidelity_mean": round(sum(scores) / len(scores), 1) if scores else None,
        "passes_bar": bool(scores) and min(scores) >= 85,
        "bar": "subject-crop ssim >= 0.55 and pHash <= 24 (see picture_scorecard identity)",
    }
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = ROOT / "state" / "evidence" / f"identity_experiment_{stamp}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")
    out["evidence"] = str(path.relative_to(ROOT)).replace("\\", "/")
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="E1 identity-by-edit experiment.")
    parser.add_argument("--reference", default="renders/mogra_lions_mane/product_front.png")
    parser.add_argument("--scenes", nargs="*", default=["lifestyle_linen"])
    parser.add_argument("--tier", default="draft")
    ns = parser.parse_args(argv)

    reference = ROOT / ns.reference
    if not reference.is_file():
        print(json.dumps({"ok": False, "error": f"reference not found: {ns.reference}"}))
        return 2

    try:
        import studio_generation as sg

        status = sg.engine_status()
        if not status.get("reachable"):
            print(json.dumps({"ok": False, "error": "comfyui_unreachable",
                              "engine": status}, indent=2))
            return 2
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}))
        return 2

    result = run(reference, ns.scenes, tier=ns.tier)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["summary"]["scenes_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
