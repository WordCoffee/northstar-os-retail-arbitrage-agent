"""Container entrypoint: tick the persisted scheduler (enqueue-only).

The scheduler never executes jobs and never calls providers. Idles harmlessly
when there are no organizations/schedules yet.
"""
from __future__ import annotations

import os
import time

from foundation.api.state import FoundationState


def main() -> None:
    state = FoundationState.build()
    interval = float(os.environ.get("SCHEDULER_INTERVAL_SECONDS", "5"))
    print("foundation scheduler started")
    while True:
        try:
            state.scheduler.tick()
        except Exception as e:  # noqa: BLE001 - keep the container alive
            print(f"scheduler tick failed: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()