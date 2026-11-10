"""Foundation database layer.

Dependency-light: stdlib ``sqlite3`` for local/dev/tests, with a **single schema
specification** that generates BOTH the SQLite DDL and the PostgreSQL DDL. This
makes backend divergence a construction error rather than a silent behavior risk.

Design rules:
- Additive schema only (``CREATE TABLE IF NOT EXISTS``).
- Safe for a disposable SQLite path or ``:memory:``.
- NEVER points at the production-like ``northstar.db`` by default.
- JSON is stored/read via explicit ``json.dumps``/``json.loads`` in the repository
  layer (identical behavior on SQLite TEXT and Postgres JSONB); booleans are
  serialized explicitly. No SQLite-only coercion is relied upon.
"""
from __future__ import annotations

import atexit
import functools
import json
import os
import sqlite3
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

# ---------------------------------------------------------------------------
# Single source of truth: table -> [(column, logical_type, constraints...)]
# logical types: id | text | int | real | bool | json | ts
# ---------------------------------------------------------------------------
SCHEMA: dict[str, list[tuple[str, str]]] = {
    "organizations": [
        ("id", "id"), ("name", "text"), ("slug", "text"),
        ("environment", "text"), ("active", "bool"), ("created_at", "ts"),
    ],
    "users": [
        ("id", "id"), ("email", "text"), ("display_name", "text"),
        ("active", "bool"), ("created_at", "ts"),
    ],
    "memberships": [
        ("id", "id"), ("organization_id", "text"), ("user_id", "text"),
        ("role", "text"), ("status", "text"), ("created_at", "ts"),
    ],
    "marketplaces": [
        ("id", "id"), ("code", "text"), ("country", "text"), ("currency", "text"),
        ("domain", "text"), ("active", "bool"),
    ],
    "catalog_products": [
        ("id", "id"), ("marketplace_id", "text"), ("asin", "text"),
        ("brand", "text"), ("canonical_title", "text"), ("pack_config_id", "text"),
        ("variation_family_id", "text"), ("created_at", "ts"), ("updated_at", "ts"),
    ],
    "product_identifiers": [
        ("id", "id"), ("product_id", "text"), ("kind", "text"), ("raw_value", "text"),
        ("normalized_value", "text"), ("marketplace_id", "text"),
        ("verification_state", "text"), ("created_at", "ts"),
    ],
    "pack_configs": [
        ("id", "id"), ("product_id", "text"), ("count", "int"), ("unit", "text"),
        ("unit_type", "text"), ("is_multipack", "bool"), ("is_bundle", "bool"),
        ("verification_state", "text"),
    ],
    "variation_relationships": [
        ("id", "id"), ("family_id", "text"), ("child_product_id", "text"),
        ("axis", "text"), ("created_at", "ts"),
    ],
    "product_aliases": [
        ("id", "id"), ("product_id", "text"), ("alias_value", "text"),
        ("reason", "text"), ("created_at", "ts"),
    ],
    "unresolved_candidates": [
        ("id", "id"), ("raw_asin", "text"), ("raw_title", "text"),
        ("raw_identifier", "text"), ("reason", "text"), ("source", "text"),
        ("source_identifier", "text"), ("created_at", "ts"),
    ],
    "identity_conflicts": [
        ("id", "id"), ("conflict_type", "text"), ("candidate_id", "text"),
        ("product_id", "text"), ("detail", "text"), ("created_at", "ts"),
    ],
    "observations": [
        ("id", "id"), ("product_id", "text"), ("candidate_id", "text"),
        ("marketplace_id", "text"), ("provider", "text"),
        ("provider_record_id", "text"), ("observation_type", "text"),
        ("observed_value", "json"), ("currency", "text"), ("unit", "text"),
        ("captured_at", "ts"), ("effective_at", "ts"), ("expires_at", "ts"),
        ("confidence", "real"), ("verification_state", "text"),
        ("provenance_class", "text"), ("raw_source_ref", "text"),
        ("transformation_version", "text"), ("job_run_id", "text"),
        ("environment", "text"), ("created_at", "ts"),
    ],
    "providers": [
        ("id", "id"), ("provider_key", "text"), ("name", "text"),
        ("category", "text"), ("adapter_module", "text"), ("read_capable", "bool"),
        ("write_capable", "bool"), ("sandbox_supported", "bool"),
        ("credential_ref_names", "json"), ("rate_limit_rpm", "int"),
        ("timeout_seconds", "int"), ("cost_model", "json"), ("health", "text"),
        ("enabled", "bool"),
    ],
    "job_requests": [
        ("id", "id"), ("organization_id", "text"), ("user_id", "text"),
        ("service", "text"), ("scope_type", "text"), ("scope_id", "text"),
        ("data_types", "json"), ("provider_policy", "text"),
        ("max_estimated_cost", "real"), ("currency", "text"),
        ("environment", "text"), ("idempotency_key", "text"),
        ("requires_approval", "bool"), ("reason", "text"), ("priority", "int"),
        ("created_at", "ts"),
        # --- 1C-04 durable execution (additive) ---
        ("state", "text"), ("job_type", "text"), ("payload", "json"),
        ("payload_schema_version", "text"), ("approval_id", "text"),
        ("provider_class", "text"), ("budget_class", "text"),
        ("estimated_cost", "money"), ("parent_job_id", "text"),
        ("correlation_id", "text"), ("provenance", "json"),
    ],
    "job_runs": [
        ("id", "id"), ("job_request_id", "text"), ("state", "text"),
        ("run_id", "text"), ("attempts", "int"), ("max_attempts", "int"),
        ("failure_class", "text"), ("error_message", "text"),
        ("started_at", "ts"), ("finished_at", "ts"), ("created_at", "ts"),
        # --- 1C-04 durable execution (additive) ---
        ("priority", "int"), ("reserved_cost", "money"),
        ("actual_cost", "money"), ("scheduled_time", "ts"),
        ("heartbeat_time", "ts"), ("lease_owner", "text"),
        ("lease_expiration", "ts"), ("idempotency_key", "text"),
        ("parent_job_id", "text"), ("correlation_id", "text"),
        ("output_reference", "text"), ("error_code", "text"),
        ("error_summary", "text"), ("cancellation_state", "text"),
    ],
    "job_state_history": [
        ("id", "id"), ("job_id", "text"), ("run_id", "text"),
        ("previous_state", "text"), ("new_state", "text"), ("actor", "text"),
        ("reason", "text"), ("correlation_id", "text"),
        ("audit_event_ref", "text"), ("occurred_at", "ts"),
    ],
    "job_schedules": [
        ("id", "id"), ("organization_id", "text"), ("owner_user_id", "text"),
        ("job_template", "json"), ("timezone", "text"),
        ("cron_expression", "text"), ("interval_seconds", "int"),
        ("enabled", "bool"), ("next_run_at", "ts"), ("last_run_at", "ts"),
        ("concurrency_policy", "json"), ("misfire_policy", "text"),
        ("approval_policy", "json"), ("budget_policy", "json"),
        ("provider_policy", "json"), ("failure_policy", "json"),
        ("version", "text"), ("archived", "bool"),
        ("created_at", "ts"), ("updated_at", "ts"),
    ],
    "schedule_occurrences": [
        ("id", "id"), ("schedule_id", "text"), ("occurrence_key", "text"),
        ("scheduled_for", "ts"), ("enqueued_job_request_id", "text"),
        ("state", "text"), ("created_at", "ts"),
    ],
    "org_balances": [
        ("organization_id", "id"), ("granted", "money"), ("reserved", "money"),
        ("consumed", "money"), ("updated_at", "ts"),
    ],
    # --- 1C-05 keyword & SEO intelligence (additive) ---
    "keywords": [
        ("id", "id"), ("organization_id", "text"),
        ("normalized_phrase", "text"), ("original_phrase", "text"),
        ("marketplace", "text"), ("language", "text"), ("match_type", "text"),
        ("brand_terms", "json"), ("confidence", "real"),
        ("freshness_state", "text"), ("created_at", "ts"),
    ],
    "search_terms": [
        ("id", "id"), ("organization_id", "text"), ("raw_term", "text"),
        ("normalized_term", "text"), ("marketplace", "text"),
        ("search_volume", "int"), ("observed_volume", "int"),
        ("impressions", "int"), ("clicks", "int"), ("spend", "money"),
        ("orders", "int"), ("revenue", "money"), ("source", "text"),
        ("observed_at", "ts"), ("created_at", "ts"),
    ],
    "targets": [
        ("id", "id"), ("organization_id", "text"), ("keyword_id", "text"),
        ("campaign_id", "text"), ("ad_group_id", "text"), ("match_type", "text"),
        ("bid", "money"), ("status", "text"), ("created_at", "ts"),
    ],
    "keyword_links": [
        ("id", "id"), ("organization_id", "text"), ("keyword_id", "text"),
        ("link_kind", "text"), ("target_ref", "text"), ("asin", "text"),
        ("product_id", "text"), ("note", "text"), ("created_at", "ts"),
    ],
    "import_batches": [
        ("id", "id"), ("organization_id", "text"), ("source_file_id", "text"),
        ("status", "text"), ("submitted_by", "text"), ("submitted_at", "ts"),
        ("started_at", "ts"), ("completed_at", "ts"), ("summary", "json"),
        ("created_at", "ts"),
    ],
    "source_files": [
        ("id", "id"), ("organization_id", "text"), ("file_name", "text"),
        ("file_sha256", "text"), ("file_size", "int"), ("marketplace", "text"),
        ("currency", "text"), ("report_type", "text"), ("date_from", "ts"),
        ("date_to", "ts"), ("status", "text"), ("registered_at", "ts"),
        ("created_at", "ts"),
    ],
    "source_rows": [
        ("id", "id"), ("organization_id", "text"), ("import_batch_id", "text"),
        ("source_file_id", "text"), ("row_index", "int"), ("row_json", "json"),
        ("status", "text"), ("created_at", "ts"),
    ],
    "rejected_rows": [
        ("id", "id"), ("organization_id", "text"), ("import_batch_id", "text"),
        ("source_file_id", "text"), ("row_index", "int"), ("row_json", "json"),
        ("rejection_reason", "text"), ("created_at", "ts"),
    ],
    "normalization_decisions": [
        ("id", "id"), ("organization_id", "text"), ("original_phrase", "text"),
        ("normalized_phrase", "text"), ("rule", "json"), ("created_at", "ts"),
    ],
    "rank_observations": [
        ("id", "id"), ("organization_id", "text"), ("keyword_id", "text"),
        ("asin", "text"), ("rank", "int"), ("placement", "text"),
        ("observed_at", "ts"), ("source", "text"), ("confidence", "real"),
        ("freshness_state", "text"), ("created_at", "ts"),
    ],
    "ad_performance_observations": [
        ("id", "id"), ("organization_id", "text"), ("search_term_id", "text"),
        ("campaign_id", "text"), ("ad_group_id", "text"), ("impressions", "int"),
        ("clicks", "int"), ("spend", "money"), ("orders", "int"),
        ("revenue", "money"), ("ctr", "real"), ("cvr", "real"),
        ("observed_at", "ts"), ("source", "text"), ("created_at", "ts"),
    ],
    "keyword_conflicts": [
        ("id", "id"), ("organization_id", "text"), ("keyword_id_a", "text"),
        ("keyword_id_b", "text"), ("conflict_type", "text"), ("detail", "text"),
        ("created_at", "ts"),
    ],
    # --- 1C-06 Lean B2B beta launch controls (additive) ---
    "legal_documents": [
        ("id", "id"), ("doc_type", "text"), ("version", "text"), ("title", "text"),
        ("content_hash", "text"), ("status", "text"), ("published_at", "ts"),
        ("created_at", "ts"),
    ],
    "acceptance_events": [
        ("id", "id"), ("organization_id", "text"), ("user_id", "text"),
        ("doc_type", "text"), ("doc_version", "text"), ("content_hash", "text"),
        ("business_use_attested", "bool"), ("age_18_attested", "bool"),
        ("ip_handling", "text"), ("request_id", "text"),
        ("correlation_id", "text"), ("accepted_at", "ts"), ("created_at", "ts"),
    ],
    "account_acceptance": [
        ("id", "id"), ("organization_id", "text"), ("user_id", "text"),
        ("privacy_notice_version", "text"), ("terms_of_service_version", "text"),
        ("acceptable_use_policy_version", "text"),
        ("private_beta_addendum_version", "text"),
        ("business_attested", "bool"), ("age_18_attested", "bool"),
        ("updated_at", "ts"),
    ],
    # --- 1C-06 master slice: private beta readiness (additive) ---
    "billing_customers": [
        ("id", "id"), ("organization_id", "text"), ("processor", "text"),
        ("processor_customer_id", "text"), ("created_at", "ts"),
        ("updated_at", "ts"),
    ],
    "checkout_sessions": [
        ("id", "id"), ("organization_id", "text"), ("price_id", "text"),
        ("tier", "text"), ("status", "text"), ("expires_at", "ts"),
        ("created_at", "ts"),
    ],
    "subscriptions": [
        ("id", "id"), ("organization_id", "text"),
        ("billing_customer_id", "text"), ("processor_subscription_id", "text"),
        ("price_id", "text"), ("tier", "text"), ("status", "text"),
        ("current_period_end", "ts"), ("created_at", "ts"), ("updated_at", "ts"),
    ],
    "billing_events": [
        ("id", "id"), ("processor_event_id", "text"), ("event_type", "text"),
        ("payload_hash", "text"), ("status", "text"), ("processed_at", "ts"),
        ("created_at", "ts"),
    ],
    "invites": [
        ("id", "id"), ("organization_id", "text"), ("invite_code", "text"),
        ("email", "text"), ("role", "text"), ("status", "text"),
        ("created_by", "text"), ("expires_at", "ts"), ("used_at", "ts"),
        ("created_at", "ts"),
    ],
    "org_entitlements": [
        ("organization_id", "id"), ("tier", "text"),
        ("max_jobs_per_month", "int"), ("export_enabled", "bool"),
        ("advanced_reports", "bool"), ("seat_limit", "int"),
        ("updated_at", "ts"),
    ],
    # --- 1C-06 master slice: private beta operations (additive) ---
    "org_lifecycle": [
        ("organization_id", "id"), ("state", "text"), ("updated_at", "ts"),
    ],
    "org_lifecycle_events": [
        ("id", "id"), ("organization_id", "text"), ("actor_user_id", "text"),
        ("previous_state", "text"), ("new_state", "text"), ("reason", "text"),
        ("correlation_id", "text"), ("occurred_at", "ts"), ("created_at", "ts"),
    ],
    "org_admin_notes": [
        ("id", "id"), ("organization_id", "text"), ("author_user_id", "text"),
        ("note", "text"), ("created_at", "ts"),
    ],
    "entitlement_overrides": [
        ("id", "id"), ("organization_id", "text"), ("feature", "text"),
        ("value_text", "text"), ("value_int", "int"), ("reason", "text"),
        ("created_by", "text"), ("scope", "text"), ("expires_at", "ts"),
        ("permanent", "bool"), ("created_at", "ts"),
    ],
    "support_tickets": [
        ("id", "id"), ("organization_id", "text"), ("reference_id", "text"),
        ("reporter_user_id", "text"), ("category", "text"), ("severity", "text"),
        ("subject", "text"), ("description", "text"), ("status", "text"),
        ("assignee_user_id", "text"), ("internal_note", "text"),
        ("tester_visible_note", "text"), ("created_at", "ts"),
        ("updated_at", "ts"),
    ],
    "onboarding": [
        ("organization_id", "id"), ("checklist", "json"), ("completed", "bool"),
        ("completed_at", "ts"), ("updated_at", "ts"),
    ],
    "usage_counters": [
        ("organization_id", "id"), ("period", "text"),
        ("monthly_jobs_used", "int"), ("updated_at", "ts"),
    ],
    "usage_events": [
        ("id", "id"), ("organization_id", "text"), ("user_id", "text"),
        ("service", "text"), ("workflow_run_id", "text"), ("provider", "text"),
        ("model_or_endpoint", "text"), ("input_units", "int"),
        ("output_units", "int"), ("provider_reported_cost", "real"),
        ("estimated_cost", "real"), ("credits_debited_shadow", "real"),
        ("cost_kind", "text"), ("status", "text"), ("idempotency_key", "text"),
        ("reversal_ref", "text"), ("environment", "text"),
        ("occurred_at", "ts"), ("provenance", "json"),
    ],
    "pricing_policies": [
        ("version", "id"), ("platform_markup", "real"), ("minimum_charge", "real"),
        ("service_multipliers", "json"), ("free_local_execution", "bool"),
        ("failed_run_charge", "bool"),
    ],
    "audit_events": [
        ("id", "id"), ("actor_user_id", "text"), ("actor_role", "text"),
        ("organization_id", "text"), ("target_organization_id", "text"),
        ("target_user_id", "text"), ("action", "text"), ("resource_type", "text"),
        ("resource_id", "text"), ("before_meta", "json"), ("after_meta", "json"),
        ("environment", "text"), ("view_context", "text"), ("approval_ref", "text"),
        ("job_run_ref", "text"), ("result", "text"), ("failure_class", "text"),
        ("correlation_id", "text"), ("occurred_at", "ts"),
    ],
    "approval_requests": [
        ("id", "id"), ("organization_id", "text"), ("requested_by_user_id", "text"),
        ("capability", "text"), ("safety_class", "text"), ("resource_type", "text"),
        ("resource_id", "text"), ("change_preview", "json"), ("risk_level", "text"),
        ("cost_estimate", "real"), ("currency", "text"), ("state", "text"),
        ("required_approver_role", "text"), ("expires_at", "ts"),
        ("idempotency_key", "text"), ("execution_ref", "text"),
        ("environment", "text"), ("created_at", "ts"),
    ],
    "approval_decisions": [
        ("id", "id"), ("approval_request_id", "text"),
        ("decided_by_user_id", "text"), ("decided_by_role", "text"),
        ("decision", "text"), ("note", "text"), ("decided_at", "ts"),
    ],
    "preview_sessions": [
        ("id", "id"), ("actor_user_id", "text"), ("target_organization_id", "text"),
        ("target_role", "text"), ("started_at", "ts"), ("ended_at", "ts"),
        ("reason", "text"), ("read_only", "bool"), ("active", "bool"),
    ],
    "sessions": [
        ("jti", "id"), ("user_id", "text"), ("organization_id", "text"),
        ("issued_at", "ts"), ("expires_at", "ts"), ("revoked_at", "ts"),
        ("revoked_reason", "text"),
    ],
    "suppliers": [
        ("id", "id"), ("name", "text"), ("supplier_class", "text"),
        ("public_catalog_url", "text"), ("created_at", "ts"),
    ],
    "supplier_documentation": [
        ("id", "id"), ("supplier_id", "text"), ("product_id", "text"),
        ("supply_state", "text"), ("documentation_state", "text"),
        ("note", "text"), ("created_at", "ts"),
    ],
    "ui_preferences": [
        ("user_id", "text"), ("organization_id", "text"), ("key", "text"),
        ("value", "json"), ("updated_at", "ts"),
    ],
}

