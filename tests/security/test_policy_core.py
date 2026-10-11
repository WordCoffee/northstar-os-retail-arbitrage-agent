"""Phase 2 acceptance tests — core gates: Amazon block, allowlist, SSRF (incl.
rebinding + redirects), and response-size cap. All denials are asserted in the
audit log too (``denied AND logged``).
"""
from __future__ import annotations

import socket

import pytest

from northstar.policy import AuditLog, GrantSet, PolicyKernel, RobotsGate, is_amazon_host
from policy_helpers import PUBLIC_IP, ROBOTS_TEXT, FakeClock, make_kernel, make_resolver


class TestAmazonHardBlock:
    @pytest.mark.parametrize(
        "url",
        [
            "http://amazon.com",
            "https://www.amazon.com/dp/B000000000",
            "http://smile.amazon.co.uk/x",
            "http://amazon.de",
            "http://amazon.com.evil.com/x",
            "http://amzn.to/abc",
            "http://amzn.eu/xyz",
            "http://a.co/abc",
        ],
    )
    def test_amazon_variants_denied_and_logged(self, url):
        bundle = make_kernel(allowlist=())
        decision = bundle.kernel.authorize_fetch(task_id="t1", url=url)
        assert not decision.allowed
        assert decision.reason == "amazon_blocked"
        last = bundle.audit.entries[-1]
        assert last.decision == "deny" and last.reason == "amazon_blocked"

    def test_cyrillic_lookalike_denied(self):
        raw = "\u0430mazon.com"  # cyrillic 'а'
        punycoded = raw.encode("idna").decode("ascii")
        assert is_amazon_host(raw, punycoded)
        bundle = make_kernel(allowlist=(punycoded,))
        decision = bundle.kernel.authorize_fetch(task_id="t1", url=f"http://{punycoded}/x")
        assert not decision.allowed and decision.reason == "amazon_blocked"

    def test_amazon_cannot_be_allowlisted(self):
        bundle = make_kernel(allowlist=("amazon.com",))
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="https://www.amazon.com/")
        assert not decision.allowed and decision.reason == "amazon_blocked"

    def test_redirect_to_amazon_denied(self):
        bundle = make_kernel()
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_redirect_chain(
            task_id="t1",
            urls=["http://allowed.example/a", "https://www.amazon.com/final"],
        )
        assert not decision.allowed and decision.reason == "amazon_blocked"


class TestAllowlist:
    def test_unlisted_domain_denied_and_logged(self):
        bundle = make_kernel()
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://other.example/x")
        assert not decision.allowed and decision.reason == "domain_not_allowed"
        assert bundle.audit.entries[-1].reason == "domain_not_allowed"

    def test_listed_domain_allowed_with_grant(self):
        bundle = make_kernel()
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/page")
        assert decision.allowed
        assert decision.target is not None and decision.target.ips == (PUBLIC_IP,)
        assert bundle.audit.entries[-1].decision == "allow"

    def test_subdomain_of_allowlisted_entry_allowed(self):
        bundle = make_kernel()
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(
            task_id="t1", url="http://sub.allowed.example/x"
        )
        assert decision.allowed

    def test_non_http_scheme_rejected(self):
        bundle = make_kernel()
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="ftp://allowed.example/x")
        assert not decision.allowed and decision.reason == "url_rejected"

    def test_missing_host_rejected(self):
        bundle = make_kernel()
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http:///nohost")
        assert not decision.allowed and decision.reason == "url_rejected"


