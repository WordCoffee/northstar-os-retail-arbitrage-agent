"""Chat core schema (S1) — additive tables for the Simple-mode Master Brain chat.

Kept as a standalone constant so BOTH the data layer's shared DDL (SQLite +
Postgres) and the offline unit tests consume ONE source of truth. The only
SQLite-ism is the `datetime('now')` default, which data_layer already
translates for Postgres. This module imports nothing.
"""

CHAT_TABLES_SQL = """
            -- Chat core (S1): Simple-mode Master Brain chat. ADDITIVE ONLY:
            -- no ds_* table is touched and no existing column is altered.
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                title TEXT DEFAULT 'New chat',
                ds_project_id TEXT,
                mode TEXT DEFAULT 'simple',      -- session affinity with the shell mode
                model TEXT,
                focus_json TEXT,                 -- JSON: focus filters (content type, platform, brand, tone)
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_chat_sessions_account ON chat_sessions(account_id);

            CREATE TABLE IF NOT EXISTS chat_messages (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,              -- user | assistant | system
                content TEXT DEFAULT '',
                thinking TEXT DEFAULT '',        -- separated reasoning stream (S1)
                parts_json TEXT,                 -- JSON: ordered parts [{type:'thinking'|'text'|'tool', ...}]
                model TEXT,
                usage_json TEXT,                 -- JSON: status + token counts (provider-reported only)
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_chat_messages_account ON chat_messages(account_id);

            CREATE TABLE IF NOT EXISTS chat_tool_calls (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                message_id TEXT,
                name TEXT NOT NULL,
                args_json TEXT,
                result_json TEXT,
                status TEXT DEFAULT 'queued',    -- queued | running | done | error | cancelled
                started_at TEXT,
                ended_at TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_chat_tool_calls_session ON chat_tool_calls(session_id);

            CREATE TABLE IF NOT EXISTS chat_attachments (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                message_id TEXT,
                asset_id TEXT,                   -- ds_assets id
                kind TEXT,
                url TEXT,
                provenance_json TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_chat_attachments_message ON chat_attachments(message_id);

            -- Tool Execution Gateway audit (V3 REA inject): every tool attempt an
            -- agent makes is logged here, allowed AND denied. Append-only.
            CREATE TABLE IF NOT EXISTS tool_audit (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                tool TEXT NOT NULL,
                decision TEXT NOT NULL,         -- allowed | executed | denied
                reason TEXT,
                detail TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_tool_audit_account ON tool_audit(account_id);

            -- Session lineage (V3 S5 fork/rewind): a child session records the
            -- parent it was branched from and the message it branched at. The
            -- parent is never mutated — rewind is non-destructive. Additive.
            CREATE TABLE IF NOT EXISTS chat_session_forks (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                session_id TEXT NOT NULL,        -- the new (child) session
                parent_session_id TEXT NOT NULL,
                forked_from_message_id TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_chat_session_forks_child ON chat_session_forks(session_id);
        """
