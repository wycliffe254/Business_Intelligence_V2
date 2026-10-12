"""Runs every analytics module on the analytical dataset and returns one KPI dict."""
from __future__ import annotations
import pandas as pd
from src.analytics import efficiency, growth, inventory, liquidity, profitability
from src.data.cleaning import reconstruct_inventory


def compute_all_kpis(analytical_df: pd.DataFrame, inventory_summary: pd.DataFrame | None = None, availability: dict | None = None) -> dict:
    """`availability` = which analyses the uploaded columns support (see src/data/schema.py); None = everything."""
    av = availability or profitability._all_available()
    inc = analytical_df[analytical_df["include_in_kpis"]].copy()
    core = profitability.compute_core_profitability(inc, av)
    monthly = growth.monthly_series(inc, av)
    inv_summary = inventory_summary if inventory_summary is not None else reconstruct_inventory(analytical_df)
    return {
        "availability": av,
        "core": core,
        "expense_breakdown": profitability.expense_breakdown(inc),
        "breakeven": profitability.break_even_analysis(inc, core),
        "collections": liquidity.collection_analysis(inc, av),
        "monthly": monthly,
        "recent_trend": growth.recent_trend(monthly),
        "comparable_yoy": growth.comparable_period_yoy(monthly),
        "profitability_stability": growth.profitability_stability(monthly),
        "product_category": efficiency.product_category_performance(inc, av),
        "product": efficiency.product_performance(inc, av),
        "branch": efficiency.branch_performance(inc, av),
        "channel": efficiency.channel_performance(inc, av),
        "customer_type": efficiency.customer_type_performance(inc, av),
        "inventory_summary": inv_summary,
        "inventory_status": inventory.inventory_status(inv_summary, av["inventory"]),
        "inventory_turnover": inventory.inventory_turnover(inc, inv_summary, core, av["inventory"]),
    }
