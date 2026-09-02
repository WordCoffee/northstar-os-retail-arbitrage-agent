import os
os.environ["QUOTA_TRACKER_PATH"] = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "_test_quota_tmp.json")

import json
import tempfile
import unittest

import approval as ap
import benchmark_drift as bd
import kirkland_discovery as kd
import pipeline_dry_run as dr
import provider_waterfall_router as rf
import quota_tracker as qt
import rapidapi_router
import snapshot_builder as sb
import unit_economics as ue

REALTIME_FIXTURE = {
    "data": {
        "asin": "B000KIRK01",
        "product_title": "Kirkland Signature Vitamin C 500mg",
        "product_price": "9.99",
        "product_offers": [
            {"seller": "Amazon", "product_price": "9.99",
             "product_condition": "New", "ships_from": "Amazon"}
        ],
        "main_buy_box": {"price": "9.99", "seller": "Amazon", "seller_id": "A1"},
        "product_information": {"Best Sellers Rank": "#123 in Health"},
        "product_num_offers": 5,
        "is_prime": True,
    }
}

DATAFORSEO_FIXTURE = {
    "title": "Kirkland Signature Vitamin C 500mg",
    "buy_box_price": 9.99,
    "buy_box_seller": "Amazon",
    "bsr": {"rank": 123, "category": "Health"},
    "offers": [{"seller_name": "Amazon", "price": 9.99, "is_fba": True,
                "fulfillment": "FBA", "seller_id": "A1", "condition": "New",
                "ships_from": "Amazon", "buybox_winner": True}],
    "offer_count": 1, "offers_returned_count": 1,
}

GENUINE_A = {"asin": "B000KIRK01", "title": "Kirkland Signature Vitamin C 500mg",
             "brand": "Kirkland Signature"}
GENUINE_B = {"asin": "B000KIRK02", "title": "Kirkland Signature Olive Oil",
             "brand": "Kirkland Signature"}
NON_BRAND = {"asin": "B000NON001", "title": "Amazon Brand Echo", "brand": "Amazon"}
NEAR = {"asin": "B000NEAR01", "title": "Kirkland-ish thing", "brand": "Kirkland"}


def mock_search(q, page):
    if page != 1:
        return []
    if q == "Kirkland Signature":
        return [GENUINE_A, NON_BRAND, NEAR, GENUINE_A]  # dup A within query
    if q == "Kirkland Signature vitamins supplements":
        return [GENUINE_A, GENUINE_B]  # A dup across queries, B new
    return []


def make_fetch(success_app, fixture):
    calls = []

    def fetch(app, asin):
        calls.append(app)
        if app == success_app:
            return 200, fixture
        return 403, None
    return fetch, calls


class TestDiscovery(unittest.TestCase):
    def test_pagination_dedup_brand_filter(self):
        seen, rejected = kd.discover(mock_search, max_pages=3)
        self.assertIn("B000KIRK01", seen)
        self.assertIn("B000KIRK02", seen)
        self.assertEqual(len(seen), 2)  # dedup across queries + within query
        reasons = {r["asin"]: r["reason"] for r in rejected}
        self.assertIn("B000NON001", reasons)
        self.assertIn("B000NEAR01", reasons)
        self.assertEqual(reasons["B000NON001"], "brand_not_kirkland_signature")
        self.assertEqual(reasons["B000NEAR01"], "brand_not_kirkland_signature")


class TestQuotaTracker(unittest.TestCase):
    def setUp(self):
        self.path = tempfile.mktemp(suffix=".json")

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_update_from_headers_only(self):
        state = qt.update_from_headers(
            "RAPIDAPI_REALTIME", "enrichment",
            {"X-RateLimit-Requests-Limit": "100", "X-RateLimit-Requests-Remaining": "87"},
            path=self.path)
        slot = state["apps"]["RAPIDAPI_REALTIME"]["enrichment"]
        self.assertEqual(slot["remaining"], 87)
        self.assertEqual(slot["used"], 13)  # derived, header-only
        self.assertEqual(slot["limit"], 100)

    def test_exhausted_flag(self):
        qt.mark_exhausted("RAPIDAPI_BDC", "enrichment", "http_403", path=self.path)
        self.assertTrue(qt.is_exhausted("RAPIDAPI_BDC", "enrichment", path=self.path))


