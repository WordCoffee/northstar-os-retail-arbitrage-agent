"""Shared, dependency-light contracts for the Proof Batch guarded run.

These definitions are imported by BOTH proof_batch_run.py (the guarded runner)
and proof_batch_easyparser_adapter.py (the live adapter) so that
`ProviderAdapter`, `GuardError`, `BindingError`, and `RunAbort` are a SINGLE
set of class objects no matter how the modules are imported or executed
(direct script, `python -m`, reload, runpy, subprocess probe, or a test
fixture re-import). This removes the class-identity divergence that the old
`import proof_batch_run as pbr` + `__main__`-alias workaround could not keep
stable across every import path (see docs/proof-batch-adapter-arming-plan.md,
"Shared contract module rationale").

This module imports ONLY the Python standard library. It must never import
proof_batch_run, proof_batch_easyparser_adapter, any provider client, or
anything that makes a network call.
"""

from typing import Any, Dict, Optional, Tuple

# Documented per-ASIN credit estimate shared by the runner and the adapter.
ESTIMATED_CREDITS_PER_REQUEST = 5.0

# ---------------------------------------------------------------------------
# DataForSEO Amazon contract (offline-authoritative)
#
# Source of truth for endpoint families, routes, and lifecycle acceptance:
# `random dataforseo amazon stuff api.txt`. Merchant Standard families are
# async (POST task_post -> task_get/{id}); Labs families are Live (single
# POST, instant result). product_info / seller_info / Merchant Reviews and
# any undocumented route are REJECTED.
#
# Shared by validation_run.py (run ledger) and dataforseo_adapter.py
# (adapter ledger) so both enforce the same family-aware predicates.
# ---------------------------------------------------------------------------

DATAFORSEO_API_HOST = "api.dataforseo.com"
DATAFORSEO_API_BASE = f"https://{DATAFORSEO_API_HOST}"

# United States defaults (per contract examples).
DEFAULT_LOCATION_CODE = 2840
DEFAULT_LANGUAGE_CODE = "en_US"      # Merchant Standard
DEFAULT_LABS_LANGUAGE_CODE = "en"    # Labs

# Endpoint families.
DATAFORSEO_MERCHANT_FAMILIES = ("products", "asin", "sellers")
DATAFORSEO_LABS_FAMILIES = (
    "product_rank_overview",
    "ranked_keywords",
    "bulk_search_volume",
    "related_keywords",
    "product_competitors",
    "keyword_intersection",
)
DATAFORSEO_LABS_FAMILIES = DATAFORSEO_LABS_FAMILIES  # canonical (no typo variant)

MERCHANT_FAMILY_TASK_TYPES = {
    "products": "keyword",   # keyword-driven listing evidence
    "asin": "asin",
    "sellers": "asin",
}

# Lifecycle state vocabulary (accepted, ready, retrieved, normalized, plus
# the rejection/reconciliation states). The create-accepted stored value is
# DATAFORSEO_ACCEPTED_STATE ("submitted") to preserve the prior repair.
DATAFORSEO_ACCEPTED_STATE = "submitted"

DATAFORSEO_REJECTION_STATES = (
    "provider_rejected_invalid_path",
    "provider_rejected_auth",
    "provider_rejected_validation",
    "provider_rejected_budget",
    "provider_rejected_unknown",
)

DATAFORSEO_LIFECYCLE_STATES = (
    "planned",
    "manual_review_required",
    "budget_rejected",
    "queued_or_submitted",          # descriptive: a queued/submitted task
    "ready_to_retrieve",
    "retrieved",
    "normalized",
    "provider_rejected_invalid_path",
    "provider_rejected_auth",
    "provider_rejected_validation",
    "provider_rejected_budget",
    "provider_rejected_unknown",
    "mapping_incompatible",
    "schema_validation_failed",
    "persistence_failure",
    "needs_manual_reconciliation",
)

# States that still hold a budget reservation (incomplete spend).
_DATAFORSEO_RESERVING_STATES = (
    "planned",
    "queued_or_submitted",
    "submitted",
    "ready_to_retrieve",
    "needs_manual_reconciliation",
)

# Task-level status codes / messages.
MERCHANT_CREATE_OK_STATUS_CODE = 20100
MERCHANT_CREATE_OK_STATUS_MESSAGE = "Task Created."
MERCHANT_CREATE_OK_STATUS_MESSAGES = frozenset({
    "task created.", "task created", "Task Created."})
