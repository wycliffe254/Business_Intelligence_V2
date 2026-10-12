import pandas as pd
import streamlit as st

st.set_page_config(page_title="Metric Definitions", layout="wide")
st.title("Metric Definitions & Traceability")
st.caption("Every KPI is traceable to its formula, source columns, exclusions and assumptions.")
ROWS = [
 ("Adjusted Net Revenue", "Net sales of SALE rows - net value of REFUND rows", "net_sales_kes, transaction_type", "Duplicate IDs, invalid/missing dates, invalid sale quantities", "Refund value is read from net_sales_kes on REFUND rows"),
 ("COGS", "Sum of cogs_kes on SALE rows", "cogs_kes, transaction_type", "Same exclusions; purchase rows are NOT COGS", ""),
 ("Gross Profit", "Adjusted Revenue - COGS", "net_sales_kes, cogs_kes", "Same exclusions", ""),
 ("Gross Margin %", "Gross Profit / Adjusted Revenue x 100", "net_sales_kes, cogs_kes, transaction_type", "Same exclusions", ""),
 ("Operating Expenses", "Sum of expense_amount_kes on EXPENSE rows", "expense_amount_kes, transaction_type", "Same exclusions; refunds and purchases are not operating expenses", ""),
 ("Operating Profit / Margin %", "Gross Profit - Opex;  Operating Profit / Adjusted Revenue x 100", "as above", "Same exclusions", ""),
 ("Operating Expense Ratio %", "Operating Expenses / Adjusted Revenue x 100", "as above", "Same exclusions", ""),
 ("Discount Rate %", "(gross_sales - net_sales) over SALE rows / gross_sales x 100", "gross_sales_kes, net_sales_kes", "Same exclusions", "Weighted by sales value, not an average of row percentages"),
 ("Refund Rate %", "Refund value / Gross Sales x 100", "net_sales_kes (REFUND), gross_sales_kes (SALE)", "Same exclusions", ""),
 ("Average Transaction Value", "Adjusted Revenue / count of valid SALE rows (quantity > 0)", "net_sales_kes, quantity", "Invalid-quantity sales excluded", ""),
 ("Collection Coverage % (ESTIMATE)", "(amount received at sale on credit-like sales + all CUSTOMER_PAYMENT cash_in) / credit-like sales value x 100", "amount_received_kes, net_sales_kes, cash_in_kes", "Same exclusions", "Credit-like = amount_received < net_sales. No invoice aging exists, so this is portfolio-level and not DSO"),
 ("Recent revenue trend", "Latest 3 months vs preceding 3 months", "monthly adjusted revenue", "Needs >= 6 months", "Otherwise: 'Insufficient historical data for this analysis.'"),
 ("Comparable-period growth", "Same calendar months in the two latest years (months present in both)", "monthly adjusted revenue", "Never compares unequal month counts", "Window Jan-Aug by default"),
 ("Profitable months", "Months with positive operating profit / total months", "monthly operating profit", "", ""),
 ("Approximate break-even revenue", "Average monthly Opex / Gross Margin (fraction)", "monthly Opex, gross margin", "", "Approximate analytical estimate based on observed margin and costs; not a forecast"),
 ("Reconstructed inventory", "Running sum of inventory_qty_change per product in date order", "inventory_qty_change, product_name, parsed date", "Duplicates and undated rows", "Negative running stock => inventory unusable for scoring; no turnover shown"),
 ("Inventory turnover", "COGS / average inventory value (opening and ending total value at cost)", "inventory_value_change_kes, cogs_kes", "Only when inventory integrity passes", "Two-point average"),
 ("Financial Health Score", "Profitability 35 + Liquidity & Collections 20 + Cost & Efficiency 20 + Growth & Stability 15 + Working Capital / Data Reliability 10", "KPIs above", "", "Sub-score curves live in config/settings.py (marked ASSUMPTION)"),
 ("RAG status", "70-100 GREEN, 50-69 AMBER, 0-49 RED; five critical-risk overrides force RED", "Score, KPIs, data-quality report", "", "Override reasons are always displayed"),
 ("Data Quality Score", "Weighted composite of duplicates, missing values, dates, quantities, label consistency, payment labels, financial consistency; capped below AMBER if inventory integrity fails", "Cleaning flags", "", "Project-defined control thresholds, not industry standards"),
]
st.dataframe(pd.DataFrame(ROWS, columns=["Metric", "Formula", "Source fields", "Excluded", "Notes / assumptions"]), hide_index=True)

st.subheader("Minimum data and what each column unlocks")
st.markdown("Your file does **not** need all 32 sample columns. The minimum is a **date** column and at least one **amount** column "
            "(`net_sales_kes` for sales and/or `expense_amount_kes` for expenses). Missing columns only limit which analyses are possible; "
            "measures that cannot be calculated are shown as *not available*, never as zero.")
from src.data.schema import CAPABILITIES
st.dataframe(pd.DataFrame([{"Analysis": l, "Columns needed": ", ".join(req), "What it unlocks": u} for _, l, req, u in CAPABILITIES]), hide_index=True)
st.caption("Fallbacks used when possible (always disclosed): transaction_type inferred from amounts; net_sales from gross sales or quantity x unit price less discount; "
           "cogs from quantity x unit cost. Common header variants (date, sales, revenue, expenses, cogs, product, qty, branch...) are recognised automatically.")
