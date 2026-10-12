# Explainable BI & Financial Health Decision Support System for Kenyan SMEs

An academic Data Science prototype that turns raw, imperfect SME transaction data into an **explainable** financial-health
assessment, not just a dashboard. Every score, driver and recommendation traces back to a formula, source columns and a stated
set of exclusions. No LLM or "fake AI" is used: all intelligence is statistical, rule-based and evidence-linked.

## 1. Purpose and 2. Problem
Many Kenyan SMEs lack structured financial reporting, so owners cannot easily answer: *What is happening? How healthy is the
business? Why? What should we do?* This system answers all four from transaction-level data, while being open about how
trustworthy that data is.

## 3. Intended users
SME owners and managers (primary); academic reviewers of the explainability and analytics methodology (secondary).

## 4. System architecture
```
Upload CSV -> Data Quality Assessment -> Cleaning/Validation -> KPIs -> Financial Health Score -> RAG (+critical overrides)
          -> Driver identification -> Explainable insights -> Recommendations -> Executive report
```
```
app.py                  Executive Overview (main page) + data input
pages/                  1 Data Quality, 2 Financial Performance, 3 Product & Category, 4 Customer, 5 Branch & Channel,
                        6 Financial Health, 7 Explainable Insights, 8 Recommendations, 9 Executive Report, 10 Metric Definitions
config/settings.py      Every threshold, weight and assumption (ASSUMPTION: markers)
src/data/               loader, schema (flexible columns), cleaning, validation
src/analytics/          profitability, liquidity, growth, efficiency, inventory, kpis
src/health/             thresholds, scoring, rag
src/explainability/     drivers, explanations, recommendations
src/reporting/          HTML executive report
src/pipeline.py         End-to-end pipeline (no Streamlit dependency; used by app and tests)
tools/                  generate_synthetic_dataset.py (reproducible test data)
tests/                  79 unit/integration tests (incl. partial files and column matching)
docs/technical_notes.md Full technical documentation
```

## 5. Dataset structure
~2,287 rows x 32 columns of transaction-level data: transaction types SALE, PURCHASE, EXPENSE, CUSTOMER_PAYMENT,
SUPPLIER_PAYMENT, REFUND, STOCK_ADJUSTMENT, with product, customer, branch, channel, supplier, cash, receivable, payable and
inventory fields (full list in `config/settings.py::REQUIRED_COLUMNS`). `discount_pct` is a **fraction** (0.02 = 2%).

## 5b. Uploading your own file (flexible schema)
The sample file shows what a complete dataset looks like; **your file does not need all 32 columns.** The system accepts any CSV
with a usable **date** column and at least one **amount** column (`net_sales_kes` for sales and/or `expense_amount_kes` for
expenses). It then analyses whatever the columns allow and tells you, on the Overview and Data Quality pages, exactly what is
missing and what each missing column would unlock (e.g. add `cogs_kes` for gross profit and margin, `amount_received_kes` for
collections, `inventory_qty_change` + `product_name` for inventory integrity).
- Headers are matched in three steps: exact standard names, common alternatives (`Date`, `Sales`, `Revenue`, `Expenses`, `COGS`, `Item`,
  `Qty`, `Branch`...), then keywords (e.g. `Total Sales (KES)`, `Txn Date`). Currency words such as KES/KSh are ignored. Keyword matches
  are flagged so you can check them.
- **Review how your columns were matched** (main page): if a match is wrong or nothing is recognised, pick the right column for each
  field from a drop-down and press *Apply*. This screen opens automatically when a file cannot be analysed.
- **One combined "Amount" column** is supported: rows typed Income/Sale/Credit count as sales and Expense/Debit as expenses; with no
  type column, positive amounts are sales and negative amounts are expenses (disclosed in the report).
- **Daily summary sheets** with a Sales column and an Expenses column side by side are supported: such rows are split into a sale row
  and an expense row.
- Disclosed fallbacks: `transaction_type` inferred from amounts; `net_sales` from gross sales (or quantity x price) less discount;
  `cogs` from quantity x unit cost. Numbers like `KES 1,200` are parsed.
- Measures that cannot be calculated show **not available**, never zero. Checks, drivers and score components that need absent
  columns are skipped and listed as "could not be assessed".
- The Financial Health Score is **provisional** when some points cannot be assessed (normalised over the assessable points). If
  fewer than 50 of the 100 points can be assessed, no RAG rating is given (**NOT RATED**) rather than a misleading Green.
- Only a file with no date, or no amounts at all, is rejected, with a message explaining the minimum needed.

## 6. Data-quality handling
Raw data and validated/analytical data are separate: nothing is deleted. The cleaning step adds flags and an `exclude_reason`
per row (duplicate IDs, invalid dates, invalid sale quantities...). The Data Quality page lists affected records, label
corrections, excluded rows, and offers downloads. **Data Reliability and Financial Health are displayed separately**, so a messy
file is never read as an unhealthy business, nor a good score presented as more reliable than the data allows.

## 7. KPI formulas
Adjusted Revenue = Net Sales - Refunds; Gross Profit = Adjusted Revenue - COGS; Gross Margin = GP / Adjusted Revenue; Operating
Profit = GP - Operating Expenses; Operating Margin and Opex Ratio on Adjusted Revenue; Discount Rate (sales-weighted); Refund
Rate = Refunds / Gross Sales; Average Transaction Value; Collection Coverage (estimate); Break-even = Avg Monthly Opex / Gross
Margin; growth = latest 3 vs preceding 3 months and **like-for-like same-calendar-months year on year** (never 8 vs 12 months).
See the in-app **Metric Definitions** page and `docs/technical_notes.md`.

