# FULL_SERVICE_TEST_PLAN — executable, gated by safety tier

**Audit date:** 2026-10-08 · **Baseline commit:** `2482048` (audit start; `f232ef8` landed during the audit — re-verify all Product Designer cases)
**Purpose:** cover the *entire intended release*, not a few working pages. 54 cases across 4 tiers.

## Classification tiers

| Tier | Meaning | Cost / side-effect | Approval |
|---|---|---|---|
| **A** | Safe local / cache-only. No provider, no money, isolated data. | none | none |
| **B** | Staging with isolated data and isolated accounts. | none external | test accounts + isolated DB |
| **C** | Separately approved **live integration** (one bounded call each). | metered provider spend | fresh named operator approval per case |
| **D** | **Production smoke** checks. | production reads only | explicit production approval |

Current status of every case: **NOT RUN** or **BLOCKED**. Nothing below was executed against tier C or D.

---

## TIER A — Safe local / cache-only (28 cases)

Preconditions: `cd Northstar_backend`, `python -m uvicorn main:app --host 127.0.0.1 --port 8017`; SPA `npm --prefix northstar-os-ui run preview` (8101); `$env:NORTHSTAR_DISABLE_RATE_LIMIT="1"` for harness runs only.

| ID | Linked req/backlog | Service & journey | Role / env | Preconditions & fixtures | Steps | Expected UI / API / persistence / job | Negative variant | Evidence | Cleanup | Side-effect class | Approval | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A-01 | R56 / P1-07 | Build integrity — SPA production build | CI-equivalent, local | clean checkout | `npm run build` | 0 errors; module count recorded | introduce a syntax error → non-zero exit | `evidence/build-output.txt` | none | none | none | NOT RUN |
| A-02 | R52 / P2-08 | Accessibility sweep over all routed screens | automated, local preview | preview server on 8101 | run an axe-style scan over each of the 51 routes | 0 critical violations; current count recorded | remove a label → violation reported | scan report | none | none | none | NOT RUN |
| A-03 | R21 / P2-03,P2-04,P2-05 | Dead-control and static audit across all rooms | automated, local | source tree | assert no button lacks an onClick; assert no `.meter-fill` width is a literal; assert every displayed count equals its row count | 0 violations | seed a dead button → reported | static report | none | none | none | NOT RUN |
| A-04 | R48 / P1-06 | SourceScout honesty | operator, local preview | backend running; stop backend for the negative case | load `/product-finder`; then stop the backend and reload | with the backend: rows from `/api/sourcescout` + a DataNotice on every subview; without: an honest "unavailable", never sample numbers | backend down → unavailable | screenshots + network log | none | none | none | **BLOCKED by P1-06** |
| A-05 | R07 / P1-01 | Noncreative read honesty under DB failure | operator, local | backend + a deliberately broken DB path | force `_rows` to raise; call all 8 `/api/v1/noncreative/*` | a distinguishable `unavailable` payload, never `[]` | healthy DB → real counts | API response capture | restore DB | none | none | **BLOCKED by P1-01** |
| A-06 | R12 / P0-01 | Zero live calls on a GET (all endpoints) | automated, local | instrumented socket probe; `SCANNER_LIVE_ALLOWED` non-opt-in | sweep all 210 GETs from `/openapi.json` | **0** non-loopback connects | none permitted | `evidence/live-call-attribution.txt` | none | none | **A1** | **BLOCKED by P0-01** |
| A-07 | R40 / P0-01 | Live gate enforcement | automated, local | env with `SCANNER_LIVE_ALLOWED` unset | `live_gate.live_enabled()` false; `search_products()` returns `[]` with 0 connects | 0 connects, `[]`, no error flag | set to `1` → refusal to boot per new guard | probe output | none | none | **A1** | **BLOCKED by P0-01** |
| A-08 | R35 / P0-02 | UI-to-openapi mapping completeness | automated, local | backend + SPA source | extract every URL from `signals.js` and `foundation/api.js`; diff against `/openapi.json` | 0 missing routes | none | mapping report | none | none | none | **BLOCKED by P0-02** |
| A-09 | R35 / P1-22 | `GET /api/v1/foundation/jobs` | automated, local | backend | call it | 405 documented as removed, or a working list | none | probe output | none | none | none | **BLOCKED by P1-22** |
| A-10 | R52 / P1-11 | Test isolation / hermeticity | automated, local | full suite | run `pytest test_provider_seller_probe.py tests/test_reasoning_routes.py` then the full suite twice, in different orders | identical results, no order dependence | reordered run differs → flagged | suite outputs | none | none | none | **BLOCKED by P1-11** |
| A-11 | R52 / P1-12 | Protected-artifact fixture restore | automated, local | git available | run the full suite; hash all fixture-protected artifacts before and after | byte-identical; the three hashes for `scanner-search-cache.json` converge | corrupt the file → restored | hash report | restore | none | none | **BLOCKED by P1-12** |
| A-12 | R52 / P1-10 | Route-table gate invariant | automated, local | `App.jsx` + gate test | run `test_v3_shell_invariants` | green with a documented, current route count | add a route without updating the assertion → fails | suite output | none | none | none | **BLOCKED by P1-10** |
| A-13 | R49 / P1-04 | Migration drift refusal | automated, local | SQLite foundation DB | run `foundation_migrate.py` twice, then mutate a migration file's bytes | second run is a no-op; the mutated run refuses on checksum drift | drift → refusal | command output | restore migration | none | none | **BLOCKED by P1-04** |
| A-14 | R38 / P1-05 | Scheduler tick with a worker | automated, local | local stack with a worker thread | create a `keyword_import` schedule; advance one tick | a durable job is enqueued within the misfire window with a claim recorded | disable the worker → nothing enqueued and visible in queue-posture | queue-posture response | delete the schedule | none | none | **BLOCKED by P1-05** |
| A-15 | R38 / P1-05 | Worker failure liveness | automated, local | forced failing handler | inject a failing handler; run one tick | the failure is visible in queue-posture and logs, not swallowed | healthy handler → no noise | queue-posture + logs | remove the handler | none | none | **BLOCKED by P1-05** |
| A-16 | R26 / S03 | Golden Goose persisted round-trip | automated, local | foundation SQLite + org scope | submit → queue → review → decide, org A and org B | org B cannot see org A's item or decision (401/404, audited as denied) | cross-org attempt → denied and audited | API responses + audit rows | delete test orgs | none | none | PASS candidate (needs re-run) |
| A-17 | R11 / S12 | Canonical economics — unknown-is-not-zero | automated, local | backend | POST `/economics/compute` with all-unknown inputs | `null`/UNKNOWN outputs; no confident margin from unknown fees | zero fee input → flagged as missing basis | API response | none | none | none | PASS candidate (needs re-run) |
| A-18 | R30 / AT-04 | AutothinK local lane end-to-end | automated, local | Ollama running | run the local probe from `TEST_RESULTS.md` §8 | a real completion, `northstar-qwen3:rev1`, honest reason on failure | stop Ollama → `[LOCAL FALLBACK]` | probe output | none | none | none | PASS (already verified) |
| A-19 | R30 / AT-01 | AutothinK hosted lane route wiring | automated, local | backend | call the exact 5 URLs the UI uses | 200 with a catalog (not 404) | unverified model → typed `ModelNotUsableError` | probe output | none | none | none | **BLOCKED by P0-02** |
| A-20 | R30 / AT-03 | Hosted reasoning posture consistency | automated, local | backend + root `.env` | compare `/api/v1/reasoning/models` against the intended armed state in `.env` | they agree, or the divergence is reported at startup | mismatch → startup log warning | probe + log | none | none | **A1** | **BLOCKED by P1-08** |
| A-21 | R30 / AT-02 | AutothinK auth boundary | automated, local | backend, no session | `GET /api/autothink/history` and `POST /api/autothink/run` without a session | 401 on both | with a session → scoped history only | probe output | none | none | **A3** | **BLOCKED by P0-04** |
| A-22 | R30 / AT-05 | AutothinK metering | automated, local | mocked provider | run twice, then resubmit the same idempotency key | exactly one usage event; the duplicate returns the original result | duplicate without a key → two events (documented as a gap) | ledger query | clear the test ledger | none | none | **A5** | **BLOCKED by P1-16** |
| A-23 | R30 / AT-06 | AutothinK tenant isolation | automated, local | two orgs | run a query in org A, then read history as org B | org B sees none of org A's entries | cross-org read → denied and audited | API responses + audit | delete test entries | none | none | **A3** | **BLOCKED by P1-17** |
| A-24 | R30 / AT-07 | AutothinK cancellation and resumability | automated, local | durable job integration | submit a long run; cancel mid-flight; resubmit the same key | a durable job id; cancel reaches a terminal state; resubmission returns the original result | unreachable model → typed failure, no partial state | job audit trail | delete the job | none | none | none | **BLOCKED by P1-18** |
| A-25 | R37 / S16 | Full-suite regression | automated, local | full suite | run the full pytest suite + all 6 Node harnesses | 0 failures | any failure → triaged and owned before tier B | suite outputs | restore fixtures | none | none | none | **BLOCKED by P1-10/11/12** |
| A-26 | R13 / P1-02 | Adapter registry completeness | automated, local | backend | remove one adapter module; boot | a startup warning and a visible entry in `/health/detailed` | healthy boot → no warnings | startup log | restore module | none | none | none | **BLOCKED by P1-02** |
| A-27 | R50 / P2-22 | `/reference` static surface | automated, local | backend, no session | `GET /reference/<internal-doc>` | 401/404 for internal docs; operator docs still reachable | allowlisted doc → 200 | probe output | none | none | none | **BLOCKED by P2-22** |
| A-28 | R44 / P1-08,P2-18 | Environment parseability | automated, local | root `.env` | `python -m dotenv -q .env`; assert 0 warnings; assert the documented precedence rule with a unit test | clean parse; the precedence test passes | malformed line → reported | command output | restore `.env` | none | none | none | **BLOCKED by P1-08/P2-18** |

