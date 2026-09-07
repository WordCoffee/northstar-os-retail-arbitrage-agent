# Offline Test Report — 10-ASIN Easyparser Run

Run: `20260907T055957Z` · All tests offline/zero-network. No Easyparser or DataForSEO
calls. No secrets in output or artifacts.

## 1. Canonical Python suite

Command: `python -m unittest discover -s . -p "test_*.py"` (from `Northstar_backend/`)

| Phase | Result | Delta |
|---|---|---|
| Pre-change baseline | **1413 tests, OK, skipped=3** (90.8s) | — |
| Post-change | **1417 tests, OK, skipped=3** (61.1s) | +4 (all new easyparser-provider tests), 0 new failures/errors |

The 1413 baseline is the documented clean current state (0 failures / 0 errors / 3 skips).

## 2. Manifest-runner module (targeted)

Command: `python -m unittest test_enrich_manifest_runner`

- **27 tests, OK** (23 pre-existing + 4 new).
- New offline proofs for this run:
  - `test_21` — easyparser provider: exactly 10 requests in canonical manifest order,
    zero repeated calls (zero retries), all outcomes available, `mapping_error` False.
  - `test_22` — provider returns a different ASIN → `mapping_error=True`, outcome
    `unavailable`, raw preserved with the wrong `provider_asin`, no retry, no re-call.
  - `test_23` — `status`/`dry-run` with `--provider easyparser` make zero network calls
    (transport mocked to raise).
  - `test_24` — `--max-requests 3` stops after exactly 3 easyparser calls; 7 rows
    `skipped_cap`.

## 3. UI display test

Command: `node test_ui_display.cjs` → **ALL UI DISPLAY TESTS PASSED** (0 failures).

## 4. Live-command smoke check (offline, zero network)

`python enrich_manifest_run.py status --provider easyparser --manifest
 data/enrich/easyparser-runs/20260907T055957Z/manifest/live-10asin-manifest.json`
→ `status: ACCEPTED`, 10 ASINs in order, `provider config resolves: YES`, `network calls made by status: 0`, exit 0.

## 5. Network-call accounting during preparation

Zero live/paid network calls were made during phases 1–9. The only processes that may
touch the network are the mocked-offline tests' own guards.