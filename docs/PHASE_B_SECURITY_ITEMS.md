# Northstar OS — Phase B Security Items (running log)

Tracked here so security-relevant Phase B work is never lost. Each item is
**flagged, not fixed** — fixes happen only under a fresh, named Phase B
approval. No item here authorizes any live call.

## B4 — Golden Goose §3 live-gate env flip (in-process)

- **Status:** RESOLVED for `run_live_scan.py` under **B1** (2026-09-19). The
  test-hygiene portion below was **fixed under Phase F/S3 (2026-09-20)** —
  `test_single_match.py` was rewritten with no import-time side effects and is
  re-included in the standard suite (no longer `--ignore`d).
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
- **Related (Phase F/S3 — RESOLVED):**
  - `agents/golden_goose_finder/test_single_match.py` previously set the §3
    envelope env var at module import and ran top-level live-discovery code.
    **Rewritten (Phase F/S3):** no import-time env flips / dotenv / execution;
    an offline mock-pipeline test replaces the old live-async test (no async
    plugin needed); the original live probe lives behind
    `if __name__ == "__main__"` with an explicit two-gate check. The file is
    **re-included** in the standard suite (the runner `--ignore` was removed).
    Hygiene is asserted by `test_import_has_no_side_effects`.

---
*Created: 2026-09-19 (Phase A Gate-1 session). Read/write-limited: flagging only.*