---

## TIER B — Staging with isolated data and accounts (14 cases)

Preconditions: isolated staging DB (SQLite or Postgres), seeded test orgs/users, `NS_TEST_EMAIL`/`NS_TEST_PASSWORD` (approval A7), a staging build served through Caddy. **No real customer data.**

| ID | Linked req/backlog | Service & journey | Role / env | Preconditions & fixtures | Steps | Expected UI / API / persistence / job | Negative variant | Evidence | Cleanup | Side-effect | Approval | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| B-01 | R3 / P0-03 | Hosted stack API parity | unauthenticated + operator, staging | staging stack via `docker compose` | `GET /health /health/detailed /api/v1/status /api/sourcescout /api/autothink/models /api/v1/reasoning/models /api/v1/noncreative/commerce-ops/queue` through Caddy | all 200; identical to the local surface | a route that only exists locally → reported | curl output | none | none | **A2** | **BLOCKED by P0-03** |
| B-02 | R22 / S19 | Invite acceptance → login → onboarding | invited-not-activated → subscriber, staging | an issued invite; a test mailbox | accept the invite, set credentials, complete onboarding and workspace setup | session established; onboarding checklist advances; audit rows written | an expired/revoked invite is refused | screenshots + audit rows | delete the test org/user | none | **A7** | **BLOCKED by A7** |
| B-03 | R22 / S19 | Customer entitlement and plan usage | subscriber, staging | a subscriber on each of the 4 plans | open `/plan` and `/account` | usage and entitlements come from the ledger, not literals; the 68%/$299 literals are gone | a plan with 0 usage → honest zero | screenshots + API | reset the org | none | **A7** | **BLOCKED by P2-06, A7** |
| B-04 | R22 / S18 | Beta-ops admin lifecycle | platform_admin, staging | a test org | issue an invite, grant, change plan, suspend, resume, export CSV | every write is audited and role-gated; destructive controls confirmed | a non-admin → 401 and an audited denial | screenshots + audit rows | delete the org | none | **A7** | **BLOCKED by A7** |
| B-05 | R50 / S18 | Cross-workspace access attempt | subscriber of org A, staging | two orgs | call org B's object URLs directly | 401/404, audited as denied | none permitted | server log + audit | none | none | **A7** | **BLOCKED by A7** |
| B-06 | R22 / S02,S03 | Research → review → decision journey | operator, staging | cached scanner data + a foundation stack | browse SourceScout, open a candidate, run a Golden Goose review, persist a decision | cached data labelled cached; the decision persists and is org-scoped | empty cache → honest empty, never sample | screenshots + API | delete the decision | none | **A7** | **BLOCKED by P1-06, A7** |
| B-07 | R41 / P1-14 | Golden Goose 10-gate evaluate | operator, staging | a complete gate set | submit the 10-gate input; then submit an incomplete set | a persisted decision with reasons; the incomplete submission is refused with the missing gates named | none permitted | API + UI | delete the decision | none | **A7** | **BLOCKED by P1-14, A7** |
| B-08 | R22 / S19 | Support ticket lifecycle | subscriber, staging | a test account | create a ticket, reply, triage as admin | state transitions persist; triage is audited and admin-only | a subscriber calling triage → 401 | screenshots + audit | delete the ticket | none | **A7** | **BLOCKED by A7** |
| B-09 | R34 / P2-13 | Recovery and reacceptance | subscriber, staging | a test account | request recovery; reaccept terms; record legal acceptance | each path persists an audited record and is reflected in the customer surfaces | an invalid token → refused | screenshots + audit | delete the account | none | **A7** | **BLOCKED by P2-13, A7** |
| B-10 | R22 / S16 | AutothinK customer journey | subscriber, staging | a local or hosted lane available | open `/autothink`, run a research task, review history and output | provider-gated honest state; history scoped to the org; usage recorded | no provider → honest fallback, not a fabrication | screenshots + API + ledger | clear the test entries | none | **A7** | **BLOCKED by P0-02/P0-04, A7** |
| B-11 | R22 / S13 | Spreadsheet Lab round-trip | operator, staging | a fixture CSV with deliberate anomalies | upload, parse, analyze, export | the export matches the parse; anomalies and warnings are reported; the analysis route resolves | malformed CSV → typed error, no silent empty | files + API | delete the exports | none | **A7** | **BLOCKED by P0-02, A7** |
| B-12 | R20 / S15 | Monitoring states | operator, staging | a forced 5xx | induce 5xx; observe the dashboard and the alert | the 5xx rate and breach state are live; delivery works only if P1-20 is done (otherwise honestly disabled) | healthy window → within threshold | screenshots + tracker | restart the tracker | none | **A7** | **BLOCKED by P1-20, A7** |
| B-13 | R47 / P2-20 | Backup and restore drill | platform operator, staging | a nightly backup | restore into a fresh DB; compare row counts and `integrity_check` | byte-comparable restore within the retention window | corrupted backup → detected | drill log | drop the restored DB | none | none | **BLOCKED by P2-20** |
| B-14 | R45 / P2-19 | Dependency and secret scan | CI, staging | seeded vulnerable dep + a seeded fake secret | run the scan | both flagged with a documented baseline | clean tree → no findings | scan report | remove the seeds | none | **A8** (tool choice) | **BLOCKED by P2-19** |

