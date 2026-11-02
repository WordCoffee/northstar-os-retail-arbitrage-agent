# A → E: Multimodal Lanes, Discovery Queue and the 3D Handoff

**Campaign:** `multimodal-architecture-a-to-e`
**Date:** 2026-11-02
**Author:** DeepSeek V4.1 Flash (opencode-go, operator session) · local: ComfyUI, `qwen3.5:4b`, `rapidocr`
**Instruction:** the operator asked for A through E explicitly; the previous 2-unit cap is superseded.
**Downloads: 1** — the SD1.5 base checkpoint relight needs, recorded in `provenance.csv`.
Everything else runs on weights already on this disk.

---

## VERDICT

**PARTIALLY READY — four of five items are complete and verified live; E is a tested contract whose
two dependencies are absent.**

| | Item | State |
|---|---|---|
| **A** | Shorts / Reels motion (9:16) | **Complete** — Wan 2.2 TI2V 5B, live clip, frame-gated, packaged |
| **B** | Cutout + relight | **Complete** — cutout verified (3.7 s); relight now works after the base-checkpoint bug was found (`c4adefa5`, follow-up commit) |
| **C** | Print master at 300 DPI | **Complete** — Real-ESRGAN 4×, measured 1040 DPI at 100 mm, manifest carries a real dieline block |
| **D** | Autonomous discovery | **Complete as a proposal queue** — never installs; a test asserts it |
| **E** | 3D generation + Blender bake | **Contract complete, generation/bake blocked** — no 3D pack, no Blender on this machine, and both are named |

The honest summary: the *creative* half of the brief is real and running (still, print, motion,
relight, cutout), the *autonomy* half is deliberately narrower than asked (no auto-install), and
the *3D* half needs a 3D pack and Blender, neither of which is installed.

---

## PER-ITEM BREAKDOWN

### A — Shorts motion (`f445fbf5`)

**Purpose.** Vertical motion, the objective left open last campaign. The weights were already here:
`Wan2.2-TI2V-5B-Q5_K_M.gguf` (3.5 GB) + `umt5` encoder + `wan2.2_vae`.

**Steps (4).** `shorts.py` graph builder → `POST /api/design-studio/shorts` → frame sampling for
the gate → package with the clip, the frames and the manifest.

**Design decisions.** Frame count snaps to Wan's `4n+1` lattice (a wrong count is a silent latent
crop). Three frames are kept — first, middle, last — because a collapsed clip shows at the ends.
`form` is not-applicable for a clip, since the container was verified before the render.

**Self-review catches (3).** A clip that "ran" is not a clip that shipped → the middle frame goes
through the same five-axis gate. A video with no frames to check cannot be gated → the graph writes
`SaveImage` alongside `SaveWEBM`. And a real bug: the first packaged clip's manifest said
`form: fail` in the axes while the verdict said `not_applicable` — the same document contradicting
itself. Fixed at the source in `quality_gate.score` (empty requested form → not-applicable) and
the clip re-rendered. The regenerated manifest now reads
`form: {status: not_applicable, reason: no_form_requested, observed: pouch}` — one statement, not two.

**Live.** 480×832, 17 frames, 16 fps, **46.2 s** render, verdict 2/2, folder
`state/deliverables/short_1793631223`. The frames are a genuine product shot: noise metric 4.6
versus 3.6 for a still render, and a mean absolute difference of 21.97 between frame 0 and frame 2
— it moves.

### B — Cutout + relight (`c4adefa5`, follow-up)

**Cutout: already shipped, now measured.** `POST /lanes/cutout` (BiRefNet) → 3.7 s, 2000 px framed,
fill 0.879 longest side / 0.4975 area, verdict `compliant`. No work needed beyond verification.

**Relight: now works, and the first failure was instructive.** `ICLightApply` does **not** take the
IC-Light unet as its model. Reading `ic_light_nodes.py` shows it clones a **base SD1.5 checkpoint**
and patches the IC-Light weights into it:

```python
work_model = model.clone()
work_model.add_patches({("diffusion_model." + k): ("diff", [v, ...])
                        for k, v in ic_model.model.diffusion_model.state_dict().items()})
```

