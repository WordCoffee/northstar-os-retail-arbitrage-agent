"""Usage ledger: raw cost, customer charge, margin, caps, monthly report (§11A.2).

One row per provider call. The numbers are computed from the price table and the
margin rule, never estimated, so a monthly report is a sum over rows.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
PRICES_PATH = Path(os.environ.get("NORTHSTAR_PROVIDER_PRICES",
                                  ROOT / "shared" / "provider-prices.json"))
MARGIN_PATH = Path(os.environ.get("NORTHSTAR_MARGIN_RULES",
                                  ROOT / "shared" / "margin-rules.json"))
LEDGER_PATH = Path(os.environ.get("NORTHSTAR_USAGE_LEDGER",
                                  ROOT / "Northstar_backend" / "data" / "usage_ledger.jsonl"))


def _read(path: Path, default: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def prices() -> Dict[str, Any]:
    return _read(PRICES_PATH, {"providers": {}})


def margin_rules() -> Dict[str, Any]:
    return _read(MARGIN_PATH, {"default_margin": 0.65,
                               "by_plan": {}, "by_service": {},
                               "user_caps": {"daily_default": 25.0,
                                             "monthly_default": 300.0}})


def margin_for(plan: Optional[str], service: Optional[str]) -> float:
    rules = margin_rules()
    base = float(rules.get("default_margin", 0.65))
    if service and service in (rules.get("by_service") or {}):
        base = float(rules["by_service"][service])
    if plan and plan in (rules.get("by_plan") or {}):
        base = float(rules["by_plan"][plan])
    floor = float(rules.get("floor_margin", 0.0))
    ceiling = float(rules.get("ceiling_margin", 1.0))
    return max(floor, min(ceiling, base))


def raw_cost(provider: str, usage: Dict[str, float]) -> float:
    """Price the call from the table. Local lanes cost 0 (own hardware)."""
    entry = (prices().get("providers") or {}).get(provider) or {}
    unit = entry.get("unit")
    if unit == "1k_tokens":
        cost = ((usage.get("tokens_in", 0) / 1000.0) * float(entry.get("input", 0.0))
                + (usage.get("tokens_out", 0) / 1000.0) * float(entry.get("output", 0.0)))
    elif unit == "gpu_second":
        cost = usage.get("gpu_seconds", 0.0) * float(entry.get("input", 0.0))
    elif unit == "1k_chars":
        cost = (usage.get("tokens_in", 0) / 1000.0) * float(entry.get("input", 0.0))
    else:
        cost = 0.0
    return round(cost, 8)


def charge_for(cost: float, margin: float) -> float:
    """charge = cost / (1 - margin). A zero cost stays zero."""
    if cost <= 0:
        return 0.0
    return round(cost / max(1e-6, (1.0 - margin)), 8)


def spent(user_id: str, *, window: str = "day") -> float:
    """Sum of CHARGES for a user in the current day/month, from the ledger."""
    total = 0.0
    for row in read_rows():
        if row.get("user_id") != user_id:
            continue
        ts = row.get("at", 0)
        if window == "day":
            if time.gmtime(ts)[:3] != time.gmtime()[:3]:
                continue
        else:
            if time.gmtime(ts)[:2] != time.gmtime()[:2]:
                continue
        total += float(row.get("charge_usd") or 0.0)
    return round(total, 6)


def cap_check(user_id: str, projected_charge: float) -> Dict[str, Any]:
    caps = margin_rules().get("user_caps") or {}
    daily = float(caps.get("daily_default", 0.0))
    monthly = float(caps.get("monthly_default", 0.0))
    day = spent(user_id, window="day")
    month = spent(user_id, window="month")
    if daily and day + projected_charge > daily:
        return {"ok": False, "reason": "daily_cap",
                "detail": f"day {day:.4f} + {projected_charge:.4f} > {daily:.2f} USD"}
    if monthly and month + projected_charge > monthly:
        return {"ok": False, "reason": "monthly_cap",
                "detail": f"month {month:.4f} + {projected_charge:.4f} > {monthly:.2f} USD"}
    return {"ok": True, "day_spend": day, "month_spend": month}


def record(*, user_id: str, tenant_id: str, role: str, provider: str, model: Optional[str],
           usage: Dict[str, float], agent: str = "", job_id: str = "",
           service: str = "", plan: str = "", ok: bool = True,
           idempotency_key: str = "", detail: str = "") -> Dict[str, Any]:
    cost = raw_cost(provider, usage)
    margin = margin_for(plan, service)
    charge = charge_for(cost, margin)
    row = {
        "id": f"u_{uuid.uuid4().hex[:12]}",
        "at": time.time(),
        "user_id": user_id, "tenant_id": tenant_id,
        "job_id": job_id, "agent": agent, "service": service, "plan": plan,
        "role": role, "provider": provider, "model": model,
        "usage": usage, "raw_cost_usd": cost, "margin": round(margin, 4),
        "charge_usd": charge, "ok": bool(ok), "detail": detail[:200],
        "idempotency_key": idempotency_key,
    }
    _append(row)
    return row


def _append(row: Dict[str, Any]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")


def read_rows() -> List[Dict[str, Any]]:
    if not LEDGER_PATH.is_file():
        return []
    rows = []
    for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def monthly_report() -> Dict[str, Any]:
    rows = read_rows()
    cost = round(sum(float(r.get("raw_cost_usd") or 0) for r in rows), 6)
    charge = round(sum(float(r.get("charge_usd") or 0) for r in rows), 6)
    realised = round((charge - cost) / charge, 4) if charge > 0 else None
    return {
        "calls": len(rows),
        "raw_cost_usd": cost,
        "charge_usd": charge,
        "gross_margin_usd": round(charge - cost, 6),
        "realised_margin": realised,
        "target_margin": margin_rules().get("default_margin"),
        "by_provider": _group(rows, "provider"),
        "by_role": _group(rows, "role"),
        "note": "sum over ledger rows; no sampling, no estimates",
    }


def _group(rows: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for r in rows:
        k = str(r.get(key) or "?")
        g = out.setdefault(k, {"calls": 0, "cost": 0.0, "charge": 0.0})
        g["calls"] += 1
        g["cost"] = round(g["cost"] + float(r.get("raw_cost_usd") or 0), 6)
        g["charge"] = round(g["charge"] + float(r.get("charge_usd") or 0), 6)
    return out
