# Library Feature Guide: Other Utilities & Data Cleaning

[← Back to Library Reference Hub](../library.md)

Essential utilities for fast column inspection, header normalization, cell replacement, missing value handling, and clipboard interaction.

---

## Contents

- [Overview & Quick Reference](#overview--quick-reference)
- [Listing Columns (`cols`)](#listing-columns-cols)
- [Transposed Overview (`glimpse`)](#transposed-overview-glimpse)
- [Handling Missing Values (`handle_missing`)](#handling-missing-values-handle_missing)
- [Cleaning Column Headers (`clean_columns`)](#cleaning-column-headers-clean_columns)
- [Replacing Cell Values (`replace_values`)](#replacing-cell-values-replace_values)
- [System Clipboard (`to_clip`)](#system-clipboard-to_clip)

---

## Overview & Quick Reference

| Utility | Method / Function | Purpose |
|---|---|---|
| **Column Names** | `df.pt.cols(ascending=True)` / `pt.cols(df)` | List column names alphabetically or in file order |
| **Glimpse** | `df.pt.glimpse(width=None)` / `pt.glimpse(df)` | Transposed summary with dtypes & samples (returns `self` for chaining) |
| **Missing Imputation** | `df.pt.handle_missing(...)` / `pt.handle_missing(df)` | Fill string NaN with marker, numeric NaN with 0/mean/median |
| **Header Cleaning** | `df.pt.clean_columns(...)` / `pt.clean_columns(df)` | Normalize headers (strip, squeeze, fill, case, dedupe) |
| **Value Replacement** | `df.pt.replace_values(v, c=None, exact=True)` | Replace values scoped to columns, exact or regex substring |
| **Clipboard Export** | `df.to_clip()` / `s.to_clip()` | Copy DataFrame or Series to clipboard (TSV, index=False) |

👉 **Interactive Walkthrough Notebook:** [`docs/library/other_utilities.ipynb`](other_utilities.ipynb)

---

## Listing Columns (`cols`)

Quickly discover or sort column names:

```python
import pytae as pt

penguins = pt.sample("penguins")

# Alphabetical ascending (default)
penguins.pt.cols()
# ['bill_depth_mm', 'bill_length_mm', 'body_mass_g', 'flipper_length_mm', 'island', 'sex', 'species']

# Reverse alphabetical
penguins.pt.cols(ascending=False)

# Original DataFrame order
penguins.pt.cols(ascending=None)
```

---

## Transposed Overview (`glimpse`)

Inspired by `dplyr::glimpse` and Polars, `glimpse()` prints a transposed overview showing total rows, column count, data types, and first few values. In Python pipelines, it returns `self` for non-destructive inspection mid-chain:

```python
(
    penguins
    .pt.qry("body_mass_g > 4000")
    .pt.glimpse()  # Prints summary and passes DataFrame downstream
    .pt.select("species", "body_mass_g")
    .head(3)
)
```

**Console Output:**
```text
Rows: 168
Columns: 7
$ species           <object> 'Gentoo', 'Gentoo', 'Gentoo', ...
$ island            <object> 'Biscoe', 'Biscoe', 'Biscoe', ...
$ bill_length_mm   <float64> 46.1, 50.0, 48.7, ...
$ bill_depth_mm    <float64> 13.2, 16.3, 14.1, ...
$ flipper_length_mm <float64> 211.0, 230.0, 210.0, ...
$ body_mass_g      <float64> 4500.0, 5700.0, 4450.0, ...
$ sex               <object> 'Female', 'Male', 'Female', ...
```

---

## Handling Missing Values (`handle_missing`)

Clean missing values before aggregation or feature engineering:
- String and object columns are filled with `fillna` (default `'.'`) and stripped of whitespace.
- Numeric columns are filled with `numeric_fill` (default `0`; can be `'mean'`, `'median'`, or `None`).
- Categorical columns preserve their categorical dtype without raising errors.

```python
# Clean all missing values across the frame
clean_df = penguins.pt.handle_missing()

# Scoped to specific columns with mean fill for numerics
custom_df = penguins.pt.handle_missing(numeric_fill="mean", cols=["body_mass_g"])
```

---

## Cleaning Column Headers (`clean_columns`)

Systematically sanitize messy column headers in a deterministic sequence:
1. `strip`: Remove leading and trailing whitespace.
2. `strip_special`: Remove non-alphanumeric punctuation (except `_`).
3. `squeeze`: Collapse multiple consecutive spaces to a single space.
4. `fill[=STR]`: Replace spaces with a separator (e.g. `'_'`).
5. `case`: Transform casing (`'lower'`, `'upper'`, or `'proper'`).
6. `dedupe`: Auto-number duplicate headers (`col`, `col_1`, `col_2`).

```python
messy_df = pd.DataFrame(columns=["  Old Name % ", "Old Name %", "Status "])

clean_df = pt.clean_columns(
    messy_df,
    strip=True,
    strip_special=True,
    fill="_",
    case="lower",
    dedupe=True,
)
# Resulting columns: ['old_name', 'old_name_1', 'status']
```

---

## Replacing Cell Values (`replace_values`)

Replace cell values with automatic scoping and regex substring support:

```python
# Exact replacement scoped to a specific column
penguins.pt.replace_values({"Male": "M", "Female": "F"}, c="sex")

# Substring replacement across entire DataFrame
notes = pd.DataFrame({"text": ["a magician performed", "no match"]})
notes.pt.replace_values({"a magician": "the magic"}, exact=False)
```

---

## System Clipboard (`to_clip`)

Copy DataFrames or Series directly to the system clipboard without index columns:

```python
# Attached directly to DataFrame and Series upon importing pytae
penguins.head(10).to_clip()
```
Now paste directly into Excel, Google Sheets, or Slack as tab-separated values.
