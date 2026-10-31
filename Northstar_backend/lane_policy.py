"""Deterministic model routing for the local lanes.

The architectural target is a dual-model tier: a coding engine for structural
edits and a reasoning engine for algorithmic work, with the orchestrator on the
long-context node. The router below encodes that policy as DATA, then checks what
is actually installed before returning a lane.

It never invents a model. If the preferred reasoning/orchestration lane is not
on disk, the route falls back to the installed coding lane and says so
(`fallback: true`, `requested_lane`), or raises `NoModelAvailable` when nothing
is installed. The caller can log the fallback instead of silently pretending the
specialised tier exists.

Intent classification is deterministic (paths / code fences / keywords), so the
same request always routes the same way and a test can pin it.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

#: Preferred lane per intent. Aliases match `tools/northstar_lane_router.py`.
ROUTES = {
    "code_edit": "northstaros-27b-coder",
    "reasoning": "northstaros-reasoner",
    "orchestration": "northstaros-orchestrator",
}
#: The lane that is known to be installed on this host today.
DEFAULT_AVAILABLE = "northstaros-27b-coder"

_CODE_HINTS = re.compile(
    r"(```|\.py\b|\.js\b|\.ts\b|\.tsx\b|refactor|rename|add method|replace function|"
    r"function body|class |def |import |patch|ast\b|unit test|pytest)", re.IGNORECASE)
_REASON_HINTS = re.compile(
    r"(why|prove|proof|analy[sz]e|root cause|algorithm|complexity|edge case|"
    r"failed test|traceback|stack trace|debug|reasoning|logic|design a|"
    r"mathematical|aime|derive)", re.IGNORECASE)
_ORCH_HINTS = re.compile(
    r"(plan|delegate|schedule|workflow|multi[- ]step|agents?\b|sop\b|"
    r"orchestrat|pipeline|roadmap|coordinate)", re.IGNORECASE)


class NoModelAvailable(RuntimeError):
    """No local lane is installed for the requested route."""


def classify(text: str, *, has_code: bool = False, path: Optional[str] = None) -> str:
    """Return code_edit / reasoning / orchestration for one request."""
    blob = str(text or "")
    if path or has_code or "```" in blob:
        return "code_edit"
    scores = {
        "code_edit": len(_CODE_HINTS.findall(blob)),
        "reasoning": len(_REASON_HINTS.findall(blob)),
        "orchestration": len(_ORCH_HINTS.findall(blob)),
    }
    best = max(scores, key=lambda k: (scores[k], k == "code_edit"))
    if scores[best] == 0:
        return "code_edit"          # Ty's Assistant is the default interactive tier
    return best


def installed_lanes(model_dir: Optional[Path] = None) -> Dict[str, bool]:
    """Which aliases have a model file on disk.

    The lane router keeps the alias -> file mapping; importing it avoids a
    second source of truth. A missing router module is reported as no lanes.
    """
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "northstar_lane_router",
            Path(__file__).resolve().parents[1] / "tools" / "northstar_lane_router.py")
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        lanes = getattr(module, "LANES", {})
        directory = Path(model_dir or getattr(module, "MODEL_DIR"))
    except Exception:  # noqa: BLE001 - no router is a supported state
        return {}
    out: Dict[str, bool] = {}
    for alias, lane in lanes.items():
        out[alias] = (directory / str(lane.get("file"))).is_file()
    return out


def route(intent: Optional[str] = None, text: str = "", *,
          has_code: bool = False, path: Optional[str] = None,
          available: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Choose a lane for the request, with an explicit fallback record."""
    kind = str(intent or "").strip().lower()
    if kind not in ROUTES:
        kind = classify(text, has_code=has_code, path=path)
    preferred = ROUTES[kind]
    lanes = dict(available) if available is not None else installed_lanes()
    if lanes.get(preferred):
        return {"intent": kind, "lane": preferred, "requested_lane": preferred,
                "fallback": False, "reason": "preferred_lane_installed",
                "installed": sorted(k for k, v in lanes.items() if v)}
    fallback = DEFAULT_AVAILABLE if lanes.get(DEFAULT_AVAILABLE) else next(
        (k for k, v in sorted(lanes.items()) if v), None)
    if fallback is None:
        raise NoModelAvailable(
            f"no local lane installed for {kind!r}; expected {preferred!r} "
            f"(known lanes: {sorted(lanes)})")
    return {"intent": kind, "lane": fallback, "requested_lane": preferred,
            "fallback": True,
            "reason": f"{preferred}_not_installed",
            "installed": sorted(k for k, v in lanes.items() if v)}


def describe(available: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    lanes = dict(available) if available is not None else installed_lanes()
    known = sorted(set(lanes) | set(ROUTES.values()))
    return {
        "routes": dict(ROUTES),
        "installed": [k for k in known if lanes.get(k)],
        "missing": [k for k in known if not lanes.get(k)],
        "fallback_lane": DEFAULT_AVAILABLE,
        "note": ("The installed local lane is the coder alias; the reasoning and "
                 "orchestrator lanes are policy targets until their weights are "
                 "present."),
    }


def main(argv: Optional[Iterable[str]] = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Route a request to a local model lane.")
    ap.add_argument("--intent", default="")
    ap.add_argument("--text", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(list(argv) if argv is not None else None)
    try:
        out = route(args.intent or None, args.text)
    except NoModelAvailable as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2) if args.json else f"{out['intent']} -> {out['lane']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ROUTES", "DEFAULT_AVAILABLE", "NoModelAvailable", "classify",
           "installed_lanes", "route", "describe"]
