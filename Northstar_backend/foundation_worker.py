"""Container entrypoint: run the durable-job worker across all organizations.

Polls each organization's queue and executes registered (local/fake) handlers
via ``JobWorker``. Never contacts a remote system. Idles when there are no
organizations yet (e.g. before the owner is seeded in P2-T5).

P1-05 / P4 (2026-10-09): the loop used to swallow every failure with a print,
so a wedged worker looked exactly like a healthy one. It now reports real
progress on a readiness endpoint:
  GET :8090/healthz  liveness
  GET :8090/readyz   readiness (503 while the last iteration failed)
  GET :8090/status   the full counters, for Monitoring
Set WORKER_HEALTH_PORT=0 to disable the endpoint.
"""

from __future__ import annotations

import os
import time

from foundation.api.state import FoundationState
from foundation.jobs_worker import JobWorker
from foundation.ops_health import ProcessHealth


def main() -> None:
    state = FoundationState.build()
    worker_id = os.environ.get("WORKER_ID", "worker-1")
    interval = float(os.environ.get("WORKER_POLL_SECONDS", "1.0"))
    health = ProcessHealth("foundation-worker")
    port = int(os.environ.get("WORKER_HEALTH_PORT", "8090"))
    if port > 0:
        health.serve(port)
    print(f"foundation worker {worker_id} started (readiness on :{port})")
    while True:
        try:
            ran = 0
            for org in state.repos.organizations.list():
                JobWorker(state.jobs_durable, worker_id=worker_id,
                          organization_id=org["id"]).run_once()
                ran += 1
            health.record_success()
            del ran
        except Exception as e:  # noqa: BLE001 - keep the container alive
            health.record_failure(e)
            print(f"worker iteration failed: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()
