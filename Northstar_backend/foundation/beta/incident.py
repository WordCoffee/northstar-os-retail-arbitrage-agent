"""Incident-response runbook (1C-06).

Usable without external tools or undocumented tribal knowledge. Covers: named
accountable role; access-disable steps; session invalidation; secret rotation;
evidence/log preservation; scope assessment; customer-communication decision
tree; recovery; post-incident review.
"""
from __future__ import annotations

RUNBOOK = {
    "named_accountable_role": "Tyrone (single operator — sole rollback, sole "
                              "approval, sole operational authority)",
    "roles": {
        "incident_commander": "Tyrone",
        "deputy": "none (single-operator beta); document handoff notes if a "
                  "second operator is ever added",
    },
    "access_disable_steps": [
        "1. Set the affected organization active=0 (suspend).",
        "2. Set the affected memberships status='suspended' (or 'revoked').",
        "3. Confirm the affected provider rows have enabled=0 (local/fake "
        "handlers never need live providers).",
        "4. If beta acceptance enforcement is on, do not change it — "
        "suspension already blocks authenticated use.",
    ],
    "session_invalidation": [
        "1. Revoke the affected jti(s): POST /session/revoke?jti=<jti> (owner "
        "or operator).",
        "2. Revoke ALL sessions for the affected user by marking every row in "
        "the sessions table for that user as revoked (operator SQL).",
        "3. Confirm: a request with a revoked token returns 401.",
    ],
    "secret_rotation_checklist": [
        "1. Rotate the affected secret (e.g., NORTHSTAR_JWT_SECRET or a "
        "credential) — generate a new value; NEVER reuse the old one.",
        "2. Update the encrypted vault (foundation/secrets.py) if the secret "
        "is stored there.",
        "3. Restart the backend/worker/scheduler so the new secret is loaded.",
        "4. Verify old tokens now fail (401) and new tokens work.",
        "5. If a secret was exposed, treat the environment as compromised and "
        "revoke all sessions.",
    ],
    "evidence_and_log_preservation": [
        "1. Export the relevant audit events (action=authz.denied, session.*, "
        "job.state.*) with correlation/request ids to a read-only location.",
        "2. Preserve the foundation DB (pg_dump) BEFORE any remediation write "
        "where possible.",
        "3. Note the exact timestamps, tokens (jti), and requests involved.",
        "4. Do not delete logs during an active incident.",
    ],
    "scope_assessment": [
        "1. Which users/organizations were affected? (query sessions + "
        "acceptance_events + audit by correlation id).",
        "2. Which data could have been exposed? (map to the data inventory).",
        "3. Was any write performed? (audit job.state.* + keyword.import + "
        "schedule.*).",
        "4. Was any provider/marketplace operation possible? (providers are "
        "disabled; confirm).",
    ],
    "customer_communication_decision_tree": [
        "Was any customer data accessed by an unauthorized party?",
        "  - YES and evidence exists -> notify the affected organization "
        "promptly with facts and next steps.",
        "  - YES but scope uncertain -> notify with conservative language; do "
        "not over-claim certainty.",
        "  - NO (contained before access) -> no notification required; "
        "document the near-miss.",
        "Was there a service outage / data loss? -> notify per SLA expectations "
        "of the beta contract.",
        "Is a legal/regulatory notification obligation triggered? -> escalate "
        "to the named accountable role (and counsel if engaged); do not guess.",
    ],
    "recovery": [
        "1. Apply the documented access-disable steps in reverse only after "
        "root cause is understood.",
        "2. Re-enable providers/memberships only after verification.",
        "3. Confirm acceptance enforcement still passes for the affected "
        "accounts.",
        "4. Verify a full smoke (auth, jobs, keywords) before restoring "
        "customer access.",
    ],
    "post_incident_review": [
        "1. Record the incident: timeline, root cause, actions, evidence "
        "paths, and outcome.",
        "2. Identify control gaps and update the risk register + known gaps.",
        "3. Update this runbook if the incident revealed a missing step.",
        "4. Re-run the affected test surface (authorization, financial "
        "integrity, beta acceptance).",
    ],
    "no_external_tools_note": "Every step uses only the foundation API, the "
                              "vault CLI, docker/psql for the local staging "
                              "box, and SQL on the foundation DB — no "
                              "undocumented tribal knowledge required.",
}


def runbook() -> dict:
    return RUNBOOK