# Primary key column(s) per table.
PRIMARY_KEYS: dict[str, tuple[str, ...]] = {
    "organizations": ("id",), "users": ("id",), "memberships": ("id",),
    "marketplaces": ("id",), "catalog_products": ("id",),
    "product_identifiers": ("id",), "pack_configs": ("id",),
    "variation_relationships": ("id",), "product_aliases": ("id",),
    "unresolved_candidates": ("id",), "identity_conflicts": ("id",),
    "observations": ("id",), "providers": ("id",), "job_requests": ("id",),
    "job_runs": ("id",), "usage_events": ("id",), "pricing_policies": ("version",),
    "audit_events": ("id",), "approval_requests": ("id",),
    "approval_decisions": ("id",), "preview_sessions": ("id",),
    "sessions": ("jti",),
    "suppliers": ("id",), "supplier_documentation": ("id",),
    "ui_preferences": ("user_id", "organization_id", "key"),
    "job_state_history": ("id",),
    "job_schedules": ("id",),
    "schedule_occurrences": ("id",),
    "org_balances": ("organization_id",),
    "keywords": ("id",),
    "search_terms": ("id",),
    "targets": ("id",),
    "keyword_links": ("id",),
    "import_batches": ("id",),
    "source_files": ("id",),
    "source_rows": ("id",),
    "rejected_rows": ("id",),
    "normalization_decisions": ("id",),
    "rank_observations": ("id",),
    "ad_performance_observations": ("id",),
    "keyword_conflicts": ("id",),
    "legal_documents": ("id",),
    "acceptance_events": ("id",),
    "account_acceptance": ("id",),
    "billing_customers": ("id",),
    "checkout_sessions": ("id",),
    "subscriptions": ("id",),
    "billing_events": ("id",),
    "invites": ("id",),
    "org_entitlements": ("organization_id",),
    "org_lifecycle": ("organization_id",),
    "org_lifecycle_events": ("id",),
    "org_admin_notes": ("id",),
    "entitlement_overrides": ("id",),
    "support_tickets": ("id",),
    "onboarding": ("organization_id",),
    "usage_counters": ("organization_id",),
}

