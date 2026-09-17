"""Tests for the free-tier provider registry and credit ledger.

Covers: provider lookup, task filtering, credit accounting, ledger
persistence, monthly resets, and key-availability metadata.
"""

import json

import pytest

from agents.golden_goose_finder.free_tier_registry import (
    ALL_TASKS,
    FREE_PROVIDERS,
    KEY_AVAILABLE,
    TASK_AMAZON_OFFERS,
    TASK_AMAZON_PRODUCT,
    TASK_AMAZON_SEARCH,
    TASK_COSTCO_SEARCH,
    TASK_GENERIC_SCRAPE,
    TASK_SAMS_SEARCH,
    FreeTierLedger,
    FreeTierProvider,
    get_provider,
    load_default_ledger,
    mark_key_available,
    providers_for_task,
)


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

class TestProviderRegistry:
    def test_providers_is_list_of_dataclass(self):
        assert isinstance(FREE_PROVIDERS, list)
        assert len(FREE_PROVIDERS) >= 15
        for p in FREE_PROVIDERS:
            assert isinstance(p, FreeTierProvider)

    def test_get_provider_found(self):
        p = get_provider("bright_data_web_unlocker")
        assert p is not None
        assert p.id == "bright_data_web_unlocker"
        assert "Bright Data" in p.name

    def test_get_provider_missing(self):
        assert get_provider("nonexistent_provider_xyz") is None

    def test_providers_for_task_costco_search(self):
        providers = providers_for_task(TASK_COSTCO_SEARCH)
        ids = [p.id for p in providers]
        assert "openwebninja_free" in ids
        assert "bright_data_web_unlocker" in ids

    def test_providers_for_task_sams_search(self):
        providers = providers_for_task(TASK_SAMS_SEARCH)
        ids = [p.id for p in providers]
        assert "apify_sams" in ids
        assert "outscraper" in ids

    def test_providers_for_task_amazon_search(self):
        providers = providers_for_task(TASK_AMAZON_SEARCH)
        assert len(providers) >= 5
        ids = [p.id for p in providers]
        assert "bright_data_web_unlocker" in ids
        assert "chocodata" in ids

    def test_providers_for_task_amazon_offers(self):
        providers = providers_for_task(TASK_AMAZON_OFFERS)
        ids = [p.id for p in providers]
        assert "easyparser" in ids
        assert "scrapebadger" in ids

    def test_providers_for_task_generic_scrape(self):
        providers = providers_for_task(TASK_GENERIC_SCRAPE)
        ids = [p.id for p in providers]
        assert "firecrawl" in ids
        assert "scrape_do" in ids

    def test_all_tasks_have_providers(self):
        for task in ALL_TASKS:
            providers = providers_for_task(task)
            assert len(providers) >= 1, f"no providers for {task}"

    def test_cost_for_returns_float(self):
        p = get_provider("bright_data_web_unlocker")
        assert p.cost_for(TASK_COSTCO_SEARCH) == 1.0
        assert p.cost_for("nonexistent_task") is None

    def test_quota_model_monthly(self):
        p = get_provider("openwebninja_free")
        assert p.quota_model == "monthly"
        assert p.monthly_quota == 100

    def test_quota_model_one_time(self):
        p = get_provider("chocodata")
        assert p.quota_model == "one_time"
        assert p.one_time_credits == 1000

    def test_start_credits_monthly(self):
        p = get_provider("openwebninja_free")
        assert p.start_credits == 100

    def test_start_credits_one_time(self):
        p = get_provider("chocodata")
        assert p.start_credits == 1000


# ---------------------------------------------------------------------------
# Key availability metadata
# ---------------------------------------------------------------------------

class TestKeyAvailability:
    def test_known_keys_are_true(self):
        for pid in ("openwebninja_free", "bright_data_web_unlocker",
                     "firecrawl", "scrape_do", "chocodata",
                     "scavio", "easyparser", "rapidapi_pool", "canopy"):
            assert KEY_AVAILABLE.get(pid) is True, pid

    def test_new_signups_are_false(self):
        for pid in ("scrapingdog", "scrapingbee", "scrapebadger",
                     "flybyapis", "amazonscraperapi", "apiclaw",
                     "apify_sams", "outscraper"):
            assert KEY_AVAILABLE.get(pid) is False, pid

    def test_mark_key_available(self):
        original = KEY_AVAILABLE.get("scrapingdog")
        mark_key_available("scrapingdog", True)
        p = get_provider("scrapingdog")
        assert p.has_key is True
        mark_key_available("scrapingdog", original or False)

    def test_mark_unknown_provider_no_crash(self):
        mark_key_available("nonexistent_xyz", True)  # no-op, no crash


