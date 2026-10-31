"""Hardware telemetry guardrail (work order Phase II, item: VRAM/thermal enforcement).

The rule the owner asked for is arithmetic, so it lives in a pure function that
can be tested without a GPU:

    used / total < 0.88          and          temperature < the thermal ceiling

Above either line the batch steps DOWN (4 -> 2 -> 1 -> 0) instead of running and
dying half-way through, and 0 is a refusal, not a silent retry.

`nvidia-smi` is the only I/O. If it is missing or unparseable the answer is
"unknown", and an unknown headroom is treated as NO headroom by the callers -
a box that cannot report is a box that must not be asked to render.
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Optional

DEFAULT_MAX_VRAM_RATIO = 0.88
DEFAULT_MAX_TEMP_C = 85.0
NEAR_MISS_MARGIN = 0.03


@dataclass(frozen=True)
class Hardware:
    ok: bool
    used_mb: Optional[int] = None
    total_mb: Optional[int] = None
    temp_c: Optional[float] = None
    reason: str = ""

    @property
    def ratio(self) -> Optional[float]:
        if not self.ok or not self.total_mb:
            return None
        return round(self.used_mb / self.total_mb, 4)


def decide_batch(
    desired: int,
    ratio: Optional[float],
    temp_c: Optional[float] = None,
    *,
    max_ratio: float = DEFAULT_MAX_VRAM_RATIO,
    max_temp_c: float = DEFAULT_MAX_TEMP_C,
    min_batch: int = 1,
) -> tuple[int, str]:
    """Return (batch, reason). batch == 0 means refuse this render."""
    want = max(0, int(desired))
    if want == 0:
        return 0, "nothing requested"
    if ratio is None:
        return 0, "vram_unknown"
    if ratio >= 1.0:
        return 0, f"vram_exhausted ({ratio:.0%})"
    if temp_c is not None and temp_c >= max_temp_c:
        return 0, f"thermal_stop ({temp_c:.0f}C >= {max_temp_c:.0f}C)"

    # Step down until the projected per-item cost fits the budget.
    batch = want
    while batch > min_batch:
        projected = ratio + batch * 0.01
        if projected < max_ratio:
            break
        batch -= 1
    projected = ratio + batch * 0.01
    if projected >= max_ratio:
        if ratio >= max_ratio:
            return 1, f"over_budget ({ratio:.0%} >= {max_ratio:.0%}) - single item only"
        return min_batch, "at_budget - minimum batch"

    hot = temp_c is not None and temp_c >= max_temp_c - 5
    note = f"{batch} of {want} (vram {ratio:.0%}"
    note += f", {temp_c:.0f}C)" if temp_c is not None else ")"
    if hot:
        note += " - near thermal ceiling"
    return batch, note


def snapshot(timeout_s: float = 6.0) -> Hardware:
    """Read the GPU once. Never raises: a probe failure is data, not a crash."""
    exe = shutil.which("nvidia-smi")
    if not exe:
        return Hardware(False, reason="nvidia-smi not found")
    try:
        out = subprocess.run(
            [exe, "--query-gpu=memory.used,memory.total,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=timeout_s, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return Hardware(False, reason=f"probe failed: {exc.__class__.__name__}")
    if out.returncode != 0 or not (out.stdout or "").strip():
        return Hardware(False, reason=f"nvidia-smi exit {out.returncode}")

    first = out.stdout.strip().splitlines()[0]
    parts = [p.strip() for p in first.split(",")]
    if len(parts) < 3:
        return Hardware(False, reason=f"unparseable output: {first[:60]}")
    try:
        used, total, temp = (int(parts[0]), int(parts[1]), float(parts[2]))
    except ValueError:
        return Hardware(False, reason=f"unparseable numbers: {first[:60]}")
    return Hardware(True, used_mb=used, total_mb=total, temp_c=temp)


def plan(desired: int, **kwargs) -> tuple[int, str, Hardware]:
    """Snapshot + decide in one call, for the render path."""
    hw = snapshot()
    batch, reason = decide_batch(desired, hw.ratio, hw.temp_c, **kwargs)
    return batch, reason, hw


__all__ = ["Hardware", "snapshot", "decide_batch", "plan",
           "DEFAULT_MAX_VRAM_RATIO", "DEFAULT_MAX_TEMP_C"]
