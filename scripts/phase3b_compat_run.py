"""Phase 3b — LIVE COMPATIBILITY RUN (owner-approved, first run only).

Sources (approved 2026-10-11, exactly these four — no widening):
    example.com, docs.python.org, books.toscrape.com, quotes.toscrape.com

Caps and rules, enforced by construction:
    - max 10 requests per source (robots fetch included), 40 total
    - minimum 2 s between requests per domain (explicit spacing + kernel limiter)
    - 10-minute global time budget (kernel RunBudget)
    - kernel response-size cap (default 2 MB per response)
    - robots.txt fetched THROUGH THE GATEWAY before each source; if it cannot
      be read or the fetch fails, the source is SKIPPED and recorded
      ("skipped: robots") — no retry, no workaround
    - no link-following off the approved domains

Control checks after the sources: redirect-to-private-IP chain denial, direct
private-IP fetch denial, and the prompt-injection fixture through the gateway
(local server only). Audit hash chain verified at the end.

Run from the repo root. JSON summary to stdout; progress log to stderr.
"""
from __future__ import annotations

import http.server
import functools
import json
import socket
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from northstar.gateway import DockerLightpandaDriver, LightpandaGateway
from northstar.policy import (
    AuditLog,
    GrantSet,
    PolicyKernel,
    RateLimiter,
    RobotsGate,
    RunBudget,
)

APPROVED_HOSTS = (
    "example.com",
    "docs.python.org",
    "books.toscrape.com",
    "quotes.toscrape.com",
)

SOURCE_PAGES = {
    "example.com": [
        ("https://example.com/", "Example Domain"),
    ],
    "docs.python.org": [
        ("https://docs.python.org/3/", "Python"),
        ("https://docs.python.org/3/tutorial/index.html", "tutorial"),
        ("https://docs.python.org/3/library/index.html", "library"),
        ("https://docs.python.org/3/reference/index.html", "reference"),
        ("https://docs.python.org/3/howto/index.html", "HOWTO"),
    ],
    "books.toscrape.com": [
        ("https://books.toscrape.com/", "Books to Scrape"),
        ("https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html", "£"),
        ("https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html", "£"),
    ],
    "quotes.toscrape.com": [
        ("https://quotes.toscrape.com/js/", "Einstein"),
    ],
}

MAX_REQUESTS = 40
MIN_SPACING_SECONDS = 2.1
GLOBAL_BUDGET_SECONDS = 600


def envelope_body(envelope: str) -> str:
    start = envelope.find("\n-----\n")
    end = envelope.rfind("\n----- END UNTRUSTED WEB CONTENT")
    if start != -1 and end != -1 and end > start:
        return envelope[start + len("\n-----\n") : end]
    return envelope


