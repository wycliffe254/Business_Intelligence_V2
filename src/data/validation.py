"""Data Quality Report: aggregates cleaning flags into counts, a 0-100 score and status."""
from __future__ import annotations
from dataclasses import dataclass, field
import pandas as pd
from config.settings import DQ_DIMENSION_WEIGHTS, DQ_STATUS_BANDS


@dataclass
class DataQualityReport:
    row_count: int
    column_count: int
    duplicate_count: int
    missing_value_summary: dict
    invalid_date_count: int
    ambiguous_date_count: int
    invalid_quantity_count: int
    inconsistent_category_count: int
    inconsistent_payment_label_count: int
    payment_method_missing_for_sale_count: int
    financial_inconsistency_count: int
    inventory_integrity_ok: bool
    inventory_negative_products: list
    dimension_scores: dict = field(default_factory=dict)
    overall_score: float = 0.0
    status: str = "RED"
    limitations: list = field(default_factory=list)
    not_assessed: list = field(default_factory=list)      # dimensions skipped because the needed columns are absent
    completeness_pct: float = 100.0
    inventory_assessed: bool = True


def _dimension_score(bad: int, total: int) -> float:
    if total == 0:
        return 100.0
    return max(0.0, 100.0 * (1 - min(bad / total, 1.0)))


def build_data_quality_report(analytical_df, flags, exclusion_summary, inventory_summary, schema=None) -> DataQualityReport:
    total = len(analytical_df)
    present = set(analytical_df.columns) if schema is None else set(schema.present_columns)
    has = lambda c: c in present
    miss_cols = ["branch", "customer_type", "sales_channel", "payment_method", "supplier_name", "customer_id"]
    missing = {c: int(analytical_df[c].isna().sum()) for c in miss_cols if has(c)}
    dup = int(flags["is_duplicate_txn_id"].sum())
    bad_dates = int((~flags["is_valid_date"]).sum())
    amb = int(flags["is_ambiguous_date"].sum())
    bad_qty = int(flags["is_invalid_sale_quantity"].sum())
    bad_cat = int(flags["has_inconsistent_category_text"].sum())
    bad_pay = int(flags["payment_label_variant"].sum())
    pay_missing_sale = int(flags["payment_method_missing_for_sale"].sum())
    fin = int(flags["has_financial_inconsistency"].sum())

    neg = inventory_summary.loc[inventory_summary["has_negative_stock"], "product_name"].tolist()
    inv_assessed = schema is None or bool(schema.availability.get("inventory", True))
    inv_ok = len(neg) == 0 or not inv_assessed

    dims = {
        "duplicates": _dimension_score(dup, total) if has("transaction_id") else None,
        "missing_values": _dimension_score(sum(missing.values()), total * len(missing)) if missing else None,
        "invalid_dates": _dimension_score(bad_dates, total),
        "invalid_quantities": _dimension_score(bad_qty, total) if has("quantity") else None,
        "inconsistent_categories": _dimension_score(bad_cat, total) if any(has(c) for c in ["branch", "customer_type", "sales_channel", "product_category"]) else None,
        "inconsistent_payment_labels": _dimension_score(bad_pay, total) if has("payment_method") else None,
        "financial_consistency": _dimension_score(fin, total) if (has("gross_sales_kes") or has("cogs_kes")) else None,
    }
    not_assessed = [k for k, v in dims.items() if v is None]
    dims = {k: v for k, v in dims.items() if v is not None}
    wsum = sum(DQ_DIMENSION_WEIGHTS[k] for k in dims)          # re-weight over the dimensions that CAN be checked
    score = sum(dims[k] * DQ_DIMENSION_WEIGHTS[k] / wsum for k in dims)
    completeness = 100.0 if schema is None else schema.coverage_pct
    if not inv_ok:   # hard cap: blocks an entire analytical capability (Spec Sec. 4)
        score = min(score, DQ_STATUS_BANDS["AMBER"] - 1)
    from config.settings import COVERAGE_MINIMAL_BELOW
    if completeness < COVERAGE_MINIMAL_BELOW:   # a very incomplete file cannot be rated highly reliable
        score = min(score, DQ_STATUS_BANDS["GREEN"] - 1)
    status = "GREEN" if score >= DQ_STATUS_BANDS["GREEN"] else "AMBER" if score >= DQ_STATUS_BANDS["AMBER"] else "RED"

    lims = []
    if pay_missing_sale > 0:
        lims.append("payment_method is not recorded for sale transactions; credit-like sales are inferred from "
                    "amount_received_kes < net_sales_kes. This is an estimate, not a confirmed payment classification.")
    if not inv_assessed:
        lims.append("Inventory integrity could not be assessed because inventory_qty_change and/or product_name are missing.")
    if not inv_ok:
        lims.append("Reconstructed inventory balances are negative for one or more products; inventory turnover "
                    "and stock-based KPIs are withheld until stock records are reconciled.")
    if dup:
        lims.append(f"{dup} duplicate transaction_id records were detected and excluded from KPI calculations "
                    "(first occurrence kept).")
    if bad_dates:
        lims.append(f"{bad_dates} records have unparseable transaction dates and are excluded from time-based analysis.")
    if amb:
        lims.append(f"{amb} records had ambiguous day/month order; day-first (DD/MM/YYYY) was assumed.")
    if bad_qty:
        lims.append(f"{bad_qty} sale records have zero/negative quantity with positive sales value and are excluded.")

    if not_assessed:
        lims.append("Not assessed (columns absent): " + ", ".join(not_assessed) + ". The score is based on the checks that could be run.")
    if schema is not None and schema.missing_columns:
        lims.append(f"Column completeness: {len(schema.present_columns)} of 32 expected columns supplied ({completeness:.0f}%).")
    return DataQualityReport(
        row_count=total, column_count=analytical_df.shape[1], duplicate_count=dup, missing_value_summary=missing,
        invalid_date_count=bad_dates, ambiguous_date_count=amb, invalid_quantity_count=bad_qty,
        inconsistent_category_count=bad_cat, inconsistent_payment_label_count=bad_pay,
        payment_method_missing_for_sale_count=pay_missing_sale, financial_inconsistency_count=fin,
        inventory_integrity_ok=inv_ok, inventory_assessed=inv_assessed, inventory_negative_products=neg, dimension_scores=dims,
        overall_score=round(score, 1), status=status, limitations=lims, not_assessed=not_assessed, completeness_pct=completeness)
