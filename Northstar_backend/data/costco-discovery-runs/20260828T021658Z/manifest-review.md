# Costco Discovery Manifest - Review Report

**run_id:** 20260828T021658Z
**generated_at:** 2026-08-28T02:16:58Z
**manifest_fingerprint_sha256:** e325264fa989758d93c11b72eb7c12d833e7800dc28611bac7ed6ed8bd7de3db
**provider (on success):** UNWRANGLE_COSTCO
**max_requests:** 15  **retries:** 0
**evidence_class_on_success:** live_verified
**sourcing_status:** discovery_only
**purchase_authorized:** false

## Product identity evidence available BEFORE lookup (15 frozen items)

All 15 requested Costco items were taken verbatim from the operator master worksheet
($src). Each carries an explicit Costco item number and title, so every target is
addressable by item_number lookup. UPC/GTIN was not present in the source and is
recorded as Unknown (null-first); it would be populated only by a future live response.

| # | item_id | requested_title | brand | requested_pack | UPC/GTIN | lookup_method | inclusion | ambiguity | mapped_asins |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 424976 | Adult 50+ Mature Multi Vitamins & Minerals, 400 Tablets | Kirkland Signature | 400 Tablets | Unknown | item_number | eligible | none | B00P8ZAWK0, B00NPQZ20O, B00YGMN122 |
| 2 | 926628 | Fish Oil 1000 mg, 400 Softgels | Kirkland Signature | 400 Softgels | Unknown | item_number | eligible | none | B002VLZHLS |
| 3 | 1586629 | Aller-Flo 50 mcg Allergy Spray, 720 Metered Sprays, 5 bottles | Kirkland Signature | 5 bottles (720 sprays) | Unknown | item_number | eligible | none | B08R2SRN88, B01H40O42I |
| 4 | 1349614 | OPTIFIBER, 26.8 Ounces, 190 Servings | Kirkland Signature | 190 Servings | Unknown | item_number | eligible | none | B01KW9KWW4 |
| 5 | 1493188 | Baby Wipes Fragrance Free, 900-count | Kirkland Signature | 900-count (9x100ct) | Unknown | item_number | eligible | none | B00SWZUC8U, B014K3BF24 |
| 6 | 1665191 | Glucosamine & Chondroitin, 280 Tablets | Kirkland Signature | 280 Tablets | Unknown | item_number | eligible | none | B00GYZWNY6 |
| 7 | 690843 | Quick Dissolve B-12 5000 mcg, 300 Tablets | Kirkland Signature | 300 Tablets | Unknown | item_number | eligible | none | B00AQ0LMTC |
| 8 | 393914 | Extra Strength D3 50 mcg (2000 IU), 600 Softgels | Kirkland Signature | 600 Softgels | Unknown | item_number | eligible | none | B01NCRITAE |
| 9 | 98268 | Vitamin C 1000 mg, 500 Tablets | Kirkland Signature | 500 Tablets | Unknown | item_number | eligible | none | B015WRSJCQ |
| 10 | 98501 | Chewable Vitamin C 500 mg, 500 Tablets | Kirkland Signature | 500 Tablets | Unknown | item_number | eligible | none | B07881PTTX, B00MPYTSGG |
| 11 | 98211 | Vitamin E 180 mg (400 IU), 500 Softgels | Kirkland Signature | 500 Softgels | Unknown | item_number | eligible | none | B005ECOBBI |
| 12 | 1089787 | Flex-Tech 13-Gallon Kitchen Trash Bag, 200-count | Kirkland Signature | 200 count | Unknown | item_number | eligible | none | B001UB44SM |
| 13 | 87507 | 10-Gallon Wastebasket Liner, Clear, 500-count | Kirkland Signature | 500 count | Unknown | item_number | eligible | none | B01M7Y0NEX |
| 14 | 1652990 | Premoistened Flushable Wipes, Fragrance Free, 640-count | Kirkland Signature | 640-count | Unknown | item_number | eligible | none | B07H4YC1GC |
| 15 | 1755436 | 18-Gallon Compactor & Kitchen Trash Bag, 70-count | Kirkland Signature | 70-count | Unknown | item_number | eligible | none | B01LNBDORK |

## Ambiguity / exclusion flags

**None.** No title, quantity, pack, or UPC record is ambiguous. The "Different pack"
flags observed earlier (B01KW9KWW4, B00NPQZ20O, B014K3BF24, B00GYZWNY6, B01NCRITAE,
B07881PTTX) are **Amazon-side pack mismatches** against the Costco item, not ambiguity
in the Costco lookup target (the Costco item number is explicit). Four item numbers are
shared across multiple Amazon ASINs (424976, 1586629, 1493188, 98501) but each remains a
single, unambiguous lookup target.

## Next step (requires separate explicit authorization)

The next step would be ONE live request per frozen item, for a **maximum of 15 requests**,
**zero retries**. An item-level provider failure (HTTP 401/403/429/5xx, timeout, or
malformed response) STOPS further requests unless I explicitly approve otherwise.

## Provider-call / credit disclosure

**No provider call or credit spend occurred during manifest persistence.** This artifact
was written entirely offline. Unwrangle / Costco / Amazon / any other provider was NOT
contacted. No .env, credential, cache, catalog, benchmark, financial, provider, or CSV
source file was read or modified.

## Invoice-backed sourcing disclaimer

Costco discovery pricing does NOT establish invoice-backed sourcing. Any price returned
by a future lookup is sourcing_status = discovery_only / cost_status = detail_only
(research-only) and is NOT purchase-authorized. A Business Center invoice is required to
confirm real paid unit costs before any buying decision.
