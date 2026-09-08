# NORTHSTAR OS — MASTER PLAN (Platform Brain)

> The complete breakdown of **Northstar OS** and **Northstar AutoThink**, every
> service/agent, capability, tech stack, operating constitution, and roadmap — as
> consolidated 2026-09-07 from the full corpus of T2 Holdings chat/markdown exports.
>
> **Credentials appear by name only. No API keys, tokens, passwords, or secret
> values are contained in this document.**

---

## 1. THE VISION

### 1.1 What Northstar OS is

Northstar OS is **not a single tool** — it is a **platform of specialized
AI-powered services** unified under one intelligent core — the **Master Brain**.

- **Publicly**, customers interact with branded, named **services** (not "agents").
- **Internally/backend**, every service is powered by a dedicated **Agent** — a
  specialized AI persona with its own model, rules, and scope of responsibility.
- This mirrors a real company: customers see product names and departments;
  internally each department has staff, procedures, and expertise.
- Northstar OS encodes T2 Holdings' accumulated e-commerce operating knowledge —
  built from real frustration with existing tools (Helium 10, Jungle Scout,
  Advigator) — into a system that thinks the way its founders think.

### 1.2 Business backing (real, not demo)

- **T2 Holdings LLC** — operating company behind the portfolio.
- Principals: **Tyrone Johnson & Tyler Edwards**, Texas (Grand Prairie).
- Business: **high-velocity Amazon FBA portfolio** — Kirkland Minoxidil arbitrage,
  **Word Coffee** (trademarked brand), and scalable additions, built on a
  **10-asset diversified strategy**.
- Objective: **compound capital via inventory reinvestment** while **protecting
  Amazon account health** and maintaining **wholesale/invoice legitimacy**.
- This repo (Northstar OS Retail Arbitrage Agent) is **operational tooling** whose
  outputs feed **real purchasing and real Amazon listings** — not a demo.

### 1.3 The two-tier product structure

| Tier | Offering | What it is |
|---|---|---|
| **Tier 1** | **NorthStar OS Services Suite** | Individually-branded purpose-built services, each backed by one dedicated agent. |
| **Tier 2** | **NorthStar AutoThink** (capital **A**uto, capital T**hink**, rest lowercase) | Premium "build-anything" layer — comparable to Perplexity Computer / Claude Code. Describe what you want; the Master Brain automates, builds, and delivers end-to-end, pulling whichever services/agents are needed. |

---

## 2. THE MASTER BRAIN (the orchestrator)

### 2.1 Role

At the center is **one orchestrating intelligence** — the Master Brain — styled as
a **"chief of staff"** over a fleet of specialized agents. It:

1. **Receives** every user request in plain language.
2. **Understands** intent and breaks it into sub-tasks (if multi-part).
3. **Delegates** each sub-task to the correct specialized agent/service.
4. **Coordinates** agents that must work together (e.g., Ads agent feeding winning
   keywords to the Listing agent).
5. **Validates** that every piece of a multi-part request was completed correctly
   before presenting the result.
6. **Learns continuously** from edits, corrections, and decisions — building a
   persistent model of how the user thinks (the "digital clone" principle).

### 2.2 TaskRouter (keyword → agent mapping)

| Keyword in task | Routed agent |
|---|---|
| ppc / ads | Amazon PPC Agent |
| listing / copy | Listings Agent |
| finance / tax | Financial Agent |
| code / build / debug | Software Agent |
| default (anything else) | General Intelligence Agent |

### 2.3 The learning function — "digital clone" principle

The single most important differentiator: the Master Brain is designed to become a
**working model of its owner's judgment**.

- Every edit, override, or correction is **captured as a signal**, not discarded.
- Over time, its decisions **converge toward what the user would have done**
  themselves.
- This earns trust in automation: the user is trusting a system that has watched
  them work, not a generic algorithm.
