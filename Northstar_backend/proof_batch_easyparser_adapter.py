"""Real-data-ready Easyparser adapter for the fixed 20-ASIN Proof Batch run
(design: docs/proof-batch-easyparser-live-adapter-plan.md).

OFFLINE-FIRST: importing this module makes NO network call. The adapter
cannot touch any provider transport unless a client is EXPLICITLY injected
(adapter_config["client"]) AND allow_live=True is passed — the adapter never
defaults to the real easyparser client, so a test that forgets its fake
client fails closed at construction. This build's CLI wires the adapter with allow_live=True only inside the
guarded run path AFTER every runner guard passes
(docs/proof-batch-adapter-arming-plan.md), and the adapter still refuses
unless both external runtime gates are set - SCANNER_LIVE_ALLOWED=1 and
PROOF_BATCH_LIVE_ARMED=1. Both are absent by default, so every live
invocation refuses before any client contact. Enabling a real pull requires
the human to set PROOF_BATCH_LIVE_ARMED=1 in the runtime environment (a
separate, explicit, non-secret opt-in - never a code default, never a CLI
argument, never a UI/GET route).

Narrow boundary (one ASIN per invocation):
    fetch(asin, request_index) -> normalized client-shaped dict + scrubbed
    'adapter_request_meta' key.

Hard invariants (no fallback anywhere):
  - No scanner cache, no candidate discovery, no enrich_cached_asins.py.
  - No --asin/--asins/--input-file options exist at any level.
  - Zero automatic retries (retries_used is always 0; retry policy is a
    separate future human-approved change).
  - Per-attempt credit accounting with distinct actual vs estimate
    (credit_accounting_status: provider_reported | estimated_only |
    unavailable; actual_credits_used is null unless the provider reported a
    usable positive int).
  - The injected client must be the project's single safe public method
    (easyparser_client.get_easyparser_offers) in a future real build — in
    this build every test injects a fake.
  - Every result and every meta is secret-scanned before it leaves fetch();
    unknown values stay null, never 0; nothing is fabricated.

Class-identity note: GuardError, ProviderAdapter, and the other shared
contracts are imported from proof_batch_contracts (stdlib-only). Both this
adapter and the runner import the SAME proof_batch_contracts.ProviderAdapter /
.GuardError classes, so the runner's strict isinstance(adapter,
ProviderAdapter) guard always resolves against the one shared base — no
__main__ double-import divergence, even under reload/runpy/subprocess probes.
The runner keeps its __main__-alias belt-and-suspenders but no longer relies
on it as the sole identity solution. Verified by regression tests in
test_proof_batch_easyparser_adapter.py.
"""

import os
import re
from typing import Any, Callable, Dict, Optional

import proof_batch as pb
from proof_batch_contracts import (
    GuardError,
    ProviderAdapter,
    ESTIMATED_CREDITS_PER_REQUEST,
)

REQUESTED_FIELDS = ("market_offers",)
PROVIDER_NAME = "EASYPARSER"

# Second explicit, non-secret external arm gate (read-only runtime check).
# Real execution requires BOTH this gate (PROOF_BATCH_LIVE_ARMED=1) AND the
# external SCANNER_LIVE_ALLOWED gate AND every runner guard. This gate is
# DISABLED by default: only an explicit environment value of "1" arms it.
# Absent/blank/"false"/"0"/"no"/any invalid value is disabled. It is separate
# from SCANNER_LIVE_ALLOWED; no CLI argument, UI/GET route, report command,
# dry-run, fixture run, test helper, or normal import can enable it; it never
# mutates the environment and nothing here prints environment contents.
PROOF_BATCH_LIVE_ARMED_ENV = "PROOF_BATCH_LIVE_ARMED"


def proof_batch_armed() -> bool:
    """Read-only Proof Batch arm gate. Enabled ONLY by an explicit runtime
    value of PROOF_BATCH_LIVE_ARMED=1. Any other value (absent, blank,
    'false', '0', 'no', invalid) is disabled."""
    return os.environ.get(PROOF_BATCH_LIVE_ARMED_ENV) == "1"


