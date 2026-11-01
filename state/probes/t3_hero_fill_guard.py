"""PROBE T3 — the listing hero must refuse an impossible fill fraction.

`listing_image.hero_on_white(fill=...)` accepts any float. With `fill > 1` the
subject is scaled beyond the canvas and cropped, so the MAIN image ships with the
product cut off; with `fill <= 0` the product vanishes. The hero lane already
refuses an empty subject, so it should refuse an impossible frame too.

Required behaviour:
  * fill <= 0, fill > 1 or a non-finite fill is refused
  * a normal request still returns a square PNG with the subject visible
"""
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "Northstar_backend"))

import numpy as np
from PIL import Image

import listing_image

failures = []


def cutout_png(w=160, h=160):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    box = Image.new("RGBA", (w // 2, h // 2), (25, 90, 55, 255))
    img.alpha_composite(box, (w // 4, h // 4))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def expect_refusal(label, fill):
    try:
        value = listing_image.hero_on_white(cutout_png(), size=256, fill=fill)
    except ValueError as exc:
        print(f"PASS {label}: refused -> {str(exc)[:110]}")
        return
    except Exception as exc:  # noqa: BLE001
        failures.append(label)
        print(f"FAIL {label}: raised {type(exc).__name__}, wanted ValueError")
        return
    failures.append(label)
    print(f"FAIL {label}: accepted -> {len(value)} bytes")


expect_refusal("fill=0", 0.0)
expect_refusal("fill=-1", -1.0)
expect_refusal("fill=1.5", 1.5)
expect_refusal("fill=nan", float("nan"))
expect_refusal("fill=inf", float("inf"))

try:
    png = listing_image.hero_on_white(cutout_png(), size=256, fill=0.85)
except Exception as exc:  # noqa: BLE001
    failures.append("positive control")
    print(f"FAIL positive control raised {type(exc).__name__}: {exc}")
else:
    im = Image.open(io.BytesIO(png)).convert("RGB")
    arr = np.asarray(im)
    non_white = int((arr.min(axis=2) < 240).sum())
    if im.size != (256, 256) or non_white < 500:
        failures.append("positive control")
        print(f"FAIL positive control size={im.size} non_white_px={non_white}")
    else:
        print(f"PASS positive control: size={im.size} non_white_px={non_white}")

try:
    edge = listing_image.hero_on_white(cutout_png(), size=128, fill=1.0)
    print(f"PASS boundary fill=1.0: {len(edge)} bytes")
except Exception as exc:  # noqa: BLE001
    failures.append("fill=1.0 boundary")
    print(f"FAIL fill=1.0 raised {type(exc).__name__}: {exc}")

if failures:
    print(f"\nRESULT FAIL ({len(failures)}): {failures}")
    raise SystemExit(1)
print("\nRESULT PASS")
raise SystemExit(0)
