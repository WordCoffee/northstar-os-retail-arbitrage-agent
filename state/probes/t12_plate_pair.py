"""Contract: a plate with no findable pouch face is refused, never composited.

Fails today. The task `ty-plate-pair` must make it pass. This is the rule that
would have caught the flat-art delivery: if the product is not in the image,
the pipeline must say so instead of producing label art and calling it a picture.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from PIL import Image  # noqa: E402


def main() -> int:
    from mockup_compositor import find_panel_quad

    flat = Image.new("RGB", (800, 1000), (236, 233, 227))  # empty studio shot
    try:
        find_panel_quad(flat)
    except ValueError as exc:
        assert "plate_face_not_found" in str(exc), str(exc)
    else:
        raise AssertionError("a plate with no face must be refused")
    print("t12 plate pair: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
