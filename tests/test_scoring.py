from tests.helpers import *
from src.health.rag import classify, score_band
from src.health.scoring import compute_health_score
from src.health.thresholds import band_score, interpolate_score


def test_interpolation_and_bands():
    t = [(0, 0), (10, 5), (20, 10)]
    assert interpolate_score(-5, t) == 0 and interpolate_score(25, t) == 10 and interpolate_score(5, t) == 2.5
    assert band_score(97, [(95, 10), (90, 9), (0, 2)]) == 10 and band_score(10, [(95, 10), (0, 2)]) == 2

def test_score_in_range_and_components_sum_and_max_weights():
    r = pipeline_for(ORIGINAL)
    h = r["health_result"]
    assert 0 <= h.total_score <= 100
    assert abs(sum(c.points for c in h.components) - h.total_score) < 0.1
    assert [c.max_points for c in h.components] == [35, 20, 20, 15, 10]
    assert all(0 <= c.points <= c.max_points + 1e-9 for c in h.components)

def test_rag_bands():
    assert score_band(70) == "GREEN" and score_band(69.9) == "AMBER" and score_band(50) == "AMBER" and score_band(49.9) == "RED"

def test_original_dataset_is_red_with_explained_overrides():
    r = pipeline_for(ORIGINAL)
    assert r["rag_result"].status == "RED"
    rules = [o["rule"] for o in r["rag_result"].triggered_overrides]
    assert "Persistent Operating Loss" in rules and "Severe Revenue Deterioration" in rules
    assert all(o["explanation"] for o in r["rag_result"].triggered_overrides)

def test_override_forces_red_even_with_high_score():
    r = pipeline_for(ORIGINAL)
    res = classify(r["kpis"], 95.0, r["dq_report"])
    assert res.score_based_status == "GREEN" and res.status == "RED"

def test_collection_failure_override():
    r = pipeline_for(SYNTH)
    k = {**r["kpis"], "collections": {**r["kpis"]["collections"], "collection_coverage_pct": 40.0}}
    res = classify(k, 85.0, r["dq_report"])
    assert res.status == "RED" and any(o["rule"] == "Severe Collection Failure" for o in res.triggered_overrides)

def test_synthetic_dataset_is_healthy_and_data_reliable():
    r = pipeline_for(SYNTH)
    assert r["rag_result"].status == "GREEN" and r["dq_report"].status == "GREEN" and r["dq_report"].inventory_integrity_ok

def test_data_reliability_is_separate_from_financial_health():
    r = pipeline_for(ORIGINAL)
    assert r["dq_report"].status == "RED" and r["dq_report"].overall_score != r["health_result"].total_score


def test_rag_statuses_are_visually_distinct_by_colour_and_marker():
    from src.utils.formatting import RAG_STYLE, rag_badge_md
    for key in ["bg", "marker"]:
        vals = [RAG_STYLE[s][key] for s in ["GREEN", "AMBER", "RED", "NOT RATED"]]
        assert len(set(vals)) == 4, key
    html = rag_badge_md("AMBER")
    assert "AMBER" in html and RAG_STYLE["AMBER"]["marker"] in html          # text label always accompanies colour


def test_data_reliability_band_caption_explains_cap_only_when_inventory_fails():
    from src.utils.formatting import dq_bands_caption
    bad, good = pipeline_for(ORIGINAL)["dq_report"], pipeline_for(SYNTH)["dq_report"]
    assert "85+ GREEN" in dq_bands_caption(good) and "capped" not in dq_bands_caption(good)
    assert "capped at 64" in dq_bands_caption(bad) and "below 65 RED" in dq_bands_caption(bad)
