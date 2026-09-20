# Northstar OS — Golden Goose Seam Contract v1 (B7)

**Contract id:** `goose-seam/v1`
**Status:** FROZEN for Phase C implementation (designed in Phase B, B7).
**Parent:** [`BFF_CONTRACT_v1.md`](BFF_CONTRACT_v1.md) — this spec inherits the
envelope, opaque-id, error, and no-leak rules and specializes them to the
Golden Goose Finder.
**Phase alignment:** Alpha Build Blueprint Phase B / B7 ("Golden Goose job model
+ entitlement mapping (which tier unlocks which categories/exports) + export
manifest contract; same opaque-ID rules as other services; export manifest
schema defined with no vendor leakage; `/scan` behavior explicitly set to 403
in alpha").

---

## 1. Scope

Specializes `bff/v1` for Golden Goose:
1. **Job model** for scan requests (opaque job ids; `queued/running/done/failed/cancelled`).
2. **Entitlement mapping** (which subscription plan unlocks which GG categories and exports).
3. **Export-manifest schema** (no-vendor-leakage contract).
4. **Alpha behavior:** `POST /api/golden-goose/scan` remains **403**, unchanged; live scanning is not wired in the alpha.

---

## 2. Job model

Reuses the BFF job resource verbatim (`BFF_CONTRACT_v1.md` §4). GG specifics:

| Field | GG value |
|---|---|
| `service` | `golden_goose` |
| `operation` | `goose.scan` (scan) · `goose.export` (export) |
| `state` | `queued` → `running` → `done` \| `failed`; `queued`/`running` → `cancelled` |
| `result_ref` | `res_…` referring to a scored opportunity result set |
| `job_id` | `job_…` opaque; **`scan_id` and report filenames are internal only** |

**Alpha constraint:** in alpha a `goose.scan` job may only be created in
**mock/dry-run** mode; a live job creation is `forbidden` (403) because
`/scan` stays hard-stopped. `goose.export` operates on an existing
`result_ref`.

**Job creation (design):**

```jsonc
// POST /api/v1/golden_goose/jobs
// request (params only; no provider hints, no file paths)
{ "operation": "goose.scan", "mode": "mock", "filters": { "roi_floor": 10.0, "min_monthly_sales": 1000, "max_results": 100 } }
// response data
{ "job": { "job_id": "job_…", "service": "golden_goose", "operation": "goose.scan",
           "state": "queued", "created_at": "…", "updated_at": "…",
           "progress_pct": 0, "result_ref": null, "error": null,
           "links": { "self": "/api/v1/jobs/job_…" } } }
```

**Result shape (design):** the existing `_scored_to_dicts` opportunity shape,
wrapped in the BFF envelope and stripped of internal fields:

```jsonc
"data": { "items": [ { /* opportunity */ } ], "page": { … } }
```

No provider names, no `report_path`, no routing/cost-formula fields.

---

## 3. Entitlement mapping

**Single source of truth for plans/prices/gates:**
[`shared/subscription-plans.json`](../../shared/subscription-plans.json). This
spec **references** it and never duplicates plan names, prices, or gate arrays.

The GG-specific category/export entitlements are declared in
[`shared/gg-entitlements.json`](../../shared/gg-entitlements.json), keyed by the
**plan id** from the catalog. A validator
(`gg_entitlements.validate_gg_entitlements()`) fails closed if any referenced
plan id is not in the catalog, or if the mapping restates catalog data.

**Proposed mapping (operator sign-off required before Phase C wiring):**

| Plan id | GG categories unlocked | Exports unlocked |
|---|---|---|
| `foundation` | *(none — demo/read of already-published reports)* | *(none)* |
| `scout` | `vitamins_supplements`, `otc_health` | `opportunities_json` |
| `mover` | + `household_cleaning`, `personal_care`, `snacks_bars` | + `opportunities_csv` |
| `autothink` | all 8 canonical categories | + `export_manifest_json` |

**Canonical GG category slugs** (source: `category_config.CATEGORY_CONFIG`):
`nicotine_cessation`, `otc_health`, `vitamins_supplements`,
`household_cleaning`, `personal_care`, `pet`, `snacks_bars`, `baby_child`.

> A plan **entitles** a category/export; it never flips a live gate. Live
> execution still requires a fresh, named operator approval (§3 / §18).

---

## 4. Export-manifest schema (no-vendor-leakage)

Every export file ships a manifest envelope describing the data without
revealing providers, routing, or internal paths.

```jsonc
{
  "manifest_version": "goose-export/v1",
  "export_id": "exp_…",              // opaque
  "job_id": "job_…",                 // opaque (BFF §4)
  "created_at": "2026-09-19T…Z",
  "service": "golden_goose",
  "export_type": "opportunities_json" | "opportunities_csv" | "export_manifest_json",
  "row_count": 42,
  "schema_version": "opportunities/v1",
  "tiers": { "HIGH": 10, "MEDIUM": 20, "LOW": 12, "REJECT": 0 },
  "filters": { "roi_floor": 10.0, "min_monthly_sales": 1000, "category": null },
  "columns": ["rank","amazon_asin","brand","tier","net_profit_per_unit", …],
  "currency": "USD",
  "disclaimer": "Estimates only. Not a recommendation to buy or an approval to resell."
}
```

**Forbidden in a manifest or export (BFF §6):** provider/vendor names or ids,
API keys/tokens/credentials, model ids, prompts, routing logic, cost formulas,
internal filesystem paths (`report_path`, `scan_id`, raw filenames), stack
traces, and raw provider payloads. `assert_no_export_leakage(manifest)` enforces
this at build time.

**Permitted:** opaque ids (`exp_`/`job_`/`res_`), product data (ASIN, brand,
tier, net/ROI, scores), counts, fixed-enum filters, dates, currency, the fixed
disclaimer string, and column name lists.

---

## 5. Alpha behavior (unchanged)

| Endpoint | Alpha behavior |
|---|---|
| `POST /api/golden-goose/scan` | **403** (hard-stopped; named §3 approval only). Unchanged. |
| `POST /api/golden-goose/scan-mock` | Offline mock scan (no provider calls). Unchanged. |
| `GET /api/golden-goose/opportunities` | Report-backed read; **must strip `report_meta.report_path`** and adopt the BFF envelope in Phase C. |
| `GET /api/golden-goose/categories`, `/health` | Unchanged. |

**Do not wire live scanning in alpha.** This spec defines the target so Phase C
builds against it without re-deciding.

---

## 6. What Phase C builds (against this frozen spec)

1. Adopt the BFF envelope on GG read endpoints; strip `report_path`.
2. Introduce opaque `goose.scan` / `goose.export` jobs (mock/dry-run in alpha).
3. Enforce the entitlement mapping on category filters and export types.
4. Emit conforming export manifests via `assert_no_export_leakage`.
5. Keep `/scan` 403.

---

*Designed Phase B (B7), 2026-09-19. FROZEN for Phase C. `/scan` stays 403.*