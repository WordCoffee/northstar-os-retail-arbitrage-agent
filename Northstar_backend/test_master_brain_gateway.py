"""Offline tests for master_brain_gateway.py — deterministic classifier and audit log.

ZERO network, ZERO LLM calls, ZERO provider calls.
"""

import os
import json
import tempfile
import unittest

import master_brain_gateway as mbg


class ClassifierTests(unittest.TestCase):
    """Deterministic task classifier — action verb > domain keyword > fallback."""

    def test_autothink_research_action_verbs(self):
        """Pure research action verbs classify as AUTOTHINK_RESEARCH even with domain terms present."""
        cases = [
            "Research how BSR affects sales estimates",
            "Investigate competitor pricing strategy",
            "Compare DataForSEO vs Bright Data costs",
            "What is the fee engine formula?",
            "How does demand estimator work?",
            "Analyze the benchmark validation results",
            "Document the authorization gate logic",
            "Examine the normalization pipeline",
            "Explore the Phase 3 intel architecture",
        ]
        for c in cases:
            self.assertEqual(mbg.classify_task(c), "AUTOTHINK_RESEARCH", msg=c)

    def test_autothink_code_action_verbs(self):
        """Code action verbs (fix/refactor/implement/write X/debug) classify as AUTOTHINK_CODE."""
        cases = [
            "Fix the fee_engine.py bug in FBA calculation",
            "Implement new BSR normalization function",
            "Refactor the offer enrichment pipeline",
            "Add test for pack_match edge case",
            "Write a fixture for normalized snapshot",
            "Patch the rapidapi_client mock",
            "Debug the validation run failure",
            "Rewrite the audit log serializer",
            "Implement Smart Cache contract",
        ]
        for c in cases:
            self.assertEqual(mbg.classify_task(c), "AUTOTHINK_CODE", msg=c)

    def test_autothink_computer_action_verbs(self):
        """Computer action verbs (run/execute/copy/delete) classify as AUTOTHINK_COMPUTER."""
        cases = [
            "Run the costco catalog refresh script",
            "Execute the benchmark validation CLI",
            "Copy the scanner cache to backup",
            "Find all test files modified today",
            "Delete the corrupt audit log",
            "Run pytest on the fee engine tests",
            "Run demand estimator on new catalog",
            "Reboot the staging server",
            "Shutdown the dev environment",
        ]
        for c in cases:
            self.assertEqual(mbg.classify_task(c), "AUTOTHINK_COMPUTER", msg=c)

    def test_northstar_os_commerce_domain(self):
        """Commerce domain terms classify as NORTHSTAR_OS_COMMERCE when no action verb present."""
        cases = [
            "Calculate ROI for ASIN B000000001 with costco cost 15.99",
            "Update the profit tier thresholds",
            "Cost basis resolution for catalog match",
            "Pack match fingerprint for 100ct vs 200ct",
            "BSR normalization across categories",
            "Demand estimator output for new snapshot",
            "Competition analytics for ASIN B0TEST001",
            "Portfolio readiness ladder",
            "Economics confidence tiers",
        ]
        for c in cases:
            self.assertEqual(mbg.classify_task(c), "NORTHSTAR_OS_COMMERCE", msg=c)

    def test_northstar_os_provider_domain(self):
        """Provider domain terms classify as NORTHSTAR_OS_PROVIDER when no action verb present."""
        cases = [
            "Bright Data Web Unlocker zone northstaros",
            "Chocodata API key for search",
            "RapidAPI Easyparser credit estimation",
            "Unwrangle rate limit handling",
            "DataForSEO Merchant Standard task_post",
            "Scavio transport error retry policy",
            "Provider enrichment cache TTL",
        ]
        for c in cases:
            self.assertEqual(mbg.classify_task(c), "NORTHSTAR_OS_PROVIDER", msg=c)

    def test_t2_operations_domain(self):
        """T2 operations domain terms classify as T2_OPERATIONS when no action verb present."""
        cases = [
            "Sunday 03:00 Costco catalog refresh schedule",
            "Business Center invoice for purchase authorization",
            "Task Scheduler weekly run configuration",
            "Vendor management compliance checklist",
            "Costco refresh catalog after 429 rate limit",
            "T2 Holdings billing reconciliation",
        ]
        for c in cases:
            self.assertEqual(mbg.classify_task(c), "T2_OPERATIONS", msg=c)

    def test_platform_admin_domain(self):
        """Platform admin domain terms classify as PLATFORM_ADMIN when no action verb present."""
        cases = [
            "Deploy to Cloudflare Workers via wrangler",
            "Cloudflare KV namespace monitoring",
            "Rotate credentials for DataForSEO",
            "Infrastructure access control policies",
            "Secrets management with vault",
            "Monitor KV namespace usage",
        ]
        for c in cases:
            self.assertEqual(mbg.classify_task(c), "PLATFORM_ADMIN", msg=c)

    def test_action_verb_priority(self):
        """Action verbs always take priority over domain keywords."""
        # Code action verb beats commerce domain
        self.assertEqual(mbg.classify_task("Fix the margin calculation"), "AUTOTHINK_CODE")
        # Code action verb beats provider domain
        self.assertEqual(mbg.classify_task("Fix DataForSEO rate limiting"), "AUTOTHINK_CODE")
        # Research action verb beats provider domain
        self.assertEqual(mbg.classify_task("Research how DataForSEO credits work"), "AUTOTHINK_RESEARCH")
        # Computer action verb beats commerce domain
        self.assertEqual(mbg.classify_task("Run the costco catalog refresh script"), "AUTOTHINK_COMPUTER")

    def test_empty_and_invalid_input(self):
        self.assertEqual(mbg.classify_task(""), "AUTOTHINK_RESEARCH")
        self.assertEqual(mbg.classify_task("   "), "AUTOTHINK_RESEARCH")
        self.assertEqual(mbg.classify_task(None), "AUTOTHINK_RESEARCH")
        self.assertEqual(mbg.classify_task(123), "AUTOTHINK_RESEARCH")

    def test_all_tracks_reachable(self):
        """Every track in the taxonomy is reachable from some input string."""
        reachable = {
            "AUTOTHINK_CODE": "Fix the broken function",
            "AUTOTHINK_COMPUTER": "Run the pytest suite",
            "AUTOTHINK_RESEARCH": "Research the new architecture",
            "NORTHSTAR_OS_COMMERCE": "Update the profit tier thresholds",
            "NORTHSTAR_OS_PROVIDER": "Bright Data Web Unlocker configuration",
            "T2_OPERATIONS": "Sunday 03:00 Costco catalog refresh",
            "PLATFORM_ADMIN": "Deploy to Cloudflare Workers",
        }
        for track, s in reachable.items():
            self.assertEqual(mbg.classify_task(s), track, msg=f"Track {track} not reachable from: {s!r}")


