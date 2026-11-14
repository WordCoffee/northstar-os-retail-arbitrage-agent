"""Contract check: the rules, and one real in-process run over all 29 services.

The contract is only meaningful if it can fail. These tests pin the parts that
would otherwise drift silently:

* external (paid-model) actions are never selected, so a contract run cannot
  spend credits;
* a stub payload fails and a measured one passes;
* no-action services report `no_primary_action` (a gap, not a pass);
* a real run against a fresh TestClient proves the writes that can persist do
  persist, and names the ones that cannot.

The run uses a throwaway SQLite store and the loopback dev identity; nothing
here touches Amazon or a paid provider.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import contract_check as cc  # noqa: E402


def _service(sid: str) -> dict:
    for service in cc.registry_services():
        if service["id"] == sid:
            return service
    raise AssertionError(f"no registry service {sid!r}")


def test_registry_has_the_28_services():
    services = cc.registry_services()
    assert len(services) == 28
    assert len({s["id"] for s in services}) == 28


def test_a_partial_probe_does_not_overwrite_the_published_artefact(tmp_path, monkeypatch):
    """Measured 2026-11-14: `--service adpilot` rewrote the shared file with one row.

    The published contract is the whole registry; a one-service measurement with no explicit
    --out must leave it alone.
    """
    shared = tmp_path / "service_contracts.json"
    shared.write_text(json.dumps({"services": [{"id": "keep-me"}]}), encoding="utf-8")
    monkeypatch.setattr(cc, "OUT", shared)
    monkeypatch.setattr(cc, "run", lambda **kwargs: {
        "services": [{"id": "adpilot", "verdict": "pass", "reason": ""}],
        "count": 1, "passed": 1, "persisted": 1, "gaps": 0,
    })

    assert cc.main(["--service", "adpilot", "--json"]) == 0
    kept = json.loads(shared.read_text(encoding="utf-8"))
    assert kept["services"] == [{"id": "keep-me"}]

    assert cc.main(["--json"]) == 0
    written = json.loads(shared.read_text(encoding="utf-8"))
    assert written["services"][0]["id"] == "adpilot"



    for sid in ("offerchisel", "towncrier", "autothink", "adpilot", "listingforge"):
        primary, skipped, _ = cc.select_primary(_service(sid))
        if primary is not None:
            assert primary.get("effect") != "external", sid
            assert str(primary.get("endpoint")) in cc.REQUESTS
        if sid in ("offerchisel", "towncrier"):
            assert primary is None
            assert skipped and all(s["effect"] == "external" for s in skipped)


def test_primary_is_highest_effect_provable_action():
    # jobs has reads and writes; the write must win.
    primary, _, _ = cc.select_primary(_service("jobs"))
    assert primary["effect"] == "write"
    assert primary["endpoint"] == "/api/v1/foundation/jobs-durable"

    # design-studio: upload is the only write, so it must win over the reads.
    primary, _, _ = cc.select_primary(_service("design-studio"))
    assert primary["endpoint"] == "/api/design-studio/assets/upload"

    # account is all reads: registry order decides.
    primary, _, _ = cc.select_primary(_service("account"))
    assert primary["endpoint"] == "/api/v1/foundation/entitlements"


def test_product_finder_contract_comes_from_the_registry_not_an_override():
    """The override existed only while the registry entry had no actions.

    `fix-product-finder-wiring` added the finder read to `ty/services.json`, so the override was
    removed rather than left shadowing the source of truth.
    """
    primary, _, _ = cc.select_primary(_service("product-finder"))
    assert primary["endpoint"] == "/api/products/finder"
    assert primary["effect"] == "read"
    assert "product-finder" not in cc.OVERRIDES
    declared = [a["endpoint"] for a in _service("product-finder")["actions"]]
    assert "/api/products/finder" in declared


def test_services_without_actions_are_gaps_not_passes():
    for sid in ("beta", "beta-support", "socialpulse"):
        primary, _, reason = cc.select_primary(_service(sid))
        assert primary is None
        assert "no actions" in reason


@pytest.mark.parametrize("payload,expected", [
    ({}, False),
    ({"kind": "x", "count": 0, "items": []}, False),
    ({"contract": "bff/v1", "status": "ok", "data": {}}, False),
    ({"total": 470, "pass": 245, "fail": 20}, True),
    ({"evaluated": [{"asin": "B0TEST00001"}]}, True),
    ({"items": [], "summary": {"products": 0, "source_avg_price": None}}, False),
])
def test_substance_separates_stubs_from_measurements(payload, expected):
    ok, _ = cc.substance(cc.unwrap(payload))
    assert ok is expected


def test_end_to_end_contract_run_on_a_fresh_backend(tmp_path, monkeypatch):
    # The product-finder reads the local search cache. `test_network_guard` points that cache at an
    # empty temp file on purpose, so this test used to pass only when an earlier module happened to
    # leave candidates in it — an order dependence, not a measurement. It seeds its own.
    cache = tmp_path / "scanner-search-cache.json"
    cache.write_text(json.dumps({
        "schema_version": 1,
        "source": "contract-test",
        "fetched_at": "2026-11-09T00:00:00+00:00",
        "candidate_count": 1,
        "products": [{"asin": "B0TEST00001", "name": "Contract Test Candidate",
                      "price": 10.0, "product_url": "https://example.invalid/dp/B0TEST00001"}],
    }), encoding="utf-8")
    monkeypatch.setenv("SCANNER_SEARCH_CACHE_PATH", str(cache))

    result = cc.run(mode="in_process", db_dir=tmp_path)

    assert result["count"] == 28
    assert len(result["services"]) == 28
    rows = {row["id"]: row for row in result["services"]}
    assert set(rows) == {s["id"] for s in cc.registry_services()}

    # The action the whole task exists to wire: product-finder must pass now.
    assert rows["product-finder"]["verdict"] == "pass"
    assert rows["product-finder"]["endpoint"] == "/api/products/finder"
    assert "row(s) under 'evaluated'" in rows["product-finder"]["evidence"]

    # Writes must be read back through a different endpoint.
    for sid in ("jobs", "keywords", "design-studio", "listingforge", "adpilot"):
        assert rows[sid]["verdict"] == "pass", rows[sid]
        assert rows[sid]["persisted"] is True, rows[sid]

    # Honest refusals and gaps.
    assert rows["beta-signup"]["verdict"] == "permission_denied"
    assert "signup" in rows["beta-signup"]["reason"].lower()
    assert rows["beta-ops"]["verdict"] == "permission_denied"
    assert rows["offerchisel"]["verdict"] == "fail"
    assert rows["towncrier"]["verdict"] == "fail"
    for sid in ("beta", "beta-support", "socialpulse"):
        assert rows[sid]["verdict"] == "no_primary_action"

    # Every row states a verdict and, when not passing, a reason.
    for row in result["services"]:
        assert row["verdict"] in {
            "pass", "fail", "no_primary_action", "endpoint_missing",
            "permission_denied", "http_error", "empty_payload",
            "persist_failed", "persist_unproven",
        }
        if row["verdict"] != "pass":
            assert row["reason"], row

    path = cc.write(result, tmp_path / "contracts.json")
    assert path.is_file()
