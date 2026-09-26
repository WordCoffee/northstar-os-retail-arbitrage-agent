# 12 — Ledger Specification

Evidence states: STATICALLY_CONFIRMED (S) / INFERRED (I). Specification only.

## 1. Primary user job

Understand credits, usage, spend, and billing posture — with every number traceable to an append-only event.

## 2. Main workspace

| Section | Content | Source |
|---|---|---|
| Balance | current derived balance | projection over `usage_event`/ledger (NOT a mutable field) |
| This period | credits consumed, by service/provider/model | usage projection |
| Usage breakdown | per service, per provider, per model/endpoint | usage_event |
| Plan | tier, included credits, limits | subscription/plan + pricing policy |
| Local vs cloud | local (free) vs cloud (charged) split | usage_event.environment/provider |
| Overage | overage usage + rules | pricing policy |
| Invoices | per-period invoice (derived) | invoice |
| Reversals/refunds | adjustment entries | ledger reversals |
| Usage alerts | thresholds reached | notification |

## 3. Workflow

- Entry: `/ledger` (or `/ledger/usage`, `/ledger/invoices`).
- Period selector; service/provider/model filters.
- Row drill-down → underlying usage_event detail (idempotency key, provider cost, estimated cost, credits, reversal ref, provenance).
- Export usage/invoice (CSV).

## 4. States

- Empty: "No usage recorded yet" (org is on free/local) — balance shows allotment with clear label "unused".
- Loading/error/stale: standard states; stale banner when projection lag > threshold.
- Permission denied: only operator/admin see org-wide usage; customer sees own-org usage.

## 5. Resolves Phase 0 ambiguity

- **"Balance" vs "Available"** (Phase 0 finding): canonical definitions now:
  - **Balance** = total granted − consumed + adjustments (derived).
  - **Available** = balance − reserved (pending reservations).
  - When equal, UI shows one value with a footnote "no pending usage"; never two identical numbers unexplained.
- **Balance is never a mutable field** (owner decision `00` §3).

## 6. Responsive

- Desktop: metric tiles + tables. Mobile: stacked metrics, usage table collapses to cards.

## 7. Tour steps

1. Read your balance (derived).
2. Break down usage by service/provider.
3. View an invoice.
4. Set a usage alert.

## 8. Events

Emits: none primary (read-side). Consumes: `usage.event.recorded`, `credits.adjusted`, `invoice.generated`.

## 9. Downstream

- Hub credit/spend widget; Account billing; notifications for thresholds.
