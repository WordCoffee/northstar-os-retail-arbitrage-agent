import io
import sys

sys.path.insert(0, ".")
import prepress as pp  # noqa: E402
from PIL import Image  # noqa: E402

tests = {
    "cream": (243, 234, 214),
    "gold": (196, 160, 74),
    "near-black": (23, 23, 23),
    "paper-white": (255, 255, 255),
    "mid-grey": (128, 128, 128),
    "pure-green": (0, 255, 0),
    "rich-red": (200, 30, 40),
    "deep-olive": (71, 85, 58),
}
for name, rgb in tests.items():
    img = Image.new("RGB", (64, 64), rgb)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    g = pp.gamut_check(buf.getvalue())
    print(f"{name:12s} dE_max={g['max_dE76']:6.2f} mean={g['mean_dE76']:6.2f} "
          f"oog%={g['out_of_gamut_pct']:6.2f}")
