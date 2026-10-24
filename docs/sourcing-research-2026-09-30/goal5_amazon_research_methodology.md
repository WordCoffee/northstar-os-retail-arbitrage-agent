# GOAL 5 — Amazon Product-Research Methodology (repeatable SOP)

**Date:** 2026-09-30 · **Status:** COMPLETE (SOP + decision tree + checklists + do-not-buy)
**Policy posture:** policy-conscious, human-approved, no live purchases.

## A. Repeatable operating procedure (per candidate)

1. **Reverse-source** from a permitted supplier catalog (SPR/Bulk Office/KEY…) → get UPC/GTIN/MPN + case pack + cost.
2. **Normalize identity:** exact UPC/GTIN match; else `pack_match_state=UNKNOWN` (never guess).
3. **Amazon match:** public product page only; capture ASIN, title, brand, buy-box, price, BSR, review count. No SP-API unless authorized.
4. **Eligibility check:** is the brand gated / does it require authorization? If UNKNOWN → treat as UNKNOWN (do not assume allowed). "Not found" ≠ "allowed".
5. **Demand/seller history:** Keepa-style price/BSR/offer-count history; flag high seller count / price collapse / private-label dominance.
6. **Economics:** Amazon price − referral − FBA (size tier) − prep − inbound − storage/returns allowance. Unknown fee = block.
7. **Rights gate:** brand resale permission / authorized distributor; invoice-quality check (identity + quantity + date).
8. **Human approval:** only after all gates PASS. Otherwise → review queue.
9. **Test order:** small (3–5 units) → verify invoice acceptance + actual landed cost → reorder only if economics hold.

## B. Decision tree

```
Candidate
  ├─ UPC exact match? ── no ─► REJECT (pack identity UNKNOWN)
  ├─ Brand permission/authorized? 
  │     ├─ no ─► REJECT (rights)
  │     └─ unknown ─► REVIEW (do not buy)
  ├─ Amazon gating?
  │     ├─ gated ─► REJECT unless authorized for that brand
  │     └─ unknown ─► REVIEW
  ├─ Economics complete (all fees known)?
  │     ├─ no ─► REVIEW
  │     └─ yes ─► net ≥ floor AND ROI ≥ min?
  │                 ├─ no ─► REJECT
  │                 └─ yes ─► QUALIFIED_FOR_REVIEW ─► human approval ─► test order
```

## C. Product-research checklist

- [ ] UPC/GTIN + MPN captured; pack count confirmed against label.
- [ ] Supplier cost per unit (case ÷ pack) with date.
- [ ] Amazon ASIN matched (brand + title + size); note confidence.
- [ ] Buy-box price, BSR, sellers-on-listing, review count.
- [ ] Brand gating status (or UNKNOWN).
- [ ] Brand resale permission / authorized distributor (or UNKNOWN).
- [ ] Full fee stack known (referral, FBA size tier, prep, inbound, storage, returns).
- [ ] Dimensions/weight known (item vs package).
- [ ] MAP/channel restrictions noted.
- [ ] Invoice acceptability (business identity + quantity + ≤180 days).
- [ ] Club comparison (Costco/Sam's/BJ's) at exact unit.
- [ ] Human review sign-off recorded.

## D. "Do not buy" failure modes

1. Pack identity uncertain (case vs each).
2. Brand gated, unauthorized, or authorization inferred from silence.
3. Fee/cost UNKNOWN treated as zero.
4. Heavy/fragile/bulky without exceptional economics.
5. Commodity the club wins on.
6. Price-history collapse / 20+ sellers / race-to-bottom.
7. Private-label or brand-direct competing offer.
8. Invoice cannot show required identity/quantity.
9. No MAP/channel clarity.
10. Any "buy now" without human approval.

## E. Method notes (from public tools research, Goal 6)

- Keepa = price/BSR/offer history. SellerAmp = live profit/eligibility on a deal. Tactical Arbitrage/BuyBotPro/Scan Unlimited = bulk catalog scanning. Use them as **decision aids**; they never replace brand-permission or invoice verification.
