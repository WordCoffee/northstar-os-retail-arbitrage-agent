# A18 — Intel I0 design (condensed, build-ready)

Full design was produced by a read-only lane and reviewed. This file keeps the decisions that the
build depends on. Nothing here is implemented yet; `state/intel/` does not exist.

## What exists vs what was assumed

| Thing | Reality |
|---|---|
| `tools/web_research.py` | exists: search, fetch, README, licence class, JSONL journal, Amazon refusal first |
| `tools/vet_package.py` | exists: OSV, `MAL-*` = stop, transport failure = refusal |
| `state/intel/` | **absent** — A18 creates it |
| `tools/patterns` (cited in the master plan) | **absent** — the real precedent is `tools/fix_patterns.py:19` → `state/fix_patterns/*.jsonl` |
| `yt-dlp` | installed (2026.8.19, Unlicense) but **not** in `provider-suite.json` |
| `config/chromecontrol_policy_owner.json`, `lib/chromecontrol/policy.js` (cited by AGENTS.md) | **absent from this repo** — only under `backups/ty_rollback/*/external/` |
| throttle / retry / 429 handling in `web_research` | **none**; `_http` also discards response headers |
| `logs/` | gitignored (`.gitignore:8`) → refusals must live in a tracked file |

## Decisions

1. **Refusals go to `state/intel/refusals.jsonl` (tracked)**, not to `logs/`, or they vanish from
   history. Closed `rule_id` vocabulary in `sources.json`; an unknown id is itself `schema_invalid`.
2. **One collector signature**: `collect(spec, ctx) -> CollectResult`, with `run_source()` owning
   accounting, validation and writing, so a buggy collector cannot report a clean run. Closure
   check: `attempted == accepted + duplicates + refused + failed`, else `run_accounting_broken`.
3. **Reuse, don't duplicate**: GitHub uses `search_github` / `read_license` / `fetch_readme` /
   `classify_license`; HF and PyPI go through the module's single transport `_http` (which is what
   enforces the Amazon guard and writes the journal). PyPI reuses `vet_package.vet` for OSV.
4. **Dedupe**: `dedupe_key = source:identity`, content revision tracked as `content_sha256`.
   Same identity + same hash = `duplicate` (counted); different hash = a new revision item.
5. **YouTube adds one dependency** (`yt-dlp`, binary, Unlicense) → a `provider-suite.json` entry via
   a `GRANT:` commit before the collector can run. Metadata → captions → local faster-whisper
   fallback → keyframes to `state/intel/raw/` deleted after transcription. `--no-cookies` makes
   credential use structurally impossible; a sign-in gate is `credential_gated`, never a retry.
6. **Competitor collector ships disabled.** It needs the browser lane, and the policy files
   AGENTS.md cites are not in this repo. It refuses with `browser_lane_required` rather than
   pretending the guard is wired.
7. **Quotas are recorded as measured or unknown** — never guessed:
   - GitHub search **10 req/min** (headers observed; prior live 429 at
     `reports/ty/research_20261105.md:10-14`), core **60 req/hr**.
   - HF, PyPI, OSV, arXiv, YouTube, competitor: **unknown** (`null` + `source_of_truth: "unknown"`
     + a note). arXiv's ~3 s spacing is applied as *self-imposed*, not asserted as a provider rule.
   - GitHub quota is read from `/rate_limit` (does not consume search quota) before any search.

## Acceptance (three commands)

```
python tools/intel_collect.py --source github --query gh-w1-composite --limit 3 --json
  -> exit 0; attempted 3, accepted 3, duplicates 0; items schema-valid before append;
     a second identical run prints duplicates 3 / accepted 0 (dedupe proven)

python tools/intel_collect.py --source github --url https://www.amazon.com/dp/B01FYY3M38 --json
  -> exit 1; rule_id amazon_host_blocked; exactly one new line in state/intel/refusals.jsonl

python -m pytest -q Northstar_backend/test_intel_collect.py
  -> refusal precedes transport (exploding opener), quota exhaustion, unstated licence is still a
     logged decision, dedupe, accounting violation exits 3, disabled source refuses, arXiv v1/v2
     are two items, --dry-run writes nothing
```

## Known gaps A18 must not hide

1. `web_research._http` discards headers and collapses HTTP errors into `Transport`. Quota is
   therefore classified from the `/rate_limit` probe plus exception text. An additive
   `return_headers=False` parameter on `_http` is the clean fix, and is recommended but not in A18's
   write scope.
2. `fetch_readme` / `read_license` hardcode `raw.githubusercontent.com`, so HF cards, PyPI pages and
   arXiv entries must use `_http` directly.
3. `yt_dlp_local` must be exactly `"installed"` in the suite entry: `provider_suite.verify` treats
   `"ready"` as `not_installed`.