- Mechanism: the manager **logs its model choices in reports** so the architecture
  accumulates decision history ("Qwen 3 14B handled multi-step orchestration well,"
  "Qwen 2.5 Coder 14B handled the refactor") and routes better over time.

### 2.4 Operating constitution (the governance split)

- **Autonomous Zone** (no confirmation): build everything end-to-end — code, tests,
  UI, data pipelines, integrations, even the full code path of paid/live features;
  local git commits; updating `00_STATE.json`; offline diagnostics; dry-run/mock
  tests; placeholder-on-blocker protocol.
- **KEY DISTINCTION**: *coding* a live/paid feature is Autonomous. *Executing/
  triggering* it for real is Hard Stop.
- **Hard Stop Zone** (fresh, explicit, NAMED approval required every time — no
  standing/blanket/prior-session authorization overrides): any live outbound call
  to paid/rate-limited APIs; reading/printing/writing credential values; any git
  push/remote op; any Amazon listing/pricing/purchase action; any spend of real
  money or paid API credits; deleting protected files/fixtures; executing any
  batch file's "LIVE AUTHORIZED" step.
- **Circuit Breaker** (inside any approved live run): on ANY hard failure — stop
  immediately, persist what succeeded, record the failure in a scrubbed manifest,
  report. Never auto-retry; never silently skip past a failed item.
- **Reporting discipline**: quote literal spec before executing; report real test
  counts/output (never projected); commit after each meaningful unit of work; never
  mark a step complete without evidence; reconcile spec-vs-disk discrepancies
  explicitly.
- **Batch Blocker Collection Protocol (2B)**: don't stop mid-build for blockers —
  make clearly-labeled stubs, log blockers to a running list, keep building,
  surface as ONE batched report. Credential values are never requested/read/written.

---

## 3. THE AGENT ROSTER & MODEL STACK

### 3.1 Current model roster (3 specialized models)

| Model | Capability focus | Powers |
|---|---|---|
| Image model | Visual generation / image tasks | Listing media, A+, ads creative |
| Reasoning / math model | Math-heavy logic, geometry, structured reasoning, rule-based decisions (ACoS/bid logic, financial calcs) | Ads agent, financial/logic agents |
| Coding / dev model | Software development, automation building | Software agent, build tasks |

### 3.2 Local model architecture (pilot machine — Ollama + OpenCode)

| Brain | Model | Size | Role |
|---|---|---|---|
| Master Brain (manager/router) | `qwen3:14b` | ~9.3 GB | Multi-step reasoning/orchestration |
| Coding Brain | `qwen2.5-coder:14b` | ~9.0 GB | Code-first tasks |
| Helper Brain | 7–9B small model | fast | Trivial tasks |
| (disabled until 24–48 GB VRAM) | `qwen3:30b` (18 GB), Qwen 3.6-35B-A3B (35B) | — | Larger reasoning — blocked on 16 GB VRAM pilot |

- Pilot machine: Windows 11 (build 10.0.26100), **RTX 5080 Laptop 16 GB VRAM**,
  16 GB RAM, Ollama at `http://127.0.0.1:11434`.
- OpenCode provider: **ollama**, `@ai-sdk/openai-compatible`, baseURL
  `http://127.0.0.1:11434/v1`; default model `qwen3:14b`; context 16384 / output 4096.
- Operational learnings: WSL optional (native Windows works); 16K context safer
  than 64K on this laptop; `/no_think` fixes Qwen thinking-eating-tokens stall;
  use PowerShell here-strings (`@'...'@`) not `python -c` for multiline files.

### 3.3 Recommended model gaps to fill (prioritized)

| Missing capability | Why | Powers |
|---|---|---|
| Live web/research model | Competitor scraping, live trends, keyword discovery; much value depends on real-time market data | Listing, Retail Arbitrage |
| Copywriting/marketing brand-voice model | Distinct from coding/reasoning; writes in each brand's specific voice | Listing, Social Media |
| Data/spreadsheet parsing model | Lightweight parsing of large CSV/XLSX (search terms, placements, targeting) without burning the heavy reasoning model | Ads, Retail Arbitrage |
| Classification/embeddings model | Small, cheap tagging/deduping/routing inside the Master Brain for instant routing decisions | Master Brain routing layer |

