"""Job foundation: request/run state machine, idempotency, cost ceiling.

Phase 1B executes ONLY the fixture/local path. No external provider execution.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .enums import JobState, FailureClass
from .models import JobRequest, JobRun, utcnow
from .repositories import Repositories


_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    JobState.REQUESTED.value: {JobState.QUEUED.value, JobState.CANCELLED.value},
    JobState.QUEUED.value: {JobState.RUNNING.value, JobState.CANCELLED.value},
    JobState.RUNNING.value: {JobState.SUCCEEDED.value, JobState.FAILED.value,
                             JobState.RETRY_SCHEDULED.value, JobState.CANCELLED.value},
    JobState.RETRY_SCHEDULED.value: {JobState.QUEUED.value, JobState.DEAD_LETTER.value,
                                     JobState.CANCELLED.value},
    JobState.FAILED.value: {JobState.DEAD_LETTER.value},
    JobState.SUCCEEDED.value: set(),
    JobState.CANCELLED.value: set(),
    JobState.DEAD_LETTER.value: set(),
}


class BudgetExceeded(RuntimeError):
    pass


@dataclass
class JobExecutionResult:
    run_id: str
    state: str
    failure_class: Optional[str] = None
    message: Optional[str] = None
    estimated_cost: Optional[float] = None


class JobOrchestrator:
    def __init__(self, repos: Repositories) -> None:
        self.repos = repos

    # -- request ---------------------------------------------------------------

    def request_job(self, req: JobRequest) -> dict:
        # Idempotency: return existing request for the same key.
        if req.idempotency_key:
            found = self.repos.job_requests.find({"idempotency_key": req.idempotency_key})
            if found:
                return found
        row = self.repos.job_requests.add(req)
        return row

    # -- run -------------------------------------------------------------------

    def create_run(self, job_request_id: str) -> dict:
        run = JobRun(job_request_id=job_request_id, state=JobState.QUEUED.value)
        return self.repos.job_runs.add(run)

    def transition(self, run_id: str, new_state: str, *,
                   failure_class: Optional[str] = None,
                   message: Optional[str] = None) -> dict:
        run = self.repos.job_runs.get(run_id)
        if run is None:
            raise ValueError(f"unknown run {run_id}")
        cur = run["state"]
        if new_state not in _ALLOWED_TRANSITIONS.get(cur, set()):
            raise ValueError(f"illegal transition {cur} -> {new_state}")
        run["state"] = new_state
        if failure_class:
            run["failure_class"] = failure_class
        if message:
            run["error_message"] = message
        if new_state == JobState.RUNNING.value and not run.get("started_at"):
            run["started_at"] = utcnow().isoformat()
        if new_state in (JobState.SUCCEEDED.value, JobState.FAILED.value,
                         JobState.CANCELLED.value, JobState.DEAD_LETTER.value):
            run["finished_at"] = utcnow().isoformat()
        if new_state == JobState.RETRY_SCHEDULED.value:
            run["attempts"] = int(run.get("attempts") or 0) + 1
            if run["attempts"] >= int(run.get("max_attempts") or 3):
                new_state = JobState.DEAD_LETTER.value
                run["state"] = new_state
                run["finished_at"] = utcnow().isoformat()
        self.repos.db.conn.execute(
            "UPDATE job_runs SET state=?, attempts=?, failure_class=?, "
            "error_message=?, started_at=?, finished_at=? WHERE id=?",
            (run["state"], run.get("attempts"), run.get("failure_class"),
             run.get("error_message"), run.get("started_at"),
             run.get("finished_at"), run_id),
        )
        self.repos.db.conn.commit()
        return run

    def enforce_ceiling(self, req_row: dict, estimated_cost: Optional[float]) -> None:
        ceiling = req_row.get("max_estimated_cost")
        if ceiling is not None and estimated_cost is not None and estimated_cost > ceiling:
            raise BudgetExceeded(
                f"estimated cost {estimated_cost} exceeds ceiling {ceiling}")

    # -- fixture/local execution path -----------------------------------------

    def execute_fixture(self, job_request_id: str, runner) -> JobExecutionResult:
        """Run a local/fixture job. ``runner`` is a callable(requests) -> (cost, ok)."""
        req = self.repos.job_requests.get(job_request_id)
        if req is None:
            raise ValueError(f"unknown job_request {job_request_id}")
        run = self.create_run(job_request_id)
        self.transition(run["id"], JobState.RUNNING.value)
        try:
            estimated_cost, ok = runner(req)
            self.enforce_ceiling(req, estimated_cost)
        except BudgetExceeded as e:
            self.transition(run["id"], JobState.FAILED.value,
                            failure_class=FailureClass.BUDGET_EXCEEDED.value,
                            message=str(e))
            return JobExecutionResult(run["run_id"], JobState.FAILED.value,
                                      FailureClass.BUDGET_EXCEEDED.value, str(e))
        except Exception as e:  # noqa: BLE001 - classify generic failure
            self.transition(run["id"], JobState.FAILED.value,
                            failure_class=FailureClass.UNKNOWN.value, message=str(e))
            return JobExecutionResult(run["run_id"], JobState.FAILED.value,
                                      FailureClass.UNKNOWN.value, str(e))
        state = JobState.SUCCEEDED.value if ok else JobState.FAILED.value
        fc = None if ok else FailureClass.PROVIDER_ERROR.value
        self.transition(run["id"], state, failure_class=fc)
        return JobExecutionResult(run["run_id"], state, fc,
                                  estimated_cost=estimated_cost)

    def cancel(self, run_id: str) -> dict:
        return self.transition(run_id, JobState.CANCELLED.value,
                               failure_class=FailureClass.CANCELLED.value)