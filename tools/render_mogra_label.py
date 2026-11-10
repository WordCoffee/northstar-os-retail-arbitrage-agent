"""Render Mogra Organics lion's mane pouch label art: front and back.

A print-shop deliverable, not a diffusion guess. The point of the split is the one
this repo already proved: FLUX gives the photograph, typography is vector-sharp
because it is drawn here, never generated. The label is 1200x1600 px at 300 dpi
with a 44 px trim margin, so a die-cut leaflet or the flat face of a 6 oz pouch
carries it without re-keying anything.

The artwork itself lives in `Northstar_backend/mogra_label_art.py` so the product
API and this CLI render exactly the same panels. Nothing here claims a
certification the brand has not got: no organic seal, no "FDA approved", no
allergen-free badge. The supplement panel carries the owner's stated values (one
ingredient, 2 g a serving) and the standard disclaimer, and the file says DRAFT
in its own margin so it cannot be mistaken for a released label.

    python tools/render_mogra_label.py --out renders/mogra_lions_mane
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import mogra_label_art as art  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(Path("renders") / "mogra_lions_mane"))
    args = ap.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    paths = {}
    for name, img in art.panels().items():
        path = out / f"mogra_lions_mane_{name}_label.png"
        img.save(path, dpi=(art.DPI, art.DPI))
        paths[name] = str(path)

    manifest = art.manifest()
    manifest["files"] = paths
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"files": paths, "size": list(art.BASE_SIZE), "dpi": art.DPI},
                     indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
