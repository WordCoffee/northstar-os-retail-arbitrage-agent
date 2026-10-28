# NorthstarOS admin automation — MOGRA T1 through Tys Assistant + Chrome Connect

**Date:** 2026-10-28
**Branch:** `feature/chrome-connect-3.0`
**Tys Assistant:** live, 4 lanes, Bojo orchestration verified again
**Verdict:** **T1 = VERIFIED COMPLETE** through the real Design Studio UI.
**Not claimed:** product acceptance for T2–T8 / C3–C5. T3 is *partial* (see §7).

---

## 1. Readiness — measured, not assumed

| Check | Method | Result |
|---|---|---|
| Tys Assistant API live | `GET /api/admin/tys/state` (dev-shim identity) | **PASS** — 5 lanes listed, `tys-assistant` / `admin_automation` |
| Bojo CPU-only + responsive | `ollama ps`, `/api/generate`, live plan turn | **PASS** — `size_vram: 0`, 100% CPU, plan in **5,818 ms**, `think=false`, `eval_count=120`, `done_reason=stop` |
| Coding worker unloaded / on demand | `:8080` closed, no 27B `llama-server` | **PASS** — not running |
| One Chrome Connect controller | `chromeconnect_status`, lock holder | **PASS** — one MCP child (pid 22012), `session_key: Profile 6`, binding VERIFIED |
| Guardrails | `chromeconnect_status` | **PASS** — fingerprint `1f84d421…cffa` == baseline, Amazon blocklist 26 |
| Backend / frontend / ComfyUI listeners | `Get-NetTCPConnection`, `/health`, `/system_stats` | **PASS** — `127.0.0.1:8000` backend, `:8101` Vite, `:8188` ComfyUI 0.40.0, CUDA RTX 5080 |
| No orphaned llama-server / Ollama runners | `Win32_Process` + `/api/ps` | **DEFECT FOUND → CLEARED** — *two* Ollama runners existed for the same model blob; one (`pid 12332`, ctx 16384, 4,167 MB private) was not in `/api/ps` and held no traffic. Stopped. No runners remain; Ollama serves on demand. |

No service was restarted. ComfyUI, Vite and the backend were already correct.

### Why the orphan mattered

System RAM was **1,497 MB free** against the render gate's **4,096 MB** floor
(`studio_generation.ensure_system_ram`). That, not VRAM, is the box's binding
constraint. After stopping the orphan runner, unloading Bojo (`keep_alive: 0`) and
trimming working sets of idle non-essential apps to standby (**no app was
closed**), available RAM reached **6,791 MB** and the render gate passed on its
own terms. The guard was not weakened or overridden.

---

## 2. Worklist — the real definitions, not invented ones

Read from the repo, not restated from memory:

* `reports/real-verify-2026-10-26/R2_ACCEPTANCE_20261027.md` — **T1 pouch render,
  T2 compositor label, T3 2000×2000 MAIN + readiness, T4 lifestyle, T5 A+ 1464×600,
  T6 dieline/prepress, T7 Wan+Piper mux with measured playback, T8 vision QC,
  plus refresh-persistence**; C3 creative-surface audit, C4 fix C3 findings,
  C5 Product Designer Studio re-audit.
* `docs/mogra-organics-packaging/BRIEF_pouch_2sku_20261016.md` — the authoritative
  product facts: SKU 1 Organic Lion's Mane 6 oz, 130×210×40 mm; approved palette
  kraft `#D5A77A`, olive `#9DBA8B`, ivory `#F5EEE2`, forest `#253628`; and the
  hard Lane B rule that the image engine is never asked to draw text, wordmarks or
  logos.
* `reports/acceptance_drain_20261027.md` — the last honest status table.

**Next incomplete item in dependency order = T1**, because its only prior
"verification" was a direct terminal render (`reports/acceptance_checkpoint_20261027.md`
§T1) — exactly the class of evidence this campaign excludes. Nothing downstream can
be accepted while the base render has never passed through the product.

---

## 3. Work orders filed through Tys Assistant

### 3.1 `tys_6554df6153d4` — planning (Bojo orchestrates)

Objective: plan the T1 workflow. No steps supplied; `planning: orchestrator`.

Bojo's accepted plan (1 attempt, no corrective retry):

```
[inspect]  Review the Organic Lion's Mane 6 oz pouch brief for product facts.
[creative] Submit the T1 stand-up hero render via the Design Studio chat composer.
[browser]  Verify the artefact, preview, download link, and persistence after a page refresh.
```

