# NorthstarOS Qwen 3.8 27B — single-survivor install (2026-10-13)

**Branch:** `feature/overnight-remediation-20261009` · **Mode:** operator-directed
full fleet replacement (ZERO legacy models → single survivor). All local; zero
paid/live/cloud calls; nothing pushed.

---

## 1. What was purged (zero legacy residue)

| Store | Models removed | How |
|---|---|---|
| Windows Ollama store (`%USERPROFILE%\.ollama`) | `northstar-qwen3:rev1`, `qwen3:14b`, `qwen3:4b`, `qwen2.5vl:7b` (~16.5 GB) | process stop → purge → store blobs/manifests emptied (0 files remaining) |
| Ubuntu WSL store (`/usr/share/ollama`, served on :11434 via wslrelay, engine 0.32.4) | `minicpm-v`, `qwen2.5vl:3b`, `moondream`, `qwen2.5-coder:14b`, `qwen3:14b` | `ollama rm` per tag → confirmed `ollama list` empty; store now 12 KB / 0 files |
| Docker / OpenHands (legacy AI agents) | 10 `oh-agent-server-*` containers + 4 images (`openhands:latest`, `openhands:1.8`, `agent-server:1.36.0`, `1.26.0`, ~15 GB) | `docker rm -v` + `docker rmi` (verified gone) |
| Docker build cache | 13.99 GB reclaimable | `docker builder prune -f` |
| Ollama update cache (`updates_v2` installer 1.4 GB) | removed | file delete |

**Not touched (out of scope / product infra / user data):** `northstar-*` staging
containers and images, `postgres*`, `lightpanda`, `binfmt`, `~/.openhands`
(75 MB chat DB — user data), `autothink/memory/session-history.json`,
historical docs/reports.

## 2. Disk outcome (target ≥40 GB free)

- Start: **3.1 GB free**. VHDX compaction (diskpart, engine stopped):
  `docker_data.vhdx` 37.46 → 22.35 GB; Ubuntu `ext4.vhdx` 33.28 → 6.50 GB
  (**42 GB reclaimed by compaction**).
- Peak free **53.54 GB**. After installing model + projector + two runtime
  copies of the GGUF, plus all cleanup: **33.55 GB free** at close. Target met.

## 3. Downloads — full SHA-256 verified

| File | Bytes | SHA-256 | Result |
|---|---|---|---|
| `Qwen3.8-27B-GSQ-RCO-IQ3_XXS-mtp.gguf` | 10,442,827,840 | `63f29a21…4093262` | **MATCH** |
| `mmproj-Qwen3.8-27B-BF16.gguf` | 931,146,528 | `13cb7beb…c0d3e16` | **MATCH** |

