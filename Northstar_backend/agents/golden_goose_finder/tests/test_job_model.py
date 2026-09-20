"""B7 tests — Golden Goose job model (opaque ids + state lifecycle)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from agents.golden_goose_finder import job_model as jm  # noqa: E402


def test_job_id_is_opaque():
    jid = jm.new_job_id()
    assert jid.startswith("job_")
    assert re.fullmatch(r"job_[0-9a-f]{32}", jid)
    assert jm.new_job_id() != jm.new_job_id()  # random, not sequential


def test_scan_id_is_distinct_and_prefixed():
    sid = jm.new_scan_id()
    assert sid.startswith("scan_")
    assert sid != jm.new_job_id()


def test_registry_create_get_and_missing_fails_closed():
    reg = jm.GooseJobRegistry()
    job = reg.create(jm.OPERATION_SCAN)
    assert reg.get(job.job_id) is job
    with pytest.raises(KeyError):
        reg.get("job_does_not_exist")


def test_unknown_operation_rejected():
    reg = jm.GooseJobRegistry()
    with pytest.raises(ValueError):
        reg.create("goose.live_scan")


def test_legal_lifecycle_queued_running_done():
    job = jm.GooseJob(job_id=jm.new_job_id())
    assert job.state == jm.QUEUED
    job.transition(jm.RUNNING, progress_pct=40)
    assert job.state == jm.RUNNING and job.progress_pct == 40
    job.transition(jm.DONE)
    assert job.state == jm.DONE
    assert job.progress_pct == 100
    assert job.result_ref and job.result_ref.startswith("res_")


def test_illegal_transition_raises():
    job = jm.GooseJob(job_id=jm.new_job_id())
    with pytest.raises(jm.JobTransitionError):
        job.transition(jm.DONE)  # queued -> done is illegal
    job.transition(jm.RUNNING)
    job.transition(jm.FAILED)
    with pytest.raises(jm.JobTransitionError):
        job.transition(jm.RUNNING)  # terminal


def test_failed_carries_bff_error_and_clears_progress():
    job = jm.GooseJob(job_id=jm.new_job_id())
    job.transition(jm.RUNNING)
    job.transition(jm.FAILED)
    assert job.progress_pct is None
    assert set(job.error) == {"code", "message", "retryable"}
    assert job.error["code"] in ("internal_error",)


def test_public_view_hides_scan_id_and_internal_notes():
    job = jm.GooseJob(job_id=jm.new_job_id())
    view = job.public_view()
    assert "scan_id" not in view
    assert "internal_notes" not in view
    assert view["job_id"] == job.job_id
    assert view["service"] == "golden_goose"
    assert set(view) == {
        "job_id", "service", "operation", "state", "created_at", "updated_at",
        "progress_pct", "result_ref", "error", "links",
    }


def test_public_view_never_leaks_provider_tokens():
    job = jm.GooseJob(job_id=jm.new_job_id())
    text = str(job.public_view()).lower()
    for tok in ("brightdata", "chocodata", "easyparser", "openwebninja", "cost_formula"):
        assert tok not in text