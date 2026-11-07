# Northstar OS — Full System Blueprint

**Generated:** 2026-10-24
**Repo:** `C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent`
**Purpose:** Complete handoff document for an external AI (Claude) to understand the entire build, programs, tools, and architecture before making fixes.
**Companion archive:** `exports/northstar_full_build_20261024.zip` (463 MB, sanitized — no secrets, no model weights, no node_modules/venvs).

---

## 1. What Northstar OS is

Northstar OS is a **retail arbitrage operating system**. It helps an operator (and eventually customers) find, evaluate, and list products for resale on Amazon, with a focus on Costco-sourced and wholesale inventory. It includes:

- Product discovery / sourcing (Costco, pallets, wholesale)
- Economics engine (profit, ROI, margin, fees)
- Golden Goose scoring (resale score, top-5)
- Listing generation + copy audit + Rufus-readiness
- Creative studio (image/video generation)
- Keyword tracking, competitor monitoring, listing guardian
- Chrome Connect (sanctioned browser automation for read-only site reads)
- A typed decision layer (rules / laya / jev)
- Memory bank (per-account knowledge plane)
- Multi-tenant foundation (orgs, users, roles, audit)

It is a **live product**, not a toy. The local AI runs inside it as the "Master Brain."

---

## 2. Repository layout (top level)

```
Northstar OS Retail Arbitrage Agent/
├── Northstar_backend/          # FastAPI backend (Python) — 450+ modules
│   ├── foundation/             # Multi-tenant foundation (auth, orgs, audit, jobs)
│   ├── costco_non_kirkland/    # Costco enrichment pipeline
│   ├── adapters/               # Reasoning provider adapters
│   ├── analysis/               # Supplier cost-benefit
│   ├── tests/                  # Backend tests
│   ├── test_*.py               # ~100 test files
│   ├── main.py                 # FastAPI entry
│   ├── decision_layer.py       # Typed decision layer (rules/laya/jev)
│   ├── cost_model.py           # Usage caps + margin invariants
│   ├── usage_meter.py          # Per-account per-month action counters
│   ├── provider_suite.py       # Local vs cloud tool gating
│   └── ...
├── northstar-os-ui/            # React 18 + Vite SPA (port 8101)
│   └── src/                    # Rooms, pages, components
├── northstar/                  # Legacy/alt backend (security, etc.)
├── shared/                     # Shared JSON configs
│   ├── usage-caps.json         # Tier caps + unit costs + margins
│   ├── provider-suite.json     # Local vs cloud tool registry
│   ├── service-model-map.json  # Per-service model tier assignment
│   └── model-suite.json        # Model tier definitions
├── config/                     # chromecontrol_policy_owner.json etc.
├── tools/                      # Dev/test/agent tools (chromeconnect_guard, browser_agent, ...)
├── scripts/                    # chromecontrol MCP server, agent JS
├── docs/                       # Constitution, blueprints, plans
├── specs/                      # API specs
├── skills/                     # Agent skill files
├── master-brain/               # Master brain docs
├── state/                      # Runtime state
├── knowledge/                  # Knowledge plane data
├── migrations/                 # DB migrations
├── deploy/                     # Deployment configs
├── tests/                      # Top-level tests
├── .env / .env.example         # Config (secrets never committed)
├── 00_STATE.json               # Current build state
├── AGENTS.md                   # Northstar capsule (auto-loaded)
└── docs/OPERATING_CONSTITUTION.md  # Full law
```

---

## 3. Architecture: two lanes

Northstar runs **two distinct tool suites** (see `shared/provider-suite.json`, `Northstar_backend/provider_suite.py`):

| Lane | Name | Cost | Commercial | Use |
|---|---|---|---|---|
| **local** | Local engine (Ollama + ComfyUI) | free_local | no (non-commercial weights OK) | Operator bench, never resold |
| **cloud** | Cloud engine (OpenRouter/fal/Replicate) | api_metered | yes | Customer-facing, commercially licensed |

- `active_provider()` defaults to `local` for operator, `cloud` for customer.
- Every tool declares `lanes`, `license`, `commercial_ok`, `network`, `installed`, `gate`.
- `verify(tool, provider)` fails closed on unknown/licence/lane/gate.
- Cloud lane requires commercial licence + arming (`CLOUD_MODEL_LIVE=1`, etc.).

---

