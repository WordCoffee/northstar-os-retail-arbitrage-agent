# REA Runbook — Packify.ai & DYP.ai mockup/quality deep dive

- **Purpose:** executable runbook for a later session (agent + operator present) to reverse-engineer the *mockup/photoshoot quality mechanics* of Packify.ai and DYP.ai with REA 6.5.0.
- **Status:** prepared 2026-10-16, read-only environment inspection only. **No live scan was run while authoring this runbook.**
- **Provenance:** method and commands adapted from `reports/competitor_re_packify_dyp_20261016.md` (previous RE, 2026-10-16) and REA docs from the local checkout `C:\Users\T2Hol\Desktop\rea`.
- **Scope discipline (must hold):** public surfaces only. Operator drives 100% of on-screen interaction in their own signed-in account. The agent never enters credentials, never solves a CAPTCHA, never submits a form, never buys credits, never calls the competitor's authenticated public API. REA attaches passively (no clicks, no input, no `Runtime.evaluate`).

---

## 1. REA status on this machine

**Installed and working — REA 6.5.0.** Verified during authoring:

| Check | Result |
|---|---|
| `npx rea-agents --version` | `6.5.0` |
| `rea --version` (on PATH) | `6.5.0` |
| Global install | `rea-agents@6.5.0` in npm prefix — shim at `C:\Users\T2Hol\AppData\Roaming\npm\rea.cmd` (plus `rea`, `rea.ps1`) |
| Node / npm | `v24.15.0` / `11.12.1` — meets REA's requirement (`>=24.11` or `22.19+` or `26+`) |
| Local checkout `C:\Users\T2Hol\Desktop\rea` | **Source checkout only** (has `.git`, docs; **no `node_modules`, no `dist`**) → not directly runnable. It is the docs/source reference; do not "run" it. Use the global `rea` or `npx`. |
| MCP registration | **Not registered** for OpenCode: `rea doctor --client opencode --json` → `registration:opencode` missing/`config_drift`, skill missing. **Use the CLI** (what the previous session proved). Optional registration below. |
| Native analysis engines (Hopper/Ghidra/IDA/JADX) | Absent / failing self-test — **irrelevant** here. Browser CDP observation and static JavaScript analysis need no native engine. |
| Chrome | `C:\Program Files\Google\Chrome\Application\chrome.exe` (Brave also installed at `C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe`) |
| Shell | Windows PowerShell 5.1 (`5.1.26100.9711`) — **no PowerShell 7 (`pwsh`)**. Encoding rules in §1.3 apply. |

### 1.1 How to invoke REA (pick one)

```powershell
# A) global install — proven, pinned to 6.5.0 (recommended)
rea <command> ...

# B) one-off runner, pin the version for reproducibility
npx -y rea-agents@6.5.0 <command> ...

# C) optional MCP registration for OpenCode (NOT required; needs operator approval + client restart)
npx rea-agents@latest setup --client opencode
#    or: rea mcp add --agent opencode
# MCP tool names mirror the CLI: list_browser_targets, inspect_web_page, analyze_web_bundle,
# export_web_scripts, capture_web_screenshot, observe_web_session.
# MCP argument names: cdp_endpoint, target_id, allowed_origins, observation_ms,
# include_json_body_shapes, include_websocket_shapes, include_script_sources, ...
```

If a shell does not resolve `rea`, use form B. Do **not** build the local checkout — no unreleased feature is needed for this task.

### 1.2 Browser prerequisite — dedicated Chrome profile + loopback CDP port

