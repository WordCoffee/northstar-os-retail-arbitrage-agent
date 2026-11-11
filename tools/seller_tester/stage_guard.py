"""A pipeline stage may decline; it may not crash quietly.

Two bugs in one day had the same shape: an `except Exception` turned a **programmer error** into a
"stage refused" record, and the run carried on with a degraded artefact that scored as if nothing had
happened. A missing `import numpy` looked like a layout that declined to run, for two scoring rounds.

The rule this enforces was tightened on 2026-11-11. The old version tolerated bare `ValueError` and
`RuntimeError` as refusals, which meant a `KeyError` wrapped in a `RuntimeError` — or a numpy shape
error, which *is* a `ValueError` — still degraded the run silently. Tolerance by exception *type* is
how a bug gets a refusal's clothing. So the guard now recognises exactly one type:

* `StageRefused` — the stage **chose** to decline, and says why. Recorded; the run continues.
* **everything else**, `ValueError` and `RuntimeError` included, is a bug in this code and aborts the
  run loudly. A score produced from a degraded artefact must never be publishable.

A third-party step that signals "cannot" with `ValueError`/`RuntimeError` (a degenerate quad, an
empty cutout) is converted at the call site with `declined("what", fn, ...)`. The refusal is then
typed, named and intentional instead of inherited by accident.

    from .stage_guard import StageRefused, declined, stage

    with stage("layout", record) as mark:
        fitted = declined("fit_aspect", deterministic.fit_aspect, png, box, aspect)
        if not fitted.get("ok"):
            raise StageRefused("the layout produced no usable canvas")
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Callable, Dict, Iterator, TypeVar

T = TypeVar("T")


class StageRefused(Exception):
    """A stage declined to run. Expected, typed, recorded, and the run continues."""

    def __init__(self, reason: str, *, stage: str = ""):
        super().__init__(reason)
        self.reason = reason
        self.stage = stage


class StageFailed(RuntimeError):
    """A stage hit something that is a bug, not a refusal. The caller must stop."""


def declined(what: str, fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Call a step that signals "cannot" with ValueError/RuntimeError, as a typed refusal.

    The conversion happens HERE, at a named call, so the refusal has a name and a reason. It is
    deliberately not a blanket `except` around a stage body: an unexpected ValueError from a line
    nobody declared still aborts the run.
    """
    try:
        return fn(*args, **kwargs)
    except (ValueError, RuntimeError) as exc:
        raise StageRefused(f"{what} declined: {type(exc).__name__}: {exc}") from exc


@contextmanager
def stage(name: str, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Run one stage; record a typed refusal, raise on anything else.

    Yields a mutable dict the stage can annotate. On `StageRefused` the record gets
    `{"kind": "refused", "stage": name, "reason": ...}` and the context swallows it; on anything
    else the exception is re-raised as `StageFailed`, which callers let propagate.
    """
    mark: Dict[str, Any] = {"stage": name, "refused": False}
    try:
        yield mark
    except StageRefused as exc:
        mark.update({"refused": True, "kind": "refused",
                     "reason": exc.reason or str(exc)})
        record[name] = dict(mark)
    except Exception as exc:  # noqa: BLE001 - the point is to make every one of these loud
        record[name] = {"stage": name, "refused": False, "kind": "error",
                        "error": f"{type(exc).__name__}: {exc}",
                        "note": "unexpected exception: the run is aborted, not degraded"}
        raise StageFailed(
            f"stage {name!r} raised {type(exc).__name__}: {exc} — this is a bug in the pipeline, "
            "not a refused stage, so the run stops here") from exc
    else:
        record[name] = dict(mark)


__all__ = ["StageFailed", "StageRefused", "declined", "stage"]
