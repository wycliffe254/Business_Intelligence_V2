"""Composite Financial Health Score (0-100) with a fully itemised component breakdown (Spec Sec. 19-24)."""
from __future__ import annotations
from dataclasses import dataclass, field
from config import settings as S
from src.health.thresholds import band_score, interpolate_score


def _ok(x):
    return x is not None and x == x and x != float("inf")


def _sub(name, pts, mx, detail, ok):
    return ScoreComponent(name, pts if ok else 0.0, mx, detail, assessable=bool(ok))


def _roll(name, subs, weight):
    """Component total over assessable sub-scores only."""
    amax = sum(x.max_points for x in subs if x.assessable)
    return ScoreComponent(name, sum(x.points for x in subs if x.assessable), weight, {}, assessable=amax > 0, assessable_max=amax)


@dataclass
class ScoreComponent:
    name: str
    points: float
    max_points: float
    detail: dict = field(default_factory=dict)
    assessable: bool = True          # False when the needed columns/history are missing: excluded from the score
    assessable_max: float = None     # points that could actually be assessed (None -> max_points)


@dataclass
class HealthScoreResult:
    total_score: float               # normalised to 0-100 over the points that could be assessed
    components: list
    subcomponents: dict
    raw_points: float = 0.0
    assessable_points: float = 100.0
    partial: bool = False            # True when some sub-scores could not be assessed


def _profitability(k):
    core, comp, av = k["core"], k["comparable_yoy"], k["availability"]
    gp_trend = comp.get("gross_profit_change_pct", float("nan")) if comp.get("sufficient_data") else float("nan")
    subs = [
        _sub("Gross Margin", interpolate_score(core["gross_margin_pct"], S.GROSS_MARGIN_SCORE_POINTS), S.PROFITABILITY_SUBWEIGHTS["gross_margin"],
             {"gross_margin_pct": core["gross_margin_pct"]}, av["gross_profit"] and _ok(core["gross_margin_pct"])),
        _sub("Operating Margin", interpolate_score(core["operating_margin_pct"], S.OPERATING_MARGIN_SCORE_POINTS), S.PROFITABILITY_SUBWEIGHTS["operating_margin"],
             {"operating_margin_pct": core["operating_margin_pct"]}, av["operating_profit"] and _ok(core["operating_margin_pct"])),
        _sub("Gross Profit Trend", interpolate_score(gp_trend, S.GROSS_PROFIT_TREND_SCORE_POINTS), S.PROFITABILITY_SUBWEIGHTS["gross_profit_trend"],
             {"comparable_gross_profit_change_pct": gp_trend}, _ok(gp_trend)),
    ]
    return _roll("Profitability", subs, S.WEIGHTS["profitability"]), subs


def _liquidity(k):
    c, av = k["collections"], k["availability"]
    ratio = c["revenue_to_opex_ratio"]
    avg_sales = k["core"]["adjusted_revenue"] / max(k["breakeven"]["n_months"], 1) if _ok(k["core"]["adjusted_revenue"]) else float("nan")
    exposure = c["estimated_uncollected_exposure"] / avg_sales if (_ok(c["estimated_uncollected_exposure"]) and _ok(avg_sales) and avg_sales) else float("nan")
    subs = [
        _sub("Collection Coverage", band_score(c["collection_coverage_pct"], S.COLLECTION_COVERAGE_SCORE_TABLE), 10,
             {"collection_coverage_pct": c["collection_coverage_pct"]}, _ok(c["collection_coverage_pct"])),
        _sub("Revenue-to-Opex Coverage", interpolate_score(ratio if _ok(ratio) else 999, S.REVENUE_TO_OPEX_SCORE_POINTS), 5,
             {"revenue_to_opex_ratio": ratio}, av["operating_expenses"] and av["revenue"]),
        _sub("Uncollected Credit Exposure", interpolate_score(exposure, S.UNCOLLECTED_EXPOSURE_SCORE_POINTS), 5,
             {"exposure_as_multiple_of_monthly_sales": exposure}, _ok(exposure)),
    ]
    return _roll("Liquidity & Collections", subs, S.WEIGHTS["liquidity_collections"]), subs


def _cost(k):
    core = k["core"]
    subs = [
        _sub("Operating Expense Ratio", interpolate_score(core["opex_ratio_pct"], S.OPEX_RATIO_SCORE_POINTS), 10, {"opex_ratio_pct": core["opex_ratio_pct"]}, _ok(core["opex_ratio_pct"])),
        _sub("Discount Discipline", interpolate_score(core["discount_rate_pct"], S.DISCOUNT_SCORE_POINTS), 5, {"discount_rate_pct": core["discount_rate_pct"]}, _ok(core["discount_rate_pct"])),
        _sub("Refund Rate", interpolate_score(core["refund_rate_pct"], S.REFUND_SCORE_POINTS), 5, {"refund_rate_pct": core["refund_rate_pct"]}, _ok(core["refund_rate_pct"])),
    ]
    return _roll("Cost & Operating Efficiency", subs, S.WEIGHTS["cost_efficiency"]), subs


def _growth(k):
    r, st = k["recent_trend"], k["profitability_stability"]
    trend = r.get("change_pct", float("nan")) if r.get("sufficient_data") else float("nan")
    pct = st["pct_profitable_months"]
    subs = [
        _sub("Recent Revenue Trend", interpolate_score(trend, S.REVENUE_TREND_SCORE_POINTS), 10, {"recent_3mo_change_pct": trend}, _ok(trend)),
        _sub("Profitability Stability", interpolate_score(pct, S.PROFITABLE_MONTHS_SCORE_POINTS), 5, {"pct_profitable_months": pct}, st.get("available", True) and _ok(pct)),
    ]
    return _roll("Growth & Stability", subs, S.WEIGHTS["growth_stability"]), subs


def _data(dq_score, inv_ok, inv_assessed=True):
    pts = interpolate_score(dq_score, S.DATA_RELIABILITY_SCORE_POINTS)
    if inv_assessed and not inv_ok:
        pts = max(0.0, pts - S.INVENTORY_INTEGRITY_PENALTY_POINTS)
    return ScoreComponent("Working Capital / Data Reliability", pts, S.WEIGHTS["data_working_capital"],
                          {"data_quality_score": dq_score, "inventory_integrity_ok": inv_ok, "inventory_assessed": inv_assessed},
                          assessable=True, assessable_max=S.WEIGHTS["data_working_capital"]), []


def compute_health_score(kpis: dict, dq_score: float, inventory_ok: bool, inventory_assessed: bool = True) -> HealthScoreResult:
    parts = [_profitability(kpis), _liquidity(kpis), _cost(kpis), _growth(kpis), _data(dq_score, inventory_ok, inventory_assessed)]
    comps = [p[0] for p in parts]
    raw = sum(c.points for c in comps if c.assessable)
    amax = sum((c.assessable_max if c.assessable_max is not None else c.max_points) for c in comps if c.assessable)
    total = raw / amax * 100 if amax else 0.0
    return HealthScoreResult(round(total, 1), comps, {p[0].name: p[1] for p in parts}, raw, amax, partial=amax < 100 - 1e-9)
