import importlib
import os
import tempfile
import test_network_guard  # noqa: F401  (blocks real network calls)
import unittest
from unittest import mock
import costco_client


class GetCostcoPriceTests(unittest.TestCase):
    def setUp(self):
        self.csv_path = os.path.join(tempfile.gettempdir(), "costco-test.csv")
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            f.write(
                "item_name,costco_cost\n"
                "Kirkland Test Item,12.34\n"
            )

    def tearDown(self):
        if os.path.exists(self.csv_path):
            os.remove(self.csv_path)

    def test_valid_match(self):
        with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
            result = costco_client.get_costco_price("Kirkland Test Item")
        self.assertEqual(result["item_name"], "Kirkland Test Item")
        self.assertEqual(result["costco_cost"], 12.34)
        self.assertNotIn("weight_lbs", result)

    def test_identical_bare_name_is_high_confidence(self):
        """A bare name with no weight/pack/UPC evidence on either side but
        a strong (identical) normalized title identity is High Confidence —
        the title itself is the equivalence evidence, and the cost is a
        research cost (never invoice-confirmed)."""
        with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
            result = costco_client.get_costco_price("Kirkland Test Item")
        self.assertEqual(result["match_quality"], "high_confidence")
        self.assertEqual(result["costco_cost_basis"], "estimated")
        self.assertIn("Strong normalized title identity", result["match_reason"])
        self.assertEqual(result["source"], "csv")

    def test_csv_rows_are_estimated_basis_never_invoice(self):
        with mock.patch.object(costco_client, "COSTCO_CSV_PATH", self.csv_path):
            result = costco_client.get_costco_price("Kirkland Test Item")
        self.assertEqual(result["costco_cost_basis"], "estimated")
        self.assertNotEqual(result["costco_cost_basis"], "invoice_confirmed")

    def test_fingerprint_exact_basis_stays_estimated(self):
        """An exact fingerprint match (weight/pack + formula equal on both
        sides) keeps the estimated basis and is purchase-eligible."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write('item_name,costco_cost\n"Kirkland Signature Dental Chews, 72 ct",33.65\n')
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                result = costco_client.get_costco_price("Kirkland Signature Dental Chews 72 ct")
        self.assertEqual(result["match_quality"], "exact")
        self.assertEqual(result["costco_cost_basis"], "estimated")

    def test_missing_path_skips_lookup(self):
        with mock.patch.object(costco_client, "COSTCO_CSV_PATH", ""):
            result = costco_client.get_costco_price("Kirkland Test Item")
        self.assertIsNone(result)

    def test_import_without_path_does_not_crash(self):
        with mock.patch.dict("os.environ", {"COSTCO_CSV_PATH": ""}):
            with mock.patch("costco_client.load_dotenv"):
                reloaded = importlib.reload(costco_client)
                result = reloaded.get_costco_price("Kirkland Test Item")
        self.assertIsNotNone(reloaded)
        self.assertIsNone(result)
        importlib.reload(costco_client)

    def test_exact_match_wins_over_fuzzy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("item_name,costco_cost\n")
                f.write("Kirkland Olive Oil,6.00\n")
                f.write("Kirkland Organic Olive Oil,8.00\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                result = costco_client.get_costco_price("Kirkland Organic Olive Oil")
        self.assertEqual(result["item_name"], "Kirkland Organic Olive Oil")
        self.assertEqual(result["costco_cost"], 8.00)

    def test_normalized_exact_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("item_name,costco_cost\n")
                f.write("Kirkland   Organic  Olive Oil,8.00\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                result = costco_client.get_costco_price("  kirkland organic olive oil  ")
        self.assertEqual(result["costco_cost"], 8.00)

    def test_fuzzy_fallback_without_exact_match(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("item_name,costco_cost\n")
                f.write("Kirkland Olive Oil,6.00\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                result = costco_client.get_costco_price("Kirkland Organic Olive Oil")
        self.assertEqual(result["costco_cost"], 6.00)

    def test_below_threshold_fuzzy_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("item_name,costco_cost\n")
                f.write("Bananas,2.00\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                result = costco_client.get_costco_price("Kirkland Organic Olive Oil")
        self.assertIsNone(result)

    def test_duplicate_exact_matches_return_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("item_name,costco_cost\n")
                f.write("Kirkland Test Item,5.00\n")
                f.write("  kirkland test item  ,7.00\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                result = costco_client.get_costco_price("Kirkland Test Item")
        self.assertIsNone(result)

    def test_legacy_three_column_file_still_loads(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("item_name,costco_cost,weight_lbs\n")
                f.write("Kirkland Test Item,5.00,1.0\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                result = costco_client.get_costco_price("Kirkland Test Item")
        self.assertEqual(result["costco_cost"], 5.00)
        self.assertNotIn("weight_lbs", result)

    def test_relative_path_resolves_against_project_root(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(
                os.path.join(tmpdir, "catalog.csv"), "w", newline="", encoding="utf-8"
            ) as f:
                f.write("item_name,costco_cost\nKirkland Test Item,5.00\n")
            with mock.patch.object(costco_client, "_BACKEND_DIR", os.path.join(tmpdir, "Northstar_backend")):
                with mock.patch.object(costco_client, "COSTCO_CSV_PATH", "catalog.csv"):
                    result = costco_client.get_costco_price("Kirkland Test Item")
        self.assertEqual(result["costco_cost"], 5.00)


class ProductEquivalenceTests(unittest.TestCase):
    """Purchase-analysis fingerprint gate. Exact match is required for
    estimated economics; anything else is candidate-only or blocked."""

    def eq(self, amazon, costco):
        return costco_client.product_equivalence(amazon, costco)

    def test_exact_when_weight_pack_and_formula_match(self):
        r = self.eq(
            "Kirkland Signature Dental Chews 72 ct",
            "Kirkland Signature Dental Chews, 72 ct",
        )
        self.assertEqual(r["match_quality"], "exact")
        self.assertIsNone(r["match_reason"])

    def test_exact_normalizes_units_and_plurals(self):
        r = self.eq(
            "Kirkland Signature Olive Oil 2 Liter",
            "Kirkland Signature Olive Oil, 2 liters",
        )
        self.assertEqual(r["match_quality"], "exact")

    def test_exact_normalizes_weight_units(self):
        r = self.eq(
            "Kirkland Signature Ground Coffee, 2.5 lbs",
            "Kirkland Signature Ground Coffee, 2.5 lb",
        )
        self.assertEqual(r["match_quality"], "exact")

    def test_exact_tolerates_marketing_packaging_descriptors(self):
        r = self.eq(
            "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Individually Wrapped Rolls",
            "Kirkland Signature Paper Towels, 2-Ply, 160 Sheets, 12 Individually Wrapped Rolls",
        )
        self.assertEqual(r["match_quality"], "exact")

    def test_flavor_swap_is_mismatch(self):
        r = self.eq(
            "Kirkland Signature Adult Formula Chicken, Rice and Vegetable Dog Food 40 lb.",
            "Kirkland Signature Adult Formula Lamb, Rice and Vegetable Dog Food, 25 lbs",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("weight", r["match_reason"])
        self.assertIn("flavor", r["match_reason"])

    def test_weight_mismatch_same_formula(self):
        r = self.eq(
            "Kirkland Signature Nature's Domain Dog Food, Beef & Sweet Potato, 35 lb",
            "Kirkland Signature Nature's Domain Dog Food, Beef & Sweet Potato, 25 lbs",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("weight", r["match_reason"])
        self.assertNotIn("flavor", r["match_reason"])

    def test_pack_count_mismatch(self):
        r = self.eq(
            "Kirkland Signature Dental Chews (4)",
            "Kirkland Signature Dental Chews, 72 ct",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("Pack/count", r["match_reason"])

    def test_upc_conflict_is_mismatch(self):
        r = self.eq(
            "Kirkland Signature Batteries, 48 ct upc 096619282548",
            "Kirkland Signature AA Batteries, 48 ct upc 096619282547",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("UPC", r["match_reason"])

    def test_shared_upc_arg_is_exact(self):
        r = costco_client.product_equivalence(
            "Kirkland Signature Batteries, 48 ct",
            "Kirkland Signature AA Batteries, 48 ct",
            amazon_upc="096619282548",
            costco_upc="096619282548",
        )
        self.assertEqual(r["match_quality"], "exact")
        self.assertIsNone(r["match_reason"])

    def test_differing_upc_args_is_mismatch(self):
        r = costco_client.product_equivalence(
            "Kirkland Signature Batteries, 48 ct",
            "Kirkland Signature AA Batteries, 48 ct",
            amazon_upc="096619282548",
            costco_upc="096619282547",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("UPC", r["match_reason"])

    def test_one_sided_upc_arg_ignored(self):
        r = costco_client.product_equivalence(
            "Kirkland Signature Dental Chews 72 ct",
            "Kirkland Signature Dental Chews, 72 ct",
            amazon_upc="096619282548",
        )
        self.assertEqual(r["match_quality"], "exact")

    def test_high_confidence_when_one_side_lacks_evidence_strong_title(self):
        """One-sided evidence with a strong normalized title identity is
        High Confidence (>= HIGH_CONFIDENCE_TITLE_RATIO), not Candidate."""
        r = self.eq(
            "Kirkland Signature Dental Chews",
            "Kirkland Signature Dental Chews, 72 ct",
        )
        self.assertEqual(r["match_quality"], "high_confidence")
        self.assertIn("Strong normalized title identity", r["match_reason"])
        self.assertIn("no weight/pack/UPC evidence", r["match_reason"])

    def test_candidate_when_weak_title_and_one_side_evidence(self):
        """One-sided evidence with a weak title identity stays Candidate —
        the title alone is not enough to bridge the missing fingerprint."""
        r = self.eq(
            "Kirkland Signature Dental Chews",
            "Dental Chews Signature Kirkland 72 ct",
        )
        self.assertEqual(r["match_quality"], "candidate")
        self.assertIn("cannot be confirmed", r["match_reason"])

    def test_unknown_when_neither_side_has_evidence_and_names_differ(self):
        """Distinct bare names with no fingerprint evidence on either side
        and a weak title identity stay Unknown — the identity cannot be
        established either way."""
        r = self.eq("Kirkland Test Item", "Kirkland Item Test")
        self.assertEqual(r["match_quality"], "unknown")

    def test_strong_title_never_overrides_known_conflict(self):
        """Title similarity never overrides a known fingerprint conflict:
        a different pack count is still a Mismatch, not High Confidence."""
        r = self.eq(
            "Kirkland Signature Dental Chews 72 ct",
            "Kirkland Signature Dental Chews 4 ct",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("Pack/count", r["match_reason"])

    def test_core_conflict_even_with_matching_weight(self):
        """Same weight but a different formula is still a mismatch, not a
        candidate — the difference is known, not unknown."""
        r = self.eq(
            "Kirkland Signature Vitamins 40 oz",
            "Kirkland Signature Chocolates 40 oz",
        )
        self.assertEqual(r["match_quality"], "mismatch")

    def test_cross_dimension_weight_vs_count_is_mismatch(self):
        """Weight/volume-only evidence on one side vs count/pack-only on the
        other is a known incompatible dimension: a 40 lb item and a 72 ct
        item can never be high_confidence or exact on title strength."""
        r = self.eq(
            "Kirkland Signature Adult Dog Food Chicken 40 lb",
            "Kirkland Signature Adult Dog Food Chicken 72 ct",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("Unit dimension differs", r["match_reason"])
        self.assertNotIn("high_confidence", r["match_quality"])

    def test_cross_dimension_mirror_direction_is_mismatch(self):
        r = self.eq(
            "Kirkland Signature Adult Dog Food Chicken 72 ct",
            "Kirkland Signature Adult Dog Food Chicken 40 lbs",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("Unit dimension differs", r["match_reason"])

    def test_differing_upc_args_same_title_is_mismatch(self):
        """Same title with conflicting UPCs is a known conflict even when
        no core-token difference exists."""
        r = costco_client.product_equivalence(
            "Kirkland Signature Batteries 48 ct",
            "Kirkland Signature Batteries 48 ct",
            amazon_upc="096619282548",
            costco_upc="096619282547",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("UPC", r["match_reason"])

    def test_flavor_variant_conflict_same_weight_is_mismatch(self):
        """A clean variant/flavor difference with identical weight evidence
        is still a mismatch — never high_confidence."""
        r = self.eq(
            "Kirkland Signature Adult Dog Food Chicken 40 lb",
            "Kirkland Signature Adult Dog Food Lamb 40 lb",
        )
        self.assertEqual(r["match_quality"], "mismatch")
        self.assertIn("Formula/flavor", r["match_reason"])


class CatalogStateTests(unittest.TestCase):
    def test_missing_when_path_unset(self):
        with mock.patch.object(costco_client, "COSTCO_CSV_PATH", ""):
            self.assertEqual(costco_client.catalog_state(), "missing")

    def test_missing_when_file_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", "nope.csv"):
                with mock.patch.object(costco_client, "_BACKEND_DIR", tmpdir):
                    self.assertEqual(costco_client.catalog_state(), "missing")

    def test_empty_when_header_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("item_name,costco_cost\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                self.assertEqual(costco_client.catalog_state(), "empty")

    def test_invalid_header(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("title,price\nKirkland Item,5.00\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                self.assertEqual(costco_client.catalog_state(), "invalid")

    def test_ready_with_valid_row(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("item_name,costco_cost\nKirkland Item,5.00\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                self.assertEqual(costco_client.catalog_state(), "ready")

    def test_empty_when_only_zero_costs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "catalog.csv")
            with open(path, "w", newline="", encoding="utf-8") as f:
                f.write("item_name,costco_cost\nKirkland Item,0.00\n")
            with mock.patch.object(costco_client, "COSTCO_CSV_PATH", path):
                self.assertEqual(costco_client.catalog_state(), "empty")


if __name__ == "__main__":
    unittest.main()
