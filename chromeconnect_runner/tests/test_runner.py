"""Tests for Chrome Connect runner (P6-T2)."""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from job_protocol import BrowserJob, BrowserEvidence, JobQueue, JobState
from runner import ChromeConnectRunner, RunnerConfig, RunnerState
from adapter_base import SiteAdapter, AdapterResult


def test_job_enqueue_and_claim():
    q = JobQueue()
    job = BrowserJob(site="costco.com", task_type="costco_scan", source="synthetic")
    jid = q.enqueue(job)
    assert jid == job.id
    assert q.get(jid).state == "QUEUED"
    assert q.claim(jid, "runner-1") is True
    assert q.get(jid).state == "CLAIMED"
    assert q.get(jid).claimed_by == "runner-1"


def test_job_claim_fails_if_not_queued():
    q = JobQueue()
    job = BrowserJob(site="costco.com", task_type="costco_scan")
    jid = q.enqueue(job)
    q.claim(jid, "runner-1")
    # Can't claim again
    assert q.claim(jid, "runner-2") is False


def test_job_state_transitions():
    q = JobQueue()
    job = BrowserJob(site="costco.com", task_type="costco_scan")
    jid = q.enqueue(job)
    q.claim(jid, "runner-1")
    q.update_state(jid, "RUNNING")
    assert q.get(jid).state == "RUNNING"
    q.update_state(jid, "SUCCEEDED")
    assert q.get(jid).state == "SUCCEEDED"


def test_job_evidence():
    q = JobQueue()
    job = BrowserJob(site="costco.com", task_type="costco_scan")
    jid = q.enqueue(job)
    ev = BrowserEvidence(job_id=jid, url="https://costco.com/p/1", extracted={"title": "Test"})
    q.add_evidence(ev)
    evidence = q.get_evidence(jid)
    assert len(evidence) == 1
    assert evidence[0].extracted["title"] == "Test"


def test_runner_register_adapter():
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner")
    runner = ChromeConnectRunner(cfg, q)
    adapter = SiteAdapter(origin="costco.com", selectors={"title": "h1"})
    runner.register_adapter("costco.com", adapter)
    assert "costco.com" in runner._adapters


def test_runner_register_handler():
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner")
    runner = ChromeConnectRunner(cfg, q)
    def handler(job, runner):
        job.state = "SUCCEEDED"
        return job
    runner.register_handler("custom_task", handler)
    assert "custom_task" in runner._job_handlers


def test_runner_execute_job_with_handler():
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner")
    runner = ChromeConnectRunner(cfg, q)
    def handler(job, runner):
        job.state = "SUCCEEDED"
        job.params["extracted"] = {"title": "Test Product"}
        return job
    runner.register_handler("custom_task", handler)
    job = BrowserJob(site="example.com", task_type="custom_task")
    jid = q.enqueue(job)
    claimed_job = q.get(jid)
    result = runner.execute_job(claimed_job)
    assert result.state == "SUCCEEDED"
    assert runner.state.jobs_completed == 1


def test_runner_execute_job_no_adapter():
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner")
    runner = ChromeConnectRunner(cfg, q)
    job = BrowserJob(site="unknown.com", task_type="unknown_task")
    jid = q.enqueue(job)
    result = runner.execute_job(q.get(jid))
    assert result.state == "FAILED"
    assert "no adapter or handler" in (result.error_reason or "")
    assert runner.state.jobs_failed == 1


def test_runner_domain_lock():
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner")
    runner = ChromeConnectRunner(cfg, q)
    assert runner.acquire_domain_lock("example.com") is True
    assert runner.acquire_domain_lock("example.com") is False
    runner.release_domain_lock("example.com")
    assert runner.acquire_domain_lock("example.com") is True


def test_runner_heartbeat():
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner")
    runner = ChromeConnectRunner(cfg, q)
    hb = runner.heartbeat()
    assert hb["runner_id"] == "test-runner"
    assert hb["timestamp"] is not None
    assert hb["running"] is False


