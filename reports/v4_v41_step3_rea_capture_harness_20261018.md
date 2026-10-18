# V4.1 Step 3 — Operator-Window REA Capture Harness (Packify first)

**Date:** 2026-10-18
**Branch:** `feature/v4.1-mesh`
**Scope:** Step 3 of the V4.1 plan — "live DOM event capture hooks and operators for
Chrome Connect (`operator_rea_capture.py`), harvesting UI states to feed agent memory."

All local-only. Nothing pushed. No credential read, printed or committed. No browser
was driven and no live capture was run.

---

## 1. What was built

| File | Change |
|---|---|
| `Northstar_backend/operator_rea_capture.py` | **NEW** — the operator-gated REA capture harness. |
| `Northstar_backend/test_operator_rea_capture.py` | **NEW** — 21 offline tests. |
| `docs/operator-rea-capture.md` | **NEW** — the operator protocol + the two required decisions. |
| `NORTHSTAR_V3_MASTER_PLAN.md` | Roadmap item 8 updated (harness BUILT; live capture gated). |
| `00_STATE.json` | `current_phase` entry prepended. |

### Design — it is a *guardrail*, not a driver

The harness **never drives a browser**. It validates the operator gate, builds a
strictly read-only observation task, and hands that task to the controller
(`chromeconnect_guard.cc_call`) — or returns a plan for the model's `chromeconnect_*`
tools. Direct Playwright use is refused by the existing Python guard.

- **Operator gate.** `plan_capture` requires a live, per-task operator authorization
  (TTL capped at 24 h) *and* the host to be `allowed` in the operator-owned policy.
- **Allowlist is operator-owned.** `host_allowed()` only *reads*
  `config/chromecontrol_policy_owner.json`; it never writes it. A missing policy →
  `unknown` → refused.
- **Read-only task text.** Explicitly forbids clicks, input, form submits, script
  evaluation and any credential/CAPTCHA/login handling; stops at those boundaries.
- **Safe live default.** `run_capture(..., dry_run=True)` plans and calls nothing. A
  live call requires `dry_run=False` **and** authorization **and** an allowlisted host
  **and** an available controller — otherwise it returns `BLOCKED` with the real reason.
- **Redaction before storage.** URLs lose userinfo and the whole query string; token
  `key=value` **values** are scrubbed (`X-Amz-*`, `Signature=`, `Bearer …`, `api_key`,
  `access_token`, `session_id`, `password`). Body shapes are value-free by construction.
- **Feeds agent memory.** `ingest_capture()` writes a value-free summary to
  `memory_entries` (`entry_type="rea_capture"`, provenance `read_only: true`,
  `source_kind: chrome_connect_passive`).

### Targets (Packify first)

`packify_app_shell`, `packify_photoshoot`, `packify_mockup`, `packify_deep_agents`
on `www.packify.ai`.

> Honesty note carried in the code + doc: Packify.ai is a packaging-design tool. Its
> surfaces are captured as UI *structure*; a "listing/inventory"-style panel is only
> captured if the operator's own screen shows one.

## 2. Evidence (real, reproducible)

| Check | Result |
|---|---|
| `python -m pytest test_operator_rea_capture.py -q` | **21 passed, 0 failed** |
| Harness CLI (`python operator_rea_capture.py packify_photoshoot`) | honest `BLOCKED` — see below |

Covered by the suite: operator gate (missing/expired authorization), allowlist gate
(absent / refused / wildcard / allowed), TTL cap, dry-run default calls **nothing**,
live path calls the controller **exactly once** with the read-only task, blocked path
**never** calls the controller, no-controller → `BLOCKED controller_not_found`,
URL/text redaction, value-free summary, and memory ingestion with provenance.

CLI against the current machine (no policy file present):

```
operator policy present: False (MISSING)
- packify_photoshoot  host=www.packify.ai  allowlist=unknown
{ "ok": false, "status": "BLOCKED", "reason": "host_not_allowlisted",
  "detail": "the operator-owned policy file was not found (chromecontrol_policy_owner.json);
             no host may be assumed permitted. ..." }
```

That refusal is the correct, honest result — the harness does not assume Packify is
permitted.

## 3. Blockers surfaced (batched, once) — operator decisions

Live Packify capture is **operator-gated** and needs:

1. **An allowlist entry.** `config/chromecontrol_policy_owner.json` is absent on this
   machine, so every target reports `allowlist=unknown` and every capture is
   `BLOCKED`. Per the constitution, *the agent may edit the allowlist only when the
   operator explicitly authorizes it for the current task, and must log it in a
   dedicated commit* — so this harness left it untouched. **Operator decision needed.**
2. **An operator window** with Chrome Connect live and the operator signed in to
   Packify (the model drives the `chromeconnect_*` tools; the harness files the
   result). This matches the standing "operator-window REA captures (Packify first)"
   item.

Neither is a code blocker; the harness is complete and tested behind the gate.

## 4. Not done (out of scope, honest)

- No live capture was run (no operator window / no allowlist entry).
- No chat tool or HTTP route was added for the harness — it is a module + CLI seam the
  model drives during an operator session. Wiring an operator-console route is a
  follow-up if desired.