# UNIQUE constraints. Each table maps to a tuple of key-tuples (supports
# composite keys). NULL idempotency values remain distinct (org-scoped
# idempotency; a key only dedupes within the owning organization).
UNIQUE_COLUMNS: dict[str, tuple[tuple[str, ...], ...]] = {
    "marketplaces": (("code",),),
    "providers": (("provider_key",),),
    # NOTE: job_requests idempotency uniqueness is intentionally NOT declared
    # here — the (organization_id, job_type, idempotency_key) unique is created
    # by migration 004 (the financial-integrity gate) so the migration set
    # stays symmetric across clean-room/rollback/reapply.
    "usage_events": (("idempotency_key",),),
    "approval_requests": (("idempotency_key",),),
    "schedule_occurrences": (("schedule_id", "occurrence_key"),),
    "keywords": (("organization_id", "normalized_phrase", "match_type", "marketplace"),),
    "source_files": (("organization_id", "file_sha256"),),
    "search_terms": (("organization_id", "normalized_term", "marketplace"),),
    "account_acceptance": (("organization_id", "user_id"),),
    "billing_events": (("processor_event_id",),),
    "subscriptions": (("processor_subscription_id",),),
    "invites": (("invite_code",),),
    "support_tickets": (("reference_id",),),
}

# Foreign keys (both SQLite and PostgreSQL DDL, keeping backend divergence a
# construction error). Only relationships whose parent row is ALWAYS created
# before the child in repository flows are declared. Deletes are restricted
# (NO ACTION) — jobs/history are never silently cascade-deleted.
FOREIGN_KEYS: dict[str, list[tuple[str, str, str]]] = {
    "job_requests": [("organization_id", "organizations", "id")],
    "job_runs": [("job_request_id", "job_requests", "id")],
    "job_schedules": [("organization_id", "organizations", "id")],
    "schedule_occurrences": [("schedule_id", "job_schedules", "id")],
    "keywords": [("organization_id", "organizations", "id")],
    "search_terms": [("organization_id", "organizations", "id")],
    "targets": [("keyword_id", "keywords", "id")],
    "keyword_links": [("keyword_id", "keywords", "id")],
    "source_files": [("organization_id", "organizations", "id")],
    "import_batches": [("organization_id", "organizations", "id"),
                       ("source_file_id", "source_files", "id")],
    "rejected_rows": [("import_batch_id", "import_batches", "id")],
    "rank_observations": [("keyword_id", "keywords", "id")],
    "ad_performance_observations": [("search_term_id", "search_terms", "id")],
}

