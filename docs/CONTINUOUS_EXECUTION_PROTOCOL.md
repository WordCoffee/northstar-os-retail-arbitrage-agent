# CONTINUOUS EXECUTION PROTOCOL (binding workflow)

Adopted 2026-09-29. This governs *workflow only*; it does not expand scope or
grant spending, infrastructure, browser, data, deployment, purchase, or
communication permissions. Authority order: `docs/OPERATING_CONSTITUTION.md`
wins, then AGENTS.md, master plan + addenda, this protocol.

## Loop
1. Read checkpoint (`docs/BUILD_STATE.md`, `00_STATE.json`). 2. Inspect git
status. 3. Select next eligible card. 4. Identify acceptance/deps. 5. Inspect
implementation. 6. Implement a bounded slice. 7. Run tests. 8. Fix safe
regressions. 9. Update evidence/state. 10. Commit only that card's files.
11. Print REPORT FORMAT. 12. Continue to the next eligible card — a card report
is not a stop.

## Never
Reopen DONE cards without evidence; invent features; skip acceptance; claim a
room works from route existence alone; treat test counts as real-data coverage;
ask "should I continue?" while authorized safe work remains; infer approval from
silence; run background loops/artificial load/unlimited retries.

## Preservation (always)
Frozen files; auth + tenant isolation; truth labels + SAMPLE isolation; Owner
Test Mode environment allowlist (development/test only) + self-approval disabled;
provider registration/arming/rate-limit/spend controls; no SP-API; no automated
Seller Central/Amazon-domain access; no Amazon ChromeConnect scanning; no paid
infra/trial credits; no unauthorized email/purchase/account creation/side effect.

## Owner-action queue
Durable queue in `docs/BUILD_STATE.md` (Owner Action Queue) + `00_STATE.json`
(`owner_action_queue`). Statuses: OPEN / ANSWERED / VERIFIED / DEFERRED /
CANCELLED (not card statuses). Ask when an action becomes useful, not only when
local work is exhausted; do not re-ask unanswered/deferred items every card; do
not infer approval from silence; never request secrets in chat.

## Reporting
REPORT FORMAT only; card statuses DONE/PARTIAL/BLOCKED. At a genuine stop, final
visible content is REPORT FORMAT with status, evidence, commits, remaining work,
pending owner-action IDs, and exact resume point.

## Stop rules
Owner must answer a blocking question with no safe alternative work; permission
pending; Constitution conflict; unresolvable failure; approved plan complete; or
a real tool/session limit. Do not label an ordinary completed card "budget
exhausted". Before a session-limit stop: finish/abandon the atomic op safely,
preserve work (never force-commit broken code), record dirty files, exact next
steps + test commands, pending owner actions, next card, then REPORT FORMAT and
say: Reply "continue" to resume from the saved checkpoint.

## Resume
On "continue": read this protocol + state, verify repo state, resume
automatically; no newly authored prompt required.
