# NORTHSTAR OS V3 — MASTER PLAN (Simple-First Shell · Cosmic Surface · Brand SEO Engine)

**Status:** canonical V3 specification, **additive** to
`master-brain/northstar-os-master-plan.md` (v1) and the research corpus
(`research/master_plan_v2_sweep_20261016/`). Nothing in v1/v2 is rewritten by
this document; it states what V3 keeps, what it adds, and what is still open.
Written 2026-10-18 on branch `feature/v3-simple-view`.

**Rollback baseline:** tag `v0.2.0-pre-v3-simple-view` (HEAD `6d4e847`) — the
build that shipped before any V3 change. Per `ROLLBACK_DRILL.md`, rollback =
worktree at the tag + boot probe; the live tree is never touched.

Status legend: **BUILT** (on disk + verified) · **PARTIAL** (real but
incomplete) · **PLANNED** (spec'd here, not built).

---

## 0. What V3 is (and is not)

**V3 makes the chat-first Simple view the product's main surface.** The
room-based Advanced view becomes a dev-level surface offered on certain
subscription tiers. On top of that, V3 adds the cosmic presentation layer
(procedural, not pre-rendered), the Brand SEO Engine, and the curated corpus.

**Kept untouched (do not alter without a reason tied to V3):**

- Every existing room, service, route, and test suite (S0–S3 chat core, Design
  Studio lanes, ListingForge/AdPilot/SocialPulse, SourceScout/Golden Goose,
  foundation/admin/beta-ops).
- The live-action safety model: `gates_always_off: true`, per-action named
  operator approval, circuit breaker, credential hygiene.
- Local-first posture: no new paid services; Amazon stays file-import-only.

**Reconciliations with the original brief (honest deltas):**

| Brief said | V3 does | Why |
|---|---|---|
| 19+ model router | Capability router over the INSTALLED lanes (qwen3:14b, qwen2.5-coder:14b, qwen3:4b, 27B, whisper.cpp, ComfyUI, qwen3-embedding:0.6b). Cloud slots only if the operator adds keys | The lanes are what runs on this machine; a "19-model" claim would be fiction |
| 20,000-resource scrape | Curated-index ingest (repo digests, MCP registries, docs, dataset cards) with license/provenance fields, resumable, honest counts | Mass scraping is out (ToS + guardrails); the v2 sweep already proved the compliant path (1,904 repos) |
| 30-minute 2K video loop | Procedural WebGL shader loop (infinite, seamless, ~0 MB texture) | A 16 GB card is shared with Ollama + ComfyUI; a 2K video loop is hundreds of MB of VRAM/disk for the same visual |
| Live continuous voice | PTT shipped (S3); continuous lane stays a later item | whisper.cpp PTT is real today; continuous bi-directional audio is a project, not a checkbox |

---

## 1. S4 — Simple-first shell (the main view) — **BUILT**

**Delivered**

| Piece | Where | Notes |
|---|---|---|
| Simple is the default mode | `src/context/ModeContext.jsx` | `DEFAULT_MODE='simple'`; resolution: `?shell=` → localStorage → default |
| Capability gate (fail-closed, async-safe) | `shell_router.py` + `App.jsx::ModeGate` | Tri-state: the gate is enforced the moment `/api/shell/context` resolves; never against an unknown, never fail-open |
| Focus rail (6 foci) | `src/shell/MasterBrainShell.jsx` + `shell_focus.py` | Auto · Create · Grow · Research · Operate · AutothinK; **server-owned** catalogue |
| Focus restricts tools | `chat_router.turn_event_stream` | The model is offered only the focus's registered tools; the UI cannot widen the set |
| Room → focus mapping | `MasterBrainShell.PATH_FOCUS` | Suite routes map 1:1 onto the rail groups in `nav-config.js`: `/autothink`→AutothinK, `/design-studio|creative-studio|product-designer`→Create, `/listings|listingforge|keyword-tracker|adpilot|socialpulse`→Grow, `/product-finder|golden-goose|competitor-monitor`→Research, `/profitability|commerce-ops|monitoring|...`→Operate |
| Focus injects brain context | `chat_adapter.build_chat_messages` | Focus prompt + context bits (`brand`, etc.) ride the system prompt |
| Focus persists per session | `PATCH /api/chat/sessions/{sid}` | Rename + focus; focus id validated against the catalogue |
| Universal chat surface | `src/chat/ChatSurface.jsx` | Markdown-lite, tool args/summaries/pct+phase, scroll respect + jump pill, edit & resend, retry, copy, queue chips, auto-grow composer, per-focus resume, rename + search rail, artifact lightbox + download, context receipts, voice meter/status |
| Room → focus mapping | `MasterBrainShell.PATH_FOCUS` | Deep links land on the right brain context (e.g. `/design-studio` → Create) |
| Auth gate parity | `App.jsx::SimpleShellRoutes` | Signed-out visitors on internal paths redirect to `/sign-in` — the Simple shell never bypasses the gate |
| Advanced entry points | `mb-to-advanced` button + top-nav toggle | Rendered only when the capability is granted |

**Remaining (PARTIAL):** mid-session focus switch re-points the brain but does
not re-summarise history; the honest label says so via the context receipt.
Suggestion chips are catalogue-owned (no learning yet). Room-based sub-views
inside a focus are still Advanced-only by design.

---

## 2. REA synthesis — reverse-engineering the four targets

Method: **public sources / existing corpus first** (autonomous), with
operator-signed-in windows only via the prepared runbook. Chrome Connect owns
browser control; REA attaches passively (no clicks, no input, no eval).

| Target | Pattern extracted | Northstar translation | Status |
|---|---|---|---|
| **Perplexity Computer** | Multi-model routing; parallel background agents; live "halo" while agents work; source receipts | Focus rail = router surface; canvas **pulse** while a turn streams; context receipts under answers (focus · model · tool runs · seconds) | BUILT (receipts, pulse, focus) / PARTIAL (parallel agents) |
| **Claude Code** | Agentic loop (gather → act → verify); MCP as tool layer; session snapshots/rewind; explicit permission prompts | Bounded tool loop already shipped (S2, `MAX_TOOL_STEPS=4`, honest tool-end); tool args/summaries now **visible**; session snapshots/rewind = PLANNED (AutothinK focus) | PARTIAL |
| **Packify.ai / Pacdora** | Conversational dielines; layered generation; print-ready exports | Already built in the design-studio RE pass (dielines, print lane, mockups); chat tools `list_templates`/`create_dieline` expose it to the Simple shell; inline SVG preview + download in artifact cards | BUILT |
| **Google Gemini** | Canvas-style side-by-side generate/refine; follow-up suggestion chips; model lane picker | Suggestion chips send on click; artifact lightbox + "Open in studio"; model lane picker = PLANNED | PARTIAL |

**Operator-window REA (deferred, needs you present):**
`research/packify_quality_deep_dive_20261016/REA_RUNBOOK.md` (Packify/DYP) —
ready to run; Perplexity/Claude/Gemini windows follow the same shape: dedicated
Chrome profile, operator drives, agent observes, `[PAUSE-AUTH]` respected.

### 2.1 REA inject — OpenBot concepts — **BUILT**

Three OpenBot patterns, adapted to this stack's guardrails (each one is a
boundary addition, not a permission addition).

