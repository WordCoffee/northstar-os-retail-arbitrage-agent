# Public-Discovery Phase — Policy Approval Applied (2026-10-04)

**Operator policy decision (this phase):** for PUBLIC, NO-SIGN-IN, READ-ONLY
supplier discovery only, reclassify `no_sensitive_session_cookies` from REQUIRED
to SUPPORTING_ONLY. Not approval to inspect cookie metadata, cookies, storage,
tokens, credentials, or account state — all remain inaccessible.

## Implemented

| File | Change |
|---|---|
| `lib/chromecontrol/profile-isolation.js` | `policy_mode = public_discovery_readonly` ⇒ `no_sensitive_session_cookies` is SUPPORTING_ONLY (non-blocking); otherwise REQUIRED. Cookie store stays unreadable (UNKNOWN). All other gates stay REQUIRED. |
| `lib/chromecontrol/rendered-state.js` (new) | `assessRenderedState()` reads ONLY rendered URL/title/text; any sign-in/account/profile/inbox/orders/payment/dashboard/supplier-message/saved-item/authenticated-session indicator ⇒ `POSSIBLE_AUTHENTICATED_STATE` (STOP). Never clicks; never claims signed-out. |
| `lib/chromecontrol/agent-loop.js` | Public-discovery safeguard: pre-navigation + post-action rendered-state assessment; stop with `possible_authenticated_state`; audit note (url, timestamp, action, rendered_state, source_type, stop_condition); trace records rendered state. |
| `lib/chromecontrol/pw-tool.js` | Public-discovery URL evaluation defers to the already-approved `public_sourcing_readonly_v1` policy (search engines/registries/unclassified) when the commerce allowlist would refuse. **No origin added**; markets/Amazon/social/email/payment/login still denied. |
| `scripts/chromecontrol-playwright-bridge.js` | `policy_mode` plumbed into `runVerifyIsolation`; binding probe now establishes the session and re-reads child/nonce/answered. |
| `scripts/chromecontrol-mcp-server.js` | Binds the operator's pinned selection before a run and before preflight verification (binding alone never passes). |
| `scripts/public-discovery-run.js` (new) | Bounded read-only discovery runner (bind → warmup → verify → search/read). |
| `test/rendered-state-tests.js` (new), `test/sourcing-policy-tests.js` | Safeguard + reclassification tests. |

`opencode.jsonc` env: `CHROMECONNECT_PUBLIC_DISCOVERY=1` (this approved phase).

## Safeguards (all active)

- Before every target-site navigation and after every action, assess rendered page
  state only; any auth indicator ⇒ STOP `POSSIBLE_AUTHENTICATED_STATE`.
- No account/chat/RFQ/contact/sample/order/cart/checkout/download/form controls.
- Only public search, navigation, read, screenshot, structured extraction.
- Transport binding, profile selection, Chrome signed-out, no-profile-fallback
  remain REQUIRED.
- Site-authentication evidence stays UNKNOWN unless rendered public page state
  supports a narrower observation.
- Audit: URL, timestamp, action, rendered-state result, source type, stop condition.

## Tests

`sourcing-policy-tests.js` 45/0 · `rendered-state-tests.js` 8/0 ·
`chromecontrol-tests.js` 58/0 · `orchestrator-tests.js` 63/0 ·
`agent-loop-tests.js` 145/145 · `mcp-session-tests.js` 27/27 ·
`run-tests.js --no-browser` 15/0 · `preflight-validation.js` 21/21.

## Live status

- **Fresh live preflight: isolation VERIFIED** in public-discovery mode
  (`transport_profile_binding` VERIFIED; nonce `3c9c43731cb347ba`, child 36240;
  all 7 required checks passed; cookie evidence SUPPORTING_ONLY / UNKNOWN).
- **Discovery blocked at run time:** the first attempts were REFUSED
  (`isolated_profile_required`) because the Playwright extension relay had dropped
  (no relay process; the Profile 7 extension status tab closed). Zero pages opened,
  zero observations.
- The discovery runner is in a warm-up window waiting for the extension to
  reconnect; it will run the two turmeric queries as soon as the session binds.

**Remaining action:** keep the Playwright extension connected in the Profile 7
window during the run window. No supplier was contacted; nothing was downloaded,
sampled, carted, checked out, or changed.