"""Installation health check for Ty's Assistant.

One command, one verdict. It proves the installed pieces are wired — it does not
prove the model is good at its job (the benchmark does that).

    python tools/install_health.py
    python tools/install_health.py --with-tests     # also runs the core suites
    python tools/install_health.py --json out.json

Exit code 0 only when every CRITICAL check passes. Informational checks (a worker
that is deliberately not resident, a missing prior benchmark run) report their
state without failing the installation.
"""
from __future__ import annotations

import argparse
import glob
import json
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))
sys.path.insert(0, str(ROOT / "tools"))

RESULTS: List[Dict[str, Any]] = []


def record(name: str, ok: Optional[bool], detail: str, *, critical: bool = True,
           data: Any = None) -> None:
    RESULTS.append({"check": name, "ok": ok, "critical": critical,
                    "detail": detail, "data": data})


def check(fn):
    """Run one check; an exception is a failed check, never a crashed report."""
    name = fn.__name__.replace("_", ".", 1)
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        record(name, False, f"{type(exc).__name__}: {exc}"[:300])
    return fn


# ── task-execution contract ─────────────────────────────────────────────────

@check
def route_run_endpoint() -> None:
    import tys_api
    run = next((r for r in tys_api.router.routes
                if r.path.endswith("/tasks/{task_id}/run") and "POST" in r.methods), None)
    assert run is not None, "POST /tasks/{task_id}/run is not registered"
    params = {p.name for p in run.dependant.query_params}
    assert params == {"max_steps"}, f"unexpected query params: {sorted(params)}"
    deps = [getattr(d.call, "__name__", "") for d in run.dependant.dependencies]
    assert "require_tys_admin" in deps, f"run route is not admin-gated: {deps}"
    record("route.run_endpoint", True,
           f"POST {run.path} — sync 200, admin-gated, params={{max_steps}}")


@check
def route_related_routes() -> None:
    import tys_api
    prefix = tys_api.router.prefix
    need = {
        ("GET", f"{prefix}/tasks/{{task_id}}"),
        ("POST", f"{prefix}/tasks/{{task_id}}/resume"),
        ("POST", f"{prefix}/tasks/{{task_id}}/cancel"),
        ("POST", f"{prefix}/tasks/{{task_id}}/controller-result"),
    }
    have = {(m, r.path) for r in tys_api.router.routes for m in r.methods if m != "HEAD"}
    missing = need - have
    assert not missing, f"missing routes: {sorted(missing)}"
    record("route.related_routes", True,
           f"{len(need)} read/resume/cancel/controller routes present")


@check
def route_no_speculative_params() -> None:
    import tys_api
    bad = [r.path for r in tys_api.router.routes
           if any(p.name == "engine" for p in r.dependant.query_params)
           or any(p.name == "stream" for p in r.dependant.query_params)]
    assert not bad, f"engine/stream params found on {bad}"
    record("route.no_speculative_params", True, "no engine= or stream= parameter anywhere")


# ── semantic validators ─────────────────────────────────────────────────────

GOOD_PATCH = ("--- a/calc.py\n+++ b/calc.py\n@@ -1,2 +1,2 @@\n"
              " def add(a, b):\n-    return a - b\n+    return a + b\n")
BAD_PATCH = ("--- a/calc.py\n+++ b/calc.py\n@@ -1,7 +1,7 @@\n def add(a, b):\n"
             "-    return a - b\n+    return a + b\n")


@check
def validators_patch_arithmetic() -> None:
    from agent_kernel import content as cv
    tmp = Path(tempfile.mkdtemp())
    good = tmp / "good.patch"
    good.write_text(GOOD_PATCH, encoding="utf-8")
    bad = tmp / "bad.patch"
    bad.write_text(BAD_PATCH, encoding="utf-8")
    assert cv.validate_patch(good)["valid"] is True, "a correct patch was rejected"
    result = cv.validate_patch(bad)
    assert result["valid"] is False, "a miscounted hunk passed"
    assert result["checks"]["semantics"]["bad_hunks"], "no bad hunk reported"
    record("validators.patch_arithmetic", True,
           "correct diff accepted; header/body mismatch rejected")


@check
def validators_json_keys() -> None:
    from agent_kernel import content as cv
    tmp = Path(tempfile.mkdtemp())
    brief = {"semantics": {"required_keys": ["run_id", "status"]}}
    ok = tmp / "ok.json"
    ok.write_text(json.dumps({"run_id": "r1", "status": "blocked"}), encoding="utf-8")
    miss = tmp / "miss.json"
    miss.write_text(json.dumps({"run_id": "r1"}), encoding="utf-8")
    assert cv.validate_json(ok, brief)["valid"] is True
    assert cv.validate_json(miss, brief)["valid"] is False
    record("validators.json_keys", True, "required keys enforced")