Step 0 executed: **inspected 2/2 files** (16,587 B brief + 70,038 B
`studio_generation.py`). Evidence: `Northstar_backend/data/tys/evidence/tys_6554df6153d4.jsonl`.

**Defect recorded (not repaired this pass):** the orchestrator routes *"via the
Design Studio chat composer"* to the **creative** lane, which calls
`studio_generation.generate_image` directly. That is a backend render — it can
never satisfy a UI-acceptance requirement, and a task that trusted Bojo's plan
would have produced a false "T1 complete". The execution plan was therefore
corrected to make the render happen **inside the browser lane**, and the
divergence is recorded here rather than hidden.

### 3.2 `tys_7d00cf26f928` — execution → **done, all steps completed**

One browser step, `max_steps 8`, hard wall 1,800 s. The lane honoured the
one-controller-per-profile rule and returned an explicit assignment
(`awaiting_controller`, `Profile 6`, owner pid 22868) instead of spawning a second
controller. The assignment was executed by the owning controller and the result
posted back via `POST /tasks/{id}/controller-result`; the task closed
`cursor 1/1`, `stop_reason: all_steps_completed`, `blockers: []`.

---

## 4. T1 executed through the real UI

Prompt submitted through the visible composer
(`textarea[data-testid="chat-input"]`), grounded in the brief: matte kraft
stand-up pouch, 130×210×40 mm proportions, cool marble surface, three-point light,
olive sprig, approved palette quoted, and an explicit instruction that the engine
must not draw text/wordmark/label copy (the Lane B rule).

| Requirement | Evidence |
|---|---|
| UI submission | Chrome Connect run `…_mvrpz037`, **6 steps, 0 refusals**, `stop_reason: typed_text_verified_in_transcript` |
| Progress observed | tool card `Rendering the image locally` → `done` · `comfyui` |
| Artefact | asset **`8a3e204c-8f4e-4ba9-b1df-0f12e2a5888c`**, `1024×1536`, `Flux-2-Klein-9B-KV-Q8_0`, seed 254456599 |
| Stored file | `Northstar_backend/data/studio_generated/2e4a7ab96e9941479b068792f592864d.png`, 2,246,742 B |
| Preview | lightbox opened (`run …_mvrq2csp`) — `screenshots/mogra_t1_20261028/t1-12-preview-lightbox.png` |
| Download | `run …_mvrq2woo` → `C:\Users\T2Hol\Downloads\generated image (Flux-2-Klein-9B-KV-Q8_0).png`, 2,246,742 B, PNG magic, **1024×1536**, SHA-256 **identical** to the stored artefact |
| Persistence after refresh | `run …_mvrq3a82` — asset card, `View`/`Download` and asset id all still present (`t1-14-after-refresh.png`) |
| Persistence at the data layer | `GET /api/chat/sessions/6d2a2a2c…/messages` → assistant turn `status: done`, `cancelled: false`, parts `thinking, tool, text`; tool `generate_image` `ok: true` with `asset_meta` `{width:1024, height:1536, url:/api/design-studio/assets/…/file}` |

The rendered image is a real kraft pouch on marble with a botanical sprig and **no
fabricated text** — the visual matches the brief's Lane B boundary.

---

## 5. Defect found, repaired, and pinned

### 5.1 The Design Studio composer became un-clickable (`scrollbar-gutter`)

Six consecutive `action_error` timeouts, all identical:

```
TimeoutError: browserBackend.callTool: Timeout 5000ms exceeded.
 - locator resolved to <textarea data-testid="chat-input" …>
 - attempting click action
   - waiting for element to be visible, enabled and stable
```

`uiScale` was **100**, so this was *not* the previously documented CSS-`zoom`
bug. `click body` succeeded while every element inside `.chat-shell` failed, and
`[data-testid="chat-new"]` failed too — so it was the shell subtree, not the
composer.

A diagnostic Playwright run (localhost-only, per the AGENTS.md e2e exception)
sampled the composer's box over 20 animation frames in a clean browser: **20/20
identical, zero running animations, zero transitions**. The page was not
inherently unstable — the layout was oscillating only in the operator's live
session, whose transcript sat near the overflow threshold.

Root cause: `overflow-y: auto` on `.chat-stream` with width-scaled artefact
images. The scrollbar appears → the content box narrows → the image gets shorter →
the content stops overflowing → the scrollbar disappears → repeat. The panel
visibly jitters and Playwright's `stable` check (two equal boxes across rAF) can
never settle.