Passing the IC-Light unet as both `model` and `ic_model` is a valid graph and a meaningless
computation — which is exactly what "success with colour noise" looks like.

Behind that mistake sat a missing dependency: **no SD1.5 checkpoint on this box** (only SDXL).
`Realistic_Vision_V6.0_NV_B1_fp16.safetensors` was downloaded (2.13 GB, 74 s,
**CreativeML OpenRAIL-M**, sha256 `c48bfd15…`), appended to `provenance.csv` and tagged
`local-lane`.

The corrected graph follows the pack's own `examples/fg.json`: LoadImage → ImageScale →
BiRefNet mask → `ICLightApplyMaskGrey` → `VAEEncodeArgMax` (c_concat) → `CheckpointLoaderSimple` +
`UNETLoader(iclight)` → `ICLightApply` → `EmptyLatentImage` → KSampler (`dpmpp_2m_sde`/`karras`,
denoise 0.9) → VAEDecode → SaveImage.

Two further defects on the way: the source must be rescaled to the canvas, or the concat latent
(1024/8 = 128) and the empty latent (768/8 = 96) disagree — the "Expected size 96 but got size 128"
error; and the new route used `uuid` where the module imports it as `_uuid`, which surfaced as a
live HTTP 500.

**Live.** `POST /relight` on the pouch: 768×768, 20 steps, **9.3 s**, noise metric **4.31**,
verdict **2/2**, folder `state/deliverables/relight_1793635344`, 18-key manifest, material
recorded as `matte`. The noise guard stays: it is what made "the graph ran" and "the image is
real" two different statements.

### C — Print master (`ef0d0944`)

**Purpose.** Turn a screen asset into a file with a physical size and a measured DPI, or refuse.

**Steps (3).** `print_master.py` (Real-ESRGAN 4× + `print_prep.dpi_report`) →
`POST /print/master` → package with the master and the measurement.

**Self-review catches (2).** The prepress arithmetic already existed; re-implementing DPI would
have been a second source of truth. And a guard from a recorded incident: the 4× model aborted
ComfyUI once on a 1216 px input, so sources above **1024 px** are refused by name — the live test
at 1024 px took 6.4 s.

**Live.** 1024 → **4096**, factor 4.0, **1040.38 DPI at 100 mm** (target 300, required 1181 px),
folder `state/deliverables/print_d48b35923e67`. The manifest is the first in this repo to carry
`"dieline": {"built": true, "face_mm": {...}}` — because here a physical face really was declared.

### D — Discovery queue (`e99e4e67`)

**Purpose.** The useful half of "autonomous ingestion" without the supply-chain hole.

**What it does.** Polls a fixed list of repositories for releases, proposes each candidate with its
licence status, lane tag and VRAM estimate, and writes one JSON per `repo@tag`. It never downloads,
never installs, and never runs anything: a test asserts the module contains no `subprocess`,
`pip install`, `git clone` or `os.system`. Unknown licence → ineligible; prerelease → never eligible;
re-running skips rather than overwrites.

**Live.** 5 ComfyUI releases queued, `errors: []`, re-run wrote 0 and skipped 5. Limitation recorded:
only repositories that publish GitHub *releases* yield candidates (several of these only tag).

### E — 3D handoff (`a5ad7ace`)

**Purpose.** The deterministic gate that must exist whatever generator produces the mesh.

**Contract.** `inspect_obj` / `inspect_ply_header` → `audit`: vertices, faces, UV coverage,
non-manifold edges, triangle budget, bounding box, and a **declared** unit system. Refusal codes:
`no_geometry`, `no_faces`, `missing_uv`, `non_manifold_edges`, `polycount_over_budget`,
`bbox_degenerate`, `bbox_unknown`, `units_unspecified`. A planar mesh is allowed — dielines are flat —
and an undeclared unit system is refused rather than assumed to be millimetres.

