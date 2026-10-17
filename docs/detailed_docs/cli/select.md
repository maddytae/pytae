# CLI Feature Guide: Column Selection

[← Back to Master Reference](../../pytae.md)

Select, filter, reorder, and exclude columns using names, negative prefixes, ranges, pattern matching, or data types with `-select`.

---

## Contents

- [Overview](#overview)
- [Selecting Explicit Columns](#selecting-explicit-columns)
- [Negative Selection & Exclusion (`-col`, `~col`, `exclude=`)](#negative-selection--exclusion)
- [Slice Notation (`start:end`)](#slice-notation-startend)
- [Pattern Matching (`contains=`, `startswith=`, `endswith=`, `regex=`)](#pattern-matching)
- [Data Type Filtering (`dtype=`, `exclude_dtype=`)](#data-type-filtering)
- [Chaining `-select` in Pipelines](#chaining--select-in-pipelines)

---

## Overview

`-select` provides unified column management across the entire CLI pipeline, matching the Python library's `pt.select()` verb.

| Capability | Syntax / Flag | Example |
|---|---|---|
| Explicit names | `col1,col2` | `-select "species,island,body_mass_g"` |
| Negative selection | `-col` or `~col` | `-select "-species"` or `-select "~island"` |
| Negative slices | `-start:end` | `-select "-bill_length_mm:flipper_length_mm"` |
| Keyword exclusion | `exclude=col` | `-select "exclude=species"` |
| Column slice | `start:end` | `-select "bill_length_mm:body_mass_g"` |
| Substring / prefix / suffix | `contains=`, `startswith=`, `endswith=` | `-select "contains=bill"` |
| Regular expression | `regex=PATTERN` | `-select "regex=^bill_.*mm$"` |
| Data type filter | `dtype=numeric` / `exclude_dtype=category` | `-select "dtype=numeric"` |

---

## Selecting Explicit Columns

List column names separated by commas. The output DataFrame columns are ordered exactly as listed in the `-select` argument:

```bash
pytae penguins.parquet -select "species,island,body_mass_g" -head 3
```

**Output:**

| species   | island    |   body_mass_g |
|:----------|:----------|--------------:|
| Adelie    | Torgersen |          3750 |
| Adelie    | Torgersen |          3800 |
| Adelie    | Torgersen |          3250 |

Reorder columns on the fly:
```bash
pytae penguins.parquet -select "body_mass_g,species" -head 3
```

**Output:**

|   body_mass_g | species   |
|--------------:|:----------|
|          3750 | Adelie    |
|          3800 | Adelie    |
|          3250 | Adelie    |

---

<a id="negative-selection--exclusion"></a>
## Negative Selection & Exclusion (`-col`, `~col`, `exclude=`)

You can exclude specific columns, combinations, or slices directly within `-select`. Remaining columns preserve their original relative order.

### Negated Column Names (`-col` or `~col`)

Prefix a column name with `-` or `~` to exclude it:

```bash
pytae penguins.parquet -select "-species" -head 3
```

**Output:**

| island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

Multiple negated columns can be combined in quotes:
```bash
pytae penguins.parquet -select "-species, -island, -sex" -head 3
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |

### Negated Slices (`-start:end`)

Exclude a contiguous range of columns:
```bash
pytae penguins.parquet -select "-bill_length_mm:flipper_length_mm" -head 3
```

**Output:**

| species   | island    |   body_mass_g | sex    |
|:----------|:----------|--------------:|:-------|
| Adelie    | Torgersen |          3750 | Male   |
| Adelie    | Torgersen |          3800 | Female |
| Adelie    | Torgersen |          3250 | Female |

### Keyword Exclusion (`exclude=`)

Use the `exclude=` parameter to exclude one or more columns:
```bash
pytae penguins.parquet -select "exclude=species" -head 3
```

**Output:**

| island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

---

## Slice Notation (`start:end`)

Select a contiguous range of columns from `start` up to and including `end` (using pandas column position order):

```bash
pytae penguins.parquet -select "bill_length_mm:body_mass_g" -head 3
```

**Output:**

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |

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

|   bill_length_mm |   bill_depth_mm |
|-----------------:|----------------:|
|             39.1 |            18.7 |
|             39.5 |            17.4 |
|             40.3 |            18   |

### Combining names with pattern tokens

```bash
pytae penguins.parquet -select "species,contains=bill" -head 3
```

**Output:**

| species   |   bill_length_mm |   bill_depth_mm |
|:----------|-----------------:|----------------:|
| Adelie    |             39.1 |            18.7 |
| Adelie    |             39.5 |            17.4 |
| Adelie    |             40.3 |            18   |

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

|   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|----------------:|--------------------:|--------------:|
|             39.1 |            18.7 |                 181 |          3750 |
|             39.5 |            17.4 |                 186 |          3800 |
|             40.3 |            18   |                 195 |          3250 |

---

## Chaining `-select` in Pipelines

`-select` can be repeated across intermediate pipeline steps (e.g. after `-mutate` or `-agg`), or chained sequentially to filter then subtract:

```bash
# Select numeric columns, then subtract bill_depth_mm
pytae penguins.parquet -select "dtype=numeric" -select "-bill_depth_mm" -head 3
```

**Output:**

|   bill_length_mm |   flipper_length_mm |   body_mass_g |
|-----------------:|--------------------:|--------------:|
|             39.1 |                 181 |          3750 |
|             39.5 |                 186 |          3800 |
|             40.3 |                 195 |          3250 |

```bash
# Narrowing output columns after an aggregation
pytae penguins.parquet \
  -by species \
  -agg "avg_mass = body_mass_g:mean, total = n" \
  -select "species,avg_mass"
```

**Output:**

| species   |   avg_mass |
|:----------|-----------:|
| Adelie    |    3700.66 |
| Chinstrap |    3733.09 |
| Gentoo    |    5076.02 |
