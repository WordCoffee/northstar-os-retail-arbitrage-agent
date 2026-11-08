"""D8: parity is a measurement, and an unavailable backend is never a pass."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from vision import parity, quarantine  # noqa: E402

BASE = "http://127.0.0.1:8101/ui/"


class GoodBackend:
    """Implements the ten tasks against an in-memory page."""

    name = "vision"

    def __init__(self, *, fail_click: bool = False, name: str = "") -> None:
        self.url = ""
        self._fail_click = fail_click
        self.text = "welcome to northstar"
        if name:
            self.name = name

    def available(self):
        return {"ok": True}

    def navigate(self, url):
        self.url = url
        return {"ok": True}

    def current_url(self):
        return self.url

    def title(self):
        return "Northstar"

    def find(self, needle):
        return {"name": "Prospector", "role": "link", "backend_node_id": 1}

    def ax_tree(self):
        return {"ok": True, "count": 12, "elements": []}

    def read_text(self, selector):
        return {"ok": True, "text": self.text}

    def click(self, element):
        if self._fail_click:
            return {"ok": False, "reason": "no box"}
        self.url = BASE.rstrip("/") + "/prospector"
        return {"ok": True}

    def type_text(self, text):
        return {"ok": True, "typed": len(text)}

    def scroll(self, dy):
        return {"ok": True}

    def close(self):
        return None


class UnavailableBackend(GoodBackend):
    name = "chromeconnect"

    def available(self):
        return {"ok": False, "reason": "no runner configured"}


def test_an_unavailable_backend_is_not_run_and_never_passes():
    result = parity.run_suite(UnavailableBackend(), base=BASE)
    assert result["ran"] is False
    assert result["pass"] is False
    assert all(task["status"] == "not_run" for task in result["tasks"])
    assert result["reason"] == "no runner configured"


def test_all_ten_tasks_pass_on_a_working_backend():
    result = parity.run_suite(GoodBackend(), base=BASE)
    assert result["ran"] is True
    assert result["total"] == 10
    assert result["passed"] == 10
    assert result["pass"] is True
    assert result["recovery"]["ok"] is True


def test_a_failed_task_makes_the_suite_fail():
    result = parity.run_suite(GoodBackend(fail_click=True), base=BASE)
    assert result["pass"] is False
    failed = [row["id"] for row in result["tasks"] if row["status"] == "fail"]
    assert "click_nav" in failed


def test_a_task_that_raises_is_a_failed_task():
    def boom(backend, base):
        raise RuntimeError("page died")

    tasks = [parity.Task("boom", "explode", boom)]
    result = parity.run_suite(GoodBackend(), base=BASE, tasks=tasks)
    assert result["ran"] is True
    assert result["tasks"][0]["status"] == "fail"
    assert "page died" in result["tasks"][0]["reason"]


def test_comparison_needs_both_backends():
    assert parity.compare([{"backend": "vision"}])["ok"] is False


def test_comparison_refuses_when_the_incumbent_could_not_run():
    rows = [parity.run_suite(GoodBackend(), base=BASE),
            parity.run_suite(UnavailableBackend(), base=BASE)]
    verdict = parity.compare(rows)
    assert verdict["ok"] is False and verdict["reason"] == "not_run"
    assert verdict["missing"] == ["chromeconnect"]


def test_comparison_passes_when_vision_matches_the_incumbent():
    rows = [parity.run_suite(GoodBackend(name="vision"), base=BASE),
            parity.run_suite(GoodBackend(name="chromeconnect"), base=BASE)]
    assert parity.compare(rows)["ok"] is True


def test_run_twice_writes_two_evidence_files(tmp_path, monkeypatch):
    monkeypatch.setitem(parity.BACKENDS, "vision", lambda: GoodBackend(name="vision"))
    monkeypatch.setitem(parity.BACKENDS, "chromeconnect",
                        lambda: GoodBackend(name="chromeconnect"))
    result = parity.run_twice(base=BASE, out_dir=tmp_path)
    assert result["ok"] is True and result["passes"] == 2
    files = sorted(tmp_path.glob("d8_parity_run*.json"))
    assert len(files) == 2
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    assert payload["comparison"]["ok"] is True


def test_one_pass_is_not_two(tmp_path, monkeypatch):
    calls = {"n": 0}

    class HalfGood(GoodBackend):
        def click(self, element):
            calls["n"] += 1
            if calls["n"] > 1:  # only the second run fails
                return {"ok": False, "reason": "no box"}
            return super().click(element)

    monkeypatch.setitem(parity.BACKENDS, "vision", lambda: HalfGood(name="vision"))
    monkeypatch.setitem(parity.BACKENDS, "chromeconnect",
                        lambda: GoodBackend(name="chromeconnect"))
    result = parity.run_twice(base=BASE, out_dir=tmp_path)
    assert result["ok"] is False
    assert result["passes"] < 2


# ------------------------------------------------------------------- quarantine
def _write_run(folder: Path, index: int, ok: bool) -> None:
    payload = {"run": index, "base": BASE, "comparison": {"ok": ok, "vision_rate": 1.0,
                                                         "chromeconnect_rate": 1.0}}
    (folder / f"d8_parity_run{index}.json").write_text(
        json.dumps(payload), encoding="utf-8")


def test_quarantine_is_refused_on_one_pass(tmp_path):
    _write_run(tmp_path, 1, True)
    assert quarantine.eligible(tmp_path)["eligible"] is False
    result = quarantine.quarantine(out_dir=tmp_path, flag=tmp_path / "flag.json")
    assert result["ok"] is False
    assert result["reason"] == "parity_not_passed_twice"


def test_quarantine_is_refused_on_two_failures(tmp_path):
    _write_run(tmp_path, 1, False)
    _write_run(tmp_path, 2, False)
    result = quarantine.quarantine(out_dir=tmp_path, flag=tmp_path / "flag.json")
    assert result["ok"] is False


def test_quarantine_is_written_after_two_passes_and_restores(tmp_path):
    _write_run(tmp_path, 1, True)
    _write_run(tmp_path, 2, True)
    flag = tmp_path / "flag.json"
    result = quarantine.quarantine(out_dir=tmp_path, flag=flag)
    assert result["ok"] is True
    assert quarantine.status(flag=flag)["quarantined"] is True
    assert quarantine.restore(flag=flag)["ok"] is True
    assert flag.exists() is False
