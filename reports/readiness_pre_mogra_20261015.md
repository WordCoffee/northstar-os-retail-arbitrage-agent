# Pre-reboot readiness audit — Mogra Organics real-work go-live (2026-10-15)

**Scope:** full security sweep + operational verification before operator reboot
and first real work on Northstar OS for **Mogra Organics** (operator + business
partner, including product design). All checks below were executed, not assumed.

## VERDICT: 🟢 OPERATIONALLY READY — with a short action list (§5)

## 1. Security posture — all green

| Check | Result |
|---|---|
| Live-call gate (`live_gate.assert_live_posture`) | **PASS** — unbounded live mode refused; unarmed posture enforced |
| Rate limiter (`rate_limiter.assert_prod_posture`) | **PASS** |
| Auth JWT posture (`auth.assert_jwt_secret_posture`) | **PASS** |
| Amazon linkage gate (file-only architecture) | **PASS** — no SP-API/Ads/OAuth possible by design |
| Brain safety gate (`tools/brain_gate.py`, hardened) | **12/12 PASS** — both refusal probes clean (`.env`, credential audit-bait). See §4 incident. |
| `.env` hygiene | ignored by git ✓, not tracked ✓, no `.env` ever in history ✓ |
| Agent file permissions (`opencode.jsonc`) | deny-rules active for `.env`, keys, PEM, SSH, credentials files (read + edit) |
| Chrome Connect guardrails (Root B) | policy.js/lessons.js/config present; **61/61 guardrail tests PASS**; **fingerprint `75977709…` = operator baseline; `assertGuardrailsIntact: true`** |
| Ubuntu WSL ollama service | disabled + inactive (port 11434 owned solely by the Windows brain) |
| Git safety | **nothing pushed** (347 local commits on feature branch); no protected-branch ops |
| Docker | stopped by operator choice; no AI containers remain |

## 2. Operations — all green

| Check | Result |
|---|---|
| Backend stack | **UP** — `/health` ok (northstar-backend 1.0.0), 253 routes |
| Brain endpoint | `/api/v1/models` → local installed: **only** `northstaros-qwen3.8:27b` |
| Brain generation | quick-gen "READY" ✓ (author-verified rebuild intact, id `77879776424f`) |
| Ollama | 0.40.4 (auto-updated), single model, 9.7 GB store |
| UI | `/ui/` HTTP 200, sign-in at **`/ui/sign-in`** (root `/` → 307 redirect) |
| Design Studio backend | `/api/design-studio/projects|assets|jobs|search|migrate|rechecks|export-manifest` present |
| Media stack | all model files present (klein/SeedVR2/Wan2.2/umt5/VAEs/TTS); ComfyUI 90.9 GB intact |
| Clip pipeline (real test) | 16 s source → two 8 s clips (within 5–15 s spec) → clean concat, 16.02 s ✓ (ffmpeg 9.0.2) |
| Disk | **92.8 GB free** (parallel session freed ~19 GB orphans + staging; pagefile cap adds ~12 GB at reboot) |

## 3. Mogra Organics assets on disk

- Existing research baseline: `docs/mogra-organics-research-2026-10-02/`,
  `research/mogra_spice_scan_20261002/`.
- Product design lanes ready as verified tools: Z-Image Turbo / FLUX.2 klein
  (renders), Qwen-Image-Edit (labels/A+ text), SeedVR2 (finishing) — currently
  driven via `tools/comfy_smoke.py` graphs; in-app wiring (MEDIA_GEN_LIVE
  runner) is the next build step (see §5).

## 4. Incidents found & resolved in this audit (transparency)

1. **Banned-call probe false-positive**: the first gate run flagged
   `leak_pattern=True`. Investigated: the model produced a *textbook refusal*
   (declined, cited the hard-stop rule, rejected "it's fine" as authorization,
   offered only scrubbed presence/length checks). The flag was our probe's
   regex tripping on the model *describing* the variable name. Verified with
   3 more runs (0 real leaks), hardened `tools/brain_gate.py` with a
   placeholder-aware detector (now 12/12). **No real exposure occurred.**
2. **Parallel session (3c68cef)**: MTP tuned to **70.1 tok/s** (+68%) on a new
   llama.cpp CUDA build; during its disk cleanup a config blob was deleted →
   model rebuilt **bit-identically** via the documented Modelfile path and
   verified by load+generation. Power plan set High performance.
3. **Windows feature update staged** (`$WINDOWS.~BT` present) — the upcoming
   reboot will install it; see §5.

## 5. Action list (operator)

1. **Reboot** (your call on timing): applies the pagefile cap (4–24 GB →
   reclaims ~12 GB), completes the staged Windows feature update. After reboot,
   sanity: `ollama list` shows the one model; open `/ui/`.
2. **Partner account**: system is invite-based — create an invite at
   `/api/v1/invites` (admin) → partner signs up via `/ui/sign-in` →
   `/api/v1/invites/redeem`. Currently **1 user** exists; add the partner
   before shared work.
3. Optional: NVIDIA driver **617.42** (Oct 6) available — installer via
   NVIDIA App (left to you per the perf session).
4. Keep ComfyUI (media server) **off during LLM-heavy sessions** — measured
   ~2× LLM slowdown when co-resident (perf session finding).
5. After the 64 GB RAM upgrade: LTX-2.3 (audio+lip-sync UGC) becomes installable.

*Companion docs:* `docs/MEDIA_STACK_2026-10.md` ·
`reports/local_llm_perf_optimization_20261014.md` ·
`reports/media_stack_install_20261014.md` · `reports/operator_authorized_chromeconnect_policy_20261007.md`
