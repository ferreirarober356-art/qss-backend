import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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

engine = create_engine(DATABASE_URL) if DATABASE_URL else None

def init_db():
    if not engine:
        return
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

@app.on_event("startup")
def startup():
    init_db()

@app.get("/")
def root():
    return {"service": "qss-backend", "status": "running"}

@app.get("/health")
def health():
    return {"ok": True, "status": "ok"}

@app.get("/cases/list")
def list_cases(limit: int = 50):
    if not engine:
        return {"cases": [], "count": 0, "status": "no_database"}

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
