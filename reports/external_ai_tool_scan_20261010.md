# External AI Tool Scan — 9 Operator-Requested Sources + YouTube Clips Channel Assessment

- **Date:** 2026-10-10 (session 18:16)
- **Operator:** T2 Holdings (resolved profile: t2-holdings-tyrone-johnson)
- **Task:** Evaluate 9 operator-provided links (Notion summaries + GitHub repos), map findings to Northstar OS services, and assess the new requirement: an AI-driven YouTube clips channel.
- **Method:** Read-only web fetches of canonical repos/pages + targeted web searches. No paid/live calls, no credentials read/written, no scraping executed, no browser automation used. Notion pages are JS-rendered; 3 of 4 loaded via a readability proxy, 1 was thin → evaluated via its canonical repository. Star counts/license states as observed 2026-10-10.
- **No secrets:** this report contains no credential values; provider/key names only where useful.

---

## 0. TL;DR — verdict table

| # | Source | What it actually is | License | Cost | Runs on pilot (RTX 5080 L 16GB)? | Verdict |
|---|--------|---------------------|---------|------|----------------------------------|---------|
| 1 | **MoneyPrinterTurbo** | Topic→HD short-video generator (script→TTS→footage→subtitles→BGM→publish) | MIT | Free core; optional paid providers | Yes (GPU optional; 8GB+ rec.) | **ADOPT** — SocialPulse content engine |
| 2 | **AgentTube** (`darkzOGx/youtube-automation-agent`) | 7-agent 24/7 YouTube channel pipeline. **Not a clipper/downloader.** | MIT | Free w/ Gemini free tier | Yes (Node 18+) | **TRIAL** — channel engine + publishing/analytics layer |
| 3 | **LongCat-Video** | 13.6B open video model (T2V/I2V/continuation) + Avatar 1.5 talking-head | MIT | Self-host = heavy GPU; hosted APIs exist | No (24GB+ floor; 48–80GB realistic) | **WATCH / hosted-only** |
| 4 | **Cloudflare OS** | Cloudflare's internal AI workspace, open-sourced (agent chat + sandboxed "gadgets" + Gatekeepers security layer) | Apache-2.0 | Free self-host | Yes (wrangler, lightweight) | **STUDY → pilot candidate** (AutothinK reference) |
| 5 | **marketingskills** | ~50 marketing agent-skills (Agent Skills spec) | MIT | Free | Yes | **ADOPT** — quick win |
| 6 | **Lightpanda** | Zig headless browser for AI (CDP + BiDi; ~16x lighter, ~9x faster than Chromium) | AGPL-3.0 | Free | Yes | **WATCH** — needs policy review (Chrome Connect) first |
| 7 | **Scrapling** | Adaptive scraping framework + MCP server; self-healing selectors | BSD-3-Clause | Free | Yes | **ADOPT (parser/HTTP)**; policy-gate browser fetchers |
| 8 | **The Agency** (`msitarzewski/agency-agents`) | 232 specialist agent personas, 16+ divisions; installs into OpenCode, Claude Code, Cursor, etc. | MIT | Free | Yes | **ADOPT selectively** — prompt-agent roster |
| 9 | **VoxCPM (VoxCPM2)** | 2B tokenizer-free TTS: 30 languages, voice design + cloning, 48kHz | Apache-2.0 | Free self-host | Yes (2B; ~0.3 RTF on 4090; 16GB fine) | **ADOPT** — voiceover engine for video work |

---

## 1. MoneyPrinterTurbo — "The Free AI Short-Video Generator"

**Canonical repo:** github.com/harry0703/MoneyPrinterTurbo (129.5k★, MIT, Python 3.11+)

**What it does (verified):** Provide a topic/keyword → generates script (13+ LLM providers incl. OpenAI, Claude, Gemini, DeepSeek, Qwen, Kimi, Grok, MiniMax, Ollama), voiceover (Edge TTS free/no key; Azure, ElevenLabs, Chatterbox, Kokoro, Fish Audio, **ModelBest VoxCPM**, and more), footage (Pexels/Pixabay/Coverr free APIs; AI video via Seedance/MiniMax H3/OFox/WaveSpeed/MuAPI), subtitles (styleable), background music, and exports 9:16 (1080×1920), 16:9, 1:1. Can publish directly to TikTok/Instagram/YouTube Shorts.