REA **never launches, owns, or closes the browser**. Start Chrome yourself, with a dedicated profile and an explicit debugging port, then keep it open for the whole session.

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Users\T2Hol\AppData\Local\rea-packify-profile"
```

Verify the endpoint answers before any REA command:

```powershell
Invoke-RestMethod http://127.0.0.1:9222/json/version | Select-Object -ExpandProperty Browser
# fallback:
Get-Content "C:\Users\T2Hol\AppData\Local\rea-packify-profile\DevToolsActivePort"
```

Circumstances:
- The profile dir is **dedicated and persistent** — the operator signs into Packify/DYP **once** in this profile; sign-in persists for later sessions. The agent never touches credentials.
- **Chrome ≥136 ignores `--remote-debugging-port` for the default profile** (REA docs, "Browsers without HTTP discovery") — that is exactly why the dedicated `--user-data-dir` is mandatory. You cannot attach to the everyday profile this way.
- REA requires a literal loopback endpoint: `http://127.0.0.1:9222` (or `[::1]`, or a `ws://127.0.0.1:9222/devtools/browser/<id>` socket). `localhost`, LAN IPs, HTTPS are **not** valid. Do not expose the port beyond loopback.
- Keep the browser running during the entire investigation. The previous session's two late capture windows failed (`provider_unavailable / disconnected`) because the dedicated profile was already closed — see §4.

> **Workspace rule check (Chrome Connect):** this repo's AGENTS.md reserves port 9222 for the single-controller Chrome Connect flow. REA attach is *passive/read-only* (no drive, no input, no eval) and was used for the previous investigation, but if a Chrome Connect controller is active, do one of: (a) pause Chrome Connect for the session, or (b) launch REA's profile on a **different loopback port** (e.g. `--remote-debugging-port=9223`) and pass `http://127.0.0.1:9223` to every REA command. Never run both against the same port at once.

### 1.3 Windows-specific caveats (PowerShell 5.1)

