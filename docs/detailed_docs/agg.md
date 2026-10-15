# Grouping & Aggregation (`by` & `agg`)

`agg` summarizes datasets into concise metric tables. Paired with `by`, it computes grouped summary statistics across one or more dimensions. Crucially, Pytae preserves missing data (`dropna=False`) by default, ensuring unclassified or null groups are never silently lost.

---

## Rosetta Stone: Python vs. CLI

| Capability | Python Library (`pytae`) | Command Line (`pytae CLI`) |
|:---|:---|:---|
| **Set Grouping Context** | `df.by("species", "island")` | `-by "species, island"` |
| **Named Summary Metrics** | `df.by("species").agg(avg_mass="mean(body_mass_g)", n="n")` | `-by species -agg "avg_mass = mean(body_mass_g), n = n"` |
| **Colon Metric Shorthand**| `df.by("species").agg(avg_mass="body_mass_g:mean")` | `-by species -agg "avg_mass = body_mass_g:mean"` |
| **Whole-Table Summary** | `df.agg(avg_mass="mean(body_mass_g)")` | `-agg "avg_mass = mean(body_mass_g)"` |
| **Distinct Count** | `df.by("island").agg(species_count="n_distinct(species)")` | `-by island -agg "species_count = n_distinct(species)"` |
| **Drop NA Groups** | `df.by("sex").agg(dropna=True, avg_mass="mean(body_mass_g)")` | `-by sex -agg "avg_mass = mean(body_mass_g), dropna=true"` |

---

## Supported Aggregation Functions

| Function | Alias | Description |
|:---|:---|:---|
| `mean` / `avg` | `mean()` | Arithmetic mean |
| `sum` | `sum()` | Sum total |
| `min`, `max` | `min()`, `max()` | Minimum, maximum values |
| `median` | `median()` | 50th percentile |
| `std`, `var` | `std()`, `var()` | Sample standard deviation and variance |
| `n` / `count` | `n`, `count()` | Number of rows in group |
| `n_distinct` | `nunique()`, `count_distinct()` | Number of unique non-null values |
| `first`, `last` | `first()`, `last()` | First or last observed value in group |
| `quantile(q)` | `quantile(0.95)` | Quantile at given probability $q$ |

---

## Python Library Usage

### 1. Grouped Aggregation
Call `.by(*cols)` followed by `.agg(...)`:

```python
import pytae as pt

penguins = pt.sample("penguins")

summary = (
    penguins
    .by("species", "island")
    .agg(
        n="n",
        avg_mass="mean(body_mass_g)",
        max_flipper="max(flipper_length_mm)",
        unique_sexes="n_distinct(sex)"
    )
)
```

### 2. Zero Data Loss by Default (`dropna=False`)
In standard Pandas, `.groupby()` silently discards rows where grouping keys contain `NaN` or `None`. In Pytae, `dropna=False` is the strict default. Groups with missing keys (like `sex=NaN`) remain visible:

```python
# Preserves sex=NaN as a visible row in the summary report!
penguins.by("sex").agg(n="n", avg_mass="mean(body_mass_g)")

# Explicitly drop NA groups if desired:
penguins.by("sex").agg(dropna=True, n="n", avg_mass="mean(body_mass_g)")
```

### 3. Whole-Table Aggregation
Omit `.by()` to aggregate across the entire table:

```python
penguins.agg(
    total_penguins="n",
    avg_mass="mean(body_mass_g)",
    min_mass="min(body_mass_g)"
)
```

---

## CLI Usage

In the CLI, `-by` sets the grouping columns, and `-agg` defines the computed metrics:

```bash
# Grouped metrics
pytae penguins.parquet \
  -by species \
  -agg "n = n, avg_mass = mean(body_mass_g), max_bill = max(bill_length_mm)"

# Colon shorthand
pytae penguins.parquet \
  -by species,island \
  -agg "avg_mass = body_mass_g:mean, n = n"

# Whole-table metrics
pytae penguins.parquet \
  -agg "total_rows = n, avg_mass = mean(body_mass_g)"

# Filter then aggregate
pytae penguins.parquet \
  -filter "body_mass_g > 3500" \
  -by species \
  -agg "n = n, avg_bill = mean(bill_length_mm)"
```

