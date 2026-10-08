# pytae — Library Reference & Python API Hub

`pytae` provides concise, expressive verbs on top of pandas DataFrames for common data-science tasks—filtering, selection, mutating, aggregation, reshaping, plotting, and SQL querying—with zero friction.

---

## Contents

- [Calling Paradigms: Accessor vs. Function](#calling-paradigms)
- [Master Modules & Notebooks Directory](#modules-directory)
- [Functional Areas at a Glance](#functional-areas)
  - [1. Row Filtering (`qry`)](#1-row-filtering--qry)
  - [2. Column Selection (`select`)](#2-column-selection--select)
  - [3. Feature Engineering (`mutate`)](#3-feature-engineering--mutate)
  - [4. Sorting & Slicing (`arrange`, `slice_max`, `slice_min`)](#4-sorting--slicing--arrange-slice_max-slice_min)
  - [5. Deduplication (`drop_duplicates`)](#5-deduplication--removing-duplicate-rows)
  - [6. Pure Reshaping (`long`, `wide`)](#6-pure-reshaping--long-wide)
  - [7. 2D Pivot Tables (`pivot`)](#7-2d-pivot-tables--pivot)
  - [8. Aggregation (`agg`)](#8-aggregation--agg)
  - [9. DuckDB SQL Engine (`sql`)](#9-duckdb-sql-engine--sql)
  - [10. Plotting (`Plotter` & `df.pt.plot`)](#10-plotting--plotter)
  - [11. Utilities & Cleaning](#11-utilities--cleaning)
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
    penguins
    .pt.filter("body_mass_g > 3000, species == 'Gentoo'")
    .pt.select("species", "island", "bill_length_mm", "body_mass_g")
    .pt.mutate(mass_kg="body_mass_g / 1000")
    .pt.arrange("mass_kg desc")
    .pt.by("species", "island")
    .pt.agg(a=["mean", "n"])
)

# 2. Function style: standalone calls
subset = pt.select(penguins, "species", contains="bill")
summary = pt.agg(subset, "species", "mean")
```

---

<a id="modules-directory"></a>
## Master Modules & Notebooks Directory

Detailed guides with step-by-step walkthroughs, outputs, and edge cases are maintained as runnable Jupyter notebooks in [`docs/library/`](library/):

| Module | Verbs / API | Description | Interactive Notebook |
|---|---|---|---|
| **Filtering** | `pt.filter()`, `df.pt.filter()` | Clean filters via callables (lambdas), expressions, dicts, or kwargs (comparisons, intervals, list membership, string ops, null checks) | [library/filter.ipynb](library/filter.ipynb) |
| **Selection** | `pt.select()`, `df.pt.select()` | Pick and reorder columns by name, slices, regex, pattern matching, or data types | [library/select.ipynb](library/select.ipynb) |
| **Mutating** | `pt.mutate()`, `df.pt.mutate()` | Create/overwrite columns via formulas, grouped transforms `by=`, `if_else()`, `case_when()`, `coalesce()`, `map()`, or `@locals` | [library/mutate.ipynb](library/mutate.ipynb) |
| **Sorting** | `pt.arrange()`, `df.pt.arrange()` | Reorder rows with `-col`/`desc`, inline directions, bracket notation for spaces | [library/arrange.ipynb](library/arrange.ipynb) |
| **Picking Rows** | `pt.pick()`, `df.pt.pick()` | Select extreme top/bottom N rows or proportion overall or per group (`by=`, `order='max'/'min'`) | [library/pick.ipynb](library/pick.ipynb) |
| **Distinct Rows** | `pt.distinct()`, `df.pt.distinct()` | Remove duplicate rows across all or specific column subsets | [library/distinct.ipynb](library/distinct.ipynb) |
| **Pure Reshaping** | `pt.long()`, `pt.wide()` | Melt numeric columns to long rows, spread back to wide tables with standard `c=`, `v=`, `r=` keys | [library/reshape.ipynb](library/reshape.ipynb) |
| **2D Pivot Tables** | `pt.pivot()`, `df.pt.pivot()` | Excel-style multi-dimensional aggregation matrices with automatic reset index and flat 1D columns (`r=`, `c=`, `v=`, `a=`) | [library/pivot.ipynb](library/pivot.ipynb) |
| **Aggregation** | `pt.agg()`, `df.pt.agg()` | Summary statistics grouped by explicit `by=` column(s) (`n` for row counts), or `None` for whole table | [library/agg.ipynb](library/agg.ipynb) |
| **SQL Engine** | `pt.sql()`, `df.pt.sql()` | Zero-copy ANSI SQL queries via DuckDB over in-memory DataFrames and multi-frame joins | [library/sql.ipynb](library/sql.ipynb) |
| **Plotting** | `pt.Plotter`, `df.pt.plot()` | Method-chainable visualizations, secondary axes, multi-panel mosaic dashboards, and small multiples | [library/plotting.ipynb](library/plotting.ipynb) |
| **Utilities** | `glimpse`, `clean_columns`, `replace_values`, `handle_missing`, `cols`, `to_clip` | Transposed column overview, header normalization, scoped cell value replacement, NA imputation, clipboard | [library/other_utilities.ipynb](library/other_utilities.ipynb) |

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

👉 **Interactive Walkthrough:** [library/filter.ipynb](library/filter.ipynb)

---

### 2. Column Selection — `select()`

Select, filter, reorder, or exclude columns using exact names, negative prefixes (`-col`, `~col`), negative slices (`-start:end`), keyword exclusion (`exclude=`), regex patterns, or data type categories:

```python
pt.select(penguins, "species", "island")              # Exact column order
pt.select(penguins, "-species")                       # Exclude column (negative selection)
pt.select(penguins, "-bill_length_mm:body_mass_g")    # Negative slice
pt.select(penguins, exclude=["species", "island"])    # Keyword exclusion
pt.select(penguins, "species:bill_length_mm")          # Contiguous slice
pt.select(penguins, contains="bill", dtype="numeric")  # Pattern union
pt.select(penguins, exclude_dtype="numeric")          # Invert selection
```

👉 **Interactive Walkthrough:** [library/select.ipynb](library/select.ipynb)

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

# Grouped window calculations without collapsing rows
pt.mutate(penguins, avg_mass="mean(body_mass_g)", diff="body_mass_g - avg_mass", n="n", by="species")

# Control NA grouping with dropna (dropna=False by default calculates on NA group; dropna=True fills NaN)
pt.mutate(df, avg_val="mean(val)", by="group", dropna=True)
```

👉 **Interactive Walkthrough:** [library/mutate.ipynb](library/mutate.ipynb)

---

### 4. Sorting & Picking Extreme Rows — `arrange()` & `pick()`

Order rows or retrieve the top/bottom records with group awareness:

```python
# Reorder rows: asc, desc, leading minus, and brackets for spaces
pt.arrange(penguins, "species", "body_mass_g desc")
pt.arrange(penguins, "-body_mass_g")
pt.arrange(penguins, "[bill length mm] desc")

# Pick top / bottom records overall or within groups
pt.pick(penguins, "body_mass_g", n=3)                 # Top 3 (default order="max")
pt.pick(penguins, "body_mass_g", n=1, order="min")    # Lightest penguin
pt.pick(penguins, "body_mass_g", prop=0.1)            # Top 10%

# Method chaining with group context
(
    penguins
    .pt.arrange("species, -body_mass_g")
    .pt.by("species")
    .pt.pick("body_mass_g", n=2)
)
```

👉 **Interactive Walkthroughs:** [library/arrange.ipynb](library/arrange.ipynb) (Sorting) • [library/pick.ipynb](library/pick.ipynb) (Picking Rows)

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

👉 **Interactive Walkthrough:** [library/distinct.ipynb](library/distinct.ipynb)

---

### 6. Pure Reshaping — `long()` & `wide()`

Reshape between long and wide formats using consistent `c=` (column dimension), `v=` (value column), and `r=` (row identifiers) parameter roles:

```python
# Melt numeric columns into (feature, value) rows
tall = pt.long(penguins, c="feature", v="reading")

# Pure reshape: spread long-form records back to columns
wide = pt.wide(tall, c="feature", v="reading")
```

👉 **Interactive Walkthrough:** [library/reshape.ipynb](library/reshape.ipynb)

---

### 7. 2D Pivot Tables — `pivot()`

Excel-style 2D pivot table engine with the intuitive `r, c, v, a` vocabulary. Guarantees flat 1D column names and automatically resets index to `RangeIndex(0, 1, 2, ...)`:

```python
# 2D summary grid of mean body mass across island and species
pt.pivot(penguins, r="island", c="species", v="body_mass_g", a="mean")

# Frequency matrix (count rows across dimensions; v can be omitted for row counts)
pt.pivot(penguins, r="island", c="species", a="n")

# Hierarchical multi-row summary
pt.pivot(penguins, r=["island", "sex"], c="species", v="body_mass_g", a="mean", fill_value=0)
```

👉 **Interactive Walkthrough:** [library/pivot.ipynb](library/pivot.ipynb)

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
pt.agg(penguins, "species", "mean")                           # Mean of all numeric columns per species
pt.agg(penguins, ["species", "island"], ["mean", "sum", "n"]) # Multi-column grouping
pt.agg(penguins, "species", body_mass_g="mean", count="n")    # Column-specific aggregations
pt.agg(tips.rename(columns={"total_bill": "total bill"}), "smoker", "tip = mean, [total bill] = mean, n = n") # String spec with bracketed spaced columns
pt.agg(penguins, "species", total="body_mass_g:sum")          # Named aggregation
pt.agg(penguins, None, a=["mean", "n"])                       # Whole-table summary (no grouping)
```

👉 **Interactive Walkthrough:** [library/agg.ipynb](library/agg.ipynb)

---

### 9. DuckDB SQL Engine — `sql()`

Execute SQL queries directly over in-memory DataFrames using DuckDB (`pip install "pytae[sql]"`). The source DataFrame is queryable as table `data`, and additional frames can be registered as keyword arguments:

```python
# Query current frame as table 'data'
pt.sql(penguins, "select species, avg(body_mass_g) as avg_mass from data group by species")

# Multi-table joins and window functions
pt.sql(orders, """
    select o.id, c.name, o.amount
    from data o
    inner join customers c on o.cust_id = c.id
""", customers=df_customers)
```

👉 **Interactive Walkthrough:** [library/sql.ipynb](library/sql.ipynb)

---

<a id="10-plotting--plotter"></a>
### 10. Plotting — `Plotter` & `df.pt.plot()`

Method-chainable visualization engine built on Matplotlib and `pandas.plot()`. Supports automated grouping, secondary Y-axes, complex multi-panel mosaic dashboards, small-multiples grid faceting, and direct accessor chaining via `df.pt.plot()`:

```python
# Direct accessor chaining
(
    penguins
    .pt.select("species", "bill_length_mm", "bill_depth_mm")
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

### 11. Utilities & Cleaning

Essential tabular utilities for everyday manipulation:

```python
penguins.pt.glimpse()                                                 # Transposed column overview (returns self)
pt.clean_columns(df, strip=True, fill="_", case="lower", dedupe=True) # Normalize headers
pt.replace_values(df, {"old": "new"}, c="col_a", exact=True)          # Replace cell values
pt.handle_missing(df, fillna="NA")                                    # Impute missing values
penguins.to_clip()                                                    # Copy DataFrame to clipboard
```

👉 **Interactive Walkthrough Notebook:** [library/other_utilities.ipynb](library/other_utilities.ipynb)

---

<a id="sample-datasets"></a>
## Bundled Sample Datasets

`pytae` includes real-world datasets for rapid experimentation:

```python
import pytae as pt

penguins = pt.sample("penguins")  # or pt.sample_data["penguins"]
tips     = pt.sample("tips")
titanic  = pt.sample("titanic")
diamonds = pt.sample("diamonds")
mpg      = pt.sample("mpg")
flights  = pt.sample("flights")
```

---

<a id="syntax-conventions"></a>
## Syntax & Convention Cheat Sheet

| Task | Syntax | Example |
|---|---|---|
| **Copy to Clipboard** | `df.to_clip()` in Python; `-o clip` in CLI | `df.head().to_clip()` |
| **Mapping vs. Assignment** | `:` maps old to new; `=` assigns values | `pt.replace_values(df, {"old": "new"})` vs `pt.mutate(col="expr")` |
| **Spaced Columns (Filter)** | Enclose in brackets `[col]` | `df.pt.filter("[bill length mm] > 40")` |
| **Spaced Columns (Select)** | Enclose in brackets `[col]` | `df.pt.select("species", "[body mass g]")` |
| **Spaced Columns (Create)** | String assignment `[col] = ...` (or `**{...}`) | `df.pt.mutate("[body mass kg] = body_mass_g / 1000")` |
| **Spaced Columns (Agg)** | String mapping `"[col] = func, n = n"` | `df.pt.agg("smoker", "tip = mean, [total bill] = mean, n = n")` |
| **Spaced Columns (Expr)** | Reference via brackets `[col]` or backticks `` `col` `` | `df.pt.mutate(ratio="[bill length mm] / [bill depth mm]")` |
| **Standard Reshape Keys** | `c=` (column), `v=` (value), `a=` (aggregation) | `pt.wide(df, c="metric", v="value", a="mean")` |
