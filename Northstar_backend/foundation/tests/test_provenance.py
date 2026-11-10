"""Provenance, freshness, null-first tests (owner decision 3)."""
from __future__ import annotations

from datetime import timedelta

from Northstar_backend.foundation.provenance import (
    make_observation, classify_staleness, provenance_meta, is_current_fact,
)
from Northstar_backend.foundation.models import utcnow
from Northstar_backend.foundation.enums import (
    ProvenanceClass, ObservationType, VerificationState, StalenessState,
)


def test_none_observation_becomes_unavailable_not_zero():
    obs = make_observation(observation_type=ObservationType.PRICE, observed_value=None,
                           provenance_class=ProvenanceClass.CACHED)
    assert obs.observed_value is None
    assert obs.provenance_class == ProvenanceClass.UNAVAILABLE.value


def test_observation_envelope_fields():
    obs = make_observation(
        observation_type=ObservationType.PRICE, observed_value={"amount": 9.99},
        provider="fixture_price", provider_record_id="r1", currency="USD",
        confidence=0.8, verification_state=VerificationState.PENDING,
        provenance_class=ProvenanceClass.LIVE, raw_source_ref="s3://x",
        transformation_version="v1", job_run_id="run1")
    assert obs.provider_record_id == "r1"
    assert obs.currency == "USD"
    assert obs.confidence == 0.8
    assert obs.transformation_version == "v1"
    assert obs.job_run_id == "run1"


def test_staleness_fresh_vs_stale():
    now = utcnow()
    assert classify_staleness(now + timedelta(hours=1), now) == StalenessState.FRESH.value
    assert classify_staleness(now - timedelta(hours=1), now) == StalenessState.STALE.value
    assert classify_staleness(None, now) == StalenessState.UNKNOWN_AGE.value


def test_benchmark_and_mocked_are_not_current_facts():
    assert not is_current_fact(ProvenanceClass.BENCHMARK.value)
    assert not is_current_fact(ProvenanceClass.MOCKED.value)
    assert not is_current_fact(ProvenanceClass.STALE.value)
    assert not is_current_fact(ProvenanceClass.UNAVAILABLE.value)
    assert is_current_fact(ProvenanceClass.LIVE.value)
    assert is_current_fact(ProvenanceClass.CACHED.value)


def test_provenance_meta_shape():
    obs = make_observation(observation_type=ObservationType.PRICE,
                           observed_value=1.0, provider="p",
                           provenance_class=ProvenanceClass.LIVE)
    meta = provenance_meta(obs)
    for key in ("provenance_class", "source", "source_identifier",
                "captured_at", "confidence", "verification_state", "staleness_state"):
        assert key in meta