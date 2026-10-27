-- Chrome Connect browser jobs protocol (P6-T1)
-- Tables: browser_jobs, browser_evidence

CREATE TABLE IF NOT EXISTS browser_jobs (
    id TEXT PRIMARY KEY,
    org_id TEXT NOT NULL DEFAULT 'default',
    site TEXT NOT NULL,
    task_type TEXT NOT NULL,
    params_json TEXT NOT NULL DEFAULT '{}',
    state TEXT NOT NULL DEFAULT 'QUEUED',
    needs_owner_reason TEXT,
    created_at TEXT NOT NULL,
    claimed_by TEXT,
    claimed_at TEXT,
    evidence_ref TEXT,
    error_reason TEXT,
    step_count INTEGER NOT NULL DEFAULT 0,
    source TEXT NOT NULL DEFAULT 'synthetic'
);

CREATE TABLE IF NOT EXISTS browser_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    url TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    screenshot_sha256 TEXT,
    extracted_json TEXT NOT NULL DEFAULT '{}',
    provenance TEXT NOT NULL DEFAULT 'OBSERVED',
    selector_version TEXT,
    confidence REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'OK',
    FOREIGN KEY (job_id) REFERENCES browser_jobs(id)
);

CREATE INDEX IF NOT EXISTS idx_browser_jobs_state ON browser_jobs(state);
CREATE INDEX IF NOT EXISTS idx_browser_jobs_site ON browser_jobs(site);
CREATE INDEX IF NOT EXISTS idx_browser_jobs_org ON browser_jobs(org_id);
CREATE INDEX IF NOT EXISTS idx_browser_evidence_job ON browser_evidence(job_id);
