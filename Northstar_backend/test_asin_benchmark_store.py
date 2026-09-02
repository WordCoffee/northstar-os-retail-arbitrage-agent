"""Offline tests for the ASIN benchmark repository (asin_benchmark_store.py).

Covers: CSV parsing, ASIN string normalization, price/review/BSR parsing,
Prime/FBA raw + normalized values, duplicate/conflict preservation,
unknown-never-zero, canonical rules, provenance. Zero provider calls.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

import asin_benchmark_store as store

FILE_A = store.FILE_A
FILE_B = store.FILE_B

HEADER_A = "# (BSR-proxy rank),Product,ASIN,Reviews,Price,Prime/FBA"
HEADER_B = "Rank,Product,ASIN,Reviews,Price,BSR"

ROW_A1 = '1,"Aller-Flo Fluticasone (Pack of 5)",B01H40O42I,"11,114","$26.74",Yes'
ROW_A2 = '11,"Stool Softener 100mg (400ct, alt listing)",B00N54AJZE,"1,665","$12.69","No (Amazon-shipped, non-Prime badge)"'
ROW_A3 = '12,"Sleep Aid Doxylamine (96ct)",B002L4M4M0,"6,270","$7.93",No'
ROW_A4 = '13,"Unknown Price Item",B0TEST0001,n/a,"$n/a",Maybe'
ROW_A5 = '14,"Pack of 2 (400ct)",B0TEST0002,"1,234","$0.00",Yes'
ROW_B1 = '1,"Aller-Flo (Pack of 5)",B01H40O42I,"11,114","$26.74","Not listed on page"'
ROW_B2 = '11,"Stool Softener 100mg (alt)",B00N54AJZE,"1,665","$12.69","#19,009 in Laxativesamazon"'
ROW_B3 = '12,"Sleep Aid Doxylamine (96ct)",B002L4M4M0,"6,270","$7.93","#14,653 in Health & Householdamazon; #24 in OTC Sleep Aidsamazon"'


def _write_csvs(tmp: str) -> None:
    with open(os.path.join(tmp, FILE_A), "w", encoding="utf-8") as fh:
        fh.write(HEADER_A + "\n")
        fh.write("\n".join([ROW_A1, ROW_A2, ROW_A3, ROW_A4, ROW_A5]) + "\n")
    with open(os.path.join(tmp, FILE_B), "w", encoding="utf-8") as fh:
        fh.write(HEADER_B + "\n")
        fh.write("\n".join([ROW_B1, ROW_B2, ROW_B3]) + "\n")


def _seed_raw_dir(tmp_root: str) -> None:
    """Write the fixture CSVs into the store's raw dir (BENCHMARK_RAW_DIR)."""
    _write_csvs(store.raw_dir())


class TempStoreTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._raw = os.path.join(self._tmp.name, "raw")
        self._reference_path = os.path.join(self._tmp.name, "asin_benchmark_reference.json")
        self._manifest_path = os.path.join(self._tmp.name, "manifest.json")
        os.makedirs(self._raw, exist_ok=True)
        self._env = mock.patch.dict(
            os.environ,
            {
                "BENCHMARK_RAW_DIR": self._raw,
                "BENCHMARK_REFERENCE_PATH": self._reference_path,
                "BENCHMARK_MANIFEST_PATH": self._manifest_path,
                "BENCHMARK_IMPORT_DIR": self._tmp.name,
            },
        )
        self._env.start()
        self.addCleanup(self._env.stop)
        self.addCleanup(self._tmp.cleanup)

    def _build(self):
        _seed_raw_dir(self._tmp.name)
        return store.build_store()


