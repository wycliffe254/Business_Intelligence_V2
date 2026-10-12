"""End-to-end analytical pipeline (no Streamlit dependency, fully testable).

RAW -> quality assessment -> cleaning -> KPIs -> health score -> RAG -> drivers
-> explanations -> recommendations -> executive summary.
"""
from __future__ import annotations
import pandas as pd
from src.analytics.kpis import compute_all_kpis
from src.data.cleaning import clean_dataset, reconstruct_inventory
from src.data.schema import prepare_frame
from src.data.validation import build_data_quality_report
from src.explainability.drivers import detect_drivers
from src.explainability.explanations import build_executive_summary, build_explanation_cards
from src.explainability.recommendations import build_recommendations
from src.health.rag import classify
from src.health.scoring import compute_health_score


def run_pipeline(raw_df: pd.DataFrame, column_map=None) -> dict:
    """Run the full chain on an upload. Missing columns limit the analysis rather than stopping it (see src/data/schema.py)."""
    prepared, schema = prepare_frame(raw_df, column_map)
    usable = set(schema.present_columns) | set(schema.derived_columns)
    cleaned = clean_dataset(prepared, usable)
    adf = cleaned["analytical_df"]
    inv = reconstruct_inventory(adf)
    dq = build_data_quality_report(adf, cleaned["flags"], cleaned["exclusion_summary"], inv, schema)
    kpis = compute_all_kpis(adf, inv, schema.availability)
    health = compute_health_score(kpis, dq.overall_score, dq.inventory_integrity_ok, dq.inventory_assessed)
    rag = classify(kpis, health.total_score, dq, health.assessable_points)
    drivers = detect_drivers(kpis, dq)
    return {
        "raw_df": raw_df, "schema": schema, "analytical_df": adf, "exclusion_summary": cleaned["exclusion_summary"],
        "inventory_summary": inv, "dq_report": dq, "kpis": kpis, "health_result": health, "rag_result": rag,
        "drivers": drivers, "explanation_cards": build_explanation_cards(kpis, drivers),
        "recommendations": build_recommendations(kpis, drivers),
        "executive_summary": build_executive_summary(kpis, health.total_score, rag.status, dq, drivers, schema),
    }
