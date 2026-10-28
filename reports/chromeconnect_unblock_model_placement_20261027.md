# Chrome Connect unblock + owner model placement

**Date:** 2026-10-27 (runs executed 2026-10-28 UTC)
**Branch:** `feature/chrome-connect-3.0`
**Scope:** restore Chrome Connect to a working interaction lane on the owner's
approved Profile 6; restore the owner-required model placement (Bojo on CPU, 27B
worker GPU-only and on demand); pass the first acceptance milestone through
Chrome Connect only.

---

## 0. Spec-vs-disk reconciliation (read this first)

The task named `lib/chromecontrol/agent-loop.js` and the `createPwTool`
implementation. **That path is not in this repo.** The controller lives outside
the working tree, at the root the repo's own guard already points at:

| Referenced by the task | Actual location |
|---|---|
| `lib/chromecontrol/agent-loop.js` | `C:\Users\T2Hol\OneDrive\Documents\Default Project\lib\chromecontrol\agent-loop.js` |
| `createPwTool` | `…\Default Project\lib\chromecontrol\pw-tool.js` |
| planner | `…\Default Project\lib\chromecontrol\plan.js` |
| transport | `…\Default Project\scripts\chromecontrol-playwright-bridge.js` |
| MCP entry point | `…\Default Project\scripts\chromecontrol-mcp-server.js` |
| owner policy | `…\Default Project\config\chromecontrol_policy_owner.json` |

This repo's half of the rule is `tools/chromeconnect_guard.py` (import hook +
port-9222 lock + `cc_call`). No file in this repo was assumed to be the
controller.

---

## 1. How `mode.readOnly` is actually enforced

**Answer: it is an asserted invariant, not a capability switch. It never
disables an action.**

1. `agent-loop.js:95` constructs the tool with a **hard-coded** mode:

   ```js
   const pw = createPwTool({ ..., mode: { headed: true, readOnly: true } });
   ```

   There is no option, argument or environment variable that lets a caller pass
   `readOnly: false`. The run's declared posture is fixed.

2. `pw-tool.js` `assertMode()` (lines 194-197) runs on **every** `invoke()`,
   after the policy checks and before the transport:

   ```js
   if (mode.headed !== true) refusal('headed_mode_required', ...);
   if (mode.readOnly !== true) refusal('read_only_required', ...);
   ```

   A `false` value is a *refusal*, not a downgrade. So `readOnly` behaves like an
   assertion about how the run was configured — it is checked, never used to
   decide whether `click` or `type` may run.

3. **Click / type / key interactions exist and are supported.**

   | Layer | Evidence |
   |---|---|
   | `ACTION_MAP` (pw-tool.js:47-64) | `click → click`, `type → type_text`, `press_key → press_key` |
   | Exposed surface (pw-tool.js:349-366) | `click()`, `type()`, `pressKey()` |
   | Credential guard (pw-tool.js:352-358) | `type()` refuses only password/otp/cvv/card selectors |
   | Planner grammar (plan.js:68-79) | `click <sel>`, `type <sel> \| <text>`, `press <Key>` |
   | Transport (bridge 1134-1146) | dispatches `click`, `type`, `press_key` to `@playwright/mcp` |

4. **The owner-approved localhost grant already allows every one of them.**
   `config/chromecontrol_policy_owner.json` grants, for both `127.0.0.1` and
   `localhost`: `click`, `type`, `type_text`, `press_key`, `hover`, `scroll`,
   `select`, `drag`, `form_submission`, `read_page`, `screenshot`, `extract` …
   `policy.js:evaluateActionForHost` returns `allowed:true` for them, and
   `isLocalOrigin()` makes the grant active **without** a per-task
   authorization (owner authorization 2026-10-27). `classifyAction` classes them
   `read_only`.

**Conclusion:** interaction is **not** disabled by the tool layer, and therefore
**no policy edit and no controller code repair was needed or made**. Guardrails
are byte-identical to the operator baseline:

```
fingerprint 1f84d42114620702c20d0181d12014c5c52b2c83d38dfcfec74290ccc4379cfa
baseline    1f84d42114620702c20d0181d12014c5c52b2c83d38dfcfec74290ccc4379cfa
intact      true
```

---

## 2. What was actually blocking Chrome Connect

Two independent blockers, found in order.

### 2.1 No browser attached (the headline blocker)

`chromeconnect_status` reported:

```
picked_profile            { captured: false, reason: "extension_relay_not_seen_yet" }
browser_attachment        "unknown"
transport_profile_binding "mismatch"   (class: REQUIRED)
cdp_url                   null
```

