# SourceScout — Retail Arbitrage Agent — Website Plan & Architecture

> **Status:** Approved for construction (Autonomous Zone) as WRAP & EXTEND.
> **Current state:** the retail arbitrage dashboard at
> `Northstar_backend/static/index.html` is mature and **tested** — 5 views (Scout,
> Calculator, Risk, Cycle, Portfolio), 13-column resizable sortable scout table,
> Authorization Gate, Proof Batch panel, premium dark sidebar/topbar, **986 jsdom
> assertions green** via `test_ui_display.cjs`.

## 1. SERVICE IDENTITY

**Public:** SourceScout — "Scout the source before the sale."
**Internal agent:** Retail Arbitrage Agent.
**Core promise:** product sourcing, margin calculation, sell-through velocity analysis,
Kirkland-to-Amazon arbitrage detection and scoring, live-pull status with typed
failures.

## 2. STRATEGY — WRAP & EXTEND (NOT REBUILD)

- The existing engine owns Scout/Calculator/Risk/Cycle/Portfolio behavior,
  element IDs, `data-view`, JS. **Do not rewrite it.**
- The suite shell hosts it inside `#/sourcescout` by rendering the existing file's
  markup into the shell's Work Surface (or by loading the existing assets in-place
  with the shell around them).
- Apply the Analyst's Desk token layer (CSS custom properties override) so the look
  matches the suite — colors/typography only; structure/behavior untouched.
- **Gate:** `test_ui_display.cjs` must stay green before AND after the wrap.

## 3. EXTENSIONS (new, on top of the tested engine)

1. **Sourcing filter facets** in the suite shell header: ≥5,000 est. monthly units (or
   consistent BSR), ≥20% net margin, buy-box stability, replenishable clean invoice
   path, no gate/variation/return risk, prefer consumables.
2. **Worksheet export** button: exports the currently filtered scout rows to CSV in the
   repo's honest shape (missing → `None`, typed statuses).
3. **Live-pull status banner**: reflects typed failure taxonomy (`url_not_found`,
   `no_data_found`, `transport_error`, `auth_error`, `rate_limited`) from run
   evidence dirs; never fabricates a "success."
4. **Portfolio overview pass-through** from the suite hub global KPIs.

## 4. DATA CONTRACT (unchanged truth anchors)

- Profit model: `Net Profit = Amazon Price − Costco Cost − Referral (0.15×) − FBA Fee −
  (FBA×0.035 surcharge) − Inbound ($0.35) − Prep − Return Reserve; ROI = Net/COGS`.
- Buy thresholds: net ≥ **$11**, ROI ≥ **30%**, confidence ≥ Medium; Cycle 1 = 50 units.
- Risk model 100 pts (Compliance 30 / Margin compression 20 / Seller crowding 15 /
  Price volatility 15 / Packaging 10 / Replenishment 10) → 0–24 Low…75+ Reject.
- Never combine the two Minoxidil models (42.00 vs 37.99) without an explicit label.

## 5. GATED-LIVE PATHS (unchanged, still gated)

- Bright Data Web Unlocker / Firecrawl Costco pulls (cost basis refresh).
- Easyparser / RapidAPI / DataForSEO enrichment runs.
- Amazon listing/pricing/purchase actions — always hard-stop.
All remain `data-live-gate="off"` with off-preflight banners; the existing
Authorization Gate UI already implements this.

## 6. TEST CONTRACT

- Wrap: existing `test_ui_display.cjs` 986 assertions unchanged & green.
- New shell-layer tests: `#/sourcescout` mounts, sourcing facets filter the rendered
  table in-memory, worksheet export writes rows w/ `None` preserved, live-pull banner
  renders typed status from a fixture manifest.
- Zero `fetch` calls across all interactions (matches existing phase assertions).

## 7. BUILD ORDER

1. Token restyle of existing file (CSS vars only) → `test_ui_display.cjs` re-run.
2. Shell hosts the dashboard in `#/sourcescout`.
3. Sourcing facets + worksheet export + live-pull banner.
4. Hub global-KPI pass-through.
5. Tests green; commit; state update.