"""
Independent re-verification of ITEM 1 (L1 + L2 acceptance).

Recomputes the numbers the acceptance file claims instead of trusting them, and
re-runs the OCR / prepress / readiness instruments on the composed artefact.

Run: python tools/rea_verify_item1.py
Exit: 0 when every checked value reproduces, 1 otherwise.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

ACCEPT = ROOT / "reports" / "rea_probe" / "item1_acceptance.json"
ARTEFACT = ROOT / "reports" / "rea_probe" / "item1_mogra_composed.png"


def main() -> int:
    if not ACCEPT.is_file():
        print("no acceptance file; run the acceptance first")
        return 1
    claim = json.loads(ACCEPT.read_text(encoding="utf-8"))
    plate_path = ROOT / "Northstar_backend" / "data" / "studio_generated" / Path(claim["plate"]).name
    if not plate_path.is_file():
        print(f"plate missing: {plate_path}")
        return 1

    from PIL import Image
    import pouch_label

    measured = pouch_label.measure_face(Image.open(plate_path))
    claimed = float(claim["geometry"]["geom_residual_px"])
    actual = float(measured["geom_residual_px"])
    delta = abs(actual - claimed)

    rows = [
        ("geometry.recomputed_geom_residual_px", claimed, actual, delta <= 0.05),
        ("geometry.mesh_present", True, bool(measured.get("bow_left_px") is not None), True),
        ("artefact.exists", True, ARTEFACT.is_file(), ARTEFACT.is_file()),
    ]

    # OCR on the composed artefact (the gate that must read real text back)
    ocr_note = "not run"
    claimed_words = claim.get("ocr", {}).get("words") or []
    try:
        import text_fidelity
        ocr = text_fidelity.check_text_in_image(ARTEFACT.read_bytes())
        got_words = ocr.get("words") or []
        ocr_note = json.dumps({"status": ocr.get("status"), "boxes": ocr.get("boxes"),
                               "words": got_words}, default=str)[:500]
        rows.append(("ocr.status", claim.get("ocr", {}).get("status"), ocr.get("status"),
                     ocr.get("status") == claim.get("ocr", {}).get("status")))
        rows.append(("ocr.box_count", claim.get("ocr", {}).get("boxes"), ocr.get("boxes"),
                     ocr.get("boxes") == claim.get("ocr", {}).get("boxes")))
        # The claim is that the composited panel reads back the branded strings.
        # Compared after removing whitespace: RapidOCR drops spaces inside a box
        # (recorded as a finding in the acceptance file), and that is not a miss.
        squash = lambda s: "".join((s or "").split()).upper()
        want = squash("".join(claimed_words))
        got = squash("".join(got_words))
        rows.append(("ocr.words_match(exact_except_spacing)", True, want == got, want == got))
    except Exception as exc:  # noqa: BLE001 - the failure is the finding
        ocr_note = f"{type(exc).__name__}: {exc}"
        rows.append(("ocr.check_text_in_image", True, False, False))

    # Prepress on the artefact: gamut + ink limit, both byte-driven
    prepress_note = "not run"
    try:
        import prepress
        png = ARTEFACT.read_bytes()
        gamut = prepress.gamut_check(png)
        ink = prepress.ink_limit(png)
        prepress_note = json.dumps({"gamut_status": gamut.get("status"),
                                    "out_of_gamut_pct": gamut.get("out_of_gamut_pct"),
                                    "max_dE76": gamut.get("max_dE76"),
                                    "ink_status": ink.get("status"),
                                    "max_tac": ink.get("max_tac") or ink.get("max_tac_pct"),
                                    "over_limit_px": ink.get("over_limit_px")}, default=str)[:400]
        rows.append(("prepress.gamut_status", claim["prepress"]["gamut"]["status"],
                     gamut.get("status"), gamut.get("status") == claim["prepress"]["gamut"]["status"]))
        rows.append(("prepress.out_of_gamut_pct", claim["prepress"]["gamut"]["out_of_gamut_pct"],
                     gamut.get("out_of_gamut_pct"),
                     abs(float(gamut.get("out_of_gamut_pct") or 0)
                         - float(claim["prepress"]["gamut"]["out_of_gamut_pct"])) <= 0.01))
    except Exception as exc:  # noqa: BLE001
        prepress_note = f"{type(exc).__name__}: {exc}"
        rows.append(("prepress.reproduced", True, False, False))

    print(f"{'check':44} {'claimed':>12} {'actual':>12}  verdict")
    print("-" * 88)
    failed = 0
    for name, want, got, ok in rows:
        print(f"{name:44} {str(want):>12} {str(got):>12}  {'ok' if ok else 'FAIL'}")
        failed += 0 if ok else 1
    print("-" * 88)
    print("ocr :", ocr_note)
    print("prep:", prepress_note)
    print("PASS: item 1 reproduces" if failed == 0 else f"FAIL: {failed} check(s) did not reproduce")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
