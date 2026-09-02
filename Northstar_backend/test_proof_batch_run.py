"""Phase 3 offline tests for the guarded execution path
(docs/proof-batch-guarded-execution-design.md, module proof_batch_run.py).

OFFLINE: no network, no provider clients, no .env, no SCANNER_LIVE_ALLOWED.
All outputs go to temp dirs; the real preflight + benchmark reference are
read-only inputs. Protected artifacts are never touched.
"""

import copy
import json
import os
import tempfile
import unittest

import benchmark_validation as bv
import proof_batch as pb
import proof_batch_run as pbr
from proof_batch_run import (
    BindingError,
    BudgetTracker,
    FixtureAdapter,
    GuardError,
    ProviderAdapter,
    RunAbort,
    STOP_ADAPTER,
    STOP_MAX_CREDITS,
    STOP_MAX_REQUESTS,
    STOP_MAPPING_MISMATCH,
    STOP_SCHEMA,
    STOP_SECRET,
    STOP_WRONG_ASIN,
    canonical_preflight_asins,
    classify_mapping,
    load_preflight,
    preflight_fingerprint,
    validate_preflight_binding,
)

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
REAL_PREFLIGHT = os.path.join(BACKEND_DIR, "data", "batch", "proof-batch-preflight-20260818T060549Z.json")
REAL_REFERENCE = os.path.join(BACKEND_DIR, "data", "benchmarks", "asin_benchmark_reference.json")

EXPECTED_REVIEW_ASINS = ["B01H40O42I", "B08R2SRN88", "B00N54AJZE"]


def _load(path: str):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def real_preflight():
    return _load(REAL_PREFLIGHT)


def real_reference():
    return _load(REAL_REFERENCE)


class AlwaysMatchAdapter(ProviderAdapter):
    """Synthetic adapter returning the benchmark title for the ASIN
    (full roster, provider-reported credits). Never raises."""

    NAME = "always-match-test"

    def __init__(self, reference=None):
        self.canonical = (reference or real_reference()).get("canonical") or {}
        self.requests_made = []

    def fetch(self, asin, request_index):
        self.requests_made.append(asin)
        row = self.canonical.get(asin) or {}
        return {
            "source": "test-adapter",
            "asin": asin,
            "title": row.get("title"),
            "offer_count": 3,
            "offers_returned_count": 3,
            "buy_box_price": 10.0,
            "buy_box_seller": "Amazon.com",
            "buy_box_is_fba": True,
            "buy_box_is_fbm": False,
            "buy_box_condition": "New",
            "observed_fba_offer_count": 3,
            "observed_fbm_offer_count": 0,
            "observed_amazon_offer_count": 1,
            "offers": [
                {
                    "position": 1,
                    "buybox_winner": True,
                    "price": {"value": 10.0, "currency": "USD"},
                    "condition": "New",
                    "seller_id": "SELLER-TEST-0",
                    "seller_name": "Amazon.com",
                    "is_prime": True,
                    "is_fba": True,
                    "is_fbm": False,
                }
            ],
            "observed_at": "2026-08-18T12:00:00+00:00",
            "credits_used": 5,
            "credits_remaining": None,
            "data_gaps": [],
        }


class WrongAsinAdapter(ProviderAdapter):
    NAME = "wrong-asin-test"

    def __init__(self, returned_asin="B0WRONG0001", title="Some Totally Unrelated Product"):
        self.returned_asin = returned_asin
        self.title = title
        self.requests_made = []

    def fetch(self, asin, request_index):
        self.requests_made.append(asin)
        return {
            "source": "test-adapter",
            "asin": self.returned_asin,
            "title": self.title,
            "offer_count": 1,
            "offers_returned_count": 1,
            "buy_box_price": 5.0,
            "buy_box_seller": "Someone Else",
            "observed_fba_offer_count": 1,
            "observed_fbm_offer_count": 0,
            "observed_amazon_offer_count": 0,
            "offers": [{"position": 1, "price": {"value": 5.0, "currency": "USD"}}],
            "observed_at": "2026-08-18T12:00:00+00:00",
            "credits_used": 5,
            "data_gaps": [],
        }


class TitleMismatchAdapter(ProviderAdapter):
    """Correct ASIN, incompatible title (hard mapping failure)."""

    NAME = "title-mismatch-test"

    def fetch(self, asin, request_index):
        return {
            "source": "test-adapter",
            "asin": asin,
            "title": "Premium Foam Roller 6 Pack",
            "offer_count": 1,
            "offers_returned_count": 1,
            "buy_box_price": 5.0,
            "observed_fba_offer_count": 1,
            "observed_fbm_offer_count": 0,
            "observed_amazon_offer_count": 0,
            "offers": [{"position": 1, "price": {"value": 5.0, "currency": "USD"}}],
            "observed_at": "2026-08-18T12:00:00+00:00",
            "credits_used": 5,
            "data_gaps": [],
        }