1. **Never use `>` to save REA output in PowerShell 5.1.** `rea ... --json > file.json` writes **UTF-16LE** and corrupts the JSON. Use `cmd /c '... > "file.json"'` (raw bytes, UTF-8 as REA emits) — the pattern used throughout this runbook. Alternative (BOM-free) PowerShell writeback:
   ```powershell
   $out = (rea <command> ... --json) -join "`n"
   [System.IO.File]::WriteAllText("C:\path\file.json", $out, (New-Object System.Text.UTF8Encoding($false)))
   ```
   `| Out-File -Encoding utf8` on PS 5.1 adds a BOM — avoid it.
2. REA emits compact JSON when piped/redirected (fine for files).
3. Exit status: `0` = completed (may still contain partial evidence/warnings); `1` = did not complete (structured error envelope on stdout). Check both the file content and `$LASTEXITCODE`.
4. Paths with spaces stay quoted; the repo path contains spaces.
5. Validate a saved capture starts with `{` (bytes `123`) and not `FF FE`:
   ```powershell
   $b = [System.IO.File]::ReadAllBytes("C:\path\capture.json"); $b[0..2] -join ','
   # good: 123,34,101   bad (UTF-16LE): 123,0,34  or BOM: 239,187,191
   ```

### 1.4 Preflight (run before every session, ~2 min)

```powershell
rea --version
Invoke-RestMethod http://127.0.0.1:9222/json/version | Select-Object -ExpandProperty Browser
cmd /c 'rea list-browser-targets http://127.0.0.1:9222 --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\01_targets.json"'
```

Read `normalized_result.targets[]` — each target has `target_id`, `url`, `title`, `origin`. Target IDs are browser-instance-specific; re-list after every Chrome restart. Optional origin filter (one origin per flag, flag is repeatable; omitting it defaults to the selected page's current origin): add `--allowed-origins https://www.packify.ai`.

---

## 2. Reverse-engineering targets, rationale, and exact command sequences

### 2.0 Session scaffolding (once)

```powershell
New-Item -ItemType Directory -Force "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures" | Out-Null
New-Item -ItemType Directory -Force "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\analysis" | Out-Null
New-Item -ItemType Directory -Force "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\notes" | Out-Null
```

Do **not** pre-create the `exports\...` leaf dirs — `export-web-scripts` requires a **non-existent** output directory and creates it.

Capture naming (fixed for this runbook):

| File | Content |
|---|---|
| `captures\01_targets.json` | `list-browser-targets` |
| `captures\02_packify_app_static.json` | Packify signed-in app page, script sources (baseline) |
| `captures\03_dyp_app_static.json` | DYP app page, script sources (baseline) |
| `captures\04_packify_photoshoot_live.json` | **T1** operator window |
| `captures\05_packify_mockup_live.json` | **T2** operator window |
| `captures\06_packify_deepagents_live.json` | **T3** operator window |
| `captures\07_dyp_mockup_live.json` | **T4** operator window |
| `captures\shot_*.json` / `shot_*.png` | screenshots + decoded PNGs |
| `exports\packify_app\`, `exports\dyp_app\` | `export-web-scripts` output dirs |
| `analysis\packify_app_analysis.json`, `analysis\dyp_app_analysis.json` | static JS application analysis |
| `notes\operator_log.md` | action timeline written during/after each window |

Static baselines (do these first; each ~1 min; both pages open in the dedicated Chrome):

```powershell
cmd /c 'rea inspect-web-page http://127.0.0.1:9222 <PACKIFY_TARGET_ID> --allowed-origins https://www.packify.ai --observation-ms 1500 --include-script-sources --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\02_packify_app_static.json"'

cmd /c 'rea inspect-web-page http://127.0.0.1:9222 <DYP_TARGET_ID> --allowed-origins https://dyp.ai --observation-ms 1500 --include-script-sources --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\03_dyp_app_static.json"'
```

Export + static analysis (repeat per site; destination must not exist):

```powershell
rea export-web-scripts "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\02_packify_app_static.json" "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\exports\packify_app" --json

cmd /c 'rea analyze-javascript-application "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\exports\packify_app\files" --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\analysis\packify_app_analysis.json"'
```

Bundle intelligence (routes/endpoints/fingerprints, optional but cheap):

```powershell
cmd /c 'rea analyze-web-bundle http://127.0.0.1:9222 <PACKIFY_TARGET_ID> --allowed-origins https://www.packify.ai --observation-ms 1500 --fetch-source-maps --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\packify_bundle.json"'
```

### 2.1 Shared live-window command (used by T1–T4)

One operator action script per window; 6 minutes per window; run as a **background** command (in the agent harness use `background=true`; standalone, use the Start-Job wrapper in §3.4) so the operator can act while REA observes:

```powershell
cmd /c 'rea inspect-web-page http://127.0.0.1:9222 <TARGET_ID> --allowed-origins <ORIGIN> --observation-ms 360000 --include-json-body-shapes --include-websocket-shapes --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\<NN>_<name>_live.json"'
```

- `<ORIGIN>` = `https://www.packify.ai` or `https://dyp.ai`.
- Do **not** add `--include-script-sources`, `--include-console-text`, `--include-accessibility-text`, `--include-storage-keys`, or `--include-storage-fingerprints` to live windows: larger payloads, and console text can carry secrets. JSON body shapes are value-free by design (property names + types only).
- What you get: per request — method, URL, status, MIME, initiator, redirects; and when selected, `body_shapes.request` / `body_shapes.response` as `{root_type, node_count, max_depth_observed, properties:[{path,types,observations}]}`. Cookies/auth headers are dropped, storage values redacted. **URL query strings are retained verbatim** (scrub before committing, §3.6). Only allowed-origin JSON media types get body shapes; multipart/binary bodies do not.
- WebSocket coverage starts at attach: frames/connections are only seen if they occur **during** the window. Operator reloads the page right after arming (see §3.3) so socket.io connect frames are captured.

---

### T1 — Packify photoshoot coordinates pipeline

**Goal:** capture a real request/response for `/api/photoshoot/*` and the exact shape of how `coordinates[]` is built, including the `extracted_coordinates` flow seen in the client bundle.

**Why:** the public API docs describe each coordinate object (`x, y, display_w/h, crop_x/y/w/h, rotation, source_w/h`); the web client arrangement (`extracted_coordinates`) is the missing piece for our scene compositor. Endpoint candidates from the previous bundle scan: `/api/photoshoot/background`, `/api/photoshoot/image/test`, `/api/photoshoot/template/list`, `/api/photoshoot/public/list`, `/api/photoshoot/landing/template/list`.

**Operator (on `https://www.packify.ai/photoshoot`, signed in):** pick scene/template → select one of the operator's own saved packaging designs (or upload the operator's own product image) → run one photoshoot generation. Wait for the result render.