def test_runner_stop_file():
    tmpdir = tempfile.mkdtemp()
    stop_path = os.path.join(tmpdir, "STOP")
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner", stop_file=stop_path)
    runner = ChromeConnectRunner(cfg, q)
    assert runner.is_stopped() is False
    runner.stop()
    assert runner.is_stopped() is True
    assert os.path.exists(stop_path)
    # Cleanup
    if os.path.exists(stop_path):
        os.remove(stop_path)
    import shutil
    shutil.rmtree(tmpdir)


def test_runner_pause():
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner")
    runner = ChromeConnectRunner(cfg, q)
    assert runner.is_paused() is False
    runner.state.paused = True
    assert runner.is_paused() is True


def test_runner_run_once():
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner")
    runner = ChromeConnectRunner(cfg, q)
    def handler(job, runner):
        job.state = "SUCCEEDED"
        return job
    runner.register_handler("test_task", handler)
    job = BrowserJob(site="example.com", task_type="test_task")
    q.enqueue(job)
    executed = runner.run_once()
    assert executed == 1
    assert runner.state.jobs_completed == 1


def test_runner_run_once_stopped():
    tmpdir = tempfile.mkdtemp()
    stop_path = os.path.join(tmpdir, "STOP")
    # Create STOP file
    with open(stop_path, "w") as f:
        f.write("stopped")
    q = JobQueue()
    cfg = RunnerConfig(runner_id="test-runner", stop_file=stop_path)
    runner = ChromeConnectRunner(cfg, q)
    def handler(job, runner):
        job.state = "SUCCEEDED"
        return job
    runner.register_handler("test_task", handler)
    job = BrowserJob(site="example.com", task_type="test_task")
    q.enqueue(job)
    executed = runner.run_once()
    assert executed == 0
    # Cleanup
    os.remove(stop_path)
    import shutil
    shutil.rmtree(tmpdir)


def test_job_stats():
    q = JobQueue()
    q.enqueue(BrowserJob(site="a.com", task_type="t1"))
    q.enqueue(BrowserJob(site="b.com", task_type="t2"))
    j = q.list_by_state("QUEUED")
    q.claim(j[0].id, "r1")
    q.update_state(j[0].id, "SUCCEEDED")
    stats = q.stats()
    assert stats.get("QUEUED", 0) == 1
    assert stats.get("SUCCEEDED", 0) == 1


def test_adapter_result():
    adapter = SiteAdapter(origin="example.com", selectors={"title": "h1"})
    result = adapter.extract("<html><body><h1>Hello</h1></body></html>", url="https://example.com")
    assert result.status == "OK"
    assert result.fields.get("title") == "Hello"
    assert result.confidence == 1.0


def test_adapter_degraded():
    adapter = SiteAdapter(origin="example.com", selectors={"title": "h1", "price": ".price"})
    result = adapter.extract("<html><body><h1>Hello</h1></body></html>", url="https://example.com")
    assert result.status == "DEGRADED"
    assert result.fields.get("price") is None
    assert "missing fields" in result.errors[0]


def test_adapter_from_dict():
    data = {"origin": "example.com", "selectors": {"title": "h1"}, "allowed_tasks": ["read"], "version": "2.0"}
    adapter = SiteAdapter.from_dict(data)
    assert adapter.origin == "example.com"
    assert adapter.selectors == {"title": "h1"}
    assert adapter.version == "2.0"


def test_evidence_make_field():
    from evidence import make_field_evidence
    fe = make_field_evidence("title", "My Title", "https://example.com", confidence=0.9)
    assert fe.status == "OK"
    assert fe.value == "My Title"
    assert fe.confidence == 0.9


def test_evidence_make_unknown():
    from evidence import make_field_evidence
    fe = make_field_evidence("price", None, "https://example.com")
    assert fe.status == "UNKNOWN"
    assert fe.value is None


def test_evidence_extraction():
    from evidence import make_extraction_evidence, make_field_evidence
    fields = [
        make_field_evidence("title", "Test", "https://example.com"),
        make_field_evidence("price", None, "https://example.com"),
    ]
    ev = make_extraction_evidence("job-1", "https://example.com", fields)
    assert ev.status == "PARTIAL"
    assert not ev.all_ok
    assert ev.has_unknown
