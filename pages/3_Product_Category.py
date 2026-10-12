import plotly.express as px
import streamlit as st
from src.ui_state import get_result

st.set_page_config(page_title="Product & Category Analysis", layout="wide")
st.title("Product & Category Analysis")
r = get_result()
k = r["kpis"]
cat, prod = k["product_category"], k["product"]
st.caption("Quadrants are relative to the median category and use neutral language: a low-revenue or low-margin category is a prompt "
           "for investigation, not a verdict that it is a 'bad' product.")

if not len(cat):
    st.info("Product/category analysis is not available: the file needs product_category (and/or product_name) together with sales values.")
if len(cat):
    fig = px.scatter(cat, x="revenue_share_pct", y="gross_margin_pct", size=cat["adjusted_revenue"].clip(lower=1), color="quadrant", hover_name="product_category",
                     labels={"revenue_share_pct": "Revenue share (%)", "gross_margin_pct": "Gross margin (%)"})
    st.plotly_chart(fig)
    show = ["product_category", "adjusted_revenue", "units_sold", "cogs", "gross_profit", "gross_margin_pct", "revenue_share_pct",
            "discount_rate_pct", "refund_rate_pct", "quadrant"]
    st.dataframe(cat[show].round(2), hide_index=True)
    if cat["gross_margin_pct"].isna().all():
        st.info("Gross margin by category is not available because cost of goods sold is missing from the file; revenue measures are shown.")
    flagged = cat[cat["quadrant"] == "High revenue / Low margin"]["product_category"].tolist()
    if flagged:
        st.info(f"{', '.join(flagged)}: a larger-than-median share of revenue but a lower-than-median gross margin, so margin work here would move overall profitability the most.")

st.subheader("Product drill-down")
choices = ["All categories"] + cat["product_category"].tolist()
pick = st.selectbox("Category", choices)
inc = r["analytical_df"]
p = prod
if pick != "All categories":
    names = inc[(inc["product_category_norm"] == pick)]["product_name"].dropna().unique()
    p = prod[prod["product_name"].isin(names)]
st.dataframe(p[["product_name", "adjusted_revenue", "units_sold", "cogs", "gross_profit", "gross_margin_pct", "revenue_share_pct",
                "discount_rate_pct", "refund_rate_pct"]].round(2), hide_index=True)
st.download_button("Category table (CSV)", cat.to_csv(index=False).encode("utf-8"), "category_performance.csv", "text/csv")
st.download_button("Product table (CSV)", prod.to_csv(index=False).encode("utf-8"), "product_performance.csv", "text/csv")
