-- db/schema.sql
-- SQLite schema for Migration Data Quality Scanner
-- Star schema rooted at scans table; raw dataset rows are never stored.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT UNIQUE NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    app_version TEXT,
    config_hash TEXT,
    overall_score REAL,
    readiness_category TEXT,
    blocker_count INTEGER DEFAULT 0,
    high_count INTEGER DEFAULT 0,
    medium_count INTEGER DEFAULT 0,
    low_count INTEGER DEFAULT 0,
    total_issues INTEGER DEFAULT 0,
    dataset_count INTEGER DEFAULT 0,
    enabled_checks_json TEXT,
    ai_insights TEXT,
    warnings_json TEXT,
    affected_rows INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scan_datasets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    dataset_name TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    column_count INTEGER NOT NULL,
    duplicate_row_count INTEGER DEFAULT 0,
    duplicate_row_pct REAL DEFAULT 0.0,
    overall_null_pct REAL DEFAULT 0.0,
    size_bytes INTEGER,
    is_primary INTEGER DEFAULT 0,
    columns_summary_json TEXT
);

CREATE TABLE IF NOT EXISTS check_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    dataset_name TEXT NOT NULL,
    check_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    affected_count INTEGER DEFAULT 0,
    affected_pct REAL DEFAULT 0.0,
    details_json TEXT
);

CREATE TABLE IF NOT EXISTS scoring_factors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    dimension_name TEXT NOT NULL,
    score REAL NOT NULL,
    weight REAL NOT NULL,
    weighted_score REAL NOT NULL,
    explanation TEXT
);

CREATE TABLE IF NOT EXISTS relationship_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    parent_dataset TEXT NOT NULL,
    parent_key TEXT NOT NULL,
    child_dataset TEXT NOT NULL,
    child_key TEXT NOT NULL,
    total_child_records INTEGER NOT NULL,
    orphan_count INTEGER NOT NULL,
    orphan_pct REAL NOT NULL,
    severity TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    severity TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    dataset_name TEXT NOT NULL,
    affected_columns_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_scans_run_id ON scans(run_id);
CREATE INDEX IF NOT EXISTS idx_scans_started_at ON scans(started_at);
CREATE INDEX IF NOT EXISTS idx_scan_datasets_scan_id ON scan_datasets(scan_id);
CREATE INDEX IF NOT EXISTS idx_check_results_scan_id ON check_results(scan_id);
CREATE INDEX IF NOT EXISTS idx_scoring_factors_scan_id ON scoring_factors(scan_id);
CREATE INDEX IF NOT EXISTS idx_relationship_results_scan_id ON relationship_results(scan_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_scan_id ON recommendations(scan_id);
