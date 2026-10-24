# OA-1 — Oracle Console Read-Only Inspection (re-check)

- **When:** 2026-09-30T08:00Z
- **Operator scope:** `OA-1` / `DEPLOY-F2` — read-only, no cloud/IAM/DNS/billing changes
- **Outcome:** **STOPPED — `SELECTED_PROFILE_VERIFICATION_PENDING`**

## 1. Dispatch note (owner said "enable browser")

Owner selected the **selection-aware Playwright bridge** when asked which browser to enable.

- Project `opencode.jsonc` → `mcp.playwright` = `node "…\Default Project\scripts\chromecontrol-mcp.js"`, `enabled: true` — **already enabled; no change made**.
- Global `C:\Users\T2Hol\.config\opencode\opencode.json` → `mcp.browser` (command `npx -y @playwright/mcp@latest --browser chrome --user-data-dir …\chrome-t2`) left `enabled: false`. It was **not** enabled (it launches the separate unsigned-in `chrome-t2` profile, forbidden by this task).

## 2. Live connection verification

| Check | Method | Result |
|---|---|---|
| Playwright extension MCP responds | `tools.playwright.browser_tabs {action:"list"}` | **Connected** — one tab only |
| Tabs visible to the live connection | same | `0 (current) [Playwright Extension Status](chrome-extension://mmlmfjhmonkocbjadbfplnigmagldckm/status.html)` |
| Oracle Cloud Console tab present | same | **NO** |
| OS windows | `Get-Process chrome \| where MainWindowTitle` | single visible window: **"Playwright Extension Status - Google Chrome" (PID 60444)**; no Oracle/Cloud/Console window |
| Desktop browser toolset | `tools.browser.tabs.list()` | disconnected (`browser.disconnected`) — separate toolset, not used |
| Chrome process | `Win32_Process` cmdline | one browser process `60444 --profile-picker --no-first-run --no-default-browser-check` (shared by all profiles; cmdline cannot identify profile) |

**No second browser was opened, no profile switched, `chrome-t2` was not used, Chrome was not restarted.**

## 3. Profile verification — **PENDING** (step 2 stop)

The task requires the live connection to be **Work / Profile 6**. It could not be verified, therefore I stopped before step 3/4, as instructed.

- Live tab evidence exposes **no safe profile identifier** (the extension status page carries no profile id).
- OS process command lines **cannot** identify the active profile (Chrome runs one browser process for all profiles in the same user-data dir); `--profile-picker` was the de-elevated chooser launch, not a profile pin.
- Saved config is **not** proof: `config/chromecontrol.json` is `attach_mode=extension`, `extension_profile_dir_name=null` (**unpinned**).
- Live ChromeConnect status (`node scripts/chromecontrol.js status`, read-only): `State = awaiting_extension_connection`, `Selected profile = unverified`, `Connected profile = unverified`, `Playwright extension = awaiting approval`, `Picker = picker_not_confirmed`, `Target service = oracle`, `Target auth state = unknown`.

**Profile probe attempt:** navigating the connected tab to `chrome://version` to read the profile path was blocked by Playwright (`Detached while handling command`; target fell to `about:blank`). The tab was **restored** to the extension status URL. Result: still no verifiable profile.

→ Reported **PENDING** (not `VERIFIED`, not `MISMATCH`).

## 4. Oracle signed-in state — **UNKNOWN**

No Oracle tab exists in the live connection, so signed-in state could not be confirmed. Per step 3 I did **not** inspect passwords, MFA prompts, tokens, cookies, recovery data, identity documents, or payment details.

## 5. Non-secret tenancy / region facts

Nothing could be observed from a live console. All are **UNKNOWN**:

| Fact | Value |
|---|---|
| Tenancy display name | UNKNOWN |
| Tenancy OCID | UNKNOWN (also sensitive-class: presence only would be recorded, never the full value) |
| Home region | UNKNOWN |
| Current selected region | UNKNOWN (the two must be distinguished once observable) |
| Account tier / trial status | UNKNOWN |
| Always Free eligibility labels | UNKNOWN |
| Compute / block / object / network limits & usage | UNKNOWN |
| Existing compartment / VCN suitable for Northstar | UNKNOWN |
| Capacity / quota / account restrictions | UNKNOWN |

