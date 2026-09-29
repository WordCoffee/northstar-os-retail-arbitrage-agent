"""Owner Test Mode (Master Plan P3-T1).

A flag-gated, audited operator mode. Off by default and requires the owner role.
When the flag is off this module returns False everywhere, so behavior is
unchanged (tested).

Scope (P3-T1/P3-T2): active only for principals whose effective role is
``internal_platform_admin`` and only in explicitly non-production environments
(``ALLOWED_ENVIRONMENTS``); production, production_tenant, staging, and
unknown/missing values fail closed.
"""
from __future__ import annotations

import os
from typing import Optional

from .enums import Role

TRUTHY = {"1", "true", "yes", "on"}
# Fail closed: Owner Test Mode activates ONLY in explicitly identified
# non-production environments. production, production_tenant, staging, unknown,
# missing, or invalid values all return False (no bypass).
ALLOWED_ENVIRONMENTS = frozenset({"development", "test"})
BANNER_TEXT = "OWNER TEST MODE — bypasses are audited."


def _truthy(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in TRUTHY


def flag_enabled() -> bool:
    """NORTHSTAR_OWNER_TEST_MODE=1 activates the mode (default off)."""
    return _truthy("NORTHSTAR_OWNER_TEST_MODE")


def self_approval_enabled() -> bool:
    """Owner self-approval stays DISABLED until the owner adopts the P0-T3
    Constitution amendment (default 0/off)."""
    return _truthy("NORTHSTAR_OWNER_SELF_APPROVAL")


def raw_environment() -> Optional[str]:
    """The raw process ENVIRONMENT value (None when unset). Unlike
    ``authn.environment()`` this does NOT default to development, so a missing
    environment fails closed for Owner Test Mode."""
    return os.environ.get("ENVIRONMENT")


def is_owner_test_mode(*, role: Optional[str], environment: Optional[str]) -> bool:
    if not flag_enabled():
        return False
    env = (environment or "").strip().lower()
    if env not in ALLOWED_ENVIRONMENTS:
        return False
    return role == Role.INTERNAL_PLATFORM_ADMIN.value


def banner() -> str:
    return BANNER_TEXT