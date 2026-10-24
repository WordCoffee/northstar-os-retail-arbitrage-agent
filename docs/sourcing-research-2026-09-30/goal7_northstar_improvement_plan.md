# GOAL 7 — Northstar Improvement Plan (prioritized)

**Date:** 2026-09-30 · **Status:** COMPLETE
Classification: **P0** prevents compliance failure / bad buys / wrong pack match / account risk / capital loss · **P1** improves accuracy/speed/conversion/replenishment · **P2** scale/automation later.

For each: *user problem · workflow · data fields · evidence sources · hard gates & UNKNOWN behavior · human approval · dependencies · paid provider? · DoD.*

## P0 — must exist before any buying

### P0-1 Brand-Permission Register
- **Problem:** unauthorized/gated brand listing → account risk, capital loss.
- **Workflow:** per brand record authorization status; LOA/policy URL; date; scope (Amazon allowed?); reviewer.
- **Fields:** `brand`, `authorization_status{ALLOWED|PROHIBITED|UNKNOWN}`, `evidence_url`, `evidence_date`, `loa_on_file`, `scope`.
- **Evidence:** brand/supplier written policy, authorized-distributor page.
- **Gates:** no candidate advances to QUALIFIED unless `ALLOWED`; UNKNOWN → REVIEW; NEVER infer from silence.
- **Human approval:** required to set ALLOWED.
- **Dependencies:** file/evidence vault. **Paid provider:** no.
- **DoD:** 0 candidates can reach QUALIFIED with `authorization_status != ALLOWED` (unit tests).

### P0-2 Invoice-Quality Scorer
- **Problem:** Amazon rejects invoices lacking identity/quantity/date.
- **Workflow:** score an invoice: business name match, address match, quantity ≥ threshold, ≤180 days, manufacturer/distributor source.
- **Fields:** `invoice_id`, `supplier`, `business_name_match`, `qty`, `invoice_date`, `source_type`, `pass/fail`, `reasons`.
- **Evidence:** Amazon invoice-policy pages (Seller Central). **Gates:** fail → item cannot be submitted for ungating.
- **Human approval:** no (deterministic). **Paid provider:** no.
- **DoD:** fails any missing-identity/quantity/aged invoice.

### P0-3 Amazon Gating State (explicit)
- **Problem:** gating UNKNOWN treated as allowed.
- **Workflow:** explicit `GATING{UNGATED|GATED|UNKNOWN}` + `brand_auth_required`.
- **Data/evidence:** authorized seller account (out of scope) OR brand policy → else UNKNOWN.
- **Gates:** GATED/UNKNOWN cannot reach QUALIFIED/`PURCHASE_READY`.
- **DoD:** no candidate reaches `PURCHASE_READY` with GATING≠UNGATED.

### P0-4 Unknown-Fee / Unknown-Cost Hard Block (reinforce)
- **Problem:** unknown fee treated as zero → false margin.
- **Gates:** any unknown fee/cost → FEE_UNKNOWN → block.
- **DoD:** existing economics suite already enforces; extend to FBA size-tier + prep + returns.

## P1 — accuracy / speed / conversion

### P1-1 Supplier Account CRM
- Track application status, required docs (EIN, resale cert, license), terms, MOQ, price tiers, contacts, notes. **Paid:** no. **DoD:** each shortlisted supplier has a status + doc checklist.

### P1-2 Club Price Snapshotter (Costco/Sam's/BJ's)
- Timestamped exact-unit prices; freshness policy (reuse `freshness.py`); UNKNOWN when stale. **Evidence:** public product pages. **Paid:** no. **DoD:** stale prices become UNKNOWN, never gate-usable.

### P1-3 Test-Order Tracker
- 3–5 unit test → invoice acceptance → actual landed cost → reorder gate. **DoD:** no reorder without a passed test.

### P1-4 Brand/MAP Policy Register
- Per brand MAP/channel restrictions + URL/date. **DoD:** MAP shown on every candidate.

## P2 — later scale

- P2-1 OA bulk-scan adapter contract (supplier-catalog → candidates) — provider-neutral.
- P2-2 YouTube transcript/lead pipeline (leads only, never authoritative).
- P2-3 Scope/brand analytics + replenishment forecasting.

## Cross-cutting requirements (all items)

- **UNKNOWN behavior:** any missing gate → REVIEW, never PASS.
- **Human approval:** always required before purchase/listing.
- **External permission/paid provider:** flagged per item; none of P0 needs a paid provider.
- **Evidence preservation:** URL + quote + date + timestamp on every fact.
- **Testable DoD:** each item ships with unit tests (existing suite patterns).