| Concept | Northstar translation | Where | Status |
|---|---|---|---|
| **Tool Execution Gateway** | One interception point for every agent tool call: a **deny-list** (exec/eval/shell/credential/network/file tools) that no future registration can silently widen, an **append-only `tool_audit`** row for every attempt (`allowed`/`denied`/`executed` + reason + latency), then delegation to `chat_tools.run_tool`. Denials return the normal tool-failure shape, so the model reacts instead of crashing. | `tool_gateway.py`, `chat_schema.py` (`tool_audit`), `data_layer.py` (`ToolAuditDB`), `chat_router.py` (turn loop) | BUILT |
| **AG-UI generative UI** | A tool may declare a **card** in its result (`title` + `rows` + `action`); the turn loop appends it as a `card` part and the shell renders an **interactive component** — not a wall of text. First consumers are the VoiceStudio tools; the pattern is generic. | `chat_router.py` (card part), `src/chat/ChatSurface.jsx` (`.chat-card*`), `src/styles/shell.css` | BUILT |
| **Human-in-the-Loop handover** | A **Pause** control stops the agent mid-stream and flips the shell to "you're driving"; the turn queue is suppressed while paused, and the operator's next message hands control back. No state is lost — persistence continues on the existing session. | `src/chat/ChatSurface.jsx` (`chat-pause`/`chat-paused`/`chat-resume`) | BUILT |

