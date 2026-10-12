"""
Explainable BI & Financial Health Decision Support System for Kenyan SMEs.
Main page = Executive Overview.   Run with:  streamlit run app.py
"""
from __future__ import annotations
import io
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from config.settings import APP_SUBTITLE, APP_TITLE, SAMPLE_FILES
from src.data.loader import load_csv, sample_path
from src.data.schema import MAP_FIELDS, suggest_mapping
from src.pipeline import run_pipeline
from src.ui_state import show_completeness
from src.utils.formatting import SERIES_COLORS, dq_bands_caption, kes, pct, rag_badge_md

st.set_page_config(page_title=APP_TITLE, layout="wide", page_icon="\U0001F4CA")


@st.cache_data(show_spinner="Running analysis pipeline...")
def _run(file_bytes: bytes, column_map_items: tuple):
    cmap = dict(column_map_items) or None
    lr = load_csv(io.BytesIO(file_bytes), cmap)
    if not lr.success:
        return {"success": False, "error": lr.error_message, "headers": lr.headers}
    res = run_pipeline(lr.raw_df, cmap)
    res["success"] = True
    res["headers"] = lr.headers
    return res


@st.cache_data(show_spinner=False)
def _headers(file_bytes: bytes):
    df = pd.read_csv(io.BytesIO(file_bytes), dtype=str, nrows=200)
    df.columns = [str(c).strip() for c in df.columns]
    return list(df.columns), suggest_mapping(df.columns), df.head(5)


st.title("Executive Overview")
st.caption(f"{APP_TITLE} \u2014 {APP_SUBTITLE}")

with st.sidebar:
    st.header("Data Input")
    uploaded = st.file_uploader("Upload SME transaction CSV", type=["csv"])
    choice = st.selectbox("...or use a bundled sample dataset", list(SAMPLE_FILES), disabled=uploaded is not None)
    st.caption("Use the pages above for Data Quality, Financial Performance, Product, Customer, Branch & Channel, "
               "Financial Health, Insights, Recommendations, Report and Metric Definitions.")

if uploaded is not None:
    data, label = uploaded.getvalue(), uploaded.name
else:
    data, label = sample_path(SAMPLE_FILES[choice]).read_bytes(), choice

# ---- column matching: automatic first, adjustable by the user ----
file_key = f"{label}:{len(data)}"
saved_maps = st.session_state.setdefault("column_maps", {})
cmap = saved_maps.get(file_key, {})
try:
    headers, auto, preview = _headers(data)
except Exception as exc:  # noqa: BLE001
    st.error(f"The file could not be read as a CSV: {exc}")
    st.stop()
result = _run(data, tuple(sorted(cmap.items())))
failed = not result["success"]

NONE_LABEL = "(not in my file)"
with st.expander("Review how your columns were matched" + (" \u2014 action needed" if failed else ""), expanded=failed):
    st.caption("The system matches your headers automatically (standard names, common alternatives, then keywords). "
               "If a match is wrong or missing, choose the right column below and press Apply. Only a date and an amount are essential.")
    st.dataframe(preview, hide_index=True)
    with st.form("column_matching"):
        choices = {}
        cols = st.columns(2)
        for i, (std, text) in enumerate(MAP_FIELDS):
            current = cmap[std] if std in cmap else auto.get(std)
            options = [NONE_LABEL] + headers
            idx = options.index(current) if current in options else 0
            choices[std] = cols[i % 2].selectbox(text, options, index=idx, key=f"map_{std}_{file_key}")
        applied = st.form_submit_button("Apply column matching")
    if applied:
        saved_maps[file_key] = {std: (None if v == NONE_LABEL else v) for std, v in choices.items()}
        st.rerun()

if failed:
    st.error(result["error"])
    st.stop()
st.session_state["pipeline_result"] = result
st.session_state["dataset_label"] = label

dq, health, rag = result["dq_report"], result["health_result"], result["rag_result"]
k = result["kpis"]
core, col = k["core"], k["collections"]
st.success(f"Loaded: {label} \u2014 {dq.row_count:,} rows.")
show_completeness(result)

