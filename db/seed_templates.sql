-- KICKBACKS / PROCUREMENT: buyer-vendor dependency (single employee drives most spend)
INSERT INTO detector_templates (typology, name, description, severity, sql_query)
VALUES (
  'kickbacks',
  'Single buyer dominates vendor spend',
  'Flags vendors where a single employee accounts for >=80% of spend (possible dependency/collusion signal).',
  'HIGH',
  $SQL$
  SELECT
    'VENDOR'::text AS entity_type,
    vendor_id::text AS entity_id,
    ('Single buyer ' || employee_id || ' drives ' || ROUND(100.0*buyer_spend/vendor_spend,1) || '% of spend') AS reason,
    LEAST(100.0, 60.0 + 40.0*(buyer_spend/vendor_spend)) AS score
  FROM (
    SELECT
      vendor_id,
      employee_id,
      SUM(amount) AS buyer_spend,
      SUM(SUM(amount)) OVER (PARTITION BY vendor_id) AS vendor_spend
    FROM purchase_orders
    GROUP BY vendor_id, employee_id
  ) t
  WHERE vendor_spend > 0
    AND buyer_spend/vendor_spend >= 0.80
  $SQL$
)
ON CONFLICT (typology, name) DO NOTHING;

-- FALSE_CLAIMS_ACT / OVERBILLING: invoice exceeds PO by >10% (you already have this, but as a reusable template)
INSERT INTO detector_templates (typology, name, description, severity, sql_query)
VALUES (
  'false_claims_act',
  'Invoice exceeds PO by >10%',
  'Flags invoices that exceed approved PO amount by more than 10%.',
  'HIGH',
  $SQL$
  SELECT
    'INVOICE'::text AS entity_type,
    i.invoice_id::text AS entity_id,
    'Invoice exceeds PO by >10%'::text AS reason,
    80.0::numeric AS score
  FROM invoices i
  JOIN purchase_orders p ON p.po_id = i.po_id
  WHERE i.amount > p.amount * 1.10
  $SQL$
)
ON CONFLICT (typology, name) DO NOTHING;

-- PROCUREMENT_FRAUD: after-hours PO creation (simple timing anomaly)
INSERT INTO detector_templates (typology, name, description, severity, sql_query)
VALUES (
  'procurement_fraud',
  'After-hours PO creation',
  'Flags POs created between 00:00-04:59 local time (unusual activity window).',
  'MEDIUM',
  $SQL$
  SELECT
    'PO'::text AS entity_type,
    po_id::text AS entity_id,
    'PO created during 00:00-04:59 window'::text AS reason,
    55.0::numeric AS score
  FROM purchase_orders
  WHERE EXTRACT(HOUR FROM created_at) BETWEEN 0 AND 4
  $SQL$
)
ON CONFLICT (typology, name) DO NOTHING;

-- FOREIGN_SOURCING: repeated foreign shipping or vendor marker (placeholder for later enrichment)
INSERT INTO detector_templates (typology, name, description, severity, sql_query)
VALUES (
  'foreign_sourcing',
  'Vendor has foreign sourcing indicator',
  'Placeholder: flags vendors with ID pattern (demo until enrichment adds country-of-origin fields).',
  'LOW',
  $SQL$
  SELECT
    'VENDOR'::text AS entity_type,
    vendor_id::text AS entity_id,
    'Foreign sourcing indicator (demo rule)'::text AS reason,
    25.0::numeric AS score
  FROM purchase_orders
  WHERE vendor_id ILIKE 'F%%'
  $SQL$
)
ON CONFLICT (typology, name) DO NOTHING;

