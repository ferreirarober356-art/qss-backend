CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 1) Cases
CREATE TABLE IF NOT EXISTS cases_mgmt (
  case_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT,
  priority TEXT NOT NULL DEFAULT 'MEDIUM',  -- LOW/MEDIUM/HIGH/CRITICAL
  status TEXT NOT NULL DEFAULT 'OPEN',      -- OPEN/ESCALATED/CLOSED
  created_by TEXT NOT NULL DEFAULT 'system',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cases_mgmt_status ON cases_mgmt(status);
CREATE INDEX IF NOT EXISTS idx_cases_mgmt_created_at ON cases_mgmt(created_at DESC);

-- 2) Link alerts to cases (many-to-many)
CREATE TABLE IF NOT EXISTS case_alerts (
  case_id UUID NOT NULL REFERENCES cases_mgmt(case_id) ON DELETE CASCADE,
  alert_id BIGINT NOT NULL REFERENCES alerts(alert_id) ON DELETE CASCADE,
  added_by TEXT NOT NULL DEFAULT 'system',
  added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (case_id, alert_id)
);

CREATE INDEX IF NOT EXISTS idx_case_alerts_alert_id ON case_alerts(alert_id);

-- 3) Alert actions (immutable audit trail)
CREATE TABLE IF NOT EXISTS alert_actions (
  action_id BIGSERIAL PRIMARY KEY,
  alert_id BIGINT NOT NULL REFERENCES alerts(alert_id) ON DELETE CASCADE,
  actor TEXT NOT NULL,                      -- username/email/agent name
  action TEXT NOT NULL,                     -- ACK/ESCALATE/DISMISS/NOTE/ATTACH_CASE/DETACH_CASE
  detail JSONB NOT NULL DEFAULT '{}'::jsonb, -- arbitrary payload
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_alert_actions_alert_id ON alert_actions(alert_id, created_at DESC);

-- Optional: simple review status on alert (fast filtering in UI)
ALTER TABLE alerts
  ADD COLUMN IF NOT EXISTS review_status TEXT NOT NULL DEFAULT 'OPEN'; -- OPEN/ESCALATED/DISMISSED/CLOSED

CREATE INDEX IF NOT EXISTS idx_alerts_review_status ON alerts(review_status);

-- Trigger to keep cases_mgmt.updated_at current
CREATE OR REPLACE FUNCTION set_cases_mgmt_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_cases_mgmt_updated_at ON cases_mgmt;
CREATE TRIGGER trg_cases_mgmt_updated_at
BEFORE UPDATE ON cases_mgmt
FOR EACH ROW
EXECUTE FUNCTION set_cases_mgmt_updated_at();

