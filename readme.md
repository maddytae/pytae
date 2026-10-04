# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Fast, ergonomic Pandas tools and zero-code CLI for tabular data manipulation, feature engineering, DuckDB SQL, and visualization.

`pytae` provides two complementary ways to work with tabular data:
1. **Python Library & DataFrame Accessor (`df.pt`)**: Ergonomic data-science verbs (`qry`, `select`, `mutate`, `agg`, `long`, `wide`, `pivot`, `sql`, `plot`) that compose smoothly with vanilla Pandas.
2. **Unix Pipeline CLI (`pytae`)**: Inspect, filter, derive columns, aggregate, join, diff, and convert tabular files (`.parquet`, `.csv`, `.tsv`, `.jsonl`, `.dat`, `.sas7bdat`, `.gz`) directly from the terminal without writing Python code.

---

## Quick Navigation

- [Installation](#installation)
- [Quick Start: CLI](#quick-start-cli)
- [Quick Start: Python Library](#quick-start-python-library)
- [Key Features](#key-features)
  - [1. Row Filtering (`qry`)](#1-row-filtering-qry)
  - [2. Column Creation & Grouped Window Calculations (`mutate`)](#2-column-creation--grouped-window-calculations-mutate)
  - [3. Column Selection & Exclusion (`select`)](#3-column-selection--exclusion-select)
  - [4. Grouped Aggregation (`agg`)](#4-grouped-aggregation-agg)
  - [5. Pure Reshaping (`long` & `wide`)](#5-pure-reshaping-long--wide)
  - [6. 2D Pivot Tables (`pivot`)](#6-2d-pivot-tables-pivot)
  - [7. Embedded DuckDB SQL Engine (`sql`)](#7-embedded-duckdb-sql-engine-sql)
  - [8. Visualization (`plot`)](#8-visualization-plot)
  - [9. Zero-Cost Metadata Inspection & Diffing](#9-zero-cost-metadata-inspection--diffing)
- [Key Syntax & Conventions Cheat Sheet](#key-syntax--conventions-cheat-sheet)
- [Documentation & Interactive Tutorials](#documentation--interactive-tutorials)
- [License](#license)

---

## Installation

```bash
pip install pytae              # Core library and CLI
pip install "pytae[plot]"       # Includes matplotlib & scipy for plotting
pip install "pytae[sql]"        # Includes DuckDB for SQL queries
pip install "pytae[plot,sql]"   # All optional dependencies
```

---

## Quick Start: CLI

`pytae` commands execute in exact terminal order like a Unix pipeline:

```bash
# 1. Fast inspection: view shape, schema, and first 5 rows without reading full files
pytae penguins.parquet -shape -head 5

# 2. Filter, engineer features, sort, and export to CSV
pytae penguins.parquet \
  -qry "species = 'Adelie', body_mass_g > 3500" \
  -mutate "mass_kg = body_mass_g / 1000, ratio = bill_length_mm / bill_depth_mm" \
  -sort_by "mass_kg desc" \
  -select "species,island,mass_kg,ratio" \
  -o heavy_adelie.csv

# 3. Grouped window calculation: calculate group mean and deviation per row
pytae tips.parquet \
  -by day \
  -mutate "avg_tip = mean(tip), diff = tip - avg_tip, sz = n" \
  -round 2 \
  -head 5

# 4. Grouped aggregation and pivoting
pytae penguins.parquet \
  -by 'island,species' \
  -agg 'avg_mass=body_mass_g:mean, count=n' \
  -wide 'c=species, v=avg_mass' \
  -round 1

# 5. Query any dataset using DuckDB SQL
pytae sales.parquet -sql "select customer_id, sum(total) as revenue from data group by 1 order by 2 desc" -head 10

# 6. Compare schemas and values between two files
pytae current.parquet -diff previous.parquet

# 7. In-line terminal visualizations & ASCII charts
pytae penguins.parquet -freq species
pytae penguins.parquet -hist body_mass_g:10

# 8. Render and export figures directly from the CLI
pytae penguins.parquet -by species -agg "body_mass_g=mean" -plot "kind=bar, x=species, y=body_mass_g" -o mass_chart.png

# 9. Pipe streaming via standard input (STDIN)
cat penguins.csv | pytae - -select "species,island" -value_counts
```

👉 **Full CLI Guide**: [docs/cli.md](https://github.com/maddytae/pytae/blob/master/docs/cli.md) | **Individual Feature Guides**: [docs/cli/](https://github.com/maddytae/pytae/tree/master/docs/cli/)

---

## Quick Start: Python Library

Use verbs as standalone functions (`pt.verb(df, ...)`) or chain them naturally on any DataFrame via the `.pt` accessor (`df.pt.verb(...)`):

```python
import pytae as pt
import pandas as pd

# Load sample dataset
penguins = pt.sample("penguins")

# Clean, expressive pipeline
summary = (
    penguins
    # 1. Row filtering with comparison and intervals
    .pt.qry(species=["Adelie", "Gentoo"], body_mass_g=">= 3500")
    # 2. Grouped window calculation (N -> N)
    .pt.mutate(
        mass_kg="body_mass_g / 1000",
        avg_mass="mean(body_mass_g)",
        diff="body_mass_g - avg_mass",
        by="species",
    )
    # 3. Select columns with negative drop support
    .pt.select("species", "island", "mass_kg", "diff")
    # 4. Grouped aggregation (N -> K)
    .pt.agg(by="species", mean_mass="mass_kg.mean()", count="n")
)

print(summary)
```

👉 **Full Library Guide**: [docs/library.md](https://github.com/maddytae/pytae/blob/master/docs/library.md) | **Interactive Tutorials**: [docs/library/](https://github.com/maddytae/pytae/tree/master/docs/library/)

---

## Key Features

### 1. Row Filtering (`qry`)
Filter rows without boilerplate. Accepts Python keywords, string expressions, and mathematical intervals:
```python
# Keywords, lists, and closed intervals [3000, 4000]
df.pt.qry(species=["Adelie", "Gentoo"], body_mass_g="[3500, 4500]")

# Columns containing spaces use square brackets
df.pt.qry("[bill length mm] > 40")

# Missing value checks
df.pt.qry(sex=("notna",))
```

### 2. Column Creation & Grouped Window Calculations (`mutate`)
Derive columns with Python/Pandas expressions, dplyr-style conditionals (`if_else`, `case_when`, `coalesce`), and grouped window summaries:
```python
# Formulas, vectorized conditionals, and caller-scope variables (@threshold)
threshold = 4000
df.pt.mutate(
    mass_kg="body_mass_g / 1000",
    size_class="if_else(body_mass_g > @threshold, 'Large', 'Normal')",
)

# Grouped window calculations: aggregates evaluate per group and broadcast back (N -> N)
df.pt.mutate(
    avg_mass="mean(body_mass_g)",
    diff="body_mass_g - avg_mass",
    group_size="n",
    by="species",
)
```

### 3. Column Selection & Exclusion (`select`)
Reorder, slice, and filter columns using names, patterns, types, and negative drops:
```python
# Negative selection (drop specific columns)
df.pt.select("-id", "-temp")

# By pattern, dtype, and position
df.pt.select("species", contains="bill", dtypes="numeric")

# Reorder with everything helper
df.pt.select("island", "species", pt.everything)
```

### 4. Grouped Aggregation (`agg`)
Concise group summaries with explicit `by=` grouping, bracket support for spaced names, and automatic row count token `n`:
```python
# Explicit grouping and named aggregations
df.pt.agg(by="species", avg_mass="body_mass_g.mean()", n="n")

# String mapping specification (perfect for spaced columns)
df.pt.agg("island", "[avg mass] = [body mass g]:mean, n = n")
```

### 5. Pure Reshaping (`long` & `wide`)
Clean, deterministic unpivoting (melting) and spreading without MultiIndex complexity:
```python
# 1. Unpivot non-numeric columns into key-value pairs
long_df = df.pt.long(id_vars=["species", "island"], cols=["bill_length_mm", "bill_depth_mm"])

# 2. Pure reshape back to wide presentation matrix
wide_df = long_df.pt.wide(c="variable", v="value")
```

### 6. 2D Pivot Tables (`pivot`)
Excel-style 2D pivot tables with automatic index reset and flat 1D columns:
```python
# 2D grid summarizing average body mass across island and species
pivot_df = df.pt.pivot(r="island", c="species", v="body_mass_g", a="mean")

# Frequency matrix (count rows across dimensions; v is optional for a="n")
freq_matrix = df.pt.pivot(r="island", c="species", a="n")
```

### 7. Embedded DuckDB SQL Engine (`sql`)
Run analytical SQL directly on any Pandas DataFrame with zero copy:
```python
result = df.pt.sql("""
    select species, count(*) as total, round(avg(body_mass_g), 1) as avg_mass
    from data
    where body_mass_g is not null
    group by 1
    order by avg_mass desc
""")
```

### 8. Visualization (`plot`)
Method-chainable charting powered by Matplotlib (`pip install "pytae[plot]"`):
```python
# Direct accessor chaining:
penguins.pt.plot(
    kind="scatter",
    x="bill_length_mm",
    y="bill_depth_mm",
    c="species",
    cmap="viridis",
    title="Penguin Bill Dimensions",
).pt.finalize()

# One-shot direct file export (no explicit finalize required):
penguins.pt.agg("species", body_mass_g="mean").pt.plot(kind="bar", x="species", y="body_mass_g").save("mass.png")
```

### 9. Zero-Cost Metadata Inspection & Diffing
Inspect large Parquet, CSV, and SAS datasets instantly without loading millions of rows into memory:
```bash
# Instant shape, columns, and types from Parquet file headers
pytae large_dataset.parquet -shape -cols -meta

# Compare schemas, null counts, and value differences across datasets
pytae current.parquet -diff previous.parquet
```

---

## Key Syntax & Conventions Cheat Sheet

| Task | Python Library (`df.pt`) | CLI Flag | Example |
| :--- | :--- | :--- | :--- |
| **Row Filtering** | `.pt.qry(...)` | `-qry "..."` | `df.pt.qry(species="Adelie", mass="> 3500")` |
| **Spaced Columns (Expr)** | `[column name]` | `[column name]` | `df.pt.mutate(ratio="[bill length mm] / [bill depth mm]")` |
| **Grouped Window Calc** | `.pt.mutate(..., by=...)` | `-by ... -mutate "..."` | `pytae data.parquet -by dept -mutate "avg=mean(salary)"` |
| **Negative Column Select** | `.pt.select("-col1", "-col2")` | `-select "-col1,-col2"` | `df.pt.select("-temp", "-raw_id")` |
| **2D Pivot Table** | `.pt.pivot(...)` | `-pivot "..."` | `df.pt.pivot(r="Region", c="Year", v="Sales", a="sum")` |
| **Data Reshaping** | `.pt.long()`, `.pt.wide()` | `-long`, `-wide` | `df.pt.wide(c="metric", v="val")` |
| **In-Line Terminal Charts** | N/A | `-freq`, `-hist` | `pytae data.parquet -freq species` / `-hist mass:10` |
| **Figure Plotting & Export** | `.pt.plot(..., save=...)` | `-plot "..." -o ...` | `pytae data.parquet -plot "kind=bar, x=sp, y=wt" -o out.png` |
| **DuckDB SQL Query** | `.pt.sql("select ...")` | `-sql "select ..."` | `pytae data.parquet -sql "select * from data limit 5"` |
| **Pipe / STDIN Stream** | N/A | `pytae - [-fmt ...]` | `cat data.csv \| pytae - -head 5` |
| **Copy to Clipboard** | `df.to_clip()` | `-o clip` | `df.head().to_clip()` vs `pytae data.parquet -head -o clip` |
| **File Export & Routing** | `df.to_parquet(...)` | `-o <target.ext>` | `pytae data.parquet -o clean.csv.gz -od ./exports` |
| **Dataset Diffing** | N/A | `-diff <other_file>` | `pytae data.parquet -diff old_data.parquet` |

---

## Documentation & Interactive Tutorials

### CLI Documentation (`docs/cli/`)
- [CLI Reference Hub](https://github.com/maddytae/pytae/blob/master/docs/cli.md) — Master flag guide, execution pipeline, and syntax rules
- [Aggregation Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/aggregate.md) — `-by`, `-agg`, and group frequency counts
- [Mutation Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/mutate.md) — Feature engineering, math, and grouped window formulas
- [Filtering Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/filter.md) — Numerical comparisons, string matching, and intervals
- [Selection Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/select.md) — Column slicing, dtypes, and negative exclusion
- [Pure Reshaping Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/reshape.md) — Long-to-wide and wide-to-long pure reshapes (`-long`, `-wide`)
- [2D Pivot Tables Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/pivot.md) — Excel-style 2D pivot tables with automatic index reset (`-pivot`)
- [Visualizations & Plotting Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/plotting.md) — In-line terminal charts (`-freq`, `-hist`) and figure export (`-plot`)
- [Export & Output Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/export_io.md) — `-o`, `-od`, compression, and clipboard routing
- [Dataset Diff Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/diff.md) — Comparing schemas and records
- [Multi-File Operations](https://github.com/maddytae/pytae/blob/master/docs/cli/multi_file.md) — `-file`, `-merge`, and `-concat`
- [SQL Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/sql.md) — Querying with embedded DuckDB
- [Metadata & Inspection Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/inspect.md) — `-shape`, `-cols`, `-meta`, and zero-cost header inspection
- [Cleaning & Replacement Guide](https://github.com/maddytae/pytae/blob/master/docs/cli/clean_replace.md) — `-clean_columns` and `-replace_values`

### Interactive Jupyter Notebooks (`docs/library/`)
Each core module has a standalone, fully runnable tutorial with live outputs:
- **Filtering**: [`docs/library/qry.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/qry.ipynb)
- **Selection**: [`docs/library/select.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/select.ipynb)
- **Feature Engineering & Window Mutations**: [`docs/library/mutate.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/mutate.ipynb)
- **Aggregation**: [`docs/library/agg.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/agg.ipynb)
- **Pure Reshaping**: [`docs/library/reshape.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/reshape.ipynb)
- **2D Pivot Tables**: [`docs/library/pivot.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/pivot.ipynb)
- **DuckDB SQL**: [`docs/library/sql.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/sql.ipynb)
- **Plotting & Dashboards**: [`docs/library/plotting.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/plotting.ipynb)
- **Utilities & Cleaning**: [`docs/library/other_utilities.ipynb`](https://github.com/maddytae/pytae/blob/master/docs/library/other_utilities.ipynb)

---

## License

MIT License. See [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE) for details.
