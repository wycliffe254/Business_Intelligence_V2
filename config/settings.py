"""
Central configuration. Every threshold / weight from the project documentation
or Expected Output Specification is reproduced here; values that had to be
assumed are marked "ASSUMPTION:" so they can be found and changed in one place.
"""

REQUIRED_COLUMNS = [
    "transaction_id", "transaction_date", "transaction_type", "document_no",
    "business_name", "branch", "sales_channel", "customer_type",
    "customer_id", "supplier_name", "product_category", "product_name",
    "quantity", "unit_price_kes", "discount_pct", "gross_sales_kes",
    "net_sales_kes", "unit_cost_kes", "cogs_kes", "gross_profit_kes",
    "expense_category", "expense_amount_kes", "cash_in_kes", "cash_out_kes",
    "amount_received_kes", "accounts_receivable_change_kes",
    "accounts_payable_change_kes", "inventory_qty_change",
    "inventory_value_change_kes", "payment_method", "salesperson_or_staff",
    "manual_entry_flag",
]

NUMERIC_COLUMNS = [
    "quantity", "unit_price_kes", "discount_pct", "gross_sales_kes",
    "net_sales_kes", "unit_cost_kes", "cogs_kes", "gross_profit_kes",
    "expense_amount_kes", "cash_in_kes", "cash_out_kes",
    "amount_received_kes", "accounts_receivable_change_kes",
    "accounts_payable_change_kes", "inventory_value_change_kes",
    "manual_entry_flag",
]

VALID_TRANSACTION_TYPES = [
    "SALE", "PURCHASE", "EXPENSE", "CUSTOMER_PAYMENT", "SUPPLIER_PAYMENT",
    "REFUND", "STOCK_ADJUSTMENT",
]

# ---- Data quality (project-defined control thresholds; ASSUMPTION) ----
DQ_STATUS_BANDS = {"GREEN": 85, "AMBER": 65}   # below AMBER -> RED
DQ_DIMENSION_WEIGHTS = {                        # must sum to 100
    "duplicates": 15, "missing_values": 20, "invalid_dates": 15,
    "invalid_quantities": 15, "inconsistent_categories": 10,
    "inconsistent_payment_labels": 10, "financial_consistency": 15,
}
FINANCIAL_TOLERANCE_KES = 1.0   # ASSUMPTION: rounding tolerance for consistency checks

# ---- RAG bands (Spec Sec. 25) ----
RAG_GREEN_MIN = 70
RAG_AMBER_MIN = 50

# ---- Health score weights (Spec Sec. 19-24) ----
WEIGHTS = {
    "profitability": 35, "liquidity_collections": 20, "cost_efficiency": 20,
    "growth_stability": 15, "data_working_capital": 10,
}
PROFITABILITY_SUBWEIGHTS = {"gross_margin": 15, "operating_margin": 15, "gross_profit_trend": 5}

# ASSUMPTION: piecewise-linear curves (value, points). Only the Collection
# Coverage table is explicit in the spec; the rest are documented assumptions.
GROSS_MARGIN_SCORE_POINTS = [(0, 0), (10, 5), (20, 9), (30, 13), (40, 15)]
OPERATING_MARGIN_SCORE_POINTS = [(-40, 0), (-15, 4), (0, 9), (10, 13), (15, 15)]
GROSS_PROFIT_TREND_SCORE_POINTS = [(-30, 0), (-10, 2), (0, 4), (5, 5)]
COLLECTION_COVERAGE_SCORE_TABLE = [(95, 10), (90, 9), (80, 7.5), (70, 6), (60, 4), (0, 2)]
REVENUE_TO_OPEX_SCORE_POINTS = [(0.5, 0), (1.0, 2), (1.5, 4), (2.0, 5)]
UNCOLLECTED_EXPOSURE_SCORE_POINTS = [(0.0, 5), (0.5, 4), (1.0, 2), (2.0, 0)]
OPEX_RATIO_SCORE_POINTS = [(25, 10), (35, 7), (45, 4), (60, 0)]
DISCOUNT_SCORE_POINTS = [(0, 5), (4, 3), (8, 1), (12, 0)]
REFUND_SCORE_POINTS = [(0, 5), (2, 4), (5, 2), (10, 0)]
REVENUE_TREND_SCORE_POINTS = [(-30, 0), (-10, 4), (0, 7), (10, 10)]
PROFITABLE_MONTHS_SCORE_POINTS = [(0, 0), (50, 2.5), (100, 5)]
DATA_RELIABILITY_SCORE_POINTS = [(30, 0), (50, 3), (70, 6), (85, 8), (100, 10)]
INVENTORY_INTEGRITY_PENALTY_POINTS = 3

