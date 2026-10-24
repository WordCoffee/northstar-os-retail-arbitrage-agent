# GOAL 3 — Office-Supply Priority Pricing Research

**Date:** 2026-09-30 · **Status:** PARTIAL — no supplier account exists, so exact wholesale prices are **UNKNOWN**. This file gives the framework, exact-unit normalization rules, candidate SKUs/UPC targets, and the Costco/Sam's/BJ's comparison method to run once accounts/price lists exist.
**Rule:** Faire = data only (banned as supplier). Never invent pricing.

## A. Office-only supplier priority (from Goal 2)

1. Bulk Office Supply (no-application, commodity SKUs)
2. uOffice Supply (importer/distributor)
3. S.P. Richards (strongest office channel; resale cert required)
4. Kole Imports / DollarDays (general/closeout)
5. Bazic / ACCO dealer accounts

## B. Exact-unit normalization rules (must hold before comparison)

- Compare **cost per sellable unit**, not per case: `unit_wholesale = case_price / pack_count`.
- Capture **UPC/GTIN** and **MPN**; confirm pack identity (`pack_count_claimed` vs actual units).
- Convert to a single currency/rounding; keep `Decimal`-style precision.
- Flag `pack_match_state` UNKNOWN unless UPC/GTIN matches exactly.
- Unknown fees/costs are never zero.

## C. Candidate office SKU/UPC target classes (hypothesis, to price)

Classes where independent wholesale *may* beat warehouse clubs: long-tail SKUs, specialty filing/binding, janitorial, toner, niche furniture accessories, multi-packs of writing instruments with high SKU velocity. Commodities clubs usually win: copy paper (cases), basic pens/pencils, generic sticky notes, basic folders, trash liners.

| Class | Example target SKUs/UPCs | Status |
|---|---|---|
| Copy/print paper | (case, 10-ream) — club commodity | commodity → club likely wins |
| Writing instruments | Bazic multi-packs; ACCO/Newell brand packs | need UPC + wholesale price |
| Filing/binding | Smead folders, GBC/Fellowes binding | brand verification needed |
| Janitorial | SPR JanSan lines | SPR account needed |
| Toner/ink | brand-restricted (gating risk) | HIGH RISK |
| Desk/tech accessories | Kensington (ACCO), Fellowes | brand channel |

*No exact SKUs are asserted as verified — owner obtains price lists per account; then fill the table.*

## D. Exact-unit price comparison table (TEMPLATE — fill after price lists)

| SKU/UPC | Supplier | Case $ | Pack | **Unit $ (sup)** | Costco | Sam's | BJ's | Best source | Evidence date |
|---|---|---|---|---|---|---|---|---|---|
| (pending) | — | — | — | — | — | — | — | UNKNOWN | — |

## E. Costco / Sam's / BJ's comparison method (public pages only)

1. Identify exact UPC/GTIN and pack.
2. Look up public product pages (Costco.com, SamsClub.com, BJs.com); record price, pack, date.
3. Normalize to unit price; compare with supplier unit cost.
4. Compute Amazon net (price − referral − FBA − prep − shipping) using current fee data; ROI = net/landed.
5. Mark any price older than policy max age as CACHED/UNKNOWN (never gate-usable).

## F. Best initial account targets ranking (office)

1. **Bulk Office Supply** — fastest to test; commodity SKUs; invoices on request (brand permission NOT covered).
2. **uOffice Supply** — importer, ecommerce-friendly.
3. **S.P. Richards** — highest legitimacy office channel once resale certificate ready.
4. **Bazic / ACCO dealer** — manufacturer/dealer legitimacy.

## G. Test-order suitability

- Low: any brand requiring Amazon authorization (gating risk).
- Medium: Bulk Office Supply / uOffice Supply commodities (test 3–5 SKUs, exact UPC, verify invoice acceptance).
- High-verification: SPR/ACCO/Bazic once accounts exist.

## H. Limitations
Prices, MOQ, and eligibility are behind accounts → **UNKNOWN**. Amazon gating → **UNKNOWN** (needs authorized seller account). No purchases approved.
