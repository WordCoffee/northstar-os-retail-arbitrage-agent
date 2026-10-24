# NorthstarOS Master Build Plan — Addendum (resume patch, 2026-09-28)

Apply these edits to `docs/NORTHSTAROS_MASTER_BUILD_PLAN.md` before resuming. They resolve the five open items from the last stop and close four gaps found on review. Do not renumber existing cards; insert new ones as noted.

---

## 1. PART 2 — Routing decision (fix conflict)

Replace the "Routing" row:

| Decision | Choice | Reason |
|---|---|---|
| Routing | Move from `HashRouter` to `BrowserRouter`, **base path `/ui`** | Needed for SEO and shareable links; keeps domain root free for the Phase 12 marketing site. |

## 2. P2-T3 — Base path (replace text)

**P2-T3 BrowserRouter migration.** Replace `HashRouter` with `BrowserRouter`; **base path `/ui`**; SPA fallback in `ui_serving.py` and Caddy; update deep links, `CommandPalette`, `RoomTabs`, and all absolute hrefs. Accept: all four harnesses pass with path routing; **direct load of `/ui/golden-goose` works.**

## 3. New card — P0-T4 Env sanity check

**P0-T4 Env sanity check.** Parse the root `.env` (and any per-service `.env` files) for syntax hazards: unquoted values containing spaces, `$`, `#`, or unescaped quotes; duplicate keys; keys referenced in code but absent from `.env.example`. Report line numbers and hazard type only — **never print values**. Write findings to `docs/ENV_SANITY_REPORT.md`. This does not fix the file; the owner fixes it. Accept: report generated; card does not block on a hazard, it only surfaces it.

## 4. New env var — harness address (insert under P1-T1)

Add before P1-T1's Accept line:

Introduce `HARNESS_BASE_URL` (env var, default unchanged / current hardcoded value) and point all four harnesses plus the backend invite/auth suites at it. Set the working default to the verified Caddy stack at `http://127.0.0.1/ui/`, which already has SPA fallback behavior. Do not investigate, stop, or kill any other process bound to a port (e.g. port 8104) — the harness no longer depends on it once this var is wired.

## 5. P1-T1 — Baseline count (replace line)

Replace:
> Costco plain suite (191)

With:
> Costco plain suite (owner-reconciled count as of last run: 217 — **before accepting 217 as the new baseline, confirm via `docs/BUILD_STATE.md` history that the delta from 191 to 217 excludes every frozen Bright Data test**; if any frozen test is included in that delta, treat the count as unverified and re-run excluding them.)

## 6. P0-T3 — Self-approval (replace text)

**P0-T3 Constitution diff.** Read the Constitution and list every rule this plan touches (Owner Test Mode, live provider arming, self-approval, ChromeConnect scope). Write `docs/PLAN_CONSTITUTION_CHECK.md`. For **self-approval** specifically: do not resolve this silently. Draft a narrow amendment proposal — *"In Owner Test Mode only, when `ENVIRONMENT != production_tenant` and principal role is `internal_platform_admin`, the same principal may hold both the requesting and approving role for approvals scoped to test-mode audit trail entries. This does not apply outside test mode and does not weaken the rule that a score alone never yields `PURCHASE_READY`."* — and print it as an `ASK OWNER` block with options: (A) adopt this amendment, (B) keep self-approval fully disabled in test mode, (C) other wording. **Default if silent: B (disabled).** Accept: file lists each item as COMPATIBLE or NEEDS-AMENDMENT; self-approval is explicitly NEEDS-AMENDMENT pending owner reply, never silently enabled.

## 7. P3-T2 — Self-approval bypass (replace bullet)

Replace the self-approval bullet:
> Self-approval: gated behind `NORTHSTAR_OWNER_SELF_APPROVAL` (default `0`/off). Only flips to `1` after the owner answers the P0-T3 ASK OWNER block with option A. While off, the owner's approvals still require a second actor even in test mode, and this is tested explicitly.

## 8. New sub-step — Part 1.2 Resume protocol

Add to Part 1.2 (Working style):

**Resume protocol.** At the start of any session, read `docs/BUILD_STATE.md` top to bottom before touching code. If the last entry's STATUS is `BLOCKED` with an `ASK OWNER` block, check for owner answers in this addendum or the kickoff prompt first — do not re-print the same `ASK OWNER` block if it's already answered here. Resume at the card listed under "NEXT"; do not re-run cards already marked DONE with a recorded commit hash.

---

# PART 5 — KICKOFF PROMPT (revised, paste this to resume)

```
Read docs/NORTHSTAROS_MASTER_BUILD_PLAN.md and its ADDENDUM (docs/NORTHSTAROS_PLAN_ADDENDUM.md) and adopt both as binding, addendum taking precedence on any conflict. Read docs/BUILD_STATE.md and resume at the card listed under NEXT — do not restart from P0-T1 if prior cards are marked DONE with commit hashes.

Owner answers to prior open items, already resolved, do not re-ask:
- Base path: /ui (per addendum). Acceptance test is direct load of /ui/golden-goose.
- Harness target: use HARNESS_BASE_URL env var, default http://127.0.0.1/ui/. Do not touch, inspect, or kill any process on port 8104 or any other port not covered by this var.
- Root .env line 98: owner is fixing this manually outside this session. Do not attempt to edit .env values. Run P0-T4 (env sanity check) but only report hazards, never print values.
- Self-approval: keep NORTHSTAR_OWNER_SELF_APPROVAL=0 (disabled) until I explicitly reply with option A to the P0-T3 ASK OWNER block. Print that block once if not already printed, then continue with other unblocked cards.
- Costco test count: before treating 217 as the new baseline, verify the 191-to-217 delta excludes every frozen Bright Data test per docs/BUILD_STATE.md history. Report this verification explicitly in the next REPORT FORMAT block.

Print only the REPORT FORMAT after each card. Use ASK OWNER blocks for anything else missing. Use the ChromeConnect SIGN-IN GATE on every site with an account. Do not skip a card's Accept line. Do not touch frozen files. Begin.
```
