# 10 — Navigation and Information Architecture

Evidence states: INFERRED (I) from Phase 0 `03`/`11`. Specification only.

## 1. Top-level structure

```
NorthstarOS (canonical React app)
├── Home / Operations Hub
├── Sourcing
│   ├── Prospector
│   └── Golden Goose
├── Listings
│   └── OfferChisel
├── Social
│   └── The Town Crier
├── Advertising
│   └── The Auctioneer
├── Intelligence
│   ├── AutothinK
│   ├── The Watch
│   ├── RankLedger
│   └── The Rival Board
├── Finance
│   └── Ledger
└── Account
    ├── Profile · Organization · Plan · Billing · Credits · Usage
    ├── Team & Roles
    ├── Security & Sessions
    ├── Notifications
    ├── Connections (Amazon, Ads, Social, Suppliers, AI providers)
    ├── Brand Voice
    ├── Data & Privacy
    ├── Audit Log
    ├── Modes & Customer Preview
    └── Help & Tours
```

## 2. Navigation components

- **Left sidebar** — collapsible to icon rail (48px); group headers collapsible; active route highlighted.
- **Top bar** — global search (services, ASINs, SKUs), environment badge, brain/provider status, notifications bell, account menu.
- **Command palette (Ctrl+K)** — jump to service/route/action.
- **Pinned drawer** — replaces the persistent right rail; opened on demand; pinned objects = products, opportunities, listings, alerts, notes; persists per user (DB).
- **Dock** — optional bottom quick actions (Phase 0 duplicate-nav finding): deprecated in favor of sidebar + palette to reduce duplicate navigation.

## 3. Pinning model (resolves Phase 0 persistent-rail finding)

| Aspect | Behavior |
|---|---|
| Collapsible drawer | right drawer; toggle in top bar; closes with Escape |
| User preference persistence | `pinned_layout` per user in DB (not just localStorage) |
| Pinning model | pin from any row (product/opportunity/listing/alert/note) |
| Responsive | drawer full-screen on mobile; always dismissible |
| Keyboard | Ctrl+K palette can open "Pinned"; Escape closes |
| Pin-capable objects | catalog products, opportunity assessments, listings, alerts, notes, keywords |

## 4. IA principles

- **One screen = one job.** No multi-purpose dashboards that mix production/admin info (Phase 0 finding: gates/integrations move to Account unless an operational exception raises an alert on Hub).
- Drill-down paths: list → detail → evidence → action.
- Every screen answers: What happened? Why it matters? What evidence? What next? What happens if you act?

## 5. Routing map (React)

| Route | Screen | Sub-routes |
|---|---|---|
| `/` | Hub | `/hub` alias |
| `/ledger` | Ledger | `/ledger/usage`, `/ledger/invoices` |
| `/prospector` | Prospector | `/prospector/:productId` |
| `/goldengoose` | Golden Goose | `/goldengoose/:opportunityId` |
| `/offerchisel` | OfferChisel | `/offerchisel/:productId`, `/offerchisel/:productId/versions` |
| `/towncrier` | Town Crier | `/towncrier/calendar`, `/towncrier/studio`, `/towncrier/assets` |
| `/auctioneer` | Auctioneer | `/auctioneer/campaigns/:campaignId` |
| `/autothink` | AutothinK | `/autothink/runs/:runId` |
| `/thewatch` | The Watch | `/thewatch/:productId` |
| `/rankledger` | RankLedger | `/rankledger/keywords/:keywordId` |
| `/rivalboard` | Rival Board | `/rivalboard/:competitorId` |
| `/account` | Account | sub-tabs (§1) |

## 6. What this resolves

- Phase 0 `11`: duplicate navigation (sidebar+dock+quick actions → sidebar+palette), persistent rail (→ drawer), ambiguous labels.
- Owner directive: gates/integrations move to Account; Pinned no longer consumes permanent width.
