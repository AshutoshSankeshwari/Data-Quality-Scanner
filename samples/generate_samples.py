"""
samples/generate_samples.py
Generates the standard V2 sample datasets for Data Quality Scanner testing and demonstrations:
  1. customers_clean_100pct.csv (200 records, 7 columns, 100% clean under V2 rules)
  2. customers_faulty.csv (200 records, reproducible quality issues across all checks)
  3. orders_related_to_customers.csv (150 records, relates to clean customers with 20 orphan records)
  4. products_normal.csv (100 records, independent product catalog)
"""
from pathlib import Path
import pandas as pd

samples_dir = Path(__file__).parent.resolve()

# ---------------------------------------------------------------------------
# 1. Clean Customers Dataset (200 rows, 100% clean under config.yaml)
# ---------------------------------------------------------------------------
clean_rows = []
countries = ["USA", "UK", "Canada", "Germany", "France", "Australia", "India", "Japan"]
domains = ["example.com", "corp.net", "business.org", "enterprise.io"]

for i in range(1, 201):
    # Customer_ID uses alphanumeric CUST0001..CUST0200 to strictly comply with alpha_numeric_only
    cid = f"CUST{i:04d}"
    name = f"Customer {i}"
    domain = domains[(i - 1) % len(domains)]
    email = f"user{i}@{domain}"
    phone = f"+1-555-{1000 + i}"
    country = countries[(i - 1) % len(countries)]
    created_date = f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
    credit_limit = float((i % 10 + 1) * 1000)

    clean_rows.append({
        "Customer_ID": cid,
        "Customer_Name": name,
        "Email": email,
        "Phone": phone,
        "Country": country,
        "Created_Date": created_date,
        "Credit_Limit": credit_limit,
    })

df_clean = pd.DataFrame(clean_rows)
df_clean.to_csv(samples_dir / "customers_clean_100pct.csv", index=False)

# ---------------------------------------------------------------------------
# 2. Faulty Customers Dataset (200 rows with intentional, reproducible issues)
# ---------------------------------------------------------------------------
faulty_rows = []
for i in range(1, 171):
    cid = f"CUST{i:04d}"
    name = f"Customer {i}"
    email = f"user{i}@example.com"
    phone = f"+1-555-{1000 + i}"
    country = countries[(i - 1) % len(countries)]
    created_date = f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}"
    credit_limit = float((i % 10 + 1) * 1000)

    # Injected intentional issues:
    if 5 <= i <= 9:
        # Whitespace: leading space
        name = f" Customer {i}"
    elif 10 <= i <= 14:
        # Whitespace: trailing space
        name = f"Customer {i} "
    elif 15 <= i <= 19:
        # Whitespace: multiple internal spaces
        name = f"Customer   {i}"
    elif 20 <= i <= 24:
        # Mandatory field / null: Customer_Name is None
        name = None
    elif 25 <= i <= 28:
        # Mandatory field / null: Empty string Email
        email = ""
    elif 30 <= i <= 33:
        # Whitespace-only string
        phone = "   "
    elif i == 35:
        # Special character anomaly: $ in Customer_ID
        cid = "CUST$0035"
    elif i == 36:
        # Special character anomaly: @ in Customer_ID
        cid = "CUST@0036"
    elif i == 37:
        # Special character anomaly: # in Customer_ID
        cid = "CUST#0037"
    elif 45 <= i <= 49:
        # Pattern inconsistency in Customer_ID (minority cluster)
        cid = f"cust_{i:04d}"
    elif 70 <= i <= 72:
        # Invalid date format
        created_date = "bad-date-value"
    elif 73 <= i <= 75:
        # Impossible calendar date (Feb 30)
        created_date = "2025-02-30"
    elif 80 <= i <= 84:
        # Missing Country
        country = None
    elif 85 <= i <= 88:
        # Whitespace in phone
        phone = f" +1-555-{1000 + i}"
    elif i == 90:
        # Anomaly character in email
        email = "invalid#email@example.com"
    elif i == 95:
        # Anomaly character in email
        email = "bad%user@example.com"

    faulty_rows.append({
        "Customer_ID": cid,
        "Customer_Name": name,
        "Email": email,
        "Phone": phone,
        "Country": country,
        "Created_Date": created_date,
        "Credit_Limit": credit_limit,
    })

# Add 30 duplicate rows (rows 171-200 duplicate rows 1-30)
for j in range(30):
    dup_row = dict(faulty_rows[j])
    faulty_rows.append(dup_row)

df_faulty = pd.DataFrame(faulty_rows)
df_faulty.to_csv(samples_dir / "customers_faulty.csv", index=False)

# ---------------------------------------------------------------------------
# 3. Orders Dataset Related to Customers (150 rows: 130 valid + 20 orphans)
# ---------------------------------------------------------------------------
order_rows = []
for i in range(1, 151):
    order_id = f"ORD{i:05d}"
    if i <= 130:
        # References valid customers from clean dataset with repetition (foreign key pattern)
        cust_num = ((i * 7) % 100) + 1
        cid = f"CUST{cust_num:04d}"
    else:
        # 20 intentional orphan references (CUST9001..CUST9020)
        cid = f"CUST{8870 + i:04d}"

    order_date = f"2025-{(i % 6) + 1:02d}-{(i % 28) + 1:02d}"
    prod_id = f"PROD{((i % 20) + 1):04d}"
    qty = (i % 5) + 1
    price = round(15.50 * ((i % 10) + 1), 2)

    order_rows.append({
        "Order_ID": order_id,
        "Customer_ID": cid,
        "Order_Date": order_date,
        "Product_ID": prod_id,
        "Quantity": qty,
        "Unit_Price": price,
    })

df_orders = pd.DataFrame(order_rows)
df_orders.to_csv(samples_dir / "orders_related_to_customers.csv", index=False)

# ---------------------------------------------------------------------------
# 4. Products Dataset (100 rows, normal independent catalog)
# ---------------------------------------------------------------------------
categories = ["Electronics", "Office Supplies", "Hardware", "Furniture", "Software"]
product_rows = []
for i in range(1, 101):
    prod_id = f"PROD{i:04d}"
    cat = categories[(i - 1) % len(categories)]
    p_name = f"Product {cat[:3].upper()}-{i}"
    price = round(9.99 + (i * 3.75), 2)
    stock = (i * 13) % 250 + 10
    supplier_id = f"SUPP{(i % 10) + 1:03d}"

    product_rows.append({
        "Product_ID": prod_id,
        "Product_Name": p_name,
        "Category": cat,
        "Price": price,
        "Stock_Quantity": stock,
        "Supplier_ID": supplier_id,
    })

df_products = pd.DataFrame(product_rows)
df_products.to_csv(samples_dir / "products_normal.csv", index=False)

print("Generated sample datasets successfully:")
print(" - customers_clean_100pct.csv (", len(df_clean), "rows)")
print(" - customers_faulty.csv (", len(df_faulty), "rows)")
print(" - orders_related_to_customers.csv (", len(df_orders), "rows)")
print(" - products_normal.csv (", len(df_products), "rows)")
