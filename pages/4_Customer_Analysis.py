import plotly.express as px
import streamlit as st
from src.ui_state import get_result
from src.utils.formatting import kes, pct

st.set_page_config(page_title="Customer Analysis", layout="wide")
st.title("Customer Analysis")
r = get_result()
k = r["kpis"]
cust = k["customer_type"]
st.caption("The largest segment by revenue is not necessarily the most profitable; compare revenue share with gross margin.")
if not len(cust):
    st.info("Customer-type analysis is not available: the file needs a customer_type column.")
if len(cust):
    a, b = st.columns(2)
    a.plotly_chart(px.bar(cust, x="customer_type", y="adjusted_revenue", title="Revenue by customer type"))
    b.plotly_chart(px.bar(cust, x="customer_type", y="gross_margin_pct", title="Gross margin % by customer type"))
    st.dataframe(cust[["customer_type", "adjusted_revenue", "transactions", "avg_transaction_value", "gross_margin_pct", "revenue_share_pct",
                       "discount_rate_pct", "credit_sales_value"]].round(2), hide_index=True)
    st.caption("credit_sales_value = value of credit-like sales (customer paid less than the sale amount at the time). It is inferred, not a recorded payment type.")

st.subheader("Credit and collection signal (portfolio-level estimate)")
c = k["collections"]
x = st.columns(3)
x[0].metric("Credit-like sales value", kes(c["credit_sales_value"]))
x[1].metric("Collection coverage", pct(c["collection_coverage_pct"]))
if not c.get("available", True):
    st.info("Collection analysis is not available: the file needs amount_received_kes.")
x[2].metric("Estimated uncollected exposure", kes(c["estimated_uncollected_exposure"]))
st.caption(c["note"])

st.subheader("Top customers by revenue")
inc = r["analytical_df"]
inc = inc[inc["include_in_kpis"] & (inc["transaction_type"] == "SALE") & inc["customer_id"].notna()]
if len(inc):
    t = inc.groupby("customer_id").agg(customer_type=("customer_type_norm", "first"), revenue=("net_sales_kes", "sum"), transactions=("transaction_id", "nunique"),
                                         credit_like_sales=("is_credit_like_sale", "sum")).sort_values("revenue", ascending=False).head(15).reset_index()
    st.dataframe(t.round(2), hide_index=True)
st.download_button("Customer-type table (CSV)", cust.to_csv(index=False).encode("utf-8"), "customer_type_performance.csv", "text/csv")
