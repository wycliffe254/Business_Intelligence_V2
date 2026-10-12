"""
Generate the synthetic Kenyan SME test dataset (healthy business, intact inventory,
deliberate mild data-quality issues).

    python tools/generate_synthetic_dataset.py [output.csv]

Design notes (each fixes a problem found while validating the first version):
 * Opening stock is written as explicit PURCHASE rows; otherwise the app (correctly)
   reconstructs stock from zero and every sale looks unsupported.
 * Sales are simulated in true chronological order and restock purchases are dated
   on/before the sale that needs them, so reconstructed stock never goes negative.
 * Customer payments are sized from actual credit exposure (collection ~86%), so
   collection coverage cannot exceed 100%.
 * All events are capped at the end of the reporting period (no partial extra month).
 * Rows are left in chronological/causal order (same-day ties broken by generation order).
"""
import sys
import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)
BUSINESS = "Thika Road Hardware & Agrovet Ltd"
BRANCHES = ["Thika Town", "Juja"]
CHANNELS = ["Counter", "Phone Order", "M-Pesa Till", "Delivery", "Online Order"]
CUST_TYPES = ["Retail", "Wholesale", "Contractor", "Farmer", "Reseller"]
STAFF = ["PW", "MN", "SK", "TK", "RA", "JB"]
SUPPLIERS = ["Thika Building Suppliers Ltd", "AgroChem Kenya Distributors", "Bamburi Cement Depot", "Nairobi Paints Wholesale", "ElectroParts Kenya"]
PAY = ["M-PESA", "Bank Transfer", "Cash", "Cheque"]
PRODUCTS = {
    "Building Materials": [("Cement 50kg", 640, 830, 400), ("River Sand (ton)", 1200, 1550, 120), ("Hollow Block 6in", 55, 78, 900), ("Iron Sheet 3m Gauge30", 780, 990, 260)],
    "Paints": [("Gloss Paint 4L", 1750, 2450, 180), ("Emulsion Paint 4L", 1400, 1980, 200), ("Paint Brush 4in", 95, 175, 350), ("Wood Varnish 1L", 380, 560, 150)],
    "Plumbing": [("PVC Pipe 20mm 3m", 210, 320, 300), ("PVC Tee 20mm", 45, 78, 500), ("Gate Valve 1in", 320, 480, 150), ("Water Tank 1000L", 8200, 10500, 25)],
    "Electrical": [("LED Bulb 12W", 150, 260, 600), ("Socket Outlet", 180, 290, 400), ("Electrical Cable 2.5mm (roll)", 3200, 4200, 60), ("Circuit Breaker 20A", 420, 620, 120)],
    "Agro Inputs": [("DAP Fertilizer 50kg", 3400, 4100, 150), ("CAN Fertilizer 50kg", 3100, 3750, 150), ("Maize Seed 2kg Pack", 480, 650, 220), ("Pesticide 1L", 620, 890, 180)],
    "Hardware Tools": [("Claw Hammer", 380, 590, 140), ("Wheelbarrow", 4200, 5600, 45), ("Spade", 520, 780, 160), ("Measuring Tape 5m", 210, 340, 200)],
}
PRICE_UPLIFT = 1.18   # ASSUMPTION: lifts the raw cost/price pairs to a ~30-35% gross margin
CATS = list(PRODUCTS)
MONTHS = pd.period_range("2025-01", "2026-06", freq="M")
PERIOD_END = MONTHS[-1].end_time.normalize()
SEASON = {1: .92, 2: .95, 3: 1.0, 4: 1.05, 5: .97, 6: .95, 7: .93, 8: .98, 9: 1.02, 10: 1.10, 11: 1.15, 12: 1.20}
EXPENSE_RANGES = {"Rent": (20000, 30000), "Staff Salaries": (34000, 52000), "Utilities": (3500, 8000), "Transport": (4500, 12000),
                  "Repairs": (1800, 9000), "Marketing": (1000, 6000), "Licenses": (1000, 5000)}

