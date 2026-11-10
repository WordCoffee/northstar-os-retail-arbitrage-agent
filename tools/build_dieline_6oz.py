"""Build the 6 oz stand-up-pouch print dieline (SVG + PDF) and a manifest.

This is the print-planning dieline, not a die: the converter's tooling is the
authority. The manifest records exactly that, plus the hash of each file.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import design_studio_print as ds  # noqa: E402

OUT = ROOT / "renders" / "mogra_lions_mane" / "print"
OUT.mkdir(parents=True, exist_ok=True)

BUILD = ds.build_from_template("doypack", {
    "width_mm": 120.0, "height_mm": 180.0, "gusset_mm": 70.0,
    "fill_g": 170.0, "bleed_mm": 3.0, "safe_mm": 5.0,
})
SVG = ds.render_svg(BUILD).encode("utf-8")
PDF = ds.render_pdf(BUILD)

svg_path = OUT / "dieline_6oz.svg"
pdf_path = OUT / "dieline_6oz.pdf"
svg_path.write_bytes(SVG)
pdf_path.write_bytes(PDF)
manifest = {
    "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "template": "doypack",
    "params": {"width_mm": 120.0, "height_mm": 180.0, "gusset_mm": 70.0,
               "fill_g": 170.0, "bleed_mm": 3.0, "safe_mm": 5.0},
    "files": [
        {"path": str(svg_path.relative_to(ROOT)).replace("\\", "/"),
         "bytes": len(SVG), "sha256": hashlib.sha256(SVG).hexdigest()},
        {"path": str(pdf_path.relative_to(ROOT)).replace("\\", "/"),
         "bytes": len(PDF), "sha256": hashlib.sha256(PDF).hexdigest()},
    ],
    "confidence": (BUILD.get("meta") or {}).get("confidence"),
    "note": ("Planning dieline. The converter's die is the authority. "
             "Nutrition values and UPC/GTIN are not present on this geometry; "
             "they belong to the label panel and still need official values."),
    "status": "dieline_ready_data_blocked",
}
(OUT / "dieline_manifest.json").write_text(json.dumps(manifest, indent=2),
                                          encoding="utf-8")
print(json.dumps({"svg": str(svg_path), "pdf": str(pdf_path),
                  "manifest": str(OUT / "dieline_manifest.json"),
                  "pdf_bytes": len(PDF)}, indent=2))
