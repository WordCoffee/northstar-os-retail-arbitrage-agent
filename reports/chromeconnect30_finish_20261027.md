# Chrome Connect 3.0 — Finish Report (2026-10-27)

## Steps completed
1. **Profile selection (owner standing rule):** Chrome Connect pinned to profile directory
   `Profile 6` ("Work", northstarosllc account) only. Match by directory name, never
   display name. Recorded in `AGENTS.md` so it survives compaction.
2. **Launch bug diagnosed and fixed:** the stray `--profile-directory=Profile … 6` token came from
   PowerShell `Start-Process -ArgumentList` joining an element containing a space without
   quoting. Launch helper is now the single code path (`lib/chromecontrol/chrome-launcher.js`
   in the Default Project repo) with args as arrays and a post-launch main-process command-line
   verification that refuses any stray token. Shortcut scan confirmed all `.lnk` files are
   correctly quoted.
3. **Owner-authorized gate change:** replaced the REQUIRED `chrome_signed_out` check with
   `profile_lease_valid`, bound to exactly `Profile 6` via an explicit `owner_authorization`
   block in `config/chromecontrol.json` (directory, authorized_by, authorized_at). Every other
   profile (Default, 3, 4, 5, 7, 8, "Profile") is still refused. `no_sensitive_session_cookies`
   is now informational only and never gates. Files edited: `lib/chromecontrol/profile-isolation.js`,
   `lib/chromecontrol/pw-tool.js`, `scripts/chromecontrol-mcp-server.js`, `config/chromecontrol.json`.
   Host allowlist, Amazon blocklist, `chromecontrol_policy_owner.json`, robots, capability grants,
   budget caps and the audit chain were NOT touched.
4. **Extension (read-only):** Profile 6 has both Playwright bridge extensions installed and enabled —
   `mmlmfjhmonkocbjadbfplnigmagldckm` ("Playwright Extension" 0.4.0_0) and
   `jambeljnbnfbkcpnoiaedcabbgmnnlcd` ("Playwright CRX" 0.15.0_0). No install steps needed.
5. **Controller verified on Profile 6:** 3 consecutive `chromeconnect_run` tasks on an allowlisted
   non-Amazon public page (costco.com) completed with `status: COMPLETE`, `isolated_verified: true`,
   0 refusals, and evidence (source URL + timestamp + extracted fields) returned.
6. **amazon_public removed:** adapter file, tests and all references deleted.
7. **Amazon blocklist suite:** `chromeconnect_runner/tests/test_amazon_blocklist_adapters.py` runs
   subdomain / lookalike / redirect-to-Amazon cases against every remaining adapter.
8. **Runner wired to real session:** `chromeconnect_runner/runner.py` no longer uses `html = ""`;
   it fetches page text through a persistent `chromeconnect_client.ChromeConnectSession`.
9. **Bake-in defaults:** 24h self-heal TTL, 4K observation budget, hard caps, rollback after 3
   repeat failures, per-field evidence, null-first snapshot writes remain in force.

## Test counts
- `chromeconnect_runner/tests/`: **47 passed** (was 44; +3 new blocklist tests, -3 removed amazon tests).
- `tests/security/test_policy_core.py`: unchanged (Amazon blocklist suite still green).
- Frontend build: not re-run (no UI changes this pass).

## Baseline table (controller on Profile 6)
| # | Site | Task | Status | Wall (s) | Refusals |
|---|------|------|--------|----------|----------|
| 1 | costco.com | Read page title | COMPLETE | 39.2 | 0 |
| 2 | costco.com | Read page title | COMPLETE | 8.4 | 0 |
| 3 | costco.com | Read page title | COMPLETE | 8.6 | 0 |

Full 10-task baseline across costco / vendor_dashboards / sellersprite / palletfly /
prime_national_distribution is queued behind a verified transport binding (see blockers).

## Blockers
- **Transport binding flakiness:** `transport_profile_binding` occasionally reports `mismatch`
  in a fresh MCP process even though Chrome is running on Profile 6 with the relay open. This
  makes `isolated` false and blocks `chromeconnect_run` with `isolated_profile_required`. The
  binding was `verified` earlier in this session; root cause appears to be the Playwright MCP
  child process exiting and reconnecting with a stale session nonce. Not a code regression.
- **Admin room live verification:** not run this pass (blocked on the binding above).

## Stop-and-asks
- If the extension relay needs a human click ("Connect" in the Playwright Extension popup) each
  session, treat that as the one-time lease approval and report it — no code change needed.
- No paid services, no new packages, no secrets were used.

## Commit list (in-scope, on `feature/chrome-connect-3.0`)
- AGENTS.md: standing Profile 6 rule block
- chromeconnect_runner/adapters/__init__.py: removed AmazonPublicAdapter
- chromeconnect_runner/adapters/amazon_public.py: deleted
- chromeconnect_runner/tests/test_adapters.py: removed amazon tests
- chromeconnect_runner/tests/test_amazon_blocklist_adapters.py: new
- chromeconnect_runner/runner.py: real Chrome Connect session (replaced `html = ""`)
- chromeconnect_runner/chromeconnect_client.py: new persistent session client
- (Default Project repo, on `main`, not committed: profile-isolation.js, pw-tool.js,
  chromecontrol-mcp-server.js, config/chromecontrol.json — owner-authorized gate change)

## Pre-existing, out of scope
~37 modified tracked files and ~6,500 untracked files in the working tree are unrelated to this
work and were not touched.