# ---------------------------------------------------------------------------
# Credit ledger
# ---------------------------------------------------------------------------

class TestFreeTierLedger:
    def test_initialization(self, tmp_path):
        ledger = FreeTierLedger(path=str(tmp_path / "test_ledger.json"))
        ledger.load()
        assert ledger.month == FreeTierLedger.current_month()
        assert ledger.remaining_credits("openwebninja_free") == 100.0
        assert ledger.remaining_credits("chocodata") == 1000.0

    def test_debit_and_remaining(self, tmp_path):
        path = tmp_path / "test_ledger.json"
        ledger = FreeTierLedger(path=str(path))
        ledger.load()
        new_bal = ledger.debit("openwebninja_free", 5.0)
        assert new_bal == 95.0
        assert ledger.remaining_credits("openwebninja_free") == 95.0
        assert ledger.used_this_month["openwebninja_free"] == 5.0

    def test_can_debit(self, tmp_path):
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()
        assert ledger.can_debit("openwebninja_free", 10.0) is True
        assert ledger.can_debit("openwebninja_free", 200.0) is False

    def test_debit_to_zero(self, tmp_path):
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()
        ledger.debit("openwebninja_free", 100.0)
        assert ledger.remaining_credits("openwebninja_free") == 0.0
        assert ledger.can_debit("openwebninja_free", 1.0) is False

    def test_restore_credits(self, tmp_path):
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()
        ledger.debit("openwebninja_free", 50.0)
        assert ledger.remaining_credits("openwebninja_free") == 50.0
        ledger.restore("openwebninja_free", 50.0)
        assert ledger.remaining_credits("openwebninja_free") == 100.0

    def test_persistence_round_trip(self, tmp_path):
        path = tmp_path / "ledger.json"
        ledger1 = FreeTierLedger(path=str(path))
        ledger1.load()
        ledger1.debit("openwebninja_free", 10.0)
        ledger1.save()

        ledger2 = FreeTierLedger(path=str(path))
        ledger2.load()
        assert ledger2.remaining_credits("openwebninja_free") == 90.0

    def test_monthly_reset(self, tmp_path):
        path = tmp_path / "ledger.json"
        ledger = FreeTierLedger(path=str(path))
        ledger.load()
        ledger.debit("openwebninja_free", 30.0)
        # Simulate new month by changing the stored month
        ledger.month = "2020-01"
        ledger.save()
        # Reload triggers monthly reset
        ledger2 = FreeTierLedger(path=str(path))
        ledger2.load()
        assert ledger2.remaining_credits("openwebninja_free") == 100.0  # reset to monthly quota

    def test_one_time_pool_not_reset(self, tmp_path):
        path = tmp_path / "ledger.json"
        ledger = FreeTierLedger(path=str(path))
        ledger.load()
        ledger.debit("chocodata", 200.0)
        assert ledger.remaining_credits("chocodata") == 800.0
        ledger.month = "2020-01"
        ledger.save()
        ledger2 = FreeTierLedger(path=str(path))
        ledger2.load()
        # One-time pool doesn't reset on month change
        assert ledger2.remaining_credits("chocodata") == 800.0

    def test_unknown_provider_starts_at_zero(self, tmp_path):
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()
        assert ledger.remaining_credits("nonexistent_xyz") == 0.0

    def test_summary(self, tmp_path):
        ledger = FreeTierLedger(path=str(tmp_path / "t.json"))
        ledger.load()
        s = ledger.summary()
        assert "month" in s
        assert "remaining" in s
        assert s["providers"] >= 15

    def test_missing_file_initializes(self, tmp_path):
        ledger = FreeTierLedger(path=str(tmp_path / "nope.json"))
        ledger.load()
        assert ledger.month == FreeTierLedger.current_month()
        assert ledger.remaining_credits("openwebninja_free") == 100.0

    def test_corrupt_file_initializes(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{")
        ledger = FreeTierLedger(path=str(path))
        ledger.load()
        assert ledger.remaining_credits("openwebninja_free") == 100.0

    def test_default_ledger_loads(self):
        ledger = load_default_ledger()
        assert ledger.month == FreeTierLedger.current_month()
