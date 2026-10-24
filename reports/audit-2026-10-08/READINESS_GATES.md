# READINESS_GATES — evidence-based gate verdicts

**Audit date:** 2026-10-08 · **Baseline commit:** `2482048` (audit start; `f232ef8` landed during the audit)
**Rule applied:** eligible-to-begin ≠ passed. Release-exit requires the suite to have *actually run*.

---

## GATE 1 — FULL-SERVICE TEST ENTRY

**Criteria:** all required scope is defined; required creative assets/screens and technical paths are implemented to testable acceptance criteria; test environment/data/accounts are ready; critical safety guards are verified; no unresolved blocker prevents complete required coverage.

### 1.1 Required scope defined — **NOT MET**

| Item | Status | Evidence |
|---|---|---|
| Release-scope document naming exactly which services ship | **MISSING** | No file declares the release scope. `docs/northstar-phase1/25-testing-and-release-plan.md` is a plan, not a ratified scope; `NON_CREATIVE_REMAINING_WORK.md` defines a *non-creative* subset and explicitly excludes creative; `SERVICE_GAPS.md` defers 8 areas to owner decision. `docs/northstar-phase1/27-open-owner-decisions.md` remains open. |
| Product Designer Studio in or out of scope | **UNDECIDED** | Committed mid-audit (`f232ef8`), unaudited. |
| The Watch / RankLedger / RivalBoard retired or revived | **UNDECIDED** | Parked, unrouted legacy pages exist; owner decision A6 outstanding. |
| Canonical service names/aliases | **UNRESOLVED** | Six spec names have no UI presence (P2-10). |
| Approvals A1–A9 | **OUTSTANDING** | 9 approvals listed in `AUDIT_SUMMARY.md` §11, none granted. |

**Verdict: SCOPE PARTIALLY UNRESOLVED.** The non-creative suite has a defensible working scope; the creative/media cluster, Product Designer Studio and three parked services do not.

### 1.2 Creative assets/screens implemented to testable acceptance criteria — **NOT MET**

| Requirement | Status | Evidence |
|---|---|---|
| Every screen has testable acceptance criteria | **NOT MET** | No acceptance-criteria artifact exists per screen; `REQUIREMENTS_TRACEABILITY.csv` marks 22 of 45 requirements PARTIAL or worse. |
| Creative Studio / SocialPulse / Product Designer | **NOT MET** | Two are localStorage-only shells with no backend; Product Designer is unaudited. |
| Golden Goose evaluate surface | **NOT MET** | Deferred by design (P1-14). |
| Hardcoded metrics removed or labelled | **NOT MET** | P2-04, P2-05, P2-06. |
| Accessibility criteria | **NOT MET** | P2-08, P2-09; no a11y scan runs in any harness. |

### 1.3 Technical paths implemented to testable acceptance criteria — **NOT MET**

| Blocker | Status |
|---|---|
| Hosted reasoning route wiring (P0-02) | **OPEN** — 4 rooms' panels unreachable |
| Hosted API surface parity (P0-03) | **OPEN** |
| Live-call safety on GET (P0-01) | **OPEN** |
| AutothinK auth (P0-04) | **OPEN** |
| Error-honesty contract (P1-01) | **OPEN** |

### 1.4 Test environment / data / accounts ready — **NOT MET**

| Item | Status | Evidence |
|---|---|---|
| Isolated test accounts for all 6 roles | **NOT READY** | Only unauthenticated was exercised. `verify-live-signin.cjs` **BLOCKED** — no `NS_TEST_EMAIL`/`NS_TEST_PASSWORD`. |
| Isolated DB with seeded fixtures | **PARTIAL** | Local SQLite works, but `data/scanner-search-cache.json` is in three inconsistent states (P1-12). |
| Deterministic suite | **NOT READY** | 9 Python failures + 1 Node failure; order-dependent env pollution (P1-11). |
| Preview/browser harness for new panels | **NOT READY** | No harness coverage for the hosted-reasoning panels. |
| Stable repository | **NOT READY** | P0-05 — concurrent commit + active scans during the audit. |

