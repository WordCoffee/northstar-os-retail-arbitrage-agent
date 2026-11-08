"""Verify-after-act: an action is not done because it was sent, but because it landed.

Work order §5.1 layer 4 and V4. Every input goes through `perform()`, which:

1. asks the risk policy whether the action may run at all,
2. tells the control layer to act (which is where the kill switch lives),
3. **observes again** and asks a predicate whether the intended change appeared,
4. on failure retries once, then reports the failure instead of assuming success.

The predicate is deliberately a plain callable over the post-state, so a caller can check
a UI Automation tree, a DOM, a URL or a frame hash with the same code path.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence

from . import risk


@dataclass
class Action:
    """One input, its risk-relevant context, and the executor that performs it."""

    kind: str
    target: str = ""
    payload: Any = None
    path: str = ""
    context: Dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "target": self.target, "path": self.path,
                **{k: v for k, v in self.context.items() if k != "scope"}}


def perform(*, action: Action, control: Any, execute: Callable[[], Any],
            observe: Callable[[], Any],
            expect: Callable[[Any, Any], bool],
            attempts: int = 2, settle_s: float = 0.0,
            scope: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Run one action and prove it landed. Failure is reported, never swallowed."""
    context = dict(action.context or {})
    verdict = risk.evaluate(action.as_dict(), url=context.get("url", ""),
                            title=context.get("title", ""),
                            process=context.get("process", ""),
                            scope=scope)
    if not verdict["allow"]:
        if verdict.get("needs_you"):
            risk.record_needs_you(action.as_dict(), verdict)
        return {"ok": False, "verified": False, "refused": True, **verdict,
                "attempts": []}

    before = _safe(observe)
    attempts_log: List[Dict[str, Any]] = []
    for attempt in range(1, max(1, attempts) + 1):
        acted = control.act(execute)
        if not acted.get("ok"):
            attempts_log.append({"attempt": attempt, "act": acted, "verified": False})
            if acted.get("blocked"):  # kill switch or pause file: stop, do not retry
                return {"ok": False, "verified": False, "blocked": True,
                        "reason": acted.get("reason"), "risk": verdict["risk"],
                        "attempts": attempts_log}
            continue
        if settle_s:
            time.sleep(settle_s)
        after = _safe(observe)
        landed = _safe_bool(lambda: bool(expect(after, before)))
        attempts_log.append({"attempt": attempt, "act_ok": True, "verified": landed})
        if landed:
            return {"ok": True, "verified": True, "risk": verdict["risk"],
                    "attempts": attempts_log, "after": _summary(after)}
        before = after

    # Two independent observations disagreed with the intent: report, do not pretend.
    risk.record_event({"event": "verify-after-act-failed", "action": action.as_dict(),
                      "attempts": len(attempts_log)})
    return {"ok": False, "verified": False, "risk": verdict["risk"],
            "reason": "intended change not observed", "attempts": attempts_log}


def _safe(call: Callable[[], Any]) -> Any:
    try:
        return call()
    except Exception as exc:  # noqa: BLE001 - an observation failure is data
        return {"error": f"{type(exc).__name__}: {exc}"}


def _safe_bool(call: Callable[[], bool]) -> bool:
    try:
        return bool(call())
    except Exception:  # noqa: BLE001 - a predicate that raises has not confirmed anything
        return False


def _summary(value: Any, limit: int = 400) -> Any:
    """Keep the evidence small enough to log and large enough to re-check."""
    if isinstance(value, (list, tuple)):
        return {"count": len(value), "head": [_summary(v, 200) for v in list(value)[:3]]}
    if isinstance(value, dict):
        return {k: _summary(v, 200) for k, v in list(value.items())[:8]}
    text = str(value)
    return text[:limit]


# --------------------------------------------------------------------- predicates
def element_value_is(elements: Sequence[Dict[str, Any]], name: str,
                     value: str) -> Callable[[Any, Any], bool]:
    """True when the element called `name` now holds `value`."""
    from . import tree

    def check(after: Any, _before: Any) -> bool:
        found = tree.find(list(after or ()), name)
        return bool(found) and str(found.get("value") or "") == str(value)

    return check


def element_present(elements: Sequence[Dict[str, Any]], name: str) -> Callable[[Any, Any], bool]:
    from . import tree

    def check(after: Any, _before: Any) -> bool:
        return tree.find(list(after or ()), name) is not None

    return check


def tree_changed() -> Callable[[Any, Any], bool]:
    """True when the observation differs from the one before the action."""

    def check(after: Any, before: Any) -> bool:
        return _fingerprint(after) != _fingerprint(before)

    return check


def url_is(needle: str) -> Callable[[Any, Any], bool]:
    """True when the observed URL contains `needle` (a DOM/URL observation)."""

    def check(after: Any, _before: Any) -> bool:
        text = after.get("url", "") if isinstance(after, dict) else str(after or "")
        return str(needle).casefold() in str(text).casefold()

    return check


def text_is(needle: str) -> Callable[[Any, Any], bool]:
    """True when the observed text contains `needle`."""

    def check(after: Any, _before: Any) -> bool:
        text = after.get("text", "") if isinstance(after, dict) else str(after or "")
        return str(needle).casefold() in str(text).casefold()

    return check


def all_of(*checks: Callable[[Any, Any], bool]) -> Callable[[Any, Any], bool]:
    def check(after: Any, before: Any) -> bool:
        return all(_safe_bool(lambda c=c: c(after, before)) for c in checks)

    return check


def _fingerprint(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, default=str)[:4000]
    except Exception:  # noqa: BLE001
        return repr(value)[:4000]


__all__ = ["Action", "perform", "element_value_is", "element_present", "tree_changed",
           "url_is", "text_is", "all_of"]
