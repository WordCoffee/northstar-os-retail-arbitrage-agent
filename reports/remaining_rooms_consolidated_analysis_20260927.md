# Consolidated Room Analysis — Remaining Blueprint Rooms (2026-09-27)

Scope: SocialPulse, Creative Studio, Listing Guardian, Keyword Tracker, Monitoring, Admin/Beta-Ops.
Benchmark: SourceScout (`ProductFinder.jsx`, frozen). Spec: `docs/UI_UX_BLUEPRINT_NORTHSTAROS.md`.
Method: code read + fresh full-page screenshots (`screenshots/41`–`47`). Structural conformance on DeepSeek; identity/polish verdicts flagged for a GLM visual pass (see §7).
Status: **analysis only — no fixes implemented.**

---

## 1. Room-by-room verdicts

### SocialPulse — `internal/SocialPulse.jsx`
**Verdict: FAIL (structural).** Not a studio — a single sample table.
- Tabs present `Content Calendar / Campaigns / Performance`; blueprint requires `Calendar, Queue, Composer, Asset Library, Presets, Approvals, Analytics` → **5 tabs missing** (Queue/Composer/Asset Library/Presets/Approvals).
- Above-the-fold missing: campaign/theme selector; Calendar/Queue/Board switcher; draft composer preview; platform preset chips; brand voice/tone presets; AI copilot; primary actions (Draft Post / Generate Variants / Schedule / Send for Approval). Only `Create Post` + `Analytics` exist.
- Calendar is a 4-row **table**, not a calendar; no kanban; no composer; all 12 presets absent; no approvals flow.
- Status column plain text (`Published/Draft`) — no stage pills; `6 posts this month` uses success-green.

### Creative Studio — `internal/CreativeStudio.jsx`
**Verdict: FAIL (structural).** A file list, not a workshop.
- Tabs present `Library / Templates / Asset Health`; blueprint requires `Briefs, Variants, Assets, Exports, Library` → **no Briefs, Variants, Exports**; `Templates/Asset Health` are off-spec extras.
- Above-the-fold missing: active brief summary; variant board/gallery; asset tray with filters; output bundle actions; campaign package panel.
- No brief builder, no variant sets, no export packages, no link-outs to SocialPulse/ListingForge.
- **Convergence risk:** "Recent Assets" list ≈ SocialPulse's future Asset Library — the two identity rooms currently look like the same table.

### Listing Guardian — `internal/ListingGuardian.jsx`
**Verdict: PARTIAL (closest of the five).** Has metric tiles + feed; missing the watchtower core.
- Tabs present `Alerts / Tracked Entities / Guardian Rules`; blueprint requires `Alerts, Diffs, History, Escalations` → **Diffs, History, Escalations missing**; Tracked/Rules off-spec.
- Above-the-fold: high-severity alerts ✓; **listing diff feed ✗ (no before/after viewer)**; policy/suppression warnings ✗; escalation actions ✗ (only `New Rule`/`History`).
- Severity column plain text (`High/Medium/Low`) — no severity pills; `Resolved` success-green; `24 monitored` success-green.

### Keyword Tracker — `internal/KeywordTracker.jsx`
**Verdict: FAIL (structural).** A rankings table only.
- Tabs present `Rankings / Tracked Terms / Reports`; blueprint requires `Sets, Trends, Coverage, Alerts` → **4-way mismatch** (no set selector, no trends, no coverage, no movement alerts).
- Above-the-fold missing: keyword set selector; rank trend summary; coverage status block; flagged movement alerts.
- Change column is colored arrows (green=up) not pills; `148 terms · 6 ASINs` success-green.

### Monitoring — `internal/Monitoring.jsx`
**Verdict: OFF-SPEC / DUPLICATIVE.** No blueprint section exists for "Monitoring".
- Overlaps **Shared Data Layer** (§ line 207, sources/freshness/quality) and **Provider Adapters** (§ line 213, runs/spend/logs). Freshness-by-source duplicates Shared Data Layer.
- Truth-color violation: `Cached` and `Observed` provenance rendered as **success-green** pills (blueprint: provenance "never success-colored").
- Tabs `Alerts / Health / Sync` are reasonable as an observability room but scope is undefined.
- Severity column plain text.

