"""Typed job-handler registry + fake/local handlers (1C-04 / B06).

Every handler declares its contract (input/output schema versions, permission,
approval/provider/budget classes, retry and timeout policies, cancellation
support, idempotency behavior). Unregistered job types FAIL CLOSED.

Fake/local handlers are deterministic and make zero network/provider calls.
They are the ONLY handlers that may execute in 1C-04.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Callable, Optional

from .permissions import PERM_RUN_LOCAL

# Failure classes (retry semantics live here, not in the DB).
TRANSIENT = "transient_error"
PERMANENT = "permanent_error"
RATE_LIMITED = "rate_limited"
TIMEOUT = "timeout"
MALFORMED_OUTPUT = "malformed_output"
CANCELLED = "cancelled"
BUDGET_VARIANCE = "budget_variance"
UNKNOWN = "unknown"

RETRYABLE_CLASSES = frozenset({TRANSIENT, RATE_LIMITED, TIMEOUT, UNKNOWN})
PERMANENT_CLASSES = frozenset({PERMANENT, MALFORMED_OUTPUT, BUDGET_VARIANCE})

DEFAULT_RETRY_POLICY = {"max_attempts": 3, "backoff_base_seconds": 1,
                        "backoff_multiplier": 2, "max_backoff_seconds": 60,
                        "jitter_seconds": 0.1}
DEFAULT_TIMEOUT_POLICY = {"timeout_seconds": 30}


@dataclass(frozen=True)
class JobHandlerSpec:
    job_type: str
    input_schema_version: str
    output_schema_version: str
    required_permission: str = PERM_RUN_LOCAL
    approval_class: str = "none"          # "none" | "operator" | "owner"
    provider_class: str = "local"         # local | fixture | (never external in 1C-04)
    budget_class: str = "free"            # free | metered
    retry_policy: dict = field(default_factory=lambda: dict(DEFAULT_RETRY_POLICY))
    timeout_policy: dict = field(default_factory=lambda: dict(DEFAULT_TIMEOUT_POLICY))
    cancellable: bool = True
    idempotent: bool = True
    deterministic_cost: Decimal = Decimal("0.00")
    # estimated/actual cost handling; fake handlers use deterministic costs.


@dataclass
class HandlerResult:
    ok: bool
    output: Optional[dict] = None
    failure_class: Optional[str] = None
    error_code: Optional[str] = None
    error_summary: Optional[str] = None   # redacted, safe to store
    actual_cost: Decimal = Decimal("0.00")
    retryable: bool = False
    output_reference: Optional[str] = None


class UnknownJobType(ValueError):
    pass


# ---------------------------------------------------------------------------
# fake/local handlers (deterministic, zero network)
# ---------------------------------------------------------------------------

def _immediate_success(payload: dict, run_ctx: dict) -> HandlerResult:
    return HandlerResult(ok=True, output={"result": "ok", "value": 1},
                         actual_cost=Decimal("0.00"))


def _slow_success(payload: dict, run_ctx: dict) -> HandlerResult:
    import time
    delay = float(payload.get("delay_seconds", 0.02))
    time.sleep(delay)
    return HandlerResult(ok=True, output={"result": "slow_ok", "value": 2},
                         actual_cost=Decimal("0.00"))


def _transient_failure(payload: dict, run_ctx: dict) -> HandlerResult:
    """Fails with a retryable error until the configured attempt, then succeeds."""
    succeed_on = int(payload.get("succeed_on_attempt", 2))
    attempt = int(run_ctx.get("attempt", 1))
    if attempt < succeed_on:
        return HandlerResult(ok=False, failure_class=TRANSIENT,
                             error_code="transient_failure",
                             error_summary="transient failure simulated",
                             retryable=True, actual_cost=Decimal("0.00"))
    return HandlerResult(ok=True, output={"result": "recovered", "attempt": attempt},
                         actual_cost=Decimal("0.00"))


def _permanent_failure(payload: dict, run_ctx: dict) -> HandlerResult:
    return HandlerResult(ok=False, failure_class=PERMANENT,
                         error_code="permanent_failure",
                         error_summary="permanent failure simulated",
                         retryable=False, actual_cost=Decimal("0.00"))


def _timeout(payload: dict, run_ctx: dict) -> HandlerResult:
    """Simulates a handler that exceeds its timeout budget. With
    ``succeed_on_attempt`` set, later attempts recover (retry-after-timeout)."""
    import time
    time.sleep(float(payload.get("delay_seconds", 0.02)))
    succeed_on = int(payload.get("succeed_on_attempt", 0) or 0)
    attempt = int(run_ctx.get("attempt", 1))
    if succeed_on and attempt >= succeed_on:
        return HandlerResult(ok=True, output={"result": "recovered_after_timeout"},
                             actual_cost=Decimal("0.00"))
    return HandlerResult(ok=False, failure_class=TIMEOUT,
                         error_code="timeout",
                         error_summary="handler exceeded timeout budget",
                         retryable=True, actual_cost=Decimal("0.00"))


def _rate_limit(payload: dict, run_ctx: dict) -> HandlerResult:
    return HandlerResult(ok=False, failure_class=RATE_LIMITED,
                         error_code="rate_limited",
                         error_summary="provider rate limit reached",
                         retryable=True, actual_cost=Decimal("0.00"))


def _malformed_output(payload: dict, run_ctx: dict) -> HandlerResult:
    """Returns output that violates the declared output schema."""
    return HandlerResult(ok=False, failure_class=MALFORMED_OUTPUT,
                         error_code="malformed_output",
                         error_summary="output failed schema validation",
                         retryable=False, output={"unexpected": object()},
                         actual_cost=Decimal("0.00"))


def _cancellable(payload: dict, run_ctx: dict) -> HandlerResult:
    """Cooperative cancellation: checks the cancellation callback between steps."""
    check = run_ctx.get("cancellation_requested")
    if callable(check) and check():
        return HandlerResult(ok=False, failure_class=CANCELLED,
                             error_code="cancelled",
                             error_summary="cooperative cancellation acknowledged",
                             retryable=False, actual_cost=Decimal("0.00"))
    import time
    time.sleep(float(payload.get("delay_seconds", 0.02)))
    if callable(check) and check():
        return HandlerResult(ok=False, failure_class=CANCELLED,
                             error_code="cancelled",
                             error_summary="cooperative cancellation acknowledged",
                             retryable=False, actual_cost=Decimal("0.00"))
    return HandlerResult(ok=True, output={"result": "cancellable_ok"},
                         actual_cost=Decimal("0.00"))


def _cost_variance(payload: dict, run_ctx: dict) -> HandlerResult:
    """Returns an actual cost above the declared estimate (budget variance)."""
    est = Decimal(str(payload.get("estimated_cost", "0.00")))
    variance = Decimal(str(payload.get("variance", "50.00")))
    return HandlerResult(ok=True, output={"result": "variance_ok"},
                         actual_cost=est + variance)


def _needs_approval(payload: dict, run_ctx: dict) -> HandlerResult:
    """Succeeds once approval-gated (submission requires owner approval)."""
    return HandlerResult(ok=True, output={"result": "approved_ok"},
                         actual_cost=Decimal("0.00"))


def _fixture_reader(payload: dict, run_ctx: dict) -> HandlerResult:
    """Simulates a fixture-backed (non-network) provider read."""
    return HandlerResult(ok=True, output={"result": "fixture_ok"},
                         actual_cost=Decimal("0.00"))


def _keyword_import(payload: dict, run_ctx: dict) -> HandlerResult:
    """Job-driven keyword import (1C-05/C05). Requires the importer service."""
    services = run_ctx.get("services") or {}
    importer = services.get("keyword_importer")
    if importer is None:
        return HandlerResult(ok=False, failure_class=UNKNOWN,
                             error_code="importer_unavailable",
                             error_summary="keyword importer not registered",
                             retryable=False)
    try:
        source_file_id = payload.get("source_file_id")
        org_id = payload.get("organization_id") or run_ctx.get("organization_id")
        if not source_file_id or not org_id:
            return HandlerResult(ok=False, failure_class=PERMANENT,
                                 error_code="missing_import_params",
                                 error_summary="source_file_id/organization_id required",
                                 retryable=False)
        result = importer.import_source_file(
            org_id, source_file_id,
            submitted_by=payload.get("submitted_by"), via_job=True)
        return HandlerResult(ok=True, output={"batch_id": result["id"],
                                              "summary": result["summary"]},
                             actual_cost=Decimal("0.00"))
    except Exception as e:  # noqa: BLE001 - classify import failure
        return HandlerResult(ok=False, failure_class=PERMANENT,
                             error_code="import_failed",
                             error_summary=f"import failed: {type(e).__name__}",
                             retryable=False)


def is_retryable(failure_class: Optional[str]) -> bool:
    return failure_class in RETRYABLE_CLASSES


def is_permanent(failure_class: Optional[str]) -> bool:
    return failure_class in PERMANENT_CLASSES


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

HandlerFn = Callable[[dict, dict], HandlerResult]


class HandlerRegistry:
    """Maps job_type -> (spec, handler). Unregistered job types fail closed."""

    def __init__(self) -> None:
        self._specs: dict[str, JobHandlerSpec] = {}
        self._handlers: dict[str, HandlerFn] = {}

    def register(self, spec: JobHandlerSpec, handler: HandlerFn) -> None:
        self._specs[spec.job_type] = spec
        self._handlers[spec.job_type] = handler

    def has(self, job_type: str) -> bool:
        return job_type in self._specs

    def spec(self, job_type: str) -> JobHandlerSpec:
        if job_type not in self._specs:
            raise UnknownJobType(f"unregistered job type {job_type!r}")
        return self._specs[job_type]

    def handler(self, job_type: str) -> HandlerFn:
        if job_type not in self._handlers:
            raise UnknownJobType(f"unregistered job type {job_type!r}")
        return self._handlers[job_type]

    def job_types(self) -> list[str]:
        return sorted(self._specs)

    def metadata(self) -> list[dict]:
        from dataclasses import asdict
        return [asdict(s) for s in self._specs.values()]


def build_default_registry() -> HandlerRegistry:
    """The registry bound by the durable job service (fake/local handlers only)."""
    reg = HandlerRegistry()
    specs = [
        JobHandlerSpec("immediate_success", "1.0", "1.0",
                       deterministic_cost=Decimal("0.00")),
        JobHandlerSpec("slow_success", "1.0", "1.0",
                       timeout_policy={"timeout_seconds": 10}),
        JobHandlerSpec("transient_failure", "1.0", "1.0",
                       retry_policy={"max_attempts": 3, "backoff_base_seconds": 0,
                                     "backoff_multiplier": 1,
                                     "max_backoff_seconds": 1, "jitter_seconds": 0}),
        JobHandlerSpec("permanent_failure", "1.0", "1.0",
                       retry_policy={"max_attempts": 1, "backoff_base_seconds": 0,
                                     "backoff_multiplier": 1,
                                     "max_backoff_seconds": 1, "jitter_seconds": 0}),
        JobHandlerSpec("timeout", "1.0", "1.0",
                       retry_policy={"max_attempts": 2, "backoff_base_seconds": 0,
                                     "backoff_multiplier": 1,
                                     "max_backoff_seconds": 1, "jitter_seconds": 0}),
        JobHandlerSpec("rate_limit", "1.0", "1.0",
                       retry_policy={"max_attempts": 3, "backoff_base_seconds": 0,
                                     "backoff_multiplier": 1,
                                     "max_backoff_seconds": 1, "jitter_seconds": 0}),
        JobHandlerSpec("malformed_output", "1.0", "1.0",
                       retry_policy={"max_attempts": 1, "backoff_base_seconds": 0,
                                     "backoff_multiplier": 1,
                                     "max_backoff_seconds": 1, "jitter_seconds": 0}),
        JobHandlerSpec("cancellable", "1.0", "1.0",
                       timeout_policy={"timeout_seconds": 10}),
        JobHandlerSpec("cost_variance", "1.0", "1.0",
                       budget_class="metered",
                       retry_policy={"max_attempts": 1, "backoff_base_seconds": 0,
                                     "backoff_multiplier": 1,
                                     "max_backoff_seconds": 1, "jitter_seconds": 0}),
        JobHandlerSpec("needs_approval", "1.0", "1.0",
                       approval_class="owner",
                       retry_policy={"max_attempts": 1, "backoff_base_seconds": 0,
                                     "backoff_multiplier": 1,
                                     "max_backoff_seconds": 1, "jitter_seconds": 0}),
        JobHandlerSpec("fixture_reader", "1.0", "1.0",
                       provider_class="fixture",
                       retry_policy={"max_attempts": 1, "backoff_base_seconds": 0,
                                     "backoff_multiplier": 1,
                                     "max_backoff_seconds": 1, "jitter_seconds": 0}),
        JobHandlerSpec("keyword_import", "1.0", "1.0",
                       required_permission=PERM_RUN_LOCAL,
                       retry_policy={"max_attempts": 1, "backoff_base_seconds": 0,
                                     "backoff_multiplier": 1,
                                     "max_backoff_seconds": 1, "jitter_seconds": 0}),
    ]
    handlers: list[HandlerFn] = [
        _immediate_success, _slow_success, _transient_failure, _permanent_failure,
        _timeout, _rate_limit, _malformed_output, _cancellable, _cost_variance,
        _needs_approval, _fixture_reader, _keyword_import,
    ]
    for spec, handler in zip(specs, handlers):
        reg.register(spec, handler)
    return reg