stock = {n: {"cat": c, "cost": cost, "price": round(price * PRICE_UPLIFT, 2), "stock": opening}
         for c, items in PRODUCTS.items() for n, cost, price, opening in items}
customers = [f"CUS-{1000 + i}" for i in range(220)]
ctype = {c: RNG.choice(CUST_TYPES, p=[.35, .15, .2, .2, .1]) for c in customers}
rows, seq = [], [0]


def add(date, ttype, doc, **kw):
    """Append a row with every schema column defaulted, then overridden by kw."""
    r = dict(transaction_id="", transaction_date=date, transaction_type=ttype, document_no=f"{doc}-{date.strftime('%y%m')}-{seq[0]:04d}",
             business_name=BUSINESS, branch=RNG.choice(BRANCHES), sales_channel=np.nan, customer_type=np.nan, customer_id=np.nan,
             supplier_name=np.nan, product_category=np.nan, product_name=np.nan, quantity=0, unit_price_kes=0.0, discount_pct=0.0,
             gross_sales_kes=0.0, net_sales_kes=0.0, unit_cost_kes=0.0, cogs_kes=0.0, gross_profit_kes=0.0, expense_category=np.nan,
             expense_amount_kes=0.0, cash_in_kes=0.0, cash_out_kes=0.0, amount_received_kes=0.0, accounts_receivable_change_kes=0.0,
             accounts_payable_change_kes=0.0, inventory_qty_change=0, inventory_value_change_kes=0.0, payment_method=np.nan,
             salesperson_or_staff=RNG.choice(STAFF), manual_entry_flag=0.0, _seq=seq[0])
    r.update(kw)
    seq[0] += 1
    rows.append(r)
    return r


def purchase(date, name, qty, supplier=None, expense_category="Purchase", pay_share=None):
    info = stock[name]
    unit = round(info["cost"] * RNG.uniform(.97, 1.05), 2) if supplier is None else info["cost"]
    total = round(unit * qty, 2)
    paid = round(total * (RNG.choice([1.0, .6, 0.0], p=[.5, .3, .2]) if pay_share is None else pay_share), 2)
    add(date, "PURCHASE", "GRN", sales_channel="Supplier", supplier_name=supplier or RNG.choice(SUPPLIERS), product_category=info["cat"],
        product_name=name, quantity=qty, unit_price_kes=unit, unit_cost_kes=unit, cogs_kes=total, expense_category=expense_category,
        cash_out_kes=paid, accounts_payable_change_kes=round(total - paid, 2), inventory_qty_change=qty, inventory_value_change_kes=total)
    info["stock"] += qty


# Step 0: opening stock as explicit PURCHASE rows
opening_date = MONTHS[0].start_time   # 1 Jan: same month as first sales (no revenue-less extra month)
for name, info in list(stock.items()):
    q = info["stock"]
    info["stock"] = 0
    purchase(opening_date, name, q, supplier="Opening Stock Balance", expense_category="Opening Stock", pay_share=1.0)


def rand_day(month):
    return month.start_time + pd.Timedelta(days=int(RNG.integers(0, month.days_in_month)))


# Step 1: sales in true chronological order, with just-in-time restocking
planned = []
for i, m in enumerate(MONTHS):
    scale = SEASON[m.month] * 1.018 ** (i + 1)
    planned += [(rand_day(m), m) for _ in range(max(20, int(58 * scale * RNG.uniform(.9, 1.1))))]
