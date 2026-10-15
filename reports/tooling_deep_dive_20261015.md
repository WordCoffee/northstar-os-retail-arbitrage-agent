# Tooling & agents deep dive for Northstar OS + AutothinK (2026-10-15)

Operator-directed research sweep before first real Mogra Organics work.
Priorities: **safety → speed → creative workflows**. Everything below is
open-source / self-hosted / free unless stated; Amazon stays file-only.

## Methodology & honest coverage

- **~40 targeted search clusters** run across 8 categories (agent security, MCP
  hardening, secrets, red-teaming, spend control, inference speed, ComfyUI
  ecosystem, product/UGC creative, audio/video, memory layers, OCR/docs,
  self-hosted ops, OpenCode ecosystem, YouTube roundups).
- **200+ distinct sources surfaced** (repos, docs, benchmarks, comparisons);
  key ~60 read in depth.
- **30+ video sources indexed** — titles/descriptions/chapters reviewed; none
  watched end-to-end (flagged honestly). See §7 for the 26-video index.
- **21 headline repos verified LIVE via GitHub API today** (stars / license /
  last-push date below are from that live check, not scraped summaries).

---

## 1. TIER 1 — Quick wins, install first

| # | Tool (verified) | License / activity | How it improves what we have |
|---|---|---|---|
| 1 | **gitleaks** + **trufflehog** secret scanning | MIT / active industry default | Repo-side safety: gitleaks as pre-commit hook (blocks a secret before it enters history) + trufflehog for periodic full-history sweep with live-credential verification. Directly protects the #1 risk class for a two-person business repo. |
| 2 | **snyk/agent-scan** ★3,139 · Apache-2.0 · pushed today | Security scanner for AI agents, **MCP servers and agent skills** — 15+ risk classes (tool poisoning, prompt injection in tool descriptions, toxic flows). | Our `opencode.jsonc` wires MCP servers (chromeconnect, context7) + skills. This scans exactly those surfaces and flags poisoned/over-scoped tools before they sit next to the master brain. |
| 3 | **llama-swap** ★5,964 · MIT · pushed today | One endpoint, on-demand hot model swapping with TTL auto-unload; wraps llama.cpp/Ollama/vLLM (even ComfyUI) behind a stable OpenAI-compatible URL. | Ends the manual unload dance between the 27B brain (70 tok/s CUDA lane), Ollama fallback and any future small model — one endpoint, auto load/unload, keeps the 16 GB card collision-free. |
| 4 | **qwen3-embedding:0.6b** (Ollama) 639 MB · Apache-2.0 | MTEB-multilingual 64.33 (best sub-1 GB), **32K context**. | Upgrades the Memory Bank / retrieval quality immediately — one `ollama pull`, tiny VRAM footprint, drop-in for semantic search over per-account knowledge (Mogra research, brand voice, product facts). |
| 5 | **ComfyUI-Manager** + **KJNodes** | Standard ecosystem layer (we have ZERO manager right now) | One-click install/update of every future node; KJNodes unlocks the standard advanced workflow primitives (masks, tiling, samplers) our Custom Nodes already assume. Removes the manual git-clone era. |
| 6 | **IC-Light** (relighting, via ComfyUI-IC-Light-Native ★645 or kijai port) | Apache-2.0 | The classic "boring product photo → studio-relit hero shot" model — exactly Mogra product photography: change background + relight while preserving the product. |
| 7 | **Docling** ★68,937 · MIT · pushed today (primary) + **MinerU** ★81,815 (hard-scan fallback) | Both actively maintained | Turn supplier PDFs, certificates, spec sheets, Amazon reports into structured markdown/JSON for the Memory Bank and product data. Docling = easy MIT default; MinerU = heavier OCR/VLM fallback for gnarly scans. (Dedicated OCR: PaddleOCR-VL-1.6 tops OmniDocBench v1.6 at 96.34%, Apache-2.0.) |

## 2. TIER 2 — High value, medium effort