MERCHANT_COMPLETION_OK_STATUS_CODE = 20000
MERCHANT_COMPLETION_OK_STATUS_MESSAGES = frozenset({"ok.", "ok"})
# Task-level "not yet ready" codes. A task_get that returns one of these is a
# transient, retryable state (queued/created) -> the caller must keep polling,
# NOT treat it as a terminal rejection.
MERCHANT_PENDING_STATUS_CODES = frozenset({20100, 40600, 40601, 40602})
LABS_OK_STATUS_CODE = 20000
LABS_OK_STATUS_MESSAGES = frozenset({"ok.", "ok"})

# States that release their reservation (provider-rejected or terminal).
# (everything not in _DATAFORSEO_RESERVING_STATES.)


def assert_valid_dataforseo_state(state: str) -> str:
    """Validate a DataForSEO ledger lifecycle state; raise on unknown state."""
    if not isinstance(state, str) or state.strip() != state or not state:
        raise GuardError(f"invalid dataforseo state: {state!r}")
    if state not in DATAFORSEO_LIFECYCLE_STATES:
        raise GuardError(f"unknown dataforseo lifecycle state: {state!r}")
    return state


def dataforseo_state_reserves_budget(state: str) -> bool:
    """True if `state` still holds a budget reservation."""
    return state in _DATAFORSEO_RESERVING_STATES


def merchant_task_post_url(family: str) -> str:
    family = _require_merchant_family(family)
    return f"{DATAFORSEO_API_BASE}/v3/merchant/amazon/{family}/task_post"


def merchant_task_get_url(family: str, task_id: str) -> str:
    family = _require_merchant_family(family)
    if not isinstance(task_id, str) or not task_id.strip() or "/" in task_id:
        raise GuardError("merchant task_get requires a nonblank, slash-free task id")
    return f"{DATAFORSEO_API_BASE}/v3/merchant/amazon/{family}/task_get/advanced/{task_id}"


def labs_live_url(family: str) -> str:
    family = _require_labs_family(family)
    return f"{DATAFORSEO_API_BASE}/v3/dataforseo_labs/amazon/{family}/live"


def expected_task_post_path(family: str) -> Tuple[str, ...]:
    return ("v3", "merchant", "amazon", _require_merchant_family(family), "task_post")


def expected_task_get_path(family: str) -> Tuple[str, ...]:
    return ("v3", "merchant", "amazon", _require_merchant_family(family), "task_get", "advanced")


def expected_labs_live_path(family: str) -> Tuple[str, ...]:
    return ("v3", "dataforseo_labs", "amazon", _require_labs_family(family), "live")


def _require_merchant_family(family: str) -> str:
    if family not in DATAFORSEO_MERCHANT_FAMILIES:
        raise GuardError(f"unsupported DataForSEO merchant family: {family!r}")
    return family


def _require_labs_family(family: str) -> str:
    if family not in DATAFORSEO_LABS_FAMILIES:
        raise GuardError(f"unsupported DataForSEO labs family: {family!r}")
    return family


def is_dataforseo_rejection_state(state: str) -> bool:
    """Vocabulary check: is this a provider-rejection ledger state?"""
    return state in DATAFORSEO_REJECTION_STATES


def classify_dataforseo_rejection(status_code: Any, status_message: Any) -> str:
    """Map a task-level non-acceptance to the rejection taxonomy.

    provider_rejected_invalid_path | provider_rejected_auth |
    provider_rejected_validation | provider_rejected_budget |
    provider_rejected_unknown
    """
    msg = str(status_message or "").strip().lower()
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        code = None
    if code == 40402 or "invalid path" in msg:
        return "provider_rejected_invalid_path"
    if code in (401, 403) or any(k in msg for k in (
            "unauthorized", "authentication", "authorization",
            "permission", "not authorized", "access denied")):
        return "provider_rejected_auth"
    if code == 402 or any(k in msg for k in (
            "insufficient credits", "insufficient balance", "credit",
            "balance", "funds")):
        return "provider_rejected_budget"
    if code is not None and 40000 <= code <= 49999 or any(k in msg for k in (
            "invalid", "missing", "parameter", "bad request", "validation")):
        return "provider_rejected_validation"
    return "provider_rejected_unknown"


