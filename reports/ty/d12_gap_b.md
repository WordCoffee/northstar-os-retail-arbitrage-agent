# D12 gap-b — thewatch & rankledger proven against real implementations

- Worktree: `state/worktrees/gap-b`, branch `ty/gap-b`
- Date: 2026-11-08
- Files added (only these): `Northstar_backend/test_monitor.py`, `Northstar_backend/test_rank.py`, this report
- `main.py` and every non-scope file untouched (`git status` shows only the two new test files before this report)

## What actually exists (found by route dump + grep, not by assumption)

Route dump of the real `main.app` for `watch|rank|monitor|keyword|competitor` returns exactly one route:

| Service | Real surface | Location |
|---|---|---|
| thewatch | `GET /api/monitoring/error-alerts` | `Northstar_backend/main.py:959` |
| rankledger | `GET /api/v1/foundation/keywords/rank-history/{keyword_id}` | `Northstar_backend/foundation/api/router.py:1163` |
| rankledger (read layer) | `KeywordReadContracts.rank_history / rank_observations / alert_conditions` | `Northstar_backend/foundation/keywords/contracts.py:112-150` |

Important distinction, stated plainly: the rank route is on the **foundation app**
(`foundation/app.py:create_app`), not on `main.app`. `main.py` does not include the
foundation keyword router. The tests therefore build the real foundation app with its
real `create_app` factory over a disposable SQLite state, and authenticate with a real
HS256 JWT (placeholder `test-` secret only).

The monitoring route reads the real `error_alerts.tracker` singleton, which is also fed
by a middleware in `main.py:383-388` for every `/api/` response **after** the response is
sent. The tests account for exactly one middleware sample per request rather than hiding it.

## Tests and what each one proves

### `Northstar_backend/test_monitor.py` (thewatch, 6 tests)

| Test | Proof |
|---|---|
| `test_monitoring_envelope_and_empty_summary_shape` | 200 + exact `bff/v1` envelope: `request_id` is `req_` + 32 hex chars, `error is None`, `meta == {service: monitoring, version: v1}`; empty-tracker summary is an exact dict (window 300 s, threshold 0.05, min 10, rate `None`), and the alert is `ok`/`info` with `channel: None` (nothing is delivered). |
| `test_monitoring_endpoint_reads_live_tracker_and_raises_breach` | The endpoint reads live state, not a stub: 10×500 + 10×200 → total 20, five_xx 10, rate 0.5, `breached true`, alert `error_rate_breached`/`critical`, message contains `50.0%` and `exceeds the 5.0% threshold`; 400 good samples in-window dilute it to 10/421 = 2.38% and clear the breach. |
| `test_monitoring_counts_5xx_only` | 30 samples of 404/422/301 produce `five_xx == 0`, rate 0.0, no breach — the gate is 500–599 only. |
| `test_monitoring_min_sample_floor_suppresses_breach` | 9×500 (100% 5xx) is **not** a breach below `min_requests=10`; proves the floor, not just the ratio. |
| `test_monitoring_rejects_post_with_405_and_advertises_get` | Error path: `POST` → 405 with `Allow: GET`. |
| `test_monitoring_unknown_subpath_is_404` | Error path: unknown subpath → 404 `{"detail": "Not Found"}`. |

### `Northstar_backend/test_rank.py` (rankledger, 6 tests)

| Test | Proof |
|---|---|
| `test_rank_history_route_returns_persisted_series_in_time_order` | Real route returns the three persisted observations as `[12, 9, 4]` in `observed_at ASC` order, same `keyword_id`/`asin`/`placement`/`source`, and every row has exactly the 9 contract keys (no internal/org fields leak). |
| `test_rank_history_keeps_unobserved_rank_null_and_missing_series_empty` | A stored observation with no measured rank stays `null` (never 0); a tracked keyword with no observations returns `[]`; an unknown keyword id returns 200 + `[]`, not a fabricated row. |
| `test_rank_history_is_organization_scoped` | Another org's keyword, which really has a rank=1 observation, returns `[]` for our org; the repo-level `for_keyword` confirms zero cross-org rows. |
| `test_rank_history_requires_authentication` | Error path: no Authorization → 401 with detail code `authentication_required`. |
| `test_rank_observation_filters_apply_and_compose` | `asin`, `placement`, both combined, and `limit` each return exactly the matching rows; another org's ASIN returns `[]`. |
| `test_alert_conditions_flag_only_keywords_without_a_known_rank` | Alerts fire only for `rank_unknown` (null latest or no observation), never for a keyword with a measured latest rank, and never across orgs; phrase passthrough is asserted. |

