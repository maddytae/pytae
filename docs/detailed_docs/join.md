# Relational Joins & Stacking (`join` & `concat`)

`pytae` provides high-performance relational joins and dataset concatenation powered natively by Polars' SIMD vector core. It supports all standard join strategies (`inner`, `left`, `right`, `full`, `semi`, `anti`, `cross`), colon key mapping (`on="left_key:right_key"`), join cardinality validation (`1:1`, `1:m`, `m:1`), and lazy execution graph preservation across both the Python library and CLI.

---

## Rosetta Stone: Python vs. CLI

| Capability | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Inner Join** | `df1.join(df2, on="id")` | `pytae -file "a.parquet=a; b.csv=b" -join "left=a, right=b, on=id"` |
| **Left Join** | `df1.join(df2, on="id", how="left")` | `-join "left=a, right=b, on=id, how=left"` |
| **Right Join** | `df1.join(df2, on="id", how="right")` | `-join "left=a, right=b, on=id, how=right"` |
| **Full Outer Join** | `df1.join(df2, on="id", how="full")` | `-join "left=a, right=b, on=id, how=full"` |
| **Semi Join** | `df1.join(df2, on="id", how="semi")` | `-join "left=a, right=b, on=id, how=semi"` |
| **Anti Join** | `df1.join(df2, on="id", how="anti")` | `-join "left=a, right=b, on=id, how=anti"` |
| **Cross Join** | `df1.join(df2, how="cross")` | `-join "left=a, right=b, how=cross"` |
| **Differing Key Names** | `df1.join(df2, on="cust_id:id")`<br>or `left_on="cust_id", right_on="id"` | `-join "left=a, right=b, on=cust_id:id"` |
| **Join Validation** | `df1.join(df2, on="id", validate="1:1")` | `-join "left=a, right=b, on=id, validate=1:1"` |
| **Row Stacking (Concat)**| `pt.concat([df1, df2])`<br>or `df1.concat(df2)` | `pytae -file "a.parquet=a; b.parquet=b" -concat "a, b"` |

---

## Supported Join Strategies (`how=`)

| Strategy | Behavior | Notes |
|:---|:---|:---|
| `inner` *(default)* | Keeps rows where keys match in both datasets | Discards unmatched rows from both sides |
| `left` | Keeps all rows from the left dataset; matches from the right | Missing right columns filled with null |
| `right` | Keeps all rows from the right dataset; matches from the left | Missing left columns filled with null |
| `full` / `outer` | Keeps all rows from both datasets | Unmatched cells filled with null |
| `semi` | Filters left rows that have a match in the right | Right columns are **not** appended |
| `anti` | Filters left rows that have **no** match in the right | Useful for orphan / discrepancy detection |
| `cross` | Computes Cartesian product ($N \times M$ rows) | Omit `on=` parameter |

---

## Python Library Usage

### 1. Basic Joining (`df.join()` or `pt.join()`)

```python
import pytae as pt

orders = pt.read_parquet("orders.parquet")
customers = pt.read_csv("customers.csv")

# Symmetrical left join
merged = orders.join(customers, on="customer_id", how="left")

# Functional equivalent
merged = pt.join(orders, customers, on="customer_id", how="left")
```

### 2. Differing Key Names (Colon Syntax)
Instead of typing separate `left_on` and `right_on` arguments, Pytae provides an ergonomic colon shorthand: `on="left_key:right_key"`:

```python
# Join orders.client_id with customers.id
merged = orders.join(customers, on="client_id:id", how="inner")

# Explicit parameter syntax is also supported:
merged = orders.join(customers, left_on="client_id", right_on="id", how="inner")
```

### 3. Multiple Join Keys
Pass a list of keys or a comma-separated string:

```python
# Shared keys
df.join(other, on=["year", "region"])
df.join(other, on="year, region")

# Differing keys with colon notation
df.join(other, on="year:yr, region:reg_code")
```

### 4. Join Integrity Validation (`validate=`)
Guarantees relational cardinality and catches accidental cartesian products before they silently corrupt downstream aggregations:

```python
# Enforce one-to-one relationship (raises ValueError if duplicate keys exist)
df.join(other, on="user_id", validate="1:1")

# Enforce one-to-many or many-to-one
df.join(other, on="dept_id", validate="m:1")
```
Supported validation strings: `"1:1"` (`"one_to_one"`), `"1:m"` (`"one_to_many"`), `"m:1"` (`"many_to_one"`), `"m:m"` (`"many_to_many"`).

### 5. Suffix Collision Handling
When both tables contain identically named non-key columns:

```python
# Default suffix is '_right'
merged = df.join(other, on="id", suffix="_target")
```

### 6. Lazy Join Optimization
When joining two lazy datasets created via `pt.scan_parquet()` or `pt.scan_csv()`, Pytae preserves the lazy execution graph. Polars optimizes join predicate pushdowns across both files before reading rows from disk:

```python
lazy_orders = pt.scan_parquet("orders_100M.parquet")
lazy_custs = pt.scan_csv("customers.csv")

# Filter pushes through the join graph into the raw Parquet read!
result = lazy_orders.join(lazy_custs, on="customer_id", how="inner").filter("region == 'EMEA'").collect()
```

---

## Dataset Stacking (`concat`)

Append rows across datasets sharing common schemas using `pt.concat()` or `df.concat()`:

```python
import pytae as pt

sales_2023 = pt.read_parquet("sales_2023.parquet")
sales_2024 = pt.read_parquet("sales_2024.parquet")

# Stack rows
all_sales = pt.concat([sales_2023, sales_2024])

# Or chain directly
all_sales = sales_2023.concat(sales_2024)
```

---

## CLI Multi-File Joining (`-file`, `-join`, `-concat`)

In the command-line interface, multi-file operations use the `-file` flag:

```bash
# Semicolon-separated file mappings: PATH=ALIAS
pytae -file "orders.parquet=o; customers.csv=c" \
  -join "left=o, right=c, on=customer_id, how=left" \
  -filter "status == 'completed'" \
  -head 5
```

### Differing Keys & Validation in CLI
```bash
pytae -file "orders.parquet=o; users.csv=u" \
  -join "left=o, right=u, on=user_id:id, how=inner, validate=m:1" \
  -by u.department \
  -agg "total = o.amount:sum"
```

### Multi-Table Chaining with `data`
Chain multiple joins by referencing the running pipeline result `data`:
```bash
pytae -file "orders.parquet=o; customers.csv=c; products.parquet=p" \
  -join "left=o, right=c, on=customer_id, how=left" \
  -join "left=data, right=p, on=product_id, how=left" \
  -head 10
```

### CLI Row-Wise Stacking (`-concat`)
```bash
pytae -file "q1.csv=q1; q2.csv=q2; q3.csv=q3" \
  -concat "q1, q2, q3" \
  -by quarter \
  -agg "revenue = amount:sum"
```