**Blocker, named.** `blender_probe()` answers **false** on this machine ("no blender executable on
PATH or in Program Files, and bpy is not importable"), so `bake_plan` refuses before it costs
anything. Generation additionally needs a 3D pack and weights that are not installed. **No 3D downloads
were made**, so E is a contract plus a probe, not a working 3D pipeline.

### Closing defects (found while tidying)

Two things surfaced only when the work was finished, and both are the kind that
would have quietly eroded trust in the numbers:

1. **The form-axis fix was uncommitted.** The report described it and the code sat dirty; committed
   as `08bd1860` before anything else.
2. **The A+ service test wrote user deliverables.** The route packages every page, and the test calls
   the route, so each suite run left an `aplus_*` folder in `state/deliverables` — **nine** by the end
   of the day. An autouse fixture now points `aplus_manifest.DELIVERABLES` at `tmp_path` (`6ba1de79`);
   the eight route tests still pass and the folder count no longer moves. The nine artifacts were
   deleted; the one live page stays.

---

## REGRESSION SUITE

**Full backend suite** (`python -m pytest -q` from `Northstar_backend`, 649.26 s):

```
30 failed, 5753 passed, 117 skipped, 2 xfailed, 88 subtests passed
```

Previous campaign closed at `30 failed, 5711 passed`. **+42 passing, 0 new failures by name** — the
30 are the same tests, in the same four pre-existing root causes (`autothink` import 11,
`local_model` `num_ctx` 5, dev-shim `KeyError: 'app'` 5, stale fixtures 8, order-dependent
`provider_suite` 1).

**New suites this campaign:** 42 tests across five new files plus the quality gate —
`test_shorts` 5 · `test_relight` 9 · `test_print_master` 8 · `test_discovery_queue` 8 ·
`test_geometry_handoff` 12 · `test_quality_gate` +1 (the form-axis fix).

**Touched-area group** (all of the above plus deliverables, A+, ad formats, print, lanes,
generate): **130 passed, 0 failed**.

---

## SPEND & RESIDUE

- **Cloud spend: $0.00.** No `opencode run` this campaign; ledger unchanged at **11 entries /
  $0.005656** (0.08 % of the $7.20 / 5 h share).
- **GPU:** local only. Renders this campaign: 1 shorts clip (46.2 s + 48.6 s re-render),
  1 print master (6.4 s), 1 cutout (3.7 s), 3 discarded relight probes and 2 relights that
  passed (9.1 s / 9.3 s). All at **$0**.
- **Downloads: 1** — the SD1.5 base checkpoint above, licence and sha256 recorded.
- **Residue:** probe PNGs and the WEBM removed from the repo root; nine test-authored A+
  packages deleted (with a fixture so they stop appearing); `state/proposals/` holds 5
  proposal JSONs (the queue's intended output, committed); deliverable folders now include the
  clip and the print master. Backend on 8000 still `armed: true`; ComfyUI and Ollama untouched.

---

## DECISIONS & ANCHORS

1. **No auto-installer, ever.** Discovery that pulls and executes third-party code at runtime
   defeats both the licence check and the provenance log. The queue proposes; a human approves.
2. **A lane must measure its own output.** The relight lane succeeded seven times out of seven at
   the API level and produced noise three times out of three at the pixel level. Only a metric
   caught it, and the metric is now part of the lane.
3. **A manifest that contradicts itself is a defect, not a formatting choice.** `form: fail` beside
   `not_applicable` was fixed at the source, and the clip was re-rendered rather than the text edited.
4. **Name the blocker with its number.** "3D blocked" is useless; "no Blender on PATH, bpy not
   importable, 3D pack absent" is actionable in one step.

**NEXT DECISION - one operator choice.**

| Option | What it buys |
|---|---|
| **A. Wire the new lanes into the UI** (recommended) | Shorts, relight, print master and the proposal queue are API-only. Four working capabilities nobody can reach from the app is the largest gap between what exists and what ships. |
| B. 3D unblock | Authorise the install batch (Blender 4.x + a 3D pack and weights) and turn E's contract into a pipeline. The largest new capability, and the only item still blocked. |
| C. Suite green | Fix the utothink import (11) and local_model 
um_ctx (5): 30 failures to 14. |
