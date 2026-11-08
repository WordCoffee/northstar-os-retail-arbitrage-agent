"""Bojo tools for OfferChisel (pricing) and Operations Hub (status).

Two plain functions, wired to Bojo by ``chat_tools``:

* :func:`offer_recommendation` — deterministic offer pricing with an explicit,
  configurable fee model. Pure arithmetic: no marketplace call, no network.
* :func:`hub_status` — per-service operational status aggregated from the ONE
  existing trust surface (:mod:`ops_status`). It never invents a value: a probe
  that cannot measure a service is reported as ``unknown`` with the reason.

Return contract (both tools)::

    {"ok": True,  "tool": "<name>", "data": {...}}
    {"ok": False, "tool": "<name>", "reason": "..."}

``hub_status`` adds ``data`` to its refusal when it has per-service detail to
show, so an operator can see *which* sources failed rather than only that all
of them did.

Rounding (chosen once, stated in the payload): the ask is rounded **up** to the
next whole cent so the target margin is never missed by rounding; fee and profit
amounts round half-up to 2 dp; the margin shown is computed from those rounded
figures, so a seller can re-add the numbers in ``data["arithmetic"]`` and land
on the same answer.

Provenance: in-house. No external code.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import ops_status

_CENT = Decimal("0.01")
_ONE_HUNDRED = Decimal("100")
_MARGIN_FLOOR_PCT = Decimal("-95")     # a clearance price may lose money, but not 100%
_MAX_BUMPS = 10_000                    # cents the rounding repair may add, a guard not a policy

# ── fee model ────────────────────────────────────────────────────────────────
#
# A marketplace offer pays, per unit:
#
#   referral  = max(sale_price * referral_pct, referral_min)
#   fulfilment = flat pick/pack/ship cost
#   other      = any further flat per-unit fee (channel, compliance, ...)
#
# The referral percentage with a per-unit minimum is the shape that makes cheap
# items loss-making if it is ignored, which is why the minimum is solved for as
# its own branch rather than clamped afterwards.

DEFAULT_FEES: Dict[str, float] = {
    "referral_pct": 15.0,   # percent of the sale price
    "referral_min": 0.30,   # per-unit floor on the referral fee
    "fulfilment": 0.0,      # flat per-unit fulfilment cost
    "other": 0.0,           # any other flat per-unit fee
}

_FEE_KEYS: Tuple[str, ...] = ("referral_pct", "referral_min", "fulfilment", "other")

ROUNDING_NOTE = (
    "Ask rounded UP to the next whole cent (never below the target margin). "
    "Fees, profit and margin are rounded half-up to 2 dp from that rounded price, "
    "so the steps in 'arithmetic' re-add to the numbers reported."
)


# ── small numeric helpers ────────────────────────────────────────────────────

def _dec(value: Any) -> Optional[Decimal]:
    """Exact decimal for a real number, else ``None``. Never coerces strings."""
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def _money(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


def _num(value: Decimal) -> str:
    """Plain decimal text: no exponent, no trailing zeros."""
    text = format(value.normalize(), "f")
    return "0" if text in ("", "-0") else text


def _usd(value: Decimal) -> str:
    return f"${value:,.2f}"


def _bad(tool: str, reason: str) -> Dict[str, Any]:
    return {"ok": False, "tool": tool, "reason": reason}


# ── OfferChisel: offer_recommendation ────────────────────────────────────────

def _resolve_fees(fees: Optional[Mapping[str, Any]]) -> Tuple[Dict[str, Decimal], List[str]]:
    """Validate and complete the fee model. Raises ``ValueError`` on bad input."""
    if fees is not None and not isinstance(fees, Mapping):
        raise ValueError("fees must be a mapping such as {'referral_pct': 15.0}")
    raw: Dict[str, Any] = dict(DEFAULT_FEES)
    supplied = set()
    if fees:
        unknown = {str(k) for k in fees} - set(DEFAULT_FEES)
        if unknown:
            raise ValueError(
                "unknown fee key(s): " + ", ".join(sorted(unknown))
                + f"; allowed: {', '.join(_FEE_KEYS)}"
            )
        raw.update({str(k): v for k, v in fees.items()})
        supplied = {str(k) for k in fees}

    resolved: Dict[str, Decimal] = {}
    for key in _FEE_KEYS:
        value = _dec(raw[key])
        if value is None:
            raise ValueError(f"fees.{key} must be a real number")
        if value < 0:
            raise ValueError(f"fees.{key} must be >= 0")
        resolved[key] = value
    if not (0 <= resolved["referral_pct"] < _ONE_HUNDRED):
        raise ValueError("fees.referral_pct must be between 0 and 100 (exclusive)")

    # Money amounts are cents; the percentage keeps its precision.
    for key in ("referral_min", "fulfilment", "other"):
        resolved[key] = _money(resolved[key])

    warnings: List[str] = []
    if "fulfilment" not in supplied:
        warnings.append(
            "fulfilment fee was not supplied; assumed $0.00 per unit — "
            "add the real pick/pack/ship cost or the margin is overstated"
        )
    return resolved, warnings


def _achieved(price: Decimal, fees: Mapping[str, Decimal], cost: Decimal) -> Dict[str, Decimal]:
    """Fees, profit and margin at a concrete cent price. Pure."""
    referral = max(price * fees["referral_pct"] / _ONE_HUNDRED, fees["referral_min"])
    referral = _money(referral)
    profit = _money(price - referral - fees["fulfilment"] - fees["other"] - cost)
    margin_pct = (profit / price * _ONE_HUNDRED).quantize(_CENT, rounding=ROUND_HALF_UP)
    return {
        "referral_fee": referral,
        "profit": profit,
        "margin_pct": margin_pct,
        "total_fees": _money(referral + fees["fulfilment"] + fees["other"]),
        "total_cost": _money(cost + referral + fees["fulfilment"] + fees["other"]),
    }


def offer_recommendation(
    cost: float,
    target_margin_pct: float,
    competitor_prices: Optional[Sequence[float]] = None,
    *,
    fees: Optional[Mapping[str, float]] = None,
    competitor_policy: str = "lowest",
    undercut_pct: float = 0.0,
    currency: str = "USD",
) -> Dict[str, Any]:
    """Recommend a per-unit offer price with the arithmetic shown.

    Solves ``profit = target_margin * price`` where

        profit = price - max(price*referral_pct, referral_min) - fulfilment
                 - other - cost

    The fee function is piecewise, so both branches are solved in closed form
    and the one that is true at its own price wins:

    * percentage branch: ``price = (cost + flat fees) / (1 - referral% - margin%)``
    * minimum branch:    ``price = (cost + flat fees + referral_min) / (1 - margin%)``

    A competitor ceiling (lowest price by default) clamps the ask; the margin
    actually achieved at the clamped price is reported, never the target.
    """
    tool = "offer_recommendation"
    try:
        fees_resolved, warnings = _resolve_fees(fees)

        cost_dec = _dec(cost)
        if cost_dec is None:
            raise ValueError("cost must be a real number")
        if cost_dec < 0:
            raise ValueError("cost must be >= 0")
        cost_dec = _money(cost_dec)

        margin = _dec(target_margin_pct)
        if margin is None:
            raise ValueError("target_margin_pct must be a real number")
        margin = margin.quantize(_CENT, rounding=ROUND_HALF_UP)
        ceiling_margin = _ONE_HUNDRED - fees_resolved["referral_pct"]
        if margin <= _MARGIN_FLOOR_PCT or margin >= ceiling_margin:
            raise ValueError(
                f"target_margin_pct {_num(margin)}% is outside the reachable range: "
                f"with a {_num(fees_resolved['referral_pct'])}% referral rate the margin "
                f"must be above {_num(_MARGIN_FLOOR_PCT)}% and below "
                f"{_num(ceiling_margin)}%"
            )

        undercut_dec = _dec(undercut_pct)
        if undercut_dec is None:
            raise ValueError("undercut_pct must be a real number")
        if not (0 <= undercut_dec <= Decimal("50")):
            raise ValueError("undercut_pct must be between 0 and 50")

        if competitor_policy not in ("lowest", "median"):
            raise ValueError("competitor_policy must be 'lowest' or 'median'")

        prices: List[Decimal] = []
        for index, raw_price in enumerate(competitor_prices or []):
            value = _dec(raw_price)
            if value is None or value <= 0:
                raise ValueError(f"competitor_prices[{index}] must be a positive number")
            prices.append(_money(value))

        flat = fees_resolved["fulfilment"] + fees_resolved["other"]
        total_base = cost_dec + flat
        if total_base <= 0:
            raise ValueError("cost + flat fees must be greater than 0 to solve a price")

        referral_pct = fees_resolved["referral_pct"] / _ONE_HUNDRED if fees_resolved["referral_pct"] else Decimal(0)
        margin_frac = margin / _ONE_HUNDRED
        headroom = Decimal(1) - referral_pct - margin_frac          # > 0 by validation

        # Where the percentage fee stops binding: below this base cost the
        # per-unit minimum is the real fee, so the other formula applies.
        min_branch_below = (
            fees_resolved["referral_min"] * headroom / referral_pct
            if referral_pct > 0 else Decimal("-1")
        )
        min_branch = total_base < min_branch_below

        if min_branch:
            exact = (total_base + fees_resolved["referral_min"]) / (Decimal(1) - margin_frac)
        else:
            exact = total_base / headroom

        price = exact.quantize(_CENT, rounding=ROUND_CEILING)
        if price <= 0:
            price = _CENT
        ceil_price = price

        # Repair the rounding: the ask must actually clear the target, measured
        # on the rounded fee the marketplace will charge.
        state = _achieved(price, fees_resolved, cost_dec)
        bumps = 0
        while state["margin_pct"] < margin and bumps < _MAX_BUMPS:
            price += _CENT
            state = _achieved(price, fees_resolved, cost_dec)
            bumps += 1
        if bumps >= _MAX_BUMPS:
            raise ValueError("price did not converge on the target margin; check the fee model")

        target_price = price

        # ── competitor ceiling ──────────────────────────────────────────────
        ceiling: Optional[Decimal] = None
        if prices:
            ordered = sorted(prices)
            if competitor_policy == "lowest":
                ceiling = ordered[0]
            else:
                middle = len(ordered) // 2
                ceiling = (ordered[middle] if len(ordered) % 2
                           else _money((ordered[middle - 1] + ordered[middle]) / 2))
        effective_ceiling = None
        if ceiling is not None:
            effective_ceiling = (ceiling * (Decimal(1) - undercut_dec / _ONE_HUNDRED)).quantize(
                _CENT, rounding=ROUND_FLOOR)

        clamped = effective_ceiling is not None and effective_ceiling < price
        if clamped:
            if effective_ceiling <= 0:
                raise ValueError(
                    f"the competitor ceiling {_usd(ceiling)} with a "
                    f"{_num(undercut_dec)}% undercut leaves no positive price"
                )
            price = effective_ceiling
            state = _achieved(price, fees_resolved, cost_dec)

        profit: Decimal = state["profit"]
        achieved_margin: Decimal = state["margin_pct"]
        target_met = achieved_margin >= margin
        if profit > 0:
            verdict = "sell"
        elif profit == 0:
            verdict = "break_even"
        else:
            verdict = "do_not_sell"

        min_fee_applied = state["referral_fee"] == fees_resolved["referral_min"] and (
            price * referral_pct < fees_resolved["referral_min"])

        if clamped:
            warnings.append(
                f"competitor ceiling {_usd(effective_ceiling)} is below the target price "
                f"{_usd(target_price)}; ask clamped, margin {_num(achieved_margin)}% vs "
                f"target {_num(margin)}%"
            )
        if profit < 0:
            warnings.append(
                f"at {_usd(price)} the unit loses {_usd(-profit)}; do not list at this ceiling"
            )
        if min_fee_applied:
            warnings.append(
                f"the {_usd(fees_resolved['referral_min'])} referral minimum applies at this "
                f"price ({_num(fees_resolved['referral_pct'])}% would be "
                f"{_usd(_money(price * referral_pct))})"
            )
        if margin < 0:
            warnings.append("target margin is negative (clearance pricing): the ask is below cost")

        # ── the seller's own audit trail ────────────────────────────────────
        arithmetic: List[str] = [
            f"flat fees per unit = fulfilment {_usd(fees_resolved['fulfilment'])} "
            f"+ other {_usd(fees_resolved['other'])} = {_usd(flat)}",
            f"base to recover = cost {_usd(cost_dec)} + flat fees {_usd(flat)} = {_usd(total_base)}",
        ]
        if min_branch:
            arithmetic.append(
                f"minimum-fee branch: {_usd(total_base)} + referral minimum "
                f"{_usd(fees_resolved['referral_min'])} over (1 - {_num(margin)}% margin) "
                f"= {_usd(exact)}"
            )
        else:
            arithmetic.append(
                f"percentage branch: {_usd(total_base)} over (1 - "
                f"{_num(fees_resolved['referral_pct'])}% referral - {_num(margin)}% margin) "
                f"= {_usd(exact)}"
            )
        arithmetic.append(
            f"round the ask up to the cent -> {_usd(ceil_price)}"
            + (f"; add {bumps} cent{'s' if bumps != 1 else ''} so the rounded fee still "
               f"clears the target -> {_usd(target_price)}" if bumps else "")
        )
        if clamped:
            arithmetic.append(f"competitor ceiling clamps the ask to {_usd(price)}")
        arithmetic.extend([
            f"referral = max({_usd(price)} x {_num(fees_resolved['referral_pct'])}%, "
            f"{_usd(fees_resolved['referral_min'])}) = {_usd(state['referral_fee'])}"
            + ("  [minimum applies]" if min_fee_applied else ""),
            f"total cost = {_usd(cost_dec)} cost + {_usd(state['total_fees'])} fees "
            f"= {_usd(state['total_cost'])}",
            f"profit = {_usd(price)} - {_usd(state['total_fees'])} fees "
            f"- {_usd(cost_dec)} cost = {_usd(profit)}",
            f"margin = {_usd(profit)} / {_usd(price)} = {_num(achieved_margin)}% "
            f"(target {_num(margin)}%)",
        ])

        return {
            "ok": True,
            "tool": tool,
            "data": {
                "currency": currency,
                "recommended_price": float(price),
                "target_price_before_ceiling": float(target_price),
                "achieved": {
                    "profit_per_unit": float(profit),
                    "margin_pct": float(achieved_margin),
                    "total_fees": float(state["total_fees"]),
                    "total_cost": float(state["total_cost"]),
                },
                "fees": {
                    "referral_pct": float(fees_resolved["referral_pct"]),
                    "referral_fee": float(state["referral_fee"]),
                    "referral_min": float(fees_resolved["referral_min"]),
                    "referral_min_applied": bool(min_fee_applied),
                    "fulfilment": float(fees_resolved["fulfilment"]),
                    "other": float(fees_resolved["other"]),
                },
                "costs": {"unit_cost": float(cost_dec)},
                "competitor": {
                    "prices": [float(p) for p in prices],
                    "policy": competitor_policy,
                    "ceiling": float(ceiling) if ceiling is not None else None,
                    "undercut_pct": float(undercut_dec),
                    "effective_ceiling": (float(effective_ceiling)
                                          if effective_ceiling is not None else None),
                    "clamped": bool(clamped),
                },
                "target_met": bool(target_met),
                "verdict": verdict,
                "warnings": warnings,
                "arithmetic": arithmetic,
                "rounding": ROUNDING_NOTE,
                "inputs": {
                    "cost": float(cost_dec),
                    "target_margin_pct": float(margin),
                    "fees": {k: float(v) for k, v in fees_resolved.items()},
                    "competitor_prices": [float(p) for p in prices],
                    "competitor_policy": competitor_policy,
                    "undercut_pct": float(undercut_dec),
                },
            },
        }
    except ValueError as exc:
        return _bad(tool, str(exc))


# ── Operations Hub: hub_status ───────────────────────────────────────────────

StatusProbe = Callable[[], Mapping[str, Any]]

DEFAULT_SERVICE_SOURCES: Dict[str, str] = {
    "disk": "ops_status.disk_status",
    "database": "ops_status.db_status",
    "lanes": "ops_status.lane_status",
    "models": "ops_status.model_status",
    "render_lock": "ops_status.render_lock_status",
}

_OK = ("ok", "green", "healthy")
_WARN = ("warn", "warning", "degraded", "amber")
_CRIT = ("critical", "red", "failed", "fail")

_RANK = {"ok": 0, "degraded": 1, "critical": 2, "unknown": 1}


def _default_services(disk_path: str) -> Dict[str, StatusProbe]:
    """The real probes: the existing status surface, never a second copy of it."""
    return {
        "disk": lambda: ops_status.disk_status(disk_path),
        "database": lambda: ops_status.db_status(),
        "lanes": lambda: ops_status.lane_status(),
        "models": lambda: ops_status.model_status(),
        "render_lock": lambda: ops_status.render_lock_status(),
    }


def _classify(payload: Any) -> Tuple[str, Optional[str]]:
    """Map one probe payload onto ``ok | degraded | critical | unknown`` + reason."""
    if not isinstance(payload, Mapping):
        return "unknown", f"probe returned {type(payload).__name__}, not a mapping"

    reason = payload.get("reason")
    if payload.get("available") is False:
        return "unknown", str(reason or "probe reports the source unavailable")

    verdict = payload.get("verdict")
    if isinstance(verdict, str):
        folded = verdict.strip().lower()
        if folded in _CRIT:
            return "critical", str(reason or f"verdict: {verdict}")
        if folded in _WARN:
            return "degraded", str(reason or f"verdict: {verdict}")
        if folded in _OK:
            return "ok", None

    if payload.get("error"):
        return "degraded", str(payload["error"])
    if "lanes" in payload and not payload.get("lanes"):
        # An empty telemetry table is not health; it is the absence of evidence.
        return "unknown", "no lane runs recorded, so nothing was measured"
    if payload.get("available") is True:
        return "ok", None
    return "unknown", str(reason or "probe returned no availability signal")


def hub_status(
    services: Optional[Mapping[str, StatusProbe]] = None,
    *,
    disk_path: str = ".",
) -> Dict[str, Any]:
    """Per-service operational status with the measured evidence for each.

    ``services`` is injectable so the caller (and the tests) can supply probes;
    omitted, it reads :mod:`ops_status`, the repo's single status surface.

    ``ok`` is false **only** when no service could be read at all. One
    unreadable source is reported as ``unknown`` for that service and lowers the
    overall status, because unknown never reads as healthy.
    """
    tool = "hub_status"
    if services is None:
        registry: Mapping[str, StatusProbe] = _default_services(disk_path)
        sources = DEFAULT_SERVICE_SOURCES
    else:
        if not isinstance(services, Mapping):
            return _bad(tool, "services must be a mapping of name -> zero-argument callable")
        registry = services
        sources = {}

    if not registry:
        return _bad(tool, "no services supplied; nothing to report")

    entries: Dict[str, Dict[str, Any]] = {}
    for name, probe in registry.items():
        if not callable(probe):
            entries[str(name)] = {
                "status": "unknown",
                "available": None,
                "source": sources.get(str(name), "injected"),
                "evidence": None,
                "reason": "probe is not callable",
            }
            continue
        try:
            payload = probe()
        except Exception as exc:  # noqa: BLE001 - reported per service, never hidden
            entries[str(name)] = {
                "status": "unknown",
                "available": None,
                "source": sources.get(str(name), "injected"),
                "evidence": None,
                "reason": f"{type(exc).__name__}: {exc}"[:200],
            }
            continue

        status, reason = _classify(payload)
        entries[str(name)] = {
            "status": status,
            "available": bool(payload.get("available")) if isinstance(payload, Mapping) and
                         isinstance(payload.get("available"), bool) else None,
            "source": sources.get(str(name), "injected"),
            "evidence": dict(payload) if isinstance(payload, Mapping) else payload,
            "reason": reason,
        }

    counts = {
        "total": len(entries),
        "ok": sum(1 for e in entries.values() if e["status"] == "ok"),
        "degraded": sum(1 for e in entries.values() if e["status"] == "degraded"),
        "critical": sum(1 for e in entries.values() if e["status"] == "critical"),
        "unknown": sum(1 for e in entries.values() if e["status"] == "unknown"),
    }
    readable = counts["total"] - counts["unknown"]

    if counts["critical"]:
        overall = "critical"
    elif counts["degraded"] or counts["unknown"]:
        overall = "degraded"
    else:
        overall = "ok"

    data: Dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": overall,
        "services": entries,
        "summary": {**counts, "readable": readable, "unreadable": counts["unknown"]},
        "unhealthy": sorted(n for n, e in entries.items() if e["status"] != "ok"),
    }

    if readable == 0:
        return {
            "ok": False,
            "tool": tool,
            "reason": "no status source could be read (" + ", ".join(sorted(entries)) + ")",
            "data": data,
        }

    return {"ok": True, "tool": tool, "data": data}


TOOLS = {
    "offer_recommendation": offer_recommendation,
    "hub_status": hub_status,
}
