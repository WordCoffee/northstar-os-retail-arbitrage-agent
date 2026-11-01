"""PROBE T2 — framing a cutout must refuse an impossible request.

`image_prep.frame_on_white` silently accepts:
  * a `fill` outside (0, 1] — the product is upscaled past the frame and clipped,
    so a listing image ships with the product cut off;
  * an empty cutout — a blank white square is returned as if it were a product,
    while `listing_image.hero_on_white` explicitly refuses the same input with
    `ValueError('empty_subject')`.

Required behaviour:
  * fill <= 0, fill > 1 or a non-finite fill is refused
  * a fully transparent cutout is refused
  * a normal request still returns a square canvas with the product visible
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

import numpy as np
from PIL import Image

import image_prep

failures = []


def cutout(w=120, h=120, alpha=255):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    if alpha:
        box = Image.new("RGBA", (w // 2, h // 2), (30, 110, 60, alpha))
        img.alpha_composite(box, (w // 4, h // 4))
    return img


def expect_refusal(label, fn):
    try:
        value = fn()
    except ValueError as exc:
        print(f"PASS {label}: refused -> {str(exc)[:110]}")
        return
    except Exception as exc:  # noqa: BLE001
        failures.append(label)
        print(f"FAIL {label}: raised {type(exc).__name__}, wanted ValueError")
        return
    failures.append(label)
    print(f"FAIL {label}: accepted -> {getattr(value, 'size', value)}")


src = cutout()
empty = cutout(alpha=0)

expect_refusal("fill=0", lambda: image_prep.frame_on_white(src, fill=0.0, size=400))
expect_refusal("fill=-0.5", lambda: image_prep.frame_on_white(src, fill=-0.5, size=400))
expect_refusal("fill=1.5", lambda: image_prep.frame_on_white(src, fill=1.5, size=400))
expect_refusal("fill=nan", lambda: image_prep.frame_on_white(src, fill=float("nan"), size=400))
expect_refusal("empty cutout", lambda: image_prep.frame_on_white(empty, fill=0.85, size=400))

try:
    ok = image_prep.frame_on_white(src, fill=0.85, size=400)
except Exception as exc:  # noqa: BLE001
    failures.append("positive control")
    print(f"FAIL positive control raised {type(exc).__name__}: {exc}")
else:
    arr = np.asarray(ok.convert("RGBA"))
    visible = int((arr[..., 3] > 8).sum())
    if ok.size != (400, 400) or visible < 1000:
        failures.append("positive control")
        print(f"FAIL positive control size={ok.size} visible={visible}")
    else:
        print(f"PASS positive control: size={ok.size} visible_px={visible}")

# A single-pixel cutout must still be framed when it is not asking for the impossible.
tiny = cutout(4, 4)
try:
    small = image_prep.frame_on_white(tiny, fill=1.0, size=64)
    print(f"PASS boundary fill=1.0: size={small.size}")
except Exception as exc:  # noqa: BLE001
    failures.append("fill=1.0 boundary")
    print(f"FAIL fill=1.0 raised {type(exc).__name__}: {exc}")

if failures:
    print(f"\nRESULT FAIL ({len(failures)}): {failures}")
    raise SystemExit(1)
print("\nRESULT PASS")
raise SystemExit(0)
