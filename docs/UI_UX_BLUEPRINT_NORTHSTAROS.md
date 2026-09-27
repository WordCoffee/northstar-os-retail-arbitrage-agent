# NorthstarOS UI/UX Blueprint — Full Service-by-Service Spec Sheet

> Operator-supplied authoritative spec (2026-09-27). SourceScout is the frozen benchmark room.
> Rooms are judged against: same suite, specifically designed for the job of the service.

NorthstarOS should be built as a premium suite of dedicated service rooms, not as a generic dashboard with many tabs. It should match the breadth, operational usefulness, and workflow coverage expected from Helium 10-class seller software while maintaining a more composed, more premium, more editorial, and more evidence-conscious experience that is visually distinct from Helium 10 and from SellerAmp (SAS, https://sas.selleramp.com/). SellerAmp is the sole competitor reference; SellerSprite is no longer a reference product.

This blueprint defines the suite-wide operating model, the page-by-page service architecture, the functional requirements for each major room, the interaction patterns that should repeat across the suite, and the room-specific UI/UX identities that make NorthstarOS feel unified without making every service look the same.

## Product direction

NorthstarOS is a suite of individually named services, not one main service with subordinate tools. Each major service must have its own landing page, own local navigation, own primary actions, own above-the-fold working surface, and its own room-specific composition that fits the job being performed.

The suite should follow a simple principle: borrow proven workflow structures from established products where those patterns are clearly useful, but do not borrow their visual identity, layout rhythm, or product feel. Seller software shows the expected functional breadth, while social-planning and AI content tools demonstrate effective planning, asset generation, calendar, and approval workflows that NorthstarOS can reinterpret through its own design system.

## Suite-wide design system

### Visual language

NorthstarOS should use a calm, premium, operator-grade interface built on warm paper and bone surfaces, forest and pine ink, restrained ochre and clay warning tones, fine mineral dividers, modest elevation, and broad content areas with intentional density. Serif should be reserved for editorial emphasis such as room titles and certain section headers, while operational UI should remain fast and readable in a clean sans-serif system.

The suite must not use dark-neon styling, glassmorphism, glowing AI ornamentation, or generic startup-dashboard gradients. Its beauty should come from proportion, hierarchy, clarity, spacing rhythm, and room-specific composition rather than decorative effects.

### Truth-state system

Every room must use one shared truth taxonomy. Unknown values must remain unknown rather than being visually softened into zero or hidden entirely. At minimum, the suite should consistently distinguish:

- UNKNOWN — no data available.
- UNVERIFIED — not yet confirmed.
- UNAVAILABLE — expected field missing or inaccessible.
- INCOMPLETE — analysis cannot be completed with current data.
- REQUIRED — user or operator action needed.
- SAMPLE DATA — fictional or placeholder content.
- ASSUMPTION — modeled or hypothetical value.
- OBSERVED — directly observed at a stated time.
- CACHED — stored snapshot, not live.
- HISTORICAL — old benchmark or prior-state value.
- VERIFIED — independently confirmed.

These must not be plain text states buried in tables. They should be visually systematized and used in tables, cards, rails, timelines, tooltips, banners, and detail drawers.

### Shared shell

Every internal service room should inherit the same shell:

- Suite Rail on the left, grouped by Research, Growth, Operations, Intelligence, and Admin.
- Top Bar with the Northstar Index, global search/open actions, session identity, notifications, and quick-create affordances.
- Room Header with service name, service purpose, primary CTA, and local tabs.
- RoomTabs for local navigation within each service.
- DataNotice banners for sample data, cached snapshots, assumptions, concept-only states, or backend-needed states.
- Cross-suite handoff links so work moves naturally between rooms.

This structure should remain stable because mature software suites rely on persistent navigation and local subnavigation for speed and clarity.

### Shared UI primitives

| Primitive | Purpose | Typical rooms |
|---|---|---|
| SuiteRail | Cross-suite navigation | All authenticated rooms |
| TopNav / Northstar Index | Global search, command, open, jump | All rooms |
| RoomTabs | Service-local navigation | All service rooms |
| DataNotice | Truth-state and environment banners | All rooms |
| StatusPill | Consistent state signaling | All rooms |
| EntityStrip | Core identity fields | Research, listings, ads, monitoring |
| DecisionRail | Readiness or gating matrix | Research, sourcing, ops |
| EvidencePacket | Provenance-rich evidence blocks | Research, reviews, AI synthesis |
| Queue + Detail | Review or ops workflow | Golden Goose, Commerce Ops, AdPilot |
| Timeline | Freshness, change logs, history | Monitoring, research, data rooms |
| Editor Canvas | Structured content editing | ListingForge, Creative Studio, SocialPulse |
| Planner Table | Scenario and allocation logic | AdPilot, Profitability, Commerce Ops |
| Alert Stack | Prioritized watch issues | Command Center, Listing Guardian |

## Information architecture

### Top-level suite groups

- Research: SourceScout, Golden Goose Finder, Keyword Tracker, Competitor Monitor
- Growth: ListingForge, AdPilot, SocialPulse, Creative Studio
- Operations: Profitability Dashboard, Commerce Ops, Listing Guardian
- Intelligence: Command Center, Master Brain, Memory Bank, AutothinK
- Systems / Admin: Shared Data Layer, Provider Adapters, Beta Ops, Administration, Customer Workspace

### Room contract

Every service room should satisfy the same six-part contract:

1. Intent — what job this room performs.
2. Working surface — the main area where the work happens.
3. Decision context — evidence, truth states, limitations, and risk framing.
4. Primary actions — what can be done next.
5. Secondary depth — tabs, drawers, below-fold detail, alternate views.
6. Handoff — how work moves to another room in the suite.

The contract stays constant, but the page composition changes depending on the type of work.

## Service-by-service specification

### Command Center
- Purpose: suite briefing room; orientation surface (what changed, what needs attention, what is blocked, where to go next). Not a catch-all dashboard.
- Page identity: executive briefing board, morning-briefing feel, composed and directional.
- Required above-the-fold: room header with briefing date range + active org + one primary CTA ("Open Priority Queue"); exception stack; What Changed panel tagged OBSERVED/CACHED/HISTORICAL; priority routes into SourceScout/GG/Commerce Ops/ListingForge/AdPilot; portfolio exposure snapshot with basis captions and truth pills.
- Local tabs: Overview, Exceptions, Activity, Exposure, Handoffs.
- Features: cross-suite alerts feed; Today/7d/30d scope switch; "Open in room" handoffs; muted non-authoritative summary metrics with basis labels; assigned-owner visibility; activity provenance timeline.
- Must not: become a catch-all dashboard; duplicate full analytical views from Profitability or AdPilot.

### SourceScout (frozen benchmark)
- Purpose: flagship product research workbench; SellerAmp-class usefulness, visually distinct and more premium.
- Page identity: research desk, evidence-first, identity hero on top, risk/economics/provenance immediately visible.
- Required above-the-fold: product identity hero (title, brand, category, ASIN state, pack state, UPC/GTIN, MPN/model, pack count); Decision Rail (eligibility, gating, hazmat, IP risk, pack match, sourcing readiness, fee basis, physical data, operator status); Market Evidence table with truth pills + source/freshness labels; primary actions (new lookup, open in product set, send to Commerce Ops); muted freshness/provenance, never success-colored.
- Local tabs: Lookup, Product Set, Saved Sets, Coverage.
- Features: search by ASIN/UPC/keyword/name; identity validation; pack/case matching; market evidence snapshots; risk/eligibility signaling; economics completeness; sourcing/invoice-readiness separation; provenance timeline; related entities; handoff to GG/Commerce Ops.
- Handoff rules: no positive research state may imply purchase authorization; forwarding preserves uncertainty.

### Golden Goose Finder
- Purpose: surfaced-opportunity review desk (operator review queue, not a top-products feed).
- Page identity: ranked queue, evidence summary, contradiction surfaces, operator actions.
- Required above-the-fold: opportunity queue with score/rank, surfaced reason, freshness, contradiction count; detail rail (why surfaced, what remains unknown, why it may fail, next actions); Research Confidence framed as evidence quality; fast handoff to SourceScout/Commerce Ops/hold-reject queues.
- Local tabs: Queue, Review, Decisions, History.
- Features: surface reason tags; contradictory-signal panel; research confidence tooltips; hold/reject/escalate; historical decision log; review-notes drawer; freshness column + cached/historical tags.

### ListingForge
- Purpose: listing-production and optimization studio — a writing room and revision workshop, not a dashboard with a health score.
- Page identity: editorial studio: drafting canvas, version control, template system, keyword coverage, health review.
- Required above-the-fold: listing queue with status + edit affordances; Editor tab with title, bullets, description, attributes, compliance/quality prompts; Save Revision + Request Health Check; revision badge/version state; Keyword Coverage (Matched/Partial/Missing); health breakdown marked sample/verified basis.
- Local tabs: Listings, Editor, Templates, Assets, Revision Log.
- Features: content editor (title, bullets, description, backend keywords); version history + revert; keyword-coverage analyzer; health check workflow; template gallery by type/category/tone; asset attachments + creative link-outs; publish readiness checklist; missing-data and compliance warnings.
- Special notes: the Editor view is the true star. Landing view may contain a queue but must not feel empty or generic.

### AdPilot
- Purpose: advertising operations workbench — campaigns, terms, placements, budgets, planning; not a performance dashboard.
- Page identity: trading-desk-like room softened into NorthstarOS's calm system.
- Required above-the-fold: Campaign Health queue with status pills and truthful rollups; Campaign Detail metrics with basis captions; Search Term Performance table; bid recommendation cards with rationale; Proposed Allocation planner with explicit BASIS column; planning-only language, no auto-apply implication.
- Local tabs: Campaigns, Campaign Detail, Search Terms, Planner, Placements, Rules.
- Features: campaign queue (health, spend, budget, ACOS/TACOS, owner/state); search-term analysis + harvesting recommendations; bid suggestion rationale; budget pacing/reallocation planner; placement insights; rule-management surface; sample/observed/assumption states by section; manual execution and approval-oriented actions only.
- Must not: imply autonomous spend changes; recommendation cards must show basis and confidence limits.

### SocialPulse
- Purpose: social content and publishing studio; scheduler strengths + AI repurposing.
- Page identity: studio room with calendar, queue board, content preview, platform presets, asset tray, right-side AI copilot.
- Required above-the-fold: campaign/theme selector; Calendar/Queue/Board switcher; draft composer preview; platform preset chips (TikTok, Instagram Reels, Stories, X Thread, Pinterest, YouTube Shorts, Email Crossover); brand voice/tone presets; AI copilot chat; primary actions (Draft Post, Generate Variants, Schedule, Send for Approval).
- Local tabs: Calendar, Queue, Composer, Asset Library, Presets, Approvals, Analytics.
- Features: monthly/weekly calendar; queue/list of drafts→approved→scheduled→published; kanban by stage; composer with platform previews; hook/format presets; repurpose-from-input (URL, product page, copy, images, UGC); copilot generation; asset library; approval flow; scheduling queue; performance rollup marked sample/cached.
- Presets: Founder voice, Product demo, Problem/solution, Before/after, Deal alert, UGC testimonial, Trend reaction, FAQ answer, Top 5 listicle, Seasonal promo, Lifestyle edit, Comparison/alternative.
- References: Hootsuite (calendar/queue/approvals), Holo (site→generated outputs).

### Creative Studio
- Purpose: campaign and asset workshop for ad creatives, social variants, brand packaging, campaign bundles.
- Page identity: visual workshop: canvases, asset trays, brief cards, export collections.
- Required above-the-fold: active brief summary; variant board/gallery; asset tray with filters; output bundle actions; campaign package panel.
- Local tabs: Briefs, Variants, Assets, Exports, Library.
- Features: brief builder; variant set management; asset organization; export packages for ads/social/listings; link-outs to SocialPulse + ListingForge; approval state + revision notes.

### Profitability Dashboard
- Purpose: decision-analysis room for unit economics, scenarios, assumptions, completeness — not a KPI wall.
- Page identity: financial notebook and modeling room: calculators, scenario matrices, explicit assumption controls.
- Required above-the-fold: product/portfolio/bundle selector; economics completeness banner; scenario cards (base, optimistic, constrained, worst case); unit economics breakdown with basis labels; assumption panel + warning stack; primary actions (Create Scenario, Export Model, Send to Commerce Ops).
- Local tabs: Overview, Scenarios, Fee Basis, Inventory Impact, Export.
- Features: margin/contribution analysis; fee basis state; shipping/prep/return assumptions; case-pack + MOQ scenarios; working-capital implications; scenario compare; export/handoff.

### Commerce Ops
- Purpose: workflow control room across sourcing, receiving, listing, approvals, task handoff.
- Page identity: clean operational control room: queues, swimlanes, blockers, owners.
- Required above-the-fold: open workflows queue; blockers panel; ownership/SLA indicators; critical next actions; cross-room linked tasks.
- Local tabs: Workflow, Tasks, Approvals, Blockers, History.
- Features: stage-based workflows; approval checkpoints; handoff tracking; role-based ownership; deadlines/aging/blockers; decision notes + audit history.

### Listing Guardian
- Purpose: monitors listing changes, policy issues, content drift.
- Page identity: watchtower and alert room.
- Required above-the-fold: high-severity alerts; listing diff feed; policy/suppression warnings; escalation actions.
- Local tabs: Alerts, Diffs, History, Escalations.
- Features: change timeline; before/after diffs; severity states; escalate to Commerce Ops or ListingForge.

### Keyword Tracker
- Purpose: visibility, rank movement, coverage, keyword-set health.
- Page identity: search-visibility lab.
- Required above-the-fold: keyword set selector; rank trend summary; coverage status block; flagged movement alerts.
- Local tabs: Sets, Trends, Coverage, Alerts.
- Features: keyword groups; rank tracking; visibility trends; coverage gaps; segmentation.

### Competitor Monitor
- Purpose: watches competing products, listings, prices, creative shifts.
- Page identity: competitor watch desk with watchlists and deltas.
- Required above-the-fold: watchlist table; latest changes panel; price/content shift feed; competitor notes drawer.
- Local tabs: Watchlist, Changes, Detail, History.
- Features: watchlists; content diffing; price/positioning deltas; cross-link to SourceScout + ListingForge.

### Master Brain
- Purpose: strategy synthesis room; cross-suite signals → operator-ready summaries, open questions, decision support.
- Page identity: strategy room: synthesis cards, open questions, linked evidence packets.
- Local tabs: Summary, Themes, Questions, Recommendations.
- Features: cross-room synthesis; linked evidence; strategy memos; uncertainty/contradiction summaries; suggested investigations.

### Memory Bank
- Purpose: knowledge vault for notes, source packets, decisions, retained context.
- Page identity: research library with packets, tags, recall tools.
- Local tabs: Notes, Packets, Decisions, Search.
- Features: research packets; saved notes/annotations; decision archive; search by entity/room/source/timeframe.

### AutothinK
- Purpose: AI-assisted operational workspace — task-and-artifact agent workspace, not a chat box.
- Page identity: conversational agent room with task plans, approvals, artifacts, tools.
- Required above-the-fold: active task thread; task plan panel; artifact/output tray; tool-use log/run transcript summary; approval-required actions stack.
- Local tabs: Workspace, Tasks, Artifacts, Runs, Approvals.
- Features: prompting; multi-step task plans; artifact generation; human approval checkpoints; linked references to Memory Bank + service rooms; clear suggestion/execution separation.

### Shared Data Layer
- Purpose: data lineage, freshness, schema shape, null-state transparency.
- Page identity: calm observability room, not a developer console.
- Local tabs: Sources, Freshness, Schemas, Snapshots, Quality.
- Features: source catalog; freshness matrix; snapshot browse; null-rate/completeness; schema + field provenance.

### Provider Adapters
- Purpose: state of controlled external integrations, run history, spend/approval controls.
- Page identity: integration console focused on governance and transparency.
- Local tabs: Adapters, Runs, Spend Controls, Logs, Approval Gates.
- Features: adapter state cards; spend caps; approval checkpoints; run history/logs; error summaries.

### Customer Workspace
- Purpose: invited-customer hub; clean, guided, useful; no internal complexity exposure.
- Page identity: subscriber home room: setup, services, documents, plan, support, account state.
- Local tabs: Home, Setup, Documents, Plan & Usage, Support, Account Status.
- Features: onboarding progress; role/plan-appropriate service links; document visibility; plan/usage transparency; support + account state.

### Beta Ops / Administration
- Purpose: internal platform administration, invites, cohorts, support, reports, lifecycle, eligibility.
- Page identity: operational admin rooms with strong role boundaries.
- Features: org + cohort management; invite workflows; eligibility review; reports/audit trail; support ops; lifecycle transitions.

## Cross-room handoff model

Every major room should support explicit handoff actions:

- SourceScout → Golden Goose Finder
- SourceScout → Commerce Ops
- Golden Goose Finder → SourceScout
- Golden Goose Finder → Commerce Ops
- ListingForge ↔ Creative Studio
- SocialPulse ↔ Creative Studio
- AdPilot ↔ Profitability Dashboard
- Commerce Ops ↔ ListingForge / SourceScout / AdPilot
- Master Brain ↔ all rooms through evidence references

## Default content rules

Each room should load with meaningful, role-appropriate content on arrival. If data is not real or unavailable, the room should still feel functional via: sample data banners; muted basis captions; partial-but-honest workflow surfaces; empty states with next actions; concept-only or backend-needed markers. Rooms must not appear broken, blank, or misleadingly complete.

## Mobile behavior

Mobile should preserve room identity: bottom navigation for main suite access; tab transforms/segmented controls for RoomTabs; card/list alternates for wide tables; sticky action areas; quick "open in full view" transitions for dense surfaces.

## Anti-patterns to forbid

- Repeating the same banner + table + dead space composition across all rooms
- Hiding the main workflow below the fold
- Using green success styling to imply purchase authorization
- Treating cached data as if it were live
- Making every room look like a dashboard homepage
- Turning AI services into vague chat screens with no work artifacts
- Letting studio rooms feel like forms instead of creative workspaces
- Letting ops rooms feel like project-management templates

## Build guidance

Implementation proceeds room by room, using SourceScout as the frozen benchmark for density, truth-state clarity, action hierarchy, and room identity. Each room is judged against: does this screen clearly belong to the same NorthstarOS suite while still feeling specifically designed for the job of this service?

The strongest outcome: the platform feels structurally familiar because it uses proven workflow patterns, and unmistakably new because each room is composed with more care, more clarity, and more service-specific intention than the products it competes with.
