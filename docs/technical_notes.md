# Technical Notes

## 1. Architecture
`loader` (raw strings, schema check) -> `cleaning` (flags; raw data never mutated) -> `validation` (Data Quality Report) ->
`analytics/*` via `kpis.compute_all_kpis` -> `health/scoring` -> `health/rag` -> `explainability/drivers|explanations|recommendations`
-> `reporting/report`. `src/pipeline.run_pipeline` chains these and has no Streamlit dependency; Streamlit pages only present.

## 1b. Flexible schema (`src/data/schema.py`)
Headers are normalised (case/spacing) and matched to the standard names or aliases (`HEADER_ALIASES` in settings). A column
"is present" only if it holds at least one non-blank value. A file is viable if it has a date column and `net_sales_kes` (given or
derivable) and/or `expense_amount_kes`. Each of 15 **capabilities** (revenue, gross profit, operating expenses, discounts, refunds,
collections, inventory, product, customer, branch, channel, duplicates, quantity checks, time, classification) is marked
available / derived / unavailable, with the columns still needed. Availability flows into every layer:
- KPIs whose inputs are absent are NaN ("not available"), never 0. Discounts need a *supplied* gross column; refunds need a
  *supplied* transaction type; collections need `amount_received_kes`.
- Cleaning skips checks whose columns are absent (no false "credit-like" sales, duplicates, or financial inconsistencies).
- Data Quality re-weights its dimensions over the checks that could be run; below 40% column coverage the status cannot be GREEN.
- Health score: sub-scores whose inputs or history are missing are excluded; the total is normalised over assessable points and
  flagged provisional. If assessable points < `MIN_ASSESSABLE_POINTS` (50) and no override fires, status is NOT RATED.
- Drivers record `assessable` and what they `need`; unassessable drivers never trigger and are listed separately.
- Inventory is "not assessable" (not "OK") when stock columns are absent.

## 2. Raw vs analytical data
`clean_dataset` returns raw + derived columns: `parsed_date`, `is_valid_date`, `is_ambiguous_date`, `is_duplicate_txn_id`,
`is_invalid_sale_quantity`, `has_financial_inconsistency`, `*_norm` (standardised labels), `is_credit_like_sale`,
`include_in_kpis`, `exclude_reason`. KPIs use only `include_in_kpis` rows. Excluded: duplicate IDs (first kept), invalid/missing
dates, missing critical fields, sales with quantity <= 0 and positive value.

## 3. Dates
ISO, DD-MM-YYYY and slash dates in either order. If one part > 12 it is the day. If both <= 12 the order is ambiguous: day-first is
assumed and the row is flagged (`is_ambiguous_date`).

## 4. Label standardisation
Spelling/case/spacing/singular-plural variants of a label (e.g. `agro inputs`, `Hardware `, `Mpesa`, `Electricals`) map to the most
frequent spelling; variants are counted as inconsistencies and listed on the Data Quality page.

## 5. KPI formulas
| KPI | Formula |
|---|---|
| Adjusted Revenue | sum(net_sales_kes, SALE) - sum(net_sales_kes, REFUND) |
| Gross Profit / Margin | Adj. Revenue - sum(cogs_kes, SALE); / Adj. Revenue x 100 |
| Operating Expenses | sum(expense_amount_kes, EXPENSE) |
| Operating Profit / Margin / Opex ratio | GP - Opex; each / Adj. Revenue x 100 |
| Discount Rate | sum(gross - net, SALE) / sum(gross, SALE) x 100 |
| Refund Rate | Refunds / Gross Sales x 100 |
| Collection Coverage (estimate) | (amount_received on credit-like sales + sum(cash_in, CUSTOMER_PAYMENT)) / credit-like sales value x 100 |
| Recent growth | latest 3 months vs preceding 3 (needs >= 6 months) |
| Comparable growth | same calendar months in the two latest years, only months present in both (window Jan-Aug) |
| Break-even | avg monthly Opex / gross margin fraction (approximate, not a forecast) |
| Inventory turnover | COGS / average of opening and ending total inventory value at cost (only if integrity passes) |

### Validation against the Expected Output Specification (original sample)
| Metric | Spec | This implementation |
|---|---|---|
| Adjusted revenue | ~7.70M | 7,704,313 |
| Gross profit / margin | ~1.64M / 21.3% | 1,637,512 / 21.25% |
| Operating profit / margin | ~-1.59M / -20.6% | -1,590,121 / -20.64% |
| Opex ratio | ~41.9% | 41.89% |
| Recent 3v3 revenue | ~-6.6% | -6.63% |
| Jan-Aug YoY revenue | ~-21.9% | -21.92% |
| Gross margin change | ~-4.9pp | -4.93pp |
| Collection coverage | ~88.5% | 88.47% |
| Discount / refund rate | ~4.4% / ~0.26% | 4.44% / 0.25% |
| Profitable months | ~20% | 20% (4 of 20) |
| Break-even revenue | ~759,283 (+97%) | 759,283 (+97.1%) |