a, b, c = st.columns(3)
a.metric("Financial Health Score" + (" (provisional)" if health.partial else ""), f"{health.total_score:.1f} / 100")
b.markdown(f"**Financial Health Status (RAG)**<br>{rag_badge_md(rag.status)}", unsafe_allow_html=True)
c.markdown(f"**Data Reliability**<br>{rag_badge_md(dq.status, f'{dq.status} ({dq.overall_score:.0f}/100)')}", unsafe_allow_html=True)
st.caption("Financial health and data reliability are separate: poor data does not by itself mean an unhealthy business.")
st.caption("Financial Health bands: \u25CF 70\u2013100 GREEN, \u25B2 50\u201369 AMBER, \u25A0 0\u201349 RED. " + dq_bands_caption(dq))
if rag.status == "NOT RATED":
    st.warning("Not rated: too little of the data needed for the scoring framework is present. Figures below show only what could be calculated.")
if rag.triggered_overrides:
    with st.container(border=True):
        st.markdown(f"**Why {rag.status}?** The numeric score alone maps to **{rag.score_based_status}**, but critical-risk override(s) apply:")
        for o in rag.triggered_overrides:
            st.markdown(f"- **{o['rule']}**: {o['explanation']}")

st.subheader("Key Figures")
r1 = st.columns(3)
r1[0].metric("Adjusted Revenue", kes(core["adjusted_revenue"]))
r1[1].metric("Gross Profit", kes(core["gross_profit"]))
r1[2].metric("Gross Margin", pct(core["gross_margin_pct"]))
r2 = st.columns(3)
r2[0].metric("Operating Profit", kes(core["operating_profit"]))
r2[1].metric("Operating Margin", pct(core["operating_margin_pct"]))
r2[2].metric("Operating Expense Ratio", pct(core["opex_ratio_pct"]))
r3 = st.columns(3)
r3[0].metric("Collection Coverage (estimate)", pct(col["collection_coverage_pct"]))
r3[1].metric("Discount Rate", pct(core["discount_rate_pct"]))
r3[2].metric("Refund Rate", pct(core["refund_rate_pct"], 2))
r4 = st.columns(3)
st_ = k["profitability_stability"]
r4[0].metric("Profitable Months", f"{st_['profitable_months']} of {st_['total_months']} ({st_['pct_profitable_months']:.0f}%)" if st_.get("available", True) else "N/A")
rec = k["recent_trend"]
r4[1].metric("Revenue: latest 3 vs preceding 3 months", pct(rec["change_pct"]) if rec.get("sufficient_data") else "N/A")
comp = k["comparable_yoy"]
r4[2].metric(f"Revenue: same months YoY ({comp.get('period_label', '')})" if comp.get("sufficient_data") else "Revenue: comparable period",
             pct(comp["revenue_change_pct"]) if comp.get("sufficient_data") else "N/A")
if not rec.get("sufficient_data") or not comp.get("sufficient_data"):
    st.info("Insufficient historical data for this analysis (one or more trend comparisons).")

m = k["monthly"]
if len(m) and k["availability"].get("revenue", True):
    fig = go.Figure()
    for col, name in [("revenue", "Revenue"), ("gross_profit", "Gross profit"), ("operating_profit", "Operating profit")]:
        fig.add_trace(go.Scatter(x=m["month_str"], y=m[col], name=name, mode="lines+markers", line={"color": SERIES_COLORS[name]}))
    fig.add_hline(y=0, line_dash="dot", line_color="gray")
    fig.update_layout(title="Monthly revenue, gross profit and operating profit (KES)", xaxis_title="Month", yaxis_title="KES", legend_title="")
    st.plotly_chart(fig)

st.subheader("Management Summary")
st.write(result["executive_summary"])
st.caption("Prototype academic decision-support system; not accounting, tax or financial advice and not a guarantee of future performance.")
