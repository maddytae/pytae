# CLI Feature Guide: Multi-File Pipelines

Load, join, stack, and query multiple disparate datasets in a unified pipeline using `-file`, `-merge`, `-concat`, and cross-file `-sql`.

---

## Contents

- [Overview & Architecture](#overview--architecture)
- [Loading Named Inputs (`-file`)](#loading-named-inputs--file)
- [Joining Datasets (`-merge`)](#joining-datasets--merge)
  - [Shared Join Keys](#shared-join-keys)
  - [Different Join Keys (`left:right`)](#different-join-keys-leftright)
  - [Join Types (`how=inner|left|right|outer`)](#join-types-howinnerleftrightouter)
  - [Validating Joins (`validate=one_to_one`)](#validating-joins-validateone_to_one)
  - [Folding Multiple Files with `data`](#folding-multiple-files-with-data)
- [Row-Wise Stacking (`-concat`)](#row-wise-stacking--concat)
- [Cross-File SQL Queries (`-sql`)](#cross-file-sql-queries--sql)
- [Exporting Merged Results](#exporting-merged-results)

---

## Overview & Architecture

While standard `pytae` operations process a single positional file path, `-file` switches the CLI into multi-file mode:
- `-file` replaces the positional path entirely.
- The pipeline must begin with either `-merge`, `-concat`, or `-sql`.
- Subsequent steps (`-qry`, `-select`, `-mutate`, `-agg_df`, `-o`) operate on the combined result.

---

## Loading Named Inputs (`-file`)

Declare two or more input files separated by semicolons `;`. Each entry maps a file path to an alias (`PATH=ALIAS`) and can include format overrides (like `-dlim` or `-encoding`):

```bash
pytae -file "emp.parquet=emp; dept.csv=dept,dlim=',' ; sales.txt=sales,dlim='|'" ...
```

---

## Joining Datasets (`-merge`)

Merges two frames (or folds in the running pipeline result `data`):

| Parameter | Required? | Meaning |
|---|---|---|
| `left=`, `right=` | **Yes** | A `-file` alias, or the keyword `data` for the running pipeline view |
| `on=` | **Yes** | Shared key column(s), or `left_col:right_col` mapping |
| `how=` | No (default: `inner`) | `inner`, `left`, `right`, `outer`, `cross` |
| `validate=` | No | Join integrity: `one_to_one`, `one_to_many`, `many_to_one`, `many_to_many` |

### Shared Join Keys

```bash
pytae -file "emp.parquet=emp; dept.csv=dept" \
  -merge "left=emp,right=dept,on=id" \
  -head 3
```

**Output:**
```text
 id    name        dept  salary
  1   Alice Engineering   95000
  2     Bob   Marketing   75000
  3 Charlie       Sales   82000
```

### Different Join Keys (`left:right`)

When key column names differ between datasets, map them using `:`:

```bash
pytae -file "customers.parquet=c; orders.csv=o" \
  -merge "left=c,right=o,on='customer_id:cust_id',how=left" \
  -head 5
```

### Join Types (`how=inner|left|right|outer`)

```bash
# Left outer join
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on=id,how=left"
```

### Validating Joins (`validate=one_to_one`)

Protect data integrity by failing immediately if relationships violate cardinality expectations:

```bash
pytae -file "a.csv=a; b.csv=b" -merge "left=a,right=b,on=id,validate=one_to_one"
```

### Folding Multiple Files with `data`

Chain multiple `-merge` flags in sequence. After the first join, use `data` to refer to the running pipeline result:

```bash
pytae -file "users.csv=u; orders.csv=o; payments.parquet=p" \
  -merge "left=u,right=o,on=user_id" \
  -merge "left=data,right=p,on=order_id" \
  -head 5
```

---

## Row-Wise Stacking (`-concat`)

Concatenates multiple datasets with matching structures into one unified table (equivalent to Pandas `pd.concat(ignore_index=True)`):

```bash
# Stack three monthly batches
pytae -file "jan.parquet=m1; feb.parquet=m2; mar.parquet=m3" \
  -concat "frames='m1,m2,m3'" \
  -shape
```

---

## Cross-File SQL Queries (`-sql`)

Instead of `-merge`, you can start a `-file` pipeline with `-sql`. Every alias in `-file` is registered directly as an in-memory DuckDB table:

```bash
pytae -file "customers.csv=c; orders.parquet=o" \
  -sql "
    select
      c.name,
      count(o.order_id) as total_orders,
      sum(o.amount) as total_spent
    from c
    left join o on c.customer_id = o.customer_id
    group by c.name
    order by total_spent desc
  "
```

---

## Exporting Merged Results

In `-file` mode, there is no single source path to infer an in-place output name. Therefore, exporting requires an explicit destination path via `-o`:

```bash
pytae -file "a.parquet=a; b.csv=b" \
  -merge "left=a,right=b,on=id" \
  -o merged_output.parquet
```
