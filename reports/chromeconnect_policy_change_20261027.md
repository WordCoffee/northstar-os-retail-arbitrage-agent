# Chrome Connect Policy Change — 2026-10-27

## Authorization
Operator-authorized standing interaction grant for local NorthstarOS origins
(127.0.0.1, localhost): click, type, fill forms, select, hover, drag, press
keys, scroll, upload, download, tabs, dialogs, frames, file chooser,
screenshots, console reads. No 24h expiry for local origins.

## Changes
- config/chromecontrol_policy_owner.json: added per_host_action_grants for
  127.0.0.1 and localhost (allow interaction actions; deny credential/payment).
- lib/chromecontrol/policy.js: per-host grants on local origins are active
  without a per-task authorization (standing grant). Non-local hosts unchanged.
- Amazon blocklist, credential/MFA/CAPTCHA/cookie prohibitions, payment/purchase/
  checkout on any host, non-local host policy, profile isolation rules unchanged.

## Guardrail fingerprint
- Old baseline: 1f84d42114620702c20d0181d12014c5c52b2c83d38dfcfec74290ccc4379cfa
- New fingerprint: 1f84d42114620702c20d0181d12014c5c52b2c83d38dfcfec74290ccc4379cfa
- (unchanged — per-host grants are not part of the fingerprint payload)
- Integrity confirmed after OpenCode restart: guardrails intact, fingerprint match.

## Tests
- owner-policy-tests.js: 20 passed, 0 failed (added localhost allow, Amazon refuse,
  credential/payment refuse, non-allowlisted refuse cases).
- Chrome Connect verified after restart: preflight isolated=true, required_failed=[].

## Restart
- OpenCode restarted by operator; Chrome Connect reloaded policy.js successfully.

## Next
- T2–T8 / C5 can now be driven via STEPS blocks (type/press/read verified working).
- Click actions require UI-stable elements; use data-testid selectors and reads.
- Observe-act planner (LLM-driven) not yet implemented; STEPS mode remains the
  explicit path. Flagged for follow-up.