class ParsingTests(TempStoreTestCase):
    def test_price_parsing(self):
        self.assertEqual(store.parse_price("$26.74"), 26.74)
        self.assertEqual(store.parse_price("12.75"), 12.75)
        self.assertEqual(store.parse_price(""), None)
        self.assertEqual(store.parse_price(None), None)
        self.assertEqual(store.parse_price("n/a"), None)
        self.assertEqual(store.parse_price("not listed"), None)
        self.assertIsNone(store.parse_price("free-ish"))

    def test_int_parsing(self):
        self.assertEqual(store.parse_int("11,114"), 11114)
        self.assertEqual(store.parse_int("18"), 18)
        self.assertIsNone(store.parse_int("n/a"))
        self.assertIsNone(store.parse_int(""))
        self.assertIsNone(store.parse_int(None))
        self.assertIsNone(store.parse_int("12.5"))

    def test_prime_fba_raw_and_normalized(self):
        parsed = store.parse_prime_fba("Yes")
        self.assertEqual(parsed, {"raw": "Yes", "state": "yes", "note": None})
        parsed = store.parse_prime_fba("No")
        self.assertEqual(parsed["state"], "no")
        parsed = store.parse_prime_fba("No (Amazon-shipped, non-Prime badge)")
        self.assertEqual(parsed["state"], "no")
        self.assertEqual(parsed["note"], "Amazon-shipped, non-Prime badge")
        parsed = store.parse_prime_fba("Maybe")
        self.assertEqual(parsed["state"], "unknown")
        self.assertIsNone(store.parse_prime_fba(None)["raw"])

    def test_bsr_parsing_strips_amazon_noise(self):
        parsed = store.parse_bsr("#14,653 in Health & Householdamazon; #24 in OTC Sleep Aidsamazon")
        self.assertEqual(parsed["rank_number"], 14653)
        self.assertEqual(parsed["category"], "Health & Household")
        parsed = store.parse_bsr("Not listed on page")
        self.assertIsNone(parsed["rank_number"])
        self.assertIsNone(parsed["category"])
        self.assertEqual(parsed["raw"], "Not listed on page")

    def test_normalize_title(self):
        self.assertEqual(store.normalize_title("  Stool Softener 100mg (400ct)  "), "stool softener 100mg 400ct")
        self.assertIsNone(store.normalize_title(None))

    def test_pack_tokens(self):
        tokens = store.pack_tokens("Sleep Aid Doxylamine (2pk/192ct)")
        self.assertIn(("pack", 2), tokens)
        self.assertIn(("count", 192), tokens)
        self.assertEqual(store.pack_tokens(None), [])


class BuildStoreTests(TempStoreTestCase):
    def test_import_copies_source_files(self):
        _write_csvs(self._tmp.name)
        copied = store.import_raw_files(self._tmp.name)
        self.assertEqual(len(copied), 2)
        for entry in copied:
            self.assertIn(entry["action"], ("copied", "skipped_same_sha"))
            self.assertTrue(entry["sha256"])
            self.assertGreater(entry["bytes"], 0)
        rerun = store.import_raw_files(self._tmp.name)
        self.assertTrue(all(e["action"] == "skipped_same_sha" for e in rerun))

    def test_build_parses_all_rows_and_normalizes_asins(self):
        _write_csvs(self._tmp.name)
        result = self._build()
        self.assertEqual(result["schema_version"], store.BENCHMARK_SCHEMA_VERSION)
        observations = result["observations"]
        self.assertEqual(len(observations), 8)  # 5 file A + 3 file B
        asins = {o["asin"] for o in observations}
        self.assertEqual(asins, {"B01H40O42I", "B00N54AJZE", "B002L4M4M0", "B0TEST0001", "B0TEST0002"})
        for obs in observations:
            self.assertIsInstance(obs["asin"], str)
            self.assertTrue(store.ASIN_PATTERN.fullmatch(obs["asin"]))
            self.assertFalse(obs["malformed_asin"])

    def test_unknown_never_becomes_zero(self):
        _write_csvs(self._tmp.name)
        result = self._build()
        obs = next(o for o in result["observations"] if o["asin"] == "B0TEST0001")
        self.assertIsNone(obs["price"])
        self.assertIsNone(obs["reviews"])
        self.assertEqual(obs["prime_fba"], "unknown")
        self.assertNotEqual(obs["price"], 0)
        self.assertNotEqual(obs["reviews"], 0)

    def test_explicit_zero_price_is_kept(self):
        _write_csvs(self._tmp.name)
        result = self._build()
        obs = next(o for o in result["observations"] if o["asin"] == "B0TEST0002")
        self.assertEqual(obs["price"], 0.0)

    def test_duplicate_and_conflict_preservation(self):
        _write_csvs(self._tmp.name)
        result = self._build()
        canon = result["canonical"]
        self.assertEqual(canon["B01H40O42I"]["observation_count"], 2)
        self.assertEqual(canon["B01H40O42I"]["source_files"], [FILE_A, FILE_B])
        self.assertTrue(canon["B01H40O42I"]["title_conflict"])
        self.assertFalse(canon["B01H40O42I"]["price_conflict"])
        self.assertFalse(canon["B01H40O42I"]["review_conflict"])
        conflicts = {c["asin"]: c["field"] for c in result["conflicts"]}
        self.assertEqual(conflicts, {"B01H40O42I": "title", "B00N54AJZE": "title"})

    def test_canonical_rules_title_from_primary_file(self):
        _write_csvs(self._tmp.name)
        result = self._build()
        canon = result["canonical"]
        self.assertEqual(canon["B01H40O42I"]["title"], "Aller-Flo Fluticasone (Pack of 5)")
        self.assertEqual(canon["B00N54AJZE"]["title"], "Stool Softener 100mg (400ct, alt listing)")
        self.assertEqual(canon["B01H40O42I"]["price"], 26.74)
        self.assertEqual(canon["B01H40O42I"]["reviews"], 11114)
        self.assertEqual(canon["B01H40O42I"]["prime_fba"], "yes")
        self.assertIsNone(canon["B01H40O42I"]["bsr_rank_number"])
        self.assertEqual(canon["B002L4M4M0"]["bsr_rank_number"], 14653)
        self.assertEqual(canon["B002L4M4M0"]["bsr_category"], "Health & Household")

    def test_capture_timestamp_unknown_everywhere(self):
        _write_csvs(self._tmp.name)
        result = self._build()
        for obs in result["observations"]:
            self.assertIsNone(obs["capture_timestamp"])
            self.assertEqual(obs["capture_time_status"], "unknown")
        for row in result["canonical"].values():
            self.assertEqual(row["capture_time_status"], "unknown")
        self.assertTrue(all(f["capture_time_status"] == "unknown" for f in result["source_files"]))

    def test_write_and_load_roundtrip(self):
        _write_csvs(self._tmp.name)
        result = self._build()
        path = store.write_reference(result)
        self.assertTrue(os.path.isfile(path))
        loaded = store.load_reference(path)
        self.assertEqual(loaded["inventory"]["observation_count"], 8)
        self.assertEqual(loaded["inventory"]["unique_asin_count"], 5)
        self.assertEqual(loaded["loaded_from"], path)

    def test_manifest_written_with_required_fields(self):
        _seed_raw_dir(self._tmp.name)
        result = self._build()
        store.write_reference(result)
        self.assertTrue(os.path.isfile(self._manifest_path))
        import json as _json
        manifest = _json.load(open(self._manifest_path, encoding="utf-8"))
        self.assertEqual(len(manifest["entries"]), 2)
        for entry in manifest["entries"]:
            self.assertEqual(entry["source_type"], "user_provided_reference")
            self.assertIsNone(entry["capture_time"])
            self.assertEqual(entry["capture_time_status"], "unknown")
            self.assertIn("Not a live-feed source", entry["notes"])
            self.assertTrue(entry["sha256"])
            self.assertGreater(entry["bytes"], 0)
            self.assertIsNotNone(entry["imported_at"])

    def test_loader_empty_state_when_reference_absent(self):
        state = store.load_reference()
        self.assertEqual(state["inventory"]["observation_count"], 0)
        self.assertEqual(state["inventory"]["unique_asin_count"], 0)
        self.assertEqual(state["observations"], [])
        self.assertEqual(state["canonical"], {})
        self.assertIsNone(state["loaded_from"])

    def test_source_files_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            store.build_store()