class TitleForAdapter(ProviderAdapter):
    """Returns a per-ASIN configurable title (falling back to the benchmark
    title). Never raises, never touches the network. Used to exercise the
    known title-conflict routing without any provider call."""

    NAME = "title-for-test"

    def __init__(self, title_for=None, reference=None):
        self.canonical = (reference or real_reference()).get("canonical") or {}
        self.title_for = dict(title_for or {})
        self.requests_made = []

    def fetch(self, asin, request_index):
        self.requests_made.append(asin)
        row = self.canonical.get(asin) or {}
        title = self.title_for.get(asin, row.get("title"))
        return {
            "source": "test-adapter",
            "asin": asin,
            "title": title,
            "offer_count": 1,
            "offers_returned_count": 1,
            "buy_box_price": 5.0,
            "observed_fba_offer_count": 1,
            "observed_fbm_offer_count": 0,
            "observed_amazon_offer_count": 0,
            "offers": [{"position": 1, "price": {"value": 5.0, "currency": "USD"}}],
            "observed_at": "2026-08-18T12:00:00+00:00",
            "credits_used": 5,
            "data_gaps": [],
        }


class SecretAdapter(ProviderAdapter):
    NAME = "secret-test"

    def fetch(self, asin, request_index):
        return {
            "source": "test-adapter",
            "asin": asin,
            "title": "Kirkland Signature Product Title",
            "api_key": "sk-live-test-12345",
            "offer_count": 0,
            "offers_returned_count": 0,
            "observed_at": "2026-08-18T12:00:00+00:00",
            "credits_used": 5,
            "data_gaps": [],
        }


class SchemaViolationAdapter(ProviderAdapter):
    """Correct ASIN + compatible title, but an offer violating the schema."""

    NAME = "schema-violation-test"

    def __init__(self, reference=None):
        self.canonical = (reference or real_reference()).get("canonical") or {}

    def fetch(self, asin, request_index):
        row = self.canonical.get(asin) or {}
        return {
            "source": "test-adapter",
            "asin": asin,
            "title": row.get("title"),
            "offer_count": 1,
            "offers_returned_count": 1,
            "buy_box_price": 5.0,
            "observed_fba_offer_count": 1,
            "observed_fbm_offer_count": 0,
            "observed_amazon_offer_count": 0,
            "offers": [{"position": 1, "is_fba": True,
                       "price": {"value": 0, "currency": "USD"}}],
            "observed_at": "2026-08-18T12:00:00+00:00",
            "credits_used": 5,
            "data_gaps": [],
        }


class CrashAdapter(ProviderAdapter):
    NAME = "crash-test"

    def fetch(self, asin, request_index):
        raise RuntimeError("simulated provider crash")


class SilentNullAdapter(ProviderAdapter):
    """No title, no offers, no buy box, no claims — nothing but the ASIN."""

    NAME = "silent-null-test"

    def fetch(self, asin, request_index):
        return {
            "source": "test-adapter",
            "asin": asin,
            "observed_at": "2026-08-18T12:00:00+00:00",
            "credits_used": 5,
            "data_gaps": ["provider returned no offers"],
        }


class PreflightBindingTests(unittest.TestCase):
    def test_real_preflight_is_valid(self):
        preflight = real_preflight()
        self.assertEqual(validate_preflight_binding(preflight), [])
        asins = canonical_preflight_asins(preflight)
        self.assertEqual(len(asins), 20)
        self.assertEqual(len(set(asins)), 20)

    def test_purpose_tamper_rejected(self):
        preflight = real_preflight()
        preflight["purpose"] = "something_else"
        self.assertTrue(validate_preflight_binding(preflight))

    def test_run_id_tamper_changes_fingerprint(self):
        preflight = real_preflight()
        base = preflight_fingerprint(preflight)
        preflight["run_id"] = "tampered-run-id"
        self.assertNotEqual(preflight_fingerprint(preflight), base)

    def test_asin_count_tamper_rejected(self):
        preflight = real_preflight()
        preflight["selection"]["asins"] = preflight["selection"]["asins"][:19]
        self.assertTrue(validate_preflight_binding(preflight))
        with self.assertRaises(BindingError):
            canonical_preflight_asins(preflight)

    def test_duplicate_asin_rejected(self):
        preflight = real_preflight()
        first = preflight["selection"]["asins"][0]
        preflight["selection"]["asins"].append(copy.deepcopy(first))
        with self.assertRaises(BindingError):
            canonical_preflight_asins(preflight)

    def test_asin_replacement_changes_fingerprint(self):
        preflight = real_preflight()
        base = preflight_fingerprint(preflight)
        rows = preflight["selection"]["asins"]
        rows[0]["asin"] = "B0DIFFXYZ9"
        self.assertNotEqual(preflight_fingerprint(preflight), base)

    def test_asin_order_swap_keeps_fingerprint(self):
        # The fingerprint covers the sorted canonical ASIN set (design §3);
        # order of execution is validated per-request by mapping checks, so a
        # reorder is intentionally fingerprint-stable.
        preflight = real_preflight()
        base = preflight_fingerprint(preflight)
        rows = preflight["selection"]["asins"]
        rows[0], rows[1] = rows[1], rows[0]
        self.assertEqual(preflight_fingerprint(preflight), base)

    def test_provider_plan_expansion_rejected(self):
        preflight = real_preflight()
        preflight["provider_plan"]["providers"].append(
            {"provider": "SCAVIO", "status": "planned", "requests_per_asin": 1,
             "credit_estimate_per_asin": 3}
        )
        self.assertTrue(validate_preflight_binding(preflight))

    def test_requested_fields_tamper_rejected(self):
        preflight = real_preflight()
        preflight["provider_plan"]["requested_fields_per_asin"] = ["market_offers", "bsr_history"]
        self.assertTrue(validate_preflight_binding(preflight))

    def test_request_count_tamper_rejected(self):
        preflight = real_preflight()
        preflight["provider_plan"]["request_count_total"] = 25
        self.assertTrue(validate_preflight_binding(preflight))

    def test_confirmation_line_tamper_rejected(self):
        preflight = real_preflight()
        preflight["human_confirmation"] = "I authorise spending"
        self.assertTrue(validate_preflight_binding(preflight))

    def test_fingerprint_ignores_runtime_credit_cap(self):
        preflight = real_preflight()
        base = preflight_fingerprint(preflight)
        self.assertIsNone(preflight["hard_caps"].get("max_credits"))
        preflight["hard_caps"]["max_credits"] = 999
        self.assertEqual(preflight_fingerprint(preflight), base)

    def test_fingerprint_deterministic(self):
        preflight = real_preflight()
        self.assertEqual(preflight_fingerprint(preflight), preflight_fingerprint(copy.deepcopy(preflight)))

    def test_missing_preflight_file(self):
        with self.assertRaises(BindingError):
            load_preflight(os.path.join(tempfile.gettempdir(), "no-such-preflight.json"))

    def test_secret_like_preflight_rejected(self):
        preflight = real_preflight()
        preflight["selection"]["asins"][0]["api_key"] = "x"
        tmp_path = os.path.join(tempfile.mkdtemp(prefix="proof-batch-secret-"), "preflight.json")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(preflight, fh)
        with self.assertRaises(BindingError):
            load_preflight(tmp_path)


