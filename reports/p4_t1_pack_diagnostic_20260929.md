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

## Unread sources (exact missing artifacts — do not invent)

1. **`ss_product_observations.pack_count_claimed`** — the table is absent from
   `data/northstar.db`; the reader requires `ssdb.ss_product_observations`
   (SellerSprite DB attached as schema `ssdb`). Prior run also notes SellerSprite
   coverage only 56/9,245 PalletFly ASINs and an empty pilot list.
2. **`amazon_identifier_crosswalk.pack_match_state`** — required by P4-T1 but
   **never read** by `northstar_identity_layer.py` (no reference in the file).
   The reader derives pack equality only from supplier/marketplace/catalog/ss;

## Remaining work to reach DONE

- Attach/provide the SellerSprite observations source (or export
  `pack_count_claimed` into the pipeline DB) — owner/data-availability item.
- Wire `amazon_identifier_crosswalk.pack_match_state` into the pack decision
  (or explicitly justify not using it) in the companion reader.
- Populate supplier/marketplace pack fields upstream (all NULL today).
- Rerun the identity layer and confirm idempotent counts + still no padded matches.

Research identity-match only. Not a purchase recommendation or authorization.
