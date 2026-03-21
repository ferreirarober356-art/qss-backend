from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, text
import pandas as pd
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
class CaseCreate(BaseModel):
    title: str
    description: Optional[str] = None
    priority: str = Field(default="MEDIUM")  # LOW/MEDIUM/HIGH/CRITICAL
    created_by: str = Field(default="analyst")

class CaseAttach(BaseModel):
    case_id: str
    alert_ids: List[int]
    actor: str = Field(default="analyst")

class AlertActionReq(BaseModel):
    alert_id: int
    actor: str = Field(default="analyst")
    action: str  # ACK/ESCALATE/DISMISS/CLOSE/NOTE
    note: Optional[str] = None

# --- DB ---
DB_URL = "postgresql://aipuser:aip_pass_change_me@localhost:5432/aipdb"
engine = create_engine(DB_URL)

# --- App ---
app = FastAPI(

title="Sentinel AIP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)




class RunRequest(BaseModel):
    po_csv_path: str
    invoices_csv_path: str
@app.post("/cases/create")
def create_case(req: CaseCreate):
    with engine.begin() as conn:
        row = conn.execute(text("""
            INSERT INTO cases_mgmt (title, description, priority, status, created_by)
            VALUES (:title, :description, :priority, 'OPEN', :created_by)
            RETURNING case_id::text
        """), req.model_dump()).mappings().one()
        return {"case_id": row["case_id"]}

@app.post("/cases/attach-alerts")
def attach_alerts(req: CaseAttach):
    with engine.begin() as conn:
        attached = 0
        for aid in req.alert_ids:
            conn.execute(text("""
                INSERT INTO case_alerts (case_id, alert_id, added_by)
                VALUES (:case_id, :alert_id, :added_by)
                ON CONFLICT DO NOTHING
            """), {"case_id": req.case_id, "alert_id": aid, "added_by": req.actor})
            attached += 1

            conn.execute(text("""
                INSERT INTO alert_actions (alert_id, actor, action, detail)
                VALUES (:alert_id, :actor, 'ATTACH_CASE', jsonb_build_object('case_id', :case_id))
            """), {"alert_id": aid, "actor": req.actor, "case_id": req.case_id})

        return {"attached": attached}

@app.post("/alerts/action")
def alert_action(req: AlertActionReq):
    action = req.action.upper()
    if action not in {"ACK", "ESCALATE", "DISMISS", "CLOSE", "NOTE"}:
        return JSONResponse(status_code=400, content={"error": "Invalid action"})

    with engine.begin() as conn:
        # Update review_status for the main triage actions
        if action == "ACK":
            conn.execute(text("UPDATE alerts SET review_status='OPEN' WHERE alert_id=:id"), {"id": req.alert_id})
        elif action == "ESCALATE":
            conn.execute(text("UPDATE alerts SET review_status='ESCALATED' WHERE alert_id=:id"), {"id": req.alert_id})
        elif action == "DISMISS":
            conn.execute(text("UPDATE alerts SET review_status='DISMISSED' WHERE alert_id=:id"), {"id": req.alert_id})
        elif action == "CLOSE":
            conn.execute(text("UPDATE alerts SET review_status='CLOSED' WHERE alert_id=:id"), {"id": req.alert_id})

        # Always write an audit action
        conn.execute(text("""
            INSERT INTO alert_actions (alert_id, actor, action, detail)
            VALUES (:alert_id, :actor, :action, :detail::jsonb)
        """), {
            "alert_id": req.alert_id,
            "actor": req.actor,
            "action": action,
            "detail": '{"note": %s}' % (('"'+req.note.replace('"','\\"')+'"') if req.note else 'null')
        })

    return {"ok": True}

@app.get("/cases/list")
def list_cases(limit: int = 50):
    try:
        with engine.begin() as conn:
            rows = conn.execute(text("""
                SELECT case_id::text, title, priority, status, created_by, created_at, updated_at
                FROM cases_mgmt
                ORDER BY updated_at DESC
                LIMIT :limit
            """), {"limit": limit}).mappings().all()

            return {"cases": list(rows), "count": len(rows)}

    except Exception as e:
        print("DB ERROR:", str(e))
        return {"cases": [], "count": 0, "status": "fallback"}

    except Exception as e:
        print("DB ERROR:", str(e))
        return {"cases": [], "count": 0, "status": "fallback"}
    except Exception as e:
        return {"cases": [], "count": 0, "warning": "database unavailable", "detail": str(e)}

@app.get("/cases/{case_id}")
def get_case(case_id: str):
    with engine.begin() as conn:
        case = conn.execute(text("""
            SELECT case_id::text, title, description, priority, status, created_by, created_at, updated_at
            FROM cases_mgmt
            WHERE case_id = :case_id
        """), {"case_id": case_id}).mappings().first()

        if not case:
            return JSONResponse(status_code=404, content={"error": "Case not found"})

        alerts = conn.execute(text("""
            SELECT a.alert_id, a.entity_type, a.entity_id, a.severity, a.reason, a.score, a.created_at, a.review_status
            FROM case_alerts ca
            JOIN alerts a ON a.alert_id = ca.alert_id
            WHERE ca.case_id = :case_id
            ORDER BY a.created_at DESC
        """), {"case_id": case_id}).mappings().all()

        return {"case": dict(case), "alerts": list(alerts)}

@app.get("/alerts/{alert_id}/actions")
def get_alert_actions(alert_id: int, limit: int = 50):
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT action_id, actor, action, detail, created_at
            FROM alert_actions
            WHERE alert_id = :alert_id
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"alert_id": alert_id, "limit": limit}).mappings().all()
        return {"actions": list(rows)}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/run-detection")
