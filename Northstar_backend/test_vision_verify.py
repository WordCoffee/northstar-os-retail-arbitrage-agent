"""Ty's Vision: a pass only on a parseable, explicit verdict; unavailable is a fail."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

from agent_kernel import vision_verify  # noqa: E402


def test_a_clean_json_verdict_passes():
    result = vision_verify.verify(
        b"png", "a pouch with a readable wordmark",
        caller=lambda image, constraint: '{"pass": true, "reasons": [], "confidence": 0.9}')
    assert result["ok"] is True and result["available"] is True


def test_a_fenced_json_verdict_is_parsed():
    result = vision_verify.verify(
        b"png", "a pouch",
        caller=lambda image, constraint: '```json\n{"pass": false, "reasons": ["no pouch"]}\n```')
    assert result["ok"] is False
    assert result["available"] is True
    assert result["reasons"] == ["no pouch"]


def test_a_degenerate_answer_is_unavailable_not_a_pass():
    result = vision_verify.verify(
        b"png", "a pouch",
        caller=lambda image, constraint: "The\n")
    assert result["ok"] is False
    assert result["pass"] is None
    assert result["available"] is False


def test_a_runner_error_is_unavailable():
    def _boom(image, constraint):
        raise RuntimeError("ollama down")

    result = vision_verify.verify(b"png", "a pouch", caller=_boom)
    assert result["ok"] is False and result["available"] is False
    assert "ollama down" in result["reason"]
