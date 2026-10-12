"""Monthly series, recent 3v3 trend, like-for-like year-on-year comparison, profitable months."""
from __future__ import annotations
import pandas as pd
from config.settings import COMPARABLE_PERIOD_MONTHS, RECENT_TREND_MONTHS

INSUFFICIENT = "Insufficient historical data for this analysis."
MONTH_ABBR = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def monthly_series(df: pd.DataFrame, avail: dict | None = None) -> pd.DataFrame:
    av = avail or {"gross_profit": True, "operating_expenses": True, "operating_profit": True}
    valid = df[df["parsed_date"].notna()].copy()
    if valid.empty:
        return pd.DataFrame(columns=["month", "revenue", "cogs", "gross_profit", "operating_expenses",
                                     "operating_profit", "gross_margin_pct", "month_str"])
    valid["month"] = valid["parsed_date"].dt.to_period("M")
    sale = valid[valid["transaction_type"] == "SALE"]
    refund = valid[valid["transaction_type"] == "REFUND"]
    expense = valid[valid["transaction_type"] == "EXPENSE"]
    months = pd.period_range(valid["month"].min(), valid["month"].max(), freq="M")

    def monthly_sum(frame, col):
        """Sum per month as float64, safe for empty groups (e.g. a dataset with no refunds)."""
        s = frame.groupby("month")[col].sum().astype("float64")
        return s.reindex(months).fillna(0.0)

    out = pd.DataFrame(index=months)
    out["revenue"] = monthly_sum(sale, "net_sales_kes") - monthly_sum(refund, "net_sales_kes")
    nan = float("nan")
    out["cogs"] = monthly_sum(sale, "cogs_kes") if av.get("gross_profit", True) else nan
    out["gross_profit"] = out["revenue"] - out["cogs"]
    out["operating_expenses"] = monthly_sum(expense, "expense_amount_kes") if av.get("operating_expenses", True) else nan
    out["operating_profit"] = (out["gross_profit"] - out["operating_expenses"]) if av.get("operating_profit", True) else nan
    out["gross_margin_pct"] = (out["gross_profit"] / out["revenue"].where(out["revenue"] != 0) * 100).fillna(0.0)
    out = out.reset_index().rename(columns={"index": "month"})
    out["month_str"] = out["month"].astype(str)
    return out


def recent_trend(monthly: pd.DataFrame, n: int = RECENT_TREND_MONTHS) -> dict:
    if len(monthly) < 2 * n:
        return {"sufficient_data": False, "message": INSUFFICIENT}
    recent = float(monthly.tail(n)["revenue"].sum())
    prev = float(monthly.tail(2 * n).head(n)["revenue"].sum())
    return {"sufficient_data": True, "recent_period_revenue": recent, "preceding_period_revenue": prev,
            "change_pct": ((recent - prev) / prev * 100) if prev else 0.0, "n_months": n}


def comparable_period_yoy(monthly: pd.DataFrame, window=COMPARABLE_PERIOD_MONTHS) -> dict:
    """Compare the SAME calendar months in the two latest years (never 8 vs 12 months).
    Only months present in BOTH years inside the window are compared."""
    if monthly.empty:
        return {"sufficient_data": False, "message": INSUFFICIENT}
    m = monthly.copy()
    m["year"] = m["month"].apply(lambda p: p.year)
    m["mo"] = m["month"].apply(lambda p: p.month)
    years = sorted(m["year"].unique())
    if len(years) < 2:
        return {"sufficient_data": False, "message": INSUFFICIENT}
    latest, prior = years[-1], years[-2]
    lo, hi = window
    in_win = m[(m["mo"] >= lo) & (m["mo"] <= hi)]
    common = sorted(set(in_win[in_win["year"] == latest]["mo"]) & set(in_win[in_win["year"] == prior]["mo"]))
    if not common:
        return {"sufficient_data": False, "message": INSUFFICIENT}
    a = in_win[(in_win["year"] == latest) & in_win["mo"].isin(common)]
    b = in_win[(in_win["year"] == prior) & in_win["mo"].isin(common)]

    def agg(x):
        rev = x["revenue"].sum()
        gp = x["gross_profit"].sum() if x["gross_profit"].notna().any() else float("nan")
        ox = x["operating_expenses"].sum() if x["operating_expenses"].notna().any() else float("nan")
        return rev, gp, ox, (gp / rev * 100 if rev else float("nan")), (ox / rev * 100 if rev else float("nan"))
    ar, agp, _, am, ao = agg(a)
    br, bgp, _, bm, bo = agg(b)
    return {
        "sufficient_data": True, "prior_year": int(prior), "latest_year": int(latest),
        "months_compared": [MONTH_ABBR[i] for i in common],
        "period_label": f"{MONTH_ABBR[common[0]]}\u2013{MONTH_ABBR[common[-1]]}",
        "prior_period_revenue": float(br), "latest_period_revenue": float(ar),
        "revenue_change_pct": float((ar - br) / br * 100) if br else 0.0,
        "prior_gross_profit": float(bgp), "latest_gross_profit": float(agp),
        "gross_profit_change_pct": float((agp - bgp) / bgp * 100) if (bgp == bgp and bgp) else float("nan"),
        "prior_gross_margin_pct": float(bm), "latest_gross_margin_pct": float(am),
        "margin_change_pp": float(am - bm),
        "prior_opex_ratio_pct": float(bo), "latest_opex_ratio_pct": float(ao),
    }


def profitability_stability(monthly: pd.DataFrame) -> dict:
    total = len(monthly)
    if not total or monthly["operating_profit"].isna().all():
        return {"available": False, "total_months": total, "profitable_months": 0, "pct_profitable_months": float("nan"),
                "longest_consecutive_loss_streak": 0}
    profitable = int((monthly["operating_profit"] > 0).sum())
    longest = cur = 0
    for flag in (monthly["operating_profit"] <= 0).tolist() if total else []:
        cur = cur + 1 if flag else 0
        longest = max(longest, cur)
    return {"available": True, "total_months": total, "profitable_months": profitable,
            "pct_profitable_months": (profitable / total * 100) if total else 0.0,
            "longest_consecutive_loss_streak": longest}
