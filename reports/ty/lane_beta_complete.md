# Lane G — the four private-beta services now have real Bojo handlers

Date: 2026-11-11 · Builder lane G · repo `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`

## What the gap actually was

`ty/scorecards.json` scored `beta`, `beta-signup`, `beta-support` and `beta-ops` at
`complete = 0.0`. The scorecard's evidence line was **"no Bojo tool declared, so Bojo
cannot drive it"** (not "declared with no handler"), and `ty/services.json` confirmed it:
all four carried `tools: []`, and `ty/service_registry.json` recorded
`bojo_tool = {name: "none", status: "none"}` with a reason.

So the question was not "wire a handler for a name that exists" but **"does each of these
four services actually have an action Bojo could perform?"** The answer, measured against
the backend, was yes for all four — each room already has a Foundation service behind an
HTTP route, and no chat tool reached any of them:

| service | what the back end already does | route |
|---|---|---|
| `beta` | `SupportService.onboarding_status` + `PlanUsageService.view` | `GET /api/v1/foundation/onboarding`, `GET /api/v1/foundation/plan-usage` |
| `beta-support` | `SupportService.submit_ticket` / `list_tickets` | `POST/GET /api/v1/foundation/support/tickets` |
| `beta-signup` | `InviteService.signup` (invite-gated, non-revealing) | `POST /api/v1/foundation/signup` |
| `beta-ops` | `TesterDashboard.list_orgs` (platform admin only) | `GET /api/v1/foundation/admin/dashboard` |

Nobody needed a "corrected" registry entry: declaring `none` for these four was the thing
that was wrong. All four are wired, and each handler calls the same service object the HTTP
route calls — no second implementation, no stub returning `{}`.

## Before / after (measured, not asserted)

`git show HEAD:ty/scorecards.json` vs the regenerated `ty/scorecards.json`:

| service | score | ranked gap | `complete` | weakest dimension after |
|---|---|---|---|---|
| `beta` | 74.7 → **88.5** | 9.3 → **0.0** | 0.0 → **100.0** | `contract` (0) |
| `beta-signup` | 74.7 → **88.5** | 8.2 → **0.0** | 0.0 → **100.0** | `contract` (0) |
| `beta-ops` | 74.7 → **88.5** | 4.1 → **0.0** | 0.0 → **100.0** | `contract` (0) |
| `beta-support` | 63.2 → **77.0** | 10.9 → **4.0** | 0.0 → **100.0** | `measured` (0) |
| **total** | — | **32.5 → 4.0** | — | — |

`at_bar` is unchanged at 4 of 29 (`hub`, `prospector`, `keyword-tracker`, `profitability`).
That is honest: the bar is "every dimension ≥ 85", and these four still carry two dimensions
that are not Bojo's to fix —

* `contract` = 0 because `state/contracts/service_contracts.json` still records
  `no_primary_action` (beta, beta-support) or `permission_denied` (beta-signup,
  beta-ops) from the last `tools/contract_check.py` run. Re-running the live contract check
  is a separate lane's command, not a Bojo wiring change.
* `measured` = 0 for **beta-support only**, because the route `'/beta#support'` is not a
  registered UI route (`tools/measured.py`). The support section is a hash anchor on the
  landing page; registering it is `northstar-os-ui/**`, outside this lane's write manifest.

No test was weakened and no threshold moved to make these numbers.

## What each handler does

All four live in one new module, `Northstar_backend/bojo_tools/foundation_ops.py`, registered
in `Northstar_backend/bojo_tools_registry.py:22`, with a chat spec each in
`Northstar_backend/chat_tools.py:2800-2841` through a ctx-aware adapter
(`_t_bojo_domain_ctx`, `chat_tools.py:2696`) and one-line model-facing summaries
(`_summarise`, `chat_tools.py:2723`).

### `beta` → `onboarding_status` (`foundation_ops.py:133`)