def real_easyparser_client():
    """Lazily resolve the project's real Easyparser offer client.

    Kept on the adapter module (not in proof_batch_run.py) so the runner's
    source stays free of provider-client import tokens, per the containment
    contract (ContainmentTests.test_module_imports_no_provider_client).
    Importing this function makes NO network call; only calling the returned
    client does, and only in the armed production path after every guard
    passes."""
    import easyparser_client as ep_client
    return ep_client.get_easyparser_offers

_ASIN_PATTERN = re.compile(r"^[A-Za-z0-9]{10}$")

# data_gaps substrings that classify a failed/malformed provider outcome.
_PROVIDER_ERROR_GAPS = (
    "timed out",
    "failed at the network level",
    "returned HTTP",
    "success is false",
    "API key is not configured",
    "Invalid ASIN",
)
_PARSE_ERROR_GAPS = (
    "not valid JSON",
    "unexpected structure",
    "missing result data",
    "missing result.product",
    "missing result.offer.offer_results",
)


def _gap_classification(result: Dict[str, Any]) -> str:
    """provider_status from the client's data_gaps: success | provider_error |
    parse_error. Informational gaps (subset/zip caveats) mean success."""
    gaps = [g for g in (result.get("data_gaps") or []) if isinstance(g, str)]
    for gap in gaps:
        if any(prefix in gap for prefix in _PROVIDER_ERROR_GAPS):
            return "provider_error"
    for gap in gaps:
        if any(prefix in gap for prefix in _PARSE_ERROR_GAPS):
            return "parse_error"
    return "success"


def _credit_accounting(result: Dict[str, Any]) -> tuple:
    """(actual_credits_used, credit_accounting_status). actual is a positive
    int ONLY when the provider explicitly reported one; otherwise None with
    the honest status (estimated_only = provider evidence absent and the
    documented estimate stands in; unavailable = provider returned something
    unusable, never interpreted as a credit count)."""
    credits = result.get("credits_used")
    if isinstance(credits, int) and not isinstance(credits, bool) and credits > 0:
        return credits, "provider_reported"
    if credits is None:
        return None, "estimated_only"
    return None, "unavailable"


