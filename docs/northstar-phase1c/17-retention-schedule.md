# 17 — Retention & Deletion Schedule (1C-06 beta)

## Retention schedule

- **authentication (email, ids, memberships)**: retention lifetime of account; deletion: account deletion request; email masked; backups: may persist in backups until rotation
- **sessions (jti registry)**: retention 30 days after expiry; deletion: scheduled cleanup; backups: n/a
- **audit + acceptance records**: retention 7 years (financial/audit record); deletion: none during legal retention; backups: retained in backups per backup policy
- **business/job/keyword/import data**: retention UNKNOWN — reviewed with customer at contract; deletion: customer deletion request; backups: backups may retain until rotation
- **logs (application)**: retention 30 days rolling; deletion: rolling rotation; backups: retained in log backups until rotation

## Backup limitation

Backups are taken before migrations and on a scheduled basis. Data that was deleted at the application layer may still exist inside backups until those backups rotate or are destroyed. We do NOT promise immediate or complete deletion where backups or legally necessary financial/audit records remain (lawful-hold exceptions may apply).

## Deletion-request process

- 1. Customer submits a deletion request to the beta operator (named accountable role) — no self-serve deletion in the beta.
- 2. Operator verifies the requester's identity and organization membership (owner or named contact).
- 3. Operator records the request with request/correlation id and logs it.
- 4. Operator performs the deletion for the requested scope using the documented mechanism per data class (mask email; revoke memberships; mark acceptance/audit records per legal retention; schedule business-data deletion).
- 5. Operator confirms what was deleted and what legally/technically remains (e.g., backups, 7-year audit/acceptance records), and says so explicitly — never over-promising.
- 6. The deletion completion is audited.
