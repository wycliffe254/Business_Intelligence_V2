import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from src.reporting.report import build_html_report
from src.ui_state import get_result

st.set_page_config(page_title="Executive Report", layout="wide")
st.title("Executive Business Health Report")
r = get_result()
html = build_html_report(r["kpis"], r["health_result"], r["rag_result"], r["dq_report"], r["drivers"], r["explanation_cards"], r["recommendations"], r["executive_summary"], r.get("schema"))
st.download_button("Download executive report (HTML)", html.encode("utf-8"), "business_health_report.html", "text/html")
st.caption("Open the file in a browser and use Print \u2192 Save as PDF for a PDF copy.")
st.subheader("Other downloads")
k = r["kpis"]
a, b, c, d = st.columns(4)
a.download_button("KPI summary (CSV)", pd.DataFrame([k["core"]]).T.reset_index().rename(columns={"index": "kpi", 0: "value"}).to_csv(index=False).encode("utf-8"), "kpi_summary.csv", "text/csv")
b.download_button("Category table (CSV)", k["product_category"].to_csv(index=False).encode("utf-8"), "category_performance.csv", "text/csv")
c.download_button("Branch table (CSV)", k["branch"].to_csv(index=False).encode("utf-8"), "branch_performance.csv", "text/csv")
d.download_button("Monthly series (CSV)", k["monthly"].drop(columns=["month"]).to_csv(index=False).encode("utf-8"), "monthly_financials.csv", "text/csv")
st.subheader("Preview")
components.html(html, height=900, scrolling=True)
