"""Offline tests for the AutoThink TaskRouter.

Zero network, zero LLM calls. Uses the real master_brain_gateway classifier
deterministically (it is itself offline + deterministic).
"""

import json
import os
import tempfile
import unittest
from unittest import mock

import orchestration.router as router_mod
from orchestration.router import route_task, build_context


class RouteTaskTests(unittest.TestCase):
    def test_code_classification_routes_to_build(self):
        r = route_task("Fix the fee engine bug in FBA calculation")
        self.assertEqual(r["task_class"], "AUTOTHINK_CODE")
        self.assertEqual(r["label"], "build")
        self.assertTrue(r["plan"])

    def test_research_classification_routes_to_research(self):
        r = route_task("Research how BSR affects monthly sales estimates")
        self.assertEqual(r["task_class"], "AUTOTHINK_RESEARCH")
        self.assertEqual(r["label"], "research")

    def test_generic_question_falls_back_to_research(self):
        r = route_task("What is the current portfolio status?")
        self.assertEqual(r["task_class"], "AUTOTHINK_RESEARCH")

    def test_gateway_backend_flag_true(self):
        r = route_task("Build a new Costco matcher")
        self.assertTrue(r["gateway_backend"])

    def test_build_context_always_has_shape(self):
        task = "Compare Costco catalog coverage"
        r = route_task(task)
        ctx = build_context(task, r, data_sources=["a.json", "b.json"])
        self.assertEqual(ctx["task"], task)
        self.assertEqual(ctx["task_class"], r["task_class"])
        self.assertEqual(ctx["plan"], r["plan"])
        self.assertEqual(ctx["data_sources"], ["a.json", "b.json"])


class AuditTests(unittest.TestCase):
    def test_audit_writes_append_only_jsonl(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "audit-test.jsonl")
            entry = {
                "track": "AUTOTHINK_RESEARCH",
                "task_class": "AUTOTHINK_RESEARCH",
                "query": "Analyze the benchmark results",
                "provider": "local",
                "files_touched": [],
                "live_action_requested": False,
                "approval_status": "not_requested",
            }
            router_mod.audit(dict(entry), log_path=log)
            router_mod.audit(dict(entry), log_path=log)
            with open(log, "r", encoding="utf-8") as f:
                lines = f.read().strip().splitlines()
            self.assertEqual(len(lines), 2)
            parsed = json.loads(lines[0])
            self.assertEqual(parsed["track"], "AUTOTHINK_RESEARCH")
            self.assertIn("timestamp", parsed)

    def test_audit_sanitizes_invalid_track(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = os.path.join(tmp, "audit-test2.jsonl")
            entry = {"track": "NOT_A_TRACK", "query": "x"}
            router_mod.audit(entry, log_path=log)
            with open(log, "r", encoding="utf-8") as f:
                parsed = json.loads(f.readline())
            self.assertEqual(parsed["track"], "AUTOTHINK_RESEARCH")


if __name__ == "__main__":
    unittest.main()