@check
def validators_text_structure() -> None:
    from agent_kernel import content as cv
    tmp = Path(tempfile.mkdtemp())
    brief = {"semantics": {"min_sentences": 2, "required_headings": ["Host", "Grant"]}}
    stub = tmp / "stub.md"
    stub.write_text("# Runbook\n\nTODO: fill this in.\n", encoding="utf-8")
    good = tmp / "good.md"
    good.write_text("# Runbook\n\n## Host\none host only.\n\n## Grant\nread only, "
                    "expiry 24 h.\n", encoding="utf-8")
    assert cv.validate_text(stub, [], 10, brief)["valid"] is False, "a TODO stub passed"
    assert cv.validate_text(good, [], 10, brief)["valid"] is True, "a finished doc failed"
    record("validators.text_structure", True,
           "placeholders, headings and sentence floor enforced")


@check
def validators_seed_unchanged() -> None:
    from agent_kernel import content as cv
    base = Path(tempfile.mkdtemp())
    text = ("# Campaign\n\nLane 1 inspects the fixtures and names the missing fact. "
            "Lane 2 browses one host. The gate stops the run for approval.\n")
    for part in ("seed", "run"):
        (base / part / "p16").mkdir(parents=True)
        (base / part / "p16" / "campaign.md").write_text(text, encoding="utf-8")
    brief = {"id": "p16", "artifact": "campaign.md", "validator": "text",
             "terms": ["gate"], "semantics": {"min_sentences": 2}}
    assert cv.validate_brief(base / "run", brief)["valid"] is True
    rejected = cv.validate_brief(base / "run", brief, seed_dir=base / "seed")
    assert rejected["valid"] is False, "an untouched stub was accepted"
    record("validators.seed_unchanged", True, "a byte-identical stub is rejected")


# ── kernel ──────────────────────────────────────────────────────────────────

@check
def kernel_acceptance_derivation() -> None:
    from agent_kernel.tys_adapter import _derive_acceptance
    rows = _derive_acceptance(
        {"lane": "coding", "params": {"acceptance": {
            "required_files": ["fix.patch"],
            "commands": [["python", "-m", "pytest", "-q"]]}}},
        {"workspace": str(ROOT)})
    verifiers = [a.verifier for a in rows]
    assert "artifact_exists" in verifiers and "command" in verifiers, verifiers
    assert "executor_ok" not in verifiers, "the lane can still grade itself"
    record("kernel.acceptance_derivation", True,
           "workspace spec -> artifact_exists + command; executor_ok retired")


@check
def kernel_acceptance_outranks_self_report() -> None:
    from agent_kernel import Acceptance, Kernel, Node, Policy
    tmp = Path(tempfile.mkdtemp())
    artifact = tmp / "fix.patch"
    artifact.write_text(GOOD_PATCH, encoding="utf-8")
    kernel = Kernel(policy=Policy(mode="dontAsk"))
    kernel.executors["inspect"] = lambda n, p: {"ok": False, "detail": "budget"}
    plan = kernel.create_plan(goal="health", nodes=[
        Node("n1", "inspect", "read", lane="inspect",
             acceptance=[Acceptance("artifact exists", "artifact_exists",
                                    {"path": str(artifact)})])],
        acceptance=[Acceptance("all done", "plan_complete")])
    kernel.submit(plan)
    kernel.approve(plan.plan_id, "health")
    result = kernel.run(plan)
    assert result.status == "complete", f"status={result.status} reason={result.reason}"
    record("kernel.acceptance_outranks_self_report", True,
           "executor said not-ok; passing acceptance still completes the node")


# ── guardrails ──────────────────────────────────────────────────────────────

@check
def guard_write_denylist() -> None:
    from agent_kernel.coding_tools import Workspace
    ws = Workspace(Path(tempfile.mkdtemp()))
    blocked = [".env", "config/chromecontrol_policy_owner.json", "fixtures/x.json"]
    for rel in blocked:
        out = ws.write(rel, "x")
        assert out.ok is False and "protected" in out.error, f"{rel} was writable"
    assert ws.write(".env.example", "X=\n").ok is True, ".env.example should be writable"
    record("guard.write_denylist", True,
           "secrets, operator policy and fixtures are read-only to every lane")


