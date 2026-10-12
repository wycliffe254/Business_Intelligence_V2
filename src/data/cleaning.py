"""
Cleaning / preparation layer.

RAW DATA is never modified or deleted. This module returns an ANALYTICAL
DataFrame = raw + derived/flag columns, with `include_in_kpis` and
`exclude_reason` recording exactly which rows are excluded from KPIs and why.
"""
from __future__ import annotations
import re
import numpy as np
import pandas as pd
from config.settings import FINANCIAL_TOLERANCE_KES, NUMERIC_COLUMNS, VALID_TRANSACTION_TYPES
from src.utils.dates import parse_date_series

CATEGORY_COLUMNS = ["branch", "customer_type", "sales_channel", "product_category",
                    "expense_category", "payment_method"]


def _to_numeric(series: pd.Series):
    """Coerce to numbers, tolerating thousands separators and KES/KSh prefixes."""
    text = series.astype("object").where(series.notna(), None)
    cleaned = text.map(lambda v: re.sub(r"(?i)kes|ksh|[,\s]", "", v) if isinstance(v, str) else v)
    numeric = pd.to_numeric(cleaned, errors="coerce")
    present = series.notna() & (series.astype(str).str.strip() != "")
    return numeric, present & numeric.isna()


def _canonicalize(series: pd.Series):
    """Map spelling/case/spacing variants of the same label to the most
    frequent spelling. Returns (canonical_series, is_inconsistent_mask)."""
    stripped = series.astype("object").where(series.notna(), None)
    stripped = stripped.map(lambda v: v.strip() if isinstance(v, str) else v)
    def _key(v):
        if not isinstance(v, str):
            return None
        k = "".join(ch for ch in v.lower() if ch.isalnum())
        return k[:-1] if len(k) > 4 and k.endswith("s") else k   # singular/plural variants
    key = stripped.map(_key)
    tmp = pd.DataFrame({"s": stripped, "k": key}).dropna()
    canon = {}
    for k, grp in tmp.groupby("k"):
        canon[k] = grp["s"].value_counts().idxmax()
    canonical = key.map(lambda k: canon.get(k) if k is not None else None)
    raw = series.astype("object")
    inconsistent = raw.notna() & canonical.notna() & (raw != canonical)
    canonical = canonical.where(canonical.notna(), None)
    return canonical, inconsistent.astype(bool)


