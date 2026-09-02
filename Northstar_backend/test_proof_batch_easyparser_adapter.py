"""Offline tests for the real-data-ready Easyparser adapter for the fixed
20-ASIN Proof Batch run (proof_batch_easyparser_adapter.py + runner wiring).

Every provider/transport path is patched to raise at module level: no test
can accidentally reach the network, the real easyparser client, or any other
provider client. Every adapter constructed with allow_live=True MUST inject
an explicit fake client — the adapter itself fails closed when one is
missing, and tests here prove that.

Regression coverage (mandatory, in addition to the 33-requirement list):
  - direct-script invocation: `python proof_batch_run.py run --live ...`
    with the external gate on still refuses cleanly (exit 2, no traceback,
    no provider call) — proves the __main__/proof_batch_run class-identity
    alias works end to end;
  - `python -m proof_batch_run run --live ...` same clean refusal;
  - isolated class-identity probe (script executed as __main__ then imported
    by name): same GuardError class, same ProviderAdapter type;
  - adapter refuses construction without an explicitly injected client;
  - SCANNER_LIVE_ALLOWED is only ever set inside patch.dict/subprocess env
    and is popped immediately after (never leaks into the parent env).

Never makes a provider/HTTP call, never reads or writes real data files
(preflight and run dirs are temp), never starts a server, never modifies
protected artifacts (module-level before/after hash comparison in
tearDownModule).
"""

import test_network_guard  # noqa: F401  (blocks real network calls)
import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import requests

import easyparser_client
import offer_enrichment
import proof_batch as pb
import proof_batch_run as pbr
from proof_batch_easyparser_adapter import EasyparserLiveAdapter
import proof_batch_easyparser_adapter as adapter_mod

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))

CONFLICT_ASINS = ("B01H40O42I", "B08R2SRN88", "B00N54AJZE")

PROTECTED_FILES = [
    "data/scanner-search-cache.json",
    "data/scanner-search-cache.brightdata-20260817-065933-20260817-021812.json",
    "data/benchmarks/raw/BSR-proxyrank-Product-ASIN-Reviews-Price-PrimeFBA.csv",
    "data/benchmarks/raw/Rank-Product-ASIN-Reviews-Price-BSR.csv",
    "data/benchmarks/manifest.json",
    "data/benchmarks/asin_benchmark_reference.json",
]
PROTECTED_ABSENT = [
    "data/amazon-market-snapshots.json",
    "data/enrichment-run-report.json",
]


def _sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _protected_before():
    return {path: _sha256(path) for path in PROTECTED_FILES if os.path.isfile(path)}


_PROTECTED_BEFORE = _protected_before()


def tearDownModule():
    """Run after the whole module: protected artifacts must be byte-identical
    and previously-absent files must still be absent (test 33)."""
    after = _protected_before()
    before = _PROTECTED_BEFORE
    changed = [
        path for path in set(before) | set(after)
        if before.get(path) != after.get(path)
    ]
    if changed:
        raise AssertionError("protected artifact hash/size changed: %s" % sorted(changed))
    for path in PROTECTED_ABSENT:
        if os.path.exists(path):
            raise AssertionError("protected-absent file appeared: %s" % path)
    for patcher in _ACTIVE_PATCHERS:
        patcher.stop()
    _ACTIVE_PATCHERS.clear()
    os.environ.pop("PROOF_BATCH_LIVE_ARMED", None)  # restore production default (disabled)
    pbr.LIVE_CLIENT_FACTORY = None
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)
    os.environ.pop("SCANNER_MARKET_SNAPSHOT_PATH", None)
    os.environ.pop("SCANNER_ENRICH_RUN_REPORT_PATH", None)


# ---------------------------------------------------------------------------
# Containment: every transport/provider path raises if touched.
# ---------------------------------------------------------------------------

def _raising(*args, **kwargs):
    raise AssertionError("transport/provider path touched in offline test")


_ACTIVE_PATCHERS = []


def setUpModule():
    os.environ.pop("SCANNER_LIVE_ALLOWED", None)
    os.environ.pop("PROOF_BATCH_LIVE_ARMED", None)
    for target in ("get", "post", "put", "delete", "patch", "head", "options", "request"):
        _ACTIVE_PATCHERS.append(patch.object(requests, target, side_effect=_raising))
    _ACTIVE_PATCHERS.append(patch.object(easyparser_client, "get_easyparser_offers", side_effect=_raising))
    for patcher in _ACTIVE_PATCHERS:
        patcher.start()
    # All adapter tests below exercise the ARMED capability (allow_live=True
    # constructions with injected fake clients) by setting the read-only
    # external arm gate PROOF_BATCH_LIVE_ARMED=1 in the test environment only.
    # The production default (gate absent -> disabled) is restored in
    # tearDownModule and proven by the disabled-default tests.
    os.environ["PROOF_BATCH_LIVE_ARMED"] = "1"
    # Redirect the adapter's on-disk stores to temp so the module's
    # PROTECTED_ABSENT contract (real data/ files stay absent) holds while the
    # write path is still exercised. Restored in tearDownModule.
    os.environ["SCANNER_MARKET_SNAPSHOT_PATH"] = os.path.join(
        tempfile.mkdtemp(prefix="adapter-test-snap-"), "amazon-market-snapshots.json")
    os.environ["SCANNER_ENRICH_RUN_REPORT_PATH"] = os.path.join(
        tempfile.mkdtemp(prefix="adapter-test-report-"), "enrichment-run-report.json")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _fake_asins():
    return ["B%09d" % i for i in range(1, 18)] + list(CONFLICT_ASINS)


def _preflight(asins=None):
    asins = asins if asins is not None else _fake_asins()
    rows = []
    for i, asin in enumerate(asins, start=1):
        conflict = asin in CONFLICT_ASINS
        rows.append({
            "asin": asin,
            "title": "Kirkland Signature Test Product %d Pack" % i,
            "price": 10.0 + i,
            "reviews": 1000 + i,
            "prime_fba": "yes",
            "bsr_rank_number": 100 + i,
            "bsr_category": "Home & Kitchen",
            "source_files": ["Rank-Product-ASIN-Reviews-Price-BSR.csv"],
            "source_rank": i,
            "capture_time_status": "unknown",
            "title_conflict": conflict,
        })
    return {
        "kind": "proof-batch-preflight",
        "purpose": "provider_data_contract_validation",
        "run_id": "offline-adapter-test-run",
        "human_confirmation": pb.HUMAN_CONFIRMATION_LINE,
        "selection": {"asins": rows},
        "provider_plan": {
            "providers": [{
                "provider": "EASYPARSER", "status": "planned",
                "fields_owned": ["market_offers"], "requests_per_asin": 1,
                "credit_estimate_per_asin": 5,
            }],
            "requested_fields_per_asin": ["market_offers"],
            "request_count_per_asin": 1,
            "request_count_total": 20,
        },
        "hard_caps": {"max_asins": 20, "max_requests": 20},
    }


def _title_for(preflight, asin):
    for row in (preflight["selection"]["asins"]):
        if row["asin"] == asin:
            return row["title"]
    return None


def _offer(position, winner, price_value):
    return {
        "position": position,
        "buybox_winner": winner,
        "price": {"value": price_value, "currency": "USD"},
        "condition": "New",
        "seller_id": "SELLER-%d" % position,
        "seller_name": "Amazon.com" if winner else "Fixture Seller %d" % position,
        "seller_rating": 4.8,
        "seller_ratings_total": 100,
        "is_prime": winner,
        "is_fba": True,
        "is_fbm": False,
        "is_sba": False,
        "fulfilled_by_amazon": True,
        "shipping_text": "FREE Shipping" if winner else None,
        "shipping_is_free": winner,
        "ships_from": "USA",
        "minimum_order_quantity": 1,
        "maximum_order_quantity": 10,
    }


