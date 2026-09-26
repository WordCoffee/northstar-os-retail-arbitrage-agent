# 12 — Known Gaps (Phase 1C, 2026-09-25)

## Resolved this phase
- 1C-03 canonical economics (incl. reconciliation) — authoritative; GG decision
  controls; scanner/economics formula version.
- 1C-04 durable execution — state machine, additive migrations (apply/rollback/
  reapply/fingerprint on disposable PG 15.19), authenticated submission, atomic
  claim (FOR UPDATE SKIP LOCKED), worker, leases/heartbeats, runtime rechecks,
  Decimal usage reservation/settlement, retry/backoff, cancellation, dead-letter,
  lease recovery, concurrency matrix, persisted scheduler.
- 1C-05 keyword/SEO — canonical schema, normalization, source registry, import
  pipeline (dry-run/job-driven/rejected rows/overlap/idempotent), org isolation,
  shared read contracts, org-scoped APIs.
- 1C-06 frontend — React/Vite build served by FastAPI (/ui) with SPA fallback,
  real JWT auth in the UI, org switching, preview, Jobs/Schedules + Keywords UIs,
  collapsible pinned drawer, tours, security headers, GET-side-effect guarantees.
- LOCAL_PRODUCTION_CANDIDATE + STAGING_READY documentation reached.

## Still open (external, owner-authorized)
1. **Staging unverified** (1C-02C/D/E NOT STARTED) — requires a designated
   staging PostgreSQL, credentials via secret delivery, verified backup, and
   migration authorization (see `staging-handoff-checklist.md` F06).
2. Legacy users not bridged to foundation memberships (owner decisions B1–B5).
3. JWKS not implemented (static-key model; acceptable unless an IdP is chosen).
4. Session cleanup not scheduled (1C-04 scheduled job is a documented follow-up).
5. Dynamic browser accessibility scan executed on the local stack; a full
   axe-style scan on staging is part of the smoke plan.
6. The built UI references Google Fonts (external CDN); CSP scoped to the font
   origins; loopback otherwise makes zero network calls.
7. Full foundation suite on PostgreSQL (the 574-test suite is SQLite-oriented;
   the focused 28-test PG subset covers the durable/keyword schema + concurrency).

## 1C-05 authorization gate (2026-09-24)

- Closed: viewer no longer reaches billing/ledger, provider configuration, or
  the administrative approval queue (previously PERM_VIEW on /usage/*,
  /providers/*, /approvals).
- Closed: cross-org cancel/retry returned 403 (existence hint) — now 404.
- Open (owner-decided): provider definitions remain global infrastructure
  (org-scoped provider CONFIG/credentials is a documented follow-up); ANALYST
  role retained for backward compatibility alongside the owner/operator/viewer
  minimum.

## 1C-06 beta launch controls (2026-09-24)

- Closed: no beta documents/acceptance existed — now versioned + enforced.
- Open: single-operator incident response (no deputy); business-data retention
  UNKNOWN until reviewed per customer; provider definitions remain global.
- Documented: backup limitations and 7-year financial/audit retention mean
  deletion is NOT immediate or complete (stated, not promised otherwise).

## 1C-06 master slice private-beta readiness (2026-09-24)

- Closed: test-mode billing (redirect checkout, exactly-once webhook), tiers &
  entitlements (centralized), invite-gated access, file sets, integrated E2E.
- Open: real payment keys / live provider activation are NOT enabled (require
  explicit owner authorization); public self-serve signup remains disabled;
  provider definitions remain global; business-data retention UNKNOWN until
  reviewed per customer.

## 1C-06 subscriber rules & operations (2026-09-24)

- Closed: subscriber plans + in-app entitlements, tester lifecycle state
  machine, admin tools (notes/overrides), onboarding + support, dashboard +
  safe export, exportable file sets.
- Open (non-blocking): secure file-upload attachments NOT exposed (safe-upload
  not yet proven); no deputy for single-operator incident response; business-
  data retention UNKNOWN until reviewed per customer.
- Open (blocking, owner-authorized only): live payment keys / live providers /
  public self-serve signup / production provisioning.

## Phase 1C UI wiring & private beta experience (2026-09-24)

- Closed: private-beta operations are now usable in the browser at /ui
  (tester onboarding/plan/support, admin Beta Operations, invite signup,
  suspended account-status screen, safe CSV export).
- Non-blocking: file attachments not exposed (safe-upload not proven); legacy
  port-8000 shell remains the historical entry (canonical UI at /ui:8001); no
  incident deputy; business-data retention UNKNOWN until reviewed.
- Blocking (owner-authorized only): live payment keys / live providers /
  public self-serve signup / production provisioning.

## Local legacy-UI cutoff (2026-09-24)

- Closed: the legacy Operations Hub shell no longer appears in the local
  private-beta UI (port 8001). Signed-out lands on the beta invite entry;
  legacy routes render a tombstone.
- Non-blocking: the legacy shell remains available in `ui_mode=full` (default)
  so non-local/future deployments are unchanged.