**Command:**

```powershell
cmd /c 'rea inspect-web-page http://127.0.0.1:9222 <PACKIFY_TARGET_ID> --allowed-origins https://www.packify.ai --observation-ms 360000 --include-json-body-shapes --include-websocket-shapes --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\04_packify_photoshoot_live.json"'
```

**Success criteria:** ≥1 `POST` to a `/api/photoshoot/*` endpoint with a non-null `body_shapes.request` containing a `coordinates` array (capture the full property tree of one element) and/or `extracted_coordinates`; the matching response shape (job id / image URL field names); `GET /api/photoshoot/template/list` or `/public/list` params for template selection. Screenshot for visual proof:

```powershell
cmd /c 'rea capture-web-screenshot http://127.0.0.1:9222 <PACKIFY_TARGET_ID> --allowed-origins https://www.packify.ai --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\shot_t1_photoshoot.json"'
```

---

### T2 — Packify mockup/erase + composite text v2

**Goal:** request/response shapes for the editor's mockup compositing lane: `/api/mockup/erase`, `/api/mockup/result`, `/api/generate/composite/text/v2`, optionally `/api/generate/mockup/removebg`.

**Why:** these are the exact server contracts behind putting a design into/onto a product photo and overlaying text — the operations our mockup lane must mirror. Erase = mask-style removal/re-render; composite text v2 = text-in-scene rendering.

**Operator (design editor):** open one of the operator's designs → Mockup tab → (a) run **erase** on a mockup (if offered), then (b) run the **composite text** flow (add/adjust a text element over the product) → apply/generate → wait for the re-render.

**Command:**

```powershell
cmd /c 'rea inspect-web-page http://127.0.0.1:9222 <PACKIFY_TARGET_ID> --allowed-origins https://www.packify.ai --observation-ms 360000 --include-json-body-shapes --include-websocket-shapes --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\05_packify_mockup_live.json"'
```

**Success criteria:** `POST /api/mockup/erase` request shape (mask/region fields, image refs) + response shape; `POST /api/generate/composite/text/v2` request shape (text, font, position/box, source refs) + response (render refs); if erase is multipart, expect `body_shapes.request: null` — record that fact and move on (field reconstruction then comes from the exported bundle, already mined).

---

### T3 — Packify deep-agents layering (socket.io + layer artifacts)

**Goal:** the layered generation loop: `/api/deep-agents/run`, `/run/layer`, `/run/pause`, `/run/regenerate`, `/run/retry` request/response shapes, plus any socket.io frames during the window (join-room per generation; client events like `onContinueDeepAgentLayering`, `deepAgentPaidContinuation`, `deepAgentPreviewElementUuid` are visible in the bundle and should be confirmed against live traffic).

**Why:** the crow-jewel moat piece — layered, pausable, regeneratable generation with preview-cheap / full-expensive metering (5 cr preview vs ~100 cr full). We need event names and per-layer artifact payloads (`uuid`, layer type, preview/full flags) to build our own AutothinK variant.

**Operator (design-chat, ideally a fresh layered-dieline generation):** start a design generation that produces layers → when the layer list appears, **pause**, **regenerate one layer**, **retry** if offered, then **continue** to completion. Keep natural pauses of ~10–15 s between clicks so requests are separable in time.

**Command:**

```powershell
cmd /c 'rea inspect-web-page http://127.0.0.1:9222 <PACKIFY_TARGET_ID> --allowed-origins https://www.packify.ai --observation-ms 360000 --include-json-body-shapes --include-websocket-shapes --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\06_packify_deepagents_live.json"'
```

