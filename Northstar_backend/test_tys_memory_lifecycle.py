"""Semantic memory is attached to the task lifecycle, not just the API."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Northstar_backend"))

import tys_assistant as tys  # noqa: E402


class FakeMemory:
    def __init__(self, fail=False):
        self.fail = fail
        self.queries = []
        self.remembered = []

    def context(self, account, query, *, budget_tokens=400):
        if self.fail:
            raise RuntimeError("memory down")
        self.queries.append((account, query, budget_tokens))
        return {"text": "Prior: the release gate is identity + legibility.",
                "hits": 1, "budget_tokens": budget_tokens, "used_tokens": 9,
                "sources": ["task:prior"]}

    def remember_text(self, account, text, *, source="", **kw):
        self.remembered.append({"account": account, "text": text, "source": source})
        return {"chunks": 1, "ids": ["c_1"]}


def _assistant(tmp_path, memory):
    return tys.TysAssistant(store=tys.TysStore(str(tmp_path / "tasks.db")),
                            memory=memory)


def test_submit_attaches_memory_context_to_the_task(tmp_path):
    memory = FakeMemory()
    assistant = _assistant(tmp_path, memory)
    task = assistant.submit({"objective": "inspect the release gate", "steps": []})
    assert task["scope"]["memory_context"]["text"].startswith("Prior:")
    assert memory.queries and memory.queries[0][1] == "inspect the release gate"


def test_task_outcome_is_written_to_memory(tmp_path):
    memory = FakeMemory()
    assistant = _assistant(tmp_path, memory)
    task = assistant.submit({"objective": "inspect the release gate", "steps": []})
    assistant._remember_outcome(task, "done", "all steps completed")
    assert memory.remembered
    assert "Outcome: done" in memory.remembered[0]["text"]
    assert memory.remembered[0]["source"].startswith("task:")


def test_memory_failure_does_not_block_submission(tmp_path):
    assistant = _assistant(tmp_path, FakeMemory(fail=True))
    task = assistant.submit({"objective": "inspect the release gate", "steps": []})
    assert task["id"]
    assert "memory_context" not in task.get("scope", {})