# ---- Critical-risk overrides (Spec Sec. 26) ----
CRITICAL_OVERRIDES = {
    "persistent_operating_loss": {"operating_margin_threshold": -10.0, "min_consecutive_months": 3},
    "severe_revenue_deterioration": {"revenue_decline_threshold": -20.0, "requires_margin_deterioration": True},
    "severe_collection_failure": {"collection_coverage_threshold": 60.0},
    "severe_margin_deterioration": {"gross_margin_decline_pp_threshold": 5.0},
}
CRITICAL_DATA_INTEGRITY_SCORE_BELOW = 40  # ASSUMPTION

# ---- Driver thresholds (Spec Sec. 29) ----
DRIVER_THRESHOLDS = {
    "margin_pressure": {"gross_margin_below_pct": 20.0, "gross_margin_decline_pp": 3.0},
    "operating_cost_pressure": {"opex_to_revenue_above_pct": 35.0},
    "revenue_deterioration": {"recent_decline_above_pct": 5.0},
    "persistent_losses": {"min_consecutive_loss_months": 3},
    "weak_collection": {"collection_coverage_below_pct": 90.0},
    "discount_pressure": {"weighted_discount_rate_above_pct": 4.0},
}

RECENT_TREND_MONTHS = 3
COMPARABLE_PERIOD_MONTHS = (1, 8)   # Jan-Aug
CURRENCY_SYMBOL = "KES"
APP_TITLE = "Explainable BI & Financial Health Decision Support System"
APP_SUBTITLE = "Kenyan SME Financial & Operational Intelligence Prototype"
SAMPLE_FILES = {
    "Original sample (messy, unhealthy business)": "data/sample/kenyan_sme_bi_financial_operational_data_1800_records.csv",
    "Synthetic sample (healthy business, intact inventory)": "data/sample/thika_road_hardware_agrovet_synthetic_dataset.csv",
}


# ---- Flexible schema handling (uploads need not match the sample file exactly) ----
# Header aliases (after lower-casing and replacing spaces/hyphens with "_"). ASSUMPTION: common SME spreadsheet headings.
HEADER_ALIASES = {
    "date": "transaction_date", "txn_date": "transaction_date", "transactiondate": "transaction_date",
    "type": "transaction_type", "txn_type": "transaction_type",
    "id": "transaction_id", "txn_id": "transaction_id", "transaction_no": "transaction_id",
    "sales": "net_sales_kes", "revenue": "net_sales_kes", "net_sales": "net_sales_kes", "sales_amount": "net_sales_kes",
    "gross_sales": "gross_sales_kes", "expenses": "expense_amount_kes", "expense": "expense_amount_kes",
    "expense_amount": "expense_amount_kes", "cogs": "cogs_kes", "cost_of_goods_sold": "cogs_kes", "cost_of_sales": "cogs_kes",
    "product": "product_name", "item": "product_name", "item_name": "product_name", "category": "product_category",
    "customer": "customer_id", "customer_name": "customer_id", "qty": "quantity", "unit_price": "unit_price_kes",
    "unit_cost": "unit_cost_kes", "discount": "discount_pct", "payment_mode": "payment_method", "payment_type": "payment_method",
    "location": "branch", "outlet": "branch", "shop": "branch", "channel": "sales_channel", "supplier": "supplier_name",
    "amount_received": "amount_received_kes", "cash_in": "cash_in_kes", "cash_out": "cash_out_kes",
}
COVERAGE_FULL_AT_LEAST = 90.0      # % of the 32 expected columns present -> "full" analysis
COVERAGE_MINIMAL_BELOW = 40.0      # below this -> "minimal" analysis banner (ASSUMPTION)
MIN_ASSESSABLE_POINTS = 50   # ASSUMPTION: below this many of the 100 score points being assessable, no RAG rating is given ("NOT RATED")
