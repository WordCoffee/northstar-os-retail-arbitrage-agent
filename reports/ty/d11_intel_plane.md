# D11 — Intel plane (A18–A21)

Date: 2026-11-08 · Branch: `ty/builder-d11` · Unit: D11 (A18→A21)

## What shipped

A discovery lane that searches five public indexes, maps each hit to a Northstar
service, vets packages through OSV, ranks with an explainable formula, verifies every
URL, and writes one tracked findings file plus a runtime mirror.

| Path | Role |
|---|---|
| `tools/scout/config.py` | A18 source registry + closed query plan + service keyword profiles + weights + quotas |
| `tools/scout/connectors/` | A18 collectors: `github`, `huggingface`, `pypi`, `npm`, `arxiv`, uniform `search(query, limit)` |
| `tools/scout/http.py` | guarded transport (reuses `tools/web_research.guard`), status/headers/gzip, scout journal |
| `tools/scout/normalize.py` | A19 one finding shape, stable id, content hash, identity dedupe |
| `tools/scout/licence.py` | A19 effective-licence engine (SPDX aliases, full-text hints, PyPI classifiers) |
| `tools/scout/evidence.py` | A20 evidence field extractor + `file:line` citation scanner |
| `tools/scout/rank.py` | A21 service matcher, scoring, gap-capped lift, hypothesis template |
| `tools/scout/vet.py` | `tools/vet_package.py` adapter + the single adoption-policy function |
| `tools/scout/verify.py` | URL resolution (HEAD/GET) + authoritative-endpoint fallback |
| `tools/scout/collect.py` | orchestrator + CLI (`--dry-run`, `--live`, `--record-fixtures`) |
| `tools/scout/fixtures/` | 18 recorded real payloads (65 KB) for offline replay |
| `ty/intel_gaps.json` | **tracked** output (58 findings, 11 service gaps) |
| `state/intel/gaps.json` | runtime mirror (gitignored by design) |
| `Northstar_backend/test_scout_intel.py` | 54 offline tests |

Run it:

```
python -m tools.scout.collect --dry-run           # fixtures only, writes nothing
python -m tools.scout.collect --live              # public APIs, writes both files
python -m tools.scout.collect --record-fixtures   # refresh the fixtures
```

## A18–A21 mapping

The automation gate already named four capabilities. This is how they landed, and
where the task prompt's four words (i0 design, connectors, ranking, vetting) sit
inside them.

| Unit | Gate definition | Built as |
|---|---|---|
| **A18** `M3-intel-I0` | source registry + collectors | `config.SOURCES`/`QUERY_PLAN` + `connectors/` (5 sources), `http.py` transport, `--record-fixtures` |
| **A19** `M3-intel-I1` | normaliser + effective-licence engine + refusal log | `normalize.py` (canonical shape, dedupe/revisions), `licence.py` (class + commercial/adoptability), `collect.log_refusal` with a closed rule vocabulary |
| **A20** `M3-intel-I2` | REA extractor: repo `file:line`, video timestamps, screenshots | `evidence.py`: per-source concrete field sets plus `citations()` for `path.ext:line` anchors. **Reconciled difference:** the video/screenshot half belongs to the media lane and is not implemented here; the report does not pretend otherwise |
| **A21** `M3-intel-I3` | gap matcher + hypothesis template + yield scoring | `rank.py`: service matcher, 0–100 composite, gap-capped `estimated_lift`, `gaps_from()` hypotheses and per-service `yield_score` |

Vetting is not a separate lettered unit: it is the A18 decision-3 reuse of
`tools/vet_package.vet`, wrapped in `vet.py` and applied to every PyPI/npm hit before
status is decided.

## Sources, endpoints and quotas

No API key, no token, no auth anywhere.

| Source | Endpoint | Quota | Note |
|---|---|---|---|
| GitHub | `api.github.com/search/repositories` | **10 req/min measured** | `X-RateLimit-Remaining` read from every response; last live run ended at 4 |
| Hugging Face | `huggingface.co/api/models` | unknown | public model API, `sort=downloads` |
| PyPI | `pypi.org/simple/` + `pypi.org/pypi/<name>/json` | unknown | see below; no keyless JSON search exists |
| npm | `registry.npmjs.org/-/v1/search` + `/<name>/latest` + `api.npmjs.org/downloads` | unknown | search omits licence, so `/latest` is read per hit |
| arXiv | `export.arxiv.org/api/query` | unknown | 3 s spacing is self-imposed politeness, not a published rule |

