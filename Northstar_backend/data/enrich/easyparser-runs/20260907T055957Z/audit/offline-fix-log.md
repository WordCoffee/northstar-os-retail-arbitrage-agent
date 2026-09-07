# Offline Fix Log — 10-ASIN Easyparser Run

Run: `20260907T055957Z`

## Findings from the offline pass

1. **Canonical suite baseline is clean.** `1413 ran / OK / 3 skipped` pre-change and
   `1417 / OK / 3 skipped` post-change (see `offline-test-report.json`). The offline pass
   surfaced **no pre-existing defect** in the manifest-runner / easyparser path.

2. **One confirmed local gap, fixed narrowly (Phase 7, mission-authorized):**
   the existing production runner `enrich_manifest_run.py` had Easyparser
   **disabled** in its provider switch — `_fetch_offers("easyparser")` returned a
   refusal dict, `--provider` choices excluded `"easyparser"`, and the ledger had no
   mapping-error channel. Since the mission mandates an Easyparser-only, exactly-10-ASIN
   pull through the existing implementation, the smallest safe change was applied:

   - `enrich_manifest_run.py`
     - `import easyparser_client` (existing module; no new endpoint).
     - `_fetch_offers("easyparser")` → `easyparser_client.get_easyparser_offers(asin)`;
       wrong/absent `provider_asin` → `mapping_error=True` + data-gap, result rejected
       (raw preserved).
     - `--provider` choices += `"easyparser"` for status/dry-run/run.
     - `_provider_key_resolves("easyparser")` → boolean `os.getenv("EASYPARSER_API_KEY")`.
     - Ledger row gains `mapping_error` flag; mapping-error snapshots forced to
       `unavailable` so a mismatched product is never counted as a live success.
     - Module docstring + status help text corrected (no longer claim disabled).
   - `test_enrich_manifest_runner.py` += 4 offline tests (exact-10 set, zero retry,
     mapping-error rejection, zero-network status/dry-run, cap enforcement).

## What was deliberately NOT changed

- `offer_enrichment.py` and `enrich_cached_asins.py` still refuse the easyparser token
  (out of scope; different execution paths).
- Protected files (`finance.py`, `pricing.py`, `product_analysis.py`, `fee_engine.py`,
  truth CSVs, prior raw evidence, failure manifests, `.env`) untouched.

## Evidence

- Targeted module: `python -m unittest test_enrich_manifest_runner` → 27 OK.
- Full suite pre/post deltas in `offline-test-report.{json,md}`.