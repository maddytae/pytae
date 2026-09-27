# CLI Feature Guide: Reshaping & Cross-Tabulation

[← Back to CLI Reference Hub](../cli.md)

Pivot, unpivot, compute frequency counts, sort, and cross-tabulate multidimensional data using `-long`, `-wide`, `-crosstab`, `-value_counts`, and `-sort_by`.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Unpivoting Wide to Long (`-long`)](#unpivoting-wide-to-long--long)
- [Pivoting Long to Wide (`-wide`)](#pivoting-long-to-wide--wide)
- [Contingency Tables & Cross-Tabulation (`-crosstab`)](#contingency-tables--cross-tabulation--crosstab)
  - [1. Basic Counts Matrix](#1-basic-counts-matrix)
  - [2. Marginal Totals & Custom Names (`margins=true`, `margins_name=`)](#2-marginal-totals--custom-names-marginstrue-margins_name)
  - [3. Percentages & Normalization (`normalize=index|columns|all`)](#3-percentages--normalization-normalizeindexcolumnsall)
  - [4. Numeric Values & Aggregation Functions (`values=`, `aggfunc=`)](#4-numeric-values--aggregation-functions-values-aggfunc)
  - [5. Multi-Column Index (3-Way Cross-Tabulation)](#5-multi-column-index-3-way-cross-tabulation)
  - [6. Columns with Spaces (`[col]`)](#6-columns-with-spaces-col)
  - [7. Preserving Missing / NA Categories (`-dropna false`)](#7-preserving-missing--na-categories--dropna-false)
  - [8. Pipeline Chaining (`-qry` → `-crosstab`)](#8-pipeline-chaining--qry---crosstab)
  - [9. Exporting Cross-Tabulations to File (`-o`)](#9-exporting-cross-tabulations-to-file--o)
- [Frequency Counts (`-value_counts`)](#frequency-counts--value_counts)
- [Deduplicating Rows (`-unique`)](#deduplicating-rows--unique)
- [Sorting Rows (`-sort_by`)](#sorting-rows--sort_by)

---

## Overview & Quick Reference

| Flag | Description | Key Parameters |
|---|---|---|
| `-long [SPEC]` | Melt numeric columns into rows | `c=` (metric header), `v=` (value header) |
| `-wide [SPEC]` | Pivot long rows into headers | `c=` (header source), `v=` (values), `a=` (aggfunc) |
| `-crosstab SPEC` | Two-way & multi-way contingency matrix | `index=`, `columns=`, `values=`, `aggfunc=`, `normalize=`, `margins=`, `margins_name=` |
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

```bash
pytae long_data.parquet -wide "c=metric,v=measurement,a=mean"
```

---

## Contingency Tables & Cross-Tabulation (`-crosstab`)

Computes a frequency or aggregation matrix across categorical factors via Pandas `pd.crosstab()`.

Key parameters:
- `index=`: One or more comma-separated columns for rows (e.g. `index=species` or multi-level `index='species,island'`). Supports bracketed spaced names `[col]`.
- `columns=`: Column for columns (e.g. `columns=island`). Supports bracketed spaced names `[col]`.
- `values=` & `aggfunc=`: Aggregate a numeric column (e.g. `values=body_mass_g,aggfunc=mean`). Must be specified together.
- `normalize=`: Normalize proportions (`index` for row %, `columns` for col %, `all` for total %).
- `margins=true`: Include row and column subtotals/totals.
- `margins_name=`: Custom label for margins (default: `All`; requires `margins=true`).
- `-dropna false`: Include missing / NaN categories in the cross-tabulation.
- `-round N`: Round numeric results to $N$ decimal places.
- `-o TARGET`: Export the contingency table directly to `.csv`, `.parquet`, `.jsonl`, etc.

### 1. Basic Counts Matrix

Compute two-way frequency counts across categorical factors:

**Penguins by Species and Island:**
```bash
pytae penguins.parquet -crosstab "index=species,columns=island"
```

**Output:**
```text
island     Biscoe  Dream  Torgersen
species                            
Adelie         44     56         52
Chinstrap       0     68          0
Gentoo        124      0          0
```

**Tips by Day of Week and Meal Time:**
```bash
pytae tips.parquet -crosstab "index=day,columns=time"
```

**Output:**
```text
time  Lunch  Dinner
day                
Thur     61       1
Fri       7      12
Sat       0      87
Sun       0      76
```

### 2. Marginal Totals & Custom Names (`margins=true`, `margins_name=`)

Add row sums, column sums, and grand totals with default or custom labels:

```bash
pytae penguins.parquet -crosstab "index=species,columns=island,margins=true,margins_name=Total"
```

**Output:**
```text
island     Biscoe  Dream  Torgersen  Total
species                                   
Adelie         44     56         52    152
Chinstrap       0     68          0     68
Gentoo        124      0          0    124
Total         168    124         52    344
```

### 3. Percentages & Normalization (`normalize=index|columns|all`)

Normalize counts to proportions across rows, columns, or the entire dataset:

**Row Proportions (`normalize=index`) — Each Row Sums to 1.0 (100%):**
```bash
pytae penguins.parquet \
  -crosstab "index=species,columns=sex,normalize=index" \
  -round 2
```

**Output:**
```text
sex        Female  Male
species                
Adelie       0.50  0.50
Chinstrap    0.50  0.50
Gentoo       0.49  0.51
```

**Column Proportions (`normalize=columns`) — Each Column Sums to 1.0 (100%):**
```bash
pytae penguins.parquet \
  -crosstab "index=species,columns=island,normalize=columns" \
  -round 3
```

**Output:**
```text
island     Biscoe  Dream  Torgersen
species                            
Adelie      0.262  0.452        1.0
Chinstrap   0.000  0.548        0.0
Gentoo      0.738  0.000        0.0
```

**Grand Total Proportions (`normalize=all`) — Entire Matrix Sums to 1.0 (100%):**
```bash
pytae penguins.parquet \
  -crosstab "index=species,columns=island,normalize=all" \
  -round 3
```

**Output:**
```text
island     Biscoe  Dream  Torgersen
species                            
Adelie      0.128  0.163      0.151
Chinstrap   0.000  0.198      0.000
Gentoo      0.360  0.000      0.000
```

### 4. Numeric Values & Aggregation Functions (`values=`, `aggfunc=`)

Compute summary statistics (`mean`, `sum`, `median`, `min`, `max`, `std`) of a numeric column across categories instead of raw frequency counts:

**Mean Body Mass by Species and Sex:**
```bash
pytae penguins.parquet \
  -crosstab "index=species,columns=sex,values=body_mass_g,aggfunc=mean" \
  -round 1
```

**Output:**
```text
sex        Female    Male
species                  
Adelie     3368.8  4043.5
Chinstrap  3527.2  3939.0
Gentoo     4679.7  5484.8
```

**Median Tip Amount by Day and Meal Time:**
```bash
pytae tips.parquet \
  -crosstab "index=day,columns=time,values=tip,aggfunc=median"
```

**Output:**
```text
time  Lunch  Dinner
day                
Thur    2.3    3.00
Fri     2.2    3.00
Sat     NaN    2.75
Sun     NaN    3.15
```

**Median Diamond Price by Cut and Color:**
```bash
pytae diamonds.parquet \
  -crosstab "index=cut,columns=color,values=price,aggfunc=median" \
  -round 0
```

**Output:**
```text
color           D       E       F       G       H       I       J
cut                                                              
Ideal      1576.0  1437.0  1775.0  1858.0  2278.0  2659.0  4096.0
Premium    2009.0  1928.0  2841.0  2745.0  4511.0  4640.0  5063.0
Very Good  2310.0  1990.0  2471.0  2437.0  3734.0  3888.0  4113.0
Good       2728.0  2420.0  2647.0  3340.0  3468.0  3640.0  3733.0
Fair       3730.0  2956.0  3035.0  3057.0  3816.0  3246.0  3302.0
```

### 5. Multi-Column Index (3-Way Cross-Tabulation)

Pass multiple comma-separated column names to `index=` to cross-tabulate across 3 or more dimensions simultaneously:

**Species and Island Distribution across Sex:**
```bash
pytae penguins.parquet -crosstab "index='species,island',columns=sex"
```

**Output:**
```text
sex                  Female  Male
species   island                 
Adelie    Biscoe         22    22
          Dream          27    28
          Torgersen      24    23
Chinstrap Dream          34    34
Gentoo    Biscoe         58    61
```

**Passenger Survival Rates by Class and Sex:**
```bash
pytae titanic.parquet \
  -qry "age >= 18" \
  -crosstab "index='pclass,sex',columns=survived,normalize=index" \
  -round 3
```

**Output:**
```text
survived           0      1
pclass sex                 
1      female  0.026  0.974
       male    0.629  0.371
2      female  0.097  0.903
       male    0.932  0.068
3      female  0.582  0.418
       male    0.867  0.133
```

### 6. Columns with Spaces (`[col]`)

Enclose column names containing spaces in square brackets `[col]`:

```bash
pytae tips.parquet \
  -rename "total_bill:[total bill],smoker:[smoker status],day:[day of week]" \
  -crosstab "index=[smoker status],columns=[day of week],values=[total bill],aggfunc=mean" \
  -round 2
```

**Output:**
```text
day of week     Thur    Fri    Sat    Sun
smoker status                            
Yes            19.19  16.81  21.28  24.12
No             17.11  18.42  19.66  20.51
```

### 7. Preserving Missing / NA Categories (`-dropna false`)

By default, missing combinations and rows/columns with all-NA values are dropped. Pass `-dropna false` to retain them:

```bash
pytae penguins.parquet \
  -crosstab "index=species,columns=sex" \
  -dropna false
```

**Output:**
```text
sex        Female  Male  NaN
species                     
Adelie         73    73    6
Chinstrap      34    34    0
Gentoo         58    61    5
```

### 8. Pipeline Chaining (`-qry` → `-crosstab`)

Combine upstream filtering with downstream cross-tabulation in a single shell command:

**Youth Survival on the Titanic:**
```bash
pytae titanic.parquet \
  -qry "age < 18" \
  -crosstab "index=pclass,columns=survived,margins=true,margins_name=Total"
```

**Output:**
```text
survived   0   1  Total
pclass                 
1          1  11     12
2          2  21     23
3         49  29     78
Total     52  61    113
```

**Weekend Dinner Average Bill for Parties of 2 or More:**
```bash
pytae tips.parquet \
  -qry "day=['Sat', 'Sun'], time='Dinner', size>=2" \
  -crosstab "index=smoker,columns=day,values=total_bill,aggfunc=mean" \
  -round 2
```

**Output:**
```text
day       Sat    Sun
smoker              
Yes     21.72  24.12
No      19.94  20.51
```

### 9. Exporting Cross-Tabulations to File (`-o`)

Export computed contingency tables directly to `.csv`, `.parquet`, or `.jsonl` files (the row index names are automatically preserved in the export):

```bash
pytae penguins.parquet \
  -crosstab "index=species,columns=island,margins=true" \
  -o crosstab_summary.csv
```

**Written CSV File:**
```csv
species,Biscoe,Dream,Torgersen,All
Adelie,44,56,52,152
Chinstrap,0,68,0,68
Gentoo,124,0,0,124
All,168,124,52,344
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
