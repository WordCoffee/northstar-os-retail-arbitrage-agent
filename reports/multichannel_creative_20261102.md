# Multi-Channel Creative Expansion (A+ · Ads · Social)

**Campaign:** `multichannel-creative-expansion`
**Date:** 2026-11-02
**Author:** DeepSeek V4.1 Flash (opencode-go, operator session); local vision `qwen3.5:4b`, OCR `rapidocr`
**Branch:** `feature/chrome-connect-3.0` · rollback tag `rollback/pre-packify-20261102-070637`
**Units:** 2 of 2 · wall clock ≈ 50 min of the 4 h cap · 0 failed attempts

---

## VERDICT

**PARTIALLY READY — two units delivered and verified; motion content was not attempted.**

| Objective | State |
|---|---|
| 1. A+ / e-commerce modules | **Already built** (header, three-tile, comparison, card modules with measured contrast and overflow). This campaign added the missing half: a page-level manifest and an OCR read-back of every drawn line. |
| 2. Multi-format ad creatives | **Done.** `square 1:1`, `story 9:16`, `wide 16:9` are validated canvases; a contradictory size is refused before the GPU is touched; OCR-first copy validation and the gibberish guard apply to every format. |
| 3. Social & YouTube Shorts sequences | **Partially.** 9:16 vertical stills ship through the same gate. **Motion/keyframing was not attempted** — no ComfyUI video workflow was built, tuned or claimed. |

Saying "A+ exists" is deliberate: the honest gap was *verification*, not generation, and
inventing another renderer would have been the wrong work.

---

## PER-UNIT BREAKDOWN

### Unit 1 — `ty-ad-formats` (commit `515d48fa`)

**Purpose.** A placement is a canvas. Before this, any `width`/`height` pair was accepted,
the manifest had no way to say which format shipped, and the typography axis only checked
the words you *asked for* — a render carrying a wall of fake background text passed.

**Steps (4).** `ad_formats.py` (three canvases + refusal) → `GenerateIn.format` →
validation moved **before** the engine gate, so a bad request is a 422 not a 409 →
`garbled_text` added to the vision schema and to the typography axis.

**Rules now enforced.**

| Request | Result |
|---|---|
| `format=story` | 864×1536, ratio `9:16`, placements `ig-story, reels, tiktok, shorts` |
| `format=story, width=1024` | **422** `ad_format_dimension_conflict` — refused, never overridden |
| `format=billboard` | **422** `ad_format_unknown` |
| any free `width` not a multiple of 8 | **422** `ad_format_invalid_size` (ComfyUI samples on 8-px latents) |
| `GET /ad-formats` | the three placements, for a UI that does not exist yet |

**Self-review catches (4).** A format that only sets width/height is not a contract; the
contradiction must be refused. Validation has to run before the engine gate or the caller
gets a 409 they cannot diagnose. The canvas must stay on the latent step or ComfyUI crops
silently. And the biggest one:

> The first live story-ad run **passed 4/4** while OCR returned 11 boxes including
> `MSNHES CIRSIE TUION` and `MORIA ILIIP RGEHET`. Coverage of the requested words was 1.0 —
> the gate was answering "did the words I asked for appear" when the brief implied "is this
> ad clean". `garbled_text` now asks the second question and blocks as `typography_garbled`.

That run's package was **deleted** after the rule tightened: leaving an accepted package that
today's gate refuses would be the exact dishonesty the gate exists to prevent.

**Live proof.**

| Case | Result |
|---|---|
| story ad, text-free brief | **3/3 pass**, 864×1536, 20-key manifest with `format`, `ratio`, `canvas`, `placements`; typography n/a and `verified: true` (OCR confirms no lettering) |
| story ad with `LION MANE` label copy | **3/4 BLOCKED** — `typography_illegible`, *"Main text is clear but secondary text below is garbled."* No folder written (7 → 7) |

### Unit 2 — `ty-aplus-verified` (commit `48ff4e78`)

**Purpose.** The A+ renderer already measures contrast, fit, container overflow and weight at
draw time. That proves the *layout model*; it does not prove the pixels contain the words.
A missing glyph run can pass every geometric check and ship a blank panel.

