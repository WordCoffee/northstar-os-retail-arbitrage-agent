# Northstar OS — Phase B Security Items (running log)

Tracked here so security-relevant Phase B work is never lost. Each item is
**flagged, not fixed** — fixes happen only under a fresh, named Phase B
approval. No item here authorizes any live call.

## B4 — Golden Goose §3 live-gate env flip (in-process)

- **Status:** RESOLVED for `run_live_scan.py` under **B1** (2026-09-19). The
  test-hygiene portion below remains OPEN for Phase B.
- **File:** `Northstar_backend/agents/golden_goose_finder/run_live_scan.py`
- **Finding:** this script set the §3 envelope env var
  `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1` **in-process**, opening the golden-goose
  live gate for the whole process.
- **Resolution (B1):** removed the in-process flip. LIVE execution now requires
  **two operator-set gates** (the established two-gate pattern): runtime
  `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1` **and** an explicit operator
  authorization phrase `GOLDEN_GOOSE_LIVE_AUTH_PHRASE="AUTHORIZE GOLDEN GOOSE
  LIVE SCAN"`, both read-only in
  `agents/golden_goose_finder/live_scan_gate.py`. `run_live_scan.py` never
  mutates the environment (guarded by tests); the CLI exits 2 when either gate
  is missing, and `run()` raises `LiveScanRefused` before any provider contact.
  Tests: `tests/test_live_scan_gate.py` (gate matrix, refusals make zero
  pipeline calls, authorized fixture path with a fake pipeline, never-self-armed
  source guard).
- **Related, still OPEN (Phase B — test hygiene, same root cause):**
  - `agents/golden_goose_finder/test_single_match.py` sets the same env var at
    **module import time** (line 8) and executes top-level live-discovery code
    on import. When the full pytest tree is collected, this leaks the gate
    open for every later test in the same process. Sanctioned suite composition
    excludes it (Golden Goose module runs = `tests/` subdir only). The file also
    contains `async def test_match` with no async pytest plugin installed.
  - Phase B scope: move the env manipulation into a fixture/monkeypatch, gate
    the import-time execution behind `if __name__ == "__main__"`, and either add
    an async plugin or make the test sync/marked. (Not actioned in B1/B2.)

---
*Created: 2026-09-19 (Phase A Gate-1 session). Read/write-limited: flagging only.*