# CLI Feature Guide: Column Selection & Dropping

Select, filter, reorder, and subtract columns using names, ranges, pattern matching, or data types with `-select` and `-drop`.

---

## Contents

- [Overview & Differences](#overview--differences)
- [Selecting Explicit Columns](#selecting-explicit-columns)
- [Slice Notation (`start:end`)](#slice-notation-startend)
- [Pattern Matching (`contains=`, `startswith=`, `endswith=`, `regex=`)](#pattern-matching)
- [Data Type Filtering (`dtype=`, `exclude_dtype=`)](#data-type-filtering)
- [Dropping Columns (`-drop`)](#dropping-columns--drop)
- [Polarity Chaining (`-select` vs `-drop`)](#polarity-chaining)
- [Repeating `-select` in Pipelines](#repeating--select-in-pipelines)

---

## Overview & Differences

| Flag | Description | Reorders Columns? | Accepts Patterns / Dtypes? |
|---|---|---|---|
| `-select SPEC` | Keeps specified columns (union of tokens in SPEC) | **Yes** (matches order in SPEC) | **Yes** (`contains=`, `dtype=`, etc.) |
| `-drop COLUMNS` | Removes specified exact column names | **No** (preserves original file order) | **No** (exact comma-separated names only) |

---

## Selecting Explicit Columns

List column names separated by commas. The output DataFrame columns are ordered exactly as listed in the `-select` argument:

```bash
pytae penguins.parquet -select "species,island,body_mass_g" -head 3
```

**Output:**
```text
species    island  body_mass_g
 Adelie Torgersen       3750.0
 Adelie Torgersen       3800.0
 Adelie Torgersen       3250.0
```

Reorder columns on the fly:
```bash
pytae penguins.parquet -select "body_mass_g,species" -head 3
```

---

## Slice Notation (`start:end`)

Select a contiguous range of columns from `start` up to and including `end` (using pandas column position order):

```bash
pytae penguins.parquet -select "bill_length_mm:body_mass_g" -head 3
```

**Output:**
```text
 bill_length_mm  bill_depth_mm  flipper_length_mm  body_mass_g
           39.1           18.7              181.0       3750.0
           39.5           17.4              186.0       3800.0
           40.3           18.0              195.0       3250.0
```

---

## Pattern Matching

Match column names dynamically without typing every name:

| Token | Description | Example |
|---|---|---|
| `contains=TEXT` | Column names containing `TEXT` | `contains=bill` |
| `startswith=PREFIX` | Column names starting with `PREFIX` | `startswith=bill_` |
| `endswith=SUFFIX` | Column names ending with `SUFFIX` | `endswith=_mm` |
| `regex=PATTERN` | Column names matching regular expression | `regex=^bill_.*mm$` |

### Example: Contains

```bash
pytae penguins.parquet -select "contains=bill" -head 3
```

**Output:**
```text
 bill_length_mm  bill_depth_mm
           39.1           18.7
           39.5           17.4
           40.3           18.0
```

### Combining names with pattern tokens

```bash
pytae penguins.parquet -select "species,contains=bill" -head 3
```

---

## Data Type Filtering

Select or exclude columns by data type:

| Token | Description |
|---|---|
| `dtype=numeric` | Numeric columns (`int64`, `float64`, etc.) |
| `dtype=object` / `dtype=str` | String or object columns |
| `dtype=datetime` | Datetime / timestamp columns |
| `exclude_dtype=category` | Exclude categorical columns |

### Example: Numeric Only

```bash
pytae penguins.parquet -select "dtype=numeric" -head 3
```

**Output:**
```text
 bill_length_mm  bill_depth_mm  flipper_length_mm  body_mass_g
           39.1           18.7              181.0       3750.0
           39.5           17.4              186.0       3800.0
           40.3           18.0              195.0       3250.0
```

---

## Dropping Columns (`-drop`)

Drop one or more columns by exact name. Remaining columns preserve their original relative order:

```bash
pytae penguins.parquet -drop "sex,island" -head 3
```

**Output:**
```text
species  bill_length_mm  bill_depth_mm  flipper_length_mm  body_mass_g
 Adelie            39.1           18.7              181.0       3750.0
 Adelie            39.5           17.4              186.0       3800.0
 Adelie            40.3           18.0              195.0       3250.0
```

---

## Polarity Chaining

Combine positive selection (`-select`) with negative subtraction (`-drop`) in a sequential pipeline:

```bash
# 1. Select all numeric columns
# 2. Subtract bill_depth_mm
pytae penguins.parquet -select "dtype=numeric" -drop "bill_depth_mm" -head 3
```

**Output:**
```text
 bill_length_mm  flipper_length_mm  body_mass_g
           39.1              181.0       3750.0
           39.5              186.0       3800.0
           40.3              195.0       3250.0
```

---

## Repeating `-select` in Pipelines

`-select` can be repeated across intermediate pipeline steps (e.g. after `-mutate` or `-agg_df`):

```bash
pytae penguins.parquet \
  -mutate "mass_kg = body_mass_g / 1000" \
  -select "species,mass_kg" \
  -agg_df mean
```
