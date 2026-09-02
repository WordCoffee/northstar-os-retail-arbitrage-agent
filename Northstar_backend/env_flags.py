"""Centralized strict boolean environment-flag parsing.

Only 1, true, yes, and on (case-insensitive) enable a feature flag.
Unset, empty, 0, false, no, off, OFF, and arbitrary strings disable it.
Never use ``if os.getenv("FLAG"):`` truthiness for a behavior-changing
feature flag: a non-empty arbitrary string would silently enable it.
"""

import os
from typing import Optional

_TRUE_VALUES = frozenset({"1", "true", "yes", "on"})


def env_flag(name: str, default: bool = False) -> bool:
    """Parse an environment variable as a strict boolean flag.

    Enabled only for 1/true/yes/on (case-insensitive, trimmed). Anything
    else — unset, empty, 0, false, no, off, arbitrary strings — returns
    ``default`` (itself False by default, so flags default to disabled).
    """
    raw = (os.getenv(name) or "").strip().lower()
    if not raw:
        return bool(default)
    return raw in _TRUE_VALUES