Repair — reserve the gutter, so a scrollbar's presence can never change layout:

* `northstar-os-ui/src/styles/chat.css` — `scrollbar-gutter: stable` on `.chat-stream`
* `northstar-os-ui/src/styles/simple.css` — same on `.mb-shell .chat-stream`
* `tests/e2e/chat_composer_stability.spec.ts` — new regression spec (gutter is
  `stable` **and** the composer box is identical across 20 frames)

**Causality proven, not assumed:** with the fix stashed the spec **fails**; with it
restored the spec **passes**. `npm run build` → **0 errors** (2.73 s).

After the repair the identical workflow succeeded first time (6 steps, 0 refusals).

---

## 6. Two further boundaries recorded

1. **Reload during an in-flight turn loses the turn.** My first T1 attempt reloaded
   the page while the assistant was still finishing; the backend kept the user
   message (06:04:22) and the render bytes (06:06:06) but persisted **no assistant
   turn**, so the work was orphaned from the transcript. A later aborted turn left
   an empty assistant row that renders as *"Stopped — the partial answer was saved
   as partial."* Reload should not be able to destroy a completed tool result.
2. **Chrome Connect has no file-input verb.** The plan grammar is
   `click / type / press / read / console / diagnose / probe / screenshot`. Any
   workflow that needs to attach a local asset (T2's logo pass) cannot be driven
   through the controller at all — the sanctioned localhost Playwright path can
   (`setInputFiles`). This is a structural blocker for T2, not a flake.
3. **`00_STATE.json` is still not writable by this session.** `opencode.json`
   denies `edit` on it (`permission.rejected: Permission denied: edit`), so the
   campaign entry for this pass is recorded here and in the commit message only.
   It still needs a path that is allowed to write the state file.

---

## 7. T3 — render and download pass, refresh persistence fails

Ran the repo's **existing** `tests/e2e/acceptance-mogra.spec.ts` (no replacement
test was written) on `chromium-desktop`, three times.

| Assertion | Result |
|---|---|
| turn completes with a tool summary for 2000×2000 | **PASS** |
| artefact `<img>` decodes at `naturalWidth/Height = 2000×2000` | **PASS** |
| download control saves a PNG whose header says 2000×2000 | **PASS** — 4,139,675 B |
| after `page.reload()` the artefact is still in the transcript | **FAIL** |

The bytes and the record are not the problem:

* `GET /api/design-studio/assets/2f2dbed6…/file` → **200, 4,139,675 B, image/png**
* the turn persisted `status: done`, `cancelled: false`, with `asset_meta`
  `{width:2000, height:2000, url:/api/design-studio/assets/…/file}`

**Actual boundary (observed after reload):** the app resumes the **wrong
session**. In the post-reload frame the rail's *active* item is the empty
**"New chat / 4m ago"**, while the session that actually carried the turn sits
unselected below it. The transcript therefore renders the user message with no
assistant turn at all — the tool card and the artefact are not "lost", the page
simply opened a different, empty conversation.

The sequence that produces it is `New chat` → send immediately → reload:
`newChat()` removes the `localStorage` resume pointer
(`ns-chat-session:<focus>`), and the pointer that ends up written afterwards does
not name the session the turn actually used. T1 did not hit this because the
operator's pointer already named the T1 session.

Two follow-on repairs were made while chasing this, and both stand on their own:

1. `ChatSurface` re-ran `loadSession` on **every** `sessions` state update, which
   blanked and refilled `messages`; it now resumes **once per focus**.
2. The spec's wait predicate was racy — `/2000\s*[x×]\s*2000/` also matches the
   model's own reasoning text ("width: 2000 … height: 2000"), so the assertions
   could run while the turn was still generating. It now waits for the tool
   summary (`/Rendered a 2000x2000 image/`, `/Rendered a 1464x600 image/`).

**Neither repair fixed the post-reload session pointer**, and this pass does not
claim T3. The correct repair is to persist the turn's session id as the resume
pointer at the moment the session is created *and* when the turn starts, then pin
it with the assertion that already catches it.

T5 never ran: the spec is serial and T3 fails first.

---

## 8. Classification

