# Northstar OS — Full Line of Services

**Version:** 2026-10-30 · Source: running code + `shared/subscription-plans.json` (catalog v4), `shared/usage-caps.json`, `docs/NORTHSTAR_OS_OVERVIEW.md`, `docs/NON_CREATIVE_REMAINING_WORK.md`.

## What Northstar OS is

Northstar OS is a commerce operating system for people who sell physical products. One surface takes a plain-language request, decides what kind of work it is, does the work with the right specialist, shows progress honestly, and hands back files you can use — with a record of what changed and what it cost.

Underneath it holds the whole operating loop of a product business: **Find → Judge → Build → List → Move → Watch → Remember → Build tooling**.

The front door is a conversation, routed by **Bojo**. Around it sit six focuses: **Auto, Create, Grow, Research, Operate, AutothinK** — lenses on the same brain, not separate apps.

## How services are classified here

**Creative service** — its output is a visual, audio, written-marketing or published asset.
**Non-creative service** — its output is analysis, a decision, a record, a measurement, or system configuration.

Where a service straddles both, it is marked with its primary classification and the straddle is named.

---

# PART 1 — CREATIVE SERVICES (6)

## 1. Design Studio — Creative

**Purpose:** The creative production house. Everything that becomes a picture, package, page, video or print file.

**Route:** `/design-studio` (10 sections). `/creative-studio` and `/product-designer` now redirect into it.

**Sections and what each produces:**
- **Projects** — project board and shared asset library.
- **Listing Images** — main image, lifestyle scenes, infographic modules.
- **A+ / Brand Story** — Amazon A+ modules and Brand Story cards, with alt text and placement instructions.
- **Storefront** — Amazon Storefront pages, hero images and tiles.
- **Ads** — Sponsored Brands video, custom images, DSP display units.
- **Video & UGC Clips** — product videos, UGC-style clips and hook frameworks.
- **Social** — posts, carousels and stories at exact per-platform pixel sizes.
- **Packaging & Mockups** — packaging concepts and photoreal mockup renders.
- **Dielines & Print** — parametric dielines exported as layered SVG, PDF and project ZIP.
- **3D Product Scene** — real 3D product scene composer.

**Engine and craft detail:**
- **Spec registry is the single source of truth** for every Amazon creative spec: main image, A+ modules, A+ size table, Premium A+, Stores tiles/hero/content, Sponsored Brands video, DSP ad types, suppression and style guides. Every spec carries a source id, a pulled-at date, and a **VERIFIED / REPORTED** confidence label. A REPORTED spec may never be the only basis for a blocking rule.
- **Safe zones are normalised (0..1 of canvas)**, so one crop rule renders correctly at every size and cannot drift from its source.
- **Default image engine:** FLUX 3 Image Klein (distilled) with Qwen3-VL-4B text encoder and the FLUX 3 VAE. FLUX.2 Klein 9B (Apache-2.0) is the fallback (`STUDIO_USE_FLUX2=1`).
- **Scene and lighting edits:** Qwen-Image-Edit-2511. Every edit records a `copy_preservation` verdict — if it is false the output is not shippable without re-compositing the text layer.
- **The image model never paints text.** Lettering, logos, weights, barcodes and legal copy are authored as deterministic structured layers (real fonts, real logo, exact spelling) via the compositor and label/logo tools. Realism dial defaults to `shading=0.5`.
- **Fidelity gate:** lock the real product photo as reference, place it as an opaque base, generate only around the product mask, then diff the exported product region against the reference. Export is blocked beyond the threshold.
- **Cutout + MAIN framing:** white background, ≥85% fill, ≥2000 px, with a compliance verdict.
- **Prepress:** CMYK conversion, gamut check, ink limit, proof output against a real press profile.
- **Package readiness verdict:** three blocker classes — real print risks, eyebrow/OCR warnings, dieline proportion cautions.
- **Disclosure ledger:** records every export transformation (PNG/JPEG, resize, re-encode, format change) so a file's history is never guessed.
- **Package builder:** front, back and side panels plus dieline in one job.
- **Video:** storyboarding and hook templates; capped motion via Wan 2.5 15s, premium via Kling 2.6 Pro / Veo 3.1 usage-metered add-ons.
- **Voice:** voice list, text-to-speech, and dubbing for voiceover work.