---

## 4. NORTHSTAR OS SERVICES SUITE (Tier 1)

Public-facing service names are separate from internal agent names. Final naming
is the operators' call; proposed names below.

### 4.1 AdPilot — Amazon Ads Agent (internal: Ads Agent)

**What it does:** PPC bid optimization, ACoS management, keyword harvesting,
placement analysis, negative-keyword hygiene.

- **Keyword harvesting OS:**
  - Start with 1 Auto campaign (Bench Auto) → let Amazon find converting terms over
    14–30 days → pull Search Term Report → filter orders > 0 → promote.
  - Tier progression: **Auto (discovery) → Broad (exploration) → Phrase
    (validation) → Exact (scaling)**.
  - Negative-match losing keywords at each tier to prevent cross-tier cannibalization.
- **Four-tier campaign structure:**
  | Tier | Campaign | Purpose | Budget | Bid strategy |
  |---|---|---|---|---|
  | 1 | Bench Auto | Discovery | $10/day | Dynamic Bids — Down Only |
  | 2 | Scale Broad | Explore new terms | $15/day | Dynamic Bids — Down Only |
  | 3 | Almost Winners | Validate 1–14 sales | $25/day | Dynamic Bids — Down Only |
  | 4 | Winners Exact | Scale 15+ sales | $40/day | Dynamic Bids — Down Only |
- **AutoThink PPC bid-rule table (target ACoS 30%):**
  | ACoS band | Rule |
  |---|---|
  | >45% AND ≥10 clicks | −10 to −30% bid |
  | 30–45% | −5 to −10% bid |
  | 15–30% | +5 to +15% bid |
  | <15% | +15 to +30% bid |
  | ≥20 clicks, 0 orders | Pause / heavy decrease |
- **Keyword lifecycle & tiers:** keyword enters the **Bench** on first sale;
  core-winner exploit loop + explore-new loop (5–10 new keywords tested per run);
  movement flags `PROMOTED`/`DEMOTED`/`NO_CHANGE`; tiers Bench → **Almost Winners**
  → **Winners**; Winner = Orders ≥2 AND ACoS ≤ 30–35% AND active; Loser = ≥5 clicks
  or ~$5 spend with 0 sales → −15% bid; fast-track = ≥5 sales in 5–7 days → Almost
  Winner.
- **Fixed bid/flow guardrails (autonomous vs gated):**
  | Action | Autonomous | Needs approval |
  |---|---|---|
  | Decrease bid ≤ 20% | ✅ | |
  | Increase bid ≤ 10% | ✅ | |
  | Add negative keyword | ✅ | |
  | Promote keyword to higher tier | ✅ | |
  | Increase bid > 10% | | ✅ |
  | Increase daily budget | | ✅ |
  | Create new campaign | | ✅ |
  | Pause all campaigns | | ✅ |
- **Inputs/outputs:** Amazon Bulk Operations CSV in → n8n in Docker (port 5678) →
  Perplexity **Sonar** models (`sonar-reasoning`, `sonar-pro`, endpoint
  `https://api.perplexity.ai/chat/completions`, Bearer, env `PPLX_API_KEY`) → annotated
  CSV of keyword/bid decisions out.
- **Data layer (Supabase/Postgres):** `ad_search_term_reports`, `seller_daily_sales`,
  `harvest_queue`; 30-day discovery window for new search terms.

### 4.2 ListingForge — Listing Optimizer Agent (internal: Listings Agent)

**What it does:** title/bullet/description rewrites, A+ content copy & image
prompts, SEO, backend terms, compliance screening, Rufus readiness.

- **Backend file structure (backend/listing/, 9 files):** `types.ts`,
  `scoringEngine.ts`, `complianceGuardrails.ts`, `copyGenerator.ts`,
  `keywordBridge.ts`, `mediaPromptGenerator.ts`, `bulkUploadParser.ts`,
  `feedbackLoop.ts`, `example/exampleListingRun.ts`.
