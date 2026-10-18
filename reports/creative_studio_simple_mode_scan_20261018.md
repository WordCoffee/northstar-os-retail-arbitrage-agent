# Creative Studio — Simple Mode Deep Scan: 100 Ways to Vastly Improve It

**Date:** 2026-10-18
**Scope:** `/creative-studio` when the global shell mode is **Simple** — i.e. the chat-first surface `northstar-os-ui/src/chat/CreativeChat.jsx` — plus everything in the stack that feeds or could feed it (chat backend, tools, engine, brand/loop records, shell).
**Method:** full read of the simple-mode surface and its supporting backend, cross-checked against the S0–S3 reports and the studio engine. Every item below is grounded in a file/line anchor, a verified behavior, or a built-but-unwired capability. No live calls were made during the scan.

---

## What Simple Mode Is Today (verified state)

| Piece | State |
|---|---|
| UI | `CreativeChat.jsx` — one 463-line component. Session rail, SSE stream, thinking block, tool chips, asset cards, queue, voice PTT, Stop. |
| Rendering | `CreativeStudio.jsx:732` swaps the whole room to `<CreativeChat />` when `useMode().mode === 'simple'` — the only room migrated so far. |
| Backend | `chat_router.py`: `GET /health`, `POST/GET /sessions`, `GET /sessions/{id}/messages`, `POST /sessions/{id}/turns` (SSE), `POST /turns/{id}/cancel`, voice transcribe/status. |
| SSE events | `start · notice · thinking · token · tool-start · tool-progress · tool-end · asset · error · done`. |
| Tools (5) | `system_status`, `list_templates`, `design_brief`, `create_dieline`, `generate_image`. `MAX_TOOL_STEPS = 4`. |
| Voice | Local whisper.cpp PTT, no audio leaves the machine. |
| Schema already supports | `chat_sessions.title`, `.focus_json`, `.ds_project_id`, `.model` — none of which the Simple UI ever sets or edits. |

**Spec-vs-disk divergence found:** the `CreativeChat.jsx` header promises "Tools + the focus rail arrive in S2". Tools shipped (S2), voice shipped (S3) — **the focus rail was never built**, even though the backend path it needs (`focus_json` → system prompt, `chat_adapter.py:210`) is fully wired and tested. That one gap is item #81 and one of the highest-leverage fixes in this list.

**Legend — Impact:** ◆ vast (changes what users can do) · ● solid (removes daily friction) · ○ polish. **Effort:** S (≤1 day) · M (2–5 days) · L (1–2+ weeks incl. tests).

---

## Top 10 Highest-Leverage Picks

| # | Item | Why it wins |
|---|---|---|
| 81 | Focus Rail (backend already built) | The whole S2 focus lane is dead weight without a UI; days of backend work already done. |
| 71 | "Open in canvas" from any render | Today a generated image dead-ends in chat. This is the missing bridge from simple → studio depth. |
| 31+38 | Auto-grow composer + queue control | The two things users touch every single turn; both are currently half-built. |
| 51–54 | Tool transparency (args, labels, summaries, pct+phase) | All payloads already stream; the UI just doesn't show them. Cheapest trust win in the suite. |
| 12 | Edit & resend a user turn | The core iteration loop for briefs/copy; everything else compounds off this. |
| 28 | Resume last session on mount | Simple mode currently "forgets" where you were every visit. |
| 1 | Markdown rendering | The model writes markdown; users read asterisks. One renderer fixes the whole reading experience. |
| 6 | Scroll-position respect | Streaming yanks you to the bottom even when you scrolled up — actively hostile during long briefs. |
| 58 | Cancel that reaches the render | Stop currently cannot stop an in-flight ComfyUI job (no interrupt path anywhere in the router/tools). |
| 82 | Brand-profile injection | The studio's `ds-brand-profile` (voice, prohibited claims, competitors) never reaches chat — every answer is off-brand by construction. |

---

## 1. Conversation Rendering & Reading (1–10)

