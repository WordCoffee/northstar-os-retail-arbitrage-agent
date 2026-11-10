"""Provenance utilities: observation envelope builders, freshness, null-first."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from .enums import (
    ProvenanceClass, VerificationState, StalenessState, SourceKind,
    ObservationType, Environment,
)
from .models import Observation, utcnow


def make_observation(
    *,
    observation_type: str | ObservationType,
    observed_value: Any,
    provider: Optional[str] = None,
    provider_record_id: Optional[str] = None,
    product_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
    marketplace_id: Optional[str] = None,
    currency: Optional[str] = None,
    unit: Optional[str] = None,
    provenance_class: str | ProvenanceClass = ProvenanceClass.CACHED,
    confidence: Optional[float] = None,
    verification_state: str | VerificationState = VerificationState.UNVERIFIED,
    raw_source_ref: Optional[str] = None,
    transformation_version: Optional[str] = None,
    job_run_id: Optional[str] = None,
    captured_at: Optional[datetime] = None,
    effective_at: Optional[datetime] = None,
    expires_at: Optional[datetime] = None,
    environment: str | Environment = Environment.PRODUCTION,
) -> Observation:
    """Build an observation envelope. Missing values stay None (null-first)."""
    ot = observation_type.value if isinstance(observation_type, ObservationType) else observation_type
    pc = provenance_class.value if isinstance(provenance_class, ProvenanceClass) else provenance_class
    vs = verification_state.value if isinstance(verification_state, VerificationState) else verification_state
    env = environment.value if isinstance(environment, Environment) else environment
    # Never coerce None to a "value"
    if observed_value is None:
        pc = ProvenanceClass.UNAVAILABLE.value
    return Observation(
        product_id=product_id,
        candidate_id=candidate_id,
        marketplace_id=marketplace_id,
        provider=provider,
        provider_record_id=provider_record_id,
        observation_type=ot,
        observed_value=observed_value,
        currency=currency,
        unit=unit,
        captured_at=captured_at or utcnow(),
        effective_at=effective_at,
        expires_at=expires_at,
        confidence=confidence,
        verification_state=vs,
        provenance_class=pc,
        raw_source_ref=raw_source_ref,
        transformation_version=transformation_version,
        job_run_id=job_run_id,
        environment=env,
    )


def classify_staleness(expires_at: Optional[datetime], now: Optional[datetime] = None) -> str:
    if expires_at is None:
        return StalenessState.UNKNOWN_AGE.value
    now = now or utcnow()
    return StalenessState.FRESH.value if now < expires_at else StalenessState.STALE.value


def provenance_meta(obs: Observation, now: Optional[datetime] = None) -> dict:
    return {
        "provenance_class": obs.provenance_class,
        "source": SourceKind.PROVIDER.value if obs.provider else SourceKind.IMPORT.value,
        "source_identifier": obs.provider_record_id or obs.raw_source_ref,
        "captured_at": obs.captured_at.isoformat() if obs.captured_at else None,
        "confidence": obs.confidence,
        "verification_state": obs.verification_state,
        "staleness_state": classify_staleness(obs.expires_at, now),
    }


# Classes that must never be presented as current facts.
NON_CURRENT_CLASSES = {ProvenanceClass.BENCHMARK.value, ProvenanceClass.MOCKED.value,
                       ProvenanceClass.UNAVAILABLE.value, ProvenanceClass.STALE.value}


def is_current_fact(provenance_class: str) -> bool:
    return provenance_class not in NON_CURRENT_CLASSES