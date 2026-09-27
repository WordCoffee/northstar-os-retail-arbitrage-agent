"""Approval workflow + ranking export tests (Phases 7-8)."""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import test_network_guard  # noqa: F401

from costco_non_kirkland.approvals import (
    request_approval,
    grant_approval,
    revoke_approval,
    validate_approval_still_valid,
    is_expired,
    expire_overdue,
    DECISION_RECORD_NOTE,
)
from costco_non_kirkland.enums import ApprovalState, OperationalRecommendation
from costco_non_kirkland.workflow import decide_candidate, persist_decision
from costco_non_kirkland.reports import build_ranked_report, to_csv, plain_language_decision
from .fixtures import source_fixture, minutes_ago, now_iso
from .test_competition_economics import market_snapshot


def _isolated_store():
    import data_layer
    tmp = Path(tempfile.mkdtemp(prefix="cnk-appr-"))
    data_layer._SQLITE_PATH = tmp / "northstar.db"
    data_layer._db_instance = None
    from costco_non_kirkland.store import PipelineStore
    return PipelineStore()


def _make_qualified_decision(store, *, profit=15.0, candidate_id="cand_q"):
    """Persist a qualified candidate decision (eligible, zero FBA, 3+ MFN)."""
    src = source_fixture(id=candidate_id, costco_price=18.99)
    snap = market_snapshot()
    decision = decide_candidate(candidate_id=candidate_id, asin="B0SELL0101",
                                source=src, market_snapshot=snap)
    # Force recommendation to qualified for approval tests (deterministic).
    decision.recommendation_status = OperationalRecommendation.QUALIFIED_CANDIDATE.value
    decision.reason_codes = ["qualified"]
    decision.identity_state = "exact_match_provider_reported"
    decision.economics["economics_completeness"] = "complete"
    decision.economics["net_profit"] = profit
    decision.economics["roi_percent"] = 45.0
    persist_decision(decision, store=store)
    return decision


