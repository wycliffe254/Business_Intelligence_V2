"""Segment analytics: product, category, branch, channel, customer type."""
from __future__ import annotations
import pandas as pd


SEG_COLUMNS = ["revenue", "gross_sales", "units_sold", "cogs", "transactions", "discount_value", "credit_sales_value", "refunds",
               "adjusted_revenue", "gross_profit", "gross_margin_pct", "revenue_share_pct", "discount_rate_pct", "refund_rate_pct",
               "avg_transaction_value"]


def _segment(df: pd.DataFrame, col: str, avail: dict | None = None) -> pd.DataFrame:
    """Per-segment performance. Measures whose source columns are absent are NaN ('not available'), not zero."""
    av = avail or {}
    if col not in df.columns or not df[col].notna().any():
        return pd.DataFrame(columns=[col] + SEG_COLUMNS)
    # Rows with a blank segment value go into an explicit "Unspecified" bucket so every table reconciles to the total
    # (groupby would otherwise drop them silently and leave shares summing to 100% of a smaller number).
    df = df.copy()
    df[col] = df[col].astype("object").where(df[col].notna(), "Unspecified")
    out = _segment_core(df, col)
    nan = float("nan")
    if not av.get("gross_profit", True):
        for c in ["cogs", "gross_profit", "gross_margin_pct"]:
            out[c] = nan
    if not av.get("discounts", True):
        for c in ["discount_value", "discount_rate_pct", "gross_sales"]:
            out[c] = nan
    if not av.get("collections", True):
        out["credit_sales_value"] = nan
    return out


def _segment_core(df: pd.DataFrame, col: str) -> pd.DataFrame:
    sale = df[df["transaction_type"] == "SALE"].copy()
    refund = df[df["transaction_type"] == "REFUND"]
    sale["_disc"] = sale["gross_sales_kes"] - sale["net_sales_kes"]
    sale["_credit"] = sale["net_sales_kes"].where(sale["is_credit_like_sale"], 0.0)
    g = sale.groupby(col).agg(
        revenue=("net_sales_kes", "sum"), gross_sales=("gross_sales_kes", "sum"),
        units_sold=("quantity", "sum"), cogs=("cogs_kes", "sum"),
        transactions=("transaction_id", "nunique"), discount_value=("_disc", "sum"),
        credit_sales_value=("_credit", "sum"))
    # Refunds can sit in a segment that has no sales (e.g. a "Counter" channel used only for returns): keep them by
    # reindexing to the UNION of both indices. float64 + fillna also keeps this safe when there are no refund rows at all.
    ref_by_seg = refund.groupby(col)["net_sales_kes"].sum().astype("float64")
    g = g.reindex(g.index.union(ref_by_seg.index))
    for c in ["revenue", "gross_sales", "units_sold", "cogs", "transactions", "discount_value", "credit_sales_value"]:
        g[c] = g[c].fillna(0.0)
    g["refunds"] = ref_by_seg.reindex(g.index).fillna(0.0)
    g["adjusted_revenue"] = g["revenue"] - g["refunds"]
    g["gross_profit"] = g["adjusted_revenue"] - g["cogs"]
    safe_rev = g["adjusted_revenue"].where(g["adjusted_revenue"] != 0)
    safe_gs = g["gross_sales"].where(g["gross_sales"] != 0)
    g["gross_margin_pct"] = (g["gross_profit"] / safe_rev * 100).fillna(0.0)
    g.loc[g["revenue"] <= 0, "gross_margin_pct"] = float("nan")     # refunds-only segment: a margin is meaningless
    total = g["adjusted_revenue"].sum()
    g["revenue_share_pct"] = (g["adjusted_revenue"] / total * 100) if total else 0.0
    g["discount_rate_pct"] = (g["discount_value"] / safe_gs * 100).fillna(0.0)
    g["refund_rate_pct"] = (g["refunds"] / safe_gs * 100).fillna(0.0)
    g["avg_transaction_value"] = (g["adjusted_revenue"] / g["transactions"].where(g["transactions"] != 0)).fillna(0.0)
    return g.reset_index().sort_values("adjusted_revenue", ascending=False).reset_index(drop=True)


def product_category_performance(df, avail=None):
    perf = _segment(df, "product_category_norm", avail).rename(columns={"product_category_norm": "product_category"})
    if perf.empty:
        perf["quadrant"] = []
        return perf
    if perf["gross_margin_pct"].isna().all():
        perf["quadrant"] = "Margin not available (cost data missing)"
        return perf
    med_rev, med_m = perf["revenue_share_pct"].median(), perf["gross_margin_pct"].median()   # NaN margins are skipped

    def quad(r):
        if r["gross_margin_pct"] != r["gross_margin_pct"]:
            return "No sales (refunds only)"
        hi_rev, hi_m = r["revenue_share_pct"] >= med_rev, r["gross_margin_pct"] >= med_m
        return {(True, True): "High revenue / High margin", (True, False): "High revenue / Low margin",
                (False, True): "Low revenue / High margin", (False, False): "Low revenue / Low margin"}[(hi_rev, hi_m)]
    perf["quadrant"] = perf.apply(quad, axis=1)
    return perf


def product_performance(df, avail=None):
    return _segment(df, "product_name", avail)


def branch_performance(df, avail=None):
    return _segment(df, "branch_norm", avail).rename(columns={"branch_norm": "branch"})


def channel_performance(df, avail=None):
    return _segment(df, "sales_channel_norm", avail).rename(columns={"sales_channel_norm": "sales_channel"})


def customer_type_performance(df, avail=None):
    return _segment(df, "customer_type_norm", avail).rename(columns={"customer_type_norm": "customer_type"})
