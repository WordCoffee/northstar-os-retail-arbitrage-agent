# Defects — NorthstarOS acceptance campaign

Status vocabulary: `open` · `code-fixed-unverified` · `verified-fixed` · `blocked` · `deferred`.

---

## D-01 — `chromeconnect_run` is refused for every run unless `require_isolated:false` is passed explicitly

**Severity:** high (blocks the entire browser layer)
**Status:** open — root cause not yet confirmed; the controller code may already be correct and the *host* may be injecting the default.
**Discovered:** 2026-10-23, first campaign run.

**Expected:** `chromeconnect_run` on an allowlisted loopback URL with no `require_isolated` argument runs in read-only headed mode against the operator-pinned profile, and reports `isolated_verified: false`.

**Actual:** `status: REFUSED`, `stop_reason: policy_or_gate_refusal:isolated_profile_required`, `refusals[0].detail = profile "Profile 6" is not an isolated research profile`, `steps: 0`, zero Playwright calls.

**Evidence:** journal `2026-10-23T06-09-04-293Z_open_the_northstaros_local_suite_and_rea_mvkkkpb7.jsonl`
seq 1 `run_started` → `require_isolated_profile: true`; seq 3 `refusal` from `pw-tool`.
Same task with `require_isolated: false` → `COMPLETE`, 4 steps, `pw_refusals: 0`.

**Analysis:** `scripts/chromecontrol-mcp-server.js` line 349 computes
`requireIsolatedProfile: !!(requireIsolated || restricted)`, and `restricted` is only true for an
Alibaba host (`policy.isAlibabaHost(policy.hostOf("http://127.0.0.1:8000/ui/")) === false`, verified
by running the real policy module). The working-tree file is clean at HEAD `fcc0942`, so the code
path *should* yield `false`. The run nevertheless recorded `true`.
**Hypothesis (not proven):** the MCP host fills the omitted optional boolean with `true` rather than
`false`, or the running child (server PID 27504, started 22 Oct 23:29:24) predates part of the
current tree (`lib/chromecontrol/pw-tool.js` mtime 23:34, commit `fcc0942` 23:30).

**Why not fixed yet:** a controlled restart of the Chrome Connect MCP server is the obvious test, but
killing PID 27504 may not be respawned by the host, which would strand the whole browser layer
mid-campaign. That is an operator decision, not a routine fix.

**Workaround in use (documented, not hidden):** every run passes `require_isolated: false` explicitly
and the report states `isolated_verified: false` / operator profile reused. No policy file was edited;
the guardrail fingerprint still matches its baseline.

---

## B-01 — Local UI requires sign-in; the operator profile has no session for `127.0.0.1:8000`

**Severity:** high (blocks all UI acceptance)
**Status:** blocked — needs a manual operator sign-in.

The SPA landing on `http://127.0.0.1:8000/ui/` resolves to `/ui/sign-in`
(`page_status: READ`, 249 characters of sign-in page text). `launch_alpha.ps1 -Restart` rotates the
public tunnel hostname, so a session established on the previous tunnel address does not apply to
loopback.

Credentials are never entered by the agent and login submission is never automated. The fix is a
human sign-in in the already-open Chrome window, then resume.

---

## D-02 — `apply_label` was not offered to the model in the Create focus

**Severity:** high (would have made the new label lane unreachable in exactly the focus that needs it)
**Status:** verified-fixed

`shell_focus.FOCUS_MODES` lists an explicit tool subset per focus; `create` did not include
`apply_label`, so `tools_for_focus("create")` would never have offered it even though the tool was
registered. Fixed by adding it to the `create` subset, with a regression assertion in
`test_shell_modes.py::test_turn_offers_only_focus_tools`
(`assert "apply_label" in start["tools"]`). 33/33 in `test_shell_modes.py`.

---

## D-03 — every `generate_image` portrait request failed before reaching the engine

**Severity:** high (operator-visible hard failure)
**Status:** verified-fixed (unit + in-process live)

See `00_STATE.json → interface_repair_20261023`. Tool schema capped width/height at 1216 and the
validator raised `height is above the maximum (1216)`; the engine then clamped each axis
independently. Now an aspect-preserving fit into the engine's 1216 px box, with `requested` /
`fitted` / `engine_max_edge_px` reported. Verified: `896x1344 → 816x1216`, `2048x2048 → 1216x1216`.

