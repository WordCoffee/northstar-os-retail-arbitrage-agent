"""Contract: composite a designed panel onto a photographed pouch face.

Fails today. The task `ty-pouch-mockup` must make it pass.

The synthetic plate stands in for a FLUX pouch photo: a light studio background
with a quad the colour of kraft paper. A panel with a known ink block is warped
onto that quad; the test then checks the three things that were wrong with the
flat-art deliverable:

  * the output is the plate's size (a panel is not a product picture),
  * the panel's corners land ON the quad (sub-pixel registration),
  * nothing outside the quad is painted (the photograph survives).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from PIL import Image, ImageDraw  # noqa: E402

QUAD = [(200, 150), (600, 170), (590, 880), (210, 860)]


def _plate() -> Image.Image:
    img = Image.new("RGB", (800, 1000), (236, 233, 227))
    d = ImageDraw.Draw(img)
    d.polygon(QUAD, fill=(213, 167, 122))
    return img


def _panel() -> Image.Image:
    img = Image.new("RGBA", (400, 600), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([6, 6, 393, 593], fill=(247, 243, 235, 255))
    d.rectangle([40, 60, 360, 150], fill=(23, 23, 23, 255))
    return img


def main() -> int:
    from mockup_compositor import composite_panel_onto_quad

    plate = _plate()
    before = plate.copy()
    out = composite_panel_onto_quad(plate, _panel(), QUAD)

    assert out.size == plate.size, f"output must be the plate size, got {out.size}"
    px = out.load()
    # corners must be panel stock, not background
    for (x, y) in QUAD:
        near = px[min(max(x, 0), 799), min(max(y, 0), 999)]
        assert sum(near[:3]) > 500, f"corner {(x, y)} was not painted: {near}"
    # far outside the quad the photograph must be untouched
    for (x, y) in ((20, 20), (780, 980), (780, 20), (20, 980)):
        assert px[x, y][:3] == before.load()[x, y][:3], f"painted outside the quad at {(x, y)}"
    print("t10 pouch mockup: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
