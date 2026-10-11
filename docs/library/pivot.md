# `pt.pivot` / `df.pt.pivot` — Excel-Style 2D Pivot Tables

[← Back to Library Reference Hub](../library.md)


`pt.pivot()` summarizes and aggregates tabular data across dimensions using the intuitive **RCVA** grammar:
- **`r`** (Rows): Row grouping dimensions (*optional*)
- **`c`** (Cols): Column header dimensions (*optional*)
- **`v`** (Values): Value / measure column(s) to aggregate (**required**)
- **`a`** (Aggregation): Aggregation function (`sum`, `mean`, `median`, `min`, `max`, `count`, `std`, `n`; default: `sum`)

### Core Guarantees:
1. **Always Flat 1D Output**: Never produces MultiIndex rows or tuples in column headers. Column names are joined with `_` (e.g. `Sales_2023`).
2. **Always Clean Reset Index**: Returns a standard `RangeIndex(0, 1, 2, ...)` every time.
3. **Automatic Subsetting**: Only references `r`, `c`, and `v`—no need to pre-select columns.
4. **No Silent Data Loss**: `dropna=False` by default, retaining missing categories.

```python
import pytae as pt
import pandas as pd

penguins = pt.sample("penguins")
flights = pt.sample("flights")
penguins.head()
```

**Output:**

| species   | island    |   bill_length_mm |   bill_depth_mm |   flipper_length_mm |   body_mass_g | sex    |
|:----------|:----------|-----------------:|----------------:|--------------------:|--------------:|:-------|
| Adelie    | Torgersen |             39.1 |            18.7 |                 181 |          3750 | Male   |
| Adelie    | Torgersen |             39.5 |            17.4 |                 186 |          3800 | Female |
| Adelie    | Torgersen |             40.3 |            18   |                 195 |          3250 | Female |
| Adelie    | Torgersen |            nan   |           nan   |                 nan |           nan | nan    |
| Adelie    | Torgersen |             36.7 |            19.3 |                 193 |          3450 | Female |

## 1. Classic 2D Contingency Grid (`r=`, `c=`, `v=`)

Summarize average body mass across islands (rows) and species (columns):

```python
penguins.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")
```

**Output:**

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |  3709.66 |      nan    |  5076.02 |
| Dream     |  3688.39 |     3733.09 |   nan    |
| Torgersen |  3706.37 |      nan    |   nan    |

## 2. Frequency Matrix via Row Counts (`a="n"`)

Count occurrences across dimensions (the direct successor to cross-tabulation):

```python
penguins.pt.pivot(r="island", c="species", v="sex", a="n")
```

**Output:**

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |       44 |           0 |      124 |
| Dream     |       56 |          68 |        0 |
| Torgersen |       52 |           0 |        0 |

## 3. Flexible Excel Layouts: Optional Rows or Columns

Just like dragging fields in Excel, `r` and `c` are completely optional.

```python
# Omit c: vertical summary table by row group
penguins.pt.pivot(r="species", v="body_mass_g", a="mean")
```

**Output:**

| species   |   body_mass_g |
|:----------|--------------:|
| Adelie    |       3700.66 |
| Chinstrap |       3733.09 |
| Gentoo    |       5076.02 |

```python
# Omit r: horizontal summary table across column headers
penguins.pt.pivot(c="species", v="body_mass_g", a="mean")
```

**Output:**

|   Adelie |   Chinstrap |   Gentoo |
|---------:|------------:|---------:|
|  3700.66 |     3733.09 |  5076.02 |

```python
# Omit both r and c: grand scalar aggregation across the dataset
penguins.pt.pivot(v="body_mass_g", a="mean")
```

**Output:**

|   body_mass_g |
|--------------:|
|       4201.75 |

## 4. Multi-Level Dimensions & Multi-Metric Reporting

Pass a list of columns to `r`, `c`, or `v`:

```python
# Hierarchical rows + multiple metric values
penguins.pt.pivot(
    r=["island", "sex"],
    c="species",
    v=["body_mass_g", "flipper_length_mm"],
    a="mean",
    fill_value=0
)
```

**Output:**

| island    | sex    |   body_mass_g_Adelie |   body_mass_g_Chinstrap |   body_mass_g_Gentoo |   flipper_length_mm_Adelie |   flipper_length_mm_Chinstrap |   flipper_length_mm_Gentoo |
|:----------|:-------|---------------------:|------------------------:|---------------------:|---------------------------:|------------------------------:|---------------------------:|
| Biscoe    | Female |              3369.32 |                    0    |              4679.74 |                    187.182 |                         0     |                    212.707 |
| Biscoe    | Male   |              4050    |                    0    |              5484.84 |                    190.409 |                         0     |                    221.541 |
| Biscoe    | nan    |                 0    |                    0    |              4587.5  |                      0     |                         0     |                    215.75  |
| Dream     | Female |              3344.44 |                 3527.21 |                 0    |                    187.852 |                       191.735 |                      0     |
| Dream     | Male   |              4045.54 |                 3938.97 |                 0    |                    191.929 |                       199.912 |                      0     |
| Dream     | nan    |              2975    |                    0    |                 0    |                    179     |                         0     |                      0     |
| Torgersen | Female |              3395.83 |                    0    |                 0    |                    188.292 |                         0     |                      0     |
| Torgersen | Male   |              4034.78 |                    0    |                 0    |                    194.913 |                         0     |                      0     |
| Torgersen | nan    |              3681.25 |                    0    |                 0    |                    187.25  |                         0     |                      0     |

## 5. Seamless Method Chaining & Plotting

Because `pt.pivot` always returns a clean, rectangular DataFrame with a flat RangeIndex, you can immediately chain into further transformations or `.pt.plot()`:

```python
piv = penguins.pt.pivot(r="island", c="species", v="body_mass_g", a="mean", fill_value=0)
# Clean flat columns and standard index ready for downstream manipulation:
print("Columns:", list(piv.columns))
print("Index:", list(piv.index))
piv
```

**Output:**

| island    |   Adelie |   Chinstrap |   Gentoo |
|:----------|---------:|------------:|---------:|
| Biscoe    |  3709.66 |        0    |  5076.02 |
| Dream     |  3688.39 |     3733.09 |     0    |
| Torgersen |  3706.37 |        0    |     0    |
