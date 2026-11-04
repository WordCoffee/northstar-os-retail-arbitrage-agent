"""Contract: the two scorers are installed, they run, and the gate uses them.

PickScore (prompt adherence) and HPSv2 (human preference) are local CPU models
run one axis at a time in a child process (both resident measured 6.4 GB on this
16 GB box). This probe fails, rather than skips, when the runtime or the weights
are missing: an uninstalled scorer must not look like a configured one.

Proof it is really wired: on a legible label with the `product_picture` surface,
the gate must reach a verdict (`passed` or `refused`) - never `needs_review`
(no scorer configured) or `unscored` (nothing blocking measured) - and both
score axes must carry a number.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402


def _label() -> Image.Image:
    img = Image.new("RGB", (900, 1200), (236, 233, 227))
    d = ImageDraw.Draw(img)
    d.rectangle([80, 80, 820, 1120], fill=(247, 243, 235))
    d.text((140, 200), "MOGRA", font=ImageFont.truetype(
        r"C:\Windows\Fonts\georgiab.ttf", 110), fill=(23, 23, 23))
    d.text((140, 900), "6 oz (170 g)", font=ImageFont.truetype(
        r"C:\Windows\Fonts\segoeuib.ttf", 58), fill=(23, 23, 23))
    return img


def main() -> int:
    import image_review_scorers as scorers
    from ship_gate import review_image

    ready = scorers.available()
    assert ready["ok"] is True, f"scorers not installed: {ready['detail']}"
    assert all(ready["deps"].values()), ready["deps"]
    assert all(ready["files"].values()), ready["files"]

    report = review_image(
        _label(), brief="a product photograph of a kraft coffee pouch",
        wordmark="MOGRA", net_weight="6 oz", surface="product_picture")

    assert report["status"] in ("passed", "refused"), report["status"]
    assert not report["required_unavailable"], report["required_unavailable"]
    preference = report["axes"]["preference"]
    adherence = report["axes"]["adherence"]
    assert isinstance(preference.get("score"), float), preference
    assert isinstance(adherence.get("score"), float), adherence
    assert -1.0 < preference["score"] < 1.0, preference
    assert 0.0 < adherence["score"] < 40.0, adherence

    print(f"t22 image scorers: OK - preference {preference['score']} "
          f"adherence {adherence['score']} -> {report['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
