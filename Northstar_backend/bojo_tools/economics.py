"""Economics tools for Bojo — the Profitability margin report.

``margin_report`` wraps the canonical engine in ``foundation.economics``: the
same ``compute(EconomicsInput(...))`` behind ``POST /api/v1/economics/compute``
in ``foundation/api/router.py``. That engine is the ONLY authoritative
calculator in this codebase — Decimal-based, versioned, and honest about
UNKNOWN inputs (a missing number stays ``None``; it is never zero-filled). This
tool does not add a fee model, a formula or a rounding rule.

The route filters the caller's mapping down to the fields ``EconomicsInput``
declares; this tool does the same and reports which keys it dropped, so an
operator is never silently ignored. A small, explicit set of operator shorthands
(``price``, ``cost``, ``cogs``, ``referral_fee``, ``fba_fee``, ``shipping``,
``qty`` …) is renamed onto the engine's own input first — see ``INPUT_ALIASES``
and ``ty/service_registry.json -> profitability.input_aliases``. A rename never
rescales or invents a value.

Contract::

    {"ok": True,  "tool": "<name>", "data": {...}}
    {"ok": False, "tool": "<name>", "reason": "<reason string>"}

Business failures — no selling price, no acquisition cost, or a result that
cannot be completed from the numbers supplied — return ``ok=False``.
Programmer errors in the argument contract raise ``TypeError``.
"""

from __future__ import annotations

import os
import sys
from dataclasses import fields as dataclass_fields
from functools import lru_cache
from typing import Any, Dict, Mapping, Optional

from ._coerce import num

TOOL_MARGIN_REPORT = "margin_report"

#: Without these two numbers a margin is not computable at all.
REQUIRED = ("selling_price", "acquisition_cost")

#: Operator shorthand -> the engine's own input name. A rename, never a rescale and never an
#: invented value: ``referral_fee`` is an amount (``referral_fee_amount``), while a percentage
#: belongs in ``referral_pct``/``referral_rate``. The mapping is reported per call in
#: ``aliased_inputs``, and a canonical key always wins over its alias.
INPUT_ALIASES: Dict[str, str] = {
    "price": "selling_price",
    "selling": "selling_price",
    "cost": "acquisition_cost",
    "unit_cost": "acquisition_cost",
    "cogs": "acquisition_cost",
    "acquisition": "acquisition_cost",
    "referral_fee": "referral_fee_amount",
    "referral_pct": "referral_fee_rate",
    "referral_rate": "referral_fee_rate",
    "fba_fee": "fba_fulfillment_fee",
    "fulfillment_fee": "fba_fulfillment_fee",
    "shipping": "inbound_freight",
    "freight": "inbound_freight",
    "prep": "prep_cost",
    "ads": "advertising_cost",
    "ad_cost": "advertising_cost",
    "advertising": "advertising_cost",
    "qty": "quantity",
}


def _backend_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _ensure_backend_on_path() -> None:
    root = _backend_root()
    if root not in sys.path:
        sys.path.insert(0, root)


@lru_cache(maxsize=1)
def _default_economics() -> Any:
    """The real canonical engine (pure, Decimal-based, offline)."""
    _ensure_backend_on_path()
    from foundation import economics

    return economics


def _bad(reason: str) -> Dict[str, Any]:
    return {"ok": False, "tool": TOOL_MARGIN_REPORT, "reason": reason}


def margin_report(
    inputs: Mapping[str, Any],
    compute: Optional[Any] = None,
) -> Dict[str, Any]:
    """Run the canonical fee/economics engine over the numbers entered.

    ``inputs`` mirrors ``EconomicsInput``: ``selling_price``,
    ``acquisition_cost``, ``referral_fee_rate`` or ``referral_fee_amount``,
    ``fba_fulfillment_fee``, ``inbound_freight``, ``prep_cost``,
    ``advertising_cost``, ``quantity``, ``provenance`` and so on. Anything the
    dataclass does not declare is dropped and named in ``ignored_inputs``.

    ``compute`` is an injection seam: a callable taking the built input
    dataclass and returning an output with ``to_dict()``. It defaults to the
    real ``foundation.economics.compute``.
    """
    if not isinstance(inputs, Mapping):
        raise TypeError("inputs must be a mapping of economics fields")

    spec = _default_economics()
    allowed = {f.name for f in dataclass_fields(spec.EconomicsInput)}
    data: Dict[str, Any] = {}
    ignored: list = []
    for key, value in inputs.items():
        name = str(key)
        if name not in allowed:
            ignored.append(name)
            continue
        data[name] = value

    # Shorthand is renamed onto the engine's own input. Canonical keys are read first, so an
    # alias can never overwrite a number the operator supplied under its real name; an alias
    # whose target is already present stays in `ignored_inputs` and says so.
    aliased: list = []
    for key, value in inputs.items():
        name = str(key)
        target = INPUT_ALIASES.get(name)
        if target is None or target not in allowed or target in data:
            continue
        data[target] = value
        aliased.append({"from": name, "to": target})
        if name in ignored:
            ignored.remove(name)

    for name in REQUIRED:
        if name not in data or data[name] is None:
            return _bad("%s is required to report a margin" % name)
        if num(data[name]) is None:
            raise TypeError("%s must be a number" % name)

    if data.get("quantity") is not None:
        quantity = data["quantity"]
        if isinstance(quantity, bool) or not isinstance(quantity, int):
            if not (isinstance(quantity, str) and quantity.strip().isdigit()):
                raise TypeError("quantity must be an integer")
            data["quantity"] = int(quantity.strip())

    try:
        built = spec.EconomicsInput(**data)
    except TypeError as exc:  # the argument contract, not a business failure
        raise TypeError("bad economics input: %s" % exc) from exc

    engine = compute if compute is not None else spec.compute
    try:
        output = engine(built)
    except Exception as exc:  # noqa: BLE001 - engine failure, surfaced honestly
        return _bad("economics engine failed: %s: %s" % (type(exc).__name__, exc))

    if not hasattr(output, "to_dict"):
        return _bad(
            "economics engine returned %s, expected an output with to_dict()"
            % type(output).__name__
        )
    payload = output.to_dict()
    if not isinstance(payload, Mapping):
        return _bad("economics engine output must serialise to a mapping")

    if payload.get("contribution_profit_after_ads") is None:
        missing = [str(m) for m in (payload.get("missing_inputs") or [])]
        return _bad(
            "the margin is not computable from these numbers; missing: %s"
            % (", ".join(missing) or "unknown inputs")
        )

    return {
        "ok": True,
        "tool": TOOL_MARGIN_REPORT,
        "data": {
            "economics": dict(payload),
            "readiness": payload.get("readiness"),
            "missing_inputs": [str(m) for m in (payload.get("missing_inputs") or [])],
            "ignored_inputs": sorted(ignored),
            "aliased_inputs": aliased,
            "inputs_used": sorted(data),
            "note": (
                "Computed by the canonical economics engine. An input supplied as "
                "null stays UNKNOWN; no value was inferred. Shorthand renames are "
                "listed in aliased_inputs."
            ),
        },
    }


TOOLS = {TOOL_MARGIN_REPORT: margin_report}