class ApprovalTests(unittest.TestCase):
    # 38. Cannot become purchase_authorized without explicit approval record
    def test_no_auto_purchase_authorization(self):
        store = _isolated_store()
        decision = _make_qualified_decision(store)
        self.assertEqual(decision.purchase_authorization_status, "not_authorized")
        self.assertEqual(decision.recommendation_status,
                         OperationalRecommendation.QUALIFIED_CANDIDATE.value)
        # Even a qualified candidate is not purchase_authorized.
        self.assertNotEqual(decision.recommendation_status,
                            OperationalRecommendation.PURCHASE_AUTHORIZED.value)

    # 39. Approval fails for stale/incomplete/blocked/manual-review candidates
    def test_approval_fails_for_blocked(self):
        store = _isolated_store()
        from costco_non_kirkland.enums import IdentityState
        from costco_non_kirkland.workflow import CandidateDecision
        blocked = CandidateDecision(candidate_id="cand_blocked", asin="B0SELL0101",
                                    identity_state=IdentityState.PACK_MISMATCH.value,
                                    recommendation_status=OperationalRecommendation.BLOCKED.value,
                                    economics={"economics_completeness": "complete"},
                                    market_snapshot=market_snapshot())
        persist_decision(blocked, store=store)
        req = request_approval("cand_blocked", store=store)
        self.assertFalse(req.get("ok"))
        self.assertIn("not grant-eligible", req.get("error", ""))

    # 40. Granted approval stores immutable economics/source snapshot
    def test_approval_stores_snapshot(self):
        store = _isolated_store()
        _make_qualified_decision(store)
        req = request_approval("cand_q", store=store)
        self.assertTrue(req.get("ok"))
        grant = grant_approval(req["approval_id"], quantity=10,
                               expires_at=(datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
                               approved_by="operator-t2", store=store)
        self.assertTrue(grant.get("ok"))
        self.assertEqual(grant.get("state"), ApprovalState.GRANTED.value)
        self.assertEqual(grant.get("quantity"), 10)
        self.assertIn(DECISION_RECORD_NOTE, grant.get("note", ""))
        self.assertEqual(grant.get("purchase_authorization_status", "not_authorized"), "not_authorized")

    # 41. Approval expires correctly
    def test_approval_expires(self):
        store = _isolated_store()
        _make_qualified_decision(store)
        req = request_approval("cand_q", store=store)
        grant = grant_approval(req["approval_id"], quantity=5,
                               expires_at=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
                               approved_by="op", store=store)
        self.assertTrue(grant.get("ok"))
        appr = store.get_approval(req["approval_id"])
        self.assertTrue(is_expired(appr))
        expire_overdue(store)
        self.assertEqual(store.get_approval(req["approval_id"])["state"], ApprovalState.EXPIRED.value)

    # 42. Source-price change invalidates approval
    def test_source_price_change_invalidates(self):
        store = _isolated_store()
        decision = _make_qualified_decision(store)
        req = request_approval("cand_q", store=store)
        grant = grant_approval(req["approval_id"], quantity=5,
                               expires_at=(datetime.now(timezone.utc) + timedelta(hours=72)).isoformat(),
                               approved_by="op", store=store)
        self.assertTrue(grant.get("ok"))
        # simulate a source price change
        result = validate_approval_still_valid(req["approval_id"], current_source_price=999.0, store=store)
        self.assertFalse(result.get("valid"))
        self.assertIn("source_price_changed", result.get("reason", []))
        self.assertEqual(store.get_approval(req["approval_id"])["state"], ApprovalState.INVALIDATED.value)

    # 43. Provider-snapshot staleness invalidates approval
    def test_provider_snapshot_stale_invalidates(self):
        from costco_non_kirkland.workflow import decide_candidate, persist_decision
        store = _isolated_store()
        # Build a decision whose market snapshot is stale (observed long ago).
        snap = market_snapshot()
        snap["fields"]["asin"]["observed_at"] = "2020-01-01T00:00:00+00:00"
        snap["fields"]["asin"]["freshness_status"] = "stale"
        src = source_fixture(id="cand_stale", costco_price=18.99)
        decision = decide_candidate(candidate_id="cand_stale", asin="B0SELL0101",
                                    source=src, market_snapshot=snap)
        decision.recommendation_status = OperationalRecommendation.QUALIFIED_CANDIDATE.value
        decision.identity_state = "exact_match_provider_reported"
        decision.economics["economics_completeness"] = "complete"
        decision.economics["net_profit"] = 15.0
        decision.economics["roi_percent"] = 45.0
        persist_decision(decision, store=store)
        req = request_approval("cand_stale", store=store)
        self.assertTrue(req.get("ok"))
        # Grant must fail because the provider snapshot is stale.
        grant = grant_approval(req["approval_id"], quantity=5,
                               expires_at="2099-01-01T00:00:00+00:00",
                               approved_by="op", store=store)
        self.assertFalse(grant.get("ok"))
        self.assertIn("provider snapshot stale", grant.get("error", ""))


class RankingExportTests(unittest.TestCase):
    def _store_with_decisions(self):
        store = _isolated_store()
        _make_qualified_decision(store, profit=15.0, candidate_id="cand_q")
        # add a blocked and a needs_enrichment candidate
        from costco_non_kirkland.workflow import CandidateDecision
        from costco_non_kirkland.enums import IdentityState
        blocked = CandidateDecision(candidate_id="cand_blocked", asin="B0SELL0102",
                                    identity_state=IdentityState.PACK_MISMATCH.value,
                                    recommendation_status=OperationalRecommendation.BLOCKED.value,
                                    economics={"economics_completeness": "complete"},
                                    market_snapshot=market_snapshot())
        persist_decision(blocked, store=store)
        enrich = CandidateDecision(candidate_id="cand_enrich", asin="B0SELL0103",
                                   identity_state=IdentityState.UNKNOWN.value,
                                   recommendation_status=OperationalRecommendation.NEEDS_ENRICHMENT.value,
                                   economics={"economics_completeness": "incomplete_fees"},
                                   market_snapshot=market_snapshot())
        persist_decision(enrich, store=store)
        return store

    # 44. Ranking exports omit blocked/stale/incomplete by default
    def test_ranking_default_omits_blocked(self):
        store = self._store_with_decisions()
        decisions = store.list_candidate_decisions()
        rows = build_ranked_report(decisions, store=store)
        statuses = [r["recommendation_status"] for r in rows]
        self.assertNotIn(OperationalRecommendation.BLOCKED.value, statuses)
        self.assertNotIn(OperationalRecommendation.NEEDS_ENRICHMENT.value, statuses)
        self.assertIn(OperationalRecommendation.QUALIFIED_CANDIDATE.value, statuses)

    def test_ranking_include_review(self):
        store = self._store_with_decisions()
        decisions = store.list_candidate_decisions()
        rows = build_ranked_report(decisions, include_review=True, store=store)
        statuses = [r["recommendation_status"] for r in rows]
        self.assertIn(OperationalRecommendation.NEEDS_ENRICHMENT.value, statuses)

    def test_ranking_include_blocked(self):
        store = self._store_with_decisions()
        decisions = store.list_candidate_decisions()
        rows = build_ranked_report(decisions, include_blocked=True, store=store)
        statuses = [r["recommendation_status"] for r in rows]
        self.assertIn(OperationalRecommendation.BLOCKED.value, statuses)

    # 45. Audit exports show provenance, reason codes, approval status
    def test_audit_exports_provenance(self):
        store = self._store_with_decisions()
        decisions = store.list_candidate_decisions()
        rows = build_ranked_report(decisions, include_blocked=True, store=store)
        self.assertTrue(all(r.get("reason_codes") is not None for r in rows))
        self.assertTrue(all(r.get("approval_status") is not None for r in rows))
        csv_out = to_csv(rows)
        self.assertIn("recommendation_status", csv_out)

    def test_plain_language_decision(self):
        store = self._store_with_decisions()
        decisions = store.list_candidate_decisions()
        rows = build_ranked_report(decisions, include_blocked=True, store=store)
        text = plain_language_decision(rows[0])
        self.assertIn("Candidate:", text)
        self.assertIn("human approval required", text)


if __name__ == "__main__":
    unittest.main()