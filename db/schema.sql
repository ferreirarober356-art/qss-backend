CREATE TABLE IF NOT EXISTS purchase_orders (
  po_id TEXT PRIMARY KEY,
  vendor_id TEXT,
  employee_id TEXT,
  amount NUMERIC,
  created_at TIMESTAMP,
  status TEXT,
  last_modified_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
  invoice_id TEXT PRIMARY KEY,
  po_id TEXT,
  vendor_id TEXT,
  amount NUMERIC,
  invoice_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS alerts (
  alert_id SERIAL PRIMARY KEY,
  entity_type TEXT,
  entity_id TEXT,
  severity TEXT,
  reason TEXT,
  score NUMERIC,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  status TEXT DEFAULT 'OPEN'
);
