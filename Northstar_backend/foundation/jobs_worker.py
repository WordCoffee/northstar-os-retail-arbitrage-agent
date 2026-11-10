"""Worker process (1C-04 / B06).

Polls and atomically claims org-scoped queued jobs, re-runs every runtime
recheck, executes the registered LOCAL/fake handler, heartbeats, settles usage,
persists versioned output, and moves the job to the correct final/retry/blocked
state. Every consequential event is audited.

A worker is always organization-scoped. Only fake/local handlers execute; no
remote system is contacted.
"""
from __future__ import annotations

import time
from typing import Optional

from .jobs_durable import DurableJobService


class JobWorker:
    def __init__(self, service: DurableJobService, *, worker_id: str,
                 organization_id: str, poll_interval: float = 0.02) -> None:
        self.service = service
        self.worker_id = worker_id
        self.organization_id = organization_id
        self.poll_interval = poll_interval

    def run_once(self, *, lease_seconds: Optional[int] = None):
        """Claim and execute at most one job. Returns the ExecutionOutcome or
        None when the queue is empty."""
        run = self.service.claim_next(
            self.worker_id, organization_id=self.organization_id,
            lease_seconds=lease_seconds)
        if run is None:
            return None
        return self.service.execute_claimed(run, self.worker_id)

    def run_loop(self, *, max_iterations: Optional[int] = None,
                 until_empty: bool = False,
                 sleep_fn=None) -> list:
        """Poll and execute. Returns the list of outcomes."""
        sleep_fn = sleep_fn or time.sleep
        outcomes = []
        i = 0
        while max_iterations is None or i < max_iterations:
            i += 1
            outcome = self.run_once()
            if outcome is None:
                if until_empty:
                    break
                sleep_fn(self.poll_interval)
                continue
            outcomes.append(outcome)
            if until_empty and _queue_drained(self.service, self.organization_id):
                break
        return outcomes

    def drain(self, *, max_iterations: Optional[int] = None,
              sleep_fn=None) -> list:
        """Run until the org queue is empty (bounded by max_iterations)."""
        return self.run_loop(max_iterations=max_iterations, until_empty=True,
                             sleep_fn=sleep_fn)


def _queue_drained(service: DurableJobService, org_id: str) -> bool:
    posture = service.queue_posture(org_id)
    return posture["queued"] == 0