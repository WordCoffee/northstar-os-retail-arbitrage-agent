"""Structural analysis of the MOGRA supplied artwork (no vision needed).

Prints: field colour, inner-field bounds, colour clusters (green/brown/dark),
row-band profile of the ink, and bounding boxes per cluster - so we know exactly
what the logo contains and what the bottom-52% 'wordmark' crop carries.
"""
from __future__ import annotations

import sys

import numpy as np
from PIL import Image

SRC = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\T2Hol\Downloads\png"

im = Image.open(SRC).convert("RGB")
w, h = im.size
a = np.array(im).astype(np.int32)
print(f"file: {SRC}")
print(f"size: {w} x {h}")

# field colour: median of the 8px border ring
edge = np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3),
                       a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
field = np.median(edge, axis=0)
print(f"outer field (border ring median): {field}")

# inner field: scan inward until the border colour is gone
lum = a.mean(axis=2)
inner = np.abs(a - field[None, None, :]).sum(axis=2) < 24  # True = field colour
# per-row/col: first index where NOT field
rows = ~inner.all(axis=1)
cols = ~inner.all(axis=0)
y0, y1 = np.argmax(rows), h - np.argmax(rows[::-1])
x0, x1 = np.argmax(cols), w - np.argmax(cols[::-1])
print(f"non-bordercolour content bbox: x{x0}..{x1} y{y0}..{y1}")

# ink clusters inside the content bbox
sub = a[y0:y1, x0:x1]
r, g, b = sub[..., 0], sub[..., 1], sub[..., 2]
lum_s = sub.mean(axis=2)
green = (g > r + 18) & (g > b + 18) & (lum_s < 235)
brown = (r > g + 18) & (g >= b) & (lum_s < 215)
dark = (lum_s < 140) & ~green
anyink = green | brown | dark
print(f"green px: {int(green.sum())}  brown px: {int(brown.sum())}  dark px: {int(dark.sum())}  any-ink: {int(anyink.sum())}")


def bbox(mask):
    ys, xs = np.where(mask)
    if not len(xs):
        return None
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))


for name, m in (("green", green), ("brown", brown), ("dark", dark)):
    print(f"{name} bbox: {bbox(m)}")

# row-band profile of any ink (36 buckets)
hb = h // 36 or 1
print("row profile (bucket = any-ink count, rows top->bottom):")
prof = anyink.sum(axis=1)
for i in range(0, anyink.shape[0], hb):
    band = prof[i:i + hb].sum()
    bar = "#" * int(60 * band / max(1, prof.max() * hb // 1 + 1))
    print(f"  y {i:4d}-{i + hb:4d}: {band:7d} {bar}")

# where does the 52% cut land?  (wordmark crops from y0 of the INNER image)
# replicate prepare_logo: crop 52px border then wordmark cut at 52%
inner2 = im.crop((52, 52, w - 52, h - 52))
cut = int(inner2.height * 0.52)
print(f"inner (52px inset): {inner2.size}; wordmark cut row (in inner): {cut}")
# content rows relative to inner
print(f"content bbox in inner coords: "
      f"x{x0 - 52}..{x1 - 52} y{y0 - 52}..{y1 - 52}  (inner height {inner2.height})")
