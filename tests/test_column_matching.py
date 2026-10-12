import io
from tests.helpers import *
from src.data.loader import load_csv
from src.data.schema import match_headers, suggest_mapping
from src.pipeline import run_pipeline


def _run(csv, cmap=None):
    lr = load_csv(io.StringIO(csv), cmap)
    assert lr.success, lr.error_message
    return run_pipeline(lr.raw_df, cmap)


COMBINED = "Date,Description,Amount (KES),Type\n" + "\n".join(
    f"2025-{m:02d}-05,Cement,{2000 + m * 50},Income\n2025-{m:02d}-20,Rent,{900 + m},Expense" for m in range(1, 9)) + "\n"


def test_standard_names_with_kes_suffix_are_still_matched_exactly():
    cols = ["inventory_value_change_kes", "net_sales_kes", "amount_received_kes"]
    m = match_headers(cols)
    assert all(v[1] == "exact" and v[0] == k for k, v in m.items())

def test_currency_words_are_ignored_in_headers():
    assert match_headers(["Amount (KES)"])["Amount (KES)"][0] == "amount_generic"
    assert match_headers(["Revenue (KSh)"])["Revenue (KSh)"][0] == "net_sales_kes"

def test_keyword_matching_on_typical_spreadsheet_headers():
    m = suggest_mapping(["Txn Date", "Total Sales", "Expenses", "Cost of Goods Sold", "Qty", "Item", "Sales Person"])
    assert m["transaction_date"] == "Txn Date" and m["net_sales_kes"] == "Total Sales" and m["cogs_kes"] == "Cost of Goods Sold"
    assert "Sales Person" not in m.values()           # must not be mistaken for a sales amount

def test_single_amount_column_with_type_labels_is_split_into_sales_and_expenses():
    r = _run(COMBINED)
    c = r["kpis"]["core"]
    assert c["adjusted_revenue"] == sum(2000 + m * 50 for m in range(1, 9))
    assert c["operating_expenses"] == sum(900 + m for m in range(1, 9))
    assert "net_sales_kes" in r["schema"].derived_columns and "expense_amount_kes" in r["schema"].derived_columns

def test_single_amount_column_without_type_uses_sign():
    r = _run("Date,Amount\n2025-01-05,1000\n2025-01-10,-300\n2025-02-05,1200\n2025-02-12,-250\n")
    c = r["kpis"]["core"]
    assert c["adjusted_revenue"] == 2200 and c["operating_expenses"] == 550
    assert "positive amounts treated as sales" in r["schema"].derived_columns["net_sales_kes"]

def test_single_amount_column_alone_is_treated_as_sales_and_disclosed():
    r = _run("Date,Total\n2025-01-05,1000\n2025-02-05,1500\n")
    assert r["kpis"]["core"]["adjusted_revenue"] == 2500 and r["schema"].derived_columns

def test_manual_mapping_rescues_unrecognisable_headers():
    csv = "Col A,Col B,Col C\n2025-01-05,1000,300\n2025-02-05,1500,400\n"
    assert not load_csv(io.StringIO(csv)).success                       # not recognised automatically...
    cmap = {"transaction_date": "Col A", "net_sales_kes": "Col B", "expense_amount_kes": "Col C"}
    r = _run(csv, cmap)                                                  # ...but fine once the user matches them
    assert r["kpis"]["core"]["adjusted_revenue"] == 2500 and r["kpis"]["core"]["operating_expenses"] == 700
    assert all(v[1] == "chosen by you" for v in r["schema"].match_how.values())

def test_user_choice_overrides_automatic_match_and_none_switches_a_field_off():
    csv = "Date,Sales,Total\n2025-01-05,10,1000\n2025-02-05,20,2000\n"
    assert _run(csv)["kpis"]["core"]["adjusted_revenue"] == 30                       # auto picks 'Sales'
    assert _run(csv, {"net_sales_kes": "Total"})["kpis"]["core"]["adjusted_revenue"] == 3000
    assert not load_csv(io.StringIO("Date,Sales\n2025-01-05,10\n"), {"net_sales_kes": None}).success

def test_failure_message_points_user_to_the_matching_screen():
    res = load_csv(io.StringIO("Date,Notes\n2025-01-05,hello\n"))
    assert not res.success and "Review how your columns were matched" in res.error_message and res.headers == ["Date", "Notes"]

def test_type_labels_are_standardised():
    r = _run("Date,Amount,Type\n2025-01-05,100,Sales\n2025-01-06,40,Debit\n2025-02-05,150,Income\n")
    assert set(r["analytical_df"]["transaction_type"]) == {"SALE", "EXPENSE"}


def test_daily_summary_rows_with_sales_and_expense_side_by_side_count_both():
    csv = "Date,Sales,Expenses\n2025-01-05,1000,300\n2025-02-05,1500,400\n2025-03-05,0,200\n"
    r = _run(csv)
    c = r["kpis"]["core"]
    assert c["adjusted_revenue"] == 2500 and c["operating_expenses"] == 900
    assert "split" in r["schema"].derived_columns["transaction_type"]
