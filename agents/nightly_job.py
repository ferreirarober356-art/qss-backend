import json
import datetime as dt
from sqlalchemy import text

from agents.daily_brief import main as brief_main()
from agents.run_ingest import main as ingest_main
from agents.label_cases import main as label_main
from agents.vendor_risk import compute_vendor_risk
from agents.db import engine

def run_rules_via_db():
    """
    Runs enabled detector_templates directly (same logic as /rules/run),
    so the nightly job works even if FastAPI isn't running.
    """
    import hashlib

    created = 0
    checked = 0

    with engine.begin() as conn:
        templates = conn.execute(text("""
            SELECT template_id, severity, sql_query
            FROM detector_templates
            WHERE is_enabled = TRUE
        """)).mappings().all()

        for t in templates:
            checked += 1
            rows = conn.execute(text(t["sql_query"])).mappings().all()

            for r in rows:
                entity_type = str(r["entity_type"])
                entity_id = str(r["entity_id"])
                reason = str(r["reason"])
                score = float(r["score"])
                severity = str(t["severity"])

                fp_src = f"{entity_type}|{entity_id}|{reason}"
                fingerprint = hashlib.sha256(fp_src.encode("utf-8")).hexdigest()

                conn.execute(text("""
                    INSERT INTO alerts (entity_type, entity_id, severity, reason, score, fingerprint)
                    VALUES (:entity_type, :entity_id, :severity, :reason, :score, :fingerprint)
                    ON CONFLICT (fingerprint) DO NOTHING
                """), {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "severity": severity,
                    "reason": reason,
                    "score": score,
                    "fingerprint": fingerprint,
                })
                created += 1

    return {"templates_checked": checked, "alerts_attempted": created}

def write_daily_report(payload: dict):
    date_str = dt.datetime.now().strftime("%Y-%m-%d")
    path = f"reports/daily_{date_str}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, default=str)
    return path

def top_summary():
    with engine.begin() as conn:
        top_vendors = conn.execute(text("""
            SELECT vendor_id, risk_score, high_alerts, med_alerts, low_alerts
            FROM vendor_risk_scores
            ORDER BY risk_score DESC
            LIMIT 10
        """)).mappings().all()

        top_alerts = conn.execute(text("""
            SELECT alert_id, entity_type, entity_id, severity, reason, score, created_at
            FROM alerts
            ORDER BY created_at DESC
            LIMIT 20
        """)).mappings().all()

    return {
        "top_vendors": [dict(r) for r in top_vendors],
        "recent_alerts": [dict(r) for r in top_alerts],
    }

def main():
    # Ensure reports dir exists
    import os
    os.makedirs("reports", exist_ok=True)

    started = dt.datetime.now()

    # 1) ingest
    ingest_main()

    # 2) label typologies
    label_main(limit=500)

    # 3) run rule templates -> alerts
    rules = run_rules_via_db()

    # 4) compute vendor risk
    risk = compute_vendor_risk()

    # 5) compile summary report
    summary = top_summary()

    finished = dt.datetime.now()
    payload = {
        "started_at": started,
        "finished_at": finished,
        "duration_seconds": (finished - started).total_seconds(),
        "rules": rules,
        "risk": risk,
        "summary": summary,
    }

    report_path = write_daily_report(payload)
    print({"ok": True, "report": report_path, **payload})

if __name__ == "__main__":
    main()