| Tool (verified) | License | Improves |
|---|---|---|
| **OWASP Agent Memory Guard** ★187 · Apache-2.0 · pushed today | OWASP incubator | Runtime screening of Memory Bank **reads/writes**: prompt injection, memory poisoning, secret/PII leakage, protected-key tampering. Direct architectural fit — our Memory Bank is exactly the target surface. (Young project; benchmark numbers project-reported.) |
| **LiteLLM proxy** ★61,330 · core MIT · pushed today | Self-hosted AI gateway | One spend/rate/guardrail layer in front of the OpenRouter cloud lanes: virtual keys per workload, hard budget caps, TPM/RPM limits, guardrails. Complements (does not replace) the code-level live_gate — a second fence around paid calls. Note: budget enforcement requires its DB (fail-open without). |
| **microsandbox** ★8,697 · Apache-2.0 · pushed today | microVM-backed sandboxes (rootless, Windows) | Safe execution of any future agent-generated code/skills on this machine without handing them the real filesystem. |
| **PuLID / InstantID** (ComfyUI) | research/OSS, pipeline-dependent | Identity-consistent human shots for UGC — the same face across a Mogra content set. (PuLID for Flux pipelines; InstantID for SDXL. Verify against klein licensing before commercial output.) |
| **MMAudio** (ComfyUI-MMAudio ★580 · MIT) | MIT | Video→synchronized SFX/ambience — completes the Wan 2.2 clips (currently silent) and preps the LTX-2.3 audio era. |
| **LatentSync** ★6,141 · Apache-2.0 | Lip-sync (ByteDance); stable since 2025 | Talking-head UGC on existing footage; complements the LTX-2.3 native-audio plan. |
| **Blender MCP** (mcp-for-blender) ★30,951 · MIT · pushed Oct 6 | Agent-driven 3D | Natural-language product/box mockups + renders in Blender through our agent layer (needs Blender installed). Big lever for "product designing". |
| **PackCAD** (dieline→3D mockup converter, has an API) + **Pacdora** (known reference) | web tools, free tiers | Packaging design pipeline: dieline → foldable 3D mockup → render; PackCAD's API allows scripted mockup generation from the same dielines the printer gets. |
| **Postiz** ★37,237 · AGPL-3.0 · pushed today | Social scheduling w/ MCP + AI content | The "social media posts" lane: plan/schedule/publish 30+ channels with agent assistance; self-hosted, keeps posts/metrics on our infra. |
| **Langfuse** ★35,875 · core MIT · pushed today | LLM observability + evals | Trace AutothinK/brain calls (latency, cost, prompt versions), run eval sets — the missing feedback loop for "the best version" claim. Heavier ops (Clickhouse) — deploy only when needed. |
| **Open WebUI** ★155,818 (multi-user, RBAC, channels, Ollama-native) | AI interface | Optional second surface: a shared multi-user AI workspace for operator + partner (channels, notes, per-user perms) while AutothinK remains the product surface. LibreChat ★~22k is the multi-provider alternative. Decision: evaluate vs building partner access in-app. |
| **Excel MCP server** (haris-musa/excel-mcp-server, candidate — stats not API-verified) | OSS | Spreadsheet read/write via agent: the flat-file/change-file and ledger workflows are Excel/TSV-shaped. Worth a sandbox trial. |
| **dbhub** (bytebase) / SQLite MCP | OSS | Give agents safe, scoped query access to the SQLite app data instead of raw file access. |
| **Chatterbox** (Resemble AI, MIT, 350M) via TTS-Audio-Suite | MIT | Second narration/cloning voice (blind-test winner vs ElevenLabs in vendor study; [laugh]/[sigh] tags) alongside the installed Qwen3-TTS. Vendor-run benchmark — weight accordingly. |
| **agent skills packs**: awesome-agent-skills (1,000+ skills), awesome-opencode, superpowers methodology, stop-slop (de-slop docs), skill-health | OSS | Extends the OpenCode/agent layer itself: reusable skills/subagents (security analyst, researcher, reviewers) — an upgrade path for how AutothinK agents are configured. |

## 3. TIER 3 — Watch list / later

