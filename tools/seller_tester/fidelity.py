"""Fidelity rules: a brief is `exact` unless it has no product in frame.

Owner instruction (2026-11-08): *define tolerant as only allowed when no product is in frame,
default exact, and report the count.*

Why it matters: `tolerant` means "full generation is acceptable", which is only honest when
there is nothing to reproduce exactly. A brief with a product in frame is always `exact`, so the
pipeline must composite the real product rather than generate a lookalike. Anything else lets a
generated pouch stand in for the seller's pouch.

The count is reported, because a tolerance that quietly grows is the same failure as a test that
skips itself.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

EXACT = "exact"
TOLERANT = "tolerant"
VALID = (EXACT, TOLERANT)


def product_in_frame(brief: Dict[str, Any]) -> bool:
    """A brief has a product in frame unless it says otherwise, explicitly.

    Default true. A brief that omits the field is treated as carrying a product, because the
    safe default is the one that demands fidelity.
    """
    value = brief.get("product_in_frame")
    if value is None:
        return True
    return bool(value)


def normalise(brief: Dict[str, Any]) -> Dict[str, Any]:
    """Return the brief with a lawful `fidelity`, refusing an unlawful one.

    `tolerant` on a brief with a product in frame is downgraded to `exact` and the reason is
    recorded — silently honouring it would defeat the rule.
    """
    out = dict(brief)
    declared = str(out.get("fidelity") or EXACT).strip().casefold()
    if declared not in VALID:
        out["fidelity"] = EXACT
        out["fidelity_note"] = f"unknown fidelity {declared!r} coerced to exact"
        return out
    if declared == TOLERANT and product_in_frame(out):
        out["fidelity"] = EXACT
        out["fidelity_note"] = "tolerant refused: a product is in frame"
        return out
    out["fidelity"] = declared
    return out


def is_tolerant_allowed(brief: Dict[str, Any]) -> bool:
    return normalise(brief)["fidelity"] == TOLERANT


def counts(briefs: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """How many briefs are exact and how many are tolerant, with the tolerant ids named."""
    exact: List[str] = []
    tolerant: List[str] = []
    downgraded: List[str] = []
    for brief in briefs or ():
        declared = str(brief.get("fidelity") or EXACT).strip().casefold()
        lawful = normalise(brief)
        if lawful["fidelity"] == TOLERANT:
            tolerant.append(str(brief.get("id")))
        else:
            exact.append(str(brief.get("id")))
            if declared == TOLERANT:
                downgraded.append(str(brief.get("id")))
    total = len(exact) + len(tolerant)
    return {"total": total, "exact": len(exact), "tolerant": len(tolerant),
            "tolerant_ids": tolerant, "downgraded_ids": downgraded,
            "tolerant_share": round(len(tolerant) / total, 3) if total else 0.0}


__all__ = ["EXACT", "TOLERANT", "VALID", "counts", "is_tolerant_allowed", "normalise",
           "product_in_frame"]