**Interfaces:** WebUI (port 8501), REST API (port 8080, OpenAPI docs), CLI, Docker images (incl. GPU), Windows one-click package, Google Colab notebook, and a **built-in agent SKILL.md** (`docs/skill/SKILL.md`) so an AI agent can install and drive it end-to-end.

**System requirements:** GPU *not* required — minimum 4 cores / 4GB RAM; recommended 6–8 cores / 8GB RAM / 4GB+ VRAM; optimal 8GB+ VRAM. Pilot laptop is comfortably above optimal. Free path = Edge TTS + Pexels/Pixabay + free-tier LLM.

**Fit:** SocialPulse (post/video generation, brand-voice content), Word Coffee promo shorts, product-video assets for listings. Its agent SKILL.md makes it callable from our agent stack.

**Verdict: ADOPT.** Lowest-friction, highest-value video tool in the set; runs today, free.

---

## 2. AgentTube — "Free YouTube AI Agent Team Runs Your Channel 24/7"

**Canonical repo:** github.com/darkzOGx/youtube-automation-agent (4.2k★, MIT, Node 18+; v2.10.0 on master)

**What it does (verified):** A 7-agent pipeline that runs a channel end to end: Content Strategy (trends, calendar) → Script Writer → Thumbnail Designer (A/B variants) → SEO Optimizer → Production Management (TTS audio + images + video assembly with fallback chains) → Publishing & Scheduling (YouTube Data API v3, OAuth desktop client) → Analytics & Optimization (feeds insights back to strategy). Live dashboard at `:3456`, scriptable API (mutating endpoints require `x-api-key`), cron scheduler (06:00 generate, 15-min publish queue, 09:00 analytics, 22:00 optimize, Sunday strategy). Default upload privacy = **private**; approval-first workflow; capability check at startup shows which stages run for real vs fallback; simulated runs are never uploaded.

**Cost path:** one free Gemini key covers topic research, scripts, SEO, image generation, and narration. Optional paid: OpenAI/OpenRouter/Kimi/GLM, ElevenLabs, Replicate (Wan 2.7), or local Ollama.

**Important correction:** despite the "scrapper" impression, this is **not** a scraper or clipper. It does not download or clip other people's videos — it generates original videos. Its reusable value for a clips channel is the **publishing/scheduling, analytics feedback loop, and approval-gated workflow** (which we can reuse as the clip-publishing layer).

**Caveats:** one-time Google Cloud OAuth setup is the fiddliest part; YouTube Data API daily quotas; ToS compliance for automated uploads is on the operator; README header carries an unexplained blockchain-address-like string (treat as a community repo; pin versions before production use).

**Fit:** long-term original-content engine for the operator's channel; publishing layer for the clips pipeline.

**Verdict: TRIAL** (originals + publishing layer).

---

## 3. LongCat-Video (Meituan)

**Canonical repo:** github.com/meituan-longcat/longcat-video (9.1k★, MIT — code and weights)

**What it is (verified):** 13.6B foundational video-generation model, single architecture for Text-to-Video, Image-to-Video, and Video-Continuation; natively good at *long* videos (minutes, no color drift); 720p/30fps "within minutes" via coarse-to-fine + Block Sparse Attention; RLHF-tuned (GRPO). **LongCat-Video-Avatar 1.5** (May 2026) adds audio-driven talking-head video: Whisper-Large lip-sync, 8-step distilled inference, INT8 quantization option for reduced VRAM, single/multi-speaker audio.

**Hardware reality:** multi-GPU code paths (`torchrun` + flash-attn) provided; no vendor-stated VRAM minimum in README. Community reporting: 24GB+ recommended for full-res; 48–80GB (H100-class) for production-quality single-GPU runs; low-VRAM/quantized paths exist but degrade. **Not viable on the 16GB pilot laptop for production output.**

**Fit:** premium product/lifestyle video ads and talking-head content (e.g., AI presenter) — but only via rented cloud GPU or a hosted inference API (Replicate/fal-style). Do not plan local deployment on the pilot.

**Verdict: WATCH / hosted-only.** Revisit when a GPU box or meaningful video budget exists.

---

## 4. Cloudflare OS

**Canonical repo:** github.com/cloudflare/cloudflare-os (11.3k★, Apache-2.0)

**What it is (verified):** Cloudflare's internal AI-productivity environment, open-sourced so any company can make "Your Company OS". Three parts: (1) agent chat UI preloaded with company knowledge; (2) sandboxed app development — agents build "gadgets" (small personal apps) safely shareable; (3) **Gatekeepers** — a security framework of per-capability Workers that applies guardrails to agents and apps. Runs locally via `pnpm run-local` (wrangler/workerd), or deploys to a Cloudflare account via an online flow; data stored under `.wrangler` locally.

