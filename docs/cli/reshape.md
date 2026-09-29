# CLI Feature Guide: Reshaping & Data Organization

[← Back to CLI Reference Hub](../cli.md)

Pure structural reshaping (`-long`, `-wide`), frequency counts (`-value_counts`), deduplication (`-unique`), and row sorting (`-sort_by`).

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Unpivoting Wide to Long (`-long`)](#unpivoting-wide-to-long--long)
- [Pivoting Long to Wide (`-wide`)](#pivoting-long-to-wide--wide)
  - [1. Pure 1-to-1 Unmelting](#1-pure-1-to-1-unmelting)
  - [2. Explicit Row Index (`r=`)](#2-explicit-row-index-r)
  - [3. Round-Trip Reshaping (`-long` → `-wide`)](#3-round-trip-reshaping--long---wide)
- [When to Use `-pivot` Instead of `-wide`](#when-to-use--pivot-instead-of--wide)
- [Frequency Counts (`-value_counts`)](#frequency-counts--value_counts)
- [Deduplicating Rows (`-unique`)](#deduplicating-rows--unique)
- [Sorting Rows (`-sort_by`)](#sorting-rows--sort_by)

---

## Overview & Quick Reference

`-long` and `-wide` are designed as a **strictly complementary, 1-to-1 reshaping pair**:

| Flag | Description | Key Parameters |
|---|---|---|
| `-long [SPEC]` | Melt numeric columns into rows | `c=` (metric header), `v=` (value header), `r=` (fixed rows) |
| `-wide [SPEC]` | Pure 1-to-1 reshape: spread long rows into headers | `c=` (header source), `v=` (values), `r=` (row index) |
| `-value_counts` | Group counts across current working columns | Pair with `-select` |
| `-unique` | Drop duplicate rows | — |
| `-sort_by SPEC` | Sort rows by column list | `col1,col2 desc` |

> [!IMPORTANT]
> **`-wide` is strictly for 1-to-1 reshaping without aggregation.** If your data has multiple rows per key combination and requires mathematical summarization (`mean`, `sum`, `count`/`n`), use **[`-pivot`](pivot.md)**.

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

`-wide` performs pure structural un-melting (inverse of `-long`), pivoting values from column `c=` into separate column headers using values from `v=`.

### 1. Pure 1-to-1 Unmelting

Given a long dataset with unique row keys (such as `flights.parquet` with unique `year` + `month` pairs):

```bash
pytae flights.parquet -wide "c=month,v=passengers" -head 3
```

**Output:**
```text
year  Jan  Feb  Mar  Apr  May  Jun  Jul  Aug  Sep  Oct  Nov  Dec
1949  112  118  132  129  121  135  148  148  136  119  104  118
1950  115  126  141  135  125  149  170  170  158  133  114  140
1951  145  150  178  163  172  178  199  199  184  162  146  166
```

### 2. Explicit Row Index (`r=`)

By default, all columns other than `c` and `v` serve as row identifiers. Use `r=` (or `by=`) to declare specific row index columns explicitly:

```bash
pytae flights.parquet -wide "r=year,c=month,v=passengers" -head 3
```

### 3. Round-Trip Reshaping (`-long` → `-wide`)

Because `-long` and `-wide` are strict 1-to-1 bijections, you can melt and immediately un-melt back to the original tabular structure:

```bash
pytae data.parquet \
  -long "c=variable,v=value" \
  -wide "c=variable,v=value"
```

---

## When to Use `-pivot` Instead of `-wide`

| Scenario | Use `-wide` | Use `-pivot` |
|---|:---:|:---:|
| **Unique key-value pairs (1:1 un-melting)** | ✅ Yes | Optional |
| **Duplicate key-value combinations** | ❌ Raises error | ✅ Yes (aggregates) |
| **Mathematical summaries (`sum`, `mean`, etc.)** | ❌ Not supported | ✅ Yes (`a=sum`, `a=mean`) |
| **Two-way frequency counts (`a=n`)** | ❌ Not supported | ✅ Yes (`a=n`) |
| **Fill empty cells (`fill=0`)** | ❌ (leaves `NaN`) | ✅ Yes (`fill=0`) |

If duplicate keys are passed to `-wide`, `pytae` stops immediately and directs you to `-pivot`:

```text
pytae: error: wide() encountered duplicate entries for index [...] and column '...'. wide() is strictly for 1-to-1 reshaping without aggregation. Use pt.pivot() / -pivot to summarize or aggregate duplicate entries.
```

👉 See the complete **[2D Pivot Tables Guide](pivot.md)** for all multi-dimensional aggregation patterns.

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
