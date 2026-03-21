import streamlit as st

import requests

QSS_API_BASE = "http://localhost:8000"

def qss_api_get(path: str):
    try:
        resp = requests.get(f"{QSS_API_BASE}{path}", timeout=10)
        resp.raise_for_status()
        return resp.json(), None
    except Exception as e:
        return None, str(e)

def render_qss_command_center():
    st.markdown("## Quantum Sentinel Solutions Command Center")

    missions, missions_err = qss_api_get("/missions")
    cases, cases_err = qss_api_get("/cases")
    health, health_err = qss_api_get("/health")

    missions = missions or {"count": 0, "missions": []}
    cases = cases or {"count": 0, "cases": []}
    health = health or {"ok": False, "services": {}}

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Missions", missions.get("count", 0))
    col2.metric("Cases", cases.get("count", 0))
    col3.metric("Health", "OK" if health.get("ok") else "Degraded")
    done_count = len([m for m in missions.get("missions", []) if m.get("status") == "DONE"])
    col4.metric("Completed", done_count)

    errs = [e for e in [missions_err, cases_err, health_err] if e]
    if errs:
        st.warning("Some QSS backend calls returned errors")
        for err in errs:
            st.code(err)

    with st.expander("Recent Missions", expanded=True):
        if missions.get("missions"):
            st.dataframe(missions["missions"][:10], use_container_width=True)
        else:
            st.info("No missions available.")

    with st.expander("Recent Cases", expanded=False):
        if cases.get("cases"):
            st.dataframe(cases["cases"][:10], use_container_width=True)
        else:
            st.info("No cases available.")

    with st.expander("Launch Mission", expanded=False):
        with st.form("qss_launch_mission"):
            title = st.text_input("Mission Title", value="QSS Threat Hunt")
            mission_type = st.selectbox(
                "Mission Type",
                ["THREAT_HUNT", "EXPOSURE_REVIEW", "COMPLIANCE_AUDIT", "FRAUD_DETECTION"]
            )
            target = st.text_input("Target", value="srv-web-01")
            requested_by = st.text_input("Requested By", value="Robert")
            priority = st.selectbox("Priority", ["LOW", "MEDIUM", "HIGH", "CRITICAL"], index=2)
            submitted = st.form_submit_button("Launch Mission")

        if submitted:
            payload = {
                "title": title,
                "payload": {
                    "mission_type": mission_type,
                    "target": target,
                    "requested_by": requested_by,
                    "priority": priority,
                },
            }
            try:
                resp = requests.post(f"{QSS_API_BASE}/missions", json=payload, timeout=15)
                resp.raise_for_status()
                st.success("Mission launched successfully")
                st.json(resp.json())
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
import requests
import os
import psycopg2

API = "http://127.0.0.1:8000"

st.set_page_config(page_title="Sentinel AIP", layout="wide")
st.title("Sentinel AIP™ Dashboard")
st.caption("Quantum Sentinel Solutions — AI Procurement Fraud Defense & Risk Intelligence")
tabs = st.tabs(["Run Detection","Alerts","Vendor Risk","Case Library","Typologies","Rules","Health"])

with tabs[2]:
    st.subheader("API Health")
    try:
        r = requests.get(f"{API}/health", timeout=5)
        st.json(r.json())
    except Exception as e:
        st.error(f"Could not reach API at {API}. Error: {e}")
with tabs[6]:
    st.subheader("Autopilot Reports")

    import glob

    md_files = sorted(glob.glob("reports/daily_*.md"), reverse=True)

    if md_files:
        st.markdown(open(md_files[0], "r", encoding="utf-8").read())
    else:
        st.info("No executive brief generated yet.")

        # Quick executive summary
        top_vendors = data.get("summary", {}).get("top_vendors", [])
        if top_vendors:
            st.write("Top Risk Vendors")
            st.dataframe(top_vendors, use_container_width=True)

        recent_alerts = data.get("summary", {}).get("recent_alerts", [])
        if recent_alerts:
            st.write("Recent Alerts")
            st.dataframe(recent_alerts, use_container_width=True)