def _valid_result(asin, title, credits_used=5, request_id="req-1",
                  provider_asin=None, extra_gaps=None, observed_at="2026-08-18T12:00:00+00:00"):
    offers = [_offer(1, True, 12.99), _offer(2, False, 13.99)]
    gaps = [
        "Returned offers may be a subset of the total offer_count; pagination and completeness are not verified.",
        "Results are ZIP-code and time specific.",
    ]
    if extra_gaps:
        gaps = gaps + list(extra_gaps)
    return {
        "source": "easyparser",
        "asin": asin,
        "provider_asin": provider_asin if provider_asin is not None else asin,
        "request_id": request_id,
        "title": title,
        "offer_count": 2,
        "offers_returned_count": 2,
        "buy_box_price": 12.99,
        "buy_box_price_raw": {"value": 12.99, "currency": "USD"},
        "buy_box_seller": "Amazon.com",
        "buy_box_seller_id": "SELLER-1",
        "buy_box_is_fba": True,
        "buy_box_is_fbm": False,
        "buy_box_is_prime": True,
        "buy_box_condition": "New",
        "observed_fba_offer_count": 2,
        "observed_fbm_offer_count": 0,
        "observed_amazon_offer_count": 1,
        "offers": offers,
        "request_zip_code": "75201",
        "observed_at": observed_at,
        "credits_used": credits_used,
        "credits_remaining": 95,
        "data_gaps": gaps,
    }


class FakeClient:
    """Explicit injected fake — the ONLY client any allow_live=True test uses."""

    def __init__(self, results=None, default=None, record=None):
        self.results = results if results is not None else {}
        self.default = default
        self.calls = record if record is not None else []

    def __call__(self, asin):
        self.calls.append(asin)
        if asin in self.results:
            return self.results[asin]
        if self.default is not None:
            return self.default
        raise AssertionError("FakeClient has no result for %s" % asin)


def _adapter(client, allow_live=True, **kwargs):
    cfg = {
        "run_id": "offline-adapter-test-run",
        "preflight_fingerprint": "f" * 64,
        "allow_live": allow_live,
        "client": client,
        "force_synthetic_label": True,
    }
    cfg.update(kwargs)
    return EasyparserLiveAdapter(adapter_config=cfg)


def _valid_results(preflight):
    return {
        asin: _valid_result(asin, _title_for(preflight, asin), request_id="req-%s" % asin)
        for asin in _fake_asins()
    }


def _run_full(preflight, client, max_requests=20, max_credits=100, out_dir=None):
    out_dir = out_dir or tempfile.mkdtemp(prefix="adapter-test-out-")
    adapter = _adapter(client)
    outcome = pbr.run_guarded(
        preflight=preflight, adapter=adapter, max_requests=max_requests,
        max_credits=max_credits, live=True, live_enabled=True,
        out_dir=out_dir, run_id=preflight.get("run_id"),
    )
    return outcome, adapter, out_dir


def _write_preflight_tmp(preflight):
    tmp_dir = tempfile.mkdtemp(prefix="adapter-test-preflight-")
    path = os.path.join(tmp_dir, "preflight.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(preflight, fh)
    return path


def _cli_args(preflight_path, extra=None, with_live=True):
    argv = ["run"]
    if with_live:
        argv.append("--live")
    argv += ["--preflight", preflight_path, "--max-requests", "20", "--max-credits", "100"]
    if extra:
        argv += extra
    return argv


@contextlib.contextmanager
def _without_arm_gate():
    """Temporarily remove the PROOF_BATCH_LIVE_ARMED env gate (production
    default is absent) so a test can exercise the disabled path. Restores the
    prior value afterwards; never leaves the gate set."""
    saved = os.environ.pop(adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV, None)
    try:
        yield
    finally:
        if saved is not None:
            os.environ[adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV] = saved


# ---------------------------------------------------------------------------
# 1-11. Guard refusals: zero provider calls
# ---------------------------------------------------------------------------

class TestGuardRefusals(unittest.TestCase):

    def test_01_import_makes_no_provider_call(self):
        adapter_mod  # imported above; no transport call happened or the
        # module-level patches would have tripped.

    def test_02_dry_run_makes_no_provider_call(self):
        preflight = _preflight()
        path = _write_preflight_tmp(preflight)
        rc = pbr.main(["dry-run", "--preflight", path, "--max-requests", "20", "--max-credits", "100"])
        self.assertEqual(rc, 0)

    def test_03_gate_off_live_makes_no_provider_call(self):
        path = _write_preflight_tmp(_preflight())
        rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)

    def test_03b_gate_on_adapter_gate_still_refuses(self):
        # Production default: the second external arm gate PROOF_BATCH_LIVE_ARMED
        # is absent, so even with SCANNER_LIVE_ALLOWED=1 and every runner guard
        # passing the arming path refuses at the adapter gate.
        path = _write_preflight_tmp(_preflight())
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}), \
                _without_arm_gate(), \
                patch.object(pbr, "LIVE_CLIENT_FACTORY", lambda: _raising):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_04_missing_live_flag_makes_no_provider_call(self):
        path = _write_preflight_tmp(_preflight())
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}):
            rc = pbr.main(_cli_args(path, with_live=False))
        self.assertEqual(rc, 2)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_05_missing_preflight_makes_no_provider_call(self):
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}):
            rc = pbr.main(["run", "--live", "--max-requests", "20", "--max-credits", "100"])
        self.assertEqual(rc, 2)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_06_altered_preflight_makes_no_provider_call(self):
        preflight = _preflight()
        preflight["run_id"] = "tampered-run-id"
        path = _write_preflight_tmp(preflight)
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_07_non_easyparser_plan_makes_no_provider_call(self):
        preflight = _preflight()
        preflight["provider_plan"]["providers"] = [{
            "provider": "KEEPA", "status": "planned",
            "fields_owned": ["bsr"], "requests_per_asin": 1,
            "credit_estimate_per_asin": None,
        }]
        path = _write_preflight_tmp(preflight)
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_08_wrong_field_contract_makes_no_provider_call(self):
        preflight = _preflight()
        preflight["provider_plan"]["requested_fields_per_asin"] = ["market_offers", "bsr"]
        path = _write_preflight_tmp(preflight)
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_09_arbitrary_asin_options_rejected(self):
        path = _write_preflight_tmp(_preflight())
        for opt in ("--asin", "--asins", "--input-file", "--discover"):
            with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}):
                rc = pbr.main(_cli_args(path, extra=[opt, "B01H40O42I"]))
            self.assertEqual(rc, 2, opt)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_10_asins_count_not_20_rejected(self):
        preflight = _preflight(asins=["B%09d" % i for i in range(1, 20)])
        path = _write_preflight_tmp(preflight)
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_11_duplicate_asins_rejected(self):
        asins = _fake_asins()
        asins[17] = asins[0]
        preflight = _preflight(asins=asins)
        path = _write_preflight_tmp(preflight)
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)


# ---------------------------------------------------------------------------
# Dry-run contract (Phase 2 C): exact printed fields, no adapter construction
# ---------------------------------------------------------------------------

