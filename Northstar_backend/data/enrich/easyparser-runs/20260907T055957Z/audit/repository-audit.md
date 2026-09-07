# Repository Audit — 10-ASIN Easyparser Enrichment Run

Run: `20260907T055957Z` · Prepared from the repo as it exists on disk (no assumption of
prior Easyparser prep artifacts). Zero network during this phase.

## 1. Layout

| Area | Path |
|---|---|
| Backend root | `Northstar_backend/` |
| Easyparser client | `Northstar_backend/easyparser_client.py` |
| Production-owned live runner | `Northstar_backend/enrich_manifest_run.py` |
| Cache-driven enrichment CLI (out of scope) | `Northstar_backend/enrich_cached_asins.py` |
| Normalized snapshot store | `Northstar_backend/market_snapshot_store.py` |
| Truth inputs (canonical, read-only) | `Northstar_backend/data/benchmarks/raw/BSR-proxyrank-...-PrimeFBA.csv`, `Northstar_backend/data/benchmarks/raw/Rank-Product-ASIN-Reviews-Price-BSR.csv` |
| Run base dir (this mission) | `Northstar_backend/data/enrich/easyparser-runs/` |
| UI test | `Northstar_backend/test_ui_display.cjs` |

## 2. Easyparser client (existing implementation)

- One **GET** per ASIN against the established route
  `https://realtime.easyparser.com/v1/request` (verified by prior live run evidence).
- Params: `api_key` (env `EASYPARSER_API_KEY`, loaded via `load_dotenv()`),
  `platform=AMZ`, `operation=OFFER`, `domain=.com`, `asin`.
- Returns a normalized dict: `source="easyparser"`, `provider_asin`, `request_id`,
  `title`, `offer_count`, `offers` (position, buybox_winner, price raw/value,
  condition, seller id/name/rating, is_prime/is_fba/is_fbm/is_sba,
  fulfilled_by_amazon, shipping text/is_free, ships_from, MOQ/MaxQ),
  `buy_box_*` (price, seller, seller_id, fba/fbm, prime, condition),
  `observed_*` counts, `request_zip_code`, `observed_at`,
  `credits_used`/`credits_remaining` (provider-reported).
- No internal retries, no polling loop, no background timer.
- Key absent → fail-closed gap result `"Easyparser API key is not configured."` (no network).

## 3. Existing live-run CLI (the command that already exists)

`enrich_manifest_run.py` is the production-owned **manifest-selection** runner:

- Hardcoded `APPROVED_ASINS` = the exact frozen 10 (B01H40O42I … B085F1QCB9).
- Only accepts manifest `kind == "live-10asin-manifest"` with canonical order,
  no duplicates, no ASIN outside the approved set, required per-ASIN CSV fields
  (`product_title_csv`, `price_csv`, `reviews_csv`, `prime_fba_flag_csv`, `bsr_text_csv`).
- **Zero retries by construction** — no `--retries` flag; the loop never invokes the
  client twice for the same ASIN (existing tests prove this).
- Finite live caps are mandatory (`--live`, `--max-requests`, `--max-credits`); the run
  refuses to start without them and stops as soon as a cap is reached.
- Writes only to a unique immutable run dir `data/enrich/easyparser-runs/manifest-<ts>-<hex>/`
  (`raw/`, `normalized/`, `manifest.json`, `preflight.json`, `request-ledger.json`,
  `live-vs-csv-comparison.csv`, `run-summary.md`, `run-index.jsonl`). Never touches the
  shared snapshot store or a single-slot report file. Refuses to overwrite an existing run dir.
- Secret scan on every provider response; hard-halt + scrubbed failure-manifest on hit.
- Prior live Easyparser run evidence: `manifest-20260822T080742Z-9e71`
  (9 requests, `stopped_cap`, provider-reported credits 10–15/request, ZIP 19805).

## 4. Confirmed local gap for this mission + narrow fix applied

- **Gap:** the provider switch in `_fetch_offers` treated `easyparser` as
  deprecated/disabled and `--provider` choices excluded it, so the existing CLI could
  not route this manifest through Easyparser.
- **Fix (smallest safe change, Phase 7):**
  1. `import easyparser_client` (module already exists; no new endpoint).
  2. `_fetch_offers("easyparser")` → `easyparser_client.get_easyparser_offers(asin)`;
     a `provider_asin` mismatch sets `mapping_error=True` + data-gap, result rejected
     (raw still persisted for evidence).
  3. `--provider` choices gain `"easyparser"` (status / dry-run / run).
  4. `_provider_key_resolves("easyparser")` → boolean `os.getenv("EASYPARSER_API_KEY")`.
  5. Ledger rows now carry `mapping_error`; mapping-error snapshots are forced to
     `unavailable` so a wrong product is never counted as a success.
- **Untouched on purpose:** `offer_enrichment.py` and `enrich_cached_asins.py`
  still refuse the easyparser token (different paths, out of scope); `finance.py`,
  `pricing.py`, `product_analysis.py`, `fee_engine.py`, the truth CSVs, prior raw
  evidence, failure manifests, and `.env` are untouched.

## 5. Other enrichment lanes (documented, NOT used here)

- `enrich_cached_asins.py` — cache-driven, easyparser refused (not manifest-driven).
- `proof_batch_easyparser_adapter.py` / `proof_batch_run.py` — separate 20-ASIN
  proof-batch lane; the mission's 10-ASIN cap excludes it.
- `data/enrich/waterfall-runs/` — legacy rapidapi waterfall artifacts.

## 6. Test commands used (Phase 5, offline)

- Canonical: `python -m unittest discover -s . -p "test_*.py"`
- UI display: `node test_ui_display.cjs`

## 7. Environment gates relevant to this run

The manifest runner's live gate is flag-based (`--live` + finite caps), not env-based.
`EASYPARSER_API_KEY` resolves to a boolean **present** via `load_dotenv()` in the exact
code path the live run uses (verified via production `status` output and a boolean-only
probe — no value read or printed). See `environment-presence-report.json`.

## 8. Scope of the live pull (planned)

10 requests maximum (one per frozen ASIN), sequential, zero retries, Easyparser only.
Output lands in a fresh immutable `manifest-<ts>-<hex>/` run dir; this run's prepared
manifest/truth/audit/preflight stay under `20260907T055957Z/`.