The gateway is what makes the hardware telemetry daemon's "read-only by
construction" guarantee enforceable for **agent-initiated** actions: the daemon
registers no tools, and every tool an agent reaches is now gated and logged.

---

## 3. S6 — Cosmic shell, Master Brain planet, hardware guard — **BUILT**

- **Procedural WebGL canvas** (`src/shell/CosmicCanvas.jsx`): one full-screen
  fragment shader — drifting nebulae (fbm), pixel-space star fields with
  opposing micro-parallax, a Milky Way band with dark dust lanes, a distant
  Gargantua-style accretion disc (upper-left: glowing tilted ring, black
  sphere, photon ring, top-half lensing), and the deep-purple **Master Brain
  planet** parked in the upper sky with rim light, cloud banding, night-side
  sparkle and atmosphere glow. The planet pulses an energy ring while the brain
  works; its two orbiting moons **scale up and brighten** with the pulse.
- **Honest fallback:** no WebGL / shader failure → `data-cosmic-fallback="1"`
  leaves the CSS nebula gradient; nothing pretends.
- **Real telemetry:** `GET /api/shell/hardware` reads `nvidia-smi`
  (util/VRAM/temp) + RAM (Windows `GlobalMemoryStatusEx`, else `/proc/meminfo`),
  cached 3 s, `ok:false` + reason when unavailable. A **daemon thread** started
  from `main.py` keeps the 3 s cache warm so the shell chip and monitor modal
  always read fresh real values without a request paying the sampling cost.
- **VRAM governor (the 14.2 GB rule in software):** each sample carries
  `reserve_ok` + `recommended_dpr`. When free VRAM drops below the **1.8 GB
  reserve** the shell automatically lowers the canvas DPR (1.5 → 1.0) and the
  status chip warns. Renders already evict the local brain (`unload_brain`)
  before using the card.
- **Glass sheet:** the chat surface is a translucent dark-glass panel over the
  scene (media-scope tokens) so the cosmos is visible through it; the Advanced
  rooms keep the paper theme.

**RTX 5080 16 GB VRAM guard (the 14.2 GB rule)**

1. Local model/vision weights must stay **≤ 14.2 GB VRAM**; **1.8 GB is
   reserved** for the WebGL canvas + compositor.
2. The canvas caps device pixel ratio at **1.5** and is a single quad — the
   reserve target is met by construction, not by luck.
3. When free VRAM drops below 1.8 GB the status chip's tooltip reports the
   reserve violation; renders already evict the local brain
   (`unload_brain`) before using the card.
4. Animation pauses when the tab is hidden; `prefers-reduced-motion` renders a
   single static frame.

---

## 4. S5 — AutothinK premium surface — **BUILT** (deep-visual plan graph pending)

Focus "AutothinK" exists in the rail and is **locked** unless the account holds
the `autothink_workspace` capability (plan gate or hosted pro/team org). It
currently reuses the universal chat surface with the full tool set.

**BUILT — session fork / rewind (non-destructive):**

