# `agg` — Reference

[← Back to Library Reference Hub](../library.md)


`agg` aggregates numeric columns with grouping inherited from standalone `pt.by()` (or computes a whole-table summary when no grouping is set).

### Calling Styles

1. **Grouped aggregation**: `df.pt.by("species").pt.agg("mean")` or `df.pt.by("species").pt.agg(["sum", "mean", "n"])
2. **Keyword column mappings**: `df.pt.by("species").pt.agg(count="n", bill_length_mm="mean", body_mass_g=["sum", "mean"])
3. **Named output columns**: `df.pt.by("species").pt.agg(total="body_mass_g:sum")
4. **Whole-table summary**: `df.pt.agg("mean")` (computes grand totals across the entire table)

---

```python
import pytae as pt

penguins = pt.sample_data["penguins"]
tips = pt.sample_data["tips"]
titanic = pt.sample_data["titanic"]
penguins.head(3)
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |

## List `a` — `n` always goes first

```python
# mean + n: regardless of list order, n always comes first before aggregated columns
(
    penguins.pt.select("species", "island", "bill_length_mm", "body_mass_g")
    .pt.by("species", "island")
    .pt.agg(a=["mean", "n"])  # notice n comes first
)
```

**Output:**

| species   | island    |   n |   bill_length_mm |   body_mass_g |
|:----------|:----------|----:|-----------------:|--------------:|
| Adelie    | Biscoe    |  44 |          38.975  |       3709.66 |
| Adelie    | Dream     |  56 |          38.5018 |       3688.39 |
| Adelie    | Torgersen |  52 |          38.951  |       3706.37 |
| Chinstrap | Dream     |  68 |          48.8338 |       3733.09 |
| Gentoo    | Biscoe    | 124 |          47.5049 |       5076.02 |

```python
# Multiple numeric aggregations — column names get suffix: col_sum, col_mean, col_max
# also works with a single string if you only need one aggfunc
(penguins.pt.select("species", "bill_length_mm", "body_mass_g").pt.by("species").pt.agg(a=["sum", "mean", "max", "n"]))
```

**Output:**

| species   |   n |   bill_length_mm_sum |   bill_length_mm_mean |   bill_length_mm_max |   body_mass_g_sum |   body_mass_g_mean |   body_mass_g_max |
|:----------|----:|---------------------:|----------------------:|---------------------:|------------------:|-------------------:|------------------:|
| Adelie    | 152 |               5857.5 |               38.7914 |                 46   |            558800 |            3700.66 |              4775 |
| Chinstrap |  68 |               3320.7 |               48.8338 |                 58   |            253850 |            3733.09 |              4800 |
| Gentoo    | 124 |               5843.1 |               47.5049 |                 59.6 |            624350 |            5076.02 |              6300 |

## Keyword arguments — per-column control, output order follows parameter order

```python
# Keyword arguments — mean for bill_length, sum+mean for body_mass, count named 'n'
(
    penguins.pt.by("species").pt.agg(
        bill_length_mm="mean",
        body_mass_g=["sum", "mean"],
        n="n",
    )
)
```

**Output:**

| species   |   bill_length_mm |   body_mass_g_sum |   body_mass_g_mean |   n |
|:----------|-----------------:|------------------:|-------------------:|----:|
| Adelie    |          38.7914 |            558800 |            3700.66 | 152 |
| Chinstrap |          48.8338 |            253850 |            3733.09 |  68 |
| Gentoo    |          47.5049 |            624350 |            5076.02 | 124 |

```python
# Place count first (n at front), then aggregations
# Output order follows parameter order
# Note: the count keyword can be named anything — 'cnt', 'count', even 'maddy'
(
    tips.pt.select("smoker", "time", "total_bill", "tip")
    .pt.by("smoker", "time")
    .pt.agg(cnt="n", total_bill="mean", tip=["mean", "max"])
)
```

**Output:**