## 6. Always Free & cost evidence

- **No console labels or links were observable** (no console session available). Any claim of "$0" is **unverified**.
- Reference constraint to confirm in-console later (Oracle documentation; **not** observed this session): Oracle states Always Free compute eligibility is indicated in the console, and certain Always Free compute resources must reside in the tenancy's **home region**. Confirm the exact eligibility badge at provisioning time.
- **Do not treat temporary trial credits as permanent Always Free eligibility** — the two are distinct; the packet below requires an explicit console eligibility label, not a credit balance.

## 7. Proposed deployment approval packet — **PROPOSAL ONLY** (blocked on console facts)

Grounded in the project's existing `DEPLOY-F1` artifacts (`docker-compose.hosted.yml`, `deploy/images.lock` linux/arm64, `Caddyfile`, `deploy/backup.sh`/`restore.sh`). **Nothing below is approved or created.**

| Item | Proposal | Always Free basis | Status |
|---|---|---|---|
| Compute | 1× Ampere A1 (ARM64) VM, within Always Free A1 allotment (≤ 4 OCPU / 24 GB total) | Always Free Ampere A1 | eligibility **UNVERIFIED** |
| Image | `ns-api-arm64:f1` + `ns-ui-arm64:f1` (existing arm64 builds) | — | emulated build only; real ARM runtime PENDING (F5) |
| Boot/block storage | within Always Free block-volume total (≤ 200 GB); size to be set | Always Free block storage | **UNVERIFIED** |
| Object storage | only if needed for backups, within Always Free allotment (≤ 20 GB) | Always Free object storage | **UNVERIFIED** |
| Networking | 1 VCN + subnet; **only** Caddy publishes 80/443; api/postgres/worker/scheduler/migrate publish nothing (matches `tests/test_hosted_compose.py`) | Always Free VCN/egress | **UNVERIFIED** |
| Region | **home region** (Always Free compute constraint), exact region TBD | — | UNKNOWN |
| Compartment | new dedicated compartment (e.g. `northstar-beta`) unless an existing suitable one is found | — | UNKNOWN |
| Hostname/HTTPS | neutral free hostname (DuckDNS candidate) + Caddy auto-TLS | — | owner login required (F4) |
| Estimated charges | **$0** claimed only if console shows Always Free eligibility badges and no paid SKU is selected; **cannot be truly confirmed** without the console | — | **cannot confirm zero** |
| Rollback | tear down via OCI console/CLI to the exact created resource list; restore DB from `deploy/backup.sh` snapshot; no permanent data loss | — | plan only |

**Deployment still gated:** no resources exist; `DEPLOY-F2/F3` remain BLOCKED.

## 8. Explicit confirmation — no changes occurred

Confirmed: **no cloud resource was created or changed; no home region selected or changed; no IAM, DNS, or billing change; no billing info added; no account upgrade; no trial credits spent; no terms accepted; no external communication sent; no Amazon action.** No credentials/MFA/tokens/cookies were read, printed, or stored. The only observable state change was the incidental tab navigation probe (restored).

## 9. State / artifacts

- `00_STATE.json` history entry appended: `oa1_oracle_readonly_recheck` (2026-09-30T08:00Z).
- Durable ChromeConnect run `oracle-20260930T003129Z` preserved (state `awaiting_extension_connection`).
- This report: `reports/oa1_oracle_readonly_recheck_20260930T0800Z.md`.

---

```
CARD: OA-1  STATUS: BLOCKED
CHANGED: reports/oa1_oracle_readonly_recheck_20260930T0800Z.md; 00_STATE.json (history entry)
TESTS: tools.playwright.browser_tabs list -> 1 tab (extension status only; no Oracle tab); tools.browser.tabs.list -> browser.disconnected; node scripts/chromecontrol.js status -> awaiting_extension_connection / selected=unverified / connected=unverified
COMMIT: none
ASSUMPTIONS LOGGED: 0
NEXT: OA-1 — re-run after owner opens the signed-in Oracle Console tab in the Work / Profile 6 window with the Playwright extension attached there
BLOCKERS: ASK OWNER — Oracle Console tab absent from the live browser; Work/Profile 6 cannot be verified by any non-secret live evidence
```