**Fit:** This is architecturally the closest public analog to **NorthStar AutothinK's "private agent workspace"** concept (chat + tools + files + guardrails). It's a study/pilot candidate for workspace UX and permissioned-capability patterns (their "Gatekeepers" ≈ our approval gates). It is Cloudflare-Workers-native; our stack is FastAPI + local-first — so treat it first as a **reference design**, then optionally a pilot on a CF account.

**Verdict: STUDY → pilot candidate.**

---

## 5. marketingskills (Corey Haines)

**Canonical repo:** github.com/coreyhaines31/marketingskills (54.1k★, MIT)

**What it is (verified):** ~50 production-grade agent skills ("when the user wants to…") following the Agent Skills spec (agentskills.io), installable into Claude Code, OpenAI Codex, Cursor, Windsurf, and **any agent that supports the spec**. Skill inventory includes: `cro`, `copywriting`, `copy-editing`, `seo-audit`, `ai-seo`, `programmatic-seo`, `schema`, `ads`, `ad-creative`, `analytics`, `attribution`, `ab-testing`, `social`, `video`, `image`, `emails`, `sms`, `cold-email`, `pricing`, `offers`, `launch`, `marketing-plan`, `marketing-loops`, `marketing-psychology`, `competitor-profiling`, `competitors`, `prospecting`, `content-strategy`, `customer-research`, `referrals`, `public-relations`, `sales-enablement`, `revops`, `popups`, `paywalls`, `onboarding`, `signup`, `churn-prevention`, `directory-submissions`, `co-marketing`, `community-marketing`, `events`, `free-tools`, `influencer-marketing`, `lead-magnets`, `site-architecture`, `marketing-ideas`, `marketing-council`, `aso`. Install: `npx skills add coreyhaines31/marketingskills` (or clone + copy to `.agents/skills/`).

**Fit:** SocialPulse (social/video/copy), ListingForge (copywriting, image, schema), AdPilot-adjacent (ads, analytics, attribution), general marketing ops for Word Coffee / T2 brands. Zero code — markdown skills; can be vendored selectively and brand-tuned.

**Verdict: ADOPT.** Fastest measurable win in the whole set. (Verify the correct install path for our OpenCode skill mechanism at install time.)

---

## 6. Lightpanda

**Canonical repo:** github.com/lightpanda-io/browser (36.2k★, **AGPL-3.0**)

**What it is (verified):** A headless browser built from scratch in Zig for AI/automation — not a Chromium fork. Benchmarks: peak memory 123MB vs 2GB (~16x), 5s vs 46s per 100 pages (~9x) on their crawl benchmark. Exposes a CDP (Chrome DevTools Protocol) server (`:9222`) and WebDriver BiDi; official Docker images; Puppeteer/Playwright clients connect via `browserWSEndpoint`. "PandaScript": deterministic, token-free JS scripts extracted from agent sessions for production replay.

**Caveats:** AGPL-3.0 (fine for internal use; distribution obligations if productized); verify JavaScript-heavy-site compatibility for target sites — its niche is fast, light automation, not full Chromium parity.

**Policy flag — important:** our operating constitution says **Chrome Connect is the controller for browser work; nothing may bypass it, and Playwright must not be driven directly.** Lightpanda is a second browser runtime; wiring it into agent flows would require an explicit operator policy decision (and any live-site use still respects site ToS + the hardcoded Amazon blocklist).

**Verdict: WATCH.** Strong future upside for controlled, high-volume scraping infrastructure — after a policy decision.

---

## 7. Scrapling — "The Adaptive Web Scraper"

**Canonical repo:** github.com/D4Vinci/Scrapling (86.7k★, BSD-3-Clause — most permissive in this set; Python 3.10+)

**What it is (verified):** Adaptive scraping framework: parser **self-heals selectors** after site redesigns (similarity-based element relocation). Three fetcher tiers: `Fetcher` (fast HTTP w/ TLS impersonation), `StealthyFetcher` (anti-bot evasion — its docs claim Cloudflare Turnstile bypass), `DynamicFetcher` (full Playwright/Chrome automation) + async variants. Scrapy-style spider API with pause/resume (`crawldir`), concurrency control, per-domain throttling, blocked-request detection, optional robots.txt compliance, JSON/JSONL export, CLI (`scrapling extract get <url> out.md`, `scrapling shell`), Docker image, and a **built-in MCP server** exposing `get/bulk_get/fetch/bulk_fetch/stealthy_fetch/bulk_stealthy_fetch/screenshot/session management` to agents (Claude Code, etc.), with an agent-skill too.

