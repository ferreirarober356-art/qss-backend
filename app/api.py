import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text

app = FastAPI(title="Sentinel AIP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATABASE_URL = os.getenv("DATABASE_URL")
engine = None
engine_error = None

if DATABASE_URL:
    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    except Exception as e:
        engine_error = str(e)


class CaseActionRequest(BaseModel):
    action: str
    actor: str = "analyst"


def init_db():
    global engine_error
    if not engine:
        return

    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS cases_mgmt (
                    case_id SERIAL PRIMARY KEY,
                    title TEXT NOT NULL,
                    priority TEXT DEFAULT 'MEDIUM',
                    status TEXT DEFAULT 'OPEN',
                    created_by TEXT DEFAULT 'system',
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))

            result = conn.execute(text("SELECT COUNT(*) FROM cases_mgmt"))
            count = result.scalar()

            if count == 0:
                conn.execute(text("""
                    INSERT INTO cases_mgmt (title, priority, status, created_by)
                    VALUES
                    ('Initial QSS Case', 'HIGH', 'OPEN', 'system'),
                    ('Threat Hunt Review', 'MEDIUM', 'OPEN', 'analyst')
                """))
    except Exception as e:
        engine_error = str(e)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return {"service": "qss-backend", "status": "running"}


@app.get("/health")
def health():
    return {
        "ok": True,
        "status": "ok",
        "has_database_url": bool(DATABASE_URL),
        "engine_ready": bool(engine),
        "engine_error": engine_error,
    }


@app.get("/debug/env")
def debug_env():
    return {
        "has_database_url": bool(DATABASE_URL),
        "database_url_prefix": (DATABASE_URL or "")[:24],
        "engine_ready": bool(engine),
        "engine_error": engine_error,
    }


@app.get("/cases/list")
def list_cases(limit: int = 50):
    if not engine:
        return {
            "cases": [],
            "count": 0,
            "status": "no_database",
            "engine_error": engine_error,
        }

    try:
        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT
                    case_id::text,
                    title,
                    priority,
                    status,
                    created_by,
                    created_at,
                    updated_at
                FROM cases_mgmt
                ORDER BY updated_at DESC
                LIMIT :limit
            """), {"limit": limit}).mappings().all()

            return {"cases": list(rows), "count": len(rows), "status": "ok"}
    except Exception as e:
        return {"cases": [], "count": 0, "status": "db_error", "detail": str(e)}


@app.get("/cases/{case_id}")
def get_case(case_id: str):
    if not engine:
        return {"error": "no_database", "engine_error": engine_error}

    try:
        with engine.begin() as conn:
            row = conn.execute(text("""
                SELECT
                    case_id::text,
                    title,
                    priority,
                    status,
                    created_by,
                    created_at,
                    updated_at
                FROM cases_mgmt
                WHERE case_id::text = :case_id
            """), {"case_id": case_id}).mappings().first()

            if not row:
                return {"error": "not_found"}

            return dict(row)
    except Exception as e:
        return {"error": "db_error", "detail": str(e)}


@app.post("/cases/{case_id}/action")
def case_action(case_id: str, req: CaseActionRequest):
    if not engine:
        return {"ok": False, "error": "no_database", "engine_error": engine_error}

    action = req.action.upper().strip()
    mapping = {
        "ACKNOWLEDGE": "ACKNOWLEDGED",
        "ESCALATE": "ESCALATED",
        "CLOSE": "CLOSED",
    }

    if action not in mapping:
        return {"ok": False, "error": "invalid_action"}

    try:
        with engine.begin() as conn:
            updated = conn.execute(text("""
                UPDATE cases_mgmt
                SET
                    status = :status,
                    updated_at = NOW()
                WHERE case_id::text = :case_id
                RETURNING
                    case_id::text,
                    title,
                    priority,
                    status,
                    created_by,
                    created_at,
                    updated_at
            """), {
                "case_id": case_id,
                "status": mapping[action],
            }).mappings().first()

            if not updated:
                return {"ok": False, "error": "not_found"}

            return {"ok": True, "case": dict(updated)}
    except Exception as e:
        return {"ok": False, "error": "db_error", "detail": str(e)}
