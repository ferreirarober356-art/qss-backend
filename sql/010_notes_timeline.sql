CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS analyst_notes (
    note_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT NOT NULL,
    author TEXT NOT NULL,
    content TEXT NOT NULL,
    tags TEXT[] DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analyst_notes_case_id
ON analyst_notes(case_id);

CREATE INDEX IF NOT EXISTS idx_analyst_notes_created_at
ON analyst_notes(created_at DESC);

CREATE TABLE IF NOT EXISTS case_timeline (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    description TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'system',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_case_timeline_case_id
ON case_timeline(case_id);

CREATE INDEX IF NOT EXISTS idx_case_timeline_created_at
ON case_timeline(created_at DESC);
