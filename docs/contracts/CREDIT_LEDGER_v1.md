# Northstar OS — Credit Ledger Contract v1 (B3)

**Contract id:** `credit-ledger/v1`
**Status:** FROZEN for Phase C implementation (designed in Phase B, B3).
**Parents:** [`BFF_CONTRACT_v1.md`](BFF_CONTRACT_v1.md) ·
[`AUTH_RBAC_v1.md`](AUTH_RBAC_v1.md) · Catalog:
[`shared/subscription-plans.json`](../../shared/subscription-plans.json).
**Phase alignment:** Alpha Build Blueprint Phase B / B3 ("Schema + idempotency
keys + reservation/release flow for Creative & Compute Credits; reservation and
charge are idempotent; retries don't double-charge; reservation expiry defined;
ledger append-only; tests prove behavior").

> **No billing.** This contract meters **usage**, not money. Stripe/payments are
> out of scope (§18 Early Paid Launch Boundary; Phase 5).

---

## 1. Chargeable unit

The chargeable unit is **1 Compute Credit (CC)**. Named credit classes:

| Class | Unit | Used by |
|---|---|---|
| **Compute Credits** | 1 CC | scans, enrichment, job execution, AutoThink runs |
| **Creative Credits** | 1 CrC | media generation (ListingForge media, SocialPulse) — *reserved; not metered in alpha* |

No "unlimited"/uncapped language anywhere; every metered action has a named CC
cost (§3).

## 2. Granting — per-tier allotment

Monthly allotments are **keyed by catalog plan id** and validated against
`shared/subscription-plans.json` (the ledger never duplicates plan names/prices).
Proposed alpha allotments (**operator sign-off required**):

| Plan id | Monthly Compute Credits |
|---|---|
| `foundation` | 0 |
| `scout` | 100 |
| `mover` | 500 |
| `autothink` | 2000 |

`allotment_for_plan(plan_id)` fails closed for unknown plan ids (returns 0 and
raises on validation, see §5).

## 3. Consumption — action costs

| Action (`action` key) | CC | Notes |
|---|---|---|
| `goose.scan.mock` | 0 | offline mock/dry-run — free |
| `goose.scan.live` | 10 | **403 in alpha**; cost defined for Phase C |
| `goose.export` | 0 | export of an existing result |
| `sourcescout.enrich` | 1 | per ASIN |
| `listingforge.generate` | 2 | per listing draft |
| `autothink.run` | 5 | per agent run |

The **C8 credit meter** reads balance via a BFF endpoint
(`GET /api/v1/{service}/credits` → envelope `data:{balance, allotment, period}`);
**no cost logic runs client-side** — the client only displays the server value.

## 4. Integrity rules (fail closed)

1. **Append-only.** Entries are never mutated or deleted; balance is derived by
   summing entries. Corrections are new compensating entries.
2. **No negative balance.** `consume()` raises `InsufficientCredits` when
   `balance < amount`; it never silently drives the balance below zero.
3. **Idempotency.** Every mutation carries an `idempotency_key`; replaying the
   same key returns the original result and appends **no** second entry
   (retries never double-charge).
4. **Reservation / release.** A job may `reserve` credits (a pending hold),
   then `commit` (charge) or `release` (return). A reservation has an
   **expiry**; an expired, uncommitted reservation is releasable.
5. **Clear insufficient state.** Insufficient funds surface as a typed state
   (`InsufficientCredits` → BFF `entitlement_required`/`conflict` at the route
   layer), never as a silent failure or a fabricated success.

## 5. Ledger entry schema

```jsonc
{
  "entry_id": "cle_<32 hex>",     // opaque
  "account_id": "<account/tenant id>",
  "kind": "grant" | "reserve" | "commit" | "release" | "adjust",
  "class": "compute",             // compute | creative
  "amount": 100,                  // signed: grant/release +, commit/adjust -
  "action": "autothink.run",      // for consume kinds
  "idempotency_key": "idem_<…>",  // caller-supplied; unique per mutation
  "reservation_id": null,         // set for reserve/commit/release
  "expires_at": null,             // set for reserve
  "created_at": "2026-09-19T…Z",
  "balance_after": 95             // derived, recorded for audit
}
```

Append-only storage: in-memory for alpha; optionally a JSONL file
(one entry per line, never rewritten). A production DB is Phase 5, not now.

## 6. Minimal wiring (this phase)

`Northstar_backend/credit_ledger.py` implements `CreditLedger` with
`grant / reserve / commit / release / consume / balance / entries`, the
`InsufficientCredits` exception, idempotency by key, reservation expiry, and
append-only storage; plus `PLAN_CREDIT_ALLOTMENT` + `allotment_for_plan()`
validated against the catalog. Tests cover grant/balance, consume,
insufficient fail-closed, idempotency (no double-charge), reservation
expiry/release, append-only, and allotment validation.

---

*Designed Phase B (B3), 2026-09-19. FROZEN for Phase C. No billing/Stripe.*