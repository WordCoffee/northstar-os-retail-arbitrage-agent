"""Mocked tests for reasoning task workflows.

All provider calls are intercepted with MockReasoningProvider. No live calls.
"""

from __future__ import annotations

import json
import unittest

from adapters.base import ProviderResponse, ProviderStatus
from adapters.reasoning_provider import MockReasoningProvider, ReasoningProvider
from reasoning_tasks import (
    ad_copy_proposal,
    listing_proposal,
    reasoning_run,
    spreadsheet_analysis,
)


class _RejectingProvider(ReasoningProvider):
    name = "rejecting"
    required_env = []
    optional_env = []

    def available(self):
        return True

    def armed(self):
        return True

    def complete(self, request):
        return ProviderResponse(
            success=False,
            status=ProviderStatus.AUTH_ERROR,
            provider=self.name,
            error="missing credentials",
        )


class ListingProposalTests(unittest.TestCase):
    def test_listing_proposal_parses_json_and_validates(self):
        provider = MockReasoningProvider(
            response_text=json.dumps({
                "sku": "SKU-123",
                "proposed": {
                    "title": "A" * 201,
                    "bullets": ["b1", "b2", "b3", "b4", "b5"],
                    "description": "desc",
                    "attributes": {"color": "blue"},
                },
                "reasons": ["made title longer"],
                "missing_evidence": ["weight"],
                "warnings": [],
            })
        )
        result = listing_proposal(
            sku="SKU-123",
            title="Old title",
            bullets=["b1", "b2", "b3", "b4", "b5"],
            description="Old desc",
            attributes={"color": "blue"},
            provider=provider,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["sku"], "SKU-123")
        self.assertEqual(result["proposed"]["attributes"]["color"], "blue")
        self.assertIn("Proposed title exceeds 200 characters.", result["warnings"])

    def test_listing_proposal_detects_prohibited_words(self):
        provider = MockReasoningProvider(
            response_text=json.dumps({
                "sku": "SKU-123",
                "proposed": {
                    "title": "The best water filter",
                    "bullets": ["b1", "b2", "b3", "b4", "b5"],
                    "description": "desc",
                    "attributes": {},
                },
                "reasons": [],
                "missing_evidence": [],
                "warnings": [],
            })
        )
        result = listing_proposal(
            sku="SKU-123",
            title="Old title",
            bullets=["b1", "b2", "b3", "b4", "b5"],
            description="Old desc",
            provider=provider,
        )
        self.assertTrue(result["ok"])
        self.assertTrue(any("best" in w for w in result["warnings"]))

    def test_listing_proposal_surfaces_provider_error(self):
        result = listing_proposal(
            sku="SKU-123",
            title="Old title",
            bullets=["b1"],
            description="Old desc",
            provider=_RejectingProvider(),
        )
        self.assertFalse(result["ok"])
        self.assertIn("missing credentials", result["error"])

    def test_listing_proposal_surfaces_invalid_json(self):
        provider = MockReasoningProvider(response_text="not json")
        result = listing_proposal(
            sku="SKU-123",
            title="Old title",
            bullets=["b1"],
            description="Old desc",
            provider=provider,
        )
        self.assertFalse(result["ok"])
        self.assertIn("valid JSON", result["error"])


class AdCopyTests(unittest.TestCase):
    def test_ad_copy_proposal_returns_structured_output(self):
        provider = MockReasoningProvider(
            response_text=json.dumps({
                "headlines": ["H1", "H2"],
                "body": "Body copy",
                "cta": "Shop now",
                "brand_tone": "professional",
                "unsupported_claims": ["cures all"],
                "warnings": ["check claims"],
            })
        )
        result = ad_copy_proposal(
            product_facts={"sku": "SKU-123", "name": "Water Filter"},
            brand_tone="professional",
            provider=provider,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["headlines"], ["H1", "H2"])
        self.assertEqual(result["cta"], "Shop now")
        self.assertEqual(result["unsupported_claims"], ["cures all"])
        self.assertIsNone(result["approved_copy"])


class SpreadsheetTests(unittest.TestCase):
    def test_spreadsheet_analysis_returns_structured_output(self):
        provider = MockReasoningProvider(
            response_text=json.dumps({
                "row_count": 2,
                "columns": ["sku", "cost"],
                "summary": "Two rows",
                "anomalies": ["negative cost in row 2"],
                "inferred_formulas": [],
                "suggested_exports": ["cleaned_csv"],
                "warnings": [],
            })
        )
        result = spreadsheet_analysis(
            rows=[{"sku": "A", "cost": 10}, {"sku": "B", "cost": -5}],
            file_name="test.csv",
            provider=provider,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["row_count"], 2)
        self.assertEqual(result["columns"], ["sku", "cost"])
        self.assertIn("negative cost in row 2", result["anomalies"])


class GenericRunTests(unittest.TestCase):
    def test_reasoning_run_returns_content(self):
        provider = MockReasoningProvider(response_text="answer")
        result = reasoning_run(query="q", provider=provider)
        self.assertTrue(result["ok"])
        self.assertEqual(result["content"], "answer")
        self.assertEqual(result["provider"], "mock_reasoning")

    def test_reasoning_run_surfaces_error(self):
        result = reasoning_run(query="q", provider=_RejectingProvider())
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "missing credentials")


if __name__ == "__main__":
    unittest.main()
