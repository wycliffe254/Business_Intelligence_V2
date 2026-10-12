"""RAG classification plus the critical-risk overrides (Spec Sec. 25-26)."""
from __future__ import annotations
from dataclasses import dataclass, field
from config import settings as S


@dataclass
class RagResult:
    status: str
    score_based_status: str
    triggered_overrides: list = field(default_factory=list)


def score_band(score: float) -> str:
    return "GREEN" if score >= S.RAG_GREEN_MIN else "AMBER" if score >= S.RAG_AMBER_MIN else "RED"


def classify(kpis: dict, health_score: float, dq_report, assessable_points: float = 100.0) -> RagResult:
    base = score_band(health_score)
    core, comp, col, st = kpis["core"], kpis["comparable_yoy"], kpis["collections"], kpis["profitability_stability"]
    cfg, hits = S.CRITICAL_OVERRIDES, []

    r = cfg["persistent_operating_loss"]
    if core["operating_margin_pct"] < r["operating_margin_threshold"] and \
            st["longest_consecutive_loss_streak"] >= r["min_consecutive_months"]:
        hits.append({"rule": "Persistent Operating Loss", "explanation":
                     f"Operating margin ({core['operating_margin_pct']:.1f}%) is below {r['operating_margin_threshold']:.0f}% and "
                     f"losses persisted for {st['longest_consecutive_loss_streak']} consecutive months "
                     f"(threshold: {r['min_consecutive_months']})."})

    r = cfg["severe_revenue_deterioration"]
    if comp.get("sufficient_data") and comp["revenue_change_pct"] <= r["revenue_decline_threshold"] and \
            (comp["margin_change_pp"] < 0 or not r["requires_margin_deterioration"]):
        hits.append({"rule": "Severe Revenue Deterioration", "explanation":
                     f"Comparable-period ({comp['period_label']}) revenue fell {abs(comp['revenue_change_pct']):.1f}% "
                     f"(threshold {abs(r['revenue_decline_threshold']):.0f}%) alongside a "
                     f"{abs(comp['margin_change_pp']):.1f} percentage-point gross-margin decline."})

    r = cfg["severe_collection_failure"]
    if col["collection_coverage_pct"] < r["collection_coverage_threshold"]:
        hits.append({"rule": "Severe Collection Failure", "explanation":
                     f"Collection coverage ({col['collection_coverage_pct']:.1f}%) is below {r['collection_coverage_threshold']:.0f}%."})

    r = cfg["severe_margin_deterioration"]
    if comp.get("sufficient_data") and comp["margin_change_pp"] <= -r["gross_margin_decline_pp_threshold"]:
        hits.append({"rule": "Severe Margin Deterioration", "explanation":
                     f"Gross margin fell {abs(comp['margin_change_pp']):.1f} percentage points over the comparable period "
                     f"(threshold {r['gross_margin_decline_pp_threshold']:.0f}pp)."})

    if dq_report.status == "RED" and dq_report.overall_score < S.CRITICAL_DATA_INTEGRITY_SCORE_BELOW:
        hits.append({"rule": "Critical Data Integrity Failure", "explanation":
                     f"Core financial values cannot be reliably determined (Data Quality Score {dq_report.overall_score:.0f}/100). "
                     "This is a data-quality warning, not evidence that the business itself is unhealthy."})

    if hits:
        final = "RED"
    elif assessable_points < S.MIN_ASSESSABLE_POINTS:
        final = "NOT RATED"      # too little of the scoring framework could be assessed to give an honest rating
    else:
        final = base
    return RagResult(final, base, hits)
