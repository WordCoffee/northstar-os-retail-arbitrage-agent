# SellerSprite Trial-Expiry Deactivation — Provider Cleanup (2026-09-27)

## Scope
SellerSprite is retired as an active NorthstarOS provider because its trial expired. This pass removes SellerSprite from all active runtime, provider, import, CLI, UI, config, scheduler, and selection paths, preserves the generic provider architecture, and adds fail-closed regression coverage.

**Provider posture after this pass:** SellerAmp is the only current provider direction, implemented as **offline manual-export import + a disabled-by-default adapter**. No live integration is assumed or enabled. The adapter registry is generic so a future provider can be onboarded through a separate approved integration pass; no future provider is named, added, enabled, or stubbed.

## Pre-change repository-wide match inventory
`git grep` (tracked) showed SellerSprite only in `00_STATE.json`, `docs/UI_UX_BLUEPRINT_NORTHSTAROS.md` (already "no longer a reference"), and one prior report. A filesystem sweep (including untracked) found the real active surface in the untracked `Northstar_backend/costco_non_kirkland/` package plus its docs.

| Area | Pre-change references (files) |
|---|---|
| Provider adapter | `providers.py` (`SellerSpriteProvider`, `ENABLE_ENV`, registry entry) |
| Import path | `provider_imports/sellersprite_importer.py`, `provider_imports/__init__.py` |
| Schemas | `provider_imports/schemas.py` (`SELLERSPRITE_CSV_COLUMNS`, `SELLERSPRITE_JSON_KEYS`, `PROVIDER_SCHEMAS`) |
| Detection | `provider_imports/common.py` (`PROVIDER_HINTS`, `SELLERSPRITE_FIELD_HINTS`) |
| CLI | `cli.py` (`import-sellersprite`, `_import_provider` switch, `--provider` choices) |
| Sign-in | `signin.py`, `enums.py` (`SignInService.SELLERSPRITE`) |
| Guard | `amazon_guard.py` (`AUTHORIZED_AMAZON_MARKET_SOURCES`) |
| Scoring | `scoring.py` (`sellersprite=` kwarg) |
| Pipeline/plan | `pipeline.py`, `plan_enrichment.py` |
| Package docs | `__init__.py` |
| Tests/fixtures | `tests/fixtures.py`, `test_provider_imports.py`, `test_pipeline_store.py`, `test_signin_disallowed_guard.py`, `test_identity_unknown.py`, `test_economics_scoring.py`, `test_competition_economics.py` |
| Docs | `docs/provider-export-import-guide.md`, `docs/costco-non-kirkland-pipeline.md`, `docs/costco-non-kirkland-troubleshooting.md`, `docs/costco-identity-resolution.md`, `docs/brightdata-costco-enrichment.md` |

No `northstar-os-ui` source referenced SellerSprite (UI copy was already clean).

## Changes (fail-closed retirement)
- **Removed** `SellerSpriteProvider` and its registry entry; `provider_imports/sellersprite_importer.py` deleted.
- **Removed** SellerSprite import command (`import-sellersprite`), importer switch, and `--provider` choice; `import-selleramp` is the only export import.
- **Removed** SellerSprite schemas/field hints/detection; `schemas.py` now maps SellerAmp only.
- **Removed** `SignInService.SELLERSPRITE`, its sign-in URL, and its env flag; services are `costco`, `selleramp`.
- **Removed** `sellersprite` from `AUTHORIZED_AMAZON_MARKET_SOURCES`; the `scoring.py` `sellersprite=` kwarg removed (SellerAmp estimate used).
- **Added explicit, labeled retirement records** (the only remaining SellerSprite mentions, by design):
  - `providers.RETIRED_PROVIDERS = {"sellersprite": "Retired 2026-09-27 — trial expired. Not a supported provider."}` + `ProviderRetired`.
  - `provider_factory("sellersprite")` → raises `ProviderRetired`.
  - `plan_enrichment(provider="sellersprite")` → `{reason: "retired_provider"}`.
  - `detect_provider(explicit="sellersprite")` and retired-provider filenames → rejected with a retired note.
  - `require_signin("sellersprite")` / `mark_signed_in("sellersprite")` → retired rejection.
  - CLI: `import-sellersprite` no longer exists (argparse error); `create-provider-manifest --provider sellersprite` rejected by choices.
- **Docs** updated to SellerAmp-only with a labeled retirement note.

## Preserved (generic architecture — unchanged)
- `ProviderAdapter` contract, `ProviderStatus`, `SANCTIONED_ACCESS_MECHANISMS`, `provider_factory` registry, and the evidence envelope (`_evidence`).
- Canonical market-snapshot contract + `map_row_to_canonical` + provenance fields; `ensure_provider_provenance`.
- Cache layers, null-first/unknown semantics, `ImportRowStatus` outcomes.
- `purchase_authorization_status` always `not_authorized`; no live calls; no scraping; no secrets.

## Regression coverage added
- `test_provider_imports.py`: retired provider rejected by name; `provider_factory` raises `ProviderRetired`; retired-provider file rejected; SellerAmp import (CSV/JSON), idempotency, dry-run no-writes, provenance, zero-network.
- `test_pipeline_store.py`: `ProviderRetired` from factory; retired sign-in; `plan_enrichment` returns `retired_provider`; SellerAmp enrichment plan remains dry-run + no live calls + sign-in gate.
- `test_signin_disallowed_guard.py`: retired service rejected; `sellersprite` absent from `SIGN_IN_URLS`; `authorized_market_source("sellersprite")` now **False**; provenance fail-closed for retired source.
- Existing `network_guard`-active zero-network assertions retained (GET/UI/plan paths make zero provider calls; `Network calls made: 0`).

## Verification
- **Tests:** `python -m pytest costco_non_kirkland/tests -q` → **180 passed, 0 failed**.
- **CLI:** `import-sellersprite` absent from `--help`; invoking it exits 2 (argparse). `create-provider-manifest --provider sellersprite` rejected (`--provider {selleramp}`).
- **py_compile:** all edited package modules compile.
- **Final grep (code + docs):** remaining SellerSprite mentions are only the labeled retirement records and the rejection regression tests; no active runtime/provider/import/CLI/config/sign-in/UI path retains SellerSprite.
- **Repo-wide grep** for `SellerSpriteImporter|sellersprite_importer|NORTHSTAR_SELLERSPRITE`: only `00_STATE.json` historical text (updated in this pass) and a prior report.

## SellerAmp status (repository evidence only)
**REPORTED** — a SellerAmp adapter (`SellerAmpProvider`) and manual-export importer (`SellerAmpImporter` + SellerAmp schemas) exist, offline/disabled by default. There is **no** live API client, credential use, browser automation, or network path in the repo; `fetch()` returns `provider_not_configured` / `requires_explicit_approval` and never calls out. Therefore SellerAmp is a *reported* provider direction (export/import + gated adapter), not a **VERIFIED** live integration. Not UNKNOWN (the offline path is evidenced).

## Tracking note (operator-reversible)
`Northstar_backend/costco_non_kirkland/` (59 `.py` files incl. tests) was **untracked** in git before this pass; it depends only on tracked modules (`data_layer.py`, `network_guard.py`). It is now tracked so the retirement is durable and regression-guarded. `__pycache__/` and `.pytest_cache/` are git-ignored. Historical research artifacts (`provider_research_*.md/json`) and the DB/snapshots were **not** committed.

## Deliverables
- Report: `reports/sellersprite_trial_expiry_deactivation_20260927.md`
- Commit: `Retire expired SellerSprite trial provider`
