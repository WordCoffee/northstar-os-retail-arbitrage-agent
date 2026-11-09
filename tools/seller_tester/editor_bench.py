"""Measure the cutout editors on the first real uploads — a leaderboard, not a preference.

Which method cuts the product out of an upload is a measured decision with the
same shape as the model scout's: one fixed eval set per role, every candidate
scored on the *same* items, and a written recommendation. The eval is the three
Mogra Organics assets in ``renders/references/mogra/`` and the items are derived
from the service's own acceptance rule, not from taste:

    coverage  the alpha's coverage is consistent with the reference's own
              corner-background subject mask (|delta| <= 0.20, and >= 3%); not
              applicable when the reference has no separable background
    border    the alpha does not own the frame border (<= 5%): a product cutout
              stops at the product, a whole-scene mask does not
    text      the product composited on white still prints the manifest's key
              words: text_match recall >= 0.60 (the reference check's rule)
    edge      the delivered alpha's gradient band is <= 8 px (not mush)
    time      the cutout finishes in <= 60 s for one asset

A full-bleed asset has no separable background, so `coverage` is not applicable
there and the item is omitted from the denominator instead of being failed.

The rows are written into ``ty/model_leaderboard.json`` under the `editors` role
through ``tools/model_scout.py``'s own ``build_leaderboard`` / ``write_leaderboard``,
so the choice is a scout leaderboard entry. Licences belong in ``provenance.csv``;
the notes here repeat the short form so a reader does not have to join files.

    python -m tools.seller_tester.editor_bench
    python -m tools.seller_tester.editor_bench --with-lane   # also measure BiRefNet
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[2]
for _extra in (str(ROOT), str(ROOT / "tools"), str(ROOT / "Northstar_backend")):
    if _extra not in sys.path:
        sys.path.insert(0, _extra)

DEFAULT_REFERENCE_DIR = ROOT / "renders" / "references" / "mogra"
DEFAULT_EVIDENCE = ROOT / "state" / "seller" / "editor_bench.json"
DEFAULT_LEADERBOARD = ROOT / "ty" / "model_leaderboard.json"
LEADERBOARD_MIRROR = ROOT / "state" / "intel" / "models.json"

#: Short licence / install record. The long form is appended to provenance.csv.
LICENCES = {
    "background_distance": "OpenCV (Apache-2.0) + NumPy (BSD-3-Clause); installed; no model weights",
    "otsu_lab": "OpenCV (Apache-2.0) + NumPy (BSD-3-Clause); installed; no model weights",
    "grabcut": "OpenCV GrabCut (Apache-2.0 implementation of Rother et al. 2004); installed; no model weights",
    "birefnet": "BiRefNet weights birefnet.safetensors (MIT, ZhengPeng7/BiRefNet); already on disk; needs the local ComfyUI lane",
    "rembg": "rembg (MIT) + U-2-Net weights (Apache-2.0); NOT installed here",
}

EDGE_MAX_PX = 8.0
TIME_MAX_S = 60.0
COVERAGE_MAX_DELTA = 0.20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_assets(reference_dir: Path = DEFAULT_REFERENCE_DIR) -> List[Dict[str, Any]]:
    manifest = json.loads((Path(reference_dir) / "manifest.json").read_text(encoding="utf-8"))
    assets: List[Dict[str, Any]] = []
    for row in manifest.get("assets") or []:
        path = Path(reference_dir) / row["file"]
        if not path.is_file():
            raise FileNotFoundError(f"reference asset missing: {path}")
        assets.append({"file": row["file"], "path": str(path),
                       "printed": list(row.get("printed") or []),
                       "subject": row.get("subject")})
    if not assets:
        raise ValueError("manifest lists no assets")
    return assets


def _ocr_engine():
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


def _read_text(engine: Any, rgb) -> str:
    import numpy as np

    result, _ = engine(np.ascontiguousarray(rgb[:, :, ::-1]))
    return " ".join(str(row[1]) for row in (result or []))


def _birefnet_alphas(assets: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    """One lane, three cutouts, stop verified. Returns {file: alpha or reason}."""
    import comfy_lane  # noqa: PLC0415
    import gpu_budget  # noqa: PLC0415
    import product_cutout as pc  # noqa: PLC0415

    lock = gpu_budget.lock("seller_editor_bench", ttl_s=1800)
    if not lock.get("ok"):
        return {"_error": f"gpu locked by {lock.get('held_by')}"}
    outcome: Dict[str, Any] = {}

    def _work() -> Dict[str, Any]:
        results = {}
        for asset in assets:
            started = time.perf_counter()
            try:
                alpha = pc.birefnet_alpha(pc.load_rgb(asset["path"]))
                results[asset["file"]] = {"alpha": alpha,
                                          "seconds": time.perf_counter() - started}
            except Exception as exc:  # noqa: BLE001 - reported per asset
                results[asset["file"]] = {"error": f"{type(exc).__name__}: {exc}"}
        return results

    try:
        lane = comfy_lane.lane(_work)
    finally:
        gpu_budget.unlock("seller_editor_bench")
    if not lane.get("ok"):
        return {"_error": f"lane failed: {lane.get('reason')}"}
    stopped = (lane.get("lane") or {}).get("stopped") or {}
    if not stopped.get("ok"):
        return {"_error": f"lane did not prove it stopped: {stopped.get('reason')}"}
    outcome.update(lane.get("result") or {})
    outcome["_lane"] = lane.get("lane")
    return outcome


def bench(*, reference_dir: Path = DEFAULT_REFERENCE_DIR,
          methods: Sequence[str] = ("background_distance", "otsu_lab", "grabcut"),
          with_lane: bool = False) -> Dict[str, Any]:
    """Score every candidate on the same three assets. Pure measurement."""
    import numpy as np

    import product_cutout as pc  # noqa: PLC0415
    from .reference_check import subject_mask, text_match  # noqa: PLC0415

    assets = load_assets(reference_dir)
    ram_after = None
    try:
        import gpu_budget  # noqa: PLC0415

        ram_after = gpu_budget.ram().get("free_gb")
    except Exception:  # noqa: BLE001
        ram_after = None

    engine = _ocr_engine()
    lane_results: Dict[str, Any] = {}
    if with_lane:
        lane_results = _birefnet_alphas(assets)
        methods = list(methods) + ["birefnet"]

    rows: Dict[str, Dict[str, Any]] = {}
    for method in methods:
        row: Dict[str, Any] = {
            "model": method, "role": "editors", "status": "measured",
            "correct": 0, "items": 0, "per_asset": {},
            "licence": LICENCES.get(method, "unrecorded"),
            "vram_gb": None, "ram_free_gb": ram_after,
        }
        latencies: List[float] = []
        for asset in assets:
            rgb = pc.load_rgb(asset["path"])
            reference_coverage = float(subject_mask(rgb).mean())
            entry: Dict[str, Any] = {"reference_coverage": round(reference_coverage, 4)}
            t0 = time.perf_counter()
            try:
                if method == "birefnet":
                    result = lane_results.get(asset["file"]) or {}
                    if "alpha" not in result:
                        raise RuntimeError(result.get("error") or lane_results.get("_error")
                                           or "BiRefNet was not measured")
                    alpha = result["alpha"]
                    seconds = float(result.get("seconds") or 0.0)
                else:
                    cut = pc.cutout(rgb, method)
                    alpha = cut.alpha
                    seconds = cut.seconds
            except Exception as exc:  # noqa: BLE001 - a failed candidate is a measured failure
                entry.update({"error": f"{type(exc).__name__}: {exc}"[:300],
                              "seconds": round(time.perf_counter() - t0, 3)})
                entry["checks"] = {}
                row["per_asset"][asset["file"]] = entry
                continue
            latencies.append(seconds)
            metrics = pc.alpha_metrics(alpha, reference_coverage=reference_coverage)
            composite = pc.compose_on(rgb, alpha)
            produced_text = _read_text(engine, composite)
            text = text_match(produced_text, " ".join(asset["printed"]))
            coverage_ok = pc.coverage_plausible(metrics, max_delta=COVERAGE_MAX_DELTA)
            checks = {
                "coverage": coverage_ok,
                "border": pc.border_ok(metrics),
                "text": bool(text.get("ok")) if not text.get("cannot_verify") else None,
                "edge": bool(metrics["edge_gradient_px"] <= EDGE_MAX_PX),
                "time": bool(seconds <= TIME_MAX_S),
            }
            entry.update({
                "seconds": round(seconds, 3), "checks": checks,
                "coverage": metrics["coverage"],
                "coverage_delta": metrics.get("coverage_delta"),
                "border_contact": metrics["border_contact"],
                "edge_gradient_px": metrics["edge_gradient_px"],
                "boundary_roughness": metrics["boundary_roughness"],
                "recall": text.get("recall"),
                "matched": text.get("matched"), "missing": text.get("missing"),
                "ocr_text": produced_text[:400],
            })
            for name, value in checks.items():
                if value is None:
                    continue
                row["items"] += 1
                row["correct"] += 1 if value else 0
            row["per_asset"][asset["file"]] = entry
        row["latency_ms"] = round(1000.0 * (sum(latencies) / len(latencies)), 1) if latencies else None
        edges = [entry["edge_gradient_px"] for entry in row["per_asset"].values()
                 if isinstance(entry.get("edge_gradient_px"), (int, float))]
        row["mean_edge_px"] = round(sum(edges) / len(edges), 2) if edges else None
        rows[method] = row

    for name in ("rembg",):
        if name not in rows:
            rows[name] = {"model": name, "role": "editors", "status": "not_installed",
                          "reason": "not in this environment; nothing was pulled",
                          "correct": None, "items": None, "latency_ms": None,
                          "licence": LICENCES[name], "per_asset": {}}
    measurement = {name: row for name, row in rows.items()}
    ranking = sorted(
        [row for row in rows.values() if row.get("status") == "measured"],
        key=lambda row: (-(row.get("correct") or 0),
                         row.get("mean_edge_px") if row.get("mean_edge_px") is not None else 1e9,
                         row.get("latency_ms") or 1e9))
    return {"at": _now(), "assets": [asset["file"] for asset in assets],
            "items_rule": {"coverage": f"|delta| <= {COVERAGE_MAX_DELTA} vs the reference mask "
                                       "(not applicable above 0.80 reference coverage)",
                           "border": "alpha does not own the frame border (<= 5%)",
                           "text": "text_match recall >= 0.60 on the white composite",
                           "edge": f"alpha gradient band <= {EDGE_MAX_PX} px",
                           "time": f"<= {TIME_MAX_S} s per asset",
                           "ranking": "correct items, then mean edge width, then latency"},
            "measurements": measurement,
            "ranking": [row["model"] for row in ranking],
            "winner": ranking[0]["model"] if ranking else None,
            "birefnet_lane": lane_results.get("_lane"),
            "birefnet_error": lane_results.get("_error"),
            "ram_free_gb": ram_after}


def write_leaderboard(result: Dict[str, Any], *,
                      path: Path = DEFAULT_LEADERBOARD,
                      mirror: Optional[Path] = LEADERBOARD_MIRROR) -> Dict[str, Any]:
    """Put the editors measurement through the model scout's own leaderboard machinery."""
    import model_scout as scout  # noqa: PLC0415

    roles = scout.load_roles()
    if "editors" not in roles:
        raise KeyError("ty/model_roles.json has no `editors` role")
    leaderboard = scout.build_leaderboard(roles, result["measurements"])
    if Path(path).is_file():
        try:
            previous = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            previous = {}
        for role_name, row in leaderboard["roles"].items():
            if role_name == "editors":
                continue
            old = (previous.get("roles") or {}).get(role_name)
            if old:
                row.update(old)
    written = scout.write_leaderboard(leaderboard, path=Path(path), mirror=mirror)
    entry = leaderboard["roles"]["editors"]
    return {"written": written, "measurements": entry.get("measurements"),
            "recommendation": entry.get("recommendation")}


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", default=str(DEFAULT_REFERENCE_DIR))
    parser.add_argument("--out", default=str(DEFAULT_EVIDENCE))
    parser.add_argument("--leaderboard", default=str(DEFAULT_LEADERBOARD))
    parser.add_argument("--with-lane", action="store_true",
                        help="also measure BiRefNet through a ComfyUI lane this run owns")
    parser.add_argument("--no-write", action="store_true",
                        help="measure and print only; do not touch the leaderboard")
    parser.add_argument("--no-mirror", action="store_true")
    args = parser.parse_args(argv)

    result = bench(reference_dir=Path(args.reference_dir), with_lane=args.with_lane)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"winner": result["winner"], "ranking": result["ranking"],
                      "measurements": {name: {k: row.get(k) for k in
                                              ("status", "correct", "items", "latency_ms",
                                               "mean_edge_px")}
                                       for name, row in result["measurements"].items()},
                      "evidence": str(out)}, indent=2))
    if not args.no_write:
        written = write_leaderboard(
            result, path=Path(args.leaderboard),
            mirror=None if args.no_mirror else LEADERBOARD_MIRROR)
        print(json.dumps({"leaderboard": written["written"],
                          "recommendation": written["recommendation"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
