"""Contract: a rendered image is reviewed before it can be presented.

The 2026-11-03 work order produced product pictures and a legibility gate, but
the gate was only reachable from the product-picture path: the graphics lane
(the surface Tys actually uses to show an image) returned the render directly.
This probe pins the review contract itself, independent of any caller:

* a sharp, readable label passes;
* a blurred one is refused with a named reason;
* a render that does not match the reference product photo is refused;
* a picture with nothing measurable is ``unscored`` - never ``passed``;
* a required scorer that is not configured is ``needs_review`` - never ``passed``.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from PIL import Image, ImageDraw, ImageFont, ImageFilter  # noqa: E402


def _label(blur: bool) -> Image.Image:
    img = Image.new("RGB", (900, 1200), (236, 233, 227))
    d = ImageDraw.Draw(img)
    d.text((140, 200), "MOGRA", font=ImageFont.truetype(
        r"C:\Windows\Fonts\georgiab.ttf", 110), fill=(23, 23, 23))
    d.text((140, 900), "6 oz (170 g)", font=ImageFont.truetype(
        r"C:\Windows\Fonts\segoeuib.ttf", 58), fill=(23, 23, 23))
    return img.filter(ImageFilter.GaussianBlur(6)) if blur else img


def _other() -> Image.Image:
    img = Image.new("RGB", (900, 1200), (18, 22, 28))
    ImageDraw.Draw(img).ellipse([120, 260, 780, 940], fill=(226, 190, 96))
    return img


def main() -> int:
    from ship_gate import review_image

    good = review_image(_label(False), wordmark="MOGRA", net_weight="6 oz")
    assert good["status"] == "passed" and good["deliverable"] is True, good["status"]

    bad = review_image(_label(True), wordmark="MOGRA", net_weight="6 oz")
    assert bad["status"] == "refused" and bad["reasons"], "a blurred label must be refused"

    wrong = review_image(_label(False), reference=_other())
    assert wrong["status"] == "refused", "a render that is not the product must be refused"
    assert "identity" in wrong["failed_axes"], wrong["failed_axes"]

    blank = review_image(Image.new("RGB", (640, 640), (40, 40, 40)))
    assert blank["status"] == "unscored" and blank["ok"] is False, blank["status"]

    required = review_image(_label(False), wordmark="MOGRA", net_weight="6 oz",
                            require_preference=True, use_default_scorers=False)
    assert required["status"] == "needs_review", required["status"]
    assert required["ok"] is False, "an unconfigured required scorer is never a pass"

    print("t21 image ship gate: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
