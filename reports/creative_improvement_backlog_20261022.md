# Creative pipeline — improvement backlog and first shipped tranche

**Date:** 2026-10-22 · **Branch:** `feature/v4.1-mesh` · **Spend:** $0

---

## On the number "1000"

I did not produce 1000 items, and I am not going to pad the list to reach it.

The first pass of my audit **did** report 977 findings. They were mostly fake: 673 of them
were "missing timeout" flags on `urllib.request.Request(...)` constructors and on
`dict.get(...)` calls, and 191 were "ungated generator" flags on private helpers like
`_reachable` and `_evict`. Reporting those would have been a fabricated backlog, and
"1000 improvements" would have been true only in the sense that a list can be made long.

So I tightened the rules until every finding could be defended, and added tests that pin
the false-positive guards. The honest number for this surface is **104** — each with a
file, a line and the literal evidence.

If you want a genuinely bigger number, the way to get it is **more rules**, not looser
ones: each rule below is one function in `tools/creative_audit.py`, and the backlog grows
as real rules are added.

---

## What was built

| Piece | Path | What it does |
|---|---|---|
| Audit tool | `tools/creative_audit.py` | 12 rules over the 28 creative modules; every finding has code, severity, file, line, evidence, detail |
| Backlog | `docs/CREATIVE_BACKLOG.json` | 104 findings, stable `CRE-####` ids, machine-readable |
| Tool tests | `Northstar_backend/test_creative_audit.py` | 9 tests, incl. the regression guards for the 673 false positives |
| Contract tests | `Northstar_backend/test_creative_surface_contracts.py` | 18 tests covering the 7 modules that **nothing imported** |

```
python tools/creative_audit.py                    # summary
python tools/creative_audit.py --code CRE-SILENT -v
python tools/creative_audit.py --write docs/CREATIVE_BACKLOG.json
```

### Current backlog

```
creative modules: 28 | findings: 104
  CRE-SILENT       66   (high)    except handler with no log, no re-raise, no warning
  CRE-LONGFN       31   (low)     function >= 60 lines
  CRE-UNGATED       4   (high)    public function reaching a generator with no armed check
  CRE-BIGFILE       3   (low)     module >= 800 lines
```

---

## Shipped in this tranche (not just listed — done, tested)

1. **7 untested modules now have contract tests.** `ad_pilot`, `design_studio_boxes`,
   `design_studio_imports`, `mockup_engine`, `social_pulse`, `listing_forge`,
   `studio_upload_router`. `CRE-NOTEST` went 7 → 0. The tests target deterministic
   paths only: no model, no GPU, no network. Several assert *refusal* behaviour —
   `generate_box` raising `BoxesUnavailable` instead of faking an SVG,
   `parse_variant_metrics("")` raising rather than inventing metrics.

2. **Two generators no longer hardcode the brain model.** `listing_forge` (4 generators
   + `_call_llm`) and `social_pulse.generate_caption` had
   `model: str = "northstaros-qwen3.8:27b"` baked into five signatures. They now resolve
   through `model_router.resolve_for_service(..., provider="local")`, so changing
   `shared/model-suite.json` actually changes them. Provider is pinned to `local`
   deliberately: these call Ollama directly, and the router's default is the customer
   (cloud) lane — a cloud id would simply not exist in Ollama.

3. **A silent failure now says why.** `social_pulse`'s caption LLM call swallowed every
   exception with `pass`; it logs at debug and still falls back to the template. That is
   one of the 66 `CRE-SILENT` items — the rest are listed, not silently "fixed".

4. **A mutable default argument removed.** `package_designs.big_name(..., axes=[600])` →
   `axes=None` with an explicit default inside.

### Verification

```
pytest test_creative_surface_contracts.py test_creative_audit.py   27 passed, 1 skipped
pytest test_seo_listing.py                                         23 passed
pytest (12 creative suites)                                        207 passed, 17 skipped
```

One test I wrote initially made a **real** Ollama call (35 s) because I patched a
function that did not exist. It now patches `httpx.post` and the suite runs in 2.6 s.

---

## The 4 remaining `CRE-UNGATED` — reviewed, and why they stay

| Finding | Verdict |
|---|---|
| `design_studio_async.run_generation_job` | gate lives in the callee: `generate_image`/`generate_video` raise when `MEDIA_GEN_LIVE` is unset |
| `design_studio_lanes.lane_cutout` | same — `generate_cutout` gates, the route converts it to a 409 |
| `studio_generation.release_models` | it posts to ComfyUI `/free`; that is cleanup, not generation |
| `social_pulse.generate_caption` | calls local Ollama, which costs nothing and is not media-gated |

Two of these are the rule reaching through a wrapper it cannot see into; two are the rule
being wrong about what "generation" means. All four are recorded so the backlog does not
accumulate known-OK entries.

---

## Recommended next tranches, in order

1. **`CRE-SILENT` (66).** Not cosmetic: each one is a place where a failure becomes an
   empty result. The right fix is per-site (log + typed fallback), not a mass sed — a
   blanket `log.exception` would turn a designed fallback into log noise. I would do
   them by module, in the generation paths first.
2. **`CRE-LONGFN` (31).** Pure maintainability; `design_studio_api.py` and
   `package_designs.py` hold most of them.
3. **`CRE-BIGFILE` (3).** `design_studio_api.py` at 1,752 lines is the obvious split
   (routes vs. logic), but it is a large mechanical change and deserves its own pass.
4. **New rules worth adding:** endpoints whose request model has no bounds on numeric
   fields; modules that write files without a size cap; OCR/vision calls with no
   confidence floor.

## What this does not claim

It is not a quality improvement to the output — nobody has judged whether the renders
are good. It is a maintainability and honesty improvement to the code that produces them,
plus a reproducible way to keep finding more.