**Tiers:** Whetstone and Mainstay get V1 imagery. Keystone adds V2/V3 imagery and 3 capped video. AutothinK gets the largest image and video allotment.

**Status:** Every section is built. Generation lanes require the local media engine armed (`MEDIA_GEN_LIVE` + ComfyUI) or an armed cloud provider.

---

## 2. ListingForge — Creative (copy)

**Purpose:** The copy engine. Writes and defends the words that sell the product.

**Route:** `/listingforge`

**What it does:**
- Title generation, ≤200 characters, keyword-optimised.
- Five feature bullets, ≤500 characters each.
- Product description and A+ module copy.
- Backend search terms inside the 250-byte cap.
- **Listing Optimization Score** — a 0–100 composite.
- **Compliance guardrails** — rule-based claims screening before anything ships.
- **Rufus readiness scoring** — optimisation for Amazon's AI shopping assistant.
- **Brand voice enforcement** — every listing matches the brand's tone, not generic AI voice.
- **Multi-language generation** — JP / DE / ES / FR from an English source.
- **Keyword bridge** — AdPilot winners flow into listing copy; listing keywords flow back into ads.
- **Bulk listing builder** — many ASINs in one pass.
- **Versioning** — every change tracked; A/B test ingestion supported.

**Straddle:** the scoring, compliance and audit half is non-creative analysis. The writing half is creative.

**Tiers:** Whetstone gets copy. Mainstay adds media. Keystone and AutothinK add bulk execution.

---

## 3. SocialPulse — Creative

**Purpose:** Brand-aware social content generation, planning and scheduling.

**Route:** `/socialpulse`

**What it does:**
- Platform-specific captions for Instagram, Facebook, TikTok, X, Pinterest and LinkedIn.
- **Hashtag engine** — smart hashtag sets per post.
- **Seven-slot content calendar** and a rolling 30-day calendar.
- Templates per format; carousels, stories, reels.
- **Image prompt generation** wired to Design Studio.
- **Email generator** — including Amazon-compliant review request emails.
- **Amazon Attribution tagging** (`maas=` tags) so social traffic's rank impact is measurable.
- Influencer outreach messages per niche.
- Seasonal content planning; occasion and gifting angles.
- Engagement metrics and a content → ads feedback loop.

**Straddle:** the calendar, scheduling and attribution measurement half is non-creative operations.

**Tiers:** Whetstone and Mainstay include SocialPulse; attribution unlocks at Mainstay. **Publishing (`socialpulse_publish`) is AutothinK-tier only** and still requires a fresh operator approval for the actual post.

---

## 4. A+ Content — Creative

**Purpose:** Plan A+ detail-page modules that pass Amazon's rules the first time.

**How it is reached:** conversation-routed service line (A+ section of Design Studio for production).

**What it does:** module selection and sequencing, eligibility checks, module-count and image-size limits, alt text, placement instructions, and copy that is screened against A+ guidelines. Draws on the verified A+ module and size sources.

**Tier:** available across the suite as a planning service.

---

## 5. Creator Connections — Creative

**Purpose:** Run creator and influencer programmes without tripping disclosure rules.

**How it is reached:** conversation-routed service line.

**What it does:** writes creator briefs, sets commission structures and deliverables, defines usage rights, and checks every brief against disclosure requirements.

---

## 6. Brand & Store — Creative

**Purpose:** Build the brand surface around the product.

**How it is reached:** conversation-routed service line (Storefront section of Design Studio for production).

**What it does:** structures storefront pages and the brand story, sequences hero and tile content, and screens what the brand may and may not claim. Uses the Amazon Stores creative asset requirements and tile/hero sources.

---

# PART 2 — NON-CREATIVE SERVICES (25)

## Find and judge

### 7. SourceScout — Non-creative
**Purpose:** Product sourcing intelligence. Finds profitable Costco → Amazon arbitrage opportunities, scores them, and gets to a buying decision.
**Route:** `/product-finder`

