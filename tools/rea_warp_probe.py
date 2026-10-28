"""
REA 1.1 probe — warp primitives on a synthetic cylindrical ground-truth plate.

No network, no GPU, no provider. Everything here is deterministic and local.

Purpose
-------
`pouch_label.py` measures a pouch face and `mockup_compositor.warp_panel()`
applies the panel with a single 4-point homography. A pouch face is curved, so
a homography is only exact at its four corners. This probe quantifies how wrong
that is, and how much a mesh / analytic mapping recovers, by comparing each
method against a ground-truth cylindrical projection whose parameters are known.

Outputs (JSON) are written to reports/rea_probe/warp_probe.json and every
number in reports/packaging_workflow_analysis_20261028.md comes from that file.

Run:  python tools/rea_warp_probe.py
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports" / "rea_probe"
OUT.mkdir(parents=True, exist_ok=True)

# ── Geometry: a cylindrical pouch face seen by a pinhole camera ──────────────
PANEL_W, PANEL_H = 600, 800          # the flat label panel (this is the source art)
F = 1000.0                           # focal length, px
D = 1200.0                           # distance from camera to cylinder axis, px
R = 300.0                            # cylinder radius, px
ARC = 0.90                           # arc of panel coverage, radians (~51.6 deg)
CANVAS_W, CANVAS_H = 900, 1100       # the "photo"
CX, CY = CANVAS_W / 2.0, CANVAS_H / 2.0
PLANE_H = 760.0                      # physical height of the panel in px


def theta_of(px: float) -> float:
    """Invert px = f * R sin(t) / (D - R cos(t)) for the near arc of the cylinder."""
    a, b, c = px * D, -px * R, F * R          # a + b cos t = c sin t
    amp = math.hypot(b, c)
    if amp == 0 or abs(a) > amp:
        return float("nan")
    phi = math.atan2(c, b)
    return phi - math.acos(max(-1.0, min(1.0, a / amp)))


def forward(u: float, v: float) -> tuple[float, float]:
    """Flat panel (u,v in 0..1) -> photo pixel (x,y). Ground truth."""
    t = (u - 0.5) * ARC
    y = (v - 0.5) * PLANE_H
    z = D - R * math.cos(t)
    return CX + F * R * math.sin(t) / z, CY + F * y / z


def backward(px: float, py: float) -> tuple[float, float]:
    """Photo pixel -> flat panel (u,v). Used to render the ground-truth photo."""
    t = theta_of(px - CX)
    if not math.isfinite(t):
        return float("nan"), float("nan")
    z = D - R * math.cos(t)
    u = t / ARC + 0.5
    v = (py - CY) * z / (F * PLANE_H) + 0.5
    return u, v


def make_panel() -> np.ndarray:
    """Source art: white panel, black keyline, 50 px grid, red landmarks."""
    img = Image.new("RGB", (PANEL_W, PANEL_H), (245, 245, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([4, 4, PANEL_W - 5, PANEL_H - 5], outline=(20, 20, 20), width=6)
    for x in range(50, PANEL_W, 50):
        d.line([(x, 4), (x, PANEL_H - 5)], fill=(120, 120, 120), width=1)
    for y in range(50, PANEL_H, 50):
        d.line([(4, y), (PANEL_W - 5, y)], fill=(120, 120, 120), width=1)
    for x in range(50, PANEL_W, 100):
        for y in range(50, PANEL_H, 100):
            d.ellipse([x - 6, y - 6, x + 6, y + 6], fill=(190, 30, 30))
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 46)
    except OSError:
        font = ImageFont.load_default()
    d.text((30, PANEL_H - 90), "NORTHSTAR", font=font, fill=(15, 15, 15))
    return np.array(img)


def render_truth(panel: np.ndarray) -> np.ndarray:
    """Render the photo by exact inverse mapping (no splatting, no aliasing bias)."""
    xs = np.arange(CANVAS_W, dtype=np.float32)
    ys = np.arange(CANVAS_H, dtype=np.float32)
    map_x = np.empty((CANVAS_H, CANVAS_W), np.float32)
    map_y = np.empty((CANVAS_H, CANVAS_W), np.float32)
    for j in range(CANVAS_H):
        for i in range(CANVAS_W):
            u, v = backward(xs[i], ys[j])
            map_x[j, i] = u * (PANEL_W - 1)
            map_y[j, i] = v * (PANEL_H - 1)
    photo = cv2.remap(panel, map_x, map_y, cv2.INTER_CUBIC,
                      borderMode=cv2.BORDER_CONSTANT, borderValue=(18, 18, 20))
    return photo


# ── Methods under test ───────────────────────────────────────────────────────
def homography_from_corners() -> np.ndarray:
    src = np.float32([[0, 0], [PANEL_W - 1, 0], [PANEL_W - 1, PANEL_H - 1], [0, PANEL_H - 1]])
    dst = np.float32([forward(0, 0), forward(1, 0), forward(1, 1), forward(0, 1)])
    return cv2.getPerspectiveTransform(src, dst)


def mesh_nodes(nx: int, ny: int):
    """Exact destination position for each mesh node (the mesh is *measured*)."""
    xs = np.linspace(0, PANEL_W - 1, nx)
    ys = np.linspace(0, PANEL_H - 1, ny)
    nodes = np.zeros((ny, nx, 2), np.float32)
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            u, v = x / (PANEL_W - 1), y / (PANEL_H - 1)
            nodes[j, i] = forward(u, v)
    return xs, ys, nodes


def mesh_map(nx: int, ny: int, pts_panel: np.ndarray) -> np.ndarray:
    """Bilinear interpolation of a quad mesh, evaluated at panel points."""
    xs, ys, nodes = mesh_nodes(nx, ny)
    out = np.zeros_like(pts_panel, np.float32)
    gx = np.clip(np.searchsorted(xs, pts_panel[:, 0]) - 1, 0, nx - 2)
    gy = np.clip(np.searchsorted(ys, pts_panel[:, 1]) - 1, 0, ny - 2)
    for k in range(pts_panel.shape[0]):
        i, j = gx[k], gy[k]
        fx = (pts_panel[k, 0] - xs[i]) / (xs[i + 1] - xs[i])
        fy = (pts_panel[k, 1] - ys[j]) / (ys[j + 1] - ys[j])
        p00, p10 = nodes[j, i], nodes[j, i + 1]
        p01, p11 = nodes[j + 1, i], nodes[j + 1, i + 1]
        out[k] = ((1 - fx) * (1 - fy) * p00 + fx * (1 - fy) * p10
                  + (1 - fx) * fy * p01 + fx * fy * p11)
    return out


def analytic(pts_panel: np.ndarray) -> np.ndarray:
    return np.float32([forward(x / (PANEL_W - 1), y / (PANEL_H - 1))
                       for x, y in pts_panel])


def metrics(err: np.ndarray, label: str) -> dict:
    return {
        "method": label,
        "mean_px": round(float(err.mean()), 3),
        "p50_px": round(float(np.percentile(err, 50)), 3),
        "p95_px": round(float(np.percentile(err, 95)), 3),
        "max_px": round(float(err.max()), 3),
        "mean_pct_of_canvas_width": round(float(err.mean() / CANVAS_W * 100), 4),
    }


def halo_probe() -> list[dict]:
    """
    Where does the edge halo actually come from?

    Two candidate causes:
      (a) the feather radius on the composite mask, and
      (b) the applied quad being larger than the true label face (overshoot
          "off the weld"), so panel paper is painted onto pouch pixels.

    Each candidate is swept independently. The band sampled is the 3 px strip
    just outside the TRUE face, so anything above the scene background there is
    a visible bright fringe.
    """
    scene_bg, panel_lum = 40.0, 240.0
    scene = np.full((CANVAS_H, CANVAS_W, 3), scene_bg, np.float32)
    src = np.float32([[0, 0], [PANEL_W - 1, 0], [PANEL_W - 1, PANEL_H - 1], [0, PANEL_H - 1]])
    true_dst = np.float32([forward(0, 0), forward(1, 0), forward(1, 1), forward(0, 1)])
    centre = true_dst.mean(axis=0)
    span = true_dst.max(axis=0) - true_dst.min(axis=0)

    H_true = cv2.getPerspectiveTransform(src, true_dst)
    hard = cv2.warpPerspective(np.ones((PANEL_H, PANEL_W), np.float32), H_true,
                               (CANVAS_W, CANVAS_H))
    hard = (hard > 0.5).astype(np.float32)
    band = np.zeros_like(hard)
    grown = cv2.dilate(hard, np.ones((7, 7), np.uint8), iterations=1)   # 3 px outward
    band[(grown > 0.5) & (hard < 0.5)] = 1.0

    rows = []
    for k in (0, 1, 3):
        # grow the applied quad by k px on every edge (about its centre)
        scale = np.array([1 + 2 * k / span[0], 1 + 2 * k / span[1]], np.float32)
        dst = (centre + (true_dst - centre) * scale).astype(np.float32)
        H = cv2.getPerspectiveTransform(src, dst)
        warped = cv2.warpPerspective(np.full((PANEL_H, PANEL_W, 3), panel_lum, np.float32), H,
                                     (CANVAS_W, CANVAS_H),
                                     borderMode=cv2.BORDER_CONSTANT, borderValue=(scene_bg,) * 3)
        quad = cv2.warpPerspective(np.ones((PANEL_H, PANEL_W), np.float32), H, (CANVAS_W, CANVAS_H))
        for r in (0, 2, 8):
            mask = quad if r == 0 else cv2.GaussianBlur(quad, (0, 0), r)
            comp = scene * (1 - mask[..., None]) + warped * mask[..., None]
            lum = comp.mean(axis=2)
            bleed = float((lum[band > 0.5] - scene_bg).mean())
            rows.append({
                "quad_overshoot_px": k,
                "feather_sigma_px": r,
                "bleed_outside_true_edge_lum": round(bleed, 3),
                "bleed_pct_of_panel_contrast": round(bleed / (panel_lum - scene_bg) * 100, 2),
            })
    return rows


def ocr_floor() -> dict:
    """Smallest cap height at which the local OCR engine still reads a label line."""
    try:
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
    except Exception as exc:  # pragma: no cover - dependency may be absent
        return {"status": "unavailable", "reason": type(exc).__name__}
    engine = RapidOCR()
    results = []
    for size in (10, 12, 14, 16, 18, 20, 24, 28, 32):
        img = Image.new("RGB", (760, 120), (245, 245, 240))
        d = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", size)
        except OSError:
            return {"status": "unavailable", "reason": "no truetype font"}
        d.text((12, 10), "ORGANIC LIONS MANE", font=font, fill=(15, 15, 15))
        arr = np.array(img)
        out, _ = engine(arr)
        texts = [t[1] for t in out] if out else []
        results.append({"font_px": size, "detected": bool(texts),
                        "text": texts[0] if texts else None})
    first = next((r["font_px"] for r in results if r["detected"]), None)
    return {"status": "ok", "first_detected_font_px": first, "samples": results}


def main() -> None:
    panel = make_panel()
    photo = render_truth(panel)
    Image.fromarray(panel).save(OUT / "panel_flat.png")
    Image.fromarray(photo).save(OUT / "photo_ground_truth.png")

    # Sample panel points off the mesh nodes so interpolation error is visible.
    gx, gy = np.meshgrid(np.linspace(7, PANEL_W - 8, 37), np.linspace(7, PANEL_H - 8, 49))
    pts = np.stack([gx.ravel(), gy.ravel()], axis=1).astype(np.float32)
    truth = analytic(pts)

    H = homography_from_corners()
    hp = cv2.perspectiveTransform(pts.reshape(-1, 1, 2), H).reshape(-1, 2)
    rows = [metrics(np.linalg.norm(hp - truth, axis=1), "4-point homography (today)")]
    for nx, ny in ((3, 4), (5, 7), (9, 13), (17, 25)):
        mp = mesh_map(nx, ny, pts)
        rows.append(metrics(np.linalg.norm(mp - truth, axis=1), f"quad mesh {nx}x{ny}"))
    rows.append(metrics(np.linalg.norm(analytic(pts) - truth, axis=1),
                        "analytic cylinder (ceiling, exact params)"))

    # Where does the homography hurt most: centre vs edge?
    cx0, cy0 = PANEL_W / 2, PANEL_H / 2
    r = np.linalg.norm(pts - [cx0, cy0], axis=1)
    inner = np.linalg.norm(hp - truth, axis=1)[r < np.percentile(r, 30)]
    outer = np.linalg.norm(hp - truth, axis=1)[r > np.percentile(r, 70)]

    out = {
        "probe": "rea_warp_probe",
        "date": "2026-10-28",
        "geometry": {"f": F, "D": D, "R": R, "arc_rad": ARC,
                     "arc_deg": round(math.degrees(ARC), 1),
                     "panel_px": [PANEL_W, PANEL_H], "canvas_px": [CANVAS_W, CANVAS_H]},
        "samples": int(pts.shape[0]),
        "warp_error": rows,
        "homography_error_inner30pct_mean_px": round(float(inner.mean()), 3),
        "homography_error_outer30pct_mean_px": round(float(outer.mean()), 3),
        "halo": halo_probe(),
        "ocr_floor": ocr_floor(),
    }
    (OUT / "warp_probe.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