### Admin / Beta-Ops
**Verdict: PARTIAL, with one concrete layout bug.**
- **Beta Ops (`admin/Overview.jsx`)**: metric tiles + error banner + activity/readiness cards + cohorts + support — reasonably full; statuses plain text (`Error/Warn/Ok`); no local tabs (routes via SuiteRail — acceptable, blueprint lists no Admin tabs); no sample-data truth notice.
- **Internal Admin (`internal/Admin.jsx`)**: **layout bug** — System Status rows render `label`+pill with no spacing (`Catalog IndexHealthy`) and statuses use `pill-ok` **without the base `pill` class**, so they render unstyled. No notice/truth labels; "Production"/"Live Calls Disabled" read as fact. This is really a health surface (belongs with Monitoring/Provider Adapters).
- `OrgsList`/`OrgDetail`/`Cohorts`/`SupportOps`/`ReportsExports`/`AuditNotes`/`InviteCreate`/`InviteDetail`/`LifecycleModal`/`EligibilityChecklist`: functional but plain; several use `pill-ok` without base `pill`; `LifecycleModal` uses a bare `alert-error` class; no truth labeling.
- **Role-clean ✓:** SuiteRail shows `PLATFORM_ADMIN`, guard redirects non-admins (verified in guards 8/8).

---

## 2. Recurring system issues (code-level, high confidence)
1. **Tab labels don't match blueprint** in all 5 internal rooms.
2. **No above-the-fold working surface** (selector/switcher/board/composer) in all 5.
3. **Plain-text status/severity columns** not pillized: Guardian (Alerts severity; Tracked status), Monitoring (severity), Keyword (change). SocialPulse statuses.
4. **Success-green on non-authoritative states:** Keyword `148 terms`, Guardian `24 monitored`, Monitoring `Cached/Observed` provenance, SocialPulse `6 posts`.
5. **Truth labeling gaps:** no `DataNotice` on Beta-Ops/Admin/Orgs/Cohorts; "Production"/"Live Calls Disabled" unlabeled.
6. **Base-class defects:** several admin files use `pill-ok` without `pill`.

## 3. Cross-room repetition issues
1. **Dominant forbidden composition "banner + table + dead space"** in SocialPulse, Creative Studio, Keyword Tracker, Monitoring (4 rooms). Guardian partially escapes via metric tiles.
2. **Everything is a flat table** — no calendar grid, kanban, gallery, diff viewer, trend chart, or coverage block anywhere → no room reads as studio/watchtower/lab.
3. **Identity collision:** SocialPulse Library ↔ Creative Studio Library/Assets; Monitoring ↔ Shared Data Layer ↔ Provider Adapters.
4. **Interchangeable feel:** SocialPulse / Creative Studio / Keyword Tracker / Monitoring landings are near-identical in composition (title → notice → tabs → one table → empty).

## 4. Room-specific opportunities
- **SocialPulse:** real month calendar grid + stage kanban + composer with platform previews + preset chips (12) + voice presets + AI copilot rail + approvals flow + schedule. (Borrow Hootsuite calendar/approvals; Holo for URL→outputs repurpose.)
- **Creative Studio:** brief cards + **visual variant gallery** + asset tray with filters + export bundle panel + SocialPulse/ListingForge link-outs. Must diverge from SocialPulse: studio = canvases/variants/bundles; SocialPulse = calendar/queue/publishing.
- **Listing Guardian:** **before/after diff viewer** + policy/suppression warnings + escalation actions (→ Commerce Ops / ListingForge) + change timeline.
- **Keyword Tracker:** set selector + trend summary (sparkline) + coverage block (covered/gap) + movement alerts.
- **Monitoring:** define scope as observability aggregator that deep-links to Shared Data Layer + Provider Adapters; remove duplicated freshness surface.
- **Admin:** fix System Status layout + truth labels + pillize; consider moving system-health into Monitoring.

---

## 5. Prioritized fixes by cluster (code-ready)

