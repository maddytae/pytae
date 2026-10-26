# CLI Feature Guide: Data Cleaning, Imputation, & Renaming

Standardize messy column headers (`-clean` / `-clean_columns`), impute missing values (`-fillna`), drop missing rows (`-dropna`), rename columns (`-rename`), and recode cell values via `-mutate "map(...)"`.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Header Standardization](#header-standardization)
  - [Supported Pipeline Steps](#supported-pipeline-steps)
  - [Cleaning Examples](#cleaning-examples)
- [Missing Value Imputation (`-fillna`)](#missing-value-imputation--fillna)
- [Dropping Missing Values](#dropping-missing-values)
- [Column Renaming (`-rename`)](#column-renaming--rename)
- [Recoding Categorical Values (`-mutate "map(...)"`)](#recoding-categorical-values--mutate-map)

---

## Overview & Quick Reference

| Flag | Scope | Delimiter / Syntax | Description |
|---|---|---|---|
| `-clean` / `-clean_columns` | Column headers | `,` / `=` | Standardizes headers (strip, squeeze, fill, case, dedupe) |
| `-fillna` | Cell contents | Scalar or `val=..., cols=...` | Replaces null / NaN with replacement values |
| `-dropna` | Rows | Bare or `col1, col2` | Drops null / NaN rows (Zero Data Loss default) |
| `-rename` | Column headers | `old:new` | Explicitly renames column names |
| `-mutate "col = map(...)"` | Cell contents | Dictionary mapping | Vectorized value recoding via Polars engine |

---

## Header Standardization

### Supported Pipeline Steps

Clean messy column names automatically. Options execute in this order:
1. `strip`: Remove leading and trailing whitespace.
2. `strip_special`: Remove non-alphanumeric punctuation (except `_`).
3. `squeeze`: Collapse multiple consecutive spaces into a single space.
4. `fill[=STR]`: Replace spaces with a separator (default `_`).
5. `case=lower|upper|proper`: Transform casing.
6. `dedupe`: Append suffixes (`_1`, `_2`) to disambiguate duplicated column names.

### Cleaning Examples

```bash
# Clean leading spaces, punctuation, lowercase, and replace spaces with underscores:
pytae messy.parquet -clean "strip,strip_special,case=lower,fill=_"
```

**Before:**
```text
  Old Name    Score %      Status
hello world      10.5 draft_stage
    bad_val       NaN    approved
        NaN      30.2 draft_stage
```

**After:**
```text
   old_name  score_      status
hello world    10.5 draft_stage
    bad_val     NaN    approved
        NaN    30.2 draft_stage
```

---

## Missing Value Imputation (`-fillna`)

Replace missing values (`null` and `NaN`) across the dataset or within specific columns:

```bash
# Impute all numeric missing values with 0
pytae dataset.parquet -fillna 0 -head 5

# Impute specific columns
pytae dataset.parquet -fillna "val='Unknown', cols='status, category'" -head 5

# Only replace Arrow nulls (leave float NaNs intact)
pytae dataset.parquet -fillna "val=0, nans=false" -head 5
```

---

## Dropping Missing Values

Pytae adheres to a **Zero Data Loss by Default** philosophy for missing values (Arrow `null`s and IEEE-754 float `NaN`s).

- **Bare `-dropna`**: Defaults to `how="all"`. Drops **only completely empty rows** (rows where every column is null/NaN), preserving partially populated rows.
- **Targeted `-dropna "col1, col2"`**: Defaults to `how="any"`. Drops rows missing *any* of the specified columns.
- **Explicit `how=any`**: Drops rows containing *any* missing value across all columns.
- **Optional `drop_nans=false`**: Drops only Arrow nulls, preserving float IEEE-754 NaNs.

```bash
# Bare flag defaults to how='all' (Zero Data Loss: keeps 344 rows in penguins)
pytae penguins.parquet -dropna -shape
# (344, 7)

# Drop rows missing specific required columns (344 -> 342 rows)
pytae penguins.parquet -dropna body_mass_g -shape
# (342, 7)

# Explicit how=any drops rows with any missing value (344 -> 333 rows)
pytae penguins.parquet -dropna how=any -shape
# (333, 7)
```

> [!NOTE]
> - **Top-level `-dropna [COLS]`**: Operates as a row filter. Bare calls use `how="all"` (Zero Data Loss), while targeted calls use `how="any"` on the specified columns. Both Arrow `null` and float `NaN` are cleaned by default.
> - **Scoped `dropna=bool`**: In `-pivot` and `-agg`, default is `dropna=false` (retains missing group keys without silent data loss). Pass `dropna=true` inside the spec (e.g. `-agg "a=mean, dropna=true"`) to exclude NA groups.

---

## Column Renaming (`-rename`)

Rename columns explicitly at any point in the pipeline using the `old:new` mapping convention:

```bash
pytae dataset.parquet -rename "Status:review_status,Old Name:clean_name"
```

**Output:**
```text
 clean_name    Score % review_status
hello world       10.5   draft_stage
    bad_val        NaN      approved
        NaN       30.2   draft_stage
```

---

## Recoding Categorical Values (`-mutate "map(...)"`)

Recode cell values cleanly via vectorized dictionary mapping directly in `-mutate`:

```bash
# 1. Two-argument: recode mapped values, preserve unmapped values intact
pytae penguins.parquet -mutate "species_code = map(species, {'Adelie': 'AD', 'Gentoo': 'GEN'})" -head 5

# 2. Three-argument with constant fallback: replace unmapped rows with 'Other'
pytae penguins.parquet -mutate "species_code = map(species, {'Adelie': 'AD'}, 'Other')" -head 5

# 3. Three-argument with column fallback: pull fallback value from another column
pytae deals.parquet -mutate "broker = map(deal_type, {'Direct': 'DIR'}, broker_code)" -head 5
```
