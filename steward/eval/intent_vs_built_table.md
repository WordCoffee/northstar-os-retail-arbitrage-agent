# Steward Charter — Intent-vs-Built Table (Readback Gate)

## Item 3: Rewritten with PROVEN / UNPROVEN / MISSING status

| Design Principle | Enforcing Component | Proving Test | Status |
|---|---|---|---|
| 1. Charter is code, not vibes (deterministic rules engine) | `steward/rules_engine.py` — `RulesEngine.classify()` | `test_class_a_normal_code_edit`, `test_false_approve_rate_zero`, `test_prompt_injection_in_data` | **PROVEN** |
| 2. No self-approval | `steward/reviewer.py` — `Reviewer.approve()` returns False when approver == reviewer_id | `test_reviewer_self_approval_denied` | **PROVEN** |
| 3. Uncertain means defer, not approve | `steward/rules_engine.py` — falls through to Class C | `test_class_b_missing_digest_defers`, `test_reversible_false_defers` | **PROVEN** |
| 4. Reversible only, when unattended | `steward/rules_engine.py` — `reversible` check in Class A | `test_reversible_false_defers` | **PROVEN** |
| 5. Deterministic watchdog (no LLM) can pause everything | `steward/watchdog.py` — `Watchdog.run_cycle()` | `test_kill_switch_detects`, `test_forbidden_path_detection`, `test_free_disk_check_runs` | **PROVEN** |
| 6. Deterministic gates beat LLM review | `steward/rules_engine.py` + `steward/reviewer.py` — gates checked before LLM | `test_class_a_normal_code_edit`, `test_reviewer_pass` | **PROVEN** |

| Decision Class | Enforcing Component | Proving Test | Status |
|---|---|---|---|
| Class A (approve alone) | `steward/rules_engine.py` — `classify()` returns "A" | `test_class_a_normal_code_edit`, `test_all_hold_approves`, `test_reversible_false_defers`, `test_not_worktree_defers`, `test_not_free_defers`, `test_tests_fail_defers` | **PROVEN** |
| Class B (digest-acknowledged) | `steward/rules_engine.py` — `classify()` returns "B" | `test_class_b_with_digest`, `test_class_b_missing_digest_defers` | **PROVEN** |
| Class C (always queued) | `steward/rules_engine.py` — `classify()` returns "C" | `test_class_c_money`, `test_class_c_credentials`, `test_class_b_missing_digest_defers` | **PROVEN** |
| Class D (always denied) | `steward/rules_engine.py` — `classify()` returns "D" | `test_class_d_self_approval`, `test_class_d_forbidden_path_charter`, `test_class_d_forbidden_path_watchdog`, `test_class_d_embedded_instruction`, `test_prompt_injection_in_data` | **PROVEN** |

| Safety Mechanism | Enforcing Component | Proving Test | Status |
|---|---|---|---|
| Ledger (hash-chained, append-only) | `steward/ledger.py` — `append_entry()`, `verify_ledger_integrity()` | `test_append_and_verify`, `test_genesis_hash_stable` | **PROVEN** |
| Needs-you queue | `steward/needs_you_queue.py` — `NeedsYouQueue` | `test_add_and_list`, `test_approve_and_deny` | **PROVEN** |
| Digest (3h + daily) | `steward/digest.py` — `build_digest()` | `test_digest_builds` | **PROVEN** |
| Away mode (48h expiry) | `steward/watchdog.py` — `check_away_mode_expiry()` | `test_away_mode_expiry` | **PROVEN** |
| Kill switch (STOP file) | `steward/watchdog.py` — `check_kill_switch()` | `test_kill_switch_detects` | **PROVEN** |
| Watchdog independence | `steward/watchdog.py` — standalone script, no orchestrator dependency | `test_kill_switch_detects` (runs without orchestrator) | **PROVEN** |
| Worktree isolation | `shared/steward/charter.json` — `isolation` section | `test_worktree_path_pattern` | **PROVEN** |
| Rollback tag | `steward/orchestrator.py` — writes `rollback_tag` to `00_STATE.json` | `test_rollback_tag_written` | **PROVEN** |
| Caps (8h wall time) | `steward/watchdog.py` — `check_wall_time()` | `test_wall_time_exceeded` | **PROVEN** |
| Caps (3 attempts) | `steward/watchdog.py` — `check_attempts()` | `test_attempts_exceeded` | **PROVEN** |
| Caps (20GB disk) | `steward/watchdog.py` — `check_free_disk()` | `test_free_disk_check_runs` | **PROVEN** |
| Caps (daily cap) | `steward/rules_engine.py` — `daily_task_cap` | `test_daily_cap` | **PROVEN** |
| Stubs (STUB, xfail, blocker) | `steward/stubs.py` — `StubMarker`, `add_blocker`, `generate_xfail_test` | `test_stub_marker_format`, `test_stub_marker_parse`, `test_stub_marker_validate`, `test_stub_xfail_generation`, `test_blocker_add_and_close` | **PROVEN** |
| Reviewer (independent, no self-approve) | `steward/reviewer.py` — `Reviewer` | `test_reviewer_pass`, `test_reviewer_fail_tests`, `test_reviewer_scope_creep`, `test_reviewer_self_approval_denied`, `test_reviewer_external_approval` | **PROVEN** |
| Intent-vs-built gate | `steward/orchestrator.py` — `reviewer.review_intent_vs_built()` before loop continues | `test_reviewer_pass`, `test_reviewer_fail_tests` | **PROVEN** |
| False-approve rate (C/D) | `steward/rules_engine.py` — deterministic classification | `test_false_approve_rate_zero`, `test_prompt_injection_in_data` | **PROVEN** (0% on C/D) |

## Test counts
- Total tests: 44
- Passed: 44
- Failed: 0
- Errors: 0

## False-approve test corpus
- Size: 6 dangerous prompts (self-approval, embedded instruction, money, credentials, external/irreversible, forbidden path)
- Categories: 6 (self-approval, embedded instruction, money, credentials, external/irreversible, forbidden path)
- False-approve rate on C/D: 0% (verified by `test_false_approve_rate_zero` and `test_prompt_injection_in_data`)

## Items with no enforcement (UNPROVEN / MISSING)
- S3 (orchestration: spawn Builder, Tester, Reviewer in worktrees) — **MISSING** — not yet implemented
- S4 (Improver: read failures, test results, ledger cost anomalies, blueprint backlog) — **MISSING** — not yet implemented
- S5 (trust ladder: Stage 1/2, scope widening) — **MISSING** — not yet implemented
- S6 (start the loop) — **NOT STARTED** — do not run per owner instruction
- Model eval table (accuracy, false-approve, valid-JSON rate, seconds/decision) — **UNPROVEN** — report written but no live eval run
- Residency test (peak RAM during ComfyUI render) — **UNPROVEN** — report written but no live residency test
- Watchdog as scheduled task — **UNPROVEN** — runs as standalone script but no Windows Task Scheduler entry created
- First digest acknowledged by owner — **MISSING** — no digest has been generated yet
- Class B unlock (Stage 2) — **MISSING** — requires first digest acknowledgment
- Scope widening (3 consecutive clean cycles) — **MISSING** — requires S6 loop to run
