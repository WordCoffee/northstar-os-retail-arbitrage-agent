"""D-019 evidence: measure "stray marks" the way a seller would, with no model.

The label-conform unit asked a local vision judge two questions of twelve prompt-only
artefacts. The second — "is the product free of stray marks?" — passed 10 of 12, and the
two failures named **page furniture** on one of them (a dashed rule, a floating ring) and
a **cutout streak** on the other.

This module answers the same question with code, and it keeps the two populations apart:

* a **photograph** is measured on the whole frame, against the product's own silhouette
  (the mask saved beside the artefact): a small, thin, detached mark is a stray;
* a **composed page** (`situation` infographic / packaging_mockup, which
  `deterministic.infographic` typesets itself) is measured **inside its photo panel**,
  with the page's rules, headings, callouts and footer outside the frame by construction.
  The panel rect is written into the layout record at generation time; a stored artefact
  without that record is reported `skipped` with the reason rather than guessed.

The proof for the composed-page rule is a fresh synthetic page — PIL only, no render lane
— scored twice: as composed (clean) and with a detached dash pasted into the panel (fails).
That is the control that keeps the fix from laundering a real stray.

    python -m tools.seller_tester.stray_report
    python -m tools.seller_tester.stray_report --dir renders/heldout_prompt_only10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from PIL import Image

from .scorers import check_stray_marks

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DIR = ROOT / "renders" / "heldout_prompt_only10"
DEFAULT_CATALOG = ROOT / "ty" / "seller_briefs_heldout_modes.json"
COMPOSED_SITUATIONS = ("infographic", "packaging_mockup")


def _briefs(path: Path) -> Dict[str, Dict[str, Any]]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {str(row.get("id")): row for row in payload.get("briefs") or []
            if isinstance(row, dict)}


def _mask_on_page(mask_path: Path, product_box: Any,
                  shape: tuple[int, int]) -> Optional[np.ndarray]:
    """The stored silhouette, mapped onto the page through the recorded product box.

    The mask is saved in the pre-layout canvas, so its own alpha box is mapped into the
    product box the record carries. Without that mapping a 2000 px page and a 2000 px
    mask happen to agree and a 4:5 page does not — which is exactly the kind of silent
    disagreement that makes a check read 0 % on a dirty picture.
    """
    try:
        with Image.open(mask_path) as opened:
            mask = np.asarray(opened.convert("L")) > 127
    except (OSError, ValueError):
        return None
    height, width = shape
    if mask.shape == (height, width):
        # Already on the artefact's own grid: the generator saved the placed silhouette,
        # so stretching it through the product box would grow it over the very marks it
        # is meant to exclude (measured 2026-11-11: PO-006's dashed streak was swallowed
        # by a mask mapped from its alpha box onto a wider product box).
        return mask
    if not isinstance(product_box, (list, tuple)) or len(product_box) != 4:
        return None
    rows, cols = np.nonzero(mask)
    if len(cols) == 0:
        return None
    mx0, mx1 = int(cols.min()), int(cols.max())
    my0, my1 = int(rows.min()), int(rows.max())
    px0, py0, px1, py1 = (int(v) for v in product_box)
    out = np.zeros((height, width), dtype=bool)
    scale_x = (px1 - px0) / max(1, (mx1 - mx0))
    scale_y = (py1 - py0) / max(1, (my1 - my0))
    xs = np.rint(px0 + (cols - mx0) * scale_x).astype(int)
    ys = np.rint(py0 + (rows - my0) * scale_y).astype(int)
    keep = (xs >= 0) & (xs < width) & (ys >= 0) & (ys < height)
    out[ys[keep], xs[keep]] = True
    return out


def measure_artefact(png: Path, brief: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """One stored artefact, measured under the rule its population calls for."""
    try:
        with Image.open(png) as opened:
            rgb = np.asarray(opened.convert("RGB"))
    except (OSError, ValueError) as exc:
        return {"brief": png.stem, "status": "unreadable", "reason": str(exc)}
    try:
        record = json.loads(png.with_suffix(".json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        record = {}
    situation = str((brief or {}).get("situation") or record.get("situation") or "")
    composed = situation in COMPOSED_SITUATIONS
    row: Dict[str, Any] = {"brief": png.stem, "situation": situation,
                           "page": list(rgb.shape[1::-1]),
                           "scope": "composed_page" if composed else "photograph"}
    if composed:
        layout = (record.get("layout") or {})
        panel = layout.get("panel")
        if not panel:
            row["status"] = "skipped"
            row["reason"] = ("this artefact was written before the layout record carried "
                             "its photo panel, so the composed-page question cannot be "
                             "measured on it; a fresh render answers it (the synthetic "
                             "page below is the same rule, measured)")
            return row
        frame = [int(panel[0]), int(panel[1]),
                 int(panel[0]) + int(panel[2]), int(panel[1]) + int(panel[3])]
    else:
        frame = None
    mask = _mask_on_page(png.with_suffix(".mask.png"), record.get("product_box"),
                         rgb.shape[:2])
    verdict = check_stray_marks(rgb, {}, subject_mask=mask, frame=frame)
    # The strict pass keeps the recorded silhouette exactly as the app saved it and applies
    # no rim exemption. Where the two disagree, the marks are *inside* the silhouette the
    # app recorded — which is a silhouette finding, not a clean picture. PO-006 is exactly
    # that case (D-019 / D-026).
    strict = check_stray_marks(rgb, {"rim_radius": 0, "min_thickness": 0.0},
                               subject_mask=mask, frame=frame)
    row.update({"status": "skipped" if verdict.get("skipped") else "measured",
                "ok": verdict.get("ok"), "mark_px": verdict.get("mark_px"),
                "marks": verdict.get("marks") or [],
                "detail": verdict.get("detail"),
                "inside_silhouette": {
                    "skipped": bool(strict.get("skipped")),
                    "marks": len(strict.get("marks") or []),
                    "mark_px": strict.get("mark_px"),
                    "detail": strict.get("detail")}})
    return row


def synthetic_page(*, dash: bool) -> Dict[str, Any]:
    """A page the harness composes itself, scored under the composed-page rule.

    The product is a drawn box on a light scene — no render lane, no GPU, deterministic.
    `dash=True` pastes a detached stroke inside the photo panel beside the product: that
    is the control. The layout's own rule, heading, callouts and footer are present in
    both pictures, so the only difference between them is the stray.
    """
    import io  # noqa: PLC0415

    from PIL import ImageDraw  # noqa: PLC0415

    from . import deterministic  # noqa: PLC0415

    width = height = 800
    scene = np.full((height, width, 3), 208, dtype=np.uint8)
    scene[:, :, 0] = 214
    box = [240, 180, 560, 640]
    scene[box[1]:box[3], box[0]:box[2]] = np.array([74, 96, 82], dtype=np.uint8)
    stream = io.BytesIO()
    Image.fromarray(scene).save(stream, format="PNG")
    brief = {"id": "SYN-D019", "situation": "infographic", "product_line": "synthetic pouch",
             "constraints": {"background": {"value": 255, "mode": "free"}}}
    laid = deterministic.infographic(stream.getvalue(), box, brief,
                                     copy_lines=["170 g of a single ingredient"])
    page = Image.open(io.BytesIO(laid["bytes"])).convert("RGB")
    panel = laid["meta"]["panel"]
    product = [int(v) for v in laid["product_box"]]
    if dash:
        draw = ImageDraw.Draw(page)
        # A detached vertical stroke beside the product, inside the panel: the margin
        # between the product and the panel edge is where a real stray would sit.
        start_y = product[1] + int(product[3] * 0.55)
        left_x = product[0] - 26
        if left_x - 6 < int(panel[0]) + 4:
            left_x = product[0] + product[2] + 14
        draw.line((left_x, start_y, left_x - 5, start_y + 34), fill=(20, 20, 20), width=5)
    rgb = np.asarray(page)
    mask = np.zeros(rgb.shape[:2], dtype=bool)
    mask[product[1]:product[1] + product[3], product[0]:product[0] + product[2]] = True
    frame = [int(panel[0]), int(panel[1]),
             int(panel[0]) + int(panel[2]), int(panel[1]) + int(panel[3])]
    verdict = check_stray_marks(rgb, {}, subject_mask=mask, frame=frame)
    return {"dash_added": dash, "panel": list(panel), "page": [rgb.shape[1], rgb.shape[0]],
            "callouts": laid["meta"].get("callouts"),
            "status": "measured", "ok": verdict.get("ok"),
            "mark_px": verdict.get("mark_px"), "marks": verdict.get("marks") or [],
            "detail": verdict.get("detail")}


def run(directory: Path = DEFAULT_DIR, catalog: Path = DEFAULT_CATALOG) -> Dict[str, Any]:
    briefs = _briefs(catalog)
    rows: List[Dict[str, Any]] = []
    for png in sorted(Path(directory).glob("*.png")):
        if ".cutout." in png.name or ".mask." in png.name:
            continue
        rows.append(measure_artefact(png, briefs.get(png.stem)))
    measured = [row for row in rows if row.get("status") == "measured"]
    flagged = [row for row in measured if row.get("ok") is False]
    inside = [{"brief": row["brief"], **(row.get("inside_silhouette") or {})}
              for row in measured if (row.get("inside_silhouette") or {}).get("marks")]
    return {
        "directory": str(directory),
        "artefacts": len(rows),
        "measured": len(measured),
        "skipped": len([row for row in rows if row.get("status") == "skipped"]),
        "clean": len(measured) - len(flagged),
        "flagged": [{"brief": row["brief"], "mark_px": row.get("mark_px"),
                     "marks": row.get("marks"), "detail": row.get("detail")}
                    for row in flagged],
        "marks_hugging_the_silhouette": inside,
        "rows": rows,
        "synthetic": {"clean_page": synthetic_page(dash=False),
                      "page_with_dash": synthetic_page(dash=True)},
        "rule": ("a photograph is measured on its frame; a composed page is measured "
                 "inside its photo panel, because its rules, headings and callout dots "
                 "are the layout, not strays"),
    }


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="D-019 stray-mark measurement (no model)")
    parser.add_argument("--dir", default=str(DEFAULT_DIR))
    parser.add_argument("--catalog", default=str(DEFAULT_CATALOG))
    parser.add_argument("--out", default=None, help="write the JSON here as well")
    parser.add_argument("--json", action="store_true")
    ns = parser.parse_args(argv)
    payload = run(Path(ns.dir), Path(ns.catalog))
    text = json.dumps(payload, indent=2)
    if ns.out:
        Path(ns.out).parent.mkdir(parents=True, exist_ok=True)
        Path(ns.out).write_text(text + "\n", encoding="utf-8")
    if ns.json:
        print(text)
    else:
        for row in payload["rows"]:
            print(f"{row['brief']:8s} {row['scope']:14s} {str(row.get('status')):9s} "
                  f"ok={row.get('ok')} marks={row.get('mark_px')} {row.get('detail', '')}")
        print(json.dumps({key: payload[key] for key in
                          ("artefacts", "measured", "skipped", "clean", "flagged")},
                         indent=2)[:2000])
        for name, row in payload["synthetic"].items():
            print(f"synthetic {name}: ok={row['ok']} marks={row['mark_px']} "
                  f"{row['detail']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
