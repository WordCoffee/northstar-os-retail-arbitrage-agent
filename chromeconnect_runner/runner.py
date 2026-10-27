"""Chrome Connect runner (P6-T2).

Polls for jobs, claims them, executes adapter tasks, posts evidence,
heartbeats. Kill switch: local STOP file + Admin pause toggle.

Uses Chrome Connect controller (MCP tools) for all browser actions.
Does NOT use Playwright directly.

Provenance: In-house implementation based on NORTHSTAROS_MASTER_BUILD_PLAN.md P6-T2.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

try:
    from .job_protocol import BrowserJob, BrowserEvidence, JobQueue, JobState
    from .adapter_base import SiteAdapter, AdapterResult
    from .evidence import ExtractionEvidence, make_field_evidence, make_extraction_evidence
except ImportError:
    from job_protocol import BrowserJob, BrowserEvidence, JobQueue, JobState
    from adapter_base import SiteAdapter, AdapterResult
    from evidence import ExtractionEvidence, make_field_evidence, make_extraction_evidence


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------
POLL_INTERVAL_S = float(os.environ.get("CC_RUNNER_POLL_INTERVAL_S", "5"))
HEARTBEAT_INTERVAL_S = float(os.environ.get("CC_RUNNER_HEARTBEAT_INTERVAL_S", "30"))
MAX_CONCURRENT_JOBS = int(os.environ.get("CC_RUNNER_MAX_CONCURRENT", "1"))
STOP_FILE = os.environ.get("CC_RUNNER_STOP_FILE", "STOP")
PAUSE_FLAG = os.environ.get("CC_RUNNER_PAUSE_FLAG", "PAUSED")


@dataclass
class RunnerConfig:
    runner_id: str = "runner-1"
    poll_interval_s: float = POLL_INTERVAL_S
    heartbeat_interval_s: float = HEARTBEAT_INTERVAL_S
    max_concurrent: int = MAX_CONCURRENT_JOBS
    stop_file: str = STOP_FILE
    pause_flag: str = PAUSE_FLAG
    allowed_domains: List[str] = field(default_factory=list)
    per_domain_concurrency: int = 1


@dataclass
class RunnerState:
    running: bool = False
    paused: bool = False
    jobs_completed: int = 0
    jobs_failed: int = 0
    last_heartbeat: Optional[str] = None
    current_job: Optional[str] = None
    domain_locks: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "running": self.running,
            "paused": self.paused,
            "jobs_completed": self.jobs_completed,
            "jobs_failed": self.jobs_failed,
            "last_heartbeat": self.last_heartbeat,
            "current_job": self.current_job,
            "domain_locks": self.domain_locks,
        }


class ChromeConnectRunner:
    """Runner that polls for jobs and executes them via Chrome Connect."""

    def __init__(self, config: RunnerConfig, queue: JobQueue) -> None:
        self.config = config
        self.queue = queue
        self.state = RunnerState()
        self._adapters: Dict[str, SiteAdapter] = {}
        self._job_handlers: Dict[str, Callable] = {}

    def register_adapter(self, site: str, adapter: SiteAdapter) -> None:
        self._adapters[site] = adapter

    def register_handler(self, task_type: str, handler: Callable) -> None:
        self._job_handlers[task_type] = handler

    def is_stopped(self) -> bool:
        """Check if STOP file exists (kill switch)."""
        return os.path.exists(self.config.stop_file)

    def is_paused(self) -> bool:
        """Check if PAUSE flag exists (admin pause)."""
        return os.path.exists(self.config.pause_flag) or self.state.paused

    def heartbeat(self) -> Dict[str, Any]:
        """Send heartbeat. Returns status dict."""
        self.state.last_heartbeat = datetime.now(timezone.utc).isoformat()
        return {
            "runner_id": self.config.runner_id,
            "timestamp": self.state.last_heartbeat,
            "running": self.state.running,
            "paused": self.state.paused,
            "current_job": self.state.current_job,
            "jobs_completed": self.state.jobs_completed,
            "jobs_failed": self.state.jobs_failed,
        }

    def acquire_domain_lock(self, domain: str) -> bool:
        """Acquire a per-domain lock (concurrency 1)."""
        if self.state.domain_locks.get(domain, False):
            return False
        self.state.domain_locks[domain] = True
        return True

    def release_domain_lock(self, domain: str) -> None:
        self.state.domain_locks[domain] = False

    def execute_job(self, job: BrowserJob) -> BrowserJob:
        """Execute a single job. Returns updated job."""
        if job.state != "QUEUED":
            return job

        # Claim
        if not self.queue.claim(job.id, self.config.runner_id):
            return job

        job.state = "RUNNING"
        self.state.current_job = job.id

        domain = job.site
        if not self.acquire_domain_lock(domain):
            job.state = "FAILED"
            job.error_reason = "domain lock not available"
            self.state.jobs_failed += 1
            self.state.current_job = None
            return job

        try:
            # Execute based on task type
            handler = self._job_handlers.get(job.task_type)
            if handler:
                result = handler(job, self)
                if job.state == "SUCCEEDED":
                    self.state.jobs_completed += 1
                elif job.state == "FAILED":
                    self.state.jobs_failed += 1
            else:
                # Default: run adapter
                adapter = self._adapters.get(job.site)
                if adapter:
                    # Fetch the page through Chrome Connect (policy-enforced).
                    from chromeconnect_client import fetch_page_text
                    url = job.params.get("url", "")
                    task = job.params.get("task", "read page")
                    html = fetch_page_text(task, url)
                    adapter_result = adapter.extract(html, url=url)
                    if adapter_result.status == "OK":
                        job.state = "SUCCEEDED"
                        self.state.jobs_completed += 1
                    elif adapter_result.status == "DEGRADED":
                        job.state = "FAILED"
                        job.error_reason = "adapter degraded"
                        self.state.jobs_failed += 1
                    else:
                        job.state = "FAILED"
                        job.error_reason = "extraction failed"
                        self.state.jobs_failed += 1
                else:
                    job.state = "FAILED"
                    job.error_reason = f"no adapter or handler for {job.task_type}"
                    self.state.jobs_failed += 1

            # Post evidence if succeeded (evidence-first extraction, P6-T4)
            if job.state == "SUCCEEDED":
                from evidence import make_extraction_evidence, make_field_evidence
                extracted = job.params.get("extracted", {})
                fields = []
                for field_name, value in extracted.items():
                    fe = make_field_evidence(
                        field_name=field_name,
                        value=value,
                        source_url=job.params.get("url", ""),
                        selector_version=job.params.get("selector_version", "1.0.0"),
                        confidence=job.params.get("confidence", 1.0),
                    )
                    fields.append(fe)
                ev = make_extraction_evidence(
                    job_id=job.id,
                    url=job.params.get("url", ""),
                    fields=fields,
                    selector_version=job.params.get("selector_version", "1.0.0"),
                )
                # Also post legacy BrowserEvidence for compatibility
                evidence = BrowserEvidence(
                    job_id=job.id,
                    url=job.params.get("url", ""),
                    extracted=extracted,
                    status=ev.status,
                    confidence=ev.fields[0].confidence if ev.fields else 0.0,
                )
                self.queue.add_evidence(evidence)
                job.evidence_ref = job.id
                # Store full evidence for admin room
                job.params["_evidence"] = ev.to_dict()

        except Exception as e:
            job.state = "FAILED"
            job.error_reason = str(e)[:500]
            self.state.jobs_failed += 1
        finally:
            self.release_domain_lock(domain)
            self.state.current_job = None

        self.queue.update_state(job.id, job.state, job.error_reason)
        return job

    def run_once(self) -> int:
        """Poll and execute one batch of jobs. Returns count executed."""
        if self.is_stopped() or self.is_paused():
            return 0

        self.state.running = True
        executed = 0
        queued = self.queue.list_by_state("QUEUED")

        for job in queued[:self.config.max_concurrent]:
            if self.is_stopped() or self.is_paused():
                break
            self.execute_job(job)
            executed += 1

        return executed

    def run_loop(self, max_iterations: int = 0) -> None:
        """Run the polling loop. max_iterations=0 means run forever."""
        self.state.running = True
        iteration = 0
        while not self.is_stopped():
            if self.is_paused():
                time.sleep(self.config.poll_interval_s)
                continue
            self.run_once()
            self.heartbeat()
            iteration += 1
            if max_iterations > 0 and iteration >= max_iterations:
                break
            time.sleep(self.config.poll_interval_s)
        self.state.running = False

    def stop(self) -> None:
        """Stop the runner."""
        self.state.running = False
        # Create STOP file
        with open(self.config.stop_file, "w") as f:
            f.write("stopped")