### Cluster A — Identity rooms (SocialPulse + Creative Studio) *highest risk / highest value*
- **A1 SocialPulse tabs** → `Calendar, Queue, Composer, Asset Library, Presets, Approvals, Analytics`.
- **A2 SocialPulse above-the-fold**: campaign selector strip + Calendar/Queue/Board switcher + draft composer preview + preset chips (TikTok/IG Reels/Stories/X Thread/Pinterest/YouTube Shorts/Email) + voice/tone presets + AI copilot rail.
- **A3 SocialPulse actions** → `Draft Post, Generate Variants, Schedule, Send for Approval` (no auto-publish language).
- **A4 SocialPulse Calendar** → real month/week grid (not table); Queue → kanban drafts→approved→scheduled→published; Presets → 12 blueprint presets; Approvals → flow; Analytics → sample/cached rollup.
- **A5 SocialPulse truth** → stage pills; green count pills → muted.
- **A6 Creative Studio tabs** → `Briefs, Variants, Assets, Exports, Library`.
- **A7 Creative Studio above-the-fold**: active brief card + **variant gallery grid** + filtered asset tray + export bundle panel.
- **A8 Creative Studio features** → brief builder, variant sets, export packages, SocialPulse + ListingForge link-outs, approval state + revision notes.
- **A9 Divergence guard** → SocialPulse owns calendar/queue/publishing; Creative Studio owns briefs/variants/bundles (document distinction, avoid shared "assets" table look).

### Cluster B — Watchtower rooms (Listing Guardian + Keyword Tracker + Monitoring)
- **B1 Guardian tabs** → `Alerts, Diffs, History, Escalations`.
- **B2 Guardian Diffs** → before/after content-diff viewer; **Escalations** → escalate → Commerce Ops / ListingForge actions; **History** → change timeline.
- **B3 Guardian above-the-fold** → high-severity alerts + diff feed + policy/suppression warnings + escalation actions.
- **B4 Guardian truth** → severity pills; `Resolved`/`24 monitored` green → muted.
- **B5 Keyword tabs** → `Sets, Trends, Coverage, Alerts`.
- **B6 Keyword above-the-fold** → set selector + rank-trend summary (sparkline) + coverage block (covered/gap) + movement alerts.
- **B7 Keyword truth** → change arrows → movement pills; green count → muted; keep CACHED-snapshot provenance (already correct wording).
- **B8 Monitoring scope** → reposition as observability aggregator; **remove freshness duplication**, deep-link Shared Data Layer + Provider Adapters.
- **B9 Monitoring truth** → `Cached/Observed` green → muted/dashed provenance; severity pills; service-health green only for genuinely healthy internal checks, labeled.
- **B10 distinct-room guard** → Guardian = listing watchtower (diffs/escalations); Keyword = search-visibility lab (trends/coverage); Monitoring = system observability (health/sync). Each must have a different above-the-fold shape.

### Cluster C — Admin rooms (Admin + Beta-Ops)
- **C1 Fix `internal/Admin.jsx` System Status layout** (label/pill flex spacing; add base `pill` class) — bug.
- **C2 Admin truth labels**: `DataNotice` (internal), change "Production"/"Live Calls Disabled" to labeled basis.
- **C3 Admin scope**: move system-health signal toward Monitoring/Provider Adapters; keep configuration here.
- **C4 Beta Ops** → pillize statuses (Error/Warn/Ok), add `DataNotice` sample, replace flat error banner with exception-stack rows (consistent with Command Center), consider RoomTabs for consistency (`Overview, Organizations, Invites, Cohorts, Support, Reports, Audit`).
- **C5 Admin sub-pages**: add base `pill` class where missing (`pill-ok`), replace bare `alert-error` in LifecycleModal, add sample/truth notices.

---

## 6. Recommended implementation order
1. **Cluster A** (SocialPulse + Creative Studio) — identity-defining; do first while context is freshest.
2. **Cluster B** (Listing Guardian + Keyword Tracker + Monitoring) — watchtower consistency; second.
3. **Cluster C** (Admin + Beta-Ops) — fix bug + trust polish; last.

Each cluster: implement → rebuild → smoke/guards → fresh screenshots → commit → state update.

## 7. Visual-review step (routing note)
Per the model-routing rule, the **subjective verdicts** (does SocialPulse feel like a studio? does Creative Studio read as a workshop? do the three watchtowers look distinct/premium?) depend on pixels and should be confirmed in a **GLM 5.3 Flash visual-review pass** before/with Cluster A approval. Attach: `41`, `41b`, `42`, `42b`, `43`, `44`, `45`, `46`, `47`. Structural findings above are code-grounded and do not require GLM.

## 8. Truth-label audit summary
- Violations to fix: green provenance (Monitoring Cached/Observed), green non-authoritative counts (Keyword, Guardian, SocialPulse), unlabeled admin facts (Admin, Beta-Ops).
- Correct already: Keyword CACHED-snapshot notice wording; SocialPulse engagement-not-verified notice; Guardian sample notice; Guardian rules not-enforced notice.