Cause: **zero `chrome.exe` processes**. Every static check passed — the pin
resolved to exactly `Profile 6`, the display name matched exactly
`NORTHSTAR OS`, and the owner lease was valid — and the Playwright bridge
extension `0.4.0_0` was present in
`…\Chrome\User Data\Profile 6\Extensions\mmlmfjhmonkocbjadbfplnigmagldckm`.
There was simply nothing to attach to. Per the standing owner rule, Chrome was
**not** killed, replaced or auto-launched; the owner opened Profile 6.

After reattachment the run navigated, read the live page and screenshotted —
so the relay, the profile pin and the transport were all proven before any
interaction was attempted.

### 2.2 Every actionability-gated action failed — CSS `zoom`

Read paths (`navigate`, `readLivePage`, `probe`, `screenshot`) worked.
`click` **and** `type` both died identically:

```
TimeoutError: browserBackend.callTool: Timeout 5000ms exceeded.
 - locator resolved to <textarea data-testid="chat-input" …>
 - attempting click action
 - waiting for element to be visible, enabled and stable
```

The same failure occurred for an unrelated, plain, enabled button
(`button[data-testid="chat-new"]`) — so it was shell-wide, not element-specific.

The element was provably fine. Probe of the composer:

```
rect 719,986 384x25 · display block · opacity 1 · visibility visible
transform none · topmost_at_center = TEXTAREA   (nothing covering it)
```

Root cause, from `northstar-os-ui/src/styles/simple.css`:

```css
.app-scale { zoom: var(--ui-scale, 1); width: calc(100vw / var(--ui-scale,1)); … }
html[data-ui-scale="90"] { --ui-scale: 0.9; }
```

The persisted display scale was **90%**, i.e. `zoom: 0.9` on the element wrapping
the entire app. Playwright's `visible + enabled + stable` wait never converges
under that subtree zoom.

**Confirmed by experiment:** with the owner's one click setting the scale to
100% (`html[data-ui-scale="100"]` → `zoom: 1`), the identical plan succeeded
first time:

```
click → type → press Enter   all OK, 0 refusals
status COMPLETE · stop_reason typed_text_verified_in_transcript
```

This is a **product defect, not a policy gate**: the shell is not
automation-actionable at a non-100% display scale. Workaround applied: leave the
scale at 100%. Proposed repair (not applied, owner review): stop driving the
frame with CSS `zoom` and use a scale mechanism that does not create an
unstable paint/layout context, or clamp scale to 100% while a controller session
is active.

---

## 3. First acceptance milestone — PASSED

Through Chrome Connect only. No standalone Playwright browser, no terminal or
API shortcut was used for any acceptance claim.

| Requirement | Evidence |
|---|---|
| Authoritative NorthstarOS UI | `http://127.0.0.1:8101/ui/design-studio`, title `NorthstarOS — Retail Arbitrage Suite` |
| Origin / grant | host `127.0.0.1` is on the operator allowlist; per-host grant allows `click`/`type`/`type_text`/`press_key`; run journal records `policy_action` + `risk: read_only` for each call |
| Auth posture visible + labelled | red banner **`DEV: AUTH DISABLED — local loopback only`** at (0,0,1760×33), `visibility: visible`, `topmost_at_center` = the banner itself; role chip **Operator**; dev shim identity `demo-t2 / org-t2 / operator` |
| Focus composer | `click textarea[data-testid="chat-input"]` → OK |
| Send harmless prompt | `type … | Reply with exactly this and nothing else: CC ACCEPTANCE OK` → `press Enter` |
| User message captured | transcript shows the message verbatim |
| Completed assistant response | assistant turn completed: `Thought · 403 chars` then **`CC ACCEPTANCE OK`** |

Journal of the accepting run (`…/data/agent-journal/2026-10-28T04-28-43-577Z_…jsonl`):

```
seq=858 tool=click     policy_action=click     risk=read_only
seq=864 tool=click     policy_action=click     risk=read_only  url=http://127.0.0.1:8101/ui/design-studio
seq=870 tool=type      policy_action=type_text risk=read_only  url=http://127.0.0.1:8101/ui/design-studio
seq=876 tool=press_key policy_action=press_key risk=read_only  url=http://127.0.0.1:8101/ui/design-studio
```

Zero refusals, zero blockers in the accepting runs.