- **Graphiti/Zep** (★~30k, Apache-2.0 core) — temporal knowledge graph memory; heavier (graph DB). Revisit if memories need validity windows (audit trails).
- **Letta / Mem0** (★67k) — alternative memory architectures; our Memory Bank is custom-local; only if it outgrows us. (Benchmark scores are vendor-run and contradictory — trust only our own eval on our data.)
- **Penpot** ★61,130 · MPL-2.0 · pushed today — self-hosted Figma-alternative for brand/design collaboration with the partner; adds an app, adopt if design files outgrow the studio.
- **demucs** (MIT) — stem separation for audio cleanup.
- **GPTCache** ★8,212 MIT — semantic cache for repeated draft prompts (last push Sept 22; mature). Only if latency on recurring prompts becomes an issue.
- **Windmill** — code-first automation; n8n already in our compose; no switch needed now.

## 4. Explicit non-picks (and why)

- **vLLM** — no benefit single-user (benchmarks: parity at concurrency 1; wins only ≥16 parallel). Wrong tool for one laptop.
- **ik_llama.cpp** — mixed real-world results (documented Qwen-MoE regressions; gains are CPU/multi-GPU-specific). Our CUDA llama.cpp b11632 at 70 tok/s already beats the field for this box.
- **FLUX.2 dev / klein-9B weights** — non-commercial licenses (client work unsafe).
- **OmniVoice, Voxtral, F5-TTS commercial use** — CC-BY-NC / unclear terms; Qwen3-TTS + Chatterbox are the commercial-safe voices.
- **CogVideoX** — 2024 vintage, far behind Wan 2.2 / LTX.
- **Cloud dashboards** (ScanMCP, Canva, Figma cloud, RunComfy) — violate local-first posture.
- **OpenHands** — purged per operator mandate; only revisit on explicit request to rebuild a local agent runtime.

## 5. Integration map (where each lands)

- **Security layer**: gitleaks/trufflehog in git hooks + agent-scan in the pre-flight script + (later) Memory Guard around the Memory Bank + LiteLLM on the cloud lane.
- **Brain/agent layer**: llama-swap replaces manual lane juggling; embeddings upgrade retrieval; skills packs upgrade AutothinK/OpenCode behavior.
- **Creative layer**: Manager+KJNodes unlock the node ecosystem; IC-Light + PuLID + MMAudio + LatentSync + Blender-MCP + PackCAD cover product photos, UGC, SFX, lip-sync and packaging mockups; Postiz ships social.
- **Data layer**: Docling/MinerU/PaddleOCR-VL turn supplier docs into structured facts for the Memory Bank.

## 6. Suggested execution order (once the stack is reloaded)

1. Tier 1 batch: gitleaks+trufflehog, agent-scan, Ollama pull qwen3-embedding:0.6b, ComfyUI-Manager + KJNodes, llama-swap config.
2. Mogra creative pass: IC-Light workflow on a real Mogra product photo; Docling on a real supplier PDF; packaging mockup (PackCAD trial or Blender MCP).
3. Decide Open WebUI vs in-app partner access; evaluate Excel-MCP in sandbox; Memory Guard trial with a poisoned-memory red-team probe.

## 7. Video index (26 sources reviewed — titles/chapters, not full watches)

Local-AI tier list (Zen van Riel) · Local AI agents in 26 min (Tina Huang) · Best local agentic coding workflow (Web Dev Simplified) · Every AI model explained (Tina Huang) · Don't buy local AI hardware (Kai) · I'm obsessed with local AI (Greg Isenberg) · Ollama full course (freeCodeCamp) · Local AI full guide (Alex Finn) · Local AI explained (Tech With Tim) · Hermes Agent guide (Metics Media) · OpenClaw agent case study (freeCodeCamp) · KK's local LLM servers benchmark · llama-swap intro · vLLM vs llama.cpp scaling test · ComfyUI Manager must-have · IC-Light product relighting tutorial · Consistent characters in ComfyUI (2026) · Character sheets with FLUX · MMAudio video-to-audio (2 videos) · MinerU tutorial (Alex Hitt) · n8n vs Windmill (2026) (2 videos) · Best TTS models 2026 · Best open-source lip-sync comparison · Self-hosted AI tools home lab (Brandon Lee) · 10 best local coding models.

---
*Companion docs:* `docs/MEDIA_STACK_2026-10.md`, `reports/readiness_pre_mogra_20261015.md`,
`reports/local_llm_perf_optimization_20261014.md`.
