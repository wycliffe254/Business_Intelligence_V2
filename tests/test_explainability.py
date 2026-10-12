from tests.helpers import *
from src.explainability.drivers import detect_drivers


def test_all_seven_drivers_present():
    r = pipeline_for(ORIGINAL)
    assert {d.code for d in r["drivers"]} == set("ABCDEFG")

def test_expected_drivers_on_original_dataset():
    trig = {d.code for d in pipeline_for(ORIGINAL)["drivers"] if d.triggered}
    assert {"A", "B", "C", "D", "G"} <= trig

def test_drivers_on_healthy_dataset_are_limited():
    trig = {d.code for d in pipeline_for(SYNTH)["drivers"] if d.triggered}
    assert "B" not in trig and "G" not in trig and "D" not in trig

def test_revenue_driver_carries_breakdown_evidence():
    c = next(d for d in pipeline_for(ORIGINAL)["drivers"] if d.code == "C")
    assert c.evidence["weakest_branches"] and c.evidence["weakest_categories"]

def test_cards_have_all_five_parts():
    cards = pipeline_for(ORIGINAL)["explanation_cards"]
    assert cards
    for c in cards:
        assert all([c.finding, c.evidence, c.driver, c.impact, c.recommendation])

def test_negative_operating_profit_card_has_numbers():
    cards = pipeline_for(ORIGINAL)["explanation_cards"]
    first = cards[0]
    assert "negative" in first.finding.lower() and "%" in first.evidence

def test_recommendations_are_evidence_linked_prioritised_and_specific():
    recs = pipeline_for(ORIGINAL)["recommendations"]
    assert [r.priority for r in recs] == sorted(r.priority for r in recs)
    for r in recs:
        assert r.evidence and r.observed_issue and r.management_action
        assert "improve your business finances" not in r.management_action.lower()

def test_no_recommendation_without_driver():
    recs = pipeline_for(SYNTH)["recommendations"]
    cats = {r.category for r in recs}
    assert "Inventory / Data Integrity" not in cats and "Operating Cost" not in cats

def test_executive_summary_content():
    s = pipeline_for(ORIGINAL)["executive_summary"]
    assert "KES" in s and "Key drivers" in s and "Data reliability" in s

def test_inventory_driver_message_and_gate():
    r = pipeline_for(ORIGINAL)
    assert r["kpis"]["inventory_status"]["usable_for_scoring"] is False
    assert "unavailable" in r["kpis"]["inventory_status"]["message"].lower()

def test_report_builds_and_contains_status():
    from src.reporting.report import build_html_report
    r = pipeline_for(ORIGINAL)
    html = build_html_report(r["kpis"], r["health_result"], r["rag_result"], r["dq_report"], r["drivers"], r["explanation_cards"], r["recommendations"], r["executive_summary"])
    assert "RED" in html and "Recommendations" in html and "break-even" in html.lower()

def test_unrelated_csv_is_rejected_gracefully():
    import io
    from src.data.loader import load_csv
    res = load_csv(io.StringIO("a,b\n1,2\n"))
    assert not res.success and "enough recognisable data" in res.error_message
