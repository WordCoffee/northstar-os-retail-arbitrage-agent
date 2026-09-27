# Provider Export Import Guide (SellerAmp)

This guide explains how to manually export data from SellerAmp
(Seller Assistant), import those exports locally into NorthstarOS, and validate
them — entirely offline. **Amazon.com is never directly scanned, scraped, or
automated.** All Amazon-market facts come only from your approved provider
exports or sanctioned provider integrations.

> **SellerSprite was retired 2026-09-27** (trial expired). It is no longer a
> supported provider: there is no adapter, importer, CLI command, schema, or
> sign-in service. `--provider sellersprite` fails closed as retired.
> SellerAmp is the only current provider direction; its implementation is
> offline export/import only (not a live integration).

## 1. Source-to-decision workflow (overview)

```text
1. Import Costco / approved source catalog       costco-non-kirkland:import-costco
2. Exclude Kirkland + disallowed classes         (automatic at import)
3. Create provider lookup manifest               costco-non-kirkland:create-provider-manifest
4. Operator signs into SellerAmp              (manual, research browser)
5. Operator records sign-in                      costco-non-kirkland:signin --done
6. Operator exports data (CSV/JSON)              (manual in the provider UI)
7. Operator imports the file locally             costco-non-kirkland:import-selleramp
8. System maps fields -> market snapshots        (provider_imports.mapping)
9. Validate identity / competition / economics   costco-non-kirkland:validate-identity / score
10. Conservative economics + ranking              costco-non-kirkland:score
11. Human approval queue                         costco-non-kirkland:approval-*
12. Exports                                      costco-non-kirkland:export-ranked
```

## 2. How to export data manually

### SellerAmp / Seller Assistant

1. Log in to your SellerAmp (SAS) account.
2. Open the lookup / product analysis screen for the ASIN.
3. Export the result (CSV/JSON) via the available export control.
4. Save the file locally.

> The export is not fetched by Northstar. You download the file in your own
> browser and import it from disk. The pipeline never opens the provider UI,
> never reuses your session, and never reads cookies or tokens.

## 3. Supported import files

| Provider | CSV | JSON |
|----------|-----|------|
| SellerAmp / Seller Assistant | ✅ | ✅ |

- File type is auto-detected from the extension (`.csv` / `.json`).
- Provider is auto-detected from column hints; if ambiguous, pass
  `--provider selleramp` explicitly.
- Unsupported files are rejected (fail closed) rather than guessed.
- Retired-provider files (e.g. a file named `*sellersprite*`) are rejected as
  retired/unsupported.

## 4. Required / supported fields

Imported fields are mapped into a canonical market snapshot. Every field keeps
provider provenance (filename, SHA-256, row number, observed/ingested time,
provider-reported flag). Unavailable fields stay `unknown` / `not_reported` —
never zero.

Canonical groups: **identity** (ASIN, parent ASIN, title, brand, manufacturer,
UPC, EAN, MPN, model, product type, variation, item/pack/unit count, unit
measure), **marketplace** (buy-box price, lowest/FBA/MFN prices, seller counts,
Amazon Retail active, brand-owner seller, price stability), **demand** (BSR,
category, timestamp, est. monthly sales/revenue, confidence), **fees/size**
(referral fee, FBA fee, storage, shipping weight, dimensions, size tier,
standard-size), **risk** (sellability, category/brand/product restriction,
hazmat, dangerous goods, meltable, expiration, compliance).

See `costco_non_kirkland/provider_imports/schemas.py` for the exact column →
canonical mapping for each provider.

## 5. Import rules

- **Idempotent**: re-importing the same file (same SHA-256 + row) does not
  create duplicate snapshots (reported as `duplicate`).
- **Dry run** (`--dry-run`): parses, validates, maps, and reports without
  writing to the database.
- **Strict** (`--strict`): rejects any row missing required qualification
  fields.
- **Allow partial** (`--allow-partial`): saves incomplete rows as
  `needs_enrichment`, never as qualified.
- **Never stores** credentials, cookies, session tokens, or account identifiers
  (beyond an optional non-secret provider label).
- Every command prints `Network calls made: 0`.

Row outcomes: `imported`, `duplicate`, `rejected`, `needs_mapping`, `stale`,
`missing_required_fields`, `identity_ambiguous`.

## 6. Dry run

```bash
cd Northstar_backend
python -m costco_non_kirkland.cli import-selleramp --file <export.csv> --dry-run
```

Expected output includes:
```text
Network calls made: 0
rows_total: N
rows_imported: N
row_status_counts: { imported: N, ... }
confirmation: Network calls made: 0
```

## 7. Real import + validate

```bash
python -m costco_non_kirkland.cli import-selleramp --file <export.csv>
python -m costco_non_kirkland.cli validate-market-snapshots --provider selleramp
python -m costco_non_kirkland.cli validate-identity
python -m costco_non_kirkland.cli calculate-economics
python -m costco_non_kirkland.cli score
python -m costco_non_kirkland.cli export-ranked
```

## 8. Addressing issues

- **needs_mapping**: an unknown column/key wasn't recognized; add it to the
  provider schema in `schemas.py` and re-import.
- **needs_enrichment**: required market fields are missing/unknown/stale —
  re-export a complete provider file, or pass `--allow-partial` to save them as
  needs-enrichment rows.
- **manual_review_required**: identity is ambiguous (title-only, variation,
  split-pack) — review the candidate and the provider listing manually.
- **identity_ambiguous**: the ASIN failed validation (not 10-char
  alphanumeric) or identity could not be confirmed.

## 9. Mapping limitations by provider

- **SellerAmp**: some risk/restriction fields may not be exported; they remain
  `not_reported` and do not become favorable/negative. Monthly sales/revenue are
  **provider estimates**, not verified Amazon figures.
- No provider exposes an official stable export schema guarantee; the
  importer fails closed on unknown files rather than guessing.

## 10. Licensing / account limitations

- You are responsible for SellerAmp terms and for keeping your
  own account credentials secret.
- The pipeline never authenticates to these services; sign-in confirmation is
  purely a local operator record with a 6-hour TTL.
- No product should be purchased based solely on an automated recommendation —
  approval requires a human decision record (see `purchase-approval-workflow.md`).