"""Finding / Evidence / Driver / Impact / Recommendation cards and the executive summary."""
from __future__ import annotations
from dataclasses import dataclass
from config.settings import CURRENCY_SYMBOL


@dataclass
class ExplanationCard:
    finding: str
    evidence: str
    driver: str
    impact: str
    recommendation: str


def _kes(v):
    return "not available" if v is None or v != v else f"{CURRENCY_SYMBOL} {v:,.0f}"


def _names(records, key):
    return ", ".join(str(r[key]) for r in records) if records else ""


def build_explanation_cards(kpis: dict, drivers: list) -> list:
    core, be, comp = kpis["core"], kpis["breakeven"], kpis["comparable_yoy"]
    cards = []
    if core["operating_profit"] < 0:
        gap = be["avg_monthly_opex"] - be["avg_monthly_gross_profit"]
        cards.append(ExplanationCard(
            "Operating profitability is negative.",
            f"Operating margin = {core['operating_margin_pct']:.1f}%.",
            "Gross profit is insufficient to cover the operating expense base.",
            f"Average monthly gross profit is about {_kes(be['avg_monthly_gross_profit'])} while average monthly operating "
            f"expenses are about {_kes(be['avg_monthly_opex'])}, a gap of about {_kes(gap)} per month.",
            "Review the largest controllable expense categories while also investigating margin deterioration and sales decline."))
    for d in drivers:
        if not d.triggered:
            continue
        e = d.evidence
        if d.code == "A":
            ch = f", a change of {e['margin_change_pp']:.1f}pp over the comparable period" if e.get("margin_change_pp") is not None else ""
            cards.append(ExplanationCard("Gross margin has weakened.", f"Gross margin = {e['gross_margin_pct']:.1f}%{ch}.",
                                         "Margin Pressure (Driver A)", "Each shilling of sales converts into less gross profit than before.", d.narrative))
        elif d.code == "B":
            top = ", ".join(f"{r['expense_category']} ({r['share_pct']:.0f}%)" for r in e["top_expense_categories"])
            cards.append(ExplanationCard("Operating expenses consume a high share of revenue.",
                                         f"Operating expense ratio = {e['opex_ratio_pct']:.1f}%.",
                                         "Excessive Operating-Cost Burden (Driver B)",
                                         f"Largest categories: {top}." if top else "See expense breakdown.", d.narrative))
        elif d.code == "C":
            parts = [f"Recent 3-month change = {e['recent_change_pct']:.1f}%" if e.get("recent_change_pct") is not None else "",
                     f"comparable-period change ({comp.get('period_label','')}) = {e['comparable_change_pct']:.1f}%" if e.get("comparable_change_pct") is not None else ""]
            weak = "; ".join(x for x in [
                f"weakest branches: {_names(e['weakest_branches'], 'branch')}" if e["weakest_branches"] else "",
                f"weakest categories: {_names(e['weakest_categories'], 'product_category')}" if e["weakest_categories"] else "",
                f"weakest customer types: {_names(e['weakest_customer_types'], 'customer_type')}" if e["weakest_customer_types"] else "",
                f"weakest channels: {_names(e['weakest_channels'], 'sales_channel')}" if e["weakest_channels"] else ""] if x)
            cards.append(ExplanationCard("Revenue has declined against the preceding period.",
                                         "; ".join(p for p in parts if p) + ".", "Revenue Deterioration (Driver C)",
                                         "Lower sales volume reduces the gross profit available to cover fixed costs. "
                                         f"By lowest revenue (not necessarily the cause of the decline): {weak}." if weak else
                                         "Lower sales volume reduces the gross profit available to cover fixed costs.", d.narrative))
        elif d.code == "D":
            cards.append(ExplanationCard("Operating losses are persistent, not a single bad month.",
                                         f"Longest loss-making streak: {e['longest_consecutive_loss_streak']} months; "
                                         f"{e['profitable_months']} of {e['total_months']} months were profitable.",
                                         "Persistent Losses (Driver D)", "A structural imbalance between revenue, margin and cost appears present.", d.narrative))
        elif d.code == "E":
            cards.append(ExplanationCard("A meaningful share of credit sales remains uncollected.",
                                         f"Collection coverage = {e['collection_coverage_pct']:.1f}%; estimated uncollected exposure = {_kes(e['estimated_uncollected_exposure'])} (estimate).",
                                         "Weak Collection (Driver E)", "Cash available to the business is lower than reported sales suggest.", d.narrative))
        elif d.code == "F":
            cards.append(ExplanationCard("Discounting is materially affecting realised prices.",
                                         f"Weighted discount rate = {e['discount_rate_pct']:.1f}%.", "Discount Pressure (Driver F)",
                                         "Discounts reduce realised revenue and gross margin.", d.narrative))
        elif d.code == "G":
            n = len(e["negative_stock_products"])
            cards.append(ExplanationCard("Reconstructed inventory balances are invalid.", f"{n} product line(s) show negative reconstructed stock.",
                                         "Inventory Data Integrity (Driver G)", "Inventory-based KPIs cannot be trusted until this is resolved.", d.narrative))
    return cards


