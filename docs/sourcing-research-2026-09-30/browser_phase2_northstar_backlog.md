# Browser Phase 2 — Evidence-Based Northstar Backlog (Goal 7)

**Date:** 2026-09-30
Each item: user problem · evidence source · workflow · data fields · hard disqualifiers · UNKNOWN behavior · human approval point · external/provider dependency · testable DoD.

## P0 — prevents compliance failure / wrong pack / ineligible purchase / bad economics / capital loss

### P0-1 Brand-Permission Register
- **Problem:** listing an unauthorized/gated brand risks account action and dead capital.
- **Evidence:** Bulk Office Supply explicitly says it "cannot say if you will be permitted to sell a specific brand" (bulkofficesupply.com/Resellers.aspx); Amazon invoice/authorization policy.
- **Workflow:** record per brand: authorization status, evidence URL/quote, date, scope, LOA file.
- **Fields:** brand, `authorization_status{ALLOWED|PROHIBITED|UNKNOWN}`, evidence_url, evidence_quote, evidence_date, loa_on_file, reviewer.
- **Hard disqualifier:** `PROHIBITED` or brand-gated without written vendor authorization.
- **UNKNOWN behavior:** blocks progression (REVIEW), never PASS.
- **Human approval:** required to set ALLOWED.
- **External/provider:** none.
- **DoD:** test proves no candidate reaches QUALIFIED with authorization ≠ ALLOWED.

### P0-2 Invoice-Quality Scorer
- **Problem:** Amazon rejects invoices lacking business identity/quantity/recency.
- **Evidence:** Amazon Seller Central invoice policy; transcripts 3/4/9 (leads).
- **Workflow:** score invoice fields; block if any fail.
- **Fields:** supplier, business_name_match, address_match, qty, invoice_date, source_type (manufacturer/distributor/retail), pass/fail, reasons.
- **Hard disqualifier:** retail receipt, missing business name/address, qty below threshold, >180 days.
- **UNKNOWN behavior:** unknowns fail closed.
- **Human approval:** none (deterministic).
- **External:** none.
- **DoD:** unit tests reject each missing field.

### P0-3 Explicit Amazon Gating State
- **Problem:** gating UNKNOWN treated as ungated.
- **Evidence:** Amazon gating/invoice policy (authoritative); no public gating source exists.
- **Fields:** `gating{UNGATED|GATED|UNKNOWN}`, `brand_auth_required`.
- **Hard disqualifier:** GATED or UNKNOWN.
- **UNKNOWN behavior:** REVIEW only.
- **Human approval:** to set UNGATED (requires authorized seller evidence).
- **External:** authorized seller account (SP-API) — out of scope now.
- **DoD:** no candidate reaches `PURCHASE_READY` with gating ≠ UNGATED.

### P0-4 Unknown-Fee / Unknown-Cost Hard Block
- **Problem:** unknown fee treated as zero → false margin.
- **Evidence:** existing economics suite; Tactical Arbitrage markets accurate fee calc (benchmark).
- **Fields:** fee stack (referral, FBA size tier, prep, inbound, storage, returns), costs.
- **Hard disqualifier:** any UNKNOWN component.
- **DoD:** existing tests extended to FBA size-tier + prep + returns.

## P1 — materially improves research speed/quality

### P1-1 Supplier Account CRM
- **Problem:** application status/docs/MOQ/tiers scattered.
- **Evidence:** multiple suppliers require resale cert/license (Bulk Office Supply, Kelco, Creative Co-Op, Essendant monthly minimums).
- **Fields:** supplier, account_status, docs_required, docs_on_file, MOQ, price_tier, terms, contact, notes.
- **DoD:** each shortlisted supplier has status + doc checklist; Essendant flagged "monthly minimums".

### P1-2 Club Price Snapshotter (Costco/Sam's/BJ's)
- **Problem:** no current exact-unit club comparison.
- **Evidence:** Goal 2/3/4 comparison method; freshness policy (`freshness.py`).
- **Fields:** UPC, club, price, pack, unit_price, source_url, captured_at, freshness_state.
- **Hard disqualifier:** stale → CACHED/UNKNOWN (never gate-usable).
- **DoD:** stale prices cannot pass a gate.

### P1-3 Test-Order Tracker
- **Problem:** reorder without verified landed cost/invoice acceptance.
- **Fields:** candidate, test_qty (3–5), invoice_status, actual_landed_cost, reorder_decision.
- **DoD:** no reorder without a passed test.

### P1-4 MAP/Channel Policy Register
- **Problem:** MAP/channel violations.
- **Evidence:** transcript 9 (MAP concept); brand policies.
- **Fields:** brand, map_price, channel_restrictions, evidence_url/date.
- **DoD:** MAP shown on every candidate.

## P2 — after P0/P1
- P2-1 provider-neutral OA bulk-scan adapter contract.
- P2-2 YouTube transcript/lead pipeline (leads only; never authoritative).
- P2-3 brand/scope analytics + replenishment forecasting.

## Cross-cutting
Any missing gate → REVIEW, never PASS. Human approval before purchase/listing. Faire never a supplier. Evidence URL+quote+date on every fact.