with tabs[0]:
    st.subheader("Run Detection (CSV)")
    po_path = st.text_input("PO CSV path", "samples/purchase_orders.csv")
    inv_path = st.text_input("Invoice CSV path", "samples/invoices.csv")

    if st.button("Run Detection Now"):
        try:
            r = requests.post(
                f"{API}/run-detection",
                json={"po_csv_path": po_path, "invoices_csv_path": inv_path},
                timeout=60
            )
            if r.status_code == 200:
                st.success("Detection run completed.")
                st.json(r.json())
            else:
                st.error(r.text)
        except Exception as e:
            st.error(f"Run failed: {e}")

with tabs[1]:
    st.subheader("Alerts")
    if st.button("Refresh Alerts"):
        st.rerun()

    try:
        r = requests.get(f"{API}/alerts", timeout=10)
        if r.status_code == 200:
            alerts = r.json().get("alerts", [])
            if alerts:
                st.dataframe(alerts, use_container_width=True)
            else:
                st.info("No alerts yet. Run detection first.")
        else:
            st.error(r.text)
    except Exception as e:
        st.error(f"Could not load alerts: {e}")
6
def pg_conn():
    return psycopg2.connect(os.environ.get(
        "SENTINEL_DB_URL",
        "postgresql://aipuser:aip_pass_change_me@localhost:5432/aipdb"
    ))
with tabs[3]:
    st.subheader("Case Library (Public Sources)")
    tabs = st.tabs(["Run Detection","Alerts","Vendor Risk","Case Library","Typologies","Health"])
with tabs[4]:
    st.subheader("Fraud Typologies (Auto-Labeled)")
with tabs[5]:
    st.subheader("Rule Templates (Explainable Detectors)")
    if st.button("Run Enabled Rule Templates"):
        r = requests.post(f"{API}/rules/run", timeout=60)
        if r.status_code == 200:
            st.success(r.json())
        else:
            st.error(r.text)

    import os, psycopg2

    def pg_conn():
        return psycopg2.connect(os.environ.get(
            "SENTINEL_DB_URL",
            "postgresql://aipuser:aip_pass_change_me@localhost:5432/aipdb"
        ))

    typ = st.text_input("Filter typology (e.g., kickbacks, overbilling, false_claims_act)", "kickbacks")
    min_usd = st.number_input("Minimum amount (USD)", min_value=0, value=1_000_000, step=100_000)
    limit = st.slider("Max results", 10, 200, 50)

    q = """
      SELECT c.published_date, c.agency, c.amount_usd, c.title, c.url, t.typology, t.confidence, t.evidence
      FROM case_typologies t
      JOIN cases c ON c.case_id = t.case_id
      WHERE t.typology ILIKE %s
        AND (c.amount_usd IS NULL OR c.amount_usd >= %s)
      ORDER BY c.amount_usd DESC NULLS LAST, c.published_date DESC NULLS LAST
      LIMIT %s
    """

    try:
        conn = pg_conn()
        cur = conn.cursor()
        cur.execute(q, (f"%{typ}%", min_usd, limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if rows:
            st.dataframe([{
                "published_date": r[0],
                "agency": r[1],
                "amount_usd": float(r[2]) if r[2] else None,
                "title": r[3],
                "url": r[4],
                "typology": r[5],
                "confidence": float(r[6]),
                "evidence": r[7],
            } for r in rows], use_container_width=True)
        else:
            st.info("No matches. Try another typology or lower the amount threshold.")
    except Exception as e:
        st.error(e)

    col1, col2 = st.columns(2)
    min_usd = col1.number_input("Minimum loss/settlement (USD)", min_value=0, value=1_000_000, step=100_000)
    limit = col2.slider("Max results", 10, 200, 50, key="case_library_max_results")

    q = """
      SELECT published_date, agency, amount_usd, title, url
      FROM cases
      WHERE (amount_usd IS NULL OR amount_usd >= %s)
      ORDER BY amount_usd DESC NULLS LAST, published_date DESC NULLS LAST
      LIMIT %s
    """

    try:
        conn = pg_conn()
        cur = conn.cursor()
        cur.execute(q, (min_usd, limit))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        if rows:
            st.write(f"Showing up to {len(rows)} cases")
            st.dataframe(
                [{"published_date": r[0], "agency": r[1], "amount_usd": float(r[2]) if r[2] else None,
                  "title": r[3], "url": r[4]} for r in rows],
                use_container_width=True
            )
        else:
            st.info("No cases found yet. Run ingestion again.")
    except Exception as e:
        st.error(e)
        st.info("If this fails, we can expose /cases via FastAPI instead.")
