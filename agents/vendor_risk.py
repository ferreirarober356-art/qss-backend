from sqlalchemy import text
from agents.db import engine

# Simple, explainable scoring (gov-friendly)
# HIGH=5 points, MEDIUM=2 points, LOW=1 point
WEIGHTS = {"HIGH": 5, "MEDIUM": 2, "LOW": 1}

def compute_vendor_risk():
    with engine.begin() as conn:
        # Aggregate alerts by vendor_id where entity_type='VENDOR'
        rows = conn.execute(text("""
            SELECT entity_id AS vendor_id,
                   SUM(CASE WHEN severity='HIGH' THEN 1 ELSE 0 END) AS high_cnt,
                   SUM(CASE WHEN severity='MEDIUM' THEN 1 ELSE 0 END) AS med_cnt,
                   SUM(CASE WHEN severity='LOW' THEN 1 ELSE 0 END) AS low_cnt
            FROM alerts
            WHERE entity_type='VENDOR'
            GROUP BY entity_id
        """)).mappings().all()

        upserts = 0
        for r in rows:
            vendor_id = str(r["vendor_id"])
            high_cnt = int(r["high_cnt"] or 0)
            med_cnt = int(r["med_cnt"] or 0)
            low_cnt = int(r["low_cnt"] or 0)

            score = high_cnt * WEIGHTS["HIGH"] + med_cnt * WEIGHTS["MEDIUM"] + low_cnt * WEIGHTS["LOW"]

            conn.execute(text("""
                INSERT INTO vendor_risk_scores (vendor_id, risk_score, high_alerts, med_alerts, low_alerts, last_updated)
                VALUES (:vendor_id, :risk_score, :high_alerts, :med_alerts, :low_alerts, NOW())
                ON CONFLICT (vendor_id) DO UPDATE
                SET risk_score = EXCLUDED.risk_score,
                    high_alerts = EXCLUDED.high_alerts,
                    med_alerts = EXCLUDED.med_alerts,
                    low_alerts = EXCLUDED.low_alerts,
                    last_updated = NOW()
            """), {
                "vendor_id": vendor_id,
                "risk_score": score,
                "high_alerts": high_cnt,
                "med_alerts": med_cnt,
                "low_alerts": low_cnt,
            })
            upserts += 1

        return {"vendor_rows": len(rows), "vendor_upserts": upserts}
