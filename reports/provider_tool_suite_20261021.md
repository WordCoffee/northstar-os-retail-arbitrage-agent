# Provider tool suite — build report

**Date:** 2026-10-21 · **Branch:** `feature/v4.1-mesh`
**Task:** give the Master Brain a local-vs-cloud tool suite, so selecting the local
engine exposes a different (and licence-appropriate) set of tools than the cloud lane.

---

## What shipped

| Piece | Path | State |
|---|---|---|
| Registry (data) | `shared/provider-suite.json` | 18 tools — 14 local-lane, 4 cloud-lane |
| Resolver (code) | `Northstar_backend/provider_suite.py` | pure, offline, fail-closed, CLI |
| API | `GET /api/v1/provider-suite[?provider=…]` | `main.py`, bff/v1 envelope |
| UI | Master Brain → *Provider tool suite* | lane switcher + licence/reason table |
| Tests | `Northstar_backend/test_provider_suite.py` | **23 passed** |
| Docs | `docs/PROVIDER_SUITE_ARCHITECTURE.md` | architecture + adoption plan |
| Capsule | `AGENTS.md` §Provider tool suite | every session now sees the rule |
| State | `00_STATE.json` → `provider_suite` | shipped record |

## The design decision that matters

`model-suite.json` already picked a model per tier. It never said which *tools* the
brain may touch. That gap is a licensing gap: `FLUX.1 [dev]` is genuinely capable and
genuinely non-commercial, and until now only prose stood between it and a customer
deliverable.

So the suite enforces three things:

1. **Licence is evaluated before lane membership.** If a non-commercial tool is ever
   mis-listed on the cloud lane, the licence still blocks it and the reason says so
   instead of a vague `not_in_lane`.
2. **`allowed` and `installed` are separate axes.** `usable = allowed AND installed
   AND gate armed`. UltraTex reports *allowed but not installed* — two different
   truths that must not be collapsed into one optimistic flag.
3. **Unknown fails closed**, including an unverified weights licence. "Probably fine"
   is not a lane.

### Reason codes
`ok` · `not_in_lane` · `license_noncommercial` · `weights_license_unverified` ·
`gate_not_armed` · `not_installed` · `agpl_network_copyleft_unreviewed` ·
`unknown_tool` · `unknown_provider`

### A trap worth naming
**Local lane ≠ offline.** OpenMontage is a local install that still pulls from
Archive.org and, optionally, 60+ paid APIs. Each entry carries `network: true|false`
so the brain cannot infer a network boundary from the word "local".

## Research recorded (the three things the operator asked about)

### UltraTex — best fit, one licence question
`visualbruno/ComfyUI-UltraTex`, SIGGRAPH Asia 2026. Mesh + one reference image →
six 2048² texture views → baked UV texture → GLB.

- Node code **MIT**; base `FLUX.2-Klein-base-9B` **Apache-2.0**; **LoRA weights from
  ModelScope state no commercial grant** → `weights_license_unverified` → local only.
- Measured ~2.3 min/workflow @1024 and ~9.6 min @2048 on an RTX 3080 Laptop 16 GB (fp8)
  — same hardware class as this box.
- **Prerequisite already satisfied:** it needs Triton on Windows, and
  `triton-windows 3.8.0.post29` is already installed from the KJNodes fix recorded in
  `00_STATE.json`.
- Value: Product Designer already has meshes, but mockups are flat plates today.
  UltraTex + approved hero plate → textured 3D prop → local video (Wan 2.2) or Blender.

### OpenMontage — clone the pattern, not the code
`calesthio/OpenMontage`, **AGPL-3.0**. 10+ pipelines, 100+ tools, 60+ providers,
700+ agent-skill files. Flow: `research → proposal → script → scene_plan → assets →
edit → compose`, one stage-director skill per stage, human approval at creative gates.
Zero-key path: Piper TTS + Remotion/HyperFrames + FFmpeg + Archive.org / NASA /
Wikimedia. Published example costs: $1.33 for a 60 s short.

- AGPL **does** allow commercial use, but §13's network clause is an unanswered legal
  question → `cloud_block: agpl_network_copyleft_unreviewed` → local lane by default.
- Decision: **do not vendor the tree.** The reusable asset is the pipeline/stage-skill
  *structure*, which carries no licence obligation. Vendoring AGPL into Northstar would
  put the whole app under review for a feature we can reimplement far smaller.

### Harnesses — the category
An agent harness is the runtime layer around a model: tools, skills, sessions,
approvals. Northstar already has one (constitution + `model_router` + Chrome Connect +
rooms). `provider-suite.json` is the capability manifest that harness was missing.

## Adoptions, ranked

| # | Adoption | Lane | Cost | Blocker | Call |
|---|---|---|---|---|---|
| 1 | UltraTex → textured 3D product props | local | $0 | LoRA weights licence | Install once licence is confirmed, or accept bench-only use |
| 2 | OpenMontage **stage-skill pattern** → our own pipeline directors | both | $0 | none (pattern) | Do now |
| 3 | OpenMontage as external local tool (`OPENMONTAGE_ROOT`, headless, file output) | local only | $0 | AGPL §13 review before customer use | Defer until a real video order exists |

## Verification (real output)

```
python -m pytest test_provider_suite.py test_model_router.py -q
45 passed, 1 warning in 3.58s

python Northstar_backend/provider_suite.py
lane: local
  local: 2 usable / 16 blocked
  cloud: 0 usable / 18 blocked
    - openmontage (harness): agpl_network_copyleft_unreviewed
    - flux1_dev (image): license_noncommercial
    - ultratex (three_d): weights_license_unverified

npm run build → ✓ built in 1.85s (0 errors)
```

The local lane showing only 2 usable is correct and honest: `MEDIA_GEN_LIVE` is not
armed in this shell, and UltraTex / OpenMontage / Piper are declared `ready` rather
than `installed`. No flag was flipped to make the output look better.

## Not done

No tool installed. No repo cloned or vendored. No AGPL code in any cloud path. No
provider key read or written. No spend. No licence reclassified.

## Next step, if the operator wants one

Confirm the UltraTex LoRA weights licence (or point at an Apache-2.0 substitute),
then install `ComfyUI-UltraTex` and run one mesh + hero-plate test on a product that
already exists in the Design Studio. That is the cheapest real upgrade on the list:
zero marginal cost, and the Triton prerequisite is already in place.
