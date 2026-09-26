# CLI Feature Guide: Aggregations & Grouping

Group, aggregate, and broadcast statistics using pytae's auto-grouping (`-agg_df`), explicit aggregations (`-group_by` + `-agg`), and broadcast transforms (`-group_x`).

---

## Contents

- [Overview & Differences](#overview--differences)
- [Auto-Grouping Aggregations (`-agg_df`)](#auto-grouping-aggregations--agg_df)
  - [Single Function](#single-function)
  - [Multiple Functions (`"mean,n"`)](#multiple-functions-meann)
  - [Column-Specific Mapping](#column-specific-mapping)
- [Explicit Grouping (`-group_by` + `-agg`)](#explicit-grouping--group_by--agg)
- [Broadcast Group Transforms (`-group_x`)](#broadcast-group-transforms--group_x)
- [Handling Missing Group Keys (`-dropna`)](#handling-missing-group-keys--dropna)

---

## Overview & Differences

| Flag | Group Columns | Numeric Columns | Collapses Rows? | Description |
|---|---|---|---|---|
| `-agg_df [SPEC]` | **Auto-detected** (all non-numeric) | Aggregated | **Yes** | Zero-config aggregation |
| `-group_by` + `-agg` | Explicitly declared | Specific columns | **Yes** | Named outputs (`as=`) |
| `-group_x [SPEC]` | Explicit or auto | Target column (`v=`) | **No** | Appends column without collapsing |

---

## Auto-Grouping Aggregations (`-agg_df`)

Pytae automatically detects non-numeric columns as grouping dimensions and applies the aggregate function to all numeric columns. Defaults to `sum`.

Supported function names: `mean`, `sum`, `std`, `min`, `max`, `median`, `n` (row count).

### Single Function

Average body mass by species:

```bash
pytae penguins.parquet -select "species,body_mass_g" -agg_df mean -round 1
```

**Output:**
```text
  species  body_mass_g
   Adelie       3700.7
Chinstrap       3733.1
   Gentoo       5076.0
```

### Multiple Functions (`"mean,n"`)

Compute mean and sample size simultaneously:

```bash
pytae penguins.parquet -select "species,body_mass_g" -agg_df "mean,n" -round 1
```

**Output:**
```text
  species   n  body_mass_g
   Adelie 152       3700.7
Chinstrap  68       3733.1
   Gentoo 124       5076.0
```

### Column-Specific Mapping

Assign different aggregate functions to different columns:

```bash
pytae penguins.parquet \
  -select "species,body_mass_g,flipper_length_mm" \
  -agg_df "body_mass_g = mean, flipper_length_mm = max, n = n" \
  -round 1
```

---

## Explicit Grouping (`-group_by` + `-agg`)

For fine-grained control with custom output column names via `as=`:

Syntax:
```bash
pytae penguins.parquet \
  -group_by "species" \
  -agg "column=body_mass_g,aggfunc=mean,as=avg_mass;column=body_mass_g,aggfunc=max,as=max_mass" \
  -round 1
```

**Output:**
```text
  species  avg_mass  max_mass
   Adelie    3700.7    4775.0
Chinstrap    3733.1    4800.0
   Gentoo    5076.0    6300.0
```

Multiple specs are separated by semicolons `;`.

---

## Broadcast Group Transforms (`-group_x`)

Appends group statistics back to every individual row without collapsing the dataset (equivalent to Pandas `transform` or SQL `OVER (PARTITION BY ...)`):

Parameters:
- `group=`: Grouping columns (defaults to non-numeric).
- `v=`: Target value column to aggregate.
- `a=`: Aggregate function (default: `n` for group size).

```bash
# Calculate maximum species mass and broadcast as column 'x'
pytae penguins.parquet \
  -select "species,sex,body_mass_g" \
  -group_x "group=species,v=body_mass_g,a=max" \
  -head 4
```

**Output:**
```text
species    sex  body_mass_g      x
 Adelie   Male       3750.0 4775.0
 Adelie Female       3800.0 4775.0
 Adelie Female       3250.0 4775.0
 Adelie    NaN          NaN 4775.0
```

---

## Handling Missing Group Keys (`-dropna`)

By default, missing values (`NaN`) in group columns are excluded from groupings (`-dropna true`). To retain rows with missing group keys:

```bash
pytae penguins.parquet -agg_df mean -dropna false
```
