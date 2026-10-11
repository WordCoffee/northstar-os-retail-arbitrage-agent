# Phase 2 — Policy Kernel Delivery

- **Date:** 2026-10-11 · **Owner:** T2 Holdings LLC
- **Security scan state (standing line):** **Active findings: 8** — 2 chat-archive key values (rotation in progress owner-side), 1 `ghp_` token (revocation in progress), 1 `rate_limiter.py` review item; 231 reviewed-benign fingerprints allowlisted.
- **Module:** `northstar/policy/` — pure, deterministic, stdlib-only; no network; no runtime policy-mutation API; resolver and clocks injected (zero live calls in tests).

## 1. What was built

| File | Responsibility |
|---|---|
| `urls.py` | URL/host normalization (IDNA→ASCII, IP-literal canonicalization), scheme allowlist (http/https only), **hardcoded Amazon blocklist** (subdomains, shorteners `amzn.to`/`amzn.eu`/`a.co`, typosquat substrings, and confusable/Cyrillic lookalikes via confusable folding + punycode decoding) |
| `allowlist.py` | Source allowlist, **default deny** (`DEFAULT_ALLOWLIST` empty — owner-approved entries land only via reviewed commits); Amazon check always first and **cannot be overridden** by allowlist/config |
| `ssrf.py` | SSRF defense: resolve **once** and pin; every resolved IP must be public (mixed public+private answer sets denied = rebinding defense); blocked ranges: `10/8, 127/8, 169.254/16 (metadata), 172.16/12, 192.168/16, 0/8, multicast/broadcast/reserved`, IPv6 `::1, fc00::/7, fe80::/10, ff00::/8`, v4-mapped IPv6 |
| `robots.py` | robots.txt enforcement, **fail-closed** when robots text is unknown (`require_robots=True` default); text is supplied — never fetched here |
| `limits.py` | Per-domain token-bucket rate limit (continuous refill), **per-run caps**: max requests / max bytes / wall-clock budget, response-size cap |
| `grants.py` | Capability grants: per-task, default **none**, TTL expiry + `release()` at task end; `fetch:<host>` grants cover subdomains |
| `approvals.py` | Approval queue (live_fetch / spend / side_effect; requester can never self-approve; decisions recorded with approver+time) + **SIMULATED-never-snapshot guard** |
| `audit.py` | **Tamper-evident hash-chained audit log** (append-only, no update/delete APIs), detail redacted via the Phase 1 redaction layer, optional JSONL sink |
| `kernel.py` | Facade composing every gate in fixed order: parse → **Amazon** → allowlist → capability → SSRF → robots → rate → budget; **every decision** (allow+deny) audited |

## 2. Acceptance matrix (all denied AND logged)

| Spec item | Test evidence |
|---|---|
| Blocked domain | `test_unlisted_domain_denied_and_logged` |
| Private IP | 6 parametrized literals incl. `169.254.169.254`, IPv6 `::1`/`fc00::1`, host-resolves-private, mixed answers |
| Redirect-to-private-IP | `test_redirect_to_private_ip_denied` (hop allowlisted+granted ⇒ SSRF gate is the denier) |
| DNS rebinding | resolve-once + pin + all-IPs-public (+ mixed-answer denial, resolver-call-count assert) |
| Oversize response | `test_oversize_denied_and_logged` |
| Rate-limit breach | limiter unit tests + kernel integration (denied + logged) |
| Expired capability | TTL test + kernel integration (denied + logged) |
| Amazon variants | subdomains, shorteners, `amazon.com.evil.com`, Cyrillic lookalike (computed punycode), **allowlist-override attempt**, redirect-to-amazon |
| Robots | allowed / disallowed path / unknown-fail-closed / operator override |
| Audit integrity | chain verify, **tamper detection** (mutated entry ⇒ verify False), redaction of detail, JSONL sink chain linkage |

**Tests:** `python -m pytest tests/security -q` → **139 passed / 0 failed** (66 new Phase-2 tests + all Phase-1 suites still green).

## 3. Design notes (decisions worth knowing)

- **Check order:** Amazon is always first and unforgeable; a private IP that is not allowlisted reports `domain_not_allowed` (still denied+logged) — the SSRF gate is specifically demonstrated via allowlisted+granted hosts.
- **DNS:** the kernel never dials — `resolve` is injected; production wiring happens in Phase 3 (gateway). A test monkeypatches `socket.getaddrinfo` to raise, proving the path never touches system DNS.
- **Pin contract:** `resolve_and_pin` returns the pinned IPs; the Phase 3 gateway must connect to the pinned IPs only (documented in the module; the gateway will be tested against this).
- **Policy immutability:** allowlist/limits are constructor data or code constants; there is no API for an agent to mutate them at runtime.

## 4. Explicit non-claims

- No live fetches, no DNS lookups, no provider calls — everything is deterministic.
- Approval-queue **enforcement inside the fetch flow** and robots-text acquisition belong to Phase 3 (gateway); this phase delivers the queue semantics + gates.
- `DEFAULT_ALLOWLIST` is intentionally empty; the Phase 3 compatibility run needs the owner-approved source list (draft diff to follow with the Phase 3 policy amendment).

## 5. Next (owner-agreed order)

**CI wiring** (scanner gate + tests + gitleaks advisory job activation), then Phase 3 (Lightpanda Connect gateway — still needs the separate Lightpanda install approval). Pending elsewhere: threat-model review (owner), scrub decision (after tonight's rotation).