@check
def guard_amazon_policy() -> None:
    from agent_kernel.policy import Policy
    decision = Policy(mode="dontAsk").evaluate("browser_click", "", host="www.amazon.com")
    assert decision.effect == "deny", f"amazon host resolved to {decision.effect}"
    record("guard.amazon_policy", True, "Amazon hosts deny before any grant is read")


@check
def guard_state_registry_is_operator_gated() -> None:
    cfg = json.loads((ROOT / "opencode.json").read_text(encoding="utf-8-sig"))
    denied = [p for p in cfg.get("permissions", [])
              if p.get("action") == "edit" and p.get("effect") == "deny"
              and p.get("resource") == "00_STATE.json"]
    assert denied, "00_STATE.json is not edit-protected"
    record("guard.state_registry_is_operator_gated", True,
           "00_STATE.json edits are denied to agents; fragments are merged by the operator",
           critical=False)


# ── engines ─────────────────────────────────────────────────────────────────

@check
def engine_ollama_and_bojo() -> None:
    url = "http://127.0.0.1:11434/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            tags = json.load(r)
    except Exception as exc:  # noqa: BLE001
        record("engine.ollama_and_bojo", None,
               f"Ollama not reachable ({type(exc).__name__}); Bojo cannot answer",
               critical=False)
        return
    names = {m.get("name") for m in tags.get("models") or []}
    assert "bojo:latest" in names, f"bojo is not installed; have {sorted(names)}"
    record("engine.ollama_and_bojo", True, "Ollama reachable; bojo installed",
           data=sorted(names))


@check
def engine_model_router_agrees_with_disk() -> None:
    import model_router as mr
    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=5) as r:
            installed = [m.get("name") for m in json.load(r).get("models") or []]
    except Exception:  # noqa: BLE001
        installed = None
    catalog = mr.catalog(installed)
    if installed is not None:
        status = catalog["text_local_status"]
        assert all(v == "ok" for v in status.values()), f"text tiers: {status}"
    assert catalog["local"]["defaults"]["T2"] == "bojo", catalog["local"]["defaults"]
    record("engine.model_router_agrees_with_disk", True,
           "every local text tier resolves to an installed model (bojo)",
           data=catalog.get("text_local_status"))


@check
def engine_documented_profile() -> None:
    suite = json.loads((ROOT / "shared" / "model-suite.json").read_text(encoding="utf-8"))
    ty = suite["local_engines"]["ty"]
    bojo = suite["local_engines"]["bojo"]
    assert ty["context_tokens"] == 65536, ty["context_tokens"]
    assert str(ty["kv_cache"]).startswith("q4_0"), ty["kv_cache"]
    assert ty["gpu_layers"] == 99 and ty["vram_gb"] == 13
    assert bojo["gpu_layers"] == 0 and bojo["context_tokens"] == 8192
    assert ty["residency"].startswith("on demand")
    record("engine.documented_profile", True,
           "Ty 65536/q4_0/-ngl 99/~13 GB on demand; Bojo CPU, 8192, 0 VRAM")


@check
def engine_ty_worker_state() -> None:
    import socket
    with socket.socket() as s:
        s.settimeout(1.0)
        open_ = s.connect_ex(("127.0.0.1", 8080)) == 0
    record("engine.ty_worker_state", None,
           ("serving on 127.0.0.1:8080" if open_
            else "idle (on demand) — start with scripts/start-northstar-llm.ps1"),
           critical=False, data={"listening": open_})


# ── harnesses + evidence ────────────────────────────────────────────────────

@check
def harness_benchmark_wiring() -> None:
    import tys_kernel_bench as bench
    assert len(bench.ALL_IDS) == 20, len(bench.ALL_IDS)
    assert bench.MAX_CODING_STEPS == 15
    assert str(bench.ROOT / "tools" / "diff_check.py") == bench.DIFF_CHECK
    assert (ROOT / "tools" / "diff_check.py").is_file(), "diff_check.py is missing"
    assert set(bench.SEMANTICS) <= set(bench.ALL_IDS)
    record("harness.benchmark_wiring", True,
           f"20 briefs; {len(bench.SEMANTICS)} carry a domain spec; patch bar in acceptance")