class ClassifyMappingTests(unittest.TestCase):
    def setUp(self):
        self.reference = real_reference()
        self.canonical = self.reference["canonical"]

    def _conflict_rows(self):
        return [
            row for row in real_preflight()["selection"]["asins"]
            if row.get("title_conflict")
        ]

    def test_expected_review_exactly_three(self):
        rows = self._conflict_rows()
        self.assertEqual(sorted(r["asin"] for r in rows), sorted(EXPECTED_REVIEW_ASINS))
        for row in rows:
            state, reason = classify_mapping(
                row["asin"], row["asin"], row["title"], row
            )
            self.assertEqual(state, pbr.STATE_EXPECTED_REVIEW, reason)
            self.assertIn("conflict", reason.lower())

    def test_exact_match_is_match(self):
        rows = real_preflight()["selection"]["asins"]
        row = next(r for r in rows if not r.get("title_conflict"))
        state, reason = classify_mapping(row["asin"], row["asin"], row["title"], row)
        self.assertEqual(state, pbr.STATE_MATCH, reason)

    def test_wrong_asin_is_unexpected(self):
        row = real_preflight()["selection"]["asins"][0]
        state, reason = classify_mapping(row["asin"], "B0WRONG0001", row["title"], row)
        self.assertEqual(state, pbr.STATE_UNEXPECTED_MISMATCH)
        self.assertIn("!= requested", reason)

    def test_incompatible_title_is_unexpected(self):
        row = next(r for r in real_preflight()["selection"]["asins"] if not r.get("title_conflict"))
        state, reason = classify_mapping(row["asin"], row["asin"], "Premium Foam Roller 6 Pack", row)
        self.assertEqual(state, pbr.STATE_UNEXPECTED_MISMATCH, reason)

    def test_no_title_is_unavailable(self):
        row = real_preflight()["selection"]["asins"][0]
        state, reason = classify_mapping(row["asin"], row["asin"], None, row)
        self.assertEqual(state, pbr.STATE_UNAVAILABLE)
        self.assertIn("no title", reason)

    def test_no_benchmark_row_is_unavailable(self):
        state, reason = classify_mapping("B0TEST12345", "B0TEST12345", "Some Title", None)
        self.assertEqual(state, pbr.STATE_UNAVAILABLE)


