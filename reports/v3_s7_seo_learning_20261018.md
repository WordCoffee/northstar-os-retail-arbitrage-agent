# V3 S7 §5.4 — Measurement + learning (the deterministic part)

**Date:** 2026-10-18 · **Branch:** `feature/v3-simple-view` · **Status:** BUILT, tests green, local commit.

## What this closes

The Brand Analytics importer (`importers/brand_analytics_importer.py`) already
lands Search Query Performance rows in `search_query_performance`, but nothing
consumed them. §5.4 now turns those **measured** rows into **candidate** keyword
additions for a brand profile — a learning step that is honest by construction.

## Design rules honoured

- **Measured, not modelled.** Ranking uses the row's `search_frequency_rank`
  (lower = more frequent), then impressions. No rank/traffic/volume number is
  ever invented.
- **Proposals only.** `propose_from_sqp` never writes. Approving is an operator
  action that appends a new profile version through the existing append-only
  path — nothing is rewritten silently.
- **No duplicates.** Queries already covered by the profile's head/body/negative
  clusters are excluded (substring match, case-folded).
- **Honest absence.** No rows → no proposals, plus an explicit caveat. Rows that
  are all already covered → empty list, plus a caveat saying so.
- **Scope is explicit.** `search_query_performance` has no account column, so the
  SQP read store requires the caller to name the ASIN(s); it does not pretend to
  be tenant-scoped when it is not.

## Pieces

| Piece | Where | What |
|---|---|---|
| Read store | `data_layer.py` `SqpPerformanceDB` (on `SeoContainer.sqp`) | Read-only SQP rows, ordered by measured rank, scoped by ASIN. |
| Engine | `seo_learn.py` `propose_from_sqp` | Deterministic candidate terms + evidence + caveats. |
| Service | `seo_router.py` `GET /api/seo/proposals` | Read-only; resolves the brand profile, reads scoped rows, returns proposals. Writes nothing. |
| Shell hook | `chat_tools.py` `seo_propose` (Grow focus) | Candidate terms as an AG-UI card; honest errors when no profile/ASIN. |

## Evidence

```
python -m py_compile seo_learn.py seo_router.py chat_tools.py data_layer.py shell_focus.py  → PY OK
python -m pytest test_seo_learning.py                                                       → 12 passed
python -m pytest test_seo_learning test_seo_listing test_seo_profiles test_shell_modes \
                  test_chat_fork test_tool_gateway test_voicestudio_adapter                 → 109 passed
seo_router.routes contains /api/seo/proposals                                                → True
```

`test_seo_learning.py` (12) covers: exclusion of already-covered terms,
ranking by rank-then-impressions, duplicate-query aggregation, honest empty
input, the `min_impressions` filter, ASIN scoping of the read store, the
`seo_propose` tool (candidates, needs-ASIN, no-profile), Grow-focus registration,
and the router endpoint (read-only proof: profile version unchanged; 400 without
an ASIN).

## Honest limits / what's next

- This is the **file-import** half of §5.4. Embedding drift
  (`qwen3-embedding:0.6b` + sqlite-vec) is the remaining half.
- Remaining §5.3 pipeline features: AdPilot negatives/harvest, SocialPulse
  external-traffic framing, SourceScout title/pack normalisation.
- Nothing was pushed; all work is local on `feature/v3-simple-view`.
