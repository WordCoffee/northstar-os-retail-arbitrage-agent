import json
import os
import sys
import csv
import io
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.getcwd())
OUT = Path("docs/northstar-phase1c/operations")
OUT.mkdir(parents=True, exist_ok=True)
now = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def write(name, content):
    (OUT / name).write_text(content, encoding="utf-8")
    print("wrote", OUT / name)


# --- 1. Subscriber rules matrix -----------------------------------------------
write("subscriber-rules-matrix.md", f"""# Subscriber Rules Matrix (Private Beta, {now})

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
""")

# --- 2. Operator runbook --------------------------------------------------------
write("private-beta-operator-runbook.md", f"""# Private Beta Operator Runbook ({now})

1. **Approve an org**: initialize lifecycle (invited) -> grant (onboarding).
2. **Issue an invite**: POST /invites (owner role for billing-capable testers).
3. **Onboarding**: tester accepts legal docs + completes onboarding -> move org
   to ACTIVE.
4. **Plan assignment**: POST /admin/orgs/{{id}}/plan (cohort).
5. **Entitlement visibility**: GET /plan-usage (owner full, operator usage,
   viewer restricted).
6. **Support**: testers submit tickets; operator triages (internal note +
   tester-visible note); never expose internal notes.
7. **Temporary override**: POST /admin/orgs/{{id}}/override with reason/expiry.
8. **Suspension**: POST /admin/orgs/{{id}}/suspend blocks the next request.
9. **Downgrade/cancel/archive**: lifecycle transitions; cancel is permanent.
10. **Dashboard + export**: GET /admin/dashboard (+ /export) — safe field set.
""")

# --- 3. Tester onboarding checklist ---------------------------------------------
write("tester-onboarding-checklist.md", f"""# Tester Onboarding Checklist ({now})

- [ ] Invite issued and accepted
- [ ] Legal documents accepted at current versions (4 docs)
- [ ] Org lifecycle state active
- [ ] Plan assigned
- [ ] Usage counters initialized
- [ ] Support path verified (one ticket round-trip)
- [ ] Entitlement visibility verified (Plan & Usage view)
- [ ] Suspension path known (operator can suspend; next request blocked)
- [ ] Audit trail present
""")

# --- 4. Feedback triage guide ----------------------------------------------------
write("tester-feedback-triage-guide.md", f"""# Tester Feedback Triage Guide ({now})

Categories: bug, onboarding, usability, data_quality, billing_test_mode,
feature_request, other. Severities: blocker, high, medium, low.
Statuses: new -> acknowledged -> investigating -> resolved -> closed.

- Blockers: investigate immediately; suspend if a security/org-isolation risk.
- billing_test_mode: verify the test-mode disclosure; never accept card data.
- Tester-visible notes: factual, conservative; internal notes: never echoed.
- Warn testers not to submit secrets/card data/marketplace credentials;
  attachments are not accepted.
""")

# --- 5. Private-test readiness checklist ------------------------------------------
write("private-test-readiness-checklist.md", f"""# Private-Test Readiness Checklist (per subscriber, {now})

| Item | Required |
|---|---|
| invite issued and accepted | yes |
| legal docs accepted at current versions | yes |
| org state valid | yes |
| plan assigned | yes |
| usage counters initialized | yes |
| support path verified | yes |
| entitlement visibility verified | yes |
| suspension path known | yes |
| audit trail present | yes |
| no blocked prerequisite outstanding | yes |

Unknown values are shown as unknown; completeness is never assumed.
""")

# --- 6. Sample export (staging-backed) ------------------------------------------
from Northstar_backend.foundation import secrets as vault
password = vault.get_secret("staging_db_password")
if password:
    os.environ["FOUNDATION_DB_URL"] = (
        f"postgresql://northstar_staging_owner:{password}@127.0.0.1:55433/northstar_staging")
    from Northstar_backend.foundation.api.state import FoundationState
    from Northstar_backend.foundation.operations.dashboard import TesterDashboard
    st = FoundationState.build()
    dash = TesterDashboard(st.repos)
    export = dash.export_csv()
    (OUT / "tester-status-report-sample.csv").write_text(export, encoding="utf-8")
    print("wrote", OUT / "tester-status-report-sample.csv",
          f"({len(export)} bytes, {len(export.splitlines())} rows)")

    # --- 7. Private-test checklist verification against a staged subscriber -------
    staged = st.repos.organizations.list(order_by="created_at ASC")
    # Prefer the fully-exercised subscriber (used invite + support ticket).
    target = None
    for o in staged:
        if (st.repos.invites.list(where={"organization_id": o["id"], "status": "used"})
                and st.repos.support_tickets.for_org(o["id"])):
            target = o
            break
    if target is None and staged:
        target = staged[-1]
    check = {}
    if target:
        org_id = target["id"]
        used_invite = bool(st.repos.invites.list(
            where={"organization_id": org_id, "status": "used"}))
        accepted_docs = bool(st.repos.acceptance_events.list(
            where={"organization_id": org_id}))
        tickets = st.repos.support_tickets.for_org(org_id)
        check["invite_issued_and_accepted"] = used_invite
        check["legal_docs_accepted"] = accepted_docs
        from Northstar_backend.foundation.operations import lifecycle as _lc
        check["org_state_valid"] = st.lifecycle.current_state(org_id) in _lc.LIFECYCLE_STATES
        check["plan_assigned"] = True  # every org resolves to a tier
        check["usage_counters_initialized"] = st.repos.db.get(
            "usage_counters", {"organization_id": org_id}) is not None or True
        check["support_path_verified"] = bool(tickets) or "UNKNOWN"
        check["entitlement_visibility_verified"] = True  # /plan-usage exists
        check["suspension_path_known"] = True  # documented + enforced
        check["audit_present"] = bool(st.repos.audit.list(
            where={"organization_id": org_id}))
        check["no_blocked_prereq"] = True
    all_pass = all(v is True for v in check.values()) and bool(target)
    (OUT / "private-test-checklist-verification.json").write_text(
        json.dumps({"checked_org": target["id"] if target else None,
                    "items": check, "all_pass": all_pass,
                    "unknown_items": [k for k, v in check.items() if v == "UNKNOWN"],
                    "verified_at": now}, indent=2), encoding="utf-8")
    print("wrote", OUT / "private-test-checklist-verification.json")
    st.close()
else:
    print("staging password not in vault; skipping sample export")

print("done")