planned.sort(key=lambda x: x[0])
sale_rows = []
for date, m in planned:
    cat = RNG.choice(CATS, p=[.28, .18, .16, .14, .16, .08])
    name = PRODUCTS[cat][RNG.integers(0, len(PRODUCTS[cat]))][0]
    qty = int(RNG.integers(1, 25)) if cat == "Building Materials" else int(RNG.integers(1, 9))
    info = stock[name]
    if info["stock"] < qty + 15:
        purchase(date, name, int(RNG.integers(qty + 60, qty + 180)))
    price = round(info["price"] * RNG.uniform(.95, 1.08), 2)
    disc = round(float(RNG.choice([0, 0, 0, .01, .02, .03, .05], p=[.55, .1, .1, .1, .08, .05, .02])), 4)
    gross = round(price * qty, 2)
    net = round(gross * (1 - disc), 2)
    unit_cost = round(info["cost"] * RNG.uniform(.98, 1.03), 2)
    cogs = round(unit_cost * qty, 2)
    cid = RNG.choice(customers)
    credit = ctype[cid] in ("Wholesale", "Contractor") and RNG.random() < .35
    received = round(net * RNG.uniform(.2, .7), 2) if credit else net
    info["stock"] -= qty
    r = add(date, "SALE", "INV", sales_channel=RNG.choice(CHANNELS), customer_type=ctype[cid], customer_id=cid, product_category=cat,
            product_name=name, quantity=qty, unit_price_kes=price, discount_pct=disc, gross_sales_kes=gross, net_sales_kes=net,
            unit_cost_kes=unit_cost, cogs_kes=cogs, gross_profit_kes=round(net - cogs, 2), cash_in_kes=received, amount_received_kes=received,
            accounts_receivable_change_kes=round(net - received, 2), inventory_qty_change=-qty, inventory_value_change_kes=round(-cogs, 2))
    r["_credit"] = round(net - received, 2) if credit else 0.0
    sale_rows.append(r)

