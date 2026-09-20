"""Golden Goose job model (B7) — opaque job ids + status lifecycle.

Implements the BFF job resource defined in docs/contracts/BFF_CONTRACT_v1.md §4
and specialized in docs/contracts/GOLDEN_GOOSE_SEAM_v1.md §2.

Pure and offline: no network, no file writes, no provider calls, no spend.
`/scan` remains 403-gated — this module only *models* jobs; it does not run
live scanning and is not wired into a live route.

Opaque-id rule: external callers address jobs by a `job_` + 32-hex token. The
internal `scan_id` (and any report filename) is stored server-side and is NEVER
emitted by `public_view()`.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

# --- BFF §4 constants -------------------------------------------------------

JOB_ID_PREFIX = "job_"
SCAN_ID_PREFIX = "scan_"  # internal only — never exposed
RESULT_REF_PREFIX = "res_"

SERVICE = "golden_goose"
OPERATION_SCAN = "goose.scan"
OPERATION_EXPORT = "goose.export"

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"

TERMINAL_STATES = frozenset({DONE, FAILED, CANCELLED})

# Legal transitions only (BFF §4 state machine).
_ALLOWED_TRANSITIONS: Dict[str, frozenset] = {
    QUEUED: frozenset({RUNNING, CANCELLED}),
    RUNNING: frozenset({DONE, FAILED, CANCELLED}),
    DONE: frozenset(),
    FAILED: frozenset(),
    CANCELLED: frozenset(),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_job_id() -> str:
    """Opaque, cryptographically-random public job id (BFF §4)."""
    return JOB_ID_PREFIX + secrets.token_hex(16)


def new_scan_id() -> str:
    """Internal correlation id — MUST NOT be emitted in any public payload."""
    return SCAN_ID_PREFIX + secrets.token_hex(16)


def new_result_ref() -> str:
    """Opaque public pointer to a result set (never a file path)."""
    return RESULT_REF_PREFIX + secrets.token_hex(16)


class JobTransitionError(ValueError):
    """Raised on an illegal state transition (maps to error code `conflict`)."""


@dataclass
class GooseJob:
    """A Golden Goose job. `scan_id` is internal; `public_view()` hides it."""

    job_id: str
    operation: str = OPERATION_SCAN
    state: str = QUEUED
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    progress_pct: Optional[int] = 0
    result_ref: Optional[str] = None
    error: Optional[dict] = None
    # Internal-only fields (never serialized by public_view):
    scan_id: str = field(default_factory=new_scan_id)
    internal_notes: List[str] = field(default_factory=list)

    def transition(self, to_state: str, *, error: Optional[dict] = None,
                   progress_pct: Optional[int] = None) -> "GooseJob":
        """Advance the job along the legal state machine; else raise."""
        if to_state not in _ALLOWED_TRANSITIONS.get(self.state, frozenset()):
            raise JobTransitionError(
                "illegal transition %s -> %s for job %s" % (self.state, to_state, self.job_id)
            )
        self.state = to_state
        self.updated_at = _now()
        if progress_pct is not None:
            self.progress_pct = progress_pct
        if to_state == DONE:
            self.progress_pct = 100
            if self.result_ref is None:
                self.result_ref = new_result_ref()
        if to_state in (FAILED, CANCELLED):
            self.progress_pct = None
        if to_state == FAILED:
            self.error = error or {"code": "internal_error", "message": "Job failed.", "retryable": False}
        return self

    def public_view(self) -> dict:
        """BFF job resource — opaque ids only, no internal/scan fields."""
        return {
            "job_id": self.job_id,
            "service": SERVICE,
            "operation": self.operation,
            "state": self.state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "progress_pct": self.progress_pct,
            "result_ref": self.result_ref,
            "error": self.error,
            "links": {"self": "/api/v1/jobs/%s" % self.job_id},
        }


class GooseJobRegistry:
    """In-memory job store (alpha design). No network, no persistence."""

    def __init__(self) -> None:
        self._jobs: Dict[str, GooseJob] = {}

    def create(self, operation: str = OPERATION_SCAN) -> GooseJob:
        if operation not in (OPERATION_SCAN, OPERATION_EXPORT):
            raise ValueError("unknown operation: %r" % (operation,))
        job = GooseJob(job_id=new_job_id(), operation=operation)
        self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> GooseJob:
        job = self._jobs.get(job_id)
        if job is None:
            raise KeyError("unknown job id: %r" % (job_id,))  # BFF not_found, fail closed
        return job

    def transition(self, job_id: str, to_state: str, **kw) -> GooseJob:
        return self.get(job_id).transition(to_state, **kw)

    def __len__(self) -> int:
        return len(self._jobs)