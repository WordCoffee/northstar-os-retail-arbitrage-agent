# ListingForge — Listing Optimizer Agent — Website Plan & Architecture

> **Status:** Approved for construction (Autonomous Zone).
> **Derives from:** master plan §4.2, profile §6 (Word Coffee voice block), and the
> verified substantive baselines (Moms ASIN **B0F87RXTVC** score 62.1→79.6; Women
> ASIN **B0F87JDPD4** score 64.8→80.1).

## 1. SERVICE IDENTITY

**Public:** ListingForge — "Forge listings that convert."
**Internal agent:** Listing Optimizer Agent (Listings Agent).
**Core promise:** title/bullet/description rewrites, A+ content copy & image prompts,
SEO, backend terms, compliance screening, Rufus readiness — in each brand's voice.

## 2. SCREENS / VIEWS (hash routes within `#/listingforge`)

| View | Purpose |
|---|---|
| **Studio** | Working surface for one listing at a time: current title/bullets/description editable, scored live, with per-section suggestions |
| **Scoring** | Weighted scoring breakdown of the current listing: SEO 30 / Conversion 25 / Compliance 20 / Visual 10 / Rufus 15 + dedicated `rufusReadinessScore` |
| **Compliance** | Rule-based screening: medical-claim terms, absolute superlatives, review solicitation, trademark risk — severity `block` vs `warn` |
| **Media** | A+/Media prompt studio: 7-slot image gallery prompts, 4-scene video storyboard, 5-module A+ plan; brand palette hints (Word Coffee: charcoal/cream/clay) |
| **Keyword Bridge** | Backend terms + front-of-listing keyword placement; ROAS tiering (high-priority winners 8x+, teach words) |
| **Feedback Loop** | Log of edits/corrections as learning signals (digital-clone principle) |

## 3. COMPONENTS

1. **Listing Card** — physical-card style; fields as "paper" form rows with mono labels.
2. **Score Dial** — rotary-knob gauge per category (SEO/Conversion/Compliance/Visual/
   Rufus) + total badge.
3. **Guardrail Flag** — `block` (crimson wax) vs `warn` (gold) pills with the matched
   term and the rule that fired.
4. **Media Grid** — 7 gallery-slot tiles + 4-scene video strip + 5-module A+ accordion.
5. **Keyword Rio** — backend-term tag editor with char/byte counters (250-byte cap) and
   duplicate detection.
6. **Voice Chip** — active brand module chip (Word Coffee) enforcing the "NOT a
   beverage" rule in copy guidance.

## 4. DATA CONTRACT

```js
listingRecord = {
  asin, brand, title, bullets[], description, backendTerms[],
  scores: { seo, conversion, compliance, visual, rufus, total, rufusReadiness },
  compliance: [{ rule, severity: 'block'|'warn', term, message }],
  mediaPlan: { gallery[7], video[4], aPlus[5] },
  provenance: 'fixture' | 'user_saved' | 'gated_live',
}
```
- Fixtures: Word Coffee Moms (`B0F87RXTVC`) and Women (`B0F87JDPD4`) baseline listings,
  labeled `data-kind="demo"`, tags `provenance: 'fixture'`.
- Character rules: title ≤ 200 chars input, flagged ≤ 131 ideal; backend terms ≤ 250
  bytes; duplicate SKU/term detection.

## 5. GATED-LIVE PATHS (code built, execution gated)

- Claude Sonnet copy rewrite call (`data-live-gate="off"`, off-preflight banner).
- Image/video generation API call (A+/media assets) — same gating.
- A/B test ingestion — fixture-only placeholder until Amazon A/B data is approved.
Multi-platform extension (Etsy/eBay/Shopify) is out of scope this pass (roadmap).

## 6. TEST CONTRACT (`test_shell.cjs` additions or `test_listingforge.cjs`)

- Shell mounts `#/listingforge`, 6 sub-views switchable.
- Scoring math: seeded fixture scores render exactly; total = weighted sum.
- Compliance: fixture with a medical-claim term → `block` pill; superlative → `warn`.
- Keyword Bridge: 251-byte backend term → over-cap flag; duplicate → duplicate flag.
- Voice chip enforces brand (Word Coffee copy guidance shows "not a beverage" note).
- Zero `fetch` calls across all ListingForge interactions.

## 7. BUILD ORDER

1. Fixtures (`demo-listings.json`).
2. Studio + Scoring (dial), Compliance pills.
3. Media grid + Keyword Bridge.
4. Feedback loop + voice chip.
5. Tests green; commit; update `00_STATE.json`.