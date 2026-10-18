# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Fast, ergonomic tabular data manipulation, feature engineering, and visualization powered natively by **Polars** for multithreaded computation and backed by **Pandas & Matplotlib** for plotting across both Python library and CLI.

`pytae` offers **one and only one obvious way** to perform tabular operations with zero code duplication:
1. **Python Library (`pt.DataFrame` / `df.pt`)**: High-performance tabular data frame backed directly by Polars vector execution. Enter via `pt(pd_df)`, `pt(pl_df)`, `pt.read_parquet("file.parquet")`, or calling `.pt` off any Pandas or Polars DataFrame. Once entered, chain verbs naturally without repeatedly calling `.pt` (`.by()`, `.mutate()`, `.filter()`, `.arrange()`, `.agg()`, `.pivot()`, `.plot()`).
2. **Unix Pipeline CLI (`pytae`)**: Blazing-fast multithreaded SIMD vector engine sharing the exact same Polars core. Ingests tabular files (`.parquet`, `.csv`, `.tsv`, `.jsonl`, `.sas7bdat`, `.gz`), filters, transforms, aggregates, reshapes, and executes analytical ANSI SQL queries (`-sql`) with zero boilerplate.

👉 **New to Pytae?** Check out the dedicated comparisons: **[vs. Pandas](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_pandas.md)** | **[vs. dplyr](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_dplyr.md)** | **[vs. SAS](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_sas.md)**.

---

## Installation

```bash
pip install pytae              # Polars-native library and CLI
pip install "pytae[plot]"       # Includes matplotlib for plotting
```

---

## Quick Start: Python Library (Polars-Powered)

Read directly with `pt.read_parquet()`, wrap existing data with `pt(df)`, or chain off Pandas via `.pt`:

```python
import pytae as pt

# Read directly with Polars-powered fast auto-detection
df = pt.read_parquet("sales_report.parquet")

# Or chain directly off pandas or polars - only one .pt call needed!
summary = (
    df.filter("amount > 0")
    .by("region")
    .mutate(pct_total="amount / sum(amount)", prev_sale="shift(amount, 1)")
    .arrange("amount desc")
    .to_pandas()  # or .to_polars(), .to_clip()
)
```

