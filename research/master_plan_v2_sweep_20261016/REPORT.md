# Master Plan V2 — Tooling & Dependency Research Report

**Date:** 2026-10-16 · **Artifact folder:** `research/master_plan_v2_sweep_20261016/`
**Method:** 52 GitHub query families via the public search API (topic searches at 100/page) →
**1,904 repo records fetched · 1,797 unique repos surfaced · ≈248,361 overlapping match counts**.
Plus 8 HuggingFace dataset searches (`hf_datasets.json`). Licenses/activity are as reported by the
GitHub/HF APIs on 2026-10-16; anything reused must be license-verified against the repo itself first.
Raw data: `github_sweep.jsonl`, per-query tables: `sweep_summary.md`. (Unauthenticated sweep — a
deliberately deep-read pass on any finalist happens at adoption time.)

**Standing constraints applied to every verdict below** (from this repo's constitution):
local-first · no new paid services/accounts · Amazon stays *file-import-only* (no SP-API/Ads linkage) ·
live-gate for any outbound call · **Chrome Connect is the only browser controller** (Playwright is its
tool; no script drives Playwright directly) · protected-branch/деployment rules · credit-meter only.

---

## PHASE 1 — UNFINISHED GATES

### S2 · Tool registry + ComfyUI progress
| Candidate | License | Activity | Verdict |
|---|---|---|---|
| **Own bridge** (FastAPI ↔ ComfyUI `/ws`: `executing`, `progress`, `execution_success/error`) + keep existing 3 s `/history` polling as fallback | — | — | **USE** — already designed in the S2 spec; the code we need is a listener, not a framework |
| [itsKaynine/comfy-ui-client](https://github.com/itsKaynine/comfy-ui-client) (JS WS client) | MIT | 2024-03 | CONSIDER — reference only |
| [mehyaa/comfyui-api-client](https://github.com/mehyaa/comfyui-api-client) (batch CLI, WS progress) | MIT | 2026-09 | **PILOT** — closest reference for progress mapping |
| [lts8989/comfyui-go-sdk](https://github.com/lts8989/comfyui-go-sdk) | none stated | 2025-03 | REJECT (license) |
| [Comfy-Org/ComfyUI](https://github.com/Comfy-Org/ComfyUI) (already running, v0.4x) | GPL-3.0 (external process) | active | KEEP |
| Python WS client for the bridge: `websockets` / `websocket-client` | BSD-3 / Apache | mature | USE (one small dep) — or stdlib polling only if we defer WS |
| Structured-output guard for tool args (validate/repair LLM JSON): [ndcorder/outputguard](https://github.com/ndcorder/outputguard) | MIT | 2026-08 | **PILOT** — pattern for arg validation/1-shot repair in the tool loop |
| [Oct4Pie/toolbridge](https://github.com/Oct4Pie/toolbridge) (universal function calling, Ollama format) | MIT | 2025-12 | CONSIDER — reference for models without native tool calls |

### S3 · Voice PTT (+ live voice later)
| Candidate | License | Where | Verdict |
|---|---|---|---|
| **whisper.cpp** ([ggml-org/whisper.cpp](https://github.com/ggml-org/whisper.cpp)) | MIT | **binaries already installed** (`C:\Users\T2Hol\whisper-tools`) | **USE** — PTT = FastAPI subprocess, exactly the `voice-stdout.bat` invocation, Silero VAD |
| [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | pip | PILOT — fallback STT (CT2 ≥4.6.3, **float16 on Blackwell**, INT8 disabled for sm_120) |
| [hwdsl2/scribecrate](https://github.com/hwdsl2/scribecrate) + `-live` | NOASSERTION — verify | self-hosted server | PILOT — OpenAI-compatible ASR API shape to mirror for our endpoint |
| [alesaccoia/VoiceStreamAI](https://github.com/alesaccoia/VoiceStreamAI) | MIT | 961★ | **PILOT** — WebSocket near-realtime pattern for the live lane |
| [Dicklesworthstone/franken_whisper](https://github.com/Dicklesworthstone/franken_whisper) | NOASSERTION — verify | Rust | CONSIDER — backend-routing ideas |
| **Kokoro TTS**: [remsky/Kokoro-FastAPI](https://github.com/remsky/Kokoro-FastAPI) | Apache-2.0 | 5.5k★, active | **USE (server)** — OpenAI-compatible, GPU/CPU; sub-50 ms first-audio lane |
| [thewh1teagle/kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | MIT | active | PILOT — embedded fallback without a server |
| Qwen3-TTS 1.7B (already on disk, Apache-2.0) | Apache-2.0 | local | USE for quality voice (later, via `qwen-tts` pkg — not ComfyUI graphs) |
| [abus-aikorea/voice-pro](https://github.com/abus-aikorea/voice-pro) / GPT-SoVITS | GPL-3.0 / MIT | — | CONSIDER (cloning out of scope v1) |

### REA / Chrome Connect pass
| Candidate | License | Verdict |
|---|---|---|
| [ChromeDevTools/chrome-devtools-mcp](https://github.com/ChromeDevTools/chrome-devtools-mcp) | Apache-2.0 (official) | **CONSIDER — must be subordinated to Chrome Connect** (house rule: no direct Playwright/CDP driving) |
| [hangwin/mcp-chrome](https://github.com/hangwin/mcp-chrome) | MIT | CONSIDER — same subordination rule |
| [microsoft/playwright-mcp](https://github.com/microsoft/playwright-mcp) | Apache-2.0 | CONSIDER — same; useful only as *inside-Chrome-Connect* tooling |
| [D4Vinci/Scrapling](https://github.com/D4Vinci/Scrapling) / [browser-use](https://github.com/browser-use/browser-use) | BSD-3 / MIT | CONSIDER — scraping/agent patterns; ToS + Chrome Connect rules apply |
| Packify pass itself | — | unchanged: **bounded, operator-approved, `[PAUSE-AUTH]` gate** (see prior REA runbook) |

### Master Brain living-file + policy scheduler
| Need | Recommendation | Notes |
|---|---|---|
| Hot-reload directives/policy JSON | **Own code**: file-mtime check loop + `os.replace` atomic writes | sweep confirms no meaningful OSS niche here (query total=3); zero new deps |
| Scheduled jobs | **Existing `foundation/jobs*` + `croniter`** (already in requirements) | only add APScheduler (MIT) if a second process needs it |
| Optional watcher dep | `watchfiles` (MIT) / `watchdog` (Apache-2.0) — verify | PILOT only if mtime polling proves insufficient |

### AutothinK AT-0 / AT-1 (premium track)
| Candidate | License | Verdict |
|---|---|---|
| **DSpark** — [MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark](https://github.com/MiaAI-Lab/DeepSeek-v4-Flash-DSpark-2x-DGX-Spark), [ARahim3/mlx-dspark](https://github.com/ARahim3/mlx-dspark) | MIT | **CONSIDER — hardware mismatch flagged**: DSpark = DeepSeek speculative-decoding family (with z-lab DFlash). The surfaced recipes target **2× NVIDIA DGX Spark** (GB10, 128 GB unified) / Apple MLX — **not our 16 GB RTX 5080 laptop**. |
| [z-lab/dflash](https://github.com/z-lab/dflash) (block-diffusion flash spec-dec) | MIT | PILOT — most plausible local experiment later (llama.cpp/GGUF ecosystem) |
| [deepseek-ai/DeepSpec](https://github.com/deepseek-ai/DeepSpec) (train/eval spec-dec) | MIT | CONSIDER — research reference |
| [sgl-project/SpecForge](https://github.com/sgl-project/SpecForge) | MIT | CONSIDER — only if we ever serve via SGLang (we use Ollama) |
| `reasoning_effort=100` from the plan | — | **SPEC CORRECTION**: not an Ollama/OpenAI-compatible parameter. Map to Ollama `think` + `num_predict`/`num_ctx` budgets + model choice; per-request effort control = our own router tiers. |

---

## PHASE 2 — SEO & COMPETITIVE INTELLIGENCE

| Need | Candidates (license, activity) | Verdict / constraint |
|---|---|---|
| Search Console data | [joshcarty/google-searchconsole](https://github.com/joshcarty/google-searchconsole) (MIT, 2025-11); [Suganthan GSC MCP](https://github.com/Suganthan-Mohanadasan/Suganthans-GSC-MCP) (Apache-2.0, 2026-09); [fenjo26/OpenGSC](https://github.com/fenjo26/OpenGSC) (MIT, self-hosted dashboard, 2026-10); [irinabuht12-oss/google-ads-meta-ads-mcp](https://github.com/irinabuht12-oss/google-ads-meta-ads-mcp) (MIT, GA4+Ads+GSC) | **PILOT (live-gated)**. Constraint: GSC covers **owned websites** (not Amazon). Amazon rank/impressions stay **file-import** (SP/SQP → `ds_imports`). Any live pull = operator approval. |
| Rank/keyword tracking | [Ryze-AI-Adgent/open-seo-mcp-skills](https://github.com/Ryze-AI-Adgent/open-seo-mcp-skills) (MIT, 5.8k★); [IamRamgarhia/All-In-One-Free-SEO-Tool](https://github.com/IamRamgarhia/All-In-One-Free-SEO-Tool) (MIT); [tomaszboloz/SEOmi](https://github.com/tomaszboloz/SEOmi) (verify) | CONSIDER as references; our primary source = own imported search-term data + scoring |
| Vector store | [milvus](https://github.com/milvus-io/milvus) (Apache-2.0) · [qdrant](https://github.com/qdrant/qdrant) (Apache-2.0) · [meilisearch](https://github.com/meilisearch/meilisearch) (license shows NOASSERTION — verify) · SQLite **sqlite-vec** (staple, verify) · browser [vector-storage](https://github.com/nitaiaharoni1/vector-storage) (MIT) · [PgVector] (PostgreSQL license, staple) | **USE: sqlite-vec on the existing SQLite first; Qdrant (Apache) if scale demands. REJECT Pinecone (cloud/paid — conflicts local-first).** |
| KG / entity work | [zaydmulani09/mnemo](https://github.com/zaydmulani09/mnemo) (MIT, local-first KG memory — maps straight onto Memory Bank V2); [automataIA/graphrag-rs](https://github.com/automataIA/graphrag-rs) (MIT); [FareedKhan-dev/agentic-knowledge-graph](https://github.com/FareedKhan-dev/agentic-knowledge-graph) (metadata KG, zero LLM calls); [Hyper-Extract](https://github.com/yifanfeng97/Hyper-Extract) (NOASSERTION — verify); staples: Microsoft GraphRAG (MIT, verify), GLiNER (MIT, verify) | **PILOT**: mnemo patterns + own entity extraction (GLiNER/spaCy MIT) over `ds_listing_records`/`ds_search_terms` |
| Semantic drift / search term vectors | own: qwen3-embedding:0.6b (already installed) + sqlite-vec; drift = centroid distance over time windows | USE — no new services |
| Competitive visual panel | [Gingiris-competitor-analysis-tool](https://github.com/Gingiris-1031/Competitor-analysis-tool) (no license — patterns only); [bonus414/ai-competitor-toolkit](https://github.com/bonus414/ai-competitor-toolkit) (MIT; uses Playwright MCP — Chrome Connect rule applies); [rxpelle/kdp-scout](https://github.com/rxpelle/kdp-scout) (MIT, KDP only) | CONSIDER references; **build own panel** on existing ds_* data + sweep corpora |
| Automated variation planning | own generator + ds_variants/metrics; optional prompt-optimization pilot (see Phase 4) | USE own |

---

## PHASE 3 — CROSS-CHANNEL, LOCALIZATION, CREATIVE AUTOMATION

| Need | Candidates | Verdict |
|---|---|---|
| Cross-posting | [humanwhocodes/crosspost](https://github.com/humanwhocodes/crosspost) (Apache-2.0, JS, multi-network util); [cogsend/cogsend](https://github.com/cogsend/cogsend) (MIT, self-hosted, CF Workers); [ShadowSlayer03/Post4U](https://github.com/ShadowSlayer03/Post4U-Schedule-Social-Media-Posts) (MIT); [brightbeanxyz/brightbean-studio](https://github.com/brightbeanxyz/brightbean-studio) (AGPL-3.0 full app); [trypostit/trypost](https://github.com/trypostit/trypost) (AGPL); [postmill-ai/postmill-app](https://github.com/postmill-ai/postmill-app) (AGPL, 45+ channels, BYOK) | **PILOT: humanwhocodes/crosspost + cogsend patterns** for X/Bluesky/Mastodon tier. AGPL full platforms = CONSIDER only (internal use OK; license hygiene if ever distributed). Every platform API → live-gate + operator approval + ToS review. |
| Translation engine | [argosopentech/argos-translate](https://github.com/argosopentech/argos-translate) (MIT, offline py — bags-offline); [LibreTranslate](https://github.com/LibreTranslate/LibreTranslate) (AGPL, self-hosted service); [Helsinki-NLP/OPUS-CAT](https://github.com/Helsinki-NLP/OPUS-CAT) (MIT); [mololab/json-translator](https://github.com/mololab/json-translator) (MIT — LLM JSON translation w/ module structure; relevant to listing/backend-term JSON) | **USE: Argos (MIT) primary, LibreTranslate service as alternative.** Glossary enforcement = own term-map layer (+ LLM pass); NLLB weights (CC-BY-NC) flagged — avoid for product. |
| Infographics / text-overlay assets | [vercel/satori](https://github.com/vercel/satori) (MPL-2.0 per API — verify); [tengj/article-poster-generator](https://github.com/tengj/article-poster-generator) (MIT, 5 styles × 6 layouts); [dean9703111/ig-card-generator](https://github.com/dean9703111/ig-card-generator) (MIT, Markdown DSL → Puppeteer → PNG); [sharp-canvas-ts](https://github.com/agustinustheo/sharp-canvas-ts) (MIT); [MuseUI](https://github.com/Leochens/MuseUI) (MIT) | **USE (v1): Playwright HTML→PNG** (already installed) + our existing engine doc templates — zero new deps. PILOT satori+resvg server-side later if browser-less rendering is wanted. Keywords/text are authored as vector/text layers (existing text-safe doctrine). |
| Asset refresh cron | own scheduler + registry timestamps/flags (aging rule: last-updated + platform-spec freshness) | USE own |

---

## PHASE 4 — BRAND VOICE, EXPERIMENTS, VERIFICATION

| Need | Candidates | Verdict |
|---|---|---|
| Brand-voice consistency | own: embedding-centroid drift (qwen3-embedding, installed) + lexicon/typography rules + LLM judge with brand guide (existing brand-voice data contracts) | **USE own** — sweep shows no production-grade OSS drop-in |
| Datasets (voice) | HF [manifesta/brandvoice-marketing-briefs](https://huggingface.co/datasets/manifesta/brandvoice-marketing-briefs) (**CC0-1.0**, real marketing briefs — eval/training-safe); [thehonestape/brand-voice-spec](https://huggingface.co/datasets/thehonestape/brand-voice-spec) (**CC-BY-4.0**, DPO preference data); voiceforge brand-voice DPO/SFT sets | **USE (CC0/CC-BY)** for eval + style experiments; CC-BY-NC-SA ad sets flagged |
| Reference tools | [GH05TCREW/stylog](https://github.com/GH05TCREW/stylog) (MIT stylometry toolkit); [tjp2021/brand-voice](https://github.com/tjp2021/brand-voice) (MIT, audio→writing-voice profile) | PILOT reference |
| A/B engine + stats | [featbit](https://github.com/featbit/featbit) (MIT, self-host flags+experiments); [Flagsmith](https://github.com/Flagsmith/flagsmith) (BSD-3, self-host); [go-feature-flag](https://github.com/thomaspoignant/go-feature-flag) (MIT); [zalando/expan](https://github.com/zalando/expan) (MIT, RCT stats); [marshant](https://github.com/trunklabs/marshant) (MIT tiny); GrowthBook (MIT core — verify); `wasabi` **abandoned** | **USE: `expan` (+scipy/statsmodels) for significance; minimal experiment tables in our DB.** featbit/Flagsmith only if a real flag UI is wanted (2-user tool — likely unnecessary). |
| Master Brain feedback → prompts | [emirhan-gazi/kaizen](https://github.com/emirhan-gazi/kaizen) (MIT, DSPy+Ollama continuous prompt optimization); [DistylAI/prefpo](https://github.com/DistylAI/prefpo) (MIT, pairwise-judge optimization); [witt3rd/tinytextgrad](https://github.com/witt3rd/tinytextgrad) (MIT); [shirkattack/PromptCraft](https://github.com/shirkattack/PromptCraft) (MIT, local DSPy+Ollama) | **PILOT** — feed win/loss data from experiments into prompt-template revisions, tracked as Master Brain checkpoints |
| Full-suite verification | own (47 `verify-*.cjs` + pytest suites + smoke harnesses) | KEEP — no OSS substitution |
| Deployment | existing Caddy/Cloudflare pipeline + `launch-all.ps1`; protected-branch rule stands | **manual, operator-gated** — no automated deploy/push added |

---

## MCP SHORTLIST (the "mcp's" ask)

| MCP | License | Fit | Rule check |
|---|---|---|---|
| context7 (docs for agents) | MIT | already usable | OK |
| chrome-devtools-mcp / mcp-chrome / playwright-mcp | Apache/MIT/Apache | browser control | **must run under Chrome Connect, never beside it** |
| GSC MCP (Suganthan) | Apache-2.0 | owned-site SEO pulls | live-gate |
| local-stt-mcp / video-transcriber-mcp | MIT / Apache | local transcription | OK (local) |
| keepa_MCP | MIT (wraps **paid** Keepa) | Amazon price history | paid service — operator decision only |
| n8n (MCP server, fair-code NOASSERTION) | — | workflow automation | CONSIDER later; heavy; not local-first |
| TrendRadar (GPL-3.0) | — | trend monitoring | CONSIDER; GPL |

## DATASETS SHORTLIST

- **CC0/CC-BY (safe):** `manifesta/brandvoice-marketing-briefs`; `thehonestape/brand-voice-spec`.
- **Public domain:** USDA FoodData Central; Open Food Facts (ODbL) — nutrition/normalcy data.
- **Research-only (flag):** Amazon Reviews 2023 ([hyp1231/AmazonReviews2023](https://github.com/hyp1231/AmazonReviews2023), MIT scripts / UCSD research data); Amazon-Product-Search-Datasets (no license).
- **Non-commercial:** social-advertising sets (CC-BY-NC-SA) — eval only.
- **Not found:** packaging dielines (0 results) → the doypack generator stays **build-our-own** (as planned).

## RECONCILIATION FLAGS (plan-vs-architecture)

1. **Pinecone** → rejected (cloud/paid) · use sqlite-vec → Qdrant escalation path.
2. **"Search console APIs"** → live-gated, owned-sites only; Amazon stays file-import-first.
3. **DSpark / reasoning_effort=100** → DGX-Spark-class hardware + non-existent Ollama param; map to think budgets + optional DFlash pilot.
4. **Browser MCPs** → must be subordinated to Chrome Connect (AGENTS.md rule).
5. **AGPL components** (LibreTranslate, brightbean, trypost, postmill, TrendRadar) → fine for internal use; isolate/licence-review before any distribution.
6. **Automated deployment** → stays operator-gated; protected branches untouched.

## RECOMMENDED NEXT EXECUTION ORDER (unchanged gates)

1. **S2 now**: own ComfyUI `/ws` bridge (+ `websockets` dep) → SSE `tool-progress` → artifact cards; arg validation via outputguard-style guard.
2. **S3 now**: PTT via installed whisper.cpp + Kokoro-FastAPI (or kokoro-onnx) for speak-back.
3. **Living-file/scheduler**: own mtime+atomic-write layer on foundation jobs.
4. **AT-0/AT-1**: start spec; keep DSpark/DFlash as an optional local pilot (hardware notes above).
5. **Phase 2**: sqlite-vec + embedding drift first; GSC behind live-gate; panel on ds_* data.
6. **Phase 3**: Argos + own glossary layer; Playwright-based card renderer; crosspost util for X/Bluesky/Mastodon.
7. **Phase 4**: expan significance + in-DB experiment rows; DSPy/Ollama prompt-optimization pilot; keep the existing verification suite; manual deploys.