**PyPI honesty note.** `pypi.org/search` returns a JavaScript client challenge (a 200
with no results) and the XML-RPC `search` method was removed. The connector therefore
reads the Simple index once (cached 24 h, 14.3 MB of project names), filters names by
query tokens with word-boundary matching, then reads per-project JSON for the best
few. `firetail` no longer matches `retail`.

Every connector has the same shape: `search(query, limit) -> list[raw hit]`, with a
pure `parse(payload)` that the tests replay. Every raw hit carries `source`, `url`,
`title`, `licence` (or `unknown`), `stars`/`downloads` when the source publishes them,
and `fetched_at`.

## Licence and adoption policy

Canonical ids are derived from what the source returned (GitHub `spdx_id`, HF
`license:` tag, PyPI `license_expression`/`license`/classifiers, npm `license`). An
unparsed value is `unknown`, never permissive.

| Status | Rule |
|---|---|
| `reject` | OSV returned a `MAL-*` advisory |
| `replace_later` | licence class `unknown`, `noncommercial` or `proprietary` — **never `adopt`** |
| `review` | copyleft (AGPL/GPL/MPL/LGPL), incomplete vet, or relevance below 0.30 |
| `adopt` | permissive/public-domain + vet clear or not applicable + relevance ≥ 0.30 |
| `watch` | papers (arXiv); research input, not a component |

`adopt_eligible` is written as its own field. A package whose OSV check could not
complete is `review`, never a silent pass.

## Live discovery run

Command and real output:

```
$ python -m tools.scout.collect --live --top 10
scout intel — LIVE
  queries=18 raw=90 unique=90 findings=58 duplicates=0 revisions=0 offtopic=24 off_domain=8
  urls verified=58 ok=58 direct=23 via_api=35 duration=85.65s
  source github: ok queries=6 hits=30 quota=4
  source huggingface: ok queries=3 hits=15 quota=None
  source pypi: ok queries=3 hits=15 quota=None
  source npm: ok queries=3 hits=15 quota=None
  source arxiv: ok queries=3 hits=15 quota=None
```

58 findings, every one with a live URL, a licence value and a verified status code.
Status split: 29 `adopt`, 18 `replace_later` (all unknown-licence), 6 `review`
(copyleft), 5 `watch` (papers). Licence classes: 29 permissive, 6 copyleft,
23 unknown. No unknown or non-commercial finding is `adopt`.

### Ranked top 10

| # | Finding | Service | Licence | Class | Lift | Score | Relevance | Status |
|---|---|---|---|---|---|---|---|---|
| 1 | `dgtlmoon/changedetection.io` | thewatch | Apache-2.0 | permissive | 12.3 | 86.2 | 0.80 | adopt |
| 2 | `AgriciDaniel/keywordpro` | keywords | Apache-2.0 | permissive | 6.0 | 80.0 | 1.00 | adopt |
| 3 | `Ryze-AI-Adgent/open-seo-mcp-skills` | keywords | MIT | permissive | 6.0 | 79.5 | 0.90 | adopt |
| 4 | `jez500/pricebuddy` | competitor-monitor | GPL-3.0 | copyleft | 11.1 | 77.0 | 0.90 | review |
| 5 | `springvoiceswell/semrush-ai-tool` | keywords | MIT | permissive | 6.0 | 76.7 | 0.90 | adopt |
| 6 | `keyword-cli` (PyPI) | keywords | MIT | permissive | 6.0 | 73.6 | 0.90 | adopt |
| 7 | `seo-keyword-research-tool` (PyPI) | keywords | MIT | permissive | 6.0 | 73.6 | 0.90 | adopt |
| 8 | `Dabble-Studio/3d-to-photo` | design-studio | MIT | permissive | 0.0 | 71.8 | 1.00 | adopt |
| 9 | `pixelpanda` (npm) | design-studio | MIT | permissive | 0.0 | 69.9 | 0.90 | adopt |
| 10 | `marketplace-price-tracker` (npm) | competitor-monitor | MIT | permissive | 9.8 | 69.6 | 0.50 | adopt |

