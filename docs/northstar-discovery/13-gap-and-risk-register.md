# 13 — Gap and Risk Register

Evidence states: STATICALLY_CONFIRMED (S) / RUNTIME_CONFIRMED (R) / INFERRED (I) / UNKNOWN (K).

## Severity key

Critical (blocks launch / financial or account-safety risk), High (major capability or control gap), Medium, Low.

## Risk register (ranked)

| ID | Risk | Severity | Probability | Area | Blast radius | Detectability | Evidence | Mitigation | Owner decision |
|---|---|---|---|---|---|---|---|---|---|
| R1 | No canonical product identity; 4 ASIN stores diverge | Critical | High | Data integrity | Whole product | Low (no reconciliation job) | `08` | Phase-1 canonical identity + reconciliation dry-run | Yes |
| R2 | Keyword/SEO + campaign intelligence dormant (schema only) | High | High | Product capability | AdPilot/OfferChisel/RankLedger useless | Low | `08` | Wire importers/consumers in Phase 1 | Yes |
| R3 | No scheduler/capture loop → Watch/Rank/Rival track nothing | High | High | Reliability | Monitoring services non-functional | High | `04`, `02` | Introduce scheduler + snapshot job | Yes |
| R4 | Credits display-only; ledger never debited; balance==allotment | High | High | Financial | Billing/plans | Medium (comment exists) | `04`, `07`, main.py:1717 | Wire meter→ledger; define conversion | Yes |
| R5 | Golden Goose live route not two-gated (only gate 1) | High | Medium | Control | Unbudgeted live scan | Low | `04` (live_scan_gate not enforced) | Enforce both gates on `/scan` | No |
| R6 | React SPA untested and not served by FastAPI | High | High | Quality | Product surface | Low | `10` | Add test framework; mount dist via FastAPI or decide surface | Yes |
| R7 | `adapters/` + `importers/` orphaned (SP-API, Ads API unwired) | High | Medium | Maintainability / capability | Ads/listings/inventory | Medium | `06` | Decide adopt-or-remove in Phase 1 | Yes |
| R8 | Unwrangle account blocked (403, 2026-09-13); single-provider dependency risk | Medium | Medium | Reliability | Enrichment | Medium | `06` (HISTORICALLY_FAILED / CURRENTLY_UNVERIFIED) | Keep fallback chain; re-check under approved envelope | No |
| R9 | "live" badges + 0.00 costs on cache-first pages misrepresent certainty | High | High | Data integrity / UX | Trust in product | Medium (visible) | `05` | Provenance labels surfaced; null-not-zero | No |
| R10 | Anonymous demo fallback means open API by default | Medium | Medium | Security | Data exposure | Low | `12` (auth_deps.py:39-48) | Private-alpha gate / auth required in production | Yes |
| R11 | JWT secret ephemeral fallback (restart invalidates sessions) | Medium | Low | Security | Auth stability | Medium | `12` | Persist NORTHSTAR_JWT_SECRET in prod | No |
| R12 | Rate limiter in-memory (not multi-worker safe) | Medium | Medium | Reliability | Rate control | Low | `12` | Redis-backed in prod (docker has redis) | No |
| R13 | Three ACoS formula implementations | Medium | High | Financial correctness | Auctioneer/OfferChisel | Low | `05` | Single shared formula module | Yes |
| R14 | Two margin definitions both labeled "margin" | Medium | High | Data integrity | Prospector | Low | `05` | Canonicalize definition | Yes |
| R15 | No mode architecture (sandbox/prod/operator/customer-view/impersonation) | High | High | Security / compliance | All tenants | Low | `12` | Phase-1 foundation | Yes |
| R16 | Hardcoded test credentials in `tools/test_chrome.py` + browser_agent | Medium | Medium | Security (hygiene) | Repo leak | High | `12` | Remove literals; use env | No |
| R17 | DataForSEO import-time credential capture (OPEN issue) | Medium | Medium | Security | Logs/diffs | Medium | `12`, 00_STATE:161-166 | Lazy config reads | No |
| R18 | `test_scavio.py` latent live-call foot-gun | Medium | Low | Provider cost | Cost | Medium | `10` | Gate/remove live `__main__` | No |
| R19 | GG + scanner read different product universes (no shared feed) | High | High | Data integrity | Golden Goose↔Prospector | Low | `08` | Shared product record feeds both | Yes |
| R20 | Four frontend surfaces; no single product surface | High | High | UX / maintainability | Everything | Low | `03`, `11` | Surface decision (owner) | Yes |
| R21 | No unified audit UI; CRUD not fully audited | Medium | Medium | Compliance | Accountability | Low | `12` | Audit middleware + UI | Yes |
| R22 | Migrations not applied; schema described 4 ways | Medium | Medium | Maintainability | Data layer | Low | `07` | Consolidate schema; apply to staging only | Yes |

**Totals: 2 Critical (R1, R19-notable) — counting strictly by severity: Critical = R1, R19 (product-universe divergence) = 2. High = R2, R3, R4, R5, R6, R7, R9, R15, R20 = 9. Medium = 11. Low = 0 flagged explicitly.**

## Explicit flags

- **Exposed secrets:** none found in frontend; test literals in tools (R16); import-time capture risk (R17).
- **Client-side credentials:** none in frontend JS (S).
- **Unbounded provider calls:** no — all live gates default off; bounded CLIs exist (S).
- **GET routes that incur charges:** none found — GET routes are cache-first; live writes require explicit POST + gate (S). `POST /api/kirkland/refresh` is the only live-trigger route and it is gated.
- **Automatic production writes:** none (no write path auto-triggered; GG/refresh gated).
- **Fabricated/mislabeled data:** R9 (0.00 costs, "live" badges).
- **Incorrect financial formulas:** R13/R14 (duplicated/ambiguous).
- **Missing authorization:** R10 (demo fallback), partial route protection.
- **Missing audit logs:** R21.
- **Missing rollback:** schema/db rollback via ROLLBACK_DRILL exists for code; no data rollback for caches.
- **Dead controls:** R5 (gate 2 unenforced), R7 (orphaned adapters).
- **Duplicate sources of truth:** R1/R2/R13/R14/R22.
- **Unbounded background jobs:** none exist (no scheduler).
- **Provider-failure loops:** no auto-retry loops found (circuit breaker patterns present).
- **Supplier/invoice misclassification:** `invoice_verified_status` defaults unverified; retail-receipt≠invoice rule present in docs (S).
- **Single-provider dependency:** R8 (Unwrangle blocked), mitigated by fallback chains.

## Gap register (positive, build-side)

1. Foundation: identity/organizations/roles/modes, canonical data model, event+audit, provider registry, provenance, credits/billing, error/observability, design system, tour/help — see `14`.
2. Intelligence: master-brain orchestration, product graph, supplier graph, keyword graph, brand voice, recommendations, monitoring/alerting.
3. Services: per-service backend→UI wiring for the 11 workspaces.
4. Release: testing, migration, sandbox validation, controlled live reads/writes, rollout, rollback.

## Counting methods

- Severity/probability: engineering judgment over source evidence (I). No automated scoring.