**Honest caveat (from its own docs):** the "1679x faster" number is one micro-benchmark (text extraction across 5,000 nested elements vs BS4+html5lib); real-world speed depends on site and fetcher. And: "use it on sites you're allowed to scrape."

**Policy flags:** the Stealthy/Dynamic tiers are browser automation outside Chrome Connect → same policy decision as Lightpanda. The parser + plain-HTTP tiers are tooling, not controllers, and can be adopted within allowed-source rules (site ToS, no Amazon, no bypassing logins/captchas). Amazon remains hard-blocked by constitution.

**Fit:** SourceScout/RivalWatch research on allowed sources (Costco/Bright Data flows, review sites, deal feeds), plus its MCP server as an agent tool for research tasks.

**Verdict: ADOPT (parser/HTTP tiers) after wiring decision on browser tiers.**

---

## 8. The Agency — "232 Free AI Specialist Agents"

**Canonical repo:** github.com/msitarzewski/agency-agents (158.8k★, MIT)

**What it is (verified):** 232 specialist agent *personas* — each with personality, workflow, and defined deliverables (not generic "act as…" prompts) — organized into divisions: engineering (35), specialized (48), marketing (32), game development (20+), GIS (13), sales (10), security (10), design (9), testing (8), paid media (7), project management (7), support (6), spatial computing (6), product (5), finance (5), academic (5); repo now also shows `research` and `strategy` folders (roster is growing beyond the advertised 16 divisions). Ships an interactive installer that detects and installs into 14 tools — **including OpenCode** (`cp integrations/opencode/agents/*.md ~/.config/opencode/agents/`) — plus Claude Code, Copilot, Cursor, Aider, Windsurf, Codex, Gemini CLI, Qwen, Kimi, OpenClaw, Antigravity, Osaurus, Hermes. Standalone desktop app exists.

**Fit:** an instant, free specialist-agent library to seed our agent roster workflows (esp. marketing/sales/product/engineering divisions for build tasks and brand ops) and to cross-check our own agent role design. Quality varies across 232; select ~10–20 relevant agents, not all.

**Verdict: ADOPT selectively.** Markdown-only; zero runtime cost.

---

## 9. VoxCPM (OpenBMB) — VoxCPM2

**Canonical repo:** github.com/OpenBMB/VoxCPM (38.5k★, Apache-2.0 — "free for commercial use")

**What it is (verified):** Tokenizer-free TTS via diffusion-autoregressive architecture. VoxCPM2: 2B params, MiniCPM-4 backbone, trained on 2M+ hours; **30 languages**; **Voice Design** (new voice from a text description — gender/age/tone/emotion/pace, no reference audio); **Controllable Cloning** (short reference clip + optional style steering); **Ultimate Cloning** (ref audio + transcript for full nuance fidelity); 48kHz studio output with built-in super-resolution; context-aware prosody; real-time streaming RTF ~0.3 on RTX 4090, ~0.13 via Nano-vLLM/vLLM-Omni with an OpenAI-compatible API server.

**Runs on pilot:** yes — 2B model is well within a 16GB RTX 5080 laptop.

**Fit:** voiceovers for MoneyPrinterTurbo (natively supported provider), the clips channel (commentary voice), Word Coffee brand voice, future AI presenter content. **Compliance note:** only clone voices we have rights/consent to use (record our own brand voice; never clone third parties without permission).

**Verdict: ADOPT.** Best-in-set value for audio; pairs directly with two other adopted tools.

---

## 10. YouTube clips channel — assessment of the operator's plan

### 10.1 What was asked
"AI clip live streams, or other YouTube videos, for viral clips; add enough to make it unique for monetization; that youtube scrapper (AgentTube) looks promising."

### 10.2 Corrections and hard truths (verified against YouTube policy docs, Oct 2026)

1. **AgentTube is not a clipper or scraper.** It generates original videos and handles publishing/analytics. For *clipping*, we need a different tool class (below). AgentTube remains valuable as the **publishing/scheduling/analytics layer** (approval-first, default-private, quota-aware, feedback loop).