**Success criteria:** HTTP shapes for ≥3 of the five deep-agents endpoints (especially `/run` request and `/run/layer` progress payload); for sockets, `network.websocket_connections`/`websocket_frames` present with directions and byte lengths. **Known limit:** socket.io frames are engine.io-prefixed (`42["event",{...}]`) and not bare JSON, so REA may classify them as `text` rather than a JSON shape — frame inventory + timing correlation with the HTTP capture is the realistic outcome; record what is missing instead of forcing it.

---

### T4 — DYP mockup classification + text2img

**Goal:** request/response shapes for `/api/mockup/classification`, `/api/mockup/text2img`, plus the credit-flow bodies `/api/credits/use` and `/api/credits/balance` (the latter was already captured live once — good baseline to compare).

**Why:** DYP's prompt-assembly convention (`[CUSTOM PROMPT]/[SCENE]/[PRODUCT]` annotations) and its `text2img` fields (`{prompt, product_type_id, product_name, design_id, scene_id, aspect:"match_input_image", tool:"mockup generation"}`) explain their quality-per-credit; classification is the entry gate.

**Operator (on `https://dyp.ai/app/mockup/studio?designId=<operator's own design>`):** upload/select an image → let classification run → pick product type + scene (or custom prompt) → generate the mockup (costs a few credits on the operator's account — operator's call; the agent must not spend anything).

**Command:**

```powershell
cmd /c 'rea inspect-web-page http://127.0.0.1:9222 <DYP_TARGET_ID> --allowed-origins https://dyp.ai --observation-ms 360000 --include-json-body-shapes --include-websocket-shapes --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\07_dyp_mockup_live.json"'
```

**Success criteria:** `/api/mockup/text2img` request shape with the six known fields (confirm exact spelling) and its response shape; `/api/mockup/classification` response shape (label/type arrays — its request is an upload, likely multipart → request body shape may be absent by design); `/api/credits/use` body shape (`featureName`, `metadata`) and one `/api/credits/balance` response shape.

---

### 2.2 Post-window processing (after each live capture)

Summary one-liner (validated against the previous DYP live capture — prints requests, body shapes, WS counts):

```powershell
node -e "const fs=require('fs');const j=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));const n=j.normalized_result;const reqs=(n.network||{}).requests||[];console.log('requests',reqs.length,'ws_conns',((n.network||{}).websocket_connections||[]).length,'ws_frames',((n.network||{}).websocket_frames||[]).length);for(const r of reqs){console.log('['+r.status+'] '+r.method+' '+r.url);if(r.body_shapes){console.log('  REQ '+(r.body_shapes.request?JSON.stringify(r.body_shapes.request).slice(0,600):'-'));console.log('  RES '+(r.body_shapes.response?JSON.stringify(r.body_shapes.response).slice(0,900):'-'));}}" "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\04_packify_photoshoot_live.json"
```

If a capture is an error envelope (`{"error":...}`) or `requests=0`, treat it as a **failed window** — §4, no automatic retry (circuit breaker): persist, report, and only re-arm with the operator's explicit go-ahead.

Decode a screenshot artifact:

```powershell
node -e "const fs=require('fs');const j=JSON.parse(fs.readFileSync(process.argv[1],'utf8'));fs.writeFileSync(process.argv[2],Buffer.from(j.normalized_result.artifact.data_base64,'base64'))" "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\shot_t1_photoshoot.json" "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\shot_t1_photoshoot.png"
```

### 2.3 Optional fifth capture (no new cost): Packify `observe-web-session`

Navigation/lifecycle metadata only (no bodies) — useful to bracket the operator's clicks with timestamps. Replace `<NN>` with a free slot; can run before/after a main window:

```powershell
cmd /c 'rea observe-web-session http://127.0.0.1:9222 <PACKIFY_TARGET_ID> --allowed-origins https://www.packify.ai --observation-ms 60000 --json > "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\08_packify_nav_session.json"'
```

---

## 3. Operator-in-the-loop protocol

### 3.1 Division of labor