- **Product database search** over the Costco catalog cross-referenced to Amazon ASINs.
- **Demand estimator** — BSR converted to monthly sales.
- **Fee calculator** against the actual Amazon 2026 US fee schedule, plus pricing and margin models.
- **Opportunity scoring** and margin shortlists.
- **Competitor analysis** — seller count, BSR movement, review velocity.
- **Price/BSR history** snapshots for trend charts.
- **Costco-to-Amazon mapping** by title, UPC and category.
- **Invoice verification** — validates COGS against Costco receipts and tags match quality.
- **COGS gap mining** — automatically finds Costco prices for ASINs missing COGS.
- **100-point risk model** — compliance 30, margin 20, crowding 15, volatility 15, packaging 10, replenishment 10.
- **Cycle scaling model** — 50-unit Cycle 1 through compound growth to a $10k infusion per cycle.
- **Inventory and replenishment intelligence** — stockout prediction from BSR velocity.
- **Authorization Gate** — four states: blocked, authorized, invoice pending, needs review. Prevents bad buys before money moves.

**Status:** offline reads cached results. A live scan needs `SCANNER_LIVE_ALLOWED=1` plus a paid provider key, which is a gated action.

**Tier:** all four plans.

### 8. Golden Goose Finder — Non-creative
**Purpose:** The strict opportunity filter. Only lets a product through when every mandatory gate is proven.
**Route:** `/golden-goose`

- **Ten-gate decision model:** product identity, variation identity, pack identity, economics complete, cost known, fees known, eligibility, sourcing route, documentation, brand permission. Nine are mandatory; brand permission applies only when relevant.
- **Missing input is UNKNOWN, never assumed PASS.** Decision states are explicit: `BLOCKED_PRODUCT_IDENTITY`, `BLOCKED_VARIATION_IDENTITY`, `BLOCKED_PACK_IDENTITY`, `BLOCKED_ECONOMICS`, `BLOCKED_ELIGIBILITY`, `BLOCKED_SOURCING`, `BLOCKED_DOCUMENTATION`, `BLOCKED_BRAND_PERMISSION`, `APPROVAL_REQUIRED`, `PURCHASE_READY`.
- **Persisted scan queue** with org-scoped review and decision round-trip.
- **Dry-run and mock scan** endpoints for safe testing.
- Scan caps per tier: 3 / 13 / 18 / 22 scans per month, 12 items per scan.

**Status:** the real evaluate surface is deliberately deferred — it needs the full ten-gate input UI first, and a half-built form would misrepresent the decision policy.

**Tier:** all four plans.

### 9. Profitability — Non-creative
**Purpose:** The money engine. Decides whether an opportunity is real.
**Route:** `/profitability`

- Backend calculator is the **only** authoritative calculator — no page defines its own formula.
- Tabs: Overview, Scenarios, Fee Basis, Inventory Impact, Export.
- Operator-supplied inputs; **anything missing stays UNKNOWN and `purchase_ready` stays false** until every gate is verified.
- Fee basis from the 2026 Amazon US schedule; inventory impact and scenario modelling.

**Status:** the economics engine is real; portfolio, fee, inventory and scenario bodies still render sample rows.

### 10. Competitor Monitor (RivalBoard) — Non-creative
**Purpose:** Watch the field so a listing does not get ambushed.
**Route:** `/competitor-monitor`
**What it does:** tracks competitor observations from real local product and source records, BSR movement, seller-count changes and review velocity.
**Status:** PARTIAL — real local records wired.

## List and defend

### 11. Listing Guardian (The Watch) — Non-creative
**Purpose:** Defend the live listing. Catch suppression, hijacks and claim problems before they cost revenue.
**Route:** `/listings`
**What it does:** listing health, identity enrichment and evidence counts over real local listing records.
**Status:** PARTIAL — real records wired, no live listing feed yet.

### 12. Keyword Tracker (RankLedger) — Non-creative
**Purpose:** Keep the rank record straight.
**Route:** `/keyword-tracker`
**What it does:** keyword sets and performance from real local data, plus rank snapshots and alerts at Mainstay and above (0 / 2,128 / 2,995 / 3,655 snapshots per month by tier).

