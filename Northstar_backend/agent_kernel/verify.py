"""Verification — the only route to `done`.

A verifier returns pass, fail or unknown. Unknown is never upgraded to pass. The
built-ins cover the four lanes: files, commands, creative artefacts and browser
page state (the last via an injected callable, because the live browser belongs to
Chrome Connect).
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .model import Acceptance, Evidence

Verifier = Callable[[Dict[str, Any]], Dict[str, Any]]


@dataclass
class VerifyContext:
    session_id: str
    node_id: str


class VerifierRegistry:
    def __init__(self):
        self._registry: Dict[str, Verifier] = {}
        self.register("file_hash", _file_hash)
        self.register("file_contains", _file_contains)
        self.register("artifact_exists", _artifact_exists)
        self.register("file_min_bytes", _file_min_bytes)
        self.register("command", _command)
        self.register("ocr_contains", _ocr_contains)
        self.register("prepress_printable", _prepress_printable)
        self.register("readiness", _readiness)
        self.register("executor_ok", _executor_ok)
        self.register("plan_complete", _plan_complete)
        self.register("label_valid", _label_valid)
        self.register("ad_valid", _ad_valid)
        self.register("patch_valid", _patch_valid)
        self.register("json_valid", _json_valid)
        self.register("text_valid", _text_valid)
        self.register("social_valid", _social_valid)
        self.register("aplus_valid", _aplus_valid)

    def register(self, name: str, fn: Verifier) -> None:
        self._registry[name] = fn

    def names(self) -> list[str]:
        return sorted(self._registry)

    def verify(self, acceptance: Acceptance, ctx: VerifyContext) -> Evidence:
        fn = self._registry.get(acceptance.verifier)
        if fn is None:
            return Evidence(_eid(), ctx.session_id, ctx.node_id, "unknown",
                            acceptance.text, acceptance.verifier, "unknown",
                            detail=f"no verifier named {acceptance.verifier!r}")
        try:
            out = fn(dict(acceptance.params)) or {}
        except Exception as exc:  # noqa: BLE001 - a broken verifier is unknown
            return Evidence(_eid(), ctx.session_id, ctx.node_id, "unknown",
                            acceptance.text, acceptance.verifier, "unknown",
                            detail=f"verifier error: {str(exc)[:200]}")
        result = str(out.get("result") or "unknown")
        if result not in ("pass", "fail", "unknown"):
            result = "unknown"
        return Evidence(_eid(), ctx.session_id, ctx.node_id,
                        str(out.get("kind") or acceptance.verifier),
                        acceptance.text, acceptance.verifier, result,
                        path=out.get("path"), sha256=out.get("sha256"),
                        detail=str(out.get("detail") or "")[:400])


def _eid() -> str:
    return "ev_" + uuid.uuid4().hex[:12]


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_hash(p: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(str(p.get("path") or ""))
    if not path.is_file():
        return {"result": "fail", "detail": "file missing", "path": str(path)}
    digest = _sha(path)
    want = str(p.get("sha256") or "")
    ok = not want or digest == want
    return {"result": "pass" if ok else "fail", "path": str(path),
            "sha256": digest, "detail": "hash matches" if ok else "hash mismatch"}


def _file_contains(p: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(str(p.get("path") or ""))
    if not path.is_file():
        return {"result": "fail", "detail": "file missing", "path": str(path)}
    text = path.read_text(encoding="utf-8", errors="replace")
    needle = str(p.get("text") or "")
    ok = needle in text if needle else False
    return {"result": "pass" if ok else "fail", "path": str(path),
            "sha256": _sha(path),
            "detail": f"{'found' if ok else 'missing'} {needle[:80]!r}"}


def _artifact_exists(p: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(str(p.get("path") or ""))
    ok = path.is_file() and path.stat().st_size > 0
    return {"result": "pass" if ok else "fail", "path": str(path),
            "sha256": _sha(path) if ok else None,
            "detail": "artifact present" if ok else "artifact missing or empty"}


def _file_min_bytes(p: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(str(p.get("path") or ""))
    if not path.is_file():
        return {"result": "fail", "detail": "file missing", "path": str(path)}
    size = path.stat().st_size
    floor = int(p.get("min_bytes") or 1)
    ok = size >= floor
    return {"result": "pass" if ok else "fail", "path": str(path),
            "sha256": _sha(path),
            "detail": f"{size} bytes (floor {floor})"}


def _command(p: Dict[str, Any]) -> Dict[str, Any]:
    cmd = p.get("cmd")
    if not cmd:
        return {"result": "unknown", "detail": "no command supplied"}
    if isinstance(cmd, str):
        cmd = [cmd]
    timeout = float(p.get("timeout_s") or 120)
    try:
        r = subprocess.run([str(c) for c in cmd], cwd=p.get("cwd"),
                           capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"result": "unknown", "detail": f"timeout after {timeout}s"}
    expect = int(p.get("expect_exit", 0))
    ok = r.returncode == expect
    return {"result": "pass" if ok else "fail", "kind": "command",
            "detail": f"exit={r.returncode} expect={expect}; "
                      f"{(r.stdout or r.stderr or '')[-300:]}"}


def _ocr_contains(p: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(str(p.get("path") or ""))
    if not path.is_file():
        return {"result": "fail", "detail": "artifact missing", "path": str(path)}
    try:
        import text_fidelity as tf  # local import; the module may be absent
    except Exception:  # noqa: BLE001
        return {"result": "unknown", "detail": "text_fidelity unavailable"}
    check = tf.check_text_in_image(path.read_bytes())
    if check.get("status") != "ok":
        return {"result": "unknown", "detail": str(check.get("error") or "OCR unavailable")}
    words = " ".join(check.get("words") or []).lower()
    terms = [str(t).lower() for t in (p.get("terms") or [])]
    missing = [t for t in terms if t not in words]
    return {"result": "pass" if not missing else "fail",
            "kind": "ocr", "path": str(path),
            "detail": f"missing={missing}" if missing else "all terms read"}


def _prepress_printable(p: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(str(p.get("path") or ""))
    if not path.is_file():
        return {"result": "fail", "detail": "artwork missing", "path": str(path)}
    try:
        import package_readiness as pr
    except Exception:  # noqa: BLE001
        return {"result": "unknown", "detail": "package_readiness unavailable"}
    rep = pr.assess_prepress(path.read_bytes())
    if not rep.get("assessed"):
        return {"result": "unknown", "detail": str(rep.get("reason") or "not assessed")}
    return {"result": "pass" if rep.get("verdict") == "printable" else "fail",
            "kind": "prepress", "path": str(path),
            "detail": str(rep.get("verdict"))}


def _readiness(p: Dict[str, Any]) -> Dict[str, Any]:
    path = Path(str(p.get("path") or ""))
    if not path.is_file():
        return {"result": "fail", "detail": "artwork missing", "path": str(path)}
    try:
        import package_readiness as pr
    except Exception:  # noqa: BLE001
        return {"result": "unknown", "detail": "package_readiness unavailable"}
    rep = pr.assess_package(artwork=path.read_bytes(),
                            expected_terms=list(p.get("terms") or []))
    return {"result": "pass" if rep.get("verdict") == "retail_ready" else "fail",
            "kind": "readiness", "path": str(path),
            "detail": str(rep.get("verdict"))}


def _executor_ok(p: Dict[str, Any]) -> Dict[str, Any]:
    """The weakest verifier: the lane's own report.

    It exists so a step with no external assertion can still be represented, but
    it is labelled `executor` so nobody mistakes it for independent proof.
    """
    ok = bool(p.get("_executor_ok"))
    return {"result": "pass" if ok else "fail", "kind": "executor",
            "detail": "lane self-report; weaker than an external assertion"}


def _plan_complete(p: Dict[str, Any]) -> Dict[str, Any]:
    ok = bool(p.get("_plan_ok"))
    return {"result": "pass" if ok else "fail", "kind": "plan",
            "detail": "every node is done with evidence" if ok else
                      "a node is not done or has no evidence"}


def _wrap_content(check: Dict[str, Any], path: Path) -> Dict[str, Any]:
    return {"result": "pass" if check.get("valid") else "fail",
            "kind": str(check.get("kind") or "content"),
            "path": str(path), "detail": str(check.get("detail") or "")[:300]}


def _label_valid(p: Dict[str, Any]) -> Dict[str, Any]:
    from .content import validate_label
    path = Path(str(p.get("path") or ""))
    return _wrap_content(validate_label(path, list(p.get("terms") or [])), path)


def _ad_valid(p: Dict[str, Any]) -> Dict[str, Any]:
    from .content import validate_ad
    path = Path(str(p.get("path") or ""))
    return _wrap_content(validate_ad(path), path)


def _patch_valid(p: Dict[str, Any]) -> Dict[str, Any]:
    from .content import validate_patch
    path = Path(str(p.get("path") or ""))
    return _wrap_content(validate_patch(path), path)


def _json_valid(p: Dict[str, Any]) -> Dict[str, Any]:
    from .content import validate_json
    path = Path(str(p.get("path") or ""))
    return _wrap_content(validate_json(path), path)


def _text_valid(p: Dict[str, Any]) -> Dict[str, Any]:
    from .content import validate_text
    path = Path(str(p.get("path") or ""))
    return _wrap_content(validate_text(path, list(p.get("terms") or []),
                                       int(p.get("min_chars") or 120)), path)


def _social_valid(p: Dict[str, Any]) -> Dict[str, Any]:
    from .content import validate_social
    path = Path(str(p.get("path") or ""))
    return _wrap_content(validate_social(path), path)


def _aplus_valid(p: Dict[str, Any]) -> Dict[str, Any]:
    from .content import validate_aplus
    path = Path(str(p.get("path") or ""))
    return _wrap_content(validate_aplus(path), path)


def page_state_verifier(expected: Dict[str, Any]):
    """Build a verifier from a Chrome Connect reading (injected by the caller)."""
    def _check(_: Dict[str, Any]) -> Dict[str, Any]:
        url = str(expected.get("url") or "")
        ok_url = not url or expected.get("actual_url", "").startswith(url)
        selectors = expected.get("required_selectors") or []
        found = expected.get("found_selectors") or []
        ok_sel = all(s in found for s in selectors)
        forbidden = expected.get("forbidden_selectors") or []
        ok_forbidden = not any(s in found for s in forbidden)
        ok = ok_url and ok_sel and ok_forbidden
        return {"result": "pass" if ok else "fail", "kind": "page_state",
                "detail": f"url={expected.get('actual_url')} "
                          f"missing={[s for s in selectors if s not in found]}"}
    return _check