Reads the caller's own org: the nine-step onboarding checklist and the first step still owed
(`SupportService.onboarding_status`), plus the role-filtered plan view
(`PlanUsageService.view`, which itself restricts viewers/analysts). Read-only — it never
completes a step. Answer: `onboarding{completed, steps, checklist, next_step, outstanding}`
+ `plan`.

### `beta-support` → `submit_support_ticket` (`foundation_ops.py:172`)

Files one ticket on the org's real queue through `SupportService.submit_ticket`, which
validates category/severity/subject, writes the row, generates the `NS-XXXXXXXX` reference
and records the audit event. The handler then re-reads the stored row
(`get_ticket`) so the answer echoes what the queue holds rather than what was sent, and
returns the service's own "no secrets / no attachments" warning. Proven by a test that lists
the queue afterwards and finds exactly that ticket id.

### `beta-signup` → `redeem_invite` (`foundation_ops.py:222`)

Calls `InviteService.signup` — the same service behind `POST /api/v1/foundation/signup` —
creating the user, the membership and consuming the invite. All failures return the route's
single non-revealing denial (`signup_denied: signup is not available at this time`), so the
tool cannot be used to probe whether an address is invited. A test asserts the bad-code and
wrong-email denials are byte-identical.

### `beta-ops` → `beta_cohort` (`foundation_ops.py:257`)

Reads `TesterDashboard.list_orgs` (the `/admin/dashboard` view): organizations, lifecycle
state, tier, seats, jobs used, open/blocker tickets, flags. Platform-admin only; a
non-admin gets `permission_denied: the tester dashboard requires the internal platform admin
role`. `limit` is capped at 200.

## How identity reaches a tool (and why an argument cannot fake it)

`studio_account` gives the chat store only the **organization**. A support ticket has to be
attributed to a user and the tester dashboard needs a real role, so the turn now carries the
whole verified session:

* `chat_router.chat_identity` (`chat_router.py:1170`) does **one** `require_session`
  resolution and returns `{account_id, user}`; `create_turn` uses it for both the store scope
  and the turn.
* `turn_event_stream(..., identity=...)` (`chat_router.py:195`, `:1207`) puts that record in
  the tool `ctx` (`chat_router.py:513-519`).