1. **Markdown rendering in bubbles.** Replies stream markdown (`**bold**`, lists, headings, tables) but render as plain pre-wrap text (`chat.css .chat-bubble`). Render a safe subset → briefs and copy become readable. ◆ M
2. **Code/JSON blocks with copy button.** `design_brief` and dieline params come back as structured JSON inside prose; add a styled `<pre>` view with copy. ◆ S
3. **Clickable links.** URLs in model output are inert text — linkify with `target="_blank" rel="noreferrer"`. ● S
4. **Asset-ID linking.** When a reply references an asset id (`db9cc274-…`), auto-link it to `/api/design-studio/assets/{id}/file`. ○ S
5. **Timestamp + duration chips per message.** `startedAt`/`endedAt` exist but duration only shows inside the thinking summary; surface "answered in 12s · 14:32" on the message. ● S
6. **Scroll-position respect.** The `useEffect` at `CreativeChat.jsx:70-74` pins to bottom on every token; pause auto-pin when the user scrolls up and show a "jump to latest" pill. ◆ S
7. **`role="log"` + `aria-live="polite"` on the stream.** Screen readers get zero announcements today; add live-region semantics + `aria-busy` while streaming. ● S
8. **Render the notices you already receive.** `notice` SSE frames (e.g. `max_tool_steps`, `chat_router.py:264`) are collected into `m.notices` (`CreativeChat.jsx:173-174`) and never displayed — render a quiet notice row. ◆ S
9. **Rewrite the stale empty state.** "…live image and dieline tools join this chat in S2" — S2/S3 shipped; teach the *real* current capabilities (local renders, dielines, voice, briefs) instead. ◆ S
10. **Long-message collapse.** Paste-bomb user turns render full-height; collapse >8 lines with "show more" (thinking body is already capped at 220px). ● S

## 2. Message Actions & Reuse (11–20)

11. **Copy message.** No copy affordance anywhere — hover toolbar: copy text / copy thinking / copy as markdown. ◆ S
12. **Edit & resend a user turn.** Post the edited prompt as a new turn that branches the conversation; the core iteration loop (server keeps full history, so replay stays honest). ◆ M
13. **Regenerate last answer.** One tap to re-roll; for renders, offer "same seed" vs "new seed" variants. ◆ M
14. **Retry button on error turns.** The error copy says "retry when the engine is up" but provides no button — add one that resubmits the same content. ◆ S
15. **Resume interrupted turns.** Cancelled/partial answers and stream deaths end the turn; add "continue" which posts the partial as context. ● M
16. **Quote-reply.** Select text in any bubble → "reply to this" pins a quote chip in the composer (anchoring for 100-message sessions). ● M
17. **"Turn into…" quick actions under assistant turns.** → brief · → dieline (prefills `create_dieline`) · → render (prefills `generate_image`) · → document. Converts prose into the actual next action. ◆ M
18. **Pin messages as turn context.** Pin a reply ("use this as art direction") injected into subsequent turns, with an unpin chip. ● M
19. **In-session search.** A small filter that jumps between turns mentioning a term. ● M
20. **Honesty badges per answer.** Distinguish model-knowledge answers from tool-backed answers (parts_json already records tool parts) — keeps the suite's honesty contract visible in simple mode. ● S

## 3. Session Rail & Organization (21–30)

21. **Rename sessions.** `data_layer.py:2754` already supports patching sessions; add `PATCH /api/chat/sessions/{sid}` + inline rail rename. ◆ S
22. **Delete / archive sessions.** Only create + list routes exist (`chat_router.py:460-478`); add DELETE with confirm, keeping the audit row. ◆ M
23. **Optimistic titles.** The rail shows "New chat" until a post-turn refetch; set the title from the first user message immediately (`CreativeChat.jsx:197`). ● S
24. **Pin sessions** to the top of the rail. ● S
25. **Group by date.** Today / Yesterday / Previous 7 days / Older headers. ● S
26. **Rail search box.** Filter sessions by title as the list grows (server cap 50, `api.js:57`). ● S
27. **Rail badges.** Message count, last tool used, asset count, relative last-activity time. ○ M
28. **Resume last session on mount.** Auto-open the last active session from localStorage instead of always the empty state; "New chat" stays one tap. ◆ S
29. **Duplicate / branch session.** Fork a session to explore a second direction without polluting the first. ○ M
30. **Context menu + keyboard nav.** Right-click/long-press menu (rename · pin · export · delete); arrow-key navigation with Enter/Del — the rail is currently plain buttons with no focus management. ● M

## 4. Composer & Input (31–40)

