"""Sandbox: credential scrubbing, process execution, isolation audit."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_kernel import sandbox as sb


def test_scrub_env_removes_secret_shaped_names():
    env = {"PATH": "x", "HOME": "h", "OPENAI_API_KEY": "sk-secret",
           "AWS_SECRET_ACCESS_KEY": "aws", "DB_PASSWORD": "pw",
           "NORTHSTAR_MODEL": "qwen"}
    out = sb.scrub_env(env)
    assert out["PATH"] == "x" and out["HOME"] == "h"
    assert "OPENAI_API_KEY" not in out
    assert "AWS_SECRET_ACCESS_KEY" not in out
    assert "DB_PASSWORD" not in out
    assert "NORTHSTAR_MODEL" not in out       # not on the allowlist


def test_scrub_env_allows_an_explicit_consumer_token():
    out = sb.scrub_env({"PATH": "x", "CONSUMER_TOKEN": "temp"},
                       allow={"CONSUMER_TOKEN"})
    assert out["CONSUMER_TOKEN"] == "temp"


def test_process_runtime_never_sees_the_secret(tmp_path):
    script = "import os; print(os.environ.get('OPENAI_API_KEY', 'missing'))"
    out = sb.run([sys.executable, "-c", script], cwd=tmp_path,
                 runtime="process", env={"OPENAI_API_KEY": "sk-secret",
                                         "PATH": __import__("os").environ.get("PATH", "")})
    assert out["ok"] is True, out
    assert "missing" in out["output"]
    assert "sk-secret" not in out["output"]


def test_process_runtime_reports_a_timeout(tmp_path):
    out = sb.run([sys.executable, "-c", "import time; time.sleep(3)"],
                 cwd=tmp_path, runtime="process", timeout=0.5)
    assert out["ok"] is False
    assert out["timeout"] is True


def test_require_isolated_refuses_the_process_fallback(monkeypatch):
    monkeypatch.setattr(sb, "detect_runtimes",
                        lambda: {"docker": False, "bubblewrap": False, "process": True})
    with pytest.raises(sb.SandboxUnavailable):
        sb.require_isolated()


def test_audit_reports_whether_isolation_is_real(monkeypatch):
    monkeypatch.setattr(sb, "detect_runtimes",
                        lambda: {"docker": True, "bubblewrap": False, "process": True})
    a = sb.audit()
    assert a["chosen"] == "docker"
    assert a["production_safe"] is True
    assert "note" in a
