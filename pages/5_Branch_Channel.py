import plotly.express as px
import streamlit as st
from src.ui_state import get_result

st.set_page_config(page_title="Branch & Channel Analysis", layout="wide")
st.title("Branch & Channel Analysis")
r = get_result()
k = r["kpis"]
branch, channel = k["branch"], k["channel"]

st.subheader("Branch performance")
if not len(branch):
    st.info("Branch analysis is not available: the file needs a branch column.")
if len(branch):
    a, b = st.columns(2)
    a.plotly_chart(px.bar(branch, x="branch", y="adjusted_revenue", title="Revenue by branch"))
    b.plotly_chart(px.bar(branch, x="branch", y="gross_margin_pct", title="Gross margin % by branch"))
    st.dataframe(branch[["branch", "adjusted_revenue", "transactions", "avg_transaction_value", "gross_margin_pct", "revenue_share_pct"]].round(2), hide_index=True)
    if len(branch) >= 2:
        top_rev, top_m = branch.iloc[0], branch.sort_values("gross_margin_pct", ascending=False).iloc[0]
        if top_rev["branch"] != top_m["branch"]:
            st.info(f"{top_rev['branch']} has the highest revenue but {top_m['branch']} has the highest gross margin: more revenue is not automatically more profit.")

st.subheader("Customer mix by branch")
inc = r["analytical_df"]
inc = inc[inc["include_in_kpis"] & (inc["transaction_type"] == "SALE")]
mix = inc.groupby(["branch_norm", "customer_type_norm"])["net_sales_kes"].sum().reset_index()
if len(mix):
    st.plotly_chart(px.bar(mix, x="branch_norm", y="net_sales_kes", color="customer_type_norm", barmode="stack",
                           labels={"branch_norm": "Branch", "net_sales_kes": "Net sales (KES)", "customer_type_norm": "Customer type"}))

st.subheader("Sales channel performance")
if not len(channel):
    st.info("Channel analysis is not available: the file needs a sales_channel column.")
if len(channel):
    a, b = st.columns(2)
    a.plotly_chart(px.bar(channel, x="sales_channel", y="adjusted_revenue", title="Revenue by channel"))
    b.plotly_chart(px.bar(channel, x="sales_channel", y="gross_margin_pct", title="Gross margin % by channel"))
    st.dataframe(channel[["sales_channel", "adjusted_revenue", "transactions", "avg_transaction_value", "gross_margin_pct", "revenue_share_pct"]].round(2), hide_index=True)
st.download_button("Branch table (CSV)", branch.to_csv(index=False).encode("utf-8"), "branch_performance.csv", "text/csv")