@check
def harness_last_evidence() -> None:
    """Evidence must exist and parse; the pass RATE is data, not a health verdict."""
    files = sorted(glob.glob(str(ROOT / "reports/rea_probe/tys_kernel_bench/*/evidence.jsonl")))
    if not files:
        record("harness.last_evidence", None, "no benchmark evidence yet", critical=False)
        return
    latest = Path(files[-1])
    rows = [json.loads(line) for line in latest.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    assert rows, "the evidence log is empty"
    required = {"id", "kernel_status", "validator", "commands", "provenance", "passed"}
    missing = [r.get("id") for r in rows if not required <= set(r)]
    assert not missing, f"records missing fields: {missing[:5]}"
    passed = sum(1 for r in rows if r.get("passed"))
    record("harness.last_evidence", True,
           f"{len(rows)} records parse with full provenance; last sweep {passed}/{len(rows)} "
           f"({latest.parent.name}) — the rate is the benchmark's result, not a health gate",
           critical=False, data={"file": str(latest), "passed": passed, "rows": len(rows)})


@check
def harness_proj_bench_dry() -> None:
    out = subprocess.run([sys.executable, str(ROOT / "tools/proj_bench.py"),
                          "--limit", "20"], cwd=str(ROOT),
                         capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, (out.stderr or out.stdout)[-300:]
    text = out.stdout or ""
    start = text.find("{")
    report = json.loads(text[start:]) if start >= 0 else {}
    assert report.get("complete") == 20 and report.get("valid_plans") == 20, report
    record("harness.proj_bench_dry", True,
           f"harness validation {report['complete']}/20, evidence "
           f"{report.get('mean_evidence_coverage')}, resume "
           f"{report.get('resume_mechanics', {}).get('no_duplicate')}")


# ── state registry ──────────────────────────────────────────────────────────

@check
def state_fragment_applies() -> None:
    frag = ROOT / "state" / "fragments" / "20261029_install_health.json"
    assert frag.is_file(), f"missing fragment {frag}"
    out = subprocess.run([sys.executable, str(ROOT / "tools/state_fragment.py"),
                          "--check", str(frag)], cwd=str(ROOT),
                         capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, (out.stdout or out.stderr)[-300:]
    parsed = json.loads(out.stdout)
    assert parsed["merged_keys"] > parsed["registry_keys"], parsed
    record("state.fragment_applies", True,
           f"fragment validates; would add {parsed['would_add']} "
           "(operator runs --apply; agents may not rewrite 00_STATE.json)",
           critical=False)


def summarise() -> Dict[str, Any]:
    critical = [r for r in RESULTS if r["critical"]]
    failed = [r for r in critical if r["ok"] is not True]
    verdict = "HEALTHY" if not failed else "ATTENTION"
    return {
        "verdict": verdict,
        "checks": len(RESULTS),
        "critical": len(critical),
        "critical_failed": len(failed),
        "failed": [r["check"] for r in failed],
        "informational": [{"check": r["check"], "detail": r["detail"]}
                          for r in RESULTS if not r["critical"]],
        "results": RESULTS,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


CORE_TESTS = ["test_agent_kernel.py", "test_content_semantics.py",
              "test_coding_guardrails.py", "test_tys_assistant.py",
              "test_model_router.py", "test_coding_agent.py"]


def run_tests() -> None:
    args = [sys.executable, "-m", "pytest", *[str(ROOT / "Northstar_backend" / t) for t in CORE_TESTS],
            "-q", "--no-header", "-p", "no:cacheprovider"]
    out = subprocess.run(args, cwd=str(ROOT / "Northstar_backend"),
                         capture_output=True, text=True, timeout=900)
    tail = [line for line in (out.stdout or "").splitlines() if " passed" in line or "failed" in line]
    ok = out.returncode == 0
    record("tests.core_suites", ok, (tail[-1] if tail else (out.stdout or "")[-200:]),
           critical=True)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--with-tests", action="store_true", help="also run the core suites")
    ap.add_argument("--json", default="", help="write the report here")
    args = ap.parse_args(argv)

    if args.with_tests:
        try:
            run_tests()
        except Exception as exc:  # noqa: BLE001
            record("tests.core_suites", False, f"{type(exc).__name__}: {exc}"[:200])

    report = summarise()
    print(f"{'PASS' if report['verdict'] == 'HEALTHY' else 'FAIL'}  "
          f"Ty's Assistant installation: {report['critical'] - report['critical_failed']}"
          f"/{report['critical']} critical checks")
    for row in RESULTS:
        mark = "ok  " if row["ok"] is True else ("skip" if row["ok"] is None else "FAIL")
        star = " " if row["critical"] else "*"
        print(f"  [{mark}]{star} {row['check']}: {row['detail']}")
    if report["informational"]:
        print("  (* informational — does not fail the installation)")

    dest = Path(args.json) if args.json else (
        ROOT / "reports" / f"install_health_{datetime.now(timezone.utc):%Y%m%d}.json")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"report: {dest}")
    return 0 if report["verdict"] == "HEALTHY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
