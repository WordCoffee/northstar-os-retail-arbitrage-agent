# Backlog handoff — 2026-11-02

One operator ferry for three frozen contracts. For each task the author may read only
the listed paths, may write only the listed path, and must leave the probe untouched.
The supervisor takes the baseline, audits the changed-path set, runs the probe, and
commits task-only bytes or restores them.

---

## 1. `ty-dpi-image-guard`

**Defect:** `print_prep.dpi_report()` measures the quad and ignores `image_size`, so a
quad measured on a large render replayed against a tiny file still reports a printable
DPI — the 300 DPI print gate can be satisfied by a file that could never print.

**Objective:** raise `ValueError` when `image_size` is not two positive numbers, and
when the measured face is wider or taller than the image. A consistent pair must still
return the report.

| | |
|---|---|
| Write | `Northstar_backend/print_prep.py` |
| Read | `Northstar_backend/print_prep.py`, `state/probes/t1_dpi_image_guard.py` |
| Probe (read-only) | `python state/probes/t1_dpi_image_guard.py` — fails at HEAD |
| Commit | `fix(print): refuse a dieline quad that cannot belong to the image` |

---

## 2. `ty-frame-fill-guard`

**Defect:** `image_prep.frame_on_white()` accepts `fill` of 0, negative and >1 (the
product is scaled past the frame and clipped) and accepts a fully transparent cutout,
returning a blank white square as if it were a product.

**Objective:** `ValueError` for a non-finite fill or one outside `(0, 1]`, and for an
empty cutout; a normal cutout at fill 0.85 and 1.0 must still frame.

| | |
|---|---|
| Write | `Northstar_backend/image_prep.py` |
| Read | `Northstar_backend/image_prep.py`, `state/probes/t2_frame_fill_guard.py` |
| Probe (read-only) | `python state/probes/t2_frame_fill_guard.py` — fails at HEAD |
| Commit | `fix(image): refuse an impossible fill and an empty cutout when framing` |

---

## 3. `ty-hero-fill-guard`

**Defect:** `listing_image.hero_on_white()` accepts fill 0, negative, >1, NaN and inf,
so the MAIN image ships with the product cut off or invisible.

**Objective:** `ValueError` for a non-finite fill or one outside `(0, 1]`; keep the
empty-subject refusal and the normal path (fill 0.85 / 1.0 still returns a square PNG
with the subject visible).

| | |
|---|---|
| Write | `Northstar_backend/listing_image.py` |
| Read | `Northstar_backend/listing_image.py`, `state/probes/t3_hero_fill_guard.py` |
| Probe (read-only) | `python state/probes/t3_hero_fill_guard.py` — fails at HEAD |
| Commit | `fix(listing): refuse an impossible fill fraction on the hero image` |

---

## Not in this queue

`cost_model` (`ppc_fee`, `refund`) showed genuine boundary defects — a negative credit
count returns a refund larger than the amount paid — but fees, refunds and credit
weighting are **billing logic**, which the directive excludes. Recorded as a proposal
only, no contract.