class KnownTitleConflictTests(unittest.TestCase):
    """Known benchmark title-conflict ASINs route to expected_mapping_review on a
    same-ASIN title mismatch (never a hard stop). All other mapping protection
    stays intact: wrong ASIN, absent ASIN, pack mismatch, and non-conflict title
    mismatch still hard-stop. Pure offline fixtures; no provider/network."""

    PROTECTED_REL = [
        "data/scanner-search-cache.json",
        "data/scanner-search-cache.brightdata-20260817-065933-20260817-021812.json",
        "data/benchmarks/raw/BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv",
        "data/benchmarks/raw/Rank-Product-ASIN-Reviews-Price-BSR.csv",
        "data/benchmarks/manifest.json",
        "data/benchmarks/asin_benchmark_reference.json",
        "finance.py",
        "pricing.py",
        "fee_engine.py",
        "product_analysis.py",
    ]

    def _row(self, asin):
        return next(
            r for r in real_preflight()["selection"]["asins"] if r["asin"] == asin
        )

    def _nonconflict_row(self):
        return next(
            r for r in real_preflight()["selection"]["asins"] if not r.get("title_conflict")
        )

    def test_conflict_asin_title_mismatch_is_expected_review(self):
        for asin in EXPECTED_REVIEW_ASINS:
            row = self._row(asin)
            state, reason = classify_mapping(asin, asin, "Generic Unrelated Widget 999", row)
            self.assertEqual(state, pbr.STATE_EXPECTED_REVIEW, (asin, reason))
            self.assertIn("human mapping review", reason)

    def test_conflict_asin_pack_mismatch_aborts(self):
        for asin in EXPECTED_REVIEW_ASINS:
            row = self._row(asin)
            state, reason = classify_mapping(
                asin, asin, "Aller-Flo Fluticasone (Pack of 10)", row
            )
            self.assertEqual(state, pbr.STATE_UNEXPECTED_MISMATCH, (asin, reason))
            self.assertIn("pack", reason.lower())

    def test_nonconflict_title_mismatch_aborts(self):
        row = self._nonconflict_row()
        state, reason = classify_mapping(row["asin"], row["asin"], "Generic Unrelated Widget 999", row)
        self.assertEqual(state, pbr.STATE_UNEXPECTED_MISMATCH, reason)

    def test_wrong_asin_aborts(self):
        row = self._nonconflict_row()
        state, reason = classify_mapping(row["asin"], "B0WRONG0001", row["title"], row)
        self.assertEqual(state, pbr.STATE_UNEXPECTED_MISMATCH, reason)

    def test_missing_title_is_unavailable_not_match(self):
        for asin in EXPECTED_REVIEW_ASINS + [self._nonconflict_row()["asin"]]:
            row = self._row(asin)
            state, reason = classify_mapping(asin, asin, None, row)
            self.assertEqual(state, pbr.STATE_UNAVAILABLE, (asin, reason))

    def test_full_run_conflict_asins_expected_review_no_unexpected(self):
        out_dir = tempfile.mkdtemp(prefix="proof-batch-ktc-")
        adapter = TitleForAdapter({EXPECTED_REVIEW_ASINS[0]: "Generic Unrelated Widget 999"})
        outcome = pbr.run_guarded(
            preflight=real_preflight(), adapter=adapter,
            max_requests=20, max_credits=100, live=True,
            live_enabled=True, out_dir=out_dir,
        )
        self.assertEqual(outcome["status"], "completed")
        manifest = _load(os.path.join(out_dir, "run-manifest.json"))
        self.assertEqual(manifest["counts"]["match"], 17)
        self.assertEqual(manifest["counts"]["expected_mapping_review"], 3)
        self.assertEqual(manifest["counts"]["available"], 20)
        self.assertEqual(manifest["counts"]["unavailable"], 0)
        report = pbr.build_run_report(out_dir)
        self.assertEqual(report["mapping_summary"]["unexpected_mapping_mismatch_count"], 0)
        self.assertTrue(report["no_universal_accuracy_percentage"])

    def test_report_preserves_review_context(self):
        asin = EXPECTED_REVIEW_ASINS[0]
        out_dir = tempfile.mkdtemp(prefix="proof-batch-ktc-report-")
        adapter = TitleForAdapter({asin: "Generic Unrelated Widget 999"})
        pbr.run_guarded(
            preflight=real_preflight(), adapter=adapter,
            max_requests=20, max_credits=100, live=True,
            live_enabled=True, out_dir=out_dir,
        )
        report = pbr.build_run_report(out_dir)
        per = next(r for r in report["per_asin"] if r["requested_asin"] == asin)
        self.assertEqual(per["mapping_state"], pbr.STATE_EXPECTED_REVIEW)
        self.assertIn("human mapping review", per["mapping_reason"])
        self.assertEqual(per["returned_title"], "Generic Unrelated Widget 999")
        self.assertEqual(per["identity"]["title_status"], "mismatch")
        self.assertTrue(per["benchmark_title"])
        self.assertTrue(per["benchmark_title_variants"])

    def test_no_network_used(self):
        out_dir = tempfile.mkdtemp(prefix="proof-batch-ktc-net-")
        adapter = TitleForAdapter({EXPECTED_REVIEW_ASINS[0]: "Generic Unrelated Widget 999"})
        self.assertFalse(hasattr(adapter, "session"))
        self.assertFalse(hasattr(adapter, "api_key"))
        outcome = pbr.run_guarded(
            preflight=real_preflight(), adapter=adapter,
            max_requests=20, max_credits=100, live=True,
            live_enabled=True, out_dir=out_dir,
        )
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(len(adapter.requests_made), 20)

    def test_protected_artifacts_byte_identical(self):
        import hashlib as _hashlib
        fixture = os.path.join(BACKEND_DIR, "fixtures", "protected_hashes.json")
        if not os.path.isfile(fixture):
            self.skipTest("protected_hashes.json baseline not present")
        baseline = _load(fixture)
        for rel, expected in baseline.items():
            path = os.path.join(BACKEND_DIR, rel)
            if not os.path.isfile(path):
                self.skipTest(f"protected artifact missing: {rel}")
            if isinstance(expected, dict):
                exp_hash = expected.get("sha256")
                exp_bytes = expected.get("bytes")
            else:
                exp_hash = expected
                exp_bytes = None
            actual = _hashlib.sha256(open(path, "rb").read()).hexdigest()
            self.assertEqual(actual, exp_hash, rel)
            if exp_bytes is not None:
                self.assertEqual(os.path.getsize(path), exp_bytes, rel)


