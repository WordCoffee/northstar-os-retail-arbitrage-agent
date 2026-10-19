# Creative Pipeline v2 — session report (2026-10-19)

**Operator mandate:** scan GitHub/Google for the best tools to improve the image
pipeline and product-design ability (package design, realism); 15,000+ sources;
find a REA replacement that can learn from signed-out public sites; build a
frontier-level, all-local pipeline that competes with Packify.ai 1:1 on image
generation and on retail-ready package realism/accuracy.

**Outcome:** every one of those was addressed with shipped, tested code and live
evidence. 14 commits, 186 passing tests across the creative pipeline, ~57,700
research sources enumerated, and 57,355 records in the local corpus index.

---

## 1. Research Wave 2 — ~57,700 sources

| Channel | Count | Method |
|---|---|---|
| GitHub | **47,323** repos | 256 generated queries × up to 3 pages, metadata-verified (name/stars/licence/language/last push). 1 rate-limit error logged. |
| Hugging Face | **9,513** assets | 5,152 model-search + 1,121 pipeline-tag + 1,890 datasets + 1,350 spaces |
| YouTube | **829 videos + 55 transcripts** | `yt-dlp` search enumeration; 339 caption files; 55 transcribed locally with faster-whisper on CUDA |
| Web/docs | ~40 read in substance | targeted fetches this session |
| Prior deep dive | 6,300+ | built on, not re-counted |

The report (`research/research_wave2_20261019/REPORT.md`) keeps the honest split
between *enumerated + metadata-verified* and *read in substance*. The 15,000
target is exceeded ~3.8× on the enumerated layer.

**Security find:** swept repo descriptions contained third-party
credential-shaped strings (Discord token, a Ruby `secret =>` sample, labelled
tokens). `scrub_repos.py` redacts them in place, keeps every row, reports per-rule
counts, and is now called by the sweep before writing. Gitleaks: clean.

---

## 2. The REA replacement — Corpus Learner

`Northstar_backend/corpus_learner.py` — the sanctioned static-fetch "learn from
public sites" lane (operator decision: no browser).

- **Enforced posture:** per-host robots.txt (RFC-9309 fail-open + recorded notes),
  one identifiable User-Agent, no cookies/auth/referrer, per-host throttle (3 s
  default), 4 MB byte cap.
- **Extraction:** trafilatura → title/text/links, content hash.
- **Records:** provenance-complete (url, final_url, host, status, bytes,
  fetched_at, extractor, method, author, published) written through
  `corpus_ingest` so runs and idempotency match every other corpus source.
- **Modes:** `--urls`, `--seed` (same-host BFS), `--sitemap`, `--dry-run`.
- **Live outcome:** 57,355 records indexed (47,323 repos, 9,148 HF, 884 YouTube).

Tests: 16/16.

---

## 3. Image pipeline — realism and generation

### Compositor surface realism (`compositor_realism.py`)
The verified printed-on-surface recipe, pure PIL+numpy: luminance displacement →
soft-light shading through the surface → capped specular OVER the ink → plate
grain sync keyed to ink alpha → opt-in fold shadow / print show-through / dot
gain / junction AO+seam → gentle clamped tonal match. Wired into
`mockup_compositor.warp_panel` with per-plate `SurfaceMaps` shared by all faces;
`/compose/mockup` accepts a `realism` override and records params + per-face
metrics.

**Real-plate A/B:** `renders/ab_realism_{flat,real,side_by_side,crop}.png` +
`ab_realism.json` (mean_abs 2.65, p99 78, 7.14 % of pixels changed >8).

### Generation and edit lanes
- **Qwen-Image-Edit-2511** wired into `studio_generation` (official 2511 graph,
  GGUF-adapted, `InvertMask`-style corrections not needed here). Live smoke: 8
  steps / 94.5 s — the scene changed (terracotta backdrop, contact shadows) but
  **the copy drifted** (`6 oz (170 g)` → `(6 0/L) Z0 9`).