class ProvenanceTests(TempStoreTestCase):
    def test_provenance_records_sha256_and_no_timestamp(self):
        _write_csvs(self._tmp.name)
        result = self._build()
        self.assertEqual(len(result["source_files"]), 2)
        for entry in result["source_files"]:
            self.assertTrue(entry["sha256"])
            self.assertIsNone(entry["capture_timestamp"])
            self.assertEqual(entry["capture_time_status"], "unknown")
        self.assertTrue(all(store.CANONICAL_RULES))


class ContainmentTests(TempStoreTestCase):
    def test_store_build_makes_zero_provider_calls(self):
        from unittest import mock as _mock
        import bright_data_client
        import scavio_client
        import amazon_search
        import offer_enrichment
        import canopy_client
        import easyparser_client
        import costco_api_client

        def _boom(*args, **kwargs):
            raise AssertionError("provider call made during offline benchmark build")

        patches = (
            _mock.patch.object(bright_data_client, "search_products", side_effect=_boom),
            _mock.patch.object(bright_data_client, "get_product_detail", side_effect=_boom),
            _mock.patch.object(scavio_client, "search_kirkland_products", side_effect=_boom),
            _mock.patch.object(amazon_search, "_search_brightdata", side_effect=_boom),
            _mock.patch.object(amazon_search, "_search_chocodata", side_effect=_boom),
            _mock.patch.object(offer_enrichment, "get_easyparser_offers", side_effect=_boom),
            _mock.patch.object(offer_enrichment, "get_offer_data", side_effect=_boom),
            _mock.patch.object(canopy_client.requests, "get", side_effect=_boom),
            _mock.patch.object(costco_api_client.requests, "get", side_effect=_boom),
            _mock.patch.object(easyparser_client.requests, "get", side_effect=_boom),
        )
        _write_csvs(self._tmp.name)
        with _mock.patch("asin_benchmark_store.json.dump", wraps=store.json.dump):
            for p in patches:
                p.start()
            try:
                result = self._build()
                self.assertEqual(result["inventory"]["observation_count"], 8)
            finally:
                for p in reversed(patches):
                    p.stop()

    def test_no_network_modules_imported(self):
        import benchmark_validation
        import asin_benchmark_store as abs_store
        for module_file in (abs_store.__file__, benchmark_validation.__file__):
            src = "".join(open(module_file, encoding="utf-8").readlines())
            self.assertNotIn("import requests", src)
            self.assertNotIn("import httpx", src)
            self.assertNotIn("urllib", src)


if __name__ == "__main__":
    unittest.main()
