# Northstar OS — Local Admin SOP & Integrity Checklist

**Branch:** `build/master-plan` — Item 4 (local completion sprint: admin
workflows / fixtures / exports / audit / tenant-isolation / backup-restore /
checklist / SOP).

**Mandate:** This is a **LOCAL-ONLY** surface. No real invitations, no tester
contact, no external accounts, no email/SMS, no production/cloud changes, no
live lifecycle operations. Every admin action surface in the SPA is a
sample-mode stub with destructive controls **disabled**; the backend admin
routes are guarded and append-only. This SOP documents how to operate + verify
that surface locally.

---

## 1. Scope & posture

| Area | Local state |
|---|---|
| `/beta-ops/*` admin UI | Sample-only stubs. Every destructive control is `disabled`. `platform_admin` only. |
| `/admin` internal | Sample system-status surface, `platform_admin` only. |
| Backend admin routes | Present, guarded, append-only (audit trail). See §4. |
| Tenant isolation | Org-scoped reads/writes enforced and tested (`test_auth_org_scope.py`, `test_authorization_matrix.py`). |
| Backup / restore | Local SQLite drill **implemented** and green (`test_backup_restore_drill.py`, 2/0). Postgres scripts are DEPLOY-F5 (not run locally). |
| Invitations / exports / lifecycle | **Not executed.** Real actions require a fresh explicit owner approval. |

---

## 2. Admin workflow inventory (UI, `/beta-ops/*`)

| Route | Surface | Local status |
|---|---|---|
| `/beta-ops` | Overview: exceptions queue, activity feed | Sample; reads only |
| `/beta-ops/orgs` | Organization list + detail | Sample; reads only |
| `/beta-ops/invites` | Create Invitation + Invite detail | **Disabled** (Send/Reissue/Revoke) |
| `/beta-ops/cohorts` | Cohort groupings | Sample; reads only |
| `/beta-ops/support` | Support operations queue | Sample; reads only |
| `/beta-ops/reports` | Reports & Exports | **Download disabled** (sample mode) |
| `/beta-ops/audit` | Audit trail & internal notes | Sample; reads only |
| `/beta-ops/lifecycle` | Lifecycle action confirm | **Disabled** |
| `/beta-ops/eligibility` | Eligibility checklist | **Disabled** (Verify) |

Verification harness: `northstar-os-ui/verify-admin.cjs` (**34/0**).

---

## 3. Backend admin surface (verified by tests)

Run from repo root:

```powershell
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
python -m pytest Northstar_backend/foundation/tests/test_private_beta.py `
  Northstar_backend/foundation/tests/test_subscriber_operations.py `
  Northstar_backend/foundation/tests/test_auth_org_scope.py `
  Northstar_backend/foundation/tests/test_authorization_matrix.py `
  Northstar_backend/foundation/tests/test_audit.py `
  Northstar_backend/foundation/tests/test_migrations_check.py `
  Northstar_backend/foundation/tests/test_e2e_matrix.py -q
```

Logged result this sprint: **92 passed**. Flows covered: beta launch, org
lifecycle (plan/status/decision), support triage, dashboard list/detail/export,
invites (issue/rescind decision — local), audit trail (append-only), tenant
isolation, migration ledger drift-refusal, and the end-to-end matrix.

---

## 4. Tenant isolation (evidence)

- Organization-scoped reads/writes are enforced by the foundation authorization
  layer and covered by `test_auth_org_scope.py`, `test_authorization_matrix.py`,
  and `test_authorization_postgres.py`.
- Cross-tenant access is denied at the authorization boundary (not at the UI).
- Golden Goose queue/lookup is org-scoped; the UI harness denies cross-tenant
  deep links (`verify-golden-goose.cjs`, 16/0).
- **Rule:** never weaken any ORG-scope guard to make a sample UI reach further.

---

## 5. Backup / restore drill (LOCAL, evidence-backed)

Local DB is SQLite (`Northstar_backend/data/northstar.db`). The backup/restore
drill uses the SQLite online backup API and verifies:

1. Backup is non-empty and passes `PRAGMA integrity_check`.
2. Restore targets a **disposable** DB name (guard mirrors `deploy/restore.sh` —
   name must contain `drill` or `restore`).
3. Restored DB passes integrity check and **row counts match the source across
   tenants** (parity, not just "no error").

Run:

```powershell
python -m pytest Northstar_backend/foundation/tests/test_backup_restore_drill.py -q
```

Log: **2/0 passed**. This drill **never touches the live DB** — it seeds and
restores only throwaway files under a temp dir.

**Manual SQLite backup (safe, documented):**

```powershell
cd "C:\Users\T2Hol\Desktop\Northstar OS Retail Arbitrage Agent"
venv-phase1c02\Scripts\python -c "import sqlite3; c=sqlite3.connect('Northstar_backend/data/northstar.db'); c.backup(sqlite3.connect('backups/northstar.db.bak')); c.close()"
```

**Mandatory guard for any real restore:** only ever restore into a database
whose name is clearly disposable (`*drill*` / `*restore*`). Never run the
Postgres `deploy/restore.sh` over the live database, and never execute it
without an approved DEPLOY-F5 destination.

---

## 6. Admin integrity checklist (run before any real tester/cohort)

- [ ] `http://127.0.0.1:8101/ui/beta-ops` renders for `platform_admin` and is
      **unreachable** for non-admin roles.
- [ ] All destructive admin controls are `disabled` (no Send/Reissue/Revoke,
      no lifecycle action, no eligibility apply, no export download).
- [ ] Internal DataNotices are present on every admin page (sample/internal).
- [ ] Backend admin/tls/tenant/audit suite green: **92/0**.
- [ ] Backup/restore drill green: **2/0**.
- [ ] Cross-tenant Golden Goose denied: **16/0**.
- [ ] Full backend suite green and `npm run build` = **0 errors** (see §7).

**Owner-decision blockers (not implemented locally):**
| Card | Blocker |
|---|---|
| OA-2 / DEPLOY-F3 | Oracle console frozen; no production/cloud changes |
| OA-7 | Third-party customer/export/redistribution/AI use — written permission/counsel |
| DEPLOY-F5 | Postgres backup destination + provider CLI not approved |
| Real invitations | No tester/external contacts, no email/SMS |
| Monetization | Stripe billing + Postgres parked pre-first-PAID-cohort |

---

## 7. Full local verification of this Item

```powershell
# backend full suite (from repo root)
python -m pytest -q
# UI acceptance + admin + golden-goose harnesses
node northstar-os-ui/verify-acceptance.cjs
node northstar-os-ui/verify-admin.cjs
node northstar-os-ui/verify-golden-goose.cjs
# UI production build (0 errors required)
cd northstar-os-ui; npm run build
```

Record results + any failure in `docs/ASSUMPTIONS_LOG.md` and
`docs/BUILD_STATE.md` before proceeding.
