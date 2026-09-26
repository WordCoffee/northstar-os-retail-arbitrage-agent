# 07 — Provenance (implemented)

## Observation envelope (owner decision 3)

`foundation/models.py:Observation` carries every required field:

`observation_id (id), product_id, candidate_id, marketplace_id, provider,
provider_record_id, observation_type, observed_value, currency, unit, captured_at,
effective_at, expires_at, confidence, verification_state, provenance_class,
raw_source_ref, transformation_version, job_run_id, environment`.

## Provenance classifications (owner decision C)

`live, cached, imported, benchmark, computed, estimated, mocked, stale, unavailable`.

- `make_observation` forces `provenance_class = unavailable` when `observed_value is None`
  (null-first).
- `is_current_fact(class)` returns **False** for `benchmark`, `mocked`, `stale`,
  `unavailable` — these are never presented as current facts.
- `classify_staleness(expires_at)` → `fresh | stale | unknown_age`.

## Freshness & null-first

- Unknown values stay `None`; never coerced to `0`/`""` (verified by tests).
- `provenance_meta(obs)` emits a stable metadata block for API responses.
- Freshness windows carried from Phase 1A (offers 7d / sales 30d / identity 90d) are
  applied at read-model level in Phase 1C; the envelope stores explicit `expires_at`.

## Evidence

- `foundation/provenance.py`
- `foundation/tests/test_provenance.py` (5 tests)