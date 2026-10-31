---
name: creative-services-loop
description: Perpetual self-improvement loop for the Design Studio and creative pipelines — prompt audit, workflow optimisation, memory sync, UI/trust compliance, action log. Runs after any creative workflow or when idle.
triggers: creative loop, design studio audit, render review, prompt audit, creative refinement, perpetual loop, studio improvement
---

# Creative services loop

Ty's Assistant runs this after a creative workflow completes, or when the box is idle. Five stages,
always in this order, always ending in an action log. It never touches Amazon and never spends.

## Stage 1 — creative quality & prompt audit

Judge the artefact against print and conversion standards, not against taste:

- **Print:** bleed present, safe margin respected, no element inside 3 mm of trim, max TAC under the
  press limit, vector text never rasterised.
- **Listing:** main image on pure white (255,255,255), subject occupying 85% of frame, no props or
  text on the main image, secondary images may carry context.
- **Prompt defects to name explicitly:** overexposed specular highlights on ceramic/glass, texture
  hallucination on fabric, scale error (a 6 oz pouch sized like a 16 oz bag), missing material verb
  ("brushed", "matte", "embossed", "kraft").
- **Then rewrite the prompt** with: material verb + finish, `soft studio lighting, 85mm lens,
  shallow depth of field`, and negative constraints for text/logos/watermarks. Copy is composited,
  never generated — the text-fidelity gate exists for a reason.

## Stage 2 — studio workflow optimisation

- Pre-render the canvas before the asset gallery asks for it; virtualise any gallery over ~50 rows
  (`VirtualList`); skeleton the shapes that are actually about to appear.
- Every generated asset must emit three records, or it is not finished: the high-res artefact, the
  exact prompt + parameter diff, and the keyword set it serves.

## Stage 3 — memory bank sync

- Read brand colours, fonts, logo placement from the account's memory before generating; write back
  the choices that worked.
- Record render cost and wall time to the account ledger. Zero-silent-cost is the rule: if the cost
  is unknown, write `unknown`, never `0`.

## Stage 4 — UI & trust compliance

- Zero user-visible "Simple" labels. The default is **Standard**; Advanced is a top-tier
  (`advanced_view`) capability unlocked in Settings.
- Standard mode is the default full-viewport frame and must not look like a downgrade.
- Confirm nothing in the run attempted an Amazon action or an unapproved spend. Both are hard
  refusals, per action, every time.
- Verification goes through backend data points (`package_readiness`, `text_fidelity`,
  `prepress`), never a model's opinion of its own output.

## Stage 5 — action log

| Refinement target | Identified anomaly / gap | Implemented optimisation | Verified result |
|---|---|---|---|

Rules for the log: one row per real change; "verified result" quotes a measurement, a path or a test
count — never "looks better". If a stage found nothing, write the row saying so; an empty cycle is a
finding, not a failure.

## Hardware respect

Before a batch render, check `hardware_guard.plan(n)`. VRAM at or above **88%**, or temperature at
the ceiling, steps the batch down; a refusal (batch 0) is reported, never retried silently.
