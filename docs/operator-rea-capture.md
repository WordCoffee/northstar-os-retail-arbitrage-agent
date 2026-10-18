# Operator-window REA capture (Packify first)

**Module:** `Northstar_backend/operator_rea_capture.py`
**Status:** harness built + tested (V4.1 Step 3). **Live capture is operator-gated.**

This is the operator-facing protocol for harvesting competitor UI *states* through
Chrome Connect and filing them as agent memory. It is deliberately a *guardrail*
document: the harness refuses to do anything unless the operator has explicitly
authorized it.

---

## The rule (unchanged, non-negotiable)

- **Chrome Connect is the controller. Playwright is only its tool.** No script,
  agent or manual call may drive Playwright directly. `tools/chromeconnect_guard.py`
  makes `import playwright` and a raw CDP attach on port 9222 fail loudly unless the
  controller issued the instruction.
- **Read-only.** Observe DOM structure (node names/roles, no values), a component
  inventory, value-free JSON body shapes and WebSocket frame inventory. **Never**
  click, type, submit a form, run `Runtime.evaluate`, enter credentials, solve a
  CAPTCHA or bypass a login. Stop at any login/consent/CAPTCHA/rate-limit boundary.
- **The operator owns the host allowlist.** The harness never edits it. An
  unauthorized host is refused with the real reason.

## Two operator decisions are required before any live capture

1. **Authorize the host in the allowlist.** The operator-owned policy file is
   `config/chromecontrol_policy_owner.json` (loaded by the controller's
   `lib/chromecontrol/policy.js`). Add the target host (e.g. `www.packify.ai`) there.
   Until then every target reports `allowlist=unknown` and every capture is
   `BLOCKED`. *This harness does not create or edit that file.*
2. **Be present, and grant a per-task authorization.** Authorizations are per task
   and expire in **at most 24 hours**.

## Procedure (operator window)

```powershell
# 0. From Northstar_backend — show the plan and the current allowlist status (no browser):
python operator_rea_capture.py
python operator_rea_capture.py packify_photoshoot   # dry-run plan (BLOCKED until allowlisted)

# 1. The model (via the chromeconnect_* tools) performs the read-only capture.
#    - chromeconnect_preflight, then chromeconnect_run with the task text from
#      plan_capture(); review chromeconnect_journal afterwards.

# 2. The model files the result into agent memory through the harness:
#    operator_rea_capture.ingest_capture(db, target_id=..., payload=<Chrome Connect result>,
#                                        authorization=<per-task auth>, account_id=<account>)
```

`run_capture(target_id, authorization=..., policy=..., dry_run=False, controller=...)`
is the single live entry point. It:
1. requires a valid, unexpired per-task authorization,
2. requires the host to be `allowed` in the operator policy,
3. hands the ready **read-only** task to the controller (`chromeconnect_guard.cc_call`),
4. returns `BLOCKED` with a concrete reason otherwise — never a simulated capture.

Safe default: `dry_run=True` (nothing is launched).

## Targets

| id | host | captures |
|---|---|---|
| `packify_app_shell` | www.packify.ai | dom_outline, component_inventory, json_body_shapes |
| `packify_photoshoot` | www.packify.ai | dom_outline, json_body_shapes, websocket_frames, screenshot |
| `packify_mockup` | www.packify.ai | dom_outline, json_body_shapes, websocket_frames |
| `packify_deep_agents` | www.packify.ai | dom_outline, json_body_shapes, websocket_frames |

> **Honesty note.** Packify.ai is a packaging-design tool. Its surfaces are captured
> as UI *structure*. A "listing/inventory"-style panel is only captured if the
> operator's own screen actually shows one. A different host (e.g. an Amazon seller
> surface) needs its own allowlist entry and is out of scope for this harness.

## Redaction

Every capture is redacted before it is stored: URLs lose their userinfo and entire
query string, and token-shaped `key=value` pairs (including `X-Amz-*`,
`Signature=`, `Bearer …`, `api_key`, `access_token`, `session_id`, `password`) have
their **values** scrubbed. Body shapes are value-free by construction. Nothing
credential-shaped is ever written to memory.
