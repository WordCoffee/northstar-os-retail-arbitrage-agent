# 14 — Migration Dry-Run Design

## Tool

`Northstar_backend/tools/foundation_migrate_dryrun.py` — **read-only**.

- Reads the four source stores:
  1. `products` table → `Northstar_backend/data/northstar.db` (SQLite URI `mode=ro`)
  2. scanner caches → `Northstar_backend/data/scanner-search-cache*.json`
  3. SourceScout manifest → `Northstar_backend/data/catalog/sourcescout_manifest.json`
  4. Golden Goose report → latest `Northstar_backend/data/golden-goose-reports/goose_scan_*.json`
- Outputs reconciliation metrics as text or JSON. `writes_performed: 0`, `read_only: true`.

## Measured output (against live source data, read-only)

| Metric | Value |
|---|---|
| products_table records | 1,024 (1,024 valid ASIN) |
| scanner caches (3 files) | 234 + 10 + 89 = 333 |
| sourcescout_manifest | 470 |
| golden_goose_report (latest) | 30 |
| **total source records** | **1,857** |
| distinct Amazon identities `(marketplace,asin)` | **1,628** |
| new product candidates | 1,628 |
| records beyond first occurrence (duplicates) | **229** |
| conflicts (same identity, differing titles) | **151** |
| invalid ASIN | 0 |
| marketplace-unknown / missing ASIN | 0 |
| pack ambiguity (heuristic on titles) | **421** |
| records missing provenance | 1,684 |
| variation ambiguity | 0 (heuristic; deferred — see notes) |

## Proposed mapping

```
catalog_product             = 1,628
product_identifier(asin)    = 1,857
amazon_offer_snapshot       = 1,857
supplier_documentation      = 0   (no invoice data present in sources)
```

## Acceptance thresholds (owner to confirm — Phase 1A §5)

- ASIN validity: 100% (currently 100%).
- Unmapped critical fields: 0.
- All conflicts reviewed before promotion.
- Provenance completeness target ≥ 95% (currently low: 1,684/1,857 records lack an
  explicit provenance field → **the import step must attach provenance**, source, and
  captured_at from the store/file).

## Safety

- The dry run does not change source or target data.
- It must not be run against the production-like DB **except** in this read-only mode
  (the only tool that opens it uses `mode=ro`).
- Promotion of any migration to a real DB is a separate, reviewed Phase 1C action.