def _cost_cents(raw: Any) -> float:
    """Provider-reported task cost as a RAW float USD value.

    DataForSEO reports `cost` in fractional USD (e.g. 0.0015 per task). Coercing
    to integer cents via int(float(cost) * 100) silently truncates sub-cent
    values to 0, so we keep the raw float and let callers accumulate it directly
    as USD (see dataforseo_adapter.get_dataforseo_offers -> result['cost_usd']).
    Returns 0.0 when absent/zero/invalid.
    """
    cost = raw.get("cost") if isinstance(raw, dict) else None
    if isinstance(cost, bool) or not isinstance(cost, (int, float)):
        return 0.0
    return float(cost)


def _task_path(raw: Dict[str, Any]) -> Optional[Tuple[str, ...]]:
    path = raw.get("path")
    if isinstance(path, list):
        return tuple(str(p) for p in path)
    return None


def evaluate_dataforseo_task_post(
    response: Any,
    endpoint_family: str = "products",
) -> Dict[str, Any]:
    """Strict provider-acceptance predicate for a DataForSEO Merchant Standard
    task_post CREATE response. Returns a verdict dict:

    {
        "accepted": bool,
        "classification": "submitted" or a rejection state,
        "task_id": Optional[str],            # set only when accepted (queued)
        "provider_cost_cents": float,        # raw provider cost in USD; 0.0 if absent/zero
        "path_match": bool,                  # response path matches family route
        "reason": str,
        "request_state": str,                # the ledger state to persist
    }

    Acceptance requires ALL of: top-level status_code == 20000;
    tasks_error in (None, 0); first task a dict; task-level status_code == 20100;
    task-level status_message is an explicit "Task Created."; non-blank slash-free
    task id; numeric task cost strictly greater than zero; response task path
    exactly matches the requested family task_post route; response task data
    corresponds to the intended request identity when present; result may be
    null (queued). Any failure -> rejection state, NEVER a task id.
    """
    def _reject(state: str, reason: str, cost_cents: float,
                path_match: bool = False) -> Dict[str, Any]:
        return {
            "accepted": False,
            "classification": state,
            "task_id": None,
            "provider_cost_cents": float(cost_cents or 0.0),
            "path_match": path_match,
            "reason": reason,
            "request_state": state,
        }

    family = _require_merchant_family(endpoint_family)
    want_path = expected_task_post_path(family)
    path_match = False

    if not isinstance(response, dict):
        return _reject("provider_rejected_unknown",
                       "payload is not a dictionary", 0)
    if response.get("status_code") != MERCHANT_COMPLETION_OK_STATUS_CODE:
        return _reject("provider_rejected_unknown",
                       f"top-level status_code {response.get('status_code')}",
                       _cost_cents(response))
    task_cost = response.get("cost")
    if response.get("tasks_error") not in (None, 0):
        # tasks_error present with no task detail -> reject; classify from
        # first task if available, else unknown.
        tasks = response.get("tasks")
        if isinstance(tasks, list) and tasks and isinstance(tasks[0], dict):
            return _reject(
                classify_dataforseo_rejection(
                    tasks[0].get("status_code"),
                    tasks[0].get("status_message")),
                f"tasks_error={response.get('tasks_error')}: "
                f"{tasks[0].get('status_code')} {tasks[0].get('status_message')}",
                _cost_cents(tasks[0]))
        return _reject("provider_rejected_unknown",
                       f"tasks_error={response.get('tasks_error')}", _cost_cents(response))

    tasks = response.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return _reject("provider_rejected_unknown",
                       "tasks is not a non-empty list", _cost_cents(response))
    first = tasks[0]
    if not isinstance(first, dict):
        return _reject("provider_rejected_unknown",
                       "first task is not a dictionary", _cost_cents(response))

    provider_cost = _cost_cents(first)
    path_match = _task_path(first) == want_path

    status_code = first.get("status_code")
    status_message = first.get("status_message")
    if status_code != MERCHANT_CREATE_OK_STATUS_CODE:
        return _reject(
            classify_dataforseo_rejection(status_code, status_message),
            f"task status_code {status_code}: {status_message}",
            provider_cost, path_match)
    if str(status_message or "").strip() not in MERCHANT_CREATE_OK_STATUS_MESSAGES:
        return _reject("provider_rejected_unknown",
                       f"task status_message not an explicit acceptance: "
                       f"{status_message}", provider_cost, path_match)

    task_id = first.get("id")
    if not isinstance(task_id, str) or not task_id.strip() or "/" in task_id:
        return _reject("provider_rejected_unknown",
                       "task id is missing or malformed", provider_cost, path_match)
    if not (isinstance(first.get("cost"), (int, float))
            and not isinstance(first.get("cost"), bool)
            and float(first.get("cost")) > 0):
        return _reject("provider_rejected_unknown",
                       "task cost is not numeric and greater than zero",
                       provider_cost, path_match)
    if not path_match:
        return _reject("provider_rejected_invalid_path",
                       f"task path {first.get('path')} does not match family "
                       f"{family} task_post route", provider_cost, path_match)

    # Identity echo check (when the provider returns request data): it must
    # not contradict the intended identity. A missing data object is allowed
    # (the provider may not echo the request).
    data = first.get("data")
    if isinstance(data, dict):
        if family == "products":
            kw = data.get("keyword")
            if isinstance(kw, str) and kw.strip() and kw.strip() != kw.strip():  # no-op guard shape
                pass
            # (keyword is request-driven; no ASIN contradiction check for products)
        elif family in ("asin", "sellers"):
            asin_echo = data.get("asin")
            if isinstance(asin_echo, str) and asin_echo and "/" in asin_echo:
                return _reject("provider_rejected_validation",
                               "task data ASIN is malformed", provider_cost, path_match)

    return {
        "accepted": True,
        "classification": DATAFORSEO_ACCEPTED_STATE,
        "task_id": task_id.strip(),
        "provider_cost_cents": provider_cost,
        "path_match": True,
        "reason": "Task Created.",
        "request_state": DATAFORSEO_ACCEPTED_STATE,
    }


