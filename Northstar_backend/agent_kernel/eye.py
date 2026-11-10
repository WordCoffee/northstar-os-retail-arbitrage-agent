"""Ty's Eye — the vision half of Tys Assistant.

**What this is.** Tys Assistant builds; the eye looks. After a step that produced
something visible — a render, a screenshot, a UI capture — the eye asks the local
vision model one question about that image and returns a verdict plus, when the
verdict is bad, the guidance the assistant should act on next.

**What the eye is not.** It does not read code, it does not edit files and it does
not decide outcomes on its own. Measured 2026-11-05 (`tools/vision_code_probe.py`):
`gemma3:4b` at 640 px answered 5/5 constraint questions about a code screenshot
correctly but transcribed the same pixels at 0.652 character similarity and
confidently invented lines. So the eye judges *appearance*, and code changes stay
with the coding lane, which reads the real bytes from disk.

**The three statuses, and why `unverified` exists.**

| status | meaning |
|---|---|
| `on_track` | an image was read and the verdict parsed as a pass |
| `off_track` | an image was read and the verdict parsed as a fail; `guidance` says why |
| `unverified` | no image, no constraint, eyes disabled, model down, or an unparseable answer |

`unverified` is never upgraded to `on_track`. A supervisor that reports success
when it could not see is worse than no supervisor: it launders an absence of
evidence into evidence of correctness.

**Enablement.** Two switches, owner-owned, dependent: Tys Assistant first, then its
eyes. `enabled` may be a bool or a zero-argument callable so a running agent picks
up an operator toggle without being rebuilt.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".webp", ".bmp")

ON_TRACK = "on_track"
OFF_TRACK = "off_track"
UNVERIFIED = "unverified"
DISABLED = "disabled"

_GUIDANCE_PREFIX = (
    "The eye judged this result off-goal. Fix what it names, then continue: "
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def default_constraint(goal: str) -> str:
    """A fallback question when the step names no constraint.

    It is deliberately coarse — "does this plausibly advance the goal" is a
    judgement, not a test — and the returned record marks it `derived_constraint`
    so nobody mistakes it for a precise acceptance check.
    """
    goal = " ".join(str(goal or "").split())[:400]
    if not goal:
        return ""
    return ("the visible result plausibly advances this goal and shows no obvious "
            "placeholder, blank area, garbled text or missing main subject: " + goal)


class TyEye:
    """One vision checkpoint over an image, with a journal and guidance."""

    name = "ty-eye"

    def __init__(
        self,
        enabled: Any = False,
        *,
        caller: Optional[Callable[[bytes, str], str]] = None,
        journal: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._enabled = enabled
        self._caller = caller
        self.model = model or os.environ.get("NORTHSTAR_VISION_MODEL", "") or \
            _vision_model()
        self.journal_path = journal or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "tys",
            "eyes.jsonl")
        self._journal_path = os.path.abspath(self.journal_path)

    # -- enablement --------------------------------------------------------

    def enabled(self) -> bool:
        value = self._enabled
        if callable(value):
            try:
                return bool(value())
            except Exception:  # noqa: BLE001 - an unreadable switch is off
                return False
        return bool(value)

    # -- the look ----------------------------------------------------------

    def look(
        self,
        goal: str,
        *,
        image: Optional[bytes] = None,
        image_path: Optional[str] = None,
        constraint: str = "",
        step: str = "",
    ) -> Dict[str, Any]:
        """Judge one image against one constraint. Never raises."""
        started = time.time()
        record: Dict[str, Any] = {
            "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "goal": " ".join(str(goal or "").split())[:400],
            "step": str(step or "")[:200],
            "model": self.model,
        }

        if not self.enabled():
            return self._finish(record, DISABLED, "eyes_disabled", started,
                                guidance="")

        if image is None and image_path:
            path = Path(str(image_path))
            if not path.is_file():
                return self._finish(record, UNVERIFIED, "image_missing", started,
                                    guidance="", image_path=str(path))
            try:
                image = path.read_bytes()
            except OSError as exc:
                return self._finish(record, UNVERIFIED,
                                    f"image_unreadable: {exc}"[:200], started,
                                    guidance="", image_path=str(path))
        if not image:
            return self._finish(record, UNVERIFIED, "no_image", started, guidance="")

        used = str(constraint or "").strip()
        derived = False
        if not used:
            used = default_constraint(goal)
            derived = True
        if not used:
            return self._finish(record, UNVERIFIED, "no_constraint", started,
                                guidance="")
        record.update({"constraint": used[:400], "derived_constraint": derived,
                       "image_sha256": _sha256(image), "image_bytes": len(image)})

        try:
            from . import vision_verify  # noqa: WPS433 - optional local model

            verdict = vision_verify.verify(image, used, caller=self._caller)
        except Exception as exc:  # noqa: BLE001 - unavailable is not on_track
            return self._finish(record, UNVERIFIED,
                                f"{type(exc).__name__}: {exc}"[:200], started,
                                guidance="")

        if not verdict.get("available"):
            return self._finish(record, UNVERIFIED,
                                str(verdict.get("reason") or "vision_unavailable")[:200],
                                started, guidance="", verdict=verdict)

        reasons = [str(r)[:300] for r in (verdict.get("reasons") or [])][:8]
        record["reasons"] = reasons
        record["confidence"] = verdict.get("confidence")
        if verdict.get("pass"):
            return self._finish(record, ON_TRACK, "", started, guidance="",
                                verdict=verdict)

        guidance = _GUIDANCE_PREFIX + ("; ".join(reasons) if reasons else
                                       "the constraint was not met")
        return self._finish(record, OFF_TRACK, "constraint_not_met", started,
                            guidance=guidance[:600], verdict=verdict)

    # -- helpers -----------------------------------------------------------

    def artifacts(self, artifacts: Sequence[str] = ()) -> List[str]:
        """The image artifacts a step produced, in the order they were given."""
        return [str(a) for a in artifacts
                if str(a).lower().endswith(IMAGE_SUFFIXES)]

    def _finish(self, record: Dict[str, Any], status: str, reason: str,
                started: float, *, guidance: str,
                verdict: Optional[Dict[str, Any]] = None,
                image_path: str = "") -> Dict[str, Any]:
        record.update({
            "status": status,
            "reason": reason,
            "guidance": guidance,
            "seconds": round(time.time() - started, 2),
        })
        if image_path:
            record["image_path"] = image_path
        if verdict:
            record["verdict"] = {"pass": verdict.get("pass"),
                                 "reasons": verdict.get("reasons") or [],
                                 "confidence": verdict.get("confidence")}
        self._journal(record)
        return record

    def _journal(self, record: Dict[str, Any]) -> None:
        path = Path(self._journal_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, default=str) + "\n")
        except OSError:
            # A journal that cannot be written is not allowed to crash a build;
            # the record still travels back to the caller in the step evidence.
            pass

    def recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """The last `limit` journal records, newest last. Unreadable journal: []."""
        path = Path(self._journal_path)
        if not path.is_file():
            return []
        out: List[Dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return out[-int(limit):] if limit else out


def _vision_model() -> str:
    try:
        from . import vision_verify

        return str(vision_verify.MODEL)
    except Exception:  # noqa: BLE001
        return "gemma3:4b"


__all__ = ["TyEye", "ON_TRACK", "OFF_TRACK", "UNVERIFIED", "DISABLED",
           "default_constraint", "IMAGE_SUFFIXES"]
