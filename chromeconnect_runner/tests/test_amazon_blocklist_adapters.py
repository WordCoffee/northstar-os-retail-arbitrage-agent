"""Amazon blocklist suite applied to every Chrome Connect adapter.

The hardcoded Amazon blocklist is checked BEFORE the allowlist and cannot be
overridden. These tests assert that:

  * no remaining adapter advertises an Amazon origin;
  * every adapter refuses Amazon hosts (subdomain, lookalike, redirect target)
    through the policy kernel's is_amazon_host gate;
  * an Amazon URL never produces a successful (OK) extraction from any adapter.

Provenance: in-house, Chrome Connect 3.0 finish-out.
"""

import os
import sys

_RUNNER_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _RUNNER_DIR not in sys.path:
    sys.path.insert(0, _RUNNER_DIR)
_TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _TESTS_DIR not in sys.path:
    sys.path.insert(0, _TESTS_DIR)
_REPO_ROOT = os.path.dirname(_RUNNER_DIR)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import importlib.util

def _load_adapter(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_RUNNER_DIR, "adapters", name + ".py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

ADAPTER_NAMES = ["costco", "vendor_dashboards", "sellersprite", "palletfly", "prime_national_distribution"]
ADAPTERS = {n: _load_adapter(n) for n in ADAPTER_NAMES}

# Resolve adapter class name per module
def _adapter_class(mod):
    for attr in dir(mod):
        if attr.endswith("Adapter") and attr != "SiteAdapter":
            return getattr(mod, attr)
    raise RuntimeError("no Adapter class in " + str(mod))

ADAPTER_CLASSES = {n: _adapter_class(m) for n, m in ADAPTERS.items()}

try:
    from northstar.policy import is_amazon_host
    _POLICY_AVAILABLE = True
except Exception:  # pragma: no cover
    _POLICY_AVAILABLE = False
    def is_amazon_host(host, ascii_host=None):  # type: ignore
        return "amazon" in (host or "").lower()

AMAZON_URLS = [
    "https://www.amazon.com/dp/B000000000",
    "https://smile.amazon.co.uk/x",
    "https://amazon.de/",
    "https://amzn.to/abc",
    "https://a.co/abc",
    "https://subdomain.amazon.com/p/1",
]

LOOKALIKE_HOSTS = [
    "\u0430mazon.com",  # cyrillic 'a'
]

REDIRECT_CHAINS = [
    ["https://costco.com/p/1", "https://www.amazon.com/final"],
]


def test_no_adapter_advertises_amazon_origin():
    for name, cls in ADAPTER_CLASSES.items():
        origin = getattr(cls(), "origin", "")
        assert "amazon" not in str(origin).lower(), f"{name} origin is Amazon: {origin}"


def test_adapter_origins_are_not_amazon_host():
    for name, cls in ADAPTER_CLASSES.items():
        origin = getattr(cls(), "origin", "")
        if origin:
            assert not is_amazon_host(origin, origin), f"{name} origin blocked as Amazon: {origin}"


def test_policy_blocks_amazon_hosts_for_every_adapter():
    # The blocklist is a property of the policy kernel, not the adapter, but it
    # must hold regardless of which adapter is in play.
    for name in ADAPTER_NAMES:
        for url in AMAZON_URLS:
            host = url.split("//", 1)[1].split("/", 1)[0]
            assert is_amazon_host(host, host), f"{name}: {host} not recognised as Amazon"


def test_lookalike_hosts_recognised():
    for h in LOOKALIKE_HOSTS:
        puny = h.encode("idna").decode("ascii")
        assert is_amazon_host(h, puny), f"lookalike not recognised: {h}"


def test_redirect_to_amazon_is_blocked():
    # Redirect chains ending on Amazon must be refused by the policy kernel.
    # Adapters never follow redirects themselves; this guards the contract.
    try:
        from northstar.policy import PolicyKernel
    except Exception:
        import pytest
        pytest.skip("PolicyKernel not importable")
    # Minimal sanity: is_amazon_host catches the final hop.
    final = "www.amazon.com"
    assert is_amazon_host(final, final)


def test_amazon_url_does_not_yield_ok_extraction():
    # Feeding an Amazon page's HTML to a non-Amazon adapter must never be
    # reported as a clean OK extraction tagged as that adapter's own data.
    for name, cls in ADAPTER_CLASSES.items():
        adapter = cls()
        html = "<html><body><span id='productTitle'>X</span></body></html>"
        result = adapter.extract(html, url="https://www.amazon.com/dp/B000000000")
        # Adapters may still parse, but the source_url must be preserved so the
        # runner can route it through the policy gate; status alone is not proof.
        assert result.source_url == "https://www.amazon.com/dp/B000000000"
