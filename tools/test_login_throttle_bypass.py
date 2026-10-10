"""Login-throttle test bypass: asserts it is fail-closed where it matters.

Run:  python tools/test_login_throttle_bypass.py
Exit: 0 = the bypass behaves, 1 = a hole.

The bypass exists so a harness is not mistaken for a regression. It must NEVER
be available in a hosted environment, and it must only RAISE the limit — never
disable the throttle.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Northstar_backend"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "Northstar_backend", "foundation"))

PASS = 0
FAIL = 0
FAILURES: list[str] = []


def ok(m):
    global PASS
    PASS += 1
    print("PASS  " + m)


def no(m):
    global FAIL
    FAIL += 1
    FAILURES.append(m)
    print("FAIL  " + m)


from foundation import login_throttle as lt  # noqa: E402


def main() -> int:
    # ── Hosted environments can NEVER enable it, whatever the env var says ──
    for env in ("production", "production_tenant", "staging", "PRODUCTION", "Staging"):
        os.environ["NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS"] = "1"
        if lt.test_bypass_enabled(env) is False:
            ok(f"bypass refused in hosted environment {env!r} even with the env var set")
        else:
            no(f"HOLE: bypass enabled in hosted environment {env!r}")

    # ── Development requires the explicit env var ───────────────────────────
    os.environ.pop("NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS", None)
    if lt.test_bypass_enabled("development") is False:
        ok("bypass off in development without the env var")
    else:
        no("HOLE: bypass on in development without the env var")

    for truthy in ("0", "", "no", "true "):
        os.environ["NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS"] = truthy
        if lt.test_bypass_enabled("development") is False:
            ok(f"bypass off for non-exact value {truthy!r}")
        else:
            no(f"HOLE: bypass on for non-exact value {truthy!r}")

    os.environ["NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS"] = "1"
    if lt.test_bypass_enabled("development") is True:
        ok("bypass on in development with the exact env var")
    else:
        no("bypass did not activate in development with the env var")

    # ── Missing environment = fail closed ──────────────────────────────────
    if lt.test_bypass_enabled(None) is True:
        ok("bypass on for an unknown environment (local dev, env var set)")
    else:
        no("bypass did not activate for an unknown environment")
    os.environ.pop("NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS", None)
    if lt.test_bypass_enabled(None) is False:
        ok("bypass off when the environment is unknown and the var is unset")
    else:
        no("HOLE: bypass on with no environment and no var")

    # ── The raise is FINITE: still a limit, and it is only a raise ──────────
    class FakeDB:
        backend = "sqlite"
        def __init__(self):
            import sqlite3
            self.conn = sqlite3.connect(":memory:")
        def execute(self, *a, **k):
            return self.conn.execute(*a, **k)

    db = FakeDB()
    os.environ["NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS"] = "1"
    allowed = sum(1 for _ in range(lt._TEST_LIMIT + 5)
                  if lt.allow(db, "k|1.2.3.4", environment="development"))
    if allowed == lt._TEST_LIMIT:
        ok(f"bypass raises the ceiling to exactly {lt._TEST_LIMIT} and still blocks after")
    else:
        no(f"bypass allowed {allowed} attempts, expected exactly {lt._TEST_LIMIT}")

    # ── Without the bypass the original limit still applies ─────────────────
    os.environ.pop("NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS", None)
    db2 = FakeDB()
    strict = sum(1 for _ in range(20)
                 if lt.allow(db2, "k|5.6.7.8", environment="development"))
    if strict == 5:
        ok("without the bypass the original 5-per-window limit is unchanged")
    else:
        no(f"strict limit allowed {strict}, expected 5")

    # ── Production path is untouched even with the env var set ──────────────
    os.environ["NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS"] = "1"
    db3 = FakeDB()
    prod = sum(1 for _ in range(20)
               if lt.allow(db3, "k|9.9.9.9", environment="production"))
    if prod == 5:
        ok("production keeps the 5-per-window limit even with the env var set")
    else:
        no(f"HOLE: production allowed {prod} attempts with the bypass env var set")
    os.environ.pop("NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS", None)

    print(f"\nLOGIN THROTTLE BYPASS: {PASS} passed, {FAIL} failed")
    if FAILURES:
        print("\nFailures:\n  " + "\n  ".join(FAILURES))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
