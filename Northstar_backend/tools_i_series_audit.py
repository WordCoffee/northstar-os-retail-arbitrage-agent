"""Overlap audit for the identity-series lockup stamps (no vision needed).

For every identity design panel (front + back) this renders it twice - with and
without the lockup stamp - and measures whether the lockup's ink intersects any
pre-existing element (type, rules, ornaments, seal). Intersections above 0.5%
of the lockup ink area are flagged for review.

Run (from Northstar_backend): python tools_i_series_audit.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import dieline_art as da  # noqa: E402
import package_designs as pd  # noqa: E402

LOGO = Path(ROOT.parent / "exports" / "mogra_logo_master_v2.png")
RAW = ROOT / "data" / "studio_generated" / "8070727f49a5401eae13a7f6a373ee5b_raw.png"
MOTIF_BOX = [198, 400, 438, 668]


def audit_pair(a_img: Image.Image, b_img: Image.Image) -> dict:
    a = np.array(a_img).astype(np.int16)
    b = np.array(b_img).astype(np.int16)
    mask = np.abs(b - a).max(axis=2) > 12          # the lockup ink itself
    n_ink = int(mask.sum())
    if n_ink == 0:
        return {"ink_px": 0, "collision_px": 0, "collision_pct": 0.0,
                "box": None, "flagged": False}
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    pad = 6
    sub = a[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad]
    px = sub.reshape(-1, 3)
    uniq, counts = np.unique(px, axis=0, return_counts=True)
    mode = uniq[counts.argmax()]                   # panel ground under the stamp
    t_ink = np.abs(sub - mode).sum(axis=2) > 36    # pre-existing template content
    t_ink_full = np.zeros(a.shape[:2], bool)
    t_ink_full[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad] = t_ink
    collision = int((t_ink_full & mask).sum())
    pct = 100.0 * collision / n_ink
    return {"ink_px": n_ink, "collision_px": collision,
            "collision_pct": round(pct, 3),
            "box": [int(x0), int(y0), int(x1), int(y1)],
            "flagged": pct > 0.5}


def main() -> None:
    logo = Image.open(LOGO).convert("RGBA")
    pd.set_logo_assets(lockup=logo)
    raw = Image.open(RAW)
    motif = da.extract_ink_motif(raw, MOTIF_BOX)
    specs = {s["key"]: s for s in pd.design_specs()}
    keys = [k for k in specs if k.startswith("i")]

    original = pd.lockup_stamp
    report = {"generated_at": datetime.now(timezone.utc).isoformat(),
              "logo": str(LOGO), "panels": {}}
    flags = []
    for key in keys:
        spec = specs[key]
        pd.lockup_stamp = lambda canvas, cx, cy, w, ink: None
        front_a = pd.BAG_FRONTS[key](logo, motif)
        back_a = pd.render_back(spec, pd.BAG_W, pd.BAG_H, logo)
        pd.lockup_stamp = original
        front_b = pd.BAG_FRONTS[key](logo, motif)
        back_b = pd.render_back(spec, pd.BAG_W, pd.BAG_H, logo)
        rf = audit_pair(front_a, front_b)
        rb = audit_pair(back_a, back_b)
        report["panels"][key] = {"front": rf, "back": rb}
        for panel, r in (("front", rf), ("back", rb)):
            status = "FLAG" if r["flagged"] else "ok"
            print(f"{key:24s} {panel:5s} ink {r['ink_px']:7d}  collision "
                  f"{r['collision_pct']:6.3f}%  {status}")
            if r["flagged"]:
                flags.append(f"{key}:{panel}")
    # a panel without any lockup ink means the stamp silently vanished
    empty = [f"{k}:front" for k in keys if report["panels"][k]["front"]["ink_px"] == 0]
    empty += [f"{k}:back" for k in keys if report["panels"][k]["back"]["ink_px"] == 0]
    report["flags"] = flags
    report["empty_stamps"] = empty
    out = ROOT.parent / "reports" / f"i_series_lockup_audit_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nflags: {flags or 'none'} | empty stamps: {empty or 'none'}")
    print(f"audit -> {out}")

    pd.lockup_stamp = original
    if empty:
        raise SystemExit("lockup missing on some panels")
    if flags:
        raise SystemExit("collisions flagged - adjust stamp sizes/anchors")


if __name__ == "__main__":
    main()
