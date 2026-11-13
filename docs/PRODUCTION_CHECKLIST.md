# Production checklist

One line per item; a box is ticked only with a command or a screenshot behind it.

## Pre-launch gate: rotation complete

- [ ] **Rotation complete** — the three committed credentials are rotated and the old ones revoked,
  the repository is private, and `state/security/keys_rotated.json` exists with no key values in it.
  Full owner steps: `reports/ty/rotation_runbook.md`. **This is a pre-launch gate only**: no
  development or staging work waits on it, and `tools/keys_rotated_watch.py` runs the retirement,
  the gitleaks gate and the promotion dry-run automatically when the marker appears.

## Model provider and billing must be the product's own (2026-11-13)

- [ ] **The product has its own model provider account, separate from the development key.**
  Today the hosted-reasoning adapter reads `OPENCODE_GO_API_KEY` — one key, used by the developer's
  machine and by anything that ships. A production product needs its own provider account so that:
  the developer's key cannot be rate-limited or revoked by customer traffic; spend is attributable
  to the product; and a leaked development key cannot bill the product.
- [ ] **The product has its own billing** (its own payment method and invoice entity), separate from
  the development subscription. Studio use becomes pay-as-you-go for free-tier users; that ledger
  must not draw on the developer's card.
- [ ] **No development credential is present in the production environment.** The launch assertion
  fails if `OPENCODE_GO_API_KEY` equals the key recorded for local development, and the app refuses
  to start with `OPENCODE_GO_ENABLED=1` and no key.
- [ ] **Spend is capped and observable**: a per-org daily budget, a refusal at the cap, and the cap
  printed in the operator surface.
- [ ] **Keys are per environment** (local / staging / production), rotated on their own schedule,
  and never in a file the repo tracks.

Why this is on the launch checklist and not a nice-to-have: the launch gate measures whether a
seller can do the job end to end. Selling a service that spends the owner's personal key is not a
product, it is a demo with a bill attached.
