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

> [!TIP]
> **Column Scoping in Aggregations**:
> - **Direct named targets**: When you declare specific columns inside `-agg` (e.g. `-by species -agg "body_mass_g=mean, n=n"`), pytae automatically restricts the output to those columns and the grouping keys without needing a pre-`-select`.
> - **Bulk aggregations & column pruning**: When using bulk functions (e.g. `-agg mean` across all numeric columns) or working with wide files where you want to load only relevant columns into RAM, using `-select` beforehand (e.g. `-select "species,contains=mass" -by species -agg mean`) is completely valid and recommended for performance.

### Single Function across Numeric Columns

Average body mass by species (specify the metric directly in `-agg` without a pre-`-select`):

```bash
pytae penguins.parquet -by species -agg body_mass_g=mean -round 1
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |        3700.7 |
| Chinstrap |        3733.1 |
| Gentoo    |        5076   |

### Multiple Functions (`"mean,n"`)

Compute mean and sample size simultaneously:

```bash
pytae penguins.parquet -by species -agg "body_mass_g=mean, n=n" -round 1
```

**Output:**

| species   |   body_mass_g |   n |
|:----------|--------------:|----:|
| Adelie    |        3700.7 | 152 |
| Chinstrap |        3733.1 |  68 |
| Gentoo    |        5076   | 124 |

### Column-Specific Mapping

Assign different aggregate functions to specific columns:

```bash
pytae penguins.parquet \
  -by species \
  -agg "body_mass_g = mean, flipper_length_mm = max, n = n" \
  -round 1
```

**Output:**

| species | body_mass_g | flipper_length_mm | n |
|:---|---:|---:|---:|
| Adelie | 3700.7 | 210.0 | 152 |
| Chinstrap | 3733.1 | 212.0 | 68 |
| Gentoo | 5076.0 | 231.0 | 124 |

### Named Outputs (`total = col:aggfunc`)

Rename aggregated outputs cleanly using `new_name = col:aggfunc`:

```bash
pytae penguins.parquet \
  -by species \
  -agg "avg_mass = body_mass_g:mean, max_mass = body_mass_g:max, count = n" \
  -round 1
```

**Output:**

| species   |   avg_mass |   max_mass |   count |
|:----------|-----------:|-----------:|--------:|
| Adelie    |     3700.7 |       4775 |     152 |
| Chinstrap |     3733.1 |       4800 |      68 |
| Gentoo    |     5076   |       6300 |     124 |

### Columns with Spaces (`[col]`)

Columns with spaces can be enclosed in square brackets `[col]` anywhere in `-by` and `-agg`:

```bash
pytae tips.parquet \
  -filter "day = ['Sat', 'Sun'], time = 'Dinner', size >= 2, total_bill > 10" \
  -rename "total_bill:[total bill]" \
  -by smoker \
  -agg "tip = mean, [total bill] = mean, n = n"
```

**Output:**

| smoker   |     tip |   total bill |   n |
|:---------|--------:|-------------:|----:|
| No       | 3.22546 |      20.7059 |  97 |
| Yes      | 3.08772 |      23.2323 |  57 |

Multiple grouping columns can be passed comma-separated: `-by "species,island"` or `-by "[group a],[group b]"`.

---

## Whole-Table Summaries (Grand Totals)

Omit `-by` to compute a grand total across all rows (producing a 1-row summary):

```bash
pytae penguins.parquet -agg "body_mass_g = mean, count = n" -round 1
```

**Output:**

|   body_mass_g |   count |
|--------------:|--------:|
|        4201.8 |     344 |

Or compute an aggregation across all numeric columns at once:

```bash
pytae penguins.parquet -agg mean -round 1
```

**Output:**

| bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g |
|---:|---:|---:|---:|
| 43.9 | 17.2 | 200.9 | 4201.8 |

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

| species   | sex    |   body_mass_g |   max_mass |   diff |
|:----------|:-------|--------------:|-----------:|-------:|
| Adelie    | Male   |          3750 |       4775 |  -1025 |
| Adelie    | Female |          3800 |       4775 |   -975 |
| Adelie    | Female |          3250 |       4775 |  -1525 |
| Adelie    | nan    |           nan |       4775 |    nan |

For more examples including group counts (`n`), multi-column grouping, and spaced column names, see the [Mutating & Computing Guide](mutate.md#grouped-mutations--by--mutate).


---

## Handling Missing Group Keys (`dropna`)

By default, missing values (`NaN`) in group columns form their own group (`dropna=false`) to prevent silent data loss:

```bash
# Keep missing sex as its own group (default)
pytae penguins.parquet -by sex -agg "body_mass_g=mean, dropna=false" -round 1
```

**Output:**

| sex | body_mass_g |
|:---|---:|
| Female | 3862.3 |
| Male | 4545.7 |
| NaN | 4005.6 |

To drop rows with missing group keys, either specify `dropna=true` inside the `-agg` mapping or chain the top-level `-dropna` flag:

```bash
# In-spec dropna=true
pytae penguins.parquet -by sex -agg "body_mass_g=mean, dropna=true" -round 1
```

**Output:**

| sex | body_mass_g |
|:---|---:|
| Female | 3862.3 |
| Male | 4545.7 |

```bash
# Or chain -dropna beforehand
pytae penguins.parquet -dropna sex -by sex -agg mean -round 1
```

**Output:**

| sex | bill_length_mm | bill_depth_mm | flipper_length_mm | body_mass_g |
|:---|---:|---:|---:|---:|
| Female | 42.1 | 16.4 | 197.4 | 3862.3 |
| Male | 45.9 | 17.9 | 204.5 | 4545.7 |