| smoker   | time   |   cnt |   total_bill |   tip_mean |   tip_max |
|:---------|:-------|------:|-------------:|-----------:|----------:|
| Yes      | Lunch  |    23 |      17.3991 |    2.83435 |       5   |
| Yes      | Dinner |    70 |      21.8594 |    3.066   |      10   |
| No       | Lunch  |    45 |      17.0509 |    2.67378 |       6.7 |
| No       | Dinner |   106 |      20.0957 |    3.12689 |       9   |

```python
# You can name the count column anything you like as a keyword argument
# Here maddy='n' creates a column called 'maddy' that holds the group count
(penguins.pt.select("species", "island", "body_mass_g").pt.by("species").pt.agg(maddy="n", body_mass_g="sum"))
```

**Output:**

| species   |   maddy |   body_mass_g |
|:----------|--------:|--------------:|
| Adelie    |     152 |        558800 |
| Chinstrap |      68 |        253850 |
| Gentoo    |     124 |        624350 |

```python
# Multiple count columns as keyword arguments — each count gets its own name
(
    penguins.pt.select("species", "island", "body_mass_g")
    .pt.by("species")
    .pt.agg(count="n", countv2="n", body_mass_g="mean")
)
```

**Output:**

| species   |   count |   countv2 |   body_mass_g |
|:----------|--------:|----------:|--------------:|
| Adelie    |     152 |       152 |       3700.66 |
| Chinstrap |      68 |        68 |       3733.09 |
| Gentoo    |     124 |       124 |       5076.02 |

```python
# median is a standard aggfunc — works in list form or as keyword argument
(
    penguins.pt.select("species", "island", "bill_length_mm", "body_mass_g")
    .pt.by("species")
    .pt.agg(a=["median", "mean", "n"])
)
```

**Output:**

| species   |   n |   bill_length_mm_median |   bill_length_mm_mean |   body_mass_g_median |   body_mass_g_mean |
|:----------|----:|------------------------:|----------------------:|---------------------:|-------------------:|
| Adelie    | 152 |                   38.8  |               38.7914 |                 3700 |            3700.66 |
| Chinstrap |  68 |                   49.55 |               48.8338 |                 3700 |            3733.09 |
| Gentoo    | 124 |                   47.3  |               47.5049 |                 5000 |            5076.02 |

## Handling Missing Group Keys (`dropna`)

```python
# Default dropna=False keeps missing grouping keys in their own group (no silent data loss)
(penguins.pt.select("species", "sex", "bill_length_mm", "body_mass_g").pt.by("species", "sex").pt.agg(a=["mean", "n"]))
```

**Output:**

| species   | sex    |   n |   bill_length_mm |   body_mass_g |
|:----------|:-------|----:|-----------------:|--------------:|
| Adelie    | Female |  73 |          37.2575 |       3368.84 |
| Adelie    | Male   |  73 |          40.3904 |       4043.49 |
| Adelie    | nan    |   6 |          37.84   |       3540    |
| Chinstrap | Female |  34 |          46.5735 |       3527.21 |
| Chinstrap | Male   |  34 |          51.0941 |       3938.97 |
| Gentoo    | Female |  58 |          45.5638 |       4679.74 |
| Gentoo    | Male   |  61 |          49.4738 |       5484.84 |
| Gentoo    | nan    |   5 |          45.625  |       4587.5  |

```python
# Pass dropna=True to exclude groups with NaN keys
(
    penguins.pt.select("species", "sex", "bill_length_mm", "body_mass_g")
    .pt.by("species", "sex")
    .pt.agg(a=["mean", "n"], dropna=True)
)
```

**Output:**

| species   | sex    |   n |   bill_length_mm |   body_mass_g |
|:----------|:-------|----:|-----------------:|--------------:|
| Adelie    | Female |  73 |          37.2575 |       3368.84 |
| Adelie    | Male   |  73 |          40.3904 |       4043.49 |
| Chinstrap | Female |  34 |          46.5735 |       3527.21 |
| Chinstrap | Male   |  34 |          51.0941 |       3938.97 |
| Gentoo    | Female |  58 |          45.5638 |       4679.74 |
| Gentoo    | Male   |  61 |          49.4738 |       5484.84 |

