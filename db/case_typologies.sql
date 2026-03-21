CREATE TABLE IF NOT EXISTS case_typologies (
  case_id INT REFERENCES cases(case_id) ON DELETE CASCADE,
  typology TEXT NOT NULL,          -- e.g., 'kickbacks', 'overbilling', 'bid_rigging'
  confidence NUMERIC NOT NULL,     -- 0..1
  evidence TEXT DEFAULT '',        -- brief excerpt/keywords
  created_at TIMESTAMP DEFAULT NOW(),
  PRIMARY KEY(case_id, typology)
);

CREATE INDEX IF NOT EXISTS idx_case_typologies_typology ON case_typologies(typology);