# Query indexes: queue/claim, lease recovery, idempotency (besides the unique
# constraint), schedules, and audit/history lookups.
INDEXES: dict[str, tuple[tuple[str, ...], ...]] = {
    "job_requests": (("organization_id", "created_at"),),
    "job_runs": (
        ("state", "priority", "created_at"),
        ("lease_expiration",),
        ("job_request_id", "created_at"),
    ),
    "job_state_history": (
        ("job_id", "run_id"),
        ("occurred_at",),
    ),
    "job_schedules": (
        ("organization_id", "enabled"),
        ("next_run_at",),
    ),
    "schedule_occurrences": (
        ("schedule_id", "scheduled_for"),
    ),
    "audit_events": (
        ("organization_id", "occurred_at"),
    ),
    "acceptance_events": (
        ("organization_id", "user_id", "accepted_at"),
    ),
    "legal_documents": (
        ("doc_type", "version"),
    ),
    "invites": (
        ("organization_id", "email"),
    ),
    "subscriptions": (
        ("organization_id", "status"),
    ),
    "org_lifecycle_events": (
        ("organization_id", "occurred_at"),
    ),
    "support_tickets": (
        ("organization_id", "status"),
        ("reference_id",),
    ),
    "org_admin_notes": (
        ("organization_id", "created_at"),
    ),
}

