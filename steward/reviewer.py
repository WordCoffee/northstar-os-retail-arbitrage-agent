"""Reviewer role — runs separately from Builder, checks intent-vs-built.

Per charter §2 and §5: "Reviewer: checks Builder claims against deterministic
evidence (tests, diff, intent-vs-built). Not the same prompt or session as
Builder."

The Reviewer:
- Cannot approve its own work (no self-approval)
- Checks intent-vs-built table against evidence
- Runs in a separate session from Builder
- Produces a verdict: PASS/FAIL with evidence refs
"""

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Reviewer:
    """Independent reviewer that checks Builder claims against evidence."""

    def __init__(self, reviewer_id: str = "reviewer-1"):
        self.reviewer_id = reviewer_id
        self._approved_by = None  # Tracks who approved (must not be self)

    def review_intent_vs_built(self, intent: Dict[str, Any],
                                built: Dict[str, Any],
                                evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Check if built matches intent.

        Returns a verdict dict with:
        - verdict: "PASS" or "FAIL"
        - mismatches: list of mismatches found
        - evidence_refs: list of evidence references
        - reviewer_id: this reviewer's ID
        """
        mismatches = []

        # Check that all intent items have corresponding built items.
        intent_items = intent.get("items", [])
        built_items = built.get("items", [])
        built_ids = {b.get("id") for b in built_items}

        for item in intent_items:
            item_id = item.get("id")
            if item_id not in built_ids:
                mismatches.append(f"Intent item '{item_id}' not found in built")

        # Check that built items don't exceed intent scope.
        for b in built_items:
            b_id = b.get("id")
            if b_id not in {i.get("id") for i in intent_items}:
                mismatches.append(f"Built item '{b_id}' not in intent (scope creep)")

        # Check evidence: tests pass, no forbidden paths, diff within scope.
        tests_pass = evidence.get("tests_pass", False)
        if not tests_pass:
            mismatches.append("Tests do not pass")

        forbidden_paths = evidence.get("forbidden_paths", [])
        if forbidden_paths:
            mismatches.append(f"Forbidden paths touched: {forbidden_paths}")

        diff_scope_ok = evidence.get("diff_scope_ok", True)
        if not diff_scope_ok:
            mismatches.append("Diff exceeds declared scope")

        secret_scan_clean = evidence.get("secret_scan_clean", True)
        if not secret_scan_clean:
            mismatches.append("Secret scan not clean")

        verdict = "PASS" if len(mismatches) == 0 else "FAIL"

        return {
            "verdict": verdict,
            "mismatches": mismatches,
            "evidence_refs": evidence.get("refs", []),
            "reviewer_id": self.reviewer_id,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "intent_count": len(intent_items),
            "built_count": len(built_items),
        }

    def approve(self, verdict: Dict[str, Any], approver_id: str) -> bool:
        """Approve a review verdict. Cannot approve own work.

        Returns True if approval succeeded, False if self-approval attempted.
        """
        if approver_id == self.reviewer_id:
            # Self-approval attempt — denied per charter §1.2
            return False
        self._approved_by = approver_id
        return True

    def get_approval_status(self) -> Optional[str]:
        """Return who approved this review, or None if not approved."""
        return self._approved_by