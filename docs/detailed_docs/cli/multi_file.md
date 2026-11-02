# CLI Feature Guide: Multi-File Relational Pipelines

[← Back to Master Reference](../../pytae.md)

Load, join, stack, and query multiple disparate datasets in a unified pipeline using natural positional file declarations, `-join`, `-concat`, `-opts`, and cross-file `-sql`.

---

## Contents

- [Overview & Architecture](#overview--architecture)
- [Positional File Declaration](#positional-file-declaration)
  - [Syntax & Alias Direction (`alias=source`)](#syntax--alias-direction-aliassource)
  - [Reader Options & Excel Sheet Selection (`-opts`)](#reader-options--excel-sheet-selection--opts)
- [Joining Datasets (`-join`)](#joining-datasets--join)
  - [Shared Join Keys](#shared-join-keys)
  - [Different Join Keys (`left:right`)](#different-join-keys-leftright)
  - [Join Types (`how=inner|left|right|outer|cross`)](#join-types-howinnerleftrightoutercross)
  - [Validating Joins (`validate=one_to_one`)](#validating-joins-validateone_to_one)
  - [Folding Multiple Files with `data`](#folding-multiple-files-with-data)
- [Row-Wise Stacking (`-concat`)](#row-wise-stacking--concat)
- [Cross-File SQL Queries (`-sql`)](#cross-file-sql-queries--sql)
- [Exporting Joined Results](#exporting-joined-results)

---

## Overview & Architecture

Pytae supports multi-file relational operations directly from the command line without intermediate script files or complex flags:
- Pass multiple positional paths or named table assignments (`alias=path`).
- Trigger relational execution with `-join`, `-concat`, or multi-table `-sql`.
- Subsequent pipeline steps (`-filter`, `-select`, `-mutate`, `-agg`, `-o`) operate directly on the merged result.

---

## Positional File Declaration

### Syntax & Alias Direction (`alias=source`)

Tables are assigned using the natural `alias=source` convention (`df=filename`), perfectly consistent with the REPL (`df = file.parquet`):

```bash
# Assign aliases to positional inputs
pytae emp=emp.parquet dept=dept.csv -join "on=dept_id"
```

If aliases are omitted, pytae automatically assigns default table names (`df1`, `df2`, `df3`, etc.):

```bash
# Bare paths automatically aliased as df1 and df2
pytae orders.parquet customers.csv -join "on=customer_id"
```

### Reader Options & Excel Sheet Selection (`-opts`)

Pass reader parameters globally across all inputs or target specific tables by alias prefix:

```bash
# Global reader options (applied to all inputs)
pytae jan.csv feb.csv -concat -opts "skiprows=2"

# Select Excel sheets strictly via -opts (colon sheet syntax is not supported)
pytae sales.xlsx -opts "sheet=Feb" -head

# Targeted reader options (e.g. ord selects sheet Q1, cust skips 3 rows)
pytae ord=orders.xlsx cust=customers.csv \
  -join "on=cust_id" \
  -opts "ord:sheet=Q1, skiprows=1, cust:skiprows=3"
```

---

## Joining Datasets (`-join`)

Merges two frames (or folds in the running pipeline result `data`):

| Parameter | Required? | Meaning |
|---|---|---|
| `left=`, `right=` | No | Table alias (defaults to first two input tables), or `data` for the running pipeline view |
| `on=` | **Yes** | Shared key column(s), or `left_col:right_col` mapping |
| `how=` | No (default: `inner`) | `inner`, `left`, `right`, `outer`, `cross` |
| `validate=` | No | Join integrity: `one_to_one`, `one_to_many`, `many_to_one`, `many_to_many` |

### Shared Join Keys

When column names match across datasets, specify `on=col`:

```bash
pytae emp=emp.parquet dept=dept.csv \
  -join "on=id" \
  -head 3
```

**Output:**

|   id | name    | dept        |   salary |
|-----:|:--------|:------------|---------:|
|    1 | Alice   | Engineering |    95000 |
|    2 | Bob     | Marketing   |    75000 |
|    3 | Charlie | Sales       |    82000 |

### Different Join Keys (`left:right`)

When key column names differ between datasets, map them using `:`:

```bash
pytae c=customers.parquet o=orders.csv \
  -join "on='customer_id:cust_id',how=left" \
  -head 5
```

### Join Types (`how=inner|left|right|outer|cross`)

```bash
# Left outer join
pytae a=a.csv b=b.csv -join "on=id,how=left"
```

**Output:**

| id | val_a | val_b |
|---:|:---|---:|
| 1 | x | 10.0 |
| 2 | y | 20.0 |
| 3 | z | NaN |

### Validating Joins (`validate=one_to_one`)

Protect data integrity by failing immediately if relationships violate cardinality expectations:

```bash
pytae a=a.csv b=b.csv -join "on=id,validate=one_to_one"
```

### Folding Multiple Files with `data`

Chain multiple `-join` flags in sequence. After the first join, use `data` to refer to the running pipeline result:

```bash
pytae u=users.csv o=orders.csv p=payments.parquet \
  -join "left=u,right=o,on=user_id" \
  -join "left=data,right=p,on=order_id" \
  -head 5
```

---

## Row-Wise Stacking (`-concat`)

Concatenates multiple datasets with matching structures into one unified table (equivalent to Polars `pl.concat`):

```bash
# Stack three monthly batches (frames default to all inputs in order)
pytae m1=jan.parquet m2=feb.parquet m3=mar.parquet -concat -shape

# Stack multiple Excel sheets via targeted -opts
pytae jan=2024.xlsx feb=2024.xlsx mar=2024.xlsx -concat \
  -opts "jan:sheet=Jan, feb:sheet=Feb, mar:sheet=Mar, skiprows=2" -shape
```

---

## Cross-File SQL Queries (`-sql`)

Execute ANSI SQL across multiple positional inputs. Every table alias is registered directly as an in-memory Polars SQL table:

```bash
pytae c=customers.csv o=orders.parquet \
  -sql "
    select
      c.name,
      count(o.order_id) as total_orders,
      coalesce(sum(o.amount), 0) as total_spent
    from c
    left join o on c.customer_id = o.customer_id
    group by c.name
    order by total_spent desc
  "
```

**Output:**

| name | total_orders | total_spent |
|:---|---:|---:|
| Alice | 2 | 400.0 |
| Bob | 1 | 300.0 |
| Charlie | 0 | 0.0 |

---

## Exporting Joined Results

Exporting from a multi-file relational pipeline requires an explicit destination path via `-o`:

```bash
pytae a=a.parquet b=b.csv \
  -join "on=id" \
  -o joined_output.parquet
```

> [!NOTE]
> - Exporting from a multi-file pipeline requires an explicit target file name (e.g. `-o out.parquet`). In-place format conversion (`-o csv`) cannot infer an output name without a single positional source file.
> - Glob-pattern batch conversion (`pytae 'data/*.parquet' -o csv`) is a separate single-file batch operation.
