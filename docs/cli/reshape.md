# CLI Feature Guide: Reshaping & Data Organization

[← Back to CLI Reference Hub](../cli.md)

Pivot, unpivot, compute frequency counts, sort, and organize multidimensional data using `-long`, `-wide`, `-value_counts`, `-unique`, and `-sort_by`.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Unpivoting Wide to Long (`-long`)](#unpivoting-wide-to-long--long)
- [Pivoting Long to Wide (`-wide`)](#pivoting-long-to-wide--wide)
- [2D Pivot Tables (`-pivot`)](#2d-pivot-tables--pivot)
  - [1. 2D Grid with Rows & Columns (`r=`, `c=`, `v=`)](#1-2d-grid-with-rows--columns-r-c-v)
  - [2. Multiple Grouping Dimensions (`r=Region,Store`)](#2-multiple-grouping-dimensions-rregionstore)
  - [3. Multiple Value Metrics (`v=Sales,Profit`)](#3-multiple-value-metrics-vsalesprofit)
  - [4. Handling Missing Grid Cells (`fill=0`)](#4-handling-missing-grid-cells-fill0)
- [Frequency Counts (`-value_counts`)](#frequency-counts--value_counts)
- [Deduplicating Rows (`-unique`)](#deduplicating-rows--unique)
- [Sorting Rows (`-sort_by`)](#sorting-rows--sort_by)

---

## Overview & Quick Reference

| Flag | Description | Key Parameters |
|---|---|---|
| `-long [SPEC]` | Melt numeric columns into rows | `c=` (metric header), `v=` (value header), `r=` (fixed rows) |
| `-wide [SPEC]` | Pure reshape: pivot long rows into headers | `c=` (header source), `v=` (values), `r=` (row index) |
| `-pivot SPEC` | Excel-style 2D pivot table with auto-reset index | `r=` (rows), `c=` (cols), `v=` (values, req), `a=` (sum), `fill=` |
| `-value_counts` | Group counts across current working columns | Pair with `-select` |
| `-unique` | Drop duplicate rows | — |
| `-sort_by SPEC` | Sort rows by column list | `col1,col2 desc` |

---

## Unpivoting Wide to Long (`-long`)

Melts all numeric columns into row-wise key-value pairs (`variable` and `value`), keeping non-numeric identifier columns intact:

```bash
pytae penguins.parquet \
  -select "species,bill_length_mm,bill_depth_mm" \
  -long \
  -head 4
```

**Output:**
```text
species       variable  value
 Adelie bill_length_mm   39.1
 Adelie bill_length_mm   39.5
 Adelie bill_length_mm   40.3
 Adelie bill_length_mm    NaN
```

Customize column names with `c=` and `v=`:
```bash
pytae penguins.parquet -long "c=metric,v=measurement" -head 4
```

---

## Pivoting Long to Wide (`-wide`)

Pivots categorical values in column `c=` into column headers, taking values from `v=`:

### 1. Pivoting Metric Values (`c=`, `v=`)

```bash
pytae long_data.parquet -wide "c=metric,v=measurement,a=mean"
```

### 2. Frequency Matrix via Group Counts (`a=n`)

Compute a two-way contingency/frequency matrix by pairing `-select` and `-wide` with `a=n` (group row count):

```bash
pytae penguins.parquet \
  -select "species,island,sex" \
  -wide "c=island,v=sex,a=n"
```

**Output:**
```text
  species  Biscoe  Dream  Torgersen
   Adelie    44.0   56.0       52.0
Chinstrap     NaN   68.0        NaN
   Gentoo   124.0    NaN        NaN
```

### 3. Custom Aggregations (`a=mean`, `a=sum`, etc.)

Pivot values using standard aggregation functions:

```bash
pytae penguins.parquet \
  -select "species,island,body_mass_g" \
  -wide "c=island,v=body_mass_g,a=mean" \
  -round 1
```

### 4. Preserving Missing Categories (`-dropna false`)

By default, missing keys are dropped (`-dropna true`). Pass `-dropna false` to retain `NaN` groups in the output:

```bash
pytae data.parquet -wide "c=category,v=score,a=mean" -dropna false
```

---

## 2D Pivot Tables (`-pivot`)

`-pivot` provides an Excel-style 2D pivot table engine with universal `r, c, v, a` vocabulary:

- **`r=`** (or `rows`, `index`, `by`): Row dimension(s) (*optional*).
- **`c=`** (or `cols`, `columns`): Column header dimension(s) (*optional*).
- **`v=`** (or `values`, `val`): Measure / value column(s) to aggregate (**required**).
- **`a=`** (or `agg`, `aggfunc`): Aggregation function (`sum`, `mean`, `median`, `min`, `max`, `count`, `std`, `n`/`size`; default: `sum`).
- **`dropna=`**: Drop `NaN` categories when `true` (default: `false`).
- **`fill=`** (or `fill_value`): Fill value for empty grid intersections (e.g. `fill=0`).

> **Auto-Selection**: Unlike `-wide`, `-pivot` automatically subsets the DataFrame to only the referenced `r`, `c`, and `v` columns—no `-select` needed beforehand.
>
> **Clean Flattened DataFrames**: The index is always reset to `RangeIndex(0, 1, 2, ...)` and column MultiIndexes are flattened into clean strings (e.g. `Sales_2023`).

### 1. 2D Grid with Rows & Columns (`r=`, `c=`, `v=`)

```bash
pytae penguins.parquet \
  -pivot "r=island,c=species,v=body_mass_g,a=mean" \
  -round 1
```

**Output:**
```text
   island  Adelie  Chinstrap  Gentoo
   Biscoe  3709.7        NaN  5076.0
    Dream  3688.4     3733.1     NaN
Torgersen  3706.4        NaN     NaN
```

### 2. Multiple Grouping Dimensions (`r=Region,Store`)

Group hierarchically by specifying comma-separated columns:

```bash
pytae sales.parquet -pivot "r=Region,Store,c=Year,v=Sales,a=sum"
```

Both `Region` and `Store` appear as leading columns without any MultiIndex row complexity.

### 3. Multiple Value Metrics (`v=Sales,Profit`)

Report multiple metrics across columns:

```bash
pytae sales.parquet -pivot "r=Region,c=Year,v=Sales,Profit,a=sum"
```

Generates flattened columns: `Sales_2023`, `Profit_2023`, `Sales_2024`, `Profit_2024`.

### 4. Handling Missing Grid Cells (`fill=0`)

Replace empty intersections with a default scalar:

```bash
pytae penguins.parquet \
  -pivot "r=island,c=species,v=body_mass_g,a=mean,fill=0" \
  -round 1
```

---

## Frequency Counts (`-value_counts`)

Counts unique combinations across current working columns (pair with `-select`):

```bash
pytae penguins.parquet -select "species,island" -value_counts
```

**Output:**
```text
  species    island  count
   Gentoo    Biscoe    124
Chinstrap     Dream     68
   Adelie     Dream     56
   Adelie Torgersen     52
   Adelie    Biscoe     44
```

---

## Deduplicating Rows (`-unique`)

Drops duplicate rows across the intermediate DataFrame:

```bash
pytae penguins.parquet -select "species,island" -unique
```

---

## Sorting Rows (`-sort_by`)

Sort rows by one or more columns with optional `asc` or `desc` order (defaults to `asc`):

```bash
pytae penguins.parquet \
  -select "species,body_mass_g" \
  -sort_by "body_mass_g desc" \
  -head 3
```

**Output:**
```text
species  body_mass_g
 Gentoo       6300.0
 Gentoo       6050.0
 Gentoo       6000.0
```
