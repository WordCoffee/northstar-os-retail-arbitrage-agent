# Cluster A/B Visual-Polish Pass (2026-09-27)

## Scope
Operator-approved fix set from the GLM visual review. All five Cluster A/B rooms already read as distinct, service-appropriate identities; this pass is **localized composition and workflow polish only — no redesign**. Cluster C remains held for its own gate.

Rooms touched: SocialPulse, Creative Studio, Listing Guardian, Keyword Tracker, Monitoring.

## P1 — required before Cluster A/B freeze

### 1. SocialPulse — Queue board
- **Before:** sparse kanban columns, 1–2 cards each with no actions; board read as a display, not a pipeline.
- **After:** every card gained a **stage-appropriate primary action** — Draft → `Send to Approvals`, Approved → `Schedule`, Scheduled → `Mark Published`, Published → `View` (+ `Repurpose`). Each card gained a stage meta line (submission/slot/publish detail, sample-honest). Each column gained a **count footer** (`n posts in stage`).
- Files: `src/pages/internal/SocialPulse.jsx` (`STAGE_ACTION`, enriched `QUEUE`, queue render).

### 2. Listing Guardian — History
- **Before:** single `Change Timeline` card, 4 events, ~40% bare paper below — read unfinished.
- **After:** timeline events enriched with **severity-coloured dot, event type pill, affected ASIN, linked alert ID, and muted provenance tag** (CACHED / OBSERVED / HISTORICAL). Added a complementary **Watch Summary** surface (right column): events grouped **by type** (with highest-severity pill + count) and **by provenance** (muted counts), with an explicit "not verified fact" footer.
- Files: `src/pages/internal/ListingGuardian.jsx` (`HISTORY` enrichment, `HISTORY_BY_TYPE/BY_STATE`, `SEV_DOT`, history view).

### 3. Listing Guardian — Diffs
- **Before:** "Detected Changes" rendered as `.filter-pill` boxes outside `.room-toolbar`, so they inherited no pill styling and read like form fields.
- **After:** real **change-list pattern** — change-type glyph box (`T`/$/`B`), field label, **old → new inline** (mono, ellipsis), and date + ASIN + provenance tag. Pills reserved for **severity** and **state** only. Added a provenance row to the before/after viewer (`diff id · ASIN · date`).
- Files: `src/pages/internal/ListingGuardian.jsx` (`fieldGlyph`, diffs view).

### 4. Keyword Tracker — Coverage
- **Before:** single 4-row table + ~45% dead space.
- **After:** added a second card **Top Uncovered Terms** (gap term, ASIN, product, set, gap signal + count, muted provenance note) with a per-row **Open in Trends** action wired to `/keyword-tracker?view=trends`.
- Files: `src/pages/internal/KeywordTracker.jsx` (`UNCOVERED`, `useNavigate`, `verifyInTrends`, coverage view).

### 5. Keyword Tracker — Alerts
- **Before:** thin 2-row table + dead space; two overlapping cached-data notices (page-level + tab-level).
- **After:** per-row **Verify in Trends** action; new **Movement by Keyword** summary surface (keyword, ASIN, direction, severity, verify action); the two notices **consolidated into one** page-level notice that carries both the ranking-snapshot and movement-alert limitation.
- Files: `src/pages/internal/KeywordTracker.jsx` (alerts view, `DataNotice` text).

## P2 — implemented in the same pass

### 6. SocialPulse — Calendar
Trailing/out-of-month days (Oct 1–4) and leading days (Aug 31) now render as **muted, non-interactive, dashed + hatched cells** with faint adjacent-month labels; September 1 correctly placed on a Tuesday. Files: `SocialPulse.jsx` (`MONTH_CELLS` as `{ out, day/label }`).

### 7. Creative Studio — Library
Added a **collection summary strip** (MetricTiles: collections / total assets / largest collection / most recent addition) above the collections grid, plus an inventory-honesty footer. Files: `CreativeStudio.jsx` (`TOTAL_COLLECTION_ITEMS`, library view).

### 8. Creative Studio — placeholders
Variant, asset, and collection thumbnails replaced with a shared `ThumbPlaceholder`: **dashed border + diagonal hatch + type label + "no preview · sample"** caption — visibly intentional, not a failed image load. Files: `CreativeStudio.jsx` (`ThumbPlaceholder`).

### 9. Monitoring — Health
`Healthy` on the sample `UI build` / `Screenshot pipeline` checks moved from success-green to **`pill-muted`**; adverse states stay distinct (`Unreachable` → error, `Rate limited` → warn). Added a truth-state legend: **green is reserved for live probe-backed checks**. Files: `Monitoring.jsx` (`SERVICES`, health view).

### 10. Monitoring — Alerts
"Where to investigate" reworked from two lone buttons into a **routed list with per-destination alert counts** (Shared Data Layer / Provider Adapters / Commerce Ops → Open), preserving its role as a navigation aid into source-of-truth rooms. Files: `Monitoring.jsx` (`DESTINATIONS`, alerts view).

## Guardrail compliance
- Warm paper / pine / restrained ochre system preserved; no new colours introduced.
- SourceScout benchmark untouched.
- No success-green on cached, observed, sample, derived, or non-authoritative data (Monitoring health corrected; Keyword/Guardian provenance tags remain muted).
- Explicit truth-state language and provenance preserved/added.
- No implication of automatic publishing, automatic escalation, purchase authorization, or autonomous action (all actions toast the manual/uncertainty framing; escalation copy unchanged).
- No backend / provider behaviour changed.
- No banner + table + dead-space layouts reintroduced.

## Verification
- `npm run build` — **clean**, 81 modules, 0 errors (js 412.67 kB / gzip 104.97 kB; css 37.08 kB).
- `node verify-smoke.cjs` — **40 passed, 0 failed** (all Cluster A/B deep links + wired actions intact).
- `node verify-guards.cjs` — **8 passed, 0 failed**.
- Screenshots captured + render-verified (regenerated via `capture-clusterA.cjs` / `capture-clusterB.cjs`).

## Screenshot inventory (changed views)
| File | View |
|---|---|
| `48-socialpulse-calendar.png` | Calendar — out-of-month cells |
| `48b-socialpulse-queue.png` | Queue — stage actions + column footers |
| `49b-creative-variants.png` | Variants — placeholder treatment |
| `49c-creative-assets.png` | Assets — placeholder treatment |
| `49e-creative-library.png` | Library — summary strip + placeholders |
| `50b-guardian-diffs.png` | Diffs — change-list pattern + provenance |
| `50c-guardian-history.png` | History — enriched timeline + Watch Summary |
| `51c-keyword-coverage.png` | Coverage — Top Uncovered Terms |
| `51d-keyword-alerts.png` | Alerts — Verify in Trends + movement summary + single notice |
| `52-monitoring-alerts.png` | Alerts — per-destination counts |
| `52b-monitoring-health.png` | Health — muted sample states + legend |

Unchanged-but-regenerated for a consistent set: `51/51b`. No functional change.

## Remaining P2 items
- None outstanding from the approved set. Both PASS rooms (Creative Studio, Monitoring) were accepted with their polish items now implemented.

## Stop point
Cluster A/B visual-polish complete and clean. `npm run build` / smoke / guards all green. **Cluster C (Admin / Beta-Ops) held for its own gate.**