2. **Clipping other people's videos for monetization is the single most policy-exposed model on YouTube.** Verified from YouTube's monetization policy pages:
   - The **reused content** policy is enforced **at channel level** — "if we cannot clearly tell that you made the content, monetization may be removed from your entire channel."
   - Explicitly **allowed** (quotes): "Reaction videos where you comment on the original video"; "Edited footage from other creators where you add a storyline and commentary"; "Using clips for a critical review"; "Replays… where you explain…". Explicitly **violating**: "Short videos you compiled from other social media websites"; "Content downloaded or copied from another online source without any substantive modifications"; "Clips of moments… edited together with little or no narrative."
   - **Minimal changes don't count.** Captions, speed, music, or light edits do not make reused content monetizable. Industry analysis (vidIQ/Rene Ritchie interview, Feb 2026) describes a "human-in-the-loop" bar: consistent editorial voice, original analysis, recognizable production style. AI must be a production assistant, not the "creator."
   - **"Repetitious content" was renamed "inauthentic content"** (2025) and enforcement waves have hit mass-produced/templated AI channels (major sweep reported Jan 2026). New-channel monetization thresholds are scheduled to rise (reported for Feb 2027) — building clean habits now matters.
   - **License ≠ monetizable.** Permission/licensing protects against copyright strikes, **not** against the reused-content policy (both bars must be cleared).
   - **Downloads:** YouTube ToS prohibit downloading videos except via official features. For *our own* content, YouTube Studio provides downloads; for third-party content, only CC-licensed, explicitly-permissioned, or licensed sources are legitimate inbound.
   - **AI disclosure:** required where synthetic/altered content could mislead.

3. **What "unique enough" actually requires** (the only versions that scale safely):
   - (A) **Own content first** — clip your own live streams/VODs into Shorts. Zero rights risk; purely a workflow/creative problem. **Recommended first build.**
   - (B) **CC BY licensed videos** — YouTube's license filter; reuse + adaptation incl. commercial allowed **with attribution**; embed in an original commentary/curation format with a rights log.
   - (C) **Written-permission creators** — clip programs (common in the streaming world).
   - (D) **Commentary/analysis over third-party clips** — must add genuine storyline/commentary; still channel-level risk; requires human review per clip. Do NOT build a pipeline that mass-reuploads raw edits of others' content — that is the exact pattern the policy names and enforces.

### 10.3 Recommended clips pipeline (own-content first, expandable to B/C later)

```
[Source: own VOD via YouTube Studio download (A) | CC BY w/ attribution (B) | permissioned (C)]
  → Whisper (faster-whisper, local) — word-level transcript
  → Highlight detection — LLM scoring over transcript windows (local qwen3:14b or free Gemini tier)
        + stream signals for VODs (chat replay heat, moments with spikes)
  → Clip cut + 9:16 reframe — ffmpeg + face/speaker tracking
  → Uniqueness layer (our differentiator) — commentary voiceover (VoxCPM),
        context intro cards, original analysis, consistent channel format
  → Compliance gates — source allowlist, per-clip rights checklist, attribution
        generator for CC, AI-disclosure flag, MANUAL REVIEW before publish
  → Publish — AgentTube publishing agent (YouTube Data API v3; approval-first; default private)
  → Analytics loop — AgentTube analytics agent → strategy/highlight tuning
```

### 10.4 Verified open-source clipper candidates (fetched 2026-10-10)

| Tool | License | Stars | Verified notes |
|------|---------|-------|----------------|
| **HotClip** (xixihhhh/hotclip) | AGPL-3.0 | 314 | Desktop app (Electron; Win/macOS/Linux), 100% local; long video **and livestream VOD** → 9:16; AI finds highlights *with reasons*; dynamic auto-captions; speaker diarization for multi-person; MCP server + Claude skill; no watermark/credits/uploads. CN-first docs, English README available. |
| **OpenShorts** (mutonby/openshorts) | MIT | 6.4k | Docker self-host (or cloud from ~$12/mo); AI moment detection, face tracking, subtitles + dubbing; MCP server + API; n8n examples; forked from Autocrop-vertical lineage. |
| AI-Youtube-Shorts-Generator (Anil-matcha) | n/v (search-reported) | n/v | LLM highlight detection + Whisper + auto vertical crop; not yet fetched/verified. |
| Others seen in search (unverified): clipmint, chopify, n8n-video-clipper, autoclipper, ViralMint | — | — | Candidate list for a trial bake-off only. |

