# Egress map — every outbound call site, and where the Amazon boundary is (2026-11-06)

Produced by a read-only exploration lane, then reviewed here. The one-line finding:

> **There is no global egress hook anywhere in the repo.** No module patches `requests`,
> `httpx`, `urllib` or `socket` to enforce the Amazon boundary at the transport layer. Every
> Amazon decision is per-call-site, so the boundary is only as wide as the handful of sites
> that happen to call one of the checks.

That is the property to fix, not the 44 individual sites.

## The seven checks that exist

| # | Check | Definition | Wired into |
|---|---|---|---|
| A | `bright_data_client._amazon_refusal` | `bright_data_client.py:460`, called `:505` | only `bright_data_client._fetch` |
| B | `web_research.guard` | `tools/web_research.py:138` -> `is_amazon_host` `:119` | only `_http` |
| C | `northstar.policy.check_source` | `northstar/policy/allowlist.py:34`, `assert_not_amazon` `:28` before allowlist `:44` | Chrome Connect only |
| D | `amazon_linkage_gate.linkage_enabled` | `amazon_linkage_gate.py:31` | SP-API/Ads importers, at method entry |
| E | `assert_no_amazon_direct_scan` | `costco_non_kirkland/amazon_guard.py:41` | **dead**: callers pass `asin=` only, so the `url` branch `:47` never runs |
| F | provider opt-in `_gate_enabled` | `scrapedo_amazon.py:86` (+ firecrawl/browserbase) | only their `__main__` |
| G | `local_screen.assert_loopback` | `local_screen.py:86` | loopback lane, not an Amazon check |

## The worst offenders (caller-supplied URL, no host check)

| file:line | why it matters |
|---|---|
| `design_studio_async.py:104` -> `urlopen` `:123` | `url` comes straight from the API body (`body["callback_url"]` `:141`). No scheme, host or loopback check: SSRF, and Amazon-reachable. Widest hole. |
| `dataforseo_adapter.py:883`/`:900` | `classify_endpoint` validates **path segments only** (`:249`, `:262-263`); `hostname` is never read. `https://www.amazon.com/v3/...` passes and receives the auth header. |
| `rapidapi_router.py:340` | `https://{host}{path}`, `host` caller-supplied, template embeds an amazon.com URL (`:60`). |
| `adapters/base.py:120` -> `client.request` `:144` | `follow_redirects=True`; target arbitrary. |
| `adapters/{brightdata,scrape_do,firecrawl}.py` | `_make_request(url)` forwards the target verbatim. |
| `importers/sp_api_importer.py:64`, `ads_api_importer.py:82` | `api.amazon.com/auth/o2/token` posted from the auth classes with **no gate inside them**; the gate is on the importer's public methods only. |
| `importers/ads_api_importer.py:519` | Downloads a report from a **provider-supplied** URL with no host check. |
| `lions_mane_pull.py:495`, `run_vision_sb.py:63` | Fetch provider-supplied image URLs from Amazon's CDN. |
| `tools/mcp_client.py` | Spawns any server and calls any tool; no policy import by design. |

Full table (44 rows) was produced in the lane's report; this file keeps the class and the
top of it. **~62 further call sites are loopback-only** and correctly unguarded.

## What this changes about the plan

The boundary is currently enforced by *seven checks that each cover one call site*. The fix
that matches the video's lesson ("a rule in prose is not a control") is a **transport-level
hook**: one place that wraps the HTTP clients, refuses Amazon hosts before the request, and
journals the decision - so a new call site is governed by default instead of by discipline.

## Remediation order (queued)

1. **T0** `tools/egress_guard.py` - a single hook installed by the service entrypoint and by
   every tool that makes requests; refuses Amazon hosts + journals `{url, host, caller}`.
   Acceptance: a new call site with no explicit check still refuses Amazon, proven by a test
   that calls `requests.get("https://www.amazon.com")` and asserts no socket was opened.
2. **T0** `design_studio_async` callback validation: scheme allowlist, host allowlist, no
   loopback, no link-local, no IP literals (SSRF), and an Amazon refusal.
3. **T1** `dataforseo_adapter.classify_endpoint` must read `hostname`, not only `path`.
4. **T1** Repair or delete `assert_no_amazon_direct_scan` - it is dead at both call sites.
5. **T1** Gate inside `SPAPIAuth._refresh` / `AdsAPIAuth._refresh`, not only at method entry.
6. **T2** Add `amzn.eu` to `bright_data_client._amazon_refusal` (covered by
   `northstar/policy/urls.py:20`, missing here).
