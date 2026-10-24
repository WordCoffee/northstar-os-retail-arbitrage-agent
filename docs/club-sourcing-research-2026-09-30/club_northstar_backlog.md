# Club Sourcing — Northstar P0/P1/P2 Backlog (Goal 7)

Each item: problem · evidence · data fields · workflow · hard gate · UNKNOWN behavior · human approval · dependencies · testable DoD.

## P0 — prevents bad purchases / account risk
### P0-1 Exact UPC/GTIN + case/inner-pack normalization
- **Problem:** club multipacks have inner units that may not match the Amazon offer.
- **Evidence:** core truth rules (this program); Amazon pack-mismatch risk.
- **Fields:** UPC_GTIN, MPN, pack_count, inner_unit_description, inner_units_independently_sealed, split_eligibility.
- **Gate:** `exact_identity_confidence != VERIFIED` or `split_eligibility != ALLOWED` → block.
- **UNKNOWN:** REVIEW, never PASS. **Approval:** required. **DoD:** unit test blocks SPLIT_NOT_VERIFIED.

### P0-2 Amazon 1P / brand-seller hard exclusion
- **Problem:** competing with Amazon Retail or the brand kills margin/eligibility.
- **Fields:** Amazon_1P_status, brand_seller_status.
- **Gate:** either ACTIVE → REJECTED.
- **DoD:** test rejects 1P/brand-seller candidates.

### P0-3 Club-price freshness + member/location caveats
- **Fields:** club_price, price_observed_at, price_freshness, membership_or_location_caveat.
- **Gate:** stale/member-only-unknown → price-UNKNOWN → REVIEW.
- **DoD:** stale price cannot pass.

### P0-4 Fee completeness / unknown-cost hard block
- **Gate:** any UNKNOWN fee → FEE_UNKNOWN → block.
- **DoD:** extended to FBA size tier/prep/inbound.

### P0-5 Invoice/documentation-risk visibility
- **Fields:** invoice_documentation_risk.
- **Rule:** retail receipts are not universal Amazon invoice evidence.
- **DoD:** risk field displayed on every candidate.

### P0-6 Human approval rail
- **Rule:** no BUY/APPROVED labels; only DISCOVERY_LEAD / EXACT_MATCH_RESEARCH_CANDIDATE / MANUAL_VERIFICATION_REQUIRED / REJECTED / INSUFFICIENT_PUBLIC_EVIDENCE.
- **DoD:** UI/route cannot emit "approved".

## P1 — research quality/speed
- Club catalog import/snapshot format (CSV/JSON schema as in `data/club_sourcing/`).
- Cross-club exact-unit comparator (Costco/Sam's/BJ's same UPC).
- Product/ASIN matching queue with confidence.
- Price/seller-history integration readiness (Keepa-style).
- Test-order + replenishment tracker.
- Clearance/seasonality tracker.
- Category/shipping-risk filters.

## P2 — later
- Opt-in paid data adapters (respect no-paid rule now).
- Location-aware inventory/pricing.
- Mobile scanning workflow.
- Automated alerts subject to approval.

## Scope notes
- Costco/BJ's public extraction blocked → Northstar should support **manual/clipboard import** of club rows rather than relying on scraping.
- Amazon seller/offer screening requires an authorized method; keep `AMAZON_SCREENING_INCOMPLETE` as a first-class state.