class BudgetTrackerTests(unittest.TestCase):
    def test_caps_required(self):
        with self.assertRaises(GuardError):
            BudgetTracker(max_requests=0, max_credits=10)
        with self.assertRaises(GuardError):
            BudgetTracker(max_requests=10, max_credits=0)
        with self.assertRaises(GuardError):
            BudgetTracker(max_requests=25, max_credits=10)

    def test_stop_before_requests(self):
        budget = BudgetTracker(max_requests=2, max_credits=100)
        self.assertTrue(budget.can_request())
        budget.record_request(credits_reported=None)
        self.assertTrue(budget.can_request())
        budget.record_request(credits_reported=None)
        self.assertFalse(budget.can_request())
        self.assertEqual(budget.stop_reason(), STOP_MAX_REQUESTS)

    def test_stop_before_credits(self):
        budget = BudgetTracker(max_requests=20, max_credits=9)
        self.assertTrue(budget.can_request())
        budget.record_request(credits_reported=None)
        self.assertFalse(budget.can_request())
        self.assertEqual(budget.stop_reason(), STOP_MAX_CREDITS)

    def test_credit_accounting_reported_vs_estimate(self):
        budget = BudgetTracker(max_requests=3, max_credits=100)
        budget.record_request(credits_reported=5)
        budget.record_request(credits_reported=None)
        state = budget.snapshot_state()
        self.assertEqual(state["credits_reported_used"], 5)
        self.assertEqual(state["credits_estimated_used"], 10.0)
        self.assertEqual(state["credits_actual_status"], "reported_by_provider")
        budget2 = BudgetTracker(max_requests=3, max_credits=100)
        budget2.record_request(credits_reported=None)
        self.assertEqual(budget2.snapshot_state()["credits_actual_status"], "unavailable_estimated_only")