- **Scoring engine (weighted `scoreListing()`):** SEO 30% / Conversion 25% /
  Compliance 20% / Visual 10% / **Rufus 15%** — plus a dedicated
  `rufusReadinessScore`.
- **Compliance guardrails:** rule-based screen for medical claims, absolute
  superlatives ("best," "guaranteed"), review solicitation, trademark risk;
  severities **block** vs **warn**.
- **Bulk upload spec:** 200-char titles, 250-byte backend terms, duplicate
  SKU/term detection; camelCase internal, snake_case input accepted.
- **Media plan:** 7-slot image gallery, 4-scene video storyboard, 5-module A+
  plan; brand color hints (Word Coffee: charcoal/cream/clay; Mogra Organics:
  sage/ivory/green).
- **Placeholders by design (not built/mocked):** live Claude Sonnet copy calls,
  live image/video generation API, A/B test ingestion, multi-platform extension
  (Etsy/eBay/Shopify later).
- **Rufus readiness:** rewards question-starter phrases, attribute density
  (materials/counts/dimensions), FAQ module presence.
- **Live Word Coffee ASINs worked:** **B0F87RXTVC** (Affirmation Cards for Moms,
  53 cards — flagship), **B0F87JDPD4** (Affirmation Cards for Women, 53 daily —
  growth engine).
- **Rebuilt titles** (len ≤ 131 chars) and backend terms tuned by ROAS tiering
  (high-priority winners 8x+, e.g., "gift cards for women" 35.53x, "yoga gifts for
  women" 31.22x, "career woman gift" 16.51x; brand term "word coffee" 166–177x).
  Score movement: Moms 62.1 → 79.6, Women 64.8 → 80.1.
- **Brand tone (standing instruction):** **bold, clear, premium, emotionally
  honest, practical, non-cheesy** — overrides softer master-brain phrasing
  ("warm/empowering/faith-adjacent").
- **Key insight:** affirmation decks convert heavily via **occasion / niche-persona
  gifting angles** (career woman, chef, hosting) rather than generic category terms
  — position as a **niche gift**.

### 4.3 SourceScout — Retail Arbitrage Agent

**What it does:** product sourcing, margin calculation, sell-through velocity
analysis, Kirkland-to-Amazon arbitrage detection and scoring.

- **Sourcing screen / filters:** ≥5,000 est. monthly units (or consistent BSR);
  ≥20% net margin after fees; buy-box stability; replenishable clean invoice path;
  no gate/variation/return risk; prefer consumables/repeat-use; **BSR is a proxy,
  not proof**.
- **Target categories:** vitamins/supplements, trash bags, paper towels/tissue,
  olive oil, pantry/snacks, body wash. Excluded: topicals/creams/cosmetics/hair
  treatments, aerosols, dangerous goods, fragile glass; prefer <3 lb standard-size.
- **Profit formula (Master Profit Model):**
  ```
  Net Profit = Amazon Price
             − Costco Cost
             − Referral Fee (0.15 × Amazon price)
             − FBA Fee
             − (FBA Fee × 0.035 fuel/logistics surcharge)
             − Inbound Fee (assumption $0.35/unit)
             − Prep Cost
             − Return Reserve
  ROI = Net Profit / Costco Cost
  Risk-adjusted profit = Net Profit × Confidence Multiplier × Risk Multiplier
  ```
- **Buy thresholds:** net profit ≥ **$11**; ROI ≥ **30%**; confidence ≥ Medium;
  Cycle 1 = **50 units**; scale only if adjusted profit positive.
- **Risk model (100 points):** Compliance 30 / Margin compression 20 / Seller
  crowding 15 / Price volatility 15 / Packaging-damage 10 / Replenishment 10;
  0–24 Low, 25–49 Moderate, 50–74 Elevated, 75+ Reject.
- **Scaling model:** 50-unit Cycle 1; compounds Amazon post-fee payout + **$10,000
  infusion per cycle** (Cycles 1–4); target **$20,000 reserve extraction after
  Cycle 4**; Cycle 4 order budget projected **$83,932.64**; Cycle 5 $137,710.80
  (hypothetical capacity model).
- **Kirkland Minoxidil baselines:** newer/$42.00 model — cost $17.99, sell $42.00,
  payout $29.52/unit, net $11.53/unit, ROI ~63–65%; earlier model — sell $37.99,
  payout $25.51, net $7.52. **Never combine the two without an explicit statement.**
- **Pipeline (names only):** `BRIGHTDATA_API_KEY` + `BRIGHTDATA_DATASET_ID`
  (dataset `gd_lwdb4vjm1ehb499uxs`), `SEARCH_KEYWORDS=kirkland,kirkland signature`,
  `PAGES_TO_SEARCH=2`, match against `./data/costco-items.csv`, thresholds
  `MIN_PROFIT_MARGIN_PERCENT=25` (later 15), `MIN_ROI_PERCENT=30` (later 20),
  `MAX_SELLER_RANK=100000`, `TOP_DEALS_COUNT=20`; writes `data/scored/*.json`.
  Runner: `npm run pipeline` = `amazonSearch.js` → `normalizeLatestSnapshot.js` →
  `scoreLatestSnapshot.js`.
- **Cloudflare deploy:** `npm run deploy` = `npx wrangler pages deploy public
  --project-name northstar-arbitrage-dashboard`; KV namespace **DEALS_KV**; live
  URL worked end-to-end; `sync-kv.ps1` auto-pushes scoring output to KV.

### 4.4 SocialPulse — Social Media Agent

**What it does:** post generation, scheduling copy, brand-voice content across
channels (Facebook/Meta, TikTok, Instagram; creator/affiliate outreach).

- Loads each brand's **voice module** (see Word Coffee §6 in the user-profile doc:
  "Grab Word Coffee, not a cup," "Fuel Your Focus," "Coffee for the Soul," etc.).
