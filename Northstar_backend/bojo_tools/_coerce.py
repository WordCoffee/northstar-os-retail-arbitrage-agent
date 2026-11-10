"""Numeric coercion shared by the domain tools.

Model arguments arrive as JSON, so a number is as often the string ``"19.99"``
as it is the float ``19.99``. This is type plumbing, not business logic: no
defaults are invented and a value that is not a number becomes ``None`` (the
callers treat ``None`` as UNKNOWN and refuse, they never substitute a zero).
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any, Optional


def num(value: Any) -> Optional[float]:
    """A finite float, or None when the value is not a number."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        try:
            return float(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def whole(value: Any) -> Optional[int]:
    """An int from a number or numeric string, or None."""
    number = num(value)
    if number is None:
        return None
    return int(number)


def text(value: Any) -> str:
    """A stripped string; None and blanks become ``""``."""
    if value is None:
        return ""
    return str(value).strip()


def jsonable(value: Any) -> Any:
    """A JSON-safe copy of a production payload.

    The canonical modules return ``Decimal`` money/rates; a tool result must be
    JSON-serialisable for the model and the API. Decimals become their exact
    decimal string (never a lossy float), everything else is untouched.
    """
    return json.loads(json.dumps(value, default=str))


__all__ = ["num", "whole", "text", "jsonable"]