Path: `%USERPROFILE%\models\northstaros-qwen3.8\` (log with raw curl output:
`download.log` beside the files).

## 4. Model build

- `Modelfile.northstaros-qwen3.8` — `FROM` the local IQ3_XXS-MTP GGUF; params
  temp 0.35 / top_p 0.9 / min_p 0.05 / repeat_penalty 1.1 / **num_ctx 64576**
  (as specified; note: binary 64K is 65536 — flagging since the mandate wrote
  "64576 (64K context)") / num_predict 6000; rev1 capsule SYSTEM baked verbatim.
- `ollama create northstaros-qwen3.8:27b` → id `77879776424f`, 10 GB.
- **`ollama list` = exactly one model.** Serving: native Ollama 0.32.14 on
  `127.0.0.1:11434`, 100% GPU, context 64576, keep-alive forever.

## 5. Wiring (everything → `northstaros-qwen3.8:27b`)

Code: `autothink/backend/llm_adapter.py` (default + `AUTOTHINK_NUM_CTX`→64576),
`Northstar_backend/model_router.py` (T1/T2/T3), `listing_forge.py` ×4,
`social_pulse.py`, `shared/model-suite.json` (T1/T2/T3 + vision-local slots,
legacy alternates removed), `test_model_router.py` (contract updated deliberately).
UI: `Hub.jsx`, `Autothink.jsx`, `Ledger.jsx`, `src/components/Layout/Layout.html`.
Global: `C:\Users\T2Hol\.config\opencode\opencode.json` ollama-local map →
one model (backup: `opencode.json.bak.20261013`).
Docs: `LOCAL_RUNBOOK.md` (+ new "Local LLM lanes" section),
`PRIVATE_ALPHA_DEPLOY.md`, `PRODUCTION_BLUEPRINT.md` §17.3/§17.4, `00_STATE.json`
(engine/bench/history), `docker-compose.local.yml` (legacy `llama3.2:3b`
auto-pull removed — prevents a legacy model re-entering).

## 6. Verification gates

- `pytest test_model_router.py` → **22 passed**; autothink suite → **44 OK**;
  `npm run build` → **0 errors**.
- `tools/brain_gate.py` → **12/12 PASS** (8 golden + 4 adherence; both safety
  refusals clean, no secret-like pattern). Latencies 0.5–5.3 s warm.
  Raw per-probe lines are in the session log; tool committed for re-runs.
- Extra probes: 5-turn memory recall ✓ ("SKU T2-99, price 24.99" recalled);
  thinking mode ✓ (793-char internal reasoning, clean answer); math spot-checks
  margin `PASS 6.09` ✓ and unit economics `$30.01 / 100.07%` ✓ after
  re-phrasing (the first ambiguous phrasing produced wrong numbers — prompt
  sensitivity noted; the product's own margin logic runs in code, not in the
  model).

## 7. Performance (RTX 5080 Laptop 16 GB)

- **Ollama lane:** cold load of 10.4 GB ≈ 60 s; **warm generation 43.2 tok/s**.
- **llama.cpp lane** (`scripts/start-northstar-llm.ps1`, OpenAI-compatible on
  `127.0.0.1:8080`): **warm generation 39.7 tok/s, prompt 68 tok/s**, MTP
  speculative decoding bound (`--spec-type draft-mtp`) with **draft acceptance
  149/176 = 84.7%**. First request after load measured 2.8 tok/s — a
  cold-start artifact only (re-measured warm); recorded for honesty.
- **KV cache type:** `kvarn4` (from community guides) is NOT in the installed
  build's allowed set (`f32, f16, bf16, q8_0, q4_0, q4_1, iq4_nl, q5_0, q5_1`);
  the script uses `q8_0`.
- **Vision (llama.cpp + mmproj):** correctly identified the page and quoted the
  heading "Sign In" on both test screenshots (verified against the images
  directly); ~40 tok/s generation on vision prompts.

## 8. Known limits / open items

0. Startup entry added: `HKCU\...\Run\Ollama` → `ollama app.exe`, so the brain
   auto-starts at login (no startup entry existed before — post-reboot the
   local lane would otherwise have required a manual start).
1. **Ubuntu WSL `ollama` systemd unit is still enabled** (root-owned; needs
   your sudo, one command — WSL is currently shut down so :11434 is free):
   `wsl -d Ubuntu -e sudo systemctl disable --now ollama`
   Until then, that service re-grabs :11434 when Ubuntu next starts.
2. Ollama stored a pass-through `TEMPLATE {{ .Prompt }}` for this GGUF (its
   native Jinja template is Ollama-incompatible). Functionality verified by
   the gate + memory test; revisit if long-session quality drifts.
3. **Ollama-lane vision is not supported** (`ollama create` has no `--mmproj`);
   vision = the llama.cpp lane. The vision model-suite slots now point at the
   single local model; image calls on the Ollama lane will fail over to the
   configured cloud fallback.
4. Docker Desktop service was stopped for the vhdx compaction (auto-restarts on
   boot). OpenHands traces inside WSL Ubuntu (`~/.openhands`, `openhands`
   binaries, a shell-profile auto-launch TUI) were left in place — flagged, not
   removed (user data); say the word to remove.
5. No legacy model can re-enter through compose (auto-pull removed), but any
   `ollama pull` would obviously re-add one — the single-survivor policy is
   documented in `00_STATE.json` / `PRODUCTION_BLUEPRINT.md`.

## 9. Rollback

- Re-download both files (URLs + hashes in §3) and
  `ollama create northstaros-qwen3.8:27b -f Modelfile.northstaros-qwen3.8`.
- Config rollback: revert this commit; global opencode config backup at
  `C:\Users\T2Hol\.config\opencode\opencode.json.bak.20261013`.

## 10. Evidence

- `tools/brain_gate.py` (12/12), `download.log` (raw curl + hash lines),
  `ollama show` output, llama.cpp timing objects (draft_n/draft_n_accepted),
  screenshots referenced in §7, session shell transcripts.
