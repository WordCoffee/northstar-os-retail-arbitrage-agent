"""Self-healing: scope extraction, AST diagnosis, sandboxed verification."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_kernel import self_heal as sh

BUGGY = '''"""Buggy module."""
VALUE = 1


def add(a, b):
    """Add two numbers."""
    return a - b


def caller():
    return add(2, 3)
'''


def _module(tmp_path) -> Path:
    path = tmp_path / "buggy.py"
    path.write_text(BUGGY, encoding="utf-8")
    return path


def _traceback(path: Path) -> str:
    return (
        'Traceback (most recent call last):\n'
        f'  File "{path}", line 12, in caller\n'
        '    return add(2, 3)\n'
        f'  File "{path}", line 7, in add\n'
        '    return a - b\n'
        'TypeError: unsupported operand\n'
    )


def _reasoner(_brief):
    return json.dumps({
        "explanation": "subtraction should be addition",
        "edits": [{"op": "replace_function_body", "target": "add",
                   "source": "return a + b"}],
    })


def test_scope_extraction_finds_the_innermost_function(tmp_path):
    path = _module(tmp_path)
    scope = sh.scope_from_traceback(_traceback(path), tmp_path)
    assert scope.qualname == "add"
    assert scope.node_type == "FunctionDef"
    assert "return a - b" in scope.source
    assert scope.line == 7


def test_scope_extraction_refuses_a_frame_outside_the_root(tmp_path):
    outside = tmp_path.parent / "outside.py"
    outside.write_text("def f():\n    return 1\n", encoding="utf-8")
    with pytest.raises(sh.SelfHealError):
        sh.scope_from_traceback(_traceback(outside), tmp_path)


def test_diagnose_validates_the_ast_edit(tmp_path):
    path = _module(tmp_path)
    scope = sh.scope_from_traceback(_traceback(path), tmp_path)
    plan = sh.diagnose(scope, _traceback(path), reasoner=_reasoner)
    assert plan["edits"][0]["op"] == "replace_function_body"
    assert "addition" in plan["explanation"]


def test_diagnose_refuses_an_edit_that_does_not_apply(tmp_path):
    path = _module(tmp_path)
    scope = sh.scope_from_traceback(_traceback(path), tmp_path)
    with pytest.raises(sh.SelfHealError):
        sh.diagnose(scope, _traceback(path),
                    reasoner=lambda _b: json.dumps(
                        {"edits": [{"op": "delete", "target": "missing"}]}))


def test_heal_proposes_without_writing(tmp_path):
    path = _module(tmp_path)
    plan = sh.heal(_traceback(path), root=tmp_path, reasoner=_reasoner)
    assert plan["applied"] is False
    assert "-    return a - b" in plan["diff"]
    assert "+    return a + b" in plan["diff"]
    assert "return a - b" in path.read_text(encoding="utf-8")


def test_heal_applies_after_a_passing_verification(tmp_path):
    path = _module(tmp_path)
    plan = sh.heal(_traceback(path), root=tmp_path, reasoner=_reasoner,
                   verify_cmd=[sys.executable, "-c",
                               "import buggy; assert buggy.add(2, 3) == 5"],
                   apply=True, require_isolation=False)
    assert plan["verified"] is True and plan["applied"] is True
    assert "return a + b" in path.read_text(encoding="utf-8")


def test_heal_restores_the_file_when_verification_fails(tmp_path):
    path = _module(tmp_path)
    before = path.read_bytes()
    plan = sh.heal(_traceback(path), root=tmp_path, reasoner=_reasoner,
                   verify_cmd=[sys.executable, "-c", "raise SystemExit(1)"],
                   apply=True, require_isolation=False)
    assert plan["verified"] is False
    assert plan.get("restored") is True
    assert path.read_bytes() == before


def test_heal_requires_an_approved_hitl_request(tmp_path):
    from agent_kernel import hitl
    path = _module(tmp_path)
    req = hitl.request("apply_self_patch", root=tmp_path)
    with pytest.raises(hitl.ApprovalRequired):
        sh.heal(_traceback(path), root=tmp_path, reasoner=_reasoner,
                verify_cmd=[sys.executable, "-c",
                            "import buggy; assert buggy.add(2, 3) == 5"],
                apply=True, require_isolation=False, approval_id=req["id"])
    hitl.approve(tmp_path, req["id"], "operator")
    plan = sh.heal(_traceback(path), root=tmp_path, reasoner=_reasoner,
                   verify_cmd=[sys.executable, "-c",
                               "import buggy; assert buggy.add(2, 3) == 5"],
                   apply=True, require_isolation=False, approval_id=req["id"])
    assert plan["applied"] is True


def test_local_reasoner_reads_the_local_lane(monkeypatch):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    import lane_policy

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(length)
            content = json.dumps({"explanation": "x", "edits": [
                {"op": "replace_function_body", "target": "add",
                 "source": "return a + b"}]})
            body = json.dumps({"choices": [{"message": {"content": content}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setattr(lane_policy, "route",
                        lambda *a, **k: {"lane": "northstaros-27b-coder"})
    try:
        text = sh.local_reasoner({"scope": "def add(): pass"},
                                 url=f"http://127.0.0.1:{server.server_address[1]}/v1",
                                 timeout=5)
    finally:
        server.shutdown()
    assert "replace_function_body" in text


def test_bad_reasoner_json_is_refused(tmp_path):
    path = _module(tmp_path)
    with pytest.raises(sh.SelfHealError):
        sh.heal(_traceback(path), root=tmp_path,
                reasoner=lambda _b: "not json")