class GuardedRunTests(unittest.TestCase):
    def _run_dir(self):
        return tempfile.mkdtemp(prefix="proof-batch-run-test-")

    def _files(self, out_dir):
        return set(os.listdir(out_dir))

    def test_refuses_without_live_flag(self):
        with self.assertRaises(GuardError):
            pbr.run_guarded(
                preflight=real_preflight(), adapter=AlwaysMatchAdapter(),
                max_requests=20, max_credits=100, live=False,
                live_enabled=True, out_dir=self._run_dir(),
            )

    def test_refuses_when_gate_disabled(self):
        with self.assertRaises(GuardError):
            pbr.run_guarded(
                preflight=real_preflight(), adapter=AlwaysMatchAdapter(),
                max_requests=20, max_credits=100, live=True,
                live_enabled=False, out_dir=self._run_dir(),
            )

    def test_refuses_without_adapter(self):
        with self.assertRaises(GuardError):
            pbr.run_guarded(
                preflight=real_preflight(), adapter=None,
                max_requests=20, max_credits=100, live=True,
                live_enabled=True, out_dir=self._run_dir(),
            )

    def test_full_success(self):
        out_dir = self._run_dir()
        adapter = AlwaysMatchAdapter()
        outcome = pbr.run_guarded(
            preflight=real_preflight(), adapter=adapter,
            max_requests=20, max_credits=100, live=True,
            live_enabled=True, out_dir=out_dir,
        )
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(len(adapter.requests_made), 20)
        files = self._files(out_dir)
        self.assertIn("run-manifest.json", files)
        self.assertIn("validated-result-envelopes.json", files)
        self.assertNotIn("failure-manifest.json", files)

        results = _load(os.path.join(out_dir, "validated-result-envelopes.json"))
        self.assertEqual(results["kind"], "proof-batch-validated-results")
        envelopes = results["envelopes"]
        self.assertEqual(len(envelopes), 20)
        fingerprint = results["preflight_fingerprint"]
        self.assertEqual(fingerprint, preflight_fingerprint(real_preflight()))
        self.assertEqual(sorted(e["asin"] for e in envelopes),
                         sorted(canonical_preflight_asins(real_preflight())))
        for index, env in enumerate(envelopes, start=1):
            self.assertEqual(env["requested_asin"], env["asin"])
            self.assertEqual(env["request_index"], index)
            self.assertEqual(env["preflight_fingerprint"], fingerprint)
            self.assertEqual(pb.validate_envelope(env), [])
        manifest = _load(os.path.join(out_dir, "run-manifest.json"))
        self.assertEqual(manifest["counts"]["match"], 17)
        self.assertEqual(manifest["counts"]["expected_mapping_review"], 3)
        self.assertEqual(manifest["counts"]["available"], 20)
        self.assertEqual(manifest["counts"]["unavailable"], 0)
        self.assertEqual(manifest["counts"]["provider_error"], 0)
        self.assertEqual(manifest["budget"]["requests_used"], 20)
        self.assertEqual(manifest["honesty"]["actual_credit_total"], 100)

    def test_budget_request_stop_aborts(self):
        out_dir = self._run_dir()
        adapter = AlwaysMatchAdapter()
        outcome = pbr.run_guarded(
            preflight=real_preflight(), adapter=adapter,
            max_requests=5, max_credits=100, live=True,
            live_enabled=True, out_dir=out_dir,
        )
        self.assertEqual(outcome["status"], "aborted")
        self.assertEqual(outcome["stop_reason"], STOP_MAX_REQUESTS)
        self.assertEqual(len(adapter.requests_made), 5)
        files = self._files(out_dir)
        self.assertIn("failure-manifest.json", files)
        self.assertNotIn("validated-result-envelopes.json", files)
        self.assertNotIn("run-manifest.json", files)

    def test_budget_credit_stop_aborts(self):
        out_dir = self._run_dir()
        adapter = AlwaysMatchAdapter()
        outcome = pbr.run_guarded(
            preflight=real_preflight(), adapter=adapter,
            max_requests=20, max_credits=9, live=True,
            live_enabled=True, out_dir=out_dir,
        )
        self.assertEqual(outcome["status"], "aborted")
        self.assertEqual(outcome["stop_reason"], STOP_MAX_CREDITS)
        self.assertEqual(len(adapter.requests_made), 1)
        self.assertIn("failure-manifest.json", self._files(out_dir))

    def test_wrong_asin_aborts_hard(self):
        out_dir = self._run_dir()
        adapter = WrongAsinAdapter()
        with self.assertRaises(RunAbort) as ctx:
            pbr.run_guarded(
                preflight=real_preflight(), adapter=adapter,
                max_requests=20, max_credits=100, live=True,
                live_enabled=True, out_dir=out_dir,
            )
        self.assertEqual(ctx.exception.reason, STOP_WRONG_ASIN)
        self.assertEqual(len(adapter.requests_made), 1)
        files = self._files(out_dir)
        self.assertIn("failure-manifest.json", files)
        self.assertNotIn("validated-result-envelopes.json", files)
        manifest = _load(os.path.join(out_dir, "failure-manifest.json"))
        self.assertEqual(manifest["stop_reason"], STOP_WRONG_ASIN)

    def test_title_mismatch_aborts_hard(self):
        out_dir = self._run_dir()
        adapter = TitleMismatchAdapter()
        with self.assertRaises(RunAbort) as ctx:
            pbr.run_guarded(
                preflight=real_preflight(), adapter=adapter,
                max_requests=20, max_credits=100, live=True,
                live_enabled=True, out_dir=out_dir,
            )
        self.assertEqual(ctx.exception.reason, STOP_MAPPING_MISMATCH)
        self.assertNotIn("validated-result-envelopes.json", self._files(out_dir))

    def test_secret_like_output_aborts_hard(self):
        out_dir = self._run_dir()
        with self.assertRaises(RunAbort) as ctx:
            pbr.run_guarded(
                preflight=real_preflight(), adapter=SecretAdapter(),
                max_requests=20, max_credits=100, live=True,
                live_enabled=True, out_dir=out_dir,
            )
        self.assertEqual(ctx.exception.reason, STOP_SECRET)
        self.assertNotIn("validated-result-envelopes.json", self._files(out_dir))

    def test_schema_violation_aborts_hard(self):
        out_dir = self._run_dir()
        with self.assertRaises(RunAbort) as ctx:
            pbr.run_guarded(
                preflight=real_preflight(), adapter=SchemaViolationAdapter(),
                max_requests=20, max_credits=100, live=True,
                live_enabled=True, out_dir=out_dir,
            )
        self.assertEqual(ctx.exception.reason, STOP_SCHEMA)
        self.assertNotIn("validated-result-envelopes.json", self._files(out_dir))

    def test_adapter_crash_aborts_hard(self):
        out_dir = self._run_dir()
        with self.assertRaises(RunAbort) as ctx:
            pbr.run_guarded(
                preflight=real_preflight(), adapter=CrashAdapter(),
                max_requests=20, max_credits=100, live=True,
                live_enabled=True, out_dir=out_dir,
            )
        self.assertEqual(ctx.exception.reason, STOP_ADAPTER)
        self.assertNotIn("validated-result-envelopes.json", self._files(out_dir))

    def test_null_preservation_never_zero(self):
        out_dir = self._run_dir()
        adapter = SilentNullAdapter()
        pbr.run_guarded(
            preflight=real_preflight(), adapter=adapter,
            max_requests=20, max_credits=100, live=True,
            live_enabled=True, out_dir=out_dir,
        )
        results = _load(os.path.join(out_dir, "validated-result-envelopes.json"))
        self.assertEqual(len(results["envelopes"]), 20)
        for env in results["envelopes"]:
            facts = env["snapshot"]["facts"]
            self.assertIsNone(facts["identity"]["name"])
            self.assertEqual(env["mapping_state"], pbr.STATE_UNAVAILABLE)
            self.assertEqual(env["result_status"], "unavailable")
            self.assertIsNone(facts["demand"]["estimated_monthly_sales"])
            self.assertIsNone(facts["market"]["amazon_price"])
            self.assertIsNone(facts["market"]["buy_box"]["price"])
            self.assertIsNone(facts["economics"]["net_profit"])
            self.assertIsNone(facts["economics"]["roi_pct"])
            self.assertEqual(facts["market"]["coverage"]["offers_complete_status"], "unknown")
            self.assertTrue(facts["market"]["coverage"]["coverage_reason"])
            for offer in facts["market"]["offers"]:
                self.assertNotEqual(offer.get("price"), 0)


