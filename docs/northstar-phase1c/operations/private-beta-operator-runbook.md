# Private Beta Operator Runbook (2026-09-25)

1. **Approve an org**: initialize lifecycle (invited) -> grant (onboarding).
2. **Issue an invite**: POST /invites (owner role for billing-capable testers).
3. **Onboarding**: tester accepts legal docs + completes onboarding -> move org
   to ACTIVE.
4. **Plan assignment**: POST /admin/orgs/{id}/plan (cohort).
5. **Entitlement visibility**: GET /plan-usage (owner full, operator usage,
   viewer restricted).
6. **Support**: testers submit tickets; operator triages (internal note +
   tester-visible note); never expose internal notes.
7. **Temporary override**: POST /admin/orgs/{id}/override with reason/expiry.
8. **Suspension**: POST /admin/orgs/{id}/suspend blocks the next request.
9. **Downgrade/cancel/archive**: lifecycle transitions; cancel is permanent.
10. **Dashboard + export**: GET /admin/dashboard (+ /export) — safe field set.
