# S0 + S1 — Global Shell Modes + Chat Core — Execution Report

**Date:** 2026-10-16 · **Branch:** `feature/overnight-remediation-20261009`
**Commits:** `c58afe7` (S0), `9e62b16` (S1), this docs commit
**Protocol:** plan → execute → verify per component; no claim without a run.

---

## 1. What shipped

### S0 — Global Simple | Advanced shell mode + Editorial Ink scope
| Item | File | Detail |
|---|---|---|
| Mode state | `northstar-os-ui/src/context/ModeContext.jsx` (new) | `ns-shell-mode` persisted; `useMode()`; default **advanced** (launch switch documented in-file) |
| Provider tree | `src/App.jsx` | `BrowserRouter → SessionProvider → TOAST_PROVIDER → **ModeProvider** → Shell` |
| Toggle | `src/components/ShellModeToggle.jsx` (new) + `src/components/TopNav.jsx` | `data-testid="ns-shell-mode"`; segmented pill; hidden < 900px |
| Tokens | `src/styles/tokens.css` | `--spark #2f6fed` (the single AI accent) + chat tokens |
| Chat/style + media scope | `src/styles/chat.css` (new, loaded last) | toggle, chat shell, thinking block, caret, queue, `[data-theme-scope="media"]` dark cinema scope; reduced-motion honored |
| CSS order | `src/main.jsx` | chat.css after foundation.css (wins duplicates) |

### S1 — Chat core (backend + SSE) and Creative Chat shell
| Item | File | Detail |
|---|---|---|
| Additive schema | `Northstar_backend/chat_schema.py` (new) + `data_layer.py` | `chat_sessions`, `chat_messages`, `chat_tool_calls`, `chat_attachments`; appended to the shared DDL (SQLite + Postgres translate path); **no ds_* table touched**; migration applied to the real DB (verified: 4 tables present) |
| Stores | `data_layer.py` | `ChatSessionsDB/ChatMessagesDB/ChatToolCallsDB/ChatAttachmentsDB` + `ChatContainer` on `NorthstarDB.chat` — tenant-scoped reads, no-FK house style, `SELECT changes()` idiom |
| Streaming | `autothink/backend/llm_adapter.py` | ADDITIVE `UnifiedLLMAdapter.stream_chat()` + pure `iter_ollama_chat_events()`: separates `message.thinking` from `message.content`, usage capture, cancel poll per line, one bounded think-flag fallback (`notice: think_unsupported`); `generate()` untouched |
| Chat adapter | `Northstar_backend/chat_adapter.py` (new) | system prompt (content Master Brain), focus injection, history window (16), `CHAT_NUM_CTX=16384` (shared 16 GB GPU), honest `offline_notice` |
| SSE router | `Northstar_backend/chat_router.py` (new) | `start/notice/thinking/token/tool-*/asset/error/done`; `POST /api/chat/sessions/{id}/turns` (StreamingResponse, no-buffering headers); `POST /turns/{id}/cancel`; sessions/messages CRUD; **partial persistence on every exit path** (done/cancel/error/client-disconnect; true status in `usage_json`); auto-title from the first user message |
| Mount | `Northstar_backend/main.py` | separate guarded import (`_HAS_CHAT`) + `include_router` |
| Bug fix | `Northstar_backend/design_studio_agent.py` | `_maybe_llm_enhance` asked the MODULE for `generate` (never existed → always fail-open); now instantiates `UnifiedLLMAdapter`, checks `ok` before using text |
| Client | `northstar-os-ui/src/chat/api.js` (new) | CSRF + LOCAL_DEV shim (house transport), fetch+ReadableStream SSE parser (`parseFrame` exported) |
| Shell | `northstar-os-ui/src/chat/CreativeChat.jsx` (new) | session rail, thinking block ("Thought for Ns · N chars"), streaming caret, **message queue** (submit while thinking), Stop (cancel+abort), honest error/cancelled states, editor-time char guard |
| Mount point | `src/pages/internal/CreativeStudio.jsx` | +8 inert lines: `useMode()` hook + `if (shellMode === 'simple') return <CreativeChat />` before the existing return; advanced tree untouched |

## 2. Verification evidence (all run, exact results)

