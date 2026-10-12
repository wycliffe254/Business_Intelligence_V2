"""Evidence-linked, priority-ranked recommendations (Spec Sec. 34). Nothing is emitted without a triggered driver."""
from __future__ import annotations
from dataclasses import dataclass
from config.settings import CURRENCY_SYMBOL


@dataclass
class Recommendation:
    priority: int
    category: str
    title: str
    observed_issue: str
    evidence: str
    management_action: str


def _kes(v):
    return "not available" if v is None or v != v else f"{CURRENCY_SYMBOL} {v:,.0f}"


def build_recommendations(kpis: dict, drivers: list) -> list:
    dm = {d.code: d for d in drivers}
    core, comp, pc = kpis["core"], kpis["comparable_yoy"], kpis["product_category"]
    recs = []
    if core["operating_profit"] < 0:
        recs.append(Recommendation(1, "Profitability", "Restore Operating Profitability", "The business is operating at a loss.",
                                   f"Operating margin = {core['operating_margin_pct']:.1f}%; operating loss = {_kes(abs(core['operating_profit']))}.",
                                   "Investigate gross-margin deterioration and operating expenses together; neither alone closes the gap."))
    if dm["C"].triggered:
        ch = comp.get("revenue_change_pct") if comp.get("sufficient_data") else dm["C"].evidence.get("recent_change_pct")
        recs.append(Recommendation(2, "Revenue", "Protect and Recover Revenue", "Revenue declined versus the preceding/comparable period.",
                                   f"Revenue change = {ch:.1f}%." if ch is not None else "Revenue decline detected.",
                                   "Identify which products, customer types, branches and channels drive the decline before acting."))
    if dm["A"].triggered:
        lm = pc[(pc["revenue_share_pct"] >= pc["revenue_share_pct"].median()) & (pc["gross_margin_pct"] < pc["gross_margin_pct"].median())]
        names = ", ".join(lm["product_category"].head(2).tolist())
        recs.append(Recommendation(3, "Margin", "Improve Margin", "Gross margin is weak or deteriorating.",
                                   f"Gross margin = {core['gross_margin_pct']:.1f}%." + (f" High-sales, relatively low-margin categories: {names}." if names else ""),
                                   "Review pricing, supplier costs, discounts and product-level contribution, starting with high-sales, low-margin categories."))
    if dm["B"].triggered:
        names = ", ".join(kpis["expense_breakdown"].head(3)["expense_category"].tolist())
        recs.append(Recommendation(4, "Operating Cost", "Control Operating Costs", "Operating expenses consume a high share of revenue.",
                                   f"Operating expense ratio = {core['opex_ratio_pct']:.1f}%. Largest categories: {names}.",
                                   f"Review {names}: is each cost fixed, variable, necessary or reducible without hurting sales?"))
    if dm["F"].triggered:
        recs.append(Recommendation(4, "Discounting", "Introduce Discount Controls", "Discounting is materially reducing realised prices.",
                                   f"Weighted discount rate = {core['discount_rate_pct']:.1f}%.",
                                   "Set approval thresholds for large discounts and check whether discounted sales add enough volume to justify the margin lost."))
    if dm["E"].triggered:
        c = kpis["collections"]
        recs.append(Recommendation(5, "Credit / Collections", "Improve Credit Collection", "Part of credit-like sales remains uncollected.",
                                   f"Collection coverage = {c['collection_coverage_pct']:.1f}%; estimated uncollected exposure = {_kes(c['estimated_uncollected_exposure'])} (estimate).",
                                   "Review the credit customers behind the exposure; tighten follow-up and credit terms where appropriate."))
    if dm["G"].triggered:
        recs.append(Recommendation(6, "Inventory / Data Integrity", "Reconcile Inventory Data", "Reconstructed inventory balances are negative.",
                                   f"{len(dm['G'].evidence['negative_stock_products'])} product line(s) affected.",
                                   "Do not use current inventory data for procurement decisions until opening stock, purchases, sales and adjustments are reconciled."))
    return sorted(recs, key=lambda r: r.priority)
