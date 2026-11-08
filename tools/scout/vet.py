"""Vetting + adoption policy (D11, reused by A18/A21).

``tools/vet_package.py`` already answers *is this package known-malicious* via
OSV.  This module is the thin adapter: it calls that interface with the
connector's ecosystem and version, records the verdict, and turns licence +
verdict into an adoption status.

Policy, stated once:

* ``malicious``               -> ``reject``
* unknown / non-commercial    -> ``replace_later`` (never ``adopt``)
* copyleft                    -> ``review`` (commercial, but the provider suite
                                 refuses unreviewed AGPL/GPL for the cloud lane)
* vet check incomplete        -> ``review`` (a transport failure is never a pass)
* clean licence + clean vet   -> ``adopt`` when relevance clears the bar
* papers                      -> ``watch`` (research input, not a component)
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from . import config

STATUSES = ("adopt", "review", "replace_later", "reject", "watch")


def _default_vet(name: str, ecosystem: str, version: Optional[str]) -> Dict[str, Any]:
    from tools.vet_package import vet  # local import: keep tests offline

    return vet(name, ecosystem, version)


def vet_hit(hit: Dict[str, Any], *,
            vet_fn: Optional[Callable[[str, str, Optional[str]], Dict[str, Any]]] = None
            ) -> Dict[str, Any]:
    """Run the OSV check where it applies.  Never fabricates a pass."""
    ecosystem = hit.get("ecosystem")
    name = str(hit.get("title") or "").strip()
    if not ecosystem:
        return {"checked": False, "verdict": "not_applicable",
                "note": f"{hit.get('source')} hits are not installable packages"}
    if not name:
        return {"checked": False, "verdict": "check_incomplete", "error": "name_missing"}
    function = vet_fn or _default_vet
    try:
        result = function(name, str(ecosystem), hit.get("version"))
    except Exception as exc:  # noqa: BLE001 - a failure is recorded, never a pass
        return {"checked": False, "verdict": "check_incomplete",
                "error": f"{type(exc).__name__}: {str(exc)[:180]}"}
    verdict = str((result or {}).get("verdict") or "check_incomplete")
    return {
        "checked": verdict in ("clear", "malicious"),
        "verdict": verdict,
        "malicious": list((result or {}).get("malicious") or []),
        "vulnerabilities": list((result or {}).get("vulnerabilities") or []),
        "ecosystem": ecosystem,
        "version": (result or {}).get("version"),
    }


def vet_factor(vet: Optional[Dict[str, Any]]) -> float:
    """0..1 weight for ranking."""
    verdict = (vet or {}).get("verdict")
    if verdict == "clear":
        return 0.85 if (vet or {}).get("vulnerabilities") else 1.0
    if verdict == "not_applicable":
        return 0.8
    if verdict == "malicious":
        return 0.0
    return 0.3  # check_incomplete / not checked


def decide_status(*, licence: str, licence_class: str, vet: Optional[Dict[str, Any]],
                  relevance: float, kind: str = "item") -> str:
    """The single adoption-policy function.  Unknown never becomes ``adopt``."""
    verdict = (vet or {}).get("verdict")
    if verdict == "malicious":
        return "reject"
    if kind == "paper":
        return "watch"
    if licence_class in ("unknown", "noncommercial", "proprietary"):
        return "replace_later"
    if licence_class == "copyleft":
        return "review"
    if vet is not None and verdict in ("check_incomplete", "not_checked"):
        return "review"
    if relevance < config.ADOPT_MIN_RELEVANCE:
        return "review"
    return "adopt"


def adopt_eligible(status: str) -> bool:
    return status == "adopt"


def explain(finding: Dict[str, Any]) -> str:
    vet = finding.get("vet") or {}
    return (f"{finding.get('licence')} ({finding.get('licence_class')}), "
            f"vet={vet.get('verdict', 'not_run')}, relevance={finding.get('relevance')}")