def clean_dataset(raw_df: pd.DataFrame, present_columns=None) -> dict:
    """`present_columns` = columns that genuinely hold data in the upload (None = assume all). Checks that depend on a
    column that is absent are skipped rather than producing false findings."""
    df = raw_df.copy()
    has = (lambda c: True) if present_columns is None else (lambda c: c in set(present_columns))
    df["_row_id"] = np.arange(len(df))

    # 1. dates
    info = parse_date_series(df["transaction_date"])
    df["parsed_date"] = info["parsed_date"]
    df["is_valid_date"] = info["is_valid_date"]
    df["is_ambiguous_date"] = info["is_ambiguous_date"]

    # 2. numerics
    invalid_any = pd.Series(False, index=df.index)
    for col in NUMERIC_COLUMNS:
        num, bad = _to_numeric(df[col])
        df[col] = num
        invalid_any |= bad
    df["has_invalid_numeric_field"] = invalid_any
    inv_num, inv_bad = _to_numeric(df["inventory_qty_change"])
    df["inventory_qty_change_numeric"] = inv_num.fillna(0.0)
    df["has_invalid_inventory_qty"] = inv_bad

    # 3. duplicates (first occurrence kept)
    df["is_duplicate_txn_id"] = df.duplicated(subset=["transaction_id"], keep="first") if has("transaction_id") else False
    df["is_valid_transaction_type"] = df["transaction_type"].isin(VALID_TRANSACTION_TYPES)

    # 4. category / label consistency
    any_cat_incons = pd.Series(False, index=df.index)
    for col in CATEGORY_COLUMNS:
        canonical, incons = _canonicalize(df[col])
        df[f"{col}_norm"] = canonical
        df[f"{col}_inconsistent"] = incons
        if col != "payment_method":
            any_cat_incons |= incons
    df["has_inconsistent_category_text"] = any_cat_incons
    df["payment_label_variant"] = df["payment_method_inconsistent"]

    # 5. credit-like sales (payment_method is blank on sales -> infer)
    is_sale = df["transaction_type"] == "SALE"
    can_credit = has("amount_received_kes") and has("net_sales_kes")
    df["is_credit_like_sale"] = (is_sale & (df["amount_received_kes"].fillna(0) < df["net_sales_kes"].fillna(0))) if can_credit else False
    df["payment_method_missing_for_sale"] = (is_sale & (
        df["payment_method"].isna() | (df["payment_method"].astype(str).str.strip() == ""))) if has("payment_method") else False

    # 6. invalid sale quantities
    df["is_invalid_sale_quantity"] = (is_sale & (df["quantity"].fillna(0) <= 0) & (df["net_sales_kes"].fillna(0) > 0)) if has("quantity") else False

    # 7. financial consistency.
    # NOTE: discount_pct is stored as a FRACTION (0.02 = 2%), not 0-100.
    expected_net = df["gross_sales_kes"].fillna(0) * (1 - df["discount_pct"].fillna(0))
    net_mismatch = is_sale & ((expected_net - df["net_sales_kes"].fillna(0)).abs() > FINANCIAL_TOLERANCE_KES)
    expected_gp = df["net_sales_kes"].fillna(0) - df["cogs_kes"].fillna(0)
    gp_mismatch = is_sale & ((expected_gp - df["gross_profit_kes"].fillna(0)).abs() > FINANCIAL_TOLERANCE_KES)
    net_ok = has("gross_sales_kes") and has("discount_pct") and has("net_sales_kes")
    gp_ok = has("cogs_kes") and has("gross_profit_kes") and has("net_sales_kes")
    df["has_financial_inconsistency"] = (net_mismatch if net_ok else False) | (gp_mismatch if gp_ok else False)

    # 8. critical fields
    df["missing_critical_field"] = (~df["is_valid_date"]) | (df["transaction_id"].isna() if has("transaction_id") else False) | df["transaction_type"].isna()

    # 9. KPI inclusion + reasons
    reasons = pd.Series("", index=df.index)
    reasons = reasons.where(~df["is_duplicate_txn_id"], reasons + "duplicate_transaction_id;")
    reasons = reasons.where(df["is_valid_date"], reasons + "invalid_date;")
    reasons = reasons.where(~df["missing_critical_field"], reasons + "missing_critical_field;")
    reasons = reasons.where(~df["is_invalid_sale_quantity"], reasons + "invalid_sale_quantity;")
    df["exclude_reason"] = reasons
    df["include_in_kpis"] = df["exclude_reason"] == ""

    exclusion_summary = {
        "duplicate_transaction_id": int(df["is_duplicate_txn_id"].sum()),
        "invalid_date": int((~df["is_valid_date"]).sum()),
        "missing_critical_field": int(df["missing_critical_field"].sum()),
        "invalid_sale_quantity": int(df["is_invalid_sale_quantity"].sum()),
        "total_excluded_rows": int((~df["include_in_kpis"]).sum()),
        "total_rows": int(len(df)),
    }
    flag_names = ["is_duplicate_txn_id", "is_valid_date", "is_ambiguous_date", "has_invalid_numeric_field",
                  "has_invalid_inventory_qty", "is_invalid_sale_quantity", "has_inconsistent_category_text",
                  "payment_label_variant", "payment_method_missing_for_sale", "has_financial_inconsistency",
                  "missing_critical_field"]
    flags = {n: df[n] for n in flag_names}
    return {"analytical_df": df, "flags": flags, "exclusion_summary": exclusion_summary}


def reconstruct_inventory(analytical_df: pd.DataFrame) -> pd.DataFrame:
    """Rebuild running stock (units) and stock value (KES at cost) per product.

    Columns: product_name, ending_stock, min_running_stock, opening_value,
    ending_value, has_negative_stock. Duplicate and undated rows are excluded.
    """
    d = analytical_df
    df = d[d["is_valid_date"] & d["product_name"].notna()
           & (d["product_name"].astype(str).str.strip() != "") & (~d["is_duplicate_txn_id"])].copy()
    df = df.sort_values(["product_name", "parsed_date", "_row_id"])
    df["inv_value_change"] = df["inventory_value_change_kes"].fillna(0.0)
    df["running_stock"] = df.groupby("product_name")["inventory_qty_change_numeric"].cumsum()
    df["running_value"] = df.groupby("product_name")["inv_value_change"].cumsum()
    summary = df.groupby("product_name").agg(
        ending_stock=("running_stock", "last"), min_running_stock=("running_stock", "min"),
        opening_value=("running_value", "first"), ending_value=("running_value", "last"),
    ).reset_index()
    summary["has_negative_stock"] = summary["min_running_stock"] < 0
    return summary
