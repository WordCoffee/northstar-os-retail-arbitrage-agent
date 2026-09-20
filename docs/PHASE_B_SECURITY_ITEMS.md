# Northstar OS — Phase B Security Items (running log)

Tracked here so security-relevant Phase B work is never lost. Each item is
**flagged, not fixed** — fixes happen only under a fresh, named Phase B
approval. No item here authorizes any live call.

## B4 — Golden Goose §3 live-gate env flip (in-process)

- **Status:** OPEN — flagged for Phase B (B4). Do not fix in Phase A.
- **File:** `Northstar_backend/agents/golden_goose_finder/run_live_scan.py`
- **Finding:** this script sets the §3 envelope env var
  `GOLDEN_GOOSE_LIVE_OPERATOR_APPROVED=1` **in-process at import/run time**.
  Any invocation of the script (intentional or accidental) opens the golden-goose
  live gate for the whole process, bypassing the HTTP 403 envelope the API
  enforces. A comment on the line now documents the review need.
- **Required change (Phase B):** replace the in-process env flip with an
  explicit operator-passed flag (e.g. `--approved <token>` or an
  operator-confirmed prompt), so running the script alone can never open the
  gate.
- **Related, also flagged for Phase B (test hygiene, same root cause):**
  - `agents/golden_goose_finder/test_single_match.py` sets the same env var at
    **module import time** (line 8) and executes top-level live-discovery code
    on import. When the full pytest tree is collected, this leaks the gate
    open for every later test in the same process (observed: the two
    golden-goose gate tests then fail, and live-path tests execute instead of
    returning 403). The file also contains `async def test_match` with no
    async pytest plugin installed (fails in plain pytest). Sanctioned suite
    composition excludes it (Golden Goose module runs = `tests/` subdir only).
  - Phase B scope: move the env manipulation into a fixture/monkeypatch,
    gate the import-time execution behind `if __name__ == "__main__"`, and
    either add an async plugin or make the test sync/marked.

---
*Created: 2026-09-19 (Phase A Gate-1 session). Read/write-limited: flagging only.*