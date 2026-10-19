"""MOGRA logo master v2 — a clear, sharp rebuild of the supplied artwork.

"EXACTLY THE SAME THING, CLEARER AND SHARPER" is treated as a hard requirement:
nothing is redrawn, re-lettered or re-coloured - the artwork's own pixels are
keyed, upscaled in premultiplied space and edge-crisped, and the script asserts
the geometry is unchanged (mask IoU vs the source).

It also fixes a real crop defect found by measurement: the old master's
wordmark() cut (52% of height) sliced through the mortar base, so every stamp
carried a clipped slice of the emblem above the letters. The v2 crop pads the
bottom so both pipeline cuts (52% wordmark / 55% monogram) land inside the true
blank gap of the artwork.

Source of truth: the operator's supplied artwork (assets/brand/mogra_logo.png;
byte-identical to Desktop\\Mogra Organics\\logo.png and Downloads\\png).

Outputs (exports root):
  mogra_logo_master_v2.png        RGBA, ~8x, transparent paper field, crisp edges
  mogra_logo_before_after.png     side-by-side review sheet (old 4x vs new 8x)
  mogra_logo_qa.json              the measured evidence

Run (from Northstar_backend):  python refine_mogra_logo.py
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT.parent / "exports"

SOURCE = ROOT / "assets" / "brand" / "mogra_logo.png"
OPERATOR_COPY = Path(r"C:\Users\T2Hol\Downloads\png")  # same file, kept for md5 proof
OLD_MASTER = EXPORTS / "mogra_logo_master.png"

PAD = 8          # px of paper kept around the ink bbox (1x scale)
SCALE = 8        # upscale factor
KEY_DIV = 120.0  # RGB field distance that reaches full alpha
SCURVE = 1.7     # alpha ramp steepening (1.0 = none)


def md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def load_source() -> Image.Image:
    if not SOURCE.is_file():
        raise SystemExit(f"source artwork missing: {SOURCE}")
    if OPERATOR_COPY.is_file() and md5(OPERATOR_COPY) != md5(SOURCE):
        raise SystemExit("operator copy on disk differs from the repo asset - stop")
    return Image.open(SOURCE).convert("RGB")


def ink_bbox(a: np.ndarray) -> tuple[int, int, int, int]:
    lum = a.mean(axis=2)
    mx = a.max(axis=2)
    mn = a.min(axis=2)
    bg = (lum >= 232) | ((mn >= 215) & (mx - mn < 45))
    ys, xs = np.where(~bg)
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def ring_median(a: np.ndarray, r: int = 6) -> np.ndarray:
    edge = np.concatenate([a[:r].reshape(-1, 3), a[-r:].reshape(-1, 3),
                           a[:, :r].reshape(-1, 3), a[:, -r:].reshape(-1, 3)])
    return np.median(edge, axis=0)


def alpha_1x(crop: np.ndarray, field: np.ndarray) -> np.ndarray:
    d = np.max(np.abs(crop.astype(np.float64) - field[None, None, :]), axis=2)
    return np.clip(d / KEY_DIV, 0.0, 1.0)


def upscale_f(arr01: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    img = Image.fromarray((arr01 * 255).astype(np.uint8), "L")
    return np.asarray(img.resize(size, Image.LANCZOS), dtype=np.float64) / 255.0


def edge_slope(a: np.ndarray, rows: list[int]) -> float:
    """Median max |d/dx| at 0.5-crossings of the given rows - the direct
    'how steep is the ink edge' measurement (bigger = crisper)."""
    slopes = []
    for r in rows:
        prof = a[r]
        s = np.sign(prof - 0.5)
        for i in np.where(np.diff(s) != 0)[0][:80]:
            seg = prof[max(0, i - 10):i + 11]
            slopes.append(np.abs(np.diff(seg)).max())
    return float(np.median(slopes)) if slopes else 0.0


def build_master() -> tuple[Image.Image, dict]:
    """Run the full pipeline and return (master RGBA, qa dict)."""
    src = load_source()
    a = np.array(src).astype(np.float64)
    x0, y0, x1, y1 = ink_bbox(np.array(src).astype(np.int32))
    cx0, cy0 = max(0, x0 - PAD), max(0, y0 - PAD)
    cx1, cy1 = min(src.width, x1 + PAD + 1), min(src.height, y1 + PAD + 1)
    crop = a[cy0:cy1, cx0:cx1]
    h, w = crop.shape[:2]
    field = ring_median(crop.astype(np.int32))
    a1 = alpha_1x(crop, field)
    print(f"source {src.width}x{src.height}  ink bbox {x0},{y0}..{x1},{y1}")
    print(f"crop {w}x{h} at ({cx0},{cy0})  field RGB {tuple(int(v) for v in field)}")

    # ── true blank gap between emblem and wordmark (strong ink >= 0.35) ─────
    row_max = a1.max(axis=1)
    soft = np.where(row_max > 0.35)[0]
    gaps = []
    run_lo = None
    for r in range(soft.min(), soft.max() + 1):
        if row_max[r] < 0.02:
            run_lo = r if run_lo is None else run_lo
        else:
            if run_lo is not None:
                gaps.append((run_lo, r - 1))
                run_lo = None
    gap_lo, gap_hi = max(gaps, key=lambda g: g[1] - g[0])
    print(f"true blank gap rows (1x): {gap_lo}..{gap_hi}")

    # ── choose bottom pad so cuts 52% (wordmark) and 55% (monogram) land in it
    pad_bottom = None
    for b in range(0, 90):
        H1 = h + b
        c52 = int(H1 * SCALE * 0.52) / SCALE
        c55 = int(H1 * SCALE * 0.55) / SCALE
        if gap_lo <= c52 <= gap_hi and gap_lo <= c55 <= gap_hi:
            score = min(c52 - gap_lo, gap_hi - c55)
            if pad_bottom is None or score > pad_bottom[0]:
                pad_bottom = (score, b, c52, c55)
    assert pad_bottom, "no bottom pad satisfies the crop-cut invariants"
    _, pad_b, cut52, cut55 = pad_bottom
    H1 = h + pad_b
    print(f"bottom pad {pad_b}px -> 1x height {H1}; cut52={cut52:.2f} cut55={cut55:.2f} (gap {gap_lo}..{gap_hi})")

    padded = np.concatenate([crop, np.tile(field.astype(np.float64), (pad_b, w, 1))], axis=0)
    a1 = alpha_1x(padded, field)
    H8, W8 = H1 * SCALE, w * SCALE

    naive_8 = upscale_f(a1, (W8, H8))

    # premultiplied 8x upscale (no dark halos), then unpremultiply + sharpen
    prem = padded * a1[..., None]
    rgb8 = np.zeros((H8, W8, 3), dtype=np.float64)
    for c in range(3):
        ch = Image.fromarray(prem[..., c].astype(np.float32), "F").resize((W8, H8), Image.LANCZOS)
        rgb8[..., c] = np.asarray(ch, dtype=np.float64)
    a8 = naive_8.copy()
    rgb8 /= np.maximum(a8, 1e-6)[..., None]
    rgb_u8 = Image.fromarray(np.clip(rgb8, 0, 255).astype(np.uint8), "RGB")
    rgb_sharp = np.asarray(rgb_u8.filter(ImageFilter.UnsharpMask(radius=5, percent=90,
                                                                 threshold=2)), dtype=np.float64)
    a_s = np.clip((a8 - 0.5) * SCURVE + 0.5, 0.0, 1.0)

    out = np.dstack([np.clip(rgb_sharp, 0, 255).astype(np.uint8), (a_s * 255).astype(np.uint8)])
    master = Image.fromarray(out, "RGBA")

    # ── QA 1: geometry unchanged (downscale the v2 mask back to 1x) ─────────
    ds = np.asarray(master.split()[3].resize((w, H1), Image.LANCZOS), dtype=np.float64) / 255.0
    m_src, m_v2 = a1 > 0.5, ds > 0.5
    iou = float((m_src & m_v2).sum()) / float((m_src | m_v2).sum())

    # ── QA 2: edges are crisper than a plain upscale ─────────────────────────
    wm_rows = [r * SCALE + SCALE // 2 for r in range(int(cut52) + 6, H1 - 8, 3)]
    slope_ref = edge_slope(naive_8, wm_rows)
    slope_new = edge_slope(a_s, wm_rows)
    ratio = slope_new / max(1e-9, slope_ref)
    print(f"IoU vs source mask: {iou:.4f}   edge slope 8x: {slope_ref:.3f} -> {slope_new:.3f} ({ratio:.2f}x)")
    assert iou >= 0.95, f"geometry drift: IoU {iou:.4f}"
    assert ratio >= 1.20, f"no sharpness gain: {ratio:.3f}"

    qa = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(SOURCE),
        "source_md5": md5(SOURCE),
        "operator_copy_md5_match": bool(OPERATOR_COPY.is_file()),
        "crop": {"x0": cx0, "y0": cy0, "w": w, "h": h, "pad_bottom": pad_b},
        "master_size": list(master.size),
        "field_rgb": [int(v) for v in field],
        "mask_iou_vs_source": round(iou, 4),
        "edge_slope_8x_plain": round(slope_ref, 4),
        "edge_slope_8x_refined": round(slope_new, 4),
        "edge_sharpness_gain": round(ratio, 3),
        "cut52_1x_row": round(cut52, 2),
        "cut55_1x_row": round(cut55, 2),
        "gap_rows_1x": [int(gap_lo), int(gap_hi)],
        "cuts_in_gap": True,
    }
    return master, qa


def main() -> None:
    master, qa = build_master()
    EXPORTS.mkdir(parents=True, exist_ok=True)
    master_path = EXPORTS / "mogra_logo_master_v2.png"
    master.save(master_path)
    qa["master"] = str(master_path)
    print(f"saved {master_path}  {master.size[0]}x{master.size[1]}")

    # ── before/after review sheet ────────────────────────────────────────────
    if OLD_MASTER.is_file():
        old = Image.open(OLD_MASTER).convert("RGBA")
        ROW = 520

        def fit_h(im: Image.Image, hh: int) -> Image.Image:
            return im.resize((max(2, int(im.width * hh / im.height)), hh), Image.LANCZOS)

        top_old, top_new = fit_h(old, ROW), fit_h(master, ROW)
        bg = Image.new("RGB", (top_old.width + top_new.width + 180, ROW * 2 + 330), (250, 248, 242))
        bg.paste(top_old, (60, 130), top_old)
        bg.paste(top_new, (top_old.width + 120, 130), top_new)
        cut_o = int(old.height * 0.52)
        cut_n = int(master.height * 0.52)
        zoom_old = fit_h(old.crop((0, cut_o, old.width, old.height)), 230)
        zoom_new = fit_h(master.crop((0, cut_n, master.width, master.height)), 230)
        bg.paste(zoom_old, (60, ROW + 240), zoom_old)
        bg.paste(zoom_new, (top_old.width + 120, ROW + 240), zoom_new)
        d = ImageDraw.Draw(bg)
        f_c = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "PlayfairDisplay.ttf"), 46)
        f_s = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Inter.ttf"), 30)
        d.text((60, 40), "MOGRA logo master - BEFORE (plain 4x LANCZOS)", fill=(60, 60, 60), font=f_c)
        d.text((top_old.width + 120, 40), "AFTER (8x, field-keyed, edge-crisped)",
               fill=(24, 24, 26), font=f_c)
        d.text((60, ROW + 180), "the pipeline's 52% wordmark cut:", fill=(90, 90, 90), font=f_s)
        d.text((top_old.width + 120, ROW + 180), "the same cut, now inside the blank gap",
               fill=(90, 90, 90), font=f_s)
        bg.save(EXPORTS / "mogra_logo_before_after.png")
        print("saved before/after sheet")

    (EXPORTS / "mogra_logo_qa.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    print(json.dumps(qa, indent=2))


if __name__ == "__main__":
    main()