_TABLE_ORDER = list(SCHEMA.keys())

_SQLITE_TYPE = {"id": "TEXT", "text": "TEXT", "int": "INTEGER", "real": "REAL",
                "bool": "INTEGER", "json": "TEXT", "ts": "TEXT", "money": "REAL"}
_PG_TYPE = {"id": "TEXT", "text": "TEXT", "int": "BIGINT", "real": "DOUBLE PRECISION",
            "bool": "BOOLEAN", "json": "JSONB", "ts": "TIMESTAMPTZ", "money": "NUMERIC"}


def _index_name(table: str, cols: tuple[str, ...]) -> str:
    return f"idx_{table}__{'__'.join(cols)}"


def _sqlite_ddl() -> list[str]:
    stmts = []
    for table, cols in SCHEMA.items():
        col_defs = []
        for name, lt in cols:
            col_defs.append(f"{name} {_SQLITE_TYPE[lt]}")
        pk = PRIMARY_KEYS[table]
        col_defs.append("PRIMARY KEY (" + ", ".join(pk) + ")")
        for u in UNIQUE_COLUMNS.get(table, ()):
            col_defs.append(f"UNIQUE ({', '.join(u)})")
        for local_col, ref_table, ref_col in FOREIGN_KEYS.get(table, ()):
            col_defs.append(
                f"FOREIGN KEY ({local_col}) REFERENCES {ref_table} ({ref_col})")
        stmts.append(
            f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(col_defs)})"
        )
    for table, index_cols in INDEXES.items():
        for cols in index_cols:
            stmts.append(
                f"CREATE INDEX IF NOT EXISTS {_index_name(table, cols)} "
                f"ON {table} ({', '.join(cols)})"
            )
    return stmts


SQLITE_DDL: list[str] = _sqlite_ddl()

