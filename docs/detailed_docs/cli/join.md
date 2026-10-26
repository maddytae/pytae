# CLI Feature Guide: Relational Joins & Stacking (`-join` & `-concat`)

Join multiple datasets or append rows across tables directly from the command line using `-file`, `-join`, and `-concat`, powered natively by Polars' multithreaded SIMD execution engine.

---

## Contents

- [Overview & Rules](#overview--rules)
- [Multi-File Declaration (`-file`)](#multi-file-declaration--file)
- [Relational Joins (`-join`)](#relational-joins--join)
  - [Join Strategies (`how=`)](#join-strategies-how)
  - [Differing Key Names](#differing-key-names)
  - [Multi-Column Join Keys](#multi-column-join-keys)
  - [Cardinality Validation](#cardinality-validation)
  - [Chaining Multiple Joins with `data`](#chaining-multiple-joins-with-data)
- [Row-Wise Stacking (`-concat`)](#row-wise-stacking--concat)
- [Downstream Verbs After Joins](#downstream-verbs-after-joins)

---

## Overview & Rules

While standard `pytae` commands process a single positional dataset, multi-table operations use `-file` to declare named input aliases:
- Aliases are semicolon-separated: `PATH=ALIAS; PATH=ALIAS`.
- Pipelines begin with `-join`, `-concat`, or `-sql`.
- Subsequent flags (`-filter`, `-mutate`, `-select`, `-by`, `-agg`, `-o`) operate on the combined result.

```bash
pytae -file "orders.parquet=o; customers.csv=c" \
  -join "left=o, right=c, on=customer_id, how=left" \
  -head 5
```

---

## Multi-File Declaration (`-file`)

Declare inputs using `PATH=ALIAS` separated by semicolons `;`:

```bash
# Two files
pytae -file "orders.parquet=o; customers.csv=c" ...

# Three files (different formats supported)
pytae -file "sales.parquet=s; stores.csv=st; targets.jsonl=t" ...
```

---

## Relational Joins (`-join`)

Syntax:
```bash
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
pytae -file "orders.parquet=o; customers.csv=c" \
  -join "left=o, right=c, on=customer_id, how=left" \
  -head 10

# Anti join: find customers who have NEVER placed an order
pytae -file "customers.csv=c; orders.parquet=o" \
  -join "left=c, right=o, on=customer_id, how=anti" \
  -cols id,name,signup_date
```

---

### Differing Key Names

When join keys have different names across datasets, use the colon syntax `on="left_key:right_key"`:

```bash
# Join orders.client_id with customers.id
pytae -file "orders.parquet=o; customers.csv=c" \
  -join "left=o, right=c, on=client_id:id, how=inner" \
  -head 5
```

---

### Multi-Column Join Keys

Separate composite keys with commas or plus signs:

```bash
pytae -file "sales.parquet=s; inventory.parquet=i" \
  -join "left=s, right=i, on=store_id:store_id, sku:sku, how=left" \
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
pytae -file "orders.parquet=o; users.csv=u" \
  -join "left=o, right=u, on=user_id:id, how=inner, validate=m:1" \
  -head 5
```
*(If `users.csv` contains duplicate IDs, `pytae` immediately aborts with a descriptive error).*

---

### Chaining Multiple Joins with `data`

Chain 3 or more datasets by referencing the running pipeline result `data`:

```bash
pytae -file "orders.parquet=o; customers.csv=c; products.parquet=p" \
  -join "left=o, right=c, on=customer_id, how=left" \
  -join "left=data, right=p, on=product_id, how=left" \
  -select order_id, customer_name, product_name, price, quantity \
  -head 10
```

---

## Row-Wise Stacking (`-concat`)

Stack multiple files sharing identical schemas into a single view:

```bash
pytae -file "q1.parquet=q1; q2.parquet=q2; q3.parquet=q3; q4.parquet=q4" \
  -concat "q1, q2, q3, q4" \
  -by quarter \
  -agg "total_revenue = amount:sum, order_count = count" \
  -o annual_summary.csv
```

---

## Downstream Verbs After Joins

Once joined or stacked, all standard `pytae` verbs apply seamlessly:

```bash
pytae -file "orders.parquet=o; customers.csv=c" \
  -join "left=o, right=c, on=customer_id, how=inner" \
  -filter "region == 'West' and amount > 100" \
  -mutate "tax = amount * 0.0825, total = amount + tax" \
  -by customer_name \
  -agg "spent = total:sum, orders = count" \
  -arrange "spent desc" \
  -head 10 \
  -o top_west_customers.parquet
```