class TestDryRunContract(unittest.TestCase):

    def _dry_run_output(self, extra_argv=None):
        preflight = _preflight()
        path = _write_preflight_tmp(preflight)
        argv = ["dry-run", "--preflight", path, "--max-requests", "20", "--max-credits", "100"]
        if extra_argv:
            argv += extra_argv
        out = io.StringIO()
        with patch.object(adapter_mod, "EasyparserLiveAdapter", side_effect=AssertionError(
                "dry-run must never construct the live adapter")):
            with contextlib.redirect_stdout(out):
                rc = pbr.main(argv)
        return rc, out.getvalue(), preflight

    def test_dry_run_prints_exact_20_asins_and_count(self):
        rc, output, preflight = self._dry_run_output()
        self.assertEqual(rc, 0)
        asins = [row["asin"] for row in preflight["selection"]["asins"]]
        for asin in asins:
            self.assertIn("\n  - %s\n" % asin, output)
        self.assertIn("asins:                 20 / 20 (fixed set)", output)

    def test_dry_run_prints_scope_contract(self):
        rc, output, _ = self._dry_run_output()
        self.assertEqual(rc, 0)
        self.assertIn("provider:              EASYPARSER", output)
        self.assertIn("requested fields:      market_offers", output)
        self.assertIn("max_requests:          20 (effective 20)", output)
        self.assertIn("max_credits:           100", output)
        self.assertIn("estimated credits:     ~100 (20 requests x 5/request, documented estimate)", output)
        self.assertIn("credit accounting:     estimated_only (provider not contacted; actual_credits_used = null)", output)
        self.assertIn("retries:               0 (default; no hidden retries)", output)

    def test_dry_run_prints_output_dir_and_review_asins(self):
        rc, output, preflight = self._dry_run_output()
        self.assertEqual(rc, 0)
        self.assertIn("output dir:            %s" % ("data/batch/live-validation-runs" + os.sep + preflight["run_id"]), output)
        for asin in sorted(CONFLICT_ASINS):
            self.assertIn(asin, output)
        self.assertIn("expected_mapping_review ASINs:", output)

    def test_dry_run_prints_all_hard_stops_and_wording(self):
        rc, output, _ = self._dry_run_output()
        self.assertEqual(rc, 0)
        for reason, _ in pbr.HARD_STOP_CONDITIONS:
            self.assertIn(reason, output)
        self.assertIn(pb.HUMAN_CONFIRMATION_LINE, output)
        self.assertIn(
            "DRY RUN ONLY — NO PROVIDER CALLS, NO CREDITS USED, NO LIVE SNAPSHOT WRITTEN",
            output,
        )

    def test_dry_run_missing_credits_cap_still_refuses(self):
        preflight = _preflight()
        path = _write_preflight_tmp(preflight)
        out = io.StringIO()
        with patch.object(adapter_mod, "EasyparserLiveAdapter", side_effect=AssertionError(
                "dry-run must never construct the live adapter")):
            with contextlib.redirect_stdout(out):
                rc = pbr.main(["dry-run", "--preflight", path, "--max-requests", "20"])
        self.assertEqual(rc, 2)
        self.assertIn("--max-credits", out.getvalue())


# ---------------------------------------------------------------------------
# 12-16. Budget, retries, one-ASIN boundary
# ---------------------------------------------------------------------------

