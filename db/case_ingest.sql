CREATE TABLE IF NOT EXISTS case_sources (
  source_id SERIAL PRIMARY KEY,
  source_name TEXT NOT NULL,
  source_url TEXT NOT NULL,
  source_type TEXT NOT NULL, -- 'rss' | 'html'
  created_at TIMESTAMP DEFAULT NOW(),
  UNIQUE(source_name, source_url)
);

CREATE TABLE IF NOT EXISTS cases (
  case_id SERIAL PRIMARY KEY,
  source_id INT REFERENCES case_sources(source_id) ON DELETE SET NULL,
  title TEXT NOT NULL,
  published_date DATE,
  url TEXT NOT NULL UNIQUE,
  summary TEXT DEFAULT '',
  body_text TEXT DEFAULT '',
  agency TEXT DEFAULT '',
  case_type TEXT DEFAULT '',   -- e.g. 'FCA', 'procurement', etc.
  amount_usd NUMERIC,          -- extracted if present
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS case_tags (
  case_id INT REFERENCES cases(case_id) ON DELETE CASCADE,
  tag TEXT NOT NULL,
  PRIMARY KEY(case_id, tag)
);

CREATE TABLE IF NOT EXISTS case_entities (
  case_id INT REFERENCES cases(case_id) ON DELETE CASCADE,
  entity_type TEXT NOT NULL,   -- 'person' | 'org' | 'vendor' | 'agency'
  entity_name TEXT NOT NULL,
  PRIMARY KEY(case_id, entity_type, entity_name)
);

CREATE INDEX IF NOT EXISTS idx_cases_published_date ON cases(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_cases_amount ON cases(amount_usd DESC NULLS LAST);