---

## D-04 — a completed render came back as a blank bag with no way to finish it in chat

**Severity:** high (the operator's headline complaint: "half complete design and an empty bag")
**Status:** verified-fixed in-process; UI verification blocked by B-01

The image model may not paint text or logos (correct), but nothing in chat could composite them, so
the turn ended with an apology. New `Northstar_backend/pouch_label.py` measures the pouch face from
the render (background-median mask → per-side least-squares edge fit → inset trapezoid) and warps a
label drawn from the operator's real logo and real fonts. New chat tool `apply_label`.
Live: `768x1216` and `1024x1216` finished mockups from the operator's own renders plus `logo.png`
(618,399-byte PNG through the tool path). 19 tests in `test_pouch_label.py`.

---

## D-05 — every spoken turn died with `unknown voice 'bojo-narrator'`

**Severity:** medium
**Status:** verified-fixed

Three compounding client bugs (hardcoded voice id, `<select>` displaying a different voice than the
state held, `useCallback([])` freezing the first render's id) plus a mixed-content audio URL. Fixed
client-side and server-side; the route now resolves an unknown voice to a real one and serves the
audio same-origin. Live: `voice_id='bojo-narrator'` → HTTP 200, `voice=microsoft-david-desktop`,
93,942-byte WAV at `/api/chat/voice/audio/…`.

---

## D-06 — reloaded artefacts lost their identity

**Severity:** medium
**Status:** verified-fixed (unit)

`chat_router` persisted only `a.get("id")` in the tool part, so a reloaded session rendered a dieline
SVG and its PDF as two identical cards named "asset", and rendered the SVG through an `<img>`.
Now `asset_meta` carries id/kind/name/width/height/url; `ChatSurface` prefers it and falls back to the
bare id for older turns.

---

---

## D-07 — a run's `data` is the LAST step's result, so `read` + `screenshot` + `console` returns console text as "page data"

**Severity:** medium (evidence quality — could make a failed read look like a pass)
**Status:** open

With `STEPS: read / screenshot / console`, the returned `data.text` was
`### Result\nTotal messages: 0 (Errors: 0, Warnings: 0)` — the **console** step's output — while
`page_status` still said `READ`. Any assertion on `data.text` would have been evaluating the wrong
step. Workaround in use: put `read` LAST, or run it as its own task.

## D-08 — the Simple shell did not fill the viewport; the page scrolled to 2717 CSS px

**Severity:** high (layout; also made the fixed space canvas unable to cover the page)
**Status:** verified-fixed by capture

`.app` only had `min-height: 100vh`, so nothing above `.main-content` had a definite height: the flex
chain collapsed and the document grew to its content. Measured: full-page capture **2619 × 5434**.
After pinning `html`, `body`, `#root` and `.app` to the viewport in Simple mode and painting them in
the space base colour, the capture is **2625 × 1520** — no scroll, no white band.

## D-09 — `screenshot` is always `fullPage: true`

**Severity:** low (evidence fidelity)
**Status:** open — documented limitation, not fixed

The controller hard-codes `page.screenshot({ fullPage: true, scale: 'css' })`. For a fixed-layout app
that both hides the real viewport composition and, before D-08, exposed a white band under the app.
The remaining ~256 px band in capture 04 is consistent with a `100dvh` vs `innerHeight` mismatch in
the extension capture path and is **unverified** — it may be a capture artefact rather than a layout
defect. A viewport-only capture mode is the fix.

## D-10 — `click` on a repeated test id fails with a strict-mode violation

**Severity:** low (test ergonomics)
**Status:** open

`click [data-testid="chat-plan-draft"]` resolved to **3** elements (the session history holds three
plan cards) and the run stopped with `tool_error:action_error`. The grammar has no `nth` support, so
the plan must scope the selector itself:
`.chat-stream > .chat-msg:last-child .chat-plan-actions .chat-plan-btn:first-child` → resolves to 1.

## O-01 — the model answers a complete packaging brief with a plan card instead of acting
**Severity:** medium (product behaviour, arguably by design)
**Status:** open / by design — recorded, not "fixed"

The brief named the tool, the size, the exact tool chain and the logo asset id; the model still ran
`creative_plan` and returned "Plan ready — pick an option below". This is the approval-before-spend
contract working as intended (draft = 34 metered credits), but it costs a turn even when the operator
has already specified everything. `DESIGN_CREDITS_ENFORCE` is unset → **meter-only**, and the cloud
provider is disarmed, so approving the draft costs nothing real.

## D-11 — a plan draft charged credits, rendered, and handed back NO artifact

**Severity:** high (paid approval produced nothing retrievable)
**Status:** verified-fixed (4 regression tests); UI re-run pending

Reported live by the model itself: *"Draft charged (34 credits) but the plan lane returned no
retrievable asset id"*. Root cause: `creative_execute.default_generate` called the `generate_image`
tool with `{"account_id": None}` and no db, and `_t_generate_image` only persists a studio asset when
it has BOTH. The render existed on disk with no id, so the chat could not show it and `apply_label`
had no plate.

Fix: the generator now receives the turn's `ctx`, falls back to the real store when called outside a
chat turn, and renders packaging jobs in portrait (832×1216) instead of a fixed square.
Tests: `test_creative_execute_artifact.py` (4).

## D-12 — the composited label could cover the whole pack and erase its silhouette

**Severity:** medium (quality — the mockup stopped reading as a pouch)
**Status:** code-fixed; recompose verified, UI re-render not re-run

The first live composite (asset `2136ae5b…`) covered the pouch edge to edge because the Flux plate
filled the frame and the face inset was only 3.5 %. Inset widened to 7.5 % x / 6.5 % top / 5 % bottom
plus a hard "printed panel ≤ 86 % of the measured face" clamp. Recomposed v2
(`screenshots/scenarioA-labelled-v2.png`) keeps the pack's edges visible. The remaining flatness is
the plate's, not the compositor's.

## D-13 — the controller reports a corrupted URL (`/ui/listings)`)

**Severity:** low (evidence accuracy)
**Status:** open

A read after navigating to `/ui/listings` returned `url: "http://127.0.0.1:8000/ui/listings)"` — a trailing
parenthesis that is not in the requested URL. It also appeared once on `/ui/`. Navigation itself worked
(`page_status: READ`), so this corrupts the recorded URL rather than the page. Any report that copies
`data.url` verbatim will contain a URL that does not exist.

## D-14 — the operator's own account cannot reach any Advanced/service workspace

**Severity:** high (product surface, not a code fault)
**Status:** blocked-by-entitlement — needs an operator decision, gates were NOT touched

`/beta-ops` redirects to `/home`; `?shell=advanced` is rewritten to `?shell=simple`. Cause: role
`operator` on plan `whetstone`; `shell_router` grants advanced view only to
`ADMIN_ROLES = ("admin", "internal_platform_admin")`, a plan with the explicit `advanced_view` ui gate,
or an org with `advanced_reports`.

Consequence: Design Studio, Listing Guardian, AdPilot, Golden Goose, Memory Bank, Beta Ops and Admin are
all unreachable in the browser, so "every service workspace" cannot be acceptance-tested at this tier.
Nothing was changed in `shared/subscription-plans.json` or the capability resolver to work around it.

## O-02 — CORRECTED: the model did not ignore instructions; the tool was not offered

**Severity:** n/a (my earlier finding was wrong)
**Status:** corrected

An explicit "call apply_label with these ids" instruction was answered with `system_status` and
`service_catalog`. I first logged this as the model disobeying. It was not: my sweep had left the
session on the **Grow** focus, and `tools_for_focus("grow")` excludes `apply_label`, so the tool was
never in the offered set — and the model said exactly that. After switching to the **Create** focus the
same message produced the composite on the first try. The focus-scoped tool surface is correct by
design; the lesson is that a sweep which clicks focus chips changes the state of the next test.

## O-03 — one turn failed with an honest engine error minutes after an explicit eviction

**Severity:** low
**Status:** observed, self-recovering

`"…check ollama server logs… Start it with: ollama serve — then resend this message."` with
`Error: unknown — nothing was fabricated.` Ollama was in fact listening and serving the 27B
(`/api/ps` returned it). The identical next turn succeeded. The failure was surfaced truthfully rather
than faked, which is the correct behaviour; the transient itself is unexplained.

## Deferred / not yet investigated

- Live voice is **not** streaming. It is record → transcribe → answer → synthesise, one turn at a
  time. It must not be described as "live voice" until incremental streaming exists.
- Export/download acceptance is untested; downloads are a policy-prohibited action class in the
  controller for restricted hosts and were never exercised.
