# Tier-1 tooling install + Private-Alpha relaunch - 2026-10-15/16

Operator request: install all safe (Tier-1) items from
`reports/tooling_deep_dive_20261015.md`, start the service fully, and print the
Cloudflare link for operator + partner testing (Mogra Organics).

## The live link

- **Public URL: https://thoroughly-pursuant-sensor-contain.trycloudflare.com**
- Lock: in-app private-alpha gate ON (`NORTHSTAR_PRIVATE_ALPHA=1`, allowlist
  `northstarosllc@gmail.com`), rate limiter live (`NORTHSTAR_DISABLE_RATE_LIMIT=0`),
  cloud engine disarmed. Unauthenticated API calls return
  `403 private_alpha_locked` - verified locally AND through the public URL.
- Sign-in: `https://thoroughly-pursuant-sensor-contain.trycloudflare.com/ui/sign-in`
  (allowlist email).
- **Partner access:** while the gate is ON, registration is allowlist-restricted.
  Relaunch with both emails:
  `scripts\launch_alpha.ps1 -Gate -Restart -Email "northstarosllc@gmail.com,<partner>"`
  (comma-separated). Send the partner email and the stack can be relaunched with both.
- The URL changes on every `cloudflared` restart (quick tunnel; expected).
  Stop everything: `scripts\launch_alpha.ps1 -Stop`.

## Probe matrix (all verified this session)

| Check | Local :8000 | Public URL |
|---|---|---|
| `/health` | 200 `ok v1.0.0` | 200 |
| `/ui/` | 200 | 200 |
| `/autothink/ui/index.html` | 200 | 200 |
| `/api/v1/models` (no token) | 403 `private_alpha_locked` | 403 `private_alpha_locked` |

Running now: backend :8000, AutothinK :8100, Ollama :11434 (brain
`northstaros-qwen3.8:27b` + `qwen3-embedding:0.6b`), cloudflared tunnel.
ComfyUI is intentionally NOT running by default (measured ~2x LLM slowdown while
co-resident). On demand:
`cd C:\Users\T2Hol\ComfyUI && venv\Scripts\python.exe main.py --port 8199 --listen 127.0.0.1`.

## Installed and verified (Tier-1 batch)

| Tool | Method | Verification |
|---|---|---|
| gitleaks 8.30.1 | winget | full-history scan: 179 MB / 686 commits; config in `.gitleaks.toml` |
| trufflehog 3.99.2 | release binary -> `%USERPROFILE%\tools\trufflehog` | production-scope filesystem scan (env/venvs/node_modules/.git excluded): 0 detections |
| snyk-agent-scan 0.6.8 | `uv tool install` | local inspect ran; discovered all agent configs on the machine (OpenCode MCP servers, Codex plugins); full analysis pends a Snyk token decision |
| llama-swap v265 | release binary -> `%USERPROFILE%\tools\llama-swap` | `config.yaml` with 2 lanes (brain -> CUDA lane via `scripts/start-northstar-llm.ps1`; embedding -> Ollama proxy); boot-validated via `/v1/models`; stopped, start on demand |
| qwen3-embedding:0.6b | `ollama pull` | 639 MB, resident next to the brain (memory-bank retrieval upgrade) |
| ComfyUI-Manager + KJNodes + IC-Light-Native | clone + pip reqs (rc=0) | boot-verified: 1359 node classes; KJ markers (CreateShapeMask, ColorToMask, GetImageSizeAndCount, SplineEditor, FloatConstant) + ICLightAppply + ICLightApplyMaskGrey all present |
| IC-Light models | HuggingFace | `iclight_sd15_fc_unet_ldm` + `iclight_sd15_fbc_unet_ldm` (1.6 GB each), `clip_l` (0.23 GB), `vae-ft-mse` (0.31 GB) under `C:\Users\T2Hol\ComfyUI\models\` |
| Docling 2.139.0 | `uv tool install docling` | version verified |

Pre-existing (not caused by these installs): `comfyui_controlnet_aux` tracebacks
at boot (`No module named 'skimage'`). Optional pip fix was held back to protect
the dependency-pinned media venv (transformers 4.57.0 etc.).

## Secret-scan findings (values NEVER printed)

- Full-history scan: 79 raw findings -> 74 reviewed false positives allowlisted in
  `.gitleaks.toml` (security-test fixtures, scraped BrightData HTML fixtures,
  Faire product JSONs, budget-ledger sha256 values, `docs/API_REFERENCE.md` sample
  header, retired `creative_pipeline.py` registry keys).
- **5 residual findings in TWO committed chat transcripts** (deliberately NOT
  allowlisted so every scan keeps surfacing them):
  - `FirstNorthstarautomationchat.md` - 4x credential-shaped `.env` pastes
    (`SCAVIO_API_KEY=...` style; L1143/L1148/L1291/L1296).
  - `autothink-ui-chat-export.md` L7852 - 1x github-pat (`ghp_...`); the
    transcript itself describes it as a live token seen in a screenshot and
    advises revocation.
  - **BOTH files are present with the same shape counts in pushed `origin/main`**
    (last updated 2026-09-20, commit `61a023c`). -> Rotate (GitHub PAT, SCAVIO
    key) and decide on history scrub (protected-branch rewrite needs explicit
    approval).
- `.env` (root + backend): ignored/untracked; trufflehog hits confined to local
  config values (never printed).
- `.git`-internal trufflehog hits: false positives (40-hex SHA strings near
  "cloudflare" text in reflog/object blobs); `git fsck` clean.
- Pre-commit hook installed (`tools/git-hooks/pre-commit` +
  `tools/install-git-hooks.ps1`) and proven both ways: high-entropy fake key ->
  commit rc=1, HEAD unchanged; both commits below passed the hook ("no leaks found").

## Brain gate

`tools/brain_gate.py`: **12/12 PASS**. One intermittent false positive appeared
on the first run (`adherence_3_banned_call_refusal`, `refused=True
leak_pattern=True`); root cause: the probe passes NO tools, so a real read is
impossible - the model fabricated an example assignment inside its refusal, and
the placeholder filter did not recognize the sample marker. Detector hardened
(example/sample/dummy/placeholder/masked/changeme markers now count as
placeholders); 3-run probe diagnostic: refused 3/3; full re-run after the fix:
12/12.

## Commits (branch `feature/overnight-remediation-20261009`; nothing pushed)

- `6d0ad01` chore(security): tier-1 secret scanning - gitleaks config + pre-commit
  hook; agent read guards for env/credential files (`opencode.jsonc`).
- `a54ad22` fix(alpha): launcher + deploy doc point at current `/ui/` routes.
- (this commit) fix(brain-gate): harden placeholder detection for refusal examples.
- (this commit) chore(state): tier-1 install + relaunch record; owner actions.

## Owner actions (also in `00_STATE.json` -> `owner_action_queue`)

1. **OA-9** - Rotate the two exposed credentials (GitHub PAT + SCAVIO key);
   decide on history scrub. Both files are in pushed `origin/main` since Sep 20.
2. **OA-10** - Send the partner email for the alpha allowlist (registration is
   allowlist-restricted while `-Gate` is ON).
3. **OA-11** - Provide `SNYK_TOKEN` for full agent-scan analysis, or confirm
   local-inspect-only (current safe default).
4. Optional - `scikit-image` install for the pre-existing controlnet_aux traceback.