| Piece | Where | Notes |
|---|---|---|
| Fork endpoint | `chat_router.py` `POST /sessions/{sid}/fork` | Body `{upto_message_id?, title?}`. Copies the session up to and including that message into a **NEW** session; the parent is never mutated. Unknown message → 400; unknown/foreign session → 404. |
| Fork store | `data_layer.py` `ChatSessionsDB.fork` | Copies mode / model / focus_json and the message prefix (new ids); tenant-scoped so a fork only ever copies the caller's messages. |
| Lineage | `chat_schema.py` `chat_session_forks` + `ChatForksDB` | Each child records its parent + fork point. Append-only, additive. |
| UI | `src/chat/ChatSurface.jsx` `chat-fork` | A **Fork** control on any persisted message branches and opens the child; a just-streamed (un-persisted) turn is not forkable. |

**BUILT — plan/DAG visualiser (reconstructed, honest):**

| Piece | Where | Notes |
|---|---|---|
| Step order | `chat_schema.py` `chat_tool_calls.step_index` (+ `data_layer._migrate_chat_columns`) | 0-based order within a turn; additive column + idempotent ALTER for existing DBs. The turn loop writes it. |
| Plan builder | `chat_plan.py` `build_plan` | Pure: rebuilds `prompt → step 0 → step 1 → … → answer` from message parts + the tool-call ledger. **Linear on purpose** — the tool loop is bounded and sequential, so no hidden edges are invented; caveats say so. |
| Endpoint | `chat_router.py` `GET /api/chat/sessions/{sid}/plan` | Returns nodes / edges / per-turn grouping. Tenant-scoped. |

**BUILT — artifact browser:**

| Piece | Where | Notes |
|---|---|---|
| Read store | `data_layer.py` `ChatAttachmentsDB.list_by_session` | Joins `chat_messages` so the session filter is authoritative. |
| Endpoint | `chat_router.py` `GET /api/chat/sessions/{sid}/artifacts` | Each artifact with `ds_assets` metadata; a missing asset is reported `present:false`, never hidden. |

**BUILT — run panel (bounded run registry, NOT a code sandbox):**

| Piece | Where | Notes |
|---|---|---|
| Registry | `chat_schema.py` `chat_runs` + `data_layer.RunRegistryDB` | Tenant-scoped ledger of what actually ran (chat turns / tool executions): status, progress, `ref` (live handle), timestamps. |
| Wiring | `chat_router.py` `turn_event_stream` | Registers a run at turn start, finalises it on **every** exit path (done / cancelled / error). Best-effort; never breaks a turn. |
| Endpoints | `chat_router.py` `GET /api/chat/runs`, `POST /api/chat/runs/{id}/cancel` | Cancel only stops a genuinely live chat turn; anything else reports `cancelled:false` honestly. |

**Honesty boundary:** this is *not* an arbitrary-code sandbox. The tool gateway's
deny-list (`shell/exec/eval/…`, `tool_gateway.py`) is the enforceable boundary; a
run here is a bounded chat turn or tool execution, exactly as the loop performs.

**BUILT — workbench UI (Simple shell):**

| Piece | Where | Notes |
|---|---|---|
| Client | `src/chat/api.js` | `plan / artifacts / runs / cancelRun`. |
| Panel | `src/chat/WorkbenchPanel.jsx` | A right-hand drawer with a **Plan · Artifacts · Runs** tablist; honest empty/error states; a missing asset is marked; a non-stoppable run is not pretend-stopped. |
| Mount | `src/chat/ChatSurface.jsx` `chat-workbench-toggle` | Available in the chat head on every Simple surface (labelled the AutothinK workbench when the focus is `autothink`). |
| Harness | `verify-shell-v3.cjs` scenario F | Drawer opens; plan chain renders the tool steps; artifacts list; runs list with cancel. |

**Remaining (deep-visual upgrade):** the plan graph is drawn as a functional
linear chain. The immersive treatment — an animated node-link graph integrated
with the cosmic shell — is the deep-visual part of the plan and is deliberately
left for a stronger visual model pass.



---

## 4A. Create focus — VoiceStudio UGC media pipeline — **BUILT**

