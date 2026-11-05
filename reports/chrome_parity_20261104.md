# Chrome Connect — six-point parity harness

**Date:** 2026-11-04 · **Contract:** `chrome_parity/v1`
**Harness:** `tools/chrome_parity_harness.py` (tests: `Northstar_backend/test_chrome_parity_harness.py`, 31 passed)
**Report:** `reports/chrome_parity_20261104.json`
**Controller measured:** `C:\Users\T2Hol\OneDrive\Documents\Default Project`

## Verdict

```
1. Host policy + hardcoded Amazon blocklist, evaluated first: VERIFIED
2. Profile 6 lease (exact directory); every other profile refused: VERIFIED
3. Credentials / CAPTCHA / login are stops, never automated: VERIFIED
4. Policy re-checked against the current URL after every action: VERIFIED
5. Audit journal records decisions, tool calls and results: VERIFIED
6. Browser-brain benchmark runs and measures: VERIFIED

OVERALL: PASS  (6 verified, 0 failed, 0 not_verified)
```

This closes the condition in `reports/v3_readiness_20261104.md` §5: the six properties
that a replacement would have to reproduce are now **measured**, not asserted. It does
**not** retire Chrome Connect — a passing parity report removes an objection, it does not
create a replacement.

## What each point measured

| # | Point | Evidence it was decided on |
|---|---|---|
| 1 | Host policy + Amazon first | `config/chromecontrol_policy_owner.json` is `host_policy: "denylist"`; the hardcoded blocklist has **26** entries; `policy.evaluateUrl()` refuses `amazon.com`, `amazon.co.uk`, `amazon.de`, `sellercentral.amazon.com` **and** the lookalike `amazon.co.uk.evil.example`, every one with `reason: "amazon_prohibited"`; an ordinary host (`example.org`) is allowed; in `evaluateUrl` the Amazon branch sits at offset **250**, the denylist branch at **1049** and the allowlist branch at **1929**, so no option can precede it. `assertGuardrailsIntact()` → `intact: true`; live fingerprint `46308c9b…49d5` equals the owner-recorded baseline. |
| 2 | Profile 6 lease | `owner_authorization.profile_directory = "Profile 6"` (owner, 2026-10-27), config pin agrees (`pin_matches: true`). `profile-isolation.verifyIsolation()` run offline with injected Local State: a **Profile 6** expectation passes the `profile_lease_valid` gate; the same call with a **Profile 7** expectation **fails** it. The code still carries `leaseDir === expectedDirectory`, `pin_matches !== false`, `selected_directory_exact`. |
| 3 | Credential / CAPTCHA / login stops | All nine required classes are in `prohibited_actions` (no missing entries). The squarespace grant allows `form_submission` but **denies** `sign_in`, `credential_entry`, `payment_action`. `agent-loop.js` still stops on `login_wall` and CAPTCHA with `owner_action_required`. The controller's own `test/denied-action-test.js` ran and exited **0**. |
| 4 | Redirect re-check | `pw-tool.js` evaluates policy against the **CURRENT page URL** before each action, and `agent-loop.js` re-evaluates after every action (“a redirect may have moved us”), so a redirect cannot smuggle an action onto a refused host. The live policy still refuses an Amazon URL at call time. |
| 5 | Audit journal | The real `journal.js` was exercised in a throwaway `NORTHSTAR_AGENT_JOURNAL_DIR`: it wrote `decision`, `tool_call` and `tool_result` records with strictly increasing `seq`, ISO timestamps and URLs; a supplied `password` value and a `Bearer …` header were **redacted** in the written file. The live journal dir holds real run files (2026-11-02 → 2026-11-05). |
| 6 | Browser benchmark | The repo's AI loop replayed a fixture end-to-end (`success: true`, 2 steps) and the recorded live bench artifact (`chromeconnect_3.0_complete_20261027.md`) reports `pass_rate = 0.667`. |

Corroborating live controller status (read-only, same session):
`isolated_profile.profile_lease_valid = true`, `profile_dir = "Profile 6"`,
`selection_source = "config_pin"`, guardrail fingerprint matches baseline,
`amazon_blocklist_size = 26`, `policy_mode = default`.

## How it fails

The harness is fail-closed by construction:

* every point returns `verified | failed | not_verified`;
* `not_verified` is what a missing input produces — a controller that cannot be
  found, node absent, a probe that timed out. It is **never** a pass;
* the overall verdict is `pass` only when all six are `verified`;
* an explicitly supplied `--root` that is not a controller returns
  `controller_not_found` rather than silently measuring a different deployment.

Run it again with:

```
python tools/chrome_parity_harness.py                 # human summary
python tools/chrome_parity_harness.py --strict        # non-zero unless pass
python tools/chrome_parity_harness.py --root <path>   # another deployment
```

## Known drift in the controller's own suites (not a parity failure)

Four of the controller's legacy test files still encode the **pre-2026-10-28 allowlist
contract**, so they fail *because* the owner's denylist directive is in force:

| Suite | Result | Cause |
|---|---|---|
| `test/owner-policy-tests.js` | 1 fail | asserts “non-allowlisted host refused”; denylist mode intentionally allows it |
| `test/chromecontrol-tests.js` | 2 fail | “non-allowlisted blocked”, service mapping now `open_web` |
| `test/sourcing-policy-tests.js` | 12 fail | allowlist-era isolation expectations |
| `test/agent-loop-tests.js` | fails | expects a `cc-isolated-01` profile lease; only Profile 6 is authorized |

`run-tests.js --no-browser` (15/15), `denied-action-test.js`, `mcp-session-tests.js`
(27/27), `orchestrator-tests.js` (63), `rendered-state-tests.js` (12) and
`profile-resolve-tests.js` (10) are green.

Those stale suites were **not** edited: they live outside this repo, and rewriting
guardrail tests from here would be exactly the kind of quiet loosening the constitution
forbids. They are recorded so that whoever builds the replacement knows it will inherit
four suites that need reconciling with the denylist directive before they mean anything.
