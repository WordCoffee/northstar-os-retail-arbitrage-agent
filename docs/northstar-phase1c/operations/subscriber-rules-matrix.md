# Subscriber Rules Matrix (Private Beta, 2026-09-25)

| Tier | max_jobs_per_month | export_enabled | advanced_reports | seat_limit | support_level | override_allowed |
|---|---|---|---|---|---|---|
| free | 1000 | no | no | 10 | none | no |
| trial | 5 | yes | no | 3 | email | yes |
| pro | 5000 | yes | yes | 25 | priority | yes |
| team | 50000 | yes | yes | 100 | priority | yes |

- Default tier: free (explicit, enforced). Unknown -> free (fail closed).
- Downgrade/cancel/non-payment revokes gated features on the NEXT entitlement
  check. Over-tier actions return a non-leaky `entitlement_denied`.
- Plan/cohort source of truth: `foundation/billing/tiers.py` (single source).