class TestBudgetAndBoundary(unittest.TestCase):

    def test_12_request_cap_blocks_next_call(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        out_dir = tempfile.mkdtemp(prefix="adapter-test-cap-")
        adapter = _adapter(client)
        outcome = pbr.run_guarded(
            preflight=preflight, adapter=adapter, max_requests=5, max_credits=100,
            live=True, live_enabled=True, out_dir=out_dir, run_id="cap-test",
        )
        self.assertEqual(outcome["status"], "aborted")
        self.assertEqual(outcome["stop_reason"], pbr.STOP_MAX_REQUESTS)
        self.assertEqual(len(client.calls), 5)
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["stop_reason"], pbr.STOP_MAX_REQUESTS)
        self.assertEqual(manifest["budget"]["requests_used"], 5)
        self.assertFalse(os.path.exists(os.path.join(out_dir, "validated-result-envelopes.json")))

    def test_13_credit_cap_blocks_next_call(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        out_dir = tempfile.mkdtemp(prefix="adapter-test-credit-")
        adapter = _adapter(client)
        outcome = pbr.run_guarded(
            preflight=preflight, adapter=adapter, max_requests=20, max_credits=7,
            live=True, live_enabled=True, out_dir=out_dir, run_id="credit-test",
        )
        self.assertEqual(outcome["status"], "aborted")
        self.assertEqual(outcome["stop_reason"], pbr.STOP_MAX_CREDITS)
        self.assertEqual(len(client.calls), 1)
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["budget"]["requests_used"], 1)
        self.assertEqual(manifest["budget"]["credits_estimated_used"], 5.0)

    def test_14_unknown_or_unbounded_cost_fails_closed(self):
        with self.assertRaises(pbr.GuardError):
            _adapter(FakeClient(default={}), estimated_credits_per_request=0)
        with self.assertRaises(pbr.GuardError):
            _adapter(FakeClient(default={}), estimated_credits_per_request=-1)
        adapter = _adapter(FakeClient(default={}), credit_budget_remaining=0)
        with self.assertRaises(pbr.GuardError):
            adapter.fetch("B000000001", 1)
        adapter = _adapter(FakeClient(default={}), credit_budget_remaining=3)
        with self.assertRaises(pbr.GuardError):
            adapter.fetch("B000000001", 1)

    def test_14b_budget_tracker_rejects_unbounded_estimate(self):
        for bad in (None, 0, -1, "n/a", True):
            with self.assertRaises(pbr.GuardError):
                pbr.BudgetTracker(max_requests=20, max_credits=100,
                                  estimated_credits_per_request=bad)
        tracker = pbr.BudgetTracker(max_requests=20, max_credits=100,
                                    estimated_credits_per_request=5.0)
        self.assertTrue(tracker.can_request())

    def test_15_retries_default_zero_in_manifests(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        outcome, adapter, out_dir = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(adapter.retries_used, 0)
        manifest = json.load(open(os.path.join(out_dir, "run-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["budget"]["retries_used"], 0)

    def test_16_exactly_one_asin_per_invocation(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        outcome, adapter, _ = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        self.assertEqual(len(client.calls), 20)
        self.assertEqual(len(set(client.calls)), 20)
        self.assertEqual(set(client.calls), set(_fake_asins()))
        self.assertEqual(adapter.requests_made, client.calls)


# ---------------------------------------------------------------------------
# 17-28. Normalization, accounting, mapping, error handling
# ---------------------------------------------------------------------------

class TestFetchAndNormalization(unittest.TestCase):

    def test_17_valid_fixture_normalizes_correctly(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        outcome, _, out_dir = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        payload = json.load(open(os.path.join(out_dir, "validated-result-envelopes.json"), encoding="utf-8"))
        self.assertEqual(payload["envelope_count"], 20)
        self.assertTrue(payload["synthetic_fixture"])
        self.assertEqual(payload["adapter"], "easyparser-live")
        envelopes = {e["asin"]: e for e in payload["envelopes"]}
        self.assertEqual(len(envelopes), 20)
        for asin in _fake_asins():
            env = envelopes[asin]
            self.assertEqual(env["result_status"], "available")
            self.assertEqual(env["provenance"]["adapter"], "easyparser-live")
            self.assertIsNotNone(env["provenance"].get("provider_request_id"))
            self.assertEqual(env["provenance"]["credit_accounting_status"], "provider_reported")
            self.assertEqual(env["snapshot"]["facts"]["market"]["buy_box"]["price"], 12.99)
            self.assertEqual(env["snapshot"]["facts"]["market"]["coverage"]["offers_complete_status"], "full")
            self.assertEqual(env["preflight_fingerprint"], pbr.preflight_fingerprint(preflight))

    def test_18_missing_values_stay_null_never_zero(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        asin = _fake_asins()[0]
        minimal = results[asin]
        minimal["buy_box_price"] = None
        minimal["buy_box_seller"] = None
        minimal["offers"] = [{
            "position": 1, "buybox_winner": None,
            "price": {"value": "n/a", "currency": None},
            "condition": None, "seller_id": None, "seller_name": None,
            "is_prime": None, "is_fba": None, "is_fbm": None,
            "shipping_text": None, "shipping_is_free": None,
        }]
        client = FakeClient(results=results)
        outcome, _, out_dir = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        payload = json.load(open(os.path.join(out_dir, "validated-result-envelopes.json"), encoding="utf-8"))
        env = next(e for e in payload["envelopes"] if e["asin"] == asin)
        offer = env["snapshot"]["facts"]["market"]["offers"][0]
        self.assertNotIn("price", offer)
        self.assertNotIn("seller_name", offer)
        self.assertEqual(env["snapshot"]["facts"]["market"]["buy_box"]["price"], None)
        self.assertEqual(env["snapshot"]["facts"]["economics"]["net_profit"], None)
        self.assertEqual(env["snapshot"]["facts"]["demand"]["bsr"], None)

    def test_19_provider_reported_credits_distinct_from_estimates(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        outcome, _, out_dir = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        payload = json.load(open(os.path.join(out_dir, "validated-result-envelopes.json"), encoding="utf-8"))
        self.assertEqual(payload["envelopes"][0]["credits_used_reported"], 5)
        self.assertEqual(payload["envelopes"][0]["credits_used_estimated"], 5.0)
        self.assertEqual(payload["envelopes"][-1]["credits_used_reported"], 100)
        self.assertEqual(payload["envelopes"][-1]["credits_used_estimated"], 100.0)
        self.assertEqual(payload["envelopes"][0]["provenance"]["credit_accounting_status"], "provider_reported")
        manifest = json.load(open(os.path.join(out_dir, "run-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["honesty"]["actual_credit_total"], 100)
        self.assertEqual(manifest["budget"]["credits_actual_status"], "reported_by_provider")

    def test_20_actual_credits_null_when_unavailable(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        for asin in results:
            results[asin]["credits_used"] = None
        client = FakeClient(results=results)
        outcome, _, out_dir = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        payload = json.load(open(os.path.join(out_dir, "validated-result-envelopes.json"), encoding="utf-8"))
        env = payload["envelopes"][0]
        self.assertEqual(env["provenance"]["credit_accounting_status"], "estimated_only")
        manifest = json.load(open(os.path.join(out_dir, "run-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["honesty"]["actual_credit_total"], None)
        self.assertEqual(manifest["budget"]["credits_actual_status"], "unavailable_estimated_only")

    def test_21_wrong_returned_asin_hard_aborts(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        asin = _fake_asins()[0]
        results[asin]["provider_asin"] = "B0WRONGASIN"
        results[asin]["asin"] = "B0WRONGASIN"
        client = FakeClient(results=results)
        out_dir = tempfile.mkdtemp(prefix="adapter-test-wrong-asin-")
        adapter = _adapter(client)
        with self.assertRaises(pbr.RunAbort) as ctx:
            pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                            max_credits=100, live=True, live_enabled=True,
                            out_dir=out_dir, run_id="wrong-asin-test")
        self.assertEqual(ctx.exception.reason, pbr.STOP_WRONG_ASIN)
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["stop_reason"], pbr.STOP_WRONG_ASIN)
        self.assertFalse(os.path.exists(os.path.join(out_dir, "validated-result-envelopes.json")))

    def test_21b_missing_provider_asin_hard_aborts(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        asin = _fake_asins()[0]
        results[asin]["provider_asin"] = None
        client = FakeClient(results=results)
        out_dir = tempfile.mkdtemp(prefix="adapter-test-no-asin-")
        adapter = _adapter(client)
        with self.assertRaises(pbr.RunAbort) as ctx:
            pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                            max_credits=100, live=True, live_enabled=True,
                            out_dir=out_dir, run_id="no-asin-test")
        self.assertEqual(ctx.exception.reason, pbr.STOP_WRONG_ASIN)
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["stop_reason"], pbr.STOP_WRONG_ASIN)

    def test_22_incompatible_pack_hard_aborts(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        asin = _fake_asins()[0]
        results[asin]["title"] = "Kirkland Signature Test Product 6 Pack"
        client = FakeClient(results=results)
        out_dir = tempfile.mkdtemp(prefix="adapter-test-pack-")
        adapter = _adapter(client)
        with self.assertRaises(pbr.RunAbort) as ctx:
            pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                            max_credits=100, live=True, live_enabled=True,
                            out_dir=out_dir, run_id="pack-test")
        self.assertEqual(ctx.exception.reason, pbr.STOP_MAPPING_MISMATCH)
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["stop_reason"], pbr.STOP_MAPPING_MISMATCH)

    def test_23_exactly_three_conflicts_expected_review(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        outcome, _, out_dir = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        payload = json.load(open(os.path.join(out_dir, "validated-result-envelopes.json"), encoding="utf-8"))
        review = [e["asin"] for e in payload["envelopes"] if e["mapping_state"] == pbr.STATE_EXPECTED_REVIEW]
        self.assertEqual(sorted(review), sorted(CONFLICT_ASINS))
        self.assertEqual(len(review), 3)
        matches = [e["asin"] for e in payload["envelopes"] if e["mapping_state"] == pbr.STATE_MATCH]
        self.assertEqual(len(matches), 17)

    def test_24_unexpected_mismatch_hard_aborts(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        asin = "B000000017"
        results[asin]["title"] = "Entirely Unrelated Gadget 6 Pack"
        client = FakeClient(results=results)
        out_dir = tempfile.mkdtemp(prefix="adapter-test-mismatch-")
        adapter = _adapter(client)
        with self.assertRaises(pbr.RunAbort) as ctx:
            pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                            max_credits=100, live=True, live_enabled=True,
                            out_dir=out_dir, run_id="mismatch-test")
        self.assertEqual(ctx.exception.reason, pbr.STOP_MAPPING_MISMATCH)

    def test_25_provider_error_scrubbed_blocks_persistence(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        asin = _fake_asins()[0]
        results[asin]["data_gaps"] = results[asin]["data_gaps"] + ["Easyparser request timed out."]
        results[asin]["offers"] = []
        client = FakeClient(results=results)
        out_dir = tempfile.mkdtemp(prefix="adapter-test-provider-error-")
        adapter = _adapter(client)
        with self.assertRaises(pbr.RunAbort) as ctx:
            pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                            max_credits=100, live=True, live_enabled=True,
                            out_dir=out_dir, run_id="provider-error-test")
        self.assertEqual(ctx.exception.reason, pbr.STOP_PROVIDER_ERROR)
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["stop_reason"], pbr.STOP_PROVIDER_ERROR)
        self.assertFalse(os.path.exists(os.path.join(out_dir, "validated-result-envelopes.json")))
        for key in ("offers", "raw", "body", "result"):
            self.assertNotIn(key, manifest)

    def test_26_malformed_response_scrubbed_blocks_persistence(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        asin = _fake_asins()[0]
        results[asin]["data_gaps"] = results[asin]["data_gaps"] + ["Easyparser response was not valid JSON."]
        client = FakeClient(results=results)
        out_dir = tempfile.mkdtemp(prefix="adapter-test-parse-")
        adapter = _adapter(client)
        with self.assertRaises(pbr.RunAbort) as ctx:
            pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                            max_credits=100, live=True, live_enabled=True,
                            out_dir=out_dir, run_id="parse-test")
        self.assertEqual(ctx.exception.reason, pbr.STOP_PARSE_ERROR)
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["stop_reason"], pbr.STOP_PARSE_ERROR)
        self.assertFalse(os.path.exists(os.path.join(out_dir, "validated-result-envelopes.json")))

    def test_27_secret_like_rejection(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        asin = _fake_asins()[0]
        results[asin]["api_token"] = "super-secret"
        client = FakeClient(results=results)
        out_dir = tempfile.mkdtemp(prefix="adapter-test-secret-")
        adapter = _adapter(client)
        with self.assertRaises(pbr.RunAbort) as ctx:
            pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                            max_credits=100, live=True, live_enabled=True,
                            out_dir=out_dir, run_id="secret-test")
        # The adapter itself refuses secret-like results (fail closed) before
        # the runner's own scan runs; either reason blocks persistence.
        self.assertIn(ctx.exception.reason, (pbr.STOP_SECRET, pbr.STOP_ADAPTER))
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["stop_reason"], ctx.exception.reason)
        self.assertFalse(os.path.exists(os.path.join(out_dir, "validated-result-envelopes.json")))

    def test_28_schema_failure_blocks_persistence(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        out_dir = tempfile.mkdtemp(prefix="adapter-test-schema-")
        adapter = _adapter(client)
        valid = _valid_result(_fake_asins()[0], _title_for(preflight, _fake_asins()[0]))
        real_snap = pbr.build_envelope_snapshot(_fake_asins()[0], valid)
        del real_snap["facts"]["provenance"]
        with patch("proof_batch_run.build_envelope_snapshot", return_value=real_snap):
            with self.assertRaises(pbr.RunAbort) as ctx:
                pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                                max_credits=100, live=True, live_enabled=True,
                                out_dir=out_dir, run_id="schema-test")
        self.assertEqual(ctx.exception.reason, pbr.STOP_SCHEMA)
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["stop_reason"], pbr.STOP_SCHEMA)


# ---------------------------------------------------------------------------
# 29-31. Persistence and reporting
# ---------------------------------------------------------------------------

class TestPersistenceAndReport(unittest.TestCase):

    def test_29_atomic_finalization_for_20_valid_fixtures(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        outcome, _, out_dir = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        results_path = os.path.join(out_dir, "validated-result-envelopes.json")
        manifest_path = os.path.join(out_dir, "run-manifest.json")
        self.assertTrue(os.path.isfile(results_path))
        self.assertTrue(os.path.isfile(manifest_path))
        self.assertFalse(os.path.exists(os.path.join(out_dir, "failure-manifest.json")))
        self.assertEqual(
            [f for f in os.listdir(out_dir) if f.endswith(".tmp")], []
        )
        payload = json.load(open(results_path, encoding="utf-8"))
        self.assertEqual(payload["preflight_fingerprint"], pbr.preflight_fingerprint(preflight))
        self.assertEqual(payload["envelope_count"], 20)
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        self.assertEqual(manifest["counts"]["match"], 17)
        self.assertEqual(manifest["counts"]["expected_mapping_review"], 3)
        self.assertTrue(manifest["persistence"]["atomic_replace"])
        self.assertTrue(manifest["persistence"]["read_back_validated"])

    def test_30_atomic_write_failure_scrubbed_manifest_only(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        out_dir = tempfile.mkdtemp(prefix="adapter-test-atomic-")
        adapter = _adapter(client)
        real_replace = pbr.os.replace

        def failing_replace(src, dst, *args, **kwargs):
            if "validated-result-envelopes" in str(dst):
                raise OSError("simulated atomic replace failure")
            return real_replace(src, dst, *args, **kwargs)

        with patch("proof_batch_run.os.replace", side_effect=failing_replace):
            with self.assertRaises(pbr.RunAbort) as ctx:
                pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                                max_credits=100, live=True, live_enabled=True,
                                out_dir=out_dir, run_id="atomic-test")
        self.assertEqual(ctx.exception.reason, pbr.STOP_PERSISTENCE)
        self.assertFalse(os.path.exists(os.path.join(out_dir, "validated-result-envelopes.json")))
        self.assertEqual(
            [f for f in os.listdir(out_dir) if f.endswith(".tmp")], []
        )
        manifest = json.load(open(os.path.join(out_dir, "failure-manifest.json"), encoding="utf-8"))
        self.assertEqual(manifest["stop_reason"], pbr.STOP_PERSISTENCE)

    def test_31_fixture_result_flows_through_report(self):
        preflight = _preflight()
        reference = {
            "canonical": {row["asin"]: dict(row) for row in preflight["selection"]["asins"]},
            "conflicts": [],
        }
        out_dir = tempfile.mkdtemp(prefix="adapter-test-report-")
        adapter = pbr.FixtureAdapter(reference)
        outcome = pbr.run_guarded(
            preflight=preflight, adapter=adapter, max_requests=20, max_credits=100,
            live=True, live_enabled=True, out_dir=out_dir, run_id="report-test",
        )
        self.assertEqual(outcome["status"], "completed")
        report = pbr.build_run_report(out_dir, reference=reference)
        self.assertEqual(report["mapping_summary"]["match_count"], 17)
        self.assertEqual(report["mapping_summary"]["expected_mapping_review_count"], 3)
        self.assertEqual(
            sorted(report["mapping_summary"]["expected_mapping_review_asins"]),
            sorted(CONFLICT_ASINS),
        )
        self.assertTrue(report["no_universal_accuracy_percentage"])
        written = pbr.write_report_files(out_dir, report)
        for path in written:
            self.assertTrue(os.path.isfile(path), path)

    def test_31b_report_fingerprint_linkage_verified_against_manifest(self):
        preflight = _preflight()
        client = FakeClient(results=_valid_results(preflight))
        outcome, _, out_dir = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        report = pbr.build_run_report(out_dir)
        self.assertTrue(report["fingerprint_linkage"]["linked"])
        self.assertEqual(report["fingerprint_linkage"]["results_artifact"],
                         report["fingerprint_linkage"]["run_manifest"])
        manifest_path = os.path.join(out_dir, "run-manifest.json")
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        manifest["preflight_fingerprint"] = "0" * 64
        with open(manifest_path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        with self.assertRaises(pbr.GuardError):
            pbr.build_run_report(out_dir)

    def test_31c_report_outcome_vocabulary_and_purchase_statement(self):
        preflight = _preflight()
        results = _valid_results(preflight)
        bench_prices = {row["asin"]: row["price"] for row in preflight["selection"]["asins"]}
        for asin, result in results.items():
            bench = bench_prices.get(asin)
            if isinstance(bench, (int, float)):
                price = round(bench * 1.01, 2)
                result["buy_box_price"] = price
                result["buy_box_price_raw"] = {"value": price, "currency": "USD"}
                result["offers"] = [
                    _offer(1, True, price),
                    _offer(2, False, round(price * 1.02, 2)),
                ]
        client = FakeClient(results=results)
        outcome, _, out_dir = _run_full(preflight, client)
        self.assertEqual(outcome["status"], "completed")
        report = pbr.build_run_report(out_dir)
        self.assertEqual(report["outcome_summary"][pbr.STATE_MATCH], 17)
        self.assertEqual(report["outcome_summary"][pbr.STATE_EXPECTED_REVIEW], 3)
        self.assertEqual(report["outcome_summary"][pbr.STATE_UNEXPECTED_MISMATCH], 0)
        self.assertEqual(report["outcome_summary"][pbr.STATE_UNAVAILABLE], 0)
        self.assertEqual(report["outcome_summary"][pbr.STATE_PROVIDER_ERROR], 0)
        self.assertEqual(sum(report["outcome_summary"].values()), 20)
        for row in report["per_asin"]:
            self.assertIn(row["outcome_status"], (
                pbr.STATE_MATCH, pbr.STATE_EXPECTED_REVIEW,
                pbr.STATE_UNEXPECTED_MISMATCH, pbr.STATE_UNAVAILABLE,
                pbr.STATE_DRIFT, pbr.STATE_PROVIDER_ERROR,
            ))
        self.assertEqual(report["outcome_vocabulary"]["parse_error"],
                         pbr.STATE_PARSE_ERROR)
        self.assertEqual(report["purchase_authorization_statement"],
                         pbr.PURCHASE_AUTHORIZATION_STATEMENT)
        written = pbr.write_report_files(out_dir, report)
        md = open(os.path.join(out_dir, "human-review-summary.md"), encoding="utf-8").read()
        self.assertIn(pbr.PURCHASE_AUTHORIZATION_STATEMENT, md)
        self.assertIn("## Outcome summary (per-ASIN vocabulary)", md)


# ---------------------------------------------------------------------------
# 32-33. Containment and protected integrity
# ---------------------------------------------------------------------------

class TestContainmentAndIntegrity(unittest.TestCase):

    def test_32_no_provider_calls_from_preflight_report_cache_ui_paths(self):
        preflight = _preflight()
        store = {
            "canonical": {row["asin"]: dict(row) for row in preflight["selection"]["asins"]},
            "conflicts": [{"asin": a, "field": "title"} for a in CONFLICT_ASINS],
        }
        generated = pb.build_preflight(store)
        self.assertEqual(len(generated["selection"]["asins"]), 20)

        out_dir = tempfile.mkdtemp(prefix="adapter-test-nocall-")
        adapter = pbr.FixtureAdapter(store)
        pbr.run_guarded(preflight=preflight, adapter=adapter, max_requests=20,
                        max_credits=100, live=True, live_enabled=True,
                        out_dir=out_dir, run_id="nocall-test")
        report = pbr.build_run_report(out_dir, reference=store)
        pbr.write_report_files(out_dir, report)

        seller_cache = os.path.join(tempfile.mkdtemp(prefix="adapter-test-cache-"), "seller-offer-cache.json")
        with patch.dict(os.environ, {
            "SCANNER_SELLER_CACHE_PATH": seller_cache,
        }, clear=False):
            contract = offer_enrichment.get_seller_offer_contract("B01H40O42I")
        self.assertIn(contract.get("offer_data_status"), ("provider_error", "unavailable"))

        import main  # noqa: F401  (route code imports fine; no calls made)

    def test_33_protected_artifacts_unchanged(self):
        before = _PROTECTED_BEFORE
        after = _protected_before()
        self.assertEqual(before, after)
        for path in PROTECTED_ABSENT:
            self.assertFalse(os.path.exists(path), path)


# ---------------------------------------------------------------------------
# Mandatory regression: CLI script/module invocation + class identity
# ---------------------------------------------------------------------------

class TestCliRegression(unittest.TestCase):

    def _write_preflight(self):
        path = _write_preflight_tmp(_preflight())
        return path

    def _env(self, gate_on):
        env = dict(os.environ)
        # Production default: the Proof Batch arm gate is absent in the CLI
        # subprocess (a fresh process never inherits the unit-test fixture).
        env.pop(adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV, None)
        if gate_on:
            env["SCANNER_LIVE_ALLOWED"] = "1"
        else:
            env.pop("SCANNER_LIVE_ALLOWED", None)
        return env

    def test_cli_direct_script_gate_on_refuses_cleanly(self):
        path = self._write_preflight()
        proc = subprocess.run(
            [sys.executable, "proof_batch_run.py", "run", "--live",
             "--preflight", path, "--max-requests", "20", "--max-credits", "100"],
            cwd=_BACKEND_DIR, env=self._env(True),
            capture_output=True, text=True, timeout=120,
        )
        output = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 2)
        self.assertIn("easyparser-live adapter is not armed", output)
        self.assertIn("no provider call was made", output)
        self.assertNotIn("Traceback", output)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_cli_module_invocation_refuses_cleanly(self):
        path = self._write_preflight()
        proc = subprocess.run(
            [sys.executable, "-m", "proof_batch_run", "run", "--live",
             "--preflight", path, "--max-requests", "20", "--max-credits", "100"],
            cwd=_BACKEND_DIR, env=self._env(True),
            capture_output=True, text=True, timeout=120,
        )
        output = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 2)
        self.assertIn("easyparser-live adapter is not armed", output)
        self.assertNotIn("Traceback", output)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_cli_gate_off_refuses_cleanly(self):
        path = self._write_preflight()
        proc = subprocess.run(
            [sys.executable, "proof_batch_run.py", "run", "--live",
             "--preflight", path, "--max-requests", "20", "--max-credits", "100"],
            cwd=_BACKEND_DIR, env=self._env(False),
            capture_output=True, text=True, timeout=120,
        )
        output = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 2)
        self.assertIn("Live providers are disabled", output)
        self.assertNotIn("Traceback", output)

    def test_cli_arbitrary_asin_option_refused(self):
        path = self._write_preflight()
        proc = subprocess.run(
            [sys.executable, "proof_batch_run.py", "run", "--live",
             "--preflight", path, "--max-requests", "20", "--max-credits", "100",
             "--asins", "B01H40O42I"],
            cwd=_BACKEND_DIR, env=self._env(True),
            capture_output=True, text=True, timeout=120,
        )
        output = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 2)
        self.assertIn("--asins is not supported", output)
        self.assertNotIn("Traceback", output)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_shared_class_identity_under_direct_invocation(self):
        probe = os.path.join(tempfile.mkdtemp(prefix="adapter-test-probe-"), "identity_probe.py")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write(
                "import sys, types, os\n"
                "BACKEND = sys.argv[1]\n"
                "sys.path.insert(0, BACKEND)\n"
                "real_exit = sys.exit\n"
                "def fake_exit(code=0):\n"
                "    raise SystemExit(code)\n"
                "sys.exit = fake_exit\n"
                "mod = types.ModuleType('__main__')\n"
                "mod.__file__ = os.path.join(BACKEND, 'proof_batch_run.py')\n"
                "saved = sys.modules.get('__main__')\n"
                "sys.modules['__main__'] = mod\n"
                "try:\n"
                "    with open(mod.__file__, encoding='utf-8') as src:\n"
                "        exec(compile(src.read(), mod.__file__, 'exec'), mod.__dict__)\n"
                "except SystemExit:\n"
                "    pass\n"
                "finally:\n"
                "    sys.exit = real_exit\n"
                "    if saved is not None:\n"
                "        sys.modules['__main__'] = saved\n"
                "    else:\n"
                "        sys.modules.pop('__main__', None)\n"
                "import proof_batch_run as pbr2\n"
                "from proof_batch_easyparser_adapter import EasyparserLiveAdapter\n"
                "import proof_batch_easyparser_adapter as am2\n"
                "os.environ['PROOF_BATCH_LIVE_ARMED'] = '1'  # probe exercises the armed capability with an injected fake client\n"
                "alias_ok = pbr2 is mod\n"
                "guard_ok = False\n"
                "try:\n"
                "    EasyparserLiveAdapter({'allow_live': False})\n"
                "except pbr2.GuardError:\n"
                "    guard_ok = True\n"
                "adapter = EasyparserLiveAdapter({\n"
                "    'allow_live': True, 'run_id': 'probe-run',\n"
                "    'preflight_fingerprint': 'f' * 64,\n"
                "    'client': lambda asin: {},\n"
                "    'force_synthetic_label': True,\n"
                "})\n"
                "isinstance_ok = isinstance(adapter, pbr2.ProviderAdapter)\n"
                "print('ALIAS=%s GUARD=%s ISINSTANCE=%s' % (alias_ok, guard_ok, isinstance_ok))\n"
                "sys.exit(0 if (alias_ok and guard_ok and isinstance_ok) else 1)\n"
            )
        proc = subprocess.run(
            [sys.executable, probe, _BACKEND_DIR],
            cwd=_BACKEND_DIR, env=self._env(True),
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("ALIAS=True GUARD=True ISINSTANCE=True", proc.stdout)


# ---------------------------------------------------------------------------
# Mandatory regression: injected-fake fail-closed
# ---------------------------------------------------------------------------

class TestFakeClientFailClosed(unittest.TestCase):

    def test_adapter_requires_explicit_client_fail_closed(self):
        with self.assertRaises(pbr.GuardError) as ctx:
            EasyparserLiveAdapter(adapter_config={
                "run_id": "r", "preflight_fingerprint": "f" * 64,
                "allow_live": True,
            })
        self.assertIn("explicitly injected client", str(ctx.exception))

    def test_fake_client_never_touches_real_transport(self):
        client = FakeClient(default={})
        adapter = _adapter(client)
        result = adapter.fetch("B000000001", 1)
        self.assertIn("adapter_request_meta", result)
        meta = result["adapter_request_meta"]
        self.assertEqual(meta["requested_asin"], "B000000001")
        self.assertEqual(meta["request_index"], 1)
        self.assertEqual(meta["request_attempted"], True)
        self.assertEqual(meta["retries_used"], 0)
        self.assertEqual(adapter.requests_made, ["B000000001"])

    def test_gate_off_adapter_refuses_without_client_even(self):
        with self.assertRaises(pbr.GuardError) as ctx:
            EasyparserLiveAdapter(adapter_config={
                "run_id": "r", "preflight_fingerprint": "f" * 64,
                "allow_live": False,
            })
        self.assertIn("allow_live=False", str(ctx.exception))

    def test_adapter_rejects_non_dict_client_result(self):
        with self.assertRaises(pbr.GuardError):
            _adapter(FakeClient(default="not-a-dict")).fetch("B000000001", 1)

    def test_allow_live_without_force_synthetic_still_requires_fake(self):
        client = FakeClient(default={})
        adapter = _adapter(client, force_synthetic_label=False)
        result = adapter.fetch("B000000001", 1)
        self.assertIsInstance(result, dict)
        self.assertFalse(adapter.force_synthetic_label)


# ---------------------------------------------------------------------------
# Arming capability: disabled by default, guards-before-factory, armed CLI
# ---------------------------------------------------------------------------

class TestAdapterArming(unittest.TestCase):

    def test_adapter_disabled_by_default_refuses_allow_live(self):
        with _without_arm_gate():
            with self.assertRaises(pbr.GuardError) as ctx:
                _adapter(FakeClient(default={}))
        message = str(ctx.exception)
        self.assertIn("easyparser-live adapter is not armed", message)
        self.assertIn("no provider call was made", message)

    def test_adapter_allow_live_false_refuses_first_path(self):
        with self.assertRaises(pbr.GuardError) as ctx:
            _adapter(FakeClient(default={}), allow_live=False)
        self.assertIn("allow_live=False", str(ctx.exception))

    def test_runner_disabled_never_calls_factory(self):
        calls = []
        path = _write_preflight_tmp(_preflight())
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}), \
                _without_arm_gate(), \
                patch.object(pbr, "LIVE_CLIENT_FACTORY", lambda: calls.append("factory") or _raising):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_factory_never_called_when_any_guard_missing(self):
        def scenario(argv, env_on):
            calls = []
            factory = lambda: calls.append("factory") or _raising
            with patch.dict(os.environ, ({"SCANNER_LIVE_ALLOWED": "1"} if env_on else {}), clear=False), \
                    patch.object(pbr, "LIVE_CLIENT_FACTORY", factory):
                rc = pbr.main(argv)
            return rc, calls

        preflight = _preflight()
        path = _write_preflight_tmp(preflight)

        rc, calls = scenario(_cli_args(path), env_on=False)  # gate off
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])

        rc, calls = scenario(_cli_args(path, with_live=False), env_on=True)  # missing --live
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])

        rc, calls = scenario(
            ["run", "--live", "--preflight", path, "--max-requests", "20"], env_on=True)  # missing --max-credit
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])

        bad_preflight = _preflight(asins=_fake_asins()[:19])  # binding: count != 20
        bad_path = _write_preflight_tmp(bad_preflight)
        rc, calls = scenario(_cli_args(bad_path), env_on=True)  # binding invalid -> refused before arming
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])

        rc, calls = scenario(_cli_args(path, extra=["--asins", "B01H40O42I"]), env_on=True)  # arbitrary ASIN option
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])

        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_armed_cli_completes_offline_with_fake_client(self):
        preflight = _preflight()
        path = _write_preflight_tmp(preflight)
        client = FakeClient(_valid_results(preflight))
        out_root = tempfile.mkdtemp(prefix="adapter-test-armed-")
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}), \
                patch.object(pbr, "LIVE_CLIENT_FACTORY", lambda: client), \
                patch.object(pbr, "RUN_OUTPUT_ROOT", out_root):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 0)
        run_dir = os.path.join(out_root, preflight["run_id"])
        envelope_path = os.path.join(run_dir, "validated-result-envelopes.json")
        self.assertTrue(os.path.isfile(envelope_path))
        with open(envelope_path, encoding="utf-8") as fh:
            payload = json.load(fh)
        self.assertEqual(payload["adapter"], "easyparser-live")
        self.assertEqual(payload["synthetic_fixture"], False)
        self.assertEqual(payload["envelope_count"], 20)
        envelopes = payload["envelopes"]
        self.assertEqual(len(envelopes), 20)
        self.assertEqual(sorted(e["asin"] for e in envelopes), sorted(_fake_asins()))
        self.assertEqual(len(client.calls), 20)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)


