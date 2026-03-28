import os
import json
from openai import OpenAI
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
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
engine = None
engine_error = None
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

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

            
            insert_event(conn, case_id, "ACTION", f"Case action executed: {action}", req.actor)
            return {"ok": True, "case": dict(updated)}
    
    except Exception as e:
        return {"ok": False, "error": "db_error", "detail": str(e)}


import json
from typing import Any, Dict, List, Optional
from pydantic import Field

class NoteCreate(BaseModel):
    author: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)
    tags: Optional[List[str]] = []

class TimelineCreate(BaseModel):
    event_type: str
    description: str
    source: str = "system"
    metadata: Optional[Dict[str, Any]] = {}

def insert_note(conn, case_id, author, content, tags=None):
    tags = tags or []
    row = conn.execute(text("""
        INSERT INTO analyst_notes (case_id, author, content, tags)
        VALUES (:case_id, :author, :content, :tags)
        RETURNING *
    """), {
        "case_id": case_id,
        "author": author,
        "content": content,
        "tags": tags
    }).mappings().first()
    return dict(row)

def get_notes(conn, case_id):
    rows = conn.execute(text("""
        SELECT * FROM analyst_notes
        WHERE case_id = :case_id
        ORDER BY created_at ASC
    """), {"case_id": case_id}).mappings().all()
    return list(rows)

def insert_event(conn, case_id, etype, desc, source="system", meta=None):
    row = conn.execute(text("""
        INSERT INTO case_timeline (case_id, event_type, description, source, metadata)
        VALUES (:c, :t, :d, :s, CAST(:m AS JSONB))
        RETURNING *
    """), {
        "c": case_id,
        "t": etype,
        "d": desc,
        "s": source,
        "m": json.dumps(meta or {})
    }).mappings().first()
    return dict(row)

def get_timeline(conn, case_id):
    rows = conn.execute(text("""
        SELECT * FROM case_timeline
        WHERE case_id = :case_id
        ORDER BY created_at ASC
    """), {"case_id": case_id}).mappings().all()
    return list(rows)

@app.post("/cases/{case_id}/notes")
def create_note(case_id: str, payload: NoteCreate):
    with engine.begin() as conn:
        note = insert_note(conn, case_id, payload.author, payload.content, payload.tags)
        insert_event(conn, case_id, "NOTE", f"Note added by {payload.author}", payload.author)
        return {"ok": True, "note": note}

@app.get("/cases/{case_id}/notes")
def list_notes(case_id: str):
    with engine.begin() as conn:
        return {"notes": get_notes(conn, case_id)}

@app.get("/cases/{case_id}/timeline")
def timeline(case_id: str):
    with engine.begin() as conn:
        return {"timeline": get_timeline(conn, case_id)}

@app.post("/cases/{case_id}/timeline")
def add_event(case_id: str, payload: TimelineCreate):
    with engine.begin() as conn:
        ev = insert_event(conn, case_id, payload.event_type, payload.description, payload.source, payload.metadata)
        return {"ok": True, "event": ev}


class CaseSummaryResponse(BaseModel):
    case_id: str
    executive_summary: str
    analyst_summary: str
    likely_tactics: list[str]
    recommended_actions: list[str]
    suggested_missions: list[str]

