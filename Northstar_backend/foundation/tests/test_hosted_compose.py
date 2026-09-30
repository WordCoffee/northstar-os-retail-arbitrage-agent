"""DEPLOY-F1 safety verification: resolved hosted configuration.

Asserts the merged (docker-compose.yml + docker-compose.hosted.yml) configuration
publishes public ports ONLY for Caddy, and that hosted staging keeps its
fail-closed guardrails. Never prints resolved secret values.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "docker-compose.yml"
HOSTED = ROOT / "docker-compose.hosted.yml"
ENVEX = ROOT / "deploy" / "hosted.env.example"

_DOCKER = shutil.which("docker") is not None


def _resolve():
    cmd = ["docker", "compose", "-f", str(BASE), "-f", str(HOSTED),
           "--env-file", str(ENVEX), "config", "--format", "json"]
    out = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=180)
    assert out.returncode == 0, "compose config failed"
    return json.loads(out.stdout)


@pytest.mark.skipif(not _DOCKER, reason="docker not available")
def test_only_caddy_publishes_public_ports():
    cfg = _resolve()
    svcs = cfg["services"]
    for name, svc in svcs.items():
        pubs = [p.get("published") for p in (svc.get("ports") or [])]
        if name == "caddy":
            assert set(pubs) == {"80", "443"}, pubs
        else:
            assert pubs == [], f"{name} must not publish host ports: {pubs}"
    all_pubs = {p.get("published") for s in svcs.values() for p in (s.get("ports") or [])}
    for forbidden in ("5432", "8000", "2375", "2376"):
        assert forbidden not in all_pubs


@pytest.mark.skipif(not _DOCKER, reason="docker not available")
def test_hosted_guardrails_present_no_local_dev():
    cfg = _resolve()
    env = {k: ("" if v is None else str(v))
           for k, v in (cfg["services"]["api"].get("environment") or {}).items()}
    assert env.get("ENVIRONMENT") == "staging"
    assert env.get("NS_FOUNDATION_ALLOW_REMOTE_DEV", "").lower() in ("0", "false")
    assert env.get("NORTHSTAR_OWNER_TEST_MODE", "").lower() in ("0", "false")
    assert env.get("NORTHSTAR_OWNER_SELF_APPROVAL", "").lower() in ("0", "false")


def test_hosted_override_file_declares_guardrails():
    body = HOSTED.read_text(encoding="utf-8")
    assert "ENVIRONMENT: staging" in body
    assert "NS_FOUNDATION_ALLOW_REMOTE_DEV" in body
    assert "NORTHSTAR_OWNER_TEST_MODE" in body
    assert "5432:" not in body.replace(" ", "")  # does not publish the DB port