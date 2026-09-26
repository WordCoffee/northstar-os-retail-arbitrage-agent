# 15 — Known Gaps

## Deviations from Phase 1A

| # | Phase 1A spec | Phase 1B implementation | Reason |
|---|---|---|---|
| D1 | API at `/api/v1/*` | API at **`/api/v1/foundation/*`** | Avoid collisions with existing live endpoints; keeps the change additive |
| D2 | Full auth/authz via JWT/org | **dev header shim** (`X-User-Id`, `X-Role`, `X-Env`) | Real auth wiring is Phase 1C; shim is clearly documented and dev-only |
| D3 | Postgres canonical DB | **SQLite (stdlib)** local store + Postgres DDL generated | SQLAlchemy unavailable; keeps tests offline; Postgres apply deferred |
| D4 | Redis job runner | In-process job state machine (no worker) | Runner deferred to Phase 1C; contract implemented now |
| D5 | Embedded local embeddings / memory | Not implemented | Out of P0 foundation scope |
| D6 | Frontend served by FastAPI | Shell runs on Vite dev; mount of `dist/` deferred | No deployment this phase |

## Gaps (honest)

1. **Auth shim is not production-safe** — must be replaced before any exposure (see `13` S1).
2. **No Postgres apply** — migration is prepared but unapplied.
3. **Job execution is fixture/local only** — no worker loop; no scheduling (Phase 1C).
4. **Provider adapters are fixture-only** — real adapters not wired (out of scope).
5. **Keyword provider-neutral contract** is specified in Phase 1A (`20`) but the keyword
   module is **not** part of this P0 build (it is P1-04). No paid keyword provider selected.
6. **Service pages** still render existing (non-foundation) data; they will be repointed
   to canonical APIs in Phase 1C.
7. **No variation-ambiguity heuristic** — dry-run reports 0 with an explicit note.
8. **Frontend foundation calls 404 against the currently running backend** because the
   server has not been restarted to pick up the additive mount (no deployment performed).
9. **`CLOUD_PROVIDER_PINS` (relace/fp4, deepinfra/fp8) are display/stub-only** — surfaced
   in the catalog (`model_router.py:338`), the AutothinK run response (`server.py:149`),
   and asserted in tests (`test_model_router.py:56,58`), but **never transmitted** in any
   OpenRouter request body. The single live call site (`llm_adapter.py:245`) builds its
   own body and ignores the pin. Left as inert metadata pending the canonical
   provider/economics registry work; do not assume it is active.

## Financial / economics

- **No fee, margin, ROI, ACoS, ROAS, TACoS, CPC, CTR, or CVR formula was changed** (owner
  rule). Phase 1B did not implement the canonical calculation module; that is P1-02. The
  existing Phase 1A inventory of formula duplication (R13/R14) stands and remains flagged
  for owner review.

## Source / invoice safety

- Supplier and documentation states are modeled (`SupplyState`, `DocumentationState`),
  including `invoice_type_unknown`, `documentation_under_review`, `invoice_capable`,
  `documentation_rejected`, and a reserved-but-disabled `purchase_authorized`.
- **Retail/club/marketplace receipts are never auto-classified as acceptable invoices**
  (no code path does so). Purchase authorization is **disabled** in Phase 1B.