* `foundation_ops._membership` (`:109`) takes the user+org from `ctx['identity']` and
  **re-reads the role from the Foundation `memberships` table**, the same doctrine as
  `foundation/api/deps.get_context` ("role and organization are always resolved from the
  database, never from headers or claims"). No active membership → refuse.
* Tool schemas carry no identity field, and `validate_tool_arguments` drops unknown keys, so
  a model that sends `user_id`/`role` cannot grant itself anything (test covers this).
* The store itself comes from `_foundation` (`:47`): injected state → the app's own
  `app.state.foundation` → the store named by `FOUNDATION_DB_PATH`/`DB_URL`. It never
  invents a throwaway database, because a write into a temp store would look like success.

`shell_focus.py:84` adds the four tools to the **Operate** focus (plus "auto"/"autothink",
which already offer everything), and `chat_tools.SERVICES` gains a `beta` service area so
`service_catalog` can tell the model these exist.

## Commands and real output

```
python -m tools.registry.repair_citations --check
  -> (no output)  EXIT=0

python -m tools.registry.build
  -> wrote ty\bojo_tool_list.json
     wrote ty\northstar_workspaces.json
     wrote ty\registry_gaps.json
     29 services · 48 tools (48 wired, 0 declared, 4 unclaimed) · gaps 13 · layouts
     {'feed': 9, 'split': 8, 'wizard': 5, 'board': 6, 'canvas': 1}  EXIT=0

python -m tools.registry.build --check
  -> registry, tool list, workspaces and gaps agree  EXIT=0

python tools/scorecards.py
  -> {"services": 29, "at_bar": 4, "top_gap": "offerchisel", "top_gap_score": 16.2}  EXIT=0
```

## Tests (pytest `-p no:cacheprovider`, basetemp under `%TEMP%\opencode`)

New: `Northstar_backend/test_beta_complete.py` — **21 passed**.

It asserts, per service: the tool is declared in `ty/services.json`, offered by
`chat_tools.tool_names()`, carries a callable handler, is a real `bojo_tools_registry`
handler, and that `tools.scorecards._wired_tools([tool])` returns `{tool: True}` with the
`complete` dimension at 100.0. Then every handler is driven through
`chat_tools.run_tool` against a real `FoundationState` on a temp SQLite path (checklist read,
ticket written and re-listed, invite redeemed and marked `used`, cohort read as platform
admin, cohort refused otherwise), plus the refusals (no identity, no membership in the
threaded org, identity injected as a tool argument, unknown category leaves the queue
empty) and one scripted `turn_event_stream` turn proving the verified session lands in
`ctx["identity"]`.

Related suites, all green:

| suite | result |
|---|---|
| `test_bojo_tools_registry, test_bojo_ops_tools, test_service_registry, test_scorecards, test_skill_warehouse, test_chat_tools_handlers, test_chat_tools_domain` | 91 passed |
| `test_chat_tools, test_chat_core, test_chat_router_intent, test_shell_modes, test_turn_contract, test_label_autochain` | 107 passed |
| `test_apply_label_tool_contract, test_autothink_transport, test_build_presets, test_canvas_edit_tool, test_chat_fork, test_chat_no_generation_guard, test_chat_plan, test_chat_tab_context, test_corpus, test_corpus_drift, test_creative_execute, test_creative_execute_artifact, test_creative_plan, test_plan_project_tool, test_purpose_commands, test_seo_learning, test_seo_listing, test_seo_ops, test_seo_profiles, test_tool_gateway, test_utility_apps, test_voicestudio_adapter` | 296 passed |
| `test_invite_flow, test_invite_flow_e2e, foundation/tests/test_1c06_gate` | 21 passed |

## Known red, not mine, unchanged

`Northstar_backend/test_tool_offering.py` is **already red before this change**: 8 failed,
21 passed, both before and after (identical failure list). It still lists the seven tools
wired by `reg-03` on 2026-11-10 (`build_dieline`, `compose_listing`, `margin_report`,
`plan_campaign`, `scan_products`, `track_keywords`, `watch_competitor`) as
"declared without handler", while `ty/bojo_tool_list.json` now reports them `wired` with 0
declared. That is a stale test against a newer truth, and fixing it is that lane's call —
I did not touch it, and I did not delete the assertion to make anything look green.

## Files touched (write manifest)

* `Northstar_backend/bojo_tools/foundation_ops.py` (new — the four handlers)
* `Northstar_backend/bojo_tools_registry.py` (+1 line: register the module)
* `Northstar_backend/chat_tools.py` (ctx-aware adapter, 4 specs, `beta` service area)
* `Northstar_backend/chat_router.py` (`chat_identity`, identity into the tool ctx)
* `Northstar_backend/shell_focus.py` (four tools in the Operate focus)
* `Northstar_backend/test_beta_complete.py` (new — 21 tests)
* `ty/services.json`, `ty/service_registry.json` (the four declarations)
* `ty/bojo_tool_list.json`, `ty/scorecards.json` (regenerated)
* `ty/TARGET_SPEC.md` (regenerated by the required `python tools/scorecards.py`)
* this report

Nothing under `northstar-os-ui/**`, `tools/seller_tester/**`, `tools/seller_scores.py`,
`docs/**`, `tools/registry/**` or other `reports/ty/*` was modified. No `git add`/`commit`.

## The one thing a verifier should re-run

```
python -m pytest Northstar_backend/test_beta_complete.py -p no:cacheprovider ^
  --basetemp "C:\Users\T2Hol\AppData\Local\Temp\opencode\verify_beta" -q
```

then `python tools/scorecards.py` and read `complete` for the four services — 100.0 with the
tool named in the evidence, not a bare number.
