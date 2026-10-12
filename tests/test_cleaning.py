from tests.helpers import *
from src.data.cleaning import clean_dataset, reconstruct_inventory
from src.utils.dates import parse_single_date


def test_parse_iso_date():
    r = parse_single_date("2025-01-24")
    assert r.is_valid and r.parsed == pd.Timestamp(2025, 1, 24) and not r.is_ambiguous

def test_parse_dash_dmy():
    assert parse_single_date("31-03-2025").parsed == pd.Timestamp(2025, 3, 31)

def test_parse_slash_mdy_when_unambiguous():
    assert parse_single_date("08/19/2026").parsed == pd.Timestamp(2026, 8, 19)

def test_parse_slash_dmy_when_unambiguous():
    assert parse_single_date("19/12/2025").parsed == pd.Timestamp(2025, 12, 19)

def test_ambiguous_defaults_day_first_and_is_flagged():
    r = parse_single_date("03/04/2025")
    assert r.is_ambiguous and r.parsed == pd.Timestamp(2025, 4, 3)

def test_invalid_and_missing_dates():
    assert not parse_single_date("not-a-date").is_valid
    assert not parse_single_date(None).is_valid
    assert not parse_single_date("31/31/2025").is_valid

def test_duplicate_detection_keeps_first():
    df = mini_df([{}, {}, {}])
    df.loc[1, "transaction_id"] = "T1"
    out = clean_dataset(df)["analytical_df"]
    assert out["is_duplicate_txn_id"].tolist() == [False, True, False]
    assert "duplicate_transaction_id" in out.loc[1, "exclude_reason"]

def test_missing_value_and_invalid_date_flags():
    df = mini_df([{"branch": None}, {"transaction_date": "garbage"}])
    r = clean_dataset(df)
    assert r["analytical_df"]["branch"].isna().sum() == 1
    assert r["exclusion_summary"]["invalid_date"] == 1
    assert not r["analytical_df"].loc[1, "include_in_kpis"]

def test_invalid_sale_quantity_flag():
    out = clean_dataset(mini_df([{"quantity": "0"}, {}]))["analytical_df"]
    assert out["is_invalid_sale_quantity"].tolist() == [True, False]

def test_discount_pct_is_a_fraction_not_percent():
    # 2% discount stored as 0.02: net = 98 must NOT be flagged inconsistent (regression test)
    out = clean_dataset(mini_df([{"discount_pct": "0.02", "gross_sales_kes": "100", "net_sales_kes": "98", "cogs_kes": "60", "gross_profit_kes": "38"}]))["analytical_df"]
    assert not out["has_financial_inconsistency"].iloc[0]
    bad = clean_dataset(mini_df([{"discount_pct": "0.02", "gross_sales_kes": "100", "net_sales_kes": "80", "cogs_kes": "60", "gross_profit_kes": "20"}]))["analytical_df"]
    assert bad["has_financial_inconsistency"].iloc[0]

def test_label_variants_standardised():
    out = clean_dataset(mini_df([{"product_category": "Paints"}, {"product_category": "paints "}, {"product_category": "Paints"}]))["analytical_df"]
    assert out["product_category_norm"].nunique() == 1 and out["has_inconsistent_category_text"].sum() == 1

def test_credit_like_sale_inferred():
    out = clean_dataset(mini_df([{"amount_received_kes": "40"}, {}]))["analytical_df"]
    assert out["is_credit_like_sale"].tolist() == [True, False]

def test_inventory_negative_detected_and_value_tracked():
    df = mini_df([{"inventory_qty_change": "-1", "inventory_value_change_kes": "-60"}])
    inv = reconstruct_inventory(clean_dataset(df)["analytical_df"])
    assert bool(inv["has_negative_stock"].iloc[0]) and "ending_value" in inv.columns

def test_inventory_ok_with_opening_purchase():
    df = mini_df([{"transaction_type": "PURCHASE", "inventory_qty_change": "10", "inventory_value_change_kes": "600", "transaction_date": "2025-01-01"}, {}])
    inv = reconstruct_inventory(clean_dataset(df)["analytical_df"])
    assert not inv["has_negative_stock"].any() and inv["ending_stock"].iloc[0] == 9