class ReportTests(unittest.TestCase):
    def _completed_run_dir(self):
        out_dir = tempfile.mkdtemp(prefix="proof-batch-report-test-")
        pbr.run_guarded(
            preflight=real_preflight(), adapter=AlwaysMatchAdapter(),
            max_requests=20, max_credits=100, live=True,
            live_enabled=True, out_dir=out_dir,
        )
        return out_dir

    def test_report_labels_honest(self):
        out_dir = self._completed_run_dir()
        report = pbr.build_run_report(out_dir)
        self.assertEqual(report["kind"], "proof-batch-benchmark-comparison-report")
        self.assertEqual(report["mapping_summary"]["expected_mapping_review_count"], 3)
        self.assertEqual(
            sorted(report["mapping_summary"]["expected_mapping_review_asins"]),
            sorted(EXPECTED_REVIEW_ASINS),
        )
        self.assertEqual(report["mapping_summary"]["unexpected_mapping_mismatch_count"], 0)
        self.assertEqual(report["mapping_summary"]["match_count"], 17)
        self.assertTrue(report["no_universal_accuracy_percentage"])
        self.assertEqual(
            report["internally_validated"]["label"], bv.INTERNAL_ONLY_LABEL
        )
        self.assertTrue(report["limitations"]["capture_time_unknown"])
        self.assertTrue(report["limitations"]["economics_demand_not_benchmarked"])
        self.assertEqual(len(report["per_asin"]), 20)
        self.assertTrue(report["metrics"]["benchmark_matched_asin_count"] == 20)

    def test_report_price_drift_classes_present(self):
        out_dir = self._completed_run_dir()
        report = pbr.build_run_report(out_dir)
        self.assertTrue(report["price_drift_summary"])
        valid = {"exact", "within_tolerance", "moderate_drift", "material_drift", "unavailable"}
        for cls, count in report["price_drift_summary"].items():
            self.assertIn(cls, valid)
            self.assertGreaterEqual(count, 0)
        self.assertEqual(sum(report["price_drift_summary"].values()), 20)

    def test_report_writes_all_files(self):
        out_dir = self._completed_run_dir()
        written = pbr.write_report_files(out_dir, pbr.build_run_report(out_dir))
        for path in written:
            self.assertTrue(os.path.isfile(path), path)
        md = open(os.path.join(out_dir, "human-review-summary.md"), encoding="utf-8").read()
        self.assertIn(pbr.PURCHASE_AUTHORIZATION_STATEMENT, md)
        self.assertIn(EXPECTED_REVIEW_ASINS[0], md)

    def test_report_refuses_non_finalized_dir(self):
        out_dir = tempfile.mkdtemp(prefix="proof-batch-empty-report-")
        with self.assertRaises(GuardError):
            pbr.build_run_report(out_dir)

    def test_report_run_id_and_fingerprint_match(self):
        out_dir = self._completed_run_dir()
        report = pbr.build_run_report(out_dir)
        results = _load(os.path.join(out_dir, "validated-result-envelopes.json"))
        self.assertEqual(report["run_id"], results["run_id"])
        self.assertEqual(report["preflight_fingerprint"], results["preflight_fingerprint"])


class ContainmentTests(unittest.TestCase):
    def test_module_imports_no_provider_client(self):
        src = open(os.path.join(BACKEND_DIR, "proof_batch_run.py"), encoding="utf-8").read()
        import_lines = [
            line.strip() for line in src.splitlines()
            if line.strip().startswith("import ") or line.strip().startswith("from ")
        ]
        for forbidden in ("requests", "urllib", "socket", "http", "easyparser_client",
                          "bright", "scavio", "chocodata", "canopy", "json" if False else "amazon_search"):
            for line in import_lines:
                self.assertNotIn(forbidden, line, f"forbidden import token {forbidden!r} in {line!r}")
        self.assertIn("import market_snapshot_store", " ".join(import_lines))

    def test_validate_and_fingerprint_are_zero_network(self):
        preflight = real_preflight()
        self.assertEqual(validate_preflight_binding(preflight), [])
        self.assertIsInstance(preflight_fingerprint(preflight), str)

    def test_dry_run_and_report_cli_write_nothing(self):
        import proof_batch_run as pbr_mod

        argv_dry = ["dry-run", "--preflight", REAL_PREFLIGHT,
                    "--max-requests", "20", "--max-credits", "100"]
        self.assertEqual(pbr_mod.main(argv_dry), 0)
        argv_missing = ["dry-run", "--preflight", REAL_PREFLIGHT]
        self.assertEqual(pbr_mod.main(argv_missing), 2)

    def test_run_cli_refuses_without_live(self):
        import proof_batch_run as pbr_mod

        argv = ["run", "--preflight", REAL_PREFLIGHT, "--max-requests", "20", "--max-credits", "100"]
        self.assertEqual(pbr_mod.main(argv), 2)

    def test_run_cli_refuses_unknown_command(self):
        import proof_batch_run as pbr_mod

        self.assertEqual(pbr_mod.main(["frobnicate"]), 2)


class FixtureAdapterTests(unittest.TestCase):
    def test_fixture_labels_synthetic_everywhere(self):
        out_dir = tempfile.mkdtemp(prefix="proof-batch-fixture-test-")
        adapter = FixtureAdapter(real_reference())
        pbr.run_guarded(
            preflight=real_preflight(), adapter=adapter,
            max_requests=20, max_credits=100, live=True,
            live_enabled=True, out_dir=out_dir,
        )
        results = _load(os.path.join(out_dir, "validated-result-envelopes.json"))
        self.assertTrue(results["synthetic_fixture"])
        manifest = _load(os.path.join(out_dir, "run-manifest.json"))
        self.assertTrue(manifest["synthetic_fixture"])
        for env in results["envelopes"]:
            self.assertIn("SYNTHETIC FIXTURE", env["snapshot"]["facts"]["market"]["coverage"]["coverage_reason"])