## 8. Financial Health Score
0-100 = Profitability 35 + Liquidity & Collections 20 + Cost & Efficiency 20 + Growth & Stability 15 + Working Capital / Data
Reliability 10, every sub-score visible. RAG: 70-100 GREEN, 50-69 AMBER, 0-49 RED, plus five critical-risk overrides (persistent
operating loss, severe revenue deterioration, severe collection failure, severe margin deterioration, critical data integrity)
that force RED and are always explained. Only the collection-coverage table is explicit in the specification; the other sub-score
curves are documented assumptions in `config/settings.py`.

## 9. Explainability and 10. Recommendations
Seven rule-based drivers (A Margin Pressure, B Operating-Cost Burden, C Revenue Deterioration, D Persistent Losses, E Weak
Collection, F Discount Pressure, G Inventory Data Integrity) fire only when thresholds are crossed and carry their evidence.
Each yields a **Finding -> Evidence -> Driver -> Impact -> Recommendation** card, and prioritised recommendations
(observed issue -> evidence -> management action). Nothing is produced without a triggered driver.

## 11. Installation
```bash
cd business-intelligence-app
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```
## 12. Running
```bash
streamlit run app.py
```
Choose a bundled sample in the sidebar or upload your own CSV with the required columns.

## 13. Testing
```bash
python tests/run_all.py        # no extra tools needed (79 tests)
python tools/smoke_test_pages.py   # runs every page's code on several datasets, incl. partial files, with stubbed streamlit
pytest tests/ -v               # if pytest is installed
```

## 14. Test datasets
1. **Original sample** (`data/sample/kenyan_sme_bi_financial_operational_data_1800_records.csv`): deliberately messy. RED data
   reliability, RED health (overrides), inventory integrity fails, so turnover is withheld.
2. **Synthetic sample** (`data/sample/thika_road_hardware_agrovet_synthetic_dataset.csv`): 18 months (Jan 2025-Jun 2026) for a
   fictional hardware/agrovet business. Healthy, GREEN data reliability, intact inventory (turnover computed), but still with
   duplicate IDs, mixed/ambiguous dates, missing categories, invalid quantities, label variants and a few financial
   inconsistencies. Regenerate with `python tools/generate_synthetic_dataset.py`.

## 15. Known limitations and scope
- Collection coverage is a portfolio-level **estimate** (no invoice aging), not DSO.
- Inventory turnover is withheld whenever reconstructed stock goes negative (by design).
- Sub-score curves other than collection coverage are assumptions; on the original sample the score is about 48 versus the spec's
  "approximately low-60s, depending on interpolation"; the final RAG (RED via overrides) matches the spec.
- Ambiguous dates (both parts <= 12) default to day-first and are flagged.
- Structural blanks (e.g. no customer on an expense row) are counted in the missing-value summary for transparency.
- With partial files, results cover only what the supplied columns allow; the report states what was not assessed.
- Prototype for academic use; not accounting, tax or financial advice, and no guarantee of future performance.

## Definition of terms
**Gross Sales**value of sales before discount. 

**Net Sales** after discount. 

**Refund** value of returned goods.

**Adjusted (Net) Revenue** Net Sales - Refunds, the "revenue" used throughout. 

**COGS** cost of the goods that were sold (cost,not selling price). 

**Gross Profit** Adjusted Revenue - COGS, i.e. profit before running costs.

**Gross Margin** Gross Profit as a % of revenue: how much of each shilling is kept after paying for the goods.

**Operating Expenses (Opex)** day-to-day running costs that are not the cost of goods (rent, salaries, utilities, transport, repairs...). 

**Operating Profit** Gross Profit - Opex; negative = operating loss. **Operating Margin** Operating Profit as a % of revenue.

**Operating Expense Ratio** Opex as a % of revenue.

**Discount Rate** share of gross sales given away as discounts.

**Refund Rate** refunds as a % of gross sales.

**Average Transaction Value** revenue per valid sale. 

**Credit-like Sale** a sale where the customer paid less than the sale amount at the time (inferred, because payment method is blank on sales).

**Collection Coverage** estimated % of credit-like sales value collected in cash (estimate only).

**Estimated Uncollected Exposure** estimated KES still owed. 

**Break-even Revenue** approximate monthly revenue needed for zero operating profit at the current margin and cost structure (an estimate,not a forecast).

**Reconstructed Inventory / Stock-on-Hand** a running stock balance per product rebuilt by adding all recorded
stock movements in date order; if it goes negative the records contradict reality.

**Inventory Integrity** whether that reconstruction stays at or above zero for every product. 

**Inventory Turnover** COGS / average inventory value (only when integrity holds).

**Data Quality Score / Data Reliability** 0-100 trust rating of the input data, separate from business health.

**Financial Health Score** 0-100 composite of five weighted areas.

**RAG Status** Green = healthy, Amber = needs attention,Red = significant concern (text always shown with colour). 

**Critical-risk Override** a rule that forces RED regardless of score, with the reason shown. 

**Driver** a rule-based, evidence-backed reason behind the result (e.g. Margin Pressure).
