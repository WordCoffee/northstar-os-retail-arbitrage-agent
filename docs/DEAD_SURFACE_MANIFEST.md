# Dead-Surface Manifest (non-creative) — 2026-10-04

**Purpose:** identify unrouted / stale UI surface that is not part of the shipped
bundle, prove it is unreferenced, and classify each candidate. **No removal was
performed in this pass** — deletion/quarantine is deferred to a later explicit
approval.

**Method:** static reference search across `northstar-os-ui/src` (all `.jsx`/`.js`)
and the Playwright harnesses (`*.cjs`), plus `git ls-files` tracked-status checks.
The shipped SPA entry is `src/main.jsx` → `src/App.jsx`; nothing below is imported
from that chain.

**Why these don't ship:** Vite only bundles modules reachable from `main.jsx`, so
these files are absent from `dist/` today. They are *developer/suite* confusion,
not a runtime surface. Readiness impact is therefore low; cleanup is hygiene.

---

## A. Safe delete (zero references, no dependents)

| File | Evidence |
|---|---|
| `src/data/services.js` | Only importer is `foundation/components/CommandPalette.jsx` (itself dead). Drives a palette whose routes (`/hub`, `/prospector`, `/offerchisel`, `/towncrier`, `/auctioneer`, `/thewatch`, `/rankledger`, `/rivalboard`, `/goldengoose`, `/foundation`, `/jobs`, `/keywords`, `/beta-signup`) do **not** exist in `App.jsx`. |
| `src/foundation/components/CommandPalette.jsx` | Only self-declares; the live palette is `src/components/CommandPalette.jsx` (imported by `App.jsx`). |
| `src/foundation/components/EnvBadge.jsx` | Zero references. |
| `src/foundation/components/PinnedDrawer.jsx` | Zero references. |
| `src/foundation/components/OrgSelector.jsx` | Zero references. |
| `src/foundation/components/PreviewBanner.jsx` | Zero references. |

> Note: `services.js` route drift is the legacy-UI artifact; removing it prevents
> a future accidental remount of a palette full of broken deep links.

## B. Quarantine later — dead dependency cluster (delete as a set, not piecemeal)

| File | Evidence |
|---|---|
| `src/foundation/components/StatusPrimitives.jsx` | Referenced only by the dead files below (and `RouteGuard`). |
| `src/foundation/components/RouteGuard.jsx` | Zero references; `App.jsx` uses its own `GuardedRoutes`. |
| `src/foundation/pages/BetaOps.jsx` | Zero references (live admin lives in `src/pages/admin/*`). |
| `src/foundation/pages/BetaSignup.jsx` | Zero references. |
| `src/foundation/pages/BetaTester.jsx` | Zero references. |
| `src/foundation/pages/FoundationStatus.jsx` | Zero references. |
| `src/foundation/pages/Jobs.jsx` | Zero references. |
| `src/foundation/pages/Keywords.jsx` | Zero references. |
| `src/pages/Account.jsx` | Zero references; live account surface is `src/pages/customer/AccountStatus.jsx`. |

**Cluster rule:** `StatusPrimitives.jsx` is safe to delete only *together with*
this whole set; deleting it alone would leave dangling imports.

## C. Uncertain / needs review — legacy service pages (keep for now)

These are unreferenced but map to **named master-plan services** (several are
parked or use different rooms today), so they are retained pending an owner
confirmation that the names are retired:

| File | Note |
|---|---|
| `src/pages/Prospector.jsx` | Legacy name for SourceScout. |
| `src/pages/Ledger.jsx` | Legacy name for Profitability/Ledger. |
| `src/pages/OfferChisel.jsx` | Legacy name for ListingForge. |
| `src/pages/TownCrier.jsx` | Legacy name for SocialPulse. |
| `src/pages/Auctioneer.jsx` | Legacy name for AdPilot. |
| `src/pages/TheWatch.jsx` | Parked service (needs SP-API). |
| `src/pages/RankLedger.jsx` | Parked service. |
| `src/pages/RivalBoard.jsx` | Parked service. |
| `src/pages/Hub.jsx` | Legacy hub. |
| `src/pages/GoldenGoose.jsx` | Superseded by `src/pages/internal/GoldenGoose.jsx`. |
| `src/pages/Autothink.jsx` | Superseded by `src/pages/internal/AutothinK.jsx`. |

`src/pages/NotFound.jsx` **is live** (imported by `App.jsx`) and is **not** a
candidate.

## D. Stale docs / non-UI references (uncertain)

| Item | Issue |
|---|---|
| `README.md` (root) | Documents a legacy Node pipeline (`npm run pipeline`, `search`/`normalize`/`score`) that no longer exists in root `package.json`. The root `src/` legacy pipeline directory still exists. |
| `docs/LOCAL_RUNBOOK.md` | Documents `npm --cwd northstar-os-ui run build/dev` — invalid for the installed npm (fixed in root `package.json` this pass to `npm --prefix`). |
| `docs/BUILD_STATE.md` | Correctly records the `--cwd` root-build defect as an open P1-T3 candidate (now fixed). |
| `CLOUDFLARE_DEPLOY.md` | References `npm run pipeline` in a CI snippet. |

These are documentation-truth items, not code. Fixing them touches files that are
currently dirty from another session, so they were left untouched this pass to
keep the commit clean.

---

## Recommendation
1. Approve **Section A** for immediate deletion (six files, zero risk).
2. Approve **Section B** as a single atomic deletion (cluster).
3. Resolve **Section C** by owner naming decision (retire vs revive), then delete.
4. Correct **Section D** docs in a dedicated docs-truth pass.