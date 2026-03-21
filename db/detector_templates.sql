CREATE TABLE IF NOT EXISTS detector_templates (
  template_id SERIAL PRIMARY KEY,
  typology TEXT NOT NULL,
  name TEXT NOT NULL,
  description TEXT DEFAULT '',
  severity TEXT NOT NULL DEFAULT 'MEDIUM',
  sql_query TEXT NOT NULL,               -- must return: entity_type, entity_id, reason, score
  is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(typology, name)
);

CREATE INDEX IF NOT EXISTS idx_detector_templates_typology ON detector_templates(typology);
