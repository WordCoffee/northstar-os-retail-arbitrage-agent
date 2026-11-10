"""A pipeline stage may decline; it may not crash quietly.

Two bugs in one day had the same shape: an `except Exception` turned a **programmer error** into a
"stage refused" record, and the run carried on with a degraded artefact that scored as if nothing had
happened. A missing `import numpy` looked like a layout that declined to run, for two scoring rounds.

The rule this enforces:

* an **expected** failure (`ValueError`, `RuntimeError` — an empty cutout, a quad with no area, a
  model that refused) is recorded and the stage degrades, because those are business outcomes;
* an **unexpected** failure (`NameError`, `TypeError`, `AttributeError`, `ImportError`, anything else)
  is a bug in this code, and it aborts the run loudly. A score produced from a degraded artefact must
  never be publishable.

    from .stage_guard import stage

    with stage("layout", record) as mark:
        ...work...
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Iterator, Tuple

#: The only exception types a stage is allowed to swallow. Everything else is a defect.
EXPECTED_STAGE_ERRORS: Tuple[type, ...] = (ValueError, RuntimeError)


class StageFailed(RuntimeError):
    """A stage hit something that is a bug, not a refusal. The caller must stop."""


@contextmanager
def stage(name: str, record: Dict[str, Any]) -> Iterator[Dict[str, Any]]:
    """Run one stage; record an expected refusal, raise on anything else.

    Yields a mutable dict the stage can annotate. On an expected error the record gets
    `{"kind": "refused", "stage": name, "reason": ...}` and the context swallows it; on anything else
    the exception is re-raised as `StageFailed`, which callers let propagate.
    """
    mark: Dict[str, Any] = {"stage": name, "refused": False}
    try:
        yield mark
    except EXPECTED_STAGE_ERRORS as exc:
        mark.update({"refused": True, "reason": f"{type(exc).__name__}: {exc}"})
        record[name] = dict(mark)
    except Exception as exc:  # noqa: BLE001 - the point is to make every one of these loud
        record[name] = {"stage": name, "refused": False,
                        "error": f"{type(exc).__name__}: {exc}",
                        "note": "unexpected exception: the run is aborted, not degraded"}
        raise StageFailed(
            f"stage {name!r} raised {type(exc).__name__}: {exc} — this is a bug in the pipeline, "
            "not a refused stage, so the run stops here") from exc
    else:
        record[name] = dict(mark)