- Handles ad creative prompts, captions, hashtag sets, video scripts, photo
  prompts, creator outreach scripts, TOS-compliant review-request emails.
- External-traffic strategy: Facebook/Instagram ads to drive **external traffic to
  Amazon listings** (with **Amazon Attribution** tags — `maas=` — for rank boost);
  only run when Amazon PPC is stable (ACoS < 30% consistently); blended ACoS < 40%
  threshold; external traffic typically converts 2–4%.

### 4.5 Recommended additional services (class-leading suite gaps)

Natural extensions of data T2 already collects — for the roadmap/pricing page so
the platform reads as a full suite from day one:

| New service | Public name | What it solves |
|---|---|---|
| Competitor Intelligence Tracking | **RivalWatch** | Tracks competitor pricing, BSR shifts, listing changes, review velocity; feeds alerts + data to ListingForge/AdPilot |
| Inventory & Restock Forecasting | **StockSense** | Predicts stockout risk; recommends reorder timing/quantity by velocity — prevents stockouts and overstock cash-tie-up |
| Review & Reputation Monitoring | **VoiceGuard** | Monitors reviews/ratings; flags defect/shipping-damage patterns before account-health problems |
| Financial/Profitability Dashboard | **MarginView** | True per-SKU profitability after ad spend, FBA fees, COGS |
| Cross-Brand Portfolio Dashboard | **PortfolioPulse** | Bird's-eye view across Word Coffee, Mobile/Mogra Organics, Neck Nirvana — investor-grade portfolio view |
| Launch Playbook Automation | **LaunchPath** | Templates the proven new-product-launch sequence (seasonal pre-loading, negative targeting, campaign structure) for every new ASIN |

---

## 5. NORTHSTAR AUTOTHINK (Tier 2 — premium)

### 5.1 What it is

