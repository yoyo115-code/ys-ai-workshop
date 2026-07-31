PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS daily_usage (
    user_id INTEGER NOT NULL,
    usage_date TEXT NOT NULL,
    usage_type TEXT NOT NULL CHECK (
        usage_type IN (
            'career_analysis',
            'suggestion_generation',
            'suggestion_regeneration',
            'resume_export'
        )
    ),
    used_count INTEGER NOT NULL DEFAULT 0 CHECK (used_count >= 0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, usage_date, usage_type),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_daily_usage_date
ON daily_usage(usage_date, usage_type);
