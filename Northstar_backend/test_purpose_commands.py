"""Purpose commands (Project Thorn v5.0 §Embedded Purpose Commands) — real tests.

The point of these tests is the CONTRACT, not the heuristics:
  * each command actually finds a planted, unambiguous issue in a known tree;
  * it is read-only (byte-identical tree before and after);
  * it is deterministic (two runs → identical report);
  * it is bounded (limits respected, findings capped);
  * it fails honestly (unknown command / escaping path → ok=False, never raises);
  * it runs against the REAL repository without exploding.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import purpose_commands as pc


# ── fixture: a small tree with one planted instance of every detectable issue ──

LONG_BODY = "\n".join(f"    step_{i} = {i} + 1" for i in range(130))

SLOW_PY = f'''
import subprocess
import time


def long_one(seed):
{LONG_BODY}
    return seed


def deep(cfg):
    if cfg:
        if cfg.get("a"):
            if cfg.get("b"):
                if cfg.get("c"):
                    if cfg.get("d"):
                        return "bottom"
    return None


def quadratic(matrix):
    total = 0
    for row in matrix:
        for cell in row:
            total += cell
    return total


def build(parts):
    out = ""
    for p in parts:
        out += p
    return out


async def handler(payload):
    time.sleep(1)
    blob = open("payload.json").read()
    subprocess.run(["echo", blob])
    return payload
'''

DEEP_INDENT = "\n".join("    " * 0 + "        " * 1)  # placeholder, kept simple above


def _write_tree(root: Path) -> None:
    (root / "pkg").mkdir(parents=True, exist_ok=True)
    (root / "tests").mkdir(parents=True, exist_ok=True)
    (root / "many").mkdir(parents=True, exist_ok=True)

    (root / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (root / "tests" / "__init__.py").write_text("", encoding="utf-8")

    # planted import cycle: a <-> b
    (root / "pkg" / "a.py").write_text("from pkg import b\n\n\ndef fa():\n    return b.fb()\n", encoding="utf-8")
    (root / "pkg" / "b.py").write_text("from pkg import a\n\n\ndef fb():\n    return a.fa()\n", encoding="utf-8")

    # planted wide interface: 13 internal imports (threshold is 12)
    imports = "\n".join(f"import pkg.m{i}" for i in range(13))
    (root / "pkg" / "hub.py").write_text(imports + "\n\n\ndef h():\n    return 1\n", encoding="utf-8")

    for i in range(13):
        (root / "many" / f"m{i}.py").write_text(f"def f{i}():\n    return {i}\n", encoding="utf-8")
    # make pkg.m0..m12 resolvable by leaf name
    for i in range(13):
        (root / "pkg" / f"m{i}.py").write_text(f"def f{i}():\n    return {i}\n", encoding="utf-8")

    (root / "pkg" / "slow.py").write_text(SLOW_PY, encoding="utf-8")
    (root / "pkg" / "lonely_feature.py").write_text(
        "def lonely_one(x):\n    return x\n\n\ndef lonely_two(y):\n    return y\n", encoding="utf-8")
    (root / "pkg" / "covered_feature.py").write_text(
        "def covered_one(x):\n    return x\n", encoding="utf-8")
    (root / "tests" / "test_covered_feature.py").write_text(
        "import pkg.covered_feature\n\n\ndef test_it():\n    assert pkg.covered_feature.covered_one(1) == 1\n",
        encoding="utf-8")


def _tree_hash(root: Path) -> str:
    h = hashlib.sha256()
    for p in sorted(root.rglob("*")):
        if p.is_file():
            h.update(str(p.relative_to(root)).encode())
            h.update(p.read_bytes())
    return h.hexdigest()


@pytest.fixture()
def tree(tmp_path: Path) -> Path:
    _write_tree(tmp_path)
    return tmp_path


# ── /optimize-architecture ───────────────────────────────────────────────────

def test_architecture_finds_the_planted_import_cycle(tree: Path) -> None:
    rep = pc.analyze_architecture(tree)
    assert rep["ok"] is True
    cycles = [f for f in rep["findings"] if f["kind"] == "import_cycle"]
    assert cycles, "the a<->b cycle was not detected"
    members = cycles[0]["metric"]["members"]
    assert members == 2
    assert "pkg.a" in cycles[0]["target"] and "pkg.b" in cycles[0]["target"]
    assert cycles[0]["severity"] in {"medium", "high"}


def test_architecture_flags_the_wide_interface_and_ranks_fan_in(tree: Path) -> None:
    rep = pc.analyze_architecture(tree)
    wide = [f for f in rep["findings"] if f["kind"] == "wide_interface"]
    assert any(f["target"] == "pkg.hub" for f in wide), wide
    assert all(f["metric"]["fan_out"] >= pc.WIDE_FANOUT for f in wide)
    assert rep["most_depended_on"], "fan-in ranking is empty"


def test_architecture_report_is_honest_about_scope(tree: Path) -> None:
    rep = pc.analyze_architecture(tree)
    assert rep["method"] and rep["caveats"]
    assert rep["scanned"]["modules"] > 0
    assert "Python" in " ".join(rep["caveats"]) or "Python" in rep["method"]


# ── /refactor-performance ────────────────────────────────────────────────────

def test_performance_finds_every_planted_offender(tree: Path) -> None:
    rep = pc.analyze_performance(tree)
    kinds = {f["kind"] for f in rep["findings"]}
    for expected in ("long_function", "deep_nesting", "nested_loops",
                     "blocking_in_async", "unbounded_read",
                     "quadratic_string_build", "no_timeout"):
        assert expected in kinds, f"{expected} not detected (got {sorted(kinds)})"


def test_performance_blocking_report_names_the_calls(tree: Path) -> None:
    rep = pc.analyze_performance(tree)
    blocking = [f for f in rep["findings"] if f["kind"] == "blocking_in_async"]
    assert blocking, "async blocking was not detected"
    calls = set(blocking[0]["metric"]["calls"])
    assert {"time.sleep", "open"} <= calls, calls
    assert blocking[0]["severity"] == "high"
    assert "handler" in blocking[0]["target"]


def test_performance_measures_rather_than_asserts(tree: Path) -> None:
    rep = pc.analyze_performance(tree)
    longf = [f for f in rep["findings"] if f["kind"] == "long_function"][0]
    assert longf["metric"]["loc"] >= pc.LONG_FUNCTION_LOC
    assert longf["metric"]["threshold"] == pc.LONG_FUNCTION_LOC
    # Absolute runtime numbers must NOT be invented.
    assert "ms" not in json.dumps(longf["metric"]).lower()


# ── /expand-vectors ──────────────────────────────────────────────────────────

def test_vectors_reports_only_the_unreferenced_module(tree: Path) -> None:
    rep = pc.expand_vectors(tree)
    targets = {f["target"] for f in rep["findings"]}
    assert "pkg.lonely_feature" in targets
    assert "pkg.covered_feature" not in targets, "a referenced module was reported as a gap"
    lonely = [f for f in rep["findings"] if f["target"] == "pkg.lonely_feature"][0]
    assert lonely["metric"]["public_symbols"] == 2
    assert "happy path" in lonely["proposal"]


def test_vectors_respects_the_limit(tree: Path) -> None:
    rep = pc.expand_vectors(tree, limit=1)
    assert len(rep["findings"]) == 1
    assert rep["gaps_total"] >= 1


# ── contract: read-only, deterministic, bounded, honest failures ─────────────

def test_every_command_is_read_only_and_deterministic(tree: Path) -> None:
    before = _tree_hash(tree)
    for cmd in sorted(pc.COMMANDS):
        # analysers take an explicit root; the dispatcher's guard is tested separately
        fn = pc.COMMANDS[cmd]
        run1 = fn(tree)
        run2 = fn(tree)
        assert json.dumps(run1, sort_keys=True) == json.dumps(run2, sort_keys=True), f"{cmd} is not deterministic"
        assert run1["ok"] is True
    assert _tree_hash(tree) == before, "a purpose command modified the tree"


def test_findings_are_capped(tree: Path) -> None:
    rep = pc.expand_vectors(tree, limit=pc.MAX_FINDINGS)
    assert len(rep["findings"]) <= pc.MAX_FINDINGS
    rep2 = pc.analyze_performance(tree)
    assert len(rep2["findings"]) <= pc.MAX_FINDINGS


def test_unknown_command_fails_honestly() -> None:
    rep = pc.run_purpose_command("not-a-command")
    assert rep["ok"] is False
    assert "known commands" in rep["error"]
    assert rep["findings"] == []


def test_path_escaping_the_repo_root_is_refused() -> None:
    rep = pc.run_purpose_command("optimize-architecture", path="../..")
    assert rep["ok"] is False
    assert "escapes the repository root" in rep["error"] or "does not exist" in rep["error"]


def test_slash_prefixed_command_id_is_accepted() -> None:
    rep = pc.run_purpose_command("/expand-vectors", path="Northstar_backend/tools")
    assert rep["ok"] is True
    assert rep["command"] == "expand-vectors"


# ── integration: the real repository + the chat tool ─────────────────────────

def test_runs_against_the_real_repository() -> None:
    rep = pc.run_purpose_command("optimize-architecture")
    assert rep["ok"] is True, rep.get("error")
    assert rep["scanned"]["modules"] > 50
    assert isinstance(rep["findings"], list)


def test_chat_tool_is_registered_and_callable() -> None:
    import chat_tools

    assert "purpose_command" in chat_tools.TOOLS
    spec = chat_tools.TOOLS["purpose_command"]
    assert "read-only" in spec["description"]
    assert spec["parameters"]["properties"]["command"]["enum"]

    out = chat_tools.run_tool("purpose_command", {"command": "expand-vectors", "limit": 3})
    assert out["ok"] is True
    assert "finding(s)" in out["summary"]
    assert len(out["findings"]) <= 10
    assert out["assets"] == []


def test_chat_tool_rejects_a_bad_command_argument() -> None:
    import chat_tools

    out = chat_tools.run_tool("purpose_command", {"command": "rm -rf /"})
    assert out["ok"] is False
    assert out["summary"]


def test_tool_listed_for_foci_that_take_all_tools() -> None:
    import shell_focus

    # auto + autothink use tools=None ("all registered tools") — the new tool is
    # therefore available there without editing the focus catalogue.
    assert shell_focus.tools_for_focus("auto") is None
    assert shell_focus.tools_for_focus("autothink") is None
    assert shell_focus.tools_for_focus("grow") is not None