31. **Auto-grow textarea.** `rows={1}` with a CSS `max-height: 140px` that never triggers (no auto-grow JS) — multi-line briefs scroll inside one line. ◆ S
32. **Per-session draft persistence.** Half-typed briefs are lost on reload/session switch; persist per session id. ◆ S
33. **Slash commands.** `/render`, `/dieline`, `/brief`, `/status`, `/help` with a picker — deterministic tool routing instead of hoping the small model picks the tool. ◆ M
34. **Quick-action chips.** Render image · Build dieline · Draft brief · Status above the composer — one tap for each live tool. ◆ S
35. **Attach reference images.** `generate_image` accepts `refs` (`chat_tools.py`) but the UI can never supply one; wire upload → refs so "make my pouch look like this photo" works. ◆ L
36. **Paste screenshot → attachment.** Clipboard-paste handler on the composer (natural for sellers). ● M (pairs with 35)
37. **Drag & drop files anywhere on the chat.** Drop zone + inline chips. ● M (pairs with 35)
38. **Queue visibility & control.** Only "N queued — next: …" is shown; render each queued item as a chip with remove / edit-into-composer / reorder. ◆ S
39. **Keyboard map.** Esc = stop/clear queue · ⌘K = new chat · `/` = focus composer · `?` = shortcuts sheet. ● S
40. **Context-budget hint.** Estimate prompt size against `CHAT_NUM_CTX=16384` and warn before the server silently truncates a paste-heavy turn. ○ M

## 5. Voice (41–50)

41. **Recording meter + elapsed time.** Only the button label changes today; add live seconds + input level so users know it's capturing. ◆ S
42. **Max-duration auto-stop.** Cap at ~60s with visible countdown — whisper is CPU-bound on this box. ● S
43. **Proactive voice status.** `chatVoice.status()` exists (`api.js:85`) but is never called; if whisper-cli is missing, disable the mic with the reason at mount instead of failing after a recording. ◆ S
44. **Transcription progress + cancel.** Long clips show only "Transcribing…"; add elapsed seconds and cancel. ● S
45. **Hold-to-talk hotkey.** Space/tilde push-to-talk while the composer is focused. ○ M
46. **Language hint + detected language.** Pass a hint to whisper and report what it used — mixed-language brands are common. ● M
47. **Voice edit affordance.** Keep "revert voice" (restore pre-dictation draft) and highlight the inserted span. ● S
48. **Permission-state guidance.** Mic denied / no device should render as inline steps, not a one-line error. ○ S
49. **Filler-word cleanup option.** Optional "clean" pass (um/uh/duplicates) before insert. ○ M
50. **Queue voice clips.** Allow recording while a turn streams, enqueued like text. ○ M

## 6. Tools, Progress & Transparency (51–60)

51. **Show tool arguments.** `tool-start` carries args (up to 2KB, `chat_router.py:279`) and the UI stores them (`CreativeChat.jsx:149`) but never displays them — expandable args row per chip. ◆ S
52. **Human tool labels.** Map `generate_image` → "Rendering image locally", `create_dieline` → "Building dieline", `design_brief` → "Structuring brief"; machine name secondary. ◆ S
53. **Show completion summaries.** `tool-end.summary` is stored and never rendered — "Built 130×210 pouch dieline (bleed/trim/fold/safe)" is exactly what users should read. ◆ S
54. **pct + phase together.** The running chip shows pct OR label, never both (`CreativeChat.jsx:350-352`); "75% · sampling" beats "75%". ● S
55. **Per-tool elapsed + ETA.** Progress frames (25/50/75/100) already arrive; show elapsed and estimate from prior local runs per model. ● M
56. **Retry failed tools.** Error chips show the error but no retry; offer one-tap re-run of the same tool + args (the registry is deterministic). ◆ S
57. **Tool-step budget indicator.** `/health` reports `max_tool_steps: 4` but nothing shows it; display "2/4 tool rounds used" and a "continue?" action when the cap is hit. ◆ S
58. **Cancel that reaches the render.** Stop sets the turn flag but nothing interrupts the in-flight ComfyUI job (no `interrupt` call exists in `chat_router`/`chat_tools`; the worker-join loop at `chat_router.py:309-324` has no cancel check). Wire cancel → ComfyUI interrupt + worker checks, then report honestly. ◆ L
59. **GPU swap notice.** Renders evict the local brain (`unload_brain`) and own the single 16 GB card: show "GPU busy — local model swapped out during render" so the pause is explained. ◆ S
60. **Persistent system readout.** Surface `system_status` results (engine armed/reachable, model, VRAM) as a header chip row refreshed periodically. ● M

## 7. Artifacts & Asset Viewer (61–70)

