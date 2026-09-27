"""Tests for the offline Bright Data preflight (fixture-only, zero network, no secrets)."""
from __future__ import annotations

import json
import os
import unittest

import test_network_guard  # noqa: F401

from costco_non_kirkland.brightdata_costco_enrichment import (
    preflight,
    render_preflight_markdown,
    run_enrichment,
    FIELD_PURPOSE_MAP,
)


class PreflightTests(unittest.TestCase):
    def test_no_configured_source_is_provider_not_configured(self):
        rep = preflight({}, env={})
        self.assertEqual(rep["result_status"], "provider_not_configured")
        self.assertFalse(rep["source_id_configured"])
        self.assertEqual(rep["network_calls_made"], 0)

    def test_missing_approval_gates_enumerated(self):
        rep = preflight({"sample_size": 25, "items": []}, env={})
        for g in ("approved_flag", "env_enrichment_approved", "env_brightdata_enabled",
                  "source_id_configured", "spend_cap_set"):
            self.assertIn(g, rep["unsatisfied_gates"])
        self.assertFalse(rep["approval_gates"]["approved_flag"])

    def test_no_credentials_printed(self):
        secret = "SUPER-SECRET-KEY-123"
        rep = preflight({}, env={"BRIGHTDATA_UNLOCKER_API_KEY": secret, "BRIGHTDATA_API_KEY": secret})
        blob = json.dumps(rep)
        self.assertNotIn(secret, blob)
        self.assertFalse(rep["credentials_printed"])
        self.assertTrue(rep["credential_env_set"]["BRIGHTDATA_UNLOCKER_API_KEY"])

    def test_source_id_present_reports_configured(self):
        rep = preflight({}, env={"NORTHSTAR_BRIGHTDATA_SOURCE_ID": "abc123"})
        self.assertTrue(rep["source_id_configured"])
        self.assertEqual(rep["result_status"], "configured_source_id_present_unverified")
        # value not printed
        self.assertNotIn("abc123", json.dumps(rep))

    def test_mandatory_optional_classification(self):
        rep = preflight({}, env={})
        self.assertIn("upc", rep["mandatory_fields_by_purpose"]["identifier_resolution"])
        self.assertIn("net_weight", rep["mandatory_fields_by_purpose"]["weight_size_validation"])
        self.assertIn("outer_pack_count", rep["mandatory_fields_by_purpose"]["pack_validation"])
        self.assertIn("description", rep["optional_fields"])
        self.assertIn("costco_item_number", rep["requested_fields"])

    def test_preflight_cannot_run_live_enrichment(self):
        # The preflight function has no run capability; the live runner still fails closed.
        out = run_enrichment({}, approved=False)
        self.assertEqual(out["result_status"], "requires_explicit_approval")
        self.assertEqual(out["network_calls_made"], 0)

    def test_report_renders_unknown_cost_and_coverage(self):
        rep = preflight({}, env={})
        md = render_preflight_markdown(rep)
        self.assertIn("cost unknown", md.lower())
        self.assertIn("provider_not_configured", md)

    def test_zero_network(self):
        import requests
        from network_guard import NetworkGuardViolation
        with self.assertRaises(NetworkGuardViolation):
            requests.get("http://127.0.0.1:9/", timeout=0.1)


if __name__ == "__main__":
    unittest.main()
