"""Async generation lane tests — credit reserve/commit/release + job lifecycle.

RE build 2026-10-16. Everything runs against fakes: no ComfyUI, no dev DB,
no thread pool, no paid providers.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import design_studio_async as dsa  # noqa: E402
from credit_ledger import CreditLedger, InsufficientCredits  # noqa: E402


def _ledger(tmp_path) -> CreditLedger:
    return CreditLedger(path=str(tmp_path / "led.jsonl"))


class _JobsStore:
    def __init__(self):
        self.updates = []
        self.created = None

    def create(self, data):
        self.created = dict(data)
        return "job-test"

    def get_by_id(self, job_id, account_id=None):
        return {"id": job_id, "status": "queued", "account_id": account_id}

    def update(self, job_id, patch, account_id=None):
        self.updates.append((job_id, {**patch, "account_id": account_id}))


class _AssetsStore:
    def __init__(self):
        self.created = []

    def create(self, data):
        self.created.append(data)
        return "aid-test"


class _DS:
    def __init__(self):
        self.jobs = _JobsStore()
        self.assets = _AssetsStore()


class _DB:
    def __init__(self):
        self.design_studio = _DS()


# ── ledger mechanics ────────────────────────────────────────────────────────

def test_initial_grant_is_idempotent_and_aligns_with_plan_allotment(tmp_path):
    led = _ledger(tmp_path)
    dsa.ensure_initial_grant(led, "org-a")
    first = led.balance("org-a")
    assert first > 0
    dsa.ensure_initial_grant(led, "org-a")
    assert led.balance("org-a") == first  # deduped by idempotency key


def test_reserve_commit_and_release_balances(tmp_path):
    led = _ledger(tmp_path)
    dsa.ensure_initial_grant(led, "org-a")
    start = led.balance("org-a")

    res = led.reserve("org-a", 3, action="design_studio.image", idempotency_key="r1")
    assert led.balance("org-a") == start - 3
    led.commit(res.reservation_id, idempotency_key="c1")
    assert led.balance("org-a") == start - 3  # a commit keeps the charge

    res2 = led.reserve("org-a", 2, action="design_studio.image", idempotency_key="r2")
    led.release(res2.reservation_id, idempotency_key="rel2")
    assert led.balance("org-a") == start - 3  # release restores the hold


def test_reserve_fails_closed_when_balance_short(tmp_path):
    led = _ledger(tmp_path)
    with pytest.raises(InsufficientCredits):
        led.reserve("org-broke", 1, action="design_studio.image")


# ── job lifecycle ───────────────────────────────────────────────────────────

def test_run_generation_job_success_commits_and_records_asset(tmp_path, monkeypatch):
    import studio_generation as sg

    monkeypatch.setattr(sg, "generate_image", lambda **kw: {
        "bytes": b"fake-png-bytes", "ext": "png", "mime": "image/png",
        "model": "test-model", "width": 64, "height": 64, "seed": 7,
    })

    led = _ledger(tmp_path)
    dsa.ensure_initial_grant(led, "org-a")
    start = led.balance("org-a")
    res = led.reserve("org-a", 1, action="design_studio.image", idempotency_key="r3")

    db = _DB()
    out = dsa.run_generation_job(
        job_id="job-1", acct="org-a",
        body={"kind": "image", "brief": "test brief", "tier": "draft"},
        reservation_id=res.reservation_id, enforce=True, db=db, ledger=led, out_dir=tmp_path,
    )

    assert out["status"] == "done" and out["asset_id"] == "aid-test"
    assert led.balance("org-a") == start - 1
    assert any(e["kind"] == "commit" for e in led.entries())
    stored = db.design_studio.assets.created[0]
    assert (tmp_path / stored["storage_key"]).is_file()
    assert stored["metadata"]["generation"]["lane"] == "async"
    assert db.design_studio.jobs.updates[-1][1]["status"] == "done"


def test_run_generation_job_failure_releases_reservation(tmp_path, monkeypatch):
    import studio_generation as sg

    def boom(**kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(sg, "generate_image", boom)

    led = _ledger(tmp_path)
    dsa.ensure_initial_grant(led, "org-a")
    start = led.balance("org-a")
    res = led.reserve("org-a", 1, action="design_studio.image", idempotency_key="r4")

    db = _DB()
    out = dsa.run_generation_job(
        job_id="job-2", acct="org-a",
        body={"kind": "image", "brief": "fail brief"},
        reservation_id=res.reservation_id, enforce=True, db=db, ledger=led, out_dir=tmp_path,
    )

    assert out["status"] == "failed" and "boom" in out["error"]
    assert led.balance("org-a") == start  # released
    assert any(e["kind"] == "release" for e in led.entries())
    failed = db.design_studio.jobs.updates[-1][1]
    assert failed["status"] == "failed" and failed["credits_used"] == 0


# ── callback_url is an SSRF surface, not a convenience ──────────────────────
#
# `case` below returns the reason token the refusal must name, so a refusal for
# the wrong reason (e.g. "unparseable" instead of "loopback") cannot pass.

@pytest.mark.parametrize("url,reason", [
    ("https://www.amazon.com/dp/X", "amazon_host"),
    ("https://amzn.eu/d/x", "amazon_host"),
    ("http://127.0.0.1:8080/hook", "loopback_ip"),
    ("http://[::1]/hook", "loopback_ip"),
    ("http://localhost/hook", "loopback_host"),
    ("http://api.localhost/hook", "loopback_host"),
    ("http://169.254.169.254/latest/meta-data/", "link_local_ip"),
    ("http://10.0.0.5/hook", "private_ip"),
    ("http://0.0.0.0/hook", "unspecified_ip"),
    ("http://2130706433/hook", "numeric_host"),      # integer form of 127.0.0.1
    ("http://127.1/hook", "numeric_host"),           # short form of 127.0.0.1
    ("file:///etc/passwd", "scheme_file"),
    ("ftp://example.com/hook", "scheme_ftp"),
    ("http:///hook", "missing_host"),
    ("http://user:pw@example.com/hook", "credentials_in_url"),
    ("", "empty_url"),
])
def test_malicious_callback_urls_are_refused_with_a_reason(url, reason):
    with pytest.raises(dsa.CallbackRefused) as ei:
        dsa.validate_callback_url(url)
    assert reason in str(ei.value)


@pytest.mark.parametrize("url", [
    "https://hooks.example.com/northstar/job",
    "http://example.com:8080/cb",
    "https://api.example.co.uk/webhook?x=1",
])
def test_named_host_callbacks_still_pass(url):
    assert dsa.validate_callback_url(url) == url


def test_refusal_happens_before_any_request_is_made():
    """The regression this item exists for: no socket, no opener call, no retry loop."""
    calls = {"n": 0}

    def counting_opener(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("a refused callback must never reach the transport")

    with pytest.raises(dsa.CallbackRefused):
        dsa.deliver_webhook("http://127.0.0.1:9/hook", {"job_id": "j1"},
                            opener=counting_opener)
    assert calls["n"] == 0


def test_loopback_needs_an_explicit_opt_in_and_link_local_is_still_refused(monkeypatch):
    monkeypatch.setenv(dsa.CALLBACK_ALLOW_LOOPBACK_ENV, "1")
    assert dsa.validate_callback_url("http://127.0.0.1:8765/hook")
    assert dsa.validate_callback_url("http://localhost:8765/hook")
    with pytest.raises(dsa.CallbackRefused) as ei:
        dsa.validate_callback_url("http://169.254.169.254/latest/meta-data/")
    assert "link_local_ip" in str(ei.value)


def test_operator_allowlist_can_pin_the_callback_hosts(monkeypatch):
    monkeypatch.setenv(dsa.CALLBACK_ALLOW_HOSTS_ENV, "hooks.example.com")
    assert dsa.validate_callback_url("https://hooks.example.com/x")
    assert dsa.validate_callback_url("https://eu.hooks.example.com/x")
    with pytest.raises(dsa.CallbackRefused) as ei:
        dsa.validate_callback_url("https://evil.test/x")
    assert "host_not_allowed" in str(ei.value)


def test_submit_generation_refuses_a_malicious_callback_before_creating_a_job(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(dsa, "_engine_status", lambda: {"armed": True, "note": "test"})
    monkeypatch.setattr(dsa, "credits_enforced", lambda: False)
    db = _DB()
    monkeypatch.setattr(dsa, "get_northstar_db", lambda: db)

    class _InlineExecutor:
        def __init__(self):
            self.calls = []

        def submit(self, fn, **kw):
            self.calls.append((fn, kw))

    ex = _InlineExecutor()
    monkeypatch.setattr(dsa, "_EXECUTOR", ex)

    with pytest.raises(HTTPException) as ei:
        dsa.submit_generation("org-a", brief="ssrf me",
                              callback_url="http://169.254.169.254/latest/meta-data/")
    assert ei.value.status_code == 422
    assert ei.value.detail["code"] == "callback_url_refused"
    assert db.design_studio.jobs.created is None
    assert ex.calls == []


def test_a_refused_callback_is_recorded_on_the_job_and_never_fails_it(monkeypatch, tmp_path):
    import studio_generation as sg

    monkeypatch.setattr(sg, "generate_image", lambda **kw: {
        "bytes": b"fake-png-bytes", "ext": "png", "mime": "image/png",
        "model": "test-model", "width": 64, "height": 64, "seed": 7,
    })

    def counting_opener(*_a, **_k):
        raise AssertionError("a refused callback must never reach the transport")

    monkeypatch.setattr(dsa.urllib.request, "urlopen", counting_opener)

    db = _DB()
    out = dsa.run_generation_job(
        job_id="job-cb", acct="org-a",
        body={"kind": "image", "brief": "with a bad callback",
              "callback_url": "https://www.amazon.com/dp/X"},
        db=db, ledger=None, out_dir=tmp_path,
    )
    assert out["status"] == "done"          # the artifact is what the job is for
    webhook = None
    for _job_id, patch in db.design_studio.jobs.updates:
        if "params" in patch and "webhook" in patch["params"]:
            webhook = patch["params"]["webhook"]
    assert webhook is not None and webhook["refused"] is True
    assert webhook["attempts"] == 0 and "amazon_host" in webhook["error"]


# ── API gates + scheduling ──────────────────────────────────────────────────

def test_submit_generation_refuses_unarmed_engine(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(dsa, "_engine_status", lambda: {"armed": False, "note": "test"})
    with pytest.raises(HTTPException) as ei:
        dsa.submit_generation("org-a", brief="hello")
    assert ei.value.status_code == 409


def test_submit_generation_queues_without_charging_in_meter_mode(monkeypatch):
    monkeypatch.setattr(dsa, "_engine_status", lambda: {"armed": True, "note": "test"})
    monkeypatch.setattr(dsa, "credits_enforced", lambda: False)
    db = _DB()

    class _CaptureJobs(_JobsStore):
        def get_by_id(self, job_id, account_id=None):
            return {"id": job_id, "status": "queued", "credits_used": self.created["credits_used"]}

    db.design_studio.jobs = _CaptureJobs()
    monkeypatch.setattr(dsa, "get_northstar_db", lambda: db)

    class _InlineExecutor:
        def __init__(self):
            self.calls = []

        def submit(self, fn, **kw):
            self.calls.append((fn, kw))
            return None

    ex = _InlineExecutor()
    monkeypatch.setattr(dsa, "_EXECUTOR", ex)

    out = dsa.submit_generation("org-a", brief="queue me", kind="image")
    assert out["enforce"] is False
    assert out["reservation"] is None
    assert out["job"]["status"] == "queued"
    assert out["job"]["credits_used"] == 0  # meter-only alpha: nothing deducted
    assert db.design_studio.jobs.created["cost_preview"]["credits"] == dsa._costs()["image"]
    assert ex.calls and ex.calls[0][1]["job_id"] == "job-test"


def test_submit_generation_enforced_reserves_credits(monkeypatch, tmp_path):
    monkeypatch.setattr(dsa, "_engine_status", lambda: {"armed": True, "note": "test"})
    monkeypatch.setattr(dsa, "credits_enforced", lambda: True)
    led = _ledger(tmp_path)
    monkeypatch.setattr(dsa, "get_ledger", lambda: led)
    db = _DB()

    class _CaptureJobs(_JobsStore):
        def get_by_id(self, job_id, account_id=None):
            return {"id": job_id, "status": "queued", "credits_used": self.created["credits_used"]}

    db.design_studio.jobs = _CaptureJobs()
    monkeypatch.setattr(dsa, "get_northstar_db", lambda: db)

    class _InlineExecutor:
        def submit(self, fn, **kw):
            return None

    monkeypatch.setattr(dsa, "_EXECUTOR", _InlineExecutor())

    dsa.ensure_initial_grant(led, "org-a")
    start = led.balance("org-a")
    out = dsa.submit_generation("org-a", brief="charge me", kind="image")
    assert out["enforce"] is True
    assert out["reservation"]["amount"] == dsa._costs()["image"]
    assert led.balance("org-a") == start - dsa._costs()["image"]
    assert out["job"]["credits_used"] == dsa._costs()["image"]
