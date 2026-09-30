# P4-T1 Pack-count diagnostic (Lane A) — 2026-09-29

Read-only diagnostic against the companion pipeline DB
`fba-product-screener/data/northstar.db` (no writes, no live calls, no invented
data). Status: PARTIAL — the diagnostic is produced; the reader is NOT yet fixed
(two required sources are unread).

## Counts (real, read-only)

- `amazon_identifier_crosswalk` rows: **7343** — `pack_match_state` = `UNKNOWN` for **7343/7343**.
- `sourcing_opportunities` rows: **9454**
  - `supplier_sellable_unit_pack_count` NULL: **9454/9454**
  - `marketplace_sellable_unit_pack_count` NULL: **9454/9454**
  - `case_to_sellable_unit_conversion_status` NULL: **9454/9454**
  - `pack_normalization_confidence` NULL: **9454/9454**
- `amazon_catalog_records` rows: **5086** — `pack_count` NULL: **5086/5086**.
- `ss_product_observations` table present in `data/northstar.db`: **NO (0)** — the
  reader expects it under an attached schema `ssdb.ss_product_observations`.

Prior run report (`data/identity_layer_run/identity_layer_report.md`):
LANE A total=9454, EXACT_UPC=0, EXACT_ASIN=0, STRONG=0, **CANDIDATE=7379**,
CONFLICT=0, NONE=2075.

## Split of the CANDIDATE cap (why EXACT_*/STRONG are 0)

The reader's hard rule `apply_pack_cap` caps EXACT_*/STRONG at CANDIDATE when the
pack is not known-equal. With the current data the split is:

| Cause | Count |
|---|---|
| supplier pack unknown | 9454 / 9454 (100%) |
| marketplace pack unknown | 9454 / 9454 (100%) |
| true pack mismatch | 0 (no populated values to mismatch) |

No padded matches: nothing was promoted; `pack_known_equal` is False everywhere,
so every would-be EXACT/STRONG pair is correctly HELD at CANDIDATE.

## Pack columns read by the reader (`northstar_identity_layer.py`)

- `sourcing_opportunities.supplier_sellable_unit_pack_count` (read, all NULL)
- `sourcing_opportunities.marketplace_sellable_unit_pack_count` (read, all NULL)
- `amazon_catalog_records.pack_count` (read, all NULL) and `unit_count` (selected)
- `ssdb.ss_product_observations.pack_count_claimed` → mapped to `pack_text`
  (read attempt; **source absent**) 

## CORRECTION (2026-09-29, P4-T2)

The earlier "ss_product_observations absent" claim was WRONG — it was based on a
`northstar.db`-only check. The reader attaches the companion
`fba-product-screener/data/products.db` as schema `ssdb`, and that DB **does**
contain `ss_product_observations`:
- rows: **109,421**
- `pack_count_claimed` non-null: **26,436**

So the SellerSprite historical export IS available. What remains is reader
usage: `_load_ss` maps `pack_count_claimed` to `pack_text` and Lane A parses it
with `extract_pack` (the numeric claimed count is not used directly), and
`amazon_identifier_crosswalk.pack_match_state` was not read at all.

Reader wiring (tested semantics) added in the companion repo (commit `bb48ab8`):
`pack_known_equal_with_crosswalk` — MISMATCH forces not-equal; MATCH never
upgrades an unknown pack; UNKNOWN passes through. Companion test 5/0. Full
identity-layer rerun NOT executed this session (pending); counts above are
before-state.

## Unread sources (CORRECTED)

1. **`ss_product_observations.pack_count_claimed`** — the table IS present in the
   companion `products.db` (109,421 rows; `pack_count_claimed` non-null 26,436)
   and is attached as `ssdb`. It is currently read only as free text
   (`pack_text`) and parsed by `extract_pack`; the numeric `pack_count_claimed`
   is not used directly. Prior run notes SellerSprite ASIN coverage 56/9,245
   PalletFly ASINs and an empty pilot list (a coverage limit, not an absence).
2. **`amazon_identifier_crosswalk.pack_match_state`** — now READ by
   `northstar_identity_layer.py` (companion commit `bb48ab8`), corroborative only:
   MISMATCH forces not-equal; MATCH never upgrades an unknown pack; UNKNOWN
   passes through. Companion test `tests/test_pack_crosswalk_semantics.py` 5/0.

## Remaining work to reach DONE

- Use `pack_count_claimed` numerically (not only text parsing) and/or capture
  manual observed pack evidence via the provenance model.
- Populate supplier/marketplace pack fields upstream (all NULL today).
- Rerun the identity layer end-to-end and confirm idempotent counts + still no
  padded matches (NOT executed this session).
- Note: SellerSprite is a ONE-TIME historical export only; no renewal/live use.

Research identity-match only. Not a purchase recommendation or authorization.
