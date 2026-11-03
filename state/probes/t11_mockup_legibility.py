"""Contract: a product picture that cannot be read is not a product picture.

Fails today. The task `ty-mockup-legibility` must make it pass.

The flat-art deliverable looked like a form. The measurable half of "looks good"
is that the wordmark and the net weight survive the composite and the output is
not soft: OCR reads them, and a deliberately blurred copy is refused instead of
shipped.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from PIL import Image, ImageDraw, ImageFont, ImageFilter  # noqa: E402


def _picture(blur: bool) -> Image.Image:
    img = Image.new("RGB", (1200, 1600), (236, 233, 227))
    d = ImageDraw.Draw(img)
    d.rectangle([120, 120, 1080, 1480], fill=(247, 243, 235))
    f = ImageFont.truetype(r"C:\Windows\Fonts\georgiab.ttf", 120)
    d.text((180, 300), "MOGRA", font=f, fill=(23, 23, 23))
    f2 = ImageFont.truetype(r"C:\Windows\Fonts\segoeuib.ttf", 64)
    d.text((180, 1200), "6 oz (170 g)", font=f2, fill=(23, 23, 23))
    return img.filter(ImageFilter.GaussianBlur(6)) if blur else img


def main() -> int:
    from mockup_quality import assert_legible

    good = assert_legible(_picture(False))
    assert good["ok"] is True, good
    assert "MOGRA" in " ".join(good["words"]).upper(), good["words"]

    bad = assert_legible(_picture(True))
    assert bad["ok"] is False and bad["reason"], "a blurred picture must be refused with a reason"
    print("t11 mockup legibility: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