---

## TIER C — Separately approved live integration (7 cases)

Each requires a **fresh, named operator approval** naming the exact endpoint, model, ASIN or provider, and a cost cap. One bounded call each. No retries. No fallbacks.

| ID | Linked req/backlog | What is exercised | Exact approval needed | Cap | Expected | Result |
|---|---|---|---|---|---|---|
| C-01 | AT-01, P0-02, A4 | One hosted OpenCode Go completion (`step-5-preview-free`, free tier) through `/api/v1/reasoning/run` | Written approval naming the model, endpoint and single call | 1 call, max_tokens=8 | HTTP 200 with the model id echoed; provenance recorded | **BLOCKED** — pending P0-02 + approval A4 |
| C-02 | R30, AT-05, A5 | One OpenRouter cloud completion | Written approval naming the provider, model and a USD cap | ≤ $0.10, no retries, no fallbacks | Usage recorded in the ledger with the estimate | **BLOCKED** — pending A5 |
| C-03 | R6, R12, A1 | One explicit live scanner refresh (`POST /api/kirkland/refresh`) | Written approval naming the keyword, page count and provider | e.g. 1 keyword × 1 page | The refresh path works when explicitly enabled while the GET path stays at 0 connects | **BLOCKED** — pending A1 |
| C-04 | R42, S03 | One Costco catalog detail refresh on a single item | Written approval naming the item id and provider | 1 item | A typed result; 403 classified as `auth_error`, never `not_found` | **BLOCKED** — pending approval |
| C-05 | R9, R42, S03 | One invoice-readiness evaluation on a real sourcing document | Written approval naming the document and the evaluation | 1 document | An evidence-backed eligibility verdict with UNKNOWNs preserved | **BLOCKED** — pending approval + document access |
| C-06 | R31-R33, A6 | One SP-API read to validate Watch/RankLedger/RivalBoard feasibility | Written approval naming the API, operation and scope | 1 call | A documented feasibility verdict, or confirmation the services stay parked | **BLOCKED** — pending A6 |
| C-07 | R22, S19 | One real transactional email (invite delivery) | Written approval naming the recipient (a test mailbox) and provider | 1 email | The invite code is delivered and the status is honest | **BLOCKED** — pending A7/provider decision |