Evidence images: `screenshots/chromeconnect_acceptance_20261027/`
(`cc-accept-08-banner-fixed.png` is the definitive one — banner visible, user
message and `CC ACCEPTANCE OK` reply in the same frame).

**Honest caveat on one intermediate run:** the plan that opened a *new* chat
reported `success_unmet:typed_text_not_in_transcript`. That is a timing
artefact, not a lost keystroke — the predicate samples the page immediately
after `Enter`, while the new chat was still mounting. The very next read shows
the message and the reply. The controller was right to refuse to claim success;
it was reading too early.

---

## 4. Defects found and repaired

### 4.1 The dev auth banner was rendered but invisible

`elementFromPoint` at the banner's own centre returned **`CANVAS.cosmic-canvas`**:
the banner is a static block, `.cosmic-canvas` is `position:fixed; z-index:0`,
so the canvas painted over it. The posture label existed in the DOM, was
correctly coloured `rgb(180,67,47)`, and no human could read it.

Fix — `northstar-os-ui/src/App.jsx`, both banners (dev + owner-test-mode):

```jsx
style={{ position: 'relative', zIndex: 10, … }}
```

10 sits above the canvas and below the sticky `.top-nav` (z-index 50).
Verified: `topmost_at_center` now returns the banner `DIV`, and
`cc-accept-08-banner-fixed.png` shows the red band.

### 4.2 The dev-shim identity was billed to the anonymous rate bucket

The live chat turn answered:

> `Error: Max 30 requests per minute on foundation plan — nothing was fabricated. Retry`

`rate_limiter._get_plan` resolved Bearer → cookie → **anonymous `foundation`
(30/min)**. The dev shim is the only identity a local session has, so every page
load (10-30 calls) and the chat stream competed for 30 requests against a
`mover` budget of 300. The cookie branch had already been fixed for exactly this
class of bug; the shim was left behind.

Fix — `Northstar_backend/rate_limiter.py`: resolve the shim through the
**existing** gate `auth_deps._dev_shim_identity` (development process +
loopback effective client + explicit `X-User-Id`, else `None`) and bill it like
any other signed-in caller.

**Live verification after a sanctioned restart**
(`scripts/launch_alpha.ps1 -Restart -NoTunnel -NoAutothink -NoComfy`, health OK,
signing key loaded from the stored secret and never printed):

```
35 requests with dev-shim headers -> HTTP 200 x35      (before: #31 would 429)
GET /health                       -> 200
GET /api/v1/foundation/me         -> user_id=demo-t2 role=operator org=org-t2
```

New tests `Northstar_backend/test_rate_limit_dev_shim.py` (9) + existing
posture tests: **14 passed**. They also pin that the shim still **fails
closed**: production process → `foundation`; remote peer → `foundation`;
untrusted `X-Forwarded-For` → `foundation`; no header → `foundation`.

### 4.3 A transient 429 signed the operator out

`foundation/session.jsx` treated *any* non-401 bootstrap failure as an
unauthenticated session, and under `LOCAL_DEV` `/sign-in` immediately redirects
to `/home`, so a 429 produced a `/home ↔ /sign-in` redirect loop mid-session.

Fix: retry once on 429/5xx/network before reporting anything, and mark the
returned failure `retriable: true` so it is no longer indistinguishable from an
expired session. `npm run build` → **0 errors**.

---

## 5. Model placement restored

### 5.1 Was Bojo really on the GPU?

Yes — **real dedicated VRAM, not shared-memory reporting.**

Before: `ollama ps` → `bojo:latest … 100% GPU … 2.5 GB`, `nvidia-smi` device
`3825 / 16303 MiB`. After `ollama stop bojo`:

```
ollama ps   -> (nothing loaded)
nvidia-smi  -> 584 MiB / 16303 MiB          (Δ = 3241 MiB)
```

A 3.24 GB device-level drop equals the model's footprint, and the device was at
23% of capacity, so there was no WDDM over-subscription to spill into system
memory. Note the limit of the evidence: **per-process VRAM is `[N/A]` under
WDDM on Windows** (`nvidia-smi --query-compute-apps` refuses), so attribution is
device-delta plus Ollama's own layer-placement report — it is not a per-process
number and none was invented.

### 5.2 What was changed

`scripts/bojo-cpu.Modelfile` (new) rebuilds the model in place:

```
FROM bojo:gpu-orig
PARAMETER num_gpu 0
… (num_ctx 8192, num_predict 2048, temperature 0.2, top_k 20, top_p 0.9,
   presence_penalty 1.5 — byte-identical to before)
```