def generate_case_summary(case_row, notes, timeline):
    title = case_row.get("title", "Unknown Case")
    priority = case_row.get("priority", "UNKNOWN")
    status = case_row.get("status", "UNKNOWN")
    created_by = case_row.get("created_by", "system")

    note_count = len(notes or [])
    timeline_count = len(timeline or [])

    combined_text = " ".join(
        [title, priority, status]
        + [str(n.get("content", "")) for n in (notes or [])]
        + [str(t.get("description", "")) for t in (timeline or [])]
    ).lower()

    tactics = []
    if "phish" in combined_text or "email" in combined_text:
        tactics.append("TA0001")
    if "lateral" in combined_text or "movement" in combined_text:
        tactics.append("TA0008")
    if "credential" in combined_text or "password" in combined_text or "auth" in combined_text:
        tactics.append("TA0006")
    if "privilege" in combined_text or "admin" in combined_text:
        tactics.append("TA0004")
    if not tactics:
        tactics = ["TA0005"]

    recommended_actions = []
    if priority in ("HIGH", "CRITICAL"):
        recommended_actions.append("Escalate investigation and validate containment status")
        recommended_actions.append("Review affected assets and confirm scope of exposure")
    else:
        recommended_actions.append("Continue triage and collect supporting evidence")

    if note_count == 0:
        recommended_actions.append("Add first analyst triage note")
    if timeline_count < 2:
        recommended_actions.append("Expand timeline with supporting events and evidence")

    suggested_missions = []
    if "TA0006" in tactics:
        suggested_missions.append("Credential Review Sweep")
    if "TA0008" in tactics:
        suggested_missions.append("Lateral Movement Hunt")
    if priority in ("HIGH", "CRITICAL"):
        suggested_missions.append("Containment Workflow")
        suggested_missions.append("Executive Reporting Workflow")
    else:
        suggested_missions.append("IOC Enrichment Workflow")

    executive_summary = (
        f"{title} is currently {status} with {priority} priority. "
        f"The case was created by {created_by} and currently contains {note_count} notes "
        f"and {timeline_count} timeline events. "
        f"QSS assessment indicates the incident should be reviewed against likely tactics: {', '.join(tactics)}."
    )

    analyst_summary = (
        f"Case {case_row.get('case_id')} titled '{title}' is in status {status}. "
        f"Observed context from notes and timeline suggests ATT&CK alignment to {', '.join(tactics)}. "
        f"Recommended analyst focus: {'; '.join(recommended_actions)}."
    )

    return {
        "case_id": str(case_row.get("case_id")),
        "executive_summary": executive_summary,
        "analyst_summary": analyst_summary,
        "likely_tactics": tactics,
        "recommended_actions": recommended_actions,
        "suggested_missions": suggested_missions,
    }

