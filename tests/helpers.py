import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from config.settings import REQUIRED_COLUMNS
from src.data.loader import load_csv, sample_path
from src.pipeline import run_pipeline

ORIGINAL = "data/sample/kenyan_sme_bi_financial_operational_data_1800_records.csv"
SYNTH = "data/sample/thika_road_hardware_agrovet_synthetic_dataset.csv"
_cache = {}


def pipeline_for(rel):
    if rel not in _cache:
        lr = load_csv(str(sample_path(rel)))
        assert lr.success
        _cache[rel] = run_pipeline(lr.raw_df)
    return _cache[rel]


def mini_df(rows):
    """Build a raw (string) frame from partial row dicts; unspecified columns default sensibly."""
    base = {c: None for c in REQUIRED_COLUMNS}
    base.update({"transaction_type": "SALE", "business_name": "B", "branch": "Main", "sales_channel": "Counter", "customer_type": "Retail",
                 "customer_id": "C1", "product_category": "Paints", "product_name": "Paint", "quantity": "1", "unit_price_kes": "100",
                 "discount_pct": "0", "gross_sales_kes": "100", "net_sales_kes": "100", "unit_cost_kes": "60", "cogs_kes": "60",
                 "gross_profit_kes": "40", "expense_amount_kes": "0", "cash_in_kes": "100", "cash_out_kes": "0", "amount_received_kes": "100",
                 "accounts_receivable_change_kes": "0", "accounts_payable_change_kes": "0", "inventory_qty_change": "-1",
                 "inventory_value_change_kes": "-60", "manual_entry_flag": "0"})
    out = []
    for i, r in enumerate(rows):
        d = dict(base)
        d.update({"transaction_id": f"T{i+1}", "transaction_date": "2025-01-15", "document_no": f"D{i+1}"})
        d.update(r)
        out.append(d)
    return pd.DataFrame(out, columns=REQUIRED_COLUMNS).astype(object).where(lambda x: x.notna(), None).astype("string")