# ---------------------------------------------------------------------------
# Mandatory regression: shared-contract class identity
# ---------------------------------------------------------------------------

import proof_batch_contracts as contracts_mod


class TestSharedContractIdentity(unittest.TestCase):
    """Proof the runner and adapter share ONE ProviderAdapter / GuardError /
    BindingError / RunAbort regardless of import method (regression coverage
    items 1-3)."""

    def test_01_ordinary_import_identity_is_single_object(self):
        self.assertIs(pbr.ProviderAdapter, contracts_mod.ProviderAdapter)
        self.assertIs(adapter_mod.ProviderAdapter, contracts_mod.ProviderAdapter)
        self.assertIs(pbr.GuardError, contracts_mod.GuardError)
        self.assertIs(pbr.BindingError, contracts_mod.BindingError)
        self.assertIs(pbr.RunAbort, contracts_mod.RunAbort)

    def test_02_adapter_passes_strict_isinstance(self):
        # setUpModule sets the read-only arm gate PROOF_BATCH_LIVE_ARMED=1 in the
        # test environment, so an allow_live=True fake-client construction is
        # permitted and must satisfy the strict shared-contract isinstance.
        self.assertEqual(os.environ.get(adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV), "1")
        adapter = _adapter(FakeClient(default={}))
        self.assertIsInstance(adapter, pbr.ProviderAdapter)
        self.assertIsInstance(adapter, contracts_mod.ProviderAdapter)

    def _env(self, gate_on):
        env = dict(os.environ)
        if gate_on:
            env["SCANNER_LIVE_ALLOWED"] = "1"
        else:
            env.pop("SCANNER_LIVE_ALLOWED", None)
        return env

    def test_03_identity_stable_after_reload(self):
        # Reloading both modules must NOT create a second ProviderAdapter
        # class; proof_batch_contracts is the single source of truth. Run in a
        # subprocess so the reload does not pollute this test process.
        probe = os.path.join(tempfile.mkdtemp(prefix="adapter-test-reload-"), "reload_probe.py")
        with open(probe, "w", encoding="utf-8") as fh:
            fh.write(
                "import sys, os\n"
                "BACKEND = sys.argv[1]\n"
                "sys.path.insert(0, BACKEND)\n"
                "os.environ['PROOF_BATCH_LIVE_ARMED'] = '1'\n"
                "import proof_batch_run as pbr\n"
                "import proof_batch_easyparser_adapter as adapter_mod\n"
                "import proof_batch_contracts as contracts\n"
                "import importlib\n"
                "before = id(contracts.ProviderAdapter)\n"
                "importlib.reload(pbr)\n"
                "importlib.reload(adapter_mod)\n"
                "ok_stable = (id(contracts.ProviderAdapter) == before)\n"
                "ok_shared = (pbr.ProviderAdapter is contracts.ProviderAdapter) and (adapter_mod.ProviderAdapter is contracts.ProviderAdapter)\n"
                "fake = lambda asin: {'source': 'x', 'asin': asin, 'offers': [], 'credits_used': 5, 'data_gaps': []}\n"
                "a = adapter_mod.EasyparserLiveAdapter({'run_id': 'd', 'preflight_fingerprint': 'f' * 64, 'allow_live': True, 'client': fake, 'force_synthetic_label': True})\n"
                "ok_isinstance = isinstance(a, pbr.ProviderAdapter)\n"
                "print('STABLE=%s SHARED=%s ISINSTANCE=%s' % (ok_stable, ok_shared, ok_isinstance))\n"
                "sys.exit(0 if (ok_stable and ok_shared and ok_isinstance) else 1)\n"
            )
        env = self._env(False)
        env[adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV] = "1"
        proc = subprocess.run(
            [sys.executable, probe, _BACKEND_DIR],
            cwd=_BACKEND_DIR, env=env,
            capture_output=True, text=True, timeout=120,
        )
        output = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 0, output)
        self.assertIn("STABLE=True SHARED=True ISINSTANCE=True", output)

    def test_04_arming_control_not_activatable_by_env_or_cli(self):
        # The second external arm gate PROOF_BATCH_LIVE_ARMED is a separate,
        # non-secret runtime opt-in OFF by default. It cannot be flipped by
        # SCANNER_LIVE_ALLOWED, CLI flags, GET routes, or report paths.
        path = self._write_preflight()
        out = io.StringIO()
        with _without_arm_gate(), \
                patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}), \
                patch.object(pbr, "LIVE_CLIENT_FACTORY", lambda: _raising):
            self.assertNotIn(adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV, os.environ)
            with contextlib.redirect_stdout(out):
                rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)
        self.assertIn("easyparser-live adapter is not armed", out.getvalue())
        # Sanity: the SCANNER_LIVE_ALLOWED flag never leaked into the parent env.
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def _write_preflight(self):
        return _write_preflight_tmp(_preflight())