**Recommendation:** trial **HotClip** (desktop, local, livestream-VOD-first, zero setup cost) and/or **OpenShorts** (Docker, MIT, agent/API-friendly) against one real VOD; pick one as the pipeline core.

### 10.5 Compliance gates to build into the pipeline (non-negotiable)
1. Source allowlist — default: own content only; CC/permission sources only after operator opt-in; no raw third-party reuploads, ever.
2. Per-clip rights checklist + attribution generator (CC) + AI-disclosure flag.
3. Human review before publish; default private → reviewed → public.
4. Consistent editorial voice/format — the channel must read as *yours* (this is what the policy actually measures).
5. Never bypass logins/captchas; respect API quotas; no Amazon-related scraping anywhere in this pipeline.

---

## 11. Cross-cutting notes

- **Chrome Connect policy:** Scrapling `StealthyFetcher`/`DynamicFetcher` and Lightpanda = browser automation outside the operator-owned controller. Adopting either into agent flows needs an explicit policy decision (and a logged change per the constitution). Parser/HTTP tiers and markdown-skill tools are unaffected.
- **Licenses:** AGPL-3.0 (Lightpanda, HotClip) — fine internally; obligations on distribution. BSD-3 (Scrapling), MIT (MoneyPrinterTurbo, AgentTube, marketingskills, The Agency, LongCat), Apache-2.0 (Cloudflare OS, VoxCPM).
- **GPU fit on pilot (RTX 5080 Laptop 16GB):** VoxCPM2 ✓ (~2B); MoneyPrinterTurbo ✓; AgentTube ✓ (CPU); clippers ✓ (Whisper small/medium + ffmpeg); LongCat ✗ (needs cloud/rented GPU).
- **Credential hygiene:** every adopted tool keeps its own keys in its own `.env`/config; the brain never reads/echoes values. Free tiers exist for every paid surface we'd need initially (Gemini, Pexels/Pixabay, Edge TTS).
- **Existing repo overlap check:** search of this repo for the nine tools/repos → **no matches** (nothing integrated yet; no conflicts).

## 12. Recommended next steps (prioritized)

1. **Install marketingskills + selected The Agency divisions** into the local OpenCode config (hours; free; immediate use in build/marketing tasks).
2. **Trial MoneyPrinterTurbo** on one real Word Coffee short (free path) → wire into SocialPulse as a content engine.
3. **Clips pilot:** one own-content VOD → 10 candidate clips → human review → 3 publishes (private-first). Choose clipper core: HotClip vs OpenShorts bake-off.
4. **VoxCPM local setup** for voiceovers (serves #2, #3, and brand voice).
5. **Scrapling parser/HTTP adoption** for allowed-source research; log the browser-tier policy question for operator decision.
6. **Cloudflare OS study note** for AutothinK workspace concepts (features: gadget builder, Gatekeepers).
7. **LongCat-Video:** keep on watch list; evaluate a hosted API only when a video campaign needs it.

## OPEN DECISIONS (operator input needed)

- **D1 — Clips source strategy:** (A) own streams only [recommended first], (B) own + CC-licensed + permissioned, (C) commentary-driven over third-party clips [highest risk], (D) mixed with gates.
- **D2 — Scraper policy:** approve/deny research use of Scrapling browser fetchers (and Lightpanda later); if approved, policy-file change requires explicit authorization in-task.
- **D3 — Clipper trial:** HotClip vs OpenShorts first.
- **D4 — Install agent/skill packs into OpenCode config now?** (marketingskills + Agency divisions)

## Evidence log
- Notion: YouTube-agent page ✓ (full), Scrapling page ✓, The Agency page ✓ (readability proxy), MoneyPrinterTurbo page ◐ (thin — JS-rendered; evaluated via canonical repo).
- GitHub fetched ✓: harry0703/MoneyPrinterTurbo (+README-en raw), darkzOGx/youtube-automation-agent, meituan-longcat/LongCat-Video (+raw README), cloudflare/cloudflare-os, coreyhaines31/marketingskills, lightpanda-io/browser, D4Vinci/Scrapling, msitarzewski/agency-agents, OpenBMB/VoxCPM, xixihhhh/hotclip, mutonby/openshorts.
- Searches ✓: Agency repo identity; LongCat VRAM reporting; OSS clipper landscape; YouTube reused-content/inauthentic-content policy (Google Help + vidIQ + air.io timeline).
- Repo overlap grep ✓: no existing references to any of the nine tools.
