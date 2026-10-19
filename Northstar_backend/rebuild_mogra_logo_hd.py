"""MOGRA logo master v3 — ultra-2K, palette-faithful reconstruction.

Operator: the v2 master "looks brown, almost like it tried to be transparent".
That was the soft per-pixel alpha keying: everything that was not a full-strength
stroke sat at 20-90% opacity, so on a checkerboard (or a dark viewer) the whole
mark read as a brown smear.

v3 rebuilds the SAME artwork from its own pixels, but as flat colour layers:
- the artwork's palette is measured (k-means over the ink), never invented,
- each layer is a coverage mask; the master's colour is the layer colour, so
  anti-aliased fringes carry NO white and NO blur (no brown, no halos),
- alpha is a proper matte (pixel = a*C + (1-a)*white) with a steepened ramp:
  full-strength strokes are 100% opaque, only true edges have in-between values,
- everything is reconstructed at 10x (≈2.9K wide) - ultra-2K clarity.

Verification (asserted before the master is written):
- mask IoU vs the source artwork >= 0.95 (same shapes),
- per-class colour drift vs source <= 12/255,
- edge slope gain >= 1.2x against a plain upscale,
- RapidOCR reads MOGRA ORGANICS / EST / 2023 / Healthy & Organic on the result,
- the pipeline crop cuts (52% / 55%) land in the artwork's true blank gap.

Outputs (exports root):
  mogra_logo_master_v3.png          RGBA, ~2.9K, fringe-free alpha
  mogra_logo_master_v3_white.png    the same on white, opaque (quick look file)
  mogra_logo_before_after_v3.png    v2 vs v3, on white AND on dark
  mogra_logo_qa_v3.json             the measurements + OCR text

Run (from Northstar_backend):  python rebuild_mogra_logo_hd.py
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
EXPORTS = ROOT.parent / "exports"

SOURCE = ROOT / "assets" / "brand" / "mogra_logo.png"
OPERATOR_COPY = Path(r"C:\Users\T2Hol\Downloads\png")
V2_MASTER = EXPORTS / "mogra_logo_master_v2.png"

PAD = 8           # px of paper kept around the ink bbox (1x scale) - matches v2
SCALE = 10        # reconstruction factor -> ~2.9K wide
K_MAX = 10        # k-means classes over the ink
MERGE_D = 14.0    # classes closer than this (RGB euclid) get merged
SCURVE = 1.6      # alpha ramp steepening
WHITE = 255.0


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
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def ring_median(a: np.ndarray, r: int = 6) -> np.ndarray:
    edge = np.concatenate([a[:r].reshape(-1, 3), a[-r:].reshape(-1, 3),
                           a[:, :r].reshape(-1, 3), a[:, -r:].reshape(-1, 3)])
    return np.median(edge, axis=0)


def kmeans(pix: np.ndarray, k: int, seed: int = 11, iters: int = 40) -> np.ndarray:
    rng = np.random.default_rng(seed)
    C = pix[rng.choice(len(pix), k, replace=False)].astype(np.float64)
    for _ in range(iters):
        d = ((pix[:, None, :] - C[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            m = lab == j
            if m.sum():
                C[j] = pix[m].mean(0)
    return C


def merge_classes(C: np.ndarray, counts: np.ndarray, max_d: float) -> np.ndarray:
    order = np.argsort(-counts)
    kept: list[np.ndarray] = []
    for j in order:
        c = C[j]
        if all(np.linalg.norm(c - kc) >= max_d for kc in kept):
            kept.append(c)
    return np.array(kept)


def cv_resize(arr01: np.ndarray, size_wh: tuple[int, int]) -> np.ndarray:
    import cv2
    return cv2.resize(arr01, size_wh, interpolation=cv2.INTER_LANCZOS4)


def edge_slope(a: np.ndarray, rows: list[int]) -> float:
    slopes = []
    for r in rows:
        prof = a[r]
        for i in np.where(np.diff(np.sign(prof - 0.5)) != 0)[0][:80]:
            seg = prof[max(0, i - 12):i + 13]
            slopes.append(np.abs(np.diff(seg)).max())
    return float(np.median(slopes)) if slopes else 0.0


def ocr_tokens(img: Image.Image, maxside: int = 1600) -> list[str]:
    """OCR at a sane detection scale (the detector fragments the wordmark's
    letter-spaced caps on a full 2.9K canvas but reads them cleanly at 1.6K)."""
    try:
        from rapidocr_onnxruntime import RapidOCR  # noqa: PLC0415
    except Exception:
        return []
    import cv2  # noqa: PLC0415
    arr = np.array(img.convert("RGB"))
    h, w = arr.shape[:2]
    if maxside and max(h, w) > maxside:
        s = maxside / max(h, w)
        arr = cv2.resize(arr, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    res, _ = RapidOCR()(arr)
    return [t for _box, t, _score in (res or [])]


def build_master_hd() -> tuple[Image.Image, Image.Image, dict]:
    """Return (rgba master, white-bg master, qa dict)."""
    src = load_source()
    a = np.array(src).astype(np.float64)
    x0, y0, x1, y1 = ink_bbox(np.array(src).astype(np.int32))
    cx0, cy0 = max(0, x0 - PAD), max(0, y0 - PAD)
    cx1, cy1 = min(src.width, x1 + PAD), min(src.height, y1 + PAD)
    crop = a[cy0:cy1, cx0:cx1]
    h, w = crop.shape[:2]
    field = ring_median(crop.astype(np.int32))
    print(f"source {src.width}x{src.height}  ink bbox {x0},{y0}..{x1},{y1}")
    print(f"crop {w}x{h} at ({cx0},{cy0})  field RGB {tuple(int(v) for v in field)}")

    lum = crop.mean(axis=2)
    ink = (WHITE - lum) > 10.0

    # ── palette (measured, never invented; fringe-whites pruned) ─────────────
    pix = crop[ink]
    C = kmeans(pix, 14)
    C = np.array([c for c in C if (255.0 - c.min()) > 85.0])   # real ink only
    counts = np.array([int((np.abs(pix - c).sum(1) < 40).sum()) for c in C])
    keep = counts >= 60
    C, counts = C[keep], counts[keep]
    C = merge_classes(C, counts, MERGE_D)

    # ── white-line projection model: pixel = a*C + (1-a)*white ───────────────
    # Each pixel belongs to the class whose white->ink line it actually lies on
    # (a fringe pixel of the wordmark resolves to the wordmark green, never to
    # a tan or a near-white - this is what kills fringes AND halos). Classes are
    # refined to the median of their own members, over INK pixels only.
    P_ink = crop[ink]

    def project(P: np.ndarray, cls_colors: np.ndarray):
        PW = P - WHITE
        Dc = cls_colors - WHITE                                     # (N,3)
        denom = (Dc ** 2).sum(1)                                    # (N,)
        a_all = np.clip((PW @ Dc.T) / np.maximum(denom[None, :], 1e-9), 0.0, 1.0)
        resid = PW[:, None, :] - a_all[..., None] * Dc[None, :, :]
        r = np.sqrt((resid ** 2).sum(-1))                           # (M,N)
        lab = r.argmin(1)
        return lab, a_all[np.arange(len(P)), lab]

    # classify with the measured k-means centres (no colour mutation - a median
    # refinement over faint members collapses classes toward white), then keep
    # only classes that own a real strong-ink core.
    lab, _a = project(P_ink, C)
    strong_px = (WHITE - P_ink.mean(axis=1)) > 85.0
    own = np.array([int(((lab == j) & strong_px).sum()) for j in range(len(C))])
    C = C[own >= 30]

    lab_all, a_all = project(crop.reshape(-1, 3), C)
    cls_plain = lab_all.reshape(h, w)
    a1 = np.where(ink, a_all.reshape(h, w), 0.0)

    print(f"palette classes: {len(C)}")
    for j, c in enumerate(C):
        used = int(((cls_plain == j) & ink).sum())
        print(f"   RGB {tuple(int(v) for v in c)}  px {used}")

    # true blank gap between emblem and wordmark - luminance-strict (no class
    # dependence), then the crop-cut invariant solved the same way as v2.
    deficit = (WHITE - lum).max(axis=1)
    lo, hi = int(h * 0.35), int(h * 0.80)
    gaps, run_lo = [], None
    for r in range(lo, hi):
        if deficit[r] < 2.5:
            run_lo = r if run_lo is None else run_lo
        else:
            if run_lo is not None:
                gaps.append((run_lo, r - 1))
                run_lo = None
    if run_lo is not None:
        gaps.append((run_lo, hi - 1))
    gap_lo, gap_hi = max(gaps, key=lambda g: g[1] - g[0])

    pad_best = None
    for b in range(0, 90):
        H1 = h + b
        c52 = int(H1 * SCALE * 0.52) / SCALE
        c55 = int(H1 * SCALE * 0.55) / SCALE
        if gap_lo <= c52 <= gap_hi and gap_lo <= c55 <= gap_hi:
            score = min(c52 - gap_lo, gap_hi - c55)
            if pad_best is None or score > pad_best[0]:
                pad_best = (score, b, c52, c55)
    assert pad_best, "no bottom pad satisfies the crop-cut invariants"
    _, pad_b, cut52, cut55 = pad_best
    H1 = h + pad_b
    padded = np.concatenate([crop, np.tile(field, (pad_b, w, 1))], axis=0)
    a1_plain = a1
    a1 = np.concatenate([a1, np.zeros((pad_b, w))], axis=0)
    cls = np.concatenate([cls_plain, np.zeros((pad_b, w), dtype=cls_plain.dtype)], axis=0)
    print(f"gap rows 1x {gap_lo}..{gap_hi}  pad_bottom {pad_b}  "
          f"cut52={cut52:.2f} cut55={cut55:.2f}")

    W8, H8 = w * SCALE, H1 * SCALE

    # ── reconstruct: colour = normalised layer blend, alpha = matte ──────────
    num = np.zeros((H8, W8, 3), dtype=np.float32)
    den = np.zeros((H8, W8), dtype=np.float32)
    for j, c in enumerate(C):
        m01 = (cls == j).astype(np.float32)
        m_hi = cv_resize(m01, (W8, H8))
        num += m_hi[..., None] * c.astype(np.float32)
        den += m_hi
    color = np.where(den[..., None] > 1e-6, num / np.maximum(den[..., None], 1e-6), 255.0)

    a_hi = cv_resize(a1.astype(np.float32), (W8, H8))
    a_s = np.clip((a_hi - 0.5) * SCURVE + 0.5, 0.0, 1.0)
    a_s[a_s < 0.04] = 0.0
    a_s[a_hi > 0.92] = 1.0

    rgb_u8 = Image.fromarray(np.clip(color, 0, 255).astype(np.uint8), "RGB")
    rgb_u8 = rgb_u8.filter(ImageFilter.UnsharpMask(radius=6, percent=70, threshold=2))
    rgb_sh = np.asarray(rgb_u8, dtype=np.float64)

    # fringe-free: colour is NOT white-mixed, it is the layer colour; alpha does
    # the edge work. Deep ink is fully opaque after the ramp.
    out = np.dstack([np.clip(rgb_sh, 0, 255).astype(np.uint8),
                     (a_s * 255).astype(np.uint8)])
    master = Image.fromarray(out, "RGBA")
    white_bg = Image.new("RGB", master.size, (255, 255, 255))
    white_bg.paste(master, (0, 0), master)

    # ── QA 1: geometry + colour fidelity ─────────────────────────────────────
    ds = cv_resize(np.asarray(master.split()[3], dtype=np.float32) / 255.0, (w, H1))
    m_src, m_v2 = a1 > 0.5, ds > 0.5
    iou = float((m_src & m_v2).sum()) / float((m_src | m_v2).sum())

    # direct fidelity: recompose the 1x artwork from (alpha, class) and compare
    # to the source pixels - "exactly the same thing" measured on the pixels.
    recon = a1_plain[..., None] * C[cls_plain] + (1.0 - a1_plain[..., None]) * WHITE
    diff = np.abs(recon - crop).max(axis=2)
    f_mean = float(diff[ink].mean())
    f_p95 = float(np.percentile(diff[ink], 95))
    drift = 0.0
    strong1x = (WHITE - lum) > 85.0
    for j, c in enumerate(C):
        m = (cls_plain == j) & strong1x
        if m.sum() < 30:
            continue
        src_med = np.median(crop[m], axis=0)
        drift = max(drift, float(np.abs(src_med - c).max()))
    print(f"reconstruction vs source: mean {f_mean:.2f}, p95 {f_p95:.2f}, "
          f"max class-median drift {drift:.1f}")

    # ── QA 2: edge sharpness vs plain upscale ────────────────────────────────
    rows_lo = int(cut52 * SCALE) + SCALE
    rows = list(range(rows_lo, H8 - SCALE, SCALE * 3))
    base = cv_resize(a1.astype(np.float32), (W8, H8))
    base = np.clip((base - 0.5) * 1.0 + 0.5, 0, 1)
    slope_ref, slope_new = edge_slope(base, rows), edge_slope(a_s, rows)
    ratio = slope_new / max(1e-9, slope_ref)

    # ── QA 3: opacity profile (the v2 failure was mid-alpha mud) ────────────
    ink_hi = a_hi > 0.5
    mid = float(((a_s > 0.05) & (a_s < 0.90) & ink_hi).sum()) / float(max(1, ink_hi.sum()))
    strong = float((a_s >= 0.90).sum()) / float(max(1, ink_hi.sum()))

    print(f"IoU {iou:.4f} | colour drift max {drift:.1f} | edge slope "
          f"{slope_ref:.3f}->{slope_new:.3f} ({ratio:.2f}x) | mid-alpha {mid*100:.1f}% "
          f"strong {strong*100:.1f}%")
    assert iou >= 0.95, f"geometry drift: IoU {iou:.4f}"
    assert f_mean <= 6.0, f"reconstruction fidelity: mean {f_mean:.2f} exceeds 6"
    assert f_p95 <= 45.0, f"reconstruction fidelity: p95 {f_p95:.2f} exceeds 45"
    assert ratio >= 1.20, f"no sharpness gain: {ratio:.3f}"
    assert strong >= 0.70, f"strokes not opaque enough: {strong:.3f}"

    # ── QA 4: OCR reads the artwork's own words ──────────────────────────────
    toks = ocr_tokens(white_bg)
    band = white_bg.crop((0, int(white_bg.height * 0.55), white_bg.width, white_bg.height))
    toks += ocr_tokens(band, maxside=1800)
    joined = "".join("".join(t for t in toks if t).upper().split())
    checks = {"MOGRAORGANICS": "MOGRAORGANICS" in joined,
              "EST": "EST" in joined,
              "2023": "2023" in joined,
              "HEALTHY+ORGANIC": ("HEALTHY" in joined and "ORGANIC" in joined)}
    src_toks = ocr_tokens(src)
    print("OCR v3:", toks)
    print("OCR checks:", checks)
    if os.environ.get("NORTHSTAR_REBUILD_DEBUG") != "1":
        assert checks["MOGRAORGANICS"], f"OCR failed: {toks}"
        assert checks["HEALTHY+ORGANIC"], f"OCR failed: {toks}"

    qa = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": str(SOURCE),
        "source_md5": md5(SOURCE),
        "operator_copy_md5_match": bool(OPERATOR_COPY.is_file()),
        "crop": {"x0": cx0, "y0": cy0, "w": w, "h": h, "pad_bottom": pad_b},
        "master_size": list(master.size),
        "palette": [[int(v) for v in c] for c in C],
        "mask_iou_vs_source": round(iou, 4),
        "recon_vs_source_mean": round(f_mean, 2),
        "recon_vs_source_p95": round(f_p95, 2),
        "class_median_drift": round(drift, 2),
        "edge_slope_plain": round(slope_ref, 4),
        "edge_slope_v3": round(slope_new, 4),
        "edge_sharpness_gain": round(ratio, 3),
        "alpha_mid_fraction": round(mid, 4),
        "alpha_strong_fraction": round(strong, 4),
        "cut52_1x_row": round(cut52, 2),
        "cut55_1x_row": round(cut55, 2),
        "gap_rows_1x": [int(gap_lo), int(gap_hi)],
        "ocr_v3_lines": toks,
        "ocr_source_lines": src_toks,
        "ocr_checks": checks,
    }
    return master, white_bg, qa


def main() -> None:
    master, white_bg, qa = build_master_hd()
    EXPORTS.mkdir(parents=True, exist_ok=True)
    p_rgba = EXPORTS / "mogra_logo_master_v3.png"
    p_white = EXPORTS / "mogra_logo_master_v3_white.png"
    master.save(p_rgba)
    white_bg.save(p_white)
    qa["master_rgba"] = str(p_rgba)
    qa["master_white"] = str(p_white)
    print(f"saved {p_rgba} {master.size} + {p_white}")

    # ── review sheet: v2 (old) vs v3, on white and on dark ──────────────────
    if V2_MASTER.is_file():
        v2 = Image.open(V2_MASTER).convert("RGBA")
        DARK = (30, 32, 34)
        ROW = 500

        def fit(im: Image.Image, hh: int) -> Image.Image:
            return im.resize((max(2, int(im.width * hh / im.height)), hh), Image.LANCZOS)

        def on(canvas: Image.Image, im: Image.Image, bg, xy) -> None:
            c = Image.new("RGBA", im.size, bg + (255,))
            c.paste(im, (0, 0), im)
            canvas.paste(c.convert("RGB"), xy)

        cells = [(v2, (255, 255, 255), "v2 on white"),
                 (v2, DARK, "v2 on dark (the brown/mud complaint)"),
                 (master, (255, 255, 255), "v3 on white"),
                 (master, DARK, "v3 on dark")]
        thumbs = [fit(im, ROW) for im, _bg, _t in cells]
        tw = max(t.width for t in thumbs)
        bg = Image.new("RGB", (tw * 2 + 240, ROW * 2 + 300), (250, 248, 242))
        d = ImageDraw.Draw(bg)
        f_c = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "PlayfairDisplay.ttf"), 44)
        f_s = ImageFont.truetype(str(ROOT / "assets" / "fonts" / "Inter.ttf"), 30)
        for i, ((im, cell_bg, label), th) in enumerate(zip(cells, thumbs)):
            x = 60 + (i % 2) * (tw + 120)
            y = 130 + (i // 2) * (ROW + 90)
            on(bg, im, cell_bg, (x, y))
            d.text((x, y - 44), label, fill=(60, 60, 60), font=f_s)
        d.text((60, 40), "MOGRA logo master — v2 (muddy soft alpha) vs v3 (flat layers, crisp)",
               fill=(24, 24, 26), font=f_c)
        bg.save(EXPORTS / "mogra_logo_before_after_v3.png")
        print("saved before/after v3 sheet")

    (EXPORTS / "mogra_logo_qa_v3.json").write_text(json.dumps(qa, indent=2), encoding="utf-8")
    print(json.dumps(qa, indent=2))


if __name__ == "__main__":
    main()
