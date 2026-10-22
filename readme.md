# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Fast, ergonomic tabular data manipulation, feature engineering, and visualization powered natively by **Polars** for multithreaded computation and backed by **Pandas & Matplotlib** for plotting across both command-line and Python library.

`pytae` delivers **one and only one obvious way** to work with tabular data:
1. **Unix Pipeline CLI (`pytae`)**: Blazing-fast multithreaded SIMD vector engine sharing the exact same Polars core. Inspect tabular files (`.parquet`, `.csv`, `.tsv`, `.jsonl`, `.sas7bdat`, `.gz`), filter, transform, aggregate, reshape, plot directly in the terminal, and execute ANSI SQL queries with zero boilerplate.
2. **Python Library (`pt.DataFrame` / `df.pt`)**: High-performance tabular data frame backed directly by Polars vector execution. Enter via `pt(pd_df)`, `pt(pl_df)`, `pt.read_parquet("file.parquet")`, or calling `.pt` off any Pandas or Polars DataFrame (`.by()`, `.mutate()`, `.filter()`, `.arrange()`, `.agg()`, `.pivot()`, `.plot()`).

👉 **Quick Links**: [**CLI Cheat Sheet & Cookbook**](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md) | **[vs. Pandas](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_pandas.md)** | **[vs. dplyr](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_dplyr.md)** | **[vs. SAS](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_sas.md)**.

---

## Installation

```bash
pip install pytae              # Polars-native CLI and Python library
pip install "pytae[plot]"       # Includes matplotlib for plotting
```

---

## Quick Start: Command-Line (CLI)

Flags execute from left to right as an in-memory pipeline powered natively by Polars SIMD:

```bash
# 1. Instant zero-cost inspection (reads Parquet headers without loading rows)
pytae penguins.parquet -head 5

# 2. Filter, engineer features, sort, and export to snappy Parquet
pytae penguins.parquet \
  -filter "species == 'Adelie' and body_mass_g > 3500" \
  -mutate "mass_kg = body_mass_g / 1000" \
  -arrange "mass_kg desc" \
  -select "species,island,mass_kg" \
  -o heavy_adelie.parquet

# 3. In-terminal frequency table & ASCII bar visualization
pytae penguins.parquet -freq species -bar

# 4. Instant format conversion (SAS7BDAT to Parquet or CSV)
pytae legacy.sas7bdat -o clean.parquet

# 5. Dataset diff & numeric drift detection between pipelines
pytae yesterday.parquet -diff today.parquet -tol 1e-4

# 6. Stream piping from STDIN
cat data.csv | pytae - -fmt csv -filter "amount > 100" -shape

# 7. Grouped aggregation & ANSI SQL query
pytae penguins.parquet -by species -agg "avg_mass=body_mass_g:mean, total=count"
pytae sales.parquet -sql "select region, sum(revenue) from data group by 1"
```

👉 **CLI Quick Reference**: [**Cheat Sheet & Cookbook (Markdown)**](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md) or run `pytae -cheatsheet` in your terminal! | **Full CLI Command Guide**: [docs/detailed_docs/cli/](https://github.com/maddytae/pytae/tree/master/docs/detailed_docs/cli)

---

## Quick Start: Python & Jupyter SDK

Need the same expressive verbs in Python scripts, Airflow, or Jupyter? `import pytae as pt` gives you the exact same superpowers:

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

## Visualizations & Dashboards (Powered by Pandas & Matplotlib)

Pytae follows a clean, pragmatic architecture: **Compute in Polars, Visualize in Pandas**.

While **Polars** provides multithreaded SIMD speed for filtering, feature engineering, and aggregation, **Pandas** and **Matplotlib** remain the undisputed industry standard for Python data visualization. Calling `.plot()` automatically converts the prepared data into a Pandas DataFrame and delegates directly to `pandas.DataFrame.plot()`—giving you 100% compatibility with all standard plot kinds, styling, and mosaic dashboarding without any manual conversion boilerplate:

```python
import pytae as pt

penguins = pt.sample("penguins")

# 1. Method chaining: compute in Polars, visualize in Pandas
(
    penguins
    .filter("body_mass_g.is_not_null()")
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
- **Column Selection**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/select.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/select.md) (`select`, negative drops `!col`, regex, pattern matches, rename)
- **Row Sorting**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/arrange.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/arrange.md) (`arrange`, `-col`, `desc`, bracketed spaced columns)
- **Row Slicing**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/head_tail.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/head_tail.md) (`arrange` + `head`/`tail`, top/bottom N or proportion per group via `by`, ties)
- **Distinct Rows**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/distinct.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/distinct.md) (`distinct`, deduplication across column subsets, `keep`)
- **Table Reshaping**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/reshape.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/reshape.md) (`long`, `wide`, pure 1-to-1 unmelting, unified `rcva` grammar)
- **Relational Joins & Stacking**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/join.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/join.md) (`df.join()`, `pt.join()`, `pt.concat()`, `-join`, `-concat`, colon keys, `validate`)
- **2D Pivot Tables**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/pivot.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/pivot.md) (`pivot`, `r, c, v, a` matrices, flat 1D headers)
- **Aggregations & Grouping**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/agg.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/agg.md) (`by`, `agg`, `dropna=False` zero data loss retention)
- **Visualizations & Plotting**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/plotting/plotting.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/cli_plots.md) (`df.plot()`, `-plot`, `-finalize`, mosaic dashboards)
- **Utilities & Inspection**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/other_utilities.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/inspect.md) (`fillna`, `dropna`, `rename`, `diff`, `glimpse`, `clean`)
- **In-Pipeline SQL**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/sql.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/sql.md) (`df.sql()`, `pt.sql()`, `-sql` DuckDB/Polars SQL engine)
- **Multi-File Pipelines**: [Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/library/join.ipynb) | [CLI Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/multi_file.md) (`-file`, multi-table pipelines, batch globbing, UNIX pipes)

---

## License

MIT License. See [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE) for details.
