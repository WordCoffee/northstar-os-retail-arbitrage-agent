"""NorthstarOS policy kernel (Phase 2) — deterministic, fail-closed, audited.

The kernel is the ONLY decision point for outbound fetch authorization in the
Secure Control-Layer build. It is pure code: no network, no runtime mutation
API, no LLM. Every decision is recorded in a hash-chained audit log.
"""
from .allowlist import DEFAULT_ALLOWLIST, assert_not_amazon, check_source, domain_allowed
from .approvals import KINDS, SIMULATED, ApprovalItem, ApprovalQueue, assert_snapshot_writable
from .audit import GENESIS_HASH, AuditEntry, AuditLog, JsonlSink
from .errors import PolicyConfigError, PolicyDenied
from .grants import GrantSet, fetch_capability
from .kernel import (
    DEFAULT_MAX_REDIRECTS,
    DEFAULT_MAX_RESPONSE_BYTES,
    Decision,
    PolicyKernel,
)
from .limits import RateLimiter, RunBudget, check_response_size
from .robots import DEFAULT_AGENT, RobotsGate
from .ssrf import ResolvedTarget, blocked_reason, is_ip_literal, resolve_and_pin
from .urls import ALLOWED_SCHEMES, is_amazon_host, normalize_host, parse_http_url

__all__ = [
    "ALLOWED_SCHEMES",
    "ApprovalItem",
    "ApprovalQueue",
    "AuditEntry",
    "AuditLog",
    "DEFAULT_AGENT",
    "DEFAULT_ALLOWLIST",
    "DEFAULT_MAX_REDIRECTS",
    "DEFAULT_MAX_RESPONSE_BYTES",
    "Decision",
    "GENESIS_HASH",
    "GrantSet",
    "JsonlSink",
    "KINDS",
    "PolicyConfigError",
    "PolicyDenied",
    "PolicyKernel",
    "RateLimiter",
    "ResolvedTarget",
    "RobotsGate",
    "RunBudget",
    "SIMULATED",
    "assert_not_amazon",
    "assert_snapshot_writable",
    "blocked_reason",
    "check_response_size",
    "check_source",
    "domain_allowed",
    "fetch_capability",
    "is_amazon_host",
    "is_ip_literal",
    "normalize_host",
    "parse_http_url",
    "resolve_and_pin",
]
