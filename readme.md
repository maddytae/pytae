# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](https://github.com/maddytae/pytae/blob/master/LICENSE)

Fast, ergonomic tabular data manipulation, feature engineering, and visualization powered natively by **Polars** for multithreaded SIMD vector computation and backed by **Pandas & Matplotlib** for plotting across command-line, interactive shell, and Python library.

`pytae` provides **one and only one obvious way** to work with tabular data across three unified modalities:

1. **Unix Pipeline CLI (`pytae`)**: Fast one-shot command-line data processing, format conversion, and terminal visualizations.
2. **Interactive REPL Shell (`pytae -i`)**: Stateful in-memory workbench with $O(1)$ pointer-reassignment undo/redo, multi-table joins, and ANSI SQL.
3. **Python & Jupyter SDK (`pt.DataFrame` / `df.pt`)**: High-performance Polars-native DataFrame library with `.pt` accessor for pandas/polars DataFrames.

👉 **Quick Links**: [**CLI Cheat Sheet & Cookbook**](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md) | [**Interactive REPL Guide**](https://github.com/maddytae/pytae/blob/master/docs/repl.md) | [**Standalone Binaries (Zero-Python)**](docs/binary_distribution.md) | [**Master Reference & Architecture Hub**](https://github.com/maddytae/pytae/blob/master/docs/pytae.md) | [**vs. Pandas**](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_pandas.md) | [**vs. dplyr**](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_dplyr.md) | [**vs. SAS**](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_sas.md)

---

## Installation

### Option 1: Standalone Portable Binary (Zero Python Required)
For locked-down corporate laptops, air-gapped environments, or instant setup without installing Python, download the single-file executable from [GitHub Releases](https://github.com/maddytae/pytae/releases):
- **Windows**: `pytae-windows-x64.zip` (Fast pre-extracted folder bundle)
- **macOS**: `pytae-macos-arm64` (Apple Silicon) or `pytae-macos-x86_64` (Intel)
- **Linux**: `pytae-linux-x86_64`

See [Standalone Binary Distribution](docs/binary_distribution.md) for details.

### Option 2: Via Python Package Managers
```bash
pip install pytae              # Polars-native CLI, REPL, and Python library
pip install "pytae[plot]"       # Includes matplotlib for plotting & dashboards
```

---

## Interactive REPL Shell (`pytae -i`)

Instead of re-reading multi-gigabyte files from disk on every command, the **Pytae REPL** loads datasets into memory **once** and provides an instantaneous interactive workbench with zero syntax bloat:

```bash
# Mode 1: Pre-load a dataset into the interactive shell
pytae penguins.parquet -i

# Mode 2: Launch an empty workbench (load multiple datasets on the fly)
pytae -i
```

### Mode 1: Single-Table Exploration (`pytae <file> -i`)
Operate directly on the loaded table with zero prefixing:
```text
pytae [penguins.parquet: 344x7]> -filter "species in ['Adelie', 'Gentoo'] and body_mass_g >= 3500"
-> penguins.parquet: 188 rows x 7 cols

pytae [penguins.parquet: 188x7]> -mutate "mass_kg = body_mass_g / 1000" -select "species,island,mass_kg"
-> penguins.parquet: 188 rows x 3 cols

# Non-destructive inspection (does not truncate active data)
pytae [penguins.parquet: 188x3]> -head 3
pytae [penguins.parquet: 188x3]> -shape

# Instant $O(1)$ rollback & snapshots
pytae> undo                      # Revert last step
pytae> checkpoint baseline       # Save named snapshot
pytae> restore baseline          # Revert to snapshot
```

### Mode 2: Multi-Table Workbench (`pytae -i`)
Load multiple datasets and operate with clean **subject-first commands (`<tbl> -<cmd>`)**:
```text
pytae> df1 = orders.parquet
pytae> df2 = customers.parquet

# Subject-first inspection & transformations
pytae [df1, df2]> df1 -head 5
pytae [df1, df2]> df1 -filter "amount > 100"

# Multi-table joins & ANSI SQL
pytae [df1, df2]> df3 = df1 -join df2 on=cust_id
pytae [df1, df2, df3]> df4 = -sql "SELECT df1.order_id, df2.name FROM df1 JOIN df2 ON df1.cust_id = df2.id"

# Export specific table
pytae [df1, df2, df3, df4]> df3 -o merged_orders.parquet
```

> [!TIP]
> **Clean Terminal (Model 2)**: Operations output concise shape confirmations (e.g. `-> df1: 10,000 rows x 3 cols` or `df1: 344 rows x 7 cols`) without dumping full tables. To inspect rows, explicitly run `-head [N]`.

👉 **Read the Full REPL Manual**: [Interactive REPL Guide](https://github.com/maddytae/pytae/blob/master/docs/repl.md)

---

## Quick Start: Command-Line (CLI)

Flags execute from left to right as an in-memory pipeline powered natively by Polars multithreading:

```bash
# 1. Zero-cost inspection (reads headers without loading rows)
pytae penguins.parquet -head 5

# 2. In-memory pipeline: filter, engineer features, sort, and export
pytae penguins.parquet \
  -filter "species == 'Adelie' and body_mass_g > 3500" \
  -mutate "mass_kg = body_mass_g / 1000" \
  -arrange "mass_kg desc" \
  -select "species,island,mass_kg" \
  -o heavy_adelie.parquet

# 3. Frequency tables, terminal ASCII visualizations & ANSI SQL
pytae penguins.parquet -freq species -bar
pytae sales.parquet -sql "SELECT region, sum(revenue) FROM data GROUP BY 1"

# 4. Instant format conversion & dataset diff
pytae legacy.sas7bdat -o clean.parquet
pytae yesterday.parquet -diff today.parquet -tol 1e-4

# 5. Sensitive PII masking and encryption
pytae users.csv -mask "email=hash, ssn=encrypt" -key "SecretKey123" -o secure.parquet
```

👉 **CLI Quick Reference**: [**Cheat Sheet & Cookbook**](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md) or run `pytae -cheatsheet` in your terminal! | **Full CLI Manuals**: [docs/detailed_docs/cli/](https://github.com/maddytae/pytae/tree/master/docs/detailed_docs/cli/)

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

### Visualizations & Dashboards (Compute in Polars, Visualize in Pandas)

While **Polars** provides multithreaded SIMD speed for transformations, **Pandas** and **Matplotlib** provide the richest visualization ecosystem. Calling `.plot()` automatically converts prepared data into Pandas and delegates directly to `pandas.DataFrame.plot()`:

```python
import pytae as pt

penguins = pt.sample("penguins")

# 1. Fluent method chaining
(
    penguins
    .filter("body_mass_g.is_not_null()")
    .by("species")
    .agg(avg_mass="body_mass_g:mean")
    .plot(kind="bar", x="species", y="avg_mass", title="Average Penguin Mass (g)")
    .finalize(save="mass_by_species.png")
)

# 2. Multi-panel dashboard layouts with pt.Plotter
plotter = pt.Plotter("""
    AAAB
    AAAC
""", figsize=(12, 6))

plotter.add("A", penguins, kind="scatter", x="bill_length_mm", y="bill_depth_mm", color="species")
plotter.add("B", penguins.by("species").count(), kind="bar", x="species", y="n")
plotter.add("C", penguins, kind="box", y="body_mass_g", by="species")
plotter.finalize(title="Penguin Morphology Dashboard", save="dashboard.png")
```

👉 **Plotting Guide**: [Plotting Notebook](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/plotting/plotting.ipynb) | [CLI Plotting Guide](https://github.com/maddytae/pytae/blob/master/docs/detailed_docs/cli/cli_plots.md)

---

## Documentation Directory

### Architecture & Comparisons
- **Master Reference & Architecture Hub**: [docs/pytae.md](https://github.com/maddytae/pytae/blob/master/docs/pytae.md)
- **Ecosystem Comparisons**: [vs. Pandas](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_pandas.md) | [vs. dplyr](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_dplyr.md) | [vs. SAS](https://github.com/maddytae/pytae/blob/master/docs/comparison_to_sas.md)
- **Interactive Shell Manual**: [Interactive REPL Guide](https://github.com/maddytae/pytae/blob/master/docs/repl.md)
- **Command-Line Quick Reference**: [CLI Cheat Sheet & Cookbook](https://github.com/maddytae/pytae/blob/master/docs/cli_cheatsheet.md)


## License

MIT License. See [LICENSE](https://github.com/maddytae/pytae/blob/master/LICENSE) for details.
