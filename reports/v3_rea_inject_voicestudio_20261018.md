# V3 REA Inject + VoiceStudio UGC Pipeline — Build Report

**Date:** 2026-10-18
**Branch:** `feature/v3-simple-view`
**Commits:** `4921700` (feature) · `8b211ed` (state)
**Rollback baseline:** tag `v0.2.0-pre-v3-simple-view` (`6d4e847`) — untouched.

---

## 1. What shipped

### 1.1 Tool Execution Gateway (`Northstar_backend/tool_gateway.py`) — NEW
One interception point for every agent tool call (OpenBot pattern), adapted to
this stack's guardrails:

- **Policy** — a `DENY_LIST` of exec/eval/shell/credential/network/file tools.
  None are registered today; the list is the enforceable boundary so a future
  registration cannot silently widen it.
- **Audit** — every attempt is written **before** execution as `allowed` or
  `denied` (with reason), then an `executed` row carries the outcome + latency.
  Append-only `tool_audit` table (`chat_schema.py`) + `ToolAuditDB`
  (`data_layer.py`, `ChatContainer.tool_audit`).
- **Execute** — delegates to `chat_tools.run_tool` (validate → execute). No
  handler is reachable without passing through the gateway.
- **Honest** — denials return the same shape as a normal tool failure
  (`ok:false` + reason), so the model reacts instead of crashing.

Wired into the turn loop: `chat_router.py` calls
`tool_gateway.run_tool_gated(db.chat, account_id, name, args, ctx)`.

### 1.2 AG-UI generative UI — NEW
A tool may declare a `card` in its result (`title` + `rows` + `action`). The
turn loop appends it as a `card` part; the shell renders an **interactive
component** (`.chat-card*` in `shell.css`), not plain text. First consumers are
the VoiceStudio tools; the pattern is generic.

### 1.3 Human-in-the-Loop handover — NEW
`ChatSurface.jsx`: **Pause** mid-stream (`chat-pause`) stops the agent and flips
the shell to "you're driving" (`chat-paused`); the turn queue is suppressed while
paused; the operator's next message / **Resume** (`chat-resume`) hands control
back. No state is lost.

### 1.4 VoiceStudio UGC media pipeline (`Northstar_backend/voicestudio_adapter.py`) — NEW
Async client for a self-hosted VoiceStudio instance:
- **Voice cloning / profile management** — `list_voices`, `clone_voice`.
- **TTS generation** — `tts` (ad script variants → voiceovers).
- **Multi-language dubbing** — `dub` (translate + synthesize for new marketplaces).

No new dependencies (small `requests` core run on a worker thread via
`asyncio.to_thread`). Configured via `VOICESTUDIO_URL` (+ optional
`VOICESTUDIO_API_KEY`, `VOICESTUDIO_PATHS`).

Wired as **Create-focus tool hooks** in `chat_tools.py` (`voice_list`,
`voice_tts`, `voice_dub`) and `shell_focus.py` (the server-owned Create tool
subset). Results render as AG-UI cards; unreachable/unarmed service → `ok:false`
with the real reason (never a fabricated voiceover). Voice calls are gated by
the same gateway.

### 1.5 Docs
`NORTHSTAR_V3_MASTER_PLAN.md` — added **§2.1 REA inject (OpenBot concepts)**
and **§4A Create focus — VoiceStudio UGC media pipeline**; refreshed
verification counts and order of work.

---

## 2. Verification (real runs)

| Suite | Command | Result |
|---|---|---|
| Tool gateway | `pytest test_tool_gateway.py -q` | **5 passed** |
| VoiceStudio adapter + hooks | `pytest test_voicestudio_adapter.py -q` | **9 passed** |
| Shell/daemon/governor | `pytest test_shell_modes.py -q` | **33 passed** |
| Combined chat/shell | `pytest test_shell_modes test_tool_gateway test_voicestudio_adapter test_chat_core test_chat_tools -q` | **75 passed** |
| Shell gate E2E | `node verify-shell-v3.cjs` | **20 passed, 0 failed** |
| Guardrails | `node verify-guards.cjs` | **11 passed, 0 failed** |
| Admin | `node verify-admin.cjs` | **33 passed, 0 failed** |
| Build | `npm run build` | **0 errors** |
| Python compile | `py_compile` on all touched modules | OK |

Harness Scenario D added to `verify-shell-v3.cjs` (+6 assertions):
AG-UI card renders as a component; card carries an action control; Pause appears
while streaming; paused banner appears on handover; Resume control offered.

---

## 3. Guardrails honored

- No credential values read, printed, or committed.
- No real-money action; no live spend.
- No push to a protected branch (work stays on `feature/v3-simple-view`).
- Only authored files were staged; pre-existing runtime dirt (golden-goose
  reports, `northstar.db`, costco data) was left untouched.
- gitleaks pre-commit hook: "no leaks found" on both commits.

## 4. Honest limits / next

- VoiceStudio endpoints are the operator's deployed routes; the default base URL
  is a configurable local default, not a claim that a service is present.
- Voice lane next: render-jobs panel, hook A/B comparison cards, wiring the
  adapter into Creative Studio's video lanes.
- S5 AutothinK premium surface, S7 Brand SEO Engine, S8 corpus remain next/PLANNED.
