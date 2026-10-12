"""Self-contained HTML executive report (print to PDF from the browser)."""
from __future__ import annotations
from datetime import datetime
from html import escape
from src.utils.formatting import kes, pct, rag_color, rag_label, rag_text_color


def build_html_report(kpis, health_result, rag_result, dq_report, drivers, explanation_cards, recommendations, executive_summary, schema=None) -> str:
    core, e = kpis["core"], escape
    comps = "".join(f"<tr><td>{e(c.name)}</td><td style='text-align:right'>{c.points:.1f} / {c.max_points}</td></tr>" for c in health_result.components)
    drv = "".join(f"<li><strong>{e(d.name)}</strong>: {e(d.narrative)}</li>" for d in drivers if d.triggered) or "<li>No major risk drivers were triggered.</li>"
    ovr = "".join(f"<li><strong>{e(o['rule'])}</strong>: {e(o['explanation'])}</li>" for o in rag_result.triggered_overrides)
    cards = "".join("<div class='card'>" + "".join(f"<p><strong>{lab}:</strong> {e(val)}</p>" for lab, val in
                    [("Finding", c.finding), ("Evidence", c.evidence), ("Driver", c.driver), ("Impact", c.impact), ("Recommendation", c.recommendation)]) + "</div>"
                    for c in explanation_cards)
    recs = "".join(f"<div class='card'><p><strong>Priority {r.priority} \u2014 {e(r.title)}</strong> ({e(r.category)})</p><p><em>Observed issue:</em> {e(r.observed_issue)}</p>"
                   f"<p><em>Evidence:</em> {e(r.evidence)}</p><p><em>Management action:</em> {e(r.management_action)}</p></div>" for r in recommendations)
    lims = "".join(f"<li>{e(x)}</li>" for x in dq_report.limitations) or "<li>None identified.</li>"
    be = kpis["breakeven"]
    note = ""
    if health_result.partial:
        note += (f"<p><strong>Provisional score:</strong> only {health_result.assessable_points:.0f} of 100 scoring points could be assessed with the supplied columns; "
                 "the score is normalised over those points.</p>")
    if schema is not None and schema.missing_columns:
        note += "<p><strong>Data completeness:</strong> " + e(f"{len(schema.present_columns)} of 32 expected columns supplied ({schema.coverage_pct:.0f}%). ") + "</p><ul>" + \
                "".join(f"<li>{e(l.replace('**', ''))}</li>" for l in schema.banner_lines()[1:]) + "</ul>"
    kpi_boxes = "".join(f"<div class='kpi-box'><div class='small'>{l}</div><div>{v}</div></div>" for l, v in [
        ("Adjusted Revenue", kes(core["adjusted_revenue"])), ("Gross Profit", kes(core["gross_profit"])),
        ("Gross Margin", pct(core["gross_margin_pct"])), ("Operating Profit", kes(core["operating_profit"])),
        ("Operating Margin", pct(core["operating_margin_pct"])), ("Operating Expense Ratio", pct(core["opex_ratio_pct"])),
        ("Avg monthly revenue", kes(be["avg_monthly_revenue"])), ("Avg monthly gross profit", kes(be["avg_monthly_gross_profit"])),
        ("Avg monthly opex", kes(be["avg_monthly_opex"])), ("Approx. break-even revenue / month", kes(be["breakeven_revenue"]))])
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Business Health Report</title><style>
body{{font-family:Arial,Helvetica,sans-serif;margin:40px;color:#222}}h1{{font-size:22px}}h2{{font-size:17px;border-bottom:2px solid #ddd;padding-bottom:4px;margin-top:28px}}
table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #ddd;padding:6px 10px;font-size:14px}}.badge{{display:inline-block;padding:4px 14px;border-radius:12px;font-weight:bold}}
.card{{background:#f7f7f7;border-left:4px solid #888;padding:6px 14px;margin:10px 0}}.kpi-grid{{display:flex;flex-wrap:wrap;gap:12px}}.kpi-box{{border:1px solid #ddd;border-radius:6px;padding:8px 14px;min-width:190px}}.small{{color:#666;font-size:12px}}
</style></head><body><h1>Explainable BI &amp; Financial Health Report</h1><p class="small">Generated {datetime.now():%Y-%m-%d %H:%M}</p>
<h2>Business Health Overview</h2><p>Financial Health Score: <strong>{health_result.total_score:.1f} / 100</strong> <span class="badge" style="background:{rag_color(rag_result.status)};color:{rag_text_color(rag_result.status)}">{rag_label(rag_result.status)}</span>
&nbsp; Data Reliability: <strong>{dq_report.status}</strong> ({dq_report.overall_score:.0f}/100)</p>{('<ul>'+ovr+'</ul>') if ovr else ''}{note}
<h2>Executive Summary</h2><p>{e(executive_summary)}</p><h2>KPI Summary</h2><div class="kpi-grid">{kpi_boxes}</div>
<p class="small">Break-even is an approximate analytical estimate, not a forecast.</p>
<h2>Financial Health Score Components</h2><table><tr><th>Component</th><th>Score</th></tr>{comps}</table>
<h2>Top Drivers</h2><ul>{drv}</ul><h2>Explainable Insights</h2>{cards}<h2>Recommendations</h2>{recs}
<h2>Data Quality Limitations</h2><ul>{lims}</ul>
<p class="small">Prototype academic decision-support system; not accounting, tax or financial advice and not a guarantee of future performance.</p></body></html>"""
