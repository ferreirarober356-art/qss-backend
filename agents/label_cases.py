from sqlalchemy import text
from agents.db import engine
from agents.typologies import classify

def main(limit: int = 500):
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT case_id, title, COALESCE(body_text,'') AS body_text
            FROM cases
            ORDER BY updated_at DESC
            LIMIT :limit
        """), {"limit": limit}).mappings().all()

    inserted = 0
    for r in rows:
        case_id = int(r["case_id"])
        title = r["title"] or ""
        body = r["body_text"] or ""

        matches = classify(title, body)
        if not matches:
            continue

        with engine.begin() as conn:
            for m in matches:
                conn.execute(text("""
                    INSERT INTO case_typologies (case_id, typology, confidence, evidence)
                    VALUES (:case_id, :typology, :confidence, :evidence)
                    ON CONFLICT (case_id, typology) DO UPDATE
                    SET confidence = EXCLUDED.confidence,
                        evidence = EXCLUDED.evidence
                """), {
                    "case_id": case_id,
                    "typology": m.typology,
                    "confidence": m.confidence,
                    "evidence": m.evidence,
                })
                inserted += 1

    print({"labeled_rows": len(rows), "typology_upserts": inserted})

if __name__ == "__main__":
    main()
