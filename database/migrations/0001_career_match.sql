PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS job_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    company_name TEXT NOT NULL DEFAULT '',
    job_title TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    job_description TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'zh',
    status TEXT NOT NULL DEFAULT 'ready',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resume_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL UNIQUE,
    source_type TEXT NOT NULL,
    original_filename TEXT,
    extracted_text TEXT NOT NULL DEFAULT '',
    content_hash TEXT NOT NULL DEFAULT '',
    parse_status TEXT NOT NULL,
    parse_error TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (application_id) REFERENCES job_applications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS match_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    overall_alignment TEXT,
    summary TEXT NOT NULL DEFAULT '',
    limitations TEXT NOT NULL DEFAULT '[]',
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (application_id) REFERENCES job_applications(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS match_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    jd_requirement TEXT NOT NULL,
    resume_evidence TEXT NOT NULL DEFAULT '',
    explanation TEXT NOT NULL,
    confidence_level TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (analysis_id) REFERENCES match_analyses(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_job_applications_user_updated
ON job_applications(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_match_analyses_application_created
ON match_analyses(application_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS idx_match_analyses_one_active
ON match_analyses(application_id) WHERE status = 'analyzing';
CREATE INDEX IF NOT EXISTS idx_match_items_analysis_category
ON match_items(analysis_id, category, sort_order);
