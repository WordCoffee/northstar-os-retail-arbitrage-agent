# Incident runbook and kill switches

## Kill-switch inventory (what to turn off, in order of blast radius)

| # | Switch | Where | Effect when off | Cost of turning it off |
| --- | --- | --- | --- | --- |
| 1 | `CLOUD_MODEL_LIVE` | `deploy/hosted.env` / container env | Cloud model calls are refused (`cloud_not_armed`); the router falls back to local or refuses honestly. | None — this is the default state. |
| 2 | `MEDIA_GEN_LIVE` | same | Image/video generation is refused; vision jobs report `not_armed`. | None — default state. |
| 3 | Provider API keys (e.g. the vision/search keys) | container env only | With no key, `provider_key_present` is false and the provider is unarmed even if a flag says otherwise. | None. |
| 4 | `NORTHSTAR_DISABLE_RATE_LIMIT` | must be `0` in any hosted env | — (leave at 0; a "1" is refused at boot in staging/production). | None. |
| 5 | Caddy (stop the container) | VM | All external access stops; the API is unreachable from outside. | Full outage — use for active abuse, not for mistakes. |
| 6 | The API container | VM | Full outage. | Full outage. |

There is no Amazon integration to switch off: the product has no Amazon
sign-in, no SP-API, no Ads API, no OAuth and no credentials by design
(`tools/test_no_amazon_linkage.py` proves the absence).

## Incident classes and first responses

### A. "The app generated / spent something it should not have"

1. Set `CLOUD_MODEL_LIVE=` and `MEDIA_GEN_LIVE=` (empty), restart the API
   container. This is instant and reversible.
2. Record what happened: the studio's job rows and the audit log (see the
   generation arming package, `docs/GENERATION_ARMING_CHECKLIST.md`) carry the
   evidence. Do not delete rows.
3. Verify the state: `GET /api/design-studio/generation-status` must show
   UNARMED with a reason.
4. Only re-arm after the cause is understood and written down.

### B. "A tenant can see another tenant's data"

1. Take the API off the proxy (stop Caddy) to freeze exposure.
2. Run the cross-tenant harness against the deployed URL
   (`tools/verify-d10-live.cjs`) to map the blast radius; it exercises
   anonymous-401 and cross-tenant negatives.
3. Preserve the database before any fix is applied (`deploy/backup.sh`).
4. Fix forward; the identity migration tool (`migrate_ds_identity.py`) exists
   for quarantining ambiguous records, not for deleting them.

### C. "The API is unhealthy"

1. `docker compose ... ps` — check which container is unhealthy.
2. `GET /readyz` through the proxy; `docker compose ... logs --tail 200 api`.
3. Common causes: Postgres not healthy (compose `depends_on` handles ordering
   on boot, not on later failures), or a bad `deploy/hosted.env` value.
4. Restart the affected container. If it persists, roll back to the previous
   `deploy/images.lock`.

### D. "Suspicious login / brute force"

1. The login throttle is ON in hosted environments (the test bypass is refused
   at boot). Confirm `NORTHSTAR_LOGIN_THROTTLE_TEST_BYPASS` is not "1".
2. If the throttle is holding, no action is required beyond monitoring.
3. If an account is compromised: rotate that account's credentials; if the
   platform-level JWT secret is suspect, rotate `NORTHSTAR_JWT_SECRET` (this
   signs out every session — expected).

### E. "A change file / upload is wrong"

- Uploads are read-only archives with checksums; change files are new files.
  The original can always be re-downloaded from Amazon and re-uploaded here.
- The round-trip validator refuses a written file whose differences are not
  exactly the approved ones; if it fails, do **not** upload the file to Amazon.
- Re-run the same flow; nothing was modified in place.

## Standing rules during any incident

- **Never** paste a secret value into a ticket, chat or log. Reference the
  secret's name and location only.
- **Never** delete data to "clean up" — quarantine (the tooling has a
  quarantine path) and record.
- **Never** auto-retry a failed live action; the circuit breaker records and
  stops by design.
- After any incident: write the timeline to `reports/`, state what is VERIFIED
  vs REPORTED vs UNKNOWN, and list the follow-up actions.
