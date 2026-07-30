PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    display_name TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    feature TEXT NOT NULL,
    input_preview TEXT NOT NULL DEFAULT '',
    output_preview TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    error TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    metadata TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_activity_user_created
ON activity_logs(user_id, created_at DESC);

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

CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    source_application_id INTEGER NOT NULL UNIQUE,
    current_version_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (source_application_id) REFERENCES job_applications(id) ON DELETE CASCADE,
    FOREIGN KEY (current_version_id) REFERENCES resume_versions(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS resume_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    parent_version_id INTEGER,
    version_number INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_version_id) REFERENCES resume_versions(id) ON DELETE SET NULL,
    UNIQUE (resume_id, version_number)
);

CREATE TABLE IF NOT EXISTS resume_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_id INTEGER NOT NULL,
    resume_version_id INTEGER NOT NULL,
    section_key TEXT NOT NULL,
    source_text TEXT NOT NULL,
    suggested_text TEXT NOT NULL,
    reason TEXT NOT NULL,
    jd_evidence TEXT NOT NULL DEFAULT '',
    resume_evidence TEXT NOT NULL DEFAULT '',
    risk_level TEXT NOT NULL,
    clarification_required INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending',
    generation_number INTEGER NOT NULL DEFAULT 1,
    prompt_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    decided_at TEXT,
    FOREIGN KEY (application_id) REFERENCES job_applications(id) ON DELETE CASCADE,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS resume_suggestion_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    suggestion_id INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    previous_value TEXT NOT NULL DEFAULT '{}',
    new_value TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY (suggestion_id) REFERENCES resume_suggestions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_resumes_user_updated
ON resumes(user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_resume_versions_resume_number
ON resume_versions(resume_id, version_number DESC);

CREATE INDEX IF NOT EXISTS idx_resume_suggestions_application_version
ON resume_suggestions(application_id, resume_version_id, status, id);

CREATE INDEX IF NOT EXISTS idx_resume_suggestion_events_suggestion
ON resume_suggestion_events(suggestion_id, id DESC);

CREATE TABLE IF NOT EXISTS resume_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    resume_id INTEGER NOT NULL,
    resume_version_id INTEGER NOT NULL,
    template_key TEXT NOT NULL CHECK (template_key IN ('professional', 'minimal_ats')),
    format TEXT NOT NULL CHECK (format IN ('docx', 'pdf')),
    paper_size TEXT NOT NULL CHECK (paper_size IN ('a4', 'letter')),
    language TEXT NOT NULL CHECK (language IN ('zh', 'en', 'bilingual')),
    status TEXT NOT NULL CHECK (status IN ('pending', 'generating', 'ready', 'failed', 'deleted')),
    filename TEXT NOT NULL,
    object_key TEXT,
    source_content_hash TEXT NOT NULL,
    structured_content TEXT NOT NULL,
    structure_hash TEXT NOT NULL,
    content_hash TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_at TEXT,
    deleted_at TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (resume_id) REFERENCES resumes(id) ON DELETE CASCADE,
    FOREIGN KEY (resume_version_id) REFERENCES resume_versions(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_resume_exports_user_created
ON resume_exports(user_id, created_at DESC, id DESC);

CREATE INDEX IF NOT EXISTS idx_resume_exports_version_created
ON resume_exports(resume_version_id, created_at DESC, id DESC);
