"""Browser job protocol (P6-T1).

Defines job states, evidence records, and the job queue interface.
Jobs are executed by the runner via Chrome Connect controller.

States: QUEUED, CLAIMED, NEEDS_OWNER, RUNNING, SUCCEEDED, FAILED,
        BLOCKED_SIGNIN, BLOCKED_POLICY, CANCELLED

Provenance: In-house implementation based on NORTHSTAROS_MASTER_BUILD_PLAN.md P6-T1.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class JobState(str, Enum):
    QUEUED = "QUEUED"
    CLAIMED = "CLAIMED"
    NEEDS_OWNER = "NEEDS_OWNER"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED_SIGNIN = "BLOCKED_SIGNIN"
    BLOCKED_POLICY = "BLOCKED_POLICY"
    CANCELLED = "CANCELLED"


class JobType(str, Enum):
    COSTCO_SCAN = "costco_scan"
    SITE_READ = "site_read"
    ADAPTER_RUN = "adapter_run"
    QA_SCREENSHOT = "qa_screenshot"
    CUSTOM = "custom"


@dataclass
class BrowserJob:
    id: str = ""
    org_id: str = "default"
    site: str = ""
    task_type: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    state: str = JobState.QUEUED.value
    needs_owner_reason: Optional[str] = None
    created_at: str = ""
    claimed_by: Optional[str] = None
    claimed_at: Optional[str] = None
    evidence_ref: Optional[str] = None
    error_reason: Optional[str] = None
    step_count: int = 0
    source: str = "synthetic"  # synthetic | operator

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrowserJob":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class BrowserEvidence:
    job_id: str = ""
    url: str = ""
    observed_at: str = ""
    screenshot_sha256: Optional[str] = None
    extracted: Dict[str, Any] = field(default_factory=dict)
    provenance: str = "OBSERVED"
    selector_version: Optional[str] = None
    confidence: float = 0.0
    status: str = "OK"  # OK | UNKNOWN | DEGRADED

    def __post_init__(self):
        if not self.observed_at:
            self.observed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrowserEvidence":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class JobQueue:
    """In-memory job queue (P6-T1). Production uses DB tables."""

    def __init__(self) -> None:
        self._jobs: Dict[str, BrowserJob] = {}
        self._evidence: Dict[str, List[BrowserEvidence]] = {}

    def enqueue(self, job: BrowserJob) -> str:
        self._jobs[job.id] = job
        return job.id

    def claim(self, job_id: str, runner_id: str) -> bool:
        job = self._jobs.get(job_id)
        if not job or job.state != JobState.QUEUED.value:
            return False
        job.state = JobState.CLAIMED.value
        job.claimed_by = runner_id
        job.claimed_at = datetime.now(timezone.utc).isoformat()
        return True

    def get(self, job_id: str) -> Optional[BrowserJob]:
        return self._jobs.get(job_id)

    def list_by_state(self, state: str) -> List[BrowserJob]:
        return [j for j in self._jobs.values() if j.state == state]

    def update_state(self, job_id: str, state: str, reason: Optional[str] = None) -> bool:
        job = self._jobs.get(job_id)
        if not job:
            return False
        job.state = state
        if reason:
            job.needs_owner_reason = reason
        return True

    def add_evidence(self, evidence: BrowserEvidence) -> str:
        if evidence.job_id not in self._evidence:
            self._evidence[evidence.job_id] = []
        self._evidence[evidence.job_id].append(evidence)
        return evidence.job_id

    def get_evidence(self, job_id: str) -> List[BrowserEvidence]:
        return self._evidence.get(job_id, [])

    def stats(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for j in self._jobs.values():
            counts[j.state] = counts.get(j.state, 0) + 1
        return counts