def build_executive_summary(kpis, health_score, rag_status, dq_report, drivers, schema=None) -> str:
    core, comp, be = kpis["core"], kpis["comparable_yoy"], kpis["breakeven"]
    ok = lambda x: x is not None and x == x
    trig = [d for d in drivers if d.triggered]
    lead = {"RED": "Business performance requires immediate management attention.",
            "AMBER": "Business performance shows areas that need closer management attention.",
            "GREEN": "Business performance is currently within an acceptable range, with some areas worth monitoring.",
            "NOT RATED": "A reliable overall rating is not possible because too little of the data needed for the assessment is in the file."}[rag_status]
    lines = [lead]
    if ok(core["adjusted_revenue"]):
        if ok(core["operating_profit"]):
            lines.append(f"The business generated about {_kes(core['adjusted_revenue'])} in adjusted revenue and recorded "
                         f"{'an operating loss' if core['operating_profit'] < 0 else 'an operating profit'} of about {_kes(abs(core['operating_profit']))} "
                         f"(Financial Health Score {health_score:.0f}/100).")
        elif ok(core["gross_profit"]):
            lines.append(f"The business generated about {_kes(core['adjusted_revenue'])} in adjusted revenue and {_kes(core['gross_profit'])} in gross profit; "
                         "operating profit cannot be calculated because operating expenses are not in the file "
                         f"(Financial Health Score {health_score:.0f}/100, based only on what could be assessed).")
        else:
            lines.append(f"The business generated about {_kes(core['adjusted_revenue'])} in adjusted revenue; profit measures cannot be calculated "
                         f"because cost data is not in the file (Financial Health Score {health_score:.0f}/100, based only on what could be assessed).")
    pos = []
    if ok(core["gross_margin_pct"]) and core["gross_margin_pct"] >= 30:
        pos.append(f"healthy gross margin ({core['gross_margin_pct']:.1f}%)")
    if ok(core["refund_rate_pct"]) and core["refund_rate_pct"] < 1:
        pos.append(f"low refund rate ({core['refund_rate_pct']:.2f}%)")
    cc = kpis["collections"]["collection_coverage_pct"]
    if ok(cc) and cc >= 90:
        pos.append(f"strong collection coverage ({cc:.1f}%)")
    if ok(core["operating_profit"]) and core["operating_profit"] > 0:
        pos.append("positive operating profit")
    lines.append("Positive indicators: " + (", ".join(pos) if pos else "none stand out strongly") + ".")
    if comp.get("sufficient_data"):
        mg = f" and gross margin moved {comp['margin_change_pp']:.1f} percentage points" if ok(comp["margin_change_pp"]) else ""
        lines.append(f"Comparing the same months ({comp['period_label']}) in {comp['prior_year']} and {comp['latest_year']}, revenue changed "
                     f"{comp['revenue_change_pct']:.1f}%{mg}.")
    top = kpis["expense_breakdown"].head(2)
    if not top.empty:
        lines.append("The largest operating expense categories are " + " and ".join(top["expense_category"].tolist()) + ".")
    lines.append("Key drivers: " + (", ".join(d.name for d in trig[:5]) if trig else "no major risk drivers were triggered") + ".")
    skipped = [d.name for d in drivers if not d.assessable]
    if skipped:
        lines.append("Not assessable with this file: " + ", ".join(skipped) + ".")
    if dq_report.status != "GREEN":
        lines.append(f"Data reliability is {dq_report.status} ({dq_report.overall_score:.0f}/100); treat some results as provisional.")
    if schema is not None and schema.missing_columns:
        lines.append(f"The file supplied {len(schema.present_columns)} of 32 expected columns; supplying the missing ones would allow a fuller analysis.")
    gap = be.get("revenue_gap_pct")
    if ok(gap) and gap > 0:
        lines.append(f"As an approximate analytical estimate, the business would need about {gap:.0f}% more monthly revenue to break even at the "
                     "current margin and cost structure, so revenue growth alone is unlikely to be enough.")
    return " ".join(lines)