class TestWaterfall(unittest.TestCase):
    def _exhaust_all_rapidapi(self, state):
        for a in rf.RAPIDAPI_POOL:
            state["apps"][a]["enrichment"]["exhausted"] = True

    def test_priority_order_and_skip_exhausted(self):
        state = qt._empty_state()
        state["apps"]["RAPIDAPI_BDC"]["enrichment"]["exhausted"] = True
        state["apps"]["RAPIDAPI_REALTIME"]["enrichment"]["exhausted"] = True
        fetch, calls = make_fetch("RAPIDAPI_AXESSO", REALTIME_FIXTURE)
        gates = rf.WarningGates()
        approvals = ap.Approvals()
        snap, audit = rf.route_asin(
            "B000KIRK01", fetch, approvals=approvals, quota_state=state, gates=gates)
        self.assertIsNotNone(snap)
        self.assertEqual(audit["final_source"], "RAPIDAPI_AXESSO")
        # Exhausted apps are skipped WITHOUT a network call (audit shows the skip).
        skipped = [t["app"] for t in audit["tried"] if t["result"] == "skipped_exhausted"]
        self.assertIn("RAPIDAPI_BDC", skipped)
        self.assertIn("RAPIDAPI_REALTIME", skipped)
        self.assertEqual(calls, ["RAPIDAPI_AXESSO"])  # only the non-exhausted app is fetched

    def test_gate1_fires_once_when_rapidapi_exhausted_approved(self):
        state = qt._empty_state()
        self._exhaust_all_rapidapi(state)
        state["apps"]["DATAFORSEO"]["enrichment"]["remaining"] = 0  # free exhausted -> gate2
        fetch, _ = make_fetch("DATAFORSEO", DATAFORSEO_FIXTURE)
        gates = rf.WarningGates()
        approvals = ap.Approvals()
        approvals.approve_enrichment()
        snap, audit = rf.route_asin(
            "B000KIRK01", fetch, approvals=approvals, quota_state=state, gates=gates)
        self.assertIsNotNone(snap)
        self.assertEqual(audit["final_source"], "DATAFORSEO")
        self.assertEqual(gates.fired_count("gate1_rapidapi_exhausted"), 1)
        self.assertEqual(gates.fired_count("gate2_dataforseo_paid"), 1)

    def test_gate1_blocks_without_approval(self):
        state = qt._empty_state()
        self._exhaust_all_rapidapi(state)
        fetch, _ = make_fetch("DATAFORSEO", DATAFORSEO_FIXTURE)
        gates = rf.WarningGates()
        approvals = ap.Approvals()  # not approved
        snap, audit = rf.route_asin(
            "B000KIRK01", fetch, approvals=approvals, quota_state=state, gates=gates)
        self.assertIsNone(snap)
        self.assertEqual(audit["validation"], "blocked_gate1")
        self.assertEqual(gates.fired_count("gate1_rapidapi_exhausted"), 1)
        self.assertEqual(gates.fired_count("gate2_dataforseo_paid"), 0)

    def test_gates_fire_exactly_once_across_batch(self):
        state = qt._empty_state()
        self._exhaust_all_rapidapi(state)
        state["apps"]["DATAFORSEO"]["enrichment"]["remaining"] = 0
        fetch, _ = make_fetch("DATAFORSEO", DATAFORSEO_FIXTURE)
        gates = rf.WarningGates()
        approvals = ap.Approvals()
        approvals.approve_enrichment()
        snaps, audits = rf.route_batch(
            ["B000KIRK01", "B000KIRK02"], fetch, approvals=approvals,
            quota_state=state, gates=gates)
        self.assertEqual(len(snaps), 2)
        self.assertEqual(gates.fired_count("gate1_rapidapi_exhausted"), 1)
        self.assertEqual(gates.fired_count("gate2_dataforseo_paid"), 1)


class TestSchemaValidation(unittest.TestCase):
    def _good_market(self):
        return rapidapi_router.to_intel_market_real_time(
            "B000KIRK01", REALTIME_FIXTURE)

    def test_valid_snapshot_passes(self):
        market = self._good_market()
        snap = sb.build_snapshot("B000KIRK01", market, "rapidapi_realtime",
                                 title="Kirkland Signature Vitamin C 500mg")
        self.assertEqual(snap["validation_status"], "valid")
        self.assertIsNone(snap["validation_errors"])

    def test_fabricated_zero_price_rejected(self):
        bad = {
            "amazon_price": 0,
            "bsr": {"bsr_capture_status": "unavailable"},
            "buy_box": {"available": False, "price": None, "source": None, "observed_at": None},
            "seller_counts": {"total_observed": None, "fba_observed": None,
                              "fbm_observed": None, "amazon_observed": None,
                              "claimed_total": None},
            "coverage": {"offer_list_available": False, "offers_complete_status": "unknown",
                         "coverage_reason": "x"},
            "offers": [],
        }
        snap = sb.build_snapshot("B000X", bad, "test")
        self.assertEqual(snap["validation_status"], "invalid")
        self.assertTrue(any("amazon_price is 0" in e for e in snap["validation_errors"]))

    def test_missing_price_null_not_fabricated(self):
        market = self._good_market()
        market["amazon_price"] = None
        snap = sb.build_snapshot("B000KIRK01", market, "rapidapi_realtime")
        self.assertEqual(snap["validation_status"], "valid")
        self.assertIsNone(snap["facts"]["market"]["amazon_price"])


