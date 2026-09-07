# Live Command Plan — 10-ASIN Easyparser Run

Run: `20260907T055957Z` · Easyparser only, no fallback provider, no DataForSEO/RapidAPI/Bright Data.

## Exact command (run from `Northstar_backend/`)

```
python enrich_manifest_run.py run --live --provider easyparser ^
  --manifest data/enrich/easyparser-runs/20260907T055957Z/manifest/live-10asin-manifest.json ^
  --max-requests 10 --max-credits 200
```

## Why this command

- `enrich_manifest_run.py` is the existing production-owned manifest runner, hardcoded
  to the exact frozen 10 ASINs; it was the cmd-chosen executor (no invented command).
- `--provider easyparser` routes through the existing `easyparser_client` (1 GET/ASIN
  against the established `realtime.easyparser.com/v1/request` OFFER route).
- `--manifest` points at the frozen manifest (hash `sha256:899660…fc5c` canonical /
  `sha256:a1dd16…d32a` file) with caps, retries 0, polling false, purchase_authorized false.
- `--live` + `--max-requests 10` + `--max-credits 200` are mandatory gate inputs; the run
  refuses to start without them.

## Caps and stop conditions

- Requests: hard cap **10** (one per frozen ASIN; `stopped_cap` if hit before the list ends
  — cannot happen with 10 ASINs unless a duplicate is injected, which validation rejects).
- Credits: hard cap **200**. Local prior evidence: 10–15 provider-reported credits/request
  → expected ≤150. Higher per-request credits stop the run early at the credit cap
  (fail-safe, fewer requests).
- **Zero retries**: no `--retries` flag exists; the loop never invokes the client twice
  for the same ASIN (tests `12`, `21` prove it).
- **No polling, no hidden/background calls.**
- Per-item hard failure: recorded as `unavailable` (or `halted_secret` → exit 5 with a
  scrubbed failure-manifest); execution moves to the next ASIN; nothing is retried.
- Run-dir collision → exit 3 (never overwrites). Manifest rejection → exit 4 (before any
  network path). Missing `--live`/caps → exit 2 (before any provider call).

## What the run writes (immutable, unique)

`data/enrich/easyparser-runs/manifest-<UTC_ts>-<hex>/` with:
`raw/<ASIN>.json` (provider responses incl. `mapping_error` flags), `normalized/<ASIN>.json`,
`manifest.json`, `preflight.json` (records the frozen-manifest byte sha it reads),
`request-ledger.json` (per-request outcome/credits/`mapping_error`), `live-vs-csv-comparison.csv`,
`run-summary.md`, and one appending line in `run-index.jsonl`.

## Post-run reconciliation (Phases 10–13)

After the CLI finishes, this run dir (`20260907T055957Z/`) will host the mission-named
views built ONLY from the CLI's evidence: `live/raw`, `live/normalized`,
`live/request-log.jsonl`, `live/live-run-metadata.json`, `live/live-failure-manifest.json`,
plus `review/live-vs-amazon-truth-comparison.{csv,md}` and `review/discrepancy-report.csv`
joining live results to truth by ASIN, and `review/run-summary.{json,md}` +
`review/operator-final-report.md`. Nothing is fabricated; no purchase authorization.

## Fields never compared

Reviews count and BSR: Easyparser OFFER does not supply these; the comparison uses
`Unknown` / "provider does not supply BSR" — never zero-filled, no substitute source.