### 13. Commerce Ops (The Ledger) — Non-creative
**Purpose:** Run the operational queue between a decision and a purchase.
**Route:** `/commerce-ops`
**Tabs:** Workflow, Tasks, Approvals, Blockers, History.
**What it does:** identity and pack resolution queue (181 items live), recent pipeline runs, blocker pills (pack match UNKNOWN, invoice pending, approval needed), approval trail and history.
**Status:** the identity-resolution queue and run history are real; the deeper task workflow is still sample.

### 14. Reseller Ops — Non-creative
**Purpose:** Keep reselling legitimate.
**How it is reached:** conversation-routed service line.
**What it does:** checks gating requirements and invoice readiness, grades product condition, and audits a reseller listing against the same rules Amazon applies.

## Move and measure

### 15. AdPilot — Non-creative
**Purpose:** Amazon PPC management, with real profit math behind every bid.
**Route:** `/adpilot`

- **ACOS / TACOS / break-even** computation.
- **Campaign judgement** and a **four-tier structure** — Auto → Broad → Phrase → Exact, with automated promotion lifecycle.
- **Keyword lifecycle** — Bench → Almost Winner → Winner, with automatic promotion and demotion.
- **Fixed bid guardrails.** Autonomous: decreases up to 20%, increases up to 10%, and adding negatives. Everything else is gated.
- **Negative keyword intelligence** from search term reports.
- **Placement optimisation** — top of search versus rest of search.
- **Dayparting** and **budget allocation** toward winners.
- **Bulk change plans** — ad reports turned into a validated, reviewable plan rather than blind writes.
- **ROI-integrated bidding** — bids against actual COGS and margin, not just ACoS.
- **Competitor ASIN targeting** auto-discovered from SourceScout data.
- **Amazon Attribution tracking** so social traffic's ad impact is measurable.

**Tiers:** ads read at Whetstone. Bulk execution at Keystone and AutothinK.

### 16. Monitoring — Non-creative
**Purpose:** Tell the operator when the system itself is unwell.
**Route:** `/monitoring`
**What it does:** live health checks and `/health/detailed`, error alerts and telemetry.
**Status:** live checks are real; service-check rows and alert delivery are partly sample and partner-side.

## Decide and remember

### 17. Command Center — Non-creative
**Purpose:** The morning briefing. What happened, what needs a decision, what the portfolio looks like.
**Route:** `/home`
**What it does:** real local activity — pipeline runs, audit events, campaigns — shown alongside live signals and portfolio tiles.

### 18. Memory Bank — Non-creative
**Purpose:** The per-account knowledge plane. The system learns *your* judgment and gets better with use.
**Route:** `/memory-bank`
**What it does:** stores facts, preferences, experiences and AI-derived learnings per account; ingests from text, images and voice; retrieves by intent at generation time so output carries real brand context. Revisions and unlearning are supported. All local, all free, no live calls.
**Status:** real knowledge-plane sessions, read-only in the room.

### 19. Master Brain — Non-creative
**Purpose:** The orchestrator and audit spine.
**Route:** `/master-brain`
**What it does:** knowledge-plane sessions, routing, agent delegation, validation and the audit trail. Holds the live-gate subscriber registry that decides whether an action is allowed right now.

### 20. Improvement — Non-creative
**Purpose:** The continuous improvement engine, visible to the operator.
**Route:** `/improvement`
**What it does:** reports coverage percentage over the golden question set, rule/atom counts, open gaps, per-domain pack versions, last cycle, and explicit `stopped` / `live_ready` flags.

## Build and automate

### 21. AutothinK — Non-creative
**Purpose:** The premium engineering and AI workspace. Claude Code meets Seller Central.
**Route:** `/autothink` (server :8100)

- Chat-based workspace with **code, research and computer tracks**.
- **Tool use** through the Master Brain gateway; full session history and an append-only run audit (`autothink-runs.jsonl`).
- **Domain-specific intelligence** — knows Amazon FBA, PPC, listings and sourcing, not generic AI.
- **Agent orchestration** — one request can route to ListingForge plus AdPilot together.
- **Cross-service queries** — "most profitable product and how are its ads?" pulls from SourceScout and AdPilot.
- **Handoff with a charge ceiling** — `handoff_to_autothink` prepares a brief and sends nothing until the operator confirms the charge; it refuses with the exact missing piece when the lane is not armed.
- **Small utility builder** — tip, percentage and break-even calculators produced as one self-contained HTML file, no network, no build step, no account.

