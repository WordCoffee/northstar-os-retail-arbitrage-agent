#!/usr/bin/env python
"""1C-04 durable-execution schema validation on disposable PostgreSQL (B02/B03).

Runs the full apply / inspect / repository / rollback / reapply / fingerprint /
regression procedure against a DISPOSABLE LOOPBACK-ONLY PostgreSQL and writes
machine-readable evidence.

Safety: refuses to run unless FOUNDATION_DB_URL points at
postgresql://northstar_phase1c02_test@127.0.0.1:55432/northstar_phase1c02_ephemeral.
No other database is ever contacted. Never contacts staging/production.

Usage:
  python -m Northstar_backend.tools.foundation_pg_validate_durable
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

sys.path.insert(0, os.getcwd())

DISPOSABLE_DB = "northstar_phase1c02_ephemeral"
DISPOSABLE_USER = "northstar_phase1c02_test"
MIG_001 = os.path.join("Northstar_backend", "migrations_foundation", "001_foundation.sql")
MIG_002 = os.path.join("Northstar_backend", "migrations_foundation", "002_jobs_durable.sql")
MIG_002_ROLLBACK = os.path.join(
    "Northstar_backend", "migrations_foundation", "002_rollback_jobs_durable.sql")
MIG_003 = os.path.join("Northstar_backend", "migrations_foundation", "003_keyword_intel.sql")
MIG_003_ROLLBACK = os.path.join(
    "Northstar_backend", "migrations_foundation", "003_rollback_keyword_intel.sql")
MIG_004 = os.path.join("Northstar_backend", "migrations_foundation",
                       "004_financial_integrity.sql")
MIG_004_ROLLBACK = os.path.join(
    "Northstar_backend", "migrations_foundation",
    "004_rollback_financial_integrity.sql")
MIG_005 = os.path.join("Northstar_backend", "migrations_foundation",
                       "005_beta_launch_controls.sql")
MIG_005_ROLLBACK = os.path.join(
    "Northstar_backend", "migrations_foundation",
    "005_rollback_beta_launch_controls.sql")
MIG_006 = os.path.join("Northstar_backend", "migrations_foundation",
                       "006_private_beta_readiness.sql")
MIG_006_ROLLBACK = os.path.join(
    "Northstar_backend", "migrations_foundation",
    "006_rollback_private_beta_readiness.sql")
MIG_007 = os.path.join("Northstar_backend", "migrations_foundation",
                       "007_private_beta_operations.sql")
MIG_007_ROLLBACK = os.path.join(
    "Northstar_backend", "migrations_foundation",
    "007_rollback_private_beta_operations.sql")
EVIDENCE = os.path.join("docs", "northstar-phase1c", "postgres-durable-validation.json")


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _assert_disposable(url: str) -> dict:
    u = urlparse(url)
    assert u.hostname == "127.0.0.1", f"host must be loopback, got {u.hostname}"
    assert u.username == DISPOSABLE_USER
    assert (u.path or "").lstrip("/") == DISPOSABLE_DB
    assert u.port == 55432
    return {"host": "127.0.0.1", "port": 55432, "database": DISPOSABLE_DB,
            "user": DISPOSABLE_USER}


def main() -> int:
    url = os.environ.get("FOUNDATION_DB_URL")
    if not url:
        print("FOUNDATION_DB_URL not set; refusing to run.")
        return 2
    target = _assert_disposable(url)

    from Northstar_backend.foundation.db import SCHEMA
    from Northstar_backend.foundation.db_postgres import PostgresFoundationDB
    from Northstar_backend.foundation.models import (
        Organization, User, Membership, JobRequest, JobRun, JobStateHistory,
        JobSchedule, ScheduleOccurrence,
    )
    from Northstar_backend.foundation.enums import Role

    db = PostgresFoundationDB(url)
    foundation_tables = list(SCHEMA.keys())
    report: dict = {
        "phase": "1C-LC Workstream B (B02/B03)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_target": target,
        "server_version": None,
        "checksums": {"001_foundation.sql": _sha(MIG_001),
                      "002_jobs_durable.sql": _sha(MIG_002),
                      "002_rollback_jobs_durable.sql": _sha(MIG_002_ROLLBACK)},
        "steps": {},
    }

    try:
        report["server_version"] = db.server_info()["version"]

        # -- 1. clean apply ----------------------------------------------------
        db.drop_all_foundation_tables(foundation_tables)
        db.apply_sql_file(MIG_001)
        db.apply_sql_file(MIG_002)
        db.apply_sql_file(MIG_003)
        db.apply_sql_file(MIG_004)
        db.apply_sql_file(MIG_005)
        db.apply_sql_file(MIG_006)
        db.apply_sql_file(MIG_007)
        fingerprint_full = db.schema_fingerprint()
        report["steps"]["1_clean_apply"] = {
            "status": "PASS",
            "tables": fingerprint_full["table_count"],
            "columns": fingerprint_full["column_count"],
        }

        # -- 2. schema inspection ----------------------------------------------
        tables = fingerprint_full["tables"]
        expected_tables = set(foundation_tables)
        missing_tables = sorted(expected_tables - set(tables))
        missing_cols = []
        for t, cols in SCHEMA.items():
            for name, _lt in cols:
                if name not in tables.get(t, []):
                    missing_cols.append(f"{t}.{name}")
        schema_ok = not missing_tables and not missing_cols
        report["steps"]["2_schema_inspection"] = {
            "status": "PASS" if schema_ok else "FAIL",
            "table_count": len(tables),
            "missing_tables": missing_tables,
            "missing_columns": missing_cols,
        }
        assert schema_ok, f"schema inspection failed: {missing_tables} {missing_cols}"

        # -- 3. constraint inspection ------------------------------------------
        constraints = fingerprint_full["constraints"]
        indexes = fingerprint_full["indexes"]
        all_index_names = [i for v in indexes.values() for i in v]
        expected_fks = ["fk_job_requests_organization_id", "fk_job_runs_job_request_id",
                        "fk_job_schedules_organization_id",
                        "fk_schedule_occurrences_schedule_id",
                        "fk_keywords_organization_id", "fk_search_terms_organization_id",
                        "fk_targets_keyword_id", "fk_keyword_links_keyword_id",
                        "fk_source_files_organization_id",
                        "fk_import_batches_organization_id",
                        "fk_import_batches_source_file_id",
                        "fk_rejected_rows_import_batch_id",
                        "fk_rank_observations_keyword_id",
                        "fk_ad_performance_observations_search_term_id"]
        missing_fks = [fk for fk in expected_fks
                       if not any(fk in item
                                  for v in constraints.values() for item in v)]
        # account + request-type scoped idempotency unique (financial-integrity gate)
        unique_present = any(
            "uq_job_requests_org_type_idem" in item
            for v in constraints.values() for item in v) \
            or "uq_job_requests_org_type_idem" in all_index_names
        report["steps"]["3_constraint_inspection"] = {
            "status": "PASS" if not missing_fks and unique_present else "FAIL",
            "foreign_keys_present": sorted(expected_fks),
            "missing_foreign_keys": missing_fks,
            "org_scoped_idempotency_unique": unique_present,
        }
        assert not missing_fks and unique_present, \
            f"missing_fks={missing_fks} unique_present={unique_present}"

        # -- 4. index inspection ------------------------------------------------
        expected_indexes = [
            "idx_job_requests__organization_id__created_at",
            "idx_job_runs__state__priority__created_at",
            "idx_job_runs__lease_expiration",
            "idx_job_runs__job_request_id__created_at",
            "idx_job_state_history__job_id__run_id",
            "idx_job_state_history__occurred_at",
            "idx_job_schedules__organization_id__enabled",
            "idx_job_schedules__next_run_at",
            "idx_schedule_occurrences__schedule_id__scheduled_for",
            "idx_audit_events__organization_id__occurred_at",
            "uq_keywords_org_phrase_match_mp",
            "uq_source_files_org_sha",
            "uq_search_terms_org_term_mp",
            "uq_job_requests_org_type_idem",
            "uq_account_acceptance_org_user",
            "idx_acceptance_events__organization_id__user_id__accepted_at",
            "idx_legal_documents__doc_type__version",
            "uq_billing_events_processor_event_id",
            "uq_subscriptions_processor_subscription_id",
            "uq_invites_invite_code",
            "idx_invites__organization_id__email",
            "idx_subscriptions__organization_id__status",
            "idx_org_lifecycle_events__organization_id__occurred_at",
            "idx_support_tickets__organization_id__status",
            "idx_support_tickets__reference_id",
            "idx_org_admin_notes__organization_id__created_at",
        ]
        missing_indexes = [i for i in expected_indexes if i not in all_index_names]
        report["steps"]["4_index_inspection"] = {
            "status": "PASS" if not missing_indexes else "FAIL",
            "index_count": len(all_index_names),
            "missing_indexes": missing_indexes,
        }
        assert not missing_indexes

        # -- 5. repository tests (on PostgreSQL) --------------------------------
        db2 = PostgresFoundationDB(url)
        try:
            from Northstar_backend.foundation.api.state import FoundationState
            state = FoundationState.build()
            org = Organization(name="Durable Org", slug="durable")
            user = User(email="durable@example.test")
            state.repos.organizations.add(org)
            state.repos.users.add(user)
            state.repos.memberships.add(Membership(
                organization_id=org.id, user_id=user.id,
                role=Role.ORGANIZATION_OWNER.value, status="active"))

            req = JobRequest(organization_id=org.id, user_id=user.id,
                             service="durable", job_type="immediate_success",
                             payload={"n": 1}, payload_schema_version="1.0",
                             provider_class="local", budget_class="free",
                             estimated_cost=0.0, idempotency_key="durable-key-1")
            req_row = state.repos.job_requests.add(req)
            assert req_row["id"] == req.id

            run = JobRun(job_request_id=req.id, state="queued", run_id="run-1",
                         priority=5, lease_owner="worker-a")
            run_row = state.repos.job_runs.add(run)
            assert run_row["lease_owner"] == "worker-a"

            hist = JobStateHistory(job_id=req.id, run_id="run-1",
                                   previous_state="draft", new_state="queued",
                                   actor="requestor", reason="submit")
            state.repos.job_state_history.add(hist)
            assert state.repos.job_state_history.for_job(req.id)

            sched = JobSchedule(organization_id=org.id, owner_user_id=user.id,
                                job_template={"job_type": "immediate_success"},
                                enabled=False)
            sched_row = state.repos.job_schedules.add(sched)
            occ = ScheduleOccurrence(schedule_id=sched.id, occurrence_key="occ-1",
                                     state="enqueued")
            state.repos.schedule_occurrences.add(occ)
            assert state.repos.schedule_occurrences.by_key(sched.id, "occ-1") is not None

            # org-scoped idempotency: duplicate (org, key) rejected
            dup = JobRequest(organization_id=org.id, user_id=user.id,
                             service="durable", job_type="immediate_success",
                             idempotency_key="durable-key-1")
            duplicate_rejected = False
            try:
                state.repos.job_requests.add(dup)
            except Exception:  # noqa: BLE001 - IntegrityError on either backend
                duplicate_rejected = True
            assert duplicate_rejected, "duplicate org-scoped idempotency key accepted"

            # same key in ANOTHER org is allowed (org-scoped)
            org2 = Organization(name="Other Org", slug="other-org")
            state.repos.organizations.add(org2)
            cross = JobRequest(organization_id=org2.id, user_id=user.id,
                               service="durable", job_type="immediate_success",
                               idempotency_key="durable-key-1")
            cross_row = state.repos.job_requests.add(cross)
            assert cross_row["id"] == cross.id
            state.close()
            report["steps"]["5_repository_tests"] = {
                "status": "PASS",
                "checks": ["org/user/membership roundtrip",
                           "job_request with durable columns",
                           "job_run with lease fields",
                           "job_state_history append",
                           "job_schedule + schedule_occurrence",
                           "org-scoped idempotency (dup rejected, cross-org allowed)"],
            }
        finally:
            db2.close()

        # -- 6. rollback (compensating: 004 then 003 then 002) ----------------------
        db.apply_sql_file(MIG_007_ROLLBACK)
        db.apply_sql_file(MIG_006_ROLLBACK)
        db.apply_sql_file(MIG_005_ROLLBACK)
        db.apply_sql_file(MIG_004_ROLLBACK)
        db.apply_sql_file(MIG_003_ROLLBACK)
        db.apply_sql_file(MIG_002_ROLLBACK)
        fingerprint_rolled = db.schema_fingerprint()
        rolled_tables = fingerprint_rolled["tables"]
        rollback_ok = (
            "job_state_history" not in rolled_tables
            and "job_schedules" not in rolled_tables
            and "schedule_occurrences" not in rolled_tables
            and "job_type" not in rolled_tables.get("job_requests", [])
            and "lease_owner" not in rolled_tables.get("job_runs", [])
            and "keywords" not in rolled_tables
            and "search_terms" not in rolled_tables
            and "source_files" not in rolled_tables
            and "correlation_id" not in rolled_tables.get("audit_events", [])
        )
        report["steps"]["6_rollback"] = {
            "status": "PASS" if rollback_ok else "FAIL",
            "tables_after_rollback": len(rolled_tables),
            "durable_objects_removed": rollback_ok,
        }
        assert rollback_ok, "compensating rollback did not remove 1C-04/1C-05 objects"

        # -- 7. reapply (002 then 003 then 004) ---------------------------------
        db.apply_sql_file(MIG_002)
        db.apply_sql_file(MIG_003)
        db.apply_sql_file(MIG_004)
        db.apply_sql_file(MIG_005)
        db.apply_sql_file(MIG_006)
        db.apply_sql_file(MIG_007)
        fingerprint_reapplied = db.schema_fingerprint()
        reapply_ok = fingerprint_reapplied["tables_columns_hash"] == \
            fingerprint_full["tables_columns_hash"]
        report["steps"]["7_reapply"] = {
            "status": "PASS" if reapply_ok else "FAIL",
            "tables_after_reapply": fingerprint_reapplied["table_count"],
        }
        assert reapply_ok

        # -- 8. fingerprint comparison -------------------------------------------
        hashes_match = (
            fingerprint_reapplied["tables_columns_hash"] == fingerprint_full["tables_columns_hash"]
            and fingerprint_reapplied["constraints_hash"] == fingerprint_full["constraints_hash"]
            and fingerprint_reapplied["indexes_hash"] == fingerprint_full["indexes_hash"]
        )
        # determinism: fresh clean-room apply of 001+002+003+004 matches
        db.drop_all_foundation_tables(foundation_tables)
        db.apply_sql_file(MIG_001)
        db.apply_sql_file(MIG_002)
        db.apply_sql_file(MIG_003)
        db.apply_sql_file(MIG_004)
        db.apply_sql_file(MIG_005)
        db.apply_sql_file(MIG_006)
        db.apply_sql_file(MIG_007)
        fingerprint_clean = db.schema_fingerprint()
        deterministic = fingerprint_clean["tables_columns_hash"] == fingerprint_full["tables_columns_hash"]
        report["steps"]["8_fingerprint_comparison"] = {
            "status": "PASS" if hashes_match and deterministic else "FAIL",
            "reapply_matches_original": hashes_match,
            "clean_room_deterministic": deterministic,
            "fingerprints": {
                "full": fingerprint_full["tables_columns_hash"][:16],
                "rolled": fingerprint_rolled["tables_columns_hash"][:16],
                "reapplied": fingerprint_reapplied["tables_columns_hash"][:16],
                "clean": fingerprint_clean["tables_columns_hash"][:16],
            },
        }
        assert hashes_match and deterministic

        # -- 9. existing-foundation regression ------------------------------------
        state = FoundationState.build()
        seed_orgs = state.repos.organizations.count()
        state.seed()
        after = {
            "marketplace_count": state.repos.marketplaces.count(),
            "pricing_policy_count": state.repos.pricing.count(),
            "provider_count": state.repos.providers.count(),
        }
        state.close()
        regression_ok = seed_orgs >= 0 and after["marketplace_count"] >= 1 \
            and after["pricing_policy_count"] >= 1 and after["provider_count"] >= 2
        report["steps"]["9_foundation_regression"] = {
            "status": "PASS" if regression_ok else "FAIL",
            "post_seed_counts": after,
        }
        assert regression_ok

        report["summary"] = {
            "status": "PASS",
            "postgres_version": report["server_version"],
            "steps_passed": len([s for s in report["steps"].values()
                                 if s["status"] == "PASS"]),
            "steps_total": len(report["steps"]),
            "database_target": target,
            "network_status": "loopback-only disposable container (docker postgres:15)",
            "staging_or_production_contacted": False,
        }
    finally:
        db.close()

    with open(EVIDENCE, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, default=str)

    print(json.dumps(report["summary"], indent=2))
    return 0 if report["summary"]["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())