`estimated_lift` is capped by the scorecard gap: design-studio and listings already
meet their bar in `ty/scorecards.json`, so their lift is 0 and they cannot outrank a
service with real headroom on popularity alone. `lift_basis` in each finding names the
formula and the cap.

### Gap list (A21 output, top rows)

| Service | Yield score | Open gap | Finding ids |
|---|---|---|---|
| competitor-monitor | 30.6 | 35.0 | `github-653aebe0b7c2`, `npm-ec36adc9cc09`, `npm-72ed12c2c5cd` |
| prospector | 25.7 | 63.0 | `github-9ccb241debab`, `github-6f483f682f2e`, `github-3116360044f3` |
| thewatch | 12.3 | 42.0 | `github-62a561385d43` |
| product-finder | 9.0 | 9.0 | `pypi-d25fca702f77`, `arxiv-b3c20834df5b` |
| listingforge | 8.5 | 8.5 | `huggingface-146c35ef7204`, `huggingface-98e8681e6678`, `huggingface-ed1a662c4397` |

Each gap row carries a hypothesis of the form *"If The Watch adopts X (Apache-2.0,
status adopt), expect up to 12.3 pts because stars=35641; 'Best and simplest tool for
website change detection…'"* — concrete field, concrete cap, falsifiable.

## URL verification

Every finding is checked. `verify_finding` does HEAD (GET on 400/403/405) against the
finding's `where`, records that status, and — when the public host refuses a
non-browser client — confirms the identity at the source's own machine endpoint.

| Source | Public URL | Authoritative check | Result |
|---|---|---|---|
| GitHub | `github.com/...` → 504 from this network | `api.github.com/repos/<owner>/<repo>` → 200 | 24/24 verified via API |
| npm | `npmjs.com/package/...` → 403 | `registry.npmjs.org/<name>/latest` → 200 | 11/11 verified via API |
| Hugging Face | model page → 200 | — | 14/14 direct |
| PyPI | project page → 200 | — | 4/4 direct |
| arXiv | abs page → 200 | — | 5/5 direct |

The 504/403 are recorded in `url_status`, not hidden: the finding keeps the real
answer for the human URL and the API status beside it (`verified_via`,
`verified_via_url`, `verified_via_status`). Host refusals are memoised after the first
probe, so the run does not spend 30 timeouts re-proving github.com does not answer.

## Tests

```
$ python -m pytest Northstar_backend/test_scout_intel.py -q
......................................................                   [100%]
54 passed in 0.30s
```

Fast and fully offline: recorded-fixture parsing for all five sources, licence
normalisation/classes, the unknown/non-commercial-never-adopt matrix, copyleft and
malicious outcomes, service mapping, gap-capped ranking, off-domain rejection,
dedupe vs revision, atomic write (and that `os.replace` is used), the closed refusal
vocabulary, Amazon refusal **before** transport (exploding opener), the API-fallback
verifier, dead-link reporting, and two whole dry runs that prove no write and no
network call.

## Known limits (not hidden)

1. **No daemon.** "Continuously" is a scheduler job, not a loop in this process; the
   lane is idempotent (`--live` can be re-run) and dedupe keeps revisions stable.
2. **GitHub HTML is unreachable from this box** (504) and npmjs.com refuses the client
   (403). Verification falls back to the authoritative API; the raw status stays in
   the record.
3. **A20 is partial by design**: text evidence and `file:line` anchors are extracted;
   video timestamps and screenshots are media-lane work.
4. **PyPI download counts are not available** in the JSON API, so `downloads` is
   `null` for PyPI findings and the ranking uses licence/relevance instead.
5. **Candidate cap** is 60 findings per run (`--max-findings`); a run currently yields
   58 after filtering 24 weak-relevance and 8 off-domain hits.
6. **Refusal log path** deviates from the A18 design note (`state/intel/refusals.jsonl`)
   because `state/` is gitignored in this repo. It lives at
   `tools/scout/refusals.jsonl`, inside this unit's write scope, so it is versioned.

## Evidence index

- Tests: `Northstar_backend/test_scout_intel.py` — 54 passed.
- Output: `ty/intel_gaps.json` (`schema: northstar.intel_gaps/1`), 58 findings, 58
  verified URLs, 11 gap rows.
- Fixtures: `tools/scout/fixtures/` (18 files, 65 KB, recorded 2026-11-08).