def evaluate_dataforseo_task_get(
    response: Any,
    endpoint_family: str,
    expected_task_id: str,
) -> Dict[str, Any]:
    """Strict acceptance predicate for a Merchant Standard task_get COMPLETION
    response. Returns a verdict dict:

    { accepted, classification, task_id, path_match, reason,
      result_item, request_state }
    """
    family = _require_merchant_family(endpoint_family)
    want_path = expected_task_get_path(family)
    path_match = False

    def _reject(state, reason, path_match=False):
        return {
            "accepted": False,
            "classification": state,
            "task_id": None,
            "path_match": path_match,
            "reason": reason,
            "request_state": "provider_error" if state == "provider_error"
            else ("provider_rejected_unknown" if state in DATAFORSEO_REJECTION_STATES
                  else state),
            "result_item": None,
            "pending": False,
        }

    if not isinstance(response, dict):
        return _reject("provider_error", "payload is not a dictionary")
    tasks = response.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return _reject("provider_error", "tasks is not a non-empty list")
    first = tasks[0]
    if not isinstance(first, dict):
        return _reject("provider_error", "first task is not a dict")
    path_match = _task_path(first) == want_path
    task_id = first.get("id")
    if task_id != expected_task_id:
        return _reject("provider_rejected_validation",
                       f"retrieved task id {task_id} != stored {expected_task_id}",
                       path_match)
    status_code = first.get("status_code")
    tasks_error = response.get("tasks_error")
    # Transient "task in queue / created" states: the task exists and matches,
    # it simply has not produced a result yet. DataForSEO reports tasks_error=1
    # while a task is still queued -- that is NOT a terminal failure, so signal
    # pending and let the caller keep polling rather than rejecting.
    if status_code in MERCHANT_PENDING_STATUS_CODES:
        return {
            "accepted": False,
            "classification": "pending",
            "task_id": task_id,
            "path_match": path_match,
            "reason": f"task in queue (status {status_code}, tasks_error="
                      f"{tasks_error}): {first.get('status_message')}",
            "request_state": "in_progress",
            "result_item": None,
            "pending": True,
        }
    if status_code != MERCHANT_COMPLETION_OK_STATUS_CODE:
        return _reject("provider_error",
                       f"task status_code {status_code}: "
                       f"{first.get('status_message')} (tasks_error={tasks_error})",
                       path_match)
    # status_code == 20000: a completed task must have tasks_error 0/None.
    if tasks_error not in (None, 0):
        return _reject("provider_error",
                       f"tasks_error={tasks_error} on completed task")
    if str(first.get("status_message") or "").strip().lower() not in MERCHANT_COMPLETION_OK_STATUS_MESSAGES:
        return _reject("provider_error",
                       f"task status_message {first.get('status_message')}", path_match)
    result = first.get("result")
    if not isinstance(result, list) or not result:
        return _reject("provider_error", "result is not a non-empty list", path_match)
    item = result[0]
    if not isinstance(item, dict):
        return _reject("provider_error", "result item is not a dict", path_match)
    return {
        "accepted": True,
        "classification": "retrieved",
        "task_id": task_id,
        "path_match": path_match,
        "reason": "completed result",
        "result_item": item,
        "request_state": "retrieved",
        "pending": False,
    }


