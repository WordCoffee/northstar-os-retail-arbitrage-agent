# Jev (TypeSafe) integration — 2026-10-24

## What was integrated
TypeSafe Jev as an **opt-in cloud decision backend** in `Northstar_backend/decision_layer.py`,
mirroring the existing laya backend pattern:

- `_jev_credentials()` / `_jev_available()` — presence checks only (JEV_API_URL + JEV_API_KEY or
  TYPESAFE_API_KEY). No network, no credential echo.
- `_jev_decide(kind, text)` — POSTs a typed decision request (kind, text, closed labels,
  instructions, criteria) to the configured URL with a Bearer token, parses value/confidence/
  probabilities from a flexible response shape, validates against the closed label set, and
  returns `None` on any failure so callers fall back to rules.
- `decide(..., backend="jev"|"typesafe")` selects it; `backend="auto"` stays local
  (rules/laya) and only touches Jev when `JEV_AUTO=1` is set — no silent spend.
- Covers every kind, including `duplicate` (which has no rule backend), so Jev can lift
  kinds the rules backend abstains on.
- `typesafe_jev` registered in `shared/provider-suite.json` (cloud lane, metered, gate
  `CLOUD_MODEL_LIVE` armed). Defaults to `gate_not_armed` → safe.
- `.env.example` gained `JEV_API_URL`, `JEV_API_KEY`, `TYPESAFE_API_KEY`, `JEV_MODEL`,
  `JEV_AUTO` (names only).
- Tests: 5 new cases in `test_decision_layer.py` (fallback reasons, missing key, no auto-use
  by default, duplicate-kind decision). All 49 tests in decision_layer + provider_suite pass.

## Cost tracking (usage meter + margin safety)
Jev is metered and rolled into the existing per-tier usage meter so it cannot erode margins:

- `usage_meter.ACTIONS` gained `jev_decision` (per-account, per-month counter; fail-closed
  on unknown action).
- `shared/usage-caps.json`: added `jev_decision` unit cost (`$0.00005`, ~$0.042/M input
  tokens with safety margin) and per-tier caps (~10% of each tier's listing cap).
- `cost_model.worst_case()` prices `jev_decision` caps into the worst-case cost; margins
  after integration: whetstone 0.7044, mainstay 0.7001, keystone 0.7064, autothink 0.7042 —
  all at or above the 70% target and inside the 60–80% band.
- `_jev_decide` captures token `usage` from the API response when present, for future
  precise per-token billing.

## What was NOT integrated (deliberately)
The `browser-use/jev-ultrafast` browser agent. It drives Playwright directly and Northstar's
sole browser controller is Chrome Connect (`tools/chromeconnect_guard.py` refuses raw
playwright imports; port 9222 is exclusively locked). Adopting it would create a second
browser path — the same rejection already recorded for `lightpanda` and `herk_edit_kit`.
Only the Jev *decision* API is wired; the browser loop stays blocked.

## Open items / blockers
- TypeSafe endpoint + response schema must be verified against docs before live use; the
  seam degrades to rules until then (no breakage).
- Commercial terms for TypeSafe Jev to be confirmed before arming `CLOUD_MODEL_LIVE`.
- Spend caps (P7-T1) must be set before any armed use.
- Optional: wire `JEV_AUTO=1` only after cost is measured against the rules baseline.

## Files touched
- Northstar_backend/decision_layer.py
- shared/provider-suite.json
- .env.example
- Northstar_backend/test_decision_layer.py
