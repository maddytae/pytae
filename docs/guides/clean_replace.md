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
| `-fillna` | Cell contents | Scalar, `col:val`, or `val, cols` | Replaces null / NaN with replacement values |
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
pytae messy.parquet -clean_columns "strip,strip_special,case=lower,fill=_"
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

## Missing Value Imputation (`-fillna`, `df.fillna()`)

Under Pytae's unified missing value architecture, all missing values, unrecorded data, and floating-point non-finite values (`NaN`, `np.nan`, `float('nan')`) are normalized uniformly to Arrow `null`.

Impute missing values across the dataset or within specific columns:

```bash
# Impute all numeric missing values with 0
pytae dataset.parquet -fillna 0 -head 5

# Impute specific columns using column mappings or value + column list
pytae dataset.parquet -fillna "status:Unknown, category:Unknown" -head 5
pytae dataset.parquet -fillna "Unknown, status, category" -head 5
```

```python
# In Python API:
df.fillna(0)
df.fillna({"status": "Unknown", "category": "Unknown"})
```

> [!IMPORTANT]
> **Hard Deprecation of `nans` parameter & `.fill_nan()` / `.fill_null()`**:
> In line with **"One and Only One Obvious Way"**, Pytae does not have separate parameters or functions for `NaN` vs. `null`.
> - Passing `nans=...` or `drop_nans=...` to `fillna()` or `dropna()` raises an explicit `ValueError`.
> - Calling `.fill_nan()` or `.fill_null()` raises `ValueError` directing users to canonical `.fillna()`.
> - In filtering, `.is_nan()` and `.is_not_nan()` are retired in favor of universal `.is_null()` and `.is_not_null()`.

---

## Dropping Missing Values (`-dropna`, `df.dropna()`)

Pytae adheres to a **Zero Data Loss by Default** philosophy for missing values:

- **Bare `-dropna` / `df.dropna()`**: Defaults to `how="all"`. Drops **only completely empty rows** (rows where every column is null), preserving partially populated rows from accidental loss.
- **Targeted `-dropna "col1, col2"` / `df.dropna("col1", "col2")`**: Defaults to `how="any"`. Drops rows missing *any* of the specified columns.
- **Explicit `how=any` across whole table**: Drops rows containing *any* missing value across all columns.
- **Explicit `how=all` on targeted columns**: Drops rows only if *all* of the specified columns are missing simultaneously.

### The Complete Matrix of `how` Cases

| Invocation (Python) | Invocation (CLI) | Scope | Effective `how` | Row Dropping Rule |
|:---|:---|:---|:---:|:---|
| `df.dropna()` | `pytae -dropna` | All columns | `how='all'` | Drops **only 100% empty rows** (all columns null). Safe default. |
| `df.dropna(how="any")` | `pytae -dropna how=any` | All columns | `how='any'` | Drops rows missing **any** column (strict complete-cases filter). |
| `df.dropna(how="all")` | `pytae -dropna how=all` | All columns | `how='all'` | Explicit equivalent of bare `df.dropna()`. |
| `df.dropna(c.a, c.b)` | `pytae -dropna "a, b"` | Columns `a, b` | `how='any'` | Drops rows missing **either** `a` OR `b`. Target default. |
| `df.dropna(c.a, c.b, how="any")` | `pytae -dropna "a, b, how=any"` | Columns `a, b` | `how='any'` | Explicit equivalent of `df.dropna(c.a, c.b)`. |
| `df.dropna(c.a, c.b, how="all")` | `pytae -dropna "a, b, how=all"` | Columns `a, b` | `how='all'` | Drops rows only if **both** `a` AND `b` are missing. |

```bash
# 1. Bare flag defaults to how='all' (Zero Data Loss: keeps 344 rows in penguins)
pytae penguins.parquet -dropna -shape
# (344, 7)

# 2. Targeted columns default to how='any' (344 -> 342 rows)
pytae penguins.parquet -dropna body_mass_g -shape
# (342, 7)

# 3. Explicit how=any across whole table drops rows with any missing value (344 -> 333 rows)
pytae penguins.parquet -dropna how=any -shape
# (333, 7)

# 4. Explicit how=all on targeted columns drops rows only if BOTH columns are missing
pytae penguins.parquet -dropna "sex, body_mass_g, how=all" -shape
# (344, 7)
```

```python
# In Python API:
df.dropna()                            # Case 1: Drops only 100% blank rows (how='all')
df.dropna(how="any")                   # Case 2: Drops rows missing ANY column across the table
df.dropna(c.sex, c.body_mass_g)        # Case 3: Drops rows missing sex OR body_mass_g (how='any')
df.dropna(c.sex, c.body_mass_g, how="all") # Case 4: Drops rows missing BOTH sex AND body_mass_g
```

> [!NOTE]
> - **Top-level `-dropna [COLS]`**: Operates as a row filter. Bare calls use `how="all"` (Zero Data Loss), while targeted calls use `how="any"` on the specified columns.
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
