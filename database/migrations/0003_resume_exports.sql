PRAGMA foreign_keys = ON;

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