| Item | Classification | Basis |
|---|---|---|
| Readiness (Tys / Bojo / worker / controller / listeners / runners) | **VERIFIED COMPLETE** | §1, after clearing the orphan runner |
| T1 pouch hero render | **VERIFIED COMPLETE** | §4 — submit, artefact, preview, download, refresh persistence, data layer |
| Composer actionability defect | **VERIFIED COMPLETE** (repaired + pinned) | §5, regression fails without the fix |
| Bojo routing the UI render to the creative lane | **FAILED** (defect logged, not repaired) | §3.1 |
| Reload discards an in-flight turn | **FAILED** (defect logged, not repaired) | §6.1 |
| T2 compositor label | **BLOCKED** | §6.2 — no file-input verb; plus the brief's own Lane A blockers (`kit-mogra` still the placeholder palette, no `pouch-mogra-lm6` / `pouch-mogra-shi8` presets) remain unfixed, so no pouch render may be presented as dimensionally accurate |
| T3 2000×2000 MAIN | **FAILED** on refresh persistence only | §7 — render, decoded size and downloaded PNG all passed; the reload opens the wrong session |
| T4 lifestyle | **DEFERRED** | depends on the same refresh defect |
| T5 A+ 1464×600 | **DEFERRED** | did not run (serial after T3) |
| T6 dieline/prepress | **DEFERRED** | engine-verified only, never UI-accepted |
| T7 Wan+Piper 5 s | **DEFERRED** | engine hardcodes 49/97 frames; needs a `frames` parameter |
| T8 vision QC | **DEFERRED** | engine-verified only |
| C3 / C4 (creative surface) | **OPTIONAL EXCLUSION** | previously verified unauthenticated, unchanged by this pass |
| C5 Product Designer re-audit | **DEFERRED** | not reached |

**Product acceptance is claimed for T1 only.** The Tys infrastructure working is
not acceptance, and this report does not present it as such.

---

## 9. Bounded execution

| Budget | Used |
|---|---|
| Substantive repair cycles (max 10) | **3** — `scrollbar-gutter` (verified), `ChatSurface` resume-once-per-focus, and the racy spec predicate. Only the first is proven to close its defect. |
| Campaign wall clock (max 90 min) | ~70 min; stopped at the T3 session-pointer boundary rather than starting a speculative fourth repair without time to verify it |
| Repeated unchanged failure (max 2) | The click failure was reproduced twice, then the variable was changed each time (no-navigation, different target, pinned viewport, diagnostic harness, window state) instead of retried blind |

Renders are serialised by the existing cross-process GPU lock; one render at a
time. No paid provider, no purchase, no model download, no licence acceptance, no
Amazon host, no push. No model deleted. Chrome profile isolation untouched;
`chrome.exe` was never killed (the operator's window was restored and resized, not
replaced).

---

## 10. Evidence index

```
Northstar_backend/data/tys/evidence/tys_6554df6153d4.jsonl   orchestrator plan + inspect step
Northstar_backend/data/tys/evidence/tys_7d00cf26f928.jsonl   execution task evidence
screenshots/mogra_t1_20261028/t1-recon-01-design-studio.png    live surface, uiScale 100
screenshots/mogra_t1_20261028/t1-11-submitted.png              prompt in the composer/transcript
screenshots/mogra_t1_20261028/t1-12-preview-lightbox.png       preview lightbox, real render
screenshots/mogra_t1_20261028/t1-13-after-download.png         after the download control
screenshots/mogra_t1_20261028/t1-14-after-refresh.png          artefact survives reload
screenshots/mogra_t3_20261028/T3-rendered-2000.png             T3 render
screenshots/mogra_t3_20261028/T3-after-refresh-FAILED.png      T3 after reload
reports/acceptance_restart_20261027/T3-downloaded.png          T3 downloaded PNG
Northstar_backend/data/studio_generated/2e4a7ab9…png           T1 stored artefact
```

Controller journals (operator-side, `Default Project/data/agent-journal/`):
`…mvrpz037` (submit), `…mvrq2csp` (preview), `…mvrq2woo` (download),
`…mvrq3a82` (refresh).

---

## 11. Next three actions

1. **Repair the post-reload session pointer** (§7) — `newChat()` → send → reload
   resumes the empty "New chat" instead of the session that carried the turn.
   Persist the turn's session id as the resume pointer when the session is created
   *and* when the turn starts, then re-run `acceptance-mogra.spec.ts` for T3 → T5.
2. **Repair `ChatSurface`'s reload-during-turn behaviour** (§6.1) so a completed
   tool result can never be orphaned from its turn.
3. **Unblock T2** — add the two MOGRA pouch presets and the real `kit-mogra`
   palette the brief specifies (`presets.js` still ships the placeholder), then give
   the label pass a supported attachment path that does not depend on a file dialog.
