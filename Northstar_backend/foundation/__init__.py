"""Northstar OS Foundation — shared P0 domain layer.

Additive, dependency-light (stdlib + pydantic). No external provider execution,
no production migration application. Safe to import without side effects.
"""

__all__ = [
    "enums",
    "models",
    "db",
    "repositories",
    "provenance",
    "context",
    "permissions",
    "identity",
    "providers",
    "jobs",
    "usage",
    "audit",
    "approvals",
    "observability",
]

FOUNDATION_SCHEMA_VERSION = "foundation-1"