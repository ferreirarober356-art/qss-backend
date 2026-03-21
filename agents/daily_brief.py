import datetime as dt
from sqlalchemy import text
from agents.db import engine

def main():
    today = dt.datetime.now().strftime("%Y-%m-%d")
    out_path = f"reports/daily_{today}.md"

    with engine.begin() as conn:
        # Newest cases
        new_cases = conn.execute(text("""
            SELECT published_date, agency, amount_usd, title, url
            FROM cases
            ORDER BY published_date DESC NULLS LAST
            LIMIT 10
        """)).mappings().all()

        # Recent alerts
        recent_alerts = conn.execute(text("""
            SELECT alert_id, entity_type, entity_id, severity, reason, score, created_at
            FROM alerts
            ORDER BY created_at DESC
            LIMIT 20
        """)).mappings().all()

        # Top vendors by risk
        top_vendors = conn.execute(text("""
            SELECT vendor_id, risk_score, high_alerts, med_alerts, low_alerts, last_updated
            FROM vendor_risk_scores
            ORDER BY risk_score DESC
            LIMIT 10
        """)).mappings().all()

        # Typology counts
        typ_counts = conn.execute(text("""
            SELECT typology, COUNT(*) AS cnt
            FROM case_typologies
            GROUP BY typology
            ORDER BY cnt DESC
        """)).mappings().all()

    def fmt_money(x):
        return f"${float(x):,.0f}" if x is not None else "—"

    lines = []
    lines.append(f"# Sentinel AIP™ Daily Brief — {today}\n")
    lines.append("## Top Vendor Risk\n")
    for v in top_vendors:
        lines.append(f"- **{v['vendor_id']}** — score **{v['risk_score']}** (HIGH {v['high_alerts']}, MED {v['med_alerts']}, LOW {v['low_alerts']})")

    lines.append("\n## Recent Alerts\n")
    for a in recent_alerts:
        lines.append(f"- [{a['severity']}] {a['entity_type']} {a['entity_id']} — {a['reason']} (score {a['score']}) @ {a['created_at']}")

    lines.append("\n## Recent Cases (DOJ/GAO)\n")
    for c in new_cases:
        lines.append(f"- {c['published_date'] or ''} [{c['agency'] or '—'}] {fmt_money(c['amount_usd'])} — {c['title']}")

    lines.append("\n## Typology Mix\n")
    for t in typ_counts:
        lines.append(f"- {t['typology']}: {t['cnt']}")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print({"ok": True, "brief": out_path})

if __name__ == "__main__":
    main()
