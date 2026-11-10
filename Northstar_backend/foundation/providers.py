"""Provider registry + adapter contract + fixture adapter.

Phase 1B: definitions, capability declarations, credential-*name* metadata only,
health state, and a fixture adapter. NO external execution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Protocol

from .enums import ProviderHealth, CapabilitySafetyClass, Environment, ProvenanceClass
from .models import ProviderDefinition, Observation
from .provenance import make_observation
from .enums import ObservationType


class ProviderDisabledError(RuntimeError):
    pass


class ProviderAdapter(Protocol):
    provider_key: str

    def capabilities(self) -> list[str]: ...
    def read(self, request: dict) -> dict: ...
    def write(self, request: dict) -> dict: ...


@dataclass
class ProviderResult:
    ok: bool
    observations: list[Observation] = field(default_factory=list)
    error_class: Optional[str] = None
    message: Optional[str] = None
    cost_kind: str = "unknown"
    estimated_cost: Optional[float] = None


class BaseAdapter:
    """Adapter contract. Real adapters would call providers; base does nothing."""

    provider_key: str = "base"
    read_capable: bool = True
    write_capable: bool = False

    def capabilities(self) -> list[str]:
        caps = [CapabilitySafetyClass.READ.value] if self.read_capable else []
        if self.write_capable:
            caps.append(CapabilitySafetyClass.WRITE_EXTERNAL.value)
        return caps

    def read(self, request: dict) -> ProviderResult:
        raise NotImplementedError

    def write(self, request: dict) -> ProviderResult:
        raise ProviderDisabledError("write not permitted in Phase 1B")


class FixtureAdapter(BaseAdapter):
    """Returns deterministic fixture observations. Never touches a network."""

    def __init__(self, provider_key: str, fixtures: Optional[dict] = None) -> None:
        self.provider_key = provider_key
        self._fixtures = fixtures or {}

    def read(self, request: dict) -> ProviderResult:
        key = request.get("fixture_key", "")
        payload = self._fixtures.get(key)
        obs: list[Observation] = []
        if payload is not None:
            obs.append(make_observation(
                observation_type=request.get("observation_type", ObservationType.PRICE.value),
                observed_value=payload,
                provider=self.provider_key,
                provider_record_id=f"fixture:{key}",
                provenance_class=ProvenanceClass.MOCKED,
                raw_source_ref=f"fixture://{self.provider_key}/{key}",
                environment=request.get("environment", Environment.SANDBOX.value),
            ))
        else:
            obs.append(make_observation(
                observation_type=request.get("observation_type", ObservationType.PRICE.value),
                observed_value=None,  # null-first
                provider=self.provider_key,
                provenance_class=ProvenanceClass.UNAVAILABLE,
                raw_source_ref=f"fixture://{self.provider_key}/{key}",
                environment=request.get("environment", Environment.SANDBOX.value),
            ))
        return ProviderResult(ok=True, observations=obs, cost_kind="local_free")


class ProviderRegistry:
    def __init__(self, repos) -> None:
        self.repos = repos
        self._adapters: dict[str, ProviderAdapter] = {}

    def register_definition(self, defn: ProviderDefinition) -> dict:
        existing = self.repos.providers.by_key(defn.provider_key)
        if existing is None:
            self.repos.providers.add(defn)
        return self.repos.providers.by_key(defn.provider_key)

    def bind_adapter(self, adapter: ProviderAdapter) -> None:
        self._adapters[adapter.provider_key] = adapter

    def adapter(self, provider_key: str) -> ProviderAdapter:
        if provider_key not in self._adapters:
            raise ProviderDisabledError(f"no adapter bound for {provider_key!r}")
        return self._adapters[provider_key]

    def is_enabled(self, provider_key: str) -> bool:
        row = self.repos.providers.by_key(provider_key)
        return bool(row and row.get("enabled"))

    def execute_read(self, provider_key: str, request: dict) -> ProviderResult:
        """Guarded read. Disabled providers never execute."""
        row = self.repos.providers.by_key(provider_key)
        if not row or not row.get("enabled"):
            return ProviderResult(ok=False, error_class="provider_disabled",
                                  message=f"{provider_key} is disabled")
        adapter = self.adapter(provider_key)
        return adapter.read(request)

    def execute_write(self, provider_key: str, request: dict) -> ProviderResult:
        """Writes are never executed in Phase 1B."""
        return ProviderResult(ok=False, error_class="write_not_permitted",
                              message="external writes are disabled in Phase 1B")