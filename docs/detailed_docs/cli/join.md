# CLI Feature Guide: Relational Joins & Stacking (`-join` & `-concat`)

Join multiple datasets or append rows across tables directly from the command line using positional file inputs, `-join`, `-concat`, and `-opts`, powered natively by Polars' multithreaded SIMD execution engine.

---

## Contents

- [Overview & Rules](#overview--rules)
- [Positional File Declaration (`alias=source`)](#positional-file-declaration-aliassource)
- [Relational Joins (`-join`)](#relational-joins--join)
  - [Join Strategies (`how=`)](#join-strategies-how)
  - [Differing Key Names](#differing-key-names)
  - [Multi-Column Join Keys](#multi-column-join-keys)
  - [Cardinality Validation](#cardinality-validation)
  - [Chaining Multiple Joins with `data`](#chaining-multiple-joins-with-data)
- [Row-Wise Stacking (`-concat`)](#row-wise-stacking--concat)
- [Reader Options (`-opts`)](#reader-options--opts)
- [Downstream Verbs After Joins](#downstream-verbs-after-joins)

---

## Overview & Rules

Multi-table operations declare positional datasets using the natural `alias=source` convention:
- Inputs are passed positionally: `o=orders.parquet c=customers.csv`.
- Pipelines begin with `-join`, `-concat`, or `-sql`.
- When `left=` and `right=` are omitted from `-join`, they default to the first two input tables.
- When `frames=` is omitted from `-concat`, all input tables are stacked in order.
- Subsequent flags (`-filter`, `-mutate`, `-select`, `-by`, `-agg`, `-o`) operate directly on the combined result.

```bash
pytae o=orders.parquet c=customers.csv \
  -join "on=customer_id, how=left" \
  -head 5
```

---

## Positional File Declaration (`alias=source`)

Declare inputs using `alias=source` directly as command-line arguments:

```bash
# Two files (left=o, right=c inferred automatically)
pytae o=orders.parquet c=customers.csv -join "on=customer_id"

# Three files (different formats supported)
pytae s=sales.parquet st=stores.csv t=targets.jsonl ...
```

---

## Relational Joins (`-join`)

Syntax:
```bash
-join "on=KEYS, how=STRATEGY"
# Or explicitly:
-join "left=LEFT_ALIAS, right=RIGHT_ALIAS, on=KEYS, how=STRATEGY"
```

### Join Strategies (`how=`)

| Strategy | Flag Syntax | Description |
|---|---|---|
| **Inner Join** *(default)* | `how=inner` | Keeps rows where keys match in both datasets |
| **Left Join** | `how=left` | Preserves all left rows; fills unmatched right cells with `null` |
| **Right Join** | `how=right` | Preserves all right rows; fills unmatched left cells with `null` |
| **Full Outer Join** | `how=full` or `how=outer` | Keeps all rows from both datasets |
| **Semi Join** | `how=semi` | Filters left rows that have a match in right (right columns excluded) |
| **Anti Join** | `how=anti` | Keeps left rows with **no** match in right (orphan/discrepancy detection) |
| **Cross Join** | `how=cross` | Full Cartesian product ($N \times M$ rows, omit `on=`) |

```bash
# Left outer join
pytae o=orders.parquet c=customers.csv \
  -join "on=customer_id, how=left" \
  -head 10

# Anti join: find customers who have NEVER placed an order
pytae c=customers.csv o=orders.parquet \
  -join "on=customer_id, how=anti" \
  -cols id,name,signup_date
```

---

### Differing Key Names

When join keys have different names across datasets, use the colon syntax `on="left_key:right_key"`:

```bash
# Join orders.client_id with customers.id
pytae o=orders.parquet c=customers.csv \
  -join "on=client_id:id, how=inner" \
  -head 5
```

---

### Multi-Column Join Keys

Separate composite keys with commas or plus signs:

```bash
pytae s=sales.parquet i=inventory.parquet \
  -join "on=store_id:store_id, sku:sku, how=left" \
  -head 5
```

---

### Cardinality Validation

Catch accidental row multiplication or duplicate keys before they corrupt aggregations using `validate=`:
- `validate=1:1`: Checks that keys are unique in both left and right datasets.
- `validate=1:m`: Checks that keys are unique in the left dataset.
- `validate=m:1`: Checks that keys are unique in the right dataset.
- `validate=m:m`: Default, allows many-to-many matches.

```bash
pytae o=orders.parquet u=users.csv \
  -join "on=user_id:id, how=inner, validate=m:1" \
  -head 5
```
*(If `users.csv` contains duplicate IDs, `pytae` immediately aborts with a descriptive error).*

---

### Chaining Multiple Joins with `data`

Chain 3 or more datasets by referencing the running pipeline result `data`:

```bash
pytae o=orders.parquet c=customers.csv p=products.parquet \
  -join "left=o, right=c, on=customer_id, how=left" \
  -join "left=data, right=p, on=product_id, how=left" \
  -select order_id, customer_name, product_name, price, quantity \
  -head 10
```

---

## Row-Wise Stacking (`-concat`)

Stack multiple files or sheets sharing identical schemas into a single view:

```bash
# Concat all positional inputs in order
pytae q1=q1.parquet q2=q2.parquet q3=q3.parquet q4=q4.parquet \
  -concat \
  -by quarter \
  -agg "total_revenue = amount:sum, order_count = count" \
  -o annual_summary.csv

# Stack multiple Excel sheets via targeted -opts
pytae jan=sales.xlsx feb=sales.xlsx -concat -opts "jan:sheet=Jan, feb:sheet=Feb" -shape
```

---

## Reader Options (`-opts`)

Fine-tune ingestion options for one or all inputs:

```bash
# Pass global or targeted options (select Excel sheets, skip rows, specify headers)
pytae ord=orders.xlsx cust=customers.csv \
  -join "on=cust_id" \
  -opts "ord:sheet=Q1, skiprows=1, cust:skiprows=3"
```

---

## Downstream Verbs After Joins

Once joined or stacked, all standard `pytae` verbs apply seamlessly:

```bash
pytae o=orders.parquet c=customers.csv \
  -join "on=customer_id, how=inner" \
  -filter "region == 'West' and amount > 100" \
  -mutate "tax = amount * 0.0825, total = amount + tax" \
  -by customer_name \
  -agg "spent = total:sum, orders = count" \
  -arrange "spent desc" \
  -head 10 \
  -o top_west_customers.parquet
```
