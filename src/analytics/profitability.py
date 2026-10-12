"""Revenue, COGS, gross profit/margin, operating expenses/profit/margin, discount, refund, break-even."""
from __future__ import annotations
import pandas as pd


NAN = float("nan")


def _all_available():
    return {"revenue": True, "gross_profit": True, "operating_expenses": True, "operating_profit": True,
            "discounts": True, "refunds": True, "collections": True, "inventory": True, "product": True,
            "customer": True, "branch": True, "channel": True, "time": True}


def compute_core_profitability(df: pd.DataFrame, avail: dict | None = None) -> dict:
    """`df` must already be filtered to include_in_kpis rows. KPIs whose source columns are absent are NaN (shown as
    'not available'), never silently zero."""
    av = avail or _all_available()
    sale = df[df["transaction_type"] == "SALE"]
    refund = df[df["transaction_type"] == "REFUND"]
    expense = df[df["transaction_type"] == "EXPENSE"]

    sales_net = float(sale["net_sales_kes"].sum()) if av["revenue"] else NAN
    refunds = float(refund["net_sales_kes"].sum()) if av["revenue"] else NAN
    adjusted_revenue = sales_net - refunds if av["revenue"] else NAN
    gross_sales = float(sale["gross_sales_kes"].sum()) if av["discounts"] else NAN
    refund_base = gross_sales if av["discounts"] else sales_net      # refund rate base: gross sales, else net sales

    cogs = float(sale["cogs_kes"].sum()) if av["gross_profit"] else NAN
    gross_profit = adjusted_revenue - cogs if av["gross_profit"] else NAN
    opex = float(expense["expense_amount_kes"].sum()) if av["operating_expenses"] else NAN
    operating_profit = gross_profit - opex if av["operating_profit"] else NAN
    discount_value = float((sale["gross_sales_kes"] - sale["net_sales_kes"]).sum()) if av["discounts"] else NAN
    valid_sales = int((sale["quantity"] > 0).sum()) if sale["quantity"].notna().any() else int(len(sale))

    def ratio(a, b):
        return (a / b * 100) if (b == b and a == a and b) else NAN

    return {
        "gross_sales": gross_sales, "sales_net_revenue": sales_net, "refunds_value": refunds,
        "adjusted_revenue": adjusted_revenue, "cogs": cogs, "gross_profit": gross_profit,
        "gross_margin_pct": ratio(gross_profit, adjusted_revenue),
        "operating_expenses": opex, "operating_profit": operating_profit,
        "operating_margin_pct": ratio(operating_profit, adjusted_revenue),
        "opex_ratio_pct": ratio(opex, adjusted_revenue),
        "discount_value": discount_value, "discount_rate_pct": ratio(discount_value, gross_sales),
        "refund_rate_pct": ratio(refunds, refund_base) if av["refunds"] else NAN,
        "valid_sales_transactions": valid_sales,
        "average_transaction_value": (adjusted_revenue / valid_sales) if (valid_sales and av["revenue"]) else NAN,
    }


def expense_breakdown(df: pd.DataFrame) -> pd.DataFrame:
    exp = df[df["transaction_type"] == "EXPENSE"].copy()
    exp["expense_category_norm"] = exp["expense_category_norm"].astype("object").where(exp["expense_category_norm"].notna(), "Unspecified")
    b = (exp.groupby("expense_category_norm")["expense_amount_kes"].sum()
         .sort_values(ascending=False).reset_index()
         .rename(columns={"expense_category_norm": "expense_category", "expense_amount_kes": "amount_kes"}))
    total = b["amount_kes"].sum()
    b["share_pct"] = (b["amount_kes"] / total * 100) if total else 0.0
    return b


def break_even_analysis(df: pd.DataFrame, core: dict) -> dict:
    """Approximate break-even revenue = avg monthly opex / gross margin (Spec Sec. 31).
    An approximate analytical estimate, NOT a forecast."""
    n_months = max(df.loc[df["parsed_date"].notna(), "parsed_date"].dt.to_period("M").nunique(), 1)
    avg_rev = core["adjusted_revenue"] / n_months
    avg_gp = core["gross_profit"] / n_months
    avg_opex = core["operating_expenses"] / n_months
    gm = core["gross_margin_pct"] / 100.0
    be = avg_opex / gm if (gm == gm and gm > 0 and avg_opex == avg_opex) else float("nan")
    gap = ((be - avg_rev) / avg_rev * 100) if (avg_rev and avg_rev == avg_rev and be == be) else float("nan")
    return {"n_months": n_months, "avg_monthly_revenue": avg_rev, "avg_monthly_gross_profit": avg_gp,
            "avg_monthly_opex": avg_opex, "breakeven_revenue": be, "revenue_gap_pct": gap}
