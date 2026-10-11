# Amazon-linkage inventory — file-only architecture

**Date:** 2026-10-11 · **Branch:** `feature/overnight-remediation-20261009` · **Decision:** NorthstarOS never signs in to Amazon and never links a seller's Amazon accounts. No SP-API, no Ads API, no OAuth/LWA, no Amazon credentials. The workflow is file-only: the seller downloads files from Amazon, uploads them, Northstar writes a change file, and the seller uploads it back manually.

## 1. Every path that referenced Amazon sign-in, APIs or live pulls

| # | Path | What it is | Risk before | Status now |
|---|---|---|---|---|
| 1 | `Northstar_backend/importers/sp_api_importer.py` | Real SP-API client: LWA refresh-token flow (`api.amazon.com/auth/o2/token`) + SP-API GETs (`sellingpartnerapi-na.amazon.com`); gated only by credential presence | A configured deployment could call Amazon on the seller's behalf | **DISABLED by the linkage gate**: refuses with the stated file-only reason unless `NS_AMAZON_LINKAGE_ENABLED` is an explicit opt-in |
| 2 | `Northstar_backend/importers/ads_api_importer.py` | Real Ads API client: OAuth2 + `advertising-api.amazon.com` calls; gated only by credential presence | Same | **DISABLED by the linkage gate** |
| 3 | `Northstar_backend/adapters/amazon_api.py` | The unified `amazon_api` adapter wrapping both importers; registered in `adapters/registry.py` | Any future caller could reach Amazon | **`is_configured()` returns False unless the linkage gate is on** |
| 4 | `Northstar_backend/tasks/brand_blacklist_updater.py` | SP-API gating re-check; already had an operator gate (`BRAND_RECHECK_LIVE_OPERATOR_APPROVED=1`) | The operator gate alone could arm a live transport | **Second condition added**: `live_armed()` now ALSO requires the linkage gate |
| 5 | `Northstar_backend/data_refresh.py` | CLI provider-refresh registry (lists `SP_API_*` env-key names for status; calls no Amazon endpoint itself) | Config-name exposure only | Listed in the scan's gated set; no endpoint call |
| 6 | `Northstar_backend/importers/brand_analytics_importer.py` | CSV-first parser (its docstring mentions the SP-API option; no live code) | None found | **File-only already**; covered by the scan |
| 7 | Provider clients (`brightdata_*`, `scavio_client`, `easyparser_*`, `canopy_client`, `amazon_search`, `costco_api_client`, ...) | Live-pull family already behind `live_gate` (A1: `SCANNER_LIVE_ALLOWED=0` + per-run arm + cost cap; `assert_live_posture` refuses to boot a live mode without both) | Guarded | Unchanged (other workstream; guarded by A1) |
| 8 | UI citations (`studio/engine/specRegistry.js`, `SocialPulse.jsx`) | Amazon **help/doc URLs** used as source citations (e.g. `advertising.amazon.com/help/...`) | None — citations, not linkage | Allowed by the scan (API hosts are forbidden; help URLs are not) |
| 9 | `research/design_studio_deep_research_20261008/mockups/render_mockups.py` | Research script (another workstream's research tree) | None found | Left untouched (not this workstream's file) |

## 2. The guard

`Northstar_backend/amazon_linkage_gate.py`:

- `NS_AMAZON_LINKAGE_ENABLED` — default OFF; `linkage_enabled()` is true only on an explicit opt-in.
- `assert_linkage_posture()` — **refuses to boot** when the flag is on in `staging` or `production`; wired into `main.py`'s lifespan alongside the rate-limiter, live-provider and JWT-secret posture asserts.
- `linkage_refusal_reason()` — the stated file-only reason the importers log and report.

## 3. The static scan (proves no path remains)

`tools/test_no_amazon_linkage.py` — **2127 checks, 0 failed**:

- Backend modules outside the gated set contain no Amazon API host (`sellingpartnerapi`, `advertising-api.amazon.com`, `api.amazon.com/auth`, `/auth/o2`) and no Amazon credential env names.
- The UI contains no Amazon API host or OAuth path in any source file.
- The file-only modules (`amazon_file_parsers.py`, `amazon_file_writers.py`, `amazon_change_files.py`) import no network library and contain no http(s) URL except inert OOXML/XML namespace identifiers.
- Posture: the gate is off by default; staging/production refuse it when on; development allows the explicit opt-in.
- Refusal with credentials: the SP-API importer, the Ads API importer, the unified adapter and the blacklist re-check all refuse **even with credentials present** while the gate is off, and configure only when it is explicitly on.

## 4. What replaced the linkage

`Ads › Amazon files` (new sub-view): upload → detect/validate → propose (before/after, evidence, blocks, spend guardrail, stale warning, title FLAGS) → row-level approve/reject → write the delta file → round-trip proof → download for manual upload. A+ uploads produce an asset pack (not an uploadable module file). No provider call exists anywhere in the path (the API harness asserts zero non-local requests outside the app's own font CDN, and zero Amazon hosts).