**What it is:** VoiceStudio is integrated as a **modular local API service**
(not a vendored dependency), powering automated UGC ad voiceovers, product
video localization, and hook testing inside the Create workspace.

| Piece | Where | Notes |
|---|---|---|
| Async API client | `voicestudio_adapter.py` | `VoiceStudioAdapter`: voice **cloning / profile management** (`list_voices`, `clone_voice`), **TTS generation** (`tts`), **multi-language dubbing** (`dub`). Config via `VOICESTUDIO_URL` (+ optional `VOICESTUDIO_API_KEY`, `VOICESTUDIO_PATHS`); no new deps (small `requests` core run on a worker thread, `asyncio.to_thread`). |
| Create-focus tool hooks | `chat_tools.py` + `shell_focus.py` | `voice_list`, `voice_tts`, `voice_dub` are registered tools and are offered **only** in the Create focus's tool set — the same server-owned restriction the other foci use. |
| Interactive results | `chat_router.py` card parts | Each voice tool returns an AG-UI **card** (voice/char count/lang) with a follow-up action, so an operator triggers and iterates on audio assets from the shell. |
| Gate | `tool_gateway.py` | Voice calls go through the gateway too: if the service is **unarmed/unreachable** the tool returns `ok:false` with the real reason — never a pretend voiceover. |

**Honesty contract:** no fabricated audio; unreachable service ⇒ honest failure;
every response reports the service's own latency, and the endpoints are the
operator's deployed routes. The adapter's default base URL is a **local
self-hosted instance** the operator runs — it is a configurable default, not a
claim that a service is present.

**Next (PARTIAL hooks):** a render-jobs panel for long dubs, hook-A/B comparison
cards, and wiring the same adapter into Creative Studio's video lanes.

---

## 5. S7 — Brand SEO Engine (across every service) — **PARTIAL**

**Principle:** SEO is not a listings feature; it is a property of the brand that
every service must serve. One canonical, versioned profile drives them all.

### 5.1 Brand SEO Profile (per brand, versioned) — **BUILT**
Entities & associations · keyword clusters (head/body/negative) · voice rules ·
prohibited claims · competitor set · measurement provenance (which numbers are
measured vs inferred). Written only by operator action or approved proposal —
never silently rewritten.

