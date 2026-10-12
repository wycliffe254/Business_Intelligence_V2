"""
Flexible schema handling.

Uploads do NOT have to match the sample file. This module
  1. normalises headers (case/spacing/common aliases),
  2. works out which columns actually hold data,
  3. derives a few safe fallbacks (documented below),
  4. reports which analyses each missing column would unlock ("capabilities").

The app only refuses a file when it holds nothing analysable: no usable date column, or no
sales/expense amounts at all.

Fallbacks (ASSUMPTIONS, always disclosed in the report):
  * transaction_type blank/missing -> inferred: expense_amount > 0 (and no sales) => EXPENSE, net_sales > 0 => SALE
  * net_sales_kes missing          -> gross_sales * (1 - discount_pct), else quantity * unit_price * (1 - discount_pct)
  * cogs_kes missing               -> quantity * unit_cost_kes
Anything not derivable stays missing and the dependent KPI is shown as "not available", never as zero.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
import numpy as np
import pandas as pd
from config.settings import COVERAGE_FULL_AT_LEAST, COVERAGE_MINIMAL_BELOW, HEADER_ALIASES, REQUIRED_COLUMNS, VALID_TRANSACTION_TYPES

# capability key -> (label, required columns, what it unlocks)
CAPABILITIES = [
    ("time", "Time trends & growth", ["transaction_date"], "Monthly trends, recent and year-on-year growth, profitable months"),
    ("classification", "Transaction classification", ["transaction_type"], "Separating sales, refunds, expenses, purchases and payments"),
    ("revenue", "Revenue", ["net_sales_kes"], "Revenue, average transaction value, revenue trends"),
    ("gross_profit", "Gross profit & margin", ["net_sales_kes", "cogs_kes"], "Gross profit, gross margin, margin pressure"),
    ("operating_expenses", "Operating expenses & operating profit", ["expense_amount_kes", "transaction_type"], "Operating profit/margin, expense ratio, break-even, persistent-loss detection"),
    ("discounts", "Discount analysis", ["gross_sales_kes", "net_sales_kes"], "Weighted discount rate, discount pressure"),
    ("refunds", "Refund analysis", ["transaction_type", "net_sales_kes"], "Refund rate"),
    ("collections", "Collections & credit exposure", ["amount_received_kes", "net_sales_kes"], "Collection coverage, uncollected exposure, weak-collection driver"),
    ("inventory", "Inventory integrity & turnover", ["inventory_qty_change", "product_name"], "Reconstructed stock, inventory integrity, turnover"),
    ("product", "Product & category analysis", ["product_name", "product_category"], "Product/category revenue, margin and quadrants"),
    ("customer", "Customer analysis", ["customer_type"], "Revenue and margin by customer type"),
    ("branch", "Branch analysis", ["branch"], "Revenue and margin by branch"),
    ("channel", "Sales-channel analysis", ["sales_channel"], "Revenue and margin by channel"),
    ("duplicates", "Duplicate detection", ["transaction_id"], "Duplicate transaction IDs"),
    ("quantity_checks", "Quantity validation", ["quantity"], "Invalid or zero sale quantities"),
]


CURRENCY_TOKENS = {"kes", "ksh", "kshs", "shs", "sh", "usd", "currency"}
GENERIC_AMOUNT = "amount_generic"      # pseudo-field: ONE amount column holding sales and expenses together
MAPPABLE_EXTRA = {GENERIC_AMOUNT}

# Keyword rules for headers that are not an exact standard name or alias: (target, must-match regex, must-NOT-match regex).
# Evaluated in order; the first unclaimed target that matches wins. Every keyword match is shown to the user for checking.
_NOT_PERSON = r"(person|rep|agent|staff|channel|date|id|no|number|category|type|name)"
KEYWORD_RULES = [
    ("transaction_date", r"(^|_)(date|datetime|timestamp|day|period)(_|$)", r"(due|expiry|birth)"),
    ("transaction_type", r"^(txn_|trans_|transaction_|entry_)?(type|nature|kind|class)$", None),
    ("gross_sales_kes", r"(gross.*(sales?|revenue))|((sales?|revenue).*gross)", None),
    ("customer_type", r"(customer|client|buyer)_?(type|segment|category|class)", None),
    ("net_sales_kes", r"(^|_)(sales?|revenue|income|turnover|takings|sold)(_|$)", _NOT_PERSON),
    ("cogs_kes", r"(^|_)cogs(_|$)|cost_of_(goods|sales)|cost_price|purchase_cost|buying_(price|cost)", None),
    ("expense_amount_kes", r"(expense|expenses|expenditure|spend|spending|outgoing|overhead|opex)", r"(category|type|name|account|ratio)"),
    ("unit_cost_kes", r"unit_cost|cost_per_unit|cost_per_item", None),
    ("unit_price_kes", r"unit_price|price_per|selling_price|^price$|(^|_)price(_|$)", None),
    ("quantity", r"(^|_)(qty|quantity|units|volume)(_|$)|no_of_(items|units)", None),
    ("product_category", r"(category|group|class|department)", r"(expense|customer|client)"),
    ("product_name", r"(product|item|goods|sku|particulars|description)", r"(category|type|code|id|group)"),
    ("customer_id", r"(customer|client|buyer)", None),
    ("branch", r"(branch|location|outlet|shop|store|site|region)", None),
    ("sales_channel", r"(channel|source)", None),
    ("payment_method", r"(payment|pay)_(method|mode|type)|mode_of_payment|paid_via|(^|_)mpesa(_|$)", None),
    ("supplier_name", r"(supplier|vendor)", None),
    ("amount_received_kes", r"(received|collected|paid_amount|amount_paid|^paid$)", None),
    ("discount_pct", r"discount", None),
    ("transaction_id", r"(^|_)(id|ref|reference|receipt_no|invoice_no|txn|transaction_no)(_|$)", None),
    (GENERIC_AMOUNT, r"(^|_)(amount|amt|total|value|sum)(_|$)", None),
]


def normalise_header(name: str) -> str:
    """lower-case, non-alphanumerics -> '_', currency words such as KES/KSh dropped ('Amount (KES)' -> 'amount')."""
    toks = [t for t in re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_").split("_") if t]
    kept = [t for t in toks if t not in CURRENCY_TOKENS]
    return "_".join(kept or toks)


def match_headers(columns, column_map=None) -> dict:
    """Decide which uploaded header plays which role. Returns {original_header: (standard_field, how)} where how is
    'chosen by you' | 'exact' | 'alias' | 'keyword'. `column_map` = {standard_field: original_header or None}; an explicit
    choice always wins, and None means 'this file has no such column' (auto-detection is switched off for that field)."""
    req = set(REQUIRED_COLUMNS) | MAPPABLE_EXTRA
    columns = list(columns)
    norms = {c: normalise_header(c) for c in columns}                                   # currency words dropped
    plain = {c: re.sub(r"[^a-z0-9]+", "_", str(c).strip().lower()).strip("_") for c in columns}   # exact spelling, nothing dropped
    claimed, result, blocked = {}, {}, set()
    for std, orig in (column_map or {}).items():
        if orig is None:
            blocked.add(std)
        elif orig in columns and std in req and std not in claimed and orig not in result:
            claimed[std] = orig
            result[orig] = (std, "chosen by you")
    # pass 1: exact standard names, pass 2: aliases, pass 3: keywords
    for how, getter in [("exact", lambda c: plain[c] if plain[c] in req else None), ("alias", lambda c: HEADER_ALIASES.get(norms[c]) or HEADER_ALIASES.get(plain[c]))]:
        for c in columns:
            if c in result:
                continue
            t = getter(c)
            if t and t in req and t not in claimed and t not in blocked:
                claimed[t] = c
                result[c] = (t, how)
    for target, must, must_not in KEYWORD_RULES:
        if target in claimed or target in blocked:
            continue
        for c in columns:
            if c in result:
                continue
            n = norms[c]
            if re.search(must, n) and not (must_not and re.search(must_not, n)):
                claimed[target] = c
                result[c] = (target, "keyword")
                break
    return result


# (standard field, plain-language label) shown on the "Review how your columns were matched" screen
MAP_FIELDS = [
    ("transaction_date", "Date"),
    ("net_sales_kes", "Sales / revenue amount"),
    ("expense_amount_kes", "Expense amount"),
    (GENERIC_AMOUNT, "ONE combined 'Amount' column (sales and expenses together)"),
    ("transaction_type", "Transaction type (sale / expense / refund ...)"),
    ("cogs_kes", "Cost of goods sold"),
    ("gross_sales_kes", "Gross sales (before discount)"),
    ("amount_received_kes", "Amount received (to detect credit sales)"),
    ("product_name", "Product / item"),
    ("product_category", "Product category"),
    ("quantity", "Quantity"),
    ("customer_type", "Customer type"),
    ("customer_id", "Customer"),
    ("branch", "Branch / location"),
    ("sales_channel", "Sales channel"),
    ("transaction_id", "Transaction ID / reference"),
]


def suggest_mapping(columns) -> dict:
    """{standard_field: original_header} the system would pick automatically (used to pre-fill the matching screen)."""
    return {std: orig for orig, (std, _) in match_headers(columns).items()}


def standardise_headers(df: pd.DataFrame, column_map=None):
    """Rename headers to the standard schema. Returns (df, renamed: {original: standard}, unrecognised: [original])."""
    matches = match_headers(df.columns, column_map)
    out = df.copy()
    out.columns = [matches[c][0] if c in matches else c for c in df.columns]
    renamed = {c: m[0] for c, m in matches.items() if m[0] != c}
    known = set(REQUIRED_COLUMNS) | MAPPABLE_EXTRA
    return out, renamed, [c for c in out.columns if c not in known]


def match_methods(columns, column_map=None) -> dict:
    """{original_header: (standard_field, how)} for display."""
    return match_headers(columns, column_map)


TYPE_SYNONYMS = {
    "SALE": {"sale", "sales", "income", "revenue", "receipt", "credit", "cash_in", "in", "turnover"},
    "EXPENSE": {"expense", "expenses", "cost", "spend", "debit", "cash_out", "out", "overhead", "opex", "expenditure"},
    "REFUND": {"refund", "refunds", "return", "returns"},
    "PURCHASE": {"purchase", "purchases", "stock_purchase"},
}


def _normalise_type_value(v):
    if v is None or v is pd.NA or (isinstance(v, float) and pd.isna(v)) or str(v).strip() in ("", "<NA>", "nan", "None"):
        return None
    key = re.sub(r"[^a-z0-9]+", "_", str(v).strip().lower()).strip("_")
    up = key.upper()
    if up in VALID_TRANSACTION_TYPES:
        return up
    for target, words in TYPE_SYNONYMS.items():
        if key in words:
            return target
    return str(v).strip()


def _has_data(series: pd.Series) -> bool:
    return bool((series.notna() & (series.astype(str).str.strip() != "")).any())


def _num(series):
    return pd.to_numeric(series.astype(str).str.replace(r"(?i)kes|ksh|[,\s]", "", regex=True), errors="coerce")


@dataclass
class CapabilityStatus:
    key: str
    label: str
    status: str                 # "available" | "derived" | "unavailable"
    missing_columns: list
    unlocks: str


@dataclass
class SchemaReport:
    viable: bool
    message: str
    present_columns: list = field(default_factory=list)      # hold data in the upload
    derived_columns: dict = field(default_factory=dict)      # column -> how it was derived
    missing_columns: list = field(default_factory=list)      # neither present nor derivable
    renamed_columns: dict = field(default_factory=dict)
    unrecognised_columns: list = field(default_factory=list)
    capabilities: list = field(default_factory=list)
    coverage_pct: float = 0.0
    level: str = "full"                                       # full | limited | minimal
    availability: dict = field(default_factory=dict)          # capability key -> bool
    match_how: dict = field(default_factory=dict)             # original header -> (standard field, how it was matched)

    def banner_lines(self):
        lines = []
        if self.missing_columns:
            lines.append(f"Your file contains {len(self.present_columns)} of {len(REQUIRED_COLUMNS)} expected columns "
                         f"({self.coverage_pct:.0f}%). Analyses that could not be fully performed are marked 'not available'.")
            for c in self.capabilities:
                if c.status == "unavailable":
                    lines.append(f"For **{c.label}** ({c.unlocks}) you would also need: {', '.join(c.missing_columns)}.")
        for col, how in self.derived_columns.items():
            lines.append(f"`{col}` was not supplied, so it was {how}. Treat related figures as estimates.")
        return lines


def prepare_frame(raw_df: pd.DataFrame, column_map=None):
    """Standardise headers, fill missing schema columns, derive safe fallbacks. Returns (prepared_df, SchemaReport)."""
    df, renamed, unrecognised = standardise_headers(raw_df, column_map)
    n = len(df)
    present = [c for c in REQUIRED_COLUMNS if c in df.columns and _has_data(df[c])]
    for c in REQUIRED_COLUMNS:
        if c not in df.columns:
            df[c] = pd.Series([None] * n, index=df.index, dtype="string")
    derived = {}

    # transaction_type VALUES like "Income"/"Expense"/"Debit" -> SALE/EXPENSE/... (already-valid values are untouched)
    if "transaction_type" in present:
        before = df["transaction_type"].astype("object")
        after = before.map(_normalise_type_value)
        if (after.fillna("") != before.fillna("").map(lambda v: str(v).strip())).any():
            derived["transaction_type"] = "standardised from your type labels (e.g. Income -> SALE, Expense -> EXPENSE)"
        df["transaction_type"] = after.astype("string")

    # ONE combined "Amount" column: split into sales vs expenses using the type column, else by sign
    if GENERIC_AMOUNT in df.columns and _has_data(df[GENERIC_AMOUNT]) and "net_sales_kes" not in present and "expense_amount_kes" not in present:
        amt = _num(df[GENERIC_AMOUNT])
        typ = df["transaction_type"].astype("object").map(_normalise_type_value)
        is_exp = (typ == "EXPENSE") | (typ.isna() & (amt < 0))
        is_ref = typ == "REFUND"
        is_sale = (typ == "SALE") | (typ.isna() & (amt >= 0))
        net = amt.where(is_sale).combine_first(amt.abs().where(is_ref))
        exp = amt.abs().where(is_exp)
        filled = typ.where(typ.notna(), pd.Series(np.where(is_exp, "EXPENSE", np.where(is_sale, "SALE", None)), index=df.index))
        df["transaction_type"] = filled.astype("object").astype("string")
        how = ("taken from your single amount column: rows typed income/sale count as sales and rows typed expense/debit as expenses"
               if typ.notna().any() else "taken from your single amount column: positive amounts treated as sales and negative amounts as expenses")
        if net.notna().any():
            df["net_sales_kes"] = net.round(2).astype("string")
            derived["net_sales_kes"] = how
        if exp.notna().any():
            df["expense_amount_kes"] = exp.round(2).astype("string")
            derived["expense_amount_kes"] = how
        derived.setdefault("transaction_type", "set from your type column or the sign of the amounts")

    # transaction_type inference (blank cells or missing column)
    if "transaction_type" not in present or df["transaction_type"].isna().any() or (df["transaction_type"].astype(str).str.strip() == "").any():
        ns, ex = _num(df["net_sales_kes"]), _num(df["expense_amount_kes"])
        inferred = pd.Series(np.where(ex.fillna(0) > 0, np.where(ns.fillna(0) > 0, "SALE", "EXPENSE"),
                                      np.where(ns.fillna(0) > 0, "SALE", "UNKNOWN")), index=df.index)
        blank = df["transaction_type"].isna() | (df["transaction_type"].astype(str).str.strip() == "")
        if blank.any() and (ns.notna().any() or ex.notna().any()):
            df["transaction_type"] = df["transaction_type"].astype("object").where(~blank, inferred).astype("string")
            derived["transaction_type"] = "inferred from amounts (expense amount => EXPENSE, sales amount => SALE)" if "transaction_type" not in present \
                else "inferred for blank rows from amounts"

    # One row holding BOTH a sales and an expense amount (e.g. a daily summary sheet) and no type column: split it into a SALE row
    # and an EXPENSE row so each amount is counted under the right heading.
    if "transaction_type" in derived and "transaction_type" not in present:
        ns, ex = _num(df["net_sales_kes"]), _num(df["expense_amount_kes"])
        both = (ns.fillna(0) > 0) & (ex.fillna(0) > 0)
        if both.any():
            exp_rows = df[both].copy()
            exp_rows["transaction_type"] = "EXPENSE"
            for c in ["net_sales_kes", "gross_sales_kes", "cogs_kes", "gross_profit_kes", "quantity", "amount_received_kes"]:
                exp_rows[c] = pd.Series(["0"] * len(exp_rows), index=exp_rows.index, dtype="string")
            if "transaction_id" in present:
                exp_rows["transaction_id"] = exp_rows["transaction_id"].astype("string") + "-EXP"
            df.loc[both, "expense_amount_kes"] = "0"
            df = pd.concat([df, exp_rows], ignore_index=True)
            derived["transaction_type"] += f"; {int(both.sum())} rows that held both a sales and an expense amount were split into a sale row and an expense row"

    # net_sales from gross / price
    if "net_sales_kes" not in present and "net_sales_kes" not in derived:
        disc = _num(df["discount_pct"]).fillna(0)
        g, q, p = _num(df["gross_sales_kes"]), _num(df["quantity"]), _num(df["unit_price_kes"])
        calc = g * (1 - disc)
        calc = calc.where(calc.notna(), q * p * (1 - disc))
        if calc.notna().any():
            df["net_sales_kes"] = calc.round(2).astype("string")
            derived["net_sales_kes"] = "calculated from gross sales (or quantity x unit price) less discount"

    # cogs from quantity x unit cost
    if "cogs_kes" not in present:
        calc = _num(df["quantity"]).abs() * _num(df["unit_cost_kes"])
        sale_like = df["transaction_type"].astype(str).str.upper().isin(["SALE", "REFUND"]) | (df["transaction_type"].isna())
        calc = calc.where(sale_like)
        if calc.notna().any():
            df["cogs_kes"] = calc.round(2).astype("string")
            derived["cogs_kes"] = "calculated as quantity x unit cost"

    usable = set(present) | set(derived)
    missing = [c for c in REQUIRED_COLUMNS if c not in usable]
    caps, avail = [], {}
    for key, label, req, unlocks in CAPABILITIES:
        miss = [c for c in req if c not in usable]
        if key == "product":                       # either product_name or category is enough
            miss = [] if ("product_name" in usable or "product_category" in usable) else req
        status = "unavailable" if miss else ("derived" if any(c in derived for c in req) else "available")
        caps.append(CapabilityStatus(key, label, status, miss, unlocks))
        avail[key] = not miss
    # discounts need a genuinely supplied gross column (a derived gross would hide discounts)
    avail["discounts"] = "gross_sales_kes" in present and "net_sales_kes" in usable
    # operating profit needs gross profit AND expenses
    avail["operating_profit"] = avail["gross_profit"] and avail["operating_expenses"]
    avail["refunds"] = avail["refunds"] and "transaction_type" in present      # inferred types cannot reveal refunds
    avail["collections"] = avail["collections"] and "amount_received_kes" in present

    coverage = len(present) / len(REQUIRED_COLUMNS) * 100
    level = "full" if coverage >= COVERAGE_FULL_AT_LEAST else "minimal" if coverage < COVERAGE_MINIMAL_BELOW else "limited"

    viable = "transaction_date" in present and ("net_sales_kes" in usable or "expense_amount_kes" in usable)
    msg = ""
    if not viable:
        hint = " Use the 'Review how your columns were matched' section on the main page to point the system at the right columns."
        needed = []
        if "transaction_date" not in present:
            needed.append("a date column (transaction_date)")
        if "net_sales_kes" not in usable and "expense_amount_kes" not in usable:
            needed.append("at least one amount column (net_sales_kes for sales and/or expense_amount_kes for expenses)")
        msg = ("This file does not contain enough recognisable data to analyse. At minimum the system needs " + " and ".join(needed) +
               ". Your file's columns are: " + ", ".join(str(c) for c in raw_df.columns) + "." + hint +
               " Recommended columns for a full analysis: " + ", ".join(REQUIRED_COLUMNS) + ".")
    return df, SchemaReport(viable, msg, present, derived, missing, renamed, unrecognised, caps, coverage, level, avail,
                            match_headers(raw_df.columns, column_map))
