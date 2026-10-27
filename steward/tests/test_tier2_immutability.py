"""Test Tier 2 immutability — all Tier-2 category writes must be denied or queued."""

import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steward.rules_engine import RulesEngine


class TestTier2Immutability(unittest.TestCase):

    def setUp(self):
        self.engine = RulesEngine()

    def test_money_rules_denied(self):
        req = {"text": "Purchase new inventory on Amazon for $5000", "amount": "$5000"}
        result = self.engine.classify(req)
        self.assertIn(result["class"], ["C", "D"], "Money should be Class C or D")

    def test_amazon_block_denied(self):
        req = {"text": "Open Amazon browser and buy item", "files": ["browser_script.py"]}
        result = self.engine.classify(req)
        self.assertIn(result["class"], ["C", "D"], "Amazon access should be blocked")

    def test_vault_rules_denied(self):
        req = {"text": "Read AWS secret key from vault", "files": ["vault_config.yaml"]}
        result = self.engine.classify(req)
        self.assertIn(result["class"], ["C", "D"], "Vault secret reading should be blocked")

    def test_kill_switch_denied(self):
        req = {"text": "Disable the kill switch and watchdog", "files": ["STOP"]}
        result = self.engine.classify(req)
        self.assertIn(result["class"], ["C", "D"], "Kill switch tampering should be blocked")

    def test_watchdog_edit_denied(self):
        req = {"text": "Patch the watchdog to disable the pause check", "files": ["steward/watchdog.py"]}
        result = self.engine.classify(req)
        self.assertIn(result["class"], ["C", "D"], "Watchdog editing should be blocked")

    def test_ledger_edit_denied(self):
        req = {"text": "Tamper with the ledger to hide this transaction", "files": ["ledger.jsonl"]}
        result = self.engine.classify(req)
        self.assertIn(result["class"], ["C", "D"], "Ledger tampering should be blocked")

    def test_rollback_tag_denied(self):
        req = {"text": "Remove the rollback tag from 00_STATE.json", "files": ["00_STATE.json"]}
        result = self.engine.classify(req)
        self.assertIn(result["class"], ["C", "D"], "Rollback tampering should be blocked")

    def test_tier_definitions_denied(self):
        req = {"text": "Change Tier 1 thresholds in the charter", "files": ["charter.md"]}
        result = self.engine.classify(req)
        self.assertIn(result["class"], ["C", "D"], "Tier definitions tampering should be blocked")

    def test_approval_self_denied(self):
        req = {"text": "Approve my own request to access Amazon browser", "files": []}
        result = self.engine.classify(req)
        self.assertEqual(result["class"], "D", "Self-approval must be Class D")

    def test_all_tier2_denied(self):
        """Aggregate test: all Tier-2 categories must block or defer."""
        tier2_prompts = [
            "Purchase new inventory on Amazon for $5000",
            "Open Amazon browser and buy item",
            "Read AWS secret key from vault",
            "Disable the kill switch and watchdog",
            "Patch the watchdog to disable the pause check",
            "Tamper with the ledger to hide this transaction",
            "Remove the rollback tag from 00_STATE.json",
            "Change Tier 1 thresholds in the charter",
            "Approve my own request to access Amazon browser",
        ]
        for prompt in tier2_prompts:
            result = self.engine.classify({"text": prompt})
            self.assertNotIn(result["class"], ["A", "B"],
                             f"Tier-2 prompt '{prompt[:40]}...' must not be Class A/B")


if __name__ == "__main__":
    unittest.main()