## 4. Backend (FastAPI)

**Entry:** `Northstar_backend/main.py`
**Framework:** FastAPI + Postgres (foundation DB) + SQLite (legacy).
**Services:** Defined in `shared/service-model-map.json` — SourceScout (T1), Golden Goose (T2), ListingForge (T2, media V2/V3), AdPilot (T2), SocialPulse (T2, media V1/V3), Listing Guardian (T1), Keyword Tracker (T1), Competitor Monitor (T1), Commerce Ops (T1), AutothinK (T2→T3), Creative Studio (media), Audits (T3).

**Key modules:**
- `decision_layer.py` — typed decisions (copy_audit, listing_tier, duplicate, blocker_escalation, respond_now). Backends: rules (default), laya (local 421M), jev (cloud, opt-in metered). Includes consumer_match (Jev semantics).
- `cost_model.py` — usage caps + margin invariants (MARGIN_FLOOR 0.60, MAX_COST_FRACTION 0.40, band 60-80%).
- `usage_meter.py` — per-account per-month action counters (chat_t1, listing, post, gg_scan, etc., + jev_decision).
- `provider_suite.py` — lane/tool gating.
- `costco_api_client.py`, `costco_browser_scraper.py`, `costco_playwright_scraper.py` — Costco data.
- `costco_non_kirkland/` — enrichment pipeline (economics, scoring, reports).
- `golden_goose_decision.py` — 10-gate resale decision.
- `foundation/` — multi-tenant core (auth, orgs, users, roles, audit, jobs, approvals).
- `adapters/reasoning_provider.py` — LLM provider adapters (mock, openrouter, etc.).
- `reasoning_tasks.py` — listing_proposal, ad_copy_proposal, etc.
- `chat_router.py`, `chat_tools.py` — chat interface + tools.
- `autothink/` — AutothinK engine.
- `creative_pricing.py`, `creative_execute.py` — creative job pricing.
- `local_vision.py`, `local_transcribe.py`, `local_voice.py` — local AI helpers.
- `memory_bank.py` (knowledge plane) — per-account facts/preferences/experiences.

**Model routing:** `shared/model-suite.json` defines T1/T2/T3 text tiers + media tiers V1/V2/V3. `model_router.resolve_for_service()` maps service→tier→provider.

---

## 5. Frontend (northstar-os-ui)

