# DATA RIGHTS REGISTER (P4-T3)

Authoritative machine register: `Northstar_backend/foundation/data_rights.py`
(`SOURCES`, `rights()`, `customer_safe_rows()`, `export_safe_rows()`, `assert_*`).
This document is the human mirror; the module is the enforcement source of truth.

Rights-status labels: **ALLOWED | PROHIBITED | UNKNOWN**. These are NOT card
statuses and NOT data truth labels. Permission is never inferred from possession,
a free trial, a public page, or the ability to download; internal-use rights do
not imply redistribution; derived scores/summaries do not escape restrictions.
No legal clearance is claimed — unresolved questions are listed.

## Sources actually present / integrated

| Key | Provider / dataset | Status | internal | customer | export | redistribute | derived | external AI |
|---|---|---|---|---|---|---|---|---|
| `sellersprite_historical_export` | SellerSprite `ss_product_observations` (one-time historical export) | INTERNAL_ONLY | ALLOWED | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| `amazon_catalog_records` | Amazon-derived catalog/crosswalk (provenance unverified) | INTERNAL_ONLY | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| `costco_discovery` | Costco public catalog/prices/discovery | INTERNAL_ONLY | ALLOWED | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| `palletfly_historical` | PalletFly historical list refs | INTERNAL_ONLY | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |
| `manual_observed_capture` | Owner first-party observation | CUSTOMER_OK | ALLOWED | ALLOWED | ALLOWED | ALLOWED | ALLOWED | UNKNOWN |

Acquisition/date, account tier, terms URL/version, evidence location, retention,
attribution, deletion requirements, restrictions, and unresolved questions are
recorded per source in the module (`DataSource`). Key unresolved items:
- SellerSprite: customer/export/redistribution/AI uses not reviewed; historical
  terms not captured (only current vendor terms may be findable — a limitation).
- Amazon-derived data: INTERNAL_ONLY until counsel clears; no SP-API / Seller
  Central / automated Amazon access is authorized.
- Costco/PalletFly: customer display + redistribution not reviewed.

## Planned providers (NOT integrated — rights UNKNOWN, no implication of operation)

`dataforseo`, `brightdata` (frozen files exist but not operational), `keepa`,
`amazon_sp_api` (NOT authorized), `amazon_ads` (NOT authorized),
`image_generation`, `email`, `stripe` (test mode only, not integrated). Each is
`NOT_INTEGRATED`; no rights are implied by being planned.

## Enforcement (customer-exposure safety)

External uses require an explicit ALLOWED; UNKNOWN and PROHIBITED are BLOCKED:

- `customer_safe_rows(rows)` — excludes rows whose source is not customer-OK.
- `export_safe_rows(rows)` — excludes rows whose source is not export-OK.
- `assert_customer_display/assert_export/assert_external_ai` — typed
  `DataRightsError` for API/export call sites.
- Owner Test Mode does NOT bypass data rights (tested).
- Retention/deletion: historical dataset is NOT deleted merely because rights are
  unresolved; no destructive canonical change.

Wiring status: no customer-facing surface currently emits historical third-party
rows (P5+ rooms are not built; local tests use SAMPLE fixtures only). The filter
functions are the enforcement boundary; **per-surface wiring is a recorded
dependency (P4-T3b)** and affected beta surfaces remain BLOCKED from serving
historical third-party data until wired and tested. Nothing here weakens provider
arming/spend gates or truth labels.

## Tests

`Northstar_backend/foundation/tests/test_data_rights.py` (9): internal vs external
labels; UNKNOWN blocked; customer/export filters exclude INTERNAL_ONLY and
unknown sources; manual capture allowed; Owner Test Mode does not bypass;
typed errors; planned providers not integrated/blocked; internal≠redistribution.
