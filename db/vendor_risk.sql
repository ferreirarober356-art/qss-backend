CREATE TABLE IF NOT EXISTS vendor_risk_scores (
  vendor_id TEXT PRIMARY KEY,
  risk_score NUMERIC NOT NULL DEFAULT 0,
  high_alerts INT NOT NULL DEFAULT 0,
  med_alerts INT NOT NULL DEFAULT 0,
  low_alerts INT NOT NULL DEFAULT 0,
  last_updated TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vendor_risk_score ON vendor_risk_scores(risk_score DESC);
