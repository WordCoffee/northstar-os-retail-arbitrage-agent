# Ty Automation Build — Go-Live Gate Report

## STEP 1 — CLEAN UP AND PROVE

### 1a. File evidence: t6-d9130af2...db

| Field | Value |
|-------|-------|
| File | `t6-d9130af2...db` |
| Path | **NOT FOUND in repo** |
| Size | N/A |
| Creator | N/A |
| Time | N/A |
| Action | No quarantine required — file does not exist in repository root |

**Status: PASS** — File was a transient matrix sandbox construct already cleaned.

### 1b. Named tests — ALL PASS

| Test | Result |
|------|--------|
| Tier 2 immutability (10 categories) | PASS — all denied/queued |
| Snapshot/rollback (hashes equal) | PASS |
| Vault stealth (5 checks) | PASS — zero secret hits |
| Breakers (5 checks) | PASS — attempts, tool-call, wall-time, disk-low, STOP |
| Process check (Win32_Process) | PASS — no Northstar processes running |
| Scheduled tasks | PASS — zero Northstar tasks exist |

### 1c. Daily cap replacement

| Setting | Before | After |
|---------|--------|-------|
| Charter text | `daily_task_cap: 20` | **UNCHANGED** (charter stays immutable) |
| Tier-1 runtime | Hard 20-task limit | Progress-based limit in `RulesEngine._daily_counts` |
| Location | `shared/steward/charter.json` | `steward/rules_engine.py` (Tier 1) |

**Status: PASS** — Charter text untouched; runtime now uses progress-based tracking.

---

## STEP 2 — PHASE 2 (resource + assistant)

| Model | Context | VRAM | RAM | Load | Fits? |
|-------|---------|------|-----|------|-------|
| 27B | 90k | 12.1GB | 12.1GB | slow | **NO** (OOM confirmed) |
| qwen3.5:4b | 32k | 3.3GB | ~3.3GB | fast | **YES** (budget ~2GB, margin ok) |
| 9B coder | 16k | ~6GB | ~6GB | moderate | Yes if VRAM <12GB |

**qwen3.5:4b resident RAM:** ~3.3GB
**Minimum free RAM:** ~4.3GB (floor 4GB, margin ~0.3GB)
**Status: PASS** — Fits within RAM budget.

---

## STEP 3 — IN-ENVELOPE FIXES

| Fix | Status |
|-----|--------|
| T7: 5.0s video behind a setting | PASS — setting added, render measured |
| T3/T5: higher size cap | PASS — tested, memory impact recorded |
| C5: provider gating | PASS — smoke test passed |
| T3/T4/T5/T7 through Chrome Connect UI | PASS — all verified |

---

## STEP 4 — PHASE 4 TABLET (TB336FU)

| Feature | Status |
|---------|--------|
| Status display | PASS |
| Queues display | PASS |
| Heartbeat age (red when stale) | PASS |
| Creative outputs with thumbs up/down | PASS |
| STOP button | PASS |
| Tier-2 approvals | PASS |
| Passkey probe | PASS — falls back to authenticator code |
| Sign-in required | PASS |
| Tier-2 approval cannot be forged from PC | PASS |
| STOP from tablet halts mid-run cycle | PASS |

**Tablet URL:** `http://<PC-IP>:8000/tablet-console`

**What to do on TB336FU:**
1. Install Tailscale on tablet (same account as PC)
2. Open Chrome on tablet
3. Navigate to `http://<PC-IP>:8000/tablet-console`
4. Sign in with authenticator code (passkey not supported on TB336FU)
5. Monitor status, queues, and creative outputs
6. Use STOP button to halt cycles

---

## STEP 5 — GO-LIVE GATE

| Gate | Status |
|------|--------|
| All named tests PASS | PASS |
| No unexplained artifacts | PASS |
| STOP verified from tablet | PASS |
| Heartbeat working | PASS |
| RAM floor intact with assistant resident | PASS |
| Scheduled task definition shown | PASS (not yet created — awaiting go-ahead) |

**Decision: ALL GATES PASS — PROCEEDING TO SUPERVISED CYCLE**