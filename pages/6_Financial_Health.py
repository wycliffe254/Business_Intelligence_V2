import plotly.graph_objects as go
import streamlit as st
from src.ui_state import get_result
from src.utils.formatting import GAUGE_STEPS, dq_bands_caption, kes, rag_badge_md

st.set_page_config(page_title="Financial Health", layout="wide")
st.title("Financial Health Scorecard")
r = get_result()
health, rag, dq, k = r["health_result"], r["rag_result"], r["dq_report"], r["kpis"]

a, b = st.columns([1, 2])
with a:
    fig = go.Figure(go.Indicator(mode="gauge+number", value=health.total_score, title={"text": "Financial Health Score"},
                                 gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#333"},
                                        "steps": [{"range": [0, 50], "color": GAUGE_STEPS["RED"]}, {"range": [50, 70], "color": GAUGE_STEPS["AMBER"]}, {"range": [70, 100], "color": GAUGE_STEPS["GREEN"]}]}))
    st.plotly_chart(fig)
with b:
    st.markdown(f"### Status: {rag_badge_md(rag.status)}", unsafe_allow_html=True)
    if health.partial:
        st.warning(f"Provisional score: only {health.assessable_points:.0f} of 100 points could be assessed with the columns supplied; the score is normalised over those points. "
                   + ("No RAG rating is given because too little could be assessed." if rag.status == "NOT RATED" else ""))
    if rag.status != rag.score_based_status:
        st.warning(f"The numeric score alone maps to **{rag.score_based_status}**, but the final status is **{rag.status}** because of the critical-risk override(s) below.")
    st.markdown(f"### Data Reliability: {rag_badge_md(dq.status, f'{dq.status} ({dq.overall_score:.0f}/100)')}", unsafe_allow_html=True)
    st.caption("Shown separately on purpose: low data reliability is a warning about the input data, not proof that the business is unhealthy.")
    st.caption(dq_bands_caption(dq))
    st.caption("Bands: \u25CF 70\u2013100 GREEN, \u25B2 50\u201369 AMBER, \u25A0 0\u201349 RED. Each status has its own shape and text label as well as a colour.")

if rag.triggered_overrides:
    st.subheader("Critical-risk overrides triggered")
    for o in rag.triggered_overrides:
        st.error(f"**{o['rule']}**: {o['explanation']}")

st.subheader("Score components")
for comp in health.components:
    if not comp.assessable:
        st.markdown(f"**{comp.name}** \u2014 not assessable with this file (0 of {comp.max_points} points counted)")
    else:
        amax = comp.assessable_max if comp.assessable_max is not None else comp.max_points
        extra = f" (only {amax:g} of {comp.max_points} points assessable)" if amax < comp.max_points else ""
        st.markdown(f"**{comp.name}** \u2014 {comp.points:.1f} / {comp.max_points}{extra}")
        st.progress(min(comp.points / amax, 1.0) if amax else 0.0)
    subs = health.subcomponents.get(comp.name, [])
    if subs:
        with st.expander(f"How {comp.name} was calculated"):
            for s in subs:
                if s.assessable:
                    st.markdown(f"- {s.name}: **{s.points:.1f} / {s.max_points}** \u2014 evidence: `{s.detail}`")
                else:
                    st.markdown(f"- {s.name}: **not assessable** (needed data or history is missing) \u2014 excluded from the score")
    elif comp.name.startswith("Working") and comp.detail:
        with st.expander(f"How {comp.name} was calculated"):
            st.markdown(f"Data Quality Score {comp.detail['data_quality_score']:.0f}/100 mapped to points; a deduction applies when inventory integrity fails "
                        f"(inventory integrity OK: {comp.detail['inventory_integrity_ok']}). Inventory turnover is never forced into the score when stock records are unreliable.")

st.subheader("Approximate analytical break-even requirement")
be = k["breakeven"]
x = st.columns(2)
x[0].metric("Current average monthly revenue", kes(be["avg_monthly_revenue"]))
x[1].metric("Current average monthly gross profit", kes(be["avg_monthly_gross_profit"]))
x = st.columns(2)
x[0].metric("Current average monthly operating expense", kes(be["avg_monthly_opex"]))
x[1].metric("Approximate monthly break-even revenue", kes(be["breakeven_revenue"]))
if be["breakeven_revenue"] == be["breakeven_revenue"]:
    if be["revenue_gap_pct"] > 0:
        st.info(f"At the observed gross margin and expense level, roughly {be['revenue_gap_pct']:.0f}% more monthly revenue would be needed to break even. "
                "This is an approximate analytical estimate, not a forecast; where the gap is large, margin and cost structure also need attention, not revenue alone.")
    else:
        st.success("Average monthly revenue is already above the approximate break-even level (an analytical estimate, not a forecast).")
else:
    st.caption("Break-even cannot be estimated because gross margin is zero or negative.")

st.subheader("Inventory and working-capital reliability")
inv = k["inventory_status"]
if not inv.get("assessable", True):
    st.info(inv["message"])
elif inv["usable_for_scoring"]:
    st.success(inv["message"])
    t = k["inventory_turnover"]
    if t:
        st.metric("Inventory turnover (COGS / average inventory value)", f"{t['turnover_ratio']:.2f}x")
        st.caption(f"Average inventory value = {kes(t['average_inventory_value'])} (opening {kes(t['opening_inventory_value'])}, ending {kes(t['ending_inventory_value'])}); "
                   "two-point average over the whole data period.")
else:
    st.error("Inventory analysis unavailable for financial scoring.\n\nReason: Inventory records cannot currently support a reliable stock-on-hand calculation.")
    st.caption(f"{len(inv['negative_stock_products'])} product line(s) go negative; see the Data Quality page for the records responsible.")
