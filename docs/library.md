# pytae — Library Reference & Python API Hub

`pytae` provides concise, expressive verbs on top of pandas DataFrames for common data-science tasks—filtering, selection, mutating, aggregation, reshaping, plotting, and SQL querying—with zero friction.

---

## Contents

- [Calling Paradigms: Accessor vs. Function](#calling-paradigms)
- [Master Modules & Notebooks Directory](#modules-directory)
- [Functional Areas at a Glance](#functional-areas)
  - [1. Row Filtering (`filter`)](#1-row-filtering--filter)
  - [2. Column Selection (`select`)](#2-column-selection--select)
  - [3. Feature Engineering (`mutate`)](#3-feature-engineering--mutate)
  - [4. Sorting & Picking (`arrange`, `pick`)](#4-sorting--picking-extreme-rows--arrange--pick)
  - [5. Deduplication (`distinct`)](#5-distinct-rows--removing-duplicate-rows)
  - [6. Pure Reshaping (`long`, `wide`)](#6-pure-reshaping--long-wide)
  - [7. 2D Pivot Tables (`pivot`)](#7-2d-pivot-tables--pivot)
  - [8. Aggregation (`agg`)](#8-aggregation--agg)
  - [9. Plotting (`Plotter` & `df.pt.plot`)](#9-plotting--plotter)
  - [10. Utilities & Cleaning](#10-utilities--cleaning)
- [Bundled Sample Datasets](#sample-datasets)
- [Syntax & Convention Cheat Sheet](#syntax-conventions)

---

<a id="calling-paradigms"></a>
## Calling Paradigms: Accessor vs. Function

Every operation in `pytae` is accessible through two equivalent styles:

1. **Accessor Chain (`df.pt.<verb>()`)**: Chains smoothly with standard pandas methods (`.rename()`, `.sort_values()`, `.assign()`). Preferred in interactive notebooks and pipelines.
2. **Function Style (`pt.<verb>(df, ...)`)**: Pure functional form, ideal for standalone transformations and scripts.

```python
import pytae as pt
import pandas as pd

penguins = pt.sample("penguins")

# 1. Accessor chain: seamless integration with pandas
(
    penguins.pt.filter("body_mass_g > 3000, species == 'Gentoo'")
    .pt.select("species", "island", "bill_length_mm", "body_mass_g")
    .pt.mutate(mass_kg="body_mass_g / 1000")
    .pt.arrange("mass_kg desc")
    .pt.by("species", "island")
    .pt.agg(a=["mean", "n"])
)
```

**Output:**

| species | island | n | bill_length_mm | body_mass_g | mass_kg |
|:---|:---|---:|---:|---:|---:|
| Gentoo | Biscoe | 123 | 47.5049 | 5076.02 | 5.07602 |

```python
# 2. Function style: standalone calls
subset = pt.select(penguins, "species", contains="bill")
summary = pt.agg(pt.by(subset, "species"), "mean")
```

---

<a id="modules-directory"></a>
## Master Modules & Feature Guides Directory

Detailed guides with step-by-step walkthroughs, outputs, and edge cases are maintained in [`docs/library/`](library/):

| Module | Verbs / API | Description | Feature Guide |
|---|---|---|---|
| **Data I/O & Joins** | `pt.read()`, `pt.scan()`, `df.join()`, `pt.concat()`, `df.to_parquet()`, `df.to_csv()`, `df.to_clip()`, `pt.sample()` | Eager reading, lazy scanning, pushdowns, relational joins, row stacking, streaming sinks, interop, and dataset sampling | [library/io.md](library/io.md) |
| **Filtering** | `pt.filter()`, `df.pt.filter()` | Clean filters via callables (lambdas), expressions, dicts, or kwargs (comparisons, intervals, list membership, string ops, null checks) | [library/filter.md](library/filter.md) |
| **Selection** | `pt.select()`, `df.pt.select()` | Pick and reorder columns by name, slices, regex, pattern matching, or data types | [library/select.md](library/select.md) |
| **Mutating** | `pt.mutate()`, `df.pt.mutate()` | Create/overwrite columns via formulas, multi-column transforms (`(col1, col2) = _ * 2`), window transforms via standalone `pt.by()`, `if_else()`, `case_when()`, `coalesce()`, `map()`, or `@locals` | [library/mutate.md](library/mutate.md) |
| **Sorting** | `pt.arrange()`, `df.pt.arrange()` | Reorder rows with `-col`/`desc`, inline directions, bracket notation for spaces | [library/arrange.md](library/arrange.md) |
| **Picking Rows** | `pt.pick()`, `df.pt.pick()` | Select extreme top/bottom N rows or proportion overall or per group via `pt.by()` (`order='max'/'min'`) | [library/pick.md](library/pick.md) |
| **Distinct Rows** | `pt.distinct()`, `df.pt.distinct()` | Remove duplicate rows across all or specific column subsets | [library/distinct.md](library/distinct.md) |
| **Pure Reshaping** | `pt.long()`, `pt.wide()` | Melt numeric columns to long rows, spread back to wide tables with standard `c=`, `v=`, `r=` keys | [library/reshape.md](library/reshape.md) |
| **2D Pivot Tables** | `pt.pivot()`, `df.pt.pivot()` | Excel-style multi-dimensional aggregation matrices with automatic reset index and flat 1D columns (`r=`, `c=`, `v=`, `a=`) | [library/pivot.md](library/pivot.md) |
| **Aggregation** | `pt.agg()`, `df.pt.agg()` | Summary statistics grouped beforehand via standalone `pt.by()` (`n` for row counts), or whole table | [library/agg.md](library/agg.md) |
| **Plotting** | `pt.Plotter`, `df.pt.plot()` | Method-chainable visualizations, secondary axes, multi-panel mosaic dashboards, and small multiples | [library/plotting.ipynb](library/plotting.ipynb) |
| **Utilities** | `glimpse`, `freq`, `hist`, `clean_columns`, `replace_values`, `handle_missing`, `cols`, `to_clip` | Transposed column overview, ASCII frequency bars & histograms, header normalization, scoped cell value replacement, NA imputation, clipboard | [library/other_utilities.md](library/other_utilities.md) |

---

👉 **Philosophical Design & Comparison:** See **[Pytae vs. Pandas vs. dplyr (Rosetta Stone & Rationale)](comparison_to_pandas_and_dplyr.md)** for detailed naming rationales and side-by-side syntax comparisons.

---

<a id="functional-areas"></a>
## Functional Areas at a Glance

### 1. Row Filtering — `filter()`

Filter rows using intuitive callables/lambdas, string expressions, python dictionaries, or keyword arguments. Safely handles column names with spaces without awkward escaping:

```python
# Bare callables / lambdas
penguins.pt.filter(lambda d: d["body_mass_g"] > 4000)

# String expressions (handles spaced names directly)
penguins.pt.filter("body_mass_g > 3500, species == 'Adelie'")

# Plain dictionary syntax
df.pt.filter({"bill length mm": "> 40", "island": "Biscoe"})

# Keyword arguments with intervals and string operators
pt.filter(penguins, body_mass_g="[3000, 4500]", species=("startswith", "Ad"))
```

👉 **Complete Guide:** [library/filter.md](library/filter.md)

---

### 2. Column Selection — `select()`

Select, filter, reorder, or exclude columns using exact names, negative prefixes (`-col`, `~col`), negative slices (`-start:end`), keyword exclusion (`exclude=`), regex patterns, or data type categories:

```python
pt.select(penguins, "species", "island")  # Exact column order
pt.select(penguins, "-species")  # Exclude column (negative selection)
pt.select(penguins, "-bill_length_mm:body_mass_g")  # Negative slice
pt.select(penguins, exclude=["species", "island"])  # Keyword exclusion
pt.select(penguins, "species:bill_length_mm")  # Contiguous slice
pt.select(penguins, contains="bill", dtype="numeric")  # Pattern union
pt.select(penguins, exclude_dtype="numeric")  # Invert selection
```

👉 **Complete Guide:** [library/select.md](library/select.md)

---

### 3. Feature Engineering — `mutate()`

Compute new columns or overwrite existing ones using python expressions evaluated in order via pandas `eval()`. Includes built-in functional helpers like `if_else`, `case_when`, `coalesce`, and `map`:

```python
# Formulas and sequential derivation
pt.mutate(penguins, mass_kg="body_mass_g / 1000", mass_lb="mass_kg * 2.20462")

# Functional helpers: if_else, case_when, coalesce, map
pt.mutate(penguins, weight_class="if_else(body_mass_g > 4000, 'heavy', 'light')")
pt.mutate(penguins, tier="case_when((body_mass_g >= 4500, 'large'), (body_mass_g >= 3500, 'medium'), default='small')")
pt.mutate(df, contact="coalesce(mobile, home_phone, work_phone, 'N/A')")
pt.mutate(penguins, code="map(species, {'Adelie': 'A', 'Gentoo': 'G'}, 'Other')")

# Grouped window calculations without collapsing rows (inherited from standalone pt.by)
pt.mutate(pt.by(penguins, "species"), avg_mass="mean(body_mass_g)", diff="body_mass_g - avg_mass", n="n")

# Multi-column transforms using (col1, col2) and _ placeholder (in-place, suffix/prefix, or selectors)
penguins.pt.mutate("(bill_length_mm, bill_depth_mm) = _ / 10")
penguins.pt.mutate("(bill_length_mm, bill_depth_mm)_cm = _ / 10")
penguins.pt.mutate("(startswith=bill_) = _ / 10")
penguins.pt.by("species").pt.mutate("z_(dtype=numeric) = (_ - mean(_)) / std(_)")

# Control NA grouping with dropna (dropna=False by default calculates on NA group; dropna=True fills NaN)
pt.mutate(pt.by(df, "group"), avg_val="mean(val)", dropna=True)
```

👉 **Complete Guide:** [library/mutate.md](library/mutate.md)

---

### 4. Sorting & Picking Extreme Rows — `arrange()` & `pick()`

Order rows or retrieve the top/bottom records with group awareness:

```python
# Reorder rows: asc, desc, leading minus, and brackets for spaces
pt.arrange(penguins, "species", "body_mass_g desc")
pt.arrange(penguins, "-body_mass_g")
pt.arrange(penguins, "[bill length mm] desc")

# Pick top / bottom records overall or within groups
pt.pick(penguins, "body_mass_g", n=3)  # Top 3 (default order="max")
pt.pick(penguins, "body_mass_g", n=1, order="min")  # Lightest penguin
pt.pick(penguins, "body_mass_g", prop=0.1)  # Top 10%

# Method chaining with group context
(penguins.pt.arrange("species, -body_mass_g").pt.by("species").pt.pick("body_mass_g", n=2))
```

👉 **Complete Guides:** [library/arrange.md](library/arrange.md) (Sorting) • [library/pick.md](library/pick.md) (Picking Rows)

---

### 5. Distinct Rows — Removing Duplicate Rows

Drop duplicate records across the intermediate DataFrame with full control over column subsets, with automatic 0-indexed RangeIndex reset:

```python
# Eliminate duplicates across all selected columns via accessor
penguins.pt.select("species", "island").pt.distinct()

# Restrict uniqueness constraint to specific columns (positional arguments only)
penguins.pt.distinct("species", "island")

# Functional style
pt.distinct(penguins, "species", "island")
```

👉 **Complete Guide:** [library/distinct.md](library/distinct.md)

---

### 6. Pure Reshaping — `long()` & `wide()`

Reshape between long and wide formats using consistent `c=` (column dimension), `v=` (value column), and `r=` (row identifiers) parameter roles:

```python
# Melt numeric columns into (feature, value) rows
tall = pt.long(penguins, c="feature", v="reading")

# Pure reshape: spread long-form records back to columns
wide = pt.wide(tall, c="feature", v="reading")
```

👉 **Complete Guide:** [library/reshape.md](library/reshape.md)

---

### 7. 2D Pivot Tables — `pivot()`

Excel-style 2D pivot table engine with the intuitive `r, c, v, a` vocabulary. Guarantees flat 1D column names and automatically resets index to `RangeIndex(0, 1, 2, ...)`:

```python
# 2D summary grid of mean body mass across island and species
pt.pivot(penguins, r="island", c="species", v="body_mass_g", a="mean")

# Frequency matrix (count rows across dimensions; v can be omitted for row counts)
pt.pivot(penguins, r="island", c="species", a="n")

# Hierarchical multi-row summary
pt.pivot(penguins, r=["island", "sex"], c="species", v="body_mass_g", a="mean", f_v=0)
```

👉 **Complete Guide:** [library/pivot.md](library/pivot.md)

---

### 8. Grouping & Aggregation — `by()`, `ungroup()`, `agg()`

Set grouping context with `.pt.by(*cols)` which flows into subsequent `.pt.mutate()`, `.pt.agg()`, and `.pt.pick()`. Clear grouping at any time using `.pt.ungroup()`. Calling `.pt.agg()` automatically clears the active grouping upon completion:

```python
# Grouped aggregation via pipeline chaining
penguins.pt.by("species", "island").pt.agg("mean")

# Grouped window mutation inheriting active grouping
penguins.pt.by("species").pt.mutate("mean_mass = mean(body_mass_g), diff = body_mass_g - mean_mass")

# Clear grouping explicitly
penguins.pt.by("species").pt.ungroup()

# Direct functional agg
pt.agg(penguins, "species", "mean")  # Mean of all numeric columns per species
pt.agg(penguins, ["species", "island"], ["mean", "sum", "n"])  # Multi-column grouping
pt.agg(penguins, "species", body_mass_g="mean", count="n")  # Column-specific aggregations
pt.agg(
    tips.rename(columns={"total_bill": "total bill"}), "smoker", "tip = mean, [total bill] = mean, n = n"
)  # String spec with bracketed spaced columns
pt.agg(penguins, "species", total="body_mass_g:sum")  # Named aggregation
pt.agg(penguins, None, a=["mean", "n"])  # Whole-table summary (no grouping)
```

👉 **Complete Guide:** [library/agg.md](library/agg.md)

---

<a id="9-plotting--plotter"></a>
### 9. Plotting — `Plotter` & `df.pt.plot()`

Method-chainable visualization engine built on Matplotlib and `pandas.plot()`. Supports automated grouping, secondary Y-axes, complex multi-panel mosaic dashboards, small-multiples grid faceting, and direct accessor chaining via `df.pt.plot()`:

```python
# Direct accessor chaining
(
    penguins.pt.select("species", "bill_length_mm", "bill_depth_mm")
    .pt.plot(kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species", palette="tab10")
    .finalize()
)

# Multi-panel mosaic dashboard
p = pt.Plotter(penguins, mosaic="AB", figsize=(10, 4))
p.plot(on="A", kind="scatter", x="bill_length_mm", y="bill_depth_mm", by="species")
p.plot(on="B", kind="box", x="species", y="bill_length_mm")
p.finalize(consolidate_legends=True)
```

👉 **Interactive Walkthrough:** [library/plotting.ipynb](library/plotting.ipynb)



---

### 10. Utilities & Cleaning

Essential tabular utilities for everyday manipulation:

```python
penguins.pt.glimpse()  # Transposed column overview (returns self)
penguins.pt.freq("species")  # Frequency distribution DataFrame with ASCII bars
penguins.pt.hist("body_mass_g:10")  # Numeric histogram DataFrame with ASCII bars
pt.clean_columns(df, strip=True, fill="_", case="lower", dedupe=True)  # Normalize headers
pt.replace_values(df, {"old": "new"}, c="col_a", exact=True)  # Replace cell values
pt.handle_missing(df, fillna="NA")  # Impute missing values
penguins.to_clip()  # Copy DataFrame to clipboard
```

👉 **Complete Guide:** [library/other_utilities.md](library/other_utilities.md)

---

<a id="sample-datasets"></a>
## Bundled Sample Datasets

`pytae` includes real-world datasets for rapid experimentation:

```python
import pytae as pt

penguins = pt.sample("penguins")  # or pt.sample_data["penguins"]
tips = pt.sample("tips")
titanic = pt.sample("titanic")
diamonds = pt.sample("diamonds")
mpg = pt.sample("mpg")
flights = pt.sample("flights")
```

---

<a id="syntax-conventions"></a>
## Syntax & Convention Cheat Sheet

| Task | Syntax | Example |
|---|---|---|
| **Copy to Clipboard** | `df.to_clip()` in Python; `-o clip` in CLI | `df.head().to_clip()` |
| **Mapping vs. Assignment** | `:` maps old to new; `=` assigns values | `pt.replace_values(df, {"old": "new"})` vs `pt.mutate(col="expr")` |
| **Multi-Column (Mutate)** | Parentheses `(col1, col2)` + `_` placeholder | `df.pt.mutate("(rev, cost)_usd = _ * 1.08")` |
| **Spaced Columns (Filter)** | Enclose in brackets `[col]` | `df.pt.filter("[bill length mm] > 40")` |
| **Spaced Columns (Select)** | Enclose in brackets `[col]` | `df.pt.select("species", "[body mass g]")` |
| **Spaced Columns (Create)** | String assignment `[col] = ...` (or `**{...}`) | `df.pt.mutate("[body mass kg] = body_mass_g / 1000")` |
| **Spaced Columns (Agg)** | String mapping `"[col] = func, n = n"` | `df.pt.agg("smoker", "tip = mean, [total bill] = mean, n = n")` |
| **Spaced Columns (Expr)** | Reference via brackets `[col]` or backticks `` `col` `` | `df.pt.mutate(ratio="[bill length mm] / [bill depth mm]")` |
| **Standard Reshape Keys** | `c=` (column), `v=` (value), `a=` (aggregation) | `pt.wide(df, c="metric", v="value", a="mean")` |
