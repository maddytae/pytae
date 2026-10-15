# Pytae — Missing Data Architecture & Core Philosophy

This document outlines Pytae's foundational philosophy regarding missing data, detailing the design, implementation, and behavior of `dropna` / `drop_nulls` across both the **Python Library API** and the **Command-Line Interface (CLI)**.

> [!NOTE]
> For complete documentation on reading files (`pt.read_parquet`, `pt.read_csv`, etc.), lazy scanning (`pt.scan_parquet`, `pt.scan_csv`, etc.), streaming sinks (`to_parquet`, `to_csv`), system clipboard, and supported file formats, see the **[Data Input & Output (I/O) Guide](library/io.md)**.

---

## Table of Contents

- [Core Philosophy: "Zero Data Loss by Default"](#core-philosophy-zero-data-loss-by-default)
- [How Pytae Compares to Pandas, Polars, and R/dplyr](#how-pytae-compares-to-pandas-polars-and-rdplyr)
  - [The Pandas Trap: Over-Aggressive Row Dropping](#the-pandas-trap-over-aggressive-row-dropping)
  - [The Polars Pitfall: Arrow Null vs. IEEE-754 Float NaN](#the-polars-pitfall-arrow-null-vs-ieee-754-float-nan)
  - [The R / dplyr Paradigm: Explicit Opt-In](#the-r--dplyr-paradigm-explicit-opt-in)
- [The "Option B" Specification](#the-option-b-specification)
  - [1. Bare Call: `how="all"` (Preserve Partial Rows)](#1-bare-call-howall-preserve-partial-rows)
  - [2. Targeted Call: `how="any"` (Enforce Required Keys)](#2-targeted-call-howany-enforce-required-keys)
  - [3. Explicit Overrides](#3-explicit-overrides)
  - [4. Dual Missing Value Cleaning (`drop_nans=True`)](#4-dual-missing-value-cleaning-drop_nanstrue)
- [Missing Values Inside Analytical Verbs](#missing-values-inside-analytical-verbs)
  - [Group Aggregations (`agg` / `-agg`)](#group-aggregations-agg---agg)
  - [2D Pivot Tables (`pivot` / `-pivot`)](#2d-pivot-tables-pivot---pivot)
  - [Frequency Tables (`freq` / `-freq`)](#frequency-tables-freq---freq)
  - [Feature Engineering (`mutate` / `-mutate`)](#feature-engineering-mutate---mutate)
  - [Arithmetic Invariance: Does `dropna` Change the `mean()`?](#arithmetic-invariance-does-dropna-change-the-mean)
- [Universal Aliasing & Full API Parity](#universal-aliasing--full-api-parity)
- [Comprehensive Examples: Python Library vs CLI](#comprehensive-examples-python-library-vs-cli)
  - [Example 1: Dropping Completely Blank Rows (Default)](#example-1-dropping-completely-blank-rows-default)
  - [Example 2: Dropping Rows Missing Critical Required Columns](#example-2-dropping-rows-missing-critical-required-columns)
  - [Example 3: Explicit Global Cleanup (`how="any"`)](#example-3-explicit-global-cleanup-howany)
  - [Example 4: Handling Float NaNs and Polars Nulls](#example-4-handling-float-nans-and-polars-nulls)
  - [Example 5: Pipeline Chaining with Aggregations](#example-5-pipeline-chaining-with-aggregations)
- [API Reference Summary](#api-reference-summary)

---

## Core Philosophy: "Zero Data Loss by Default"

In standard data science workflows, accidental data loss is one of the most common causes of skewed metrics, corrupted reporting, and incorrect modeling. A single missing optional field—such as a customer's secondary phone number or an optional shipping note—should **never** silently obliterate an entire multi-thousand-dollar transaction from a dataset.

Pytae adheres strictly to the principle of **Zero Data Loss by Default**:

1. **Conservative Row Elimination**: General cleanup operations only purge completely useless rows (i.e., rows where every single column is null/NaN).
2. **Intentional Filtering**: Rows are only filtered on specific columns when the user explicitly requests those columns or explicitly asks for `how="any"`.
3. **Preservation of NA Groups**: Analytical operations (`agg`, `pivot`, `freq`, `mutate`) retain missing/NA group categories rather than silently omitting them, ensuring you always know how much of your data lacks categorization.

---

## How Pytae Compares to Pandas, Polars, and R/dplyr

| Feature / Behavior | Pandas | Polars | R / dplyr | Pytae (Option B) |
|:---|:---|:---|:---|:---|
| **Bare Call (`df.dropna()`)** | Drops rows if *any* column is NA (`how='any'`) | Drops rows if *any* column is `null` | No global verb; requires `filter(!is.na(col))` or `tidyr::drop_na()` | **Drops only 100% blank rows (`how='all'`)** |
| **Float `NaN` vs Arrow `null`** | Conflates both into `np.nan` / `pd.NA` | Differentiates; `drop_nulls()` **ignores** `NaN`! | Treats `NA` and `NaN` distinctly | **Drops both `null` and `NaN` by default (`drop_nans=True`)** |
| **Analytical Verbs (`groupby`, `pivot`)** | `dropna=True` by default (drops NA groups!) | Preserves `null` group keys | `group_by()` preserves `NA` groups | **`dropna=False` by default (Zero Data Loss)** |
| **Targeted Columns (`df.dropna("a", "b")`)** | `subset=['a', 'b']`, drops if any is NA | `subset=['a', 'b']`, drops if any is null | `tidyr::drop_na(a, b)` | **Drops if any specified column is NA (`how='any'`)** |
| **CLI & Library Aliasing** | `dropna()` only | `drop_nulls()` only | `drop_na()` | **`dropna`, `drop_nulls`, `drop_na` (100% interchangeable)** |

### The Pandas Trap: Over-Aggressive Row Dropping
In Pandas, running `df.dropna()` without arguments defaults to `how="any"`. On wide real-world tables (e.g. 50+ columns), almost every row contains at least one optional missing value. A bare `df.dropna()` frequently drops **90% to 100% of valid business data** without warning.

Furthermore, in Pandas `df.groupby(...).mean()`, the default setting has historically been `dropna=True`, silently dropping all rows belonging to an unassigned or missing category.

### The Polars Pitfall: Arrow Null vs. IEEE-754 Float NaN
Polars adopts the Apache Arrow specification, which separates missingness into two distinct concepts:
- **`null`**: A bitmask indicating absence of data (applies to integers, strings, floats, dates, structs).
- **`NaN`**: A valid 64-bit IEEE-754 floating-point numerical value representing an invalid computation (e.g., `0.0 / 0.0`).

Calling `pl.DataFrame.drop_nulls()` **only drops Arrow `null`s**. It leaves float `NaN` values completely untouched in memory! When performing downstream arithmetic:
```python
# Polars native behavior:
pl.Series([10.0, float("nan")]).mean()  # Returns NaN! Float NaN poisons arithmetic!
```
Because `drop_nulls()` leaves `NaN` in place, users frequently encounter arithmetic poisoning.

### The R / dplyr Paradigm: Explicit Opt-In
In R's `tidyverse` (`dplyr`), data loss is prevented by design:
- `dplyr::group_by()` always preserves `NA` groups as a distinct category.
- Summaries do not drop missing data silently; functions require explicit opt-in (e.g., `mean(x, na.rm = TRUE)`).
- `tidyr::drop_na()` is used when row dropping is explicitly desired.

Pytae adopts the best of the R philosophy combined with high-performance vector execution in Polars.

---

## The "Option B" Specification

Pytae implements **Option B** across the entire library and CLI.

### 1. Bare Call: `how="all"` (Preserve Partial Rows)
When called without column arguments, `dropna` operates as a safe table-cleaning sweep:
```python
# Python
clean_df = df.dropna()
# or
clean_df = df.drop_nulls()
```
```bash
# CLI
pytae data.parquet -dropna
# or
pytae data.parquet -drop_nulls
```
- **Behavior**: Drops **only** rows where every single column is null/NaN.
- **Outcome**: Valid rows with partial missing values remain intact. No business data is lost.

### 2. Targeted Call: `how="any"` (Enforce Required Keys)
When one or more columns are explicitly specified, `dropna` treats them as mandatory:
```python
# Python
clean_df = df.dropna("customer_id", "order_date")
# or
clean_df = df.drop_nulls("customer_id", "order_date")
```
```bash
# CLI
pytae data.parquet -dropna "customer_id, order_date"
# or
pytae data.parquet -drop_nulls "customer_id, order_date"
```
- **Behavior**: Drops any row where *at least one* of the specified columns is missing.
- **Outcome**: Guarantees that the resulting dataset contains complete, non-null values for the required fields.

### 3. Explicit Overrides
You can explicitly override the default `how` parameter at any time:
```python
# Python: Force drop any row with ANY null across the entire dataframe
df.dropna(how="any")

# Python: Drop only if BOTH specified columns are null
df.dropna("phone", "email", how="all")
```
```bash
# CLI: Explicit how=any across entire dataframe
pytae data.parquet -dropna how=any

# CLI: Drop only if both specified columns are missing
pytae data.parquet -dropna "phone, email, how=all"
```

### 4. Dual Missing Value Cleaning (`drop_nans=True`)
Pytae bridges Arrow `null` and IEEE-754 `NaN`. By default (`drop_nans=True`), Pytae inspects the column data types in the schema:
- For floating-point columns (`Float32`, `Float64`), it builds an expression combining `.is_null() | .is_nan()`.
- For all other columns (strings, ints, dates, booleans), it checks `.is_null()`.
- If you specifically need to preserve IEEE-754 float `NaN` values while only purging Arrow nulls, pass `drop_nans=False` (or `nans=false` in the CLI).

---

## Missing Values Inside Analytical Verbs

Pytae maintains consistent "Zero Data Loss by Default" across all analytical operations.

### Group Aggregations (`agg` / `-agg`)
When grouping data using `.pt.by("region")` or CLI `-by region -agg ...`:
- **Default**: `dropna=False` / `drop_nulls=False`.
- **Effect**: Rows where `region` is `null` form their own grouping category (e.g. `null | count=12 | sum=1500`).
- **Override**: Pass `dropna=True` or `drop_nulls=True` inside `agg(...)` or `-agg "sum, dropna=true"` to omit null groups.

### 2D Pivot Tables (`pivot` / `-pivot`)
When pivoting data into cross-tabulations:
- **Default**: `dropna=False` / `drop_nulls=False`.
- **Effect**: If the row (`r`) or column (`c`) variables contain `null`s, they are included as their own row or column in the pivot table, preventing invisible row drops.
- **Override**: Pass `dropna=True` or `drop_nulls=True` inside `pivot(...)` or `-pivot "..., dropna=true"`.

### Frequency Tables (`freq` / `-freq`)
When generating categorical distributions:
- **Default**: `dropna=False`.
- **Effect**: Null/NaN entries are displayed as an explicit `NA` category with their frequency count and percentage.
- **Override**: Pass `dropna=True` or CLI `-freq col, dropna=true`.

### Feature Engineering (`mutate` / `-mutate`)
When creating calculated columns:
- **Default**: `dropna=False`.
- **Effect**: Window functions and grouped computations evaluate across the `null` group just like any other group.

### Arithmetic Invariance: Does `dropna` Change the `mean()`?

A common question is: *If I calculate the mean of a column, does calling `dropna` first change the mathematical answer?*

#### Case 1: Single-Column Metric (Invariant)
$$\bar{x} = \frac{\sum_{i=1}^N x_i}{N}$$
In both Polars and Pandas, `mean()` inherently divides the sum of non-null values by the count of non-null values ($N$). 
If a column contains `[10, 20, null]`, the mean is:
$$\frac{10 + 20}{2} = 15.0$$
Dropping the `null` beforehand leaves `[10, 20]`, whose mean is also $15.0$. **The numeric result is identical.**

#### Case 2: Multi-Column Cross-Contamination (Catastrophic Data Loss)
The danger arises when dropping rows across multiple columns (e.g., Pandas' default `df.dropna()`):
Suppose you have:
| sales | feedback_notes |
|:---|:---|
| 1000 | "Great service" |
| 5000 | `null` |
| 2000 | "Will return" |

If you run Pandas `df.dropna()` before computing `df["sales"].mean()`:
- Row 2 is dropped simply because `feedback_notes` is null!
- The mean of `sales` changes from $\frac{1000 + 5000 + 2000}{3} = 2666.67$ to $\frac{1000 + 2000}{2} = 1500.00$.
- **You have introduced massive statistical bias and data loss.**

Pytae's Option B prevents this disaster entirely:
- Calling `df.dropna()` bare preserves Row 2 because it is not 100% blank.
- `df["sales"].mean()` accurately computes $2666.67$.

---

## Universal Aliasing & Full API Parity

Pytae provides complete 100% interchangeability across terminology:

| Operation | Canonical | Aliases |
|:---|:---|:---|
| **Python Function** | `pt.dropna(df, ...)` | `pt.drop_nulls(df, ...)`, `pt.drop_na(df, ...)` |
| **DataFrame Method** | `df.dropna(...)` | `df.drop_nulls(...)`, `df.drop_na(...)` |
| **Grouped DataFrame** | `df.pt.by(...).dropna(...)` | `df.pt.by(...).drop_nulls(...)`, `df.pt.by(...).drop_na(...)` |
| **Accessor Method** | `df.pt.dropna(...)` | `df.pt.drop_nulls(...)`, `df.pt.drop_na(...)` |
| **CLI Flags** | `pytae file -dropna` | `pytae file -drop_nulls`, `pytae file -drop_na` |
| **Keyword Arguments** | `dropna=True` | `drop_nulls=True` (in `agg`, `pivot`, etc.) |

---

## Comprehensive Examples: Python Library vs CLI

### Example 1: Dropping Completely Blank Rows (Default)

#### Python API
```python
import pytae as pt

# Lazy scan or eager DataFrame
df = pt.read_parquet("transactions.parquet")

# Drops ONLY rows where all columns are null or NaN
clean_df = df.dropna()
# Exactly identical to:
clean_df = df.drop_nulls()
```

#### CLI
```bash
# Bare flag defaults to how='all'
pytae transactions.parquet -dropna -shape

# Using the Polars alias
pytae transactions.parquet -drop_nulls -shape
```

---

### Example 2: Dropping Rows Missing Critical Required Columns

#### Python API
```python
import pytae as pt

df = pt.read_parquet("penguins.parquet")

# Drops rows where body_mass_g OR sex is missing (how='any' on specified subset)
complete_cases = df.dropna("body_mass_g", "sex")

# Accessor style
complete_cases = df.pt.dropna("body_mass_g", "sex")
```

#### CLI
```bash
# Drop rows where body_mass_g is missing (344 -> 342 rows)
pytae penguins.parquet -dropna body_mass_g -shape

# Multiple required columns
pytae penguins.parquet -drop_nulls "body_mass_g, sex" -shape
```

---

### Example 3: Explicit Global Cleanup (`how="any"`)

#### Python API
```python
import pytae as pt

df = pt.read_parquet("penguins.parquet")

# Drops any row that contains ANY null or NaN in ANY column (344 -> 333 rows)
strict_complete = df.dropna(how="any")
```

#### CLI
```bash
# Explicit how=any flag
pytae penguins.parquet -dropna how=any -shape

# Or with drop_nulls
pytae penguins.parquet -drop_nulls how=any -shape
```

---

### Example 4: Handling Float NaNs and Polars Nulls

#### Python API
```python
import polars as pl
import pytae as pt

# Dataset containing both Arrow null and IEEE-754 float NaN
raw_data = pl.DataFrame({"id": [1, 2, 3, 4], "value": [10.5, None, float("nan"), 40.0]})

df = pt.DataFrame(raw_data)

# By default, drop_nans=True cleans BOTH None (null) and float('nan')
clean = df.dropna("value")
# Result contains: [10.5, 40.0] (2 rows)

# If you explicitly want to keep float('nan') and only drop Arrow nulls:
keep_nans = df.dropna("value", drop_nans=False)
# Result contains: [10.5, nan, 40.0] (3 rows)
```

#### CLI
```bash
# Cleans both null and NaN by default
pytae measurements.csv -dropna value

# Retain float NaNs while dropping nulls
pytae measurements.csv -dropna "value, drop_nans=false"
```

---

### Example 5: Pipeline Chaining with Aggregations

#### Python API
```python
import pytae as pt

penguins = pt.sample("penguins")

# Drop rows missing body mass, group by species, and aggregate
result = penguins.pt.dropna("body_mass_g").pt.by("species").pt.agg(count="n", avg_mass="mean(body_mass_g)")
print(result)
```

#### CLI
```bash
pytae penguins.parquet \
  -dropna body_mass_g \
  -by species \
  -agg "count = n, avg_mass = mean(body_mass_g)"
```

**Output:**
```
species    count    avg_mass
Adelie       151     3700.66
Chinstrap     68     3733.09
Gentoo       123     5076.02
```

---

## API Reference Summary

### Function: `pt.dropna` / `pt.drop_nulls` / `pt.drop_na`
```python
pt.dropna(
    df: DataFrame | pl.DataFrame | pd.DataFrame,
    *cols: str,
    how: str | None = None,
    drop_nans: bool = True,
) -> DataFrame
```
- **`df`**: Input table (Pytae DataFrame, Polars DataFrame/LazyFrame, or Pandas DataFrame).
- **`*cols`**: Optional column names to inspect.
- **`how`**: `'all'` or `'any'`. If omitted, defaults to `'all'` when `cols` is empty, or `'any'` when `cols` is specified.
- **`drop_nans`**: `bool` (default `True`). When `True`, drops float IEEE-754 `NaN`s in addition to Arrow `null`s.

### Method: `DataFrame.dropna` / `DataFrame.drop_nulls` / `DataFrame.drop_na`
```python
df.dropna(*cols: str, how: str | None = None, drop_nans: bool = True) -> DataFrame
```

### CLI Flag: `-dropna` / `-drop_nulls` / `-drop_na`
```bash
pytae <path> -dropna [SPEC]
```
- Bare `-dropna` $\rightarrow$ `how="all"` (Zero Data Loss).
- `-dropna "col1, col2"` $\rightarrow$ `how="any"` on specified columns.
- `-dropna how=any` $\rightarrow$ Drops rows with any missing value across all columns.
- `-dropna "col1, how=all"` $\rightarrow$ Drops row only if all listed columns are missing.
- `-dropna "col1, drop_nans=false"` $\rightarrow$ Preserves float NaNs.