class TestSnapshotWrite(unittest.TestCase):
    def test_write_path_succeeds(self):
        market = rapidapi_router.to_intel_market_real_time(
            "B000KIRK01", REALTIME_FIXTURE)
        snap = sb.build_snapshot("B000KIRK01", market, "rapidapi_realtime")
        path = sb.write_run_snapshots({"B000KIRK01": snap})
        self.assertTrue(os.path.exists(path))
        with open(path) as f:
            payload = json.load(f)
        self.assertIn("B000KIRK01", payload["asins"])


class TestBenchmarkDrift(unittest.TestCase):
    def test_overlapping_and_nonoverlapping(self):
        market = rapidapi_router.to_intel_market_real_time(
            "B000KIRK01", REALTIME_FIXTURE)
        snap = sb.build_snapshot("B000KIRK01", market, "rapidapi_realtime",
                                 title="Kirkland Signature Vitamin C 500mg")
        other_market = dict(market)
        other = sb.build_snapshot("B000OTHER", other_market, "rapidapi_realtime",
                                  title="Other Product")
        canonical = {
            "B000KIRK01": {"asin": "B000KIRK01", "title": "Kirkland Signature Vitamin C 500mg",
                           "price": 9.99, "reviews": 100, "prime_fba": "yes",
                           "bsr_rank_number": 123, "bsr_category": "Health"},
        }
        out = bd.compare_batch({"B000KIRK01": snap, "B000OTHER": other}, canonical)
        self.assertTrue(out["B000KIRK01"]["benchmark_overlap"])
        self.assertFalse(out["B000OTHER"]["benchmark_overlap"])
        self.assertIsNone(out["B000OTHER"]["benchmark_fields"])
        self.assertEqual(out["B000OTHER"]["disposition"], "no_benchmark_reference")


class TestEconomics(unittest.TestCase):
    def test_estimated_cost_flagged(self):
        market = rapidapi_router.to_intel_market_real_time(
            "B000KIRK01", REALTIME_FIXTURE)
        snap = sb.build_snapshot("B000KIRK01", market, "rapidapi_realtime")
        econ = ue.compute_economics(snap, {"B000KIRK01": {"cost": 5.0, "status": "estimated"}})
        self.assertEqual(econ["net_profit"], 4.99)
        self.assertEqual(econ["cost_basis_flag"], "estimated")
        self.assertEqual(econ["economics_confidence"], "estimated")

    def test_invoice_confirmed_not_flagged_estimated(self):
        market = rapidapi_router.to_intel_market_real_time(
            "B000KIRK01", REALTIME_FIXTURE)
        snap = sb.build_snapshot("B000KIRK01", market, "rapidapi_realtime")
        econ = ue.compute_economics(snap, {"B000KIRK01": {"cost": 5.0, "status": "invoice_confirmed"}})
        self.assertEqual(econ["cost_basis_flag"], "invoice_confirmed")
        self.assertEqual(econ["economics_confidence"], "invoice_confirmed")

    def test_missing_cost_null_not_zero(self):
        market = rapidapi_router.to_intel_market_real_time(
            "B000KIRK01", REALTIME_FIXTURE)
        snap = sb.build_snapshot("B000KIRK01", market, "rapidapi_realtime")
        econ = ue.compute_economics(snap, {})
        self.assertIsNone(econ["net_profit"])
        self.assertIsNone(econ["roi_pct"])


class TestDryRunTrace(unittest.TestCase):
    def test_end_to_end_offline(self):
        fetch, _ = make_fetch("RAPIDAPI_BDC", REALTIME_FIXTURE)
        canonical = {
            "B000KIRK01": {"asin": "B000KIRK01", "title": "Kirkland Signature Vitamin C 500mg",
                           "price": 9.99, "reviews": 100, "prime_fba": "yes",
                           "bsr_rank_number": 123, "bsr_category": "Health"},
        }
        cost = {"B000KIRK01": {"cost": 5.0, "status": "estimated"}}
        trace = dr.dry_run(mock_search, fetch, canonical, cost, ap.Approvals())
        self.assertEqual(trace["steps"]["discovery"]["found"], 2)
        self.assertEqual(trace["steps"]["enrichment"]["enriched"], 2)
        self.assertIn("B000KIRK01", trace["steps"]["economics"])
        self.assertIn("fingerprint", trace["steps"]["discovery"])


if __name__ == "__main__":
    unittest.main()