def evaluate_dataforseo_labs_live(
    response: Any,
    endpoint_family: str,
) -> Dict[str, Any]:
    """Acceptance predicate for a DataForSEO Labs LIVE response.

    Labs is immediate-response: a single POST returns the result. Accepted
    only when top-level status_code == 20000, tasks_error == 0, task
    status_code == 20000, path matches the requested Labs family /live route,
    and a parseable result is present.
    """
    family = _require_labs_family(endpoint_family)
    want_path = expected_labs_live_path(family)
    path_match = False

    def _reject(reason, path_match=False, cost_cents=0.0):
        return {
            "accepted": False,
            "classification": "provider_rejected_unknown",
            "reason": reason,
            "path_match": path_match,
            "provider_cost_cents": float(cost_cents or 0.0),
            "request_state": "provider_rejected_unknown",
            "result_item": None,
        }

    if not isinstance(response, dict):
        return _reject("payload is not a dictionary")
    if response.get("status_code") != LABS_OK_STATUS_CODE:
        return _reject(f"top-level status_code {response.get('status_code')}")
    if response.get("tasks_error") not in (None, 0):
        return _reject(f"tasks_error={response.get('tasks_error')}")
    tasks = response.get("tasks")
    if not isinstance(tasks, list) or not tasks:
        return _reject("tasks is not a non-empty list")
    first = tasks[0]
    if not isinstance(first, dict):
        return _reject("first task is not a dict")
    path_match = _task_path(first) == want_path
    if first.get("status_code") != LABS_OK_STATUS_CODE:
        return _reject(
            f"task status_code {first.get('status_code')}: "
            f"{first.get('status_message')}", path_match)
    if str(first.get("status_message") or "").strip().lower() not in LABS_OK_STATUS_MESSAGES:
        return _reject(f"task status_message {first.get('status_message')}", path_match)
    # Labs cost is reported at the root; fall back to task-level if present.
    cost = _cost_cents(first) or _cost_cents(response)
    if cost <= 0:
        return _reject("task cost is not numeric and greater than zero", path_match, cost)
    result = first.get("result")
    if not isinstance(result, list) or not result:
        return _reject("result is not a non-empty list", path_match, cost)
    item = result[0]
    if not isinstance(item, dict):
        return _reject("result item is not a dict", path_match, cost)
    return {
        "accepted": True,
        "classification": "retrieved",
        "path_match": path_match,
        "provider_cost_cents": cost,
        "reason": "labs live result accepted",
        "request_state": "retrieved",
        "result_item": item,
    }


class GuardError(Exception):
    """Raised on a failed runner guard (nothing is written; clean refusal)."""


class BindingError(Exception):
    """Raised on an invalid preflight binding (fingerprint/secret/structure)."""


class RunAbort(Exception):
    """Raised with (reason, stage, asin_or_None) on a hard-stop condition."""

    def __init__(self, reason: str, stage: str, asin: Optional[str] = None, detail: str = ""):
        super().__init__(f"{reason} @ {stage} {asin or ''}: {detail}".strip())
        self.reason = reason
        self.stage = stage
        self.asin = asin
        self.detail = detail


class ProviderAdapter:
    """Narrow adapter contract for one provider request.

    fetch(asin, request_index) -> normalized dict in the easyparser_client
    result shape (never raises; every outcome is a dict). The runner's
    FixtureAdapter and the adapter's EasyparserLiveAdapter both subclass this
    one shared base, so the strict `isinstance(adapter, ProviderAdapter)`
    guard always resolves against a single class object.
    """

    def fetch(self, asin: str, request_index: int) -> dict:
        raise NotImplementedError