class EasyparserLiveAdapter(ProviderAdapter):
    """One-ASIN Easyparser market-offers adapter behind the full guard stack.

    Construction REFUSES unless allow_live=True (never set by this build's
    CLI) AND an explicit client is injected (never defaults to the real
    transport — fail closed). fetch() re-verifies the guard context; the
    injected client is the only network-capable object, so every path is
    exercisable offline with mocks.
    """

    NAME = "easyparser-live"

    def __init__(self, adapter_config: Optional[Dict[str, Any]] = None):
        config = adapter_config if isinstance(adapter_config, dict) else {}
        if pb.contains_secret_like(config):
            raise GuardError("adapter_config contains secret-like keys; refused")
        self.allow_live = bool(config.get("allow_live"))
        self.run_id = config.get("run_id")
        self.preflight_fingerprint = config.get("preflight_fingerprint")
        self.request_budget_remaining = config.get("request_budget_remaining")
        self.credit_budget_remaining = config.get("credit_budget_remaining")
        raw_est = config.get("estimated_credits_per_request")
        if raw_est is None:
            raw_est = ESTIMATED_CREDITS_PER_REQUEST
        try:
            self.estimated_credits_per_request = float(raw_est)
        except (TypeError, ValueError):
            raise GuardError("estimated_credits_per_request must be numeric") from None
        if self.estimated_credits_per_request <= 0:
            raise GuardError("estimated_credits_per_request must be positive")
        self.client: Optional[Callable[[str], dict]] = config.get("client")
        self.force_synthetic_label = bool(config.get("force_synthetic_label"))
        self.requests_made: list = []
        self.attempts = 0
        self.retries_used = 0

        if not self.allow_live:
            raise GuardError(
                "easyparser-live adapter is not enabled in this build (allow_live=False). "
                "No live execution is possible until a separately human-approved build "
                "enables it; no provider call was made."
            )
        if not proof_batch_armed():
            raise GuardError(
                "easyparser-live adapter is not armed (set %s=1 in the runtime "
                "environment to authorize the guarded live path); adapter remains "
                "disabled by default. No live execution is possible until the arm gate "
                "is explicitly set; no provider call was made." % PROOF_BATCH_LIVE_ARMED_ENV
            )
        if not callable(self.client):
            raise GuardError(
                "adapter requires an explicitly injected client; it never defaults to "
                "the real easyparser transport in this build (fail closed - tests must "
                "supply a fake client)"
            )
        if not isinstance(self.run_id, str) or not self.run_id:
            raise GuardError("adapter requires run_id")
        if not isinstance(self.preflight_fingerprint, str) or not self.preflight_fingerprint:
            raise GuardError("adapter requires preflight_fingerprint")

    def refresh_guard_state(self, request_budget_remaining: int, credit_budget_remaining: float) -> None:
        """Runner refreshes stop-before values before each request."""
        self.request_budget_remaining = request_budget_remaining
        self.credit_budget_remaining = credit_budget_remaining

    def _guard_fetch(self, asin: str, request_index: int) -> str:
        if not self.allow_live:
            raise GuardError("live adapter disabled; no provider call")
        if not isinstance(asin, str) or not _ASIN_PATTERN.fullmatch(asin.strip()):
            raise GuardError(f"invalid ASIN for live fetch: {asin!r}")
        canonical = asin.strip().upper()
        if not isinstance(request_index, int) or isinstance(request_index, bool) or request_index < 1:
            raise GuardError("request_index must be an integer >= 1")
        if self.request_budget_remaining is not None:
            if (not isinstance(self.request_budget_remaining, int)
                    or isinstance(self.request_budget_remaining, bool)
                    or self.request_budget_remaining < 1):
                raise GuardError("request budget exhausted; stop-before violated")
        if self.credit_budget_remaining is not None:
            if (not isinstance(self.credit_budget_remaining, (int, float))
                    or isinstance(self.credit_budget_remaining, bool)
                    or self.credit_budget_remaining < 0):
                raise GuardError("credit budget exhausted; stop-before violated")
            if self.estimated_credits_per_request > self.credit_budget_remaining:
                raise GuardError(
                    "estimated cost of the next request exceeds the credit budget; "
                    "stop-before violated — no provider call"
                )
        return canonical

    def _build_meta(self, requested_asin: str, request_index: int, result: Dict[str, Any]) -> Dict[str, Any]:
        actual, accounting_status = _credit_accounting(result)
        return {
            "request_index": request_index,
            "request_attempted": True,
            "requested_asin": requested_asin,
            "provider": PROVIDER_NAME,
            "requested_fields": list(REQUESTED_FIELDS),
            "estimated_credits_per_request": round(self.estimated_credits_per_request, 2),
            "estimated_credits_consumed": round(self.estimated_credits_per_request, 2),
            "actual_credits_used": actual,
            "credit_accounting_status": accounting_status,
            "request_id": result.get("request_id"),
            "provider_status": _gap_classification(result),
            "provider_asin": result.get("provider_asin"),
            "captured_at": result.get("observed_at"),
            "retries_used": 0,
            "run_id": self.run_id,
            "preflight_fingerprint": self.preflight_fingerprint,
        }

    def fetch(self, asin: str, request_index: int) -> Dict[str, Any]:
        """One ASIN, one request attempt, zero retries. Returns the client-
        shaped normalized dict plus a scrubbed 'adapter_request_meta' key."""
        canonical = self._guard_fetch(asin, request_index)
        self.attempts += 1
        result = self.client(canonical)
        if not isinstance(result, dict):
            raise GuardError(f"adapter client returned a non-dict result for {canonical}")
        if pb.contains_secret_like(result):
            raise GuardError(f"secret-like key in provider result for {canonical}; refused")
        meta = self._build_meta(canonical, request_index, result)
        if pb.contains_secret_like(meta):
            raise GuardError(f"secret-like key in adapter request meta for {canonical}; refused")
        result["adapter_request_meta"] = meta
        self.requests_made.append(canonical)
        return result