## `n`-only aggregation — count with no numeric columns needed

```python
# Count only — useful for frequency tables on categorical columns
(penguins.pt.select(exclude_dtype="number").pt.by("species", "island").pt.agg(a="n"))
```

**Output:**

| species   | island    |   n |
|:----------|:----------|----:|
| Adelie    | Biscoe    |  44 |
| Adelie    | Dream     |  56 |
| Adelie    | Torgersen |  52 |
| Chinstrap | Dream     |  68 |
| Gentoo    | Biscoe    | 124 |

## Pipeline Chaining: Filter -> Select -> Aggregation -> Sort

Because  operations return DataFrames, you can chain them seamlessly with standard Pandas operations:

```python
(
    penguins.pt.filter("body_mass_g > 3000")
    .pt.select("species", "sex", "body_mass_g")
    .pt.by("species", "sex")
    .pt.agg(a=["mean", "max", "n"])
    .sort_values("body_mass_g_mean", ascending=False)
)
```

**Output:**

| species   | sex    |   n |   body_mass_g_mean |   body_mass_g_max |
|:----------|:-------|----:|-------------------:|------------------:|
| Gentoo    | Male   |  61 |            5484.84 |              6300 |
| Gentoo    | Female |  58 |            4679.74 |              5200 |
| Gentoo    | nan    |   4 |            4587.5  |              4875 |
| Adelie    | Male   |  73 |            4043.49 |              4775 |
| Chinstrap | Male   |  34 |            3938.97 |              4800 |
| Adelie    | nan    |   4 |            3681.25 |              4250 |
| Chinstrap | Female |  32 |            3572.66 |              4150 |
| Adelie    | Female |  65 |            3424.62 |              3900 |

## Columns with Spaces & String Specifications

When column names have spaces, passing them as keyword arguments (`[total bill]='mean'`) is forbidden by Python syntax.

`agg` solves this by accepting **string mapping specifications** (matching the CLI `-agg` flag), where column names with spaces are enclosed in square brackets `[col]`. No dictionary unpacking `**{...}` is required:

```python
# Create DataFrame with spaced column names
tips_spaced = tips.rename(columns={"total_bill": "total bill"})

# Single string mapping with bracketed spaced columns
(tips_spaced.pt.by("smoker").pt.agg("tip = mean, [total bill] = mean, n = n"))
```

**Output:**

| smoker   |     tip |   total bill |   n |
|:---------|--------:|-------------:|----:|
| Yes      | 3.00871 |      20.7563 |  93 |
| No       | 2.99185 |      19.1883 | 151 |

```python
# Multiple positional string specifications
(tips_spaced.pt.by("smoker").pt.agg("tip = mean", "[total bill] = mean", "n = n"))
```

**Output:**

| smoker   |     tip |   total bill |   n |
|:---------|--------:|-------------:|----:|
| Yes      | 3.00871 |      20.7563 |  93 |
| No       | 2.99185 |      19.1883 | 151 |

```python
# Custom output names and bracketed source column
(tips_spaced.pt.by("smoker").pt.agg("[avg bill] = [total bill]:mean, [total tip] = tip:sum, [table count] = n"))
```

**Output:**

| smoker   |   avg bill |   total tip |   table count |
|:---------|-----------:|------------:|--------------:|
| Yes      |    20.7563 |      279.81 |            93 |
| No       |    19.1883 |      451.77 |           151 |

```python
# Complete pipeline: filter -> select -> agg with bracketed spaced columns across every verb
(
    tips.rename(columns={"total_bill": "total bill"})
    .pt.filter("[total bill] > 10", day=["Sat", "Sun"], time="Dinner", size=">= 2")
    .pt.select("smoker", "tip", "[total bill]")
    .pt.by("smoker")
    .pt.agg("tip = mean, [total bill] = mean, n = n")
)
```

**Output:**

| smoker   |     tip |   total bill |   n |
|:---------|--------:|-------------:|----:|
| Yes      | 3.08772 |      23.2323 |  57 |
| No       | 3.22546 |      20.7059 |  97 |
