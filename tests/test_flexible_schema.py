import io
from tests.helpers import *
from src.data.loader import load_csv
from src.data.schema import standardise_headers
from src.pipeline import run_pipeline


def _run(csv):
    lr = load_csv(io.StringIO(csv))
    assert lr.success, lr.error_message
    return run_pipeline(lr.raw_df)


SALES_ONLY = "Date,Item,Sales\n" + "\n".join(f"2025-{m:02d}-05,Cement,{1000 + m * 40}" for m in range(1, 9)) + "\n"
FULL_LITE = "date,type,net_sales_kes,cogs_kes,expense_amount_kes\n" + "\n".join(
    f"2025-{m:02d}-10,SALE,{1000 + m * 50},{700 + m * 20},0\n2025-{m:02d}-15,EXPENSE,0,0,{150 + m}" for m in range(1, 9)) + "\n"


def test_file_with_few_columns_is_analysed_not_rejected():
    r = _run(SALES_ONLY)
    assert r["kpis"]["core"]["adjusted_revenue"] == sum(1000 + m * 40 for m in range(1, 9))

def test_common_header_aliases_are_recognised():
    df = pd.DataFrame({"Date": ["2025-01-01"], "Sales": ["5"], "Item": ["x"], "Qty": ["1"]})
    out, renamed, _ = standardise_headers(df)
    assert {"transaction_date", "net_sales_kes", "product_name", "quantity"} <= set(out.columns) and renamed["Sales"] == "net_sales_kes"

def test_missing_measures_are_not_available_never_zero():
    c = _run(SALES_ONLY)["kpis"]["core"]
    for k in ["gross_profit", "gross_margin_pct", "operating_profit", "operating_expenses", "discount_rate_pct", "refund_rate_pct"]:
        assert c[k] != c[k], k          # NaN, not 0

def test_no_false_credit_sales_when_amount_received_missing():
    r = _run(SALES_ONLY)
    assert not r["analytical_df"]["is_credit_like_sale"].any()
    assert r["kpis"]["collections"]["collection_coverage_pct"] != r["kpis"]["collections"]["collection_coverage_pct"]

def test_schema_report_lists_what_each_missing_column_unlocks():
    s = _run(SALES_ONLY)["schema"]
    lines = " ".join(s.banner_lines())
    assert "cogs_kes" in lines and "Gross profit" in lines and s.coverage_pct < 20 and s.level == "minimal"
    assert any(c.key == "gross_profit" and c.status == "unavailable" for c in s.capabilities)

def test_transaction_type_inferred_and_disclosed():
    s = _run(FULL_LITE)["schema"]
    assert "net_sales_kes" in s.present_columns and "transaction_type" in s.present_columns
    s2 = _run("date,sales,expenses\n2025-01-05,100,0\n2025-02-05,0,50\n2025-03-05,120,0\n")["schema"]
    assert "transaction_type" in s2.derived_columns

def test_available_columns_still_give_full_chain():
    k = _run(FULL_LITE)["kpis"]
    assert k["core"]["gross_profit"] == k["core"]["adjusted_revenue"] - k["core"]["cogs"]
    assert k["core"]["operating_profit"] == k["core"]["gross_profit"] - k["core"]["operating_expenses"]

def test_partial_score_is_normalised_and_flagged_provisional():
    h = _run(FULL_LITE)["health_result"]
    assert h.partial and h.assessable_points < 100 and 0 <= h.total_score <= 100

def test_too_little_assessable_gives_not_rated_not_green():
    r = _run(SALES_ONLY)
    assert r["health_result"].assessable_points < 50 and r["rag_result"].status == "NOT RATED"

def test_unassessable_drivers_are_marked_not_triggered():
    d = {x.code: x for x in _run(SALES_ONLY)["drivers"]}
    assert not d["A"].assessable and not d["A"].triggered and d["A"].needs
    assert not d["G"].assessable and not d["E"].assessable

def test_inventory_not_assessable_without_stock_columns():
    r = _run(FULL_LITE)
    assert r["kpis"]["inventory_status"]["assessable"] is False and r["kpis"]["inventory_turnover"] is None
    assert r["dq_report"].inventory_assessed is False and r["dq_report"].inventory_integrity_ok

def test_dq_skips_checks_for_absent_columns_and_reweights():
    dq = _run(SALES_ONLY)["dq_report"]
    assert "duplicates" in dq.not_assessed and "invalid_quantities" in dq.not_assessed and 0 < dq.overall_score <= 100

def test_rejected_only_when_nothing_analysable():
    assert not load_csv(io.StringIO("item,sales\na,5\n")).success                 # no date
    assert not load_csv(io.StringIO("date,item\n2025-01-01,a\n")).success         # no amounts
    assert load_csv(io.StringIO("date,expenses\n2025-01-01,100\n")).success       # expenses alone is enough to start

def test_numbers_with_commas_and_currency_are_parsed():
    r = _run("date,type,net_sales_kes\n2025-01-05,SALE,\"KES 1,200\"\n2025-02-05,SALE,\"2,300\"\n")
    assert r["kpis"]["core"]["adjusted_revenue"] == 3500

def test_full_sample_files_unaffected_by_flexible_schema():
    r = pipeline_for(ORIGINAL)
    assert r["schema"].coverage_pct == 100 and not r["health_result"].partial and not r["schema"].derived_columns
    assert abs(r["kpis"]["core"]["adjusted_revenue"] - 7704313) < 5
