# Word Coffee — Alpha Test Plan (Phase H / H7)

**Goal:** use the full suite on the Word Coffee ad account, ending with a
measurable answer to "did sales increase?" — safely, with dry-runs first.

**Baseline (operator-provided, ~90d):** spend $2,370.40 · ad sales $1,428.30 ·
**ACoS 166%** · 90 ad units · Business Report 210 units / $3,223.80 · implied
ASP $15.87. Every campaign is above 100% ACoS.

---

## 1. Offline rehearsal (no Amazon, no spend)

1. `word_coffee.summary()` → confirms every campaign is unprofitable, lists the
   five ≥100% ACoS targets, worst first (`gifts for women` BROAD 459%,
   `substitutes` 412%).
2. `change_plan()` → the dry-run bid plan with guardrails applied
   (≤20% decrease, ≤10% increase).
3. Optional: `breakeven_acos(cogs_per_unit=…)` once COGS is supplied
   (provisional target ACoS 30% until then).

**Deliverable:** a reviewed change plan. Nothing has touched Amazon.

## 2. Engine pass (local vs cloud)

Run the analysis and copy generation on **Local** (`northstar-qwen3:rev1`) and
on **Cloud** (DeepSeek lane, armed) and compare. Confirms the dual-engine
switch end-to-end on real data.

## 3. Live changes (each needs a fresh named §3 approval)

Order matters — stop the bleed first:

1. **Cuts only (recommended first live action):**
   pause/negative `gifts for women` BROAD and `substitutes` (PT); cut the
   remaining ≥100% targets by ≤20%.
2. **Raise (only after COGS gives a real breakeven):** the single healthy
   target `birthday gift for women` BROAD (68.7%) — raise within ≤10%.

Guardrails are fixed and enforced by AdPilot: autonomous ≤20% decrease,
≤10% increase, negatives only; everything else is gated.

## 4. Measure (the "did sales increase" answer)

| Metric | Source | Window |
|---|---|---|
| Ad sales + units | Ads console | 14 days pre vs post |
| Business Report units + ordered sales | Seller Central | 14 days pre vs post |
| ACoS | derived | 14 days pre vs post |
| Organic vs ad-attributed | Business Report | isolate the halo |

**Success = lower ACoS at equal-or-higher total units**, not just lower spend.
Record the numbers in a scrubbed manifest; never auto-retry a failed action.

## 5. Data still needed

- **COGS per unit** (the two SKUs) → unlocks breakeven ACoS and real targets.
- **Ads API write access** for live bid changes (OAuth + approval).
- **Target ACoS** confirmation (provisional 30% until COGS arrives).