## 6. Health score
Weights 35/20/20/15/10. Sub-score curves are piecewise-linear tables in `config/settings.py`; only collection coverage is explicit in
the spec. The Gross Profit Trend sub-score uses comparable-period gross-profit change. On the original sample the total is about
48 (spec: "approximately low-60s depending on interpolation"). All underlying KPIs match, so the gap is purely the assumed
curves; the RAG outcome (RED through overrides 1 and 2) matches the spec. Recalibrate in `config/settings.py` only.

## 7. RAG and overrides
>=70 GREEN, 50-69 AMBER, <50 RED. Overrides: persistent operating loss (margin < -10% and >= 3 consecutive loss months); severe
revenue deterioration (comparable decline <= -20% with margin also falling); collection coverage < 60%; gross margin fall >= 5pp;
critical data integrity (DQ RED and score < 40). Each emits a plain-language explanation.

## 8. Data quality score
Seven weighted dimensions (duplicates 15, missing values 20, invalid dates 15, invalid quantities 15, category consistency 10,
payment-label consistency 10, financial consistency 15). GREEN >= 85, AMBER >= 65, else RED; failed inventory integrity caps the
score below AMBER. These are project-defined control thresholds, not industry standards.

## 9. Explainability and recommendations
Drivers A-G (see README) with thresholds in `DRIVER_THRESHOLDS`. Driver C attaches branch, category, customer-type and channel
breakdowns (lowest-revenue segments; descriptive, not causal). Recommendation priorities: 1 Restore profitability, 2 Protect
revenue, 3 Improve margin, 4 Control costs / discount controls, 5 Collections, 6 Reconcile inventory. Emitted only when the
driver fired.

## 10. Machine learning
Not used: no prediction target is needed, and rule-based, auditable logic is better for explainability here.

## 11. Limitations
Collection coverage is an estimate; inventory turnover is withheld on unreliable stock; ambiguous dates default to day-first;
filters on the Financial Performance page keep expense rows whole because expenses are not attributable to products.

## 12. Changelog (issues found and fixed during validation)
- **Flexible uploads**: files no longer need the full sample schema (see 1b); partial files are analysed, with clear notices,
  NOT RATED when too little can be assessed, and a page-level smoke harness (`tools/smoke_test_pages.py`) that caught a crash in the
  missing-values table for files with none of the tracked descriptive fields.
- **Financial-consistency check**: `discount_pct` is a fraction (0.02 = 2%); dividing by 100 had flagged ~58% of valid sales.
- **Inventory turnover**: previously divided KES COGS by a unit count (nonsense ratio); now uses inventory *value*.
- **Synthetic dataset generator**: opening stock now recorded as purchases; chronological simulation; collections tied to credit
  exposure (cannot exceed 100%); events capped at period end; opening stock dated within the first month.
- **Comparable-period growth**: compares only months present in both years (no unequal month counts).
- **Full-figure KPI display**: pages show complete KES figures (e.g. KES 7,704,313), 3 per row, instead of truncated values.
- **Empty-group robustness**: datasets with no refund rows no longer crash the monthly/segment analytics.
- **Streamlit compatibility**: pages avoid the deprecated `use_container_width` argument.
- **Stray internals shown on the Data Quality page**: a one-line conditional (`st.dataframe(...) if x else st.write(...)`) written as a
  bare statement was auto-displayed by Streamlit "magic". Replaced with if/else; a static test now forbids standalone non-call
  expressions in any page.
- **Segment tables now reconcile**: blank branch/channel/customer/category values form an explicit "Unspecified" row, refunds in
  segments with no sales are kept, and refund-only segments show no margin. Tests assert every segment table, the monthly series
  and the expense breakdown sum to the headline totals, and that headline KPIs equal an independent recomputation from the raw CSV.
- **RAG visuals**: amber is now a bright orange-yellow with dark text, clearly different from the crimson red; every status also has a shape
  marker (\u25CF green, \u25B2 amber, \u25A0 red, \u25C6 not rated) in addition to its text label. Defined once in `src/utils/formatting.py`.
- **Wrong arrow on the revenue-change metric**: the delta text began with "KES", so Streamlit treated a negative change as positive (green up
  arrow). Deltas now use `signed_kes()` so the sign comes first; a test forbids `delta=kes(...)`.
- **Monthly charts are all line charts** with one fixed colour per measure and a zero reference line; category comparisons (branch, channel,
  customer type, expenses by category) stay as bar charts because categories have no natural order.
- **Uploads with unfamiliar headers were rejected** (e.g. `Amount (KES)`, `Total`): header matching is now exact -> alias -> keyword, with
  currency words ignored (exact standard names are matched *before* stripping, so `inventory_value_change_kes` still matches). A manual
  "Review how your columns were matched" form (`column_map` {field: header | None}) overrides auto-detection. Added support for a single
  combined Amount column (type labels or sign decide sales vs expense), type-label standardisation (Income/Expense/Debit...), and splitting
  daily-summary rows that hold both a sales and an expense amount. `LoadResult.raw_df` now keeps the original headers; the pipeline
  standardises once so the "how it was matched" information shown to the user is accurate.