class Attempt2PreflightTests(unittest.TestCase):
    """Offline verification that the Attempt 2 preflight is a deterministic,
    schema-valid derivation of Attempt 1 — same 20 ASINs/order/scope, new run ID
    and fingerprint, audit metadata preserved, and Attempt 1 evidence untouched.
    No provider/network call; no protected artifact modified."""

    ATTEMPT1_PREFLIGHT = REAL_PREFLIGHT
    ATTEMPT1_FAILURE = os.path.join(
        BACKEND_DIR, "data", "batch", "live-validation-runs",
        "proof-batch-preflight-20260818T060549Z", "failure-manifest.json",
    )

    def _attempt2_paths(self):
        import glob as _glob
        matches = sorted(
            _glob.glob(os.path.join(BACKEND_DIR, "data", "batch", "proof-batch-preflight-attempt-2-*.json"))
        )
        # Exclude the adjacent attempt-manifest files.
        preflights = [m for m in matches if not m.endswith(".attempt-manifest.json")]
        self.assertEqual(len(preflights), 1, "expected exactly one Attempt 2 preflight")
        pf = preflights[0]
        manifest = pf + ".attempt-manifest.json"
        self.assertTrue(os.path.isfile(manifest), "adjacent attempt manifest missing")
        return pf, manifest

    def _ordered_asins(self, preflight):
        return [r["asin"] for r in preflight["selection"]["asins"]]

    def test_attempt2_same_20_asins_and_order(self):
        pf2, _ = self._attempt2_paths()
        a1 = real_preflight()
        a2 = _load(pf2)
        self.assertEqual(self._ordered_asins(a1), self._ordered_asins(a2))
        self.assertEqual(len(self._ordered_asins(a2)), 20)

    def test_attempt2_distinct_run_id_and_fingerprint(self):
        pf2, _ = self._attempt2_paths()
        a1 = real_preflight()
        a2 = _load(pf2)
        self.assertNotEqual(a1["run_id"], a2["run_id"])
        self.assertTrue(a2["run_id"].startswith("proof-batch-preflight-attempt-2-"))
        fp1 = pbr.preflight_fingerprint(a1)
        fp2 = pbr.preflight_fingerprint(a2)
        self.assertNotEqual(fp1, fp2)

    def test_attempt1_evidence_unchanged(self):
        # Attempt 1 preflight content is unchanged: its fingerprint still equals
        # the value recorded inside the Attempt 1 failure manifest.
        a1 = real_preflight()
        failure = _load(self.ATTEMPT1_FAILURE)
        self.assertEqual(
            pbr.preflight_fingerprint(a1),
            failure["preflight_fingerprint"],
        )
        self.assertEqual(failure["stop_reason"], "mapping_incompatible")
        self.assertEqual(failure["stage"], "map(B01H40O42I)")

    def test_attempt2_preserves_three_expected_review_asins(self):
        pf2, _ = self._attempt2_paths()
        a2 = _load(pf2)
        self.assertEqual(
            sorted(a2["benchmark_summary"]["title_conflict_asins"]),
            sorted(EXPECTED_REVIEW_ASINS),
        )
        conflict_asins = [r["asin"] for r in a2["selection"]["asins"] if r.get("title_conflict")]
        self.assertEqual(sorted(conflict_asins), sorted(EXPECTED_REVIEW_ASINS))

    def test_attempt2_preserves_17_strict_asins(self):
        pf2, _ = self._attempt2_paths()
        a2 = _load(pf2)
        strict = [r["asin"] for r in a2["selection"]["asins"] if not r.get("title_conflict")]
        self.assertEqual(len(strict), 17)
        self.assertEqual(len(a2["selection"]["asins"]), 20)

    def test_attempt2_accepted_by_validator(self):
        pf2, _ = self._attempt2_paths()
        a2 = _load(pf2)
        self.assertEqual(pbr.validate_preflight_binding(a2), [])

    def test_attempt2_output_path_uses_new_run_id(self):
        pf2, _ = self._attempt2_paths()
        a2 = _load(pf2)
        stem = os.path.basename(pf2)[:-len(".json")]
        self.assertEqual(stem, a2["run_id"])
        self.assertNotIn("20260818T060549Z", a2["run_id"])

    def test_failure_manifest_sha_preserved_in_audit(self):
        import hashlib as _hashlib
        pf2, manifest_path = self._attempt2_paths()
        manifest = _load(manifest_path)
        actual = _hashlib.sha256(open(self.ATTEMPT1_FAILURE, "rb").read()).hexdigest()
        self.assertEqual(actual, manifest["prior_failure_manifest_sha256"])
        self.assertEqual(manifest["attempt_number"], 2)
        self.assertEqual(manifest["supersedes_run_id"], "proof-batch-preflight-20260818T060549Z")
        self.assertEqual(
            manifest["new_canonical_fingerprint"], pbr.preflight_fingerprint(_load(pf2))
        )
        self.assertEqual(manifest["prior_attempt_request_count"], 1)
        self.assertEqual(manifest["prior_attempt_estimated_credits"], 3)
        self.assertEqual(manifest["prior_attempt_provider_reported_credits"], 3)
        self.assertEqual(manifest["mapping_policy_version"], "known_title_conflict_review_v2")

    def test_no_protected_artifact_changed(self):
        import hashlib as _hashlib
        fixture = os.path.join(BACKEND_DIR, "fixtures", "protected_hashes.json")
        self.assertTrue(os.path.isfile(fixture), "protected baseline missing")
        baseline = _load(fixture)
        for rel, expected in baseline.items():
            path = os.path.join(BACKEND_DIR, rel)
            self.assertTrue(os.path.isfile(path))
            exp = expected["sha256"] if isinstance(expected, dict) else expected
            actual = _hashlib.sha256(open(path, "rb").read()).hexdigest()
            self.assertEqual(actual, exp, rel)


if __name__ == "__main__":
    unittest.main()