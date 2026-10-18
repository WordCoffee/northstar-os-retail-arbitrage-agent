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

## 4. S5 — AutothinK premium surface — **PARTIAL**

Focus "AutothinK" exists in the rail and is **locked** unless the account holds
the `autothink_workspace` capability (plan gate or hosted pro/team org). It
currently reuses the universal chat surface with the full tool set.
**PLANNED:** session snapshots/rewind (fork a session from any turn),
multi-step plan/DAG visualiser, sandbox runner panel, build-artifact browser.

---

## 5. S7 — Brand SEO Engine (across every service) — **PLANNED**

**Principle:** SEO is not a listings feature; it is a property of the brand that
every service must serve. One canonical, versioned profile drives them all.

### 5.1 Brand SEO Profile (per brand, versioned)
Entities & associations · keyword clusters (head/body/negative) · voice rules ·
prohibited claims · competitor set · measurement provenance (which numbers are
measured vs inferred). Written only by operator action or approved proposal —
never silently rewritten.

### 5.2 Listing revisions — latest is the SEO beneficiary
- A new listing build or update creates a **revision**; the newest revision is
  the only object SEO work targets.
- Prior revisions are archived **read-only** (history, diffs, rollback); SEO
  passes never mutate them.
- `ds_listing_records` gains revision linkage (new additive table rather than
  rewriting the existing one).

### 5.3 Cross-service hooks
- **ListingForge** — title/bullets/backend terms scored against the profile.
- **Creative Studio** — alt text, A+ copy, image-text policy, dieline copy.
- **AdPilot** — search terms → negatives/harvest; ad copy angles.
- **SocialPulse** — hooks/hashtags; external-traffic framing.
- **SourceScout** — pack/title normalisation toward the brand's cluster.

### 5.4 Measurement + learning (honest)
File-import first (SQP / search-term exports; the `search_query_performance`
schema already exists and is empty). Embeddings drift via
`qwen3-embedding:0.6b` + sqlite-vec; the Master Brain proposes profile updates
that the operator approves. **No rank-change claims** are ever manufactured.

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
| Backend unit/integration | `python -m pytest test_shell_modes.py` (27) + `test_chat_core`/`test_chat_tools`/`test_subscription_catalog_smoke`/`test_plans_route` (65 total in the combined run) |
| Shell gate end-to-end | `node verify-shell-v3.cjs` — 14/14 (denied tier: shell only, no Advanced, `?shell=advanced` degrades; granted tier: Advanced renders rooms and returns; mobile toggle reachable at 390px) |
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
3. S5 AutothinK premium surface (snapshots/rewind, plan visualiser) — next UI phase
4. S7 Brand SEO Engine (profile, revisions, cross-service hooks, imports)
5. S8 curated corpus + learning loop
6. Operator-window REA captures (Packify first) when the operator is present

Every live/paid action remains gated per action; nothing in V3 alters that.
