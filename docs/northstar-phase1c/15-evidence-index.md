# 15 — Phase 1C Evidence Index (2026-09-25)

| Artifact | Evidence |
|---|---|
| `foundation/economics/` + tests | 1C-03 canonical economics (30 tests) |
| `foundation/golden_goose_decision.py` + tests | 1C-03R C4 decision controls |
| `foundation/jobs_state.py` + `test_job_state_machine.py` | B01 state machine (99 tests) |
| `postgres-durable-validation.json` + `foundation_pg_validate_durable.py` | B02/B03/C01 migrations (9/9) |
| `foundation/jobs_durable.py`/`jobs_worker.py`/`jobs_scheduler.py` + suites | B04–B16 durable execution |
| `foundation/tests/test_jobs_durable_concurrency_postgres.py` | B14 concurrency matrix (PG) |
| `foundation/keywords/*` + keyword test modules | C01–C10 keyword intelligence |
| `foundation/tests/test_1c05_gate.py` | C11 1C-05 gate |
| `northstar-os-ui/dist` + `foundation/app.py` + `test_frontend_gate.py` | D01–D15 canonical frontend |
| `foundation/tests/test_e2e_matrix.py` | E04 e2e matrix (37) |
| `foundation/tests/test_local_production.py` | E06/E08 security + perf smoke |
| `local-production-candidate-runbook.md` | E09/E10 operational runbook |
| `staging-migration-package.json` + `staging-handoff-checklist.md` | F01–F06 staging handoff |
| `phase1c-continuation-state.json` | Machine-readable continuation state (validated JSON) |

Runtime totals: SQLite 574 passed / 28 skipped; PG 28 passed; harness 9/9;
e2e 37; frontend 30; security/perf 13.

| 1C-05 authorization | `test_authorization_matrix.py` (9) + `test_authorization_postgres.py` (4, PG) + `01c05-authorization.md` + staging smoke item 28 |
| 1C-04 decision | accepted PASSED; evidence preserved (financial-integrity report + staging reports) |

| 1C-06 beta controls | `test_beta_launch.py` (11) + `test_beta_launch_postgres.py` (6, PG) + `19-beta-controls.md` + staging smoke item 29 + `staging-005-apply-report.json` |
| Internal records | `16-data-inventory.md`, `17-retention-schedule.md`, `18-incident-runbook.md` |

| Master slice (private beta readiness) | `test_private_beta.py` (16) + `test_private_beta_postgres.py` (7, PG) + staging smoke items 29-30 + `staging-006-apply-report.json` + `reports/northstar_phase1c_private_beta_20260924.md` |
| Formal decision | PRIVATE_TEST_READY (see `reports/northstar_phase1c_private_beta_20260924.md`) |
| Subscriber rules & operations | `test_subscriber_operations.py` (12) + `test_subscriber_operations_postgres.py` (9, PG) + staging smoke item 31 + `operations/` file sets + `staging-007-apply-report.json` |
| Exportable files | `operations/subscriber-rules-matrix.md`, `operations/private-beta-operator-runbook.md`, `operations/tester-onboarding-checklist.md`, `operations/tester-feedback-triage-guide.md`, `operations/private-test-readiness-checklist.md`, `operations/tester-status-report-sample.csv` |
| Private-test checklist | `operations/private-test-checklist-verification.json` (all_pass True) |

| UI wiring & private beta experience | browser E2E (a-e) on 127.0.0.1:8001/ui + `reports/ui-evidence/01..07` screenshots + `tester-status-export-final.csv` + `reports/northstar_phase1c_ui_wiring_20260924.md` |