@app.get("/cases/{case_id}/summary")
def case_summary(case_id: str):
    if not engine:
        return {"ok": False, "error": "no_database", "engine_error": engine_error}

    try:
        with engine.begin() as conn:
            case_row = conn.execute(text("""
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

            if not case_row:
                return {"ok": False, "error": "not_found"}

            notes = conn.execute(text("""
                SELECT note_id, case_id, author, content, tags, created_at
                FROM analyst_notes
                WHERE case_id = :case_id
                ORDER BY created_at ASC
            """), {"case_id": case_id}).mappings().all()

            timeline = conn.execute(text("""
                SELECT event_id, case_id, event_type, description, source, metadata, created_at
                FROM case_timeline
                WHERE case_id = :case_id
                ORDER BY created_at ASC
            """), {"case_id": case_id}).mappings().all()

            summary = generate_case_summary_ai(dict(case_row), list(notes), list(timeline)) or generate_case_summary(dict(case_row), list(notes), list(timeline))
            
            auto_response_engine(conn, case_id, dict(case_row), summary)
            auto_result = auto_hunt_and_response(conn, case_id, dict(case_row), summary)
            containment_result = auto_plan_containment_actions(conn, case_id, dict(case_row), summary)
            return {
                "ok": True,
                "summary": summary,
                "autonomous_actions": auto_result,
                "auto_planned_responses": containment_result
            }
    
    except Exception as e:
        return {"ok": False, "error": "db_error", "detail": str(e)}


class MissionLaunchRequest(BaseModel):
    mission_name: str
    actor: str = "analyst"

@app.post("/cases/{case_id}/missions/launch")
def launch_mission(case_id: str, req: MissionLaunchRequest):
    if not engine:
        return {"ok": False, "error": "no_database", "engine_error": engine_error}

    try:
        with engine.begin() as conn:
            case_row = conn.execute(text("""
                SELECT case_id::text
                FROM cases_mgmt
                WHERE case_id::text = :case_id
            """), {"case_id": case_id}).mappings().first()

            if not case_row:
                return {"ok": False, "error": "not_found"}

            insert_event(
                conn,
                case_id,
                "MISSION",
                f"Mission launched: {req.mission_name}",
                req.actor,
                {"mission_name": req.mission_name}
            )

            return {
                "ok": True,
                "case_id": case_id,
                "mission": req.mission_name,
                "status": "queued"
            }
    except Exception as e:
        return {"ok": False, "error": "db_error", "detail": str(e)}


def generate_case_summary_ai(case_row, notes, timeline):
    if not client:
        return None

    payload = {
        "case": case_row,
        "notes": notes,
        "timeline": timeline,
        "task": "Return JSON with executive_summary, analyst_summary, likely_tactics, recommended_actions, suggested_missions"
    }

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are a SOC AI assistant. Output strict JSON."},
            {"role": "user", "content": json.dumps(payload)}
        ]
    )

    return json.loads(response.choices[0].message.content)


def auto_response_engine(conn, case_id, case_row, summary):
    try:
        priority = case_row.get("priority", "MEDIUM")
        tactics = summary.get("likely_tactics", [])

        triggered = []

        if priority in ("HIGH", "CRITICAL"):
            triggered.append("Containment Workflow")
            triggered.append("Executive Reporting Workflow")

        if "TA0008" in tactics:
            triggered.append("Lateral Movement Hunt")

        if "TA0006" in tactics:
            triggered.append("Credential Review Sweep")

        for mission in triggered:
            insert_event(
                conn,
                case_id,
                "AUTO_MISSION",
                f"Auto-triggered mission: {mission}",
                "ai-engine",
                {"reason": "auto_response"}
            )

        if triggered:
            insert_event(
                conn,
                case_id,
                "AI",
                f"Auto-response triggered {len(triggered)} missions",
                "ai-engine",
                {"missions": triggered}
            )

    except Exception:
        pass


class HuntRequest(BaseModel):
    objective: str = "Autonomous threat hunt"
    actor: str = "ai-hunter"

def generate_hunt_plan(case_row, notes, timeline):
    title = case_row.get("title", "Unknown Case")
    priority = case_row.get("priority", "UNKNOWN")
    status = case_row.get("status", "UNKNOWN")

    combined_text = " ".join(
        [title, priority, status]
        + [str(n.get("content", "")) for n in (notes or [])]
        + [str(t.get("description", "")) for t in (timeline or [])]
    ).lower()

    hypotheses = []
    pivots = []
    queries = []
    confidence = "medium"

    if "credential" in combined_text or "password" in combined_text or "auth" in combined_text:
        hypotheses.append("Possible credential abuse or password spray activity")
        pivots.extend(["identity provider logs", "failed vs successful auth spikes", "privileged account review"])
        queries.extend([
            "failed logins by source IP over time",
            "successful logins following multiple failures",
            "new admin role assignments"
        ])

    if "lateral" in combined_text or "movement" in combined_text:
        hypotheses.append("Possible lateral movement between hosts")
        pivots.extend(["east-west traffic", "remote execution telemetry", "new service creation"])
        queries.extend([
            "RDP/SMB/WMI activity between internal assets",
            "process creation linked to remote admin tools",
            "new scheduled tasks or services"
        ])
        confidence = "high"

    if "phish" in combined_text or "email" in combined_text:
        hypotheses.append("Potential phishing-driven initial access")
        pivots.extend(["mail gateway logs", "user click telemetry", "new inbox rule events"])
        queries.extend([
            "emails with suspicious sender domains",
            "mailbox rule creation after suspect message delivery",
            "login events after mail interaction"
        ])

    if not hypotheses:
        hypotheses.append("General suspicious activity requiring enrichment and scoping")
        pivots.extend(["endpoint alerts", "network connections", "recent auth anomalies"])
        queries.extend([
            "recent high-severity alerts for affected assets",
            "unusual outbound connections",
            "recent user/account changes"
        ])

    return {
        "case_id": str(case_row.get("case_id")),
        "objective": "Autonomous threat hunt",
        "hypotheses": hypotheses,
        "pivots": pivots,
        "queries": queries,
        "confidence": confidence,
    }

def generate_hunt_plan_ai(case_row, notes, timeline, objective="Autonomous threat hunt"):
    if not client:
        return None

    payload = {
        "case": case_row,
        "notes": notes,
        "timeline": timeline,
        "objective": objective,
        "task": (
            "Return strict JSON with keys: case_id, objective, hypotheses, pivots, queries, confidence. "
            "Focus on SOC hunting actions and concise operational pivots."
        ),
    }

    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "You are an autonomous SOC threat hunter. Output strict JSON only."},
            {"role": "user", "content": json.dumps(payload)},
        ],
    )

    data = json.loads(response.choices[0].message.content)
    return {
        "case_id": str(case_row.get("case_id")),
        "objective": data.get("objective", objective),
        "hypotheses": data.get("hypotheses", []),
        "pivots": data.get("pivots", []),
        "queries": data.get("queries", []),
        "confidence": data.get("confidence", "medium"),
    }

@app.get("/cases/{case_id}/hunt")
def get_hunt_plan(case_id: str):
    if not engine:
        return {"ok": False, "error": "no_database", "engine_error": engine_error}

    try:
        with engine.begin() as conn:
            case_row = conn.execute(text("""
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

            if not case_row:
                return {"ok": False, "error": "not_found"}

            notes = conn.execute(text("""
                SELECT note_id, case_id, author, content, tags, created_at
                FROM analyst_notes
                WHERE case_id = :case_id
                ORDER BY created_at ASC
            """), {"case_id": case_id}).mappings().all()

            timeline = conn.execute(text("""
                SELECT event_id, case_id, event_type, description, source, metadata, created_at
                FROM case_timeline
                WHERE case_id = :case_id
                ORDER BY created_at ASC
            """), {"case_id": case_id}).mappings().all()

            plan = generate_hunt_plan_ai(dict(case_row), list(notes), list(timeline)) or generate_hunt_plan(dict(case_row), list(notes), list(timeline))
            return {"ok": True, "hunt": plan}
    except Exception as e:
        return {"ok": False, "error": "db_error", "detail": str(e)}

@app.post("/cases/{case_id}/hunt")
def run_hunt(case_id: str, req: HuntRequest):
    if not engine:
        return {"ok": False, "error": "no_database", "engine_error": engine_error}

    try:
        with engine.begin() as conn:
            case_row = conn.execute(text("""
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

            if not case_row:
                return {"ok": False, "error": "not_found"}

            notes = conn.execute(text("""
                SELECT note_id, case_id, author, content, tags, created_at
                FROM analyst_notes
                WHERE case_id = :case_id
                ORDER BY created_at ASC
            """), {"case_id": case_id}).mappings().all()

            timeline = conn.execute(text("""
                SELECT event_id, case_id, event_type, description, source, metadata, created_at
                FROM case_timeline
                WHERE case_id = :case_id
                ORDER BY created_at ASC
            """), {"case_id": case_id}).mappings().all()

            plan = generate_hunt_plan_ai(dict(case_row), list(notes), list(timeline), req.objective) or generate_hunt_plan(dict(case_row), list(notes), list(timeline))

            insert_event(
                conn,
                case_id,
                "HUNT",
                f"Autonomous hunt generated: {req.objective}",
                req.actor,
                plan
            )

            return {"ok": True, "hunt": plan, "status": "generated"}
    except Exception as e:
        return {"ok": False, "error": "db_error", "detail": str(e)}


def auto_hunt_and_response(conn, case_id, case_row, summary):
    try:
        priority = str(case_row.get("priority", "MEDIUM")).upper()
        tactics = summary.get("likely_tactics", []) or []
        triggered_missions = []
        hunt_objective = None

        if priority in ("HIGH", "CRITICAL"):
            triggered_missions.append("Containment Workflow")
            triggered_missions.append("Executive Reporting Workflow")

        if "TA0008" in tactics:
            triggered_missions.append("Lateral Movement Hunt")
            hunt_objective = "Investigate likely lateral movement and internal propagation"

        if "TA0006" in tactics:
            triggered_missions.append("Credential Review Sweep")
            if not hunt_objective:
                hunt_objective = "Investigate likely credential abuse and authentication anomalies"

        if not hunt_objective and priority in ("HIGH", "CRITICAL"):
            hunt_objective = "Investigate high-priority case for scope, impact, and follow-on attacker activity"

        deduped = []
        

        existing = conn.execute(text("""
            SELECT description
            FROM case_timeline
            WHERE case_id = :case_id
              AND event_type = 'AUTO_MISSION'
        """), {"case_id": case_id}).mappings().all()

        existing_descriptions = {row["description"] for row in existing}

        deduped = []
        for mission in triggered_missions:
            desc = f"Auto-triggered mission: {mission}"
            if desc not in existing_descriptions:
                deduped.append(mission)

        triggered_missions = deduped

        for mission in triggered_missions:
            if mission not in deduped:
                deduped.append(mission)
        triggered_missions = deduped

        

        existing = conn.execute(text("""
            SELECT description
            FROM case_timeline
            WHERE case_id = :case_id
              AND event_type = 'AUTO_MISSION'
        """), {"case_id": case_id}).mappings().all()

        existing_descriptions = {row["description"] for row in existing}

        deduped = []
        for mission in triggered_missions:
            desc = f"Auto-triggered mission: {mission}"
            if desc not in existing_descriptions:
                deduped.append(mission)

        triggered_missions = deduped

        for mission in triggered_missions:
            insert_event(
                conn,
                case_id,
                "AUTO_MISSION",
                f"Auto-triggered mission: {mission}",
                "ai-engine",
                {"mission_name": mission, "reason": "summary_analysis"}
            )

        hunt_plan = None
        if hunt_objective:
            notes = conn.execute(text("""
                SELECT note_id, case_id, author, content, tags, created_at
                FROM analyst_notes
                WHERE case_id = :case_id
                ORDER BY created_at ASC
            """), {"case_id": case_id}).mappings().all()

            timeline = conn.execute(text("""
                SELECT event_id, case_id, event_type, description, source, metadata, created_at
                FROM case_timeline
                WHERE case_id = :case_id
                ORDER BY created_at ASC
            """), {"case_id": case_id}).mappings().all()

            hunt_plan = generate_hunt_plan_ai(dict(case_row), list(notes), list(timeline), hunt_objective) or generate_hunt_plan(dict(case_row), list(notes), list(timeline))

            insert_event(
                conn,
                case_id,
                "AUTO_HUNT",
                f"Auto-triggered hunt: {hunt_objective}",
                "ai-engine",
                hunt_plan
            )

        if triggered_missions or hunt_plan:
            insert_event(
                conn,
                case_id,
                "AI",
                "Autonomous cyber response executed",
                "ai-engine",
                {
                    "missions": triggered_missions,
                    "hunt_generated": bool(hunt_plan),
                    "tactics": tactics,
                    "priority": priority
                }
            )

        return {
            "missions": triggered_missions,
            "hunt_generated": bool(hunt_plan)
        }
    except Exception:
        return {
            "missions": [],
            "hunt_generated": False
        }


@app.post("/cases/{case_id}/response/plan")
def plan_response(case_id: str, payload: dict):
    if not engine:
        return {"ok": False}

    with engine.begin() as conn:
        insert_event(
            conn,
            case_id,
            "RESPONSE_PLAN",
            f"Planned response: {payload.get('action_type')} -> {payload.get('target')}",
            "ai-engine",
            payload
        )

        return {"ok": True, "planned": payload}


class ResponseApproveRequest(BaseModel):
    approver: str = "analyst"

def ensure_response_table(conn):
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS response_actions (
            response_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id TEXT NOT NULL,
            action_type TEXT NOT NULL,
            target TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'PENDING_APPROVAL',
            requested_by TEXT NOT NULL DEFAULT 'ai-engine',
            approved_by TEXT,
            execution_result JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMP NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMP NOT NULL DEFAULT NOW()
        )
    """))

def insert_response_action(conn, case_id, action_type, target, requested_by="ai-engine"):
    ensure_response_table(conn)
    row = conn.execute(text("""
        INSERT INTO response_actions (case_id, action_type, target, requested_by)
        VALUES (:case_id, :action_type, :target, :requested_by)
        RETURNING *
    """), {
        "case_id": case_id,
        "action_type": action_type,
        "target": target,
        "requested_by": requested_by
    }).mappings().first()
    return dict(row)

def list_response_actions(conn, case_id):
    ensure_response_table(conn)
    rows = conn.execute(text("""
        SELECT *
        FROM response_actions
        WHERE case_id = :case_id
        ORDER BY created_at ASC
    """), {"case_id": case_id}).mappings().all()
    return list(rows)

def execute_response_adapter(action_type, target):
    if action_type == "block_ip":
        return {"ok": True, "mode": "simulated", "message": f"Simulated firewall block for {target}"}
    if action_type == "disable_user":
        return {"ok": True, "mode": "simulated", "message": f"Simulated user disable for {target}"}
    if action_type == "isolate_host":
        return {"ok": True, "mode": "simulated", "message": f"Simulated host isolation for {target}"}
    if action_type == "contain_case":
        return {"ok": True, "mode": "simulated", "message": f"Simulated case containment for {target}"}
    return {"ok": False, "mode": "simulated", "message": f"Unknown action type: {action_type}"}

@app.get("/cases/{case_id}/response")
def get_response_actions(case_id: str):
    if not engine:
        return {"ok": False, "error": "no_database", "engine_error": engine_error}
    try:
        with engine.begin() as conn:
            return {"ok": True, "responses": list_response_actions(conn, case_id)}
    except Exception as e:
        return {"ok": False, "error": "db_error", "detail": str(e)}

@app.post("/cases/{case_id}/response/{response_id}/approve")
def approve_response(case_id: str, response_id: str, req: ResponseApproveRequest):
    if not engine:
        return {"ok": False, "error": "no_database", "engine_error": engine_error}
    try:
        with engine.begin() as conn:
            ensure_response_table(conn)
            row = conn.execute(text("""
                UPDATE response_actions
                SET
                    status = 'APPROVED',
                    approved_by = :approved_by,
                    updated_at = NOW()
                WHERE case_id = :case_id
                  AND response_id::text = :response_id
                RETURNING *
            """), {
                "case_id": case_id,
                "response_id": response_id,
                "approved_by": req.approver
            }).mappings().first()

            if not row:
                return {"ok": False, "error": "not_found"}

            insert_event(
                conn,
                case_id,
                "RESPONSE_APPROVED",
                f"Approved response: {row['action_type']} -> {row['target']}",
                req.approver,
                {"response_id": str(row["response_id"])}
            )

            return {"ok": True, "response": dict(row)}
    except Exception as e:
        return {"ok": False, "error": "db_error", "detail": str(e)}

@app.post("/cases/{case_id}/response/{response_id}/execute")
def execute_response(case_id: str, response_id: str):
    if not engine:
        return {"ok": False, "error": "no_database", "engine_error": engine_error}
    try:
        with engine.begin() as conn:
            ensure_response_table(conn)
            row = conn.execute(text("""
                SELECT *
                FROM response_actions
                WHERE case_id = :case_id
                  AND response_id::text = :response_id
            """), {
                "case_id": case_id,
                "response_id": response_id
            }).mappings().first()

            if not row:
                return {"ok": False, "error": "not_found"}

            if row["status"] != "APPROVED":
                return {"ok": False, "error": "not_approved"}

            result = execute_response_adapter(row["action_type"], row["target"])
            new_status = "EXECUTED" if result.get("ok") else "FAILED"

            updated = conn.execute(text("""
                UPDATE response_actions
                SET
                    status = :status,
                    execution_result = CAST(:execution_result AS JSONB),
                    updated_at = NOW()
                WHERE response_id::text = :response_id
                RETURNING *
            """), {
                "response_id": response_id,
                "status": new_status,
                "execution_result": json.dumps(result)
            }).mappings().first()

            insert_event(
                conn,
                case_id,
                "RESPONSE_EXECUTED",
                f"Executed response: {row['action_type']} -> {row['target']}",
                "response-engine",
                {
                    "response_id": response_id,
                    "result": result,
                    "status": new_status
                }
            )

            return {"ok": True, "response": dict(updated), "execution": result}
    except Exception as e:
        return {"ok": False, "error": "db_error", "detail": str(e)}


def auto_plan_containment_actions(conn, case_id, case_row, summary):
    try:
        priority = str(case_row.get("priority", "MEDIUM")).upper()
        tactics = summary.get("likely_tactics", []) or []
        plans = []

        if priority in ("HIGH", "CRITICAL"):
            plans.append(("contain_case", f"case-{case_id}"))

        if "TA0006" in tactics:
            plans.append(("disable_user", f"user-linked-to-case-{case_id}"))

        if "TA0008" in tactics:
            plans.append(("isolate_host", f"host-linked-to-case-{case_id}"))

        if "TA0006" in tactics or "TA0008" in tactics:
            plans.append(("block_ip", f"suspect-ip-for-case-{case_id}"))

        existing = conn.execute(text("""
            SELECT action_type, target
            FROM response_actions
            WHERE case_id = :case_id
        """), {"case_id": case_id}).mappings().all()

        existing_pairs = {(row["action_type"], row["target"]) for row in existing}
        created = []

        for action_type, target in plans:
            if (action_type, target) in existing_pairs:
                continue

            action = insert_response_action(conn, case_id, action_type, target, "ai-engine")
            created.append({
                "response_id": str(action["response_id"]),
                "action_type": action["action_type"],
                "target": action["target"],
                "status": action["status"]
            })

            insert_event(
                conn,
                case_id,
                "RESPONSE_PLAN",
                f"Auto-planned response: {action_type} -> {target}",
                "ai-engine",
                {
                    "response_id": str(action["response_id"]),
                    "status": action["status"],
                    "reason": "summary_and_tactics"
                }
            )

        if created:
            insert_event(
                conn,
                case_id,
                "AI",
                f"Auto-planned {len(created)} containment actions",
                "ai-engine",
                {"planned_actions": created}
            )

        return {"planned_actions": created}
    except Exception:
        return {"planned_actions": []}
