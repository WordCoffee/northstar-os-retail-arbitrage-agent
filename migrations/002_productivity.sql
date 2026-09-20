-- Phase F/S9 — Postgres migration 002: productivity tables
-- (invites + support queue + credit ledger). Mirrors invites.py / support.py /
-- credit_ledger.py entry schema. NOT APPLIED (see MIGRATION_GUIDE.md).

BEGIN;

CREATE TABLE IF NOT EXISTS invites (
    code       TEXT PRIMARY KEY,               -- invite_<hex>
    cohort     TEXT NOT NULL,                  -- COHORT_OPS.md cohort ids
    email      TEXT,
    created_by TEXT NOT NULL DEFAULT 'operator',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ NOT NULL,
    redeemed_at TIMESTAMPTZ,
    used_by    TEXT
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id         TEXT PRIMARY KEY,               -- tkt_<hex>
    account_id TEXT NOT NULL,
    subject    TEXT NOT NULL,
    body       TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','resolved')),
    assigned_to TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON support_tickets (status);

CREATE TABLE IF NOT EXISTS credit_ledger_entries (
    entry_id        TEXT PRIMARY KEY,          -- cle_<hex>
    account_id      TEXT NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('grant','reserve','commit','release','adjust')),
    credit_class    TEXT NOT NULL DEFAULT 'compute',
    amount          INTEGER NOT NULL,
    action          TEXT,
    idempotency_key TEXT UNIQUE,
    reservation_id  TEXT,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    balance_after   INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_ledger_account ON credit_ledger_entries (account_id, credit_class);

COMMIT;