def run_detection(req: RunRequest):
    df_pos = pd.read_csv(req.po_csv_path)
    df_inv = pd.read_csv(req.invoices_csv_path)

    # Store purchase orders
    with engine.begin() as conn:
        for _, r in df_pos.iterrows():
            row = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
            conn.execute(text("""
                INSERT INTO purchase_orders (po_id, vendor_id, employee_id, amount, created_at, status, last_modified_at)
                VALUES (:po_id, :vendor_id, :employee_id, :amount, :created_at, :status, :last_modified_at)
                ON CONFLICT (po_id) DO UPDATE SET
                    vendor_id=EXCLUDED.vendor_id,
                    employee_id=EXCLUDED.employee_id,
                    amount=EXCLUDED.amount,
                    created_at=EXCLUDED.created_at,
                    status=EXCLUDED.status,
                    last_modified_at=EXCLUDED.last_modified_at
            """), row)

        # Store invoices
        for _, r in df_inv.iterrows():
            row = {k: (None if pd.isna(v) else v) for k, v in r.to_dict().items()}
            conn.execute(text("""
                INSERT INTO invoices (invoice_id, po_id, vendor_id, amount, invoice_date)
                VALUES (:invoice_id, :po_id, :vendor_id, :amount, :invoice_date)
                ON CONFLICT (invoice_id) DO UPDATE SET
                    po_id=EXCLUDED.po_id,
                    vendor_id=EXCLUDED.vendor_id,
                    amount=EXCLUDED.amount,
                    invoice_date=EXCLUDED.invoice_date
            """), row)

    # Simple alert example: invoice > PO by 10%
    alerts = []
    if "po_id" in df_pos.columns and "po_id" in df_inv.columns:
        pos_amt = df_pos.set_index("po_id")["amount"].to_dict()
        for _, inv in df_inv.iterrows():
            po_id = inv.get("po_id")
            if po_id in pos_amt:
                if float(inv["amount"]) > float(pos_amt[po_id]) * 1.10:
                    alerts.append({
                        "entity_type": "INVOICE",
                        "entity_id": str(inv["invoice_id"]),
                        "severity": "HIGH",
                        "reason": "Invoice exceeds PO by >10%",
                        "score": 80.0
                    })

    with engine.begin() as conn:
        for a in alerts:
            conn.execute(text("""
                INSERT INTO alerts (entity_type, entity_id, severity, reason, score)
                VALUES (:entity_type, :entity_id, :severity, :reason, :score)
            """), a)

    return {"inserted_pos": len(df_pos), "inserted_invoices": len(df_inv), "alerts_created": len(alerts)}

@app.get("/alerts")
def list_alerts():
    with engine.begin() as conn:
        rows = conn.execute(text("""
            SELECT alert_id, entity_type, entity_id, severity, reason, score, created_at, status
            FROM alerts
            ORDER BY created_at DESC
            LIMIT 200
        """)).mappings().all()
    return {"alerts": [dict(r) for r in rows]}
import hashlib
from sqlalchemy import text
from agents.db import engine

@app.post("/rules/run")
def run_rule_templates():
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
