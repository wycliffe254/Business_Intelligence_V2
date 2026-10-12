import pandas as pd
import streamlit as st
from src.ui_state import get_result
from src.ui_state import show_completeness
from src.utils.formatting import dq_bands_caption, rag_badge_md

st.set_page_config(page_title="Data Quality", layout="wide")
st.title("Data Quality Report")
r = get_result()
dq, df = r["dq_report"], r["analytical_df"]

st.markdown(f"**Data Quality Score:** {dq.overall_score:.1f} / 100 &nbsp; {rag_badge_md(dq.status)}", unsafe_allow_html=True)
st.caption(dq_bands_caption(dq))
st.caption("Data reliability is assessed separately from financial health. Nothing is silently deleted: excluded rows are listed below with reasons.")

st.subheader("Data completeness")
show_completeness(r, always_table=True)
if dq.not_assessed:
    st.caption("Quality checks skipped because their columns are absent: " + ", ".join(dq.not_assessed))

c = st.columns(4)
c[0].metric("Rows", f"{dq.row_count:,}")
c[1].metric("Columns supplied", len(r["schema"].present_columns))
c[2].metric("Duplicate transaction IDs", dq.duplicate_count)
c[3].metric("Invalid dates", dq.invalid_date_count)
c = st.columns(4)
c[0].metric("Ambiguous dates (day-first assumed)", dq.ambiguous_date_count)
c[1].metric("Invalid sale quantities", dq.invalid_quantity_count)
c[2].metric("Inconsistent category labels", dq.inconsistent_category_count)
c[3].metric("Payment-label variants", dq.inconsistent_payment_label_count)
c = st.columns(4)
c[0].metric("Financial inconsistencies", dq.financial_inconsistency_count)
c[1].metric("Sales without payment method", dq.payment_method_missing_for_sale_count)
c[2].metric("Total missing values (key fields)", sum(dq.missing_value_summary.values()))
c[3].metric("Rows excluded from KPIs", r["exclusion_summary"]["total_excluded_rows"])

st.subheader("Score by dimension")
st.dataframe(pd.DataFrame({"dimension": list(dq.dimension_scores), "score_0_100": [round(v, 1) for v in dq.dimension_scores.values()]}), hide_index=True)

st.subheader("Inventory integrity")
if not dq.inventory_assessed:
    st.info("Inventory integrity could not be assessed: inventory_qty_change and product_name are needed to reconstruct stock on hand.")
elif dq.inventory_integrity_ok:
    st.success("Inventory reconstruction is internally consistent: no product's running stock goes negative.")
else:
    st.error("Inventory analysis unavailable for financial scoring.\n\nReason: Inventory records cannot currently support a reliable stock-on-hand calculation.")
    inv = r["inventory_summary"]
    st.dataframe(inv[inv["has_negative_stock"]][["product_name", "min_running_stock", "ending_stock"]].sort_values("min_running_stock"), hide_index=True)
    neg = df[df["product_name"].isin(dq.inventory_negative_products) & df["is_valid_date"] & ~df["is_duplicate_txn_id"]]
    st.caption("Stock-moving records for the affected products (earliest first):")
    st.dataframe(neg.sort_values(["product_name", "parsed_date"])[["transaction_id", "transaction_date", "transaction_type", "product_name", "inventory_qty_change"]].head(300), hide_index=True)

st.subheader("Missing values by field")
miss = pd.DataFrame([{"field": k, "missing_count": v, "missing_pct": round(v / dq.row_count * 100, 1)} for k, v in dq.missing_value_summary.items()],
                    columns=["field", "missing_count", "missing_pct"])
if len(miss):
    st.dataframe(miss.sort_values("missing_count", ascending=False), hide_index=True)
else:
    st.caption("None of the tracked descriptive fields (branch, customer, channel, payment method, supplier) were supplied.")
st.caption("Some blanks are structural (e.g. no customer on an expense row) and are not errors; they are shown for transparency.")

st.subheader("Limitations")
for lim in dq.limitations:
    st.markdown(f"- {lim}")

st.subheader("Affected records")
cols = ["transaction_id", "transaction_date", "transaction_type", "product_name", "quantity", "net_sales_kes", "exclude_reason"]
tabs = st.tabs(["Duplicate IDs", "Invalid dates", "Ambiguous dates", "Invalid quantities", "Financial inconsistencies", "Label variants", "All excluded rows"])
masks = [df["is_duplicate_txn_id"], ~df["is_valid_date"], df["is_ambiguous_date"], df["is_invalid_sale_quantity"],
         df["has_financial_inconsistency"], df["has_inconsistent_category_text"] | df["payment_label_variant"], ~df["include_in_kpis"]]
for tab, mask in zip(tabs, masks):
    with tab:
        st.write(f"{int(mask.sum())} record(s)")
        st.dataframe(df[mask][cols].head(500), hide_index=True)

st.subheader("Corrections applied to labels")
corr = []
for col in ["branch", "customer_type", "sales_channel", "product_category", "payment_method"]:
    sub = df[df[f"{col}_inconsistent"]][[col, f"{col}_norm"]].value_counts().reset_index()
    sub.columns = ["original_value", "standardised_to", "rows"]
    sub.insert(0, "field", col)
    corr.append(sub)
corr = pd.concat(corr) if corr else pd.DataFrame()
if len(corr):
    st.dataframe(corr, hide_index=True)
else:
    st.write("No label corrections were needed.")

st.subheader("Downloads")
d = st.columns(3)
d[0].download_button("Validated / analytical dataset (CSV)", df.to_csv(index=False).encode("utf-8"), "validated_analytical_dataset.csv", "text/csv")
d[1].download_button("Raw uploaded dataset (CSV)", r["raw_df"].to_csv(index=False).encode("utf-8"), "raw_dataset.csv", "text/csv")
d[2].download_button("Excluded rows with reasons (CSV)", df[~df["include_in_kpis"]][cols].to_csv(index=False).encode("utf-8"), "excluded_rows.csv", "text/csv")
