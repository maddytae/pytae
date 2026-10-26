# pytae

[![PyPI](https://img.shields.io/pypi/v/pytae.svg)](https://pypi.org/project/pytae/)
[![Python](https://img.shields.io/pypi/pyversions/pytae.svg)](https://pypi.org/project/pytae/)
[![CI](https://github.com/maddytae/pytae/actions/workflows/ci.yml/badge.svg)](https://github.com/maddytae/pytae/actions/workflows/ci.yml)
[![License](https://img.shields.io/pypi/l/pytae.svg)](LICENSE)

Fast, ergonomic tabular data manipulation, feature engineering, and visualization powered natively by **Polars** for multithreaded SIMD vector computation and backed by **Pandas & Matplotlib** for plotting across command-line, interactive shell, and Python library.

`pytae` provides **one and only one obvious way** to work with tabular data across three unified modalities:

1. **Unix Pipeline CLI (`pytae`)**: Fast one-shot command-line data processing, format conversion, and terminal visualizations.
2. **Interactive REPL Shell (`pytae -i`)**: Stateful in-memory workbench with $O(1)$ pointer-reassignment undo/redo, multi-table joins, and ANSI SQL.
3. **Python & Jupyter SDK (`pt.DataFrame` / `df.pt`)**: High-performance Polars-native DataFrame library with `.pt` accessor for pandas/polars DataFrames.

👉 **Quick Links**: [**CLI Cheat Sheet & Cookbook**](docs/cli_cheatsheet.md) | [**Interactive REPL Guide**](docs/detailed_docs/cli/repl.md) | [**Master Reference & Architecture Hub**](docs/pytae.md) | [**vs. Pandas**](docs/comparison_to_pandas.md) | [**vs. dplyr**](docs/comparison_to_dplyr.md) | [**vs. SAS**](docs/comparison_to_sas.md)

---

## Installation

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

👉 **Read the Full REPL Manual**: [docs/detailed_docs/cli/repl.md](docs/detailed_docs/cli/repl.md)

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

👉 **CLI Quick Reference**: [**Cheat Sheet & Cookbook**](docs/cli_cheatsheet.md) or run `pytae -cheatsheet` in your terminal! | **Full CLI Manuals**: [docs/detailed_docs/cli/](docs/detailed_docs/cli/)

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

👉 **Plotting Guide**: [docs/detailed_docs/plotting/plotting.ipynb](docs/detailed_docs/plotting/plotting.ipynb) | [CLI Plotting Guide](docs/detailed_docs/cli/cli_plots.md)

---

## Documentation Directory

### Architecture & Comparisons
- **Master Reference & Architecture Hub**: [docs/pytae.md](docs/pytae.md)
- **Ecosystem Comparisons**: [vs. Pandas](docs/comparison_to_pandas.md) | [vs. dplyr](docs/comparison_to_dplyr.md) | [vs. SAS](docs/comparison_to_sas.md)
- **Interactive Shell Manual**: [Interactive REPL Guide](docs/detailed_docs/cli/repl.md)
- **Command-Line Quick Reference**: [CLI Cheat Sheet & Cookbook](docs/cli_cheatsheet.md)

### Detailed Topic Guides (`docs/detailed_docs/`)

| Topic | Jupyter Notebook (`docs/detailed_docs/library/`) | CLI Guide (`docs/detailed_docs/cli/`) | Key Features / Verbs |
|---|---|---|---|
| **Interactive REPL** | — | [CLI Guide](docs/detailed_docs/cli/repl.md) | `pytae -i`, `df1 = file`, `-head`, `undo`, `checkpoint`, `-sql` |
| **Data Ingestion & Sinks** | [Notebook](docs/detailed_docs/library/read_write.ipynb) | [CLI Guide](docs/detailed_docs/cli/read_write.md) | `pt.read_*`, `pt.scan_*`, `-o`, `-out_dir`, `-dlim`, `-encoding` |
| **Row Filtering** | [Notebook](docs/detailed_docs/library/filter.ipynb) | [CLI Guide](docs/detailed_docs/cli/filter.md) | `filter`, `-filter`, intervals, set membership, `and`/`or` |
| **Feature Engineering** | [Notebook](docs/detailed_docs/library/mutate.ipynb) | [CLI Guide](docs/detailed_docs/cli/mutate.md) | `mutate`, `-mutate`, formulas, sequential assignments, `map`, `if_else` |
| **Column Selection** | [Notebook](docs/detailed_docs/library/select.ipynb) | [CLI Guide](docs/detailed_docs/cli/select.md) | `select`, `-select`, negative drops `!col`, regex, pattern matches |
| **Row Sorting** | [Notebook](docs/detailed_docs/library/arrange.ipynb) | [CLI Guide](docs/detailed_docs/cli/arrange.md) | `arrange`, `-arrange`, `desc`, bracketed spaced columns |
| **Row Slicing** | [Notebook](docs/detailed_docs/library/head_tail.ipynb) | [CLI Guide](docs/detailed_docs/cli/head_tail.md) | `head`, `tail`, `-head`, `-tail`, top/bottom N or % per group |
| **Distinct Rows** | [Notebook](docs/detailed_docs/library/distinct.ipynb) | [CLI Guide](docs/detailed_docs/cli/distinct.md) | `distinct`, `-distinct`, deduplication across column subsets |
| **Aggregations & Grouping** | [Notebook](docs/detailed_docs/library/agg.ipynb) | [CLI Guide](docs/detailed_docs/cli/agg.md) | `by`, `agg`, `-by`, `-agg`, zero data loss retention |
| **Relational Joins & Stacking**| [Notebook](docs/detailed_docs/library/join.ipynb) | [CLI Guide](docs/detailed_docs/cli/join.md) | `join`, `concat`, `-join`, `-concat`, colon keys `on=k1:k2`, `how` |
| **Table Reshaping** | [Notebook](docs/detailed_docs/library/reshape.ipynb) | [CLI Guide](docs/detailed_docs/cli/reshape.md) | `long`, `wide`, `-long`, `-wide`, 1-to-1 unmelting, `rcva` grammar |
| **2D Pivot Tables** | [Notebook](docs/detailed_docs/library/pivot.ipynb) | [CLI Guide](docs/detailed_docs/cli/pivot.md) | `pivot`, `-pivot`, `r, c, v, a` matrices, flat 1D headers |
| **Visualizations & Plotting** | [Notebook](docs/detailed_docs/plotting/plotting.ipynb) | [CLI Guide](docs/detailed_docs/cli/cli_plots.md) | `df.plot()`, `-plot`, `-finalize`, mosaic dashboards, `-freq`, `-hist`, `-bar` |
| **ANSI SQL Engine** | [Notebook](docs/detailed_docs/library/sql.ipynb) | [CLI Guide](docs/detailed_docs/cli/sql.md) | `df.sql()`, `pt.sql()`, `-sql` Polars SQL engine across tables |
| **Data Masking & Privacy** | [Notebook](docs/detailed_docs/library/other_utilities.ipynb) | [CLI Guide](docs/detailed_docs/cli/mask.md) | `mask`, `unmask`, `-mask`, `-unmask`, hash, salt, encrypt, redact |
| **Dataset Inspection & Diff** | [Notebook](docs/detailed_docs/library/other_utilities.ipynb) | [CLI Guide](docs/detailed_docs/cli/inspect.md) | `fillna`, `dropna`, `diff`, `-diff`, `-tol`, `-shape`, `-cols`, `-dtype` |
| **Multi-File & Batch Pipelines**| [Notebook](docs/detailed_docs/library/join.ipynb) | [CLI Guide](docs/detailed_docs/cli/multi_file.md) | `-file`, multi-table pipelines, batch globbing, UNIX pipes |

---

## License

MIT License. See [LICENSE](LICENSE) for details.
