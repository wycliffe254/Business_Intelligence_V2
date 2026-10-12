"""Rule-based driver detection A-G (Spec Sec. 29). Every driver carries its evidence."""
from __future__ import annotations
from dataclasses import dataclass, field
from config import settings as S


@dataclass
class Driver:
    code: str
    name: str
    triggered: bool
    evidence: dict = field(default_factory=dict)
    narrative: str = ""
    assessable: bool = True      # False when the columns needed to test this rule are missing
    needs: str = ""              # what is needed to assess it


def _breakdown(df, key, value_col="adjusted_revenue", n=2):
    return df.sort_values(value_col).head(n)[[key, value_col]].to_dict("records") if len(df) else []


def detect_drivers(kpis: dict, dq_report) -> list:
    core, comp, rec = kpis["core"], kpis["comparable_yoy"], kpis["recent_trend"]
    st, col, inv = kpis["profitability_stability"], kpis["collections"], kpis["inventory_status"]
    t = S.DRIVER_THRESHOLDS
    out = []

    low = core["gross_margin_pct"] < t["margin_pressure"]["gross_margin_below_pct"]
    falling = bool(comp.get("sufficient_data")) and comp["margin_change_pp"] <= -t["margin_pressure"]["gross_margin_decline_pp"]
    out.append(Driver("A", "Margin Pressure", bool(low or falling),
                      {"gross_margin_pct": core["gross_margin_pct"], "margin_change_pp": comp.get("margin_change_pp")},
                      "Gross margin has weakened, so less gross profit is retained from each shilling of sales. Review supplier "
                      "costs, selling prices, discounting and product-level margins."))

    top = kpis["expense_breakdown"].head(3)
    out.append(Driver("B", "Excessive Operating-Cost Burden", core["opex_ratio_pct"] > t["operating_cost_pressure"]["opex_to_revenue_above_pct"],
                      {"opex_ratio_pct": core["opex_ratio_pct"], "top_expense_categories": top.to_dict("records")},
                      "Operating expenses consume a high share of revenue. Prioritise the largest expense categories for review."))

    recent_drop = bool(rec.get("sufficient_data")) and rec["change_pct"] <= -t["revenue_deterioration"]["recent_decline_above_pct"]
    yoy_drop = bool(comp.get("sufficient_data")) and comp["revenue_change_pct"] <= -t["revenue_deterioration"]["recent_decline_above_pct"]
    out.append(Driver("C", "Revenue Deterioration", bool(recent_drop or yoy_drop),
                      {"recent_change_pct": rec.get("change_pct"), "comparable_change_pct": comp.get("revenue_change_pct"),
                       "weakest_branches": _breakdown(kpis["branch"], "branch"),
                       "weakest_categories": _breakdown(kpis["product_category"], "product_category"),
                       "weakest_customer_types": _breakdown(kpis["customer_type"], "customer_type"),
                       "weakest_channels": _breakdown(kpis["channel"], "sales_channel")},
                      "Revenue declined versus the preceding/comparable period. Investigate the decline by branch, customer type, "
                      "product category and channel instead of treating it as one company-wide problem."))

    out.append(Driver("D", "Persistent Losses", st["longest_consecutive_loss_streak"] >= t["persistent_losses"]["min_consecutive_loss_months"],
                      {"longest_consecutive_loss_streak": st["longest_consecutive_loss_streak"],
                       "profitable_months": st["profitable_months"], "total_months": st["total_months"]},
                      "Operating losses are persistent rather than isolated; examine the structural balance between gross margin, "
                      "revenue volume and operating expenses."))

    out.append(Driver("E", "Weak Collection", col["collection_coverage_pct"] < t["weak_collection"]["collection_coverage_below_pct"],
                      {"collection_coverage_pct": col["collection_coverage_pct"],
                       "estimated_uncollected_exposure": col["estimated_uncollected_exposure"]},
                      "Part of credit-like sales is still uncollected. Review customer balances and credit terms. This is a "
                      "portfolio-level estimate; the data has no invoice aging."))

    out.append(Driver("F", "Discount Pressure", core["discount_rate_pct"] > t["discount_pressure"]["weighted_discount_rate_above_pct"],
                      {"discount_rate_pct": core["discount_rate_pct"]},
                      "Discounting is eroding realised prices. Review discounts by product, customer type and salesperson."))

    out.append(Driver("G", "Inventory Data Integrity", not inv["usable_for_scoring"],
                      {"negative_stock_products": inv["negative_stock_products"]},
                      "Inventory records are internally inconsistent. Reconcile stock before using turnover, stockout or "
                      "replenishment outputs."))
    ok = lambda x: x is not None and x == x
    assess = {
        "A": (ok(core["gross_margin_pct"]), "cost of goods sold (cogs_kes, or quantity and unit_cost_kes)"),
        "B": (ok(core["opex_ratio_pct"]), "operating expenses (expense_amount_kes with transaction_type)"),
        "C": (bool(rec.get("sufficient_data")) or bool(comp.get("sufficient_data")), "at least 6 months of dated sales history"),
        "D": (st.get("available", True), "cost of goods sold and operating expenses by month"),
        "E": (bool(col.get("available", True)), "amount_received_kes (to infer credit sales)"),
        "F": (ok(core["discount_rate_pct"]), "gross_sales_kes alongside net_sales_kes"),
        "G": (inv.get("assessable", True), "inventory_qty_change and product_name"),
    }
    final = []
    for d in out:
        can, need = assess[d.code]
        final.append(Driver(d.code, d.name, bool(d.triggered and can), d.evidence, d.narrative, bool(can), need))
    return final
