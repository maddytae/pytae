# CLI Feature Guide: 2D Pivot Tables (`-pivot`)

[← Back to CLI Reference Hub](../cli.md)

`-pivot` provides an Excel-style 2D pivot table engine with universal `r, c, v, a` vocabulary:
- **Rows (`r=`)**: Row dimension(s) (*optional*).
- **Cols (`c=`)**: Column dimension(s) to spread as headers (*optional*).
- **Values (`v=`)**: Measure / metric column(s) to aggregate (*optional*; defaults to row count `n` when omitted).
- **Aggregation (`a=`)**: Summary function (`sum`, `mean`, `median`, `min`, `max`, `count`, `std`, `n`; default: `sum`).
- **Missing Categories (`dropna=`)**: Retain `NaN` keys when `false` (default: `false`).
- **Empty Intersections (`f_v=`)**: Fill missing grid cells (e.g. `f_v=0`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Excel-Style Pivot Layouts](#excel-style-pivot-layouts)
  - [1. 2D Grid with Rows & Columns (`r=`, `c=`, `v=`)](#1-2d-grid-with-rows--columns-r-c-v)
  - [2. Frequency Tables & Count Matrices (v= Omitted)](#2-frequency-tables--count-matrices-v-omitted)
  - [3. Vertical Summary Table (`r=`, `v=`)](#3-vertical-summary-table-r-v)
  - [4. Horizontal Summary Table (`c=`, `v=`)](#4-horizontal-summary-table-c-v)
  - [5. Grand Total Summary (`v=`)](#5-grand-total-summary-v)
- [Hierarchical Grouping with Multiple Rows (`r=Region,Store`)](#hierarchical-grouping-with-multiple-rows-rregionstore)
- [Multi-Metric Reporting (`v=Sales,Profit`)](#multi-metric-reporting-vsalesprofit)
- [Filling Empty Intersections (`f_v=0`)](#filling-empty-intersections-f_v0)
- [Guarantees & Differences from `-wide`](#guarantees--differences-from--wide)

---

## Overview & Quick Reference

| Parameter | Meaning | Default | Example |
|---|---|---|---|
| `r` | Row dimension(s) | *None (optional)* | `r=Region` or `r=Region,Store` |
| `c` | Column header dimension(s) | *None (optional)* | `c=Year` or `c=Year,Quarter` |
| `v` | Metric column(s) to aggregate | *Optional (defaults to row counts `n`)* | `v=Sales` or `v=Sales,Profit` |
| `a` | Aggregation function | `sum` | `a=mean`, `a=sum`, `a=n` (count) |
| `dropna` | Drop NA categories | `false` | `dropna=false` (keeps NA groups) |
| `f_v` | Fill for empty cells | `None` (`0` for counts) | `f_v=0` |

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

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |   3709.7 |       nan   |     5076 |
| Dream     |   3688.4 |      3733.1 |      nan |
| Torgersen |   3706.4 |       nan   |      nan |

### 2. Frequency Tables & Count Matrices (v= Omitted)

Just like in Excel where omitting a measure counts records, omitting `v=` in `-pivot` automatically computes row counts (`n`), returns clean integer columns (`int64`), and defaults unobserved intersections to `0`:

#### 2D Contingency Table (Cross-Tabulation):
```bash
# Omit v to produce a 2D cross-tabulation count matrix
pytae penguins.parquet -pivot "r=island,c=species"
```

**Output:**

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |       44 |           0 |      124 |
| Dream     |       56 |          68 |        0 |
| Torgersen |       52 |           0 |        0 |

#### 1D Frequency Breakdown:
```bash
# Omit c and v to produce a 1D frequency breakdown with column 'n'
pytae penguins.parquet -pivot "r=island,sex"
```

**Output:**

| island    | sex    |   n |
|:----------|:-------|----:|
| Biscoe    | Female |  80 |
| Biscoe    | Male   |  83 |
| Biscoe    | nan    |   5 |
| Dream     | Female |  61 |
| Dream     | Male   |  62 |
| Dream     | nan    |   1 |
| Torgersen | Female |  24 |
| Torgersen | Male   |  23 |
| Torgersen | nan    |   5 |

### 3. Vertical Summary Table (`r=`, `v=`)

Omit `c=` to summarize values strictly by row groups (like Excel with only Rows and Values):

```bash
pytae sales.parquet -pivot "r=Region,v=Sales,a=sum"
```

**Output:**

| Region   |   Sales |
|:---------|--------:|
| East     |    4500 |
| West     |    3350 |

### 4. Horizontal Summary Table (`c=`, `v=`)

Omit `r=` to summarize values horizontally across column headers:

```bash
pytae sales.parquet -pivot "c=Year,v=Sales,a=sum"
```

**Output:**

|   2022 |   2023 |   2024 |
|-------:|-------:|-------:|
|   2100 |   2600 |   3150 |

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

| Region   | Store   |   2023 |   2024 |
|:---------|:--------|-------:|-------:|
| Store    | A       |    700 |    850 |
| Store    | B       |    800 |    950 |
| Store    | C       |    900 |   1100 |

Both `Region` and `Store` appear as clean leading columns without any MultiIndex row complexity.

---

## Multi-Metric Reporting (`v=Sales,Profit`)

Report multiple measures simultaneously across dimensions:

```bash
pytae sales.parquet -pivot "r=Region,c=Year,v=Sales,Profit,a=sum"
```

**Output:**

| Region   |   Profit_2023 |   Profit_2024 |   Sales_2023 |   Sales_2024 |
|:---------|--------------:|--------------:|-------------:|-------------:|
| East     |            90 |           120 |          700 |          850 |
| West     |           110 |           150 |          900 |         1100 |

Column names are automatically flattened into intuitive strings (`Metric_Col`), completely avoiding Pandas MultiIndex tuples.

---

## Filling Empty Intersections (`f_v=0`)

When a category combination has no records, replace the missing cell with a scalar:

```bash
pytae penguins.parquet \
  -pivot "r=island,c=species,v=body_mass_g,a=mean,f_v=0" \
  -round 1
```

**Output:**

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |   3709.7 |         0   |   5076   |
| Dream     |   3688.4 |      3733.1 |      0   |
| Torgersen |   3706.4 |         0   |      0   |

---

## Guarantees & Differences from `-wide`

| Feature | `-pivot` (Analytical Reporting) | `-wide` (Pure Reshaping) |
|---|---|---|
| **Purpose** | Multi-dimensional summarization | Format conversion (spread tall to wide) |
| **Silent Aggregation** | **Expected** via `a` (default: `sum`) | **None** (1:1 structural bijection) |
| **Column Selection** | **Automatic**: only touches `r`, `c`, and `v` | Keeps all other columns as row IDs |
| **Index** | Always flat `RangeIndex(0, 1, 2, ...)` | Flat `RangeIndex` |
| **Subtotals & Totals** | None (preserves relational types & chaining) | None |