**Tiers:** locked unless the account holds `autothink_workspace` — AutothinK tier only. Local Ollama or an armed cloud provider.

### 22. Spreadsheet Lab — Non-creative
**Purpose:** Clean and validate operational data without leaving the product.
**Route:** `/spreadsheet-lab`
**What it does:** paste or import CSV, detect and clean bad rows, dedupe, validate columns, choose a reasoning model, export a clean CSV.

### 23. Chrome Connect — Non-creative (infrastructure)
**Purpose:** The one and only way browser work happens.
**Route:** `/chromeconnect` (operator view)

- Plans each step, evaluates the live page, decides what to extract, and journals every decision, tool call, URL, timestamp and result.
- Headed, **read-only by default**, throttled.
- Runs on a **named leased Chrome profile** — Profile 6 only — with a 30-minute idle lease.
- Host policy is a denylist; **Amazon and its lookalikes stay in a hardcoded blocklist evaluated first**, even before the denylist.
- Action-level protections stay intact for credential entry, CAPTCHA, purchases/checkouts and external state changes. Opening the web never opens an action.
- Every action is re-checked against the current page URL, so a redirect cannot smuggle an action onto a refused host.
- Lessons are **PROPOSED-only** until an operator approves them; guardrail fingerprints are checked against a recorded baseline.

### 24. Tys Assistant — Non-creative (internal)
**Purpose:** The admin-facing automation agent.
**How it is reached:** `admin_automation`, `/api/admin/tys`
**What it does:** runs approved, bounded development and testing campaigns — files work orders, plans, delegates to coding and browser lanes, checkpoints, resumes and records evidence. It is the automation that builds and tests the product, not a customer service.

## Data and platform

### 25. Shared Data Layer — Non-creative
**Purpose:** One canonical dataset every service reads from, instead of five private copies.
**Route:** `/shared-data`
**What it does:** source refresh registry, live pull records, products, ASINs, cost records, keyword sets, snapshots — the single truth that cross-service intelligence depends on.

### 26. Provider Adapters — Non-creative
**Purpose:** Manage the engines behind the product, and keep the lanes honest.
**Route:** `/provider-adapters`
**What it does:** provider registry and configuration, arming state, model lists with verified usability, cost and licence metadata, and the **local lane versus cloud lane** split. A licence refusal is a refusal, not a warning.

### 27. Research & Corpus — Non-creative
**Purpose:** Answer a question with a cited source instead of a guess.
**How it is reached:** conversation-routed service line.
**What it does:** full-text and vector search over the local research corpus (57k+ sources), drift reporting when a rule's source changes, and knowledge lookup that returns the do/don't rule with its source. A weak lexical match is not a rule — below the confidence bar it says so.

### 28. Bojo (the Northstar Brain) — Non-creative
**Purpose:** The front door and router.
**What it does:** takes a plain-language request and decides whether to answer, build or hand off. Before spending time or credits it states what it will do, which specialists it will use, what it still needs, and roughly what it will cost. It reports real progress per tool run, and returns a downloadable artefact plus a change log.

## Admin and account

### 29. Beta-Ops — Non-creative
**Purpose:** Run the private beta.
**Routes:** `/beta-ops` and subpages
**What it does:** dashboard, orgs, invites (issue and revoke), cohort view, support triage, reports and CSV exports, audit notes, lifecycle actions and an eligibility checklist. Real: dashboard, orgs, audit, support, invites. Sample: cohorts, report rows, eligibility checklist.

### 30. Admin — Non-creative
**Purpose:** Platform administration.
**Route:** `/admin`
**What it does:** org management, plan and tier changes, suspend/resume, grant and activation, exports. **`platform_admin` only, fail-closed 401 otherwise.** Entitlement override, cancel and archive remain deliberately disabled.

### 31. Customer account surface — Non-creative
**Purpose:** Everything a customer needs around the product itself.
**Routes:** `/setup`, `/documents`, `/plan`, `/support`, `/account`, `/legal`, `/reaccept`, `/suspended`, `/downgraded`, plus public `/beta`, `/sign-in`, `/recovery`
**What it does:** onboarding and profile, operational documents, plan and usage view, support tickets, account status, legal acceptance and re-acceptance, and clear suspended/downgraded states.

