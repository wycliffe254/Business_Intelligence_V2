"""Collection coverage / credit exposure (portfolio-level estimate; Spec Sec. 14/21)."""
from __future__ import annotations
import pandas as pd


def collection_analysis(df: pd.DataFrame, avail: dict | None = None) -> dict:
    nan = float("nan")
    if avail is not None and not avail.get("collections", True):
        opex_ok = avail.get("operating_expenses", True)
        sale = df[df["transaction_type"] == "SALE"]
        opex = float(df[df["transaction_type"] == "EXPENSE"]["expense_amount_kes"].sum())
        return {"available": False, "credit_sales_value": nan, "received_at_sale": nan, "total_customer_payments": nan,
                "collection_coverage_pct": nan, "estimated_uncollected_exposure": nan,
                "revenue_to_opex_ratio": (float(sale["net_sales_kes"].sum()) / opex) if (opex_ok and opex) else nan,
                "note": "Collection coverage is not available: it needs amount_received_kes (and net sales)."}
    sale = df[df["transaction_type"] == "SALE"]
    credit = sale[sale["is_credit_like_sale"]]
    credit_value = float(credit["net_sales_kes"].sum())
    received_at_sale = float(credit["amount_received_kes"].sum())
    collections = float(df[df["transaction_type"] == "CUSTOMER_PAYMENT"]["cash_in_kes"].sum())
    collected = received_at_sale + collections
    coverage = (collected / credit_value * 100) if credit_value else 100.0
    revenue = float(sale["net_sales_kes"].sum())
    opex = float(df[df["transaction_type"] == "EXPENSE"]["expense_amount_kes"].sum())
    return {
        "available": True, "credit_sales_value": credit_value, "received_at_sale": received_at_sale,
        "total_customer_payments": collections, "collection_coverage_pct": coverage,
        "estimated_uncollected_exposure": max(credit_value - collected, 0.0),
        "revenue_to_opex_ratio": (revenue / opex) if (opex and (avail is None or avail.get("operating_expenses", True))) else (float("inf") if avail is None else nan),
        "note": ("Collection coverage is a portfolio-level ESTIMATE: the dataset has no invoice-level aging or "
                 "matching between sales and payments, so it is not a true Days Sales Outstanding (DSO)."),
    }
