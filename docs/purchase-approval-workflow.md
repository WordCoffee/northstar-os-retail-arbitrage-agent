# Purchase Approval Workflow

The approval queue is a **durable, auditable human decision record** — it never
buys anything and never interacts with any marketplace. No cart, checkout,
listing, message, Seller Central change, or other external action exists in this
workflow.

```
This is a decision record only. No purchase, checkout, cart action,
marketplace action, or external communication has occurred.
```

## 1. Commands

```bash
# Create an approval REQUEST for a candidate (decision record only)
python -m costco_non_kirkland.cli approval-request --candidate-id <id>

# GRANT (only after human review; decision record only)
python -m costco_non_kirkland.cli approval-grant \
    --candidate-id <id> --quantity <n> --expires-at <ISO8601> --approved-by "<operator>"

# Revoke
python -m costco_non_kirkland.cli approval-revoke --approval-id <id> --reason "<reason>"

# List
python -m costco_non_kirkland.cli approval-list
```

Every command prints `Network calls made: 0`.

## 2. Grant eligibility (fail closed)

`approval-grant` fails if the candidate is:

- **stale** (source price or provider snapshot older than configured freshness),
- **blocked**,
- **incomplete** (economics not `complete`),
- **needs enrichment**,
- **manual review**,
- or **lacks exact identity** (must be `exact_match_verified` or
  `exact_match_provider_reported`).

## 3. Immutable snapshot

At grant time, the approval **snapshots** economics and source price
(economics_snapshot, market_snapshot, source_price, source_price_observed_at,
quantity, expiry). This snapshot is stored and never changed.

## 4. Expiry and invalidation

- **Automatic expiry**: `approval-list`/`validate` marks overdue granted
  approvals as `expired` (`expire_overdue`).
- **Invalidation** occurs when any of these change:
  - source price changed,
  - source product changed,
  - ASIN mismatch,
  - provider snapshot stale.

`validate_approval_still_valid()` performs the check and marks the approval
`invalidated` with a reason.

## 5. States

`requested` → `granted` → `expired` | `revoked` | `invalidated`

## 6. Important

- No scorer, importer, enrichment workflow, or CLI can produce
  `purchase_authorized` without this explicit separate approval record.
- A granted approval is a decision record authorizing a *planned* buy; it does
  **not** place an order. No external action is performed.
- Approval is time-limited and becomes invalid if evidence changes.