---

## TIER D — Production smoke checks requiring approval (5 cases)

Read-only against production. Each requires explicit production approval and a rollback plan.

| ID | Linked req/backlog | What is checked | Approval | Expected | Result |
|---|---|---|---|---|---|
| D-01 | R3, P0-03 | Production API surface parity | A2 + production approval | All 210 routes resolve; `/health` and `/health/detailed` reachable through the edge | **BLOCKED** |
| D-02 | P0-04, A3 | Production auth posture | A3 + production approval | `/api/autothink/*` requires a session; `/api/v1/foundation/*` 401s unauthenticated | **BLOCKED** |
| D-03 | P0-01, A1 | Production live-call audit | A1 + production approval | Instrumented sweep of production GETs shows 0 provider connects | **BLOCKED** |
| D-04 | R44 | Production observability | production approval | Structured logs, request ids, error-rate telemetry, and the audit trail are all present and actionable | **BLOCKED** |
| D-05 | R47, P2-20 | Production backup/restore evidence | production approval | A restorable backup inside the retention window, verified in a drill | **BLOCKED** |

---

## Coverage ledger (explicit)

| Dimension | Discovered | Covered by this plan | Executed now |
|---|---|---|---|
| Routes discovered vs inspected | 51 SPA routes / 210 API routes | 51 / 210 (tier A-06 sweep) | 51 static / 32 GET live / 6 harness routes |
| Required journeys vs exercised | 10 journey classes | 10 | 2 (build + local AutothinK lane) |
| APIs mapped vs tested | 210 (96 UI-relevant) | 96 + 210 sweep | 32 live |
| AutothinK capabilities discovered vs verified | 19 applicable | 19 (tier A-18..A-24, C-01, C-02) | 1 (local lane) |
| Creative surfaces required vs reviewed | 3 creative rooms + 19 routed screens | 3 + 19 (code-level) + browser sweep in A-02/A-04 | 0 browser-level |
| Roles: unauthenticated / invitee / subscriber / operator / admin / unauthorized | 6 | 6 (tier B) | 1 (unauthenticated) |

---

## Gate reminders

- **Eligibility to begin testing ≠ a successful release.** Passing tier A and B means the suite *can* be tested; it does not mean it is ready to ship.
- Tier C and D cases must never be run to "make progress" on a backlog item. A blocked case is reported as blocked with the exact approval needed.
- Any exception requires explicit documented owner acceptance.