_PG_HEADER = """-- Northstar OS Foundation — canonical schema (PostgreSQL)
-- ADDITIVE ONLY. NOT APPLIED. Apply per MIGRATION_GUIDE.md in a reviewed step.
-- GENERATED from foundation/db.py SCHEMA (single source of truth). Do not edit
-- by hand; regenerate with tools/foundation_generate_sql.py.
-- Logical-type mapping: id->TEXT, text->TEXT, int->BIGINT, real->DOUBLE PRECISION,
-- money->NUMERIC, bool->BOOLEAN, json->JSONB, ts->TIMESTAMPTZ
-- (SQLite: TEXT/INTEGER/REAL/REAL/INTEGER/TEXT/TEXT).
"""


def postgres_ddl() -> str:
    """Generate Postgres DDL from the same SCHEMA used for SQLite."""
    out = [_PG_HEADER]
    for table, cols in SCHEMA.items():
        col_defs = []
        for name, lt in cols:
            col_defs.append(f'"{name}" {_PG_TYPE[lt]}')
        pk = PRIMARY_KEYS[table]
        col_defs.append("PRIMARY KEY (" + ", ".join(f'"{c}"' for c in pk) + ")")
        for u in UNIQUE_COLUMNS.get(table, ()):
            cols_quoted = ", ".join(f'"{c}"' for c in u)
            col_defs.append(f"UNIQUE ({cols_quoted})")
        out.append(
            f'CREATE TABLE IF NOT EXISTS "{table}" (\n    '
            + ",\n    ".join(col_defs) + "\n);"
        )
    for table, fks in FOREIGN_KEYS.items():
        for local_col, ref_table, ref_col in fks:
            out.append(
                "DO $$\nBEGIN\n"
                f'    ALTER TABLE "{table}" ADD CONSTRAINT "fk_{table}_{local_col}" '
                f'FOREIGN KEY ("{local_col}") REFERENCES "{ref_table}" ("{ref_col}");\n'
                "EXCEPTION WHEN duplicate_object THEN NULL;\n"
                "END $$;\n"
            )
    for table, index_cols in INDEXES.items():
        for cols in index_cols:
            cols_quoted = ", ".join(f'"{c}"' for c in cols)
            out.append(
                f'CREATE INDEX IF NOT EXISTS "{_index_name(table, cols)}" '
                f'ON "{table}" ({cols_quoted});'
            )
    return "\n\n".join(out)