👉 **Full Master Documentation Hub**: [docs/pytae.md](https://github.com/maddytae/pytae/blob/master/docs/pytae.md)

---

## Quick Start: CLI (Polars-Powered)

Flags execute from left to right as an in-memory pipeline powered natively by Polars:

```bash
# 1. Zero-cost inspection (reads Parquet headers without loading rows)
pytae penguins.parquet -shape -head 5

# 2. Filter, engineer features, sort, and export
pytae penguins.parquet \
  -filter "species = 'Adelie', body_mass_g > 3500" \
  -mutate "mass_kg = body_mass_g / 1000" \
  -arrange "mass_kg desc" \
  -select "species,island,mass_kg" \
  -o heavy_adelie.csv

# 3. Grouped aggregation & reshaping
pytae penguins.parquet -by species -agg "avg_mass=body_mass_g:mean, total=count"

# 4. Deduplicate rows across key columns
pytae penguins.parquet -distinct "species,island"

# 5. Polars SQL Query
pytae sales.parquet -sql "select region, sum(revenue) from data group by 1"

# 6. Fast dataset comparison
pytae current.parquet -diff baseline.parquet
```

👉 **Full CLI & Library Guides**: [docs/pytae.md#detailed-documentation-directory](https://github.com/maddytae/pytae/blob/master/docs/pytae.md#detailed-documentation-directory)

---

## Visualizations & Dashboards (Powered by Pandas & Matplotlib)

Pytae follows a clean, pragmatic architecture: **Compute in Polars, Visualize in Pandas**.

While **Polars** provides multithreaded SIMD speed for filtering, feature engineering, and aggregation, **Pandas** and **Matplotlib** remain the undisputed industry standard for Python data visualization. Calling `.plot()` automatically converts the prepared data into a Pandas DataFrame and delegates directly to `pandas.DataFrame.plot()`—giving you 100% compatibility with all standard plot kinds, styling, and mosaic dashboarding without any manual conversion boilerplate:

```python
import pytae as pt

penguins = pt.sample("penguins")

# 1. Method chaining: compute in Polars, visualize in Pandas
(
    penguins
    .filter("body_mass_g.notna()")
    .by("species")
    .agg(avg_mass="body_mass_g:mean")
    .plot(kind="bar", x="species", y="avg_mass", title="Average Penguin Mass (g)")
    .finalize(save="mass_by_species.png")
)

# 2. Multi-panel dashboard layouts (pt.Plotter with ASCII mosaics)
plotter = pt.Plotter("""
    AAAB
    AAAC
""", figsize=(12, 6))

plotter.add("A", penguins, kind="scatter", x="bill_length_mm", y="bill_depth_mm", color="species")
plotter.add("B", penguins.by("species").count(), kind="bar", x="species", y="n")
plotter.add("C", penguins, kind="box", y="body_mass_g", by="species")
plotter.finalize(title="Penguin Morphology Dashboard", save="dashboard.png")
```

On the command line, generate distribution charts directly in your terminal or save figures headlessly:
```bash
# In-terminal distribution histogram
pytae penguins.parquet -hist body_mass_g

# Headless plot generation
pytae penguins.parquet -by species -agg "avg_mass=body_mass_g:mean" \
  -plot "kind=bar, x=species, y=avg_mass" -finalize "save=mass.png"
```

👉 **Interactive Plotting Notebook & Guide**: [docs/detailed_docs/plotting/plotting.ipynb](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/plotting/plotting.ipynb)

---

## Documentation Directory

### Guides & Specifications
- **Master Reference & Architecture Hub**: [docs/pytae.md](https://github.com/maddytae/pytae/blob/master/docs/pytae.md)
- **Ecosystem Comparisons & Migration Guides**:
  - [Pytae vs. Pandas Deep Dive](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_pandas.md)
  - [Pytae vs. dplyr Deep Dive](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_dplyr.md)
  - [Pytae vs. SAS Migration Guide](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_sas.md)

### Detailed Topic Guides (`docs/detailed_docs/`)
Comprehensive documentation split into two dedicated folders:
- **`docs/detailed_docs/library/`**: Interactive, fully executed Jupyter Notebooks (`.ipynb`)
- **`docs/detailed_docs/cli/`**: In-depth Command Line Markdown manuals (`.md`)

- **Data Ingestion & Sinks**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/read_write.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/read_write.md) (`pt.read_*`, `pt.scan_*`, `write_*`, `-o`, `-od`, `-fmt`, `-progress`)
- **Feature Engineering**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/mutate.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/mutate.md) (`mutate`, formulas, sequential assignments, `if_else`, `map`, `shift`, `@var`)
- **Row Filtering**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/filter.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/filter.md) (`filter`, intervals, set membership, `or`/`and`, callables, pushdown)
- **Column Selection**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/select.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/select.md) (`select`, negative drops `-col`, regex, pattern matches, rename)
- **Row Sorting**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/arrange.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/arrange.md) (`arrange`, `-col`, `desc`, bracketed spaced columns)
- **Row Slicing**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/head_tail.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/head_tail.md) (`arrange` + `head`/`tail`, top/bottom N or proportion per group via `by`, ties)
- **Distinct Rows**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/distinct.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/distinct.md) (`distinct`, deduplication across column subsets, `keep`)
- **Table Reshaping**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/reshape.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/reshape.md) (`long`, `wide`, pure 1-to-1 unmelting)
- **Relational Joins & Stacking**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/join.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/join.md) (`df.join()`, `pt.join()`, `pt.concat()`, `-join`, `-concat`, colon keys, `validate`)
- **2D Pivot Tables**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/pivot.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/pivot.md) (`pivot`, `r, c, v, a` matrices, flat 1D headers)
- **Aggregations & Grouping**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/agg.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/agg.md) (`by`, `agg`, `dropna=False` zero data loss retention)
- **Visualizations & Plotting**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/plotting/plotting.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/plotting.md) (`df.plot()`, `-plot`, `-finalize`, mosaic dashboards)
- **Utilities & Inspection**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/other_utilities.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/inspect.md) (`fillna`, `dropna`, `rename`, `diff`, `glimpse`, `clean`)
- **In-Pipeline SQL**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/sql.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/sql.md) (`df.sql()`, `pt.sql()`, `-sql` DuckDB/Polars SQL engine)
- **Multi-File Pipelines**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/join.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/multi_file.md) (`-file`, multi-table pipelines, batch globbing, UNIX pipes)

---

## License

MIT License. See [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE) for details.
