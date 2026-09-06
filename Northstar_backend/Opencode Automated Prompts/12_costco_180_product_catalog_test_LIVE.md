STATUS: PENDING

# BATCH 12 — Costco 180-Product Catalog Live Test — REQUIRES FRESH NAMED APPROVAL

Scope: live-test every one of the 180 tracked Kirkland products in
`data/costco-items.csv` against the Bright Data Web Unlocker Costco detail
adapter (`bright_data_costco.py`), using the prepared run manifest built by
`bright_data_costco_prepare.py`, plus the new gated search lookup
(`bright_data_costco_lookup.py`) for the 18 products that the offline resolver
could not map to an item number.

This batch is NOT part of the automatic batch chain (Batch 11 remains the final
auto batch). It is a standalone bound spec. It MUST NOT start until the operator
explicitly approves it by name — including the paragraph below — inside a fresh
instruction. Building and testing the code for this batch is complete and needs
no approval; EXECUTING the live steps does.

## Approvals needed before ANY live step (quote back in your approval)
1. Approve live Costco item-detail refreshes of the resolved 162 products via
   the Bright Data Web Unlocker (1 credit per item, zero retries, sequential
   pacing ~2.0s, circuit breaker on hard failure).
2. Approve live Costco SEARCH lookups for the 18 unresolved products via
   `bright_data_costco_lookup.py` (1 credit per query) — this is a NEW
   endpoint type (site search) not covered by the item-number flat-URL
   approvals from earlier batches.
3. Approve follow-up detail refreshes on the lookup-derived candidate ids.
4. Confirm the credit budget (up to 162 + 18 + follow-ups; the free Bright Data
   shared pool is 5,000/mo) and that `.env` is NOT read or written by the tool.

## Prepared artifacts (already built, offline, tested)
- `Northstar_backend/data/catalog/brightdata_costco_180_prepared_manifest.json`
  — 180 items: item_id (or null), requested_title/brand/pack,
  costco_cost_reference, resolution classification + provenance.
- `Northstar_backend/data/catalog/brightdata_costco_180_resolution_audit.csv`
  — human-readable audit of the same resolution.

Resolution summary (offline, 2026-09-06T03:44:23Z, deterministic, no live calls):
- 156 resolved_catalog_exact   (normalized-name equality vs 2026-08-14 capture)
- 2   resolved_manifest_seed   (frozen discovery manifest, operator-verified ids)
- 3   resolved_catalog_fuzzy   (reviewed allowlist: AA Batteries 2322010,
       Pure Sea Salt 384732, Elegant Plastic Plates 1343253 — low-confidence
       entry flagged manual_verify)
- 1   resolved_catalog_alt_for_dead  (Baby Wipes 900: manifest seed 1493188 is
       live-CONFIRMED dead; catalog candidate 1493488 substituted, MUST verify)
- 18  unresolved_needs_lookup  (apparel, laundry, bath tissue, paper towels,
       coffee K-cups, dog food, minoxidil, mattress, crushed red pepper, etc.)

## Step 1 — Pre-flight (no network call)
- Confirm `data/costco-api-catalog.json` still present (capture 2026-08-14).
- Confirm the prepared manifest fingerprint matches
  `brightdata_costco_180_prepared_manifest.json` as regenerated 2026-09-06.
- Presence-only (not values) env checks: `BRIGHTDATA_UNLOCKER_API_KEY`,
  `BRIGHTDATA_UNLOCKER_ZONE` SET/NOT SET. Report only SET/NOT SET.
- Confirm `BRIGHTDATA_COSTCO_DETAIL_ENABLED` is NOT set (fail-closed default).
- List the 18 lookup-target products for approval transparency.

## Step 2 — Lookup the 18 unresolved items (LIVE AUTHORIZED ONLY on approval)
- Run: `python bright_data_costco_lookup.py resolve --unresolved-from
  data/catalog/brightdata_costco_180_prepared_manifest.json
  --run-dir <new run dir, NOT the frozen 20260828T021658Z dir>`
- One request per query, zero retries, sequential pacing, circuit breaker on
  hard failure. Evidence (raw + normalized, scrubbed) persisted per item.
- Report each item's top candidate id + score; do NOT auto-trust — every
  candidate must be verified by a Step-4 detail refresh before use.

## Step 3 — Build the final 180-item run list (offline)
- Merge: 162 resolved ids + lookup-confirmed ids for the 18 (where lookups
  produce a verifiable candidate) + any operator-supplied ids.
- Persist as a second prepared manifest (from the lookup results).

## Step 4 — Detail refresh of the full list (LIVE AUTHORIZED ONLY on approval)
- Run: `python bright_data_costco.py details refresh --item-ids <all ids>
  --expected-json <final prepared manifest> --run-dir <new run dir>`
- One request per item, zero retries, ~2.0s pacing, circuit breaker halts the
  batch on auth/http/transport/config errors; url_not_found/no_data_found are
  soft per-item failures that continue.
- Every item gets raw + normalized evidence, scrubbed.

## Step 5 — Report
- Table: tracked product, resolved item id, returned title, price, pack,
  identity status (probable_match/unverified/url_not_found/no_data_found),
  costco_cost_reference vs returned price, resolution class.
- Flag EVERY manual_verify / alt_for_dead item explicitly.
- Credits consumed (documented request attempts) on completion.
- Explicit statement: "All Costco output is discovery-only evidence. It does not
  establish invoice-backed sourcing, Amazon sellability, purchase authorization,
  or durable unit economics." No follow-up Amazon workflow in this batch.

## End of batch
Append a history entry to `00_STATE.json` recording counts, evidence paths,
failures, and this batch's own close-out. Do NOT set `next_batch` — the auto
chain ended at Batch 11; this is operator-invoked only.