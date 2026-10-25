# Batch 1 — test results (2026-10-24)

All times are local (UTC−4). Machine clock reports 2026-10-25 UTC, so the journal
filenames carry the 2026-10-25 date while the local batch date is 2026-10-24.

## Verdict

| Item | Status | Reason |
|---|---|---|
| Step 0 (setup) | PASS (UI-verified) for sign-in/mount; BACKEND-ONLY for backend, ComfyUI, queue, RAM, disk | see matrix |
| Step 0 (session named `TEST-20261024`) | PARTIAL | session created by the first prompt; rail rename input never opened (D5) |
| G1 mockup → draft → inline image | BLOCKED | Chrome Connect MCP server exited between the plan-card read and the Generate click (D1) |
| G2 portrait 896×1344 | BLOCKED | D1 |
| G3 main-style + lifestyle | BLOCKED | D1 |
| G4 A+ pack | BLOCKED | D1 |
| G5 5-second ad | BLOCKED | D1 |
| G6 tip calculator | BLOCKED | D1 |

No generation was started. No credits were spent. Nothing was purchased, listed
or published. No cloud lane and no cost was offered at any point — the G1 plan
card showed `Generate draft 34 cr` / `Generate final 71 cr`, both local-lane
credit metering, neither clicked.

## Chrome Connect runs (real ids from this batch)

| # | run id | steps executed | outcome |
|---|---|---|---|
| 1 | `open_http_127_0_0_1_8101_ui_read_the_pag_mvn8s7sz` | navigate → readLivePage | COMPLETE, read the app |
| 2 | `steps_read_screenshot_c_users_t2hol_desk_mvn8tkwq` | navigate → read → screenshot | COMPLETE, `t0-01-home-desktop.png` written |
| 3 | `steps_read_screenshot_c_users_t2hol_desk_mvn8uakx` | read → screenshot → click `chat-new` → type prompt → Enter → read | COMPLETE, transcript shows the prompt and the G1 plan card |
| 4 | `steps_click_chat_rail_row_active_chat_ra_mvn8uwmg` | click rail edit | ERROR — rename input absent (D5) |
| 5 | `steps_screenshot_c_users_t2hol_desktop_n_mvn8wdo8` | screenshot → click `chat-plan-draft` | ERROR — strict-mode violation, 3 matching draft buttons (the session already held the earlier cards); screenshot `g1-02-plan-card.png` written |

Journal files (controller-owned, under
`C:\Users\T2Hol\OneDrive\Documents\Default Project\data\agent-journal\`):

```
2026-10-25T03-02-17-988Z_open_http_127_0_0_1_8101_ui_read_the_pag_mvn8s7sz.jsonl
2026-10-25T03-03-21-627Z_steps_read_screenshot_c_users_t2hol_desk_mvn8tkwq.jsonl
2026-10-25T03-03-54-897Z_steps_read_screenshot_c_users_t2hol_desk_mvn8uakx.jsonl
2026-10-25T03-04-23-465Z_steps_click_chat_rail_row_active_chat_ra_mvn8uwmg.jsonl
2026-10-25T03-05-32-217Z_steps_screenshot_c_users_t2hol_desktop_n_mvn8wdo8.jsonl
```

## What the UI actually showed (read by the controller, not inferred)

```
NorthstarOS / Simple / Operator / 1 / Deep field · vista 7 of 7
Auto Create Grow Research Operate AutothinK 🔒
4% GPU · 0.9/15.9 GB VRAM · 50°C
Whetstone · New chat · Mogra 3D mockup test
Engine: northstaros-qwen3.8:27b · 34 skills across 9 services
Bojo — Northstar creative assistant · Create · Workbench
```

After the G1 prompt the same tab showed the prompt bubble and a plan card with
`Generate draft 34 cr` and `Generate final 71 cr`, plus an Edit plan / Cancel
pair. Screenshot: `product-tests/G1/g1-02-plan-card.png`.

Visual review: **PERFORMED** (the PNG is readable in this session). Two defects
were read straight off it: the duplicated Display Scale control (D2) and the
empty band below the app frame (D3).

## Executable checks

| Check | Command | Result |
|---|---|---|
| UI build | `npm run build` | 0 errors, 1.27 s |
| Shell gate | `set HARNESS_BASE_URL=http://127.0.0.1:8101/ui/; node verify-shell-v3.cjs` | 28 passed, 0 failed |
| Backend chat | `python -m pytest test_chat_plan.py -q` | 18 passed |
| Controller | `node test/chromecontrol-tests.js` | 78 passed (2 new tab-selection tests) |

## Late-session discovery (after the commits)

The Chrome Connect **MCP** server was dead, but the sanctioned path turned out to
be the **agent CLI**, not the MCP tools:

```
node scripts/chromecontrol-agent.js run --profile "Profile 6" --task "STEPS:…" --url …
```

It attaches to the same "Profile 6" / "Work" / `northstarosllc@gmail.com`
profile and the same guardrails. A read-only run attached successfully and read
the app page — **but the app now renders the Sign In screen**, so the session
that was signed in earlier has expired (or the agent landed in a signed-out tab).

I cannot enter credentials (credential hygiene, §guardrails), so G1–G6 remain
BLOCKED. What is needed from the operator, once, to unblock:

1. Sign in to NorthstarOS in the "Work" Chrome profile (the one already attached
   to Chrome Connect) at `http://127.0.0.1:8101/ui/`.
2. Re-run the G1 scenario from the composer using the agent CLI above; the
   existing `reports/batch1-audit-20261024/product-tests/G0/G1` evidence slots
   and the run-id/journal convention in this file still apply.

Everything else in this batch is committed and verified by executable checks:
product repo `8520824b` + `09f350cd`; Chrome Connect repo `05c7df9`.
No push was performed.


## Controller reliability (late, 2026-10-24 23:45)

The sanctioned chromecontrol-agent.js CLI attaches and reads the app, but its
navigate step hangs unpredictably (180 s without returning; the journal stops
at the navigate tool_call). A single read succeeded earlier in 30 s; the same
command then hung for three consecutive runs. No generation was started, no
credits spent, no Generate clicked successfully. G1-G6 remain BLOCKED. This is
a controller defect, not a product defect, and it is outside the scope of the
product repo.
