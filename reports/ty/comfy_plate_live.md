# comfy-plate-live — real plates, for the first time

Unit: `comfy-plate-live` (queue rank 1). Rollback tag: `rollback/pre-pack01-20261111`
(same tree, same cycle).

## What changed

| item | before | now |
|---|---|---|
| render lane | `engine_status()`: *armed but unreachable at 127.0.0.1:8188* | started under `tools/comfy_lane.lane()`, which owns the GPU for the pass, starts ComfyUI with `--cache-none`, and **stops it in `finally`** — the evidence that the VRAM came back is that the process exited (this build answers `/free` with 200 and releases nothing) |
| harness `--renderer comfy` | refused every brief: the renderer returned a *scene* and `_plate` will not call a scene a plate | the comfy route no longer injects a plate at all: it calls `pp.build(design, generator=None)`, i.e. **the app's own FLUX 3 Klein text-safe lane**, so the pass measures the product |
| `lane_ready()` inside a lane | refused with *"ComfyUI is already running"* even when the running instance was the lane's own | `COMFY_LANE_OWNED=1` (set by the wrapper for its child) makes the lane accept the instance it started |
| cylinder measurement | chroma segmentation (pouch geometry) | `find_cylinder_bands`: difference from the plate's own background, then a column-profile body with hysteresis. Measured on the first real plate, the old measurement returned a **153 × 121 px patch of shadow** on a 410 px body |

New file `tools/comfy_plate_pass.py`: one real-plate pass inside one lane.

## Measured

```
python tools/comfy_plate_pass.py --limit 2 --out renders/comfy_plate2
```

| brief | category | plate | score | passed | failed checks |
|---|---|---|---|---|---|
| ST-001 | supplement_pouch | `comfy-flux3` | 70 | no | `background`, `alpha_matte` |
| ST-002 | ceramic_mug | `comfy-flux3` | **100** | **yes** | — |

First real, non-drawn product picture through the app path: a white cylinder with
the Word Coffee label warped round it, `renders/comfy_plate2/ST-002/product_front.png`.
Earlier in the same cycle a single `pp.build(..., seed=11)` on a real FLUX plate
took **72.4 s** and returned `ok=True` with a text-free plate
(`{"contains_text": false, "attempts": [1]}`).

Lane evidence: `state/gpu/comfy_lanes.jsonl` — pid started, ready in 15.6 s,
`gpu_before_work` / `gpu_after_work` snapshots, `stopped: {ok: true}`,
`gpu_after` back to 16003 MB free. After the pass: port closed, **16.0 GB VRAM
free, 7.6 GB RAM free**.

## What this measured, and what it did not

1. **A white-background brief fails on a real plate** (`ST-001`: `background`,
   `alpha_matte`). The app composites the label onto a *photograph* of the product
   on a sweep; a main-image brief wants the product cut out on 255 white. That is
   a missing product path (cutout → white canvas), not a render-lane fault.
   Filed as **D-015**.
2. **The label is under-scaled on a white body.** `find_cylinder_bands` reads the
   body's width from columns that differ from the background; on a white body
   against a pale grey sweep the right-hand columns fall below the threshold, so
   the measured width is narrower than the body and the label is drawn too small
   (`ST-002`: the label covers ~30 % of the body width). The picture still scores
   100 on its brief because the label is legible and the brief has no wrap-width
   rule — so this is a **quality** defect, not a scoring one. Filed as **D-016**.
3. **A mug is drawn as a plain cylinder.** The plate brief is per *form*, so a
   ceramic mug gets "a rigid cylindrical package" with no handle. Per-category
   plate detail is the fix; filed with D-016.
4. **The pass was limited to 2 briefs on purpose.** Each real plate is 70–90 s on
   this box, and RAM (16 GB total) is the binding constraint: with ComfyUI
   resident the app's own guard refused a second render at 2.6 GB free
   (`system_ram_insufficient: free 2601 MB, need 4096 MB`). A full 20-brief pass
   is a scheduled lane, not an interactive one.

## Tests

`python -m pytest Northstar_backend/test_package_cylinder_form.py` — **23 passed**
after the measurement change. The drawn catalog pass is unchanged:
**20 scored, 20 passed, mean 96.0**.
