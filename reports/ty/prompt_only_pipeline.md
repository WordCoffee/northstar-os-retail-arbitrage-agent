# Prompt-only: what the pipeline change did, and what it did not

Owner ask (2026-11-09): *build prompt-only as generate, cut out, deterministic stages; rescore the
twelve and report.*

## What changed

`CompositeGenerator._full_generation` used to return the raw render. It now treats the render as
**material**, the same way the composite route treats a seller's photograph:

1. **generate** the plate from the brief's own description;
2. **cut** the product out of that plate (GrabCut, seeded so the mask is deterministic);
3. **re-compose** the cutout on a canvas the brief's constraints can actually satisfy, at 0.62 of the
   frame;
4. **lay out** — the deterministic infographic / packaging stages run exactly as they do for an
   uploaded reference.

Fidelity stays `tolerant`: nothing claims the generated pixels are the seller's.

## The result: 34.5, down from 37.5

| version | pipeline | scored | passed | mean |
|---|---|---|---|---|
| v1 | generate only | 12 | 0 | **37.5** |
| v2 | generate → cut → compose → layout | 12 | 0 | **34.5** |

**The change made the number slightly worse, and that is the honest finding.** Structuring the
pipeline does not rescue a mode whose bottleneck is the *generated product itself*: the plates do not
satisfy the brief's own background, fill and text rules, and re-composing them adds a failure mode
(the cut mask) without removing the first one. Twelve of twelve still fail; none is `cannot_verify`,
so these are measurements, not refusals.

## What it does buy

- The stages are now the *same* for every mode, so a prompt-only failure is comparable to a
  composite failure instead of being a different kind of number.
- The product-region check correctly does not apply (no reference to preserve), which is recorded as
  a skip rather than a silent pass.
- The marginal cost is measurable: **−3.0 mean points** for the extra stages, which is the honest
  price of making the modes comparable.

## What would actually move prompt-only

1. **A better plate.** The current prompts describe the product in one sentence and the model draws
   a plausible package, not *that* package. Nothing downstream can fix a wrong package.
2. **Constraint-aware prompting.** The brief already knows its background level, aspect and fill
   range; those should be in the prompt, not only in the scorer.
3. **A reference at the end.** The moment a seller uploads one photograph the mode becomes
   uploaded-reference, which scores 90.0. That is the product answer, and it is why the mode is
   measured separately rather than blended into the headline.
