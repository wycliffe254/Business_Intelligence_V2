"""Inventory analytics with the integrity gate (Spec Sec. 4 / 24)."""
from __future__ import annotations
import pandas as pd

UNAVAILABLE_MESSAGE = ("Inventory analysis unavailable for financial scoring. Reason: Inventory records cannot "
                       "currently support a reliable stock-on-hand calculation.")


NOT_ASSESSABLE_MESSAGE = ("Inventory analysis is not available for this file: it needs inventory_qty_change and product_name "
                          "to reconstruct stock on hand.")


def inventory_status(inventory_summary: pd.DataFrame, assessable: bool = True) -> dict:
    if not assessable:
        return {"assessable": False, "usable_for_scoring": False, "negative_stock_products": [], "message": NOT_ASSESSABLE_MESSAGE}
    neg = inventory_summary.loc[inventory_summary["has_negative_stock"], "product_name"].tolist()
    ok = len(neg) == 0
    return {"assessable": True, "usable_for_scoring": ok, "negative_stock_products": neg,
            "message": "Inventory reconstruction is internally consistent for all products." if ok else UNAVAILABLE_MESSAGE}


def inventory_turnover(df, inventory_summary: pd.DataFrame, core: dict, assessable: bool = True):
    """COGS / Average Inventory VALUE (two-point average of opening and ending total value at cost).
    Returns None when inventory integrity fails."""
    if not inventory_status(inventory_summary, assessable)["usable_for_scoring"] or core["cogs"] != core["cogs"]:
        return None
    if not {"opening_value", "ending_value"} <= set(inventory_summary.columns):
        return None
    opening = float(inventory_summary["opening_value"].sum())
    ending = float(inventory_summary["ending_value"].sum())
    avg = (opening + ending) / 2
    if avg <= 0:
        return None
    return {"turnover_ratio": core["cogs"] / avg, "opening_inventory_value": opening,
            "ending_inventory_value": ending, "average_inventory_value": avg}