class TestRuntimeArmGate(unittest.TestCase):
    """Focused fixture-only coverage of the PROOF_BATCH_LIVE_ARMED gate.

    The second external, non-secret, read-only runtime opt-in must be OFF by
    default and only the explicit value "1" enables it. Real execution requires
    BOTH SCANNER_LIVE_ALLOWED=1 AND PROOF_BATCH_LIVE_ARMED=1 plus every runner
    guard. No test here makes a network/provider transport call.
    """

    def _write_preflight(self):
        return _write_preflight_tmp(_preflight())

    def test_gate_absent_refuses_real_construction(self):
        with _without_arm_gate():
            with self.assertRaises(pbr.GuardError) as ctx:
                _adapter(FakeClient(default={}))
        self.assertIn("not armed", str(ctx.exception))
        self.assertIn("no provider call was made", str(ctx.exception))

    def test_gate_non_one_values_stay_disabled(self):
        for bad in ("false", "0", "no", "FALSE", " 1", "true", ""):
            with patch.dict(os.environ, {adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV: bad}):
                with self.assertRaises(pbr.GuardError):
                    _adapter(FakeClient(default={}))

    def test_arm_set_but_live_gate_absent_refused(self):
        # Proof Batch arm set, but SCANNER_LIVE_ALLOWED missing -> the runner's
        # own live gate refuses before any adapter construction.
        path = self._write_preflight()
        with patch.dict(os.environ, {adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV: "1"}):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)

    def test_live_gate_set_but_arm_absent_refused(self):
        path = self._write_preflight()
        out = io.StringIO()
        with _without_arm_gate(), \
                patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1"}), \
                patch.object(pbr, "LIVE_CLIENT_FACTORY", lambda: _raising):
            with contextlib.redirect_stdout(out):
                rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 2)
        self.assertIn("not armed", out.getvalue())
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_both_gates_present_invalid_preflight_refused_before_client(self):
        bad = _preflight(asins=_fake_asins()[:19])
        bad_path = _write_preflight_tmp(bad)
        calls = []
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1",
                                     adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV: "1"}), \
                patch.object(pbr, "LIVE_CLIENT_FACTORY", lambda: calls.append("factory") or _raising):
            rc = pbr.main(_cli_args(bad_path))
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_both_gates_present_cap_invalid_refused_before_client(self):
        path = self._write_preflight()
        calls = []
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1",
                                     adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV: "1"}), \
                patch.object(pbr, "LIVE_CLIENT_FACTORY", lambda: calls.append("factory") or _raising):
            # Missing --max-credits -> _require_caps refuses before arming.
            rc = pbr.main(["run", "--live", "--preflight", path, "--max-requests", "20"])
        self.assertEqual(rc, 2)
        self.assertEqual(calls, [])

    def test_both_gates_present_fake_client_reaches_runner(self):
        preflight = _preflight()
        path = _write_preflight_tmp(preflight)
        client = FakeClient(_valid_results(preflight))
        out_root = tempfile.mkdtemp(prefix="adapter-test-armrun-")
        with patch.dict(os.environ, {"SCANNER_LIVE_ALLOWED": "1",
                                     adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV: "1"}), \
                patch.object(pbr, "LIVE_CLIENT_FACTORY", lambda: client), \
                patch.object(pbr, "RUN_OUTPUT_ROOT", out_root):
            rc = pbr.main(_cli_args(path))
        self.assertEqual(rc, 0)
        run_dir = os.path.join(out_root, preflight["run_id"])
        envelope_path = os.path.join(run_dir, "validated-result-envelopes.json")
        self.assertTrue(os.path.isfile(envelope_path))
        self.assertEqual(len(client.calls), 20)
        self.assertFalse("SCANNER_LIVE_ALLOWED" in os.environ)

    def test_dry_run_ignores_arm_gate_and_constructs_no_adapter(self):
        path = self._write_preflight()
        with patch.dict(os.environ, {adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV: "1"}), \
                patch.object(adapter_mod, "EasyparserLiveAdapter",
                             side_effect=AssertionError("dry-run must never construct the live adapter")):
            rc = pbr.main(["dry-run", "--preflight", path, "--max-requests", "20", "--max-credits", "100"])
        self.assertEqual(rc, 0)

    def test_direct_and_module_invocation_preserve_typed_error(self):
        # Fresh subprocess: arm gate is absent (production default), so a
        # SCANNER_LIVE_ALLOWED=1 invocation still refuses at the adapter gate
        # with a typed message and no traceback and no provider call.
        path = self._write_preflight()
        env = dict(os.environ)
        env.pop(adapter_mod.PROOF_BATCH_LIVE_ARMED_ENV, None)
        env["SCANNER_LIVE_ALLOWED"] = "1"
        for cmd in (["proof_batch_run.py"], ["-m", "proof_batch_run"]):
            proc = subprocess.run(
                [sys.executable] + cmd + ["run", "--live", "--preflight", path,
                 "--max-requests", "20", "--max-credits", "100"],
                cwd=_BACKEND_DIR, env=env, capture_output=True, text=True, timeout=120,
            )
            output = proc.stdout + proc.stderr
            self.assertEqual(proc.returncode, 2, output)
            self.assertIn("not armed", output)
            self.assertNotIn("Traceback", output)


if __name__ == "__main__":
    unittest.main()