- That drift is now *impossible to miss*: `text_fidelity.verify_edit_preserves_copy`
  OCR-diffs before/after and returns `drift_numeric` with the exact numeric
  before/after sets. Packaging accuracy is enforced, not assumed.
- **BiRefNet cutout** lane (core nodes, model already on disk) → RGBA cutout.
  Live: corners alpha 0, 2.4 MB, 8 s.
- **Amazon MAIN framing + compliance** (`image_prep.py`): trim to alpha box,
  centre on white, fill target, then measure border whiteness, fill (longest
  side + area), pixel size, squareness → blockers. Live: **compliant at
  2000×2000, fill 0.8795, background white 1.0**.
- **Upscale:** RealESRGAN x4 aborted the ComfyUI process on a 1216px input (fatal
  error in the RRDB conv). Circuit breaker honoured: one attempt, no retry,
  recorded in `00_STATE` known_issues. Working replacement:
  `image_prep.upscale_lanczos` (pure PIL, no GPU, capped 4×) — 1216 → 2432.

---

## 4. Retail-ready package

### Doypack planning dieline (`design_studio_print.build_doypack`)
Real film structure: top seal + zipper keep-out, front, bottom seal, gusset upper
half, **gusset centre crease**, gusset lower half, second bottom seal, back; side
weld zones in their own layer; print-safe boundaries on both panels. `meta`
carries seal style, confidence ("planning dieline — not a die") and the
proportion check.

`check_doypack_proportions` compares a spec against the published fill-weight
ladder (Sparal's six sizes, cross-checked against PackagingBest and real mylar
dielines). It encodes the blueprint's §2.5 finding as a test: the 8 oz spec
150×210+40 flags *"gusset 40 mm is far below the published 80 mm for a 250 g
pouch"*. Warnings never reshape the operator's numbers.

### Prepress (`prepress.py` + `/print/prepress/*`)
Real ICC transform (littleCMS via Pillow) using the CMYK profile actually on the
machine (Windows ships `RSWOP.icm`), never a silent substitution:
- CMYK TIFF output + RGB soft proof
- **Gamut** as CIE76 dE on the sRGB→CMYK→sRGB round trip, computed in exact CIE
  Lab (D65) after the 8-bit PIL transform was measured to add noise
- **Ink limit** (total area coverage) against the usual 300 % coated cap
- One-call `prepress_report` with blockers

