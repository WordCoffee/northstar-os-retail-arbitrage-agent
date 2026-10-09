"""Adapter registry completeness (P1-02, A-26).

Every declared adapter must either load or be reported in
``registry.load_failures``. A missing dependency must never leave the registry
silently incomplete — that is indistinguishable from "not configured" and hides
a broken deployment.
"""

from __future__ import annotations

import importlib
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from adapters.base import registry  # noqa: E402
from adapters import registry as adapter_registry  # noqa: E402


def test_every_declared_adapter_is_registered_or_reported():
    registered = set(registry.list_adapters())
    failures = {f["adapter"] for f in adapter_registry.load_failures}
    missing = []
    for key, _module, _cls in adapter_registry._DECLARED:
        if key not in registered and key not in failures:
            missing.append(key)
    assert not missing, f"adapters neither loaded nor reported: {missing}"


def test_healthy_registry_has_no_load_failures():
    assert adapter_registry.load_failures == [], adapter_registry.load_failures


def test_a_broken_adapter_is_reported_not_dropped():
    """Break one adapter's import; it must appear in load_failures."""
    saved = {k: v for k, v in sys.modules.items() if k.startswith("adapters")}
    for key in list(sys.modules):
        if key.startswith("adapters"):
            sys.modules.pop(key, None)

    real_import_module = importlib.import_module

    def _fake_import(name, package=None):
        if name == ".scrape_do" or name.endswith("adapters.scrape_do"):
            raise ImportError("blocked for test")
        return real_import_module(name, package)

    with patch.object(importlib, "import_module", _fake_import):
        module = importlib.import_module("adapters.registry")
    try:
        failures = {f["adapter"]: f for f in module.load_failures}
        assert "scrape_do" in failures, failures
        assert "ImportError" in failures["scrape_do"]["error"]
    finally:
        for key in list(sys.modules):
            if key.startswith("adapters"):
                sys.modules.pop(key, None)
        sys.modules.update(saved)
        importlib.import_module("adapters.registry")


def test_registry_records_each_successful_registration():
    """Sanity: the registry actually holds the adapters it claims to."""
    registered = registry.list_adapters()
    assert "bright_data" in registered
    assert "amazon_api" in registered