class TestSsrf:
    @pytest.mark.parametrize(
        "url",
        [
            "http://10.0.0.1/",
            "http://127.0.0.1:8080/",
            "http://169.254.169.254/latest/meta-data/",
            "http://192.168.1.5/",
            "http://172.20.0.9/",
            "http://0.0.0.0/",
        ],
    )
    def test_private_ip_literals_denied_even_when_allowlisted(self, url):
        # Allowlist + grant the literal host — the SSRF gate must still deny.
        host = url.split("//", 1)[1].split("/", 1)[0].split(":", 1)[0]
        bundle = make_kernel(allowlist=(host,))
        bundle.grants.issue("t1", [f"fetch:{host}"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url=url)
        assert not decision.allowed
        assert decision.reason == "private_ip"
        assert bundle.audit.entries[-1].reason == "private_ip"

    def test_ipv6_loopback_and_ula_denied(self):
        bundle = make_kernel(allowlist=("::1", "fc00::1"))
        bundle.grants.issue("t1", ["fetch:::1", "fetch:fc00::1"])
        for url in ("http://[::1]/", "http://[fc00::1]/"):
            decision = bundle.kernel.authorize_fetch(task_id="t1", url=url)
            assert not decision.allowed and decision.reason == "private_ip", url

    def test_host_resolving_to_private_is_denied(self):
        bundle = make_kernel(resolve=make_resolver("10.0.0.5"))
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        assert not decision.allowed and decision.reason == "private_ip"

    def test_mixed_answer_set_is_denied(self):
        # Classic rebinding trick: one public + one private answer.
        bundle = make_kernel(resolve=make_resolver(PUBLIC_IP, "10.0.0.5"))
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        assert not decision.allowed and decision.reason == "private_ip"

    def test_resolve_is_called_exactly_once(self):
        resolver = make_resolver(PUBLIC_IP)
        bundle = make_kernel(resolve=resolver)
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        assert decision.allowed
        assert resolver.calls == ["allowed.example"]

    def test_empty_dns_answer_denied(self):
        bundle = make_kernel(resolve=make_resolver())
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        assert not decision.allowed and decision.reason == "dns_no_answer"

    def test_missing_resolver_denies_hostname(self):
        bundle = make_kernel(resolve="none")
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        assert not decision.allowed and decision.reason == "resolver_unavailable"

    def test_system_dns_is_never_used(self, monkeypatch):
        def _boom(*args, **kwargs):
            raise AssertionError("system DNS must not be used in these paths")

        monkeypatch.setattr(socket, "getaddrinfo", _boom)
        bundle = make_kernel(resolve=make_resolver(PUBLIC_IP))
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_fetch(task_id="t1", url="http://allowed.example/x")
        assert decision.allowed


class TestRedirectChains:
    def test_redirect_to_private_ip_denied(self):
        # The hop is allowlisted + granted so the SSRF layer itself is the gate.
        bundle = make_kernel(allowlist=("allowed.example", "10.0.0.1"))
        bundle.grants.issue("t1", ["fetch:allowed.example", "fetch:10.0.0.1"])
        decision = bundle.kernel.authorize_redirect_chain(
            task_id="t1",
            urls=["http://allowed.example/a", "http://10.0.0.1/b"],
        )
        assert not decision.allowed and decision.reason == "private_ip"

    def test_too_many_redirects_denied(self):
        bundle = make_kernel(max_redirects=2)
        decision = bundle.kernel.authorize_redirect_chain(
            task_id="t1", urls=[f"http://allowed.example/{i}" for i in range(4)]
        )
        assert not decision.allowed and decision.reason == "too_many_redirects"
        assert bundle.audit.entries[-1].action == "redirect_chain"

    def test_valid_chain_allowed(self):
        bundle = make_kernel()
        bundle.grants.issue("t1", ["fetch:allowed.example"])
        decision = bundle.kernel.authorize_redirect_chain(
            task_id="t1",
            urls=["http://allowed.example/a", "http://sub.allowed.example/b"],
        )
        assert decision.allowed


class TestResponseSize:
    def test_oversize_denied_and_logged(self):
        bundle = make_kernel(max_response_bytes=1000)
        decision = bundle.kernel.check_response_size(task_id="t1", size=1001)
        assert not decision.allowed and decision.reason == "response_too_large"
        assert bundle.audit.entries[-1].decision == "deny"

    def test_within_limit_allowed(self):
        bundle = make_kernel(max_response_bytes=1000)
        assert bundle.kernel.check_response_size(task_id="t1", size=1000).allowed
