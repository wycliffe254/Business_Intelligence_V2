from tests.helpers import *
from src.analytics import growth
from src.analytics.kpis import compute_all_kpis
from src.data.cleaning import clean_dataset


def _k(rows):
    return compute_all_kpis(clean_dataset(mini_df(rows))["analytical_df"])


def test_gross_profit_margin_and_operating_profit_formulas():
    k = _k([{"net_sales_kes": "1000", "gross_sales_kes": "1000", "cogs_kes": "700", "gross_profit_kes": "300", "quantity": "5"},
            {"transaction_type": "REFUND", "net_sales_kes": "100", "quantity": "-1"},
            {"transaction_type": "EXPENSE", "expense_amount_kes": "200", "net_sales_kes": "0", "cogs_kes": "0", "gross_sales_kes": "0", "quantity": "0"}])
    c = k["core"]
    assert c["adjusted_revenue"] == 900 and c["gross_profit"] == 200
    assert round(c["gross_margin_pct"], 2) == 22.22
    assert c["operating_expenses"] == 200 and c["operating_profit"] == 0
    assert round(c["refund_rate_pct"], 2) == 10.0

def test_weighted_discount_rate():
    k = _k([{"gross_sales_kes": "1000", "net_sales_kes": "900", "discount_pct": "0.1"}, {"gross_sales_kes": "100", "net_sales_kes": "100"}])
    assert round(k["core"]["discount_rate_pct"], 2) == round(100 / 1100 * 100, 2)

def test_breakeven_formula():
    k = _k([{"net_sales_kes": "1000", "gross_sales_kes": "1000", "cogs_kes": "500", "gross_profit_kes": "500"},
            {"transaction_type": "EXPENSE", "expense_amount_kes": "400", "net_sales_kes": "0", "cogs_kes": "0", "gross_sales_kes": "0", "quantity": "0"}])
    assert k["breakeven"]["breakeven_revenue"] == 800   # 400 / 0.5

def test_recent_trend_and_insufficient_history():
    m = pd.DataFrame({"revenue": [100] * 3 + [90] * 3})
    t = growth.recent_trend(m)
    assert round(t["change_pct"], 1) == -10.0
    assert growth.recent_trend(pd.DataFrame({"revenue": [1, 2, 3]}))["sufficient_data"] is False

def test_comparable_period_uses_only_common_months():
    months = pd.period_range("2025-01", "2026-06", freq="M")
    m = pd.DataFrame({"month": months, "revenue": 100.0, "gross_profit": 20.0, "operating_expenses": 10.0})
    c = growth.comparable_period_yoy(m)
    assert c["months_compared"] == ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]   # not Jan-Aug vs Jan-Jun
    assert c["revenue_change_pct"] == 0

def test_profitable_months_and_loss_streak():
    s = growth.profitability_stability(pd.DataFrame({"operating_profit": [1, -1, -1, -1, 5]}))
    assert s["profitable_months"] == 2 and s["longest_consecutive_loss_streak"] == 3

def test_original_dataset_matches_spec_expectations():
    k = pipeline_for(ORIGINAL)["kpis"]
    c = k["core"]
    assert abs(c["adjusted_revenue"] / 1e6 - 7.70) < 0.05
    assert abs(c["gross_margin_pct"] - 21.3) < 0.3
    assert abs(c["operating_margin_pct"] - (-20.6)) < 0.3
    assert abs(c["opex_ratio_pct"] - 41.9) < 0.3
    assert abs(k["comparable_yoy"]["revenue_change_pct"] - (-21.9)) < 0.3
    assert abs(k["comparable_yoy"]["margin_change_pp"] - (-4.9)) < 0.3
    assert abs(k["collections"]["collection_coverage_pct"] - 88.5) < 0.5
    assert abs(k["breakeven"]["breakeven_revenue"] - 759283) < 500
    assert k["profitability_stability"]["profitable_months"] == 4

def test_inventory_gate():
    assert pipeline_for(ORIGINAL)["kpis"]["inventory_turnover"] is None
    t = pipeline_for(SYNTH)["kpis"]["inventory_turnover"]
    assert t is not None and 0.5 < t["turnover_ratio"] < 20   # sane ratio, not tens of thousands


def _independent(rel):
    """Recompute headline KPIs straight from the raw CSV with no app code, using the app's row-inclusion list."""
    raw = pd.read_csv(sample_path(rel), dtype=str)
    r = pipeline_for(rel)
    keep = r["analytical_df"].query("include_in_kpis")["transaction_id"]
    d = raw[~raw.transaction_id.duplicated()]
    d = d[d.transaction_id.isin(keep)].copy()
    for c in ["net_sales_kes", "cogs_kes", "expense_amount_kes"]:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    sale, ref, ex = (d[d.transaction_type == t] for t in ["SALE", "REFUND", "EXPENSE"])
    rev = sale.net_sales_kes.sum() - ref.net_sales_kes.sum()
    gp = rev - sale.cogs_kes.sum()
    return rev, gp, gp - ex.expense_amount_kes.sum(), ex.expense_amount_kes.sum()

def test_kpis_match_independent_recomputation_from_raw_csv():
    for rel in [ORIGINAL, SYNTH]:
        c = pipeline_for(rel)["kpis"]["core"]
        rev, gp, op, opex = _independent(rel)
        assert abs(c["adjusted_revenue"] - rev) < 1 and abs(c["gross_profit"] - gp) < 1
        assert abs(c["operating_profit"] - op) < 1 and abs(c["operating_expenses"] - opex) < 1

def test_monthly_series_sums_to_totals():
    for rel in [ORIGINAL, SYNTH]:
        k = pipeline_for(rel)["kpis"]
        m, c = k["monthly"], k["core"]
        assert abs(m.revenue.sum() - c["adjusted_revenue"]) < 1 and abs(m.operating_profit.sum() - c["operating_profit"]) < 1

def test_every_segment_table_reconciles_to_total_revenue():
    for rel in [ORIGINAL, SYNTH]:
        k = pipeline_for(rel)["kpis"]
        for name in ["branch", "channel", "customer_type", "product_category", "product"]:
            seg = k[name]
            assert abs(seg.adjusted_revenue.sum() - k["core"]["adjusted_revenue"]) < 1, (rel, name)
            assert abs(seg.revenue_share_pct.sum() - 100) < 0.01
        assert abs(k["expense_breakdown"].amount_kes.sum() - k["core"]["operating_expenses"]) < 1

def test_refund_only_segment_has_no_margin():
    k = pipeline_for(ORIGINAL)["kpis"]
    ch = k["channel"]
    row = ch[ch.revenue <= 0] if "revenue" in ch else ch.iloc[0:0]
    assert row["gross_margin_pct"].isna().all()
