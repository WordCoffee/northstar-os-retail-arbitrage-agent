"""Container entrypoint: run the durable-job worker across all organizations.

Polls each organization's queue and executes registered (local/fake) handlers
via ``JobWorker``. Never contacts a remote system. Idles when there are no
organizations yet (e.g. before the owner is seeded in P2-T5).
"""
from __future__ import annotations

import os
import time

from foundation.api.state import FoundationState
from foundation.jobs_worker import JobWorker


def main() -> None:
    state = FoundationState.build()
    worker_id = os.environ.get("WORKER_ID", "worker-1")
    interval = float(os.environ.get("WORKER_POLL_SECONDS", "1.0"))
    print(f"foundation worker {worker_id} started")
    while True:
        try:
            for org in state.repos.organizations.list():
                JobWorker(state.jobs_durable, worker_id=worker_id,
                          organization_id=org["id"]).run_once()
        except Exception as e:  # noqa: BLE001 - keep the container alive
            print(f"worker iteration failed: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    main()