**Steps (4).** `render_page` now records `copy_texts` (the strings it actually drew) →
`aplus_manifest.py` writes the package → wire into `/aplus/render` → fix what the live run
exposed.

**Verdict, reusing `quality_gate.verdict` so A+ and the ad lane speak the same language.**

| Axis | Decided by |
|---|---|
| `typography` | OCR coverage of the **drawn** strings (threshold 0.8, calibrated on a measured 1.0) |
| `layout` | the renderer's own QA: contrast, fit, container, canvas |
| `design_alignment` | every requested module kind exists in the page |
| `form`, `material` | not applicable to a composited module |

**Self-review catches (5).** Geometry cannot prove glyphs → read the pixels. Comparing pixels
against the *request* would pass a wrong drawing → compare against what the renderer says it
drew. A page with no copy is `n/a`, not a pass. A failing page is removed from disk rather
than left looking shipped. And two packages written while the `copy_texts` bug was live were
deleted — a `2/2` that never read the pixels is the fabrication this unit exists to stop.

**Defects found while proving it.**
- `render_page` read `res["records"]`; the renderer returns the record list as `res["texts"]`.
  Every module reported `copy_texts: []` and the first page scored **2/2 with typography n/a** —
  a false pass caught by looking at the manifest rather than the HTTP 200.
- `design_studio_aplus.py` carried a UTF-8 BOM and a merged statement from an earlier edit,
  which broke test collection. Stripped and split; 92 A+ tests pass.

**Sample manifest output** (`state/deliverables/aplus_1793627450/manifest.json`):

```json
{
  "run_id": "aplus_1793627450",
  "created_at": "2026-11-02T07:50:56",
  "kind": "aplus",
  "requested_kinds": ["header", "three_tiles", "comparison"],
  "modules": [
    {
      "index": 1, "kind": "header", "size": [970, 600], "bytes": 328964,
      "copy_mode": "panel",
      "qa": {"ok": true, "problems": [],
             "warnings": ["accent darkened for legible small caps"]},
      "texts": ["WELLNESS", "LION / MANE", "Organic lions mane mushroom / powder"],
      "coverage": {"applicable": true, "expected": 3,
                   "matched": ["WELLNESS", "LION / MANE",
                               "Organic lions mane mushroom / powder"],
                   "missing": [], "coverage": 1.0},
      "ocr": {"engine": "rapidocr", "status": "ok", "contains_text": true, "boxes": 5,
              "words": ["WELLNESS", "LION", "MANE",
                        "Organic lions mane mushroom", "powder"]},
      "file": "aplus_01_header.png"
    }
  ],
  "quality": {
    "axes": {
      "form": {"status": "not_applicable", "reason": "aplus_module"},
      "design_alignment": {"status": "pass", "modules": 3},
      "layout": {"status": "pass", "modules_measured": 3},
      "typography": {"status": "pass", "coverage": 1.0, "modules_read": 3},
      "material": {"status": "not_applicable", "reason": "composited_module"}
    },
    "verdict": {"ok": true, "passed": ["design_alignment", "layout", "typography"],
                "failed": [], "not_applicable": ["form"], "score": "3/3", "reasons": []},
    "model": "deterministic:pillow+rapidocr",
    "coverage_threshold": 0.8
  },
  "dieline": {"built": false,
              "reason": "A+ module; canvas is fixed by the module, not a die"},
  "color_profile": {"working": "RGB", "target": "sRGB", "converted": false,
                    "note": "A+ modules ship as sRGB PNG/JPG; no print conversion"},
  "files": ["aplus_01_header.png", "aplus_02_three_tiles.png",
            "aplus_03_comparison.png", "manifest.json"]
}
```

**Live page:** header + three_tiles + comparison, **14 text blocks drawn, OCR coverage 1.0 on
all three modules**, renderer QA clean, verdict 3/3, package written. Comparison and tile
modules are exactly the "modular comparison chart / feature callout" objective, now carrying
their own read-back evidence.

---

## REGRESSION SUITE

**Full backend suite** (`python -m pytest -q` from `Northstar_backend`, 630.31 s):

```
30 failed, 5711 passed, 117 skipped, 2 xfailed, 88 subtests passed
```

