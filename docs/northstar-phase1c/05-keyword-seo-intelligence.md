# 05 — Keyword & SEO Intelligence (1C-05)

**Status:** ✅ **PASS** — RUNTIME_CONFIRMED (SQLite 494 passed / 28 skipped;
disposable PostgreSQL 28 passed; migration harness 9/9).

## Canonical schema (C01)

Additive tables (all organization-scoped): `keywords`, `search_terms`,
`targets`, `keyword_links`, `import_batches`, `source_files`, `source_rows`,
`rejected_rows`, `normalization_decisions`, `rank_observations`,
`ad_performance_observations`, `keyword_conflicts`.

Hard separations (never collapsed):
- keyword ≠ search term ≠ target (three tables).
- organic rank ≠ sponsored placement (`rank_observations.placement`).
- imported data ≠ live data (provenance class `imported`).
- search-volume *estimate* ≠ *observed* volume (separate nullable columns).

Null-first: `search_volume`, `rank`, `spend`, `revenue` remain null when
unknown; known zero stays distinguishable. Money columns are NUMERIC/Decimal.
Org-scoped uniqueness: `keywords(org, normalized_phrase, match_type,
marketplace)`, `source_files(org, file_sha256)`, `search_terms(org,
normalized_term, marketplace)`.

Migrations: `001_foundation.sql` (regenerated) + `003_keyword_intel.sql`
(additive delta) + `003_rollback_keyword_intel.sql`. The validation harness
now validates 001+002+003: clean apply, schema/constraint/index inspection,
repository tests, compensating rollback, reapply, fingerprint comparison,
clean-room determinism, foundation regression — **9/9 PASS**.

## Normalization (C02)

`foundation/keywords/normalize.py`: Unicode NFKC, whitespace collapse,
case folding, punctuation/hyphen/apostrophe handling, match-type/marketplace/
language canonicalization, ASIN-like detection, brand-term extraction, stop
words only for 3+ token phrases. Preserves the original; never over-normalizes
distinct commercial intent; idempotent. Tests: 34.

## Source registry (C03)

`foundation/keywords/sources.py`: discovers local report files (search-term,
campaign, placement, top-of-search, advertised-product, targeting, business,
keyword workbooks), classifies by header aliases, hashes (sha256), registers,
detects duplicates, records marketplace/currency/date-range. Absent report
types are recorded `SOURCE_NOT_PRESENT_LOCALLY` — never invented.

## Import pipeline (C04–C07)

`foundation/keywords/importer.py`:
- Dry run validates without writing (validity, required columns, row-level
  rejection, duplicate detection).
- Job-driven imports: the `keyword_import` handler executes large imports
  through the 1C-04 worker (submit → queue → claim → import → settle).
- Rejected rows preserved with reasons (`missing_search_term`,
  `non_numeric_spend`, …) and the original row JSON.
- Idempotent reimport (same org + sha → existing batch replay; no duplicates).
- Overlap detection flags overlapping date ranges per org/report type so
  reports are never silently double-counted.
- Cancellation with state guards; retry-safe; organization isolation; audit
  events on every consequential step.

## Organization isolation (C08)

Cross-org keyword search/detail, source files, import batches, rejected rows,
rank history, and search-term performance all fail closed (404/empty, never
leaked). Tests cover every surface.

## Shared read contracts (C09)

`foundation/keywords/contracts.py` — `KeywordReadContracts`:
- OfferChisel: relevant keywords, listing coverage, keyword gaps, search
  intent, evidence, confidence, freshness.
- Auctioneer: search terms, targets, match types, performance aggregation,
  harvest candidates, negation candidates.
- RankLedger: rank observations, historical series, alert conditions.
- Town Crier: approved themes (human-review flagged), brand-language guidance.
- AutothinK / Master Brain: authorized graph search with provenance,
  confidence, freshness, organization isolation. Local/imported data only.

## APIs (C10)

Authenticated organization-scoped endpoints: keyword search/detail, product
keywords, listing coverage, gaps, search-term performance, target performance,
harvest/negation candidates, rank history, conflicts, sources, provenance,
import dry-run/submit/status/rejected/cancel. GET is strictly read-only; large
imports use 1C-04 jobs.

## Gate (C11)

`foundation/tests/test_1c05_gate.py` — full lifecycle: job-driven import,
keyword/search-term/target separation, normalization, isolation,
duplicate-file prevention, reimport idempotence, overlap protection,
rejected-row preservation, source-file immutability, provenance, currency,
Decimal metrics, null search volume/rank, shared read contracts, and
zero provider calls.

## Evidence

| Command | Result |
|---|---|
| `pytest foundation/tests` | 494 passed, 28 skipped |
| `pytest` keyword modules + 1C05 gate | 75 passed |
| `pytest` (disposable PG modules) | 28 passed |
| `foundation_pg_validate_durable` | 9/9 steps PASS |

## Warnings / skips

- 28 SQLite skips are the three PostgreSQL-only modules.
- 5 HMAC key-length warnings (test fixtures only).