No `skip`, no `xfail`, no `assert True`, no 200-without-body. Every assertion is a concrete
value or set that would fail if the implementation changed or fabricated data.

## Test run

Command:

```
python -m pytest Northstar_backend/test_monitor.py Northstar_backend/test_rank.py -q
```

Tail from one captured run (timings vary per run):

```
............                                                             [100%]
=============================== warnings summary ===============================
Northstar_backend/design_studio_api.py:1455
  ... UserWarning: Field name "copy" in "APlusPackIn" shadows an attribute in parent "BaseModel"
    class APlusPackIn(BaseModel):
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
12 passed, 1 warning in 5.36s
```

The single warning is pre-existing (`design_studio_api.py:1455`), unrelated to these tests.
No network, no paid provider, no Amazon, no sleeps; all data is local and deterministic.

## Honest gap list (what these tests do **not** cover, because it does not exist)

### thewatch
1. **No watchlist CRUD, thresholds, signal feed, snapshot history, or alert acknowledgement.**
   `docs/northstar-phase1/19-watch-spec.md` §3/§5/§6 describes them; no route, module or table
   exists in `main.py` or the backend (grep for `watchlist`, `watch`, `threshold`, `signal`,
   `snapshot` returns only this one monitoring route and unrelated text).
2. **No `/thewatch/:productId` product-level API** (price/rank/seller history). Nothing to test.
3. **Envelope status is hardcoded** at `main.py:974`: `"status": "ok" if not summary["breached"] else "ok"`.
   A breach is visible only inside `data.alert`; the top-level status never changes. The test
   pins the alert-level breach but deliberately does not bless the status field as correct.
4. **No alert delivery.** `channel` is `None` by design (`error_alerts.compose_alert`), so there is
   no delivery path to test.
5. The tracker is process-memory only (restart clears it) and counts the monitoring request
   itself; there is no persistence or per-product dimension.
6. **No UI tests for the watch surface** — there are no watch UI routes to drive offline.

### rankledger
1. **No rank routes in `main.app`.** The only rank HTTP route lives on the standalone foundation
   app. If the deployed server is `main:app` only, RankLedger's rank route is not exposed there.
   That is a wiring gap, not a test gap.
2. **No keyword-group CRUD, annotations, trend-alert thresholds, or track/untrack actions.**
   `20-rankledger-spec.md` §3/§6 lists them; only imported keywords and rank reads exist.
3. **No HTTP route** for rank-observation filtering or `alert_conditions`; those are exercised at
   the real `KeywordReadContracts` layer instead of inventing endpoints.
4. **No rank capture/scheduler.** Rank observations must be written by an importer or another
   job; nothing here refreshes rank from a provider, and no test asserts a provider call.
5. `rank-history/{unknown_id}` returns 200 + `[]` rather than 404 — current behaviour is pinned,
   but it is ambiguous for API consumers.
6. The model comment says rank is `null = unknown, never 0`, but nothing at write time rejects 0;
   the tests prove null is preserved, not that 0 is refused.
7. **No UI tests for `/rankledger`** — the room has no offline-drivable API beyond the reads above.

## Scope compliance

- Only `Northstar_backend/test_monitor.py`, `Northstar_backend/test_rank.py` and this report were written.
- No changes to `main.py`, `AGENTS.md`, `docs/OPERATING_CONSTITUTION.md`, config, or any other file.
- No Amazon, no spending/credits, no credentials read or written, no installs. The JWT secret is a
  placeholder beginning with `test-`, which the ancestor conftest never treats as a credential.