61. **Lightbox viewer.** Cards open raw files in a new tab; add an in-app zoom/pan lightbox using the `data-theme-scope="media"` dark scope (defined at `chat.css:124`, currently unused). ◆ S
62. **Download with real filenames.** Add an explicit download button; name files from metadata (current names are "chat render — …", card links are raw file URLs). ● S
63. **Faithful history replay.** Replay collapses every attachment to `{name:'asset'}` (`CreativeChat.jsx:98-99`), losing kind/dims — persist kind/name/width/height in parts_json and rebuild cards identically on reload. ◆ S
64. **Dieline previews inline.** `create_dieline` returns SVG + PDF assets; render the SVG directly in the card (kind `dieline` currently falls through to a text-only card) with a PDF secondary link. ◆ S
65. **Video-capable card.** The card renders only `<img>` (`!a.kind || a.kind === 'image'`); add a `<video controls>` branch so a future `generate_video` doesn't look broken. ● S
66. **Gallery for multi-asset turns.** Render loops can return several images; add count badge + contact-sheet/carousel layout. ● M
67. **Metadata line on cards.** Model, seed, tier, dimensions, bytes — seed already arrives in tool data and is needed for reproducibility. ◆ S
68. **Re-roll controls.** "Same seed" / "New seed" / "Lighter" one-tap variations from the render card. ● M
69. **Pin an asset as session reference.** One tap to feed a rendered image into `refs` for subsequent renders (pairs with 35). ● M
70. **Card actions menu.** Copy asset id · open in canvas (71) · save to a collection · delete — one menu instead of a bare link. ● S

## 8. The Bridge — Chat → Studio Depth (71–80)

71. **"Open in canvas" from any render.** Create a studio document with the asset as a product/image layer using the existing engine (`docFromTemplate` / `addLayer` in `studio/engine/doc.js`) — closes the loop from generation to a designed deliverable. ◆ L
72. **"Make an ad set" from a hero render.** Run the existing channel-set render + export (`exportChannelSet`) with the compliance gate; chat becomes the fastest path to a full placement set. ◆ L
73. **Type pass from chat.** Run the existing typography compose (`mockup_compositor` presets via `engineApi.compose`) with the operator's logo on a chat render; report which preset ran. ◆ M
74. **Text-fidelity check inline.** After a render, call the OCR text-check and show the verdict chip (text-free / zones cleared / lettering detected) exactly like the advanced room does. ◆ M
75. **Compliance pre-flight inline.** Run `checkCompliance` (+ brand profile: prohibited claims, competitors, listing copy) on anything chat proposes to export and show block/flag verdicts. ◆ M
76. **Save-as-brief (persistent).** `design_brief` returns data only (`chat_tools.py`); add "Save brief" that writes a record into the studio briefs store so it shows up in the Briefs room and the daily loop. ◆ M
77. **Save-as-document.** "Turn into document" creates a saved `ds-docs` record from the answer's headline/copy with a template + kit, opening in the canvas. ◆ M
78. **Daily loop cards.** `planToday` proposals as chat cards: Approve → opens an editable document (same semantics as the Today room), Dismiss → records the decision. ● L
79. **The four handoffs.** AdPilot / SocialPulse / Product Designer / ListingForge one-tap sends after relevant answers (the advanced room already navigates with local record ids). ● S
80. **Bind sessions to a studio project.** `chat_sessions.ds_project_id` exists and is threaded into tool ctx (`chat_router.py:290`, passed as `project_id` to asset records) but is never set by the UI — bind per project and show the project chip in the header. ● M

## 9. Context, Brand & Memory (81–90)