The previous campaign closed at `30 failed, 5689 passed`. **+22 passing, 0 new failures** —
the 30 are the same tests by name, in the same four pre-existing root causes:

| Root cause | Count | Where |
|---|---|---|
| `autothink/backend/server.py` imports `build_system_prompt_with_context`, absent from its `llm_adapter` | 11 | `test_autothink_routes` (8), `test_autothink_auth_boundary` (2), `test_ui_route_contract` live probe (1) |
| `agent_kernel/local_model.py:89` — `NameError: num_ctx is not defined` | 5 | `test_local_model` |
| Dev-shim tests build a Starlette `Request` without `app` → `KeyError: 'app'` | 5 | `test_session_cookie_contract::DevShimSessionTests` |
| Stale fixtures/invariants (route count 53 vs 57, HITL totals, shell-mode plan gates, two guard-prompt strings, a sample URL in `HitlQueue.jsx`) | 8 | `test_frontend_gate`, `test_autonomy_hitl_pathlike`, `test_hitl_counts`, `test_shell_modes`, `test_coding_guardrails`, `test_generation_guards`, `test_ui_route_contract` |
| Order-dependent (passes alone: 24 passed) | 1 | `test_provider_suite` |

**Touched-area suites:** **214 passed, 0 failed** — `test_ad_formats` 13 ·
`test_quality_gate` 24 · `test_aplus_manifest` 7 · `test_aplus_layout` 13 ·
`test_aplus_render` 64 · `test_design_studio_aplus` 8 · `test_deliverables` 10 ·
`test_dieline_geometry` 18 · `test_generate_form` 4 · `test_text_fidelity` 20 ·
`test_mockup_compositor` 11 · `test_design_studio_lanes` 9 · `test_design_studio_print` 13.

---

## SPEND & RESIDUE

- **Cloud / Go spend: $0.00.** No `opencode run` invocation this campaign. Ledger unchanged:
  11 entries, **$0.005656 cumulative** (0.08 % of the $7.20 / 5 h share, ≈ **$7.1943** left;
  weekly and monthly shares untouched).
- **Renders:** 3 live image renders + 1 A+ page (3 modules), all local at **$0**.
- **Downloads:** none.
- **State residue: zero.** No daemons started or left; backend on 8000 is the operator's
  launcher (restarted for module reloads, still `armed: true`); Ollama and ComfyUI unchanged.
  Scratch packages removed; **7 deliverable folders remain, each one defensible** — 3 with
  verified typography, 2 text-free runs verified by OCR, 2 from before the quality gate which
  the UI labels "quality not recorded" rather than inventing a score. Rollback tag
  `rollback/pre-packify-20261102-070637` still marks the pre-quality work.

---

## DECISIONS & ANCHORS

1. **A placement is a canvas, a ratio and a placements list — not a width/height pair.**
   The format is resolved before the engine is consulted, so a contradictory request costs
   nothing and the manifest can state what was delivered.
2. **The gate must ask about the whole frame, not only the words you requested.**
   A wall of fake background copy passed a 4/4 until `garbled_text` existed. Coverage answers
   "did my copy land"; it does not answer "is this ad clean".
3. **Compare pixels to what the renderer says it drew, not to the request.** The A+ read-back
   would have passed a page that drew the wrong strings; recording `copy_texts` at draw time
   is what makes the comparison meaningful.
4. **A package that today's gate would refuse does not stay on disk.** Three folders were
   deleted this campaign (one pre-rule ad pass, two pre-fix A+ pages) instead of being
   grandfathered in.

**NEXT DECISION — one operator choice.**

| Option | What it buys |
|---|---|
| **A. Motion for Shorts/Reels** (recommended) | The open third objective: 9:16 sequences with container rotation and finish transitions through ComfyUI, gated frame-by-frame with the same OCR/typography rules. Highest new capability, highest GPU time. |
| B. Ad format UI + A+ package UI | Make both reachable without curl: a format selector on the ads surface and a package preview in Design Studio. Lowest risk, no new rendering. |
| C. Suite green | Fix the `autothink` import (11) and `local_model` `num_ctx` (5): 30 failures → 14. |

Option A is recommended because it is the one stated objective still open; B and C improve
the platform around the pipeline rather than extending it.
