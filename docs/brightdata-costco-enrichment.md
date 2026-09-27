# Bright Data Costco Enrichment (approval-gated)

Bright Data is an **optional, approval-gated** enrichment source for Costco
product identity (UPC/EAN/GTIN, MPN/model, weight, dimensions, pack, brand,
category). It is **disabled by default**. This module never makes a live call
during implementation, tests, imports, API GETs, page loads, or ordinary CLI use.

## Modes

```
disabled            (default)
fixture             (local fixture data only)
dry_run_manifest    (build a proposed sample manifest; zero calls)
approved_live_run   (gated; requires every approval below)
imported_snapshot   (import an operator-provided normalized snapshot)
```

## Fail-closed live gates

A live run requires ALL of:

```
--approved
NORTHSTAR_ENRICHMENT_APPROVED=1
NORTHSTAR_BRIGHT_DATA_ENABLED=1
--max-items N
--spend-cap X
an approved manifest id
an approved source/scraper id
```

Otherwise the adapter returns `requires_explicit_approval` and makes **zero**
calls. It never reads or prints secrets, never uses browser automation, and only
uses a sanctioned API/dataset mechanism if actually configured.

## Field availability must be validated

Marketing claims (GTIN/MPN/weight/dimensions) are **not** assumed. Field
availability is validated on a small, approved live sample before any broader
use. Typed capture outcomes: `field_not_returned`, `field_not_supported`,
`parse_error`, `stale`, `identifier_conflict`, `insufficient_source_identity`,
`provider_unavailable`, `provider_not_configured`.

## Commands (all offline)

```
python -m costco_non_kirkland.cli plan-brightdata-enrichment --run-id <id> --max-items 25 --out manifest.json
python -m costco_non_kirkland.cli validate-brightdata-schema --file <snapshot.json>
python -m costco_non_kirkland.cli import-brightdata-snapshot --file <snapshot.json> [--dry-run]
python -m costco_non_kirkland.cli run-brightdata-enrichment --manifest <id> --approved --max-items 25 --spend-cap X --source-id <scraper>
```

`run-brightdata-enrichment` fails closed (exit 2) unless every gate is set.

## Importing snapshots

Imported snapshots are **not live source truth**. Each imported record preserves
provider provenance (`provider_name`, `provider_snapshot_id`, `snapshot_sha256`,
`captured_at`, `ingested_at`, `field_capture_status`, `field_limitations`) and is
idempotent by file SHA-256. Raw Costco source files are never mutated.

## Approval prompt (before a live run)

```
Northstar Action Required — Bright Data Enrichment Approval

Purpose:
Validate whether the configured Bright Data Costco enrichment source can return
UPC/EAN/GTIN, MPN/model, product weight, dimensions, pack configuration, brand,
and specifications for a capped Costco sample.

Sample size: [count]
Input source: [existing local Costco dataset]
Configured Bright Data source/scraper: [name or unavailable]
Known cost/credit impact: [amount or "not available"]
Spend cap: [cap]
Fields requested: [fields]

No Amazon.com, SellerAmp, ChromeControl, checkout, purchase, or
account-changing action will occur.

To approve this exact run, reply:
Approve Bright Data Costco enrichment for [count] items with spend cap [amount].
```

## Discipline

- No direct Costco browsing; replaces manual identity gaps only.
- No fabricated UPC/GTIN/MPN/weight/dimensions/pack.
- Missing identifiers route to `identifier_resolution_required` (never guessed).
- No purchase authorization; no Amazon access; no browser automation.