81. **Build the Focus Rail (the missing S2 piece).** `focus_json` is stored per session and injected into the system prompt (`chat_adapter.py:210`) with tests — yet no UI ever sets it. Ship the chips (content type, platform, brand, tone) + `PATCH` route. ◆ M
82. **Brand-profile injection.** The persisted `ds-brand-profile` (name, voice, prohibited claims, competitors, listing copy) never reaches chat; inject it (or set as focus) so every answer respects the brand automatically. ◆ M
83. **Conversational brand setup.** "Set up my brand" flow that writes the brand profile + kit records the studio rooms already read — the one-time step that unlocks the whole loop. ● L
84. **Assumed vs known chips.** `.chat-context .chip.assumed` CSS exists (`chat.css:92`) and is unused; mark inferred values vs profile-sourced values on answers. ● S
85. **Turn context receipt.** A small "context used" row per answer (brand profile version, kit, focus, history depth) — trust + debuggability. ● M
86. **Memory Bank retrieval in chat.** The per-account knowledge store (§8 of the constitution) exists; retrieve relevant facts/preferences into the system prompt at turn time. ◆ L
87. **Memory write-back.** "Remember: we never say 'cleanse'" → writes a knowledge record + optionally a prohibited-claims entry. ● M
88. **Model lane switcher.** `TurnIn.model` is honored end-to-end (`chat_router.py:508`) but the UI never sets it — a header picker (qwen3:4b small lane vs 27B when memory allows) makes the known hardware tradeoff user-controllable. ◆ S
89. **Think control.** `think: true` is hardcoded (`CreativeChat.jsx:138`); expose Quick / Think-harder per turn (llm_adapter already maps think + budget). ● S
90. **Smarter suggestions.** Replace the 3 static starters with context-aware ones (brand-profile completeness, last tool, the daily plan) — and make them **send** on click instead of only filling the composer. ◆ M

## 10. Reliability, Performance & Shell (91–100)

91. **SSE resilience.** A dropped stream marks the turn error and the answer is gone (`streamTurn` has no retry); add reconnect-and-resume, or at minimum an "interrupted — resume" record. ◆ M
92. **Health/voice polling + offline banner.** Health is fetched once at mount (`CreativeChat.jsx:47-67`); poll with backoff, show an honest offline banner, and recover when the engine returns. ◆ S
93. **Streaming re-render cost.** Every token maps over the full message list and re-renders every bubble (`patchBot` in `runTurn`); memoize `Message` and isolate the streaming bubble (or move to a reducer) — long sessions get janky. ◆ M
94. **Component split.** One 463-line component with 8 `useState` + 5 `useRef`; extract `ChatRail` / `MessageList` / `Message` / `ToolChip` / `AssetCard` / `Composer` before the next feature wave. ◆ M
95. **Session-switch during stream.** Switching sessions mid-stream resets `messages` while streaming continues, leaving an orphaned visual stream and a live Stop button on the new session (`loadSession`, `CreativeChat.jsx:76-105`); lock the rail or offer "cancel & switch". ● S
96. **Stop/queue semantics.** Stopping a turn immediately drains the queue (by design, `CreativeChat.jsx:213-219`); the Stop button should say so ("stop turn & queue" vs "stop this turn, keep queue"). ○ S
97. **Mobile reachability of Simple mode.** `.shell-mode-toggle` is `display: none` below 900px (`chat.css:24`) and lives only in `TopNav` — mobile users cannot enter (or leave) simple mode. Put it in the mobile menu / bottom nav. ◆ S
98. **Responsive chat layout.** `.chat-shell` is a fixed `236px` grid with `height: calc(100dvh - 176px)` and no breakpoints; make the rail an off-canvas drawer under ~900px and let the shell size flexibly. ◆ M
99. **Deep-link the mode.** Simple mode isn't addressable (localStorage only); support `?shell=simple` / a route so operators, tests, and support can link straight into the chat shell. ● S
100. **Simple-mode test coverage.** The verify/acceptance harnesses exercise the advanced room; add coverage for the chat surface: SSE turn (token/tool/asset frames), queue drain, cancel-as-partial, voice button states, rail ops, and the mobile toggle path. ◆ M

---

## Notes & Reconciliation

- **Every payload to build #51–#57 and #63 already streams over SSE** — args (`tool-start`), phase labels + pct (`tool-progress`), summaries + asset metadata (`tool-end`, `asset`). Most of the transparency wins are UI-only changes.
- **#21, #81, #82 are backend-half-done**: the data layer can patch sessions, focus injection has tests, brand records persist. Each needs a small route + a UI surface, not new architecture.
- **Geometric honesty preserved**: none of these items weakens the room's honesty contract (provider-gated states, local-only claims, no fabricated records). Items #71–#79 attach to *real* existing engine functions (`doc.js`, `compose.js`, `compliance.js`, `loop.js`, `engineApi.js`).
- **Highest-risk item**: #58 — cancel semantics touch the GPU lane; build it with the circuit-breaker discipline (persist what succeeded, never auto-retry).
- **Cheapest five wins (< 1 day each)**: #9 (stale copy), #14 (retry button), #31 (auto-grow), #38 (queue chips), #44/#41 (voice meter), #54 (pct+phase), #63 (replay fidelity).

*Scan performed read-only. No code was changed; no live provider calls were made.*
