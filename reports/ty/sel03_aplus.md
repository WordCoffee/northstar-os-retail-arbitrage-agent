# sel-03 — A+ content on the deterministic layout stages

Branch `ty/sel-03`, worktree `state/worktrees/sel-03`. Everything below was executed in that
worktree. Nothing was merged, pushed or tagged.

## What changed

| file | change |
|---|---|
| `tools/seller_tester/aplus.py` | producer rewritten onto `deterministic.infographic`; uploads enforced in validation; recorded-cutout alpha bug fixed; seeded GrabCut; new `run_aplus_family` that produces twice and compares every hash |
| `tools/seller_tester/deterministic.py` | `infographic` gains `variant="band"` (photo panel on the product's side, copy in the opposite column), `variant="copy"` (text-only module), `copy_lines`, `copy_box`, `background`; panel geometry now sizes the panel to the crop instead of forcing the panel's aspect onto a wide subject |
| `tools/seller_tester/cli.py` | `python -m tools.seller_tester aplus` composite path for the family |
| `tools/seller_tester/__init__.py` | A+ exports |
| `ty/seller_briefs.json` | all six A+ briefs are `uploaded_reference` / `uploaded_file` on the Mogra uploads; AP-004's `lifestyle_band` is `flat`, not `generated` |
| `Northstar_backend/test_seller_tester_aplus.py` | 13 tests (below) |
| `tools/seller_tester/{composite_check,generators,harness,scorers}.py`, `deterministic.py`, `Northstar_backend/test_seller_deterministic.py`, `reports/ty/deterministic_layouts.md` | brought forward from `staging` (the deterministic stage this unit builds on) |

### Three defects found and fixed on the way

1. **The recorded cutout alpha was wrapped.** `_cutout_png` did
   `(np.asarray(cut.alpha) * 255).astype(np.uint8)` on an alpha that was already `uint8 0..255`;
   `255 * 255` wrapped to `1`. The module looked right (it used the PNG) but the product-region
   check masked almost every pixel and scored AP-001's hero **0.09** (3.6 % of the subject).
   Now the alpha is recorded as-is.
2. **The panel's aspect was forced onto a wide subject.** The old crop clamped one dimension to
   the canvas (a 948×867 crop on a 600-high page became 948×600), so `scale_x != scale_y` and the
   mapped product box was distorted. The panel is now sized to the product's own crop and the box
   maps through one uniform scale. The product is neither stretched nor cropped by the panel.
3. **GrabCut is not deterministic unseeded.** Two runs on the same upload produced different
   masks (`af7b25bc…` vs `ccfd7975…`), which broke the byte-for-byte claim. `_cutout_png` seeds
   OpenCV before GrabCut; the same upload now hashes identically in separate processes.

## Commands, with real output

```
$ python -m pytest -q Northstar_backend/test_seller_tester_aplus.py \
    Northstar_backend/test_seller_tester.py Northstar_backend/test_seller_deterministic.py
........................................................................ [ 93%]
.....                                                                    [100%]
77 passed in 28.76s
```

```
$ python -c "from tools.seller_tester.scene_render import lane_ready; print(lane_ready())"
(True, 'lane can start from C:\\Users\\T2Hol\\ComfyUI')
$ python -c "import psutil;print(round(psutil.virtual_memory().available/1e9,2),'GB free')"
7.31 GB free
```

The lane was ready and RAM was above the 3 GB floor, but the A+ path uses **no diffusion**: the
whole page is deterministic layout over the seller's upload, so the GPU was not claimed.

```
$ python -m tools.seller_tester aplus --out-dir renders/aplus \
    --summary-out state/seller/aplus_proof.json
{"brief": "AP-001", "content_type": "hero_band", "passed": true, "score": 100.0, "modules": "3/3", "deterministic": true, ...}
{"brief": "AP-002", "content_type": "comparison_table", "passed": true, "score": 100.0, "modules": "2/2", "deterministic": true, ...}
{"brief": "AP-003", "content_type": "ingredient_grid", "passed": true, "score": 100.0, "modules": "2/2", "deterministic": true, ...}
{"brief": "AP-004", "content_type": "lifestyle_band", "passed": true, "score": 100.0, "modules": "2/2", "deterministic": true, ...}
{"brief": "AP-005", "content_type": "brand_story", "passed": true, "score": 100.0, "modules": "2/2", "deterministic": true, ...}
{"brief": "AP-006", "content_type": "spec_strip", "passed": true, "score": 100.0, "modules": "3/3", "deterministic": true, ...}
{"briefs": 6, "passed": 6, "mean_score": 100.0, "modules_passed": 14, "modules_total": 14}
proof: state/seller/aplus_proof.json
```

## Per-module scores (real run)

All 14 modules scored 100.0 (`present`, `size`, `text`, and `product` where required).

| brief | module | score | layout |
|---|---|---|---|
| AP-001 | hero / sub_band / spec_strip | 100 / 100 / 100 | band / copy / copy |
| AP-002 | comparison / cta | 100 / 100 | band / copy |
| AP-003 | ingredient_grid / benefit_band | 100 / 100 | band / copy |
| AP-004 | lifestyle_band / tagline_band | 100 / 100 | band / copy |
| AP-005 | brand_story / founder_quote | 100 / 100 | copy / copy |
| AP-006 | tech_hero / spec_rows / certification | 100 / 100 / 100 | band / copy / copy |

Determinism is proved per brief, not asserted: each brief was produced a second time into a
throwaway directory. The proof records `modules_identical: true`, `page_identical: true` and the
page hash for all six. Examples: AP-001 `56e208c6…`, AP-003 `1cba8418…`, AP-006 `a31112b3…`.

Artefacts: `renders/aplus/AP-00{1..6}.png` plus one PNG per module. Proof:
`state/seller/aplus_proof.json`. Both `renders/` and `state/` are gitignored in this repo, so the
artefacts and proof exist on disk and are not in the commit; the report carries the hashes.

## Tests in `Northstar_backend/test_seller_tester_aplus.py` (13)

Brief validation: shipped family valid and all-upload; stored reference refused; non-
`uploaded_file` kind refused; product module must be `exact`; module width must match page;
duplicate module ids refused; page height must match the grid.

Producer: module produced at its declared size; same brief + upload gives identical module and
page bytes; product module with no cutout is `cannot_verify` with a reason.

Scoring: an all-pass page is 100 with correct order/count; one missing module fails the page and
is not skipped; a wrong-height page fails the page check.

## What I did NOT do

- **No diffusion scene.** AP-004's `scene: generated` became `flat`; every module is layout over
  the seller's upload. The render lane was probed and left unused.
- **No new infographic copy.** The A+ pages carry the brief's declared copy plus structural
  labels ("product guide", footer). Nothing invents a product claim. Whether the seller wants
  benefit copy in callouts is a content decision, not a renderer one.
- **No tracked uploads.** `renders/references/mogra/*` is gitignored. In a fresh checkout the A+
  briefs resolve to `cannot-verify` until the upload is present; the run above had it.
- **No full pytest suite** (another lane owns it), no merge, push or tag.
- **No dieline** — `panel_warp` is not used by A+; the dieline remains `sel-05`.