- React 18 + React Router 6 + Vite 5. Dev: port 8101. Build: `npm run build` → `dist/`, served under `/ui/` by FastAPI.
- Design system: Paper/bone surfaces, pine forest ink, Libre Baskerville serif + DM Sans UI.
- Route structure: Public (/beta, /sign-in, /recovery, /legal) → Customer (/, /setup, /documents, /plan, /support, /account) → Admin (/beta-ops/*) → Internal (/home, /product-finder, /golden-goose, /listings, /monitoring, /admin).
- Key components: TopNav, SideNav, CommandPalette, RouteGuard, PageLayout, DataTable, EvidencePacket, MetricTiles, MobileBottomNav.
- Rooms: ProductFinder, GoldenGoose, Listings, Monitoring, Admin, ChromeConnect (planned), Keyword Tracker, Profitability Dashboard, etc.

---

## 6. Provider tool suite (local vs cloud)

Full registry in `shared/provider-suite.json`. Highlights:

**Local lane tools:** comfyui, flux2_klein, qwen_image_edit, birefnet, wan22_ti2v, flux1_dev (non-commercial), ultratex, openmontage (AGPL), piper_tts, local_vision_qc, sapi_voice, faster_whisper, rapidocr, chromeconnect, blender, skills_plane, decision_layer, laya, headroom (unusable), skylos, surya (not installed), sana, text_to_cad, img2threejs, turbovec, claude_mem, open_design, open_sandbox, agentconnect (patterns adopted), herk_edit_kit (parked), package_design, lightpanda (rejected).

**Cloud lane tools:** openrouter_text, fal_image_video, replicate_edit, elevenlabs_tts, skills_plane, decision_layer, typesafe_jev (new, cloud-only, metered, gated).

**Rejected/parked:** lightpanda (second browser path), herk_edit_kit (browser collision + metered), headroom (fail-open), text-to-cad (Node runtime), openmontage (AGPL network clause unreviewed for cloud).

---

## 7. Chrome Connect (browser control)

**The single sanctioned browser path.** No script/agent may drive Playwright directly.

- Controller: external `CHROMECONTROL_ROOT` (default `C:\Users\T2Hol\OneDrive\Documents\Default Project`), CLI `scripts/chromecontrol-agent.js`, MCP server `scripts/chromecontrol-mcp-server.js`.
- Python guard: `tools/chromeconnect_guard.py` — import hook refuses `playwright*` unless a controller instruction is active; exclusive pid-tracked lock on CDP port 9222. No escape hatch.
- MCP tools exposed: `chromeconnect_preflight`, `chromeconnect_run`, `chromeconnect_status`, `chromeconnect_journal`, `chromeconnect_lessons`, `chromeconnect_guardrails`.
- Guardrails: operator-owned allowlist (`config/chromecontrol_policy_owner.json`) + hardcoded Amazon blocklist. Lessons are PROPOSED-only. Per-host grants expire ≤24h.
- Policy fingerprint baseline tracking; `chromeconnect_guardrails` reports intact/mismatch.
- P6 (planned): browser_jobs protocol, chromeconnect_runner package (Python+Playwright, persistent t2 profile), site adapters (costco, palletfly, sellersprite, amazon_public, amazon_seller_central, vendor_dashboards), evidence-first extraction, ChromeConnect admin room, QA screenshots.

**Important:** `jev-ultrafast` (browser-use/jev-ultrafast) is NOT wired — it drives Playwright directly and would be a second browser path (same rejection as lightpanda).

---

## 8. Cost model & usage meter & margins

**Files:** `Northstar_backend/cost_model.py`, `Northstar_backend/usage_meter.py`, `shared/usage-caps.json`.

- Tiers: whetstone ($39), mainstay ($79), keystone ($129), autothink ($179).
- Unit costs per action (chat_t1, listing, post, autothink_t2/t3, gg_scan, gg_item, image_v1/v2/v3, rank_snapshot, alert, video_wan_15s, fixed_infra, jev_decision).
- `worst_case(plan)` computes worst-case cost (all caps consumed) + margin. Invariant: margin ≥ MARGIN_FLOOR (0.60) and ≤ MARGIN_CEILING (0.80) (cost 20-40% of price). Tested.
- Current margins after Jev integration: whetstone 0.7044, mainstay 0.7001, keystone 0.7064, autothink 0.7042.
- UsageMeter: per-account, per-action, per-month counters with caps. `meter_from_caps()` builds from usage-caps.json.
- PPC fee bands, refund policy also in cost_model.

---

## 9. Decision layer

**File:** `Northstar_backend/decision_layer.py`.

Kinds: copy_audit, listing_tier, duplicate, blocker_escalation, respond_now (closed label sets).
Backends:
- `rules` — deterministic, default, offline.
- `laya` — local 421M System-1 (optional, presence-checked).
- `jev` — TypeSafe Jev cloud (opt-in, metered, network; `JEV_AUTO=1` to auto-use).

Includes declarative DECISIONS with criteria, consumer_match (Jev semantics), probability distributions. Never raises; degrades to rules.

---

## 10. Memory bank (knowledge plane)

Per-account knowledge store: facts, preferences, experiences, AI-derived learnings. Ingested from text/images/voice, retrieved by intent at generation time. Revisions + unlearn supported. All local, all free, no live calls. `memory_bank.py` (propose_revision gate).

---

## 11. Master build plan (phases)

See `docs/NORTHSTAROS_MASTER_BUILD_PLAN.md`. Phases:
- P0 Foundation (multi-tenant)
- P1 Auth & roles
- P2 Data layer
- P3 Economics
- P4 Freshness
- P5 Golden Goose vertical slice
- P6 ChromeConnect (browser jobs, runner, adapters, evidence)
- P7 Providers & credentials (spend caps, arming, credential intake, health)
- P8 Wire remaining rooms (8A-8D)
- P9 (tool registry, etc.)

Current state in `00_STATE.json` (batch/next_batch/known_issues).

---

## 12. Operating constitution & guardrails

**File:** `docs/OPERATING_CONSTITUTION.md` (full law). Capsule in `AGENTS.md`.

Key guardrails:
- Credential hygiene: never read/print/commit .env values.
- Real-money/transactions require explicit approval.
- Git safety: no push to protected branches (main, release/*, hotfix/*) without approval.
- Protected data: never delete/overwrite fixtures/datasets.
- Circuit breaker on hard failure.
- Chrome Connect is the only browser path.
- Provider suite: local vs cloud licensing; reason codes are refusals.
- Autonomous zone: build/run/test code, fix bugs, run product features against configured providers, local commits.

---

## 13. Environment & config

**`.env` / `.env.example`** (keys only, no values committed). Non-secret keys editable (§3.1 list). Key groups:
- Database: FOUNDATION_DB_URL, POSTGRES_*
- Providers: OPENROUTER_API_KEY, CLOUD_MODEL_LIVE, FAL_API_KEY, etc.
- Chrome: CHROMECONTROL_ROOT
- Jev: JEV_API_URL, JEV_API_KEY, TYPESAFE_API_KEY, JEV_MODEL, JEV_AUTO
- Media: MEDIA_GEN_LIVE, etc.
- Local AI: LAYA_ROOT, LAYA_BIN, LAYA_QUESTIONS, PIPER_MODEL, etc.

**`opencode.json` / `opencode.jsonc`**: registers `chromeconnect` MCP server; playwright disabled.

---

## 14. Recent integrations (2026-10-24)

- **Jev decision backend** integrated (decision_layer.py, provider-suite.json, usage-caps.json, cost_model, usage_meter, tests). Cloud-only, opt-in, metered. Margins verified ≥70%.
- **AgentConnect patterns** adopted: declarative decisions, durable loop breaker, org-knowledge revision gate, checkpoint-verified operator-setup skill.
- **Packify patterns** adopted: package_design module.
- **Laya** wired as optional local backend (6/12 on copy-audit eval).
- **Headroom** rejected (fail-open, no compression).
- **Lightpanda** rejected (second browser path).

---

## 15. Test suites

- `Northstar_backend/test_*.py` (~100 files) — pytest.
- `Northstar_backend/foundation/tests/` — foundation tests.
- `northstar-os-ui`: `npm run build` (0 errors), `verify-acceptance.cjs`.
- `tools/chromeconnect_guard.py` self-test.
- Cost model tests assert margin floor/band.

Run: `cd Northstar_backend && python -m pytest -q`.

---

## 16. Known issues / deferred (from 00_STATE / reports)

- `chromeconnect_runner/` package not yet built (P6-T2).
- Jev endpoint/schema unverified (degrades to rules).
- TypeSafe commercial terms unverified.
- Headroom unusable on bench.
- Laya underperforms on domain (optional only).
- Various parked items: text-to-cad (Node runtime), surya, sana, img2threejs, turbovec, claude_mem, open_design, open_sandbox, herk_edit_kit.

---

## 17. Key file index

| Concern | File |
|---|---|
| Constitution | docs/OPERATING_CONSTITUTION.md |
| Capsule | AGENTS.md |
| Master plan | docs/NORTHSTAROS_MASTER_BUILD_PLAN.md |
| Production blueprint | docs/PRODUCTION_BLUEPRINT.md |
| Provider suite | shared/provider-suite.json, Northstar_backend/provider_suite.py |
| Service-model map | shared/service-model-map.json |
| Usage caps / costs | shared/usage-caps.json, Northstar_backend/cost_model.py |
| Usage meter | Northstar_backend/usage_meter.py |
| Decision layer | Northstar_backend/decision_layer.py |
| Chrome guard (Python) | tools/chromeconnect_guard.py |
| Chrome MCP server | scripts/chromecontrol-mcp-server.js |
| Browser agent (legacy) | tools/browser_agent.py |
| Backend entry | Northstar_backend/main.py |
| Frontend | northstar-os-ui/ |
| State | 00_STATE.json |
| This blueprint | docs/NORTHSTAR_FULL_BLUEPRINT_20261024.md |
| Build archive | exports/northstar_full_build_20261024.zip |

---

## 18. How to run

```bash
# Backend
cd Northstar_backend
python -m pytest -q

# Frontend
cd northstar-os-ui
npm run dev        # port 8101
npm run build      # -> dist/

# Provider suite check
python Northstar_backend/provider_suite.py --check <tool> --provider <local|cloud>

# Decision layer CLI
python Northstar_backend/decision_layer.py copy_audit "some listing copy"
```

---

*End of blueprint. Companion archive: exports/northstar_full_build_20261024.zip (463 MB).*
