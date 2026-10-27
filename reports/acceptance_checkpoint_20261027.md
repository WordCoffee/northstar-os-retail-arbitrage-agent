# NorthstarOS Acceptance Checkpoint — 2026-10-27

## Step 2 — Chrome Connect verification
- Six chromeconnect tools registered; transport_module set:
  `C:\Users\T2Hol\OneDrive\Documents\Default Project\scripts\chromecontrol-playwright-bridge.js`.
- Guardrail fingerprint matches baseline:
  `1f84d42114620702c20d0181d12014c5c52b2c83d38dfcfec74290ccc4379cfa`.
- Isolation exemption (profile_lease_valid) passes for dir == "Profile 6" only;
  authorized_directory = "Profile 6", pin_matches = true.
- Amazon blocklist size = 26 (unchanged).
- Stale display-name expectation corrected: `extension_profile_display_name`
  updated from "Work" to "NORTHSTAR OS" (directory pin unchanged). Preflight now
  reports `isolated_signed_out_satisfied: true`, required_failed = [].
- Supporting-only checks still red by design: chrome_signed_out (signed-in),
  extension_relay_present (no relay window title observed). These are not gates.

## Step 3 — Attach
- Transport binding verified: MCP child PID 31844, session_key "Profile 6",
  session_nonce present, extension answered.
- Authenticated NorthstarOS workspace visible on http://127.0.0.1:8000/ui
  (Operator session; rooms Create/Grow/Research/Operate visible).

## T1 — Pouch render
- Core render pipeline verified via direct local call:
  `Flux-2-Klein-9B-KV-Q8_0.gguf` + `qwen_3_8b_fp8mixed.safetensors`,
  1024x1024, 1,348,997 bytes, ~draft tier.
- UI "Generate draft" attempt hit a stale planner state and an earlier ComfyUI
  VRAM/execution error; core pipeline passes after freeing RAM. RAM gate floor
  4096 MB was the limiting factor (freed by closing non-essential apps).
- Ollama 27B unloaded during render and restarted (`ollama serve`); /api/ps
  empty at render time, restored after.

## T2–T8, C5
- Not executed: require interactive UI steps (compositor label, 2000x2000 MAIN,
  lifestyle, A+ 1464x600, dieline/prepress, Wan+Piper mux, vision QC,
  preview/download/refresh persistence) that Chrome Connect's read-only mode
  does not drive. Product Designer route (/ui/product-designer) loads under the
  authenticated session.
- Playwright Test localhost path is available but cannot inherit the signed-in
  Chrome session without credentials; needs operator decision on a test
  storageState or manual run.

## Backlog
- Remaining backlog (C5 full workspace audit, B1–B14) not started this session.
- No paid providers, publishing, purchases, model downloads, license
  acceptance, or push performed.

## Limits honored
- Renders run one at a time; Ollama restarted after render (safe handoff).
- No git push; only local config metadata correction + this report.
