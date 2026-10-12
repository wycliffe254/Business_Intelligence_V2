import plotly.graph_objects as go
import streamlit as st
from src.analytics.kpis import compute_all_kpis
from src.ui_state import get_result
from src.utils.formatting import SERIES_COLORS, kes, pct, signed_kes

st.set_page_config(page_title="Financial Performance", layout="wide")
st.title("Financial Performance")
r = get_result()
df = r["analytical_df"]
inc = df[df["include_in_kpis"]]
if inc["parsed_date"].isna().all():
    st.warning("No valid dates found: time-based analysis is not available.")
    st.stop()

st.sidebar.header("Filters")
dmin, dmax = inc["parsed_date"].min().date(), inc["parsed_date"].max().date()
dr = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
def opts(col):
    return sorted(inc[col].dropna().unique().tolist())
sel = {
    "branch_norm": st.sidebar.multiselect("Branch", opts("branch_norm")),
    "product_category_norm": st.sidebar.multiselect("Product category", opts("product_category_norm")),
    "product_name": st.sidebar.multiselect("Product", opts("product_name")),
    "customer_type_norm": st.sidebar.multiselect("Customer type", opts("customer_type_norm")),
    "sales_channel_norm": st.sidebar.multiselect("Sales channel", opts("sales_channel_norm")),
}
f = df
if isinstance(dr, tuple) and len(dr) == 2:
    f = f[(f["parsed_date"] >= str(dr[0])) & (f["parsed_date"] <= str(dr[1]) + " 23:59:59") | f["parsed_date"].isna()]
active = False
for col, vals in sel.items():
    if vals:
        active = True
        f = f[f[col].isin(vals) | f[col].isna()]
if active:
    st.info("Filters applied. Operating expenses are not attributable to a product, customer type or branch split in the data, so "
            "expense rows are kept in full when a product/customer/channel filter is active; operating profit should then be read with care.")
if not len(f[f["include_in_kpis"]]):
    st.warning("No records match the current filters.")
    st.stop()
k = compute_all_kpis(f, r["inventory_summary"], r["kpis"]["availability"])
core, m = k["core"], k["monthly"]

x = st.columns(3)
x[0].metric("Adjusted Revenue", kes(core["adjusted_revenue"]))
x[1].metric("Gross Profit", kes(core["gross_profit"]))
x[2].metric("Gross Margin", pct(core["gross_margin_pct"]))
y = st.columns(3)
y[0].metric("Operating Expenses", kes(core["operating_expenses"]))
y[1].metric("Operating Profit", kes(core["operating_profit"]))
y[2].metric("Operating Margin", pct(core["operating_margin_pct"]))

fig = go.Figure()
for col, name in [("revenue", "Revenue"), ("gross_profit", "Gross profit"), ("operating_profit", "Operating profit")]:
    fig.add_trace(go.Scatter(x=m["month_str"], y=m[col], name=name, mode="lines+markers", line={"color": SERIES_COLORS[name]}))
fig.add_hline(y=0, line_dash="dot", line_color="gray")
fig.update_layout(title="Revenue, gross profit and operating profit", xaxis_title="Month", yaxis_title="KES", legend_title="")
st.plotly_chart(fig)

fig = go.Figure(go.Scatter(x=m["month_str"], y=m["gross_margin_pct"], mode="lines+markers"))
fig.update_layout(title="Gross margin trend", xaxis_title="Month", yaxis_title="Gross margin %")
st.plotly_chart(fig)

fig = go.Figure()
for col, name in [("revenue", "Revenue"), ("operating_expenses", "Operating expenses")]:
    fig.add_trace(go.Scatter(x=m["month_str"], y=m[col], name=name, mode="lines+markers", line={"color": SERIES_COLORS[name]}))
fig.update_layout(title="Revenue vs operating expenses", xaxis_title="Month", yaxis_title="KES")
st.plotly_chart(fig)

eb = k["expense_breakdown"]
st.subheader("Expense composition")
if len(eb):
    st.plotly_chart(go.Figure(go.Bar(x=eb["expense_category"], y=eb["amount_kes"])).update_layout(xaxis_title="Category", yaxis_title="KES"))
    st.dataframe(eb, hide_index=True)

st.subheader("Comparable-period analysis (same calendar months, year on year)")
comp = k["comparable_yoy"]
if comp.get("sufficient_data"):
    st.caption(f"Months compared in both years: {', '.join(comp['months_compared'])} (never 8 months against 12).")
    z = st.columns(3)
    z[0].metric(f"Revenue {comp['prior_year']}", kes(comp["prior_period_revenue"]))
    z[1].metric(f"Revenue {comp['latest_year']}", kes(comp["latest_period_revenue"]), delta=f"{comp['revenue_change_pct']:.1f}%")
    z[2].metric("Gross margin change", f"{comp['margin_change_pp']:.1f} pp")
    z = st.columns(2)
    z[0].metric("Opex ratio, prior year", pct(comp["prior_opex_ratio_pct"]))
    z[1].metric("Opex ratio, latest year", pct(comp["latest_opex_ratio_pct"]))
else:
    st.info(comp.get("message", "Insufficient historical data for this analysis."))
st.subheader("Recent trend (latest 3 months vs preceding 3)")
rec = k["recent_trend"]
if rec.get("sufficient_data"):
    st.metric("Revenue change", pct(rec["change_pct"]), delta=signed_kes(rec["recent_period_revenue"] - rec["preceding_period_revenue"]))
else:
    st.info(rec.get("message", "Insufficient historical data for this analysis."))
st.download_button("Monthly series (CSV)", m.drop(columns=["month"]).to_csv(index=False).encode("utf-8"), "monthly_financials.csv", "text/csv")