- **NorthStar AutoThink** (capital **A**, capital **T**) — the premium,
  "build-anything" layer. Comparable to **Perplexity Computer** or **Claude Code**
  ("Perplexity AI's computer," Claude's "Code Work"): you tell it what you want in
  plain language and it **automates, builds, and delivers** end-to-end, pulling
  whichever agents/services are needed.
- Powered by the **same Master Brain** that learns the user's judgment over time —
  which is what makes it trustworthy enough to run autonomously rather than just
  answer questions.
- Built by e-commerce operators out of the needs they felt using existing services.

### 5.2 Reference framing (vs Perplexity Computer / Claude Code)

| Tool | What it is |
|---|---|
| Perplexity Computer | Web-grounded research agent |
| Claude Code (and OpenCode) | Code/agent harness |
| **NorthStar AutoThink / Northstar OS** | **Private agent workspace** — chat, tools, files, prompts, workflows — hosting a **Helium-10/Advigator-style FBA intelligence + harvesting engine** as the moat |

Mental model:
1. **Open WebUI / Ollama** = private operator console
2. **n8n** = automation nervous system
3. **Supabase** = memory & reporting layer
4. **Custom PPC/harvesting modules = the actual business moat**

"Offline" = **private/self-hosted first** (data under own control), not necessarily
air-gapped.

### 5.3 Implementation status (v2.0.0)

- **Northstar OS v2.0.0** — FastAPI web app on **port 8000**, dark Perplexity-style
  UI (`#0a0a0f`), subtitle "T2 Holdings — Local AI Command Center."
- **Files:** `config/settings.json`; `core/llm_adapter.py` (**UnifiedLLMAdapter**
  routing local Ollama or cloud `gpt-4o` via `OPENAI_API_KEY`, fallback strings
  `[LOCAL FALLBACK]`/`[OPENAI FALLBACK]`); `core/router.py` (**TaskRouter**);
  `server/app.py` (FastAPI); `server/static/index.html`; `requirements.txt`
  (fastapi, uvicorn, pydantic, requests); `launch.bat`.

### 5.4 Recommended stack, costs, timelines

| Layer | Purpose | Best fit |
|---|---|---|
| Private agent workspace | "Offline Perplexity Computer" | Open WebUI + Ollama |
| Workflow orchestration | Automations, report parsing, harvest jobs, triggers, scheduling | **n8n self-hosted (Docker)** |
| Data warehouse / backend | Search terms, keyword tiers, harvest queue, sales history | **Supabase/Postgres** |
| Amazon FBA engine | Harvesting, bidding, reporting, movement flags | **Custom logic (the moat)** |

- **Build order:** (1) local/private agent workspace first (Docker → n8n → Open
  WebUI w/ Ollama), (2) then the Helium-10-style core (CSV ingestion → search-term
  harvesting → Bench/Almost Winners/Winners logic → bulk-sheet output + exec
  summaries).
- **Costs (real figures from conversation):** build v1 ~$2.5k–$12k (internal
  framing $5k–$10k); production-grade $15k–$50k+; run cost $40–$300/mo at small
  scale (bare-bones internal $40–$80/mo; active/multi-brand $100–$300/mo);
  Supabase Pro ~$25/mo; self-hosted n8n $5–10/mo (n8n Cloud ~$24/mo);
  `costco_detail`/`costco_search` = 1 request each (OpenWebNinja search free
  tier 100 req/mo); Costco item-detail pulls run through Bright Data Web
  Unlocker (free tier 5,000 credits/mo shared pool, 1 credit/request, hard stop
  at 0) with Firecrawl as the free-tier fallback (1,000 pages/mo recurring, no
  card, 2 concurrent). Unwrangle was REMOVED 2026-09 — no free tier, paid
  starts $99/mo (its old "5,000 free credits/mo" claim is stale). Perplexity Pro
  $5/mo API credit reportedly **discontinued Feb 2026 — do not rely on it**.
- **Timelines:** prototype 1–2 weeks; real v1 MVP 4–8 weeks; deployment-ready
  8–12 weeks; subscription-ready 3–6 months. Blunt estimate for THIS project:
  30–45 days internal v1 without $100, 21–35 days with $100 wisely spent (~25–35%
  faster).
- **Product strategy:** one codebase / multiple deployments; Docker-first;
  env-var config; migrations-based DB changes; separate UI/workflow/DB/business
  logic layers. **Local = the first deployment environment, not "the product on
  your PC."** Phase 1 local internal tool → Phase 2 hosted subscription → Phase 3
  premium self-hosted/private deployment for serious brands/agencies. Rule: "if a
  feature only works because it is tied to my personal machine, it is not part of
  the real product."

### 5.5 Hosting / access architecture

- **Cloudflare Tunnel** (works behind NAT, no public IP) for **MFA-protected
  remote/shared access** with per-partner workspaces + audit trails.
- **GitHub private source control + self-hosted runners**; keep models and
  business data local.

---

## 6. EXAMPLE DELEGATION FLOW (master brain in action)

> User request: *"Get my Word Coffee affirmation card listing ready for the holiday
> season — optimize the ads and refresh the listing."*

1. Master Brain receives the request; identifies two domains: **Ads + Listing**.
2. Delegates to **AdPilot**: pull current search-term performance, identify
   seasonal winner keywords, adjust bids, flag negative-keyword gaps (e.g.,
   "free," "printable").
3. Delegates to **ListingForge**: once AdPilot returns top-performing seasonal
   keywords, rewrite bullets and generate holiday A+ content image prompts.
4. **Validates**: both outputs complete, keyword-aligned, internally consistent
   (ListingForge didn't use a keyword AdPilot flagged as a Loser).
5. **Assembles** the final package — updated bid sheet + updated listing copy +
   image prompts — and delivers for review.
6. Whatever the user edits becomes a **learning signal** stored against the user's
   profile for next time.

---

## 7. DATA & LEARNING ARCHITECTURE

```
                    ┌─────────────────────────────┐
                    │        MASTER BRAIN          │
                    │  (Router + Validator +       │
                    │   User Judgment Model)       │
                    └───────────────┬─────────────┘
                                    │
    ┌───────────┬───────────┬───────┴────┬───────────┬────────────┬─────────┐
    ▼           ▼           ▼            ▼           ▼            ▼         ▼
 AdPilot   ListingForge  SourceScout  SocialPulse  RivalWatch  StockSense  ...
    │           │           │            │           │            │         │
    └───────────┴───────────┴────────────┴───────────┴────────────┴─────────┘
                                    │
                          ┌─────────▼──────────┐
                          │  Proprietary local   │
                          │  Database (owned,     │
                          │  self-hosted)         │
                          └──────────────────────┘
```

- Every agent reads/writes **one shared, owned database** — insights cumulative
  across services, while each agent's reasoning/brain stays isolated (avoid
  "watering down" specialized logic).
- **User-profiling intent:** per-partner workspaces + audit trails retain per-user
  context and behavior so the manager routes and personalizes — while keeping
  domain knowledge **isolated per agent**.

---

## 8. IMPLEMENTED OPERATIONAL TOOLING (this repo)

The repo already contains real, tested tooling that the agents rely on:

- **Fee calculator** (`Northstar_backend/fee_calculator.py` + standalone HTML) —
  honest by construction: money rounded to 2 decimals; missing values stay `None`;
  storage fee default 0; fulfillment fees approximate (verify in Seller Central);
  referral rates from Amazon 2026 schedule (`amazon_us_fee_rules_2026.py`,
  `REFERRAL_RULES`); price-switch categories Health & Personal Care / Beauty switch
  8% ≤$10 / 15% >$10; FBA standard-size all-in fee table (0.5 lb $4.75 → 20 lb
  $12.50 → inf $15.00; fuel/logistics surcharge 0.035).
- **Scout UI** (`Northstar_backend/static/index.html`) — 5 views (Scout, Calculator,
  Risk, Cycle, Portfolio); rich filters/sorts (26 sort options, extensive filter
  facets), statuses (Pass/Hold/Reject/Needs Fee Verification/Needs Mapping
  Verification/Unscored), Proof Batch panel with offline-preflight banner and
  operator hard cap $0.01–$1.00 (recommended $0.50), type-to-approve live-run gate.
- **Spatial Command Center direction** — deep-space gradient mesh, sentiment-driven
  orbs (`--pos` #38c98e / `--warn` #d9a441), glassmorphism, Spotlight-style Command
  Omnibar, Contextual Tool Dock, Orbital Market Mapping, Risk/Reward Radar Webs
  (5-axis), Thermal Profit Topography; constraint: preserve element IDs/data-view/
  JS engine so jsdom tests keep passing; no fabricated visualizations.
- **Live-ops layer:** Bright Data Web Unlocker parallel adapter
  (`bright_data_costco.py`, gate `BRIGHTDATA_COSTCO_DETAIL_ENABLED` default 0),
  Firecrawl fallback adapter (`firecrawl_costco.py`, gate
  `FIRECRAWL_COSTCO_DETAIL_ENABLED` default 0), unified failover/full-pull
  runner (`costco_live_runner.py` — Bright Data primary, Firecrawl fallback,
  provider budgets, circuit-breaker halt), Easyparser Amazon enrichment runner
  (`enrich_manifest_run.py`, `--provider easyparser`, budget guard
  `WORST_CASE_REQUEST_CREDITS=30`), typed failure taxonomy (`url_not_found`,
  `no_data_found`, `unverified`, `transport_error`, `matched_dead_item`, ...).
- **Backend policy:** `Northstar_backend/config/brain_policy.json` —
  `live_provider_calls_default: false`, `min_roi_target_pct: 20.0`,
  `max_api_envelope_usd: 0.25`, `purchase_authorization_default: false`, etc.
- **DataForSEO guardrail architecture (planned):** 4-stage provider policy,
  hard $1.00 budget ceiling, integer micros, idempotency key
  `sha256(dataforseo:v1:standard_queue:{asin}:{validation_type}:{request_fingerprint})`,
  cache-first/null-first, build-to-fail-closed, canonical 20-ASIN source
  (`data/batch/proof-batch-preflight-20260818T060549Z.json`), run-id
  `data-validation-20asin-YYYYMMDD-HHMMSS`.

---

## 9. ROADMAP / NEXT STEPS

1. **Consolidate knowledge** into one master file for the Master Brain (this
   directory is that consolidation) — seed context for how T2 already operates.
2. **Finalize public naming** for each service (AdPilot, ListingForge, SourceScout,
   SocialPulse — or alternates).
3. **Build the lightweight classification/routing layer** in the Master Brain so
   requests are routed instantly without invoking a full reasoning model just to
   decide "who handles this."
4. **Design UI/UX for both tiers** — Services Suite (dashboard-style, one card per
   service) and AutoThink (chat/prompt-style, "tell it what you want").
5. **Fill model gaps** (live web/research, brand-voice copywriting, lightweight
   data-parsing, embeddings/routing).
6. **Prototype the learning loop** — capture user edits/corrections and feed them
   back into the user's judgment model.
7. **Execute the pending B085F1QCB9** single-request follow-up under the patched
   budget guard (needs fresh operator approval).
8. **Costco Step-2 retry decision** (8 items) — matcher-issue, recommendation
   leans against retrying.
9. **Known outstanding security item:** rotate `BRIGHTDATA_API_KEY` and scrub the
   plaintext credential in `FirstNorthstarautomationchat.md` (never read/printed).

---

*Consolidated 2026-09-07 from every source in `All AI Chat Markdowns` (master
vision session, local setup, AutoThink PPC, ads/PPC analysis, FBA 2026 compliance,
listing optimizer, retail arbitrage chats, and Word Coffee brand docs). Credentials
referenced by name only.*