---

# PART 3 — TIER LADDER

| Plan | Price / month | Services included | Action caps |
|---|---|---|---|
| **Whetstone** (`foundation`) | $39 | SourceScout, ListingForge, AdPilot, SocialPulse, Golden Goose | 4,153 chat · 3 GG scans · 906 listings · 226 posts · 40 images · 0 rank snapshots · 0 alerts |
| **Mainstay** (`scout`) | $79 | + Listing Guardian, Keyword Tracker | 14,635 chat · 13 GG scans · 3,193 listings · 798 posts · 141 images · 2,128 rank snapshots · 532 alerts |
| **Keystone** (`mover`) | $129 | + Competitor Monitor, Commerce Ops, advanced view | 20,591 chat · 18 GG scans · 4,492 listings · 1,123 posts · 199 V1 + 112 V2 + 28 V3 images · 3 video · 2,995 rank · 748 alerts |
| **AutothinK** (`autothink`) | $179 | Everything + AutothinK workspace | 25,134 chat · 22 GG scans · 5,483 listings · 1,370 posts · 243 V1 + 137 V2 + 34 V3 images · 4 video · 3,655 rank · 913 alerts · 9,871 T2 + 1,645 T3 AutothinK runs |

**Pricing discipline:** every tier is held inside a 60–80% margin band, worst-case cost between 20% and 40% of price. Refunds are pro-rated against credits actually consumed at $0.0078 per credit; credits are never refunded as cash. PPC management is included to $10k monthly ad spend, then 2.5% / 3.0% / 3.5% on the bands above.

**Important:** plan entitlements control which *surfaces* you can see. They never unlock a live or paid action. That separation is enforced in code.

---

# PART 4 — THE TRUST LAYER (applies to every service)

Two standing gates always require a fresh, explicit operator approval:

1. **Spending money or consuming paid credits.**
2. **Anything touching Amazon** — connecting, navigating, scanning, crawling or calling its APIs.

Everything else is autonomous by design; the product is meant to make its own outbound calls.

Around the gates:
- Browser work goes through **Chrome Connect** and nothing else.
- **Two provider lanes, separately armed.** The local bench may use non-commercial weights because nothing is resold; the cloud lane is restricted to commercially licensed tools. Every tool is checked against a registry before use.
- **Nothing pretends.** An empty field shows a dash and says what it needs. A missing provider shows a named boundary — engine, env var, gate flag — not a placeholder. A refused request says what it could have built.
- **Circuit breaker.** Any hard failure of an approved live action stops immediately, persists what succeeded, records a scrubbed manifest, and reports. No auto-retry, no silent skip.

---

# PART 5 — HONEST READINESS NOTES

- **Fully real locally:** Golden Goose queue and decisions, Admin/Beta-Ops admin routes, Commerce Ops identity queue, Profitability economics engine, Memory Bank sessions, Shared Data reads, Improvement telemetry, Design Studio editor and spec registry.
- **Real but partial:** Listing Guardian, Competitor Monitor, Command Center, Keyword Tracker, Monitoring, Profitability dashboard bodies, Commerce Ops task workflow.
- **Provider-gated:** SourceScout live scan (`SCANNER_LIVE_ALLOWED` + paid provider), media generation (`MEDIA_GEN_LIVE` + ComfyUI or armed cloud), AutothinK runs (Ollama or armed provider), SocialPulse publishing (operator approval).
- **Deliberately not built:** Golden Goose evaluate form (needs the full ten-gate UI), self-service recovery, acceptance recording, entitlement override, cancel, archive.
- **Legacy or experimental pages, not services:** `/packify-design` (earlier packaging concept page), `/baroque` (Gilded Void — the Baroque Hyperrealism visual-system stage).

---

**One line:** Northstar OS is one conversation over a full commerce operator's toolset — six creative service lines that produce the assets, twenty-five non-creative service lines that find the opportunity, prove the money, defend the listing, run the ads and keep the record — wrapped in a trust layer that never lets a convenience become a permission.