def system_resolver(host: str) -> list:
    """Real DNS for the live run (the kernel checks every resolved IP; the
    container resolves independently for the actual connection)."""
    infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def main() -> int:
    audit = AuditLog()
    grants = GrantSet()
    budget = RunBudget(
        max_requests=MAX_REQUESTS, max_bytes=40_000_000, max_seconds=GLOBAL_BUDGET_SECONDS
    )
    limiter = RateLimiter(rate_per_minute=30.0, burst=1.0)

    robots_cache: dict[str, str] = {}

    def robots_loader(host: str):
        return robots_cache.get(host)

    bootstrap_kernel = PolicyKernel(
        allowlist=APPROVED_HOSTS,
        resolve=system_resolver,
        robots=RobotsGate(lambda host: "", require_robots=False),  # robots bootstrap
        grants=grants,
        audit=audit,
        rate_limiter=limiter,
        budget=budget,
    )
    main_kernel = PolicyKernel(
        allowlist=APPROVED_HOSTS,
        resolve=system_resolver,
        robots=RobotsGate(robots_loader, require_robots=True),
        grants=grants,
        audit=audit,
        rate_limiter=limiter,
        budget=budget,
    )
    driver = DockerLightpandaDriver()
    bootstrap_gateway = LightpandaGateway(kernel=bootstrap_kernel, driver=driver)
    gateway = LightpandaGateway(kernel=main_kernel, driver=driver)

    task = "compat-run"
    grants.issue(task, [f"fetch:{host}" for host in APPROVED_HOSTS])

    last_request_at: dict[str, float] = {}
    per_source_counts: dict[str, int] = {host: 0 for host in APPROVED_HOSTS}
    started = time.monotonic()

    def spaced_fetch(tool, url: str):
        from urllib.parse import urlsplit

        host = (urlsplit(url).hostname or "").lower()
        now = time.monotonic()
        wait = MIN_SPACING_SECONDS - (now - last_request_at.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        if per_source_counts[host] >= 10:
            raise RuntimeError(f"per-source cap reached for {host}")
        if time.monotonic() - started > GLOBAL_BUDGET_SECONDS - 30:
            raise RuntimeError("global time budget nearly exhausted")
        result = tool(task_id=task, url=url)
        last_request_at[host] = time.monotonic()
        per_source_counts[host] += 1
        return result

    report: dict = {"sources": [], "controls": {}, "caps": {
        "max_requests": MAX_REQUESTS,
        "min_spacing_seconds": MIN_SPACING_SECONDS,
        "global_budget_seconds": GLOBAL_BUDGET_SECONDS,
        "per_source_counts": per_source_counts,
    }}

    # ---- sources ---------------------------------------------------------
    for host in APPROVED_HOSTS:
        entry: dict = {"host": host, "robots": None, "pages": []}
        robots_url = f"https://{host}/robots.txt"
        print(f"[robots] {robots_url}", file=sys.stderr)
        try:
            robots_result = spaced_fetch(bootstrap_gateway.markdown_dump, robots_url)
        except Exception as exc:  # cap/budget guard
            robots_result = None
            print(f"[robots-stop] {host}: {exc}", file=sys.stderr)
        if robots_result is None or not robots_result.ok:
            reason = robots_result.reason if robots_result is not None else "budget"
            entry["robots"] = {"status": "skipped: robots", "reason": reason}
            report["sources"].append(entry)
            continue
        robots_text = envelope_body(robots_result.envelope).strip()
        if not robots_text:
            entry["robots"] = {"status": "skipped: robots", "reason": "empty robots body"}
            report["sources"].append(entry)
            continue
        robots_cache[host] = robots_text
        entry["robots"] = {"status": "fetched", "chars": len(robots_text)}

        for url, marker in SOURCE_PAGES.get(host, []):
            print(f"[page] {url}", file=sys.stderr)
            try:
                page_result = spaced_fetch(gateway.markdown_dump, url)
            except Exception as exc:
                entry["pages"].append({"url": url, "ok": False, "reason": str(exc)})
                continue
            if not page_result.ok:
                entry["pages"].append(
                    {
                        "url": url,
                        "ok": False,
                        "reason": page_result.reason,
                        "detail": page_result.detail[:200],
                        "escalate_chrome_connect": False,
                    }
                )
                continue
            body = envelope_body(page_result.envelope)
            marker_found = marker.lower() in body.lower()
            non_empty = len(body.strip()) > 200
            entry["pages"].append(
                {
                    "url": url,
                    "ok": True,
                    "content_chars": len(body),
                    "marker": marker,
                    "marker_found": marker_found,
                    "js_evidence": marker_found if "js" in url else None,
                    "escalate_chrome_connect": bool(not marker_found and not non_empty),
                }
            )
        report["sources"].append(entry)

    # ---- controls --------------------------------------------------------
    controls: dict = {}

    chain = main_kernel.authorize_redirect_chain(
        task_id=task,
        urls=["https://example.com/", "http://10.0.0.1/redirected"],
    )
    controls["redirect_to_private_denied"] = {
        "allowed": chain.allowed,
        "reason": chain.reason,
    }

    private_attempt = gateway.markdown_dump(task_id=task, url="http://127.0.0.1:9222/json/version")
    controls["direct_private_fetch_denied"] = {
        "allowed": private_attempt.ok,
        "reason": private_attempt.reason,
    }

    fixtures = REPO / "tests" / "lightpanda_fixtures"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(fixtures))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        control_grants = GrantSet()
        control_kernel = PolicyKernel(
            allowlist=("host.docker.internal",),
            resolve=lambda host: ["93.184.216.34"],
            robots=RobotsGate({"host.docker.internal": "User-agent: *\nAllow: /\n"}),
            grants=control_grants,
            audit=audit,
        )
        control_gateway = LightpandaGateway(kernel=control_kernel, driver=driver)
        control_grants.issue("control-task", ["fetch:host.docker.internal"])
        inj = control_gateway.markdown_dump(
            task_id="control-task",
            url=f"http://host.docker.internal:{port}/prompt_injection_page.html",
        )
        controls["injection_fixture"] = {
            "ok": inj.ok,
            "enveloped": inj.envelope.startswith("----- BEGIN UNTRUSTED WEB CONTENT") if inj.ok else False,
            "hostile_text_present_as_data": ("IGNORE ALL PREVIOUS INSTRUCTIONS" in inj.envelope) if inj.ok else False,
            "scripts_stripped": ("bad(" not in inj.envelope) if inj.ok else False,
        }
    finally:
        httpd.shutdown()
        httpd.server_close()

    report["controls"] = controls
    report["audit_chain_ok"] = audit.verify()
    report["elapsed_seconds"] = round(time.monotonic() - started, 1)
    report["caps"]["per_source_counts"] = per_source_counts

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
