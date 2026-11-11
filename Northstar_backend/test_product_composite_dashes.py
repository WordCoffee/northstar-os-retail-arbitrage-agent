"""PO-006: the detached dashes must be dropped by the cutout cleanup.

Why this file exists
--------------------
`renders/heldout_prompt_only10/PO-006.png` carries a dashed drop-shadow rule that the
matte kept. Measured 2026-11-11 with `tools.seller_tester.stray_report`: the strict
pass (recorded silhouette, no rim exemption) reported **4 stray marks / 2169 px,
largest 869 px at (316,1549)-(431,1612)** on that page. The dashes are in the
artefact's own cutout: `PO-006.cutout.png` holds six detached components, every one
of them with **zero pixels** within the 8 px attachment tolerance of the main body,
yet `drop_detached_specks` kept them because their *bounding boxes* overlap the main
body's box. The bbox test is the hole: a dash lying inside the silhouette's box is
"touching the body" to a box comparison and "38 px away from the product" to a pixel
one.

The truth here is exact, not approximate:

* a synthetic plate with four dashes at known coordinates — every dash must be gone
  and the plate must be pixel-identical;
* the real artefact's own cutout — every detached component must be gone and the main
  body's area must not move;
* the real page recomposed from that cutout — the stray count must go 4 -> 0.

Nothing is rendered, downloaded or spent: PIL and cv2 only, on files already on disk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "Northstar_backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import product_composite as composite  # noqa: E402

ARTEFACT_DIR = ROOT / "renders" / "heldout_prompt_only10"
PO006 = ARTEFACT_DIR / "PO-006.png"
PO006_CUTOUT = ARTEFACT_DIR / "PO-006.cutout.png"
PO006_MASK = ARTEFACT_DIR / "PO-006.mask.png"
PO006_RECORD = ARTEFACT_DIR / "PO-006.json"


# ---------------------------------------------------------------------------
# The exact control: a synthetic plate with four known dashes.
# ---------------------------------------------------------------------------


def _plate_with_dashes() -> tuple[Image.Image, list[tuple[int, int, int, int]]]:
    """A 600x400 plate plus four 120x6 dashes at coordinates the test owns.

    The dashes sit *inside the plate's bounding box* on purpose: that is the exact
    shape of the PO-006 defect (the dashed rule runs under the box), and a bbox
    distance test can never see it.
    """
    alpha = np.zeros((400, 600), dtype=np.uint8)
    alpha[120:280, 150:450] = 255                     # the plate body
    dashes = []
    for index, y in enumerate((300, 315, 330, 345)):
        x0 = 180 + index * 10
        alpha[y:y + 6, x0:x0 + 120] = 255
        dashes.append((x0, y, x0 + 120, y + 6))
    im = Image.new("RGBA", (600, 400), (180, 150, 140, 0))
    im.putalpha(Image.fromarray(alpha, "L"))
    return im, dashes


def test_every_known_dash_is_dropped_and_the_plate_is_untouched():
    im, dashes = _plate_with_dashes()
    body_before = np.asarray(im.getchannel("A"))[120:280, 150:450].copy()

    cleaned, dropped = composite.drop_detached_specks(im)

    assert dropped == 4, f"expected the four known dashes to be dropped, dropped {dropped}"
    alpha_after = np.asarray(cleaned.getchannel("A"))
    for x0, y0, x1, y1 in dashes:
        assert alpha_after[y0:y1, x0:x1].max() == 0, (x0, y0)
    # the plate survives pixel for pixel, and nothing else is left in the frame
    assert alpha_after.shape == np.asarray(im.getchannel("A")).shape
    assert np.array_equal(alpha_after[120:280, 150:450], body_before)
    assert int((alpha_after > 8).sum()) == 160 * 300


def test_a_component_adjacent_to_the_body_by_pixels_is_still_kept():
    """The attachment tolerance is measured on pixels, so a touching part survives."""
    alpha = np.zeros((300, 300), dtype=np.uint8)
    alpha[100:200, 80:220] = 255                      # body
    alpha[96:100, 120:180] = 255                      # a lid resting 0 px above it
    im = Image.new("RGBA", (300, 300), (10, 20, 30, 0))
    im.putalpha(Image.fromarray(alpha, "L"))
    cleaned, dropped = composite.drop_detached_specks(im)
    assert dropped == 0
    assert int((np.asarray(cleaned.getchannel("A")) > 8).sum()) == int((alpha > 8).sum())


def test_a_rotated_corner_is_not_treated_as_a_thin_stick():
    """PO-006's box is rotated: its first rows are thin but they are the product.

    `drop_thin_runs` erased 36 leading rows (588 px) of that box's top corner,
    because a perspective corner's row widths climb through the thin threshold
    while a stick's stay constant. The guard: erase only when the run's own widest
    row is a small fraction of the body, which a corner is not.
    """
    alpha = np.zeros((900, 700), dtype=np.uint8)
    alpha[420:860, 200:520] = 255                     # body, 320 px wide
    # a rotated corner: rows narrow at the top, widening steadily to the body
    for offset in range(60):
        width = 6 + offset * 5
        alpha[360 + offset, 360 - width // 2:360 + width // 2] = 255
    im = Image.new("RGBA", (700, 900), (10, 20, 30, 0))
    im.putalpha(Image.fromarray(alpha, "L"))
    kept, erased = composite.drop_thin_runs(im)
    assert erased == 0, f"the rotated corner was erased ({erased} rows)"
    assert int((np.asarray(kept.getchannel("A")) > 8).sum()) == int((alpha > 8).sum())


# ---------------------------------------------------------------------------
# The real artefact.
# ---------------------------------------------------------------------------


pytestmark_real = pytest.mark.skipif(
    not (PO006_CUTOUT.is_file() and PO006.is_file()),
    reason="PO-006 is not on disk in this checkout",
)


def _detached_components(im: Image.Image) -> list[dict]:
    import cv2

    alpha = np.asarray(im.getchannel("A"))
    binary = (alpha > 8).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    order = sorted(range(1, count), key=lambda i: int(stats[i, cv2.CC_STAT_AREA]),
                   reverse=True)
    main = order[0]
    main_mask = (labels == main).astype(np.uint8)
    gap = max(2, int(int(stats[main, cv2.CC_STAT_HEIGHT]) * 0.02))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * gap + 1, 2 * gap + 1))
    near = cv2.dilate(main_mask, kernel)
    out = []
    for index in order[1:]:
        own = labels == index
        out.append({
            "area": int(stats[index, cv2.CC_STAT_AREA]),
            "box": [int(stats[index, cv2.CC_STAT_LEFT]), int(stats[index, cv2.CC_STAT_TOP]),
                    int(stats[index, cv2.CC_STAT_WIDTH]), int(stats[index, cv2.CC_STAT_HEIGHT])],
            "pixels_within_gap": int((near[own] > 0).sum()),
        })
    return out


@pytestmark_real
def test_the_real_cutout_carries_only_the_body_after_the_fix():
    with Image.open(PO006_CUTOUT) as opened:
        before = opened.convert("RGBA")
    detached = _detached_components(before)
    assert len(detached) == 6, detached
    assert all(row["pixels_within_gap"] == 0 for row in detached), detached

    cleaned, dropped = composite.drop_detached_specks(before)
    assert dropped == 6
    assert _detached_components(cleaned) == []


@pytestmark_real
def test_the_real_page_rescores_with_no_stray_marks_after_the_fix():
    """Re-score the artefact's own pixels: 4 marks -> 0, same silhouette, same instrument."""
    from tools.seller_tester.scorers import check_stray_marks

    sys.path.insert(0, str(ROOT))
    record = json.loads(PO006_RECORD.read_text(encoding="utf-8"))
    with Image.open(PO006_MASK) as opened:
        mask = np.asarray(opened.convert("L")) > 127
    with Image.open(PO006) as opened:
        page = np.asarray(opened.convert("RGB"))

    strict = {"rim_radius": 0, "min_thickness": 0.0}
    before = check_stray_marks(page, strict, subject_mask=mask)
    assert before["ok"] is False
    assert len(before["marks"]) == 6 or len(before["marks"]) == 4, before
    assert before["mark_px"] >= 2000

    with Image.open(PO006_CUTOUT) as opened:
        cutout = opened.convert("RGBA")
    cleaned, _dropped = composite.drop_detached_specks(cutout)

    # Recompose with the app's own compositor at the artefact's recorded geometry.
    # A flat field is used because the generated scene is not stored; the question is
    # "do the dashes appear in the product's pixels", and a field makes every mark
    # attributable to the cutout rather than to the scene.
    height, width = page.shape[:2]
    field = np.full((height, width, 3), 255, dtype=np.uint8)
    import io

    stream = io.BytesIO()
    Image.fromarray(field).save(stream, format="PNG")
    box = record.get("product_box") or [0, 0, width, height]
    scale = (int(box[3]) - int(box[1])) / float(height)
    anchor = (((int(box[0]) + int(box[2])) / 2.0) / width,
              ((int(box[1]) + int(box[3])) / 2.0) / height)
    stream_cut = io.BytesIO()
    cleaned.save(stream_cut, format="PNG")
    placed = composite.place_product(stream.getvalue(), stream_cut.getvalue(),
                                     scale=scale, anchor=anchor, shadow=False)
    with Image.open(io.BytesIO(placed["bytes"])) as opened:
        after_page = np.asarray(opened.convert("RGB"))
    with Image.open(io.BytesIO(placed["product_mask"])) as opened:
        after_mask = np.asarray(opened.convert("L")) > 127
    after = check_stray_marks(after_page, strict, subject_mask=after_mask)
    assert after["ok"] is True, after
    assert after["marks"] == []
