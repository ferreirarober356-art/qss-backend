import os
from sqlalchemy import create_engine, text

DB_URL = os.environ.get(
    "SENTINEL_DB_URL",
    "postgresql://aipuser:aip_pass_change_me@localhost:5432/aipdb",
)

engine = create_engine(DB_URL, pool_pre_ping=True)

def upsert_source(source_name: str, source_url: str, source_type: str) -> int:
    with engine.begin() as conn:
        row = conn.execute(
            text("""
                INSERT INTO case_sources (source_name, source_url, source_type)
                VALUES (:n, :u, :t)
                ON CONFLICT (source_name, source_url) DO UPDATE
                SET source_type = EXCLUDED.source_type
                RETURNING source_id
            """),
            {"n": source_name, "u": source_url, "t": source_type},
        ).mappings().first()
        return int(row["source_id"])

def upsert_case(payload: dict) -> bool:
    """
    Returns True if inserted new, False if updated existing.
    """
    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT case_id FROM cases WHERE url=:url"),
            {"url": payload["url"]},
        ).first()

        if existing is None:
            conn.execute(text("""
                INSERT INTO cases
                (source_id, title, published_date, url, summary, body_text, agency, case_type, amount_usd, updated_at)
                VALUES
                (:source_id, :title, :published_date, :url, :summary, :body_text, :agency, :case_type, :amount_usd, NOW())
            """), payload)
            return True

        conn.execute(text("""
            UPDATE cases
            SET source_id=:source_id,
                title=:title,
                published_date=:published_date,
                summary=:summary,
                body_text=:body_text,
                agency=:agency,
                case_type=:case_type,
                amount_usd=:amount_usd,
                updated_at=NOW()
            WHERE url=:url
        """), payload)
        return False

def replace_tags(url: str, tags: list[str]):
    with engine.begin() as conn:
        cid = conn.execute(text("SELECT case_id FROM cases WHERE url=:u"), {"u": url}).scalar()
        if cid is None:
            return
        conn.execute(text("DELETE FROM case_tags WHERE case_id=:cid"), {"cid": cid})
        for t in sorted(set(tags)):
            conn.execute(text("INSERT INTO case_tags (case_id, tag) VALUES (:cid, :t)"), {"cid": cid, "t": t})

def replace_entities(url: str, entities: list[tuple[str, str]]):
    with engine.begin() as conn:
        cid = conn.execute(text("SELECT case_id FROM cases WHERE url=:u"), {"u": url}).scalar()
        if cid is None:
            return
        conn.execute(text("DELETE FROM case_entities WHERE case_id=:cid"), {"cid": cid})
        for etype, name in sorted(set(entities)):
            conn.execute(
                text("INSERT INTO case_entities (case_id, entity_type, entity_name) VALUES (:cid, :e, :n)"),
                {"cid": cid, "e": etype, "n": name.strip()},
            )