- **Operator:** launches Chrome (dedicated profile), signs in, opens pages, clicks every control, solves any CAPTCHA, decides whether to spend credits on their own account. Manages the shared clock and the page state.
- **Agent:** runs REA commands only; reads captures; never drives the page. REA has no navigation, input, evaluation, or form capability — that is the point. The agent must stop and ask the operator if anything requires credentials, a CAPTCHA, or a payment — it never does these itself.

### 3.2 Pre-flight checklist (agent, before any window)

1. Chrome is running with the dedicated profile; `http://127.0.0.1:9222/json/version` returns a browser string (§1.4).
2. `01_targets.json` is fresh; the target page is already open at the URL the window will observe (`https://www.packify.ai/photoshoot` etc.). Target IDs change after a Chrome restart.
3. Static baselines (§2.0) are done — they anchor field names if a live shape is ambiguous.
4. `notes\operator_log.md` is open; the operator writes local time + action per click.

### 3.3 Live-window discipline (the part that failed last time)

1. Agent announces the window target and the action script; asks the operator to stand by on the exact page.
2. Agent starts the background REA window; once the capture file is being written, agent signals **ARM**.
3. Operator **first reloads the page (F5)** — this registers the socket.io connection and any load-time API calls inside the window — then performs the action script at a deliberate pace, pausing 10–15 s between steps.
4. Operator signals **DONE**; agent waits for the window command to exit.
5. Agent runs the §2.2 summary, confirms `requests > 0` (and shapes where expected), and only then moves to the next target. A window with zero requests = failed window → §4.
6. Timing rule: capture timestamps are UTC (`capture_window.started_at` ends in `Z`); operator log is local. Correlate by order and relative offsets, or note the UTC offset up front.

### 3.4 Standalone-PowerShell background window (no agent harness)

```powershell
$targetId = "PASTE_TARGET_ID"
$cap = "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\04_packify_photoshoot_live.json"
$job = Start-Job -ScriptBlock { param($id) rea inspect-web-page http://127.0.0.1:9222 $id --allowed-origins https://www.packify.ai --observation-ms 360000 --include-json-body-shapes --include-websocket-shapes --json } -ArgumentList $targetId
# <operator performs the flow now>
Wait-Job $job | Out-Null
$out = (Receive-Job $job) -join "`n"
if ($out.StartsWith('{')) { [System.IO.File]::WriteAllText($cap, $out, (New-Object System.Text.UTF8Encoding($false))); "saved $cap" } else { "window FAILED - inspect:"; $out }
Remove-Job $job
```

### 3.5 What REA does and does not retain (rules the operator can rely on)

| Retained | Dropped / never requested |
|---|---|
| Methods, statuses, MIME, sizes, initiator stacks, complete URLs (query values! userinfo removed) | Cookies, `Authorization`/`Set-Cookie` headers; request/response header values generally |
| JSON body **shapes** — property names, typed paths, counts; **no values** | Body bytes/values; non-JSON (multipart, binary) bodies are not read |
| WebSocket direction, opcode, byte length; text frames as text or value-free JSON shape | Raw WebSocket payloads, binary frames, hashes, prefixes |
| Storage **keys**/fingerprints only if explicitly selected (we do not select them) | Storage values (always redacted) |
| DOM node names/types, not values; accessibility text only if selected (we do not) | Console object internals; console text only if selected (we do not) |

### 3.6 Post-run hygiene (before anything is committed)

1. Scrub query-string tokens from captures (signed CDN URLs are the real risk — REA keeps full query values):
   ```powershell
   Select-String -Path "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent\research\packify_quality_deep_dive_20261016\captures\*.json" -Pattern 'X-Amz-|Signature=|token=|api_key|apikey|access_token|Bearer ' -List
   ```
   If hits: hand-redact those URL values in the capture (replace with `<redacted>`), note it in the operator log.
2. Never commit `.env` values or keys; captures contain none, but the scrub above is mandatory for URLs.
3. Close the dedicated Chrome when the session is over (frees the port; the REA failure last time happened because this was done *mid*-investigation — do it last).
4. Write the final report to `reports\` per repo convention; keep derived artifacts internal (no republishing competitor docs text).

---

## 4. Troubleshooting

### 4.1 Failures seen in the previous run (verbatim shapes)

**A. `provider_unavailable / disconnected` — "lost its debugging connection" (observed: `packify_live3.json`, `dyp_live3.json`)**

```json
{"error":"Browser observation failed","code":"provider_unavailable","category":"unavailable",
 "message":"inspect_web_page lost its debugging connection. Verify that the target process is still running, refresh target discovery, and retry the observation.",
 "retryable":true,"details":{"operation":"inspect_web_page","reason":"disconnected"}}