* Model-level, not per-call: **every** caller gets CPU, not just chat.
* `ollama cp bojo:latest bojo:gpu-orig` preserves the original tag.
* `ollama create` reported **`using existing layer`** for every layer — nothing
  downloaded, no extra weights on disk.
* Inheriting the local tag kept `TEMPLATE`, `SYSTEM`, `RENDERER/PARSER qwen3.5`
  **and the vision Projector** (`ollama show` still lists `vision`).

Verified live:

```
ollama ps -> bojo:latest  2.4 GB  100% CPU   ctx 8192   llamacpp
nvidia-smi -> 584 MiB / 16303 MiB   (identical to the no-model baseline => 0 MiB)
tool call -> engine_status(lane="Northstar"), 1 tool_call, done_reason=stop, 16.7 s
```

The running `llama-server.exe` (pid 11628, 2819 MB working set) is **Ollama's own
runner** at `…\Programs\Ollama\lib\ollama\llama-server.exe`, serving from
`…\.ollama\models\blobs\` — i.e. Bojo resident in **system RAM**, not the 27B
worker.

### 5.3 The 27B worker

* It is **not** an Ollama model — it is `llama-server.exe` on `127.0.0.1:8080`,
  started by `scripts/start-northstar-llm.ps1` with `-ngl 99` (full GPU offload).
* State now: **not running** (`:8080` closed), weights present
  (`Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` 9.73 GB) → genuinely **on demand**.
* Bojo and the 27B worker can no longer contend for the GPU: Bojo is pinned to
  CPU by the model definition, and a test asserts that pin.
* Launcher repaired: its pre-launch step evicted a hard-coded
  `"northstaros-qwen3.8:27b"` that **no longer exists in Ollama**, so it evicted
  nothing and still printed success. It now drains `/api/ps`. VRAM is moot with
  Bojo on CPU, but RAM (15.4 GB) is this box's binding constraint for a 10.4 GB
  model plus a 64K KV cache.
* "Must not remain resident during ComfyUI work": `studio_generation.unload_brain()`
  drains `/api/ps` and refuses the render if the list is non-empty; Bojo now also
  holds 0 VRAM. ComfyUI confirms the room: `vram_free 14.64 GB`.

Tests: `Northstar_backend/test_bojo_cpu_placement.py` — **7 passed** (num_gpu 0,
inherited original, unchanged sampling params, `-ngl 99`, no service
registration, `/api/ps` drain, `CHAT_NUM_GPU` defaulting to `None` so no chat
turn can silently re-enable GPU placement).

**Side effect to record:** during the acceptance a *previous* conversation in the
same session queued "generate the Amazon MAIN listing image…", and the model
executed it for real — Flux-2-Klein-9B-KV-Q8_0, 2000×2000, via local ComfyUI.
Local, no spend, no external call. It happened because the tab was on a session
that already carried that prompt.

---

## 6. Not done / open

1. **`00_STATE.json` was not updated.** This repo's own `opencode.json` denies
   `edit` on `00_STATE.json`, so the state file is intentionally untouched by
   this session. Everything here needs to be folded in by a path that is allowed
   to write it.
2. **CSS `zoom` at non-100% display scale still breaks automation.** Workaround
   only (scale at 100%). The real repair needs owner sign-off because it changes
   the shell's scaling mechanism.
3. **The `stable`-wait failure is silent.** A better controller-side future
   improvement would be an explicit diagnostic when actionability fails only on
   "stable" (it currently surfaces as a generic 5 s timeout).
4. **Model-based upscaling** and the other long-standing open items from
   `00_STATE.json` were not touched.
5. The rate-limit fix is **live and verified**, but the session-bootstrap retry
   (4.3) is verified only by build + reasoning; no live 429 was induced to
   exercise it.

## 7. Commands run (for reproduction)

```
ollama cp bojo:latest bojo:gpu-orig
ollama create bojo:latest -f scripts/bojo-cpu.Modelfile
ollama stop bojo
python -m pytest test_bojo_cpu_placement.py -q            # 7 passed
python -m pytest test_rate_limit_dev_shim.py test_rate_limit_posture.py -q   # 14 passed
cd northstar-os-ui && npm run build                       # 0 errors
powershell -File scripts/launch_alpha.ps1 -Restart -NoTunnel -NoAutothink -NoComfy
```

Chrome Connect runs: `chromeconnect_status`, `chromeconnect_preflight`,
`chromeconnect_run` ×11, `chromeconnect_journal`.
