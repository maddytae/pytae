# CLI Feature Guide: 2D Pivot Tables (`-pivot`)

[← Back to CLI Reference Hub](../cli.md)

`-pivot` provides an Excel-style 2D pivot table engine with universal `r, c, v, a` vocabulary:
- **Rows (`r=`)**: Row dimension(s) (*optional*).
- **Cols (`c=`)**: Column dimension(s) to spread as headers (*optional*).
- **Values (`v=`)**: Measure / metric column(s) to aggregate (**required**).
- **Aggregation (`a=`)**: Summary function (`sum`, `mean`, `median`, `min`, `max`, `count`, `std`, `n`/`size`; default: `sum`).
- **Missing Categories (`dropna=`)**: Retain `NaN` keys when `false` (default: `false`).
- **Empty Intersections (`fill=`)**: Fill missing grid cells (e.g. `fill=0`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Excel-Style Pivot Layouts](#excel-style-pivot-layouts)
  - [1. 2D Grid with Rows & Columns (`r=`, `c=`, `v=`)](#1-2d-grid-with-rows--columns-r-c-v)
  - [2. 2D Frequency Matrix / Cross-Tabulation (`a=n`)](#2-2d-frequency-matrix--cross-tabulation-an)
  - [3. Vertical Summary Table (`r=`, `v=`)](#3-vertical-summary-table-r-v)
  - [4. Horizontal Summary Table (`c=`, `v=`)](#4-horizontal-summary-table-c-v)
  - [5. Grand Total Summary (`v=`)](#5-grand-total-summary-v)
- [Hierarchical Grouping with Multiple Rows (`r=Region,Store`)](#hierarchical-grouping-with-multiple-rows-rregionstore)
- [Multi-Metric Reporting (`v=Sales,Profit`)](#multi-metric-reporting-vsalesprofit)
- [Filling Empty Intersections (`fill=0`)](#filling-empty-intersections-fill0)
- [Guarantees & Differences from `-wide`](#guarantees--differences-from--wide)

---

## Overview & Quick Reference

| Parameter | Meaning | Default | Example |
|---|---|---|---|
| `r` (or `rows`, `index`, `by`) | Row dimension(s) | *None (optional)* | `r=Region` or `r=Region,Store` |
| `c` (or `cols`, `columns`) | Column header dimension(s) | *None (optional)* | `c=Year` or `c=Year,Quarter` |
| `v` (or `values`, `val`) | Metric column(s) to aggregate | **Required** | `v=Sales` or `v=Sales,Profit` |
| `a` (or `agg`, `aggfunc`) | Aggregation function | `sum` | `a=mean`, `a=sum`, `a=n` (count) |
| `dropna` | Drop NA categories | `false` | `dropna=false` (keeps NA groups) |
| `fill` (or `fill_value`) | Fill for empty cells | `None` (`NaN`) | `fill=0` |

---

## Excel-Style Pivot Layouts

Just like dragging fields into Rows and Columns in Excel, `r` and `c` are completely optional:

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

### 2. 2D Frequency Matrix / Cross-Tabulation (`a=n`)

When counting occurrences across dimensions with `a=n` (or `a=size`), `pytae` automatically returns standard integers (`int64`) and sets unobserved intersections to `0` rather than `NaN`:

```bash
pytae penguins.parquet -pivot "r=island,c=species,v=sex,a=n"
```

**Output:**
```text
   island  Adelie  Chinstrap  Gentoo
   Biscoe      44          0     124
    Dream      56         68       0
Torgersen      52          0       0
```

### 3. Vertical Summary Table (`r=`, `v=`)

Omit `c=` to summarize values strictly by row groups (like Excel with only Rows and Values):

```bash
pytae sales.parquet -pivot "r=Region,v=Sales,a=sum"
```

**Output:**
```text
Region   Sales
  East  4500.0
  West  3350.0
```

### 4. Horizontal Summary Table (`c=`, `v=`)

Omit `r=` to summarize values horizontally across column headers:

```bash
pytae sales.parquet -pivot "c=Year,v=Sales,a=sum"
```

**Output:**
```text
  2022    2023    2024
2100.0  2600.0  3150.0
```

### 5. Grand Total Summary (`v=`)

Omit both `r=` and `c=` for a single-row grand aggregation:

```bash
pytae sales.parquet -pivot "v=Sales,a=sum"
```

**Output:**
```text
 Sales
7850.0
```

---

## Hierarchical Grouping with Multiple Rows (`r=Region,Store`)

Pass comma-separated columns to `r=` to group across multiple levels:

```bash
pytae sales.parquet -pivot "r=Region,Store,c=Year,v=Sales,a=sum"
```

**Output:**
```text
Region   Store   2023   2024
  East Store A  700.0  850.0
  East Store B  800.0  950.0
  West Store C  900.0 1100.0
```

Both `Region` and `Store` appear as clean leading columns without any MultiIndex row complexity.

---

## Multi-Metric Reporting (`v=Sales,Profit`)

Report multiple measures simultaneously across dimensions:

```bash
pytae sales.parquet -pivot "r=Region,c=Year,v=Sales,Profit,a=sum"
```

**Output:**
```text
Region  Profit_2023  Profit_2024  Sales_2023  Sales_2024
  East         90.0        120.0       700.0       850.0
  West        110.0        150.0       900.0      1100.0
```

Column names are automatically flattened into intuitive strings (`Metric_Col`), completely avoiding Pandas MultiIndex tuples.

---

## Filling Empty Intersections (`fill=0`)

When a category combination has no records, replace the missing cell with a scalar:

```bash
pytae penguins.parquet \
  -pivot "r=island,c=species,v=body_mass_g,a=mean,fill=0" \
  -round 1
```

---

## Guarantees & Differences from `-wide`

| Feature | `-pivot` (Analytical Reporting) | `-wide` (Pure Reshaping) |
|---|---|---|
| **Purpose** | Multi-dimensional summarization | Format conversion (spread tall to wide) |
| **Silent Aggregation** | **Expected** via `a` (default: `sum`) | **None** (1:1 structural bijection) |
| **Column Selection** | **Automatic**: only touches `r`, `c`, and `v` | Keeps all other columns as row IDs |
| **Index** | Always flat `RangeIndex(0, 1, 2, ...)` | Flat `RangeIndex` |
| **Subtotals & Totals** | None (preserves relational types & chaining) | None |