| Gate | Command | Result |
|---|---|---|
| Chat unit tests | `python -m pytest test_chat_core.py -q` | **15 passed** (thinking split, keep-alive junk, cancel, think-fallback, transport error, SSE sequence, cancel/error/disconnect persistence, cut-without-tokens persists nothing, registry, store CRUD + tenant scoping, focus build) |
| RE + design-studio subset | `pytest test_chat_core test_design_studio_{agent,print,async,scenes,openapi,re_ext}` | **54 passed** |
| Autothink suite (adapter additions) | `pytest autothink/tests` | **44 passed** |
| Full backend suite | `python -m pytest -q --continue-on-collection-errors` | **3637 passed, 65 skipped, 8 failed, 3 collection errors** (8m09s) — **all 8 failures pre-existing** (see §3); 3 errors are untracked scratch tests from a parallel session (`costco_non_kirkland/tests/*`, imports of non-existent helpers) |
| Real-DB migration | `get_northstar_db()` probe | `['chat_attachments','chat_messages','chat_sessions','chat_tool_calls']`, store list call OK |
| Live route mount | uvicorn on scratch port 8011 → curl `/api/chat/health` | `{"detail":"Authentication required."} STATUS:401` — route exists, auth enforced (404 would have meant unmounted) |
| UI build | `npm run build` | **0 errors** (pre-existing chunk-size + compose.js chunk warnings only) |
| Studio harness | `HARNESS_BASE_URL=http://127.0.0.1:8000/ui/ node verify-studio.cjs` | **65 passed / 6 failed** — all 6 pre-existing drift (§3); deterministic across two runs |

## 3. Pre-existing failure attribution (the 8-suite + 6-harness failures)

| Failure | Verdict / proof |
|---|---|
| `test_v3_shell_invariants` (expects 48 routes) | **Pre-existing.** `git show HEAD~1:src/App.jsx` route count = **52**; worktree = 52. My commits added zero `<Route>`. |
| `test_frozen_file_boundary_is_a_static_rule` | **Pre-existing.** Documented known failure in `00_STATE.json` (protected-hash drift since 2026-09-30). |
| `test_brand_blacklist_updater::test_live_armed_requires_exact_gate` | **Pre-existing.** `tasks/brand_blacklist_updater.py` untouched (`git status` empty); env-gate behavior unrelated to chat. |
| `test_env_hygiene::test_env_example_tracked_but_is_placeholder` | **Pre-existing.** `.env.example` (root) contains `Bearer ` in a Bright Data comment and lacks the word "example"; file unmodified by this session. |
| `test_invite_flow::test_email_send_is_stubbed` (full-run fail) | **Order pollution, pre-existing.** Alone: 7 passed. After `tests/test_reasoning_routes.py`: fails. After `test_chat_core.py`: **22 passed** — polluter is reasoning-routes, not my file. |
| `tests/test_reasoning_routes.py` ×2 (full-run fail) | **Order-dependent, pre-existing.** Pass standalone and in small combos; no touched files involved. |
| `test_ui_route_contract` (8 → **7** entries) | **7 pre-existing** (bare `/api/design-studio` base constants in six untouched UI files + scanner artifact `/api/design-studiosample`). **My contribution fixed to zero**: added `GET /api/chat` root route; entry `('api.js','/api/chat')` no longer listed. |
| Harness: "New Brief" toast | **Pre-existing drift.** Assertion waits for toast text `'sample'`; `addBrief` message (untouched, line ~639) says "New brief draft created — local draft only…". My diff on this file = +8 inert lines. |
| Harness: ListingForge ×2 + templates + loop-canvas (×3 rooms) | **Pre-existing.** Files absent from both commit stats (`git show --stat`); flows unchanged. |
| Harness: "unexpected" engine/compose fetches | **Pre-existing.** `engineApi.js`, `CompositingSurface.jsx` untouched; those calls predate S0/S1 (RE build surfaces) while the harness whitelist only stubs `/api/v1/foundation`. |

## 4. Operational notes

- **Restart required:** the running `:8000` backend predates this work — restart it (e.g. `launch-all.ps1` / its uvicorn command) to serve `/api/chat/*`. The SPA default is **advanced**, so nothing changes for the operator until the top-nav toggle is flipped to Simple.
- **Simple-mode test path:** restart backend → open `/ui/design-studio?section=projects` (Creative Studio) → top-nav pill → *Simple* → chat appears. Stop persists partials; queued messages send at turn end.
- **Harness refresh queued for S4** (when the per-room `ModeToggle` is retired and the global shell extends): update the `'sample'` toast expectation, ListingForge markers, and the network whitelist — decide the real contract first, per house rule.
- **Not started (awaiting approval / pause-gates):** S2 tool registry + ComfyUI progress bridge; S3 voice PTT (whisper-tools binaries ready); REA/Chrome Connect Packify pass (requires `[PAUSE-AUTH]` gate and fresh operator approval); Master Brain living-file + policy scheduler; AutothinK AT-0/AT-1 (its own product track, premium tier).