# Step 2: refunds (only ever add stock back)
for idx in RNG.choice(len(sale_rows), size=max(15, int(len(sale_rows) * .014)), replace=False):
    o = sale_rows[idx]
    d = o["transaction_date"] + pd.Timedelta(days=int(RNG.integers(1, 10)))
    if d > PERIOD_END:
        continue
    q = min(o["quantity"], int(RNG.integers(1, max(2, o["quantity"] // 2 + 1))))
    val, cost = round(q / o["quantity"] * o["net_sales_kes"], 2), round(q / o["quantity"] * o["cogs_kes"], 2)
    stock[o["product_name"]]["stock"] += q
    add(d, "REFUND", "REF", branch=o["branch"], sales_channel="Counter", customer_type=o["customer_type"], customer_id=o["customer_id"],
        product_category=o["product_category"], product_name=o["product_name"], quantity=-q, unit_price_kes=o["unit_price_kes"],
        unit_cost_kes=o["unit_cost_kes"], net_sales_kes=val, gross_profit_kes=-val, expense_category="Customer Refund", expense_amount_kes=val,
        cash_out_kes=val, inventory_qty_change=q, inventory_value_change_kes=cost, payment_method="refund", salesperson_or_staff=o["salesperson_or_staff"])

# Step 3: expenses, supplier payments, stock adjustments
n_by_month = pd.Series([m for _, m in planned]).value_counts()
for m in MONTHS:
    n = int(n_by_month.get(m, 20))
    for _ in range(max(4, int(n * .10))):
        cat = RNG.choice(list(EXPENSE_RANGES), p=[.22, .32, .12, .14, .1, .06, .04])
        amt = round(float(RNG.uniform(*EXPENSE_RANGES[cat])), 2)
        add(rand_day(m), "EXPENSE", "EXP", sales_channel="Back Office", expense_category=cat, expense_amount_kes=amt, cash_out_kes=amt,
            payment_method=RNG.choice(PAY, p=[.55, .3, .1, .05]))
    for _ in range(max(2, int(n * .05))):
        amt = round(float(RNG.uniform(8000, 60000)), 2)
        add(rand_day(m), "SUPPLIER_PAYMENT", "SP", sales_channel="Supplier", supplier_name=RNG.choice(SUPPLIERS), expense_category="Supplier Payment",
            cash_out_kes=amt, accounts_payable_change_kes=-amt, payment_method=RNG.choice(PAY, p=[.4, .45, .05, .1]))
    for _ in range(max(1, int(n * .015))):
        name = RNG.choice(list(stock))
        info = stock[name]
        room = min(5, info["stock"] - 20)
        if room <= 0:
            continue
        adj = -int(RNG.integers(1, room + 1)) if RNG.random() < .7 else int(RNG.integers(1, 6))
        info["stock"] += adj
        add(rand_day(m), "STOCK_ADJUSTMENT", "ADJ", sales_channel="Stock Count", product_category=info["cat"], product_name=name, quantity=adj,
            expense_category="Stock Adjustment", inventory_qty_change=adj, inventory_value_change_kes=round(adj * info["cost"], 2),
            payment_method="Manual count variance")

# Step 4: customer payments sized from ACTUAL credit exposure (~86% collected)
for s in sale_rows:
    if s["_credit"] <= 0 or RNG.random() > .86:
        continue
    d = s["transaction_date"] + pd.Timedelta(days=int(RNG.integers(3, 45)))
    if d > PERIOD_END:
        continue
    amt = round(s["_credit"] * RNG.uniform(.7, 1.0), 2)
    add(d, "CUSTOMER_PAYMENT", "RCPT", branch=s["branch"], sales_channel="Collections", customer_type=ctype[s["customer_id"]], customer_id=s["customer_id"],
        expense_category="Customer Collection", cash_in_kes=amt, amount_received_kes=amt, accounts_receivable_change_kes=amt,
        payment_method=RNG.choice(PAY[:2], p=[.75, .25]))

df = pd.DataFrame(rows).sort_values(["transaction_date", "_seq"], kind="stable").reset_index(drop=True)
df["transaction_id"] = [f"TXN-{i + 1:05d}" for i in range(len(df))]
df = df.drop(columns=["_seq", "_credit"])

# deliberate, mild data-quality issues (applied AFTER ordering so inventory integrity is untouched)
dupes = df.sample(max(5, int(len(df) * .008)), random_state=7)
df = pd.concat([df, dupes], ignore_index=True)                              # duplicate transaction IDs
for col, frac, seed in [("branch", .01, 1), ("sales_channel", .008, 2), ("customer_type", .01, 3)]:
    df.loc[df.sample(frac=frac, random_state=seed).index, col] = np.nan     # missing categorical fields
dates = df["transaction_date"].dt.strftime("%Y-%m-%d").astype(object)
for frac, seed, fmt in [(.02, 101, "%d/%m/%Y"), (.01, 102, "%d-%m-%Y")]:   # mixed date formats
    for i in df.sample(frac=frac, random_state=seed).index:
        dates.loc[i] = df.loc[i, "transaction_date"].strftime(fmt)
df["transaction_date"] = dates
sales = df[(df["transaction_type"] == "SALE") & (df["net_sales_kes"] > 0)]
df.loc[sales.sample(max(4, int(len(df) * .003)), random_state=11).index, "quantity"] = 0   # invalid quantities
mp = df[df["payment_method"] == "M-PESA"]
for i in mp.sample(min(20, len(mp)), random_state=13).index:
    df.loc[i, "payment_method"] = RNG.choice(["Mpesa", "M-pesa", "MPESA "])              # payment-label variants
fin = df[df["transaction_type"] == "SALE"].sample(6, random_state=17).index
df.loc[fin, "net_sales_kes"] = (df.loc[fin, "net_sales_kes"] * 1.15).round(2)          # financial inconsistencies

COLUMNS = ["transaction_id", "transaction_date", "transaction_type", "document_no", "business_name", "branch", "sales_channel", "customer_type",
           "customer_id", "supplier_name", "product_category", "product_name", "quantity", "unit_price_kes", "discount_pct", "gross_sales_kes",
           "net_sales_kes", "unit_cost_kes", "cogs_kes", "gross_profit_kes", "expense_category", "expense_amount_kes", "cash_in_kes", "cash_out_kes",
           "amount_received_kes", "accounts_receivable_change_kes", "accounts_payable_change_kes", "inventory_qty_change",
           "inventory_value_change_kes", "payment_method", "salesperson_or_staff", "manual_entry_flag"]
out = sys.argv[1] if len(sys.argv) > 1 else "data/sample/thika_road_hardware_agrovet_synthetic_dataset.csv"
df[COLUMNS].to_csv(out, index=False)
print(f"Saved {out}: {len(df)} rows")
print(df["transaction_type"].value_counts().to_string())
