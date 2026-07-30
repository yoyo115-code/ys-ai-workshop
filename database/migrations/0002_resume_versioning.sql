PRAGMA foreign_keys = ON;

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
