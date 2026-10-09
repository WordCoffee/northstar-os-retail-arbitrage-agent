"""Container entrypoint: tick the persisted scheduler (enqueue-only).

The scheduler never executes jobs and never calls providers. Idles harmlessly
when there are no organizations/schedules yet.

P1-05 / P4 (2026-10-09): a failed tick used to vanish into a print. It now
reports real progress on a readiness endpoint:
  GET :8091/healthz  liveness
  GET :8091/readyz   readiness (503 while the last tick failed)
  GET :8091/status   the full counters, for Monitoring
Set SCHEDULER_HEALTH_PORT=0 to disable the endpoint.
"""

from __future__ import annotations

import os
import time

from foundation.api.state import FoundationState
from foundation.ops_health import ProcessHealth


def main() -> None:
    state = FoundationState.build()
    interval = float(os.environ.get("SCHEDULER_INTERVAL_SECONDS", "5"))
    health = ProcessHealth("foundation-scheduler")
    port = int(os.environ.get("SCHEDULER_HEALTH_PORT", "8091"))
    if port > 0:
        health.serve(port)
    print(f"foundation scheduler started (readiness on :{port})")
    while True:
        try:
            state.scheduler.tick()
            health.record_success()
        except Exception as e:  # noqa: BLE001 - keep the container alive
            health.record_failure(e)
            print(f"scheduler tick failed: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
