"""Tests for tools/creative_audit.py — the audit must not inflate its own numbers.

The first draft flagged 673 "missing timeout" findings that were all `Request(...)`
constructors and dict `.get()` calls. These tests pin the false-positive guards so
the backlog stays trustworthy.
"""

from __future__ import annotations

import ast
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import creative_audit as ca  # noqa: E402


def _call(src: str) -> ast.Call:
    return next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.Call))


def test_dict_get_is_not_a_network_call():
    assert ca._is_network_call(_call("x = headers.get('k')")) is False
    assert ca._is_network_call(_call("x = mapping.get('k', 0)")) is False


def test_request_constructor_is_not_a_network_call():
    # The timeout belongs to urlopen(req, timeout=...), not to Request(...).
    assert ca._is_network_call(_call("urllib.request.Request(url, data=b'')")) is False


def test_real_network_calls_are_detected():
    assert ca._is_network_call(_call("urllib.request.urlopen(req, timeout=5)")) is True
    assert ca._is_network_call(_call("requests.get(url, timeout=5)")) is True
    assert ca._is_network_call(_call("httpx.post(url, json={})")) is True


def test_dotted_resolves_attribute_chains():
    node = _call("urllib.request.urlopen(req)")
    assert ca._dotted(node.func) == "urllib.request.urlopen"


def test_main_block_ranges_cover_cli_code():
    tree = ast.parse("def main():\n    print('x')\n\nif __name__ == '__main__':\n    main()\n")
    ranges = ca._main_block_ranges(tree)
    assert ranges and all(lo <= hi for lo, hi in ranges)
    assert ca._in_ranges(1, ranges) and ca._in_ranges(5, ranges)


def test_silent_handler_detection():
    src = (
        "try:\n    x = 1\nexcept Exception:\n    pass\n"
        "try:\n    y = 2\nexcept Exception:\n    raise\n"
    )
    handlers = [n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ExceptHandler)]
    assert ca._silent(handlers[0], src) is True
    assert ca._silent(handlers[1], src) is False


def test_documented_swallow_is_reviewed_not_flagged():
    """A stated reason counts; a bare noqa does not."""
    src = "try:\n    x = 1\nexcept Exception:  # noqa: BLE001 - probe only\n    pass\n"
    handler = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ExceptHandler))
    line = "except Exception:  # noqa: BLE001 - probe only"
    assert ca._silent(handler, src, line) is False


def test_bare_noqa_does_not_excuse_a_swallow():
    src = "try:\n    x = 1\nexcept Exception:  # noqa: BLE001\n    pass\n"
    handler = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.ExceptHandler))
    assert ca._silent(handler, src, "except Exception:  # noqa: BLE001") is True


def test_audit_output_shape_and_unique_ids():
    findings = ca.audit()
    assert findings, "audit found nothing at all - that would be suspicious"
    ids = [f["id"] for f in findings]
    assert len(ids) == len(set(ids)), "duplicate finding ids"
    for f in findings:
        assert set(f) >= {"id", "code", "severity", "file", "line", "evidence", "detail"}
        assert f["file"].startswith("Northstar_backend/")
        assert f["severity"] in ("high", "medium", "low")


def test_every_finding_code_is_declared():
    declared = set(ca.SEVERITY)
    produced = {f["code"] for f in ca.audit()}
    assert produced <= declared, f"undeclared codes: {produced - declared}"


def test_summary_counts_match_findings():
    findings = ca.audit()
    counts = ca.summary(findings)
    assert sum(counts.values()) == len(findings)
