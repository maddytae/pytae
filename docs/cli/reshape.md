# CLI Feature Guide: Reshaping & Cross-Tabulation

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

Computes a frequency matrix of two categorical factors via Pandas `pd.crosstab()`.

### Counts Matrix

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

### Percentages & Normalization (`normalize=`)

Display row proportions (`normalize=index`), column proportions (`normalize=columns`), or total proportions (`normalize=all`):

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

### Marginal Totals (`margins=true`)

Add row and column totals:

```bash
pytae penguins.parquet -crosstab "index=species,columns=island,margins=true"
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