### 1.5 Critical safety guards verified — **NOT MET**

| Guard | Status | Evidence |
|---|---|---|
| Zero live calls on GET | **FAILS in this environment** | 19 connects on `GET /api/kirkland/scanner` (`evidence/live-call-attribution.txt`) |
| Provider presence never ≠ authorization | **HELD** | `reasoning_provider` fail-closed; `cloud_live_armed` requires an explicit flag |
| Authenticated API boundary | **FAILS** | `/api/autothink/*` unauthenticated |
| Write-path authorization | **HELD** | `WRITE_PATH_AUTHORIZATION.md`; destructive beta-ops controls disabled |
| Secret hygiene | **HELD** | No credential value surfaced by the audit; adapters read presence only |

---

## GATE 1 VERDICT: **NOT READY**

Four of five criteria fail outright; the fifth (scope) is partially unresolved. Three P0 defects are independently reproducible, and one of them was reproduced *by this audit's own read-only sweep*.

---

## GATE 2 — RELEASE EXIT

**Criteria:** the approved full-service suite has actually run; required cases pass; critical/high-severity release blockers are closed; evidence, operational readiness and required approvals are complete.

| Criterion | Status | Evidence |
|---|---|---|
| The approved full-service suite has actually run | **NOT TESTED** | No case from `FULL_SERVICE_TEST_PLAN.md` tier B, C or D has been executed. Tier A is 1 of 28 executed (A-18). |
| Required cases pass | **NOT TESTED** | 12 failures currently exist across 5,000+ tests. |
| Critical/high-severity release blockers closed | **NOT MET** | 5 P0 + 22 P1 open; 28 items flagged `blocks_release` in `PENDING_WORK.csv`. |
| Evidence complete | **NOT MET** | `00_STATE.json` baseline stale (2026-09-22); readiness docs contradict the code; no screenshots from this audit. |
| Operational readiness | **NOT MET** | P1-05 (no worker), P1-07 (lint stub), P2-19 (no scanning), P2-20 (no backup), P0-03 (hosted parity). |
| Required approvals complete | **NOT MET** | A1–A9 outstanding. |

---

## GATE 2 VERDICT: **NOT TESTED** (not "failed")

The suite has not been run, so it cannot be said to have passed or failed release-exit.

---

## Blocking dependency chain (shortest path to Gate 1)

```
P0-05 (freeze/re-baseline the repo)
  └─ P0-01 (SCANNER_LIVE_ALLOWED decision) ──────┐
  └─ P0-02 (reasoning route wiring) ─────────────┼─► A-01..A-24 (tier A) ─► A7 (test accounts)
  └─ P0-03 (hosted surface decision) ────────────┘                                │
  └─ P0-04 (AutothinK auth)                                                       ▼
                                                                      B-01..B-14 (tier B)
                                                                            │
                                              A4/A5/A1/A6/A8 (named live approvals)
                                                                            ▼
                                                              C-01..C-07 (tier C)
                                                                            │
                                                          production approval
                                                                            ▼
                                                              D-01..D-05 (tier D) ─► GATE 2
```

Parallel, non-blocking work that should proceed regardless: P1-10, P1-11, P1-12 (deterministic suite), P1-02, P1-13, P2-16, P2-17, P3-* hygiene.

---

## Explicit non-findings (recorded so they are not "fixed" by assumption)

- **No performance verdict is given.** No approved performance target exists in the repo. This is recorded as a missing requirement (P3-08), not as a pass or a failure.
- **No live hosted or cloud model call was made.** The only real completion verified was local Ollama. The hosted lane is untested, not failing-at-inference.
- **No authenticated journey was exercised.** All auth-gated findings are code- and live-probe-derived, not session-derived.
- **No browser visual inspection was performed by this audit.** Creative findings are code-derived; visual confirmation remains.