def _ser(value: Any) -> Any:
    """Serialize a value for SQLite storage (JSON for dict/list, ISO for dt)."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, datetime):
        return value.isoformat()
    from decimal import Decimal
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return value


class _SerializedConnection:
    """Thread-safe facade over ONE ``sqlite3.Connection``.

    FastAPI runs synchronous endpoints in a worker threadpool, so several
    requests reach the same connection at once. CPython's sqlite3 keeps a
    per-connection statement cache, and concurrent statement creation on one
    connection raises ``InterfaceError: bad parameter or other API misuse``
    (observed live as 500s on ``/api/v1/foundation/me`` and ``/environment``
    whenever the SPA issued its parallel context calls). Every statement
    therefore takes one re-entrant lock.

    Callers that need a whole transaction serialized (more than one statement)
    hold ``FoundationDB.lock`` explicitly - see ``atomic_claim_job``.
    """

    def __init__(self, conn: sqlite3.Connection, lock) -> None:
        self._conn = conn
        self._lock = lock

    @property
    def row_factory(self):
        return self._conn.row_factory

    @row_factory.setter
    def row_factory(self, value) -> None:
        self._conn.row_factory = value

    def execute(self, *args, **kwargs):
        with self._lock:
            return self._conn.execute(*args, **kwargs)

    def executemany(self, *args, **kwargs):
        with self._lock:
            return self._conn.executemany(*args, **kwargs)

    def executescript(self, *args, **kwargs):
        with self._lock:
            return self._conn.executescript(*args, **kwargs)

    def cursor(self, *args, **kwargs):
        with self._lock:
            return self._conn.cursor(*args, **kwargs)

    def commit(self):
        with self._lock:
            return self._conn.commit()

    def rollback(self):
        with self._lock:
            return self._conn.rollback()

    def close(self):
        with self._lock:
            return self._conn.close()

    def __getattr__(self, name):
        # Anything else (isolation_level, total_changes, ...) passes through.
        return getattr(self._conn, name)


def _serialized(fn):
    """Run a whole ``FoundationDB`` operation under the shared connection lock.

    Statement-level locking (``_SerializedConnection``) stops the sqlite3
    statement-cache corruption, but a concurrent ``commit()`` also RESETS any
    cursor that is mid-read on the same connection - a SELECT could then return
    an empty result set for rows that are committed. Repository reads/writes are
    therefore atomic end to end (execute + fetch + commit) under one re-entrant
    lock. Nesting is expected and safe (e.g. ``upsert`` -> ``get``/``insert``,
    ``table_counts`` -> ``count``).
    """
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        with self.lock:
            return fn(self, *args, **kwargs)
    return wrapper


class FoundationDB:
    """SQLite-backed foundation store. Disposable by default.

    When no path is given the store creates a temp file **and owns it**: the file is removed when
    the store is closed and again at interpreter exit if nobody closed it. Before this, every
    ``create_app`` in the suite left one ``ns_foundation_*.db`` behind — 9,018 of them had
    accumulated in %TEMP% by 2026-11-09 (``reports/ty/defects.md`` D-001). A caller-supplied path
    is never touched: that file may be the real database.
    """

    def __init__(self, path: Optional[str] = None, *, schema: bool = True) -> None:
        owns_path = path is None
        if owns_path:
            fd, tmp = tempfile.mkstemp(prefix="ns_foundation_", suffix=".db")
            os.close(fd)
            path = tmp
        self.path = path
        self._owns_path = owns_path
        # One connection, one lock: every statement is serialized (see
        # _SerializedConnection); multi-statement transactions hold this lock.
        self.lock = threading.RLock()
        self.conn = _SerializedConnection(
            sqlite3.connect(path, check_same_thread=False), self.lock)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.execute("PRAGMA busy_timeout=5000")
        if owns_path:
            # Belt and braces: a process that forgets to close() still leaves nothing behind.
            atexit.register(_remove_quietly, path)
        if schema:
            self.ensure_schema()

    @_serialized
    def ensure_schema(self) -> None:
        for stmt in SQLITE_DDL:
            self.conn.execute(stmt)
        self.conn.commit()

    # -- generic helpers -------------------------------------------------------

    @_serialized
    def insert(self, table: str, row: dict) -> None:
        cols = list(row.keys())
        placeholders = ",".join("?" for _ in cols)
        col_sql = ",".join(cols)
        values = [_ser(row[c]) for c in cols]
        self.conn.execute(
            f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})", values
        )
        self.conn.commit()

    @_serialized
    def insert_ignore(self, table: str, row: dict, conflict_cols=("id",)) -> bool:
        """Idempotent insert: no-op on PK conflict (INSERT OR IGNORE)."""
        cols = list(row.keys())
        placeholders = ",".join("?" for _ in cols)
        col_sql = ",".join(cols)
        values = [_ser(row[c]) for c in cols]
        cur = self.conn.execute(
            f"INSERT OR IGNORE INTO {table} ({col_sql}) VALUES ({placeholders})",
            values)
        self.conn.commit()
        return cur.rowcount > 0

    @_serialized
    def insert_no_commit(self, table: str, row: dict) -> None:
        """INSERT inside the caller's transaction (no commit). The caller owns
        commit/rollback — used for atomic multi-write operations."""
        cols = list(row.keys())
        placeholders = ",".join("?" for _ in cols)
        col_sql = ",".join(cols)
        values = [_ser(row[c]) for c in cols]
        self.conn.execute(
            f"INSERT INTO {table} ({col_sql}) VALUES ({placeholders})", values)

    @_serialized
    def upsert(self, table: str, row: dict, pk_cols: Iterable[str]) -> None:
        pk = list(pk_cols)
        for p in pk:
            if p not in row:
                raise ValueError(f"missing pk column {p!r} for {table}")
        existing = self.get(table, {p: row[p] for p in pk})
        if existing:
            sets = [c for c in row.keys() if c not in pk]
            if sets:
                set_sql = ",".join(f"{c}=?" for c in sets)
                values = [_ser(row[c]) for c in sets]
                where = " AND ".join(f"{p}=?" for p in pk)
                self.conn.execute(
                    f"UPDATE {table} SET {set_sql} WHERE {where}",
                    values + [_ser(row[p]) for p in pk],
                )
                self.conn.commit()
        else:
            self.insert(table, row)

    @_serialized
    def get(self, table: str, where: dict) -> Optional[dict]:
        clause = " AND ".join(f"{k}=?" for k in where)
        cur = self.conn.execute(
            f"SELECT * FROM {table} WHERE {clause}", [_ser(v) for v in where.values()]
        )
        r = cur.fetchone()
        return dict(r) if r else None

    @_serialized
    def list(self, table: str, where: Optional[dict] = None, order_by: Optional[str] = None,
             limit: Optional[int] = None, offset: int = 0) -> list[dict]:
        sql = f"SELECT * FROM {table}"
        params: list[Any] = []
        if where:
            sql += " WHERE " + " AND ".join(f"{k}=?" for k in where)
            params += [_ser(v) for v in where.values()]
        if order_by:
            sql += f" ORDER BY {order_by}"
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params += [limit, offset]
        cur = self.conn.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    @_serialized
    def count(self, table: str) -> int:
        cur = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
        return int(cur.fetchone()[0])

    @_serialized
    def table_counts(self) -> dict:
        return {t: self.count(t) for t in _TABLE_ORDER}

    # -- atomic claim (1C-04/B05) ------------------------------------------
    # SQLite serializes writers (single-writer model), so a BEGIN IMMEDIATE
    # + conditional UPDATE is demonstrably equivalent to PostgreSQL's
    # FOR UPDATE SKIP LOCKED for the local/dev path. The row's state change
    # is the lock: exactly one worker observes the queued->leased transition.
    @_serialized
    def atomic_claim_job(self, *, worker_id: str, organization_id: str,
                         lease_seconds: int, now_iso: str, limit: int = 1) -> list[dict]:
        sql = (
            "SELECT jr.* FROM job_runs jr "
            "JOIN job_requests jq ON jq.id = jr.job_request_id "
            "WHERE jr.state = 'queued' AND jq.organization_id = ? "
            "AND (jr.scheduled_time IS NULL OR jr.scheduled_time <= ?) "
            "ORDER BY jr.priority ASC, jr.created_at ASC LIMIT ?"
        )
        # Hold the lock for the WHOLE transaction: BEGIN IMMEDIATE is
        # connection-scoped, so an interleaved second thread would otherwise
        # join (and commit) this transaction.
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                cur = self.conn.execute(sql, [organization_id, now_iso, limit])
                rows = [dict(r) for r in cur.fetchall()]
                claimed = []
                from datetime import datetime, timedelta, timezone
                exp = (datetime.now(timezone.utc) + timedelta(seconds=lease_seconds)).isoformat()
                for row in rows:
                    self.conn.execute(
                        "UPDATE job_runs SET state='leased', lease_owner=?, "
                        "lease_expiration=? WHERE id=? AND state='queued'",
                        [worker_id, exp, row["id"]])
                    row["state"] = "leased"
                    row["lease_owner"] = worker_id
                    row["lease_expiration"] = exp
                    claimed.append(row)
                self.conn.commit()
                return claimed
            except Exception:
                self.conn.rollback()
                raise

    @_serialized
    def release_lease(self, run_id: str, worker_id: str,
                      new_state: str = "queued", now_iso: Optional[str] = None) -> int:
        """Release a claimed run back to the queue (owner must match)."""
        cur = self.conn.execute(
            "UPDATE job_runs SET state=?, lease_owner=NULL, lease_expiration=NULL "
            "WHERE id=? AND lease_owner=?",
            [new_state, run_id, worker_id])
        self.conn.commit()
        return cur.rowcount

    @_serialized
    def expire_stale_leases(self, now_iso: str) -> int:
        """Mark runs whose lease expired as EXPIRED (recovery can re-queue)."""
        cur = self.conn.execute(
            "UPDATE job_runs SET state='expired' WHERE state='leased' "
            "AND lease_expiration IS NOT NULL AND lease_expiration < ?",
            [now_iso])
        self.conn.commit()
        return cur.rowcount

    @_serialized
    def close(self) -> None:
        self.conn.close()
        if getattr(self, "_owns_path", False):
            # Only after the connection is closed: Windows will not unlink an open file.
            _remove_quietly(self.path)


def _remove_quietly(path: Optional[str]) -> None:
    """Remove a temp database file, ignoring the races that make this best-effort.

    Called from close() and from atexit, so a second call must be harmless, and a failure (Windows
    still holding the handle, a file already gone) must never turn a clean shutdown into a crash.
    """
    try:
        if path:
            os.unlink(path)
    except OSError:
        pass


@contextmanager
def temp_db() -> Iterator[FoundationDB]:
    db = FoundationDB()
    try:
        yield db
    finally:
        db.close()
        try:
            Path(db.path).unlink(missing_ok=True)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Schema-equivalence validation (SQLite generated tables vs the SCHEMA spec)
# ---------------------------------------------------------------------------

def validate_sqlite_schema() -> dict:
    """Create an in-memory DB, apply the generated DDL, and compare the actual
    SQLite column set per table against the SCHEMA spec. Returns a report; raises
    if any table/column diverges. This proves the SQLite path matches the single
    source of truth (and therefore the Postgres DDL, which is generated from it).
    """
    con = sqlite3.connect(":memory:")
    try:
        for stmt in SQLITE_DDL:
            con.execute(stmt)
        report: dict[str, dict] = {}
        for table, cols in SCHEMA.items():
            expected = [c for c, _ in cols]
            actual = [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
            ok = expected == actual
            report[table] = {"expected": expected, "actual": actual, "match": ok}
            if not ok:
                raise AssertionError(
                    f"schema divergence in {table}: expected {expected}, actual {actual}"
                )
        return {"tables": len(SCHEMA), "all_match": True, "detail": report}
    finally:
        con.close()


def schema_equivalence_report() -> dict:
    """Structural equivalence: both SQLite and Postgres DDL are generated from the
    same SCHEMA, so the column set per table is identical by construction. We also
    verify the SQLite DDL matches SCHEMA and that the Postgres DDL text contains
    every table and column."""
    sqlite_check = validate_sqlite_schema()
    pg_text = postgres_ddl()
    missing = []
    for table, cols in SCHEMA.items():
        if f'"{table}"' not in pg_text:
            missing.append(f"table {table}")
        for name, _lt in cols:
            if f'"{name}"' not in pg_text:
                missing.append(f"{table}.{name}")
    return {
        "single_source_of_truth": "foundation/db.py:SCHEMA",
        "sqlite_validated": sqlite_check["all_match"],
        "postgres_ddl_generated": True,
        "postgres_missing_items": missing,
        "equivalent": sqlite_check["all_match"] and not missing,
        "type_mapping": {
            "id": {"sqlite": "TEXT", "postgres": "TEXT"},
            "text": {"sqlite": "TEXT", "postgres": "TEXT"},
            "int": {"sqlite": "INTEGER", "postgres": "BIGINT"},
            "real": {"sqlite": "REAL", "postgres": "DOUBLE PRECISION"},
            "money": {"sqlite": "REAL", "postgres": "NUMERIC"},
            "bool": {"sqlite": "INTEGER", "postgres": "BOOLEAN"},
            "json": {"sqlite": "TEXT", "postgres": "JSONB"},
            "ts": {"sqlite": "TEXT", "postgres": "TIMESTAMPTZ"},
        },
        "notes": [
            "JSON columns are written/read through explicit json.dumps/json.loads in the repository layer; behavior is identical on SQLite TEXT and Postgres JSONB.",
            "Booleans are serialized explicitly (0/1 on SQLite, native BOOLEAN on Postgres); no implicit coercion is relied upon.",
            "Timestamps are stored as ISO-8601 TEXT on SQLite and TIMESTAMPTZ on Postgres; comparisons/freshness are computed in Python, not in SQL.",
            "UNIQUE constraints on idempotency_key enforce idempotency at both backends (NULLs are allowed and not deduped, matching current behavior).",
        ],
    }