```
Cause: the dedicated Chrome profile was closed after the investigation; the late windows tried to attach to a dead browser.
Mitigation: confirm `Invoke-RestMethod http://127.0.0.1:9222/json/version` immediately before arming; keep Chrome open for the whole session. If it was closed: relaunch (§1.2), re-run `list-browser-targets` (IDs change), restart the flow from §3.2. Per the repo's circuit-breaker rule: persist the failure envelope, **do not auto-retry**, report and get the operator's go-ahead.

**B. `provider_unavailable / endpoint_unreachable` — port doesn't answer**

```json
{"code":"provider_unavailable","details":{"operation":"list_browser_targets","reason":"endpoint_unreachable"}}
```
Causes/mitigations, in order:
1. Chrome not running / closed → launch it (§1.2).
2. Chrome **ignored** the debug flag because a Chrome instance already owned that `--user-data-dir` (only the first process opens the port) → find and stop only the REA-profile PIDs:
   ```powershell
   Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -like "*rea-packify-profile*" } | Select-Object ProcessId, CommandLine
   ```
   Then relaunch. (Do not kill the operator's other Chrome windows.)
3. Default-profile mistake: Chrome ≥136 ignores `--remote-debugging-port` without a custom `--user-data-dir` → always pass the dedicated profile path.
4. Wrong endpoint string: use `http://127.0.0.1:9222` exactly (`localhost` is invalid).

**C. Port occupied by something else → `invalid_endpoint_response`**

```powershell
Get-NetTCPConnection -LocalPort 9222 -State Listen | Select-Object OwningProcess
```
If the owner is not your Chrome, pick another port (e.g. 9223) for Chrome **and** for every REA command.

**D. Empty windows (`requests=0`) while the operator acted** — previous exact failure mode: actions ran outside the armed window (or before attach). Mitigation: §3.3 order (arm → operator reloads → acts → done); shorter, single-purpose windows; verify each window before moving on.

**E. `target_changed` / discarded capture** — the page navigated while REA finalized the capture. Mitigation: be on the final URL before the window ends; avoid full-page navigations in the last ~15 s.

### 4.2 Other conditions to expect

- `completeness.status: "policy_filtered"` + `attach_limited` are **normal**: REA only sees network events from the moment it attaches (`prior_activity_available` is always `false`); scripts parsed before attach are still listed.
- No body shape for a specific request despite `--include-json-body-shapes`: it was not JSON, or not on an allowed origin. Re-check the MIME/URL in the capture rather than re-running.
- Target list empty but Chrome is up: pass `--allowed-origins`; also note non-page targets are excluded by design.
- Huge capture on long windows: capture returns inline — keep windows ≤ 6–10 min and save with `cmd /c` redirection; if a web socket frame or body were to exceed 64 MiB per CDP message the operation fails with `payload_limit` (not realistic here).
- Cancelling a running window: Ctrl+C (foreground) or stop the background job; the partial result may be `cancelled` and no file is written — treat as a failed window, re-arm with operator approval.
- `rea doctor` exits `1` on this host even for healthy workflows (native engines missing) — not a blocker for browser/static JS work; scope checks with `rea doctor --client opencode --json` if registration questions arise.

---

## 5. When NOT to use REA (build from OSS instead)

Per the previous report's wheel classification, these are commodity and should **not** consume live REA windows (their interfaces are public/undifferentiated; verify with docs or small OSS spikes):

| Piece | Build/verify with | Why not REA |
|---|---|---|
| Background removal | `rembg` (U²-Net) local or BRIA RMBG API | Wheel; no proprietary mechanics |
| Upscale | SeedVR2 (already smoke-tested) / Real-ESRGAN | Wheel |
| Vectorize (raster→SVG) | `vtracer` | Wheel |
| Canvas editor (design/mockup) | fabric.js (matches DYP `canvas_data` model) or Konva | Wheel; our `northstar-os-ui/src/studio/engine` already covers more |
| PDF/ZIP export | client `pdf-lib`/`jspdf`+`jszip`; server `reportlab`+`svglib` | Wheel |
| Parametric dielines/labels (SVG math) | own generators (label types, FEFCO-style templates) | Math is commodity; their template *economy* is T1/T3-adjacent and already known |
| Billing rails | Stripe (Packify) / Polar (DYP) | Wheel; use our test-mode foundation when ready |
| Queue/async jobs | **existing** `foundation/jobs*` | We already have claim/lease/retry/DLQ — zero new tech |
| Auth, teams, i18n, analytics, S3 upload | standard OSS/SaaS | Wheel |
| Packify B2B public API | their public docs (`research/packify_dyp_re_20261016/packify_public_api_docs_extract.txt`) | Already extracted; live calls need a Business-plan `PackifyApiKey` we must not use |
| Pacdora 3D engine / `models/ctree` / materials | treat as external, out of scope | Commodity 3D/DOM rendering; not the quality moat |
| Payments, auth internals, credit meter internals of the competitors | never | Protected surfaces; no need |

The four things worth this runbook's live captures remain: **T1 photoshoot coordinates, T2 mockup/erase + composite text, T3 deep-agents layering, T4 DYP classification→text2img** — plus our own build of the four moat pieces (chat→layered generation, layered editable dielines, scene/product compositor, metered API+webhooks) per `reports/competitor_re_packify_dyp_20261016.md` §7.

---

## Appendix A — previous-session command patterns (proven, verbatim from the report)

```bash
# passive page capture + script sources
rea inspect-web-page http://127.0.0.1:9222 <TARGET_ID> --observation-ms 1500 --include-script-sources --json
# saved-capture → script export → static JS application analysis
rea export-web-scripts <capture.json> <outdir> --json
rea analyze-javascript-application <outdir>/files --json
# static bundle intelligence (routes, endpoint candidates, vendor fingerprints)
rea analyze-web-bundle http://127.0.0.1:9222 <TARGET_ID> --fetch-source-maps --json
# live passive observation of operator-driven actions (value-free shapes)
rea inspect-web-page http://127.0.0.1:9222 <TARGET_ID> --observation-ms 360000 --include-json-body-shapes --include-websocket-shapes --json
# UI evidence
rea capture-web-screenshot http://127.0.0.1:9222 <TARGET_ID> --json
```

Previous evidence to reuse (do not redo): `reports\competitor_re_packify_dyp_20261016.md`, `research\packify_dyp_re_20261016\` (docs extract, endpoint scans, `runtime_dyp_live_capture.json` — 8× `/api/credits/balance` with response shapes), raw working set `C:\Users\T2Hol\Desktop\packify-dyp-re\` (bundle analyses, exports, failure envelopes `packify_live3.json` / `dyp_live3.json`).

## Appendix B — session checklist (print this)

- [ ] Chrome up on dedicated profile; port answers; operator signed in.
- [ ] `01_targets.json` fresh; target IDs copied.
- [ ] Static baselines (`02`, `03`) + exports + JS analysis done.
- [ ] T1 window: arm → operator reloads → photoshoot flow → DONE → verify requests>0 + `coordinates` shape.
- [ ] T2 window: mockup erase + composite text → verify shapes.
- [ ] T3 window: layered generation with pause/regenerate/continue → verify deep-agents shapes (+WS inventory).
- [ ] T4 window: DYP classification → scene/product → generate → verify text2img/credits shapes.
- [ ] Screenshots decoded for each flow.
- [ ] Scrub query tokens; commit captures + report.
- [ ] Close dedicated Chrome **last**.