class AuditLogTests(unittest.TestCase):
    """Append-only JSONL audit log — never overwrites, confirms structure."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmpdir, "audit.log.jsonl")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_write_and_read_single_entry(self):
        mbg.write_audit_entry(
            track="AUTOTHINK_CODE",
            files_touched=["test.py"],
            live_action_requested=False,
            approval_status="not_requested",
            log_path=self.log_path,
        )
        entries = mbg.read_audit_log(self.log_path)
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e["track"], "AUTOTHINK_CODE")
        self.assertEqual(e["files_touched"], ["test.py"])
        self.assertFalse(e["live_action_requested"])
        self.assertEqual(e["approval_status"], "not_requested")
        self.assertIn("timestamp", e)
        self.assertIn("metadata", e)

    def test_append_only_multiple_entries(self):
        mbg.write_audit_entry("AUTOTHINK_RESEARCH", log_path=self.log_path)
        mbg.write_audit_entry("NORTHSTAR_OS_COMMERCE", live_action_requested=True, approval_status="pending", log_path=self.log_path)
        mbg.write_audit_entry("PLATFORM_ADMIN", files_touched=["wrangler.toml"], log_path=self.log_path)
        entries = mbg.read_audit_log(self.log_path)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0]["track"], "AUTOTHINK_RESEARCH")
        self.assertEqual(entries[1]["track"], "NORTHSTAR_OS_COMMERCE")
        self.assertTrue(entries[1]["live_action_requested"])
        self.assertEqual(entries[1]["approval_status"], "pending")
        self.assertEqual(entries[2]["track"], "PLATFORM_ADMIN")

    def test_invalid_track_raises(self):
        with self.assertRaises(ValueError):
            mbg.write_audit_entry("INVALID_TRACK", log_path=self.log_path)

    def test_all_valid_tracks_accepted(self):
        for track in mbg.TRACKS:
            mbg.write_audit_entry(track, log_path=self.log_path)
        entries = mbg.read_audit_log(self.log_path)
        self.assertEqual(len(entries), len(mbg.TRACKS))

    def test_metadata_field_preserved(self):
        mbg.write_audit_entry(
            "AUTOTHINK_CODE",
            metadata={"commit": "abc123", "lines_changed": 42},
            log_path=self.log_path,
        )
        entries = mbg.read_audit_log(self.log_path)
        self.assertEqual(entries[0]["metadata"], {"commit": "abc123", "lines_changed": 42})

    def test_missing_log_returns_empty_list(self):
        missing = os.path.join(self.tmpdir, "missing.log.jsonl")
        self.assertEqual(mbg.read_audit_log(missing), [])

    def test_corrupt_log_line_handled(self):
        with open(self.log_path, "w", encoding="utf-8") as f:
            f.write('{"valid": "json"}\n')
            f.write("not json\n")
            f.write('{"track": "AUTOTHINK_CODE"}\n')
        entries = mbg.read_audit_log(self.log_path)
        # Should skip corrupt line, keep valid ones
        self.assertEqual(len(entries), 2)


if __name__ == "__main__":
    unittest.main()