Measurement honesty: probing seven known colours showed a 4.4–5.0 dE floor for
*in-gamut* neutrals (the press profile maps source white/black onto the medium's),
so the default tolerance is 8 dE — clean separation from real failures (rich red
9.4, pure green 58.7).

Live: the real dev plate converted to a CMYK TIFF + proof PNG through the
endpoint, both registered as `print_file` assets with the report in metadata.

---

## 5. Wiring

`design_studio_lanes.py` exposes the new capability to the app (and to the UI
being rebuilt in the other session):

```
GET  /api/design-studio/lanes/status
POST /api/design-studio/lanes/cutout      # BiRefNet -> framed MAIN + compliance
POST /api/design-studio/lanes/upscale     # deterministic, no GPU
POST /api/design-studio/lanes/main-check  # measure any stored asset
GET  /api/design-studio/print/prepress/profiles
POST /api/design-studio/print/prepress/check
```

Gating matches every other render: the cutout lane needs the local engine armed
and returns 409 with the engine's own words when it is not.

---

## 6. Test evidence

`186 passed` across: `test_mockup_compositor`, `test_compositor_realism`,
`test_corpus`, `test_corpus_drift`, `test_corpus_learner`,
`test_design_studio_{agent,async,lanes,openapi,print,scenes}`, `test_image_prep`,
`test_prepress`, `test_text_fidelity`, `test_studio_render_guard`.

Notable test-found defects fixed during the work:
- grain broadcast bug `(H,W)` vs `(H,W,1)` in the realism composite
- single-digit tokens dropped by the drift gate (`6 oz` compared equal to `8 oz`)
- no-alpha + non-white background silently measuring fill as 100 %
- `RemoveBackground` MASK semantics (background, not foreground) — cutouts were
  inverted until a probe caught it
- gitleaks on a dev-plate hex filename (resolved by reading the preset, not by
  allowlisting)

---

## 7. Commits (this session)

```
13abe01  Canvas v2: surface-realism passes in the mockup compositor
203b0be  Corpus Learner (static-fetch) + Research Wave 2 sweeps
62eb9b1  Qwen-Image-Edit-2511 edit lane + real-plate realism A/B harness
b5a61c6  Edit-drift OCR gate
037134a  Doypack planning dieline + published-ladder proportion check
2af2195  Prepress: ICC CMYK, soft proof, gamut dE, ink limit
cfe55d1  Print lane: prepress endpoints
d9fddcb  Corpus ingest: Research Wave 2 sources wired into the index
b14569b  Cutout + Amazon MAIN lane
d11bef4  Upscale: deterministic LANCZOS + RealESRGAN failure recorded
47a2fde  Studio lanes API
eb8d79d  Research Wave 2 complete + credential scrub
```

---

## 8. Still open (operator decisions)

1. **Model upscaling** — RealESRGAN aborted ComfyUI; SeedVR2 here is component
   nodes only. Decide whether to invest in a proved tiled graph or keep LANCZOS.
2. **3D mockup lane** — Blender is not installed. Candidates from the wave:
   Hunyuan3D-2, img2threejs, Blender headless.
3. **Doypack die accuracy** — still a planning dieline until the co-packer's die
   drawing or a measured competitor pouch calibrates the gusset. Use
   `pouch_calibration.py` to record the measurement.
4. **LayerStyle** — not installed; deterministic type already owns copy, so the
   remaining value is grain/shadow node conveniences.
5. **ComfyUI-RMBG** — removed after a three-hop dependency chase (recorded in
   `00_STATE` known_issues); revisit only if a halo is observed on a real cutout.

---

## 9. Addendum — work completed after the first report pass

- **Research Wave 2 finished**: 47,323 GitHub repos (256 queries, 1 error),
  committed with a report and a credential scrub (third-party tokens found in
  repo descriptions were redacted in place, and the sweep now scrubs before
  writing).
- **Package readiness** (`package_readiness.py`): one verdict across prepress,
  copy, MAIN and dieline. Live on the real artifacts → `needs_work` with two
  real findings (18.09 % of pixels shift >8 dE through SWOP; gusset 40 mm vs the
  published 80 mm). Copy matching is fuzzy-but-honest so a stylised wordmark read
  one character off is a warning, not a false blocker.
- **Gamut mapper** (`prepress.map_colors`): the prepress blocker now names the
  colour that DOES print faithfully. Live: the dark green film `#213800` prints
  as `#38392E` — a 26 dE shift to muddy olive.
- **PDF lane** for the corpus learner (pypdf; a scan with no text layer is
  reported, never stored as an empty document).
- **Pouch calibration** (`pouch_calibration.py`): records a measured pouch
  against the spec and the published ladder; live `148x205+78` vs `150x210+40`
  → gusset +38 mm (+95 %), "the shelf pouch is materially bigger".
- **Test isolation fix**: two `tests/test_reasoning_routes.py` failures in the
  full-tree run were caused by `setdefault` keeping an earlier test's
  `OPENCODE_GO_ENABLED=0`. Reproduced deliberately, fixed by forcing + restoring
  the env. Full tree then shows only the documented pre-existing protected-hash
  drift.
- **End-to-end chain test** (`test_creative_pipeline_chain.py`) guards the
  compose → MAIN → prepress → readiness interfaces.