| Piece | Where | Notes |
|---|---|---|
| Schema | `seo_schema.py` (`SEO_TABLES_SQL`) | `brand_seo_profiles` (identity + `current_version` pointer) + immutable `brand_seo_profile_versions`. Additive; one source of truth for the shared DDL and the offline tests. |
| Store | `data_layer.py` `SeoProfilesDB` / `SeoContainer` | Create, get (with current body + version count), list, **append version** (never rewrites history), list/get versions. Tenant-scoped on every read and write. |
| Body rule | `seo_profile.py` `normalize_body` | A profile body is a JSON object; known sections must have the right container shape; **unknown keys are preserved, never dropped or coerced**; nothing is invented for the operator. |
| Service | `seo_router.py` `/api/seo/*` | `GET/POST /profiles`, `GET /profiles/{id}`, `GET/POST /profiles/{id}/versions`, `GET /profiles/{id}/versions/{v}`. Registered in `main.py` behind its own import guard. |
| Shell hook | `chat_tools.py` `seo_profile` (Grow focus) | Shows the current profile (or the account's profile list) as an **AG-UI card** — S7 is reachable from the Simple shell. Read-only; never invents a profile. |

Versions are append-only, so a rollback is always possible and an old version
stays readable; editing a profile is never a silent rewrite.

### 5.2 Listing revisions — latest is the SEO beneficiary — **BUILT**
- A new listing build or update creates a **revision**; the newest revision is
  the only object SEO work targets.
- Prior revisions are archived **read-only** (history, diffs, rollback); SEO
  passes never mutate them.
- `ds_listing_records` gains revision linkage (new additive table rather than
  rewriting the existing one).

| Piece | Where | Notes |
|---|---|---|
| Schema | `seo_schema.py` (`SEO_TABLES_SQL`) | Additive `ds_listing_revisions`: monotonic `revision` per `(account_id, listing_key)`, unique index; `ds_listing_records` is **not touched**. |
| Store | `data_layer.py` `DsListingRevisionsDB` (on `SeoContainer.revisions`) | `add_revision` (append-only; computes the next revision), `get`, `get_latest`, `list_revisions` (newest first), `list_latest` (one row per key). Tenant-scoped. |
| Service | `seo_router.py` `/api/seo/listings*` | `GET /listings`, `GET/POST /listings/{key}/revisions`, `GET /listings/{key}/revisions/{v}`, `GET /listings/{key}` (latest). |
| Scoring | `seo_score.py` `score_listing` | Deterministic keyword coverage of the profile clusters across title/bullets/backend/description; reports matched/missing/violations/competitor mentions. **No rank or volume claims**; `score=None` when the profile has no clusters. |

### 5.3 Cross-service hooks
- **ListingForge** — title/bullets/backend terms scored against the profile.
  **BUILT** as the `seo_check` tool (Grow focus): scores the latest stored
  revision (`listing_key`/`asin`) or inline copy against the brand profile and
  returns an AG-UI card (score, matched/total, missing head terms, prohibited
  claims, competitor mentions). Honest errors when there is no profile/listing.
- **Creative Studio** — alt text, A+ copy, dieline copy.
- **AdPilot** — ad copy angles.
- **SocialPulse** — hooks/hashtags.
- **SourceScout** — pack/title.

  **BUILT (scoring hook) for all five surfaces.** The engine is shared:
  `seo_score.score_text` scores any single block against the profile, and
  `SURFACES` names each service (`listing` / `creative` / `ad` / `social` /
  `source`). `seo_check` takes `content` + `surface` and returns the same card,
  so every service can score its own copy from the Simple shell. Deterministic
  keyword coverage only — no rank/volume claims.

  **BUILT (pipeline ops) for AdPilot and SourceScout:**
  `seo_ops.py` — `classify_search_terms` splits search terms into **negatives**
  (match the profile's negative cluster or a competitor) and **harvest**
  candidates (match a head/body cluster), reachable as the Grow tool
  `seo_negatives`; `retitle` normalises a raw title toward the head clusters
  within a length budget, reachable as `seo_retitle`. Both are deterministic,
  write nothing, and claim no performance. SocialPulse framing is served by the
  surface check above (`seo_check` with `surface=social`).

### 5.4 Measurement + learning (honest) — **BUILT (deterministic part)**
File-import first (SQP / search-term exports; the `search_query_performance`
schema already exists and is fed by `importers/brand_analytics_importer.py`).
The learning step reads those **measured** rows and proposes profile keyword
additions — candidates only, never an automatic edit.

| Piece | Where | Notes |
|---|---|---|
| Read store | `data_layer.py` `SqpPerformanceDB` (on `SeoContainer.sqp`) | Read-only access to imported SQP rows; scoped by ASIN (the import table has no account column, so callers must scope explicitly). |
| Proposal engine | `seo_learn.py` `propose_from_sqp` | Deterministic candidate terms: excludes terms already in the profile, ranks by measured `search_frequency_rank` then impressions. **No rank/volume claims**; empty rows → empty proposals + caveat. |
| Service | `seo_router.py` `GET /api/seo/proposals` | Read-only. Resolves the brand profile, reads scoped SQP rows, returns proposals. Writes nothing. |
| Shell hook | `chat_tools.py` `seo_propose` (Grow focus) | Candidate terms as an AG-UI card, reachable from the Simple shell. |

Approving a proposal is an **operator action** that appends a new profile version
via the existing append-only `POST /profiles/{id}/versions` — nothing is rewritten
silently. Embedding drift (`qwen3-embedding:0.6b` + sqlite-vec) remains the next
step; no rank-change claims are ever manufactured.

---

## 6. S8 — Curated corpus + continuous learning — **PLANNED**

Ingest pre-aggregated indices (local `research/**` including the v2 sweep's
`github_sweep.jsonl`, MCP registries, docs, dataset cards) into a local SQLite
index with license + provenance per record. Resumable, honest counts, no
scraping, no paid services. Feeds retrieval for the Master Brain and the SEO
engine's competitive context. *(20,000 is a target, not a gate.)*

---

## 7. Tier matrix (UI capabilities)

`shared/subscription-plans.json` (v4) is the single source of truth.
**UI gates are presentation/routing only — they never arm a live action.**

| Plan (tier) | `advanced_view` | `autothink_workspace` |
|---|---|---|
| Whetstone (foundation, $39) | — | — |
| Mainstay (scout, $79) | — | — |
| Keystone (mover, $129) | ✔ | — |
| AutothinK (autothink, $179) | ✔ | ✔ |
| platform admin (`internal_platform_admin`) | ✔ always | ✔ always |

During the hosted beta, orgs whose materialised entitlements carry
`advanced_reports` (pro/team cohorts) also receive `advanced_view`.

---

## 8. Verification protocol

| Layer | Evidence |
|---|---|
| Backend unit/integration | `python -m pytest` — S4/S5/S7 suites: `test_shell_modes` (33) · `test_tool_gateway` (5) · `test_voicestudio_adapter` (9) · `test_chat_fork` (10) · `test_chat_plan` (16) · `test_seo_profiles` (17) · `test_seo_listing` (23) · `test_seo_learning` (12) · `test_seo_ops` (15) + `test_chat_core`/`test_chat_tools`/`test_subscription_catalog_smoke`/`test_plans_route` (combined run: 168 passed) |
| Shell gate end-to-end | `node verify-shell-v3.cjs` — 28/28 (denied tier: shell only, no Advanced, `?shell=advanced` degrades; granted tier: Advanced renders rooms and returns; mobile toggle reachable at 390px; AG-UI card as a component; pause → paused → resume handover; fork opens a new branched session; **S5 workbench: plan chain, artifacts list, runs with cancel**) |
| Existing harnesses | `verify-guards.cjs` 11/0, `verify-admin.cjs` 33/0, `verify-acceptance.cjs` 2 fails (both pre-existing; baseline had 8 — 6 fixed by the harness role-vocabulary correction) |
| Build | `npm run build` — 0 errors |
| Live E2E (operator) | Start the stack, open `/ui/home` → Simple shell; switch focus; run one turn; open a render in the lightbox; flip to Advanced (if entitled) |

Harness note: the stubs now pin `ns-shell-mode=advanced` and stub
`/api/shell/*`, because **Simple is the product default** — room assertions
must opt into the Advanced shell. The stubs also use canonical backend roles
(`internal_platform_admin`, `organization_owner`), which fixed pre-existing
false failures.

---

## 9. Order of work

1. ~~S4 shell foundation~~ **BUILT + verified**
2. ~~S6 canvas / planet / telemetry~~ **BUILT + verified** (presentation polish
   continues under the UI/model phase)
3. ~~REA inject — tool gateway · AG-UI cards · human handover~~ **BUILT + verified**
4. ~~Create focus — VoiceStudio UGC media pipeline~~ **BUILT + verified**
5. S5 AutothinK premium surface — ~~session fork/rewind~~ · ~~plan/artifact/run
   backends~~ · ~~workbench UI~~ **BUILT**; the immersive plan-graph visual
   (deep-visual) is pending a stronger visual model pass
6. S7 Brand SEO Engine — ~~§5.1 versioned Brand SEO Profile~~ ·
   ~~§5.2 listing revisions~~ · ~~§5.3 cross-service scoring hook (all
   surfaces) + AdPilot negatives/harvest + SourceScout retitle~~ ·
   ~~§5.4 file-import learning (deterministic proposals)~~ **BUILT**;
   remaining §5.4 embeddings drift (sqlite-vec) next
7. S8 curated corpus + learning loop
8. Operator-window REA captures (Packify first) when the operator is present

Every live/paid action remains gated per action; nothing in V3 alters that.
