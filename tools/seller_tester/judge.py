"""Vision judge adapter — local only, OFF by default.

The harness scores images programmatically. A judge is an optional semantic
second opinion with one contract::

    judge(image_bytes, rubric) -> {"pass": bool, "score": float, "reasons": [...]}

The default implementation is a thin wrapper around the repo's local verifier
(`Northstar_backend/agent_kernel/vision_verify.py`, Ollama on 127.0.0.1). It is
disabled unless `NORTHSTAR_SELLER_JUDGE=1` is set, and it refuses to run against
any non-loopback URL. Pixels never go to a cloud model.

Tests inject `FakeJudge` and never touch a model.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = REPO_ROOT / "Northstar_backend"


class JudgeUnavailable(RuntimeError):
    """Raised when the local vision path cannot be reached."""


def _loopback(url: str) -> bool:
    return any(host in url for host in ("127.0.0.1", "localhost", "::1", "[::1]"))


def _import_vision_verify():
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    try:
        from agent_kernel import vision_verify  # type: ignore

        return vision_verify
    except ImportError:
        pass
    try:
        from Northstar_backend.agent_kernel import vision_verify  # type: ignore

        return vision_verify
    except ImportError as exc:
        raise JudgeUnavailable(f"local vision module not importable: {exc}") from exc


def local_judge(image_bytes: bytes, rubric: Dict[str, Any]) -> Dict[str, Any]:
    """Ask the local vision model. Never cloud; never raises to the harness."""
    url = os.environ.get("NORTHSTAR_VISION_URL", "http://127.0.0.1:11434/api/chat")
    if not _loopback(url):
        return {"pass": None, "score": 0.0, "available": False,
                "reasons": [f"refused: vision URL is not loopback ({url})"]}
    constraint = str((rubric or {}).get("constraint") or "").strip()
    if not constraint:
        return {"pass": None, "score": 0.0, "available": False,
                "reasons": ["no rubric constraint supplied"]}
    try:
        vision_verify = _import_vision_verify()
        verdict = vision_verify.verify(image_bytes, constraint)
    except Exception as exc:  # noqa: BLE001 - unavailable is a skip, not a pass
        return {"pass": None, "score": 0.0, "available": False,
                "reasons": [f"{type(exc).__name__}: {exc}"[:300]]}
    if not verdict.get("available"):
        return {"pass": None, "score": 0.0, "available": False,
                "reasons": [str(verdict.get("reason") or "vision unavailable")[:300]]}
    passed = bool(verdict.get("pass"))
    confidence = verdict.get("confidence")
    score = 100.0 if passed else 0.0
    if isinstance(confidence, (int, float)):
        score = 100.0 * float(confidence) if passed else 100.0 * (1.0 - float(confidence))
    return {"pass": passed, "score": round(score, 1),
            "reasons": [str(r)[:300] for r in (verdict.get("reasons") or [])][:8],
            "available": True, "model": verdict.get("model")}


class FakeJudge:
    """Deterministic judge for tests and dry runs."""

    def __init__(self, passed: bool = True, score: Optional[float] = None,
                 reasons: Optional[list[str]] = None) -> None:
        self.passed = passed
        self.score = score
        self.reasons = reasons or (["fake judge: pass"] if passed else ["fake judge: fail"])
        self.calls: list[Dict[str, Any]] = []

    def __call__(self, image_bytes: bytes, rubric: Dict[str, Any]) -> Dict[str, Any]:
        self.calls.append({"bytes": len(image_bytes or b""), "rubric": dict(rubric or {})})
        score = self.score if self.score is not None else (100.0 if self.passed else 0.0)
        return {"pass": self.passed, "score": score, "reasons": list(self.reasons),
                "available": True}


def judge_enabled() -> bool:
    return os.environ.get("NORTHSTAR_SELLER_JUDGE", "0").strip().lower() in ("1", "true", "yes", "on")


def get_judge(default: Optional[Callable[[bytes, Dict[str, Any]], Dict[str, Any]]] = None
              ) -> Optional[Callable[[bytes, Dict[str, Any]], Dict[str, Any]]]:
    """Return the judge the harness should use, or None (the default)."""
    if default is not None:
        return default
    return local_judge if judge_enabled() else None


__all__ = ["JudgeUnavailable", "local_judge", "FakeJudge", "judge_enabled", "get_judge"]
