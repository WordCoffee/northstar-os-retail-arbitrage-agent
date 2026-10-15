# Phase-3 Unit 4 — protego (robots.txt parsing in the gateway) — 2026-10-14

- **Standing line:** 0 new / 0 known-active / 231 allowlisted. Owner-approved Phase-3 adoption (unit 4 of 7).
- **Adopted:** `protego` **0.7.0** — **BSD-3-Clause** (Phase-2 verified; upstream pin `53d6df88ea74…`; license text sha256 `07f276b2c407d709…`). Installed via `python -m pip install protego==0.7.0` (pure-Python; no services).
- **Integration:** `northstar/policy/robots.py` — protego is now the **preferred parser** inside `RobotsGate` (`parser_kind()` added for observability); stdlib `urllib.robotparser` remains the automatic fallback; **fail-closed semantics unchanged** (unknown/empty robots + `require_robots=True` → `robots_unknown`).
- **Fixture suite (google/robotstxt):** upstream `robots_test.cc` @ `22b355ff855419e6a3ff8ff09c0ad7fdb17116f9` (**Apache-2.0**) parsed into **28 sampled cases** (of 99 resolvable) at `tests/security/fixtures/robotstxt_google/cases.json` (+ provenance README; transformation disclosed — derived JSON, not a verbatim copy).
- **Results through the gate:**
  - **17/28 cases agree with Google's C++ reference and are asserted** (allow/deny + `robots_denied` reason).
  - **11 divergences documented and pinned**: all from upstream's `GoogleOnly_SystemTest` block ("Google-specific: system test") — Google's C++ matcher DENIES while RFC 9309-style parsers (**both** protego and urllib.robotparser) ALLOW. Kept in the fixture, asserted as a divergence list so parser changes make them visible.
  - **1 intentional difference asserted**: empty robots.txt → Google allows; our gate **fails closed** (`robots_unknown`) by design.
- **Tests:** new `tests/security/test_robots_protego.py` (21 tests incl. the fallback path with `_Protego` monkeypatched to None). **Full suite: 240/240.**
- **Non-claims:** Google's C++ code is not used or linked; only derived expectations. No behavior change for the kernel/gateway API (same `RobotsGate.check` contract).
