CREATE TABLE IF NOT EXISTS response_actions (
    response_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    target TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
    requested_by TEXT NOT NULL DEFAULT 'ai-engine',
    approved_by TEXT,
    execution_result JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_response_actions_case_id
ON response_actions(case_id);

CREATE INDEX IF NOT EXISTS idx_response_actions_status
ON response_actions(status);
