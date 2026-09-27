# CLI Feature Guide: Reshaping & Cross-Tabulation

[← Back to CLI Reference Hub](../cli.md)

Pivot, unpivot, compute frequency counts, sort, and cross-tabulate multidimensional data using `-long`, `-wide`, `-crosstab`, `-value_counts`, and `-sort_by`.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Unpivoting Wide to Long (`-long`)](#unpivoting-wide-to-long--long)
- [Pivoting Long to Wide (`-wide`)](#pivoting-long-to-wide--wide)
- [Contingency Tables & Proportions (`-crosstab`)](#contingency-tables--proportions--crosstab)
  - [Counts Matrix](#counts-matrix)
  - [Percentages & Normalization (`normalize=`)](#percentages--normalization-normalize)
  - [Marginal Totals (`margins=true`)](#marginal-totals-marginstrue)
- [Frequency Counts (`-value_counts`)](#frequency-counts--value_counts)
- [Deduplicating Rows (`-unique`)](#deduplicating-rows--unique)
- [Sorting Rows (`-sort_by`)](#sorting-rows--sort_by)

---

## Overview & Quick Reference

| Flag | Description | Key Parameters |
|---|---|---|
| `-long [SPEC]` | Melt numeric columns into rows | `c=` (metric header), `v=` (value header) |
| `-wide [SPEC]` | Pivot long rows into headers | `c=` (header source), `v=` (values), `a=` (aggfunc) |
| `-crosstab SPEC` | Two-way contingency matrix | `index=`, `columns=`, `normalize=`, `margins=` |
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

## Contingency Tables & Proportions (`-crosstab`)

Computes a frequency or aggregation matrix across categorical factors via Pandas `pd.crosstab()`.

Key parameters:
- `index=`: One or more comma-separated columns for rows (e.g. `index=species` or multi-level `index='species,island'`).
- `columns=`: Column for columns (e.g. `columns=island`).
- `values=` & `aggfunc=`: Aggregate a numeric column (e.g. `values=body_mass_g,aggfunc=mean`).
- `normalize=`: Normalize proportions (`index` for row %, `columns` for col %, `all` for total %).
- `margins=true`: Include row and column subtotals/totals.
- `margins_name=`: Custom label for margins (default: `All`).

### 1. Basic Counts Matrix

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

### 2. Marginal Totals & Custom Names (`margins=true`, `margins_name=`)

Add row and column totals with a custom label:

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

### 3. Percentages & Normalization (`normalize=`)

Display row proportions (`normalize=index`), column proportions (`normalize=columns`), or total proportions (`normalize=all`):

**Row Proportions (`normalize=index`):**
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

**Total Table Proportions (`normalize=all`):**
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

### 4. Numeric Values & Aggregation Function (`values=`, `aggfunc=`)

Compute summary statistics (like `mean`, `sum`, `median`, `min`, `max`) of a numeric column across categories instead of raw counts:

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

### 5. Multi-Column Index (3-Way Cross-Tabulation)

Pass multiple comma-separated columns to `index=` to cross-tabulate across 3 dimensions:

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

### 6. Columns with Spaces (`[col]`)

Enclose column names with spaces in square brackets `[col]`:

```bash
pytae tips.parquet \
  -rename "total_bill:[total bill],smoker:[smoker status]" \
  -crosstab "index=[smoker status],columns=day,values=[total bill],aggfunc=mean" \
  -round 2
```

**Output:**
```text
day             Thur    Fri    Sat    Sun
smoker status                            
Yes            19.19  16.81  21.28  24.12
No             17.11  18.42  19.66  20.51
```

### 7. Pipeline Chaining (`-qry` → `-crosstab`)

Filter data upstream in the CLI pipeline before generating the contingency matrix:

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
