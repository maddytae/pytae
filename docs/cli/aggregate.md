# CLI Feature Guide: Aggregations & Grouping

[← Back to CLI Reference Hub](../cli.md)

Group, aggregate, and calculate window statistics using pytae's unified `-by` + `-agg` framework and grouped mutations (`-by` + `-mutate`).

---

## Contents

- [Overview & Differences](#overview--differences)
- [Group Aggregations (`-by` + `-agg`)](#group-aggregations--by--agg)
  - [Single Function across Numeric Columns](#single-function-across-numeric-columns)
  - [Multiple Functions (`"mean,n"`)](#multiple-functions-meann)
  - [Column-Specific Mapping](#column-specific-mapping)
  - [Named Outputs (`total = col:aggfunc`)](#named-outputs-total--colaggfunc)
- [Whole-Table Summaries (Grand Totals)](#whole-table-summaries-grand-totals)
- [Grouped Transforms (`-by` + `-mutate`)](#grouped-transforms--by--mutate)
- [Handling Missing Group Keys (`-dropna`)](#handling-missing-group-keys--dropna)

---

## Overview & Differences

| Flag | Group Columns | Numeric Columns | Collapses Rows? | Description |
|---|---|---|---|---|
| `-by COLS -agg [SPEC]` | Declared via `-by` | Aggregated | **Yes** | Group summary ($N \to K$ rows) |
| `-agg [SPEC]` (no `-by`) | None (whole table) | Aggregated | **Yes** | Grand total (1 row) |
| `-by COLS -mutate "..."` | Declared via `-by` | Evaluated per group | **No** | Window transform without collapsing ($N \to N$ rows) |

---

<a id="group-aggregations--by--agg"></a>
## Group Aggregations (`-by` + `-agg`)

Specify grouping column(s) with `-by` (or `--by`), and aggregation function(s) with `-agg` (or `--agg`). Defaults to `sum` if `-agg` is given without an argument.

Supported function names: `mean`, `sum`, `std`, `min`, `max`, `median`, `n` (row count), etc.

### Single Function across Numeric Columns

Average body mass by species:

```bash
pytae penguins.parquet -select "species,body_mass_g" -by species -agg mean -round 1
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
pytae penguins.parquet -select "species,body_mass_g" -by species -agg "mean,n" -round 1
```

**Output:**
```text
  species   n  body_mass_g
   Adelie 152       3700.7
Chinstrap  68       3733.1
   Gentoo 124       5076.0
```

### Column-Specific Mapping

Assign different aggregate functions to specific columns:

```bash
pytae penguins.parquet \
  -by species \
  -agg "body_mass_g = mean, flipper_length_mm = max, n = n" \
  -round 1
```

### Named Outputs (`total = col:aggfunc`)

Rename aggregated outputs cleanly using `new_name = col:aggfunc`:

```bash
pytae penguins.parquet \
  -by species \
  -agg "avg_mass = body_mass_g:mean, max_mass = body_mass_g:max, count = n" \
  -round 1
```

**Output:**
```text
  species  avg_mass  max_mass  count
   Adelie    3700.7    4775.0    152
Chinstrap    3733.1    4800.0     68
   Gentoo    5076.0    6300.0    124
```

### Columns with Spaces (`[col]`)

Columns with spaces can be enclosed in square brackets `[col]` anywhere in `-by` and `-agg`:

```bash
pytae tips.parquet \
  -qry "day in ['Sat', 'Sun'], time = 'Dinner', size >= 2, total_bill > 10" \
  -select "smoker, tip, total_bill" \
  -rename "total_bill:[total bill]" \
  -by smoker \
  -agg "tip = mean, [total bill] = mean, n = n"
```

**Output:**
```text
smoker      tip  total bill  n
   Yes 3.087719   23.232281 57
    No 3.225464   20.705876 97
```

Multiple grouping columns can be passed comma-separated: `-by "species,island"` or `-by "[group a],[group b]"`.

---

## Whole-Table Summaries (Grand Totals)

Omit `-by` to compute a grand total across all rows (producing a 1-row summary):

```bash
pytae penguins.parquet -agg "body_mass_g = mean, count = n" -round 1
```

**Output:**
```text
  body_mass_g  count
       4201.8    344
```

Or compute an aggregation across all numeric columns at once:

```bash
pytae penguins.parquet -agg mean -round 1
```

---

<a id="grouped-transforms--by--mutate"></a>
## Grouped Transforms (`-by` + `-mutate`)

Appends group statistics and window calculations back to every individual row without collapsing the dataset (equivalent to Pandas `transform` or SQL `OVER (PARTITION BY ...)`).

Grouped mutations are evaluated per group by combining `-by` with `-mutate`:
- Available aggregations in `-mutate`: `mean(col)`, `sum(col)`, `median(col)`, `min(col)`, `max(col)`, `std(col)`, `var(col)`, `n` (or `n()`).
- Multiple sequential calculations can be combined in one `-mutate` flag.
- Custom target column names are supported freely.

```bash
# Calculate maximum species mass and deviation from maximum without collapsing rows
pytae penguins.parquet \
  -select "species,sex,body_mass_g" \
  -by species \
  -mutate "max_mass = max(body_mass_g), diff = body_mass_g - max_mass" \
  -head 4
```

**Output:**
```text
species    sex  body_mass_g  max_mass    diff
 Adelie   Male       3750.0    4775.0 -1025.0
 Adelie Female       3800.0    4775.0  -975.0
 Adelie Female       3250.0    4775.0 -1525.0
 Adelie    NaN          NaN    4775.0     NaN
```

For more examples including group counts (`n`), multi-column grouping, and spaced column names, see the [Mutating & Computing Guide](mutate.md#grouped-mutations--by--mutate).


---

## Handling Missing Group Keys (`-dropna`)

By default, missing values (`NaN`) in group columns form their own group (`-dropna false`) to prevent silent data loss. To exclude rows with missing group keys:

```bash
pytae penguins.parquet -by sex -agg mean -dropna true
```
